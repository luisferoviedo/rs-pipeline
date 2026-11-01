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


def leer_hoja(
    params: dict,
    archivo: str = "hoja_codificacion_piloto.csv",
    con_codigos: bool = True,
) -> pd.DataFrame:
    ruta = RAIZ_REPO / params["semantico"]["salidas"] / archivo
    hoja = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if con_codigos and (hoja[CRITERIOS] == "").to_numpy().any():
        fallar(f"{archivo} no tiene los nueve códigos de Luis Fer por informe")
    return hoja


def archivo_de_codigos(archivo_hoja: str) -> str:
    """hoja_codificacion_40.csv -> codigos_claude_40.csv"""
    return archivo_hoja.replace("hoja_codificacion_", "codigos_claude_")


def lineas_del_lote(
    entrada: dict, hoja: pd.DataFrame, libro: Path, params: dict
) -> list:
    """Líneas del registro de un lote, validadas todas antes de escribir ninguna."""
    if sorted(entrada["informes"]) != sorted(hoja["id_ciego"]):
        fallar("El lote no trae exactamente los informes de la hoja")
    campos = params["codificacion"]["campos_ficha"]
    por_id = hoja.set_index("id_ciego")
    fecha = datetime.now().astimezone().isoformat(timespec="seconds")
    lineas = []
    for id_ciego, datos in entrada["informes"].items():
        validar_codificacion(id_ciego, datos["codigos"], datos["justificaciones"])
        ficha = {c: por_id.loc[id_ciego, c] for c in campos}
        lineas.append(
            {
                "fecha": fecha,
                "modelo": entrada["modelo"],
                "libro": {"archivo": libro.name, "sha256": S.sha256(libro)},
                "id_ciego": id_ciego,
                "sha256_ficha": hash_ficha(ficha),
                "codigos": datos["codigos"],
                "justificaciones": datos["justificaciones"],
            }
        )
    return lineas


def registrar_lote(
    ruta_json: Path,
    params: dict,
    archivo_hoja: str = "hoja_codificacion_piloto.csv",
    version_libro: str = "v1",
) -> int:
    """Agrega al registro (y a un CSV ignorado) los informes de un lote de Claude."""
    libro = RAIZ_REPO / "config" / f"libro_codigos_{version_libro}.yaml"
    if not libro.is_file():
        fallar(f"No existe {libro.name}")
    hoja = leer_hoja(params, archivo_hoja, con_codigos=False)
    entrada = json.loads(ruta_json.read_text(encoding="utf-8"))
    lineas = lineas_del_lote(entrada, hoja, libro, params)
    for linea in lineas:
        registrar(linea)
    ruta_csv = (
        RAIZ_REPO / params["semantico"]["salidas"] / archivo_de_codigos(archivo_hoja)
    )
    filas = pd.DataFrame(
        [
            {
                "fecha": r["fecha"],
                "id_ciego": r["id_ciego"],
                "criterio": c,
                "codigo": r["codigos"][c],
                "justificacion": r["justificaciones"][c],
            }
            for r in lineas
            for c in CRITERIOS
        ]
    )
    filas.to_csv(
        ruta_csv,
        mode="a",
        header=not ruta_csv.is_file(),
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )
    return len(lineas)


def actualizar_resumen(params: dict) -> dict:
    """Resumen numérico del registro (sin códigos ni justificaciones): va a git."""
    registro = leer_registro()
    por_libro: dict[tuple[str, str], dict] = {}
    for r in registro:
        clave = (r["libro"]["archivo"], r["libro"]["sha256"])
        grupo = por_libro.setdefault(
            clave, {"lineas": 0, "modelos": set(), "ultima_fecha": ""}
        )
        grupo["lineas"] += 1
        grupo["modelos"].add(r["modelo"])
        grupo["ultima_fecha"] = max(grupo["ultima_fecha"], r["fecha"])
    resumen = {
        "lineas_en_el_registro": len(registro),
        "por_libro": [
            {
                "libro": archivo,
                "sha256": sha,
                "informes_codificados": g["lineas"],
                "modelos": sorted(g["modelos"]),
                "ultima_fecha": g["ultima_fecha"],
            }
            for (archivo, sha), g in sorted(por_libro.items())
        ],
    }
    ruta = RAIZ_REPO / params["salidas"]["tablas"] / "codificacion_claude_resumen.json"
    ruta.write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen


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


def _opcion(nombre: str, por_defecto: str) -> str:
    if nombre not in sys.argv:
        return por_defecto
    return sys.argv[sys.argv.index(nombre) + 1]


def main() -> int:
    try:
        params = S.cargar_params()
        if "--registrar" in sys.argv:
            ruta = Path(sys.argv[sys.argv.index("--registrar") + 1])
            hoja = _opcion("--hoja", "hoja_codificacion_piloto.csv")
            libro = _opcion("--libro", "v1")
            n = registrar_lote(ruta, params, hoja, libro)
            actualizar_resumen(params)
            print(f"informes registrados: {n}")
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
