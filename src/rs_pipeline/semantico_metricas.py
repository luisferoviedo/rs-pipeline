"""Métricas del mini-sprint semántico (solo numpy/pandas; sin torch ni BERTopic).

Estabilidad (ARI), coherencia (NPMI con línea base al azar), reparto de los temas por
atributo, mezcla de idiomas, temas "de un documento" y el veredicto frente a los
umbrales aprobados. El tema -1 es el de los trozos sin tema (outliers).
"""

from __future__ import annotations

import itertools
import math
import re

import numpy as np

from rs_pipeline.semantico_texto import fallar

SIN_TEMA = -1
TOKEN = re.compile(r"(?u)\b[^\W\d_]{2,}\b")


# --- Acuerdo entre asignaciones --------------------------------------------------


def comb2(x: np.ndarray) -> np.ndarray:
    return x * (x - 1) / 2


def ari(a: list[int] | np.ndarray, b: list[int] | np.ndarray) -> dict:
    """Índice de Rand ajustado entre dos asignaciones, sin las unidades sin tema.

    Solo cuentan las unidades con tema en AMBAS asignaciones. Devuelve el valor, cuántas
    unidades se usaron y la fracción que eso representa.
    """
    x, y = np.asarray(a), np.asarray(b)
    if x.shape != y.shape:
        fallar(f"ARI: las asignaciones miden {x.shape} y {y.shape}")
    usar = (x != SIN_TEMA) & (y != SIN_TEMA)
    n = int(usar.sum())
    if n < 2:
        return {"valor": math.nan, "n_usadas": n, "fraccion_usada": 0.0}
    _, xi = np.unique(x[usar], return_inverse=True)
    _, yi = np.unique(y[usar], return_inverse=True)
    tabla = np.zeros((xi.max() + 1, yi.max() + 1))
    np.add.at(tabla, (xi, yi), 1)
    suma = comb2(tabla).sum()
    filas, columnas = comb2(tabla.sum(1)).sum(), comb2(tabla.sum(0)).sum()
    esperado = filas * columnas / comb2(np.array(n))
    maximo = (filas + columnas) / 2
    valor = 1.0 if maximo == esperado else (suma - esperado) / (maximo - esperado)
    return {"valor": float(valor), "n_usadas": n, "fraccion_usada": n / len(x)}


def ari_entre_semillas(asignaciones: dict[int, np.ndarray]) -> dict:
    """ARI de todos los pares de semillas de un mismo modelo y prueba."""
    pares = []
    for s1, s2 in itertools.combinations(sorted(asignaciones), 2):
        resultado = ari(asignaciones[s1], asignaciones[s2])
        pares.append({"semillas": [s1, s2], **resultado})
    valores = [p["valor"] for p in pares]
    return {
        "pares": pares,
        "media": float(np.nanmean(valores)),
        "minimo": float(np.nanmin(valores)),
        "fraccion_usada_media": float(np.mean([p["fraccion_usada"] for p in pares])),
    }


def semilla_medoide(asignaciones: dict[int, np.ndarray]) -> int:
    """La semilla cuyo resultado más se parece (ARI medio) al de las demás."""
    medias = {}
    for s in sorted(asignaciones):
        otros = [
            ari(asignaciones[s], asignaciones[o])["valor"]
            for o in asignaciones
            if o != s
        ]
        medias[s] = float(np.nanmean(otros))
    return max(medias, key=lambda s: (medias[s], -s))


# --- Coherencia NPMI -----------------------------------------------------------


def conjuntos_de_palabras(textos: list[str]) -> list[set[str]]:
    return [set(TOKEN.findall(t.lower())) for t in textos]


def indice_invertido(conjuntos: list[set[str]]) -> dict[str, frozenset[int]]:
    indice: dict[str, set[int]] = {}
    for numero, palabras in enumerate(conjuntos):
        for palabra in palabras:
            indice.setdefault(palabra, set()).add(numero)
    return {palabra: frozenset(docs) for palabra, docs in indice.items()}


def npmi_par(n1: int, n2: int, n12: int, total: int) -> float:
    """NPMI de dos palabras; -1 si nunca aparecen juntas, 1 si siempre juntas."""
    if n12 == 0:
        return -1.0
    p12 = n12 / total
    if p12 == 1:
        return 1.0
    pmi = math.log(p12 / ((n1 / total) * (n2 / total)))
    return pmi / -math.log(p12)


