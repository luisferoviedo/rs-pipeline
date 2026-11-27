"""Medición de los recortes de los Estándares básicos de competencias 2004 (D60).

Piloto: se mide UNA vez y los valores se congelan en config/recortes_ebc_2004.yaml,
como en D57; el extractor (paso siguiente) leerá ese YAML y no volverá a medir. Esto
solo PROPONE: la persona que revisa confirma a ojo antes de llenar `verificado_por`.

Cada grupo de grados ocupa dos páginas (18-19, 20-21 y 22-23) que forman una tabla.
Con pdftotext -bbox (puntos PDF), en cada página:
- el pie es el número de página o el rótulo grande «CIENCIAS NATURALES»;
- los globos (estándares generales: contexto, no unidades) están por encima de una
  palabra ancla del encabezado («lograrlo...» o «propios»);
- cada columna empieza donde están sus viñetas «•» y su texto va desde la primera;
- lo demás es encabezado de columna.
Un recorte lateral queda en la mitad del hueco entre dos columnas; el superior, en la
mitad entre el encabezado y la primera viñeta; el inferior, 1 pt bajo la última línea.
Una palabra es de un recorte si cabe entre x_izquierda y x_derecha y el CENTRO de su
alto está entre y_superior e y_inferior (en las impares la caja del rótulo del pie
se monta 1,7 pt sobre la última línea, y por el borde no se podrían separar).

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.recortes_ebc_09

Escribe el YAML (si ya existe, FALLA: puede traer una verificación) y las imágenes
para revisar (cada recorte en rojo) en data/processed/curriculo/.
"""

from __future__ import annotations

import math
import tempfile
from datetime import date
from pathlib import Path
from typing import NamedTuple

import yaml

from rs_pipeline.extraccion_09 import (
    documento_del_inventario,
    pdf_verificado,
    version_pdftotext,
)
from rs_pipeline.ocr_pe_09 import ejecutar
from rs_pipeline.recortes_dba_09 import (
    Palabra,
    intervalos_x,
    mitad_del_hueco,
    paginas_con_cajas,
    unica,
)
from rs_pipeline.recortes_pe_09 import escribir_png_rgb, hoja_de_contacto, leer_pgm
from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
ID_EBC = "CO-EBC-2004"
CONFIG = RAIZ_REPO / "config" / "recortes_ebc_2004.yaml"
EVIDENCIA = RAIZ_REPO / "data" / "processed" / "curriculo" / "CO-EBC-2004_recortes"

APROXIMO = "me_aproximo"
VIVO = "entorno_vivo"
FISICO = "entorno_fisico"
CTS = "ciencia_tecnologia_sociedad"
COMPROMISOS = "desarrollo_compromisos"
# Texto que debe aparecer en el encabezado de cada columna
TITULOS = {
    APROXIMO: "como científico-a natural",
    VIVO: "Entorno vivo",
    FISICO: "Entorno físico",
    CTS: "Ciencia, tecnología y sociedad",
    COMPROMISOS: "desarrollo compromisos personales y sociales",
}


class Pagina(NamedTuple):
    grupo: str  # grupo de grados de la tabla
    ancla: str  # palabra del encabezado; por encima solo están los globos
    columnas: tuple[str, ...]  # de izquierda a derecha
    globos: int


PAGINAS = {
    18: Pagina("6-7", "lograrlo...", (APROXIMO, VIVO), 2),
    19: Pagina("6-7", "propios", (FISICO, CTS, COMPROMISOS), 2),
    20: Pagina("8-9", "lograrlo...", (APROXIMO, VIVO), 2),
    21: Pagina("8-9", "propios", (FISICO, CTS, COMPROMISOS), 3),
    # en 10.º-11.º el entorno físico se parte en dos columnas, una en cada página
    22: Pagina("10-11", "lograrlo...", (APROXIMO, VIVO, FISICO), 3),
    23: Pagina("10-11", "propios", (FISICO, CTS, COMPROMISOS), 3),
}
SUBCOLUMNAS = {
    (22, VIVO): "Procesos biológicos",
    (22, FISICO): "Procesos químicos",
    (23, FISICO): "Procesos físicos",
}
# En la página par, el primer globo presenta el grupo y nombra su último grado
INTRODUCCION = "Al final de"
ULTIMO_GRADO = {18: "séptimo", 20: "noveno", 22: "undécimo"}

