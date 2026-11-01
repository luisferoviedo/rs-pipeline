"""Tests del cruce de criterios con la evidencia (criterios_05; D43).

Reglas puras con casos hechos a mano y las tablas de salida recalculadas con una
lectura independiente de la matriz y de las asignaciones de e5.
"""

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from rs_pipeline import criterios_05 as K

RAIZ = Path(__file__).resolve().parents[1]
TABLAS = RAIZ / "outputs" / "tablas"
MATRIZ = RAIZ / "data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv"
ASIGNACIONES = RAIZ / "outputs/semantico/asignaciones_prueba2b_principal_s4.csv"


def fila(**campos):
    base = {
        "mmat_s1": "Sí",
        "pre_post_un_grupo": "0",
        "comparacion": "clase tradicional",
        "oe1_direccion_norm": "favorable a la simulación",
        "nivel_dudoso": "0",
        "nivel_norm": "media",
    }
    return pd.Series(base | campos)


# --- Reglas puras ----------------------------------------------------------------


def test_a_umbrales_y_filtro_1():
    assert [K.puntos_a(fila(), ["Sí"] * n + ["No"] * (5 - n)) for n in range(6)] == [
        0,
        0,
        1,
        2,
        2,
        2,
    ]
    assert K.puntos_a(fila(mmat_s1="No"), ["Sí"] * 5) == 0


def test_b_tres_diseños_y_el_ajuste_de_no_comparativo():
    assert K.puntos_b(fila()) == 2
    assert K.puntos_b(fila(pre_post_un_grupo="1", comparacion="ninguna")) == 1
    assert K.puntos_b(fila(comparacion="[F] ninguna (un solo grupo)")) == 0
    assert K.puntos_b(fila(oe1_direccion_norm="no comparativo")) == 0


def test_c_niveles():
    assert K.puntos_c(fila()) == 2
    assert K.puntos_c(fila(nivel_norm="primer año universitario")) == 1
    assert K.puntos_c(fila(nivel_norm="formación docente")) == 1
    assert K.puntos_c(fila(nivel_norm="mixto")) == 1
    assert K.puntos_c(fila(nivel_norm="universitario: año no reportado")) == 0
    assert K.puntos_c(fila(nivel_norm="mixto", nivel_dudoso="1")) == 0


def test_peso_suma_y_minimo():
    assert [K.peso_suma(2, 2, 2), K.peso_suma(2, 2, 1), K.peso_suma(2, 1, 1)] == [
        "alto",
        "alto",
        "medio",
    ]
    assert [K.peso_suma(1, 1, 1), K.peso_suma(2, 0, 0), K.peso_suma(1, 1, 0)] == [
        "medio",
        "bajo",
        "bajo",
    ]
    assert K.peso_minimo(2, 2, 2) == "alto"
    assert K.peso_minimo(2, 2, 1) == "medio"
    assert K.peso_minimo(2, 2, 0) == "bajo"


def test_grupos_de_reporte():
    g = K.grupo_de_reporte
    assert g("Interfaz en inglés con subtítulos de apoyo") == "real"
    assert g("Idioma de las simulaciones: no reporta. Accesibilidad: no reporta") == (
        "solo_no_reporta"
    )
    assert (
        g("no reporta (no hay medición de usabilidad ni fallas)") == "solo_no_reporta"
    )
    assert g("Interfaz en inglés; accesibilidad e inclusión: no reporta") == "mixta"
    assert g("no reporta PhET es gratuita en la web") == "mixta"


def test_mmat_falla_si_no_hay_cinco_items():
    with pytest.raises(K.ErrorPipeline):
        K.respuestas_mmat("Sí — a || No — b", "R0001")
    assert K.respuestas_mmat(
        "Sí — a || No — b || No se puede saber — c || Sí — d || No — e", "R0001"
    ) == ["Sí", "No", "No se puede saber", "Sí", "No"]


# --- Salidas -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def matriz():
    tabla = pd.read_csv(MATRIZ, dtype=str, keep_default_na=False)
    return tabla[tabla["excluido_nivel"] == "0"].reset_index(drop=True)


@pytest.fixture(scope="module")
def cruce():
    return pd.read_csv(TABLAS / "criterios_v0_evidencia.csv").set_index("id_criterio")


