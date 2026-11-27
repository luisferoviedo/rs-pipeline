"""Medición de las viñetas de los desempeños de Perú (PE-PCS-2016; D57, D60).

El inicio de cada desempeño es su viñeta (el punto redondo), detectada en la imagen:
el OCR no la lee siempre. Se mide UNA vez y las posiciones se congelan en
config/vinetas_pe_pcs_2016.yaml; el extractor (paso siguiente) leerá ese YAML y no
volverá a medir. Esto solo PROPONE: la persona que revisa confirma a ojo antes de
llenar `verificado_por`.

En cada página con desempeños, sobre la misma imagen que leyó el OCR (v2):
- la tabla es la mancha de tinta más grande que ocupe más de un tercio del ancho;
- las columnas se separan en la mitad de la tabla;
- la zona de desempeños va desde debajo de «…siguientes:» (en la 187, continuación,
  desde arriba de la tabla) hasta el borde inferior de la tabla;
- una viñeta es un punto redondo y lleno en el carril izquierdo de su columna.
Controles: ningún punto redondo fuera del carril; cada viñeta tiene texto a su derecha
y ese texto empieza por uno de los verbos en tercera persona de los desempeños; el
grado del encabezado de la columna es el esperado.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.vinetas_pe_09

Escribe el YAML (si ya existe, FALLA: puede traer verificaciones) y las imágenes para
revisar en data/processed/curriculo/PE-PCS-2016_ocr/revision_vinetas/ (fuera de git).
"""

from __future__ import annotations

import csv
import json
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import NamedTuple

import yaml

from rs_pipeline.ocr_pe_09 import (
    DESTINO,
    DPI,
    ID_REFERENTE,
    PROCEDENCIA,
    RAIZ_REPO,
    ejecutar,
    pdf_del_inventario,
    sha256_de,
)
from rs_pipeline.recortes_pe_09 import escribir_png_rgb, leer_pgm
from rs_pipeline.semantico_texto import fallar

CONFIG = RAIZ_REPO / "config" / "vinetas_pe_pcs_2016.yaml"
EVIDENCIA = DESTINO / "revision_vinetas"
OCR_JSON = PROCEDENCIA / "PE-PCS-2016_ocr_p177-194_v2.json"


class Pagina(NamedTuple):
    competencia: str
    grados: tuple[int, ...]  # un grado por columna, de izquierda a derecha
    continuacion: bool = False  # sigue de la página anterior, sin encabezado


PAGINAS = {
    181: Pagina("indaga", (1, 2)),
    182: Pagina("indaga", (3, 4)),
    183: Pagina("indaga", (5,)),
    186: Pagina("explica", (1, 2)),
    187: Pagina("explica", (1, 2), continuacion=True),
    188: Pagina("explica", (3, 4)),
    189: Pagina("explica", (5,)),
    192: Pagina("disena", (1, 2)),
    193: Pagina("disena", (3, 4)),
    194: Pagina("disena", (5,)),
}
ORDINALES = {1: "PRIMER", 2: "SEGUNDO", 3: "TERCER", 4: "CUARTO", 5: "QUINTO"}
# Verbos con los que empieza un desempeño (D57, cuarta adenda: control de la viñeta)
VERBOS = frozenset(
    "Compara Comprueba Describe Ejecuta Establece Explica Formula Fundamenta "
    "Justifica Obtiene Propone Realiza Representa Sustenta".split()
)
INICIO_ZONA = "siguientes"  # «…realiza desempeños como los siguientes:»

