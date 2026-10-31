"""Mini-sprint semántico: ¿sirve BERTopic con embeddings multilingües? (Bloque 5).

Se ejecuta con el venv aparte (.venv-semantico), todo local y sin llamadas a la API:
    PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.semantico_04

Prueba 1 (mecánica): trozos del texto completo de 10 informes (Drive, solo lectura).
Prueba 2a: fichas de los 196 informes (oe1_hallazgo, oe2_*, oe4_*).
Prueba 2b: solo oe2_*.
Cada prueba corre con dos modelos (e5 principal y MiniLM de control) y 5 semillas.
Lo que trae texto de los artículos (hoja a ciegas, asignaciones) va a outputs/semantico/
(ignorado por git); a outputs/semantico_metricas/ solo van números.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
import os
import resource
import sys
import time
import warnings
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from rs_pipeline import semantico_metricas as M
from rs_pipeline import semantico_texto as T
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
IDIOMAS = {"inglés", "español", "portugués"}
PRUEBAS = ["prueba1", "prueba2a", "prueba2b"]
ROTULO_PRUEBA = {"prueba1": "P1", "prueba2a": "P2a", "prueba2b": "P2b"}


# --- Lectura de entradas (copia mínima de prisma_02: este venv no lo importa) ---


def leer_env(ruta: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not ruta.is_file():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip("\"'")
    return valores


def raiz_drive(nombre_variable: str) -> Path:
    valor = os.environ.get(nombre_variable) or leer_env(RAIZ_REPO / ".env").get(
        nombre_variable, ""
    )
    if not valor or not Path(valor).expanduser().is_dir():
        fallar(f"{nombre_variable} no está definida o no apunta a una carpeta")
    return Path(valor).expanduser()


def sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def cargar_params() -> dict:
    ruta = RAIZ_REPO / "config" / "params.yaml"
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def ram_maxima_mb() -> float:
    """Pico de memoria del proceso (macOS reporta bytes)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6


def a_json(valor: object) -> object:
    """Convierte numpy a tipos de Python y NaN a null (JSON válido)."""
    if isinstance(valor, dict):
        return {str(k): a_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [a_json(v) for v in valor]
    if isinstance(valor, np.ndarray):
        return a_json(valor.tolist())
    if isinstance(valor, np.generic):
        return a_json(valor.item())
    if isinstance(valor, float) and math.isnan(valor):
        return None
    return valor


# --- Matriz y unidades de análisis ---------------------------------------------


def nombre_matriz(params: dict) -> str:
    return f"{Path(params['archivos']['extraccion']).stem}_normalizada.csv"


def columnas_de_ficha(cfg: dict) -> list[str]:
    return [c for campos in cfg["prueba2"]["campos"].values() for c in campos]


def cargar_matriz(params: dict) -> dict:
    """Matriz normalizada sin los excluidos por nivel; comprueba hash y 196 informes."""
    cfg = params["semantico"]
    ruta = RAIZ_REPO / params["salidas"]["procesados"] / nombre_matriz(params)
    registro = json.loads(ruta.with_suffix(".json").read_text(encoding="utf-8"))
    if sha256(ruta) != registro["salida"]["sha256"]:
        fallar("La matriz cambió desde que se normalizó: corre normalizar_01")
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8")
    necesarias = ["id", "idioma", "disciplina_norm", "nivel_norm", "excluido_nivel"]
    faltan = [c for c in [*necesarias, *columnas_de_ficha(cfg)] if c not in tabla]
    if faltan:
        fallar(f"La matriz normalizada no tiene las columnas {faltan}")
    incluidos = tabla[tabla["excluido_nivel"] == "0"].reset_index(drop=True)
    ruta_conteos = RAIZ_REPO / params["prisma_counts_vigente"]
    declarado = json.loads(ruta_conteos.read_text(encoding="utf-8"))
    if len(incluidos) != declarado["incluidos_informes"]:
        fallar(
            f"Hay {len(incluidos)} informes incluidos y prisma_counts declara "
            f"{declarado['incluidos_informes']}"
        )
    return {"tabla": incluidos, "ruta": ruta, "sha256": sha256(ruta)}


def unidades_prueba1(params: dict, tabla: pd.DataFrame) -> dict:
    """Trozos de los 10 informes, con el tamaño propio de cada modelo."""
    cfg = params["semantico"]
    p1 = cfg["prueba1"]
    raiz = raiz_drive(params["drive_root_env"])
    idioma = tabla.set_index("id")["idioma"].to_dict()
    ausentes = [i for i in p1["informes"] if i not in idioma]
    if ausentes:
        fallar(f"Informes de la Prueba 1 que no están entre los incluidos: {ausentes}")
    if not {idioma[i] for i in p1["informes"]} <= IDIOMAS:
        fallar("Idioma fuera de inglés, español y portugués en la Prueba 1")
    datos = {}
    for clave, modelo in cfg["modelos"].items():
        unidades, estadisticas = [], {}
        for id_ in p1["informes"]:
            ruta = raiz / p1["ruta_textos"] / f"{id_}.txt"
            if not ruta.is_file():
                fallar(f"No existe el texto completo: {ruta}")
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            trozos, est = T.trozos_de_informe(
                texto, id_, modelo["palabras_por_trozo"], p1
            )
            unidades += [
                {
                    "id": f"{id_}#{k}",
                    "informe": id_,
                    "idioma": idioma[id_],
                    "texto": t["texto"],
                    "oraciones": [f"{id_}:{i}" for i in t["oraciones"]],
                }
                for k, t in enumerate(trozos)
            ]
            estadisticas[id_] = est | {
                "sha256_texto": sha256(ruta),
                "idioma": idioma[id_],
            }
        datos[clave] = {"unidades": unidades, "estadisticas": estadisticas}
    return datos


def unidades_prueba2(cfg: dict, tabla: pd.DataFrame) -> tuple[list[dict], dict]:
    """Una unidad por campo de ficha (y por criterio) de cada informe incluido."""
    p2 = cfg["prueba2"]
    unidades, descartadas = [], {}
    for oe, campos in p2["campos"].items():
        for campo in campos:
            descartadas[campo] = 0
            for fila in tabla.to_dict("records"):
                textos = T.unidades_de_campo(fila[campo], campo, p2)
                unidades += [
                    {
                        "id": f"{fila['id']}|{campo}|{k}",
                        "informe": fila["id"],
                        "campo": campo,
                        "oe": oe,
                        "disciplina": fila["disciplina_norm"],
                        "nivel": fila["nivel_norm"],
                        "texto": texto,
                    }
                    for k, texto in enumerate(textos)
                ]
                if not textos:
                    descartadas[campo] += 1
    return unidades, descartadas


# --- Embeddings ------------------------------------------------------------------


def cargar_modelo(modelo: dict, dispositivo: str):  # noqa: ANN201
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        modelo["id"], revision=modelo["revision"], device=dispositivo
    )


