"""Extracción de enunciados curriculares del Bloque 9 (D56, D60): ICFES y PISA.

Lee los PDF del inventario (config/referentes_curriculares.yaml) con pdftotext y saca
una unidad por enunciado:

- CO-ICFES-MR-CN-S11: cada evidencia de la Tabla 5 (págs. 38-45), con su afirmación y
  su competencia. La tabla tiene tres columnas; se leen las palabras con sus
  coordenadas (pdftotext -bbox) y se asigna cada palabra a su columna por la x.
- OCDE-PISA2025-MARCO: cada descriptor (viñeta) de los recuadros 2.3, 2.4 y 2.5
  (págs. 34-36), con su competencia, en inglés (texto original; D60).

Los textos van a data/processed/curriculo/ (fuera de git), cada uno con la ruta y el
sha256 de su PDF y su página. A outputs/tablas/ va solo el resumen: conteos, rutas y
hashes de las entradas y de la salida, versión de pdftotext. Si el sha256 de un PDF no
coincide con el del inventario, o la estructura leída no es la esperada, el script
falla.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.extraccion_09
"""

from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

import yaml

from rs_pipeline.ocr_pe_09 import ejecutar, sha256_de
from rs_pipeline.referentes_09 import validar_inventario
from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
INVENTARIO = RAIZ_REPO / "config" / "referentes_curriculares.yaml"
SALIDA_DATOS = RAIZ_REPO / "data" / "processed" / "curriculo" / "enunciados_09_v1.jsonl"
SALIDA_RESUMEN = RAIZ_REPO / "outputs" / "tablas" / "extraccion_09_v1.json"

# --- ICFES ------------------------------------------------------------------
ID_ICFES = "CO-ICFES-MR-CN-S11"
PAGINAS_ICFES = (38, 45)  # Tabla 5. Especificaciones de la prueba
# Límites de columna (puntos PDF, medidos en el piloto del 25 nov 2026): la columna
# Competencia empieza en x ≈ 91, Afirmación en x ≈ 183-187 y los números de evidencia
# en x ≈ 344-349. Una palabra va a la columna cuyo inicio está a su izquierda.
X_AFIRMACION = 165.0
X_EVIDENCIA = 340.0
Y_PIE = 700.0  # debajo: número de página y «Marco de referencia»
# Aviso al pie de la tabla en las págs. 38-44. Su altura cambia (y entre 667 y 713), así
# que Y_PIE no basta para sacarlo: la tabla termina donde empieza el aviso.
AVISO_CONTINUA = "Continúa en la siguiente página"
TOLERANCIA_LINEA = 3.0  # palabras con y a menos de 3 pt están en la misma línea
SALTO_ROTULO = 20.0  # en la 1.ª columna, líneas a menos de 20 pt son el mismo rótulo
# Tabla 5 contada contra el PDF: competencia -> {afirmación: número de evidencias}
ESTRUCTURA_ICFES = {
    "Explicación de fenómenos": {"1": 3, "2": 9, "3": 3},
    "Uso comprensivo del conocimiento científico": {"4": 8, "5": 7},
    "Indagación": {"6": 2, "7": 4, "8": 2, "9": 5},
}

# --- PISA -------------------------------------------------------------------
ID_PISA = "OCDE-PISA2025-MARCO"
PAGINAS_PISA = (34, 36)  # Box 2.3, 2.4 y 2.5
DESCRIPTORES_PISA = {1: 6, 2: 4, 3: 5}  # contados a ojo en el piloto

RE_PALABRA = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="[\d.]+">([^<]*)</word>'
)
RE_ID_EVIDENCIA = re.compile(r"^(\d{1,2})\.(\d{1,2})$")
RE_ID_AFIRMACION = re.compile(r"^(\d{1,2})\.$")
RE_BOX = re.compile(r"^\s*Box 2\.[345]\. PISA 2025 Science Competency ([123])\s*$")
RE_VINETA = re.compile(r"^(\s*)•\s+(\S.*)$")