ALTO_ROTULO_PIE = 30.0  # pt; «CIENCIAS NATURALES» mide 41,6 y el texto 8,6
Y_NUMERO_PAGINA = 690.0  # el número de página está por debajo
TOLERANCIA_X = 2.0  # una palabra de la columna no empieza antes de su viñeta menos esto
TOLERANCIA_Y = 1.0
MARGEN = 3  # pt de aire en los bordes de fuera y alrededor de cada globo
SEPARACION_GLOBOS = 6.0  # tramos a menos de esto son del mismo globo
DPI_EVIDENCIA = 90
METODO = "propuesto por medición de coordenadas (pdftotext -bbox), verificado a ojo"
CRITERIO = (
    "una palabra es del recorte si cabe entre x_izquierda y x_derecha y el centro "
    "de su alto está entre y_superior e y_inferior"
)


def centro_y(p: Palabra) -> float:
    return (p.y0 + p.y1) / 2


def dentro(p: Palabra, r: dict) -> bool:
    """El criterio con el que se lee un recorte (CRITERIO)."""
    cabe = r["x_izquierda"] <= p.x0 and p.x1 <= r["x_derecha"]
    return cabe and r["y_superior"] < centro_y(p) < r["y_inferior"]


def en_orden(palabras: list[Palabra]) -> str:
    return " ".join(p.texto for p in sorted(palabras, key=lambda p: (p.y0, p.x0)))


def separar(palabras: list[Palabra], n: int) -> dict:
    """Pie, ancla, globos y el resto (encabezados y columnas) de una página."""
    pie = [
        p
        for p in palabras
        if p.y1 - p.y0 > ALTO_ROTULO_PIE
        or (p.texto == str(n) and p.y0 > Y_NUMERO_PAGINA)
    ]
    if not pie:
        fallar(f"p{n}: no hay número de página ni rótulo en el pie")
    ancla = unica(palabras, PAGINAS[n].ancla, n)
    cuerpo = [p for p in palabras if p not in pie]
    return {
        "pie": pie,
        "ancla": ancla,
        "globos": [p for p in cuerpo if p.y0 < ancla.y0],
        "resto": [p for p in cuerpo if p.y0 >= ancla.y0],
    }


def textos_de_columna(resto: list[Palabra], n: int) -> list[list[Palabra]]:
    """Las palabras de cada columna, desde su primera viñeta hacia abajo."""
    inicios: list[float] = []
    for x in sorted(p.x0 for p in resto if p.texto.startswith("•")):
        if not inicios or x - inicios[-1] > TOLERANCIA_X:
            inicios.append(x)
    esperadas = PAGINAS[n].columnas
    if len(inicios) != len(esperadas):
        fallar(f"p{n}: viñetas en {inicios} y se esperaban {len(esperadas)} columnas")
    columnas = []
    for x, siguiente in zip(inicios, [*inicios[1:], math.inf], strict=True):
        propias = [
            p for p in resto if x - TOLERANCIA_X <= p.x0 < siguiente - TOLERANCIA_X
        ]
        arriba = min(p.y0 for p in propias if p.texto.startswith("•"))
        columnas.append([p for p in propias if p.y0 >= arriba - TOLERANCIA_Y])
    return columnas


def limites_x(columnas: list[list[Palabra]], n: int) -> list[int]:
    """Bordes verticales: n columnas dan n + 1 límites."""
    entre = [
        mitad_del_hueco(max(p.x1 for p in a), min(p.x0 for p in b), f"columnas en p{n}")
        for a, b in zip(columnas, columnas[1:], strict=False)
    ]
    primero = math.floor(min(p.x0 for p in columnas[0])) - MARGEN
    ultimo = math.ceil(max(p.x1 for p in columnas[-1])) + MARGEN
    return [primero, *entre, ultimo]


