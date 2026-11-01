"""Registro de la codificación de Claude Code y su acuerdo con Luis Fer (D45, D46).

Cada informe codificado deja una línea en logs/codificacion_claude.jsonl (solo se
agrega, nunca se reescribe). Compara los códigos de Claude con los de la hoja de Luis
Fer: porcentaje de acuerdo y kappa ponderado (pesos cuadráticos) por criterio y total.
Falla (código 1) si falta un archivo, un código no es 0, 1 o 2, o una línea del registro
no trae los nueve criterios con su justificación.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from rs_pipeline import semantico_04 as S
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ_REPO = S.RAIZ_REPO
CRITERIOS = [f"C0{n}" for n in range(1, 10)]
RUTA_LOG = RAIZ_REPO / "logs" / "codificacion_claude.jsonl"
CATEGORIAS = (0, 1, 2)


# --- Registro ---------------------------------------------------------------------


def hash_ficha(campos: dict[str, str]) -> str:
    """SHA-256 de los campos leídos (ya limpios), en el orden de la hoja."""
    texto = json.dumps(campos, ensure_ascii=False, sort_keys=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def validar_codificacion(id_ciego: str, codigos: dict, justificaciones: dict) -> None:
    if list(codigos) != CRITERIOS or list(justificaciones) != CRITERIOS:
        fallar(f"{id_ciego}: deben venir los nueve criterios C01 a C09, en orden")
    if any(c not in CATEGORIAS for c in codigos.values()):
        fallar(f"{id_ciego}: un código no es 0, 1 ni 2")
    for criterio, texto in justificaciones.items():
        if not texto.strip() or "\n" in texto:
            fallar(f"{id_ciego} {criterio}: la justificación debe ser de una línea")


def registrar(linea: dict, ruta: Path = RUTA_LOG) -> None:
    """Agrega una línea al registro (nunca reescribe las anteriores)."""
    validar_codificacion(linea["id_ciego"], linea["codigos"], linea["justificaciones"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(linea, ensure_ascii=False) + "\n")


def leer_registro(ruta: Path = RUTA_LOG) -> list[dict]:
    if not ruta.is_file():
        fallar(f"Falta {ruta}")
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x]


def ultimas_por_informe(registro: list[dict], libro_sha: str) -> dict[str, dict]:
    """El intento más reciente de cada informe hecho con esta versión del libro."""
    vigentes = [r for r in registro if r["libro"]["sha256"] == libro_sha]
    return {r["id_ciego"]: r for r in vigentes}


# --- Acuerdo ----------------------------------------------------------------------


def kappa_ponderado(a: list[int], b: list[int]) -> float:
    """Kappa con pesos cuadráticos; NaN si el azar no deja margen para medirlo."""
    n = len(a)
    k = len(CATEGORIAS)
    observada = np.zeros((k, k))
    for x, y in zip(a, b, strict=True):
        observada[x, y] += 1
    esperada = np.outer(observada.sum(axis=1), observada.sum(axis=0)) / n
    pesos = np.array(
        [[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)]
    )
    denominador = (pesos * esperada).sum()
    if denominador == 0:
        return math.nan
    return float(1 - (pesos * observada).sum() / denominador)


def fila_de_acuerdo(nombre: str, a: list[int], b: list[int]) -> dict:
    acuerdos = sum(x == y for x, y in zip(a, b, strict=True))
    kappa = kappa_ponderado(a, b)
    return {
        "criterio": nombre,
        "n": len(a),
        "n_acuerdos": acuerdos,
        "pct_acuerdo": round(100 * acuerdos / len(a), 1),
        "kappa_ponderado": None if math.isnan(kappa) else round(kappa, 3),
    }


def comparar(luis: pd.DataFrame, claude: dict[str, dict]) -> tuple[pd.DataFrame, list]:
    """Tabla de acuerdo por criterio y total, y la lista de desacuerdos."""
    ids = sorted(luis["id_ciego"])
    if sorted(claude) != ids:
        fallar(
            "La hoja de Luis Fer y el registro de Claude no tienen los mismos informes"
        )
    por_id = luis.set_index("id_ciego")
    filas, todos_l, todos_c, desacuerdos = [], [], [], []
    for criterio in CRITERIOS:
        luis_c = [int(por_id.loc[i, criterio]) for i in ids]
        c = [claude[i]["codigos"][criterio] for i in ids]
        filas.append(fila_de_acuerdo(criterio, luis_c, c))
        todos_l += luis_c
        todos_c += c
        desacuerdos += [
            {
                "id_ciego": i,
                "criterio": criterio,
                "codigo_luisfer": x,
                "codigo_claude": y,
                "justificacion_claude": claude[i]["justificaciones"][criterio],
            }
            for i, x, y in zip(ids, luis_c, c, strict=True)
            if x != y
        ]
    filas.append(fila_de_acuerdo("TOTAL", todos_l, todos_c))
    return pd.DataFrame(filas), desacuerdos


# --- Ejecución --------------------------------------------------------------------


def leer_hoja(params: dict) -> pd.DataFrame:
    ruta = RAIZ_REPO / params["semantico"]["salidas"] / "hoja_codificacion_piloto.csv"
    hoja = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if (hoja[CRITERIOS] == "").to_numpy().any():
        fallar("La hoja del piloto no tiene los nueve códigos de Luis Fer por informe")
    return hoja


def registrar_lote(ruta_json: Path, params: dict) -> int:
    """Agrega al registro los informes de un JSON con codigos y justificaciones."""
    libro = RAIZ_REPO / "config" / "libro_codigos_v1.yaml"
    hoja = leer_hoja(params)
    entrada = json.loads(ruta_json.read_text(encoding="utf-8"))
    campos = params["codificacion"]["campos_ficha"]
    por_id = hoja.set_index("id_ciego")
    for id_ciego, datos in entrada["informes"].items():
        ficha = {c: por_id.loc[id_ciego, c] for c in campos}
        registrar(
            {
                "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
                "modelo": entrada["modelo"],
                "libro": {"archivo": libro.name, "sha256": S.sha256(libro)},
                "id_ciego": id_ciego,
                "sha256_ficha": hash_ficha(ficha),
                "codigos": datos["codigos"],
                "justificaciones": datos["justificaciones"],
            }
        )
    return len(entrada["informes"])


def comparar_piloto(params: dict) -> dict:
    libro = RAIZ_REPO / "config" / "libro_codigos_v1.yaml"
    luis = leer_hoja(params)
    claude = ultimas_por_informe(leer_registro(), S.sha256(libro))
    tabla, desacuerdos = comparar(luis, claude)
    carpeta = RAIZ_REPO / params["salidas"]["tablas"]
    ruta_csv = carpeta / "acuerdo_piloto_luisfer_claude.csv"
    tabla.to_csv(ruta_csv, index=False, lineterminator="\n")
    traza = {
        "nota": "Con 5 informes es solo orientativo. Los códigos de Luis Fer ya "
        "estaban a la vista de Claude al codificar: no es una codificación ciega.",
        "libro": {"archivo": libro.name, "sha256": S.sha256(libro)},
        "kappa": "ponderado, pesos cuadráticos, categorías 0-1-2; vacío si no "
        "calculable",
        "modelo": sorted({r["modelo"] for r in claude.values()}),
        "n_informes": len(claude),
        "salida": {"archivo": ruta_csv.name, "sha256": S.sha256(ruta_csv)},
    }
    (carpeta / "acuerdo_piloto_luisfer_claude.json").write_text(
        json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    pd.DataFrame(desacuerdos).to_csv(
        privada / "desacuerdos_piloto_luisfer_claude.csv",
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )
    pd.DataFrame(
        [
            {
                "id_ciego": i,
                "criterio": c,
                "codigo": r["codigos"][c],
                "justificacion": r["justificaciones"][c],
            }
            for i, r in sorted(claude.items())
            for c in CRITERIOS
        ]
    ).to_csv(
        privada / "codigos_claude_piloto.csv",
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )
    return {"tabla": tabla, "desacuerdos": desacuerdos}


def main() -> int:
    try:
        params = S.cargar_params()
        if "--registrar" in sys.argv:
            ruta = Path(sys.argv[sys.argv.index("--registrar") + 1])
            print(f"informes registrados: {registrar_lote(ruta, params)}")
            return 0
        salida = comparar_piloto(params)
        print(salida["tabla"].to_string(index=False))
        for d in salida["desacuerdos"]:
            print(
                d["id_ciego"],
                d["criterio"],
                d["codigo_luisfer"],
                d["codigo_claude"],
                d["justificacion_claude"],
            )
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
