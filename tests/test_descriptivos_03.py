"""Tests de descriptivos_03: tablas contra la matriz normalizada y el Drive."""

import json
import shutil

import pandas as pd
import pytest

from rs_pipeline import descriptivos_03, normalizar_01, prisma_02

UNICAS = [
    "anio", "anio_quinquenio", "idioma", "pais", "nivel", "disciplina",
    "mmat_categoria", "oe1_direccion",
]


@pytest.fixture(scope="module")
def params():
    return prisma_02.cargar_params()


@pytest.fixture(scope="module")
def carpeta(params, tmp_path_factory):
    # La matriz normalizada se regenera desde el Drive antes de medir sus tablas.
    procesados = descriptivos_03.RAIZ_REPO / params["salidas"]["procesados"]
    normalizar_01.normalizar(params, procesados)
    destino = tmp_path_factory.mktemp("tablas")
    descriptivos_03.generar(params, destino)
    return destino


def leer(carpeta, nombre):
    return pd.read_csv(carpeta / f"{nombre}.csv", encoding="utf-8")


@pytest.mark.parametrize("nombre", UNICAS)
def test_cada_tabla_de_categoria_unica_suma_196(carpeta, nombre):
    tabla = leer(carpeta, nombre)
    assert tabla["n_informes"].sum() == 196
    # cada porcentaje se redondea a 1 decimal: el error máximo es 0,05 por fila
    assert abs(tabla["pct_informes"].sum() - 100) <= 0.05 * len(tabla)


def test_las_tablas_de_estudio_suman_193(carpeta):
    disciplina = leer(carpeta, "disciplina")
    assert disciplina["n_estudios"].sum() == 193
    assert disciplina["n_informes"].sum() - disciplina["n_estudios"].sum() == 3


def test_conteos_reales_de_cada_tabla(carpeta):
    assert leer(carpeta, "idioma").set_index("idioma")["n_informes"].to_dict() == {
        "inglés": 155, "español": 34, "portugués": 7,
    }
    anio = leer(carpeta, "anio").set_index("anio")["n_informes"].to_dict()
    # año de la base de datos (D24); el año APA queda en cita_apa
    assert anio == {2021: 46, 2022: 31, 2023: 33, 2024: 33, 2025: 31, 2026: 22}
    mmat = leer(carpeta, "mmat_categoria").set_index("categoria")
    assert mmat.loc["3 no aleatorizado", "n_pre_post_un_grupo"] == 82
    assert mmat["n_pre_post_un_grupo"].sum() == 82
    herramientas = leer(carpeta, "herramientas").set_index("herramienta")
    assert herramientas["n_informes"].to_dict() == {
        "simulación interactiva": 134, "laboratorio virtual": 52, "móvil": 4,
        "realidad virtual/aumentada": 2, "otro": 7,
    }
    assert herramientas.loc["simulación interactiva", "n_estudios"] == 131
    resultados = leer(carpeta, "resultados").set_index("resultado")["n_informes"]
    assert resultados.to_dict() == {
        "conceptual": 155, "indagación/habilidades": 69,
        "actitud/motivación": 116, "otro": 30,
    }


def test_el_cruce_es_coherente_con_las_otras_tablas(carpeta):
    cruce = leer(carpeta, "disciplina_x_herramienta")
    por_herramienta = cruce.groupby("herramienta")["n_informes"].sum()
    herramientas = leer(carpeta, "herramientas").set_index("herramienta")["n_informes"]
    assert por_herramienta.to_dict() == herramientas.to_dict()
    bases = cruce.groupby("disciplina")["base_disciplina_informes"].first()
    disciplina = leer(carpeta, "disciplina").set_index("disciplina")["n_informes"]
    assert bases.to_dict() == disciplina.to_dict()
    assert (cruce["n_estudios"] <= cruce["n_informes"]).all()


def test_cada_tabla_tiene_su_json_con_base_y_hashes(carpeta):
    todas = [*UNICAS, "herramientas", "resultados", "disciplina_x_herramienta"]
    for nombre in todas:
        traza = json.loads((carpeta / f"{nombre}.json").read_text(encoding="utf-8"))
        assert "196 informes" in traza["base"]
        assert traza["salida"]["sha256"] == prisma_02.sha256(carpeta / f"{nombre}.csv")
        assert len(traza["entrada"]["sha256"]) == 64
        entradas = traza["entrada"]["entradas_de_la_matriz"]
        assert any("Extraccion_datos_v2" in ruta for ruta in entradas)
    traza = json.loads((carpeta / "disciplina.json").read_text(encoding="utf-8"))
    assert "193 estudios" in traza["base"]
    anio = json.loads((carpeta / "anio.json").read_text(encoding="utf-8"))
    assert len(anio["informes_con_cita_apa_de_otro_anio"]) == 4


def test_una_matriz_modificada_hace_fallar(params, tmp_path, monkeypatch):
    origen = descriptivos_03.RAIZ_REPO / params["salidas"]["procesados"]
    nombre = normalizar_01.nombre_matriz(params)
    (tmp_path / "data").mkdir()
    carpeta_copia = tmp_path / "data" / "processed"
    carpeta_copia.mkdir()
    for ruta in (origen / nombre, (origen / nombre).with_suffix(".json")):
        shutil.copy(ruta, carpeta_copia / ruta.name)
    with (carpeta_copia / nombre).open("a", encoding="utf-8") as archivo:
        archivo.write("\n")
    monkeypatch.setattr(descriptivos_03, "RAIZ_REPO", tmp_path)
    with pytest.raises(prisma_02.ErrorPipeline, match="cambió"):
        descriptivos_03.cargar_matriz(params)