def embeber(encoder, prefijo: str, textos: list[str]) -> tuple[np.ndarray, float]:
    """Embeddings normalizados y segundos (tras una pasada de calentamiento)."""
    texto = [prefijo + t for t in textos]
    encoder.encode(texto[:8], batch_size=8, show_progress_bar=False)
    inicio = time.perf_counter()
    e = encoder.encode(
        texto, batch_size=16, normalize_embeddings=True, show_progress_bar=False
    )
    return np.asarray(e, dtype=np.float32), time.perf_counter() - inicio


def pct_truncados(encoder, prefijo: str, textos: list[str]) -> float:
    largos = [len(encoder.tokenizer(prefijo + t)["input_ids"]) for t in textos]
    return 100 * float((np.array(largos) > encoder.max_seq_length).mean())


def liberar(encoder) -> None:
    import torch

    del encoder
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def embeddings_de_modelo(
    clave: str, modelo: dict, p1: list[dict], p2: list[dict]
) -> dict:
    """Embeddings de la Prueba 1 (MPS y CPU) y de las fichas (MPS) de un modelo."""
    textos1 = [u["texto"] for u in p1]
    textos2 = [u["texto"] for u in p2]
    encoder = cargar_modelo(modelo, "mps")
    e1, seg_mps = embeber(encoder, modelo["prefijo"], textos1)
    e2, seg_fichas = embeber(encoder, modelo["prefijo"], textos2)
    truncados = pct_truncados(encoder, modelo["prefijo"], textos1)
    tokens = encoder.max_seq_length
    liberar(encoder)
    encoder = cargar_modelo(modelo, "cpu")
    e1_cpu, seg_cpu = embeber(encoder, modelo["prefijo"], textos1)
    liberar(encoder)
    return {
        "e1": e1,
        "e2": e2,
        "metricas": {
            "unidades_prueba1": len(p1),
            "unidades_fichas": len(p2),
            "segundos_prueba1_mps": seg_mps,
            "segundos_prueba1_cpu": seg_cpu,
            "segundos_fichas_mps": seg_fichas,
            "coseno_mps_cpu_medio": float((e1 * e1_cpu).sum(1).mean()),
            "pct_trozos_truncados": truncados,
            "max_seq_length": tokens,
            "dimension": int(e1.shape[1]),
            "ram_maxima_mb": ram_maxima_mb(),
        },
        "clave": clave,
    }


# --- BERTopic ------------------------------------------------------------------


def lista_de_stopwords(cfg: dict) -> list[str]:
    ruta = RAIZ_REPO / cfg["stopwords"]
    por_idioma = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return sorted(
        {str(p).lower() for palabras in por_idioma.values() for p in palabras}
    )


