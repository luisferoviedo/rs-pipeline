"""Tests de la propuesta de recortes de PE-PCS-2016 (recortes_pe_09; D57, adenda).

No corren pdftoppm: se prueban la lectura de PGM, las bandas de tinta y el PNG.
"""

import struct

import pytest

from rs_pipeline import recortes_pe_09 as R
from rs_pipeline.semantico_texto import ErrorPipeline


def test_leer_pgm_devuelve_dimensiones_y_filas():
    datos = b"P5\n3 2\n255\n" + bytes([0, 255, 128, 10, 20, 30])
    assert R.leer_pgm(datos) == (3, 2, [b"\x00\xff\x80", b"\n\x14\x1e"])


def test_leer_pgm_falla_si_el_tamano_no_cuadra():
    with pytest.raises(ErrorPipeline, match="bytes"):
        R.leer_pgm(b"P5\n3 2\n255\n" + bytes([0, 1, 2]))


def test_leer_pgm_falla_si_no_es_de_8_bits():
    with pytest.raises(ErrorPipeline, match="8 bits"):
        R.leer_pgm(b"P5\n1 1\n65535\n" + bytes([0, 0]))


def test_proporcion_tinta_cuenta_pixeles_bajo_el_umbral():
    # 0 y 139 son tinta (< 140); 255 y 140 no.
    assert R.proporcion_tinta(bytes([0, 255, 139, 140])) == 0.5


def test_bandas_unen_huecos_cortos_y_descartan_motas():
    p = [0.0] * 100
    for i in range(10, 30):  # banda 10-29
        p[i] = 0.5
    for i in range(33, 41):  # tras un hueco de 3 filas (< 6): se une -> 10-40
        p[i] = 0.5
    for i in range(60, 63):  # mota de 3 filas (< 9): se descarta
        p[i] = 0.5
    for i in range(80, 100):  # banda aparte
        p[i] = 0.5
    assert R.bandas_de_tinta(p) == [(10, 40), (80, 99)]


def test_bandas_no_unen_un_hueco_de_seis_filas():
    p = [0.0] * 50
    for i in list(range(10, 25)) + list(range(31, 46)):  # hueco de 6 filas (25-30)
        p[i] = 0.5
    assert R.bandas_de_tinta(p) == [(10, 24), (31, 45)]


def test_bandas_sin_tinta_devuelve_lista_vacia():
    assert R.bandas_de_tinta([0.0] * 30) == []


def test_png_rgb_tiene_firma_dimensiones_y_cierre(tmp_path):
    ruta = tmp_path / "x.png"
    R.escribir_png_rgb(ruta, [b"\xff\x00\x00" * 4, b"\x00\x00\xff" * 4])
    datos = ruta.read_bytes()
    assert datos[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", datos[16:24]) == (4, 2)  # ancho 4, alto 2
    assert datos.endswith(b"IEND\xaeB`\x82")
