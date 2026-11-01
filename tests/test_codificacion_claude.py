"""Tests del registro de Claude Code y del acuerdo con Luis Fer (D45, D46)."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest
import yaml

from rs_pipeline import codificacion_claude as K
from rs_pipeline import semantico_04 as S

RAIZ = Path(__file__).resolve().parents[1]
CRITERIOS = [f"C0{n}" for n in range(1, 10)]
LUIS = {
    "P01": [2, 1, 1, 1, 1, 1, 1, 1, 0],
    "P02": [1, 1, 2, 0, 1, 0, 0, 1, 2],
    "P03": [2, 2, 2, 0, 2, 1, 1, 1, 1],
    "P04": [2, 2, 1, 1, 1, 1, 1, 1, 1],
    "P05": [1, 1, 1, 1, 2, 1, 1, 1, 1],
}


def test_kappa_ponderado_con_cuenta_a_mano():
    # Calculado a mano: sin acuerdo por azar, 1 - 0,5 / 1,375 = 7/11
    assert K.kappa_ponderado([0, 1, 2, 2], [0, 2, 2, 1]) == pytest.approx(7 / 11)
    assert K.kappa_ponderado([0, 1, 2, 1], [0, 1, 2, 1]) == pytest.approx(1.0)
    assert math.isnan(K.kappa_ponderado([1, 1, 1], [1, 1, 1]))


def test_fila_de_acuerdo_y_validacion():
    f = K.fila_de_acuerdo("X", [0, 1, 2, 2], [0, 2, 2, 1])
    assert (f["n_acuerdos"], f["pct_acuerdo"], f["kappa_ponderado"]) == (2, 50.0, 0.636)
    justif = dict.fromkeys(CRITERIOS, "una línea")
    codigos = dict.fromkeys(CRITERIOS, 1)
    K.validar_codificacion("P01", codigos, justif)
    with pytest.raises(K.ErrorPipeline):
        K.validar_codificacion("P01", codigos | {"C03": 3}, justif)
    with pytest.raises(K.ErrorPipeline):
        K.validar_codificacion("P01", codigos, justif | {"C03": "dos\nlíneas"})


def test_registro_solo_agrega(tmp_path):
    ruta = tmp_path / "log.jsonl"
    base = {
        "id_ciego": "P01",
        "codigos": dict.fromkeys(CRITERIOS, 1),
        "justificaciones": dict.fromkeys(CRITERIOS, "x"),
    }
    K.registrar(base | {"fecha": "a"}, ruta)
    K.registrar(base | {"fecha": "b"}, ruta)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["fecha"] for x in lineas] == ["a", "b"]


def test_registro_real_del_piloto():
    libro = RAIZ / "config/libro_codigos_v1.yaml"
    registro = K.leer_registro(RAIZ / "logs/codificacion_claude.jsonl")
    vigentes = K.ultimas_por_informe(registro, S.sha256(libro))
    assert sorted(vigentes) == sorted(LUIS)
    hoja = pd.read_csv(
        RAIZ / "outputs/semantico/hoja_codificacion_piloto.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    ).set_index("id_ciego")
    campos = yaml.safe_load((RAIZ / "config/params.yaml").read_text("utf-8"))
    campos = campos["codificacion"]["campos_ficha"]
    for id_ciego, r in vigentes.items():
        assert r["modelo"] == "claude-sonnet-5-5" and r["fecha"]
        assert list(r["codigos"]) == CRITERIOS
        assert r["sha256_ficha"] == K.hash_ficha(
            {c: hoja.loc[id_ciego, c] for c in campos}
        )
        assert all(r["justificaciones"][c].strip() for c in CRITERIOS)


def test_hoja_tiene_los_codigos_de_luisfer_y_respaldo_sin_codificar():
    privada = RAIZ / "outputs/semantico"
    hoja = pd.read_csv(
        privada / "hoja_codificacion_piloto.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    ).set_index("id_ciego")
    for id_ciego, codigos in LUIS.items():
        assert [int(hoja.loc[id_ciego, c]) for c in CRITERIOS] == codigos
    respaldo = pd.read_csv(
        privada / "hoja_codificacion_piloto_sin_codificar_respaldo.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    assert (respaldo[[*CRITERIOS, "nota"]] == "").all().all()


def test_acuerdo_publicado_se_recalcula():
    luis = [c for ids in LUIS.values() for c in ids]
    registro = K.leer_registro(RAIZ / "logs/codificacion_claude.jsonl")
    libro = S.sha256(RAIZ / "config/libro_codigos_v1.yaml")
    claude = K.ultimas_por_informe(registro, libro)
    mias = [claude[i]["codigos"][c] for i in LUIS for c in CRITERIOS]
    tabla = pd.read_csv(RAIZ / "outputs/tablas/acuerdo_piloto_luisfer_claude.csv")
    total = tabla[tabla["criterio"] == "TOTAL"].iloc[0]
    assert total["n"] == 45
    assert total["n_acuerdos"] == sum(a == b for a, b in zip(luis, mias, strict=True))
    assert len(tabla) == 10


def test_libro_v1_tiene_las_tres_reglas_nuevas_y_v0_no_cambia():
    v1 = yaml.safe_load((RAIZ / "config/libro_codigos_v1.yaml").read_text("utf-8"))
    v0 = yaml.safe_load((RAIZ / "config/libro_codigos_v0.yaml").read_text("utf-8"))
    assert v1["version"] == "v1" and v1["decision"] == "D45"
    assert v1["reglas"][: len(v0["reglas"])] == v0["reglas"]
    assert len(v1["reglas"]) == len(v0["reglas"]) + 3
    assert v1["criterios"] == v0["criterios"] and v1["escala"] == v0["escala"]


def test_lote_exige_exactamente_los_informes_de_la_hoja():
    hoja = pd.DataFrame({"id_ciego": ["M01", "M02"], "tema": ["a", "b"]})
    params = {"codificacion": {"campos_ficha": ["tema"]}}
    libro = RAIZ / "config/libro_codigos_v2.yaml"
    uno = {
        "codigos": dict.fromkeys(CRITERIOS, 1),
        "justificaciones": dict.fromkeys(CRITERIOS, "x"),
    }
    lote = {"modelo": "m", "informes": {"M01": uno, "M02": uno}}
    lineas = K.lineas_del_lote(lote, hoja, libro, params)
    assert [x["id_ciego"] for x in lineas] == ["M01", "M02"]
    assert lineas[0]["sha256_ficha"] == K.hash_ficha({"tema": "a"})
    assert lineas[0]["libro"]["sha256"] == S.sha256(libro)
    with pytest.raises(K.ErrorPipeline):
        K.lineas_del_lote(
            {"modelo": "m", "informes": {"M01": uno}}, hoja, libro, params
        )
    malo = uno | {"codigos": dict.fromkeys(CRITERIOS, 5)}
    with pytest.raises(K.ErrorPipeline):
        K.lineas_del_lote(
            {"modelo": "m", "informes": {"M01": malo, "M02": uno}}, hoja, libro, params
        )


def test_nombre_del_archivo_de_codigos():
    assert K.archivo_de_codigos("hoja_codificacion_40.csv") == "codigos_claude_40.csv"


def test_resumen_numerico_no_trae_codigos():
    r = json.loads(
        (RAIZ / "outputs/tablas/codificacion_claude_resumen.json").read_text("utf-8")
    )
    assert set(r) == {"lineas_en_el_registro", "por_libro"}
    assert all(
        "codigos" not in g and "justificaciones" not in g for g in r["por_libro"]
    )
