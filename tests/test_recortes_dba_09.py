"""Tests de la medición de recortes de los DBA (recortes_dba_09; D60).

Primero con páginas armadas a mano; al final, si el PDF está en el disco, contra el
documento real y contra los valores congelados en config/recortes_dba_cn.yaml.
"""

import pytest
import yaml

from rs_pipeline import recortes_dba_09 as R
from rs_pipeline.semantico_texto import ErrorPipeline


def P(texto: str, x0: float, y0: float, x1: float = 0, alto: float = 12):
    return R.Palabra(texto, x0, y0, x1 or x0 + 30, y0 + alto)


def pagina(*extra) -> list:
    """Encabezado (hasta y = 105), un DBA en la columna izquierda, pie en y = 787."""
    return [
        P("Derechos", 160, 82, alto=23),
        P("V.1", 473, 87, alto=16),
        P("1.", 64, 162, 86, alto=31),
        P("Evidencias", 67, 220, 121),
        P("q", 87, 250, 94),
        P("texto", 98, 250, 317),
        P("Ejemplo", 67, 300, 110),
        P("columna", 337, 162, 586),
        P("21", 550, 787, 560),
        P("CienciasNaturales", 31, 823),
        P("21", 128, 823, 134),  # la marca de InDesign repite el número de página
        *extra,
    ]


def test_los_recortes_quedan_en_la_mitad_de_cada_hueco():
    cortes, medidas, _ = R.medir({21: pagina()})
    # columnas 317-337; encabezado 105 y texto 162; texto 312 y pie 787
    assert cortes == {"x_columnas": 327, "y_superior": 134, "y_inferior": 550}
    assert medidas[0]["fin_izquierda_x"] == 317
    assert medidas[0]["inicio_derecha_x"] == 337


def test_pagina_sin_columna_derecha_queda_sin_medida():
    sola = [p for p in pagina() if p.texto != "columna"]
    segunda = [p._replace(texto="22") if p.texto == "21" else p for p in sola]
    _, medidas, _ = R.medir({21: pagina(), 22: segunda})
    assert medidas[1]["inicio_derecha_x"] is None


def test_palabra_que_cruza_las_columnas_falla():
    with pytest.raises(ErrorPipeline, match="2 columnas"):
        R.medir({21: pagina(P("cruzada", 300, 400, 360))})


def test_texto_pegado_al_pie_falla():
    with pytest.raises(ErrorPipeline, match="hueco de pie"):
        R.medir({21: pagina(P("baja", 98, 772, 130))})


@pytest.mark.parametrize("falta", ["V.1", "21", "CienciasNaturales"])
def test_pagina_sin_ancla_falla(falta):
    with pytest.raises(ErrorPipeline, match="p21"):
        R.medir({21: [p for p in pagina() if p.texto != falta]})


def test_orden_de_lectura_izquierda_y_luego_derecha():
    # DBA 2: el enunciado queda abajo a la izquierda y sus evidencias a la derecha
    p = pagina(
        P("2.", 64, 600, 86, alto=31),
        P("Evidencias", 338, 200, 395),
        P("q", 358, 230, 365),
        P("q", 358, 260, 365),
        P("Ejemplo", 338, 290, 380),
    )
    assert R.controlar_orden({21: R.separar(p, 21)[1]}, 327) == [[1, 2]]


def test_orden_roto_falla():
    p = pagina(P("q", 87, 350, 94))  # una viñeta después de «Ejemplo»
    with pytest.raises(ErrorPipeline, match="orden de lectura"):
        R.controlar_orden({21: R.separar(p, 21)[1]}, 327)


def test_numeracion_con_salto_falla():
    p = pagina(
        P("3.", 64, 400, 86, alto=31),
        P("Evidencias", 67, 450, 121),
        P("q", 87, 480, 94),
        P("Ejemplo", 67, 510, 110),
    )
    with pytest.raises(ErrorPipeline, match="no consecutiva"):
        R.controlar_orden({21: R.separar(p, 21)[1]}, 327)


# --- Contra el PDF real y el YAML congelado ----------------------------------


@pytest.fixture(scope="module")
def real():
    doc = R.documento_del_inventario(R.ID_DBA)
    if not (R.RAIZ_REPO / doc["ruta_local"]).is_file():
        pytest.skip("el PDF de los DBA no está en data/raw/curriculo/")
    pdf = R.pdf_verificado(doc)
    orden = ["pdftotext", "-bbox", "-f", "21", "-l", "39", str(pdf), "-"]
    leidas = R.paginas_con_cajas(R.ejecutar(orden).stdout)
    paginas = {n: pal for n, (_, pal) in zip(R.PAGINAS, leidas, strict=True)}
    return doc, paginas, R.medir(paginas)


def test_yaml_congelado_coincide_con_la_medicion(real):
    doc, _, (cortes, medidas, _) = real
    config = yaml.safe_load(R.CONFIG.read_text(encoding="utf-8"))
    assert config["entrada"]["sha256"] == doc["sha256"]
    assert [f["pagina"] for f in config["paginas"]] == list(range(21, 40))
    for fila, m in zip(config["paginas"], medidas, strict=True):
        assert {k: fila[k] for k in cortes} == cortes
        assert {"pagina": fila["pagina"], **fila["medido"]} == m


def test_recortes_reales_no_tocan_ninguna_palabra(real):
    _, paginas, (cortes, _, textos) = real
    x, y0, y1 = (cortes[k] for k in ("x_columnas", "y_superior", "y_inferior"))
    assert (x, y0, y1) == (327, 132, 778)
    for n, palabras in paginas.items():
        assert all(p.y1 < y0 or p.y0 > y1 or (p.y0 > y0 and p.y1 < y1)
                   for p in palabras)  # fmt: skip
        dentro = [p for p in palabras if y0 < p.y0 and p.y1 < y1]
        assert dentro == textos[n]  # el recorte deja justo el texto
        assert all(p.x1 < x or p.x0 > x for p in dentro)


def test_conteos_reales(real):
    _, paginas, (cortes, _, textos) = real
    grupos = R.controlar_orden(textos, cortes["x_columnas"])
    assert [len(g) for g in grupos] == [5, 4, 5, 6, 4, 5]  # grados 6.º a 11.º
    assert sum(map(sum, grupos)) == 99
    # el mismo total de viñetas contado sin usar los recortes
    assert sum(p.texto == "q" for pal in paginas.values() for p in pal) == 99
