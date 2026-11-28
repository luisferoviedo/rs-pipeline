"""Tests de la extracción de los NAP de Argentina (extraccion_ar_09; D60).

Primero con palabras y líneas armadas a mano, para fijar cada regla. Al final, si los
PDF están en el disco, contra los documentos: 74 unidades del ciclo básico y 25 del
orientado, y cada texto visto también en la lectura -layout de pdftotext.
"""

import json
import re
from collections import Counter

import pytest

from rs_pipeline import extraccion_ar_09 as X
from rs_pipeline.semantico_texto import ErrorPipeline


def P(texto: str, x: float, y: float, alto: float = 11.0, ancho: float = 30.0):
    return X.Palabra(texto, x, y, x + ancho, y + alto)


# --- Líneas y notas ----------------------------------------------------------


def test_quita_la_llamada_a_nota_el_encabezado_y_las_notas():
    palabras = [
        P("Ministerio", 45, 110),  # encabezado de la página
        P("ciencia", 85, 200),
        P("escolar", 120, 200),  # termina en x = 150
        P("2", 150.5, 198, alto=7, ancho=4),  # llamada pegada
        P(",", 155, 200, ancho=3),
        P("para", 165, 200),
        P("2", 85, 460, alto=6, ancho=4),  # número de la nota al pie
        P("Nota", 95, 462, alto=9),
    ]
    lineas, numeros = X.lineas_de_pagina(palabras, X.FORMATOS[X.ID_CB], 2)
    assert [x.texto for x in lineas] == ["ciencia escolar, para"]
    assert numeros == [2]


def test_la_puntuacion_sin_llamada_no_se_pega():
    assert X.unir_linea([P("a", 10, 0), P(",", 50, 0)], set()) == "a ,"


# --- Ciclo básico ------------------------------------------------------------


def lineas(*textos: str, pagina: int = 2) -> list:
    return [X.Linea(pagina, 200 + 12 * i, t) for i, t in enumerate(textos)]


CB = (
    "La escuela ofrecerá situaciones en",
    "el Tercer Ciclo:",
    "• La interpretación de",
    "problemas.",
    "7° AÑO",
    "EN RELACIÓN CON LOS SERES VIVOS: DIVERSIDAD, UNIDAD,",
    "INTERRELACIONES Y CAMBIOS",
    "• La caracterización de algo.",
    "I. LOS FENÓMENOS DEL MUNDO FÍSICO",
    "• El empleo de algo.",
    "9° AÑO",
    "La Tierra, el universo y sus cambios",
    "• La interpretación del clima.",
)


def test_cb_asigna_grado_y_eje_a_cada_vineta():
    unidades, entradilla = X.leer_cb(lineas(*CB))
    assert entradilla == "La escuela ofrecerá situaciones en el Tercer Ciclo:"
    assert [(u["grado"], u["eje"]) for u in unidades] == [
        (None, "general"),
        (7, "seres_vivos"),
        (7, "fisicos"),
        (9, "tierra_universo"),
    ]
    assert unidades[0]["lineas"] == ["La interpretación de", "problemas."]


