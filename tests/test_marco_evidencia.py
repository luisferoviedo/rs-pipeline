"""Tests de la tabla de evidencia del marco (D54)."""

import json
from math import isclose
from pathlib import Path

import pandas as pd
import pytest

from rs_pipeline import criterios_05 as C
from rs_pipeline import marco_evidencia_08 as M

RAIZ = Path(__file__).resolve().parents[1]
PRIVADA = RAIZ / "outputs" / "semantico"
TABLAS = RAIZ / "outputs" / "tablas"


def test_fisher_con_cuentas_a_mano():
    # tabla clásica de la «dama del té»: [[3, 1], [1, 3]] → p bilateral = 34/70
    assert isclose(M.fisher_dos_colas(3, 1, 1, 3), 34 / 70)
    # sin diferencia → p = 1; diferencia total 4/0 vs 0/4 → 2/70
    assert isclose(M.fisher_dos_colas(2, 2, 2, 2), 1.0)
    assert isclose(M.fisher_dos_colas(4, 0, 0, 4), 2 / 70)


def test_fila_de_criterio_con_datos_inventados():
    informes = pd.DataFrame(
        {
            "id": ["R1", "R2", "R3", "R4"],
            "estudio": ["R1", "R1", "R3", "R4"],  # R1 y R2 son el mismo estudio
            "C01": [0, 1, 1, 0],  # el estudio R1 queda presente por R2
        }
    )
    estudios = pd.DataFrame(
        {
            "peso_suma": ["alto", "bajo", "medio"],
            "peso_minimo": ["medio", "bajo", "bajo"],
            "nivel": ["secundaria", "otro", "universitario"],
            "disciplina": ["física", "química", "otra"],
            "direccion": ["favorable", "mixto", "favorable"],
        },
        index=["R1", "R3", "R4"],
    )
    fila = M.fila_de_criterio("C01", informes, estudios)
    assert (fila["n_informes_presentes"], fila["n_informes_ausentes"]) == (2, 2)
    assert (fila["n_estudios_presentes"], fila["n_estudios_ausentes"]) == (2, 1)
    assert fila["suma_alto"] == 1 and fila["suma_bajo"] == 1
    assert fila["pct_suma_alto"] == 50.0
    assert fila["dir_presente_favorable"] == 1 and fila["dir_ausente_favorable"] == 1


def test_falla_si_faltan_los_archivos_de_codigos(tmp_path):
    params = {"semantico": {"salidas": str(tmp_path.relative_to(tmp_path.anchor))}}
    with pytest.raises(M.ErrorPipeline):
        M.leer_presencia(params)  # no existen los archivos


def test_salida_real_cuadra_con_los_codigos():
    tabla = pd.read_csv(TABLAS / f"{M.SALIDA}.csv", index_col="id_criterio")
    assert list(tabla.index) == [f"C0{i}" for i in range(1, 10)]
    assert (tabla["n_informes_total"] == 196).all()
    assert (tabla["n_estudios_total"] == 193).all()
    assert (tabla["n_informes_presentes"] + tabla["n_informes_ausentes"] == 196).all()
    assert (tabla["n_estudios_presentes"] + tabla["n_estudios_ausentes"] == 193).all()
    for regla in ("suma", "minimo"):
        total = sum(tabla[f"{regla}_{e}"] for e in C.ETIQUETAS_PESO)
        assert (total == tabla["n_estudios_presentes"]).all()
    for dim in ("nivel_secundaria nivel_universitario nivel_otro",):
        assert (tabla[dim.split()].sum(axis=1) == tabla["n_estudios_presentes"]).all()
    dirs = [f"dir_presente_{d}" for d in C.DIRECCIONES]
    assert (tabla[dirs].sum(axis=1) == tabla["n_estudios_presentes"]).all()
    dirs = [f"dir_ausente_{d}" for d in C.DIRECCIONES]
    assert (tabla[dirs].sum(axis=1) == tabla["n_estudios_ausentes"]).all()
    # contra los códigos fuente: n de informes con presencia por criterio
    codigos = pd.read_csv(PRIVADA / M.CODIGOS, dtype=str, encoding="utf-8-sig")
    n = codigos[codigos["codigo"] == "1"].groupby("criterio").size()
    assert (n == tabla["n_informes_presentes"]).all()
    assert (
        tabla.loc["C01", "etiqueta"] == tabla.loc["C02", "etiqueta"] == "condición base"
    )
    assert tabla.loc["C06", "etiqueta"] == "brecha de diseño"
    assert list(tabla.index[tabla["nota_calibracion_d52"] == "sí"]) == M.CON_NOTA_D52


def test_json_trae_hashes_y_base():
    traza = json.loads((TABLAS / f"{M.SALIDA}.json").read_text("utf-8"))
    assert traza["base"] == {"informes": 196, "estudios": 193}
    assert {"codigos_claude", "marco_de_criterios", "libro_codigos"} <= set(
        traza["entradas"]
    )
