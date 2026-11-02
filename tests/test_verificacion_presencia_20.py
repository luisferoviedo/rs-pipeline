"""Tests de la verificación de C05, C06 y C08 en 20 informes (D51)."""

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from rs_pipeline import verificacion_presencia_20 as V

RAIZ = Path(__file__).resolve().parents[1]
PRIVADA = RAIZ / "outputs" / "semantico"
TABLAS = RAIZ / "outputs" / "tablas"


def leer(nombre: str) -> pd.DataFrame:
    return pd.read_csv(
        PRIVADA / nombre, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )


def test_cruce_con_datos_inventados():
    c20 = pd.DataFrame({"id_ciego": ["V01", "V02"], "id": ["R2", "R9"]})
    c196 = pd.DataFrame({"id_ciego": ["T1", "T2"], "id": ["R2", "R5"]})
    with pytest.raises(V.ErrorPipeline):  # tamaños distintos de 20 y 196
        V.cruzar_ids(c20, c196)


def test_cruce_falla_si_un_informe_no_esta_entre_los_196(monkeypatch):
    monkeypatch.setattr(V, "N_VERIFICACION", 2)
    monkeypatch.setattr(V, "N_TOTAL", 2)
    c20 = pd.DataFrame({"id_ciego": ["V01", "V02"], "id": ["R2", "R9"]})
    c196 = pd.DataFrame({"id_ciego": ["T1", "T2"], "id": ["R2", "R5"]})
    with pytest.raises(V.ErrorPipeline, match="R9"):
        V.cruzar_ids(c20, c196)
    c20["id"] = ["R2", "R5"]
    assert V.cruzar_ids(c20, c196) == {"V01": "T1", "V02": "T2"}


def test_los_20_reales_estan_entre_los_196():
    cruce = V.cruzar_ids(leer(V.CORRESPONDENCIA_20), leer(V.CORRESPONDENCIA_196))
    assert len(cruce) == 20 and len(set(cruce.values())) == 20


def test_salida_publicada_cuadra_con_los_codigos_fuente():
    params = yaml.safe_load((RAIZ / "config/params.yaml").read_text(encoding="utf-8"))
    r = V.calcular(params)
    publicada = pd.read_csv(TABLAS / "verificacion_presencia_20.csv")
    assert list(publicada["criterio"]) == V.VERIFICADOS
    luis = leer(V.ARCHIVO_LUIS).set_index("id_ciego")
    n_desacuerdos = r["tabla"]["n"] - r["tabla"]["n_acuerdos"]
    for c, esperado in zip(V.VERIFICADOS, n_desacuerdos, strict=True):
        fila = publicada.set_index("criterio").loc[c]
        assert fila["n_acuerdos"] == 20 - esperado
        assert fila["prevalencia_luis"] == pytest.approx((luis[c] == "1").mean())
        assert fila["veredicto"] == (
            "validado" if fila["ac1_gwet"] >= 0.60 else "adjudicar"
        )
    assert len(r["desacuerdos"]) == int(n_desacuerdos.sum())
    traza = json.loads((TABLAS / "verificacion_presencia_20.json").read_text("utf-8"))
    assert (
        sorted(traza["criterios_validados"] + traza["criterios_a_adjudicar"])
        == V.VERIFICADOS
    )


def test_hoja_de_adjudicacion_no_pisa_decisiones(tmp_path):
    d = pd.DataFrame(
        {
            "id_ciego": ["V01"],
            "criterio": ["C05"],
            "codigo_luisfer": [1],
            "codigo_claude": [0],
            "justificacion_claude": ["x"],
        }
    )
    traza = {"criterios_a_adjudicar": ["C05"]}
    ruta = tmp_path / "adj.csv"
    V.guardar_hoja_adjudicacion(ruta, d, traza)
    assert (
        pd.read_csv(ruta, dtype=str, keep_default_na=False)["codigo_final"].eq("").all()
    )
    hoja = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    hoja["codigo_final"] = "1"
    hoja.to_csv(ruta, index=False)
    with pytest.raises(V.ErrorPipeline):
        V.guardar_hoja_adjudicacion(ruta, d, traza)
