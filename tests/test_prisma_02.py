"""Tests de prisma_02: números reales contra los CSV del Drive (RS_DRIVE_ROOT)."""

import json

import pandas as pd
import pytest

from rs_pipeline import prisma_02


@pytest.fixture(scope="module")
def params():
    return prisma_02.cargar_params()


@pytest.fixture(scope="module")
def resultado():
    return prisma_02.calcular()


@pytest.fixture(scope="module")
def entradas(params):
    return prisma_02.cargar_entradas(params)


def test_cada_etapa_suma_con_la_siguiente(resultado):
    for regla, esperado, obtenido in resultado["cascada"]:
        assert esperado == obtenido, regla


def test_conteos_recalculados_igualan_al_json(resultado):
    for nombre, calculado, declarado in resultado["filas"]:
        assert calculado == declarado, nombre
    assert not prisma_02.hay_diferencias(resultado)


def test_desglose_de_los_137_no_recuperados(resultado):
    assert resultado["desglose_no_recuperados"] == {
        "sin_acceso": 119,
        "duplicado": 1,
        "pdf_otro_documento": 15,
        "incompletos_ilegibles": 2,
    }
    assert resultado["calculado"]["no_recuperados"] == 137
    assert len(resultado["ids"]["sin_fila_con_pdf"]) == 5


def test_un_conteo_distinto_se_detecta(entradas, resultado):
    cribado = entradas["cribado"].copy()
    cribado.loc[cribado["decision"] == "E1", "decision"] = "E2"
    alterado = dict(resultado)
    alterado["calculado"] = resultado["calculado"] | prisma_02.contar_cribado(cribado)
    alterado["filas"] = prisma_02.filas_comparacion(
        alterado["calculado"], resultado["declarado"]
    )
    assert prisma_02.hay_diferencias(alterado)


def test_reclasificacion_que_no_coincide_falla(tmp_path):
    cribado = pd.DataFrame({"id_revision": ["R0001"], "decision": ["I"]})
    ruta = tmp_path / "reclas.yaml"
    ruta.write_text(
        "reclasificaciones:\n  - {id_revision: R0001, de: D, a: E2}\n",
        encoding="utf-8",
    )
    with pytest.raises(prisma_02.ErrorPipeline, match="R0001"):
        prisma_02.aplicar_reclasificaciones(cribado, ruta)


def test_sin_variable_del_drive_falla(monkeypatch, tmp_path):
    monkeypatch.delenv("RS_DRIVE_ROOT", raising=False)
    monkeypatch.setattr(prisma_02, "RAIZ_REPO", tmp_path)
    with pytest.raises(prisma_02.ErrorPipeline, match="RS_DRIVE_ROOT"):
        prisma_02.raiz_drive("RS_DRIVE_ROOT")


def test_ruta_del_drive_inexistente_falla(monkeypatch, tmp_path):
    monkeypatch.setenv("RS_DRIVE_ROOT", str(tmp_path / "no_existe"))
    with pytest.raises(prisma_02.ErrorPipeline, match="no existe"):
        prisma_02.raiz_drive("RS_DRIVE_ROOT")


def test_201_informes_son_198_estudios_con_3_pares(resultado):
    assert resultado["calculado"]["informes_extraccion"] == 201
    assert resultado["calculado"]["incluidos_estudios"] == 198
    assert resultado["pares_estudio"] == [
        ["R0177", "R0188"],
        ["R0844", "R0930"],
        ["R0990", "R1031"],
    ]


def test_los_15_pdf_de_otro_documento_estan_respaldados(entradas, resultado):
    ids = resultado["ids"]["sin_fila_con_pdf"]
    assert set(ids) <= entradas["pdfs_no_corresponde"]
    assert len(entradas["pdfs_no_corresponde"]) == 15


def test_pdf_de_otro_documento_sin_respaldo_falla():
    elegibilidad = pd.DataFrame(
        {"id_revision": ["R0001"], "decision": ["NO_CORRESPONDE"]}
    )
    with pytest.raises(prisma_02.ErrorPipeline, match="R0999"):
        prisma_02.verificar_pdfs_otro_documento(elegibilidad, ["R0999"], {"R0001"})


