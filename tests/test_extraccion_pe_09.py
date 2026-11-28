"""Tests de la extracción de Perú (extraccion_pe_09; D57, D60).

Primero con palabras y textos armados a mano, para fijar cada regla. Al final, si los
PDF, el OCR y las correcciones están en el disco, contra los documentos: 107 desempeños
por competencia y grado, textos vistos en las imágenes y estándares del CNEB.
"""

import copy
import difflib
import json
import re
from collections import Counter

import pytest
import yaml

from rs_pipeline import extraccion_pe_09 as X
from rs_pipeline.semantico_texto import ErrorPipeline

V = X.V


def P(texto: str, x: int, y: int) -> V.Palabra:
    return V.Palabra(texto, x, y, x + 60, y + 30)


def columna(*vinetas_y: int, grado: int = 1) -> dict:
    return {
        "grado": grado,
        "x_izquierda": 0,
        "x_derecha": 1000,
        "y_superior": 100,
        "y_inferior": 900,
        "vinetas": [[40, y + 7, 56, y + 23] for y in vinetas_y],
    }


# --- Armado ------------------------------------------------------------------


def test_zona_de_columna_sin_vineta_leida_ni_bordes():
    palabras = [
        P("siguientes:", 200, 60),  # sobre la zona
        V.Palabra("e", 40, 207, 56, 223),  # la viñeta leída como letra
        P("Explica", 100, 200),
        P("|", 700, 200),
        P("algo", 200, 203),
        P("más.", 100, 260),
        P("]", 700, 260),
        P("sello", 100, 950),  # bajo la tabla
    ]
    lineas = X.lineas_de_columna(palabras, columna(200))
    assert [[p.texto for p in x["palabras"]] for x in lineas] == [
        ["Explica", "algo"],
        ["más."],
    ]
    assert [x["abre"] for x in lineas] == [True, False]


@pytest.mark.parametrize("vinetas", [(230,), (200, 202)])
def test_vineta_que_no_abre_una_sola_linea_falla(vinetas):
    with pytest.raises(ErrorPipeline, match="una sola línea"):
        X.lineas_de_columna([P("Explica", 100, 200)], columna(*vinetas))


def pagina(n: int, *columnas: dict) -> dict:
    return {"pagina": n, "competencia": "explica", "columnas": list(columnas)}


def test_la_187_continua_el_desempeno_de_la_186():
    palabras = {
        186: [P("Explica", 100, 200), P("cómo", 200, 200)],
        187: [P("todo.", 100, 150), P("Describe", 100, 300), P("más.", 200, 300)],
    }
    filas = [pagina(186, columna(200)), pagina(187, columna(300))]
    a, b = X.armar(filas, palabras)
    assert (a["texto"], a["paginas"]) == ("Explica cómo todo.", [186, 187])
    assert (b["texto"], b["paginas"]) == ("Describe más.", [187])


def test_texto_antes_de_la_primera_vineta_falla():
    palabras = {
        186: [P("Explica", 100, 200)],
        188: [P("suelto", 100, 150), P("Describe", 100, 300)],
    }
    filas = [pagina(186, columna(200)), pagina(188, columna(300))]
    with pytest.raises(ErrorPipeline, match="antes de la primera viñeta"):
        X.armar(filas, palabras)


# --- Correcciones y ejemplos -------------------------------------------------


def unidad(texto: str, pagina: int = 186, **otros) -> dict:
    base = {"texto": texto, "paginas": [pagina], "grado": 1, "competencia": "explica"}
    return base | {"corregida": False, "ejemplo": None, "ciclo": "VI"} | otros


def correccion(antes, ocr, corregido, despues="", pagina="186") -> dict:
    return {
        "pagina": pagina,
        "texto_antes": antes,
        "texto_ocr": ocr,
        "texto_corregido": corregido,
        "texto_despues": despues,
    }


def test_aplica_la_correccion_en_el_unico_sitio():
    u = [unidad("Explica que brinda a"), unidad("Explica hasta 39 *C, que es.")]
    X.aplicar_correcciones(
        u,
        [
            correccion("brinda a", "", "la sociedad."),
            correccion("hasta", "39 *C,", "39 °C,", "que es."),
        ],
    )
    assert [x["texto"] for x in u] == [
        "Explica que brinda a la sociedad.",
        "Explica hasta 39 °C, que es.",
    ]
    assert all(x["corregida"] for x in u)


