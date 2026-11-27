"""Tests de la extracción de enunciados del ICFES y de PISA (extraccion_09; D60).

Primero con textos armados a mano (columnas de la tabla del ICFES con sus coordenadas y
un recuadro de PISA con -layout), para fijar cada regla. Al final, si los PDF están en
el disco, se verifica contra los documentos: 9 afirmaciones y 43 evidencias del ICFES;
6, 4 y 5 descriptores de PISA; y que el texto extraído sea el mismo que se lee por otra
vía (columnas recortadas por pdftotext y modo -raw), sin nada de más ni de menos.
"""

import json

import pytest

from rs_pipeline import extraccion_09 as X
from rs_pipeline.semantico_texto import ErrorPipeline


def palabra(texto: str, x: float, y: float) -> str:
    return f'<word xMin="{x}" yMin="{y}" xMax="{x + 30}" yMax="{y + 10}">{texto}</word>'


def pagina(*lineas: tuple[float, float, str]) -> str:
    """Una página con encabezado de tabla (y = 150) y las líneas (x, y, texto) dadas."""
    ws = [
        palabra("Competencia", 92, 150),
        palabra("Afirmación", 233, 150),
        palabra("Evidencia", 417, 150),
    ]
    for x, y, texto in lineas:
        for k, w in enumerate(texto.split()):
            ws.append(palabra(w, x + 40 * k, y))
    ws.append(palabra("Continúa", 400, 710))  # pie: se descarta
    return '<page width="595" height="765">' + "".join(ws) + "</page>"


def tabla_minima(evidencias_afirm_2=("2.1", "2.2")) -> str:
    """Dos páginas: el rótulo de la 2.ª competencia está en la segunda página."""
    p1 = pagina(
        (92, 200, "Explicación"),
        (92, 215, "de fenómenos"),
        (185, 200, "1. Analizar el"),
        (190, 215, "potencial del uso."),
        (349, 200, "1.1 Explica algunos"),
        (355, 215, "principios de salud."),
        (349, 260, "1.2 Explica cómo la"),
        (355, 275, "explotación de un re-"),
        (355, 290, "curso tiene efectos."),
    )
    lineas = [(92, 200, "Indagación"), (185, 200, "2. Comprender la pregunta.")]
    lineas += [
        (349, 200 + 40 * i, f"{e} Analiza qué tipo de pregunta.")
        for i, e in enumerate(evidencias_afirm_2)
    ]
    return p1 + pagina(*lineas)


ESTRUCTURA_MINIMA = {
    "Explicación de fenómenos": {"1": 2},
    "Indagación": {"2": 2},
}


def test_icfes_columnas_rotulos_y_continuaciones():
    evid, afirm = X.extraer_icfes_sin_validar(tabla_minima(), 38)
    assert afirm == {
        "1": "Analizar el potencial del uso.",
        "2": "Comprender la pregunta.",
    }
    assert [e["id"] for e in evid] == ["1.1", "1.2", "2.1", "2.2"]
    assert evid[0]["competencia"] == "Explicación de fenómenos"
    assert evid[2]["competencia"] == "Indagación"
    assert evid[2]["pagina"] == 39
    # continuación en dos líneas y guion de corte reparado; el pie no entra
    assert (
        evid[1]["texto"] == "Explica cómo la explotación de un recurso tiene efectos."
    )
    assert all("Continúa" not in e["texto"] for e in evid)


def test_icfes_aviso_de_continuacion_no_entra():
    # en los PDF el aviso queda a veces por encima de Y_PIE (p. ej. y = 667 en la 40)
    p = pagina(
        (92, 200, "Indagación"),
        (185, 200, "1. Comprender la pregunta."),
        (349, 200, "1.1 Analiza qué tipo de pregunta."),
        (400, 667, "Continúa en la siguiente página"),
    )
    evid, _ = X.extraer_icfes_sin_validar(p, 38)
    assert evid[0]["texto"] == "Analiza qué tipo de pregunta."


def test_icfes_evidencias_no_consecutivas_fallan(monkeypatch):
    monkeypatch.setattr(X, "ESTRUCTURA_ICFES", ESTRUCTURA_MINIMA)
    X.extraer_icfes(tabla_minima(), 38)  # la tabla buena pasa
    with pytest.raises(ErrorPipeline, match="no consecutivas"):
        X.extraer_icfes(tabla_minima(("2.1", "2.3")), 38)


def test_icfes_conteo_de_afirmaciones_distinto_falla():
    with pytest.raises(ErrorPipeline, match="afirmaciones"):
        X.extraer_icfes(tabla_minima(), 38)  # esperadas 9, hay 2


def test_icfes_falta_la_ultima_evidencia_falla(monkeypatch):
    # 2.1 sola sigue siendo «consecutiva»: solo el conteo esperado lo detecta
    monkeypatch.setattr(X, "ESTRUCTURA_ICFES", ESTRUCTURA_MINIMA)
    with pytest.raises(ErrorPipeline, match="distintas de las esperadas"):
        X.extraer_icfes(tabla_minima(("2.1",)), 38)


