"""Tests de la medición de recortes de los EBC 2004 (recortes_ebc_09; D60).

Primero con una página armada a mano (la 18: dos globos y dos columnas); al final, si el
PDF está en el disco, contra el documento y contra config/recortes_ebc_2004.yaml.
"""

import pytest
import yaml

from rs_pipeline import recortes_ebc_09 as R
from rs_pipeline.semantico_texto import ErrorPipeline


def frase(texto: str, x: float, y: float, alto: float = 8.6) -> list:
    """Palabras de 20 pt de ancho, una cada 25 pt."""
    return [
        R.Palabra(w, x + 25 * k, y, x + 25 * k + 20, y + alto)
        for k, w in enumerate(texto.split())
    ]


def pagina(*extra) -> list:
    return [
        *frase("Al final de séptimo", 100, 52),
        *frase("Un estándar general.", 330, 52),
        *frase("Para lograrlo...", 50, 145),
        *frase("como científico-a natural", 100, 175),
        *frase("Entorno vivo", 400, 180),
        *frase("•Observo cosas varias.", 54, 201),  # hasta x = 124
        *frase("y más cosas.", 60, 212),
        *frase("•Registro todo.", 54, 230),
        *frase("•Explico la célula.", 385, 201),
        *frase("18", 283, 701, alto=17),
        *extra,
    ]


def test_recortes_de_las_columnas_y_de_los_globos():
    [m] = R.medir({18: pagina()})
    a, b = m["columnas"]
    # columnas: texto 54-130 y 385-455; encabezado hasta 183,6 / 188,6; viñetas en 201
    assert (a["x_izquierda"], a["x_derecha"], b["x_derecha"]) == (51, 258, 458)
    assert (a["y_superior"], b["y_superior"], a["y_inferior"]) == (192, 195, 240)
    assert [c["vinetas"] for c in m["columnas"]] == [2, 1]
    assert [g["tipo"] for g in m["contexto"]] == ["introduccion", "estandar_general"]


@pytest.mark.parametrize(
    ("extra", "mensaje"),
    [
        (frase("•Otra columna.", 200, 201), "se esperaban 2 columnas"),
        (frase("suelto", 5, 300), "fuera de las columnas"),
        (frase("pegado", 385, 189), "encabezado en p18"),
        (frase("bajo", 60, 702), "llega hasta el pie"),
        (frase("larguísima", 360, 220), "hueco de columnas"),
        (frase("Sobra otro globo.", 500, 52), "se esperaban 2"),
    ],
)
def test_pagina_distinta_de_la_esperada_falla(extra, mensaje):
    if mensaje == "hueco de columnas":
        extra = [R.Palabra("larguísima", 90, 220, 382, 228.6)]
    with pytest.raises(ErrorPipeline, match=mensaje):
        R.medir({18: pagina(*extra)})


@pytest.mark.parametrize(
    ("viejo", "nuevo", "mensaje"),
    [
        ("séptimo", "noveno", "no nombra el grado séptimo"),
        ("general.", "general", "no termina en punto"),
        ("vivo", "físico", "sin 'Entorno vivo'"),
        ("lograrlo...", "lograrlo", "lograrlo"),
        ("18", "19", "pie"),
    ],
)
def test_texto_distinto_del_esperado_falla(viejo, nuevo, mensaje):
    palabras = [p._replace(texto=nuevo) if p.texto == viejo else p for p in pagina()]
    with pytest.raises(ErrorPipeline, match=mensaje):
        R.medir({18: palabras})


def test_el_criterio_usa_el_centro_de_la_palabra():
    recorte = {"x_izquierda": 0, "x_derecha": 100, "y_superior": 10, "y_inferior": 680}
    monta = R.Palabra("Tierra.", 10, 670, 40, 678.6)
    rotulo = R.Palabra("CIENCIAS", 10, 676.6, 90, 718.2)  # centro en 697,4
    assert R.dentro(monta, recorte)
    assert not R.dentro(rotulo, recorte)
    assert not R.dentro(R.Palabra("cruza", 90, 300, 110, 308), recorte)


# --- Contra el PDF real y el YAML congelado ----------------------------------


@pytest.fixture(scope="module")
def real():
    doc = R.documento_del_inventario(R.ID_EBC)
    if not (R.RAIZ_REPO / doc["ruta_local"]).is_file():
        pytest.skip("el PDF de los EBC no está en data/raw/curriculo/")
    _, paginas = R.leer_paginas(R.pdf_verificado(doc))
    return doc, paginas, R.medir(paginas)


def test_yaml_congelado_coincide_con_la_medicion(real):
    doc, _, medidas = real
    config = yaml.safe_load(R.CONFIG.read_text(encoding="utf-8"))
    assert config["entrada"]["sha256"] == doc["sha256"]
    assert [f["pagina"] for f in config["paginas"]] == list(range(18, 24))
    for fila, m in zip(config["paginas"], medidas, strict=True):
        assert {k: fila[k] for k in m} == m


def test_vinetas_reales_por_grupo_y_columna(real):
    _, paginas, medidas = real
    conteo = R.conteo_por_grupo(medidas)
    orden = (R.APROXIMO, R.VIVO, R.FISICO, R.CTS, R.COMPROMISOS)
    assert {g: [c[k] for k in orden] for g, c in conteo.items()} == {
        "6-7": [22, 16, 16, 13, 11],
        "8-9": [21, 15, 12, 15, 12],
        "10-11": [19, 12, 24, 11, 12],  # físico: 13 químicos y 11 físicos
    }
    assert [sum(c.values()) for c in conteo.values()] == [78, 75, 78]
    # el mismo total contado sin usar los recortes
    assert sum(p.texto.count("•") for pal in paginas.values() for p in pal) == 231


def test_cada_palabra_real_queda_en_un_solo_sitio(real):
    _, paginas, medidas = real
    for m in medidas:
        palabras = paginas[m["pagina"]]
        partes = R.separar(palabras, m["pagina"])
        recortes = [*m["columnas"], *m["contexto"]]
        veces = {p: sum(R.dentro(p, r) for r in recortes) for p in palabras}
        assert set(veces.values()) <= {0, 1}
        # lo que queda fuera de todo recorte es solo pie o encabezado
        fuera = [p for p, v in veces.items() if v == 0]
        arriba = max(c["y_superior"] for c in m["columnas"])
        assert all(p in partes["pie"] or partes["ancla"].y0 <= p.y0 < arriba
                   for p in fuera)  # fmt: skip
        assert not [p for p in fuera if p.texto.startswith("•")]


def test_cada_columna_real_empieza_en_vineta(real):
    _, paginas, medidas = real
    for m in medidas:
        for c in m["columnas"]:
            texto = R.en_orden([p for p in paginas[m["pagina"]] if R.dentro(p, c)])
            assert texto.startswith("•"), (m["pagina"], c["columna"])
            assert texto.endswith("."), (m["pagina"], c["columna"])
    # 3 estándares generales en 6.º-7.º, 4 en 8.º-9.º y 5 en 10.º-11.º
    estandares = [
        sum(g["tipo"] == "estandar_general" for g in m["contexto"]) for m in medidas
    ]
    assert estandares == [1, 2, 1, 3, 2, 3]