PIXEL_OSCURO = 140  # de 0 (negro) a 255 (blanco); es tinta si vale menos
LADO_MIN, LADO_MAX = 11, 22  # px a 300 dpi; la viñeta mide unos 16
LADOS_DIF_MAX = 4  # ancho y alto casi iguales
RELLENO_MIN = 0.66  # un círculo lleno ocupa 0,79 de su caja
TABLA_ANCHO_MIN, TABLA_ALTO_MIN = 0.35, 60  # fracción del ancho y px
HOLGURA_X = 20  # px que una viñeta puede quedar a la izquierda de su columna
ANCHO_CARRIL = 45  # px; las viñetas de una columna están alineadas
ALTO_LINEA = 24  # px entre el centro de la viñeta y el de las palabras de su línea
GLIFO_MAX = 3  # el OCR lee a veces la viñeta como «e», «+» o «.»
PASO_PAGINA, PASO_PAREJA = 2, 3  # reducción de las imágenes de revisión
PAREJAS = {"m1": (181, 182), "m2": (183, 189), "m3": (186, 187),
           "m4": (188, 194), "m5": (192, 193)}  # fmt: skip
METODO = "detección de puntos redondos en la imagen del OCR, verificada a ojo"

_A_BINARIO = bytes(49 if v < PIXEL_OSCURO else 48 for v in range(256))  # «1» o «0»
ROJO, AZUL, VERDE = b"\xff\x00\x00", b"\x00\x00\xff", b"\x00\x80\x00"


class Caja(NamedTuple):
    x0: int
    y0: int
    x1: int
    y1: int
    pixeles: int = 0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


class Palabra(NamedTuple):
    texto: str
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


# --- Manchas de tinta ---------------------------------------------------------


def _raiz(padre: list[int], i: int) -> int:
    while padre[i] != i:
        padre[i] = padre[padre[i]]
        i = padre[i]
    return i


def _juntar(a: Caja, b: Caja) -> Caja:
    return Caja(
        min(a.x0, b.x0),
        min(a.y0, b.y0),
        max(a.x1, b.x1),
        max(a.y1, b.y1),
        a.pixeles + b.pixeles,
    )


def componentes(filas: list[bytes]) -> list[Caja]:
    """Cajas de las manchas de píxeles oscuros que se tocan (también en diagonal)."""
    padre: list[int] = []
    cajas: list[Caja] = []
    anteriores: list[tuple[int, int, int]] = []
    for y, fila in enumerate(filas):
        actuales = []
        for tramo in re.finditer(rb"1+", fila.translate(_A_BINARIO)):
            a, b = tramo.span()
            i = len(padre)
            padre.append(i)
            cajas.append(Caja(a, y, b, y + 1, b - a))
            for pa, pb, j in anteriores:
                if pa <= b and a <= pb:
                    r1, r2 = _raiz(padre, i), _raiz(padre, j)
                    if r1 != r2:
                        padre[r2] = r1
                        cajas[r1] = _juntar(cajas[r1], cajas[r2])
            actuales.append((a, b, i))
        anteriores = actuales
    return [c for i, c in enumerate(cajas) if padre[i] == i]


def es_punto_redondo(c: Caja) -> bool:
    ancho, alto = c.x1 - c.x0, c.y1 - c.y0
    if not (LADO_MIN <= ancho <= LADO_MAX and LADO_MIN <= alto <= LADO_MAX):
        return False
    lleno = c.pixeles / (ancho * alto)
    return abs(ancho - alto) <= LADOS_DIF_MAX and lleno >= RELLENO_MIN


def tabla_de(cajas: list[Caja], ancho: int, pagina: int) -> Caja:
    grandes = [
        c
        for c in cajas
        if c.x1 - c.x0 > ancho * TABLA_ANCHO_MIN and c.y1 - c.y0 >= TABLA_ALTO_MIN
    ]
    if not grandes:
        fallar(f"p{pagina}: no se encontró el marco de la tabla")
    return max(grandes, key=lambda c: (c.x1 - c.x0) * (c.y1 - c.y0))


# --- Columnas y viñetas -------------------------------------------------------


def limites_de_columnas(tabla: Caja, n: int) -> list[tuple[float, float]]:
    if len(PAGINAS[n].grados) == 1:
        return [(tabla.x0, tabla.x1)]
    mitad = (tabla.x0 + tabla.x1) / 2
    return [(tabla.x0, mitad), (mitad, tabla.x1)]