def test_icfes_texto_con_algo_pegado_falla(monkeypatch):
    monkeypatch.setattr(X, "ESTRUCTURA_ICFES", {"Indagación": {"1": 1}})
    p = pagina(
        (92, 200, "Indagación"),
        (185, 200, "1. Comprender la pregunta."),
        (349, 200, "1.1 Analiza qué tipo de pregunta."),
        (349, 600, "Ciencias naturales 43"),
    )
    with pytest.raises(ErrorPipeline, match="algo pegado"):
        X.extraer_icfes(p, 38)


def test_icfes_afirmacion_repetida_falla():
    p = pagina(
        (92, 200, "Indagación"),
        (185, 200, "1. Una afirmación."),
        (185, 260, "1. Otra afirmación."),
        (349, 200, "1.1 Una evidencia cualquiera."),
    )
    with pytest.raises(ErrorPipeline, match="repetida"):
        X.extraer_icfes_sin_validar(p, 38)


def test_icfes_afirmacion_sin_competencia_falla():
    p = pagina((185, 200, "1. Una afirmación."), (349, 200, "1.1 Una evidencia."))
    with pytest.raises(ErrorPipeline, match="rótulo de competencia"):
        X.extraer_icfes_sin_validar(p, 38)


def test_icfes_palabra_ilegible_en_el_bbox_falla():
    p = pagina().replace('xMin="92"', 'xMin="-92"')
    with pytest.raises(ErrorPipeline, match="no se pudieron leer"):
        X.extraer_icfes_sin_validar(p, 38)


def test_icfes_texto_sin_numero_que_lo_abra_falla():
    p = pagina((349, 200, "texto suelto sin número"))
    with pytest.raises(ErrorPipeline, match="sin número"):
        X.extraer_icfes_sin_validar(p, 38)


RECUADROS = """\
 Box 2.3. PISA 2025 Science Competency 1
 Explain phenomena scientifically
 Produce and evaluate explanations demonstrating the ability to:
         •    Recall and apply appropriate scientific knowledge
         •    Use different forms of representations and translate between these
              forms
The text after the box is a normal paragraph.
 Box 2.4. PISA 2025 Science Competency 2
 Construct and evaluate designs
 Construct and evaluate scientific investigations demonstrating the ability to:
         •    Identify the question in a given scientific study

 Box 2.5. PISA 2025 Science Competency 3
 Research, evaluate and use scientific information
 Research and evaluate demonstrating the ability to:
         •    Search and evaluate sources
         •    Justify decisions
"""


def test_pisa_vinetas_continuacion_y_fin_de_recuadro(monkeypatch):
    monkeypatch.setattr(X, "DESCRIPTORES_PISA", {1: 2, 2: 1, 3: 2})
    u = X.extraer_pisa(RECUADROS.replace(" Box 2.5", "\f Box 2.5"), 34)
    assert [d["pagina"] for d in u] == [34, 34, 34, 35, 35]
    assert [(d["competencia"], d["n"]) for d in u] == [
        (1, 1),
        (1, 2),
        (2, 1),
        (3, 1),
        (3, 2),
    ]
    assert (
        u[1]["texto"]
        == "Use different forms of representations and translate between these forms"
    )
    assert u[2]["titulo"] == "Construct and evaluate designs"
    assert all("paragraph" not in d["texto"] for d in u)


def test_pisa_conteo_distinto_falla():
    with pytest.raises(ErrorPipeline, match="PISA"):
        X.extraer_pisa(RECUADROS, 34)  # esperados 6, 4 y 5


@pytest.mark.parametrize("existente", ["e.jsonl", "r.json"])
def test_no_sobrescribe_una_extraccion_anterior(tmp_path, existente):
    (tmp_path / existente).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ErrorPipeline, match="no se sobrescribe"):
        X.correr(tmp_path / "e.jsonl", tmp_path / "r.json")
    assert [p.name for p in tmp_path.iterdir()] == [existente]


def test_pdf_con_hash_distinto_falla():
    doc = {**X.documento_del_inventario(X.ID_ICFES), "sha256": "0" * 64}
    if not (X.RAIZ_REPO / doc["ruta_local"]).is_file():
        pytest.skip("el PDF del ICFES no está en data/raw/curriculo/")
    with pytest.raises(ErrorPipeline, match="sha256"):
        X.pdf_verificado(doc)


def _pdfs_en_disco() -> bool:
    return all(
        (X.RAIZ_REPO / X.documento_del_inventario(i)["ruta_local"]).is_file()
        for i in (X.ID_ICFES, X.ID_PISA)
    )


