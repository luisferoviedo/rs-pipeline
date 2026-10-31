"""Tests de las salidas del mini-sprint semántico (después de correr semantico_04).

Recalculan métricas con fórmulas independientes a partir de las asignaciones que
guardó la corrida, y comprueban la hoja a ciegas y que lo versionado no traiga texto.
"""

import json
import math
from pathlib import Path

import pandas as pd
import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
PRIVADA = RAIZ / "outputs" / "semantico"
PUBLICA = RAIZ / "outputs" / "semantico_metricas"
PRUEBAS = ["prueba1", "prueba2a", "prueba2b"]
MODELOS = ["principal", "control"]
EXCLUIDOS_NIVEL = {"R0186", "R0295", "R0720", "R0877", "R0935"}


@pytest.fixture(scope="module")
def cfg():
    todo = yaml.safe_load((RAIZ / "config/params.yaml").read_text(encoding="utf-8"))
    return todo["semantico"]


@pytest.fixture(scope="module")
def metricas():
    return {
        p: json.loads((PUBLICA / f"{p}_metricas.json").read_text(encoding="utf-8"))
        for p in PRUEBAS
    }


def asignacion(prueba, modelo, semilla):
    ruta = PRIVADA / f"asignaciones_{prueba}_{modelo}_s{semilla}.csv"
    return pd.read_csv(ruta, dtype={"id_unidad": str, "tema": int})


def ari_independiente(a, b):
    """ARI con tabla de contingencia de pandas y math.comb (sin numpy)."""
    usar = (a != -1) & (b != -1)
    tabla = pd.crosstab(a[usar], b[usar])
    n = int(usar.sum())
    suma = sum(math.comb(int(x), 2) for x in tabla.to_numpy().ravel())
    filas = sum(math.comb(int(x), 2) for x in tabla.sum(axis=1))
    columnas = sum(math.comb(int(x), 2) for x in tabla.sum(axis=0))
    esperado = filas * columnas / math.comb(n, 2)
    return (suma - esperado) / ((filas + columnas) / 2 - esperado)


def test_hay_cinco_corridas_por_modelo_y_diez_pares_de_semillas(metricas, cfg):
    for prueba in PRUEBAS:
        for modelo in MODELOS:
            m = metricas[prueba]["modelos"][modelo]
            assert [c["semilla"] for c in m["corridas"]] == cfg["semillas"]
            assert len(m["ari_entre_semillas"]["pares"]) == 10
            assert m["semilla_medoide"] in cfg["semillas"]
        assert len(metricas[prueba]["acuerdo_entre_modelos"]["pares"]) == 25


@pytest.mark.parametrize("prueba", PRUEBAS)
@pytest.mark.parametrize("modelo", MODELOS)
def test_ari_entre_semillas_coincide_con_el_recalculo_independiente(
    metricas, prueba, modelo
):
    pares = metricas[prueba]["modelos"][modelo]["ari_entre_semillas"]["pares"]
    for par in (pares[0], pares[-1]):
        s1, s2 = par["semillas"]
        a = asignacion(prueba, modelo, s1)["tema"]
        b = asignacion(prueba, modelo, s2)["tema"]
        assert par["valor"] == pytest.approx(ari_independiente(a, b), abs=1e-9)


@pytest.mark.parametrize("prueba", ["prueba2a", "prueba2b"])
def test_ari_entre_modelos_de_fichas_coincide_con_el_recalculo(metricas, prueba):
    par = metricas[prueba]["acuerdo_entre_modelos"]["pares"][0]
    s1, s2 = par["semillas"]
    a = asignacion(prueba, "principal", s1)
    b = asignacion(prueba, "control", s2)
    assert list(a["id_unidad"]) == list(b["id_unidad"])  # mismas unidades
    assert par["valor"] == pytest.approx(ari_independiente(a["tema"], b["tema"]))


def test_el_numero_de_temas_y_de_sin_tema_coinciden_con_las_asignaciones(metricas):
    for prueba in PRUEBAS:
        for modelo in MODELOS:
            for corrida in metricas[prueba]["modelos"][modelo]["corridas"]:
                a = asignacion(prueba, modelo, corrida["semilla"])["tema"]
                assert len(a) == corrida["n_unidades"]
                assert a[a != -1].nunique() == corrida["n_temas"]
                assert 100 * (a == -1).mean() == pytest.approx(corrida["pct_sin_tema"])
                assert sum(corrida["tamanos_temas"]) == int((a != -1).sum())


def test_las_fichas_no_incluyen_los_5_excluidos_por_nivel(metricas):
    for prueba in ["prueba2a", "prueba2b"]:
        ids = asignacion(prueba, "principal", 1)["id_unidad"]
        informes = set(ids.str.split("|").str[0])
        assert not EXCLUIDOS_NIVEL & informes
        assert len(informes) <= 196
    ids_b = set(asignacion("prueba2b", "principal", 1)["id_unidad"])
    ids_a = set(asignacion("prueba2a", "principal", 1)["id_unidad"])
    assert ids_b < ids_a
    assert all("|oe2_" in i for i in ids_b)


