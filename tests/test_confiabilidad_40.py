"""Tests de la confiabilidad de la muestra de 40 (D48)."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from rs_pipeline import confiabilidad_40 as C

RAIZ = Path(__file__).resolve().parents[1]
TABLAS = RAIZ / "outputs" / "tablas"


def test_ac1_con_cuenta_a_mano():
    # a=[0,1,2,2], b=[0,2,2,1]: acuerdo 0,5; pi = (1/4, 1/4, 1/2);
    # pe = (3/16 + 3/16 + 4/16) / 2 = 5/16; AC1 = (1/2 - 5/16) / (11/16) = 3/11
    assert C.ac1_gwet([0, 1, 2, 2], [0, 2, 2, 1]) == pytest.approx(3 / 11)
    assert C.ac1_gwet([0, 1, 2, 1], [0, 1, 2, 1]) == pytest.approx(1.0)
    # todo en una categoría: pe = 0 y el AC1 vale 1 (el kappa, en cambio, es NaN)
    assert C.ac1_gwet([1, 1, 1], [1, 1, 1]) == pytest.approx(1.0)


def test_veredicto_por_umbrales():
    assert "156 restantes" in C.veredicto(0.60)
    assert "revisar" in C.veredicto(0.599)
    assert "revisar" in C.veredicto(0.40)
    assert "replantea" in C.veredicto(0.399)


def test_fila_cuenta_distribuciones_y_sentido():
    f = C.fila("X", [0, 1, 2, 2], [0, 2, 2, 1])
    assert (f["n_acuerdos"], f["luis_2"], f["claude_2"]) == (2, 2, 2)
    assert f["claude_mayor"] == 1
    assert (f["claude_menor"], f["media_luis"], f["media_claude"]) == (1, 1.25, 1.25)


def test_salidas_publicadas_cuadran_con_los_codigos_fuente():
    traza = json.loads((TABLAS / "confiabilidad_40.json").read_text(encoding="utf-8"))
    tabla = pd.read_csv(TABLAS / "confiabilidad_40.csv")
    assert traza["n_informes"] == 40
    assert list(tabla["criterio"]) == [f"C0{n}" for n in range(1, 10)] + ["TOTAL"]
    total = tabla.iloc[-1]
    assert total["n"] == 360
    assert total["kappa_ponderado"] == traza["kappa_total"]
    ic = traza["kappa_total_ic95"]
    assert ic["bajo"] <= traza["kappa_total"] <= ic["alto"]
    # cada codificador reparte sus 360 códigos entre 0, 1 y 2
    assert tabla.iloc[-1][["luis_0", "luis_1", "luis_2"]].sum() == 360
    assert tabla.iloc[-1][["claude_0", "claude_1", "claude_2"]].sum() == 360
    # ninguna columna de la salida de git trae texto de las fichas ni justificaciones
    assert not any("justific" in c or "nota" in c for c in tabla.columns)


def test_kappa_cohen_y_ac1_binarios_con_cuenta_a_mano():
    # a=[0,1,1,0], b=[0,1,0,0]: po=3/4, pe=1/2*1/4+1/2*3/4=1/2 -> kappa=1/2
    assert C.kappa_cohen([0, 1, 1, 0], [0, 1, 0, 0]) == pytest.approx(0.5)
    # pi1=3/8; pe=2*(3/8*5/8)=15/32; AC1=(3/4-15/32)/(17/32)=9/17
    assert C.ac1_gwet([0, 1, 1, 0], [0, 1, 0, 0], C.BINARIAS) == pytest.approx(9 / 17)
    assert math.isnan(C.kappa_cohen([1, 1, 1], [1, 1, 1]))
    assert C.a_presencia([0, 1, 2]) == [0, 1, 1]


def test_presencia_publicada_cuadra_con_la_tabla_de_codigos():
    traza = json.loads(
        (TABLAS / "confiabilidad_40_presencia.json").read_text(encoding="utf-8")
    )
    tabla = pd.read_csv(TABLAS / "confiabilidad_40_presencia.csv")
    d48 = pd.read_csv(TABLAS / "confiabilidad_40.csv").iloc[-1]
    assert traza["atribucion"] == {
        "codigos_2_luis": int(d48["luis_2"]),
        "codigos_2_claude": int(d48["claude_2"]),
        "codigos_total": 360,
    }
    por_criterio = tabla[tabla["criterio"] != "TOTAL"]
    ok = list(por_criterio.loc[por_criterio["ac1_gwet"] >= 0.60, "criterio"])
    assert ok == traza["criterios_ac1_ge_060"] == [
        "C01", "C02", "C03", "C04", "C07", "C09"
    ]  # fmt: skip
    assert list(tabla["criterio"])[-1] == "TOTAL"
    assert all((tabla["kappa_ic_bajo"].dropna() <= tabla["kappa_ic_alto"].dropna()))
