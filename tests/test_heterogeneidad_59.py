"""Tests de la exploración de la heterogeneidad de la dirección del efecto (D59)."""

import json
from math import isclose
from pathlib import Path

import pandas as pd
import pytest

from rs_pipeline import heterogeneidad_59 as H
from rs_pipeline import marco_evidencia_08 as M
from rs_pipeline import semantico_04 as S

RAIZ = Path(__file__).resolve().parents[1]
TABLAS = RAIZ / "outputs" / "tablas"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("laboratorio real", "laboratorio real"),
        ("Laboratorio Real (mismo tiempo de práctica)", "laboratorio real"),
        ("clase tradicional — [F] explicación del docente", "clase tradicional"),
        ("laboratorio real | otra: clase tradicional", "varios"),
        ("ninguna (un solo grupo)", "ninguna"),
        ("[F] ninguna — pre-post", "ninguna"),
        ("otra simulación (PhET frente a otra)", "otra simulación"),
        ("otra simulacion sin tilde", "otra simulación"),
        ("otra — [F] 7E contextual sin simulación", "otra"),
    ],
)
def test_reglas_del_comparador(texto, esperado):
    assert H.clasificar_comparador(texto) == esperado


def test_holm_con_cuentas_a_mano():
    # ordenados: 0,01 × 3 = 0,03; 0,03 × 2 = 0,06; 0,04 × 1 = 0,04 → sube a 0,06
    assert all(
        isclose(x, y)
        for x, y in zip(H.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06], strict=True)
    )
    # tope en 1: 0,5 × 2 = 1,0; 0,6 × 1 = 0,6 → sube a 1,0
    assert H.holm([0.5, 0.6]) == [1.0, 1.0]


def test_aplicar_decisiones_con_datos_inventados():
    base = pd.DataFrame(
        {"comparador_regla": ["varios", "otra", "laboratorio real"]},
        index=["E1", "E2", "E3"],
    )
    final = H.aplicar_decisiones(base, {"E1": "laboratorio real"})
    assert list(final["comparador"]) == ["laboratorio real", "otra", "laboratorio real"]
    with pytest.raises(H.ErrorPipeline):  # E3 no era ambiguo: no se puede decidir
        H.aplicar_decisiones(base, {"E3": "clase tradicional"})
    with pytest.raises(H.ErrorPipeline):  # E9 no está en la base
        H.aplicar_decisiones(base, {"E9": "otra"})


def test_leer_decisiones_falla_con_categoria_o_estudio_repetido():
    malo = "decisiones:\n  - {estudio: E1, categoria: laboratorio virtual}\n"
    with pytest.raises(H.ErrorPipeline):
        H.leer_decisiones(malo)
    repetido = (
        "decisiones:\n  - {estudio: E1, categoria: otra}\n"
        "  - {estudio: E1, categoria: varios}\n"
    )
    with pytest.raises(H.ErrorPipeline):
        H.leer_decisiones(repetido)


def test_archivo_real_de_decisiones():
    texto = (RAIZ / H.DECISIONES).read_text(encoding="utf-8")
    decisiones = H.leer_decisiones(texto)
    assert len(decisiones) == 14
    assert sum(c == "laboratorio real" for c in decisiones.values()) == 7
    assert sum(c == "clase tradicional" for c in decisiones.values()) == 6
    assert decisiones["R0341"] == "otra"


def test_base_solo_comparativos():
    estudios = pd.DataFrame(
        {
            "direccion": [
                "favorable",
                "mixto",
                "sin_diferencia",
                "no_comparativo",
                "otro",
            ]
        }
    )
    assert list(H.base_comparativa(estudios)["direccion"]) == list(H.COMPARATIVAS)


def test_fila_de_cruce_con_datos_inventados():
    base = pd.DataFrame(
        {
            "direccion": ["favorable", "favorable", "mixto", "sin_diferencia"]
            + ["favorable", "favorable"],
            "nivel": ["secundaria"] * 3 + ["universitario"] * 2 + ["otro"],
        }
    )
    fila = H.fila_de_cruce("nivel", base)
    assert (fila["n_1"], fila["favorables_1"]) == (3, 2)
    assert (fila["n_2"], fila["favorables_2"]) == (2, 1)
    assert fila["n_base"] == 6
    assert json.loads(fila["fuera_de_prueba"]) == {"otro": "1/1"}
    assert fila["pct_favorables_1"] == 66.7 and fila["diferencia_pp"] == 16.7
    assert isclose(fila["p_fisher"], M.fisher_dos_colas(2, 1, 1, 1))


def test_falla_si_un_grupo_queda_vacio():
    base = pd.DataFrame(
        {"direccion": ["favorable", "mixto"], "nivel": ["secundaria"] * 2}
    )
    with pytest.raises(H.ErrorPipeline):
        H.fila_de_cruce("nivel", base)


def test_salidas_reales_contra_la_matriz():
    salida = H.ejecutar(S.cargar_params())
    publicada = pd.read_csv(TABLAS / f"{H.SALIDA}.csv")
    calculada = salida["cruces"]
    assert list(publicada["pregunta"]) == ["nivel", "peso", "comparador"]
    for columna in ["n_base", "n_1", "favorables_1", "n_2", "favorables_2"]:
        assert list(publicada[columna]) == list(calculada[columna])
    for _, fila in publicada.iterrows():
        fuera = json.loads(fila["fuera_de_prueba"])
        n_fuera = sum(int(v.split("/")[1]) for v in fuera.values())
        assert fila["n_1"] + fila["n_2"] + n_fuera == fila["n_base"]
        assert fila["p_holm"] >= fila["p_fisher"]
    assert sum(salida["comparadores"].values()) == publicada["n_base"].iloc[0]


def test_holm_de_d54_contra_la_tabla_fuente():
    holm = pd.read_csv(TABLAS / f"{H.SALIDA_HOLM}.csv")
    assert len(holm) == H.N_PRUEBAS_D54
    d54 = pd.read_csv(TABLAS / H.ENTRADA_D54)
    c01 = d54[d54["id_criterio"] == "C01"].iloc[0]
    fila = holm[(holm["id_criterio"] == "C01") & (holm["direccion"] == "mixto")].iloc[0]
    assert isclose(fila["p"], c01["fisher_p_mixto"])
    assert fila["p"] < H.ALFA < fila["p_holm"]


def test_trazabilidad_y_sin_texto_en_git():
    traza = json.loads((TABLAS / f"{H.SALIDA}.json").read_text(encoding="utf-8"))
    for nombre, sha in traza["salidas"].items():
        assert S.sha256(TABLAS / nombre) == sha
    publicada = pd.read_csv(TABLAS / f"{H.SALIDA}.csv")
    assert "comparacion_texto" not in publicada
    decisiones = traza["entradas"]["decisiones_comparador"]
    assert S.sha256(RAIZ / decisiones["archivo"]) == decisiones["sha256"]