def limite_inferior(columnas: list[list[Palabra]], pie: list[Palabra], n: int) -> int:
    limite = math.ceil(max(p.y1 for c in columnas for p in c)) + 1
    if limite >= min(centro_y(p) for p in pie):
        fallar(f"p{n}: el texto llega hasta el pie (y_inferior = {limite})")
    return limite


def recortes_de_columnas(partes: dict, n: int) -> list[dict]:
    """El recorte de cada columna, con sus medidas y su número de viñetas."""
    columnas = textos_de_columna(partes["resto"], n)
    de_columna = {p for c in columnas for p in c}
    cabecera = [p for p in partes["resto"] if p not in de_columna]
    arriba = max(min(p.y0 for p in c) for c in columnas)
    sueltas = [p.texto for p in cabecera if p.y0 >= arriba]
    if sueltas:
        fallar(f"p{n}: texto fuera de las columnas bajo el encabezado: {sueltas}")
    x = limites_x(columnas, n)
    y_inferior = limite_inferior(columnas, partes["pie"], n)
    recortes = []
    for k, (nombre, texto) in enumerate(
        zip(PAGINAS[n].columnas, columnas, strict=True)
    ):
        x0, x1 = min(p.x0 for p in texto), max(p.x1 for p in texto)
        encima = [p for p in cabecera if p.x1 > x0 and p.x0 < x1]
        if not encima:
            fallar(f"p{n}, {nombre}: no hay encabezado sobre la columna")
        fin_cabecera = max(p.y1 for p in encima)
        inicio = min(p.y0 for p in texto)
        recortes.append(
            {
                "columna": nombre,
                "subcolumna": SUBCOLUMNAS.get((n, nombre)),
                "x_izquierda": x[k],
                "x_derecha": x[k + 1],
                "y_superior": mitad_del_hueco(
                    fin_cabecera, inicio, f"encabezado en p{n}, {nombre}"
                ),
                "y_inferior": y_inferior,
                "vinetas": sum(p.texto.startswith("•") for p in texto),
                "medido": {
                    "fin_encabezado_y": fin_cabecera,
                    "inicio_texto_y": inicio,
                    "fin_texto_y": max(p.y1 for p in texto),
                    "texto_x0": x0,
                    "texto_x1": x1,
                },
            }
        )
    controlar_columnas(recortes, columnas, cabecera, partes, n)
    return recortes


def controlar_columnas(
    recortes: list[dict],
    columnas: list[list[Palabra]],
    cabecera: list[Palabra],
    partes: dict,
    n: int,
) -> None:
    """Cada recorte deja justo su texto y está bajo el encabezado que le toca."""
    todas = [*partes["globos"], *partes["resto"], *partes["pie"]]
    for r, texto in zip(recortes, columnas, strict=True):
        nombre = r["columna"]
        if {p for p in todas if dentro(p, r)} != set(texto):
            fallar(f"p{n}, {nombre}: el recorte no deja justo el texto de la columna")
        titulo = en_orden(
            [
                p
                for p in cabecera
                if r["x_izquierda"] < (p.x0 + p.x1) / 2 < r["x_derecha"]
                and p.y0 < r["y_superior"]
            ]
        )
        for esperado in (TITULOS[nombre], r["subcolumna"]):
            if esperado and esperado not in titulo:
                fallar(f"p{n}, {nombre}: el encabezado es {titulo!r}, sin {esperado!r}")