def ajustar_bertopic(textos: list[str], e: np.ndarray, semilla: int, cfg: dict):  # noqa: ANN201
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modelo = BERTopic(
            umap_model=UMAP(random_state=semilla, **cfg["umap"]),
            hdbscan_model=HDBSCAN(
                min_cluster_size=cfg["min_topic_size"],
                metric="euclidean",
                cluster_selection_method="eom",
                prediction_data=True,
            ),
            vectorizer_model=CountVectorizer(
                stop_words=lista_de_stopwords(cfg), token_pattern=M.TOKEN.pattern
            ),
            top_n_words=cfg["palabras_clave"],
            calculate_probabilities=False,
        )
        etiquetas, _ = modelo.fit_transform(textos, embeddings=e)
    return modelo, np.asarray(etiquetas)


def palabras_de_temas(modelo, temas: set[int], n: int) -> dict[int, list[str]]:
    return {t: [p for p, _ in modelo.get_topic(t)][:n] for t in sorted(temas)}


def corrida(
    textos: list[str], e: np.ndarray, semilla: int, cfg: dict, indice: dict
) -> dict:
    """Una corrida de BERTopic con su coherencia real y la del azar (barajado)."""
    inicio = time.perf_counter()
    modelo, etiquetas = ajustar_bertopic(textos, e, semilla, cfg)
    segundos = time.perf_counter() - inicio
    n = cfg["palabras_clave"]
    temas = set(etiquetas.tolist()) - {M.SIN_TEMA}
    palabras = palabras_de_temas(modelo, temas, n)
    detalle = {
        t: {
            "n": int((etiquetas == t).sum()),
            "palabras": palabras[t],
            "docs": list(modelo.get_representative_docs(t) or []),
        }
        for t in sorted(temas)
    }
    azar = np.random.default_rng(cfg["semilla_azar"] + semilla).permutation(etiquetas)
    modelo.update_topics(textos, topics=azar.tolist(), top_n_words=n)
    palabras_azar = palabras_de_temas(modelo, set(azar.tolist()) - {M.SIN_TEMA}, n)
    total = len(textos)
    return {
        "etiquetas": etiquetas,
        "temas": detalle,
        "segundos_ajuste": segundos,
        "npmi_real": M.coherencia(palabras, indice, total),
        "npmi_azar": M.coherencia(palabras_azar, indice, total),
    }


# --- Métricas de una prueba -----------------------------------------------------


def atributos_del_reparto(prueba: str, unidades: list[dict]) -> dict[str, list[str]]:
    if prueba == "prueba1":
        return {"idioma": [u["idioma"] for u in unidades]}
    atributos = {
        "disciplina": [u["disciplina"] for u in unidades],
        "nivel": [u["nivel"] for u in unidades],
    }
    if prueba == "prueba2a":
        atributos["oe"] = [u["oe"] for u in unidades]
    return atributos


def detalle_por_tema(
    etiquetas: np.ndarray, unidades: list[dict], prueba: str
) -> list[dict]:
    """Reparto numérico de cada tema (solo conteos; sin texto)."""
    informes = [u["informe"] for u in unidades]
    por_informe = M.repartos(etiquetas, informes)
    filas = []
    for atributo, valores in atributos_del_reparto(prueba, unidades).items():
        for tema, cuenta in M.repartos(etiquetas, valores).items():
            fila = next((f for f in filas if f["tema"] == tema), None)
            if fila is None:
                fila = {
                    "tema": tema,
                    "n_unidades": sum(cuenta.values()),
                    "n_informes": len(por_informe[tema]),
                    "pct_informe_mas_frecuente": 100
                    * max(por_informe[tema].values())
                    / sum(cuenta.values()),
                }
                filas.append(fila)
            fila[f"reparto_{atributo}"] = cuenta
    return sorted(filas, key=lambda f: f["tema"])


def resumen_de_corrida(
    prueba: str, semilla: int, c: dict, unidades: list[dict], cfg: dict
) -> dict:
    etiquetas = c["etiquetas"]
    resumen = {
        "semilla": semilla,
        "n_unidades": len(etiquetas),
        "n_temas": len(c["temas"]),
        "pct_sin_tema": M.pct_sin_tema(etiquetas),
        "npmi_real": c["npmi_real"],
        "npmi_azar": c["npmi_azar"],
        "segundos_ajuste": c["segundos_ajuste"],
        "tamanos_temas": sorted((t["n"] for t in c["temas"].values()), reverse=True),
    }
    umbral = cfg["prueba1" if prueba == "prueba1" else "prueba2"]["umbral_dominancia"]
    informes = [u["informe"] for u in unidades]
    if prueba == "prueba1":
        resumen["mezcla_idiomas"] = M.mezcla_de_idiomas(
            etiquetas,
            [u["idioma"] for u in unidades],
            cfg["prueba1"]["minimo_pct_idioma"],
        )
        resumen["temas_de_un_documento"] = M.porcentaje_dominado(
            etiquetas, informes, umbral
        )
        return resumen
    for atributo, valores in atributos_del_reparto(prueba, unidades).items():
        resumen[f"dominados_por_{atributo}"] = M.porcentaje_dominado(
            etiquetas, valores, umbral
        )
    if prueba == "prueba2a":
        oe = [u["oe"] for u in unidades]
        resumen["ari_tema_vs_oe"] = M.ari(etiquetas, pd.factorize(pd.Series(oe))[0])
    return resumen


