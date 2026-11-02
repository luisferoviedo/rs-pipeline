"""Tests de la revisión de discrepancias de C05, C06 y C08 (D53)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from rs_pipeline import adjudicacion_d52 as A52
from rs_pipeline import adjudicacion_d53 as A
from rs_pipeline import verificacion_presencia_20 as V

RAIZ = Path(__file__).resolve().parents[1]
PRIVADA = RAIZ / "outputs" / "semantico"
TABLAS = RAIZ / "outputs" / "tablas"


def cierre_inventado() -> pd.DataFrame:
    casos = [("A01", "C05"), ("A02", "C05"), ("A03", "C06"), ("A04", "C06")]
    casos += [(f"A{i:02d}", "C08") for i in range(5, 38)]  # hasta 37 casos
    # A01 y A02 ya estaban en 0; A03 quedó en «revisar»; el resto en 0 por D52
    decision = ["claude", "claude", "revisar"] + [A52.REGLA] * 34
    return pd.DataFrame(
        {
            "caso": [c[0] for c in casos],
            "criterio": [c[1] for c in casos],
            "decision": decision,
            "codigo_final": ["0", "0", ""] + ["0"] * 34,
            "razon": "",
        }
    )


def test_revisar_pasa_a_cero_y_lo_demas_no_cambia():
    entrada = cierre_inventado()
    hoja = A.aplicar(entrada).set_index("caso")
    assert hoja.loc["A03", ["decision", "codigo_final"]].tolist() == [A.DECISION, "0"]
    assert hoja.loc["A01", "decision"] == "claude"
    assert hoja.loc["A04", "decision"] == A52.REGLA
    assert hoja.loc["A01", "nota_d53"] == A.NOTAS["A01"]
    assert hoja.loc["A04", "nota_d53"] == A.NOTAS["A04"]
    assert entrada.loc[2, "decision"] == "revisar"  # no modifica la entrada


def test_falla_si_no_son_37_casos():
    with pytest.raises(A.ErrorPipeline):
        A.aplicar(cierre_inventado().head(4))


def test_prevalencia_con_cuentas_a_mano():
    # 20 informes, Luis Fer marcó C05 en 19; 9 adjudicados a 0 → 10/20
    cierre = pd.DataFrame({"criterio": ["C05"] * 9, "codigo_final": ["0"] * 9})
    luis = pd.DataFrame({"C05": ["1"] * 19 + ["0"], "C06": ["1"] * 17 + ["0"] * 3})
    luis["C08"] = "1"
    tabla = A.prevalencias(cierre, luis).set_index("criterio")
    assert tabla.loc["C05", "n_final"] == 10
    assert tabla.loc["C05", "prevalencia_final"] == 0.5
    assert tabla.loc["C06", "n_final"] == 17  # sin casos adjudicados no cambia


def test_salidas_reales_cuadran():
    cierre = pd.read_csv(
        PRIVADA / A52.CIERRE, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    assert len(cierre) == 37
    assert set(cierre["codigo_final"]) == {"0"}
    assert not (cierre["decision"] == "revisar").any()
    assert (cierre["decision"] == A.DECISION).sum() == 15
    assert set(cierre.loc[cierre["nota_d53"] != "", "caso"]) == set(A.NOTAS)
    tabla = pd.read_csv(TABLAS / f"{A.SALIDA}.csv").set_index("criterio")
    luis = V.leer_luis(PRIVADA)
    for c in V.VERIFICADOS:
        desacuerdos = (cierre["criterio"] == c).sum()
        assert tabla.loc[c, "casos_adjudicados_a_0"] == desacuerdos
        assert tabla.loc[c, "n_final"] == luis[c].astype(int).sum() - desacuerdos
    # coincide con la prevalencia mínima de D52 (todo lo dudoso quedó en 0)
    d52 = pd.read_csv(TABLAS / "calibracion_presencia_20.csv").set_index("criterio")
    assert (tabla["prevalencia_final"] == d52["prevalencia_final_minima"]).all()
    traza = json.loads((TABLAS / f"{A.SALIDA}.json").read_text("utf-8"))
    assert traza["casos_adjudicados_a_0"] == 37


def test_d52_no_pisa_un_cierre_con_revision_d53(tmp_path):
    ruta = tmp_path / A52.CIERRE
    A52.comprobar_cierre(ruta)  # no existe: no falla
    pd.DataFrame({"nota_d53": ["", ""]}).to_csv(ruta, index=False)
    A52.comprobar_cierre(ruta)  # sin revisión: se puede regenerar
    pd.DataFrame({"nota_d53": ["", "nota"]}).to_csv(ruta, index=False)
    with pytest.raises(A52.ErrorPipeline):
        A52.comprobar_cierre(ruta)
