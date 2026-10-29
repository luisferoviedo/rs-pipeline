"""Normaliza las categorías de la matriz de extracción (Paso B).

Lee la matriz v2 del Drive (solo lectura), quita los 18 E4 de los dudosos, aplica
config/categorias.yaml y escribe la matriz normalizada en data/processed/ con un
archivo hermano que registra la ruta y el hash de cada entrada. Falla (código 1) si
falta un archivo o una columna, si un valor crudo no está en el mapeo o si no quedan
los 201 informes.
"""

from __future__ import annotations

import json
import re
import sys
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import yaml

from rs_pipeline import prisma_02
from rs_pipeline.prisma_02 import ErrorPipeline, fallar

RAIZ_REPO = prisma_02.RAIZ_REPO
COLUMNAS_A_NORMALIZAR = [
    "disciplina",
    "mmat_categoria",
    "oe1_direccion",
    "oe2_tipo_herramienta",
    "oe1_resultado_tipo",
]
COLUMNAS_NECESARIAS = ["id", *COLUMNAS_A_NORMALIZAR]
PATRON_SEGMENTO = re.compile(r"^([^(:]+?)\s*(?::\s*(.+)|\((.+)\))?$", re.DOTALL)


# --- Entradas ------------------------------------------------------------------


def cargar_categorias(ruta: Path) -> dict:
    if not ruta.is_file():
        fallar(f"No existe el archivo: {ruta}")
    categorias = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    faltan = [c for c in COLUMNAS_A_NORMALIZAR if c not in categorias]
    if faltan:
        fallar(f"categorias.yaml: faltan las columnas {faltan}")
    return categorias


def mapear(serie: pd.Series, mapa: dict, nombre: str) -> list:
    """Devuelve el valor del mapa para cada fila. Un valor sin mapear hace fallar."""
    sin_mapear = serie[~serie.isin(list(mapa))]
    if len(sin_mapear):
        detalle = ", ".join(
            f"{valor!r} (n={n})" for valor, n in sin_mapear.value_counts().items()
        )
        fallar(f"{nombre}: valores sin mapear en config/categorias.yaml: {detalle}")
    return [mapa[valor] for valor in serie]


def preparar_tabla(params: dict) -> dict:
    """Lee la matriz y los dudosos, quita los 18 E4 y comprueba las 201 filas."""
    raiz = prisma_02.raiz_drive(params["drive_root_env"])
    rutas = {nombre: raiz / rel for nombre, rel in params["archivos"].items()}
    matriz = prisma_02.leer_csv(rutas["extraccion"], COLUMNAS_NECESARIAS, "id")
    dudosos = prisma_02.leer_csv(
        rutas["dudosos"], prisma_02.COLUMNAS["dudosos"], "id"
    )
    prisma_02.exigir_valores(
        dudosos["decision_luisfer"], prisma_02.DUDOSOS_VALIDOS, "dudosos.decision"
    )
    ids_e4 = sorted(prisma_02.dudosos_e4(dudosos)["id"])
    ausentes = sorted(set(ids_e4) - set(matriz["id"]))
    if ausentes:
        fallar(f"E4 de los dudosos que no están en la matriz: {ausentes}")
    tabla = matriz[~matriz["id"].isin(ids_e4)].reset_index(drop=True)
    declarado = prisma_02.leer_declarado(rutas["prisma_counts"])
    if len(tabla) != declarado["incluidos_informes"]:
        fallar(
            f"Quedan {len(tabla)} informes y prisma_counts declara "
            f"{declarado['incluidos_informes']}"
        )
    return {
        "raiz": raiz,
        "rutas": rutas,
        "tabla": tabla,
        "filas_matriz": len(matriz),
        "ids_e4": ids_e4,
    }


# --- Columnas con un solo valor por fila ----------------------------------------


