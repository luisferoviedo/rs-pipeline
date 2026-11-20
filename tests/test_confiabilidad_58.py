"""Tests de D58, paso C: AC1 de varios codificadores, registro y resultados."""

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from rs_pipeline import confiabilidad_58 as C
from rs_pipeline.codificacion_claude import CRITERIOS
from rs_pipeline.confiabilidad_40 import BINARIAS, ac1_gwet

RAIZ = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ / "config" / "d58.yaml").read_text(encoding="utf-8"))


def test_ac1_varios_con_dos_codificadores_es_el_ac1_de_siempre():
    azar = np.random.default_rng(1)
    for _ in range(20):
        m = azar.integers(0, 2, size=(30, 2))
        esperado = ac1_gwet(m[:, 0].tolist(), m[:, 1].tolist(), BINARIAS)
        assert C.ac1_varios(m) == pytest.approx(esperado)


def test_ac1_varios_con_cuenta_a_mano():
    # pa = (1 + 1 + 1/3 + 1/3) / 4 = 2/3; pi = 6/12 = 0,5; pe = 0,5; AC1 = 1/3
    m = np.array([[1, 1, 1], [0, 0, 0], [1, 1, 0], [1, 0, 0]])
    assert C.ac1_varios(m) == pytest.approx(1 / 3)


def test_veredicto_con_los_umbrales_de_d58():
    assert C.veredicto(0.60) == "robusto"
    assert C.veredicto(0.5999) == "moderado"
    assert C.veredicto(0.40) == "moderado"
    assert C.veredicto(0.3999) == "sensible al modelo"


def _lote(ids, lote=1, codigo=1, modelo="m-1"):
    unos = {c: codigo for c in CRITERIOS}
    just = {c: "una línea" for c in CRITERIOS}
    return {
        "modelo": modelo,
        "lote": lote,
        "informes": {
            i: {"codigos": dict(unos), "justificaciones": dict(just)} for i in ids
        },
    }


def test_leer_lote_valida_informes_codigos_y_modelo(tmp_path):
    ruta = tmp_path / "x_lote1.json"
    ruta.write_text(json.dumps(_lote(["X01", "X02"])), encoding="utf-8")
    assert C.leer_lote(ruta, 1, ["X01", "X02"])["modelo"] == "m-1"
    with pytest.raises(C.ErrorPipeline, match="exactamente"):
        C.leer_lote(ruta, 1, ["X01", "X03"])
    ruta.write_text(json.dumps(_lote(["X01"], codigo=2)), encoding="utf-8")
    with pytest.raises(C.ErrorPipeline, match="permitidos"):
        C.leer_lote(ruta, 1, ["X01"])
    ruta.write_text(json.dumps(_lote(["X01"], modelo=" ")), encoding="utf-8")
    with pytest.raises(C.ErrorPipeline, match="modelo"):
        C.leer_lote(ruta, 1, ["X01"])


def test_registrar_no_reescribe_un_codificador(tmp_path):
    manifiesto = tmp_path / "man.json"
    lotes = [{"lote": 1, "ids": ["X01", "X02"]}]
    manifiesto.write_text(json.dumps({"paquete": {"lotes": lotes}}), encoding="utf-8")
    cfg = {
        "codificadores": ["codex"],
        "registro_d58": str(tmp_path / "log.jsonl"),
        "salidas": {"manifiesto": str(manifiesto)},
    }
    lote = json.dumps(_lote(["X01", "X02"]))
    (tmp_path / "codex_lote1.json").write_text(lote, encoding="utf-8")
    assert C.registrar(tmp_path, "codex", cfg) == 2
    with pytest.raises(C.ErrorPipeline, match="ya está registrado"):
        C.registrar(tmp_path, "codex", cfg)
    with pytest.raises(C.ErrorPipeline, match="no es uno"):
        C.registrar(tmp_path, "otro", cfg)


def test_resultados_publicados_coinciden_con_los_codigos_fuente():
    publicado = RAIZ / f"{CFG['resultados']}.json"
    if not publicado.is_file():
        pytest.skip("D58 aún no tiene resultados publicados")
    filas = json.loads(publicado.read_text(encoding="utf-8"))["filas"]
    assert C.calcular(CFG) == filas
