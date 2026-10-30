"""Tests del mini-sprint semántico: módulos puros y números reales de entrada.

No necesitan torch ni BERTopic (corren con el venv principal). Las pruebas de
entradas reales leen la matriz normalizada y los textos del Drive (RS_DRIVE_ROOT).
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from rs_pipeline import semantico_metricas as M
from rs_pipeline import semantico_texto as T

RAIZ = Path(__file__).resolve().parents[1]
INFORMES_P1 = "R0998 R0045 R0578 R0527 R1085 R0755 R0711 R0730 R0713 R0922".split()
EXCLUIDOS_NIVEL = {"R0186", "R0295", "R0720", "R0877", "R0935"}


@pytest.fixture(scope="module")
def params():
    return yaml.safe_load((RAIZ / "config/params.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def matriz(params):
    ruta = RAIZ / params["salidas"]["procesados"]
    ruta /= f"{Path(params['archivos']['extraccion']).stem}_normalizada.csv"
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8")
    return tabla[tabla["excluido_nivel"] == "0"].reset_index(drop=True)


# --- ARI -----------------------------------------------------------------------


def test_ari_valores_conocidos():
    assert M.ari([0, 0, 1, 1], [0, 0, 1, 1])["valor"] == pytest.approx(1.0)
    assert M.ari([0, 0, 1, 1], [1, 1, 0, 0])["valor"] == pytest.approx(1.0)
    assert M.ari([0, 0, 1, 1], [0, 0, 1, 2])["valor"] == pytest.approx(4 / 7)
    assert M.ari([0, 0, 1, 1], [0, 1, 0, 1])["valor"] == pytest.approx(-0.5)


def test_ari_ignora_las_unidades_sin_tema_en_cualquiera_de_las_dos():
    a, b = [0, 0, 1, 1, -1, 2], [5, 5, 6, 6, 7, -1]
    r = M.ari(a, b)
    assert r["valor"] == pytest.approx(1.0)
    assert r["n_usadas"] == 4
    assert r["fraccion_usada"] == pytest.approx(4 / 6)


def test_ari_con_menos_de_dos_unidades_no_es_calculable():
    assert math.isnan(M.ari([0, -1], [0, 0])["valor"])


def test_ari_con_largos_distintos_hace_fallar():
    with pytest.raises(T.ErrorPipeline, match="ARI"):
        M.ari([0, 1], [0, 1, 2])


def test_la_semilla_medoide_es_la_mas_parecida_a_las_demas():
    base = np.array([0, 0, 1, 1, 2, 2])
    asignaciones = {1: base, 2: base.copy(), 3: np.array([0, 1, 0, 1, 2, 2])}
    assert M.semilla_medoide(asignaciones) == 1  # empate 1 y 2: gana la menor


# --- Coherencia ----------------------------------------------------------------


def test_npmi_de_palabras_independientes_es_cero():
    assert M.npmi_par(n1=50, n2=50, n12=25, total=100) == pytest.approx(0.0)


def test_npmi_extremos():
    assert M.npmi_par(10, 10, 0, 100) == -1.0
    assert M.npmi_par(100, 100, 100, 100) == 1.0
    assert M.npmi_par(10, 10, 10, 100) == pytest.approx(1.0)


def test_coherencia_de_palabras_que_siempre_van_juntas_es_uno():
    conjuntos = M.conjuntos_de_palabras(["gato perro", "gato perro", "mesa silla"])
    indice = M.indice_invertido(conjuntos)
    assert M.coherencia_tema(["gato", "perro"], indice, 3) == pytest.approx(1.0)
    assert M.coherencia_tema(["gato", "mesa"], indice, 3) == -1.0


def test_coherencia_no_cuenta_el_tema_de_los_sin_tema():
    indice = M.indice_invertido(M.conjuntos_de_palabras(["gato perro", "mesa silla"]))
    temas = {-1: ["gato", "mesa"], 0: ["gato", "perro"]}
    assert M.coherencia(temas, indice, 2) == pytest.approx(1.0)


# --- Reparto, mezcla y dominancia --------------------------------------------------


def test_temas_dominados_por_un_valor():
    etiquetas = np.array([0, 0, 0, 0, 1, 1, -1])
    atributo = ["a", "a", "a", "b", "a", "b", "a"]
    r = M.porcentaje_dominado(etiquetas, atributo, 0.7)
    assert (r["n_temas"], r["n_dominados"]) == (2, 1)  # tema 0: 75 %; tema 1: 50 %
    assert r["pct_dominados"] == pytest.approx(50.0)


def test_mezcla_de_idiomas_exige_dos_idiomas_sobre_el_minimo():
    etiquetas = np.array([0] * 10 + [1] * 10)
    idiomas = ["en"] * 9 + ["es"] + ["en"] * 5 + ["es"] * 5
    r = M.mezcla_de_idiomas(etiquetas, idiomas, 10)
    assert r["n_mezclan"] == 2  # tema 0: es = 10 % (llega al mínimo); tema 1: 50 %
    assert M.mezcla_de_idiomas(etiquetas, idiomas, 20)["n_mezclan"] == 1


def test_juzgar_con_los_dos_umbrales():
    assert M.juzgar(0.7, 0.6, 0.4, True) == "cumple"
    assert M.juzgar(0.5, 0.6, 0.4, True) == "intermedio"
    assert M.juzgar(0.3, 0.6, 0.4, True) == "no cumple"
    assert M.juzgar(35, 40, 60, False) == "cumple"
    assert M.juzgar(50, 40, 60, False) == "intermedio"
    assert M.juzgar(70, 40, 60, False) == "no cumple"
    assert M.juzgar(math.nan, 40, 60, False) == "no calculable"


# --- Texto completo --------------------------------------------------------------


def test_se_corta_en_el_marcador_de_referencias():
    lineas = [
        "Texto uno.",
        "Texto dos.",
        "[[REFERENCIAS OMITIDAS desde el carácter 9]]",
    ]
    cuerpo, corte = T.cortar_referencias(lineas, "R1")
    assert (cuerpo, corte) == (["Texto uno.", "Texto dos."], "marcador")


def test_sin_marcador_se_corta_en_el_encabezado_del_ultimo_40_por_ciento():
    lineas = ["References"] + ["x"] * 3 + ["Texto."] * 4 + ["References", "Autor 2020."]
    cuerpo, corte = T.cortar_referencias(lineas, "R1")
    assert corte == "encabezado" and len(cuerpo) == 8  # el de la línea 0 no cuenta


def test_sin_seccion_de_referencias_falla():
    with pytest.raises(T.ErrorPipeline, match="R9"):
        T.cortar_referencias(["Texto."] * 10, "R9")


def test_quitar_ruido_quita_titulos_marcadores_e_indices():
    lineas = [
        "2. Methods",
        "Los estudiantes usaron la simulación durante cuatro semanas completas.",
        "[[p. 5]]",
        "Resultados ...........................  12",
        "1 3",
        "Journal of Science Education 2023 vol 28",
        "Journal of Science Education 2023 vol 28",
        "Journal of Science Education 2023 vol 28",
    ]
    assert T.quitar_ruido(lineas) == [lineas[1]]


def test_unir_lineas_junta_palabras_cortadas_con_guion():
    assert T.unir_lineas(["la simu-", "lación es útil", "y gratis."]) == (
        "la simulación es útil y gratis."
    )


def test_las_abreviaturas_no_cortan_oraciones():
    texto = "Según Lee et al. (2020) el efecto fue grande. A. J. Magaña lo confirmó."
    assert T.oraciones(texto) == [
        "Según Lee et al. (2020) el efecto fue grande.",
        "A. J. Magaña lo confirmó.",
    ]


def test_los_trozos_no_cortan_oraciones_y_llegan_al_objetivo():
    lista = [("palabra " * n).strip() + "." for n in (40, 40, 40, 40, 40, 40, 10)]
    trozos, descartadas = T.armar_trozos(lista, 100, 0.4, 3)
    assert trozos == [[0, 1, 2], [3, 4, 5, 6]]  # el resto de 10 palabras se une
    assert descartadas == 0
    assert sorted(i for t in trozos for i in t) == list(range(7))


def test_una_oracion_gigante_se_descarta_y_se_cuenta():
    lista = ["a " * 400, "corta " * 60 + "fin.", "otra " * 50 + "fin."]
    trozos, descartadas = T.armar_trozos(lista, 100, 0.4, 3)
    assert descartadas == 1
    assert trozos == [[1, 2]]


# --- Fichas ----------------------------------------------------------------------


def test_limpiar_ficha_quita_etiquetas_y_paginas_pero_no_el_resto():
    assert T.limpiar_ficha("[F] Gratuita (recursos en línea) (p. 1)") == (
        "Gratuita (recursos en línea)"
    )
    assert T.limpiar_ficha(
        "[I] Sesiones en línea (p. 29). Conectividad: 12 % (p. 85)"
    ) == ("Sesiones en línea. Conectividad: 12 %")
    assert T.limpiar_ficha(
        "Fue mejor (Tabla 2, p. 9) y estable (pp. 3–4, p. 12) [F/I]"
    ) == ("Fue mejor (Tabla 2) y estable")
    assert T.limpiar_ficha("Usa p. ej. Excel (p. 5, 8)") == "Usa p. ej. Excel"


def test_los_criterios_se_parten_y_las_fichas_cortas_se_descartan(params):
    p2 = params["semantico"]["prueba2"]
    texto = (
        "El laboratorio debería mostrar vectores en tiempo real (p. 10) || "
        "Debería emparejarse con una tarea guiada de papel y lápiz [F] || no reporta"
    )
    unidades = T.unidades_de_campo(texto, "oe2_criterios_candidatos", p2)
    assert len(unidades) == 2
    assert T.unidades_de_campo("no reporta", "oe4_steam", p2) == []
    assert len(T.unidades_de_campo(texto, "oe4_barreras", p2)) == 1  # sin partir


# --- Números reales de entrada ---------------------------------------------------


def test_la_base_es_196_informes_sin_los_5_excluidos_por_nivel(matriz):
    assert len(matriz) == 196
    assert not EXCLUIDOS_NIVEL & set(matriz["id"])


def test_la_muestra_de_la_prueba_1_es_5_ingles_3_espanol_2_portugues(matriz, params):
    assert params["semantico"]["prueba1"]["informes"] == INFORMES_P1
    idioma = matriz.set_index("id").loc[INFORMES_P1, "idioma"]
    assert idioma.value_counts().to_dict() == {
        "inglés": 5,
        "español": 3,
        "portugués": 2,
    }
    assert (
        matriz.set_index("id").loc[INFORMES_P1, "estudio_compartido_con"] == ""
    ).all()


def test_las_fichas_dan_3608_unidades_de_196_informes(matriz, params):
    p2 = params["semantico"]["prueba2"]
    por_oe = {}
    for oe, campos in p2["campos"].items():
        n = 0
        for campo in campos:
            for texto in matriz[campo]:
                n += len(T.unidades_de_campo(texto, campo, p2))
        por_oe[oe] = n
    assert por_oe == {"oe1": 196, "oe2": 2176, "oe4": 1236}
    assert "oe2_tipo_herramienta" not in sum(p2["campos"].values(), [])


def test_el_campo_excluido_existe_y_no_entra(params):
    p2 = params["semantico"]["prueba2"]
    assert p2["campos_excluidos"] == ["oe2_tipo_herramienta"]


def test_los_trozos_de_los_10_informes(params):
    from rs_pipeline.semantico_04 import raiz_drive

    cfg = params["semantico"]
    raiz = raiz_drive(params["drive_root_env"])
    totales = {}
    for clave, modelo in cfg["modelos"].items():
        n = 0
        for id_ in INFORMES_P1:
            texto = (raiz / cfg["prueba1"]["ruta_textos"] / f"{id_}.txt").read_text(
                encoding="utf-8", errors="replace"
            )
            trozos, estadisticas = T.trozos_de_informe(
                texto, id_, modelo["palabras_por_trozo"], cfg["prueba1"]
            )
            n += len(trozos)
            assert all("REFERENCIAS OMITIDAS" not in t["texto"] for t in trozos)
            assert all("[[p." not in t["texto"] for t in trozos)
            assert estadisticas["corte_referencias"] in {"marcador", "encabezado"}
        totales[clave] = n
    assert totales == {"principal": 408, "control": 624}