@pytest.mark.parametrize(
    ("textos", "c", "mensaje"),
    [
        (["Explica algo."], correccion("otra", "cosa", "x"), "coincide 0 veces"),
        (["Explica a b", "Explica a b"], correccion("a", "b", "c"), "coincide 2"),
        (["Explica a b y más."], correccion("a", "b", "c"), "no cae al final"),
    ],
)
def test_correccion_que_no_coincide_una_vez_falla(textos, c, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.aplicar_correcciones([unidad(t) for t in textos], [c])


def test_correccion_de_otra_pagina_no_se_aplica():
    with pytest.raises(ErrorPipeline, match="coincide 0 veces"):
        X.aplicar_correcciones([unidad("a b", pagina=188)], [correccion("a", "b", "c")])


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        ({"verificado_por": " "}, "sin verificar"),
        ({"pagina": "182"}, "el resumen"),
    ],
)
def test_correcciones_sin_verificar_o_que_no_cuadran_fallan(
    tmp_path, monkeypatch, cambio, mensaje
):
    fila = correccion("a", "b", "c") | {"motivo": "m", "verificado_por": "yo"} | cambio
    csv_ = tmp_path / "c.csv"
    csv_.write_text(
        ",".join(fila) + "\n" + ",".join(fila.values()) + "\n", encoding="utf-8"
    )
    resumen = tmp_path / "r.json"
    resumen.write_text('{"por_pagina": {"186": 1}}', encoding="utf-8")
    monkeypatch.setattr(X, "CORRECCIONES", csv_)
    monkeypatch.setattr(X, "RESUMEN_CORRECCIONES", resumen)
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.cargar_correcciones()


def test_el_ejemplo_pasa_a_contexto():
    u = [unidad("Explica algo. Ejemplo: El estudiante explica."), unidad("Explica.")]
    X.separar_ejemplos(u)
    assert (u[0]["texto"], u[0]["ejemplo"]) == (
        "Explica algo.",
        "El estudiante explica.",
    )
    assert u[1]["ejemplo"] is None


def test_dos_ejemplos_en_un_desempeno_fallan():
    with pytest.raises(ErrorPipeline, match="dos"):
        X.separar_ejemplos([unidad("A. Ejemplo: b. Ejemplo: c.")])


# --- Ciclo -------------------------------------------------------------------


def test_menciones_de_ciclo_sin_distinguir_mayusculas_ni_bordes():
    texto = (
        "al final del ciclo Vii | nivel esperado del | ciclo VII, ciclo celular. CICLO"
    )
    palabras = [P(w, 0, 0) for w in texto.split()]
    assert X.menciones_de_ciclo(palabras) == ["VII", "VII"]


@pytest.mark.parametrize(
    ("menciones", "origen"),
    [(["VII", "VII"], "texto"), (["VI", "VII"], "referencia"), (["VIL"], "referencia")],
)
def test_ciclo_de_pagina(menciones, origen):
    assert X.ciclo_de_pagina(menciones, "VII", 188) == ("VII", origen)