@pytest.fixture(scope="module")
def corrida_real(tmp_path_factory):
    """Una sola extracción real para las pruebas contra los PDF."""
    if not _pdfs_en_disco():
        pytest.skip("los PDF del ICFES y de PISA no están en data/raw/curriculo/")
    d = tmp_path_factory.mktemp("extraccion_09")
    r = X.correr(d / "e.jsonl", d / "r.json")
    texto = (d / "e.jsonl").read_text("utf-8")
    filas = [json.loads(x) for x in texto.splitlines()]
    return r, filas, (d / "r.json").read_text("utf-8")


def pdftotext(id_doc: str, *opciones: str) -> str:
    """Texto del PDF leído por otra vía (recorte o -raw), con espacios unificados."""
    pdf = X.RAIZ_REPO / X.documento_del_inventario(id_doc)["ruta_local"]
    salida = X.ejecutar(["pdftotext", *opciones, str(pdf), "-"]).stdout
    return " ".join(salida.split())


def columna_del_pdf(x: int, ancho: int, encabezado: str) -> str:
    """Una columna de la Tabla 5 recortada por pdftotext, sin encabezado ni pie."""
    partes = []
    for p in range(38, 46):
        t = pdftotext(
            X.ID_ICFES,
            "-layout",
            "-f",
            str(p),
            "-l",
            str(p),
            "-x",
            str(x),
            "-y",
            "0",
            "-W",
            str(ancho),
            "-H",
            "700",
        )
        assert encabezado in t
        t = t.partition(encabezado)[2].partition("Continúa en la siguiente")[0]
        partes.append(t.strip())
    return " ".join(t for t in partes if t)


def test_icfes_real_no_pierde_ni_agrega_texto(corrida_real):
    _, filas, _ = corrida_real
    icfes = [f for f in filas if f["documento"] == X.ID_ICFES]
    evidencias = " ".join(
        f"{f['id_unidad'].split(':E')[1]} {f['texto']}" for f in icfes
    )
    assert evidencias == columna_del_pdf(340, 260, "Evidencia")
    afirmaciones = " ".join(dict.fromkeys(f["afirmacion"] for f in icfes))
    assert afirmaciones == columna_del_pdf(165, 175, "Afirmación")


def test_pisa_real_descriptores_y_paginas(corrida_real):
    _, filas, _ = corrida_real
    pisa = [f for f in filas if f["documento"] == X.ID_PISA]
    assert [f["pagina"] for f in pisa] == [34] * 10 + [36] * 5
    # cada recuadro, con sus viñetas seguidas, está igual en la lectura -raw
    for comp, pagina in (("C1.", 34), ("C2.", 34), ("C3.", 36)):
        grupo = [f["texto"] for f in pisa if f":{comp}" in f["id_unidad"]]
        crudo = pdftotext(X.ID_PISA, "-raw", "-f", str(pagina), "-l", str(pagina))
        assert " ".join(f"• {t}" for t in grupo) in crudo
    # el final de cada recuadro, copiado del PDF: ahí un corte no se notaría arriba
    texto = {f["id_unidad"].split(":")[1]: f["texto"] for f in pisa}
    assert texto["C1.6"].endswith("of scientific knowledge for society")
    assert texto["C2.4"].endswith("and evaluate their relative merits")
    assert texto["C3.5"].endswith("contemporary issues or sustainable development")
    assert list(dict.fromkeys(f["competencia"] for f in pisa)) == [
        "Competency 1: Explain phenomena scientifically",
        "Competency 2: Construct and evaluate designs for scientific enquiry and "
        "interpret scientific data and evidence critically",
        "Competency 3: Research, evaluate and use scientific information for "
        "decision making and action",
    ]


def test_trazabilidad_y_resumen_sin_texto(corrida_real):
    r, filas, resumen_texto = corrida_real
    for f in filas:
        assert f["sha256_archivo"] == X.sha256_de(X.RAIZ_REPO / f["archivo"])
    for doc in r["documentos"].values():
        assert doc["sha256"] == X.sha256_de(X.RAIZ_REPO / doc["archivo"])
    assert r["inventario"]["sha256"] == X.sha256_de(X.INVENTARIO)
    # el resumen va a git: ningún enunciado puede estar en él
    assert not any(f["texto"] in resumen_texto for f in filas)


def test_conteos_reales_contra_los_pdf(corrida_real):
    r, filas, _ = corrida_real
    assert r["documentos"][X.ID_ICFES]["afirmaciones"] == 9
    assert r["documentos"][X.ID_ICFES]["evidencias"] == 43
    assert r["documentos"][X.ID_PISA]["descriptores"] == 15
    assert r["unidades"] == 58
    por_comp = {}
    for f in filas:
        por_comp[f["competencia"]] = por_comp.get(f["competencia"], 0) + 1
    assert por_comp["Explicación de fenómenos"] == 15
    assert por_comp["Uso comprensivo del conocimiento científico"] == 15
    assert por_comp["Indagación"] == 13
    assert len({f["id_unidad"] for f in filas}) == 58  # ids únicos
    e46 = next(f for f in filas if f["id_unidad"] == "CO-ICFES-MR-CN-S11:E9.5")
    assert e46["texto"] == "Usa información adicional para evaluar una predicción."
