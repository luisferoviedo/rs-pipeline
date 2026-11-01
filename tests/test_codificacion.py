"""Tests del libro de códigos, las muestras y la hoja del piloto (D44)."""

import json
import re
from pathlib import Path

import pandas as pd
import pytest
import yaml

from rs_pipeline import codificacion_06 as C

RAIZ = Path(__file__).resolve().parents[1]
PRIVADA = RAIZ / "outputs" / "semantico"
CAMPOS = (
    "tema nivel_norm disciplina_norm diseno comparacion oe1_hallazgo oe1_condiciones "
    "oe1_direccion_norm oe2_herramienta oe2_andamiaje oe2_retroalimentacion "
    "oe2_interactividad oe2_dispositivo oe2_conectividad oe2_idioma_accesibilidad "
    "oe2_costo_licencia oe2_usabilidad_calidad oe4_secuencia oe4_rol_docente"
).split()
EXCLUIDOS_NIVEL = {"R0186", "R0295", "R0720", "R0877", "R0935"}


@pytest.fixture(scope="module")
def params():
    return yaml.safe_load((RAIZ / "config/params.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def matriz():
    ruta = RAIZ / "data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv"
    return pd.read_csv(ruta, dtype=str, keep_default_na=False)


def test_libro_repite_los_criterios_y_la_escala():
    libro = yaml.safe_load((RAIZ / "config/libro_codigos_v0.yaml").read_text("utf-8"))
    marco = yaml.safe_load((RAIZ / "config/criterios_v0.yaml").read_text("utf-8"))
    assert list(libro["escala"]) == [0, 1, 2]
    assert libro["campos_ficha"] == CAMPOS
    for c, origen in zip(libro["criterios"], marco["criterios"], strict=True):
        for clave in ("id", "dimension", "criterio_corto", "enunciado", "estado"):
            assert c[clave] == origen[clave]
    con_ejemplos = [c for c in libro["criterios"] if "ejemplos" in c]
    assert 2 <= len(con_ejemplos) <= 3
    assert all(list(c["ejemplos"]) == [0, 1, 2] for c in con_ejemplos)
    md = (RAIZ / "docs/libro_codigos_v0.md").read_text(encoding="utf-8")
    assert all(f"C0{n}" in md for n in range(1, 10))
    assert "oe2_criterios_candidatos" in libro["campos_excluidos"]


def test_hoja_del_piloto_tiene_las_columnas_exactas_y_nada_codificado():
    hoja = pd.read_csv(
        PRIVADA / "hoja_codificacion_piloto.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    esperadas = ["id_ciego", *CAMPOS, *[f"C0{n}" for n in range(1, 10)], "nota"]
    assert list(hoja.columns) == esperadas
    assert list(hoja["id_ciego"]) == [f"P0{n}" for n in range(1, 6)]
    texto = hoja[CAMPOS].to_numpy().ravel()
    assert not any(re.search(r"\[\s*[FI]\s*\]|\bpp?\.\s*\d", t) for t in texto)
    assert (PRIVADA / "hoja_codificacion_piloto.csv").read_bytes()[
        :3
    ] == b"\xef\xbb\xbf"


def test_campos_de_la_hoja_vienen_de_la_matriz(matriz):
    hoja = pd.read_csv(
        PRIVADA / "hoja_codificacion_piloto.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    ).set_index("id_ciego")
    corr = pd.read_csv(PRIVADA / "hoja_codificacion_piloto_correspondencia.csv")
    base = matriz.set_index("id")
    for _, f in corr.iterrows():
        for campo in ("nivel_norm", "disciplina_norm", "oe1_direccion_norm"):
            assert hoja.loc[f["id_ciego"], campo] == base.loc[f["id"], campo]


def test_piloto_variado_y_sin_los_excluidos(params):
    pesos = C.informes_con_peso(params)[1]
    corr = pd.read_csv(PRIVADA / "hoja_codificacion_piloto_correspondencia.csv")
    p = pesos[pesos["id"].isin(corr["id"])]
    assert len(p) == 5 and not set(corr["id"]) & EXCLUIDOS_NIVEL
    assert p["peso_suma"].nunique() >= 3 and p["idioma"].nunique() >= 3
    assert p["disciplina"].nunique() >= 3 and p["estudio"].nunique() == 5
    cfg = params["codificacion"]
    assert C.elegir_piloto(pesos, 5, cfg["semilla"]) == sorted(corr["id"])


def test_muestra_de_confiabilidad(params):
    pesos = C.informes_con_peso(params)[1]
    corr = pd.read_csv(PRIVADA / "hoja_codificacion_piloto_correspondencia.csv")
    m = pd.read_csv(PRIVADA / "muestra_confiabilidad_40.csv")
    assert len(m) == 40 and m["id"].is_unique
    assert not set(m["id"]) & (set(corr["id"]) | EXCLUIDOS_NIVEL)
    estudios_piloto = set(pesos[pesos["id"].isin(corr["id"])]["estudio"])
    assert not set(m["estudio"]) & estudios_piloto
    assert {"alto", "medio", "bajo"} <= set(m["peso_suma"])
    cfg = params["codificacion"]
    de_nuevo = C.elegir_confiabilidad(pesos, sorted(corr["id"]), 40, cfg["semilla"])
    assert list(de_nuevo["id"]) == list(m["id"])


def test_cuotas_proporcionales_con_minimo_uno():
    tamanos = pd.Series({"a": 100, "b": 50, "c": 3, "d": 1})
    cuota = C.cuotas(tamanos, 20)
    assert sum(cuota.values()) == 20 and min(cuota.values()) >= 1
    assert cuota["a"] > cuota["b"] > cuota["c"]


def test_no_pisa_una_hoja_con_codigos(tmp_path):
    ruta = tmp_path / "hoja.csv"
    columnas = ["id_ciego", *C.CRITERIOS, "nota"]
    pd.DataFrame([dict.fromkeys(columnas, "")]).to_csv(ruta, index=False)
    C.exigir_hoja_sin_codificar(ruta)
    pd.DataFrame([dict.fromkeys(columnas, "") | {"C03": "1"}]).to_csv(ruta, index=False)
    with pytest.raises(C.ErrorPipeline):
        C.exigir_hoja_sin_codificar(ruta)


def test_costo_con_cuentas_a_mano(params):
    precios = params["codificacion"]["modelos_costo"]["claude-sonnet-5-5"]
    # 2 informes, solo el libro (1 millón de tokens): 1 escritura de 1 h + 1 lectura
    tokens = {"libro": 1e6, "ficha": 0, "salida": 0}
    r = C.costo_por_modelo(tokens, precios, 2, 0.5)
    assert r["con_cache"] == pytest.approx(4.0 * 0.5 + 0.10 * 0.5)
    assert r["sin_cache"] == pytest.approx(2 * 2.0 * 0.5)
    json_costo = json.loads(
        (RAIZ / "outputs/tablas/costo_codificacion_estimado.json").read_text("utf-8")
    )
    # D46: la estimación de la API quedó marcada como «no aplica»
    assert json_costo["estado"] == "no aplica (D46)"
    historica = json_costo["estimacion_api_no_vigente"]
    assert historica["n_informes"] == 196
    assert "platform.claude.com" in historica["fuente_precios"]
