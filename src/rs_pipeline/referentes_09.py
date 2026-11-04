"""Inventario de referentes curriculares del Bloque 9 (D56): esquema y validación.

El inventario (config/referentes_curriculares.yaml) lista los documentos oficiales
que se homologan contra el marco v1. Aquí solo se valida su forma; la descarga vive
en referentes_descarga_09. Falla (ErrorPipeline) si falta un campo, si un valor no
es de los permitidos o si un documento aprobado apunta a un dominio fuera de la lista
explícita.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from rs_pipeline.semantico_texto import ErrorPipeline, fallar

POR_VERIFICAR = "POR VERIFICAR"
ROLES = {"curriculo", "marco_evaluacion", "contexto_unesco"}
ESTADOS = {"por_verificar", "aprobado", "aprobado_manual", "referencia"}
# aprobado_manual: aprobado; Luis Fer baja el PDF a mano (el sitio rechaza scripts)
APROBADOS = {"aprobado", "aprobado_manual"}
# Pueden traer los campos de descarga: aprobados y referencia (esta, por ingesta manual)
REGISTRABLES = APROBADOS | {"referencia"}
PAISES = {"Colombia", "Perú", "Brasil", "México", "Argentina", "OCDE", "UNESCO"}
CAMPOS_BASE = [
    "id",
    "rol",
    "pais",
    "organismo",
    "titulo",
    "version",
    "fecha",
    "acto_de_adopcion",
    "url_oficial",
    "idioma",
    "nivel_cine",
    "grados_originales",
    "area",
    "estado",
    "notas",
]
CAMPOS_DESCARGA = ["ruta_local", "fecha_descarga", "tamano_bytes", "paginas", "sha256"]
CAMPOS = CAMPOS_BASE + CAMPOS_DESCARGA
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def url_permitida(url: str, dominios: list[str]) -> bool:
    """https, sin usuario, y servidor igual a un dominio listado o subdominio de uno."""
    partes = urlsplit(url)
    servidor = (partes.hostname or "").lower()
    if partes.scheme != "https" or partes.username or not servidor:
        return False
    return any(servidor == d or servidor.endswith("." + d) for d in dominios)


def validar_dominios(dominios: object) -> list[str]:
    if not isinstance(dominios, list) or not dominios:
        fallar("el inventario no trae 'dominios_permitidos' como lista")
    for dominio in dominios:
        if not isinstance(dominio, str) or not re.fullmatch(
            r"[a-z0-9.-]+\.[a-z]{2,}", dominio
        ):
            fallar(
                f"dominio no válido en 'dominios_permitidos' (sin comodines): "
                f"{dominio!r}"
            )
    if len(set(dominios)) != len(dominios):
        fallar("'dominios_permitidos' tiene dominios repetidos")
    return dominios


def validar_campos(doc: dict) -> None:
    id_doc = doc.get("id", "?")
    faltan = [c for c in CAMPOS if c not in doc]
    sobran = [c for c in doc if c not in CAMPOS]
    if faltan or sobran:
        fallar(f"{id_doc}: campos que faltan {faltan} o que sobran {sobran}")
    if doc["rol"] not in ROLES:
        fallar(f"{id_doc}: rol {doc['rol']!r} no está en {sorted(ROLES)}")
    if doc["estado"] not in ESTADOS:
        fallar(f"{id_doc}: estado {doc['estado']!r} no está en {sorted(ESTADOS)}")
    if doc["pais"] not in PAISES:
        fallar(f"{id_doc}: país {doc['pais']!r} no está en {sorted(PAISES)}")


def validar_cine(doc: dict) -> None:
    cine = doc["nivel_cine"]
    if not isinstance(cine, list) or not set(cine) <= {2, 3}:
        fallar(f"{doc['id']}: nivel_cine debe ser una lista con 2 y/o 3, no {cine!r}")
    if doc["rol"] == "curriculo" and not cine:
        fallar(f"{doc['id']}: un currículo debe declarar su nivel CINE (2 y/o 3)")


def validar_descarga(doc: dict) -> None:
    id_doc = doc["id"]
    llenos = [c for c in CAMPOS_DESCARGA if doc[c] is not None]
    if llenos and len(llenos) != len(CAMPOS_DESCARGA):
        fallar(f"{id_doc}: los campos de descarga están a medias: {llenos}")
    if llenos and not SHA256.fullmatch(str(doc["sha256"])):
        fallar(f"{id_doc}: sha256 no válido: {doc['sha256']!r}")
    if llenos and doc["estado"] not in REGISTRABLES:
        fallar(
            f"{id_doc}: solo se descargan documentos aprobados, no {doc['estado']!r}"
        )


def validar_documento(doc: dict, dominios: list[str]) -> None:
    validar_campos(doc)
    validar_cine(doc)
    validar_descarga(doc)
    if doc["estado"] in APROBADOS and not url_permitida(
        str(doc["url_oficial"]), dominios
    ):
        fallar(
            f"{doc['id']}: url_oficial fuera de los dominios permitidos: "
            f"{doc['url_oficial']}"
        )


def validar_inventario(inventario: dict) -> list[dict]:
    """Devuelve los documentos si el inventario es válido; si no, falla."""
    if not isinstance(inventario, dict) or "documentos" not in inventario:
        fallar("el inventario no trae la lista 'documentos'")
    dominios = validar_dominios(inventario.get("dominios_permitidos"))
    documentos = inventario["documentos"]
    ids = [d.get("id") for d in documentos]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        fallar(f"ids repetidos en el inventario: {repetidos}")
    for doc in documentos:
        validar_documento(doc, dominios)
    return documentos


__all__ = ["ErrorPipeline", "url_permitida", "validar_inventario"]
