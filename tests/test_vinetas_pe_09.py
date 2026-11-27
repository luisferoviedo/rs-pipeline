"""Tests de la medición de viñetas de Perú (vinetas_pe_09; D57, D60).

Primero con imágenes y palabras armadas a mano; al final, si el PDF y el OCR están en el
disco, contra las diez páginas reales y contra config/vinetas_pe_pcs_2016.yaml.
"""

from collections import Counter

import pytest
import yaml

from rs_pipeline import vinetas_pe_09 as V
from rs_pipeline.semantico_texto import ErrorPipeline

ANCHO, ALTO = 600, 400


def lienzo(*cajas: tuple[int, int, int, int]) -> list[bytes]:
    """Página blanca con rectángulos negros llenos (x0, y0, x1, y1)."""
    filas = [bytearray(b"\xff" * ANCHO) for _ in range(ALTO)]
    for x0, y0, x1, y1 in cajas:
        for y in range(y0, y1):
            filas[y][x0:x1] = b"\x00" * (x1 - x0)
    return [bytes(f) for f in filas]


def marco(x0=20, y0=20, x1=580, y1=380) -> list[tuple[int, int, int, int]]:
    return [
        (x0, y0, x1, y0 + 2),
        (x0, y1 - 2, x1, y1),
        (x0, y0, x0 + 2, y1),
        (x1 - 2, y0, x1, y1),
    ]


def punto(x: int, y: int) -> tuple[int, int, int, int]:
    return (x, y, x + 16, y + 16)


def palabra(texto: str, x: int, y: int) -> V.Palabra:
    return V.Palabra(texto, x, y, x + 60, y + 20)


def palabras(verbo="Explica", grado="QUINTO") -> list[V.Palabra]:
    return [
        palabra("DESEMPEÑOS", 100, 40),
        palabra(grado, 200, 40),
        palabra("siguientes:", 100, 80),
        V.Palabra("e", 40, 148, 56, 166),  # la viñeta leída como letra
        palabra(verbo, 80, 148),
        palabra("Describe", 80, 248),
    ]


def imagen(*extra) -> list[bytes]:
    return lienzo(*marco(), punto(40, 150), punto(40, 250), *extra)


def test_componentes_junta_lo_que_se_toca():
    cajas = V.componentes(lienzo((10, 10, 20, 20), (20, 20, 30, 30), (50, 50, 60, 60)))
    assert sorted((c.x0, c.y0, c.x1, c.y1, c.pixeles) for c in cajas) == [
        (10, 10, 30, 30, 200),
        (50, 50, 60, 60, 100),
    ]


@pytest.mark.parametrize(
    ("caja", "redondo"),
    [
        (V.Caja(0, 0, 16, 16, 200), True),
        (V.Caja(0, 0, 8, 8, 60), False),  # un punto de puntuación
        (V.Caja(0, 0, 16, 30, 400), False),  # una letra alta
        (V.Caja(0, 0, 18, 12, 200), False),  # ancho y alto distintos
        (V.Caja(0, 0, 16, 16, 100), False),  # hueco, como una «o»
    ],
)
def test_punto_redondo(caja, redondo):
    assert V.es_punto_redondo(caja) is redondo


def test_mide_las_vinetas_de_la_zona():
    # el punto de arriba (capacidades) queda fuera de la zona
    m = V.medir_pagina(imagen(punto(40, 60)), palabras(), 183)
    [c] = m["columnas"]
    assert m["tabla"] == [20, 20, 580, 380]
    assert (c["grado"], c["y_superior"], c["y_inferior"]) == (5, 100, 380)
    assert c["vinetas"] == [[40, 150, 56, 166], [40, 250, 56, 266]]


@pytest.mark.parametrize(
    ("filas", "texto", "mensaje"),
    [
        (imagen(punto(300, 200)), palabras(), "fuera del carril"),
        (imagen(punto(40, 320)), palabras(), "no tiene texto a su derecha"),
        (imagen(), palabras(verbo="Cuando"), "empieza por 'Cuando'"),
        (imagen(), palabras(grado="CUARTO"), "no el grado 5"),
        (imagen(), palabras()[:2] + palabras()[3:], "siguientes"),
        (lienzo(*marco()), palabras(), "no tiene viñetas"),
        (lienzo(punto(40, 150)), palabras(), "marco de la tabla"),
    ],
)
def test_pagina_distinta_de_la_esperada_falla(filas, texto, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        V.medir_pagina(filas, texto, 183)


def test_continuacion_empieza_arriba_de_la_tabla():
    filas = lienzo(*marco(), punto(40, 150), punto(320, 150))
    texto = [palabra("Explica", 80, 148), palabra("Justifica", 360, 148)]
    m = V.medir_pagina(filas, texto, 187)
    assert [c["y_superior"] for c in m["columnas"]] == [20, 20]
    assert [len(c["vinetas"]) for c in m["columnas"]] == [1, 1]
    with pytest.raises(ErrorPipeline, match="continuación"):
        V.medir_pagina(filas, [*texto, palabra("siguientes:", 80, 40)], 187)


def test_ocr_de_otro_pdf_falla():
    with pytest.raises(ErrorPipeline, match="otro PDF"):
        V.fichas_del_ocr("0" * 64)


# --- Contra las páginas reales y el YAML congelado ---------------------------


@pytest.fixture(scope="module")
def real():
    inventario = V.RAIZ_REPO / "data" / "raw" / "curriculo" / "PE-PCS-2016.pdf"
    faltan = [n for n in V.PAGINAS if not (V.DESTINO / f"p{n}.tsv").is_file()]
    if not inventario.is_file() or faltan:
        pytest.skip("faltan el PDF de Perú o las salidas del OCR en data/")
    pdf, hash_pdf = V.pdf_del_inventario()
    medidas, _ = V.medir_todo(pdf, hash_pdf)
    return hash_pdf, medidas


def test_yaml_congelado_coincide_con_la_medicion(real):
    hash_pdf, medidas = real
    config = yaml.safe_load(V.CONFIG.read_text(encoding="utf-8"))
    assert config["entrada"]["sha256"] == hash_pdf
    assert config["ocr"]["sha256"] == V.sha256_de(V.OCR_JSON)
    assert [f["pagina"] for f in config["paginas"]] == list(V.PAGINAS)
    for fila, m in zip(config["paginas"], medidas, strict=True):
        assert {k: fila[k] for k in m} == m


def test_vinetas_reales_por_competencia_y_grado(real):
    _, medidas = real
    conteo = V.conteo_por_grado(medidas)
    assert conteo == {
        "indaga": [5, 5, 5, 5, 5],
        "explica": [12, 15, 12, 10, 13],
        "disena": [4, 4, 4, 4, 4],
    }
    assert sum(map(sum, conteo.values())) == 107
    # ninguna viñeta repetida
    cajas = Counter(
        (m["pagina"], *v) for m in medidas for c in m["columnas"] for v in c["vinetas"]
    )
    assert len(cajas) == 107