@pytest.mark.parametrize(
    ("textos", "mensaje"),
    [
        ((*CB[:5], "• La caracterización de algo."), "viñeta sin eje"),
        ((*CB[:5], "EN RELACIÓN CON LA ASTRONOMÍA"), "encabezado desconocido"),
        ((*CB[:6], "• La caracterización de algo."), "incompleto"),
        ((*CB[:5], CB[8], "• El empleo.", "8° AÑO", "suelto"), "fuera de toda"),
    ],
)
def test_cb_con_estructura_rota_falla(textos, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.leer_cb(lineas(*textos))


# --- Ciclo orientado ---------------------------------------------------------


def co(*filas: tuple[int, float, str]) -> list:
    return [X.Linea(p, y, t) for p, y, t in filas]


CO = (
    (2, 190, "CIENCIAS NATURALES"),
    (2, 216, "Durante el Ciclo Orientado, la escuela"),
    (2, 228, "promueve:"),
    (2, 253, "La construcción de una visión."),
    (2, 278, "La comprensión del lenguaje"),
    (2, 290, "científico."),
    (4, 205, "BIOLOGÍA"),
    (4, 227, "CICLO ORIENTADO"),
    (4, 254, "EJE: EN RELACIÓN CON LOS PROCESOS EVOLUTIVOS"),
    (4, 279, "La aplicación de los conocimientos y"),
    (5, 190, "el reconocimiento de algo."),
    (7, 190, "FÍSICA"),
    (7, 241, "El análisis de los fenómenos."),
    (9, 190, "QUÍMICA"),
    (9, 240, "EJE: EN RELACIÓN CON LAS PROPIEDADES, ESTRUCTURA Y USOS DE LOS"),
    (9, 252, "MATERIALES"),
    (9, 277, "La explicación de propiedades."),
    (10, 190, "La interpretación cualitativa."),
)


def test_co_separa_parrafos_y_une_el_que_pasa_de_pagina():
    unidades, entradilla = X.leer_co(co(*CO))
    assert entradilla == "Durante el Ciclo Orientado, la escuela promueve:"
    assert [(u["disciplina"], u["eje"], u["paginas"]) for u in unidades] == [
        (None, "general", [2]),
        (None, "general", [2]),
        ("Biología", "procesos_evolutivos", [4, 5]),
        ("Física", None, [7]),
        ("Química", "propiedades_materiales", [9]),
        ("Química", "propiedades_materiales", [10]),
    ]
    assert unidades[1]["lineas"] == ["La comprensión del lenguaje", "científico."]


@pytest.mark.parametrize(
    ("filas", "mensaje"),
    [
        ((*CO[:9], (4, 279, "sin mayúscula inicial.")), "no empieza en mayúscula"),
        ((*CO[:8], (4, 254, "EJE: EN RELACIÓN CON LA NADA")), "desconocido"),
        ((*CO[:15], (9, 277, "La explicación.")), "desconocido o incompleto"),
    ],
)
def test_co_con_estructura_rota_falla(filas, mensaje):
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.leer_co(co(*filas))


# --- Documento y controles ---------------------------------------------------


def paginas_cb(portada="NÚCLEOS DE APRENDIZAJES", llamadas=(1, 2)) -> list:
    cuerpo = [P("texto", 85, 200)]
    x = 115.5
    for n in llamadas:
        cuerpo.append(P(str(n), x, 198, alto=7, ancho=4))
        cuerpo.append(P("más", x + 5, 200))
        x += 35.5
    return [[P(portada, 85, 300)], cuerpo] + [[] for _ in range(9)]


@pytest.mark.parametrize(
    ("paginas", "mensaje"),
    [
        (paginas_cb()[:5], "páginas y se esperaban 11"),
        (paginas_cb(portada="Otra cosa"), "portada"),
        (paginas_cb(llamadas=(1,)), "llamadas a nota"),
    ],
)
def test_documento_distinto_del_esperado_falla(paginas, mensaje):
    X.texto_de_documento(X.ID_CB, paginas_cb())
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.texto_de_documento(X.ID_CB, paginas)


def u(texto: str = "La caracterización de algo.", **campos) -> dict:
    base = {"documento": X.ID_CB, "grado": 7, "disciplina": None, "eje": "fisicos"}
    return base | {"texto": texto, "paginas": [4]} | campos


@pytest.mark.parametrize(
    ("malo", "mensaje"),
    [
        ("La ciencia escolar2 y más.", "número de nota"),
        ("La ciencia escolar , y más.", "signo suelto"),
        ("La nota. Este enunciado sigue.", "restos"),
        ("La nota del Consejo Federal sigue.", "restos"),
        ("La viñeta • La otra viñeta.", "restos"),
        ("La frase cortada sin punto", "cortado"),
        ("de algo que empieza mal.", "cortado"),
    ],
)
def test_controles_de_texto(malo, mensaje):
    X.controlar_textos([u()])
    with pytest.raises(ErrorPipeline, match=mensaje):
        X.controlar_textos([u(malo)])


def test_conteo_distinto_del_piloto_falla(monkeypatch):
    monkeypatch.setattr(X, "ESTRUCTURA_AR", {(X.ID_CB, 7, None, "fisicos"): 2})
    X.controlar_estructura([u(), u()])
    with pytest.raises(ErrorPipeline, match="distintas de las del piloto"):
        X.controlar_estructura([u()])
    with pytest.raises(ErrorPipeline, match="distintas de las del piloto"):
        X.controlar_estructura([u(), u(grado=8)])


def test_vineta_perdida_falla():
    paginas = [[P("•", 85, 200), P("•", 85, 220)]]
    X.controlar_vinetas([u(), u()], paginas)
    with pytest.raises(ErrorPipeline, match="viñetas"):
        X.controlar_vinetas([u()], paginas)


def test_cine_distinto_del_esperado_falla():
    doc = X.documento_del_inventario(X.ID_CB) | {"nivel_cine": [3]}
    with pytest.raises(ErrorPipeline, match="CINE"):
        X.extraer({X.ID_CB: doc})


@pytest.mark.parametrize("existente", ["e.jsonl", "r.json"])
def test_no_sobrescribe_una_extraccion_anterior(tmp_path, existente):
    (tmp_path / existente).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ErrorPipeline, match="no se sobrescribe"):
        X.correr(tmp_path / "e.jsonl", tmp_path / "r.json")
    assert [p.name for p in tmp_path.iterdir()] == [existente]