@pytest.mark.parametrize(
    ("menciones", "mensaje"),
    [(["VI", "VI"], "referencia"), ([], "no menciona")],
)
def test_ciclo_dudoso_falla(menciones, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.ciclo_de_pagina(menciones, "VII", 188)


def test_ciclo_que_no_cuadra_con_el_grado_falla():
    ciclos = {186: ("VI", "texto"), 187: ("VI", "hereda")}
    u = unidad("a", grado=2, paginas=[186, 187])
    X.asignar_ciclos([u], ciclos)
    assert u["ciclo"] == "VI"
    with pytest.raises(ErrorPipeline, match="del ciclo VII"):
        X.asignar_ciclos([unidad("a", grado=3)], ciclos)


# --- CNEB y controles --------------------------------------------------------

MARCAS = ("Siete empieza", "Seis empieza", "Cinco empieza")


def test_estandares_llegan_hasta_el_nivel_siguiente():
    texto = X.texto_de_estandares(
        "   D     Destacado.\n 7        Siete empieza\n          y acaba.\n"
        "   6     Seis empieza y acaba.\n          Cinco empieza.\n"
    )
    assert X.estandares_de_pagina(texto, MARCAS) == {
        "VII": "Siete empieza y acaba.",
        "VI": "Seis empieza y acaba.",
    }


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("Siete empieza. Cinco empieza.", "aparece 0 veces"),
        ("Seis empieza. Siete empieza. Cinco empieza.", "en ese orden"),
        ("Siete empieza 6 así. Seis empieza. Cinco empieza.", "rótulos"),
        ("Siete empieza. Seis empieza cortado Cinco empieza.", "cortado"),
    ],
)
def test_estandar_mal_delimitado_falla(texto, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.estandares_de_pagina(texto, MARCAS)


BUENO = "Explica el ADN y el CO2 a 39 °C en el “norte-sur”."


@pytest.mark.parametrize(
    ("malo", "mensaje"),
    [
        ("Explica a *C algo.", "restos"),
        ("Explica esto > A META 3].", "restos"),
        ("Explica la VISACION del acta.", "restos"),
        ("Explica algo. DESEMPEÑOS de nuevo.", "restos"),
        ("Explica algo como los siguientes:.", "restos"),
        ("Explica al final del ciclo VII algo.", "restos"),
        ("Explica 649-2016 MINEDU algo.", "restos"),
        ("Explica algo sin punto,", "cortado"),
        ("Cuando el estudiante explica algo.", "restos"),
        ("Analiza algo que no toca.", "verbo"),
    ],
)
def test_controles_de_texto(malo, mensaje):
    X.controlar_textos([unidad(BUENO)])
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.controlar_textos([unidad(malo)])


def test_el_ejemplo_tambien_se_controla():
    with pytest.raises(ErrorPipeline, match="restos"):
        X.controlar_textos([unidad(BUENO, ejemplo="Algo con | borde.")])


def test_conteo_distinto_del_piloto_falla(monkeypatch):
    estructura = {"explica": [1, 0, 0, 0, 0]}
    monkeypatch.setattr(X, "ESTRUCTURA_PE", estructura)
    monkeypatch.setattr(X, "EJEMPLOS_PE", {})
    X.controlar_conteos([unidad("a")])
    with pytest.raises(ErrorPipeline, match="distintos de los del piloto"):
        X.controlar_conteos([unidad("a"), unidad("b")])
    with pytest.raises(ErrorPipeline, match="ejemplos"):
        X.controlar_conteos([unidad("a", ejemplo="x")])


# --- Viñetas aprobadas y salidas ---------------------------------------------


def vinetas_de_prueba(tmp_path, monkeypatch, cambiar) -> str:
    config = yaml.safe_load(V.CONFIG.read_text(encoding="utf-8"))
    cambiar(config)
    ruta = tmp_path / "v.yaml"
    ruta.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(X, "VINETAS", ruta)
    return config["entrada"]["sha256"]


@pytest.mark.parametrize(
    ("cambiar", "mensaje"),
    [
        (lambda c: c["paginas"][3].update(verificado_por=""), "sin verificar"),
        (lambda c: c["paginas"].pop(), "faltan o sobran"),
        (lambda c: c["ocr"].update(sha256="0"), "otro registro"),
        (lambda c: c["paginas"][0]["columnas"].pop(), "no son los esperados"),
    ],
)
def test_vinetas_no_aprobadas_fallan(tmp_path, monkeypatch, cambiar, mensaje):
    sha = vinetas_de_prueba(tmp_path, monkeypatch, cambiar)
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.cargar_vinetas(sha)


def test_vinetas_de_otro_pdf_fallan():
    with pytest.raises(ErrorPipeline, match="otro PDF"):
        X.cargar_vinetas("0" * 64)


@pytest.mark.parametrize("existente", ["e.jsonl", "r.json"])
def test_no_sobrescribe_una_extraccion_anterior(tmp_path, existente):
    (tmp_path / existente).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ErrorPipeline, match="no se sobrescribe"):
        X.correr(tmp_path / "e.jsonl", tmp_path / "r.json")
    assert [p.name for p in tmp_path.iterdir()] == [existente]


# --- Contra los documentos reales --------------------------------------------


@pytest.fixture(scope="module")
def en_disco():
    faltan = [
        i
        for i in (X.ID_PCS, X.ID_CNEB)
        if not (X.RAIZ_REPO / X.documento_del_inventario(i)["ruta_local"]).is_file()
    ]
    if faltan or not X.CORRECCIONES.is_file():
        pytest.skip("faltan los PDF de Perú, el OCR o las correcciones en data/")


