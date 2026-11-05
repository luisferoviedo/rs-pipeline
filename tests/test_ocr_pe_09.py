"""Tests del OCR de Perú (ocr_pe_09; D57). No corren Tesseract ni pdftoppm.

Se prueban las partes puras: el cálculo del recorte, la confianza leída de un TSV
pequeño hecho a mano, el rechazo de páginas fuera de 177–194 y la falla cuando el hash
del PDF no coincide con el del inventario.
"""

import sys

import pytest
import yaml

from rs_pipeline import ocr_pe_09 as O
from rs_pipeline.semantico_texto import ErrorPipeline

COLUMNAS = "level page_num block_num par_num line_num word_num left top width height"
ENCABEZADO = "\t".join((COLUMNAS + " conf text").split()) + "\n"


def fila(nivel: str, conf: str, texto: str) -> str:
    return f"{nivel}\t1\t1\t1\t1\t1\t0\t0\t10\t10\t{conf}\t{texto}\n"


def test_recorte_en_pixeles_a_72_dpi():
    # 600 x 800 pts a 72 dpi = 600 x 800 px; arriba 9 % = 72 px; abajo 90,5 % = 724 px.
    r = O.recorte_en_pixeles(600, 800, 72, 0.09)
    assert r == {
        "x": 0,
        "y": 72,
        "ancho": 600,
        "alto": 652,
        "pagina_ancho": 600,
        "pagina_alto": 800,
    }


def test_recorte_en_pixeles_a_300_dpi():
    # 600 x 800 pts a 300 dpi = 2500 x 3333 px; y0 = 300, y1 = 3016.
    r = O.recorte_en_pixeles(600, 800, 300, 0.09)
    assert (r["pagina_ancho"], r["pagina_alto"]) == (2500, 3333)
    assert (r["y"], r["alto"]) == (300, 3016 - 300)


def test_confianza_ignora_conf_negativa_y_texto_vacio(tmp_path):
    tsv = tmp_path / "p.tsv"
    tsv.write_text(
        ENCABEZADO
        + fila("1", "-1", "")  # página: no es palabra
        + fila("4", "-1", "")  # línea
        + fila("5", "90", "hola")
        + fila("5", "70", "mundo")
        + fila("5", "-1", "basura")  # conf -1: se ignora
        + fila("5", "95", " ")  # texto vacío: se ignora
        + fila("5", "50", "dudosa"),
        encoding="utf-8",
    )
    r = O.confianza_de_tsv(tsv)
    assert r["palabras"] == 3
    assert r["confianza_media"] == 70.0  # (90 + 70 + 50) / 3
    assert r["palabras_confianza_baja"] == 1  # solo la de 50 (< 60)


def test_confianza_falla_si_no_hay_palabras(tmp_path):
    tsv = tmp_path / "vacio.tsv"
    tsv.write_text(ENCABEZADO + fila("5", "-1", ""), encoding="utf-8")
    with pytest.raises(ErrorPipeline):
        O.confianza_de_tsv(tsv)


@pytest.mark.parametrize("pagina", ["176", "195", "1"])
def test_rechaza_paginas_fuera_de_177_194(monkeypatch, pagina):
    monkeypatch.setattr(sys, "argv", ["ocr_pe_09", "--paginas", "182", pagina])
    with pytest.raises(ErrorPipeline, match="fuera de 177–194"):
        O.main()


