"""Tests del marco de criterios v1 (D55): v0 con C01, C06 y C09 aprobados y 3 niveles.

v0 queda congelado: v1 se compara contra el archivo v0 real, y los textos nuevos
de C01, C06 y C09 están escritos aquí a mano (no se leen de v1).
"""

import hashlib
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
V0 = RAIZ / "config" / "criterios_v0.yaml"
V1 = RAIZ / "config" / "criterios_v1.yaml"

IDS = [f"C{n:02d}" for n in range(1, 10)]
NIVELES = {
    "base": ["C01", "C02", "C03"],
    "calidad": ["C04", "C07", "C09"],
    "innovacion": ["C05", "C06", "C08"],
}
SIN_CAMBIO = ["C02", "C03", "C04", "C05", "C07", "C08"]

C01_ENUNCIADO = (
    "El laboratorio virtual debe articularse con decisiones didácticas explícitas "
    "del docente antes, durante y después de la simulación, de modo que el "
    "estudiante participe de forma activa, guiada y reflexiva, y no se limite a "
    "ejecutar la simulación."
)
C06_CORTO = "Retroalimentación automática y visualización del desempeño."
C06_ENUNCIADO = (
    "El laboratorio virtual debe generar respuestas automáticas e inmediatas a las "
    "acciones del estudiante (mensajes, gráficas o representaciones visuales) que "
    "le permitan identificar errores y ajustar su procedimiento sin depender en "
    "todo momento de la intervención docente."
)
C09_ENUNCIADO = (
    "El laboratorio virtual debe poder usarse con los dispositivos, la "
    "conectividad, el idioma y los recursos económicos disponibles en las "
    "instituciones, sin equipos costosos, licencias pagas ni conexión permanente, y"
    " debe declarar explícitamente esos requisitos de uso."
)
C09_EXTENSION = (
    "DUA (CAST, 2024) como fundamento teórico declarado; la accesibilidad para la "
    "diversidad de estudiantes no se codificó con el libro v3."
)


def cargar(ruta):
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def v0():
    return cargar(V0)


@pytest.fixture(scope="module")
def v1():
    return cargar(V1)


def por_id(marco):
    return {c["id"]: c for c in marco["criterios"]}


def test_cabecera_y_niveles_en_orden(v1):
    assert v1["version"] == "v1"
    assert v1["decision"] == "D55"
    assert v1["niveles"] == ["base", "calidad", "innovacion"]


def test_nueve_criterios_en_orden_y_aprobados(v1):
    assert [c["id"] for c in v1["criterios"]] == IDS
    assert [c["estado"] for c in v1["criterios"]] == ["aprobado"] * 9


def test_tres_criterios_por_nivel_con_la_asignacion_exacta(v1):
    for nivel, ids in NIVELES.items():
        assert [c["id"] for c in v1["criterios"] if c["nivel"] == nivel] == ids


def test_dimension_y_temas_origen_identicos_a_v0(v0, v1):
    a, b = por_id(v0), por_id(v1)
    for cid in IDS:
        assert b[cid]["dimension"] == a[cid]["dimension"], cid
        assert b[cid]["temas_origen"] == a[cid]["temas_origen"], cid


@pytest.mark.parametrize("cid", SIN_CAMBIO)
def test_enunciados_sin_cambio_identicos_a_v0(v0, v1, cid):
    a, b = por_id(v0)[cid], por_id(v1)[cid]
    assert b["enunciado"] == a["enunciado"]
    assert b["criterio_corto"] == a["criterio_corto"]


def test_textos_nuevos_de_c01_c06_y_c09(v1):
    c = por_id(v1)
    assert c["C01"]["enunciado"] == C01_ENUNCIADO
    assert c["C06"]["criterio_corto"] == C06_CORTO
    assert c["C06"]["enunciado"] == C06_ENUNCIADO
    assert c["C09"]["enunciado"] == C09_ENUNCIADO
    assert c["C09"]["extension_teorica"] == C09_EXTENSION
    assert [i for i in IDS if "extension_teorica" in c[i]] == ["C09"]


def test_c01_y_c09_conservan_su_criterio_corto_de_v0(v0, v1):
    for cid in ("C01", "C09"):
        assert por_id(v1)[cid]["criterio_corto"] == por_id(v0)[cid]["criterio_corto"]


def test_sha256_de_v0_registrado_en_v1_coincide_con_el_archivo(v1):
    assert v1["fuente"]["archivo"] == "config/criterios_v0.yaml"
    assert v1["fuente"]["sha256"] == hashlib.sha256(V0.read_bytes()).hexdigest()


def test_fuente_origen_v0_y_descartados_copiados_de_v0(v0, v1):
    assert v1["fuente_origen_v0"] == v0["fuente"]
    assert v1["descartados"] == v0["descartados"]


def test_v0_sigue_congelado_con_c01_c06_y_c09_en_borrador(v0):
    estados = {c["id"]: c["estado"] for c in v0["criterios"]}
    borrador = "borrador: revisar Luis Fer"
    assert [i for i, e in estados.items() if e == borrador] == ["C01", "C06", "C09"]
    assert all(estados[i] == "aprobado" for i in SIN_CAMBIO)
    assert v0["version"] == "v0"