# --- Utilidades ----------------------------------------------------------------


def documento_del_inventario(id_doc: str) -> dict:
    datos = yaml.safe_load(INVENTARIO.read_text(encoding="utf-8"))
    for doc in validar_inventario(datos):
        if doc["id"] == id_doc:
            return doc
    fallar(f"{id_doc} no está en el inventario")


def pdf_verificado(doc: dict) -> Path:
    """Ruta del PDF; falla si no existe o si su sha256 no es el del inventario."""
    if doc["ruta_local"] is None:
        fallar(f"{doc['id']}: el inventario no tiene registrado el PDF")
    ruta = RAIZ_REPO / doc["ruta_local"]
    if not ruta.is_file():
        fallar(f"no existe {ruta}")
    if sha256_de(ruta) != doc["sha256"]:
        fallar(f"el sha256 de {ruta.name} no coincide con el del inventario")
    return ruta


def unir(palabras: list[str]) -> str:
    """Une palabras en un texto y repara los cortes de línea con guion."""
    texto = " ".join(palabras)
    texto = re.sub(r"(\w)- (\w)", r"\1\2", texto)
    return re.sub(r"\s+", " ", texto).strip()


# --- ICFES: palabras con coordenadas -----------------------------------------


def palabras_por_pagina(bbox_html: str) -> list[list[tuple[str, float, float]]]:
    """Del HTML de `pdftotext -bbox`: por página, (palabra, x, y)."""
    paginas = []
    for bloque in bbox_html.split("<page ")[1:]:
        leidas = RE_PALABRA.findall(bloque)
        if len(leidas) != bloque.count("<word "):
            fallar("pdftotext -bbox: hay palabras que no se pudieron leer")
        paginas.append([(html.unescape(w), float(x), float(y)) for x, y, w in leidas])
    return paginas


def y_encabezado(palabras: list[tuple[str, float, float]]) -> float:
    """y de la fila «Competencia Afirmación Evidencia» de la tabla."""
    for w, x, y in palabras:
        if w == "Evidencia" and x > X_EVIDENCIA:
            return y
    fallar("no encontré el encabezado «Evidencia» de la tabla en una página")


def lineas_de_columna(
    palabras: list[tuple[str, float, float]], x_min: float, x_max: float
) -> list[tuple[float, list[str]]]:
    """Palabras de una columna agrupadas en líneas, de arriba abajo."""
    sel = sorted((y, x, w) for w, x, y in palabras if x_min <= x < x_max)
    lineas: list[tuple[float, list[tuple[float, str]]]] = []
    for y, x, w in sel:
        if lineas and abs(y - lineas[-1][0]) <= TOLERANCIA_LINEA:
            lineas[-1][1].append((x, w))
        else:
            lineas.append((y, [(x, w)]))
    return [(y, [w for _, w in sorted(ws)]) for y, ws in lineas]


def y_fin_de_tabla(palabras: list[tuple[str, float, float]]) -> float:
    """y donde termina la tabla: el aviso de continuación, si está, o el pie."""
    for y, ws in lineas_de_columna(palabras, X_EVIDENCIA, 1e9):
        if " ".join(ws) == AVISO_CONTINUA:
            return min(y - TOLERANCIA_LINEA, Y_PIE)
    return Y_PIE


def cuerpo_tabla(
    palabras: list[tuple[str, float, float]],
) -> list[tuple[str, float, float]]:
    """Quita título, encabezado de la tabla, aviso de continuación y pie de página."""
    y0 = y_encabezado(palabras)
    fin = y_fin_de_tabla(palabras)
    return [(w, x, y) for w, x, y in palabras if y0 + 5 < y < fin]