def inicio_de_zona(palabras: list[Palabra], tabla: Caja, n: int) -> int:
    """Borde inferior de «…siguientes:»; en la continuación, el de arriba."""
    marcas = [p for p in palabras if INICIO_ZONA in p.texto]
    if PAGINAS[n].continuacion:
        if marcas:
            fallar(f"p{n}: es continuación y trae un encabezado «siguientes»")
        return tabla.y0
    if not marcas:
        fallar(f"p{n}: una columna no tiene «…siguientes:»")
    return max(marcas, key=lambda p: p.y0).y1


def controlar_grado(palabras: list[Palabra], y: int, grado: int, n: int) -> None:
    """El encabezado de la columna nombra el grado esperado (la 187 no lo trae)."""
    if PAGINAS[n].continuacion:
        return
    leidos = {p.texto for p in palabras if p.cy < y} & set(ORDINALES.values())
    if leidos != {ORDINALES[grado]}:
        fallar(f"p{n}: el encabezado de la columna dice {leidos}, no el grado {grado}")


def es_glifo(p: Palabra, vinetas: list[Caja]) -> bool:
    """La propia viñeta leída por el OCR como una palabra corta."""
    return len(p.texto) <= GLIFO_MAX and any(
        c.x0 - 6 <= p.cx <= c.x1 + 6 and c.y0 - 12 <= p.cy <= c.y1 + 12 for c in vinetas
    )


def primera_palabra(vineta: Caja, palabras: list[Palabra], n: int) -> str:
    linea = [
        p for p in palabras if abs(p.cy - vineta.cy) <= ALTO_LINEA and p.cx > vineta.x1
    ]
    if not linea:
        fallar(f"p{n}: la viñeta en y={vineta.y0} no tiene texto a su derecha")
    return min(linea, key=lambda p: p.x0).texto.strip(" .,|+-")


def vinetas_de_columna(
    puntos: list[Caja], limites: tuple[float, float], y0: int, y1: int, n: int
) -> list[Caja]:
    """Los puntos redondos de la zona; todos deben estar en el carril izquierdo."""
    a, b = limites
    zona = [c for c in puntos if a - HOLGURA_X <= c.x0 < b and y0 < c.cy < y1]
    if not zona:
        fallar(f"p{n}: una columna no tiene viñetas")
    carril = min(c.x0 for c in zona)
    fuera = [(c.x0, c.y0) for c in zona if c.x0 - carril > ANCHO_CARRIL]
    if fuera:
        fallar(f"p{n}: puntos redondos fuera del carril de viñetas: {fuera}")
    return sorted(zona, key=lambda c: c.y0)


def medir_pagina(filas: list[bytes], palabras: list[Palabra], n: int) -> dict:
    cajas = componentes(filas)
    tabla = tabla_de(cajas, len(filas[0]), n)
    puntos = [c for c in cajas if es_punto_redondo(c)]
    columnas = []
    for grado, (a, b) in zip(
        PAGINAS[n].grados, limites_de_columnas(tabla, n), strict=True
    ):
        propias = [p for p in palabras if a <= p.cx < b and tabla.y0 < p.cy < tabla.y1]
        y = inicio_de_zona(propias, tabla, n)
        controlar_grado(propias, y, grado, n)
        vinetas = vinetas_de_columna(puntos, (a, b), y, tabla.y1, n)
        texto = [p for p in propias if not es_glifo(p, vinetas)]
        for v in vinetas:
            verbo = primera_palabra(v, texto, n)
            if verbo not in VERBOS:
                fallar(f"p{n}: junto a una viñeta el texto empieza por {verbo!r}")
        columnas.append(
            {
                "grado": grado,
                "x_izquierda": int(a),
                "x_derecha": int(b),
                "y_superior": y,
                "y_inferior": tabla.y1,
                "vinetas": [[v.x0, v.y0, v.x1, v.y1] for v in vinetas],
            }
        )
    return {
        "pagina": n,
        "competencia": PAGINAS[n].competencia,
        "tabla": [tabla.x0, tabla.y0, tabla.x1, tabla.y1],
        "columnas": columnas,
    }


