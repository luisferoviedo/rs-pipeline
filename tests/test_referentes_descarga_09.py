"""Tests de la descarga de referentes curriculares (referentes_descarga_09; D56).

Sin red: la lectura de la URL se reemplaza por una función que devuelve bytes. Los PDF
de prueba se arman a mano con un número de páginas conocido. Al final, si ya hay
documentos descargados de verdad, se verifican hash, tamaño, cabecera y páginas contra
los archivos que están en el disco.
"""

import hashlib
import io
from datetime import date

import pytest
import yaml

from rs_pipeline import referentes_09 as R
from rs_pipeline import referentes_descarga_09 as D

DOMINIOS = ["oecd.org"]
HOY = date(2026, 11, 4)


def pdf_con_paginas(n: int) -> bytes:
    """PDF mínimo y válido con n páginas en blanco."""
    objetos = ["<< /Type /Catalog /Pages 2 0 R >>"]
    hijos = " ".join(f"{3 + i} 0 R" for i in range(n))
    objetos.append(f"<< /Type /Pages /Kids [{hijos}] /Count {n} >>")
    objetos += ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>"] * n
    salida = b"%PDF-1.4\n"
    posiciones = []
    for i, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{i} 0 obj\n{cuerpo}\nendobj\n".encode()
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for pos in posiciones:
        salida += f"{pos:010d} 00000 n \n".encode()
    trailer = f"<< /Size {len(objetos) + 1} /Root 1 0 R >>"
    salida += f"trailer\n{trailer}\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return salida


def doc(**campos):
    base = {
        "id": "T-1",
        "rol": "marco_evaluacion",
        "pais": "OCDE",
        "organismo": "OECD",
        "titulo": "Documento de prueba",
        "version": R.POR_VERIFICAR,
        "fecha": R.POR_VERIFICAR,
        "acto_de_adopcion": R.POR_VERIFICAR,
        "url_oficial": "https://www.oecd.org/a.pdf",
        "idioma": "en",
        "nivel_cine": [],
        "grados_originales": "n/a",
        "area": "Ciencias",
        "estado": "aprobado",
        "notas": "",
    } | dict.fromkeys(R.CAMPOS_DESCARGA)
    return base | campos


@pytest.fixture
def inventario_en_disco(tmp_path):
    def crear(*documentos):
        ruta = tmp_path / "inv.yaml"
        inv = {"dominios_permitidos": DOMINIOS, "documentos": list(documentos)}
        ruta.write_text(
            "# cabecera de prueba\n" + yaml.safe_dump(inv), encoding="utf-8"
        )
        return ruta

    return crear


# --- Piezas ----------------------------------------------------------------------


def test_verificar_pdf_acepta_pdf_y_rechaza_html():
    D.verificar_pdf(pdf_con_paginas(1), "https://x")
    with pytest.raises(D.ErrorPipeline, match="no empieza con %PDF"):
        D.verificar_pdf(b"<html>Acepte los t\xc3\xa9rminos</html>", "https://x")


def test_paginas_pdf_cuenta_las_paginas(tmp_path):
    for n in (1, 3, 7):
        ruta = tmp_path / f"{n}.pdf"
        ruta.write_bytes(pdf_con_paginas(n))
        assert D.paginas_pdf(ruta) == n


def test_paginas_pdf_falla_con_un_archivo_que_no_es_pdf(tmp_path):
    ruta = tmp_path / "malo.pdf"
    ruta.write_bytes(b"esto no es un pdf")
    with pytest.raises(D.ErrorPipeline, match="pdfinfo no pudo leer"):
        D.paginas_pdf(ruta)


def test_leer_en_bloques_respeta_el_limite():
    assert D.leer_en_bloques(io.BytesIO(b"abc"), 3) == b"abc"
    with pytest.raises(D.ErrorPipeline, match="límite"):
        D.leer_en_bloques(io.BytesIO(b"abcd"), 3)


def test_redireccion_solo_a_dominios_permitidos():
    manejador = D.RedireccionControlada(DOMINIOS)
    peticion = D.Request("https://www.oecd.org/a")
    with pytest.raises(D.ErrorPipeline, match="fuera de la lista"):
        manejador.redirect_request(
            peticion, None, 302, "Found", {}, "https://malo.com/a"
        )
    with pytest.raises(D.ErrorPipeline, match="fuera de la lista"):
        manejador.redirect_request(
            peticion, None, 302, "Found", {}, "http://www.oecd.org/a"
        )
    nueva = manejador.redirect_request(
        peticion, None, 302, "Found", {}, "https://www.oecd.org/b.pdf"
    )
    assert nueva.full_url == "https://www.oecd.org/b.pdf"


def test_leer_url_rechaza_dominios_fuera_de_la_lista():
    with pytest.raises(D.ErrorPipeline, match="fuera de los dominios"):
        D.leer_url("https://malo.com/a.pdf", DOMINIOS)


