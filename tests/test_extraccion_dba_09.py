"""Tests de la extracción de los DBA (extraccion_dba_09; D60).

Primero con palabras y líneas armadas a mano, para fijar cada regla. Al final, si el PDF
está en el disco, contra el documento: 29 DBA y 99 evidencias por grado, y el mismo
texto leído por otra vía (columnas recortadas por pdftotext), sin nada de más ni de
menos.
"""

import json
import re
from collections import Counter

import pytest
import yaml

from rs_pipeline import extraccion_dba_09 as X
from rs_pipeline.semantico_texto import ErrorPipeline

R = X.R


def P(texto: str, x0: float, x1: float, y0: float = 200, alto: float = 12):
    return R.Palabra(texto, x0, y0, x1, y0 + alto)


# --- Palabras y líneas -------------------------------------------------------


def test_subindice_se_pega_y_no_desordena_la_linea():
    columna = [
        P("(NaCl,", 143.9, 172.2, 507.4),
        P("H", 175.3, 181.4, 507.4),
        P("2", 181.5, 184.8, 514.7, alto=7),
        P("O,", 184.9, 195.2, 507.4),
        P("Cu).", 198.3, 217.3, 507.4),
        P("importancia", 147.1, 203.4, 520.9),
    ]
    lineas = X.lineas_de_columna(columna, 22, 6)
    assert [x.texto for x in lineas] == ["(NaCl, H2O, Cu).", "importancia"]


def test_palabras_juntas_de_tamano_normal_llevan_espacio():
    assert X.unir_palabras([P("de", 10, 20), P("la", 20.2, 30)]) == "de la"


def test_subindice_sin_linea_falla():
    suelto = [P("texto", 10, 40, 200), P("2", 50, 53, 300, alto=7)]
    with pytest.raises(ErrorPipeline, match="subíndice"):
        X.lineas_de_columna(suelto, 22, 6)


def test_numero_de_dba_va_con_su_primera_linea():
    columna = [
        P("Comprende", 87, 150, 161.2),
        P("1.", 64, 86, 161.6, alto=31),
        P("cómo", 87, 120, 175.7),
    ]
    lineas = X.lineas_de_columna(columna, 21, 6)
    assert [(x.texto, x.numero) for x in lineas] == [("Comprende", 1), ("cómo", None)]


@pytest.mark.parametrize(
    ("lineas", "esperado"),
    [
        (["(Boyle-", "Mariotte)"], "(Boyle-Mariotte)"),
        (["inflar/", "explotar"], "inflar/explotar"),
        (["(Brönsted –", "Lowry)"], "(Brönsted – Lowry)"),
        (["soluto -", "solvente"], "soluto - solvente"),
        (["una", "línea"], "una línea"),
    ],
)
def test_union_de_lineas(lineas, esperado):
    assert X.unir_lineas(lineas) == esperado


def test_palabra_que_cruza_un_recorte_falla():
    for p in (P("columnas", 300, 340), P("arriba", 10, 40, 125)):
        with pytest.raises(ErrorPipeline, match="cruza un recorte"):
            X.texto_de_pagina([p], (327, 132, 778), 21)


def test_encabezado_y_pie_quedan_fuera():
    palabras = [
        P("Derechos", 160, 200, 82),
        P("texto", 90, 120),
        P("21", 550, 560, 787),
    ]
    dentro = X.texto_de_pagina(palabras, (327, 132, 778), 21)
    assert [p.texto for p in dentro] == ["texto"]


def test_numero_de_pagina_dentro_del_recorte_falla():
    palabras = [
        P("V.1", 473, 492, 87, alto=16),
        P("texto", 90, 120),
        P("21", 550, 560, 787),
        P("CienciasNaturales", 31, 81, 823),
    ]
    bien = X.texto_de_pagina(palabras, (327, 132, 778), 21)
    X.controlar_encabezado_y_pie(palabras, bien, 21)
    mal = X.texto_de_pagina(palabras, (327, 132, 812), 21)  # entra el «21»
    with pytest.raises(ErrorPipeline, match="encabezado o del pie"):
        X.controlar_encabezado_y_pie(palabras, mal, 21)


def test_grado_sale_del_encabezado():
    palabras = [P("10º", 500, 520, 45), P("5º", 90, 100, 300)]
    assert X.grado_de_pagina(palabras, 132, 34) == 10
    with pytest.raises(ErrorPipeline, match="grado"):
        X.grado_de_pagina(palabras[1:], 132, 34)


# --- DBA ---------------------------------------------------------------------