def tramos_de_globos(globos: list[Palabra], n: int) -> list[tuple[float, float]]:
    """Dónde empieza y termina cada globo, de izquierda a derecha."""
    tramos: list[tuple[float, float]] = []
    for a, b in intervalos_x(globos):
        if tramos and a - tramos[-1][1] < SEPARACION_GLOBOS:
            tramos[-1] = (tramos[-1][0], b)
        else:
            tramos.append((a, b))
    if len(tramos) != PAGINAS[n].globos:
        fallar(f"p{n}: hay {len(tramos)} globos y se esperaban {PAGINAS[n].globos}")
    return tramos


def tipo_de_globo(texto: str, k: int, n: int) -> str:
    """Introducción del grupo (primer globo de la página par) o estándar general."""
    es_intro = texto.startswith(INTRODUCCION)
    if es_intro != (n in ULTIMO_GRADO and k == 0):
        fallar(f"p{n}: la introducción del grupo no está donde se esperaba")
    if es_intro and ULTIMO_GRADO[n] not in texto:
        fallar(f"p{n}: la introducción no nombra el grado {ULTIMO_GRADO[n]}")
    if not es_intro and not texto.endswith("."):
        fallar(f"p{n}: un estándar general no termina en punto (globo {k + 1})")
    return "introduccion" if es_intro else "estandar_general"


def recortes_de_globos(partes: dict, n: int) -> list[dict]:
    """El recorte de cada globo, con su tipo."""
    recortes: list[dict] = []
    for k, (a, b) in enumerate(tramos_de_globos(partes["globos"], n)):
        palabras = [p for p in partes["globos"] if a <= p.x0 <= b]
        r = {
            "tipo": tipo_de_globo(en_orden(palabras), k, n),
            "x_izquierda": math.floor(a) - MARGEN,
            "x_derecha": math.ceil(b) + MARGEN,
            "y_superior": math.floor(min(p.y0 for p in palabras)) - MARGEN,
            "y_inferior": math.ceil(max(p.y1 for p in palabras)) + MARGEN,
        }
        if recortes and r["x_izquierda"] <= recortes[-1]["x_derecha"]:
            fallar(f"p{n}: dos globos se montan")
        if r["y_inferior"] >= partes["ancla"].y0:
            fallar(f"p{n}: un globo llega hasta el encabezado")
        if {p for p in partes["globos"] if dentro(p, r)} != set(palabras):
            fallar(f"p{n}: el recorte del globo {k + 1} no deja justo su texto")
        recortes.append(r)
    return recortes


def medir(paginas: dict[int, list[Palabra]]) -> list[dict]:
    """Los recortes de cada página, ya controlados."""
    medidas = []
    for n, palabras in paginas.items():
        partes = separar(palabras, n)
        columnas = recortes_de_columnas(partes, n)
        vinetas = sum(p.texto.count("•") for p in palabras)
        if sum(c["vinetas"] for c in columnas) != vinetas:
            fallar(f"p{n}: hay {vinetas} viñetas y no todas quedaron en una columna")
        medidas.append(
            {
                "pagina": n,
                "grupo": PAGINAS[n].grupo,
                "columnas": columnas,
                "contexto": recortes_de_globos(partes, n),
            }
        )
    return medidas


def conteo_por_grupo(medidas: list[dict]) -> dict[str, dict[str, int]]:
    """Viñetas por grupo de grados y columna (el entorno físico suma sus dos partes)."""
    conteo: dict[str, dict[str, int]] = {}
    for m in medidas:
        grupo = conteo.setdefault(m["grupo"], {})
        for c in m["columnas"]:
            grupo[c["columna"]] = grupo.get(c["columna"], 0) + c["vinetas"]
    return conteo


def rectangulo(filas: list[bytearray], r: dict, escala: float) -> None:
    """Dibuja en rojo, con 2 px, el borde de un recorte."""
    rojo = b"\xff\x00\x00"
    x0, x1 = (round(r[k] * escala) for k in ("x_izquierda", "x_derecha"))
    y0, y1 = (round(r[k] * escala) for k in ("y_superior", "y_inferior"))
    for y in (y0, y0 + 1, y1 - 1, y1):
        filas[y][3 * x0 : 3 * (x1 + 1)] = rojo * (x1 - x0 + 1)
    for y in range(y0, y1 + 1):
        for x in (x0, x1 - 1):
            filas[y][3 * x : 3 * (x + 2)] = rojo * 2


