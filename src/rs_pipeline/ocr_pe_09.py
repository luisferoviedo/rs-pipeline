"""OCR de páginas del Programa curricular de Secundaria de Perú (PE-PCS-2016; D56, D57).

El PDF es un escaneo sin capa de texto. Este script pasa páginas a imagen con pdftoppm
(300 dpi), les recorta el encabezado «649-2016-MINEDU» y el pie, y lee el texto con
Tesseract (idioma spa). Por página guarda la imagen recortada, el texto (con la marca
«origen: OCR») y el TSV con la confianza por palabra en data/processed/curriculo/
(fuera de git). El JSON de procedencia (versiones, hashes, recortes, confianza por
página) va a outputs/ocr/ y SÍ se versiona: no contiene texto del documento.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.ocr_pe_09 --paginas 182 186

Si el sha256 del PDF no coincide con el del inventario, el script falla.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import yaml

from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
INVENTARIO = RAIZ_REPO / "config" / "referentes_curriculares.yaml"
ID_REFERENTE = "PE-PCS-2016"
DESTINO = RAIZ_REPO / "data" / "processed" / "curriculo" / "PE-PCS-2016_ocr"
PROCEDENCIA = RAIZ_REPO / "outputs" / "ocr"
RECORTES = RAIZ_REPO / "config" / "recortes_pe_pcs_2016.yaml"
PAGINAS_PERMITIDAS = range(177, 195)  # sección 6.9, Ciencia y Tecnología
DPI = 300
IDIOMA = "spa"
# Recorte inferior, como fracción de la altura de la página: quita el número de página
# y la parte baja del sello de visación (verificado a ojo en el piloto; debajo no hay
# texto). El recorte SUPERIOR (encabezado «649-2016-MINEDU») es distinto en cada página:
# se lee de config/recortes_pe_pcs_2016.yaml y debe estar verificado (D57, adenda).
RECORTE_INFERIOR = 0.905
CONFIANZA_BAJA = 60
UMBRAL_PAGINA = (
    85  # confianza media de página por debajo de la cual se marca para revisión
)
TSV_NIVEL_PALABRA = "5"
# Franja del sello de visación (esquina inferior izquierda de la imagen recortada).
ZONA_SELLO_ALTURA = 0.15
# Control del encabezado (D57): tras el recorte superior no debe quedar nada del
# encabezado «649-2016-MINEDU» en el texto leído. En p191 el hueco bajo el encabezado
# es de solo 10 px, así que además se exige que su primera línea sea la esperada.
PATRONES_ENCABEZADO = ("minedu", "649-2016")
PRIMERA_LINEA_ESPERADA = {191: "Estándares"}


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def ejecutar(orden: list[str]) -> subprocess.CompletedProcess[str]:
    """Corre un programa del sistema; si falla, el script falla con su mensaje."""
    r = subprocess.run(orden, capture_output=True, text=True, check=False)  # noqa: S603
    if r.returncode != 0:
        fallar(f"falló {orden[0]} (código {r.returncode}): {r.stderr.strip()}")
    return r


def tamano_pagina_pts(pdf: Path, pagina: int) -> tuple[float, float]:
    salida = ejecutar(
        ["pdfinfo", "-f", str(pagina), "-l", str(pagina), str(pdf)]
    ).stdout
    m = re.search(rf"Page\s+{pagina} size:\s+([\d.]+) x ([\d.]+) pts", salida)
    if m is None:
        fallar(f"pdfinfo no dio el tamaño de la página {pagina}")
    return float(m.group(1)), float(m.group(2))


def recorte_en_pixeles(
    ancho_pts: float, alto_pts: float, dpi: int, superior: float
) -> dict[str, int]:
    """Convierte el recorte (fracciones de la altura) a píxeles para pdftoppm."""
    ancho = round(ancho_pts * dpi / 72)
    alto = round(alto_pts * dpi / 72)
    y0 = round(alto * superior)
    y1 = round(alto * RECORTE_INFERIOR)
    return {
        "x": 0,
        "y": y0,
        "ancho": ancho,
        "alto": y1 - y0,
        "pagina_ancho": ancho,
        "pagina_alto": alto,
    }


def confianza_de_tsv(tsv: Path) -> dict[str, float | int]:
    """Confianza media por palabra (nivel 5 del TSV de Tesseract, texto no vacío)."""
    confs: list[float] = []
    with tsv.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if fila["level"] != TSV_NIVEL_PALABRA or not (fila["text"] or "").strip():
                continue
            conf = float(fila["conf"])
            if conf >= 0:
                confs.append(conf)
    if not confs:
        fallar(f"el TSV {tsv.name} no trae palabras con confianza")
    return {
        "palabras": len(confs),
        "confianza_media": round(sum(confs) / len(confs), 2),
        "palabras_confianza_baja": sum(c < CONFIANZA_BAJA for c in confs),
        "umbral_confianza_baja": CONFIANZA_BAJA,
    }


def zona_sello(tsv: Path, ancho: int, alto: int) -> list[dict]:
    """Líneas de la franja inferior izquierda (último 15 % de la altura, izquierda).

    El sello de visación borra o daña texto ahí (D57). Solo se listan, con su confianza
    media; no se corrige nada. Una línea cuenta si su palabra más alta empieza en la
    franja y su primera palabra está en la mitad izquierda.
    """
    lineas: dict[tuple[str, str, str], list[dict]] = {}
    with tsv.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if fila["level"] != TSV_NIVEL_PALABRA or not (fila["text"] or "").strip():
                continue
            if float(fila["conf"]) < 0:
                continue
            clave = (fila["block_num"], fila["par_num"], fila["line_num"])
            lineas.setdefault(clave, []).append(fila)
    limite = alto * (1 - ZONA_SELLO_ALTURA)
    salida = []
    for (bloque, parrafo, linea), palabras in lineas.items():
        if min(int(w["top"]) for w in palabras) < limite:
            continue
        if min(int(w["left"]) for w in palabras) >= ancho / 2:
            continue
        confs = [float(w["conf"]) for w in palabras]
        salida.append(
            {
                "bloque": int(bloque),
                "parrafo": int(parrafo),
                "linea": int(linea),
                "palabras": len(palabras),
                "confianza_media": round(sum(confs) / len(confs), 2),
                "texto": " ".join(w["text"] for w in palabras),
            }
        )
    return salida


def tokens_de_tsv(tsv: Path) -> list[str]:
    """Palabras (nivel 5 del TSV, texto no vacío) tal como las leyó Tesseract."""
    with tsv.open(encoding="utf-8", newline="") as f:
        return [
            fila["text"]
            for fila in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
            if fila["level"] == TSV_NIVEL_PALABRA and (fila["text"] or "").strip()
        ]


def primera_linea(texto: str) -> str:
    return next((x.strip() for x in texto.splitlines() if x.strip()), "")


def controlar_encabezado(pagina: int, texto: str, tokens: list[str]) -> list[str]:
    """Problemas del encabezado en lo leído; lista vacía si todo está bien.

    No ajusta nada: si hay problemas, una persona revisa el recorte a ojo.
    """
    problemas = []
    compacto = re.sub(r"\s+", "", texto).lower()
    for patron in PATRONES_ENCABEZADO:
        if patron in compacto:
            problemas.append(f"p{pagina}: el texto leído contiene «{patron}»")
    problemas += [
        f"p{pagina}: token con MINEDU: {t!r}" for t in tokens if "minedu" in t.lower()
    ]
    esperada = PRIMERA_LINEA_ESPERADA.get(pagina)
    if esperada and not primera_linea(texto).startswith(esperada):
        problemas.append(
            f"p{pagina}: la primera línea debe empezar por «{esperada}» y es "
            f"{primera_linea(texto)!r}"
        )
    return problemas


def versiones() -> dict[str, str]:
    t = ejecutar(["tesseract", "--version"])
    texto_t = (t.stdout + t.stderr).splitlines()
    tesseract = next(
        (x.strip() for x in texto_t if x.strip().startswith("tesseract ")), ""
    )
    leptonica = next((x.strip() for x in texto_t if "leptonica" in x.lower()), "")
    p = ejecutar(["pdftoppm", "-v"])
    poppler = next(
        (x.strip() for x in (p.stdout + p.stderr).splitlines() if "version" in x), ""
    )
    if not (tesseract and leptonica and poppler):
        fallar("no se pudieron leer las versiones de Tesseract, Leptonica o poppler")
    prefijo = ejecutar(["brew", "--prefix"]).stdout.strip()
    modelo = Path(prefijo) / "share" / "tessdata" / f"{IDIOMA}.traineddata"
    if not modelo.is_file():
        fallar(f"no existe {modelo}")
    return {
        "tesseract": tesseract,
        "leptonica": leptonica,
        "poppler_pdftoppm": poppler,
        f"{IDIOMA}.traineddata_sha256": sha256_de(modelo),
    }


def cargar_recortes(paginas: list[int]) -> dict[int, float]:
    """Recorte superior (fracción) de cada página pedida, tomado del YAML congelado.

    Falla si el YAML no existe, si falta una página o si su `verificado_por` está vacío:
    un recorte sin revisar a ojo no se usa.
    """
    if not RECORTES.is_file():
        fallar(f"no existe {RECORTES.relative_to(RAIZ_REPO)}")
    config = yaml.safe_load(RECORTES.read_text(encoding="utf-8"))
    por_pagina: dict[int, dict] = {}
    for fila in config.get("paginas", []):
        if fila["pagina"] in por_pagina:
            fallar(f"p{fila['pagina']}: aparece dos veces en {RECORTES.name}")
        por_pagina[fila["pagina"]] = fila
    recortes: dict[int, float] = {}
    for pagina in paginas:
        fila = por_pagina.get(pagina)
        if fila is None:
            fallar(f"p{pagina}: no hay recorte en {RECORTES.name}")
        if not str(fila.get("verificado_por") or "").strip():
            fallar(f"p{pagina}: recorte sin verificar (verificado_por vacío)")
        recortes[pagina] = float(fila["recorte_superior"])
    return recortes


def pdf_del_inventario() -> tuple[Path, str]:
    inv = yaml.safe_load(INVENTARIO.read_text(encoding="utf-8"))
    docs = [d for d in inv["documentos"] if d["id"] == ID_REFERENTE]
    if len(docs) != 1:
        fallar(f"el inventario debe tener exactamente un {ID_REFERENTE}")
    ruta = RAIZ_REPO / docs[0]["ruta_local"]
    if not ruta.is_file():
        fallar(f"no existe {ruta}")
    hash_inventario = docs[0]["sha256"]
    hash_real = sha256_de(ruta)
    if hash_real != hash_inventario:
        fallar(
            f"sha256 del PDF ({hash_real}) distinto del inventario ({hash_inventario})"
        )
    return ruta, hash_real


def ocr_pagina(pdf: Path, pagina: int, superior: float) -> dict:
    ancho_pts, alto_pts = tamano_pagina_pts(pdf, pagina)
    r = recorte_en_pixeles(ancho_pts, alto_pts, DPI, superior)
    DESTINO.mkdir(parents=True, exist_ok=True)
    base = DESTINO / f"p{pagina:03d}"
    ejecutar(
        [
            "pdftoppm",
            "-r",
            str(DPI),
            "-f",
            str(pagina),
            "-l",
            str(pagina),
            "-gray",
            "-png",
            "-singlefile",
            "-x",
            str(r["x"]),
            "-y",
            str(r["y"]),
            "-W",
            str(r["ancho"]),
            "-H",
            str(r["alto"]),
            str(pdf),
            str(base),
        ]
    )
    png = base.with_suffix(".png")
    ejecutar(
        [
            "tesseract",
            str(png),
            str(base),
            "-l",
            IDIOMA,
            "--dpi",
            str(DPI),
            "tsv",
            "txt",
        ]
    )
    txt, tsv = base.with_suffix(".txt"), base.with_suffix(".tsv")
    marca = (
        f"origen: OCR (Tesseract, {IDIOMA}, {DPI} dpi) de {ID_REFERENTE}, "
        f"página PDF {pagina}\n\n"
    )
    leido = txt.read_text(encoding="utf-8")
    txt.write_text(marca + leido, encoding="utf-8")
    problemas = controlar_encabezado(pagina, leido, tokens_de_tsv(tsv))
    confianza = confianza_de_tsv(tsv)
    zona = zona_sello(tsv, r["ancho"], r["alto"])
    registro = {
        "pagina_pdf": pagina,
        "recorte_superior_fraccion": superior,
        "recorte_px": r,
        **confianza,
        "umbral_pagina": UMBRAL_PAGINA,
        "bajo_umbral_pagina": confianza["confianza_media"] < UMBRAL_PAGINA,
        "salidas": {
            p.name: {"sha256": sha256_de(p), "ruta": str(p.relative_to(RAIZ_REPO))}
            for p in (png, txt, tsv)
        },
        "revisar_zona_sello": zona,
        "problemas_encabezado": problemas,
    }
    return registro


def escribir_zona_sello_csv(paginas: list[dict]) -> Path:
    """Texto de las líneas de la zona del sello; fuera de git (trae texto)."""
    ruta = DESTINO / "revisar_zona_sello.csv"
    campos = [
        "pagina",
        "bloque",
        "parrafo",
        "linea",
        "palabras",
        "confianza_media",
        "texto",
    ]
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for pag in paginas:
            for linea in pag["revisar_zona_sello"]:
                w.writerow({"pagina": pag["pagina_pdf"], **linea})
    return ruta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--paginas", type=int, nargs="+", required=True, help="páginas PDF (177–194)"
    )
    ap.add_argument(
        "--sufijo", default="", help="sufijo del JSON de procedencia (p. ej. v2)"
    )
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9]*", args.sufijo):
        fallar(f"sufijo no válido: {args.sufijo!r} (solo letras y números)")
    fuera = [p for p in args.paginas if p not in PAGINAS_PERMITIDAS]
    if fuera:
        fallar(f"páginas fuera de 177–194: {fuera}")
    recortes = cargar_recortes(args.paginas)
    ps = sorted(args.paginas)
    contiguas = ps == list(range(ps[0], ps[-1] + 1)) and len(ps) > 2
    nombre = f"{ps[0]}-{ps[-1]}" if contiguas else "_".join(str(p) for p in ps)
    if args.sufijo:
        nombre += f"_{args.sufijo}"
    destino = PROCEDENCIA / f"{ID_REFERENTE}_ocr_p{nombre}.json"
    if destino.exists():
        fallar(f"{destino.relative_to(RAIZ_REPO)} ya existe; no se sobrescribe")
    pdf, hash_pdf = pdf_del_inventario()
    registro = {
        "id": ID_REFERENTE,
        "decision": "D57",
        "fecha": date.today().isoformat(),
        "entrada": {"ruta": str(pdf.relative_to(RAIZ_REPO)), "sha256": hash_pdf},
        "herramientas": versiones(),
        "dpi": DPI,
        "idioma": IDIOMA,
        "recorte": {
            "superior": "por página, de config/recortes_pe_pcs_2016.yaml",
            "superior_config": {
                "ruta": str(RECORTES.relative_to(RAIZ_REPO)),
                "sha256": sha256_de(RECORTES),
            },
            "inferior_fraccion_altura": RECORTE_INFERIOR,
            "quita": (
                "encabezado 649-2016-MINEDU, número de página y parte baja del sello"
            ),
        },
        "paginas": [ocr_pagina(pdf, p, recortes[p]) for p in args.paginas],
    }
    problemas = [x for pag in registro["paginas"] for x in pag["problemas_encabezado"]]
    if problemas:
        fallar(
            "control del encabezado: no se escribe la procedencia; revisar el recorte "
            "a ojo (no se ajusta solo): " + " | ".join(problemas)
        )
    for pag in registro["paginas"]:
        del pag["problemas_encabezado"]
        pag["control_encabezado"] = "ok"
    escribir_zona_sello_csv(registro["paginas"])
    for pag in registro["paginas"]:
        for linea in pag["revisar_zona_sello"]:
            del linea["texto"]  # el texto va solo al CSV fuera de git
    PROCEDENCIA.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for pag in registro["paginas"]:
        print(
            f"p{pag['pagina_pdf']}: {pag['palabras']} palabras, "
            f"confianza media {pag['confianza_media']}"
        )
    print(f"procedencia: {destino.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()
