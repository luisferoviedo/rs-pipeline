"""Verificación de C05, C06 y C08 en 20 informes: Luis Fer frente a Claude (D51).

Cruza V (hoja de 20) → id real → T (hoja de 196), toma los códigos de Claude del libro
v3 (logs/codificacion_claude.jsonl) y los compara con los de Luis Fer
(outputs/semantico/codigos_luisfer_presencia_20.csv). Por criterio calcula % de acuerdo,
kappa de Cohen y AC1 de Gwet con IC 95 % por bootstrap de informes, y la prevalencia de
cada codificador (la lógica de cálculo es la de confiabilidad_40.py).
Veredicto por criterio: AC1 >= 0,60 → validado; si no, se prepara la adjudicación.
A git van solo los números; las listas con la justificación de Claude quedan en
outputs/semantico (ignorada). Falla (código 1) si falta un archivo, un informe de los
20 no está entre los 196, o un código no es 0 ni 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from rs_pipeline import semantico_04 as S
from rs_pipeline.codificacion_claude import (
    RAIZ_REPO,
    RUTA_LOG,
    leer_registro,
    ultimas_por_informe,
)
from rs_pipeline.confiabilidad_40 import (
    AC1_CONFIABLE,
    BINARIAS,
    REMUESTREOS,
    SEMILLA,
    fila_presencia,
)
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

VERIFICADOS = ["C05", "C06", "C08"]
ARCHIVO_LUIS = "codigos_luisfer_presencia_20.csv"
CORRESPONDENCIA_20 = "hoja_codificacion_presencia_20_correspondencia.csv"
CORRESPONDENCIA_196 = "hoja_codificacion_196_correspondencia.csv"
LIBRO = "libro_codigos_v3.yaml"
N_VERIFICACION = 20
N_TOTAL = 196
DESACUERDOS = "desacuerdos_presencia_20_luisfer_claude.csv"
ADJUDICACION = "adjudicacion_presencia_20.csv"


def _leer(ruta: Path, columnas: list[str], claves: list[str]) -> pd.DataFrame:
    if not ruta.is_file():
        fallar(f"Falta {ruta.name}")
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    faltan = [c for c in columnas if c not in tabla.columns]
    if faltan:
        fallar(f"{ruta.name} no trae las columnas {faltan}")
    for clave in claves:
        if tabla[clave].duplicated().any():
            fallar(f"{ruta.name} repite valores de {clave}")
    return tabla


def cruzar_ids(corr20: pd.DataFrame, corr196: pd.DataFrame) -> dict[str, str]:
    """V → id real → T. Falla si alguno de los 20 no está entre los 196."""
    if len(corr20) != N_VERIFICACION or len(corr196) != N_TOTAL:
        fallar(f"Se esperaban {N_VERIFICACION} y {N_TOTAL} informes en las hojas")
    por_id = corr196.set_index("id")["id_ciego"]
    fuera = sorted(set(corr20["id"]) - set(por_id.index))
    if fuera:
        fallar(
            f"{len(fuera)} informes de la muestra de 20 no están entre los 196: {fuera}"
        )
    return {v: por_id[i] for v, i in zip(corr20["id_ciego"], corr20["id"], strict=True)}


def leer_luis(carpeta: Path) -> pd.DataFrame:
    tabla = _leer(carpeta / ARCHIVO_LUIS, ["id_ciego", *VERIFICADOS], ["id_ciego"])
    if any(v not in {"0", "1"} for v in tabla[VERIFICADOS].to_numpy().ravel()):
        fallar(f"{ARCHIVO_LUIS} tiene un código que no es 0 ni 1")
    return tabla.set_index("id_ciego")


def calcular(params: dict) -> dict:
    carpeta = RAIZ_REPO / params["semantico"]["salidas"]
    corr20 = _leer(carpeta / CORRESPONDENCIA_20, ["id_ciego", "id"], ["id_ciego", "id"])
    corr196 = _leer(
        carpeta / CORRESPONDENCIA_196, ["id_ciego", "id"], ["id_ciego", "id"]
    )
    cruce = cruzar_ids(corr20, corr196)
    luis = leer_luis(carpeta)
    if sorted(luis.index) != sorted(cruce):
        fallar(f"{ARCHIVO_LUIS} no trae exactamente los {N_VERIFICACION} informes V")
    libro = RAIZ_REPO / "config" / LIBRO
    if not libro.is_file():
        fallar(f"No existe {libro.name}")
    claude = ultimas_por_informe(leer_registro(), S.sha256(libro))
    if set(claude) != set(corr196["id_ciego"]):
        fallar(f"El registro no trae los {N_TOTAL} informes T con el libro v3")
    ids = sorted(cruce)
    codigos = {
        c: (
            [int(luis.loc[i, c]) for i in ids],
            [claude[cruce[i]]["codigos"][c] for i in ids],
        )
        for c in VERIFICADOS
    }
    if any(y not in BINARIAS for c in VERIFICADOS for y in codigos[c][1]):
        fallar("Claude tiene un código que no es 0 ni 1 en C05, C06 o C08")
    idx = np.random.default_rng(SEMILLA).integers(
        0, len(ids), size=(REMUESTREOS, len(ids))
    )
    filas = []
    for c in VERIFICADOS:
        fila = fila_presencia(c, *codigos[c], idx)
        fila["veredicto"] = "validado" if fila["ac1_ge_060"] else "adjudicar"
        filas.append(fila)
    desacuerdos = [
        {
            "id_ciego": i,
            "criterio": c,
            "codigo_luisfer": x,
            "codigo_claude": y,
            "justificacion_claude": claude[cruce[i]]["justificaciones"][c],
        }
        for c in VERIFICADOS
        for i, x, y in zip(ids, *codigos[c], strict=True)
        if x != y
    ]
    return {
        "tabla": pd.DataFrame(filas),
        "desacuerdos": desacuerdos,
        "entradas": [
            carpeta / ARCHIVO_LUIS,
            carpeta / CORRESPONDENCIA_20,
            carpeta / CORRESPONDENCIA_196,
            libro,
            RUTA_LOG,
        ],
        "modelos": sorted({r["modelo"] for r in claude.values()}),
        "n": len(ids),
    }


def _sentido(desacuerdos: pd.DataFrame, criterio: str) -> dict:
    d = desacuerdos[desacuerdos["criterio"] == criterio]
    return {
        "luis_1_claude_0": int(
            ((d["codigo_luisfer"] == 1) & (d["codigo_claude"] == 0)).sum()
        ),
        "luis_0_claude_1": int(
            ((d["codigo_luisfer"] == 0) & (d["codigo_claude"] == 1)).sum()
        ),
    }


def guardar(params: dict, r: dict) -> None:
    carpeta = RAIZ_REPO / params["salidas"]["tablas"]
    ruta_csv = carpeta / "verificacion_presencia_20.csv"
    r["tabla"].to_csv(ruta_csv, index=False, lineterminator="\n")
    desacuerdos = pd.DataFrame(
        r["desacuerdos"],
        columns=[
            "id_ciego",
            "criterio",
            "codigo_luisfer",
            "codigo_claude",
            "justificacion_claude",
        ],
    )
    filas = r["tabla"].set_index("criterio")
    traza = {
        "nota": "D51: Luis Fer codificó C05, C06 y C08 a ciegas en 20 informes nuevos; "
        "Claude los codificó con el libro v3 dentro de los 196.",
        "n_informes": r["n"],
        "kappa": "Cohen sin pesos sobre presencia 0/1",
        "ac1": "AC1 de Gwet sobre presencia 0/1",
        "ic": f"bootstrap por informe, {REMUESTREOS} remuestreos, semilla {SEMILLA}, "
        "percentiles 2,5 y 97,5 (los mismos remuestreos para todas las filas)",
        "umbral_ac1_validado": AC1_CONFIABLE,
        "criterios_validados": [c for c in VERIFICADOS if filas.loc[c, "ac1_ge_060"]],
        "criterios_a_adjudicar": [
            c for c in VERIFICADOS if not filas.loc[c, "ac1_ge_060"]
        ],
        "sentido_de_los_desacuerdos": {
            c: _sentido(desacuerdos, c) for c in VERIFICADOS
        },
        "modelos": r["modelos"],
        "entradas": [{"archivo": p.name, "sha256": S.sha256(p)} for p in r["entradas"]],
        "salida": {"archivo": ruta_csv.name, "sha256": S.sha256(ruta_csv)},
    }
    (carpeta / "verificacion_presencia_20.json").write_text(
        json.dumps(traza, ensure_ascii=False, indent=2, default=bool) + "\n",
        encoding="utf-8",
    )
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    salida = dict(encoding="utf-8-sig", lineterminator="\n", index=False)
    desacuerdos.to_csv(privada / DESACUERDOS, **salida)
    guardar_hoja_adjudicacion(privada / ADJUDICACION, desacuerdos, traza)


def guardar_hoja_adjudicacion(
    ruta: Path, desacuerdos: pd.DataFrame, traza: dict
) -> None:
    """Hoja para que Luis Fer decida el código final; no pisa una hoja ya decidida."""
    if ruta.is_file():
        previa = pd.read_csv(
            ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
        if (previa.get("codigo_final", pd.Series(dtype=str)) != "").any():
            fallar(f"{ruta.name} ya tiene códigos finales; no se sobrescribe")
    hoja = desacuerdos[
        desacuerdos["criterio"].isin(traza["criterios_a_adjudicar"])
    ].copy()
    hoja["codigo_final"] = ""
    hoja.to_csv(ruta, index=False, encoding="utf-8-sig", lineterminator="\n")


def main() -> int:
    try:
        params = S.cargar_params()
        resultado = calcular(params)
        guardar(params, resultado)
        print(resultado["tabla"].to_string(index=False))
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
