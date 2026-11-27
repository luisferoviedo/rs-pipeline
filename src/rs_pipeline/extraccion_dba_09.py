"""Extracción de los DBA de Ciencias Naturales, 6.º a 11.º (Bloque 9; D60).

Una unidad por evidencia de aprendizaje, con su DBA, su grado y el texto del «Ejemplo»
como contexto (el «Ejemplo» no es unidad). Cada unidad lleva el nivel CINE 2011 de su
grado (D56): 2 de 6.º a 9.º y 3 en 10.º y 11.º. Usa los recortes aprobados de
config/recortes_dba_cn.yaml: no vuelve a medir.

Lectura: pdftotext -bbox da cada palabra con su caja. En cada página (21-39) se deja
lo que está entre y_superior y y_inferior y se lee la columna izquierda y luego la
derecha. La secuencia es siempre número de DBA, enunciado, «Evidencias de aprendizaje»,
viñetas «q», «Ejemplo» y su texto, aunque salte de columna o de página.

Uniones: un subíndice (el «2» de H2O) es más bajo que su línea y se pega a sus vecinos
sin espacio. Cuando una línea termina en un guion o una barra pegados a la palabra, en
este documento son parte de ella («Boyle-Mariotte», «inflar/explotar» y direcciones
web): se conservan y no se mete espacio. Un guion suelto («Brönsted – Lowry») no.

Los textos van a data/processed/curriculo/ (fuera de git); a outputs/tablas/ va solo
el resumen. Las figuras de los «Ejemplo» no tienen capa de texto: el contexto guarda
solo el texto, y es None en los DBA cuyo ejemplo es solo una figura.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.extraccion_dba_09
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import NamedTuple

import yaml

from rs_pipeline import recortes_dba_09 as R
from rs_pipeline.extraccion_09 import (
    INVENTARIO,
    TOLERANCIA_LINEA,
    documento_del_inventario,
    pdf_verificado,
    procedencia,
    relativa,
    resumen_documento,
    version_pdftotext,
)
from rs_pipeline.ocr_pe_09 import ejecutar, sha256_de
from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
RECORTES = R.CONFIG
CURRICULO = RAIZ_REPO / "data" / "processed" / "curriculo"
SALIDA_DATOS = CURRICULO / "enunciados_09_dba_v1.jsonl"
SALIDA_RESUMEN = RAIZ_REPO / "outputs" / "tablas" / "extraccion_09_dba_v1.json"

ALTO_SUBINDICE = 9.0  # pt; el texto mide 10,8 a 13,2 y el subíndice 7
PEGADO_MAX = 1.0  # pt; un subíndice está a menos de esto de la letra que completa
ENCABEZADO_EVIDENCIAS = "Evidencias de aprendizaje"
ENCABEZADO_EJEMPLO = "Ejemplo"
VINETA = "q"
CORTES_SIN_ESPACIO = ("-", "/")  # pegados a una palabra al final de una línea
RE_GRADO = re.compile(r"^(\d{1,2})º$")
# Si algo de esto aparece en una unidad, se coló el encabezado o el pie
RESTOS_DE_ENCABEZADO_Y_PIE = (
    "•",
    "V.1",
    "Derechos Básicos",
    "CienciasNaturales",
    ".indd",
    "p.m.",
)
# Piloto aprobado (D60): por grado, número de evidencias de cada DBA en orden
ESTRUCTURA_DBA = {
    6: (2, 3, 4, 4, 3),
    7: (3, 3, 3, 4),
    8: (4, 4, 3, 4, 4),
    9: (3, 3, 4, 4, 3, 4),
    10: (3, 2, 4, 3),
    11: (4, 3, 4, 3, 4),
}
# Nivel CINE 2011 de cada grado en Colombia (D56)
CINE_POR_GRADO = {6: 2, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3}
# DBA cuyo «Ejemplo» es solo una figura (verificado a ojo en las páginas)
EJEMPLOS_SOLO_FIGURA = (
    "G6.D1",
    "G6.D3",
    "G7.D1",
    "G7.D2",
    "G8.D1",
    "G9.D1",
    "G10.D1",
    "G10.D2",
    "G11.D2",
)


class Linea(NamedTuple):
    pagina: int
    grado: int
    texto: str
    numero: int | None  # número del DBA, si esta es su primera línea


# --- Recortes y páginas ---------------------------------------------------------


def cargar_recortes(sha_pdf: str) -> dict[int, tuple[int, int, int]]:
    """Por página: (x_columnas, y_superior, y_inferior) del YAML aprobado."""
    if not RECORTES.is_file():
        fallar(f"no existe {RECORTES}")
    config = yaml.safe_load(RECORTES.read_text(encoding="utf-8"))
    if config["entrada"]["sha256"] != sha_pdf:
        fallar(f"{RECORTES.name}: los recortes se midieron sobre otro PDF")
    filas = {f["pagina"]: f for f in config["paginas"]}
    if len(filas) != len(config["paginas"]):
        fallar(f"{RECORTES.name}: hay páginas repetidas")
    recortes = {}
    for n in R.PAGINAS:
        if n not in filas:
            fallar(f"p{n}: no hay recorte en {RECORTES.name}")
        f = filas[n]
        if not str(f.get("verificado_por") or "").strip():
            fallar(f"p{n}: recorte sin verificar (verificado_por vacío)")
        recortes[n] = (f["x_columnas"], f["y_superior"], f["y_inferior"])
    return recortes


def grado_de_pagina(palabras: list[R.Palabra], y_superior: int, pagina: int) -> int:
    """El grado, tomado del encabezado («Ciencias Naturales • Grado 6º»)."""
    grados = [
        int(m.group(1))
        for p in palabras
        if p.y1 < y_superior and (m := RE_GRADO.match(p.texto))
    ]
    if len(grados) != 1:
        fallar(f"p{pagina}: se esperaba un grado en el encabezado y hay {grados}")
    return grados[0]


def texto_de_pagina(
    palabras: list[R.Palabra], recorte: tuple[int, int, int], pagina: int
) -> list[R.Palabra]:
    """Palabras entre el encabezado y el pie; ninguna puede cruzar un recorte."""
    x, y_superior, y_inferior = recorte
    dentro = []
    for p in palabras:
        if p.y1 < y_superior or p.y0 > y_inferior:
            continue
        if p.y0 <= y_superior or p.y1 >= y_inferior or p.x0 <= x <= p.x1:
            fallar(f"p{pagina}: una palabra cruza un recorte ({p.texto!r})")
        dentro.append(p)
    return dentro


def controlar_encabezado_y_pie(
    palabras: list[R.Palabra], dentro: list[R.Palabra], pagina: int
) -> None:
    """El recorte debe dejar justo el texto que queda entre «V.1» y el número de página.

    No vuelve a medir: compara el recorte aprobado con una segunda definición del
    encabezado y del pie, la de las anclas de texto de la página.
    """
    if dentro != R.separar(palabras, pagina)[1]:
        fallar(
            f"p{pagina}: el recorte deja palabras del encabezado o del pie, "
            "o quita texto"
        )


# --- Líneas ----------------------------------------------------------------------


def unir_palabras(palabras: list[R.Palabra]) -> str:
    """Las palabras de una línea (ordenadas por x); el subíndice va sin espacio."""
    partes = [palabras[0].texto]
    for previa, p in zip(palabras, palabras[1:], strict=False):
        alto = min(previa.y1 - previa.y0, p.y1 - p.y0)
        pegada = alto < ALTO_SUBINDICE and p.x0 - previa.x1 < PEGADO_MAX
        partes.append(p.texto if pegada else f" {p.texto}")
    return "".join(partes)


def unir_lineas(lineas: list[str]) -> str:
    """Une líneas; tras un guion o una barra pegados a una palabra no va espacio."""
    texto = ""
    for linea in lineas:
        pegado = texto.endswith(CORTES_SIN_ESPACIO) and texto[-2:-1].strip() != ""
        texto += linea if not texto or pegado else f" {linea}"
    return texto


def _agrupar(palabras: list[R.Palabra]) -> list[dict]:
    """Grupos por altura (y0), de arriba abajo, con el alto de su primera palabra."""
    grupos: list[dict] = []
    for p in sorted(palabras, key=lambda p: (p.y0, p.x0)):
        if grupos and p.y0 - grupos[-1]["y0"] <= TOLERANCIA_LINEA:
            grupos[-1]["palabras"].append(p)
        else:
            grupos.append({"y0": p.y0, "y1": p.y1, "palabras": [p], "numero": None})
    return grupos


def _unico_grupo(grupos: list[dict], sirve, que: str, pagina: int) -> dict:
    candidatos = [g for g in grupos if sirve(g)]
    if len(candidatos) != 1:
        fallar(f"p{pagina}: {que} corresponde a {len(candidatos)} líneas y no a una")
    return candidatos[0]


def lineas_de_columna(columna: list[R.Palabra], pagina: int, grado: int) -> list[Linea]:
    """Líneas de una columna; coloca los subíndices y los números de DBA."""
    numeros = [p for p in columna if R.marca(p) == "N"]
    resto = [p for p in columna if R.marca(p) != "N"]
    bajas = [p for p in resto if p.y1 - p.y0 < ALTO_SUBINDICE]
    grupos = _agrupar([p for p in resto if p.y1 - p.y0 >= ALTO_SUBINDICE])
    for s in bajas:
        centro = (s.y0 + s.y1) / 2
        _unico_grupo(
            grupos,
            lambda g, c=centro: g["y0"] <= c <= g["y1"],
            f"el subíndice {s.texto!r}",
            pagina,
        )["palabras"].append(s)
    for n in numeros:
        _unico_grupo(
            grupos,
            lambda g, y=n.y0: abs(g["y0"] - y) <= TOLERANCIA_LINEA,
            f"el número {n.texto!r}",
            pagina,
        )["numero"] = int(n.texto.rstrip("."))
    return [
        Linea(
            pagina,
            grado,
            unir_palabras(sorted(g["palabras"], key=lambda p: p.x0)),
            g["numero"],
        )
        for g in grupos
    ]


def leer_lineas(
    paginas: dict[int, list[R.Palabra]], recortes: dict[int, tuple[int, int, int]]
) -> list[Linea]:
    """Todas las líneas en orden de lectura: izquierda, derecha, página siguiente."""
    lineas: list[Linea] = []
    for n in sorted(paginas):
        grado = grado_de_pagina(paginas[n], recortes[n][1], n)
        dentro = texto_de_pagina(paginas[n], recortes[n], n)
        controlar_encabezado_y_pie(paginas[n], dentro, n)
        for izquierda in (True, False):
            columna = [p for p in dentro if (p.x0 < recortes[n][0]) == izquierda]
            lineas += lineas_de_columna(columna, n, grado)
    return lineas


# --- DBA -------------------------------------------------------------------------


def _agregar_a_evidencias(dba: dict, linea: Linea) -> None:
    primera, _, resto = linea.texto.partition(" ")
    if primera == VINETA:
        dba["evidencias"].append({"pagina": linea.pagina, "lineas": [resto]})
    elif dba["evidencias"]:
        dba["evidencias"][-1]["lineas"].append(linea.texto)
    else:
        fallar(f"p{linea.pagina}: texto bajo «Evidencias» antes de la primera viñeta")


def _agregar_linea(dbas: list[dict], seccion: str | None, linea: Linea) -> str:
    """Pone una línea en el DBA abierto y devuelve la sección en la que se queda."""
    if not dbas:
        fallar(f"p{linea.pagina}: hay texto antes del primer DBA")
    dba = dbas[-1]
    donde = f"p{linea.pagina}, grado {dba['grado']}, DBA {dba['numero']}"
    if linea.grado != dba["grado"]:
        fallar(f"{donde}: sigue en una página del grado {linea.grado}")
    if linea.texto == ENCABEZADO_EVIDENCIAS:
        if seccion != "enunciado":
            fallar(f"{donde}: «Evidencias» fuera de lugar")
        return "evidencias"
    if linea.texto == ENCABEZADO_EJEMPLO:
        if seccion != "evidencias" or not dba["evidencias"]:
            fallar(f"{donde}: «Ejemplo» sin evidencias antes")
        return "ejemplo"
    if seccion == "evidencias":
        _agregar_a_evidencias(dba, linea)
    else:
        dba[seccion].append(linea.texto)  # «enunciado» o «ejemplo»
    return seccion


def armar_dbas(lineas: list[Linea]) -> list[dict]:
    """Cada DBA con su enunciado, sus evidencias y el texto de su «Ejemplo»."""
    dbas: list[dict] = []
    seccion = None
    for linea in lineas:
        if linea.numero is None:
            seccion = _agregar_linea(dbas, seccion, linea)
            continue
        if seccion not in (None, "ejemplo"):
            fallar(
                f"p{linea.pagina}: empieza un DBA y el anterior no llegó a «Ejemplo»"
            )
        dbas.append(
            {
                "grado": linea.grado,
                "numero": linea.numero,
                "enunciado": [linea.texto],
                "evidencias": [],
                "ejemplo": [],
            }
        )
        seccion = "enunciado"
    if seccion != "ejemplo":
        fallar("el último DBA no llegó a «Ejemplo»")
    for d in dbas:
        d["enunciado"] = unir_lineas(d["enunciado"])
        d["ejemplo"] = unir_lineas(d["ejemplo"]) or None
        d["evidencias"] = [
            {"pagina": e["pagina"], "texto": unir_lineas(e["lineas"])}
            for e in d["evidencias"]
        ]
    return dbas


# --- Controles -------------------------------------------------------------------


def controlar_estructura(dbas: list[dict]) -> None:
    """Numeración consecutiva en cada grado y los DBA y evidencias del piloto."""
    numeros: dict[int, list[int]] = {}
    leida: dict[int, list[int]] = {}
    for d in dbas:
        numeros.setdefault(d["grado"], []).append(d["numero"])
        leida.setdefault(d["grado"], []).append(len(d["evidencias"]))
    for grado, nums in numeros.items():
        if nums != list(range(1, len(nums) + 1)):
            fallar(f"DBA: numeración no consecutiva en el grado {grado}: {nums}")
    encontrada = {g: tuple(v) for g, v in leida.items()}
    if encontrada != ESTRUCTURA_DBA:
        fallar(
            "DBA: evidencias por DBA distintas de las del piloto. "
            f"Leído: {encontrada}. Esperado: {ESTRUCTURA_DBA}"
        )


def controlar_textos(dbas: list[dict]) -> None:
    """Sin restos de encabezado o pie, sin viñetas sueltas y sin textos vacíos."""
    for d in dbas:
        nombre = f"G{d['grado']}.D{d['numero']}"
        obligatorios = [d["enunciado"], *(e["texto"] for e in d["evidencias"])]
        if any(len(t.split()) < 3 for t in obligatorios):
            fallar(f"{nombre}: enunciado o evidencia sin texto")
        for t in [*obligatorios, d["ejemplo"] or ""]:
            restos = [r for r in RESTOS_DE_ENCABEZADO_Y_PIE if r in t]
            if restos:
                fallar(f"{nombre}: hay restos de encabezado o pie: {restos}")
            if VINETA in t.split():
                fallar(f"{nombre}: una viñeta quedó dentro de un texto")
    sin_texto = tuple(
        f"G{d['grado']}.D{d['numero']}" for d in dbas if d["ejemplo"] is None
    )
    if sin_texto != EJEMPLOS_SOLO_FIGURA:
        fallar(
            f"DBA sin texto en «Ejemplo»: {sin_texto}; "
            f"esperados: {EJEMPLOS_SOLO_FIGURA}"
        )


# --- Salida -----------------------------------------------------------------------


def nivel_cine_del_grado(grado: int) -> int:
    if grado not in CINE_POR_GRADO:
        fallar(f"no hay nivel CINE definido para el grado {grado} (D56)")
    return CINE_POR_GRADO[grado]


def registros_dba(doc: dict, dbas: list[dict]) -> list[dict]:
    return [
        {
            "id_unidad": f"{doc['id']}:G{d['grado']}.D{d['numero']}.E{k}",
            **procedencia(doc),
            # el del grado, no la lista de niveles de todo el documento
            "nivel_cine": [nivel_cine_del_grado(d["grado"])],
            "tipo_unidad": "evidencia_dba",
            "grado": d["grado"],
            "dba": d["numero"],
            "enunciado_dba": d["enunciado"],
            "ejemplo": d["ejemplo"],
            "texto": e["texto"],
            "texto_es": e["texto"],
            "idioma": "es",
            "pagina": e["pagina"],
        }
        for d in dbas
        for k, e in enumerate(d["evidencias"], start=1)
    ]


def conteos(dbas: list[dict]) -> dict:
    por_grado = {}
    for grado in sorted({d["grado"] for d in dbas}):
        del_grado = [d for d in dbas if d["grado"] == grado]
        por_grado[str(grado)] = {
            "nivel_cine": nivel_cine_del_grado(grado),
            "dba": len(del_grado),
            "evidencias": sum(len(d["evidencias"]) for d in del_grado),
        }
    return {
        "dba": len(dbas),
        "evidencias": sum(len(d["evidencias"]) for d in dbas),
        "por_grado": por_grado,
        "dba_sin_texto_en_ejemplo": [
            f"G{d['grado']}.D{d['numero']}" for d in dbas if d["ejemplo"] is None
        ],
    }


def extraer(pdf: Path, sha_pdf: str) -> list[dict]:
    """Los DBA leídos del PDF con los recortes aprobados y ya controlados."""
    recortes = cargar_recortes(sha_pdf)
    a, b = R.PAGINAS[0], R.PAGINAS[-1]
    orden = ["pdftotext", "-bbox", "-f", str(a), "-l", str(b), str(pdf), "-"]
    leidas = R.paginas_con_cajas(ejecutar(orden).stdout)
    if len(leidas) != len(R.PAGINAS):
        fallar(f"se leyeron {len(leidas)} páginas y se esperaban {len(R.PAGINAS)}")
    paginas = {n: pal for n, (_, pal) in zip(R.PAGINAS, leidas, strict=True)}
    dbas = armar_dbas(leer_lineas(paginas, recortes))
    controlar_estructura(dbas)
    controlar_textos(dbas)
    return dbas


def correr(salida_datos: Path, salida_resumen: Path) -> dict:
    for ruta in (salida_datos, salida_resumen):
        if ruta.exists():
            fallar(f"ya existe {ruta}; no se sobrescribe una extracción anterior")
    doc = documento_del_inventario(R.ID_DBA)
    dbas = extraer(pdf_verificado(doc), doc["sha256"])
    registros = registros_dba(doc, dbas)
    version = version_pdftotext()  # antes de escribir: si falla, no queda nada a medias
    salida_datos.parent.mkdir(parents=True, exist_ok=True)
    with salida_datos.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    paginas = (R.PAGINAS[0], R.PAGINAS[-1])
    resumen = {
        "decision": "D60",
        "fecha": date.today().isoformat(),
        "pdftotext": version,
        "inventario": {
            "archivo": relativa(INVENTARIO),
            "sha256": sha256_de(INVENTARIO),
        },
        "recortes": {"archivo": relativa(RECORTES), "sha256": sha256_de(RECORTES)},
        "documentos": {R.ID_DBA: resumen_documento(doc, paginas, conteos(dbas))},
        "unidades": len(registros),
        "salida_datos": relativa(salida_datos),
        "salida_datos_sha256": sha256_de(salida_datos),
    }
    salida_resumen.parent.mkdir(parents=True, exist_ok=True)
    salida_resumen.write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen


def main() -> None:
    r = correr(SALIDA_DATOS, SALIDA_RESUMEN)
    print(json.dumps(r["documentos"], ensure_ascii=False, indent=2))
    print(f"unidades: {r['unidades']}")


if __name__ == "__main__":
    main()