def lineas(*textos: str, grado: int = 6) -> list:
    """«1|texto» abre el DBA 1; el resto son líneas normales."""
    salida = []
    for t in textos:
        numero, barra, resto = t.partition("|")
        if barra:
            salida.append(X.Linea(21, grado, resto, int(numero)))
        else:
            salida.append(X.Linea(21, grado, t, None))
    return salida


BASE = (
    "1|Comprende una cosa",
    "y otra cosa.",
    "Evidencias de aprendizaje",
    "q Explica la primera",
    "cosa pedida.",
    "q Explica la segunda cosa.",
    "Ejemplo",
    "Un caso para",
    "trabajar.",
)


def test_arma_el_dba_con_enunciado_evidencias_y_ejemplo():
    [d] = X.armar_dbas(lineas(*BASE))
    assert d["enunciado"] == "Comprende una cosa y otra cosa."
    assert [e["texto"] for e in d["evidencias"]] == [
        "Explica la primera cosa pedida.",
        "Explica la segunda cosa.",
    ]
    assert d["ejemplo"] == "Un caso para trabajar."


def test_ejemplo_sin_texto_queda_en_none():
    [d] = X.armar_dbas(lineas(*BASE[:7]))
    assert d["ejemplo"] is None


@pytest.mark.parametrize(
    ("textos", "mensaje"),
    [
        (("texto suelto", *BASE), "antes del primer DBA"),
        ((*BASE[:3], "sin viñeta", *BASE[3:]), "primera viñeta"),
        ((*BASE[:3], "Ejemplo"), "sin evidencias"),
        ((*BASE[:2], "Ejemplo"), "sin evidencias"),
        (BASE[:6], "último DBA"),
        ((*BASE[:6], "2|Otro enunciado aquí"), "no llegó a «Ejemplo»"),
        ((*BASE, "Evidencias de aprendizaje"), "fuera de lugar"),
    ],
)
def test_secuencia_rota_falla(textos, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.armar_dbas(lineas(*textos))


def test_dba_que_sigue_en_otro_grado_falla():
    mezcla = lineas(*BASE[:3]) + lineas(*BASE[3:], grado=7)
    with pytest.raises(ErrorPipeline, match="grado 7"):
        X.armar_dbas(mezcla)


# --- Controles ---------------------------------------------------------------


def dba(numero: int = 1, evidencias: int = 2, ejemplo: str | None = "Un caso.") -> dict:
    return {
        "grado": 6,
        "numero": numero,
        "enunciado": "Comprende una cosa.",
        "evidencias": [
            {"pagina": 21, "texto": "Explica una cosa pedida."}
            for _ in range(evidencias)
        ],
        "ejemplo": ejemplo,
    }


def test_numeracion_con_salto_falla():
    with pytest.raises(ErrorPipeline, match="no consecutiva en el grado 6"):
        X.controlar_estructura([dba(1), dba(3)])


def test_evidencias_distintas_de_las_del_piloto_fallan(monkeypatch):
    monkeypatch.setattr(X, "ESTRUCTURA_DBA", {6: (2, 2)})
    X.controlar_estructura([dba(1), dba(2)])  # la buena pasa
    with pytest.raises(ErrorPipeline, match="distintas de las del piloto"):
        X.controlar_estructura([dba(1), dba(2, evidencias=1)])


@pytest.mark.parametrize(
    "sucio", ["algo CienciasNaturales", "DBA_Final.indd 21", "Aprendizaje • V.1"]
)
def test_restos_de_encabezado_o_pie_fallan(monkeypatch, sucio):
    monkeypatch.setattr(X, "EJEMPLOS_SOLO_FIGURA", ())
    X.controlar_textos([dba()])
    with pytest.raises(ErrorPipeline, match="encabezado o pie"):
        X.controlar_textos([dba(ejemplo=sucio)])


def test_ejemplo_sin_texto_no_esperado_falla(monkeypatch):
    monkeypatch.setattr(X, "EJEMPLOS_SOLO_FIGURA", ())
    with pytest.raises(ErrorPipeline, match="sin texto en «Ejemplo»"):
        X.controlar_textos([dba(ejemplo=None)])


@pytest.mark.parametrize(
    ("grado", "cine"), [(6, 2), (7, 2), (8, 2), (9, 2), (10, 3), (11, 3)]
)
def test_cada_unidad_lleva_el_nivel_cine_de_su_grado(grado, cine):
    doc = X.documento_del_inventario(R.ID_DBA)
    d = dba() | {"grado": grado}
    assert [f["nivel_cine"] for f in X.registros_dba(doc, [d])] == [[cine], [cine]]


def test_grado_sin_nivel_cine_falla():
    with pytest.raises(ErrorPipeline, match="grado 5"):
        X.nivel_cine_del_grado(5)


def recortes_de_prueba(tmp_path, monkeypatch, cambiar) -> str:
    config = yaml.safe_load(X.R.CONFIG.read_text(encoding="utf-8"))
    cambiar(config)
    ruta = tmp_path / "recortes.yaml"
    ruta.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(X, "RECORTES", ruta)
    return config["entrada"]["sha256"]


@pytest.mark.parametrize(
    ("cambiar", "mensaje"),
    [
        (lambda c: c["paginas"][3].update(verificado_por="  "), "sin verificar"),
        (lambda c: c["paginas"].pop(3), "no hay recorte"),
        (lambda c: c["paginas"].append(c["paginas"][0]), "repetidas"),
    ],
)
def test_recortes_no_aprobados_fallan(tmp_path, monkeypatch, cambiar, mensaje):
    sha = recortes_de_prueba(tmp_path, monkeypatch, cambiar)
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.cargar_recortes(sha)


def test_recortes_de_otro_pdf_fallan():
    with pytest.raises(ErrorPipeline, match="otro PDF"):
        X.cargar_recortes("0" * 64)


@pytest.mark.parametrize("existente", ["e.jsonl", "r.json"])
def test_no_sobrescribe_una_extraccion_anterior(tmp_path, existente):
    (tmp_path / existente).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ErrorPipeline, match="no se sobrescribe"):
        X.correr(tmp_path / "e.jsonl", tmp_path / "r.json")
    assert [p.name for p in tmp_path.iterdir()] == [existente]


