"""Confiabilidad de la muestra de 40 (D48): Luis Fer frente a Claude.

Compara, con el libro v2, los códigos de Luis Fer
(outputs/semantico/codigos_luisfer_40.csv) con los de Claude
(logs/codificacion_claude.jsonl). Por criterio y en total calcula el
acuerdo exacto, el kappa ponderado cuadrático, el AC1 de Gwet y la distribución de
códigos de cada codificador. El IC del kappa total sale de un bootstrap por informe.
A git van solo los números (outputs/tablas/confiabilidad_40.csv y .json); la lista de
desacuerdos, con la justificación de Claude, queda en outputs/semantico (ignorada).
Falla (código 1) si falta un archivo, un informe o un código no es 0, 1 o 2.
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np
import pandas as pd

from rs_pipeline import semantico_04 as S
from rs_pipeline.codificacion_claude import (
    CATEGORIAS,
    CRITERIOS,
    RAIZ_REPO,
    kappa_ponderado,
    leer_registro,
    ultimas_por_informe,
)
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

ARCHIVO_LUIS = "codigos_luisfer_40.csv"
LIBRO = "libro_codigos_v2.yaml"
REMUESTREOS = 5000
SEMILLA = 20261101
UMBRAL_ALTO = 0.60
UMBRAL_BAJO = 0.40


def ac1_gwet(a: list[int], b: list[int]) -> float:
    """AC1 de Gwet para dos codificadores y categorías 0-1-2.

    Si todos los códigos caen en una sola categoría, pe = 0 y el AC1 vale 1.
    """
    n = len(a)
    q = len(CATEGORIAS)
    acuerdo = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pi = [(a.count(c) + b.count(c)) / (2 * n) for c in CATEGORIAS]
    esperado = sum(p * (1 - p) for p in pi) / (q - 1)
    return (acuerdo - esperado) / (1 - esperado)


def veredicto(kappa: float) -> str:
    if kappa >= UMBRAL_ALTO:
        return "kappa total >= 0,60: Claude codifica los 156 restantes con el libro v2"
    if kappa >= UMBRAL_BAJO:
        return "kappa total entre 0,40 y 0,60: revisar los criterios con kappa bajo"
    return "kappa total < 0,40: se replantea el libro"


def leer_luis(params: dict) -> pd.DataFrame:
    ruta = RAIZ_REPO / params["semantico"]["salidas"] / ARCHIVO_LUIS
    if not ruta.is_file():
        fallar(f"Falta {ruta.name}")
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    faltan = [c for c in ["id_ciego", *CRITERIOS] if c not in tabla.columns]
    if faltan:
        fallar(f"{ARCHIVO_LUIS} no trae las columnas {faltan}")
    if tabla["id_ciego"].duplicated().any():
        fallar(f"{ARCHIVO_LUIS} repite informes")
    if any(v not in {"0", "1", "2"} for v in tabla[CRITERIOS].to_numpy().ravel()):
        fallar(f"{ARCHIVO_LUIS} tiene un código que no es 0, 1 ni 2")
    return tabla


def codigos_por_criterio(luis: pd.DataFrame, claude: dict[str, dict], ids: list[str]):
    por_id = luis.set_index("id_ciego")
    return {
        c: (
            [int(por_id.loc[i, c]) for i in ids],
            [claude[i]["codigos"][c] for i in ids],
        )
        for c in CRITERIOS
    }


def kappa_total_bootstrap(codigos: dict, n: int) -> tuple[float, float, int]:
    """IC 95 % (percentiles) del kappa total, remuestreando informes completos."""
    a = np.array([codigos[c][0] for c in CRITERIOS])
    b = np.array([codigos[c][1] for c in CRITERIOS])
    azar = np.random.default_rng(SEMILLA)
    valores = []
    for _ in range(REMUESTREOS):
        idx = azar.integers(0, n, size=n)
        k = kappa_ponderado(a[:, idx].ravel().tolist(), b[:, idx].ravel().tolist())
        if not math.isnan(k):
            valores.append(k)
    if not valores:
        fallar("Ningún remuestreo permitió calcular el kappa total")
    bajo, alto = np.percentile(valores, [2.5, 97.5])
    return float(bajo), float(alto), REMUESTREOS - len(valores)


def _redondeo(valor: float) -> float | None:
    return None if math.isnan(valor) else round(valor, 3)


def fila(nombre: str, a: list[int], b: list[int]) -> dict:
    n = len(a)
    acuerdos = sum(x == y for x, y in zip(a, b, strict=True))
    fila_ = {
        "criterio": nombre,
        "n": n,
        "n_acuerdos": acuerdos,
        "pct_acuerdo": round(100 * acuerdos / n, 1),
        "kappa_ponderado": _redondeo(kappa_ponderado(a, b)),
        "ac1_gwet": _redondeo(ac1_gwet(a, b)),
    }
    for codigo in CATEGORIAS:
        fila_[f"luis_{codigo}"] = a.count(codigo)
    for codigo in CATEGORIAS:
        fila_[f"claude_{codigo}"] = b.count(codigo)
    fila_["media_luis"] = round(sum(a) / n, 2)
    fila_["media_claude"] = round(sum(b) / n, 2)
    fila_["claude_mayor"] = sum(y > x for x, y in zip(a, b, strict=True))
    fila_["claude_menor"] = sum(y < x for x, y in zip(a, b, strict=True))
    return fila_


def calcular(params: dict) -> dict:
    luis = leer_luis(params)
    libro = RAIZ_REPO / "config" / LIBRO
    if not libro.is_file():
        fallar(f"No existe {libro.name}")
    claude = ultimas_por_informe(leer_registro(), S.sha256(libro))
    ids = sorted(luis["id_ciego"])
    if sorted(claude) != ids or len(ids) != 40:
        fallar("Luis Fer y Claude no tienen los mismos 40 informes con el libro v2")
    codigos = codigos_por_criterio(luis, claude, ids)
    filas = [fila(c, *codigos[c]) for c in CRITERIOS]
    todos_l = [x for c in CRITERIOS for x in codigos[c][0]]
    todos_c = [x for c in CRITERIOS for x in codigos[c][1]]
    filas.append(fila("TOTAL", todos_l, todos_c))
    bajo, alto, descartados = kappa_total_bootstrap(codigos, len(ids))
    desacuerdos = [
        {
            "id_ciego": i,
            "criterio": c,
            "codigo_luisfer": x,
            "codigo_claude": y,
            "justificacion_claude": claude[i]["justificaciones"][c],
        }
        for c in CRITERIOS
        for i, x, y in zip(ids, *codigos[c], strict=True)
        if x != y
    ]
    return {
        "tabla": pd.DataFrame(filas),
        "desacuerdos": desacuerdos,
        "ic": (bajo, alto, descartados),
        "libro": libro,
        "luis": RAIZ_REPO / params["semantico"]["salidas"] / ARCHIVO_LUIS,
        "modelos": sorted({r["modelo"] for r in claude.values()}),
        "n": len(ids),
    }


def guardar(params: dict, r: dict) -> None:
    carpeta = RAIZ_REPO / params["salidas"]["tablas"]
    ruta_csv = carpeta / "confiabilidad_40.csv"
    r["tabla"].to_csv(ruta_csv, index=False, lineterminator="\n")
    total = r["tabla"].iloc[-1]
    bajo, alto, descartados = r["ic"]
    traza = {
        "nota": "D48: los códigos de Luis Fer los decidió él leyendo las fichas, "
        "apoyado en notas propias de lecturas previas; Claude codificó primero en "
        "sesión limpia sin acceso a los códigos humanos.",
        "n_informes": r["n"],
        "kappa": "ponderado, pesos cuadráticos, categorías 0-1-2",
        "ac1": "AC1 de Gwet sin pesos (acuerdo exacto), categorías 0-1-2",
        "kappa_total": _redondeo(float(total["kappa_ponderado"])),
        "kappa_total_ic95": {
            "bajo": round(bajo, 3),
            "alto": round(alto, 3),
            "metodo": f"bootstrap por informe, {REMUESTREOS} remuestreos, "
            f"semilla {SEMILLA}, percentiles 2,5 y 97,5",
            "remuestreos_descartados": descartados,
        },
        "veredicto": veredicto(float(total["kappa_ponderado"])),
        "modelos": r["modelos"],
        "entradas": {
            "libro": {"archivo": r["libro"].name, "sha256": S.sha256(r["libro"])},
            "codigos_luisfer": {
                "archivo": r["luis"].name,
                "sha256": S.sha256(r["luis"]),
            },
        },
        "salida": {"archivo": ruta_csv.name, "sha256": S.sha256(ruta_csv)},
    }
    (carpeta / "confiabilidad_40.json").write_text(
        json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    pd.DataFrame(r["desacuerdos"]).to_csv(
        privada / "desacuerdos_40_luisfer_claude.csv",
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )


def main() -> int:
    try:
        params = S.cargar_params()
        resultado = calcular(params)
        guardar(params, resultado)
        print(resultado["tabla"].to_string(index=False))
        print("IC95 kappa total:", resultado["ic"])
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
