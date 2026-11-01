"""Cruce de los criterios del marco v0 con la evidencia (Bloque 6, paso 2; D42, D43).

Para cada criterio de config/criterios_v0.yaml toma las unidades de ficha de sus temas
(Prueba 2b, e5, semilla medoide), y cuenta informes y estudios (base 196 / 193), su
peso de evidencia (A calidad MMAT, B diseño, C pertinencia), nivel, disciplina,
dirección del efecto, la sensibilidad sin los estudios de peso bajo y cuántas
unidades solo dicen que el estudio «no reporta» el dato. Escribe tablas numéricas
en outputs/tablas/ (se versionan) y los IDs, ejemplos y similares con texto en
outputs/semantico/ (ignorado).
Falla (código 1) si falta un archivo o una columna, o si un conteo no cuadra.
Correr con .venv-semantico (los embeddings de e5 necesitan torch).
"""

from __future__ import annotations

import json
import os
import re
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from rs_pipeline import semantico_04 as S
from rs_pipeline import semantico_texto as T
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ_REPO = S.RAIZ_REPO
ETIQUETAS_PESO = ["bajo", "medio", "alto"]
MMAT_RESPUESTA = re.compile(r"^(Sí|No se puede saber|No)\b")
SIN_COMPARACION = re.compile(r"^\W*(?:\[F\]\s*)?ninguna", re.IGNORECASE)
NIVEL_GRUPO = {
    "media": "secundaria",
    "secundaria básica": "secundaria",
    "secundaria (sin precisar)": "secundaria",
    "primer año universitario": "universitario",
    "universitario: 2.º año o superior": "universitario",
    "universitario: año no reportado": "universitario",
    "mixto": "otro",
    "formación docente": "otro",
}
DIRECCIONES = [
    "favorable",
    "mixto",
    "sin_diferencia",
    "no_comparativo",
    "otro",
]
DISCIPLINAS = ["física", "química", "biología", "ciencias integradas", "otra"]
CAMPOS_REPORTE = [
    "oe2_herramienta",
    "oe2_andamiaje",
    "oe2_retroalimentacion",
    "oe2_interactividad",
    "oe2_dispositivo",
    "oe2_conectividad",
    "oe2_idioma_accesibilidad",
    "oe2_costo_licencia",
    "oe2_usabilidad_calidad",
]
# Frases con las que la ficha dice que el estudio no informa el dato (D43).
NO_REPORTA = re.compile(
    r"\bno\s+(?:se\s+)?(?:reporta|reportan|menciona|mencionan|especifica|"
    r"especifican|declara|detalla|indica|describe|informa|evalúa|evaluó|evaluaron)\b|"
    r"\bsin\s+(?:datos|información|reporte|medición)\b|"
    r"\bno\s+hay\s+(?:datos|medición)\b",
    re.IGNORECASE,
)
AUSENCIA_AL_INICIO = re.compile(r"\s*(?:no\s+hay|sin)\b", re.IGNORECASE)
SEGMENTO = re.compile(r"[;()]\s*|\.\s+|\.$|\s[—–]\s")


# --- Peso de la evidencia (D43) --------------------------------------------------


def respuestas_mmat(texto: str, id_informe: str) -> list[str]:
    """Las 5 respuestas (Sí / No / No se puede saber) de mmat_items."""
    partes = [p.strip() for p in texto.split(" || ")]
    if len(partes) != 5:
        fallar(f"{id_informe}: mmat_items tiene {len(partes)} ítems, no 5")
    respuestas = []
    for parte in partes:
        encontrada = MMAT_RESPUESTA.match(parte)
        if not encontrada:
            fallar(f"{id_informe}: ítem MMAT sin Sí / No / No se puede saber")
        respuestas.append(encontrada.group(1))
    return respuestas


def puntos_a(fila: pd.Series, respuestas: list[str]) -> int:
    """2 alta (3+ «Sí»), 1 media (2), 0 baja (0-1 o filtro 1 distinto de «Sí»)."""
    si = respuestas.count("Sí")
    if fila["mmat_s1"] != "Sí" or si <= 1:
        return 0
    return 1 if si == 2 else 2