def rotulos_competencia(
    paginas: list, pagina_inicial: int
) -> list[tuple[int, float, str]]:
    """Rótulos de la 1.ª columna: líneas a menos de SALTO_ROTULO pt forman un rótulo."""
    rotulos: list[tuple[int, float, list[str]]] = []
    for k, pal in enumerate(paginas):
        previo = None
        for y, ws in lineas_de_columna(cuerpo_tabla(pal), 0, X_AFIRMACION):
            if previo is not None and y - previo <= SALTO_ROTULO:
                rotulos[-1][2].extend(ws)
            else:
                rotulos.append((pagina_inicial + k, y, list(ws)))
            previo = y
    return [(p, y, unir(ws)) for p, y, ws in rotulos]


def bloques_de_columna(
    paginas: list, pagina_inicial: int, x_min: float, x_max: float, patron: re.Pattern
) -> list[dict]:
    """Une las líneas de una columna en bloques que empiezan con un número (patron)."""
    bloques: list[dict] = []
    for k, pal in enumerate(paginas):
        for y, ws in lineas_de_columna(cuerpo_tabla(pal), x_min, x_max):
            if patron.match(ws[0]):
                bloques.append(
                    {
                        "num": ws[0].rstrip("."),
                        "pagina": pagina_inicial + k,
                        "y": y,
                        "palabras": ws[1:],
                    }
                )
            elif not bloques:
                suelto = " ".join(ws)
                fallar(
                    f"p{pagina_inicial + k}: texto sin número que lo abra ({suelto})"
                )
            else:
                bloques[-1]["palabras"].extend(ws)
    return bloques


def extraer_icfes_sin_validar(
    bbox_html: str, pagina_inicial: int
) -> tuple[list[dict], dict[str, str]]:
    """Evidencias con su afirmación y competencia, y el texto de cada afirmación."""
    paginas = palabras_por_pagina(bbox_html)
    rotulos = rotulos_competencia(paginas, pagina_inicial)
    afirm = bloques_de_columna(
        paginas, pagina_inicial, X_AFIRMACION, X_EVIDENCIA, RE_ID_AFIRMACION
    )
    evid = bloques_de_columna(
        paginas, pagina_inicial, X_EVIDENCIA, 1e9, RE_ID_EVIDENCIA
    )
    comp_de: dict[str, str] = {}
    for a in afirm:
        previos = [
            r
            for r in rotulos
            if (r[0], r[1]) <= (a["pagina"], a["y"] + TOLERANCIA_LINEA)
        ]
        if not previos:
            fallar(f"ICFES: la afirmación {a['num']} no tiene rótulo de competencia")
        comp_de[a["num"]] = previos[-1][2]
    afirm_texto = {a["num"]: unir(a["palabras"]) for a in afirm}
    if len(afirm_texto) != len(afirm):
        fallar(f"ICFES: afirmación repetida en {[a['num'] for a in afirm]}")
    salida = []
    for e in evid:
        n_afirm = e["num"].split(".")[0]
        if n_afirm not in afirm_texto:
            fallar(f"ICFES: la evidencia {e['num']} no tiene afirmación {n_afirm}.")
        salida.append(
            {
                "id": e["num"],
                "pagina": e["pagina"],
                "afirmacion": n_afirm,
                "competencia": comp_de[n_afirm],
                "texto": unir(e["palabras"]),
            }
        )
    return salida, afirm_texto


def extraer_icfes(
    bbox_html: str, pagina_inicial: int
) -> tuple[list[dict], dict[str, str]]:
    """Como extraer_icfes_sin_validar, pero falla si la estructura no es la esperada."""
    evid, afirm = extraer_icfes_sin_validar(bbox_html, pagina_inicial)
    validar_icfes(evid, afirm)
    return evid, afirm