def cols_disciplina(tabla: pd.DataFrame, cfg: dict) -> dict[str, list]:
    valores = mapear(tabla["disciplina"], cfg["mapa"], "disciplina")
    return {cfg["columna_salida"]: valores}


def cols_mmat(tabla: pd.DataFrame, cfg: dict) -> dict[str, list]:
    mapeado = mapear(tabla["mmat_categoria"], cfg["mapa"], "mmat_categoria")
    return {
        cfg["columna_salida"]: [x["categoria"] for x in mapeado],
        cfg["columna_pre_post"]: [str(x["pre_post_un_grupo"]) for x in mapeado],
    }


def cols_direccion(tabla: pd.DataFrame, cfg: dict) -> dict[str, list]:
    mapeado = mapear(tabla["oe1_direccion"], cfg["mapa"], "oe1_direccion")
    return {
        cfg["columna_salida"]: [x["categoria"] for x in mapeado],
        cfg["columna_efecto_aislado"]: [
            "" if x["efecto_aislado"] is None else str(x["efecto_aislado"])
            for x in mapeado
        ],
    }


# --- Columnas multi-etiqueta ----------------------------------------------------


def cols_herramienta(tabla: pd.DataFrame, cfg: dict) -> dict[str, list]:
    mapeado = mapear(tabla["oe2_tipo_herramienta"], cfg["mapa"], "oe2_tipo_herramienta")
    columnas = cfg["columnas"]
    usadas = {etiqueta for x in mapeado for etiqueta in x["etiquetas"]}
    sin_columna = sorted(usadas - set(columnas))
    if sin_columna:
        fallar(f"oe2_tipo_herramienta: etiquetas sin columna: {sin_columna}")
    salida = {
        columna: [str(int(etiqueta in x["etiquetas"])) for x in mapeado]
        for etiqueta, columna in columnas.items()
    }
    salida[cfg["columna_detalle"]] = [x["detalle"] for x in mapeado]
    return salida


def dividir_fuera_de_parentesis(texto: str, separador: str) -> list[str]:
    """Divide en `separador` solo fuera de paréntesis."""
    partes: list[str] = []
    actual: list[str] = []
    nivel = 0
    for caracter in texto:
        nivel += (caracter == "(") - (caracter == ")")
        if nivel < 0:
            fallar(f"oe1_resultado_tipo: paréntesis desbalanceados en '{texto}'")
        if caracter == separador and nivel == 0:
            partes.append("".join(actual).strip())
            actual = []
        else:
            actual.append(caracter)
    partes.append("".join(actual).strip())
    if nivel != 0 or not all(partes):
        fallar(f"oe1_resultado_tipo: no se puede dividir '{texto}'")
    return partes


def partir_segmento(segmento: str) -> tuple[str, str]:
    """Devuelve (cabeza, calificador) de 'conceptual (x)' u 'otro: x'."""
    coincide = PATRON_SEGMENTO.match(segmento)
    if not coincide:
        fallar(f"oe1_resultado_tipo: no se entiende el segmento '{segmento}'")
    return coincide[1].strip(), coincide[2] or coincide[3] or ""


def asignar_otro(segmento: dict, calificador: str, cfg: dict) -> dict:
    """Un 'otro' cuyo texto coincide con una regla pasa a la etiqueta de la regla."""
    for indice, regla in enumerate(cfg["reasignar_otro"]):
        if re.search(regla["patron"], calificador, re.IGNORECASE):
            if regla["a"] not in cfg["columnas"]:
                fallar(f"reasignar_otro: etiqueta desconocida '{regla['a']}'")
            return segmento | {"etiqueta": regla["a"], "reasignado": indice}
    return segmento | {"detalle": calificador}