def puntos_b(fila: pd.Series) -> int:
    """2 comparativo con control, 1 pre-post de un grupo, 0 sin comparación."""
    if fila["pre_post_un_grupo"] == "1":
        return 1
    sin_comparacion = SIN_COMPARACION.match(fila["comparacion"].strip())
    if sin_comparacion or fila["oe1_direccion_norm"] == "no comparativo":
        return 0
    return 2


def puntos_c(fila: pd.Series) -> int:
    """2 secundaria, 1 primer año/2.º año/docente/mixto, 0 dudoso o sin año."""
    if fila["nivel_dudoso"] == "1" or fila["nivel_norm"] == (
        "universitario: año no reportado"
    ):
        return 0
    return 2 if NIVEL_GRUPO[fila["nivel_norm"]] == "secundaria" else 1


def peso_suma(a: int, b: int, c: int) -> str:
    total = a + b + c
    return ETIQUETAS_PESO[2 if total >= 5 else (1 if total >= 3 else 0)]


def peso_minimo(a: int, b: int, c: int) -> str:
    return ETIQUETAS_PESO[min(a, b, c)]


def etiqueta_direccion(valor: str, id_informe: str) -> str:
    if valor.startswith("otro"):
        return "otro"
    claves = {
        "favorable a la simulación": "favorable",
        "mixto": "mixto",
        "sin diferencia": "sin_diferencia",
        "no comparativo": "no_comparativo",
    }
    if valor not in claves:
        fallar(f"{id_informe}: dirección del efecto desconocida '{valor}'")
    return claves[valor]


def asignar_estudios(tabla: pd.DataFrame, esperados: int) -> pd.Series:
    """Id de estudio por informe: el menor id del par que comparte estudio."""
    socio = tabla["estudio_compartido_con"].str.strip()
    por_id = dict(zip(tabla["id"], socio, strict=True))
    for id_informe, otro in por_id.items():
        if otro and por_id.get(otro) != id_informe:
            fallar(f"{id_informe}: estudio_compartido_con '{otro}' no es recíproco")
    estudios = pd.Series(
        [min(i, o) if o else i for i, o in zip(tabla["id"], socio, strict=True)],
        index=tabla.index,
    )
    if estudios.nunique() != esperados:
        fallar(f"Hay {estudios.nunique()} estudios y prisma_counts declara {esperados}")
    return estudios


def tabla_de_informes(tabla: pd.DataFrame, estudios: pd.Series) -> pd.DataFrame:
    """Por informe: respuestas MMAT, puntos A/B/C y pesos (suma y mínimo)."""
    filas = []
    for fila, estudio in zip(tabla.to_dict("records"), estudios, strict=True):
        serie = pd.Series(fila)
        respuestas = respuestas_mmat(fila["mmat_items"], fila["id"])
        a, b, c = puntos_a(serie, respuestas), puntos_b(serie), puntos_c(serie)
        filas.append(
            {
                "id": fila["id"],
                "estudio": estudio,
                "respuestas": respuestas,
                "A": a,
                "B": b,
                "C": c,
                "puntos": a + b + c,
                "peso_suma": peso_suma(a, b, c),
                "peso_minimo": peso_minimo(a, b, c),
                "nivel": NIVEL_GRUPO[fila["nivel_norm"]],
                "disciplina": fila["disciplina_norm"],
                "direccion": etiqueta_direccion(fila["oe1_direccion_norm"], fila["id"]),
            }
        )
    return pd.DataFrame(filas)


def tabla_de_estudios(informes: pd.DataFrame) -> pd.DataFrame:
    """Un renglón por estudio: el informe de más puntos (a igual, el de menor id)."""
    ordenada = informes.sort_values(["estudio", "puntos", "id"], ascending=[1, 0, 1])
    return ordenada.groupby("estudio", as_index=False).first().set_index("estudio")


def tabla_mmat_items(informes: pd.DataFrame, tabla: pd.DataFrame) -> pd.DataFrame:
    """Anexo: respuestas ítem por ítem, sin texto ni puntaje global."""
    salida = pd.DataFrame(
        {
            "id": informes["id"],
            "estudio": informes["estudio"],
            "mmat_categoria": tabla["mmat_categoria_norm"],
            "filtro_1": tabla["mmat_s1"],
            "filtro_2": tabla["mmat_s2"],
        }
    )
    for k in range(5):
        salida[f"item_{k + 1}"] = [r[k] for r in informes["respuestas"]]
    permitidas = {"Sí", "No", "No se puede saber"}
    columnas = ["filtro_1", "filtro_2", *[f"item_{k}" for k in range(1, 6)]]
    if not set(salida[columnas].to_numpy().ravel()) <= permitidas:
        fallar(
            "La tabla de ítems MMAT trae algo distinto de Sí / No / No se puede saber"
        )
    return salida