def validar_icfes(evid: list[dict], afirm: dict[str, str]) -> None:
    """Falla si la estructura de la tabla no es la esperada."""
    por_afirm: dict[str, list[int]] = {}
    leida: dict[str, dict[str, int]] = {}
    for e in evid:
        a, n = e["id"].split(".")
        por_afirm.setdefault(a, []).append(int(n))
        conteo = leida.setdefault(e["competencia"], {})
        conteo[a] = conteo.get(a, 0) + 1
    for a in afirm:
        nums = por_afirm.get(a, [])
        if not nums or nums != list(range(1, len(nums) + 1)):
            fallar(f"ICFES: evidencias de la afirmación {a} no consecutivas: {nums}")
    if leida != ESTRUCTURA_ICFES:
        fallar(
            "ICFES: competencias, afirmaciones o evidencias distintas de las "
            f"esperadas. Leído: {leida}. Esperado: {ESTRUCTURA_ICFES}"
        )
    textos = {e["id"]: e["texto"] for e in evid}
    textos |= {f"afirmación {a}": t for a, t in afirm.items()}
    # en la tabla todos terminan en punto: si no, hay texto cortado o algo pegado
    malos = [k for k, t in textos.items() if len(t.split()) < 3 or t[-1:] != "."]
    if malos:
        fallar(f"ICFES: textos vacíos, cortados o con algo pegado: {malos}")


# --- PISA: recuadros en texto con -layout --------------------------------------


def extraer_pisa(texto_layout: str, pagina_inicial: int) -> list[dict]:
    """Descriptores (viñetas) de los recuadros 2.3-2.5, con competencia y página."""
    unidades: list[dict] = []
    # pdftotext separa las páginas con un salto de formulario (\f)
    for k, hoja in enumerate(texto_layout.split("\f")):
        _recuadros_de_pagina(hoja.splitlines(), pagina_inicial + k, unidades)
    for u in unidades:
        u["texto"] = unir(u.pop("partes"))
    validar_pisa(unidades)
    return unidades


def _recuadros_de_pagina(lineas: list[str], pagina: int, unidades: list) -> None:
    i = 0
    while i < len(lineas):
        m = RE_BOX.match(lineas[i])
        if m is None:
            i += 1
            continue
        recuadro = {
            "competencia": int(m.group(1)),
            "titulo": lineas[i + 1].strip(),
            "pagina": pagina,
        }
        i += 2
        while i < len(lineas) and RE_VINETA.match(lineas[i]) is None:
            i += 1  # frase que introduce la lista («…demonstrating the ability to:»)
        i = _vinetas_pisa(lineas, i, recuadro, unidades)


def _vinetas_pisa(lineas: list[str], i: int, recuadro: dict, unidades: list) -> int:
    """Lee las viñetas desde la línea i; una viñeta sigue en líneas más sangradas."""
    n = 0
    while i < len(lineas):
        m = RE_VINETA.match(lineas[i])
        if m is not None:
            n += 1
            unidades.append({**recuadro, "n": n, "partes": [m.group(2)]})
            sangria = len(m.group(1)) + 2
        elif lineas[i].strip() and len(lineas[i]) - len(lineas[i].lstrip()) > sangria:
            unidades[-1]["partes"].append(lineas[i].strip())
        else:
            break  # línea en blanco o párrafo normal: termina el recuadro
        i += 1
    return i


def validar_pisa(unidades: list[dict]) -> None:
    conteo = {c: 0 for c in DESCRIPTORES_PISA}
    for u in unidades:
        conteo[u["competencia"]] += 1
    if conteo != DESCRIPTORES_PISA:
        fallar(
            f"PISA: descriptores por competencia {conteo}, "
            f"esperados {DESCRIPTORES_PISA}"
        )


# --- Salida -------------------------------------------------------------------


def procedencia(doc: dict) -> dict:
    """Campos comunes de cada unidad: de qué documento, archivo y versión viene."""
    return {
        "documento": doc["id"],
        "archivo": doc["ruta_local"],
        "sha256_archivo": doc["sha256"],
        "pais": doc["pais"],
        "nivel_cine": doc["nivel_cine"],
        "grados": doc["grados_originales"],
    }


def registros_icfes(doc: dict, evid: list[dict], afirm: dict[str, str]) -> list[dict]:
    return [
        {
            "id_unidad": f"{doc['id']}:E{e['id']}",
            **procedencia(doc),
            "tipo_unidad": "evidencia_icfes",
            "competencia": e["competencia"],
            "afirmacion": f"{e['afirmacion']}. {afirm[e['afirmacion']]}",
            "texto": e["texto"],
            "texto_es": e["texto"],
            "idioma": "es",
            "pagina": e["pagina"],
        }
        for e in evid
    ]


