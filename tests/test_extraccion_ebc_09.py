"""Tests de la extracción de los EBC 2004 (extraccion_ebc_09; D60).

Primero con líneas y textos armados a mano, para fijar cada regla. Al final, si el PDF
está en el disco, contra el documento: 231 viñetas por grupo y columna, y en cada
columna y globo el mismo texto que pdftotext lee recortando la página, sin nada de más
ni de menos.
"""

import copy
import json
from collections import Counter

import pytest
import yaml

from rs_pipeline import extraccion_ebc_09 as X
from rs_pipeline.semantico_texto import ErrorPipeline

R = X.R


# --- Reglas ------------------------------------------------------------------


def test_cada_vineta_junta_sus_lineas():
    lineas = ["•Observo fenómenos", "específicos.", "•Busco información."]
    assert X.vinetas(lineas, "p18") == [
        "Observo fenómenos específicos.",
        "Busco información.",
    ]


def test_texto_antes_de_la_primera_vineta_falla():
    with pytest.raises(ErrorPipeline, match="antes de la primera viñeta"):
        X.vinetas(["Entorno vivo", "•Explico algo."], "p18")


@pytest.mark.parametrize(("grupo", "cine"), [("6-7", 2), ("8-9", 2), ("10-11", 3)])
def test_nivel_cine_del_grupo(grupo, cine):
    assert X.nivel_cine_del_grupo(grupo) == cine


