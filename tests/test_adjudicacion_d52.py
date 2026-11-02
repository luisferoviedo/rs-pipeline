"""Tests del cierre de la adjudicación con la definición estricta (D52)."""

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from rs_pipeline import adjudicacion_d52 as A

RAIZ = Path(__file__).resolve().parents[1]
PRIVADA = RAIZ / "outputs" / "semantico"
TABLAS = RAIZ / "outputs" / "tablas"


def lector_inventado() -> pd.DataFrame:
    filas = [
        ("A01", "C05", "La medición de la temperatura"),  # decidido por Luis Fer
        ("A03", "C05", "La medición de la temperatura"),  # medi- → revisar
        ("A04", "C05", "Los estudiantes exploran y observan"),  # sin término → 0
        ("A05", "C06", "Retroalimentación automática del sistema"),
        ("A06", "C06", "Hay retroalimentación del docente"),  # no es automática → 0
        ("A07", "C08", "Compara con el valor teórico"),
        ("A08", "C08", "Mediano plazo"),  # «medi-» es de C05, no de C08 → 0
    ]
    return pd.DataFrame(
        {
            "caso": [f[0] for f in filas],
            "id_ciego": "V01",
            "criterio": [f[1] for f in filas],
            "tema": [f[2] for f in filas],
            "nivel_norm": "media",  # «media» no debe contar como «medi-»
            "decision": "",
            "item_cuenta": "",
            "razon": "",
        }
    )


def test_clasificacion_con_datos_inventados():
    hoja = A.cerrar(lector_inventado()).set_index("caso")
    assert hoja.loc["A01", ["decision", "codigo_final"]].tolist() == ["claude", "0"]
    assert hoja.loc["A03", "decision"] == "revisar"
    assert hoja.loc["A03", "item_cuenta"] == "medi-"
    assert hoja.loc["A03", "codigo_final"] == ""
    assert hoja.loc["A05", "item_cuenta"] == "retroaliment- automática"
    for caso in ("A04", "A06", "A08"):
        assert hoja.loc[caso, ["decision", "codigo_final"]].tolist() == [A.REGLA, "0"]
    assert hoja.loc["A07", "item_cuenta"] == "compar-"


def test_retroalimentacion_automatica_en_cualquier_orden():
    patron = A.TERMINOS["C06"]["retroaliment- automática"]
    for texto in ("retroalimentación automática", "automática y retroalimentación"):
        assert re.search(patron, A._sin_tildes(texto))
    assert not re.search(patron, A._sin_tildes("retroalimentación del docente"))


def test_salidas_reales_cuadran():
    traza = json.loads((TABLAS / "calibracion_presencia_20.json").read_text("utf-8"))
    tabla = pd.read_csv(TABLAS / "calibracion_presencia_20.csv")
    cierre = pd.read_csv(
        PRIVADA / A.CIERRE, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    revisar = pd.read_csv(
        PRIVADA / A.REVISAR, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    lector = pd.read_csv(
        PRIVADA / A.LECTOR, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    assert len(cierre) == 37 and list(cierre["caso"]) == list(lector["caso"])
    assert list(revisar.columns) == list(lector.columns)
    assert (revisar["decision"] == "revisar").all()
    assert len(revisar) == traza["casos_a_revisar"] == tabla["a_revisar"].sum()
    assert traza["casos_a_revisar"] + traza["casos_decididos_a_0"] == 37
    assert set(cierre.loc[cierre["decision"] != "revisar", "codigo_final"]) == {"0"}
    # el lector del investigador no se toca: sigue sin decisiones
    assert (lector["decision"] == "").all()
    assert (
        tabla["prevalencia_final_minima"] <= tabla["prevalencia_final_maxima"]
    ).all()
    assert (
        tabla["n_amplia_investigador"] - tabla["desacuerdos"]
        == tabla["prevalencia_final_minima"] * 20
    ).all()


def test_no_pisa_decisiones_del_investigador(tmp_path):
    ruta = tmp_path / A.REVISAR
    A.comprobar_revisar(ruta)  # no existe: no falla
    pd.DataFrame({"decision": ["revisar"]}).to_csv(ruta, index=False)
    A.comprobar_revisar(ruta)  # sin cambios: se puede regenerar
    pd.DataFrame({"decision": ["claude"]}).to_csv(ruta, index=False)
    with pytest.raises(A.ErrorPipeline):
        A.comprobar_revisar(ruta)