def registros_pisa(doc: dict, unidades: list[dict]) -> list[dict]:
    return [
        {
            "id_unidad": f"{doc['id']}:C{u['competencia']}.{u['n']}",
            **procedencia(doc),
            "tipo_unidad": "descriptor_pisa",
            "competencia": f"Competency {u['competencia']}: {u['titulo']}",
            "afirmacion": None,
            "texto": u["texto"],
            "texto_es": None,  # la traducción se agrega aparte (D60)
            "idioma": "en",
            "pagina": u["pagina"],
        }
        for u in unidades
    ]


def version_pdftotext() -> str:
    r = ejecutar(["pdftotext", "-v"])
    return (r.stderr or r.stdout).splitlines()[0].strip()


def relativa(ruta: Path) -> str:
    """Ruta desde la raíz del repo; completa si está fuera (tests)."""
    dentro = ruta.is_relative_to(RAIZ_REPO)
    return str(ruta.relative_to(RAIZ_REPO) if dentro else ruta)


def resumen_documento(doc: dict, paginas: tuple[int, int], conteos: dict) -> dict:
    return {
        "archivo": doc["ruta_local"],
        "sha256": doc["sha256"],
        "paginas": list(paginas),
        **conteos,
    }


def correr(salida_datos: Path, salida_resumen: Path) -> dict:
    for ruta in (salida_datos, salida_resumen):
        if ruta.exists():
            fallar(f"ya existe {ruta}; no se sobrescribe una extracción anterior")
    d_icfes = documento_del_inventario(ID_ICFES)
    d_pisa = documento_del_inventario(ID_PISA)
    pdf_i, pdf_p = pdf_verificado(d_icfes), pdf_verificado(d_pisa)
    a, b = PAGINAS_ICFES
    orden = ["pdftotext", "-bbox", "-f", str(a), "-l", str(b), str(pdf_i), "-"]
    evid, afirm = extraer_icfes(ejecutar(orden).stdout, a)
    a, b = PAGINAS_PISA
    orden = ["pdftotext", "-layout", "-f", str(a), "-l", str(b), str(pdf_p), "-"]
    pisa = extraer_pisa(ejecutar(orden).stdout, a)
    registros = registros_icfes(d_icfes, evid, afirm) + registros_pisa(d_pisa, pisa)
    version = version_pdftotext()  # antes de escribir: si falla, no queda nada a medias
    salida_datos.parent.mkdir(parents=True, exist_ok=True)
    with salida_datos.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    conteos_icfes = {
        "competencias": len({e["competencia"] for e in evid}),
        "afirmaciones": len(afirm),
        "evidencias": len(evid),
    }
    conteos_pisa = {
        "competencias": len({u["competencia"] for u in pisa}),
        "descriptores": len(pisa),
    }
    resumen = {
        "decision": "D60",
        "fecha": date.today().isoformat(),
        "pdftotext": version,
        "inventario": {
            "archivo": relativa(INVENTARIO),
            "sha256": sha256_de(INVENTARIO),
        },
        "documentos": {
            ID_ICFES: resumen_documento(d_icfes, PAGINAS_ICFES, conteos_icfes),
            ID_PISA: resumen_documento(d_pisa, PAGINAS_PISA, conteos_pisa),
        },
        "unidades": len(registros),
        "salida_datos": relativa(salida_datos),
        "salida_datos_sha256": sha256_de(salida_datos),
    }
    salida_resumen.parent.mkdir(parents=True, exist_ok=True)
    salida_resumen.write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen


def main() -> None:
    r = correr(SALIDA_DATOS, SALIDA_RESUMEN)
    print(json.dumps(r["documentos"], ensure_ascii=False, indent=2))
    print(f"unidades: {r['unidades']}")


if __name__ == "__main__":
    main()