def test_la_prueba_1_tiene_los_10_informes_y_los_trozos_esperados(metricas):
    p1 = metricas["prueba1"]
    assert p1["unidades"] == {"principal": 408, "control": 624}
    assert sorted(p1["estadisticas_por_informe"]["principal"]) == sorted(
        "R0998 R0045 R0578 R0527 R1085 R0755 R0711 R0730 R0713 R0922".split()
    )


def test_la_hoja_a_ciegas_2b_no_revela_modelo_ni_semilla(cfg):
    hoja = pd.read_csv(
        PRIVADA / "hoja_calificacion_ciega_2b.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    assert list(hoja.columns) == [
        "codigo", "prueba", "tamano_del_tema", "palabras_clave",
        "fragmento_1", "fragmento_2", "fragmento_3", "calificacion",
    ]  # fmt: skip
    assert len(hoja) == 35  # 20 temas de e5 + los 15 más grandes de MiniLM
    assert (hoja["prueba"] == "P2b").all()
    # ya calificada por Luis Fer (el respaldo sin calificar es otro archivo)
    assert hoja["calificacion"].isin(["interpretable", "mixto", "ruido"]).all()
    assert hoja["codigo"].is_unique and (hoja["codigo"].str.len() == 5).all()
    assert (hoja["palabras_clave"].str.count(",") == cfg["palabras_clave"] - 1).all()
    assert (hoja[["fragmento_1", "fragmento_2", "fragmento_3"]] != "").all().all()


def test_la_traduccion_2b_es_la_semilla_medoide_y_los_temas_mas_grandes(metricas):
    hoja = pd.read_csv(
        PRIVADA / "hoja_calificacion_ciega_2b.csv", dtype=str, encoding="utf-8-sig"
    )
    tabla = pd.read_csv(PRIVADA / "traduccion_codigos_2b.csv", dtype={"codigo": str})
    assert set(hoja["codigo"]) == set(tabla["codigo"]) and len(hoja) == len(tabla)
    assert (tabla["prueba"] == "P2b").all()
    esperados = {"principal": 20, "control": 15}
    for modelo, cantidad in esperados.items():
        filas = tabla[tabla["modelo"] == modelo]
        m = metricas["prueba2b"]["modelos"][modelo]
        corrida = next(c for c in m["corridas"] if c["semilla"] == m["semilla_medoide"])
        assert set(filas["semilla"]) == {m["semilla_medoide"]}
        assert len(filas) == cantidad
        mayores = sorted(corrida["tamanos_temas"], reverse=True)[:cantidad]
        assert sorted(filas["n_unidades"], reverse=True) == mayores
    tamanos = hoja.set_index("codigo")["tamano_del_tema"].astype(int)
    assert (
        tamanos.loc[tabla["codigo"]].to_numpy() == tabla["n_unidades"].to_numpy()
    ).all()


def test_lo_versionado_no_trae_texto_de_los_articulos():
    def cadenas(valor):
        if isinstance(valor, dict):
            for clave, v in valor.items():
                assert clave not in {"palabras", "docs", "texto", "fragmentos"}
                yield from cadenas(v)
        elif isinstance(valor, list):
            for v in valor:
                yield from cadenas(v)
        elif isinstance(valor, str):
            yield valor

    for ruta in PUBLICA.glob("*.json"):
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        assert all(len(c) <= 130 for c in cadenas(contenido)), ruta.name


def test_el_veredicto_deja_pendiente_la_interpretabilidad_de_las_otras_pruebas():
    v = json.loads((PUBLICA / "veredicto.json").read_text(encoding="utf-8"))
    assert len(v["criterios"]) == 6  # 3 pruebas x 2 modelos
    for clave, criterios in v["criterios"].items():
        if clave.startswith("prueba2b/"):
            assert criterios["interpretabilidad"] == "cumple"  # calificada (D40)
        else:
            assert criterios["interpretabilidad"].startswith("pendiente")
    assert v["hoja_a_ciegas"]["temas_en_la_hoja"] == 35
    assert set(v["criterios"]["prueba1/principal"]) >= {
        "mezcla_de_idiomas", "temas_de_un_documento", "tiempo_embeddings_mps",
    }  # fmt: skip


# --- Calificación de la hoja a ciegas (Prueba 2b) ----------------------------------


@pytest.fixture(scope="module")
def calificacion():
    ruta = PUBLICA / "prueba2b_calificacion.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


def calificaciones_por_modelo():
    hoja = pd.read_csv(
        PRIVADA / "hoja_calificacion_ciega_2b.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
        usecols=["codigo", "calificacion"],
    )
    traduccion = pd.read_csv(
        PRIVADA / "traduccion_codigos_2b.csv", dtype={"codigo": str}
    )
    return traduccion.merge(hoja, on="codigo")


