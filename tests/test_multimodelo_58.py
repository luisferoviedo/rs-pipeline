"""Tests del paquete ciego de D58 (paso A): muestra, orden, fichas y destino."""

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from rs_pipeline import multimodelo_58 as M
from rs_pipeline.codificacion_claude import hash_ficha

RAIZ = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ / "config" / "d58.yaml").read_text(encoding="utf-8"))
PARAMS = yaml.safe_load((RAIZ / "config" / "params.yaml").read_text(encoding="utf-8"))
CAMPOS = PARAMS["codificacion"]["campos_ficha"]


def test_muestra_falla_con_repetidos_o_tamano_distinto():
    c40 = pd.DataFrame({"id_ciego": ["M01", "M02"], "id": ["R1", "R2"]})
    c20 = pd.DataFrame({"id_ciego": ["V01"], "id": ["R2"]})
    with pytest.raises(M.ErrorPipeline, match="repetidos"):
        M.muestra_60(c40, c20, 3)
    c20["id"] = ["R3"]
    with pytest.raises(M.ErrorPipeline, match="deben ser 4"):
        M.muestra_60(c40, c20, 4)
    assert len(M.muestra_60(c40, c20, 3)) == 3


def test_asignar_ciegos_falla_si_un_informe_no_esta_entre_los_196():
    muestra = pd.DataFrame(
        {"id": ["R1", "R9"], "origen": ["a", "b"], "id_origen": ["M01", "V01"]}
    )
    c196 = pd.DataFrame({"id_ciego": ["T1", "T2"], "id": ["R1", "R2"]})
    with pytest.raises(M.ErrorPipeline, match="R9"):
        M.asignar_ciegos(muestra, c196, 1, "X")


def test_asignar_ciegos_es_reproducible_con_la_semilla():
    muestra = pd.DataFrame(
        {"id": [f"R{i}" for i in range(10)], "origen": "a", "id_origen": "M"}
    )
    c196 = pd.DataFrame({"id_ciego": [f"T{i}" for i in range(10)], "id": muestra["id"]})
    a = M.asignar_ciegos(muestra, c196, 7, "X")
    b = M.asignar_ciegos(muestra, c196, 7, "X")
    assert a.equals(b)
    assert list(a["id_ciego"]) == [f"X{i:02d}" for i in range(1, 11)]
    assert (a["id_t"] == a["id"].str.replace("R", "T")).all()


def test_fichas_falla_si_no_coincide_con_el_registro():
    mapa = pd.DataFrame({"id_ciego": ["X01"], "id_t": ["T1"]})
    hoja = pd.DataFrame({"id_ciego": ["T1"], "a": ["texto"], "b": ["otro"]})
    bueno = {"T1": hash_ficha({"a": "texto", "b": "otro"})}
    tabla = M.fichas(mapa, hoja, ["a", "b"], bueno)
    assert list(tabla.columns) == ["id_ciego", "a", "b"]
    with pytest.raises(M.ErrorPipeline, match="no coincide"):
        M.fichas(mapa, hoja, ["a", "b"], {"T1": "otro-hash"})
    with pytest.raises(M.ErrorPipeline, match="faltan columnas"):
        M.fichas(mapa, hoja, ["a", "c"], bueno)


def test_destino_con_lotes_no_se_sobrescribe(tmp_path):
    (tmp_path / "lotes").mkdir()
    (tmp_path / "lotes" / "lote1.csv").write_text("x")
    with pytest.raises(M.ErrorPipeline, match="no se sobrescribe"):
        M.exigir_destino_libre(tmp_path)
    with pytest.raises(M.ErrorPipeline, match="No existe"):
        M.exigir_destino_libre(tmp_path / "no_existe")


def test_paquete_real(tmp_path):
    """Archivos reales: 60 = 40 + 20, 3 lotes de 20, fichas como en la original."""
    cfg = dict(CFG)
    cfg["salidas"] = {
        "correspondencia": str(tmp_path / "corr.csv"),
        "manifiesto": str(tmp_path / "man.json"),
    }
    destino = tmp_path / "paquete"
    destino.mkdir()
    m = M.preparar(destino, cfg, PARAMS)
    assert m["n_informes"] == 60
    assert m["por_origen"] == {"calibracion_40": 40, "verificacion_20": 20}
    assert [len(x["ids"]) for x in m["paquete"]["lotes"]] == [20, 20, 20]
    corr = pd.read_csv(tmp_path / "corr.csv", dtype=str, encoding="utf-8-sig")
    assert corr["id"].is_unique and corr["id_t"].is_unique and len(corr) == 60
    for n in (1, 2, 3):
        ruta = destino / "lotes" / f"lote{n}.csv"
        lote = pd.read_csv(ruta, dtype=str, encoding="utf-8-sig")
        assert list(lote.columns) == ["id_ciego", *CAMPOS]  # sin códigos ni notas
        assert len(lote) == 20
    libro = M.S.sha256(destino / "libro_codigos_v3.md")
    assert libro == CFG["libro"]["markdown_sha256"]
    texto = json.dumps(m, ensure_ascii=False)
    assert "R0" not in texto  # el manifiesto no trae ids reales ni texto de fichas
