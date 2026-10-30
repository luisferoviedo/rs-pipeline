"""Tests de normalizar_01: números reales contra la matriz del Drive (RS_DRIVE_ROOT)."""

import json

import pandas as pd
import pytest

from rs_pipeline import normalizar_01, prisma_02


@pytest.fixture(scope="module")
def params():
    return prisma_02.cargar_params()


@pytest.fixture(scope="module")
def resultado(params, tmp_path_factory):
    return normalizar_01.normalizar(params, tmp_path_factory.mktemp("procesados"))


@pytest.fixture(scope="module")
def salida(resultado):
    return pd.read_csv(
        resultado["csv"], dtype=str, keep_default_na=False, encoding="utf-8"
    )


@pytest.fixture(scope="module")
def fuente(params):
    raiz = prisma_02.raiz_drive(params["drive_root_env"])
    ruta = raiz / params["archivos"]["extraccion"]
    return prisma_02.leer_csv(ruta, normalizar_01.COLUMNAS_NECESARIAS, "id")


@pytest.fixture(scope="module")
def reglas_resultado(params):
    ruta = normalizar_01.RAIZ_REPO / params["categorias"]
    return normalizar_01.cargar_categorias(ruta)["oe1_resultado_tipo"]


def cuenta(salida, columna):
    return salida[columna].value_counts().to_dict()


def suma(salida, columna):
    return int((salida[columna] == "1").sum())


def test_se_conservan_las_201_filas_y_las_originales(salida, fuente, resultado):
    assert len(salida) == 201
    e4 = set(resultado["trazabilidad"]["ids_excluidos_e4"])
    assert len(e4) == 18
    esperado = fuente[~fuente["id"].isin(e4)].reset_index(drop=True)
    assert salida[list(fuente.columns)].equals(esperado)
    assert len(fuente) == 219


def test_ningun_valor_sin_mapear_ni_columna_vacia(salida, resultado):
    nuevas = resultado["trazabilidad"]["columnas_nuevas"]
    assert len(nuevas) == 21
    for columna in nuevas:
        if columna.endswith("_norm"):
            assert (salida[columna] != "").all(), columna
    banderas = [c for c in nuevas if c.startswith(("oe1_res_", "oe2_herr_"))]
    for columna in set(banderas) - {"oe1_res_otro_detalle", "oe2_herr_otro_detalle"}:
        assert set(salida[columna]) <= {"0", "1"}, columna
    resultados = ["oe1_res_conceptual", "oe1_res_indagacion_habilidades",
                  "oe1_res_actitud_motivacion", "oe1_res_otro"]
    herramientas = [
        c for c in nuevas if c.startswith("oe2_herr_") and not c.endswith("detalle")
    ]
    assert (salida[resultados].astype(int).sum(axis=1) >= 1).all()
    assert (salida[herramientas].astype(int).sum(axis=1) >= 1).all()


def test_categorias_con_conteos_reales(salida):
    assert cuenta(salida, "disciplina_norm") == {
        "física": 90, "química": 70, "biología": 22,
        "ciencias integradas": 14, "otra": 5,
    }
    assert cuenta(salida, "mmat_categoria_norm") == {
        "3 no aleatorizado": 109, "5 métodos mixtos": 40,
        "2 ensayo aleatorizado": 19, "1 cualitativo": 18,
        "4 cuantitativo descriptivo": 15,
    }
    assert suma(salida, "pre_post_un_grupo") == 83
    assert cuenta(salida, "oe1_direccion_norm") == {
        "no comparativo": 76, "favorable a la simulación": 63, "mixto": 50,
        "sin diferencia": 11,
        "otro (comparación dentro de la misma simulación)": 1,
    }
    assert cuenta(salida, "efecto_aislado") == {"1": 61, "0": 2, "": 138}


def test_efecto_aislado_solo_aplica_a_los_favorables(salida):
    favorables = salida["oe1_direccion_norm"] == "favorable a la simulación"
    assert (salida.loc[favorables, "efecto_aislado"] != "").all()
    assert (salida.loc[~favorables, "efecto_aislado"] == "").all()


def test_herramientas_multietiqueta(salida):
    assert suma(salida, "oe2_herr_simulacion_interactiva") == 137
    assert suma(salida, "oe2_herr_laboratorio_virtual") == 54
    assert suma(salida, "oe2_herr_movil") == 4
    assert suma(salida, "oe2_herr_realidad_virtual_aumentada") == 3
    assert suma(salida, "oe2_herr_otro") == 8
    assert (salida["oe2_herr_otro_detalle"] != "").sum() == 5


