"""Propuesta de recorte superior por página para PE-PCS-2016 (D57, adenda).

Se mide UNA vez y los valores se congelan en config/recortes_pe_pcs_2016.yaml; el OCR
(ocr_pe_09.py) lee ese YAML y no vuelve a medir. Esta detección solo PROPONE: la
persona que revisa confirma a ojo y escribe su nombre en `verificado_por`.

Método: pdftoppm entrega la franja superior de la página (15 % de la altura) a 300 dpi
en formato PGM (texto plano de píxeles que se lee con la biblioteca estándar). Por cada
fila se calcula la proporción de píxeles oscuros. Las filas con tinta se agrupan en
bandas; la primera banda es el encabezado «649-2016-MINEDU». El recorte propuesto es el
fin de esa banda más un margen pequeño (MARGEN_PX).

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.recortes_pe_09

Escribe el YAML (si ya existe, FALLA: puede traer verificaciones) y la evidencia para
revisar (franja superior de cada página a 100 dpi con una línea roja en el recorte
propuesto) en data/processed/curriculo/PE-PCS-2016_ocr/revision_recortes/. No corre OCR.
"""

from __future__ import annotations

import re
import struct
import tempfile
import zlib
from datetime import date
from pathlib import Path

import yaml

from rs_pipeline.ocr_pe_09 import (
    DPI,
    ID_REFERENTE,
    PAGINAS_PERMITIDAS,
    RAIZ_REPO,
    ejecutar,
    pdf_del_inventario,
    tamano_pagina_pts,
)
from rs_pipeline.semantico_texto import fallar

CONFIG = RAIZ_REPO / "config" / "recortes_pe_pcs_2016.yaml"
EVIDENCIA = (
    RAIZ_REPO
    / "data"
    / "processed"
    / "curriculo"
    / "PE-PCS-2016_ocr"
    / "revision_recortes"
)
FRANJA = 0.15  # parte superior de la página que se examina (fracción de la altura)
PIXEL_OSCURO = 140  # un píxel de 0 (negro) a 255 (blanco) es tinta si vale menos
TINTA_MINIMA_FILA = 0.004  # proporción de píxeles oscuros para que una fila tenga tinta
ALTO_MIN_BANDA_PX = (
    9  # una banda más baja es una mota del escaneo, no texto (a 300 dpi)
)
UNION_HUECOS_PX = 6  # huecos menores que esto dentro de una banda no la parten
# Margen bajo el encabezado, en píxeles a 300 dpi (0,5 mm). Debe ser mayor que el borde
# difuso de la tinta (MARGEN_MIN_PX) y no pasar de la mitad del hueco hasta la línea de
# abajo, para no tocar ni el encabezado ni el texto siguiente. Si el hueco es estrecho
# (p191: 10 px) el margen baja a la mitad del hueco; si ni así llega al mínimo, FALLA.
MARGEN_PX = 6
MARGEN_MIN_PX = 3
DPI_EVIDENCIA = 100
METODO = "propuesto por detección PGM, verificado a ojo"


def leer_pgm(datos: bytes) -> tuple[int, int, list[bytes]]:
    """Lee un PGM binario (P5, 8 bits) y devuelve ancho, alto y las filas."""
    m = re.match(rb"P5\s+(\d+)\s+(\d+)\s+(\d+)\s", datos)
    if m is None or int(m.group(3)) != 255:
        fallar("el PGM no es P5 de 8 bits")
    ancho, alto = int(m.group(1)), int(m.group(2))
    cuerpo = datos[m.end() :]
    if len(cuerpo) != ancho * alto:
        fallar(f"el PGM trae {len(cuerpo)} bytes y se esperaban {ancho * alto}")
    return ancho, alto, [cuerpo[i * ancho : (i + 1) * ancho] for i in range(alto)]


def proporcion_tinta(fila: bytes) -> float:
    return sum(p < PIXEL_OSCURO for p in fila) / len(fila)


def bandas_de_tinta(proporciones: list[float]) -> list[tuple[int, int]]:
    """Bandas (fila inicial, fila final inclusive) de filas con tinta.

    Los huecos de menos de UNION_HUECOS_PX filas no parten una banda y las bandas más
    bajas que ALTO_MIN_BANDA_PX se descartan.
    """
    corridas: list[list[int]] = []
    for i, p in enumerate(proporciones):
        if p < TINTA_MINIMA_FILA:
            continue
        if corridas and i - corridas[-1][1] - 1 < UNION_HUECOS_PX:
            corridas[-1][1] = i
        else:
            corridas.append([i, i])
    return [(a, b) for a, b in corridas if b - a + 1 >= ALTO_MIN_BANDA_PX]


