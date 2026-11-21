"""Exploración de la heterogeneidad de la dirección del efecto (D59).

Protocolo: docs/protocolo_d59.md (reglas fijadas antes de calcular). Con los estudios
comparativos (dirección favorable, mixto o sin diferencia) responde tres preguntas con
una tabla 2 × 2 cada una (favorable frente a no favorable): nivel (secundaria frente a
universitario), peso de la evidencia (alto frente a medio + bajo, regla de la suma) y
comparador (clase tradicional frente a laboratorio real). Prueba exacta de Fisher
bilateral (la de D54), con corrección de Holm entre las tres. Además calcula la
corrección de Holm de las 45 pruebas de D54.

Los atributos de cada estudio salen del informe de más puntos (D43, D54). No se
recodifica nada. El comparador sale de las reglas de texto del protocolo y, en los
estudios que la regla dejó en «varios» u «otra», de las decisiones de Luis Fer en
config/comparador_d59.yaml (adenda a D59, tomadas antes de calcular las pruebas).
A git van solo números; la hoja para revisar los comparadores ambiguos trae texto
de la matriz y va a outputs/semantico/ (ignorado).
Falla (código 1) si falta un archivo o una columna, si las bases no son 196 informes
y 193 estudios, si un grupo queda vacío o si un conteo no cuadra.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata

import pandas as pd
import yaml

from rs_pipeline import criterios_05 as C
from rs_pipeline import marco_evidencia_08 as M
from rs_pipeline import semantico_04 as S
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ_REPO = S.RAIZ_REPO
SALIDA = "heterogeneidad_59"
SALIDA_HOLM = "holm_d54"
REVISION = "d59_revision_comparador.csv"
ENTRADA_D54 = "marco_evidencia_v0.csv"
N_INFORMES, N_ESTUDIOS, N_PRUEBAS_D54 = 196, 193, 45
COMPARATIVAS = ("favorable", "mixto", "sin_diferencia")
DIRECCIONES_D54 = ("favorable", "mixto", "sin_diferencia", "no_comparativo", "otro")
ALFA = 0.05
# pregunta → (columna del estudio, grupo 1, grupo 2); lo demás queda fuera de la prueba
CRUCES = {
    "nivel": ("nivel", ("secundaria",), ("universitario",)),
    "peso": ("peso_suma", ("alto",), ("medio", "bajo")),
    "comparador": ("comparador", ("clase tradicional",), ("laboratorio real",)),
}
AMBIGUOS = ("varios", "otra")
DECISIONES = "config/comparador_d59.yaml"
CATEGORIAS = (
    "clase tradicional",
    "laboratorio real",
    "otra simulación",
    "otra",
    "varios",
    "ninguna",
)


def sin_tildes(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar textos sin depender de la escritura."""
    descompuesto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def clasificar_comparador(texto: str) -> str:
    """Reglas del protocolo (sección 6), en este orden."""
    limpio = sin_tildes(texto).strip()
    laboratorio, tradicional = "laboratorio real" in limpio, "tradicional" in limpio
    if laboratorio and tradicional:
        return "varios"
    if laboratorio:
        return "laboratorio real"
    if tradicional:
        return "clase tradicional"
    if C.SIN_COMPARACION.match(texto.strip()):
        return "ninguna"
    if "otra simulacion" in limpio:
        return "otra simulación"
    return "otra"


def holm(valores: list[float]) -> list[float]:
    """p ajustados de Holm (1979), en el orden de entrada y con tope en 1."""
    m = len(valores)
    orden = sorted(range(m), key=lambda i: valores[i])
    ajustados = [0.0] * m
    maximo = 0.0
    for posicion, i in enumerate(orden):
        maximo = max(maximo, min(1.0, (m - posicion) * valores[i]))
        ajustados[i] = maximo
    return ajustados


def leer_decisiones(texto: str) -> dict[str, str]:
    """Estudio → categoría decidida por Luis Fer (adenda a D59)."""
    decisiones: dict[str, str] = {}
    for fila in yaml.safe_load(texto)["decisiones"]:
        if fila["categoria"] not in CATEGORIAS:
            fallar(f"{fila['estudio']}: categoría desconocida '{fila['categoria']}'")
        if fila["estudio"] in decisiones:
            fallar(f"{fila['estudio']}: aparece dos veces en {DECISIONES}")
        decisiones[fila["estudio"]] = fila["categoria"]
    return decisiones


def aplicar_decisiones(base: pd.DataFrame, decisiones: dict[str, str]) -> pd.DataFrame:
    """Comparador final: la decisión manual si existe; si no, el de la regla."""
    faltan = [e for e in decisiones if e not in base.index]
    if faltan:
        fallar(f"Decisiones para estudios fuera de la base comparativa: {faltan}")
    fuera = [e for e in decisiones if base.at[e, "comparador_regla"] not in AMBIGUOS]
    if fuera:
        fallar(f"Decisiones para estudios que la regla no dejó ambiguos: {fuera}")
    base = base.copy()
    reglas = base["comparador_regla"]
    base["comparador"] = [
        decisiones.get(e, c) for e, c in zip(base.index, reglas, strict=True)
    ]
    return base