@pytest.fixture(scope="module")
def corrida_real(en_disco, tmp_path_factory):
    d = tmp_path_factory.mktemp("extraccion_pe")
    r = X.correr(d / "e.jsonl", d / "r.json")
    texto = (d / "e.jsonl").read_text("utf-8")
    filas = [json.loads(x) for x in texto.splitlines()]
    return r, filas, (d / "r.json").read_text("utf-8")


def por_id(filas: list[dict]) -> dict[str, dict]:
    return {f["id_unidad"].split(":")[1]: f for f in filas}


def test_conteos_reales(corrida_real):
    r, filas, _ = corrida_real
    veces = Counter((f["competencia_id"], f["grado"]) for f in filas)
    assert {c: [veces[c, g] for g in range(1, 6)] for c in X.ESTRUCTURA_PE} == {
        "indaga": [5, 5, 5, 5, 5],
        "explica": [12, 15, 12, 10, 13],
        "disena": [4, 4, 4, 4, 4],
    }
    assert Counter(f["competencia_id"] for f in filas) == {
        "indaga": 25, "explica": 62, "disena": 20
    }  # fmt: skip
    assert len(filas) == len({f["id_unidad"] for f in filas}) == 107
    assert len({f["texto"] for f in filas}) == 99  # el Programa repite algunos
    assert Counter(f["nivel_cine"][0] for f in filas) == {2: 66, 3: 41}
    # 21 + 24 desempeños de 1.º y 2.º (ciclo VI); 21 + 19 + 22 de 3.º a 5.º
    assert Counter(f["ciclo"] for f in filas) == {"VI": 45, "VII": 62}
    assert all(f["ciclo"] == ("VI" if f["grado"] <= 2 else "VII") for f in filas)
    assert {f["origen"] for f in filas} == {"OCR"}
    conteo = r["documentos"][X.ID_PCS]
    revisadas = [
        n for n, c in conteo["ciclo_por_pagina"].items() if c["origen"] == "referencia"
    ]
    assert revisadas == ["188", "189"]
    assert conteo["con_ejemplo"] == 7


def test_todos_terminan_en_punto_y_sin_restos(corrida_real):
    _, filas, _ = corrida_real
    marcas = ("*", "|", "]", "[", ">", "META", "Cópno", "epila", "MINEDU", "DESEMP")
    for f in filas:
        for t in (f["texto"], f["ejemplo"] or "a."):
            assert t.endswith("."), f["id_unidad"]
            assert not [m for m in marcas if m in t], f["id_unidad"]


def test_textos_vistos_en_las_imagenes(corrida_real):
    r, filas, _ = corrida_real
    u = por_id(filas)
    assert u["S1.explica.8"]["texto"] == (
        "Explica cómo los organismos actuales de los diversos reinos se originan a "
        "partir de ancestros comunes mediante la selección natural."
    )
    assert u["S1.explica.8"]["paginas"] == [186, 187]
    assert u["S1.explica.7"]["texto"].endswith("que brinda a la sociedad.")
    assert u["S2.explica.9"]["texto"].endswith("para la perpetuación de la especie.")
    assert "hasta 39 °C, que es un signo" in u["S2.explica.4"]["ejemplo"]
    assert u["S5.indaga.5"]["texto"].endswith("a través de otros medios.")
    assert u["S3.explica.8"]["texto"].endswith("a partir del ciclo celular.")
    assert u["S3.explica.12"]["texto"].endswith("su impacto en la sociedad y el "
                                                "ambiente.")  # fmt: skip
    assert u["S5.disena.3"]["texto"].startswith("Ejecuta la secuencia de pasos")
    assert u["S1.indaga.1"]["texto"].startswith("Formula preguntas acerca de las")
    corregidas = sorted(x.split(":")[1] for x in r["unidades_corregidas"])
    assert corregidas == [
        "S1.explica.7", "S1.explica.8", "S2.explica.4", "S3.explica.12",
        "S3.explica.8", "S5.disena.3", "S5.indaga.5",
    ]  # fmt: skip


