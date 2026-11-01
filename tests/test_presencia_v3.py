"""Tests del libro v3, la muestra de verificación y la hoja de 196 (D50)."""

import hashlib
from pathlib import Path

import pandas as pd
import pytest
import yaml

from rs_pipeline import codificacion_06 as C
from rs_pipeline import codificacion_claude as K

RAIZ = Path(__file__).resolve().parents[1]
PRIVADA = RAIZ / "outputs" / "semantico"
CRITERIOS = [f"C0{n}" for n in range(1, 10)]
EXCLUIDOS_NIVEL = {"R0186", "R0295", "R0720", "R0877", "R0935"}
# Libros históricos: no se tocan (hash del contenido al cerrar D47).
HASH_HISTORICOS = {
    "config/libro_codigos_v0.yaml": "4b8d9eae94cf0ab797c6c7d018afa2c73ebc20f3a81b39aed34acc069ec82101",  # noqa: E501
    "config/libro_codigos_v1.yaml": "33ce0facb6cd13e99b6a242ad0e17a88c55489f8806e9df8a453dd546f4d60b9",  # noqa: E501
    "config/libro_codigos_v2.yaml": "69ff2a4afca9eadf5e59fe2e9e30b4c011cbb7ec0a931e098b6d17b4540ffd66",  # noqa: E501
    "docs/libro_codigos_v1.md": "acaa3a356ac68a39ff9bbb325678b52cb38113aa128146c359791ff4308fe1ec",  # noqa: E501
    "docs/libro_codigos_v2.md": "bf5100ce26eeb269d34a847e05179bd176c95b59cf4d322ed6ce2f86e2069389",  # noqa: E501
}


@pytest.fixture(scope="module")
def params():
    return yaml.safe_load((RAIZ / "config/params.yaml").read_text(encoding="utf-8"))


def leer(nombre):
    return pd.read_csv(
        PRIVADA / nombre, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )


# --- Libro v3 ---------------------------------------------------------------------


def test_libro_v3_es_binario_y_repite_el_marco():
    v3 = yaml.safe_load((RAIZ / "config/libro_codigos_v3.yaml").read_text("utf-8"))
    marco = yaml.safe_load((RAIZ / "config/criterios_v0.yaml").read_text("utf-8"))
    assert v3["version"] == "v3" and v3["decision"] == "D50"
    assert list(v3["escala"]) == [0, 1]
    for c, origen in zip(v3["criterios"], marco["criterios"], strict=True):
        for clave in ("id", "dimension", "criterio_corto", "enunciado", "estado"):
            assert c[clave] == origen[clave]
        assert all(list(e) == [0, 1] for e in [c.get("ejemplos", {0: 0, 1: 1})])
    md = (RAIZ / "docs/libro_codigos_v3.md").read_text(encoding="utf-8")
    assert all(f"C0{n}" in md for n in range(1, 10))
    assert "atribución" in " ".join(v3["reglas"])


def test_c06_del_marco_sin_docentes_ni_pares_y_en_borrador():
    marco = yaml.safe_load((RAIZ / "config/criterios_v0.yaml").read_text("utf-8"))
    c06 = marco["criterios"][5]
    assert c06["id"] == "C06"
    assert "docentes o pares" not in c06["enunciado"]
    assert c06["estado"] == "borrador: revisar Luis Fer"
    assert {c["id"] for c in marco["criterios"] if c["estado"] != "aprobado"} == {
        "C01",
        "C06",
        "C09",
    }


def test_listas_cuenta_no_cuenta_en_c05_c06_c08_y_notas():
    v3 = yaml.safe_load((RAIZ / "config/libro_codigos_v3.yaml").read_text("utf-8"))
    por_id = {c["id"]: c for c in v3["criterios"]}
    for criterio in ("C05", "C06", "C08"):
        assert len(por_id[criterio]["cuenta"]) >= 4
        assert len(por_id[criterio]["no_cuenta"]) >= 4
    otros = [c for c in v3["criterios"] if c["id"] not in ("C05", "C06", "C08")]
    assert not any("cuenta" in c or "no_cuenta" in c for c in otros)
    assert any("docente" in x and "C04" in x for x in por_id["C06"]["no_cuenta"])
    assert "condición base" in por_id["C01"]["nota"]
    assert "condición base" in por_id["C02"]["nota"]
    assert "C04" in " ".join(v3["reglas"]) and "(0)" in " ".join(v3["reglas"])