# --- Contra el PDF real ------------------------------------------------------


@pytest.fixture(scope="module")
def corrida_real(tmp_path_factory):
    doc = X.documento_del_inventario(R.ID_DBA)
    if not (X.RAIZ_REPO / doc["ruta_local"]).is_file():
        pytest.skip("el PDF de los DBA no está en data/raw/curriculo/")
    d = tmp_path_factory.mktemp("extraccion_dba")
    r = X.correr(d / "e.jsonl", d / "r.json")
    texto = (d / "e.jsonl").read_text("utf-8")
    filas = [json.loads(x) for x in texto.splitlines()]
    return r, filas, (d / "r.json").read_text("utf-8")


def sin_espacios(texto: str) -> str:
    return "".join(texto.split())


@pytest.fixture(scope="module")
def columnas_del_pdf(corrida_real):
    """Las 38 columnas recortadas por pdftotext, en orden de lectura y sin espacios."""
    pdf = X.RAIZ_REPO / X.documento_del_inventario(R.ID_DBA)["ruta_local"]
    partes = []
    for p in range(21, 40):
        for x, ancho in ((0, 327), (327, 328)):
            orden = ["pdftotext", "-layout", "-f", str(p), "-l", str(p)]
            orden += ["-x", str(x), "-y", "132", "-W", str(ancho), "-H", "646"]
            partes.append(X.ejecutar([*orden, str(pdf), "-"]).stdout)
    return sin_espacios(" ".join(partes))


def dbas_de(filas: list[dict]) -> list[list[dict]]:
    grupos: dict[tuple[int, int], list[dict]] = {}
    for f in filas:
        grupos.setdefault((f["grado"], f["dba"]), []).append(f)
    return list(grupos.values())


def test_conteos_reales_por_grado(corrida_real):
    r, filas, _ = corrida_real
    por_grado = r["documentos"][R.ID_DBA]["por_grado"]
    assert [v["dba"] for v in por_grado.values()] == [5, 4, 5, 6, 4, 5]
    assert [v["evidencias"] for v in por_grado.values()] == [16, 13, 19, 21, 12, 18]
    assert Counter(f["grado"] for f in filas) == {
        6: 16, 7: 13, 8: 19, 9: 21, 10: 12, 11: 18
    }  # fmt: skip
    assert len(dbas_de(filas)) == 29
    assert len(filas) == len({f["id_unidad"] for f in filas}) == 99
    for grado in range(6, 12):
        numeros = list(dict.fromkeys(f["dba"] for f in filas if f["grado"] == grado))
        assert numeros == list(range(1, len(numeros) + 1))