def test_falla_si_el_sha256_del_pdf_no_coincide(tmp_path, monkeypatch):
    pdf = tmp_path / "PE-PCS-2016.pdf"
    pdf.write_bytes(b"%PDF-1.4 contenido de prueba")
    inventario = tmp_path / "inventario.yaml"
    inventario.write_text(
        yaml.safe_dump(
            {
                "documentos": [
                    {"id": O.ID_REFERENTE, "ruta_local": pdf.name, "sha256": "0" * 64}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(O, "RAIZ_REPO", tmp_path)
    monkeypatch.setattr(O, "INVENTARIO", inventario)
    with pytest.raises(ErrorPipeline, match="distinto del inventario"):
        O.pdf_del_inventario()


def test_acepta_el_pdf_si_el_sha256_coincide(tmp_path, monkeypatch):
    pdf = tmp_path / "PE-PCS-2016.pdf"
    pdf.write_bytes(b"%PDF-1.4 contenido de prueba")
    hash_ok = O.sha256_de(pdf)
    inventario = tmp_path / "inventario.yaml"
    inventario.write_text(
        yaml.safe_dump(
            {
                "documentos": [
                    {"id": O.ID_REFERENTE, "ruta_local": pdf.name, "sha256": hash_ok}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(O, "RAIZ_REPO", tmp_path)
    monkeypatch.setattr(O, "INVENTARIO", inventario)
    assert O.pdf_del_inventario() == (pdf, hash_ok)


def test_zona_sello_solo_franja_inferior_izquierda(tmp_path):
    # Imagen de 1000 x 1000: la franja es top >= 850 y la mitad izquierda, left < 500.
    def palabra(b, par, lin, left, top, conf, texto):
        return f"5\t1\t{b}\t{par}\t{lin}\t1\t{left}\t{top}\t10\t10\t{conf}\t{texto}\n"

    tsv = tmp_path / "p.tsv"
    tsv.write_text(
        ENCABEZADO
        + palabra(1, 1, 1, 100, 100, 99, "arriba")  # fuera: no está en la franja
        + palabra(2, 1, 1, 100, 900, 80, "sello")  # dentro
        + palabra(2, 1, 1, 200, 900, 60, "dañado")  # misma línea
        + palabra(3, 1, 1, 600, 900, 95, "derecha"),  # fuera: mitad derecha
        encoding="utf-8",
    )
    zona = O.zona_sello(tsv, 1000, 1000)
    assert len(zona) == 1
    assert zona[0]["texto"] == "sello dañado"
    assert zona[0]["palabras"] == 2
    assert zona[0]["confianza_media"] == 70.0


def config_de_recortes(tmp_path, monkeypatch, filas):
    ruta = tmp_path / "recortes.yaml"
    ruta.write_text(yaml.safe_dump({"paginas": filas}), encoding="utf-8")
    monkeypatch.setattr(O, "RECORTES", ruta)
    monkeypatch.setattr(O, "RAIZ_REPO", tmp_path)


def fila_recorte(pagina, verificado_por="Luis Fer", fraccion=0.05):
    return {
        "pagina": pagina,
        "recorte_superior": fraccion,
        "verificado_por": verificado_por,
    }


def test_recortes_devuelve_el_valor_verificado_de_cada_pagina(tmp_path, monkeypatch):
    config_de_recortes(
        tmp_path, monkeypatch, [fila_recorte(177, fraccion=0.081), fila_recorte(178)]
    )
    assert O.cargar_recortes([178, 177]) == {178: 0.05, 177: 0.081}


def test_recortes_falla_si_falta_la_pagina(tmp_path, monkeypatch):
    config_de_recortes(tmp_path, monkeypatch, [fila_recorte(177)])
    with pytest.raises(ErrorPipeline, match="p178: no hay recorte"):
        O.cargar_recortes([177, 178])


@pytest.mark.parametrize("verificado_por", ["", "   ", None])
def test_recortes_falla_si_falta_la_verificacion(tmp_path, monkeypatch, verificado_por):
    config_de_recortes(
        tmp_path, monkeypatch, [fila_recorte(177), fila_recorte(178, verificado_por)]
    )
    with pytest.raises(ErrorPipeline, match="p178: recorte sin verificar"):
        O.cargar_recortes([177, 178])


def test_recortes_falla_si_la_pagina_esta_repetida(tmp_path, monkeypatch):
    config_de_recortes(tmp_path, monkeypatch, [fila_recorte(177), fila_recorte(177)])
    with pytest.raises(ErrorPipeline, match="aparece dos veces"):
        O.cargar_recortes([177])


def test_recortes_falla_si_no_existe_el_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "RECORTES", tmp_path / "no_existe.yaml")
    monkeypatch.setattr(O, "RAIZ_REPO", tmp_path)
    with pytest.raises(ErrorPipeline, match="no existe"):
        O.cargar_recortes([177])


def test_control_encabezado_acepta_un_texto_limpio():
    texto = "Estándares de aprendizaje de la competencia\nDiseña y construye"
    assert O.controlar_encabezado(191, texto, ["Estándares", "de"]) == []


@pytest.mark.parametrize(
    "texto",
    ["649-2016-MINEDU\nCompetencia", "algo\n6 4 9 - 2016 . M I N E D U", "x 649-2016"],
)
def test_control_encabezado_detecta_restos_del_encabezado(texto):
    assert O.controlar_encabezado(180, texto, []) != []


def test_control_encabezado_detecta_token_con_minedu():
    problemas = O.controlar_encabezado(180, "texto limpio", ["xMINEDUx"])
    assert len(problemas) == 1
    assert "token con MINEDU" in problemas[0]


def test_control_encabezado_exige_la_primera_linea_en_p191():
    bien = O.controlar_encabezado(191, "\n\nEstándares de aprendizaje", [])
    mal = O.controlar_encabezado(191, "Nivel...\nEstándares", [])
    assert bien == []
    assert len(mal) == 1
    assert "debe empezar por «Estándares»" in mal[0]


def test_control_encabezado_no_exige_primera_linea_en_otras_paginas():
    assert O.controlar_encabezado(180, "Cualquier cosa", []) == []


def test_sufijo_no_valido_falla(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["ocr_pe_09", "--paginas", "182", "--sufijo", "../x"]
    )
    with pytest.raises(ErrorPipeline, match="sufijo no válido"):
        O.main()