def proyectar_a_oraciones(
    unidades: list[dict], etiquetas: np.ndarray
) -> dict[str, int]:
    return {
        o: int(t)
        for u, t in zip(unidades, etiquetas, strict=True)
        for o in u["oraciones"]
    }


def acuerdo_entre_modelos(prueba: str, datos: dict, corridas: dict) -> dict:
    """ARI entre e5 y MiniLM: 25 pares (cada semilla contra cada semilla)."""
    a, b = "principal", "control"
    if prueba == "prueba1":
        mapas = {
            k: {
                s: proyectar_a_oraciones(datos[k]["unidades"], c["etiquetas"])
                for s, c in corridas[k].items()
            }
            for k in (a, b)
        }
        comunes = sorted(
            set(next(iter(mapas[a].values()))) & set(next(iter(mapas[b].values())))
        )
        vector = lambda k, s: np.array([mapas[k][s][o] for o in comunes])  # noqa: E731
        unidad = "oraciones"
    else:
        vector = lambda k, s: corridas[k][s]["etiquetas"]  # noqa: E731
        unidad = "unidades de ficha"
    pares = [
        {"semillas": [s1, s2], **M.ari(vector(a, s1), vector(b, s2))}
        for s1 in sorted(corridas[a])
        for s2 in sorted(corridas[b])
    ]
    valores = [p["valor"] for p in pares]
    return {
        "unidad_de_comparacion": unidad,
        "media": float(np.nanmean(valores)),
        "minimo": float(np.nanmin(valores)),
        "maximo": float(np.nanmax(valores)),
        "fraccion_usada_media": float(np.mean([p["fraccion_usada"] for p in pares])),
        "pares": pares,
    }


def evaluar_modelo(
    prueba: str, clave: str, datos: dict, corridas: dict, cfg: dict
) -> dict:
    """Resumen numérico de las 5 corridas de un modelo en una prueba."""
    unidades = datos["unidades"]
    resumenes = [
        resumen_de_corrida(prueba, s, c, unidades, cfg)
        for s, c in sorted(corridas.items())
    ]
    asignaciones = {s: c["etiquetas"] for s, c in corridas.items()}
    entre_semillas = M.ari_entre_semillas(asignaciones)
    medoide = M.semilla_medoide(asignaciones)
    medias = {
        "n_temas": float(np.mean([r["n_temas"] for r in resumenes])),
        "pct_sin_tema": float(np.mean([r["pct_sin_tema"] for r in resumenes])),
        "npmi_real": float(np.nanmean([r["npmi_real"] for r in resumenes])),
        "npmi_azar": float(np.nanmean([r["npmi_azar"] for r in resumenes])),
        "corridas_con_npmi_real_mayor": sum(
            r["npmi_real"] > r["npmi_azar"] for r in resumenes
        ),
        "ari_semillas_media": entre_semillas["media"],
    }
    return {
        "corridas": resumenes,
        "ari_entre_semillas": entre_semillas,
        "semilla_medoide": medoide,
        "medias": medias,
        "detalle_por_tema_semilla_medoide": detalle_por_tema(
            asignaciones[medoide], unidades, prueba
        ),
    }


# --- Pruebas completas -----------------------------------------------------------


def ejecutar_prueba(prueba: str, datos: dict, cfg: dict) -> tuple[dict, dict]:
    """5 semillas x 2 modelos; devuelve las métricas y las corridas (con texto)."""
    corridas: dict[str, dict[int, dict]] = {}
    for clave, d in datos.items():
        textos = [u["texto"] for u in d["unidades"]]
        indice = M.indice_invertido(M.conjuntos_de_palabras(textos))
        corridas[clave] = {}
        for semilla in cfg["semillas"]:
            c = corrida(textos, d["e"], semilla, cfg, indice)
            corridas[clave][semilla] = c
            print(
                f"  [{ROTULO_PRUEBA[prueba]}/{clave}/semilla {semilla}] "
                f"{len(c['temas'])} temas, "
                f"{M.pct_sin_tema(c['etiquetas']):.1f} % sin tema, "
                f"{c['segundos_ajuste']:.1f} s",
                flush=True,
            )
    resultado = {
        "unidades": {k: len(d["unidades"]) for k, d in datos.items()},
        "modelos": {
            k: evaluar_modelo(prueba, k, d, corridas[k], cfg) for k, d in datos.items()
        },
        "acuerdo_entre_modelos": acuerdo_entre_modelos(prueba, datos, corridas),
    }
    return resultado, corridas


