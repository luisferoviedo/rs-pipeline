"""Tests del esquema del inventario de referentes curriculares (referentes_09; D56).

Casos hechos a mano: cada regla se prueba con un documento inventado que la cumple y
otro que la rompe.
"""

import copy

import pytest

from rs_pipeline import referentes_09 as R

DOMINIOS = ["mineducacion.gov.co", "oecd.org", "gob.pe"]


def doc(**campos):
    base = {
        "id": "CO-EBC-2004",
        "rol": "curriculo",
        "pais": "Colombia",
        "organismo": "MEN",
        "titulo": "Documento de prueba",
        "version": R.POR_VERIFICAR,
        "fecha": R.POR_VERIFICAR,
        "acto_de_adopcion": R.POR_VERIFICAR,
        "url_oficial": "https://www.mineducacion.gov.co/archivo.pdf",
        "idioma": "es",
        "nivel_cine": [2, 3],
        "grados_originales": "6.º a 11.º",
        "area": "Ciencias Naturales",
        "estado": "por_verificar",
        "notas": "",
    } | dict.fromkeys(R.CAMPOS_DESCARGA)
    return base | campos


def inventario(*documentos):
    return {"dominios_permitidos": list(DOMINIOS), "documentos": list(documentos)}


def falla(inv, texto):
    with pytest.raises(R.ErrorPipeline, match=texto):
        R.validar_inventario(inv)


def test_inventario_valido_devuelve_los_documentos():
    docs = R.validar_inventario(inventario(doc(), doc(id="OTRO", estado="aprobado")))
    assert [d["id"] for d in docs] == ["CO-EBC-2004", "OTRO"]


def test_campo_que_falta_o_que_sobra():
    sin_area = {k: v for k, v in doc().items() if k != "area"}
    falla(inventario(sin_area), "faltan \\['area'\\]")
    falla(inventario(doc() | {"extra": 1}), "sobran \\['extra'\\]")


def test_ids_repetidos():
    falla(inventario(doc(), doc()), "ids repetidos")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("rol", "otro"), ("estado", "listo"), ("pais", "Chile")],
)
def test_valores_fuera_de_la_lista(campo, valor):
    falla(inventario(doc(**{campo: valor})), campo.replace("pais", "país"))


def test_nivel_cine():
    falla(inventario(doc(nivel_cine=[1])), "nivel_cine")
    falla(inventario(doc(nivel_cine=2)), "nivel_cine")
    falla(inventario(doc(nivel_cine=[])), "nivel CINE")
    R.validar_inventario(
        inventario(doc(rol="contexto_unesco", pais="UNESCO", nivel_cine=[]))
    )


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://www.mineducacion.gov.co/a.pdf", True),
        ("https://mineducacion.gov.co/a.pdf", True),
        ("https://curriculonacional.minedu.gob.pe/a.pdf", True),
        ("http://www.oecd.org/a.pdf", False),
        ("https://oecd.org.malo.com/a.pdf", False),
        ("https://malooecd.org/a.pdf", False),
        ("https://usuario@oecd.org/a.pdf", False),
        ("https://gob.mx/a.pdf", False),
        ("ftp://oecd.org/a.pdf", False),
    ],
)
def test_url_permitida(url, esperado):
    assert R.url_permitida(url, DOMINIOS) is esperado


def test_aprobado_con_dominio_fuera_de_la_lista_falla():
    malo = doc(estado="aprobado", url_oficial="https://example.com/a.pdf")
    falla(inventario(malo), "fuera de los dominios")
    R.validar_inventario(inventario(doc(url_oficial="https://example.com/a.pdf")))


@pytest.mark.parametrize(
    "dominios", [None, [], ["*.gob.ar"], ["gob"], ["a.com", "a.com"]]
)
def test_dominios_invalidos(dominios):
    inv = inventario(doc()) | {"dominios_permitidos": dominios}
    falla(inv, "dominio")


def test_campos_de_descarga():
    lleno = {
        "ruta_local": "data/raw/curriculo/x.pdf",
        "fecha_descarga": "2026-11-04",
        "tamano_bytes": 10,
        "paginas": 2,
        "sha256": "a" * 64,
    }
    R.validar_inventario(inventario(doc(estado="aprobado", **lleno)))
    falla(inventario(doc(estado="aprobado", **(lleno | {"paginas": None}))), "a medias")
    falla(inventario(doc(estado="aprobado", **(lleno | {"sha256": "xyz"}))), "sha256")
    falla(inventario(doc(estado="referencia", **lleno)), "solo se descargan")


def test_el_inventario_no_se_modifica():
    inv = inventario(doc())
    copia = copy.deepcopy(inv)
    R.validar_inventario(inv)
    assert inv == copia