def base_comparativa(estudios: pd.DataFrame) -> pd.DataFrame:
    """Solo estudios con dirección favorable, mixto o sin diferencia."""
    base = estudios[estudios["direccion"].isin(COMPARATIVAS)]
    if base.empty:
        fallar("No hay estudios comparativos")
    return base


def fila_de_cruce(pregunta: str, base: pd.DataFrame) -> dict:
    """Tabla 2 × 2 de una pregunta, con los grupos que quedan fuera de la prueba."""
    columna, grupo_1, grupo_2 = CRUCES[pregunta]
    favorable = base["direccion"] == "favorable"
    en_1, en_2 = base[columna].isin(grupo_1), base[columna].isin(grupo_2)
    a, b = int((en_1 & favorable).sum()), int((en_1 & ~favorable).sum())
    c, d = int((en_2 & favorable).sum()), int((en_2 & ~favorable).sum())
    if a + b == 0 or c + d == 0:
        fallar(f"{pregunta}: un grupo de la prueba quedó vacío")
    fuera = base[~(en_1 | en_2)]
    if a + b + c + d + len(fuera) != len(base):
        fallar(f"{pregunta}: los grupos no suman la base")
    detalle_fuera = {
        str(k): f"{int((g['direccion'] == 'favorable').sum())}/{len(g)}"
        for k, g in fuera.groupby(columna)
    }
    pct_1, pct_2 = 100 * a / (a + b), 100 * c / (c + d)
    return {
        "pregunta": pregunta,
        "n_base": len(base),
        "grupo_1": " + ".join(grupo_1),
        "n_1": a + b,
        "favorables_1": a,
        "pct_favorables_1": round(pct_1, 1),
        "grupo_2": " + ".join(grupo_2),
        "n_2": c + d,
        "favorables_2": c,
        "pct_favorables_2": round(pct_2, 1),
        "diferencia_pp": round(pct_1 - pct_2, 1),
        "p_fisher": M.fisher_dos_colas(a, b, c, d),
        "fuera_de_prueba": json.dumps(detalle_fuera, ensure_ascii=False),
    }