def subconjunto_oe2(datos: dict) -> dict:
    """Prueba 2b: las mismas unidades y embeddings, solo las de oe2_*."""
    salida = {}
    for clave, d in datos.items():
        indices = [i for i, u in enumerate(d["unidades"]) if u["oe"] == "oe2"]
        salida[clave] = {
            "unidades": [d["unidades"][i] for i in indices],
            "e": d["e"][indices],
        }
    return salida


# --- Hoja de calificación a ciegas -------------------------------------------------


def recortar(texto: str, n: int) -> str:
    palabras = texto.split()
    return " ".join(palabras[:n]) + (" …" if len(palabras) > n else "")


def temas_de_hoja(
    prueba: str, clave: str, semilla: int, c: dict, cfg: dict, maximo: int | None
) -> list[dict]:
    """Temas de una corrida (los más grandes primero) con 10 palabras y 3 fragmentos."""
    hoja = cfg["hoja_ciega"]
    ordenados = sorted(c["temas"].items(), key=lambda x: (-x[1]["n"], x[0]))
    if maximo:
        ordenados = ordenados[:maximo]
    filas = []
    for tema, info in ordenados:
        fragmentos = [recortar(d, hoja["palabras_por_fragmento"]) for d in info["docs"]]
        fragmentos += [""] * (hoja["fragmentos"] - len(fragmentos))
        filas.append(
            {
                "prueba": ROTULO_PRUEBA[prueba],
                "modelo": clave,
                "semilla": semilla,
                "tema": tema,
                "n": info["n"],
                "palabras": ", ".join(info["palabras"]),
                "fragmentos": fragmentos[: hoja["fragmentos"]],
            }
        )
    return filas


def codigos_unicos(rng: np.random.Generator, cantidad: int) -> list[str]:
    alfabeto = np.array(list("ABCDEFGHJKMNPQRSTUVWXYZ23456789"))
    codigos: list[str] = []
    vistos: set[str] = set()
    while len(codigos) < cantidad:
        codigo = "".join(rng.choice(alfabeto, 5))
        if codigo not in vistos:
            vistos.add(codigo)
            codigos.append(codigo)
    return codigos


CALIFICACIONES = ["interpretable", "mixto", "ruido"]


def exigir_hoja_sin_calificar(ruta: Path) -> None:
    """No se sobrescribe una hoja en la que Luis Fer ya puso calificaciones."""
    if not ruta.is_file():
        return
    hoja = pd.read_csv(
        ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig",
        usecols=["calificacion"],
    )  # fmt: skip
    if (hoja["calificacion"].str.strip() != "").any():
        fallar(f"{ruta.name} ya tiene calificaciones: no se sobrescribe")


def escribir_hoja_ciega(
    semillas: dict[str, int], corridas: dict, cfg: dict, carpeta: Path
) -> dict:
    """Hoja de la Prueba 2b con códigos aleatorios (sin modelo ni semilla)."""
    filas = []
    for clave in cfg["modelos"]:
        semilla = semillas[clave]
        filas += temas_de_hoja(
            "prueba2b",
            clave,
            semilla,
            corridas[clave][semilla],
            cfg,
            cfg["hoja_ciega"]["temas_por_modelo"][clave],
        )
    rng = np.random.default_rng(cfg["semilla_codigos"])
    codigos = codigos_unicos(rng, len(filas))
    orden = rng.permutation(len(filas))
    hoja, traduccion = [], []
    for posicion in orden:
        f, codigo = filas[posicion], codigos[posicion]
        fila = {
            "codigo": codigo,
            "prueba": f["prueba"],
            "tamano_del_tema": f["n"],
            "palabras_clave": f["palabras"],
        }
        fila |= {f"fragmento_{k + 1}": t for k, t in enumerate(f["fragmentos"])}
        hoja.append(fila | {"calificacion": ""})
        traduccion.append(
            {
                "codigo": codigo,
                "prueba": f["prueba"],
                "modelo": f["modelo"],
                "semilla": f["semilla"],
                "tema": f["tema"],
                "n_unidades": f["n"],
            }
        )
    exigir_hoja_sin_calificar(carpeta / "hoja_calificacion_ciega_2b.csv")
    carpeta.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(hoja).to_csv(
        carpeta / "hoja_calificacion_ciega_2b.csv",
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )
    pd.DataFrame(traduccion).to_csv(
        carpeta / "traduccion_codigos_2b.csv",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )
    cuenta = pd.DataFrame(traduccion).groupby("modelo").size()
    return {
        "prueba": "P2b",
        "temas_en_la_hoja": len(hoja),
        "por_modelo": {m: int(n) for m, n in cuenta.items()},
    }


