"""Tests de descriptivos_03: tablas contra la matriz normalizada y el Drive."""

import json
import shutil

import pandas as pd
import pytest

from rs_pipeline import descriptivos_03, normalizar_01, prisma_02

UNICAS = [
    "anio", "anio_quinquenio", "idioma", "disciplina", "mmat_categoria",
    "oe1_direccion",
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
def test_cada_tabla_de_categoria_unica_suma_201(carpeta, nombre):
    tabla = leer(carpeta, nombre)
    assert tabla["n_informes"].sum() == 201
    assert abs(tabla["pct_informes"].sum() - 100) < 0.5


def test_las_tablas_de_estudio_suman_198(carpeta):
    disciplina = leer(carpeta, "disciplina")
    assert disciplina["n_estudios"].sum() == 198
    assert disciplina["n_informes"].sum() - disciplina["n_estudios"].sum() == 3


def test_conteos_reales_de_cada_tabla(carpeta):
    assert leer(carpeta, "idioma").set_index("idioma")["n_informes"].to_dict() == {
        "inglés": 159, "español": 35, "portugués": 7,
    }
    anio = leer(carpeta, "anio").set_index("anio")["n_informes"].to_dict()
    assert anio == {2020: 2, 2021: 44, 2022: 31, 2023: 32, 2024: 36, 2025: 33, 2026: 23}
    mmat = leer(carpeta, "mmat_categoria").set_index("categoria")
    assert mmat.loc["3 no aleatorizado", "n_pre_post_un_grupo"] == 83
    assert mmat["n_pre_post_un_grupo"].sum() == 83
    herramientas = leer(carpeta, "herramientas").set_index("herramienta")
    assert herramientas["n_informes"].to_dict() == {
        "simulación interactiva": 137, "laboratorio virtual": 54, "móvil": 4,
        "realidad virtual/aumentada": 3, "otro": 8,
    }
    assert herramientas.loc["simulación interactiva", "n_estudios"] == 134
    resultados = leer(carpeta, "resultados").set_index("resultado")["n_informes"]
    assert resultados.to_dict() == {
        "conceptual": 160, "indagación/habilidades": 71,
        "actitud/motivación": 120, "otro": 31,
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
    for nombre in [*UNICAS, "herramientas", "resultados", "disciplina_x_herramienta"]:
        traza = json.loads((carpeta / f"{nombre}.json").read_text(encoding="utf-8"))
        assert "201 informes" in traza["base"]
        assert traza["salida"]["sha256"] == prisma_02.sha256(carpeta / f"{nombre}.csv")
        assert len(traza["entrada"]["sha256"]) == 64
        entradas = traza["entrada"]["entradas_de_la_matriz"]
        assert any("Extraccion_datos_v2" in ruta for ruta in entradas)
    traza = json.loads((carpeta / "disciplina.json").read_text(encoding="utf-8"))
    assert "198 estudios" in traza["base"]
    anio = json.loads((carpeta / "anio.json").read_text(encoding="utf-8"))
    assert len(anio["informes_con_anio_distinto_al_de_la_base_de_datos"]) == 4


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