@pytest.mark.parametrize(
    ("grupo", "mensaje"), [("9-10", "mezcla niveles"), ("4-5", "grado 4")]
)
def test_grupo_sin_un_solo_nivel_cine_falla(grupo, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.nivel_cine_del_grupo(grupo)


def test_conteo_distinto_del_piloto_falla(monkeypatch):
    monkeypatch.setattr(X, "ESTRUCTURA_EBC", {"6-7": {R.VIVO: 2}})
    u = {"grupo": "6-7", "columna": R.VIVO}
    X.controlar_conteos([u, u])
    with pytest.raises(ErrorPipeline, match="distintas de las del piloto"):
        X.controlar_conteos([u])
    with pytest.raises(ErrorPipeline, match="distintas de las del piloto"):
        X.controlar_conteos([u, u | {"columna": R.CTS}])


def unidad(texto: str = "Explico una cosa.") -> dict:
    return {"pagina": 18, "texto": texto}


CONTEXTO = {"6-7": ["Identifico una condición."]}


@pytest.fixture
def un_estandar(monkeypatch):
    monkeypatch.setattr(X, "ESTANDARES_GENERALES", {"6-7": 1})


@pytest.mark.parametrize(
    "sucio",
    [
        "Explico algo CIENCIAS NATURALES.",
        "Explico algo. Para lograrlo.",
        "…desarrollo compromisos personales.",
        "Explico algo Entorno físico.",
        "Explico algo. •Registro otra cosa.",
        "Explico Procesos químicos aquí.",
        "Al final de séptimo grado.",
    ],
)
def test_restos_de_encabezado_o_pie_fallan(un_estandar, sucio):
    X.controlar_textos([unidad()], CONTEXTO)
    with pytest.raises(ErrorPipeline, match="restos"):
        X.controlar_textos([unidad(sucio)], CONTEXTO)
    with pytest.raises(ErrorPipeline, match="restos"):
        X.controlar_textos([unidad()], {"6-7": [sucio]})


def test_ciencias_naturales_en_minusculas_es_texto_de_vineta(un_estandar):
    X.controlar_textos([unidad("Explico el uso de las ciencias naturales.")], CONTEXTO)


@pytest.mark.parametrize(
    "malo", ["Explico algo sin punto", "Explico algo. 18", "y de otra cosa."]
)
def test_texto_cortado_o_con_algo_pegado_falla(un_estandar, malo):
    with pytest.raises(ErrorPipeline, match="cortado"):
        X.controlar_textos([unidad(malo)], CONTEXTO)


def test_estandares_generales_de_mas_o_de_menos_fallan(un_estandar):
    for lista in ([], CONTEXTO["6-7"] * 2):
        with pytest.raises(ErrorPipeline, match="estándares generales"):
            X.controlar_textos([unidad()], {"6-7": lista})


# --- Recortes ----------------------------------------------------------------


def recortes_de_prueba(tmp_path, monkeypatch, cambiar) -> str:
    config = yaml.safe_load(R.CONFIG.read_text(encoding="utf-8"))
    cambiar(config)
    ruta = tmp_path / "recortes.yaml"
    ruta.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(X, "RECORTES", ruta)
    return config["entrada"]["sha256"]


@pytest.mark.parametrize(
    ("cambiar", "mensaje"),
    [
        (lambda c: c["paginas"][2].update(verificado_por=" "), "sin verificar"),
        (lambda c: c["paginas"].pop(2), "faltan o sobran"),
        (lambda c: c["paginas"].append(c["paginas"][0]), "faltan o sobran"),
        (lambda c: c["paginas"][1]["columnas"].pop(), "no son los esperados"),
        (lambda c: c["paginas"][1].update(grupo="8-9"), "no son los esperados"),
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
def pdf_real():
    doc = X.documento_del_inventario(R.ID_EBC)
    if not (X.RAIZ_REPO / doc["ruta_local"]).is_file():
        pytest.skip("el PDF de los EBC no está en data/raw/curriculo/")
    return X.pdf_verificado(doc)


@pytest.fixture(scope="module")
def filas_yaml():
    return yaml.safe_load(R.CONFIG.read_text(encoding="utf-8"))["paginas"]


@pytest.fixture(scope="module")
def corrida_real(pdf_real, tmp_path_factory):
    d = tmp_path_factory.mktemp("extraccion_ebc")
    r = X.correr(d / "e.jsonl", d / "r.json")
    texto = (d / "e.jsonl").read_text("utf-8")
    filas = [json.loads(x) for x in texto.splitlines()]
    return r, filas, (d / "r.json").read_text("utf-8")


@pytest.mark.parametrize(
    ("pagina", "campo", "valor"),
    [
        (19, "y_superior", 150),  # entra el encabezado «propios de las…»
        (18, "y_inferior", 715),  # entra el número de página
        (22, "y_superior", 165),  # entra el encabezado de la columna
        (18, "y_superior", 215),  # se pierde la primera viñeta
    ],
)
def test_recorte_que_deja_encabezado_o_pie_falla(
    pdf_real, filas_yaml, pagina, campo, valor
):
    _, paginas = R.leer_paginas(pdf_real)
    fila = copy.deepcopy(next(f for f in filas_yaml if f["pagina"] == pagina))
    X.controlar_encabezado_y_pie(paginas[pagina], fila)
    fila["columnas"][0][campo] = valor
    with pytest.raises(ErrorPipeline, match="encabezado o pie"):
        X.controlar_encabezado_y_pie(paginas[pagina], fila)


@pytest.mark.parametrize("pagina", [19, 21, 23])
def test_la_marca_de_agua_no_entra_en_ninguna_columna(pdf_real, filas_yaml, pagina):
    _, paginas = R.leer_paginas(pdf_real)
    marca = [p for p in paginas[pagina] if p.texto in ("CIENCIAS", "NATURALES")]
    assert len(marca) == 2
    fila = copy.deepcopy(next(f for f in filas_yaml if f["pagina"] == pagina))
    for r in fila["columnas"]:
        r["y_inferior"] = 765  # hasta el borde de la página
    # es más ancha que cualquier columna: no cabe aunque se baje el corte
    assert not [p for p in marca for r in fila["columnas"] if R.dentro(p, r)]
    fila["columnas"][0]["x_derecha"] = 320  # además se ensancha la primera
    with pytest.raises(ErrorPipeline, match="encabezado o pie"):
        X.controlar_encabezado_y_pie(paginas[pagina], fila)


def test_vinetas_reales_por_grupo_y_columna(corrida_real):
    r, filas, _ = corrida_real
    orden = (R.APROXIMO, R.VIVO, R.FISICO, R.CTS, R.COMPROMISOS)
    veces = Counter((f["grupo_grados"], f["columna"]) for f in filas)
    assert [[veces[g, c] for c in orden] for g in ("6-7", "8-9", "10-11")] == [
        [22, 16, 16, 13, 11],
        [21, 15, 12, 15, 12],
        [19, 12, 24, 11, 12],
    ]
    assert len(filas) == len({f["id_unidad"] for f in filas}) == 231
    por_grupo = r["documentos"][R.ID_EBC]["por_grupo"]
    assert [v["vinetas"] for v in por_grupo.values()] == [78, 75, 78]
    assert por_grupo["10-11"]["por_subcolumna"] == {
        "Procesos biológicos": 12,
        "Procesos químicos": 13,
        "Procesos físicos": 11,
    }


def test_subcolumna_solo_en_10_y_11(corrida_real):
    _, filas, _ = corrida_real
    con = [f for f in filas if f["subcolumna"]]
    assert {f["grupo_grados"] for f in con} == {"10-11"}
    assert Counter((f["columna"], f["subcolumna"], f["pagina"]) for f in con) == {
        (R.VIVO, "Procesos biológicos", 22): 12,
        (R.FISICO, "Procesos químicos", 22): 13,
        (R.FISICO, "Procesos físicos", 23): 11,
    }
    sin = [f for f in filas if f["grupo_grados"] == "10-11" and not f["subcolumna"]]
    assert {f["columna"] for f in sin} == {R.APROXIMO, R.CTS, R.COMPROMISOS}


def test_nivel_cine_y_contexto_por_grupo(corrida_real):
    _, filas, _ = corrida_real
    assert Counter(f["nivel_cine"][0] for f in filas) == {2: 153, 3: 78}
    for grupo, cuantos in (("6-7", 3), ("8-9", 4), ("10-11", 5)):
        contextos = {
            tuple(f["estandares_generales"])
            for f in filas
            if f["grupo_grados"] == grupo
        }
        assert len(contextos) == 1
        [contexto] = contextos
        assert len(contexto) == cuantos
        assert not [t for t in contexto if "Al final de" in t]
    # un estándar general nunca es una unidad
    generales = {t for f in filas for t in f["estandares_generales"]}
    assert len(generales) == 12
    assert not generales & {f["texto"] for f in filas}


def recorte_de_pdftotext(pdf, pagina: int, r: dict) -> str:
    """El texto del recorte según el recorte propio de pdftotext, sin espacios."""
    orden = ["pdftotext", "-layout", "-f", str(pagina), "-l", str(pagina)]
    orden += ["-x", str(r["x_izquierda"]), "-y", str(r["y_superior"])]
    orden += ["-W", str(r["x_derecha"] - r["x_izquierda"])]
    orden += ["-H", str(r["y_inferior"] - r["y_superior"])]
    return "".join(X.R.ejecutar([*orden, str(pdf), "-"]).stdout.split())


def test_cada_columna_y_globo_tiene_el_mismo_texto_en_el_pdf(
    corrida_real, pdf_real, filas_yaml
):
    _, filas, _ = corrida_real
    for fila in filas_yaml:
        n, grupo = fila["pagina"], fila["grupo"]
        for r in fila["columnas"]:
            mias = [
                f"•{f['texto']}"
                for f in filas
                if f["pagina"] == n and f["columna"] == r["columna"]
            ]
            assert "".join("".join(mias).split()) == recorte_de_pdftotext(
                pdf_real, n, r
            ), (n, r["columna"])
        contexto = next(
            f["estandares_generales"] for f in filas if f["grupo_grados"] == grupo
        )
        juntos = "".join("".join(contexto).split())
        for r in fila["contexto"]:
            if r["tipo"] == "estandar_general":
                assert recorte_de_pdftotext(pdf_real, n, r) in juntos, n


def test_sin_encabezado_ni_pie(corrida_real):
    _, filas, _ = corrida_real
    marcas = ("CIENCIAS", "NATURALES", "lograrlo", "…", "•", "Entorno ", "Al final")
    for f in filas:
        for texto in (f["texto"], *f["estandares_generales"]):
            assert not [m for m in marcas if m in texto], f["id_unidad"]
        assert not f["texto"].rstrip(".").endswith(f" {f['pagina']}")


def test_trazabilidad_y_resumen_sin_texto(corrida_real):
    r, filas, resumen_texto = corrida_real
    for f in filas:
        assert f["sha256_archivo"] == X.sha256_de(X.RAIZ_REPO / f["archivo"])
    assert r["recortes"]["sha256"] == X.sha256_de(R.CONFIG)
    assert r["inventario"]["sha256"] == X.sha256_de(X.INVENTARIO)
    textos = {f["texto"] for f in filas}
    textos |= {t for f in filas for t in f["estandares_generales"]}
    assert not any(t in resumen_texto for t in textos)
