"""Descarga de los PDF del inventario de referentes curriculares (Bloque 9, D56).

Solo baja documentos con estado «aprobado» (los aprueba Luis Fer) y solo de los dominios
de la lista explícita del inventario; una redirección a otro dominio hace fallar la
descarga. Lo descargado debe empezar con %PDF; si no, el script falla (el sitio puede
estar pidiendo sesión, captcha o aceptar términos: en ese caso se detiene y se avisa).
Nunca ejecuta ni abre lo descargado: solo guarda los bytes en data/raw/curriculo/ (fuera
de git) y le pide a pdfinfo el conteo de páginas. Registra en el inventario ruta, fecha,
tamaño, páginas y sha256.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.referentes_descarga_09 [--id ID ...]

Ingesta manual (PDF que descarga Luis Fer a mano, p. ej. PISA 2025 de la OCDE):

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.referentes_descarga_09 \\
        --ingesta-manual ID [--archivo NOMBRE.pdf]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml

from rs_pipeline import referentes_09 as R
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
INVENTARIO = RAIZ_REPO / "config" / "referentes_curriculares.yaml"
DESTINO = RAIZ_REPO / "data" / "raw" / "curriculo"
LIMITE_BYTES = 300 * 1024 * 1024
PAUSA_SEGUNDOS = 60
BLOQUE = 1024 * 1024
AGENTE = "rs-pipeline (tesis de maestría; lectura de documentos oficiales)"
AVISO_ACCESO = (
    "si el sitio pide iniciar sesión, captcha o aceptar términos, hay que detenerse "
    "y avisar a Luis Fer"
)


class RedireccionControlada(HTTPRedirectHandler):
    """Sigue redirecciones solo si el nuevo destino está en los dominios permitidos."""

    def __init__(self, dominios: list[str]) -> None:
        self.dominios = dominios

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not R.url_permitida(newurl, self.dominios):
            fallar(f"redirección a un dominio fuera de la lista: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def leer_en_bloques(respuesta, limite: int) -> bytes:
    """Lee la respuesta completa; falla si pasa del límite de tamaño."""
    partes: list[bytes] = []
    total = 0
    while bloque := respuesta.read(BLOQUE):
        total += len(bloque)
        if total > limite:
            fallar(f"el archivo pasa del límite de {limite} bytes; no se descarga")
        partes.append(bloque)
    return b"".join(partes)


def leer_url(url: str, dominios: list[str]) -> bytes:
    if not R.url_permitida(url, dominios):
        fallar(f"URL fuera de los dominios permitidos: {url}")
    abridor = build_opener(RedireccionControlada(dominios))
    peticion = Request(url, headers={"User-Agent": AGENTE})  # noqa: S310
    try:
        with abridor.open(peticion, timeout=PAUSA_SEGUNDOS) as respuesta:
            return leer_en_bloques(respuesta, LIMITE_BYTES)
    except OSError as error:
        fallar(f"no se pudo leer {url}: {error}; {AVISO_ACCESO}")


def verificar_pdf(contenido: bytes, url: str) -> None:
    if not contenido.startswith(b"%PDF"):
        fallar(f"lo descargado de {url} no empieza con %PDF; {AVISO_ACCESO}")


def paginas_pdf(ruta: Path) -> int:
    """Conteo de páginas con pdfinfo (poppler); falla si no lo puede leer."""
    programa = shutil.which("pdfinfo")
    if programa is None:
        fallar("no se encontró pdfinfo (poppler) en el sistema")
    resultado = subprocess.run(  # noqa: S603 - programa fijo y ruta propia
        [programa, str(ruta)],
        capture_output=True,
        text=True,
        timeout=PAUSA_SEGUNDOS,
        check=False,
    )
    pedazo = re.search(r"^Pages:\s+(\d+)\s*$", resultado.stdout, re.MULTILINE)
    if resultado.returncode != 0 or pedazo is None:
        fallar(f"pdfinfo no pudo leer {ruta.name}: {resultado.stderr.strip()[:200]}")
    return int(pedazo.group(1))


def sha256_de(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def guardar_pdf(doc: dict, contenido: bytes, destino: Path) -> Path:
    ruta = destino / f"{doc['id']}.pdf"
    if ruta.exists():
        fallar(f"{ruta} ya existe; no se sobrescribe (revisar a mano)")
    destino.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta


def descargar_documento(
    doc: dict,
    dominios: list[str],
    destino: Path,
    leer: Callable[[str, list[str]], bytes],
    hoy: date,
) -> bool:
    """Descarga un documento aprobado y llena sus campos. False si ya estaba bajado."""
    if doc["estado"] != "aprobado":
        fallar(f"{doc['id']}: solo se descargan documentos aprobados")
    if doc["sha256"] is not None:
        return False
    contenido = leer(doc["url_oficial"], dominios)
    verificar_pdf(contenido, doc["url_oficial"])
    ruta = guardar_pdf(doc, contenido, destino)
    try:
        paginas = paginas_pdf(ruta)
    except ErrorPipeline:
        ruta.unlink()
        raise
    doc["ruta_local"] = ruta.relative_to(RAIZ_REPO).as_posix()
    doc["fecha_descarga"] = hoy.isoformat()
    doc["tamano_bytes"] = len(contenido)
    doc["paginas"] = paginas
    doc["sha256"] = sha256_de(ruta)
    return True


def ingerir_manual(
    doc: dict, dominios: list[str], destino: Path, nombre: str | None, hoy: date
) -> None:
    """Registra un PDF que Luis Fer ya dejó en la carpeta de destino (sin red)."""
    if doc["estado"] != "aprobado_manual":
        fallar(
            f"{doc['id']}: la ingesta manual es solo para documentos aprobado_manual"
        )
    if doc["sha256"] is not None:
        fallar(f"{doc['id']}: ya está registrado; no se registra dos veces")
    if not R.url_permitida(doc["url_oficial"], dominios):
        fallar(f"{doc['id']}: url_oficial fuera de los dominios permitidos")
    ruta = (destino / (nombre or f"{doc['id']}.pdf")).resolve()
    if ruta.parent != destino.resolve():
        fallar(f"el archivo debe estar directamente en {destino}, no en {ruta.parent}")
    if not ruta.is_file():
        fallar(f"{doc['id']}: no encuentro {ruta}; descárgalo a mano y vuelve a correr")
    verificar_pdf(ruta.read_bytes()[:8], doc["url_oficial"])
    doc["ruta_local"] = ruta.relative_to(RAIZ_REPO).as_posix()
    doc["fecha_descarga"] = hoy.isoformat()
    doc["tamano_bytes"] = ruta.stat().st_size
    doc["paginas"] = paginas_pdf(ruta)
    doc["sha256"] = sha256_de(ruta)
    doc["notas"] = (
        f"{doc['notas']} Ingesta manual registrada el {hoy.isoformat()}.".strip()
    )


def cabecera_de_comentarios(ruta: Path) -> str:
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    comentarios = []
    for linea in lineas:
        if not linea.startswith("#"):
            break
        comentarios.append(linea)
    return "".join(comentarios)


def guardar_inventario(ruta: Path, inventario: dict) -> None:
    cabecera = cabecera_de_comentarios(ruta)
    cuerpo = yaml.safe_dump(inventario, allow_unicode=True, sort_keys=False, width=100)
    ruta.write_text(cabecera + cuerpo, encoding="utf-8")


def elegir(documentos: list[dict], ids: list[str] | None) -> list[dict]:
    if ids:
        desconocidos = sorted(set(ids) - {d["id"] for d in documentos})
        if desconocidos:
            fallar(f"ids que no están en el inventario: {desconocidos}")
        return [d for d in documentos if d["id"] in ids]
    return [d for d in documentos if d["estado"] == "aprobado"]


def ejecutar(
    ruta_inventario: Path,
    destino: Path,
    ids: list[str] | None = None,
    leer: Callable[[str, list[str]], bytes] = leer_url,
    hoy: date | None = None,
) -> list[str]:
    """Descarga lo pendiente, guarda el inventario tras cada archivo y da los ids."""
    inventario = yaml.safe_load(ruta_inventario.read_text(encoding="utf-8"))
    documentos = R.validar_inventario(inventario)
    bajados = []
    for doc in elegir(documentos, ids):
        if descargar_documento(
            doc, inventario["dominios_permitidos"], destino, leer, hoy or date.today()
        ):
            guardar_inventario(ruta_inventario, inventario)
            bajados.append(doc["id"])
    return bajados


def ejecutar_ingesta(
    ruta_inventario: Path,
    destino: Path,
    id_doc: str,
    nombre: str | None = None,
    hoy: date | None = None,
) -> None:
    inventario = yaml.safe_load(ruta_inventario.read_text(encoding="utf-8"))
    documentos = R.validar_inventario(inventario)
    elegidos = elegir(documentos, [id_doc])
    ingerir_manual(
        elegidos[0],
        inventario["dominios_permitidos"],
        destino,
        nombre,
        hoy or date.today(),
    )
    guardar_inventario(ruta_inventario, inventario)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--id", action="append", dest="ids", help="solo este id")
    analizador.add_argument(
        "--ingesta-manual", metavar="ID", help="registrar un PDF a mano"
    )
    analizador.add_argument("--archivo", help="nombre del PDF en data/raw/curriculo/")
    args = analizador.parse_args(argv)
    try:
        if args.ingesta_manual:
            ejecutar_ingesta(INVENTARIO, DESTINO, args.ingesta_manual, args.archivo)
            print(f"Registrado: {args.ingesta_manual}")
            return 0
        bajados = ejecutar(INVENTARIO, DESTINO, args.ids)
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Descargados: {bajados}" if bajados else "Nada pendiente de descargar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