def estudios_con_comparador(matriz: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Estudios (D43) con el comparador del informe de más puntos."""
    conteos = json.loads((RAIZ_REPO / params["prisma_counts_vigente"]).read_text())
    ids = C.asignar_estudios(matriz, conteos["incluidos_estudios"])
    informes = C.tabla_de_informes(matriz, ids)
    estudios = C.tabla_de_estudios(informes)
    if len(informes) != N_INFORMES or len(estudios) != N_ESTUDIOS:
        fallar(f"Las bases deben ser {N_INFORMES} informes y {N_ESTUDIOS} estudios")
    texto = dict(zip(matriz["id"], matriz["comparacion"], strict=True))
    estudios = estudios.copy()
    estudios["comparacion_texto"] = estudios["id"].map(texto)
    regla = estudios["comparacion_texto"].map(clasificar_comparador)
    estudios["comparador_regla"] = regla
    return estudios


def preparar_base(params: dict) -> tuple[pd.DataFrame, dict]:
    """Base comparativa con el comparador final, y las entradas con su hash."""
    matriz = S.cargar_matriz(params)
    if "comparacion" not in matriz["tabla"]:
        fallar("La matriz normalizada no tiene la columna 'comparacion'")
    ruta_decisiones = RAIZ_REPO / DECISIONES
    if not ruta_decisiones.is_file():
        fallar(f"Falta {DECISIONES}")
    decisiones = leer_decisiones(ruta_decisiones.read_text(encoding="utf-8"))
    estudios = estudios_con_comparador(matriz["tabla"], params)
    base = aplicar_decisiones(base_comparativa(estudios), decisiones)
    entradas = {
        "matriz_normalizada": {
            "archivo": str(matriz["ruta"].relative_to(RAIZ_REPO)),
            "sha256": matriz["sha256"],
        },
        "decisiones_comparador": {
            "archivo": DECISIONES,
            "sha256": S.sha256(ruta_decisiones),
            "n_decisiones": len(decisiones),
        },
    }
    return base, entradas


def hoja_de_revision(base: pd.DataFrame) -> pd.DataFrame:
    """Estudios que la regla dejó en «varios» u «otra», con la decisión aplicada."""
    revision = base[base["comparador_regla"].isin(AMBIGUOS)].reset_index()
    columnas = ["estudio", "id", "comparador_regla", "comparador", "comparacion_texto"]
    return revision[columnas]


def tabla_holm_d54(ruta: str) -> pd.DataFrame:
    """Las 45 pruebas de D54 con su p de Holm."""
    d54 = pd.read_csv(ruta, dtype={"id_criterio": str})
    faltan = [f"fisher_p_{k}" for k in DIRECCIONES_D54 if f"fisher_p_{k}" not in d54]
    if faltan:
        fallar(f"{ENTRADA_D54} no tiene las columnas {faltan}")
    filas = [
        {"id_criterio": x["id_criterio"], "direccion": k, "p": x[f"fisher_p_{k}"]}
        for x in d54.to_dict("records")
        for k in DIRECCIONES_D54
    ]
    if len(filas) != N_PRUEBAS_D54:
        fallar(f"Se esperaban {N_PRUEBAS_D54} pruebas de D54 y hay {len(filas)}")
    tabla = pd.DataFrame(filas)
    tabla["p_holm"] = holm(tabla["p"].tolist())
    tabla["bajo_alfa_sin_corregir"] = tabla["p"] < ALFA
    tabla["bajo_alfa_holm"] = tabla["p_holm"] < ALFA
    return tabla


def ejecutar(params: dict) -> dict:
    base, entradas = preparar_base(params)
    cruces = pd.DataFrame([fila_de_cruce(p, base) for p in CRUCES])
    cruces["p_holm"] = holm(cruces["p_fisher"].tolist())
    ruta_d54 = RAIZ_REPO / params["salidas"]["tablas"] / ENTRADA_D54
    entradas["pruebas_d54"] = {
        "archivo": str(ruta_d54.relative_to(RAIZ_REPO)),
        "sha256": S.sha256(ruta_d54),
    }
    return {
        "cruces": cruces,
        "holm_d54": tabla_holm_d54(str(ruta_d54)),
        "revision": hoja_de_revision(base),
        "comparadores": base["comparador"].value_counts().to_dict(),
        "entradas": entradas,
    }


def guardar(params: dict, salida: dict) -> None:
    carpeta = RAIZ_REPO / params["salidas"]["tablas"]
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    ruta_csv, ruta_holm = carpeta / f"{SALIDA}.csv", carpeta / f"{SALIDA_HOLM}.csv"
    C.escribir_csv(ruta_csv, salida["cruces"], encoding="utf-8")
    C.escribir_csv(ruta_holm, salida["holm_d54"], encoding="utf-8")
    C.escribir_csv(privada / REVISION, salida["revision"], encoding="utf-8-sig")
    holm_d54 = salida["holm_d54"]
    traza = {
        "decision": "D59",
        "protocolo": "docs/protocolo_d59.md",
        "unidad": "estudio; atributos del informe de más puntos (D43)",
        "base": "estudios comparativos (favorable, mixto, sin diferencia)",
        "resultado": "favorable frente a no favorable (mixto + sin diferencia)",
        "prueba": "Fisher exacta bilateral (D54), Holm (1979) entre las tres",
        "comparador": "reglas de texto del protocolo + decisiones de Luis Fer "
        "(config/comparador_d59.yaml) en los casos «varios» u «otra»",
        "comparadores_en_la_base": salida["comparadores"],
        "holm_d54": {
            "pruebas": N_PRUEBAS_D54,
            "bajo_alfa_sin_corregir": int(holm_d54["bajo_alfa_sin_corregir"].sum()),
            "bajo_alfa_holm": int(holm_d54["bajo_alfa_holm"].sum()),
        },
        "entradas": salida["entradas"],
        "salidas": {
            ruta_csv.name: S.sha256(ruta_csv),
            ruta_holm.name: S.sha256(ruta_holm),
        },
    }
    (carpeta / f"{SALIDA}.json").write_text(
        json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resumen(salida: dict) -> str:
    cols = ["pregunta", "grupo_1", "n_1", "pct_favorables_1", "grupo_2", "n_2"]
    cols += ["pct_favorables_2", "p_fisher", "p_holm", "fuera_de_prueba"]
    lineas = [salida["cruces"][cols].to_string(index=False)]
    lineas.append(f"Comparadores en la base: {salida['comparadores']}")
    lineas.append(f"Casos para revisar a ojo (varios/otra): {len(salida['revision'])}")
    holm_d54 = salida["holm_d54"]
    lineas.append(
        f"D54 con Holm: {int(holm_d54['bajo_alfa_holm'].sum())} de {N_PRUEBAS_D54} "
        f"bajo {ALFA} (sin corregir: {int(holm_d54['bajo_alfa_sin_corregir'].sum())})"
    )
    return "\n".join(lineas)


def solo_revision(params: dict) -> str:
    """Paso previo del protocolo: hoja de comparadores ambiguos, sin ninguna prueba."""
    base, _ = preparar_base(params)
    ruta = RAIZ_REPO / params["semantico"]["salidas"] / REVISION
    C.escribir_csv(ruta, hoja_de_revision(base), encoding="utf-8-sig")
    conteo = base["comparador"].value_counts().to_dict()
    return f"Comparadores en la base: {conteo}\nHoja para revisar: {ruta}"


def main() -> int:
    lector = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lector.add_argument(
        "--revision",
        action="store_true",
        help="solo escribe la hoja de comparadores ambiguos, sin correr pruebas",
    )
    argumentos = lector.parse_args()
    try:
        params = S.cargar_params()
        if argumentos.revision:
            print(solo_revision(params))
            return 0
        salida = ejecutar(params)
        guardar(params, salida)
        print(resumen(salida))
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