def coherencia_tema(
    palabras: list[str], indice: dict[str, frozenset[int]], total: int
) -> float:
    """NPMI medio de los pares de palabras clave (co-aparición en la misma unidad)."""
    conocidas = [p for p in palabras if p in indice]
    valores = [
        npmi_par(len(indice[a]), len(indice[b]), len(indice[a] & indice[b]), total)
        for a, b in itertools.combinations(conocidas, 2)
    ]
    return float(np.mean(valores)) if valores else math.nan


def coherencia(
    temas: dict[int, list[str]], indice: dict[str, frozenset[int]], total: int
) -> float:
    """NPMI medio de los temas (sin el de los outliers)."""
    valores = [
        coherencia_tema(p, indice, total) for t, p in temas.items() if t != SIN_TEMA
    ]
    return float(np.nanmean(valores)) if valores else math.nan


# --- Reparto y concentración -----------------------------------------------------


def repartos(etiquetas: np.ndarray, atributo: list[str]) -> dict[int, dict[str, int]]:
    """Por tema (sin outliers): cuántas unidades hay de cada valor del atributo."""
    resultado: dict[int, dict[str, int]] = {}
    for tema, valor in zip(etiquetas, atributo, strict=True):
        if tema == SIN_TEMA:
            continue
        cuenta = resultado.setdefault(int(tema), {})
        cuenta[valor] = cuenta.get(valor, 0) + 1
    return resultado


def porcentaje_dominado(
    etiquetas: np.ndarray, atributo: list[str], umbral: float
) -> dict:
    """Temas cuyo valor más frecuente supera `umbral` de sus unidades."""
    por_tema = repartos(etiquetas, atributo)
    dominados = [
        t for t, c in por_tema.items() if max(c.values()) / sum(c.values()) > umbral
    ]
    n = len(por_tema)
    return {
        "n_temas": n,
        "n_dominados": len(dominados),
        "pct_dominados": 100 * len(dominados) / n if n else math.nan,
    }


def mezcla_de_idiomas(
    etiquetas: np.ndarray, idiomas: list[str], minimo_pct: float
) -> dict:
    """Temas con 2 o más idiomas que pasan de `minimo_pct` % de sus unidades."""
    por_tema = repartos(etiquetas, idiomas)
    mezclan = [
        t
        for t, c in por_tema.items()
        if sum(100 * v / sum(c.values()) >= minimo_pct for v in c.values()) >= 2
    ]
    n = len(por_tema)
    return {
        "n_temas": n,
        "n_mezclan": len(mezclan),
        "pct_mezclan": 100 * len(mezclan) / n if n else math.nan,
    }


def pct_sin_tema(etiquetas: np.ndarray) -> float:
    return 100 * float((np.asarray(etiquetas) == SIN_TEMA).mean())


# --- Veredicto frente a los umbrales ---------------------------------------------


def juzgar(valor: float, sigue: float, no_sigue: float, mayor_es_mejor: bool) -> str:
    """'cumple', 'no cumple' o 'intermedio' según los dos umbrales aprobados."""
    if math.isnan(valor):
        return "no calculable"
    if mayor_es_mejor:
        bueno, malo = valor >= sigue, valor < no_sigue
    else:
        bueno, malo = valor <= sigue, valor > no_sigue
    return "cumple" if bueno else ("no cumple" if malo else "intermedio")


def veredicto_estabilidad(medias: dict, umbrales: dict) -> dict:
    """ARI entre semillas, % sin tema y NPMI real contra azar (por modelo y prueba)."""
    return {
        "ari_entre_semillas": juzgar(
            medias["ari_semillas_media"],
            umbrales["ari_semillas_sigue"],
            umbrales["ari_semillas_no_sigue"],
            True,
        ),
        "pct_sin_tema": juzgar(
            medias["pct_sin_tema"],
            umbrales["outliers_sigue_pct"],
            umbrales["outliers_no_sigue_pct"],
            False,
        ),
        "npmi_real_mayor_que_azar": (
            "cumple" if medias["npmi_real"] > medias["npmi_azar"] else "no cumple"
        ),
    }