def procesar_segmento(cabeza: str, calificador: str, cfg: dict) -> dict:
    segmento = {
        "etiqueta": cabeza,
        "detalle": "",
        "autoinforme": 0,
        "covariable": 0,
        "reasignado": None,
    }
    if cabeza not in cfg["columnas"]:
        fallar(f"oe1_resultado_tipo: etiqueta desconocida '{cabeza}'")
    patron_covariable = cfg["no_cuenta_como_resultado"]["patron"]
    if re.search(patron_covariable, calificador, re.IGNORECASE):
        return segmento | {"etiqueta": None, "covariable": 1}
    patron_autoinforme = cfg["conceptual_autoinforme"]["patron"]
    if cabeza == "conceptual" and re.search(
        patron_autoinforme, calificador, re.IGNORECASE
    ):
        segmento["autoinforme"] = 1
    if cabeza == "otro":
        segmento = asignar_otro(segmento, calificador, cfg)
    return segmento


def etiquetar_resultado(valor: str, cfg: dict) -> dict:
    segmentos = [
        procesar_segmento(*partir_segmento(texto), cfg)
        for texto in dividir_fuera_de_parentesis(valor, cfg["separador"])
    ]
    etiquetas = {s["etiqueta"] for s in segmentos if s["etiqueta"]}
    if not etiquetas:
        fallar(f"oe1_resultado_tipo: '{valor}' se queda sin ninguna etiqueta")
    return {
        "etiquetas": etiquetas,
        "detalle": " | ".join(s["detalle"] for s in segmentos if s["detalle"]),
        "autoinforme": int(any(s["autoinforme"] for s in segmentos)),
        "reasignados": [
            s["reasignado"] for s in segmentos if s["reasignado"] is not None
        ],
        "covariables": sum(s["covariable"] for s in segmentos),
    }


def verificar_esperados(filas: list[dict], cfg: dict) -> None:
    """Las reglas de excepción deben tocar exactamente los casos que aprobó Luis Fer."""
    pruebas = [
        (
            "conceptual_autoinforme",
            sum(f["autoinforme"] for f in filas),
            cfg["conceptual_autoinforme"]["esperados"],
        ),
        (
            "no_cuenta_como_resultado",
            sum(f["covariables"] for f in filas),
            cfg["no_cuenta_como_resultado"]["esperados"],
        ),
    ]
    for indice, regla in enumerate(cfg["reasignar_otro"]):
        reales = sum(f["reasignados"].count(indice) for f in filas)
        pruebas.append((f"reasignar_otro[{indice}]", reales, regla["esperados"]))
    distintas = [
        f"{nombre}: {real} en vez de {esperado}"
        for nombre, real, esperado in pruebas
        if real != esperado
    ]
    if distintas:
        fallar(f"oe1_resultado_tipo: reglas que no tocan lo esperado: {distintas}")


def cols_resultado(tabla: pd.DataFrame, cfg: dict) -> dict[str, list]:
    filas = [etiquetar_resultado(valor, cfg) for valor in tabla["oe1_resultado_tipo"]]
    verificar_esperados(filas, cfg)
    salida = {
        columna: [str(int(etiqueta in f["etiquetas"])) for f in filas]
        for etiqueta, columna in cfg["columnas"].items()
    }
    salida[cfg["columna_detalle"]] = [f["detalle"] for f in filas]
    salida[cfg["columna_autoinforme"]] = [str(f["autoinforme"]) for f in filas]
    return salida


# --- Salida ----------------------------------------------------------------------


def columnas_nuevas(tabla: pd.DataFrame, categorias: dict) -> dict[str, list]:
    nuevas: dict[str, list] = {}
    for funcion, columna in [
        (cols_disciplina, "disciplina"),
        (cols_mmat, "mmat_categoria"),
        (cols_direccion, "oe1_direccion"),
        (cols_herramienta, "oe2_tipo_herramienta"),
        (cols_resultado, "oe1_resultado_tipo"),
    ]:
        for nombre, valores in funcion(tabla, categorias[columna]).items():
            if nombre in nuevas or nombre in tabla.columns:
                fallar(f"La columna nueva '{nombre}' ya existe")
            nuevas[nombre] = valores
    return nuevas