def test_mismo_desempeno_en_dos_grados_se_lee_igual(corrida_real):
    # desempeños que el Programa repite palabra por palabra: dos lecturas del OCR
    _, filas, _ = corrida_real
    u = por_id(filas)
    for grupo in (
        ("S1.disena.2", "S2.disena.2"),
        ("S1.disena.3", "S2.disena.3"),
        ("S2.disena.1", "S3.disena.1", "S4.disena.1"),  # la 193 junta dos columnas
    ):
        assert len({u[k]["texto"] for k in grupo}) == 1, grupo


def test_columnas_unicas_igual_que_el_txt_del_ocr(en_disco):
    doc = X.documento_del_inventario(X.ID_PCS)
    filas = X.cargar_vinetas(doc["sha256"])
    fichas = V.fichas_del_ocr(doc["sha256"])
    palabras = {n: X.palabras_de_pagina(fichas[n]) for n in V.PAGINAS}
    crudas = X.armar(copy.deepcopy(filas), palabras)
    # en las páginas de una columna, el .txt trae el mismo texto en el mismo orden
    for n in (183, 189, 194):
        txt = (V.DESTINO / f"p{n}.txt").read_text(encoding="utf-8")
        leido = []
        for linea in txt.rsplit("siguientes:", 1)[1].splitlines():
            palabras_linea = linea.split()
            # al comienzo de línea, la viñeta sale leída como «e» o «+»
            if palabras_linea[:1] in (["e"], ["+"]):
                palabras_linea = palabras_linea[1:]
            leido += palabras_linea
        armado = " ".join(u["texto"] for u in crudas if u["paginas"] == [n]).split()
        assert armado == leido, n


def parecido(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()


def test_estandar_del_cneb_por_competencia_y_ciclo(corrida_real):
    _, filas, _ = corrida_real
    estandares = {(f["competencia_id"], f["ciclo"]): f["estandar_cneb"] for f in filas}
    assert len({e["texto"] for e in estandares.values()}) == 6
    for (_, ciclo), e in estandares.items():
        assert e["nivel"] == (6 if ciclo == "VI" else 7)
        assert e["documento"] == X.ID_CNEB
    assert "determinar la interrelación" in estandares["disena", "VII"]["texto"]
    assert "al delimitar el alcance" in estandares["disena", "VI"]["texto"]
    # el Programa imprime en cada página la descripción de su nivel: coincide con el
    # CNEB salvo en 193 y 194, que repiten la del ciclo VI bajo el rótulo VII
    paginas = {181: "indaga", 182: "indaga", 183: "indaga", 186: "explica",
               188: "explica", 189: "explica", 192: "disena", 193: "disena",
               194: "disena"}  # fmt: skip
    referencia = yaml.safe_load(X.CICLOS.read_text(encoding="utf-8"))["ciclos"]
    for n, competencia in paginas.items():
        txt = (V.DESTINO / f"p{n}.txt").read_text(encoding="utf-8")
        trozo = re.search(r"al final del ciclo \S+(.*?)DESEMPEÑOS", txt, re.S)
        ciclo = "VI" if n in (193, 194) else referencia[n]
        assert parecido(trozo.group(1), estandares[competencia, ciclo]["texto"]) > 0.98
    for n in (193, 194):
        txt = (V.DESTINO / f"p{n}.txt").read_text(encoding="utf-8")
        trozo = re.search(r"al final del ciclo \S+(.*?)DESEMPEÑOS", txt, re.S)
        assert parecido(trozo.group(1), estandares["disena", "VII"]["texto"]) < 0.7


def test_trazabilidad_y_resumen_sin_texto(corrida_real):
    r, filas, resumen_texto = corrida_real
    for f in filas:
        assert f["sha256_archivo"] == X.sha256_de(X.RAIZ_REPO / f["archivo"])
        assert f["ocr"]["sha256_registro"] == X.sha256_de(V.OCR_JSON)
        assert [t["archivo"][-8:] for t in f["ocr"]["tsv"]] == [
            f"p{n}.tsv" for n in f["paginas"]
        ]
        for t in f["ocr"]["tsv"]:
            assert t["sha256"] == X.sha256_de(X.RAIZ_REPO / t["archivo"])
    for nombre, entrada in r["entradas"].items():
        assert entrada["sha256"] == X.sha256_de(X.RAIZ_REPO / entrada["archivo"]), (
            nombre
        )
    textos = [f["texto"] for f in filas] + [f["ejemplo"] for f in filas]
    textos += [f["estandar_cneb"]["texto"] for f in filas]
    assert not any(t in resumen_texto for t in textos if t)