# --- Entradas: imagen y palabras del OCR --------------------------------------


def palabras_del_tsv(ruta: Path) -> list[Palabra]:
    with ruta.open(encoding="utf-8", newline="") as f:
        filas = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        return [
            Palabra(
                r["text"],
                int(r["left"]),
                int(r["top"]),
                int(r["left"]) + int(r["width"]),
                int(r["top"]) + int(r["height"]),
            )
            for r in filas
            if r["level"] == "5" and r["text"].strip()
        ]


def orden_pdftoppm(pdf: Path, n: int, r: dict, salida: Path, formato: str) -> list:
    orden = ["pdftoppm", "-r", str(DPI), "-f", str(n), "-l", str(n), "-gray"]
    if formato == "png":
        orden.append("-png")
    orden += ["-singlefile", "-x", str(r["x"]), "-y", str(r["y"])]
    orden += ["-W", str(r["ancho"]), "-H", str(r["alto"]), str(pdf), str(salida)]
    return orden


def entradas_de_pagina(pdf: Path, ficha: dict) -> tuple[list[bytes], list[Palabra]]:
    """Imagen (filas de grises) y palabras; ambas deben ser las del OCR registrado."""
    n = ficha["pagina_pdf"]
    nombre = f"p{n:03d}"
    tsv = DESTINO / f"{nombre}.tsv"
    if sha256_de(tsv) != ficha["salidas"][tsv.name]["sha256"]:
        fallar(f"p{n}: el TSV no es el del registro {OCR_JSON.name}")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / nombre
        ejecutar(orden_pdftoppm(pdf, n, ficha["recorte_px"], base, "png"))
        png = base.with_suffix(".png")
        if sha256_de(png) != ficha["salidas"][f"{nombre}.png"]["sha256"]:
            fallar(f"p{n}: la imagen no sale igual a la que leyó el OCR")
        ejecutar(orden_pdftoppm(pdf, n, ficha["recorte_px"], base, "pgm"))
        _, _, filas = leer_pgm(base.with_suffix(".pgm").read_bytes())
    return filas, palabras_del_tsv(tsv)


def fichas_del_ocr(hash_pdf: str) -> dict[int, dict]:
    registro = json.loads(OCR_JSON.read_text(encoding="utf-8"))
    if registro["entrada"]["sha256"] != hash_pdf:
        fallar(f"{OCR_JSON.name}: el OCR se hizo sobre otro PDF")
    fichas = {p["pagina_pdf"]: p for p in registro["paginas"]}
    faltan = [n for n in PAGINAS if n not in fichas]
    if faltan:
        fallar(f"{OCR_JSON.name}: faltan las páginas {faltan}")
    return fichas


# --- Imágenes de revisión -----------------------------------------------------