# --- Contra los PDF reales ---------------------------------------------------


@pytest.fixture(scope="module")
def corrida_real(tmp_path_factory):
    for i in (X.ID_CB, X.ID_CO):
        if not (X.RAIZ_REPO / X.documento_del_inventario(i)["ruta_local"]).is_file():
            pytest.skip("los PDF de Argentina no están en data/raw/curriculo/")
    d = tmp_path_factory.mktemp("extraccion_ar")
    r = X.correr(d / "e.jsonl", d / "r.json")
    texto = (d / "e.jsonl").read_text("utf-8")
    filas = [json.loads(x) for x in texto.splitlines()]
    return r, filas, (d / "r.json").read_text("utf-8")


def test_conteos_reales_por_documento_ano_y_eje(corrida_real):
    r, filas, _ = corrida_real
    cb = [f for f in filas if f["documento"] == X.ID_CB]
    co = [f for f in filas if f["documento"] == X.ID_CO]
    assert (len(cb), len(co), len(filas)) == (74, 25, 99)
    assert len({f["id_unidad"] for f in filas}) == 99
    veces = Counter((f["grado"], f["eje_id"]) for f in cb)
    ejes = ("seres_vivos", "materiales", "fisicos", "tierra_universo")
    assert veces[None, "general"] == 14
    assert [veces[7, e] for e in ejes] == [9, 5, 3, 1]
    assert [veces[8, e] for e in ejes] == [7, 6, 4, 2]
    assert [veces[9, e] for e in ejes] == [6, 7, 5, 5]
    assert Counter((f["disciplina"], f["eje_id"]) for f in co) == {
        (None, "general"): 6,
        ("Biología", "informacion_genetica"): 5,
        ("Biología", "procesos_evolutivos"): 3,
        ("Física", None): 4,
        ("Química", "propiedades_materiales"): 3,
        ("Química", "transformaciones_quimicas"): 4,
    }
    conteo = r["documentos"][X.ID_CB]
    assert (conteo["generales"], conteo["con_marca_de_nivel"]) == (14, 18)


def test_generales_marca_y_cine(corrida_real):
    _, filas, _ = corrida_real
    generales = [f for f in filas if f["eje_id"] == "general"]
    assert len(generales) == 20
    assert all(f["grado"] is None and f["eje"] == "general" for f in generales)
    assert all(f["contexto"] and f["contexto"].endswith(":") for f in generales)
    assert all(f["contexto"] is None for f in filas if f not in generales)
    for f in filas:
        assert f["nivel_cine"] == ([2] if f["documento"] == X.ID_CB else [3])
        marcada = "varía según jurisdicción" if f["grado"] == 7 else None
        assert f["marca_nivel"] == marcada
    assert all(f["grado"] is None for f in filas if f["documento"] == X.ID_CO)