def test_tabla_de_items_mmat_sin_texto_y_con_conteo_independiente(matriz):
    t = pd.read_csv(TABLAS / "mmat_items_por_informe.csv", dtype=str)
    assert len(t) == 196 and set(t["id"]) == set(matriz["id"])
    columnas = ["filtro_1", "filtro_2", *[f"item_{k}" for k in range(1, 6)]]
    permitidas = {"Sí", "No", "No se puede saber"}
    assert set(t[columnas].to_numpy().ravel()) <= permitidas
    esperado = matriz.set_index("id")["mmat_items"].map(
        lambda s: sum(p.strip().startswith("Sí") for p in s.split(" || "))
    )
    obtenido = t.set_index("id")[columnas[2:]].apply(
        lambda r: (r == "Sí").sum(), axis=1
    )
    assert (esperado == obtenido.loc[esperado.index]).all()
    # 28 alta, 49 media, 119 baja (conteos de D43, con el filtro 1)
    pesos = [
        K.puntos_a(f, K.respuestas_mmat(f["mmat_items"], f["id"]))
        for _, f in matriz.iterrows()
    ]
    assert [pesos.count(2), pesos.count(1), pesos.count(0)] == [28, 49, 119]


def test_marco_y_cruce_coinciden_en_ids_y_temas(cruce):
    marco = yaml.safe_load((RAIZ / "config/criterios_v0.yaml").read_text("utf-8"))
    assert list(cruce.index) == [c["id"] for c in marco["criterios"]]
    for c in marco["criterios"]:
        assert cruce.loc[c["id"], "temas_origen"] == " ".join(
            map(str, c["temas_origen"])
        )


def test_unidades_informes_y_estudios_recalculados(matriz, cruce):
    marco = yaml.safe_load((RAIZ / "config/criterios_v0.yaml").read_text("utf-8"))
    a = pd.read_csv(ASIGNACIONES)
    a["informe"] = a["id_unidad"].str.split("|").str[0]
    socio = dict(zip(matriz["id"], matriz["estudio_compartido_con"], strict=True))
    estudio = {i: min(i, o) if o else i for i, o in socio.items()}
    for c in marco["criterios"]:
        u = a[a["tema"].isin(c["temas_origen"])]
        fila_c = cruce.loc[c["id"]]
        assert fila_c["n_unidades"] == len(u)
        assert fila_c["n_informes"] == u["informe"].nunique()
        assert fila_c["n_estudios"] == len({estudio[i] for i in u["informe"]})


def test_repartos_suman_y_sensibilidad_es_consistente(cruce):
    for _, f in cruce.iterrows():
        n = f["n_estudios"]
        assert f["suma_alto"] + f["suma_medio"] + f["suma_bajo"] == n
        assert f["minimo_alto"] + f["minimo_medio"] + f["minimo_bajo"] == n
        assert f["n_estudios_sin_bajo_suma"] == n - f["suma_bajo"]
        assert f["n_estudios_sin_bajo_minimo"] == n - f["minimo_bajo"]
        assert f["nivel_secundaria"] + f["nivel_universitario"] + f["nivel_otro"] == n
        directos = [c for c in cruce.columns if c.startswith("direccion_")]
        propias = [c for c in directos if "sin_bajo" not in c]
        sin_bajo = [c for c in directos if "sin_bajo" in c]
        assert f[propias].sum() == n
        assert f[sin_bajo].sum() == f["n_estudios_sin_bajo_suma"]
        total = f["n_unidades_real"] + f["n_unidades_mixta"]
        assert total + f["n_unidades_solo_no_reporta"] == f["n_unidades"]


def test_trazabilidad_y_solapamiento_6_12():
    j = json.loads((TABLAS / "criterios_v0_evidencia.json").read_text("utf-8"))
    csv = TABLAS / "criterios_v0_evidencia.csv"
    import hashlib

    assert j["salida"]["sha256"] == hashlib.sha256(csv.read_bytes()).hexdigest()
    s = j["solapamiento_temas_6_12"]
    assert s["informes_comunes"] <= min(s["informes_a"], s["informes_b"])
    assert s["supera_70_pct"] == (max(s["pct_de_a"], s["pct_de_b"]) > 70)
    assert "textos" not in json.dumps(j)