# --- Descarga de un documento ------------------------------------------------------


def test_descarga_registra_ruta_fecha_tamano_paginas_y_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "RAIZ_REPO", tmp_path)
    contenido = pdf_con_paginas(4)
    d = doc()
    bajo = D.descargar_documento(
        d, DOMINIOS, tmp_path / "raw", lambda url, dominios: contenido, HOY
    )
    ruta = tmp_path / d["ruta_local"]
    assert bajo is True
    assert d["ruta_local"] == "raw/T-1.pdf"
    assert d["fecha_descarga"] == "2026-11-04"
    assert d["tamano_bytes"] == len(contenido) == ruta.stat().st_size
    assert d["paginas"] == 4
    assert d["sha256"] == hashlib.sha256(contenido).hexdigest()
    assert ruta.read_bytes() == contenido


def test_si_no_es_pdf_falla_y_no_deja_archivo(tmp_path):
    d = doc()
    with pytest.raises(D.ErrorPipeline, match="%PDF"):
        D.descargar_documento(
            d, DOMINIOS, tmp_path / "raw", lambda u, dom: b"<html></html>", HOY
        )
    assert not (tmp_path / "raw").exists()
    assert d["sha256"] is None


def test_pdf_ilegible_para_pdfinfo_se_borra(tmp_path):
    d = doc()
    with pytest.raises(D.ErrorPipeline, match="pdfinfo"):
        D.descargar_documento(
            d, DOMINIOS, tmp_path / "raw", lambda u, dom: b"%PDF-1.4 roto", HOY
        )
    assert list((tmp_path / "raw").iterdir()) == []


def test_solo_se_descargan_aprobados(tmp_path):
    with pytest.raises(D.ErrorPipeline, match="solo se descargan"):
        D.descargar_documento(
            doc(estado="por_verificar"), DOMINIOS, tmp_path, lambda u, dom: b"", HOY
        )


def test_no_sobrescribe_un_archivo_existente(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "T-1.pdf").write_bytes(b"otro")
    with pytest.raises(D.ErrorPipeline, match="no se sobrescribe"):
        D.descargar_documento(
            doc(), DOMINIOS, tmp_path / "raw", lambda u, dom: pdf_con_paginas(1), HOY
        )
    assert (tmp_path / "raw" / "T-1.pdf").read_bytes() == b"otro"


def test_documento_ya_descargado_no_se_vuelve_a_bajar(tmp_path):
    llamadas = []

    def leer(url, dominios):
        llamadas.append(url)
        return pdf_con_paginas(1)

    d = doc(sha256="a" * 64)
    assert D.descargar_documento(d, DOMINIOS, tmp_path, leer, HOY) is False
    assert llamadas == []


# --- Corrida completa sobre un inventario en disco ---------------------------------


def test_ejecutar_descarga_solo_aprobados_y_guarda_el_inventario(
    tmp_path, monkeypatch, inventario_en_disco
):
    monkeypatch.setattr(D, "RAIZ_REPO", tmp_path)
    ruta = inventario_en_disco(
        doc(id="A", estado="aprobado"),
        doc(id="B", estado="por_verificar"),
        doc(id="C", estado="referencia"),
    )
    pedidos = []

    def leer(url, dominios):
        pedidos.append(url)
        return pdf_con_paginas(2)

    bajados = D.ejecutar(ruta, tmp_path / "raw", leer=leer, hoy=HOY)
    guardado = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    por_id = {d["id"]: d for d in guardado["documentos"]}
    assert bajados == ["A"]
    assert len(pedidos) == 1
    assert por_id["A"]["paginas"] == 2
    assert por_id["B"]["sha256"] is None
    assert por_id["C"]["sha256"] is None
    assert ruta.read_text(encoding="utf-8").startswith("# cabecera de prueba\n")
    assert D.ejecutar(ruta, tmp_path / "raw", leer=leer, hoy=HOY) == []


def test_ejecutar_con_id_desconocido_falla(tmp_path, inventario_en_disco):
    ruta = inventario_en_disco(doc())
    with pytest.raises(D.ErrorPipeline, match="que no están en el inventario"):
        D.ejecutar(ruta, tmp_path / "raw", ids=["NO-EXISTE"])


def test_main_devuelve_1_si_algo_falla(capsys):
    assert D.main(["--id", "NO-EXISTE"]) == 1
    assert "ERROR" in capsys.readouterr().err


# --- Archivos descargados de verdad (si ya los hay) --------------------------------


def test_los_descargados_reales_coinciden_con_el_inventario():
    inventario = yaml.safe_load(D.INVENTARIO.read_text(encoding="utf-8"))
    bajados = [d for d in inventario["documentos"] if d["sha256"] is not None]
    if not bajados:
        pytest.skip("todavía no se ha descargado ningún documento")
    for d in bajados:
        ruta = D.RAIZ_REPO / d["ruta_local"]
        assert ruta.is_file(), f"{d['id']}: falta {ruta}"
        contenido = ruta.read_bytes()
        assert contenido.startswith(b"%PDF"), d["id"]
        assert len(contenido) == d["tamano_bytes"], d["id"]
        assert hashlib.sha256(contenido).hexdigest() == d["sha256"], d["id"]
        assert D.paginas_pdf(ruta) == d["paginas"], d["id"]