def test_estudio_compartido_con_un_informe_ausente_falla():
    extraccion = pd.DataFrame(
        {"id": ["R0001", "R0002"], "estudio_compartido_con": ["R0777", ""]}
    )
    with pytest.raises(prisma_02.ErrorPipeline, match="R0777"):
        prisma_02.contar_estudios(extraccion, set())


def test_registro_agrupa_1227_en_1105_bases_y_122_repositorios(resultado):
    grupos = resultado["identificacion"]["grupos"]
    assert grupos["bases_de_datos"]["n"] == 1105
    assert grupos["repositorios_de_tesis"]["n"] == 122
    assert resultado["identificacion"]["total_registro"] == 1227
    assert resultado["calculado"]["identificados_por_registro"] == 1227


def test_registro_con_total_que_no_suma_falla():
    registro = "**Total identificado:** ERIC 707 · Scopus 345 = **1.000**"
    with pytest.raises(prisma_02.ErrorPipeline, match="no suma"):
        prisma_02.fuentes_del_registro(registro)


def test_fuente_que_no_esta_en_el_registro_falla():
    registro = "**Total identificado:** ERIC 707 · Scopus 345 = **1.052**"
    grupos = {"bases_de_datos": ["ERIC", "Scopus"], "repositorios_de_tesis": ["BDTD"]}
    with pytest.raises(prisma_02.ErrorPipeline, match="BDTD"):
        prisma_02.verificar_identificacion(registro, grupos)


def test_diagrama_en_espanol_con_trazabilidad(params, resultado, tmp_path):
    salidas = prisma_02.generar_diagrama(resultado, params, tmp_path)
    svg = salidas["svg"].read_text(encoding="utf-8")
    for texto in [
        "Registros identificados en:",
        "Bases de datos (n = 1.105)",
        "Repositorios de tesis (n = 122)",
        "Registros excluidos (n = 671)",
        "E4 Tipo de estudio (sin datos empíricos de resultados) (n = 68)",
        "Informes no recuperados (n = 137)",
        "Identificación de estudios a través de bases de datos y repositorios",
        "Sin acceso (n = 119)",
        "Duplicado detectado en la recuperación (n = 1)",
        "PDF de otro documento (n = 15)",
        "Incompletos o ilegibles (n = 2)",
        "Informes excluidos (n = 94)",
        "Informes incluidos (n = 201)",
        "Estudios incluidos (n = 198)",
    ]:
        assert texto in svg, texto
    assert "nuevos estudios" not in svg
    assert 'class="diagram-title"' not in svg  # sin título visible (APA 7)
    assert "<title id=\"title\">Diagrama de flujo PRISMA 2020</title>" in svg
    assert "Records" not in svg
    assert "Reports" not in svg
    png = salidas["png"].read_bytes()
    ancho, alto = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    assert f'width="{ancho / 2:g}" height="{alto / 2:g}"' in svg


def test_trazabilidad_registra_entradas_y_hashes(params, resultado, tmp_path):
    salidas = prisma_02.generar_diagrama(resultado, params, tmp_path)
    traza = json.loads(salidas["json"].read_text(encoding="utf-8"))
    assert traza["conteos_calculados"]["incluidos_estudios"] == 198
    assert "config/reclasificaciones.yaml" in traza["entradas_sha256"]
    entradas = traza["entradas_sha256"]
    assert any(ruta.endswith("prisma_counts_2026-10-26.json") for ruta in entradas)
    for ext in ("svg", "png"):
        archivo = salidas[ext]
        assert traza["salidas_sha256"][archivo.name] == prisma_02.sha256(archivo)


def test_no_se_genera_diagrama_si_hay_diferencias(params, resultado, tmp_path):
    alterado = dict(resultado)
    alterado["filas"] = [("cribados", 1102, 1103)]
    with pytest.raises(prisma_02.ErrorPipeline, match="No se genera"):
        prisma_02.generar_diagrama(alterado, params, tmp_path)
    assert not list(tmp_path.iterdir())