def proponer_pagina(pdf: Path, pagina: int) -> dict:
    ancho_pts, alto_pts = tamano_pagina_pts(pdf, pagina)
    alto_px = round(alto_pts * DPI / 72)
    franja_px = round(alto_px * FRANJA)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "franja"
        ejecutar(
            [
                "pdftoppm", "-r", str(DPI), "-f", str(pagina), "-l", str(pagina),
                "-gray", "-H", str(franja_px), "-singlefile", str(pdf), str(base),
            ]
        )  # fmt: skip
        _, _, filas = leer_pgm(base.with_suffix(".pgm").read_bytes())
    bandas = bandas_de_tinta([proporcion_tinta(f) for f in filas])
    if not bandas:
        fallar(f"p{pagina}: no hay ninguna banda de tinta en la franja superior")
    inicio, fin = bandas[0]
    if fin >= len(filas) - 1:
        fallar(f"p{pagina}: la primera banda llega al borde de la franja examinada")
    hueco = bandas[1][0] - fin - 1 if len(bandas) > 1 else None
    margen = MARGEN_PX if hueco is None else min(MARGEN_PX, hueco // 2)
    if margen < MARGEN_MIN_PX:
        fallar(
            f"p{pagina}: el hueco ({hueco} px) no deja un margen de {MARGEN_MIN_PX} px"
        )
    recorte_px = fin + 1 + margen
    siguiente = (
        f"hueco hasta la siguiente banda: {hueco} px"
        if hueco is not None
        else "no hay otra banda dentro de la franja examinada"
    )
    return {
        "pagina": pagina,
        "recorte_superior": round(recorte_px / alto_px, 6),
        "px_300dpi": recorte_px,
        "metodo": METODO,
        "verificado_por": "",
        "fecha": date.today().isoformat(),
        "nota": (
            f"encabezado en las filas {inicio}-{fin} (px a 300 dpi); {siguiente}; "
            f"margen {margen} px; altura de página {alto_px} px"
        ),
    }


def _chunk(tipo: bytes, datos: bytes) -> bytes:
    crc = zlib.crc32(tipo + datos) & 0xFFFFFFFF
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)


def escribir_png_rgb(ruta: Path, filas: list[bytes]) -> None:
    """PNG RGB de 8 bits con la biblioteca estándar (cada fila: 3 bytes por píxel)."""
    ancho, alto = len(filas[0]) // 3, len(filas)
    crudo = b"".join(b"\x00" + f for f in filas)
    ruta.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(crudo, 9))
        + _chunk(b"IEND", b"")
    )


def franja_con_linea_roja(pdf: Path, pagina: int, recorte_px_300: int) -> list[bytes]:
    """Franja superior (15 %) a 100 dpi en RGB, con una línea roja en el recorte."""
    _, alto_pts = tamano_pagina_pts(pdf, pagina)
    franja_px = round(round(alto_pts * DPI_EVIDENCIA / 72) * FRANJA)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "franja"
        ejecutar(
            [
                "pdftoppm", "-r", str(DPI_EVIDENCIA), "-f", str(pagina), "-l",
                str(pagina), "-gray", "-H", str(franja_px), "-singlefile", str(pdf),
                str(base),
            ]
        )  # fmt: skip
        ancho, _, grises = leer_pgm(base.with_suffix(".pgm").read_bytes())
    filas = []
    for g in grises:
        rgb = bytearray(3 * ancho)
        rgb[0::3], rgb[1::3], rgb[2::3] = g, g, g
        filas.append(bytes(rgb))
    y = round(recorte_px_300 * DPI_EVIDENCIA / DPI)
    for yy in (y, y + 1):
        if yy < len(filas):
            filas[yy] = b"\xff\x00\x00" * ancho
    return filas


def hoja_de_contacto(franjas: list[list[bytes]]) -> list[bytes]:
    """Junta las franjas en dos columnas (orden: izquierda a derecha, arriba abajo)."""
    ancho = len(franjas[0][0]) // 3
    blanco = b"\xff\xff\xff" * 6
    filas: list[bytes] = []
    for i in range(0, len(franjas), 2):
        izq = franjas[i]
        der = (
            franjas[i + 1] if i + 1 < len(franjas) else [b"\xff" * 3 * ancho] * len(izq)
        )
        filas += [a + blanco + b for a, b in zip(izq, der, strict=True)]
        filas += [b"\xff\xff\xff" * (2 * ancho + 6)] * 6
    return filas


def main() -> None:
    if CONFIG.exists():
        fallar(
            f"{CONFIG.name} ya existe; no se sobrescribe (puede traer verificaciones)"
        )
    pdf, hash_pdf = pdf_del_inventario()
    paginas = [proponer_pagina(pdf, p) for p in PAGINAS_PERMITIDAS]
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    franjas = []
    for pag in paginas:
        filas = franja_con_linea_roja(pdf, pag["pagina"], pag["px_300dpi"])
        escribir_png_rgb(EVIDENCIA / f"p{pag['pagina']}.png", filas)
        franjas.append(filas)
    escribir_png_rgb(EVIDENCIA / "todas.png", hoja_de_contacto(franjas))
    config = {
        "id": ID_REFERENTE,
        "decision": "D57",
        "entrada_sha256": hash_pdf,
        "dpi_referencia": DPI,
        "margen_px_300dpi": {"maximo": MARGEN_PX, "minimo": MARGEN_MIN_PX},
        "paginas": paginas,
    }
    CONFIG.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    for pag in paginas:
        print(f"p{pag['pagina']}: {pag['px_300dpi']} px ({pag['recorte_superior']})")
    print(f"config: {CONFIG.relative_to(RAIZ_REPO)}")
    print(f"evidencia: {EVIDENCIA.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()