def test_la_calificacion_suma_29_interpretables_6_mixtos_0_ruido(calificacion):
    assert calificacion["total"]["n_temas"] == 35
    assert calificacion["total"]["conteos"] == {
        "interpretable": 29, "mixto": 6, "ruido": 0,
    }  # fmt: skip


def test_los_porcentajes_por_modelo_coinciden_con_el_recalculo(calificacion):
    unidos = calificaciones_por_modelo()
    esperado = {"principal": (20, 18, 2, 0), "control": (15, 11, 4, 0)}
    for modelo, (n, interpretables, mixtos, ruido) in esperado.items():
        grupo = unidos[unidos["modelo"] == modelo]["calificacion"]
        assert len(grupo) == n
        assert (grupo == "interpretable").sum() == interpretables
        assert (grupo == "mixto").sum() == mixtos
        assert (grupo == "ruido").sum() == ruido
        r = calificacion["por_modelo"][modelo]
        assert r["pct"]["interpretable"] == pytest.approx(100 * interpretables / n)
        assert r["interpretabilidad"] == "cumple"  # 90 % y 73,3 % (umbral >= 60 %)


def test_el_veredicto_final_de_la_prueba_2b_es_sigue_en_los_dos_modelos(calificacion):
    for modelo in MODELOS:
        final = calificacion["veredicto_final"][modelo]
        assert final["veredicto"] == "sigue"
        assert set(final["criterios"].values()) == {"cumple"}
    guardado = json.loads((PUBLICA / "veredicto.json").read_text(encoding="utf-8"))
    assert guardado["veredicto_final_prueba2b"] == calificacion["veredicto_final"]


def test_la_calificacion_guarda_el_hash_de_la_hoja_calificada(calificacion):
    from rs_pipeline import semantico_04

    ruta = PRIVADA / "hoja_calificacion_ciega_2b.csv"
    assert calificacion["hoja"]["sha256_hoja_calificada"] == semantico_04.sha256(ruta)
    assert len(calificacion["por_tema"]) == 35


def test_el_respaldo_sin_calificar_sigue_sin_calificar():
    kw = {"dtype": str, "keep_default_na": False, "encoding": "utf-8-sig"}
    respaldo = pd.read_csv(
        PRIVADA / "hoja_calificacion_ciega_2b_sin_calificar_respaldo.csv", **kw
    )
    calificada = pd.read_csv(PRIVADA / "hoja_calificacion_ciega_2b.csv", **kw)
    assert len(respaldo) == 35 and (respaldo["calificacion"] == "").all()
    assert list(respaldo["codigo"]) == list(calificada["codigo"])
    columnas = [c for c in respaldo.columns if c != "calificacion"]
    assert respaldo[columnas].equals(
        calificada[columnas]
    )  # solo cambia la calificación


def test_no_se_sobrescribe_una_hoja_ya_calificada(tmp_path):
    from rs_pipeline import semantico_04, semantico_texto

    ruta = tmp_path / "hoja.csv"
    semantico_04.exigir_hoja_sin_calificar(ruta)  # no existe: no pasa nada
    ruta.write_text("codigo,calificacion\nAAAAA,\nBBBBB,\n", encoding="utf-8")
    semantico_04.exigir_hoja_sin_calificar(ruta)  # sin calificar: se puede reescribir
    ruta.write_text("codigo,calificacion\nAAAAA,mixto\nBBBBB,\n", encoding="utf-8")
    with pytest.raises(semantico_texto.ErrorPipeline, match="no se sobrescribe"):
        semantico_04.exigir_hoja_sin_calificar(ruta)


def test_una_calificacion_invalida_o_codigos_distintos_hacen_fallar(tmp_path):
    from rs_pipeline import semantico_04, semantico_texto

    (tmp_path / "traduccion_codigos_2b.csv").write_text(
        "codigo,prueba,modelo,semilla,tema,n_unidades\nAAAAA,P2b,principal,4,0,30\n",
        encoding="utf-8",
    )
    hoja = tmp_path / "hoja_calificacion_ciega_2b.csv"
    hoja.write_text("codigo,calificacion\nAAAAA,regular\n", encoding="utf-8")
    with pytest.raises(semantico_texto.ErrorPipeline, match="regular"):
        semantico_04.leer_calificacion_2b(tmp_path)
    hoja.write_text("codigo,calificacion\nZZZZZ,mixto\n", encoding="utf-8")
    with pytest.raises(semantico_texto.ErrorPipeline, match="mismos códigos"):
        semantico_04.leer_calificacion_2b(tmp_path)


def test_el_veredicto_final_combina_los_criterios():
    from rs_pipeline.semantico_04 import veredicto_final

    assert veredicto_final({"a": "cumple", "b": "cumple"}) == "sigue"
    assert veredicto_final({"a": "cumple", "b": "intermedio"}).startswith("intermedio")
    assert veredicto_final({"a": "intermedio", "b": "no cumple"}) == "no sigue"