def test_libros_historicos_intactos_y_protegidos():
    for ruta, esperado in HASH_HISTORICOS.items():
        contenido = (RAIZ / ruta).read_bytes()
        assert hashlib.sha256(contenido).hexdigest() == esperado, ruta
    with pytest.raises(C.ErrorPipeline):
        C.escribir_libro({"campos_ficha": []}, "v2")
    assert (
        hashlib.sha256((RAIZ / "config/libro_codigos_v2.yaml").read_bytes()).hexdigest()
        == HASH_HISTORICOS["config/libro_codigos_v2.yaml"]
    )


# --- Lotes ------------------------------------------------------------------------


def test_repartir_en_lotes():
    ids = [f"T{n:03d}" for n in range(1, 197)]
    lotes = C.repartir_en_lotes(ids[::-1], 4, 50)
    assert [len(x) for x in lotes] == [49, 49, 49, 49]
    assert sum(lotes, []) == ids
    assert [len(x) for x in C.repartir_en_lotes(ids[:10], 3, 50)] == [4, 4, 2]
    with pytest.raises(C.ErrorPipeline):
        C.repartir_en_lotes(ids, 3, 50)


# --- Muestra de verificación (20) -------------------------------------------------


def test_hoja_de_20_columnas_ids_y_sin_codigos(params):
    hoja = leer("hoja_codificacion_presencia_20.csv")
    campos = params["codificacion"]["campos_ficha"]
    assert list(hoja.columns) == [
        "id_ciego",
        *campos,
        "C05",
        "C06",
        "C08",
        "modo_presencia",
        "nota",
    ]
    assert list(hoja["id_ciego"]) == [f"V{n:02d}" for n in range(1, 21)]
    assert (hoja[["C05", "C06", "C08", "modo_presencia", "nota"]] == "").all().all()
    assert (PRIVADA / "hoja_codificacion_presencia_20.csv").read_bytes()[:3] == (
        b"\xef\xbb\xbf"
    )


def test_muestra_de_20_nueva_y_estratificada_igual(params):
    cfg = params["codificacion"]
    pesos = C.informes_con_peso(params)[1]
    corr = leer("hoja_codificacion_presencia_20_correspondencia.csv")
    muestra = pd.read_csv(PRIVADA / "muestra_verificacion_presencia_20.csv")
    usados = set(C.ids_ya_usados(PRIVADA))
    assert len(usados) == 45 and len(muestra) == 20
    assert sorted(corr["id"]) == sorted(muestra["id"])
    assert not set(muestra["id"]) & (usados | EXCLUIDOS_NIVEL)
    estudios_usados = set(pesos[pesos["id"].isin(usados)]["estudio"])
    assert not set(muestra["estudio"]) & estudios_usados
    # mismo reparto proporcional (mínimo 1) sobre el universo disponible
    pool = pesos[~pesos["estudio"].isin(estudios_usados)]
    estrato = pool["peso_suma"] + " | " + pool["nivel"]
    esperado = C.cuotas(estrato.value_counts(), 20)
    assert muestra.groupby("estrato").size().to_dict() == esperado
    de_nuevo = C.elegir_confiabilidad(
        pesos, sorted(usados), 20, cfg["semilla"], desplazamiento=4
    )
    assert list(de_nuevo["id"]) == list(muestra["id"])


# --- Hoja de 196 y lotes ----------------------------------------------------------


def test_hoja_de_196_cubre_todos_los_informes_sin_codigos(params):
    hoja = leer("hoja_codificacion_196.csv")
    piloto = leer("hoja_codificacion_piloto.csv")
    assert list(hoja.columns) == list(piloto.columns)
    assert list(hoja["id_ciego"]) == [f"T{n:03d}" for n in range(1, 197)]
    assert (hoja[[*CRITERIOS, "nota"]] == "").all().all()
    corr = leer("hoja_codificacion_196_correspondencia.csv")
    matriz = pd.read_csv(
        RAIZ / "data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv",
        dtype=str,
        keep_default_na=False,
    )
    incluidos = set(matriz[matriz["excluido_nivel"] == "0"]["id"])
    assert len(incluidos) == 196 and set(corr["id"]) == incluidos
    assert not set(corr["id"]) & EXCLUIDOS_NIVEL
    assert hoja["id_ciego"].is_unique and corr["id"].is_unique