def test_resultados_multietiqueta_y_excepciones_aprobadas(salida):
    assert suma(salida, "oe1_res_conceptual") == 160
    assert suma(salida, "oe1_res_indagacion_habilidades") == 71
    assert suma(salida, "oe1_res_actitud_motivacion") == 120
    assert suma(salida, "oe1_res_otro") == 31
    assert suma(salida, "conceptual_autoinforme") == 3
    # La resolución de problemas ya no queda en "otro"
    detalles = " ".join(salida["oe1_res_otro_detalle"])
    assert "resolución" not in detalles
    # La covariable no cuenta: ese informe queda solo con "otro"
    con_ia = salida["oe1_res_otro_detalle"].str.contains("alfabetización en IA")
    solo_otro = salida[con_ia]
    assert len(solo_otro) == 1
    assert solo_otro.iloc[0]["oe1_res_actitud_motivacion"] == "0"


def test_trazabilidad_con_hash_de_la_fuente_y_de_la_salida(resultado, params):
    raiz = prisma_02.raiz_drive(params["drive_root_env"])
    traza = json.loads(resultado["json"].read_text(encoding="utf-8"))
    ruta_fuente = params["archivos"]["extraccion"]
    assert traza["entradas_sha256"][ruta_fuente] == prisma_02.sha256(raiz / ruta_fuente)
    assert traza["salida"]["sha256"] == prisma_02.sha256(resultado["csv"])
    assert "config/categorias.yaml" in traza["entradas_sha256"]
    assert traza["filas_salida"] == 201


def test_un_valor_sin_mapear_hace_fallar():
    serie = pd.Series(["física", "astronomía"])
    with pytest.raises(prisma_02.ErrorPipeline, match="astronomía"):
        normalizar_01.mapear(serie, {"física": "física"}, "disciplina")


def test_una_etiqueta_desconocida_en_resultados_hace_fallar(reglas_resultado):
    with pytest.raises(prisma_02.ErrorPipeline, match="inventada"):
        normalizar_01.etiquetar_resultado("conceptual; inventada (x)", reglas_resultado)


def test_las_reglas_de_excepcion_deben_tocar_los_casos_esperados(reglas_resultado):
    tabla = pd.DataFrame({"oe1_resultado_tipo": ["conceptual", "actitud/motivación"]})
    with pytest.raises(prisma_02.ErrorPipeline, match="en vez de"):
        normalizar_01.cols_resultado(tabla, reglas_resultado)


def test_parentesis_desbalanceados_hacen_fallar():
    with pytest.raises(prisma_02.ErrorPipeline, match="paréntesis"):
        normalizar_01.dividir_fuera_de_parentesis("conceptual) ; otro", ";")


def test_pais_normalizado(salida):
    paises = cuenta(salida, "pais_norm")
    assert len(paises) == 51
    assert paises["Colombia"] == 26 and paises["Estados Unidos"] == 25
    assert paises["Turquía"] == 9
    assert sum(paises.values()) == 201
    # R1006: el artículo escribe "Nicosia, Turkey"; Nicosia está en Chipre (D26)
    assert salida.loc[salida["id"] == "R1006", "pais_norm"].iloc[0] == "Chipre"
    varios = salida.loc[salida["pais_norm"] == "varios países", "id"]
    assert sorted(varios) == ["R0047", "R1091"]


def test_nivel_segun_el_texto_y_marca_de_revision(salida):
    assert cuenta(salida, "nivel_norm") == {
        "media": 95, "secundaria básica": 46, "primer año universitario": 32,
        "universitario: 2.º año o superior": 13, "mixto": 6,
        "universitario: año no reportado": 5, "formación docente": 3,
        "secundaria (sin precisar)": 1,
    }
    en_revision = salida[salida["nivel_en_revision"] == "1"]
    assert len(en_revision) == 32
    assert cuenta(en_revision, "nivel_norm") == {
        "universitario: 2.º año o superior": 13, "primer año universitario": 9,
        "universitario: año no reportado": 5, "formación docente": 3, "mixto": 2,
    }
    assert {"R0263", "R0416"} <= set(en_revision["id"])
    dudosos = set(salida.loc[salida["nivel_dudoso"] == "1", "id"])
    assert dudosos == {"R0280", "R0064", "R0453", "R0597", "R0870", "R0416"}
    # el texto manda: R0115 dice "en realidad segundo año"
    nivel = salida.set_index("id")["nivel_norm"]
    assert nivel["R0115"] == "universitario: 2.º año o superior"