def reproducir_corrida_2b(
    clave: str,
    modelo: dict,
    semilla: int,
    unidades: list[dict],
    cfg: dict,
    privada: Path,
) -> dict:
    """Repite la corrida medoide; debe dar las asignaciones ya guardadas."""
    textos = [u["texto"] for u in unidades]
    encoder = cargar_modelo(modelo, "mps")
    e, _ = embeber(encoder, modelo["prefijo"], textos)
    liberar(encoder)
    indice = M.indice_invertido(M.conjuntos_de_palabras(textos))
    c = corrida(textos, e, semilla, cfg, indice)
    guardado = pd.read_csv(privada / f"asignaciones_prueba2b_{clave}_s{semilla}.csv")
    mismas = list(guardado["id_unidad"]) == [u["id"] for u in unidades]
    if not mismas or not np.array_equal(guardado["tema"].to_numpy(), c["etiquetas"]):
        fallar(
            f"{clave}/semilla {semilla}: la repetición no da las asignaciones guardadas"
        )
    return c


def regenerar_hoja_2b(params: dict) -> dict:
    """Rehace solo la hoja a ciegas de la Prueba 2b (no toca las métricas)."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    cfg = params["semantico"]
    privada, publica = RAIZ_REPO / cfg["salidas"], RAIZ_REPO / cfg["salidas_metricas"]
    unidades, _ = unidades_prueba2(cfg, cargar_matriz(params)["tabla"])
    unidades = [u for u in unidades if u["oe"] == "oe2"]
    guardadas = json.loads(
        (publica / "prueba2b_metricas.json").read_text(encoding="utf-8")
    )
    semillas = {k: guardadas["modelos"][k]["semilla_medoide"] for k in cfg["modelos"]}
    corridas = {
        k: {
            semillas[k]: reproducir_corrida_2b(
                k, m, semillas[k], unidades, cfg, privada
            )
        }
        for k, m in cfg["modelos"].items()
    }
    hoja = escribir_hoja_ciega(semillas, corridas, cfg, privada)
    ruta = publica / "veredicto.json"
    veredicto_guardado = json.loads(ruta.read_text(encoding="utf-8"))
    escribir_json(ruta, {**veredicto_guardado, "hoja_a_ciegas": hoja})
    return hoja


# --- Calificación de la hoja a ciegas (Prueba 2b) ----------------------------------


def leer_calificacion_2b(privada: Path) -> pd.DataFrame:
    """Une la hoja calificada con la traducción de códigos; exige valores válidos."""
    hoja = pd.read_csv(
        privada / "hoja_calificacion_ciega_2b.csv", dtype=str, keep_default_na=False,
        encoding="utf-8-sig", usecols=["codigo", "calificacion"],
    )  # fmt: skip
    traduccion = pd.read_csv(
        privada / "traduccion_codigos_2b.csv", dtype={"codigo": str}
    )
    hoja["calificacion"] = hoja["calificacion"].str.strip().str.lower()
    invalidas = sorted(set(hoja["calificacion"]) - set(CALIFICACIONES))
    if invalidas:
        fallar(f"Calificaciones fuera de {CALIFICACIONES}: {invalidas}")
    if len(hoja) != len(traduccion) or set(hoja["codigo"]) != set(traduccion["codigo"]):
        fallar("La hoja calificada y la traducción no tienen los mismos códigos")
    return traduccion.merge(hoja, on="codigo")


def resumen_de_calificacion(grupo: pd.DataFrame, umbrales: dict) -> dict:
    n = len(grupo)
    conteos = {c: int((grupo["calificacion"] == c).sum()) for c in CALIFICACIONES}
    pct = {c: 100 * v / n for c, v in conteos.items()}
    minimo = conteos["interpretable"] >= umbrales["minimo_temas_interpretables"]
    return {
        "n_temas": n, "conteos": conteos, "pct": pct,
        "interpretabilidad": M.juzgar(
            pct["interpretable"],
            umbrales["interpretables_sigue_pct"],
            umbrales["interpretables_no_sigue_pct"],
            True,
        ),
        "minimo_temas_interpretables": "cumple" if minimo else "no cumple",
    }  # fmt: skip


def veredicto_final(criterios: dict) -> str:
    valores = set(criterios.values())
    if "no cumple" in valores or "no calculable" in valores:
        return "no sigue"
    return "intermedio: decide Luis Fer" if "intermedio" in valores else "sigue"


def calificar_hoja_2b(params: dict) -> dict:
    """% interpretables, mixtos y ruido por modelo y el veredicto final de la 2b."""
    cfg = params["semantico"]
    privada, publica = RAIZ_REPO / cfg["salidas"], RAIZ_REPO / cfg["salidas_metricas"]
    unidos = leer_calificacion_2b(privada)
    por_modelo = {
        m: resumen_de_calificacion(g, cfg["umbrales"])
        for m, g in unidos.groupby("modelo")
    }
    ruta_veredicto = publica / "veredicto.json"
    guardado = json.loads(ruta_veredicto.read_text(encoding="utf-8"))
    final = {}
    for modelo, r in por_modelo.items():
        criterios = guardado["criterios"][f"prueba2b/{modelo}"]
        criterios["interpretabilidad"] = r["interpretabilidad"]
        criterios["minimo_temas_interpretables"] = r["minimo_temas_interpretables"]
        final[modelo] = {
            "criterios": criterios,
            "veredicto": veredicto_final(criterios),
        }
    resultado = {
        "prueba": "prueba2b",
        "hoja": {
            "temas": len(unidos),
            "sha256_hoja_calificada": sha256(
                privada / "hoja_calificacion_ciega_2b.csv"
            ),
            "sha256_traduccion": sha256(privada / "traduccion_codigos_2b.csv"),
        },
        "por_modelo": por_modelo,
        "total": resumen_de_calificacion(unidos, cfg["umbrales"]),
        "veredicto_final": final,
        "por_tema": unidos.drop(columns=["codigo", "prueba"]).to_dict("records"),
    }
    escribir_json(publica / "prueba2b_calificacion.json", resultado)
    guardado["veredicto_final_prueba2b"] = final
    escribir_json(ruta_veredicto, guardado)
    return resultado


# --- Veredicto -------------------------------------------------------------------


def veredicto(resultados: dict, embeddings: dict, cfg: dict) -> dict:
    """Cada criterio frente a sus umbrales; la interpretabilidad queda pendiente."""
    u = cfg["umbrales"]
    salida = {}
    for prueba in PRUEBAS:
        for clave, r in resultados[prueba]["modelos"].items():
            v = M.veredicto_estabilidad(r["medias"], u)
            if prueba == "prueba1":
                segundos = embeddings[clave]["metricas"]["segundos_prueba1_mps"]
                v["tiempo_embeddings_mps"] = (
                    "cumple" if segundos < u["tiempo_embeddings_s"] else "no cumple"
                )
                mezcla = float(
                    np.nanmean(
                        [c["mezcla_idiomas"]["pct_mezclan"] for c in r["corridas"]]
                    )
                )
                v["mezcla_de_idiomas"] = M.juzgar(
                    mezcla, u["mezcla_idiomas_sigue_pct"], 1e-6, True
                )
                doc = float(
                    np.nanmean(
                        [
                            c["temas_de_un_documento"]["pct_dominados"]
                            for c in r["corridas"]
                        ]
                    )
                )
                v["temas_de_un_documento"] = M.juzgar(
                    doc,
                    u["temas_de_un_documento_no_util_pct"],
                    u["temas_de_un_documento_no_util_pct"],
                    False,
                )
            v["interpretabilidad"] = "pendiente (hoja a ciegas de Luis Fer)"
            salida[f"{prueba}/{clave}"] = v
    rojos = [
        f"{k}: {c}" for k, v in salida.items() for c, x in v.items() if x == "no cumple"
    ]
    return {"criterios": salida, "no_cumple": rojos}


# --- Salidas ---------------------------------------------------------------------


def metadatos(params: dict, matriz: dict) -> dict:
    cfg = params["semantico"]
    paquetes = [
        "bertopic",
        "sentence-transformers",
        "torch",
        "umap-learn",
        "hdbscan",
        "transformers",
        "numpy",
        "pandas",
        "scikit-learn",
    ]
    rutas = {
        "matriz_normalizada": matriz["ruta"],
        "params.yaml": RAIZ_REPO / "config/params.yaml",
        "prisma_counts_vigente": RAIZ_REPO / params["prisma_counts_vigente"],
        "stopwords": RAIZ_REPO / cfg["stopwords"],
        "requirements_semantico": RAIZ_REPO / cfg["requirements"],
    }
    return {
        "script": "src/rs_pipeline/semantico_04.py",
        "python": sys.version.split()[0],
        "versiones": {p: version(p) for p in paquetes},
        "modelos": {
            k: {"id": m["id"], "revision": m["revision"]}
            for k, m in cfg["modelos"].items()
        },
        "entradas_sha256": {n: sha256(r) for n, r in rutas.items()},
        "parametros": {
            k: cfg[k]
            for k in [
                "semillas",
                "umap",
                "min_topic_size",
                "palabras_clave",
                "umbrales",
                "semilla_azar",
                "semilla_codigos",
            ]
        },
    }


def guardar_asignaciones(
    prueba: str, datos: dict, corridas: dict, carpeta: Path
) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    for clave, por_semilla in corridas.items():
        ids = [u["id"] for u in datos[clave]["unidades"]]
        for semilla, c in por_semilla.items():
            ruta = carpeta / f"asignaciones_{prueba}_{clave}_s{semilla}.csv"
            pd.DataFrame({"id_unidad": ids, "tema": c["etiquetas"]}).to_csv(
                ruta, index=False
            )


def escribir_json(ruta: Path, contenido: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(a_json(contenido), ensure_ascii=False, indent=2, allow_nan=False)
    ruta.write_text(texto + "\n", encoding="utf-8")


def ejecutar(params: dict) -> dict:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    cfg = params["semantico"]
    privada, publica = RAIZ_REPO / cfg["salidas"], RAIZ_REPO / cfg["salidas_metricas"]
    matriz = cargar_matriz(params)
    d1 = unidades_prueba1(params, matriz["tabla"])
    unidades2, descartadas = unidades_prueba2(cfg, matriz["tabla"])
    trozos = {k: len(v["unidades"]) for k, v in d1.items()}
    print(f"Prueba 1: {trozos} trozos")
    print(
        f"Prueba 2: {len(unidades2)} unidades de ficha de "
        f"{len(matriz['tabla'])} informes",
        flush=True,
    )
    emb = {
        k: embeddings_de_modelo(k, m, d1[k]["unidades"], unidades2)
        for k, m in cfg["modelos"].items()
    }
    datos = {
        "prueba1": {k: {"unidades": d1[k]["unidades"], "e": emb[k]["e1"]} for k in emb},
        "prueba2a": {k: {"unidades": unidades2, "e": emb[k]["e2"]} for k in emb},
    }
    datos["prueba2b"] = subconjunto_oe2(datos["prueba2a"])
    resultados, corridas = {}, {}
    for prueba in PRUEBAS:
        resultados[prueba], corridas[prueba] = ejecutar_prueba(
            prueba, datos[prueba], cfg
        )
        guardar_asignaciones(prueba, datos[prueba], corridas[prueba], privada)
    medoides = {
        k: resultados["prueba2b"]["modelos"][k]["semilla_medoide"]
        for k in cfg["modelos"]
    }
    hoja = escribir_hoja_ciega(medoides, corridas["prueba2b"], cfg, privada)
    juicio = veredicto(resultados, emb, cfg)
    meta = metadatos(params, matriz)
    extra = {
        "prueba1": {
            "estadisticas_por_informe": {k: v["estadisticas"] for k, v in d1.items()}
        },
        "prueba2a": {"fichas_descartadas_por_campo": descartadas},
    }
    for prueba in PRUEBAS:
        escribir_json(
            publica / f"{prueba}_metricas.json",
            {
                **meta,
                "prueba": prueba,
                **resultados[prueba],
                **extra.get(prueba, {}),
                "embeddings": {k: e["metricas"] for k, e in emb.items()},
            },
        )
    escribir_json(publica / "veredicto.json", {**juicio, "hoja_a_ciegas": hoja})
    return {
        "resultados": resultados,
        "embeddings": emb,
        "veredicto": juicio,
        "hoja": hoja,
        "ram_maxima_mb": ram_maxima_mb(),
    }


def reporte(salida: dict) -> list[str]:
    lineas = ["== Métricas por prueba y modelo (medias de las 5 semillas) =="]
    for prueba in PRUEBAS:
        r = salida["resultados"][prueba]
        for clave, m in r["modelos"].items():
            md = m["medias"]
            lineas.append(
                f"  {ROTULO_PRUEBA[prueba]}/{clave}: temas {md['n_temas']:.1f} | "
                f"sin tema {md['pct_sin_tema']:.1f} % | "
                f"ARI semillas {md['ari_semillas_media']:.3f} "
                f"(mín {m['ari_entre_semillas']['minimo']:.3f}) | "
                f"NPMI real {md['npmi_real']:.3f} vs azar {md['npmi_azar']:.3f} "
                f"({md['corridas_con_npmi_real_mayor']}/5 corridas)"
            )
        a = r["acuerdo_entre_modelos"]
        lineas.append(
            f"  {ROTULO_PRUEBA[prueba]} acuerdo e5 vs MiniLM: "
            f"ARI medio {a['media']:.3f} (mín {a['minimo']:.3f}, "
            f"máx {a['maximo']:.3f}) sobre {a['unidad_de_comparacion']}"
        )
    lineas += ["", "== Veredicto frente a los umbrales =="]
    for clave, v in salida["veredicto"]["criterios"].items():
        lineas.append(f"  {clave}: " + "; ".join(f"{c}: {x}" for c, x in v.items()))
    lineas += [
        "",
        f"RAM máxima del proceso: {salida['ram_maxima_mb']:.0f} MB",
        f"Hoja a ciegas (P2b): {salida['hoja']['temas_en_la_hoja']} temas",
    ]
    return lineas


def main() -> int:
    try:
        if "--calificacion-2b" in sys.argv:
            resultado = calificar_hoja_2b(cargar_params())
            print(
                json.dumps(
                    a_json(resultado["por_modelo"]), ensure_ascii=False, indent=1
                )
            )
            print(
                json.dumps(
                    a_json(resultado["veredicto_final"]), ensure_ascii=False, indent=1
                )
            )
            return 0
        if "--hoja-2b" in sys.argv:
            print(regenerar_hoja_2b(cargar_params()))
            return 0
        salida = ejecutar(cargar_params())
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("\n".join(reporte(salida)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