def test_un_estudio_con_informes_distintos_hace_fallar():
    tabla = pd.DataFrame({"id": ["R1", "R2"], "disciplina_norm": ["física", "química"]})
    estudios = pd.Series(["R1", "R1"])
    with pytest.raises(prisma_02.ErrorPipeline, match="disciplina_norm"):
        descriptivos_03.exigir_atributo_de_estudio(tabla, estudios, ["disciplina_norm"])


def test_un_socio_que_no_es_reciproco_hace_fallar():
    tabla = pd.DataFrame({"id": ["R1", "R2"], "estudio_compartido_con": ["R2", ""]})
    with pytest.raises(prisma_02.ErrorPipeline, match="recíproco"):
        descriptivos_03.asignar_estudios(tabla, 1)


def test_una_cita_sin_anio_hace_fallar():
    tabla = pd.DataFrame({"id": ["R1"], "cita_apa": ["Autor, A. (s. f.). Título."]})
    with pytest.raises(prisma_02.ErrorPipeline, match="R1"):
        descriptivos_03.anios_de_la_cita(tabla)


def test_pais_y_nivel_suman_196_informes_y_193_estudios(carpeta):
    for nombre in ("pais", "nivel", "disciplina"):
        tabla = leer(carpeta, nombre)
        assert tabla["n_informes"].sum() == 196
        assert tabla["n_estudios"].sum() == 193
    pais = leer(carpeta, "pais").set_index("pais")["n_informes"]
    assert pais["Chipre"] == 1 and pais["varios países"] == 2


def test_revision_de_elegibilidad_por_nivel(carpeta, params):
    revision = pd.read_csv(
        carpeta / "revision_elegibilidad_nivel.csv", dtype=str, keep_default_na=False
    )
    assert list(revision.columns) == [
        "id", "cita_apa", "nivel_crudo", "nivel_norm", "fragmento_justificativo",
        "motivo_revision", "decision_luisfer",
    ]
    assert len(revision) == 32
    decision = revision.set_index("id")["decision_luisfer"]
    assert decision.value_counts().to_dict() == {
        "incluir": 27, "excluir E1": 4, "excluir E3": 1
    }
    assert decision["R0295"] == "excluir E3"
    assert {i for i in decision.index if decision[i] == "excluir E1"} == {
        "R0186", "R0720", "R0877", "R0935"
    }
    assert (revision["fragmento_justificativo"] != "").all()
    assert {"R0115", "R0186", "R0015", "R0450"} <= set(revision["id"])
    traza = json.loads(
        (carpeta / "revision_elegibilidad_nivel.json").read_text(encoding="utf-8")
    )
    regla = traza["regla_3_de_elegibilidad"]
    assert regla["texto"].startswith(
        "Se incluyen los estudios con estudiantes de 2.º año universitario"
    )
    assert regla["texto"].endswith("(E1, población).")
    assert "clínico" not in regla["texto"]
    assert "No cambia el PRISMA" in traza["descripcion"]


def test_la_revision_no_cambia_el_prisma(params):
    resultado = prisma_02.calcular(params)
    assert not prisma_02.hay_diferencias(resultado)
    assert resultado["calculado"]["incluidos_informes"] == 196


def test_un_anio_fuera_de_la_ventana_hace_fallar(params, tmp_path):
    ruta = tmp_path / "elegibilidad.csv"
    ruta.write_text("id_revision,anio\nR1,2019\n", encoding="utf-8")
    tabla = pd.DataFrame({"id": ["R1"]})
    with pytest.raises(prisma_02.ErrorPipeline, match="R1"):
        descriptivos_03.anios_de_la_base_de_datos(tabla, ruta, [2021, 2026])


def test_un_anio_ilegible_hace_fallar(tmp_path):
    ruta = tmp_path / "elegibilidad.csv"
    ruta.write_text("id_revision,anio\nR1,s. f.\n", encoding="utf-8")
    tabla = pd.DataFrame({"id": ["R1"]})
    with pytest.raises(prisma_02.ErrorPipeline, match="ilegible"):
        descriptivos_03.anios_de_la_base_de_datos(tabla, ruta, [2021, 2026])


def test_nivel_sin_los_excluidos_por_nivel(carpeta):
    nivel = leer(carpeta, "nivel").set_index("nivel")["n_informes"].to_dict()
    assert nivel == {
        "media": 95, "secundaria básica": 46, "primer año universitario": 31,
        "universitario: 2.º año o superior": 10, "mixto": 6,
        "universitario: año no reportado": 5, "formación docente": 2,
        "secundaria (sin precisar)": 1,
    }


def test_la_base_viene_de_prisma_counts_vigente(carpeta):
    traza = json.loads((carpeta / "nivel.json").read_text(encoding="utf-8"))
    entradas = traza["entrada"]["entradas_de_la_matriz"]
    assert "config/prisma_counts_2026-10-29.json" in entradas
    assert "config/exclusiones_nivel.yaml" in entradas