# --- Ingesta manual (PDF que baja Luis Fer a mano) -----------------------------------


def doc_manual(**campos):
    return doc(estado="aprobado_manual", **campos)


def test_el_estado_aprobado_manual_es_valido_y_se_revisa_el_dominio():
    R.validar_inventario(
        {"dominios_permitidos": DOMINIOS, "documentos": [doc_manual()]}
    )
    malo = doc_manual(url_oficial="https://example.com/a.pdf")
    with pytest.raises(R.ErrorPipeline, match="fuera de los dominios"):
        R.validar_inventario({"dominios_permitidos": DOMINIOS, "documentos": [malo]})


def test_la_descarga_automatica_no_toca_los_aprobado_manual(
    tmp_path, inventario_en_disco
):
    ruta = inventario_en_disco(doc_manual())

    pedidos = []

    def leer(url, dominios):
        pedidos.append(url)
        return pdf_con_paginas(1)

    assert D.ejecutar(ruta, tmp_path / "raw", leer=leer, hoy=HOY) == []
    assert pedidos == []


def test_ingesta_manual_registra_igual_que_la_descarga(
    tmp_path, monkeypatch, inventario_en_disco
):
    monkeypatch.setattr(D, "RAIZ_REPO", tmp_path)
    contenido = pdf_con_paginas(5)
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "T-1.pdf").write_bytes(contenido)
    ruta = inventario_en_disco(doc_manual(notas="Se baja a mano."))
    D.ejecutar_ingesta(ruta, tmp_path / "raw", "T-1", hoy=HOY)
    d = yaml.safe_load(ruta.read_text(encoding="utf-8"))["documentos"][0]
    assert d["ruta_local"] == "raw/T-1.pdf"
    assert d["fecha_descarga"] == "2026-11-04"
    assert d["tamano_bytes"] == len(contenido)
    assert d["paginas"] == 5
    assert d["sha256"] == hashlib.sha256(contenido).hexdigest()
    assert d["notas"] == "Se baja a mano. Ingesta manual registrada el 2026-11-04."
    with pytest.raises(D.ErrorPipeline, match="ya está registrado"):
        D.ejecutar_ingesta(ruta, tmp_path / "raw", "T-1", hoy=HOY)


def test_ingesta_manual_con_nombre_de_archivo_propio(
    tmp_path, monkeypatch, inventario_en_disco
):
    monkeypatch.setattr(D, "RAIZ_REPO", tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "PISA_2025.pdf").write_bytes(pdf_con_paginas(2))
    ruta = inventario_en_disco(doc_manual())
    D.ejecutar_ingesta(ruta, tmp_path / "raw", "T-1", "PISA_2025.pdf", HOY)
    d = yaml.safe_load(ruta.read_text(encoding="utf-8"))["documentos"][0]
    assert d["ruta_local"] == "raw/PISA_2025.pdf"
    assert d["paginas"] == 2


@pytest.mark.parametrize(
    ("contenido", "texto"),
    [(None, "no encuentro"), (b"<html></html>", "%PDF"), (b"%PDF-1.4 roto", "pdfinfo")],
)
def test_ingesta_manual_falla_si_falta_o_no_es_pdf_valido(
    tmp_path, monkeypatch, inventario_en_disco, contenido, texto
):
    monkeypatch.setattr(D, "RAIZ_REPO", tmp_path)
    (tmp_path / "raw").mkdir()
    if contenido is not None:
        (tmp_path / "raw" / "T-1.pdf").write_bytes(contenido)
    ruta = inventario_en_disco(doc_manual())
    with pytest.raises(D.ErrorPipeline, match=texto):
        D.ejecutar_ingesta(ruta, tmp_path / "raw", "T-1", hoy=HOY)
    d = yaml.safe_load(ruta.read_text(encoding="utf-8"))["documentos"][0]
    assert d["sha256"] is None


def test_ingesta_manual_solo_para_aprobado_manual_y_dentro_de_la_carpeta(
    tmp_path, inventario_en_disco
):
    (tmp_path / "raw").mkdir()
    ruta = inventario_en_disco(doc(estado="aprobado"))
    with pytest.raises(D.ErrorPipeline, match="solo para documentos aprobado_manual"):
        D.ejecutar_ingesta(ruta, tmp_path / "raw", "T-1", hoy=HOY)
    ruta = inventario_en_disco(doc_manual())
    with pytest.raises(D.ErrorPipeline, match="directamente en"):
        D.ejecutar_ingesta(ruta, tmp_path / "raw", "T-1", "../fuera.pdf", HOY)
