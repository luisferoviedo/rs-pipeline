"""Preparación de textos del mini-sprint semántico (sin torch ni BERTopic).

Dos fuentes: el texto completo de un informe (Prueba 1: se limpia y se parte en
trozos de ~N palabras sin cortar oraciones) y los campos de la ficha de extracción
(Prueba 2: se quitan las marcas [F]/[I] y las citas de página). Todo falla con
ErrorPipeline si algo no es lo esperado.
"""

from __future__ import annotations

import re
from typing import NoReturn


class ErrorPipeline(Exception):
    """Falla esperada: falta un dato o algo no es lo esperado."""


def fallar(mensaje: str) -> NoReturn:
    raise ErrorPipeline(mensaje)


# --- Texto completo (Prueba 1) -------------------------------------------------

MARCADOR_REFERENCIAS = re.compile(r"^\[\[REFERENCIAS OMITIDAS")
MARCADOR_CUALQUIERA = re.compile(r"^\[\[.*\]\]$")
ENCABEZADO_REFERENCIAS = re.compile(
    r"^\W*(?:\d+\.?\s*)?(references?|referencias(?: bibliogr[aá]ficas)?|"
    r"refer[eê]ncias(?: bibliogr[aá]ficas)?|bibliograf[ií]a|bibliography|"
    r"literatura citada|works cited)\W*$",
    re.IGNORECASE,
)
PUNTOS_GUIA = re.compile(r"\.{4,}|(?:\. ){4,}")
FIN_DE_ORACION = re.compile(r"[.,;:?!)\]”\"]$")
CORTE_DE_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑÀ-ÖØ-Þ¿¡\"“(\[])")
ABREVIATURAS = {
    "al.",
    "fig.",
    "figs.",
    "eq.",
    "tab.",
    "no.",
    "vs.",
    "etc.",
    "dr.",
    "dra.",
    "prof.",
    "sr.",
    "sra.",
    "p.",
    "pp.",
    "vol.",
    "cf.",
    "ca.",
    "aprox.",
    "núm.",
    "ej.",
    "ud.",
    "e.g.",
    "i.e.",
    "approx.",
    "sec.",
    "cap.",
}
UNA_INICIAL = re.compile(r"^[A-ZÁÉÍÓÚÑ]\.$")


def cortar_referencias(lineas: list[str], id_informe: str) -> tuple[list[str], str]:
    """Quita desde el marcador de referencias (o su encabezado en el último 40 %)."""
    for numero, linea in enumerate(lineas):
        if MARCADOR_REFERENCIAS.match(linea):
            return lineas[:numero], "marcador"
    candidatos = [
        n
        for n, linea in enumerate(lineas)
        if ENCABEZADO_REFERENCIAS.match(linea) and n >= 0.6 * len(lineas)
    ]
    if not candidatos:
        fallar(f"{id_informe}: no se encontró la sección de referencias")
    return lineas[: candidatos[-1]], "encabezado"


def es_encabezado(linea: str) -> bool:
    """Línea corta sin puntuación final que empieza con mayúscula o número."""
    palabras = linea.split()
    if len(palabras) > 7 or FIN_DE_ORACION.search(linea):
        return False
    return bool(re.match(r"^[A-ZÁÉÍÓÚÑ0-9]", linea))


def proporcion_alfabetica(texto: str) -> float:
    sin_espacios = re.sub(r"\s", "", texto)
    if not sin_espacios:
        return 0.0
    return sum(c.isalpha() for c in sin_espacios) / len(sin_espacios)


def quitar_ruido(lineas: list[str]) -> list[str]:
    """Marcadores [[...]], índices con puntos, encabezados repetidos y títulos."""
    veces: dict[str, int] = {}
    for linea in lineas:
        veces[linea] = veces.get(linea, 0) + 1
    limpias = []
    for linea in lineas:
        if not linea or MARCADOR_CUALQUIERA.match(linea) or PUNTOS_GUIA.search(linea):
            continue
        if len(linea) > 8 and veces[linea] >= 3:
            continue
        if proporcion_alfabetica(linea) < 0.5 or es_encabezado(linea):
            continue
        limpias.append(linea)
    return limpias


def unir_lineas(lineas: list[str]) -> str:
    """Une las líneas del PDF; une las palabras cortadas con guion al final."""
    texto = ""
    for linea in lineas:
        if texto.endswith("-") and linea[:1].islower():
            texto = texto[:-1] + linea
        else:
            texto += (" " if texto else "") + linea
    return re.sub(r"\s+", " ", texto).strip()


def limpiar_texto_completo(texto: str, id_informe: str) -> tuple[str, dict]:
    """Texto corrido sin referencias, encabezados ni ruido de PDF + estadísticas."""
    lineas = [linea.strip() for linea in texto.split("\n")]
    cuerpo, corte = cortar_referencias(lineas, id_informe)
    limpias = quitar_ruido(cuerpo)
    estadisticas = {
        "lineas": len(lineas),
        "lineas_cuerpo": len(cuerpo),
        "lineas_conservadas": len(limpias),
        "corte_referencias": corte,
    }
    return unir_lineas(limpias), estadisticas


