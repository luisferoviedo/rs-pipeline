"""Tests de prisma_02: números reales contra los CSV del Drive (RS_DRIVE_ROOT)."""

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
        "sin_acceso": 120,
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