def pagina_con_recortes(pdf: Path, ancho_pts: float, medida: dict) -> list[bytes]:
    """La página en RGB (filas de bytes) con todos sus recortes en rojo."""
    n = medida["pagina"]
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "pagina"
        orden = ["pdftoppm", "-r", str(DPI_EVIDENCIA), "-f", str(n), "-l", str(n)]
        ejecutar([*orden, "-gray", "-singlefile", str(pdf), str(base)])
        ancho, _, grises = leer_pgm(base.with_suffix(".pgm").read_bytes())
    escala = DPI_EVIDENCIA / 72
    # las líneas solo valen si la imagen usa las mismas coordenadas que -bbox
    if abs(ancho - ancho_pts * escala) > 1:
        fallar(f"p{n}: la imagen ({ancho} px) no corresponde a {ancho_pts} pt")
    filas = []
    for g in grises:
        rgb = bytearray(3 * ancho)
        rgb[0::3], rgb[1::3], rgb[2::3] = g, g, g
        filas.append(rgb)
    for r in (*medida["columnas"], *medida["contexto"]):
        rectangulo(filas, r, escala)
    return [bytes(f) for f in filas]


def leer_paginas(pdf: Path) -> tuple[dict[int, float], dict[int, list[Palabra]]]:
    a, b = min(PAGINAS), max(PAGINAS)
    orden = ["pdftotext", "-bbox", "-f", str(a), "-l", str(b), str(pdf), "-"]
    leidas = paginas_con_cajas(ejecutar(orden).stdout)
    if len(leidas) != len(PAGINAS):
        fallar(f"se leyeron {len(leidas)} páginas y se esperaban {len(PAGINAS)}")
    anchos = {n: ancho for n, (ancho, _) in zip(PAGINAS, leidas, strict=True)}
    return anchos, {n: pal for n, (_, pal) in zip(PAGINAS, leidas, strict=True)}


def main() -> None:
    if CONFIG.exists():
        fallar(f"{CONFIG.name} ya existe; no se sobrescribe (puede estar verificado)")
    doc = documento_del_inventario(ID_EBC)
    pdf = pdf_verificado(doc)
    anchos, paginas = leer_paginas(pdf)
    medidas = medir(paginas)
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    imagenes = []
    for m in medidas:
        filas = pagina_con_recortes(pdf, anchos[m["pagina"]], m)
        escribir_png_rgb(EVIDENCIA / f"p{m['pagina']}.png", filas)
        imagenes.append(filas)
    escribir_png_rgb(EVIDENCIA / "todas.png", hoja_de_contacto(imagenes))
    config = {
        "id": ID_EBC,
        "decision": "D60",
        "entrada": {"archivo": doc["ruta_local"], "sha256": doc["sha256"]},
        "pdftotext": version_pdftotext(),
        "unidades": "puntos PDF, como los da pdftotext -bbox",
        "criterio": CRITERIO,
        "metodo": METODO,
        "paginas": [
            {
                "pagina": m["pagina"],
                "grupo": m["grupo"],
                "verificado_por": "",
                "fecha": date.today().isoformat(),
                "columnas": m["columnas"],
                "contexto": m["contexto"],
            }
            for m in medidas
        ],
    }
    CONFIG.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    for m in medidas:
        columnas = {c["columna"]: c["vinetas"] for c in m["columnas"]}
        globos = len(m["contexto"])
        print(f"p{m['pagina']} ({m['grupo']}): {columnas} · globos {globos}")
    for grupo, columnas in conteo_por_grupo(medidas).items():
        print(f"grupo {grupo}: {sum(columnas.values())} viñetas · {columnas}")
    print(f"config: {CONFIG.relative_to(RAIZ_REPO)}")
    print(f"imágenes: {EVIDENCIA.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()