# --- Unidades «no reporta» ---------------------------------------------------------


def tiene_contenido(segmento: str) -> bool:
    """Un segmento con «no reporta» sigue aportando dato si, sin la etiqueta antes
    de «:» y sin esa frase, le quedan 3 palabras o más. «No hay datos de X» o
    «sin datos de X» al inicio ya es toda una ausencia."""
    if not NO_REPORTA.search(segmento):
        return True
    cola = segmento.split(":")[-1]
    if AUSENCIA_AL_INICIO.match(cola):
        return False
    resto = NO_REPORTA.sub(" ", cola)
    return len(re.findall(r"\w+", resto)) >= 3


def grupo_de_reporte(texto: str) -> str:
    """vacio, solo_no_reporta, mixta (hay contenido y «no reporta») o real."""
    limpio = T.limpiar_ficha(texto)
    segmentos = [s.strip() for s in SEGMENTO.split(limpio) if re.search(r"\w", s)]
    if not segmentos:
        return "vacio"
    if not any(NO_REPORTA.search(s) for s in segmentos):
        return "real"
    return "mixta" if any(tiene_contenido(s) for s in segmentos) else "solo_no_reporta"


def unidades_con_tema(params: dict, tabla: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Unidades oe2 con el tema de e5 (semilla medoide) y su grupo de reporte."""
    cfg, privada = params["semantico"], RAIZ_REPO / params["semantico"]["salidas"]
    unidades, _ = S.unidades_prueba2(cfg, tabla)
    unidades = [u for u in unidades if u["oe"] == "oe2"]
    metricas = json.loads(
        (RAIZ_REPO / cfg["salidas_metricas"] / "prueba2b_metricas.json").read_text(
            encoding="utf-8"
        )
    )
    semilla = metricas["modelos"]["principal"]["semilla_medoide"]
    ruta = privada / f"asignaciones_prueba2b_principal_s{semilla}.csv"
    asignadas = pd.read_csv(ruta)
    if list(asignadas["id_unidad"]) != [u["id"] for u in unidades]:
        fallar(f"{ruta.name} no corresponde a las unidades actuales de las fichas")
    datos = pd.DataFrame(unidades).rename(columns={"id": "id_unidad"})
    datos["tema"] = asignadas["tema"].to_numpy()
    datos["grupo"] = [grupo_de_reporte(t) for t in datos["texto"]]
    return datos, {"ruta": ruta, "semilla": semilla, "sha256": S.sha256(ruta)}


def reporte_por_campo(tabla: pd.DataFrame) -> pd.DataFrame:
    """Por campo de ficha: en cuántos de los 196 informes el campo entero no reporta."""
    filas = []
    for campo in CAMPOS_REPORTE:
        grupos = tabla[campo].map(grupo_de_reporte).value_counts()
        n = len(tabla)
        filas.append(
            {
                "campo": campo,
                "n_informes_solo_no_reporta": int(grupos.get("solo_no_reporta", 0)),
                "n_informes_mixta": int(grupos.get("mixta", 0)),
                "n_informes_real": int(grupos.get("real", 0)),
                "n_informes_vacio": int(grupos.get("vacio", 0)),
                "pct_solo_no_reporta_de_196": round(
                    100 * grupos.get("solo_no_reporta", 0) / n, 1
                ),
            }
        )
    return pd.DataFrame(filas)


# --- Cruce por criterio ------------------------------------------------------------


def contar(serie: pd.Series, categorias: list[str], prefijo: str) -> dict:
    cuenta = serie.value_counts()
    return {f"{prefijo}{c}": int(cuenta.get(c, 0)) for c in categorias}


def fila_de_reporte(u: pd.DataFrame) -> dict:
    por_grupo = u["grupo"].value_counts()
    solo = int(por_grupo.get("solo_no_reporta", 0))
    mixta = int(por_grupo.get("mixta", 0))
    con_contenido = u[u["grupo"].isin(["real", "mixta"])]["informe"].nunique()
    informes_solo = u.groupby("informe")["grupo"].apply(
        lambda g: bool((g == "solo_no_reporta").all())
    )
    return {
        "n_unidades_real": int(por_grupo.get("real", 0)),
        "n_unidades_mixta": mixta,
        "n_unidades_solo_no_reporta": solo,
        "pct_unidades_solo_no_reporta": round(100 * solo / len(u), 1),
        "supera_20_pct_no_reporta": bool(100 * solo / len(u) > 20),
        "pct_unidades_con_no_reporta": round(100 * (solo + mixta) / len(u), 1),
        "supera_20_pct_con_no_reporta": bool(100 * (solo + mixta) / len(u) > 20),
        "n_informes_con_contenido": int(con_contenido),
        "n_informes_solo_no_reporta": int(informes_solo.sum()),
    }


def fila_de_criterio(
    criterio: dict,
    unidades: pd.DataFrame,
    informes: pd.DataFrame,
    estudios: pd.DataFrame,
) -> dict:
    u = unidades[unidades["tema"].isin(criterio["temas_origen"])]
    ids = sorted(u["informe"].unique())
    e = estudios.loc[sorted(informes.set_index("id").loc[ids, "estudio"].unique())]
    sin_bajo_suma = e[e["peso_suma"] != "bajo"]
    fila = {
        "id_criterio": criterio["id"],
        "estado": criterio["estado"],
        "temas_origen": " ".join(str(t) for t in criterio["temas_origen"]),
        "n_unidades": len(u),
        "n_informes": len(ids),
        "n_estudios": len(e),
    }
    fila |= contar(e["peso_suma"], ETIQUETAS_PESO[::-1], "suma_")
    fila |= contar(e["peso_minimo"], ETIQUETAS_PESO[::-1], "minimo_")
    fila["n_estudios_sin_bajo_suma"] = len(sin_bajo_suma)
    fila["n_estudios_sin_bajo_minimo"] = int((e["peso_minimo"] != "bajo").sum())
    fila |= contar(e["nivel"], ["secundaria", "universitario", "otro"], "nivel_")
    fila |= contar(e["disciplina"], DISCIPLINAS, "disciplina_")
    fila |= contar(e["direccion"], DIRECCIONES, "direccion_")
    fila |= contar(sin_bajo_suma["direccion"], DIRECCIONES, "direccion_sin_bajo_suma_")
    return fila | fila_de_reporte(u)


def solapamiento(unidades: pd.DataFrame, a: int, b: int) -> dict:
    """Informes que comparten dos temas (aviso si pasan de 70 % en alguno)."""
    sa = set(unidades[unidades["tema"] == a]["informe"])
    sb = set(unidades[unidades["tema"] == b]["informe"])
    comunes = len(sa & sb)
    return {
        "temas": [a, b],
        "informes_a": len(sa),
        "informes_b": len(sb),
        "informes_comunes": comunes,
        "pct_de_a": round(100 * comunes / len(sa), 1),
        "pct_de_b": round(100 * comunes / len(sb), 1),
        "supera_70_pct": bool(comunes / len(sa) > 0.7 or comunes / len(sb) > 0.7),
    }


def ejemplos_de_reporte(
    criterio: dict, unidades: pd.DataFrame, cantidad: int, semilla: int
) -> pd.DataFrame:
    """`cantidad` unidades al azar (semilla fija) por grupo de reporte."""
    u = unidades[unidades["tema"].isin(criterio["temas_origen"])]
    azar = np.random.default_rng(semilla)
    filas = []
    for grupo in ("real", "mixta", "solo_no_reporta"):
        ids = sorted(u[u["grupo"] == grupo]["id_unidad"])
        if not ids:
            continue
        elegidas = azar.choice(ids, size=min(cantidad, len(ids)), replace=False)
        for k, id_unidad in enumerate(elegidas, start=1):
            texto = u.loc[u["id_unidad"] == id_unidad, "texto"].iloc[0]
            filas.append(
                {
                    "id_criterio": criterio["id"],
                    "grupo": grupo,
                    "ejemplo": k,
                    "id_unidad": id_unidad,
                    "texto": texto,
                }
            )
    return pd.DataFrame(filas)


# --- Candidatos parecidos (embeddings e5) --------------------------------------------


def candidatos_parecidos(
    marco: dict, unidades: pd.DataFrame, params: dict, cuantos: int
) -> pd.DataFrame:
    """Los `cuantos` oe2_criterios_candidatos más cercanos (coseno) a cada enunciado."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    modelo = params["semantico"]["modelos"]["principal"]
    pool = unidades[unidades["campo"] == "oe2_criterios_candidatos"].reset_index(
        drop=True
    )
    encoder = S.cargar_modelo(modelo, "mps")
    e_pool, _ = S.embeber(encoder, modelo["prefijo"], list(pool["texto"]))
    enunciados = [c["enunciado"] for c in marco["criterios"]]
    e_crit, _ = S.embeber(encoder, modelo["prefijo"], enunciados)
    S.liberar(encoder)
    filas = []
    for criterio, vector in zip(marco["criterios"], e_crit, strict=True):
        similitud = e_pool @ vector
        for rango, i in enumerate(np.argsort(-similitud, kind="stable")[:cuantos], 1):
            filas.append(
                {
                    "id_criterio": criterio["id"],
                    "rango": rango,
                    "coseno": round(float(similitud[i]), 4),
                    "id_unidad": pool.loc[i, "id_unidad"],
                    "informe": pool.loc[i, "informe"],
                    "tema": int(pool.loc[i, "tema"]),
                    "texto": pool.loc[i, "texto"],
                }
            )
    return pd.DataFrame(filas)


# --- Ejecución -----------------------------------------------------------------------


def escribir_csv(ruta: Path, tabla: pd.DataFrame, **opciones: object) -> str:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(ruta, index=False, lineterminator="\n", **opciones)
    return S.sha256(ruta)


def trazabilidad(params: dict, entradas: dict, extra: dict) -> dict:
    return {
        "entradas": entradas,
        "reglas": {
            "A": "3+ «Sí» en los 5 ítems MMAT = alta, 2 = media, 0-1 o filtro 1 "
            "distinto de «Sí» = baja (el conteo solo agrupa; no es un puntaje global)",
            "B": "pre-post de un grupo = medio; sin comparación o no comparativo = "
            "bajo; "
            "el resto = alto (comparativo con control)",
            "C": "secundaria = 2; primer año, 2.º año, formación docente y mixto = 1; "
            "nivel_dudoso o año no reportado = 0",
            "peso_suma": "puntos A+B+C (0-2 cada uno): 5-6 alto, 3-4 medio, 0-2 bajo",
            "peso_minimo": "el menor de los tres puntos: 2 alto, 1 medio, 0 bajo",
            "estudio": "atributos del informe de más puntos del estudio",
            "no_reporta": NO_REPORTA.pattern,
        },
        "versiones": {
            "pandas": version("pandas"),
            "numpy": version("numpy"),
            "python": sys.version.split()[0],
        },
    } | extra


def ejecutar(params: dict) -> dict:
    cfg = params["semantico"]
    privada, tablas = (
        RAIZ_REPO / cfg["salidas"],
        RAIZ_REPO / params["salidas"]["tablas"],
    )
    matriz = S.cargar_matriz(params)
    tabla = matriz["tabla"]
    ruta_marco = RAIZ_REPO / "config" / "criterios_v0.yaml"
    marco = yaml.safe_load(ruta_marco.read_text(encoding="utf-8"))
    conteos = json.loads((RAIZ_REPO / params["prisma_counts_vigente"]).read_text())
    estudios_id = asignar_estudios(tabla, conteos["incluidos_estudios"])
    informes = tabla_de_informes(tabla, estudios_id)
    estudios = tabla_de_estudios(informes)
    unidades, asignaciones = unidades_con_tema(params, tabla)
    unidades["estudio"] = unidades["informe"].map(informes.set_index("id")["estudio"])
    filas = [
        fila_de_criterio(c, unidades, informes, estudios) for c in marco["criterios"]
    ]
    resultado = pd.DataFrame(filas)
    por_campo = reporte_por_campo(tabla)
    entradas = {
        "matriz_normalizada": {
            "archivo": str(matriz["ruta"].relative_to(RAIZ_REPO)),
            "sha256": matriz["sha256"],
        },
        "marco_de_criterios": {
            "archivo": "config/criterios_v0.yaml",
            "sha256": S.sha256(ruta_marco),
        },
        "asignaciones_e5_prueba2b": {
            "archivo": asignaciones["ruta"].name,
            "semilla": asignaciones["semilla"],
            "sha256": asignaciones["sha256"],
        },
        "prisma_counts": params["prisma_counts_vigente"],
        "modelo_embeddings": cfg["modelos"]["principal"],
    }
    mmat = tabla_mmat_items(informes, tabla)
    hash_mmat = escribir_csv(
        tablas / "mmat_items_por_informe.csv", mmat, encoding="utf-8"
    )
    hash_cruce = escribir_csv(
        tablas / "criterios_v0_evidencia.csv", resultado, encoding="utf-8"
    )
    hash_campos = escribir_csv(
        tablas / "criterios_v0_reporte_por_campo.csv", por_campo, encoding="utf-8"
    )
    ruta_candidatos = privada / "criterios_v0_candidatos_similares.csv"
    candidatos = candidatos_parecidos(marco, unidades, params, 5)
    escribir_csv(ruta_candidatos, candidatos, encoding="utf-8-sig")
    ids = unidades[
        unidades["tema"].isin(
            {t for c in marco["criterios"] for t in c["temas_origen"]}
        )
    ]
    ids = ids.assign(
        id_criterio=ids["tema"].map(
            {t: c["id"] for c in marco["criterios"] for t in c["temas_origen"]}
        )
    )
    escribir_csv(
        privada / "criterios_v0_ids_unidades.csv",
        ids.drop(columns=["texto"]),
        encoding="utf-8",
    )
    ejemplos = pd.concat(
        [ejemplos_de_reporte(c, unidades, 3, 0) for c in marco["criterios"]]
    )
    escribir_csv(
        privada / "criterios_v0_ejemplos_reporte.csv", ejemplos, encoding="utf-8-sig"
    )
    cruce_6_12 = solapamiento(unidades, 6, 12)
    base = {"base": "196 informes y 193 estudios (sin los 5 excluidos por nivel)"}
    salidas = {
        "criterios_v0_evidencia.csv": hash_cruce,
        "criterios_v0_reporte_por_campo.csv": hash_campos,
        "mmat_items_por_informe.csv": hash_mmat,
    }
    for nombre, extra in {
        "criterios_v0_evidencia": {
            "salida": {"archivo": "criterios_v0_evidencia.csv", "sha256": hash_cruce},
            "solapamiento_temas_6_12": cruce_6_12,
            "reporte_por_campo": por_campo.to_dict("records"),
            **base,
        },
        "mmat_items_por_informe": {
            "salida": {"archivo": "mmat_items_por_informe.csv", "sha256": hash_mmat},
            **base,
        },
    }.items():
        (tablas / f"{nombre}.json").write_text(
            json.dumps(
                trazabilidad(params, entradas, extra), ensure_ascii=False, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
    return {
        "resultado": resultado,
        "por_campo": por_campo,
        "cruce_6_12": cruce_6_12,
        "salidas": salidas,
    }


def reporte(salida: dict) -> list[str]:
    r = salida["resultado"]
    columnas = [
        "id_criterio",
        "n_unidades",
        "n_informes",
        "n_estudios",
        "suma_alto",
        "suma_medio",
        "suma_bajo",
        "n_estudios_sin_bajo_suma",
        "n_estudios_sin_bajo_minimo",
        "pct_unidades_solo_no_reporta",
        "pct_unidades_con_no_reporta",
        "n_informes_con_contenido",
        "n_informes_solo_no_reporta",
        "supera_20_pct_no_reporta",
        "supera_20_pct_con_no_reporta",
    ]
    return [
        r[columnas].to_string(index=False),
        "",
        salida["por_campo"].to_string(index=False),
        "",
        f"solapamiento temas 6-12: {salida['cruce_6_12']}",
    ]


def main() -> int:
    try:
        if "--ejemplos" in sys.argv:
            params = S.cargar_params()
            ruta = (
                RAIZ_REPO
                / params["semantico"]["salidas"]
                / "criterios_v0_ejemplos_reporte.csv"
            )
            tabla = pd.read_csv(ruta, encoding="utf-8-sig")
            for fila in tabla[tabla["id_criterio"] == "C09"].to_dict("records"):
                print(f"[{fila['grupo']} {fila['ejemplo']}] {fila['texto'][:220]}")
            return 0
        print("\n".join(reporte(ejecutar(S.cargar_params()))))
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