def test_hojas_de_lote_son_la_hoja_partida_en_cuatro(params):
    hoja = leer("hoja_codificacion_196.csv")
    cfg = params["codificacion"]
    assert (cfg["n_lotes_196"], cfg["max_por_lote"]) == (4, 50)
    partes = [leer(f"hoja_codificacion_196_lote{n}.csv") for n in range(1, 5)]
    assert [len(p) for p in partes] == [49, 49, 49, 49]
    assert pd.concat(partes, ignore_index=True).equals(hoja)
    assert partes[0]["id_ciego"].iloc[0] == "T001"
    assert partes[3]["id_ciego"].iloc[-1] == "T196"


# --- Registro de lotes parciales -------------------------------------------------


def lote_falso(ids, codigo=1):
    return {
        "modelo": "modelo-de-prueba",
        "informes": {
            i: {
                "codigos": dict.fromkeys(CRITERIOS, codigo),
                "justificaciones": dict.fromkeys(CRITERIOS, "una línea"),
            }
            for i in ids
        },
    }


def test_lote_parcial_valida_sus_propios_id(params):
    hoja = K.leer_hoja(params, "hoja_codificacion_196.csv", con_codigos=False)
    libro = RAIZ / "config/libro_codigos_v3.yaml"
    esperados = K.ids_del_lote(hoja, params, 2)
    assert esperados[0] == "T050" and esperados[-1] == "T098" and len(esperados) == 49
    lineas = K.lineas_del_lote(
        lote_falso(esperados), hoja, libro, params, esperados, (0, 1)
    )
    assert [x["id_ciego"] for x in lineas] == esperados
    por_id = hoja.set_index("id_ciego")
    campos = params["codificacion"]["campos_ficha"]
    primera = lineas[0]
    assert primera["sha256_ficha"] == K.hash_ficha(
        {c: por_id.loc["T050", c] for c in campos}
    )
    assert primera["libro"]["archivo"] == "libro_codigos_v3.yaml"
    with pytest.raises(K.ErrorPipeline):  # falta un informe del lote
        K.lineas_del_lote(lote_falso(esperados[1:]), hoja, libro, params, esperados)
    otro = K.ids_del_lote(hoja, params, 3)[:1]
    with pytest.raises(K.ErrorPipeline):  # trae un informe de otro lote
        K.lineas_del_lote(
            lote_falso([*esperados[1:], *otro]), hoja, libro, params, esperados
        )
    with pytest.raises(K.ErrorPipeline):  # esperados fuera de la hoja
        K.lineas_del_lote(lote_falso(["X1"]), hoja, libro, params, ["X1"])
    with pytest.raises(K.ErrorPipeline):  # lote que no existe
        K.ids_del_lote(hoja, params, 5)


def test_libro_v3_no_acepta_el_codigo_2(params):
    hoja = K.leer_hoja(params, "hoja_codificacion_196.csv", con_codigos=False)
    libro = RAIZ / "config/libro_codigos_v3.yaml"
    esperados = K.ids_del_lote(hoja, params, 1)
    with pytest.raises(K.ErrorPipeline):
        K.lineas_del_lote(
            lote_falso(esperados, codigo=2), hoja, libro, params, esperados, (0, 1)
        )
    # con la escala 0-1-2 de v2 el mismo lote sí pasa la validación de códigos
    assert K.lineas_del_lote(
        lote_falso(esperados, codigo=2), hoja, libro, params, esperados
    )


def test_nombre_del_csv_de_codigos():
    assert K.archivo_de_codigos("hoja_codificacion_196.csv", "v3") == (
        "codigos_claude_196_v3.csv"
    )
    assert K.archivo_de_codigos("hoja_codificacion_40.csv", "v2") == (
        "codigos_claude_40.csv"
    )
    assert K.archivo_de_codigos("hoja_codificacion_piloto.csv", "v1") == (
        "codigos_claude_piloto.csv"
    )


# --- Protocolo --------------------------------------------------------------------


def test_protocolo_lista_lo_permitido_y_lo_prohibido():
    t = (RAIZ / "docs/protocolo_codificacion_ciega.md").read_text(encoding="utf-8")
    permitido, resto = t.split("## Qué NO se debe abrir")
    assert (
        "libro_codigos_v3.md" in permitido and "hoja_codificacion_196_lote" in permitido
    )
    assert "codificacion_claude.py" in permitido
    for prohibido in ("codigos_luisfer_", "notas_", "logs/", "codigos_claude_"):
        assert prohibido in resto.split("## Cómo codificar")[0]
    assert "--lote {N}" in t and "codigos_claude_196_v3.csv" in t
    assert "git log" in t and "no hacer push" in t