def resumir(salida: pd.DataFrame, nuevas: dict[str, list]) -> dict:
    """Frecuencias de las categorías y suma de cada columna 0/1."""
    resumen: dict = {}
    for nombre in nuevas:
        valores = set(salida[nombre])
        if nombre.endswith("_norm"):
            resumen[nombre] = salida[nombre].value_counts().to_dict()
        elif valores <= {"0", "1"}:
            resumen[nombre] = int((salida[nombre] == "1").sum())
        elif valores <= {"0", "1", ""}:
            resumen[nombre] = salida[nombre].value_counts().to_dict()
    return resumen


def normalizar(params: dict, carpeta: Path) -> dict:
    """Escribe la matriz normalizada y su archivo de trazabilidad en `carpeta`."""
    fuentes = preparar_tabla(params)
    ruta_categorias = RAIZ_REPO / params["categorias"]
    categorias = cargar_categorias(ruta_categorias)
    tabla = fuentes["tabla"]
    nuevas = columnas_nuevas(tabla, categorias)
    salida = pd.concat([tabla, pd.DataFrame(nuevas)], axis=1)
    if len(salida) != len(tabla) or not salida[list(tabla.columns)].equals(tabla):
        fallar("La normalización cambió filas o columnas originales")
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_csv = carpeta / f"{fuentes['rutas']['extraccion'].stem}_normalizada.csv"
    salida.to_csv(ruta_csv, index=False, encoding="utf-8", lineterminator="\n")
    resumen = resumir(salida, nuevas)
    raiz = fuentes["raiz"]
    entradas = {
        str(ruta.relative_to(raiz)): prisma_02.sha256(ruta)
        for nombre, ruta in fuentes["rutas"].items()
        if nombre in ("extraccion", "dudosos", "prisma_counts")
    } | {params["categorias"]: prisma_02.sha256(ruta_categorias)}
    ruta_json = ruta_csv.with_suffix(".json")
    trazabilidad = {
        "script": "src/rs_pipeline/normalizar_01.py",
        "versiones": {"pandas": version("pandas"), "python": sys.version.split()[0]},
        "entradas_sha256": entradas,
        "filas_matriz_fuente": fuentes["filas_matriz"],
        "ids_excluidos_e4": fuentes["ids_e4"],
        "filas_salida": len(salida),
        "columnas_originales": len(tabla.columns),
        "columnas_nuevas": list(nuevas),
        "resumen": resumen,
        "salida": {"archivo": ruta_csv.name, "sha256": prisma_02.sha256(ruta_csv)},
    }
    ruta_json.write_text(
        json.dumps(trazabilidad, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"csv": ruta_csv, "json": ruta_json, "trazabilidad": trazabilidad}


def reporte(resultado: dict) -> list[str]:
    t = resultado["trazabilidad"]
    lineas = ["== Entradas (ruta relativa, sha256) =="]
    lineas += [f"  {ruta}  {h}" for ruta, h in t["entradas_sha256"].items()]
    lineas += [
        "",
        f"Filas: {t['filas_matriz_fuente']} en la matriz - "
        f"{len(t['ids_excluidos_e4'])} E4 = {t['filas_salida']} informes",
        f"Columnas: {t['columnas_originales']} originales + "
        f"{len(t['columnas_nuevas'])} nuevas",
        "",
        "== Resumen de las columnas nuevas ==",
    ]
    lineas += [f"  {nombre}: {valor}" for nombre, valor in t["resumen"].items()]
    lineas += ["", f"Salida: {resultado['csv']}", f"Trazabilidad: {resultado['json']}"]
    return lineas


def main() -> int:
    try:
        params = prisma_02.cargar_params()
        resultado = normalizar(params, RAIZ_REPO / params["salidas"]["procesados"])
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("\n".join(reporte(resultado)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