def es_abreviatura(fragmento: str) -> bool:
    ultima = fragmento.split()[-1] if fragmento.split() else ""
    return ultima.lower() in ABREVIATURAS or bool(UNA_INICIAL.match(ultima))


def oraciones(texto: str) -> list[str]:
    """Parte en oraciones; une los cortes que fueron abreviaturas o iniciales."""
    resultado: list[str] = []
    for fragmento in CORTE_DE_ORACION.split(texto):
        if resultado and es_abreviatura(resultado[-1]):
            resultado[-1] += " " + fragmento
        else:
            resultado.append(fragmento)
    return [o.strip() for o in resultado if o.strip()]


def armar_trozos(
    lista: list[str], objetivo: int, minimo_ultimo: float, maximo_veces: int
) -> tuple[list[list[int]], int]:
    """Agrupa oraciones en trozos de >= `objetivo` palabras sin cortar oraciones.

    Devuelve los índices de oración de cada trozo y cuántas oraciones se descartaron
    por ser más largas que `maximo_veces` x `objetivo` (no son prosa).
    """
    trozos: list[list[int]] = []
    actual: list[int] = []
    palabras = descartadas = 0
    for indice, oracion in enumerate(lista):
        n = len(oracion.split())
        if n > maximo_veces * objetivo:
            descartadas += 1
            continue
        actual.append(indice)
        palabras += n
        if palabras >= objetivo:
            trozos.append(actual)
            actual, palabras = [], 0
    if actual and (palabras >= minimo_ultimo * objetivo or not trozos):
        trozos.append(actual)
    elif actual:
        trozos[-1].extend(actual)
    return trozos, descartadas


def trozos_de_informe(
    texto: str, id_informe: str, objetivo: int, cfg: dict
) -> tuple[list[dict], dict]:
    """Trozos {id, oraciones, texto} de un informe y las estadísticas de la limpieza."""
    limpio, estadisticas = limpiar_texto_completo(texto, id_informe)
    lista = oraciones(limpio)
    grupos, descartadas = armar_trozos(
        lista, objetivo, cfg["minimo_ultimo_trozo"], cfg["maximo_oracion_veces_trozo"]
    )
    trozos = []
    for indices in grupos:
        cuerpo = " ".join(lista[i] for i in indices)
        if proporcion_alfabetica(cuerpo) >= cfg["proporcion_alfabetica_minima"]:
            trozos.append({"oraciones": indices, "texto": cuerpo})
    estadisticas |= {
        "oraciones": len(lista),
        "oraciones_descartadas_largas": descartadas,
        "trozos_antes_de_filtrar": len(grupos),
        "trozos": len(trozos),
    }
    if not trozos:
        fallar(f"{id_informe}: no quedó ningún trozo")
    return trozos, estadisticas


# --- Fichas (Prueba 2) -----------------------------------------------------------

ETIQUETA = re.compile(r"\[\s*[FI](?:\s*/\s*[FI])?\s*\]")
NUMEROS_PAGINA = r"\d+(?:\s*[–—\-]\s*\d+)?(?:\s*(?:,|y)\s*\d+(?:\s*[–—\-]\s*\d+)?)*"
CITA_ENTRE_PARENTESIS = re.compile(
    rf"\(\s*(?:pp?|págs?)\.\s*{NUMEROS_PAGINA}"
    rf"(?:\s*[,;]\s*(?:pp?|págs?)\.\s*{NUMEROS_PAGINA})*\s*\)",
    re.IGNORECASE,
)
CITA_SUELTA = re.compile(
    rf"(?:,\s*)?\b(?:pp?|págs?)\.\s*{NUMEROS_PAGINA}", re.IGNORECASE
)


def limpiar_ficha(texto: str) -> str:
    """Quita [F]/[I] y las citas de página; deja el resto del texto igual."""
    texto = ETIQUETA.sub(" ", texto)
    texto = CITA_ENTRE_PARENTESIS.sub(" ", texto)
    texto = CITA_SUELTA.sub("", texto)
    texto = re.sub(r"\(\s*[,;]?\s*\)", " ", texto)
    texto = re.sub(r"\s+([,.;:)])", r"\1", texto)
    texto = re.sub(r"\(\s+", "(", texto)
    return re.sub(r"\s+", " ", texto).strip(" ;,")


def unidades_de_campo(texto: str, campo: str, cfg: dict) -> list[str]:
    """Textos limpios de un campo; oe2_criterios_candidatos se parte en criterios."""
    partes = [texto]
    if campo == "oe2_criterios_candidatos":
        partes = texto.split(cfg["separador_criterios"])
    limpias = (limpiar_ficha(parte) for parte in partes)
    return [t for t in limpias if len(t.split()) >= cfg["minimo_palabras"]]