def test_nivel_cine_real_por_grado(corrida_real):
    r, filas, _ = corrida_real
    assert all(f["nivel_cine"] == ([2] if f["grado"] <= 9 else [3]) for f in filas)
    # 16 + 13 + 19 + 21 evidencias en CINE 2 y 12 + 18 en CINE 3
    assert Counter(f["nivel_cine"][0] for f in filas) == {2: 69, 3: 30}
    por_grado = r["documentos"][R.ID_DBA]["por_grado"]
    assert [v["nivel_cine"] for v in por_grado.values()] == [2, 2, 2, 2, 3, 3]


def test_grado_de_cada_unidad_segun_su_pagina(corrida_real):
    _, filas, _ = corrida_real
    # encabezados leídos a ojo en las páginas
    paginas = {6: (21, 23), 7: (24, 26), 8: (27, 29), 9: (30, 33)}
    paginas |= {10: (34, 36), 11: (37, 39)}
    for f in filas:
        a, b = paginas[f["grado"]]
        assert a <= f["pagina"] <= b, f["id_unidad"]


def test_no_se_pierde_ni_se_agrega_texto(corrida_real, columnas_del_pdf):
    _, filas, _ = corrida_real
    partes = []
    for grupo in dbas_de(filas):
        primera = grupo[0]
        partes += [f"{primera['dba']}.", primera["enunciado_dba"]]
        partes.append("Evidencias de aprendizaje")
        partes += [f"q {f['texto']}" for f in grupo]
        partes += ["Ejemplo", primera["ejemplo"] or ""]
    # mismos caracteres, las mismas veces: nada falta y nada sobra
    assert Counter(sin_espacios(" ".join(partes))) == Counter(columnas_del_pdf)


def test_cada_texto_esta_seguido_en_el_pdf(corrida_real, columnas_del_pdf):
    _, filas, _ = corrida_real
    for f in filas:
        assert sin_espacios(f["texto"]) in columnas_del_pdf, f["id_unidad"]
        if f["ejemplo"]:
            assert sin_espacios(f["ejemplo"]) in columnas_del_pdf, f["id_unidad"]
    # el número grande del DBA cae en medio de su enunciado: se quita de los dos lados
    numero = re.compile(r"[1-6]\.")
    sin_numeros = numero.sub("", columnas_del_pdf)
    for grupo in dbas_de(filas):
        enunciado = numero.sub("", sin_espacios(grupo[0]["enunciado_dba"]))
        assert enunciado in sin_numeros, grupo[0]["id_unidad"]


def test_sin_encabezado_ni_pie(corrida_real):
    _, filas, _ = corrida_real
    marcas = ("•", "V.1", "CienciasNaturales", ".indd", "p.m.", "12/10/16", "Grado ")
    for f in filas:
        for campo in ("enunciado_dba", "texto", "ejemplo"):
            valor = f[campo] or ""
            assert not [m for m in marcas if m in valor], (f["id_unidad"], campo)
            assert not valor.endswith(f" {f['pagina']}"), (f["id_unidad"], campo)


def test_casos_vistos_en_las_paginas(corrida_real):
    _, filas, _ = corrida_real
    por_id = {f["id_unidad"].split(":")[1]: f for f in filas}
    assert por_id["G6.D3.E2"]["texto"].endswith("símbolos químicos (NaCl, H2O, Cu).")
    assert "(Boyle-Mariotte, Charles, Gay-Lussac" in por_id["G8.D3.E3"]["texto"]
    assert "inflar/explotar" in por_id["G8.D3.E3"]["texto"]
    assert "(Arrhenius, Brönsted – Lowry y Lewis)" in por_id["G9.D2.E1"]["texto"]
    # DBA 5 de 9.º: enunciado en la columna izquierda, evidencias en la derecha
    assert por_id["G9.D5.E1"]["enunciado_dba"].startswith("Explica la forma como")
    assert por_id["G9.D5.E1"]["texto"].startswith("Interpreta a partir de modelos")
    # un ejemplo que salta de columna
    assert "para respaldar sus explicaciones" in por_id["G10.D3.E1"]["ejemplo"]
    assert por_id["G6.D1.E1"]["ejemplo"] is None


def test_trazabilidad_y_resumen_sin_texto(corrida_real):
    r, filas, resumen_texto = corrida_real
    for f in filas:
        assert f["sha256_archivo"] == X.sha256_de(X.RAIZ_REPO / f["archivo"])
    assert r["recortes"]["sha256"] == X.sha256_de(R.CONFIG)
    assert r["inventario"]["sha256"] == X.sha256_de(X.INVENTARIO)
    textos = [f[c] for f in filas for c in ("texto", "enunciado_dba", "ejemplo")]
    assert not any(t in resumen_texto for t in textos if t)