def test_textos_vistos_en_las_paginas(corrida_real):
    _, filas, _ = corrida_real
    por_id = {f["id_unidad"]: f for f in filas}
    assert por_id["AR-NAP-CB:G7.seres_vivos.1"]["texto"] == (
        "La caracterización de la nutrición y su interpretación como conjunto "
        "integrado de funciones en los seres vivos."
    )
    assert por_id["AR-NAP-CB:G8.fisicos.3"]["texto"] == (
        "El análisis de experiencias donde aparecen interrelaciones eléctricas y "
        "magnéticas, por ejemplo con un electroimán."
    )
    # las dos llamadas a nota del CB estaban aquí y en la entradilla
    primera = por_id["AR-NAP-CB:general.1"]
    assert "de la ciencia escolar, para contribuir" in primera["texto"]
    assert primera["contexto"].endswith("Tercer Ciclo de EGB/Nivel Medio:")
    co = por_id["AR-NAP-CO:general.2"]["texto"]
    assert "hipótesis alternativas; que involucren" in co
    assert co.endswith("situaciones de trabajo colaborativo.")
    # errata del original: no se corrige
    assert por_id["AR-NAP-CB:G8.fisicos.4"]["texto"].startswith("Introducción a la")


def test_unidades_que_pasan_de_pagina(corrida_real):
    _, filas, _ = corrida_real
    dos = {f["id_unidad"]: f for f in filas if len(f["paginas"]) > 1}
    assert {k: v["paginas"] for k, v in dos.items()} == {
        "AR-NAP-CB:general.4": [2, 3],
        "AR-NAP-CO:biologia.informacion_genetica.5": [4, 5],
    }
    biologia = dos["AR-NAP-CO:biologia.informacion_genetica.5"]["texto"]
    assert "así como el reconocimiento y análisis de sus implicancias" in biologia


def solo_letras(texto: str) -> str:
    """Sin espacios ni dígitos (las llamadas a nota)."""
    return re.sub(r"[\s\d]", "", texto)


def pagina_layout(doc_id: str, pagina: int) -> str:
    doc = X.documento_del_inventario(doc_id)
    orden = ["pdftotext", "-layout", "-f", str(pagina), "-l", str(pagina)]
    salida = X.ejecutar([*orden, str(X.RAIZ_REPO / doc["ruta_local"]), "-"]).stdout
    return solo_letras(salida)


def test_cada_texto_esta_en_la_lectura_layout(corrida_real):
    _, filas, _ = corrida_real
    paginas: dict[tuple[str, int], str] = {}
    for f in filas:
        trozos = [
            paginas.setdefault((f["documento"], n), pagina_layout(f["documento"], n))
            for n in f["paginas"]
        ]
        texto = solo_letras(f["texto"].replace("•", ""))
        if len(trozos) == 1:
            assert texto in trozos[0].replace("•", ""), f["id_unidad"]
            continue
        # entre las dos páginas quedan las notas y el encabezado: se parte el texto
        palabras = f["texto"].split()
        assert any(
            solo_letras(" ".join(palabras[:k])) in trozos[0]
            and solo_letras(" ".join(palabras[k:])) in trozos[1]
            for k in range(1, len(palabras))
        ), f["id_unidad"]


def test_sin_notas_ni_encabezados(corrida_real):
    _, filas, _ = corrida_real
    # comienzos de notas al pie y de encabezados de los dos documentos
    marcas = ("La alfabetización científica iniciada", "ciencia experta",
              "Las actividades enumeradas", "El trabajo colaborativo favorece",
              "enunciado", "Ministerio", "Antonio Berni", "Documento aprobado",
              "NÚCLEOS", "CICLO ORIENTADO", "EJE:")  # fmt: skip
    for f in filas:
        assert not [m for m in marcas if m in f["texto"]], f["id_unidad"]
        assert not re.search(r"\d", f["texto"]), f["id_unidad"]
    ejes = {f["eje"] for f in filas}
    assert "Los fenómenos del mundo físico" in ejes
    assert not any(e and (e.startswith("I.") or e == e.upper()) for e in ejes)


def test_trazabilidad_y_resumen_sin_texto(corrida_real):
    r, filas, resumen_texto = corrida_real
    for f in filas:
        assert f["sha256_archivo"] == X.sha256_de(X.RAIZ_REPO / f["archivo"])
    assert r["inventario"]["sha256"] == X.sha256_de(X.INVENTARIO)
    assert not any(f["texto"] in resumen_texto for f in filas)
    assert not any(f["contexto"] in resumen_texto for f in filas if f["contexto"])