def _pintar(filas: list[bytearray], x0: int, y0: int, x1: int, y1: int, color: bytes):
    x0, x1 = max(x0, 0), min(x1, len(filas[0]) // 3)
    for y in range(max(y0, 0), min(y1, len(filas))):
        filas[y][3 * x0 : 3 * x1] = color * (x1 - x0)


def pagina_marcada(grises: list[bytes], medida: dict) -> list[bytearray]:
    """La página en RGB: cada viñeta en rojo y el inicio de cada zona en azul."""
    ancho = len(grises[0])
    filas = []
    for g in grises:
        rgb = bytearray(3 * ancho)
        rgb[0::3], rgb[1::3], rgb[2::3] = g, g, g
        filas.append(rgb)
    for c in medida["columnas"]:
        for x0, y0, x1, y1 in c["vinetas"]:
            a, b, d, e = x0 - 14, y0 - 14, x1 + 14, y1 + 14
            for caja in ((a, b, d, b + 6), (a, e - 6, d, e),
                         (a, b, a + 6, e), (d - 6, b, d, e)):  # fmt: skip
                _pintar(filas, *caja, ROJO)
        y = c["y_superior"]
        _pintar(filas, c["x_izquierda"], y, c["x_derecha"], y + 5, AZUL)
    return filas


def reducir(filas: list[bytearray], paso: int) -> list[bytes]:
    ancho = len(filas[0]) // 3
    return [
        b"".join(bytes(f[3 * x : 3 * x + 3]) for x in range(0, ancho, paso))
        for f in filas[::paso]
    ]


def lado_a_lado(imagenes: list[list[bytes]]) -> list[bytes]:
    """Dos o más páginas en fila, separadas por una franja verde."""
    alto = max(len(i) for i in imagenes)
    blancos = [b"\xff" * len(i[0]) for i in imagenes]
    return [
        (VERDE * 6).join(
            i[y] if y < len(i) else blancos[k] for k, i in enumerate(imagenes)
        )
        for y in range(alto)
    ]


def medir_todo(pdf: Path, hash_pdf: str) -> tuple[list[dict], dict[int, list]]:
    """Medidas de las diez páginas y sus imágenes (para revisarlas)."""
    fichas = fichas_del_ocr(hash_pdf)
    medidas, imagenes = [], {}
    for n in PAGINAS:
        grises, palabras = entradas_de_pagina(pdf, fichas[n])
        medidas.append(medir_pagina(grises, palabras, n))
        imagenes[n] = grises
    return medidas, imagenes


def conteo_por_grado(medidas: list[dict]) -> dict[str, list[int]]:
    """Viñetas por competencia, de 1.º a 5.º."""
    conteo = {p.competencia: [0] * 5 for p in PAGINAS.values()}
    for m in medidas:
        for c in m["columnas"]:
            conteo[m["competencia"]][c["grado"] - 1] += len(c["vinetas"])
    return conteo


def main() -> None:
    if CONFIG.exists():
        fallar(f"{CONFIG.name} ya existe; no se sobrescribe (puede estar verificado)")
    pdf, hash_pdf = pdf_del_inventario()
    medidas, imagenes = medir_todo(pdf, hash_pdf)
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    marcadas = {}
    for m in medidas:
        n = m["pagina"]
        marcadas[n] = pagina_marcada(imagenes[n], m)
        escribir_png_rgb(EVIDENCIA / f"p{n}.png", reducir(marcadas[n], PASO_PAGINA))
    for nombre, paginas in PAREJAS.items():
        juntas = lado_a_lado([reducir(marcadas[n], PASO_PAREJA) for n in paginas])
        escribir_png_rgb(EVIDENCIA / f"{nombre}.png", juntas)
    config = {
        "id": ID_REFERENTE,
        "decision": "D57",
        "entrada": {"archivo": str(pdf.relative_to(RAIZ_REPO)), "sha256": hash_pdf},
        "ocr": {
            "archivo": str(OCR_JSON.relative_to(RAIZ_REPO)),
            "sha256": sha256_de(OCR_JSON),
        },
        "unidades": "píxeles de la imagen recortada del OCR, a 300 dpi",
        "vineta": "caja [x0, y0, x1, y1] del punto redondo que abre un desempeño",
        "metodo": METODO,
        "paginas": [
            {
                "pagina": m["pagina"],
                "competencia": m["competencia"],
                "verificado_por": "",
                "fecha": date.today().isoformat(),
                "tabla": m["tabla"],
                "columnas": m["columnas"],
            }
            for m in medidas
        ],
    }
    CONFIG.write_text(
        yaml.safe_dump(
            config, allow_unicode=True, sort_keys=False, default_flow_style=None
        ),
        encoding="utf-8",
    )
    for m in medidas:
        por_columna = {c["grado"]: len(c["vinetas"]) for c in m["columnas"]}
        print(f"p{m['pagina']} {m['competencia']}: viñetas por grado {por_columna}")
    for competencia, grados in conteo_por_grado(medidas).items():
        print(f"{competencia}: {grados} = {sum(grados)}")
    print(f"config: {CONFIG.relative_to(RAIZ_REPO)}")
    print(f"imágenes: {EVIDENCIA.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()
