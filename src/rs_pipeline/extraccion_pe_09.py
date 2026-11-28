"""Extracción de los desempeños de Perú, 1.º a 5.º de secundaria (Bloque 9; D57, D60).

Una unidad por desempeño de PE-PCS-2016, con su grado, ciclo, competencia, nivel CINE,
su «Ejemplo» como contexto y el estándar del CNEB de su competencia y ciclo. No mide
nada: lee el OCR v2 (TSV) y las viñetas aprobadas de config/vinetas_pe_pcs_2016.yaml.

1. Cada columna se arma con las palabras del TSV que caen en su zona, línea por línea;
   se quitan la viñeta leída como letra y los «|» y «]» de los bordes de la tabla.
2. Cada viñeta abre un desempeño. La pág. 187 continúa la 186, columna con columna.
3. Se aplican las correcciones verificadas (correcciones.csv): cada una debe coincidir
   una sola vez.
4. El texto desde «Ejemplo:» se separa como contexto.
5. El ciclo sale de todas las menciones de la página; si no coinciden, de la referencia
   verificada (config/ciclos_pe_pcs_2016.yaml). Debe cuadrar con el grado.
6. El estándar del ciclo se toma de la capa de texto del CNEB (págs. 125, 129, 133).

Los textos van a data/processed/curriculo/ (fuera de git); a outputs/tablas/ va solo
el resumen.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.extraccion_pe_09
"""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

import yaml

from rs_pipeline import vinetas_pe_09 as V
from rs_pipeline.extraccion_09 import (
    INVENTARIO,
    documento_del_inventario,
    pdf_verificado,
    procedencia,
    relativa,
    resumen_documento,
    version_pdftotext,
)
from rs_pipeline.ocr_pe_09 import ejecutar, sha256_de
from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
ID_PCS, ID_CNEB = "PE-PCS-2016", "PE-CNEB-2016"
VINETAS = V.CONFIG
CICLOS = RAIZ_REPO / "config" / "ciclos_pe_pcs_2016.yaml"
CORRECCIONES = V.DESTINO / "correcciones.csv"
RESUMEN_CORRECCIONES = V.PROCEDENCIA / "PE-PCS-2016_correcciones_resumen.json"
CURRICULO = RAIZ_REPO / "data" / "processed" / "curriculo"
SALIDA_DATOS = CURRICULO / "enunciados_09_pe_v1.jsonl"
SALIDA_RESUMEN = RAIZ_REPO / "outputs" / "tablas" / "extraccion_09_pe_v1.json"

COMPETENCIAS = {
    "indaga": "Indaga mediante métodos científicos para construir conocimientos",
    "explica": (
        "Explica el mundo físico basándose en conocimientos sobre los seres vivos, "
        "materia y energía, biodiversidad, Tierra y universo"
    ),
    "disena": (
        "Diseña y construye soluciones tecnológicas para resolver problemas de su "
        "entorno"
    ),
}
# Piloto aprobado (D60): desempeños por competencia, de 1.º a 5.º
ESTRUCTURA_PE = {
    "indaga": [5, 5, 5, 5, 5],
    "explica": [12, 15, 12, 10, 13],
    "disena": [4, 4, 4, 4, 4],
}
EJEMPLOS_PE = {("explica", 1): 3, ("explica", 2): 4}
CICLO_DEL_GRADO = {1: "VI", 2: "VI", 3: "VII", 4: "VII", 5: "VII"}  # D57
CINE_DEL_GRADO = {1: 2, 2: 2, 3: 2, 4: 3, 5: 3}  # D56

TOLERANCIA_LINEA = 22  # px a 300 dpi; palabras a menos de esto son de la misma línea
BORDES = ("|", "]")  # líneas de la tabla leídas como texto (D57, cuarta adenda)
MARCA_EJEMPLO = "Ejemplo:"
RE_MENCION_CICLO = re.compile(
    r"(?:nivel esperado|al final) del ciclo (\S+)", re.IGNORECASE
)
# Restos del sello o de encabezados: ni en el desempeño ni en su ejemplo
RE_CARACTER_AJENO = re.compile(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,;:()/\-°“”]")
SIGLAS = {"ADN", "CO2", "°C"}
RESTOS = (
    "DESEMPEÑOS",
    "GRADO DE",
    "Cuando el estudiante",
    "los siguientes",
    "nivel esperado",
    "al final del ciclo",
    "MINEDU",
    "649-2016",
    "Ejemplo",
)
# CNEB: página y comienzo de los niveles 7 (ciclo VII), 6 (ciclo VI) y 5
ESTANDARES = {
    "indaga": (
        125,
        "Indaga a partir de preguntas y plantea",
        "Indaga a partir de preguntas e hipótesis",
        "Indaga las causas",
    ),
    "explica": (
        129,
        "Explica, con base en evidencias con respaldo científico",
        "Explica, con base en evidencia con respaldo científico, las relaciones "
        "cualitativas y las cuantificables entre: el campo",
        "Explica, con base en evidencia con respaldo científico, las relaciones "
        "entre: propiedades",
    ),
    "disena": (
        133,
        "Diseña y construye soluciones tecnológicas al justificar el alcance del "
        "problema tecnológico, determinar",
        "Diseña y construye soluciones tecnológicas al delimitar el alcance",
        "Diseña y construye soluciones tecnológicas al identificar las causas",
    ),
}
NIVEL_CNEB = {"VII": 7, "VI": 6}


# --- Entradas verificadas ----------------------------------------------------------


def cargar_vinetas(hash_pdf: str) -> list[dict]:
    """Las páginas del YAML de viñetas, aprobado y sobre el mismo PDF y OCR."""
    if not VINETAS.is_file():
        fallar(f"no existe {VINETAS}")
    config = yaml.safe_load(VINETAS.read_text(encoding="utf-8"))
    if config["entrada"]["sha256"] != hash_pdf:
        fallar(f"{VINETAS.name}: las viñetas se midieron sobre otro PDF")
    if config["ocr"]["sha256"] != sha256_de(V.OCR_JSON):
        fallar(f"{VINETAS.name}: las viñetas se midieron con otro registro del OCR")
    filas = config["paginas"]
    if [f["pagina"] for f in filas] != list(V.PAGINAS):
        fallar(f"{VINETAS.name}: faltan o sobran páginas, o van en otro orden")
    for f in filas:
        n = f["pagina"]
        if not str(f.get("verificado_por") or "").strip():
            fallar(f"p{n}: viñetas sin verificar (verificado_por vacío)")
        grados = tuple(c["grado"] for c in f["columnas"])
        esperada = V.PAGINAS[n]
        if (f["competencia"], grados) != (esperada.competencia, esperada.grados):
            fallar(f"p{n}: la competencia o los grados no son los esperados")
    return filas


def palabras_de_pagina(ficha: dict) -> list[V.Palabra]:
    """Las palabras del TSV, que debe ser el registrado en el OCR v2."""
    nombre = f"p{ficha['pagina_pdf']:03d}.tsv"
    ruta = V.DESTINO / nombre
    if sha256_de(ruta) != ficha["salidas"][nombre]["sha256"]:
        fallar(f"{nombre}: no es el TSV del registro {V.OCR_JSON.name}")
    return V.palabras_del_tsv(ruta)


def cargar_correcciones() -> list[dict]:
    """Correcciones verificadas; su número por página cuadra con el resumen en git."""
    if not CORRECCIONES.is_file():
        fallar(f"no existe {CORRECCIONES}")
    with CORRECCIONES.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    por_pagina: dict[str, int] = {}
    for fila in filas:
        if not fila["verificado_por"].strip():
            fallar(f"p{fila['pagina']}: corrección sin verificar")
        por_pagina[fila["pagina"]] = por_pagina.get(fila["pagina"], 0) + 1
    resumen = json.loads(RESUMEN_CORRECCIONES.read_text(encoding="utf-8"))
    if por_pagina != resumen["por_pagina"]:
        fallar(
            f"{CORRECCIONES.name}: correcciones por página {por_pagina} y el resumen "
            f"dice {resumen['por_pagina']}"
        )
    return filas


# --- Armado de desempeños ----------------------------------------------------------


def en_lineas(palabras: list[V.Palabra]) -> list[dict]:
    """Líneas de arriba abajo, cada una con su altura media y sus palabras por x."""
    lineas: list[dict] = []
    for p in sorted(palabras, key=lambda p: p.cy):
        if lineas and p.cy - lineas[-1]["cy"] <= TOLERANCIA_LINEA:
            linea = lineas[-1]
            linea["palabras"].append(p)
            linea["cy"] = sum(q.cy for q in linea["palabras"]) / len(linea["palabras"])
        else:
            lineas.append({"cy": p.cy, "palabras": [p]})
    for linea in lineas:
        linea["palabras"].sort(key=lambda p: p.x0)
    return lineas


def lineas_de_columna(palabras: list[V.Palabra], columna: dict) -> list[dict]:
    """Las líneas de la zona de una columna, marcando las que abre una viñeta."""
    vinetas = [V.Caja(*v) for v in columna["vinetas"]]
    zona = [
        p
        for p in palabras
        if columna["x_izquierda"] <= p.cx < columna["x_derecha"]
        and columna["y_superior"] < p.cy < columna["y_inferior"]
        and not V.es_glifo(p, vinetas)
        and p.texto.strip() not in BORDES
    ]
    lineas = en_lineas(zona)
    for linea in lineas:
        linea["abre"] = False
    for v in vinetas:
        junto = [x for x in lineas if abs(x["cy"] - v.cy) <= V.ALTO_LINEA]
        if len(junto) != 1 or junto[0]["abre"]:
            fallar(
                f"grado {columna['grado']}: la viñeta en y={v.y0} no corresponde "
                "a una sola línea"
            )
        junto[0]["abre"] = True
    return lineas


def armar(filas: list[dict], palabras: dict[int, list]) -> list[dict]:
    """Los desempeños en orden de lectura, con sus páginas y su texto sin corregir."""
    unidades: list[dict] = []
    abiertos: dict[tuple[str, int], dict] = {}
    for fila in filas:
        n, competencia = fila["pagina"], fila["competencia"]
        for columna in fila["columnas"]:
            clave = (competencia, columna["grado"])
            if not V.PAGINAS[n].continuacion:
                abiertos.pop(clave, None)
            for linea in lineas_de_columna(palabras[n], columna):
                if linea["abre"]:
                    abiertos[clave] = {
                        "competencia": competencia,
                        "grado": columna["grado"],
                        "paginas": [],
                        "palabras": [],
                    }
                    unidades.append(abiertos[clave])
                if clave not in abiertos:
                    fallar(f"p{n}: hay texto antes de la primera viñeta de la columna")
                u = abiertos[clave]
                u["palabras"] += [p.texto for p in linea["palabras"]]
                if n not in u["paginas"]:
                    u["paginas"].append(n)
    for u in unidades:
        u["texto"] = " ".join(" ".join(u.pop("palabras")).split())
        u["corregida"] = False
    return unidades


def _junta(*partes: str) -> str:
    return " ".join(p for p in partes if p)


def aplicar_correcciones(unidades: list[dict], correcciones: list[dict]) -> None:
    """Cada corrección debe coincidir una sola vez en los desempeños de su página."""
    for c in correcciones:
        n = int(c["pagina"])
        patron = _junta(c["texto_antes"], c["texto_ocr"], c["texto_despues"])
        nuevo = _junta(c["texto_antes"], c["texto_corregido"], c["texto_despues"])
        suyas = [u for u in unidades if u["paginas"][0] == n]
        veces = sum(u["texto"].count(patron) for u in suyas)
        if veces != 1:
            fallar(
                f"p{n}: la corrección que da «{c['texto_corregido'][:30]}» coincide "
                f"{veces} veces y no una"
            )
        [u] = [u for u in suyas if patron in u["texto"]]
        if not c["texto_despues"] and not u["texto"].endswith(patron):
            fallar(f"p{n}: la corrección sin «texto_despues» no cae al final")
        u["texto"] = u["texto"].replace(patron, nuevo)
        u["corregida"] = True


def separar_ejemplos(unidades: list[dict]) -> None:
    """Lo que sigue a «Ejemplo:» pasa a ser contexto del desempeño."""
    for u in unidades:
        partes = u["texto"].split(MARCA_EJEMPLO)
        if len(partes) > 2:
            fallar(f"grado {u['grado']}: un desempeño trae dos «{MARCA_EJEMPLO}»")
        u["texto"] = partes[0].strip()
        u["ejemplo"] = partes[1].strip() if len(partes) == 2 else None


# --- Ciclo -------------------------------------------------------------------------


def menciones_de_ciclo(palabras: list[V.Palabra]) -> list[str]:
    """Lo que sigue a «ciclo» en la página, en el orden de lectura del OCR."""
    texto = " ".join(p.texto for p in palabras if p.texto not in BORDES)
    return [m.strip(" .,;:").upper() for m in RE_MENCION_CICLO.findall(texto)]


def ciclo_de_pagina(menciones: list[str], referencia: str, n: int) -> tuple[str, str]:
    """El ciclo y de dónde sale: «texto» o «referencia» (revisión manual)."""
    if not menciones:
        fallar(f"p{n}: la página no menciona su ciclo")
    if len(set(menciones)) == 1 and menciones[0] in NIVEL_CNEB:
        if menciones[0] != referencia:
            fallar(
                f"p{n}: el texto dice ciclo {menciones[0]} y la referencia "
                f"verificada {referencia}"
            )
        return referencia, "texto"
    return referencia, "referencia"


def ciclos_de_paginas(palabras: dict[int, list]) -> dict[int, tuple[str, str]]:
    referencia = yaml.safe_load(CICLOS.read_text(encoding="utf-8"))["ciclos"]
    con_texto = [n for n, p in V.PAGINAS.items() if not p.continuacion]
    if sorted(referencia) != con_texto:
        fallar(f"{CICLOS.name}: debe traer las páginas {con_texto}")
    ciclos: dict[int, tuple[str, str]] = {}
    for n, pagina in V.PAGINAS.items():
        if pagina.continuacion:
            ciclos[n] = (ciclos[n - 1][0], f"hereda de la {n - 1}")
        else:
            menciones = menciones_de_ciclo(palabras[n])
            ciclos[n] = ciclo_de_pagina(menciones, referencia[n], n)
    return ciclos


def asignar_ciclos(unidades: list[dict], ciclos: dict[int, tuple[str, str]]) -> None:
    """El ciclo de la página donde empieza; debe cuadrar con todas y con el grado."""
    for u in unidades:
        leidos = {ciclos[n][0] for n in u["paginas"]}
        esperado = CICLO_DEL_GRADO[u["grado"]]
        if leidos != {esperado}:
            fallar(
                f"p{u['paginas'][0]}: el grado {u['grado']} es del ciclo {esperado} "
                f"y las páginas dicen {sorted(leidos)}"
            )
        u["ciclo"] = esperado


# --- Estándares del CNEB -----------------------------------------------------------


def texto_de_estandares(salida_layout: str) -> str:
    """La página en una sola línea, sin los rótulos de nivel (D, 7, 6…) del margen."""
    lineas = [
        re.sub(r"^\s*(D|[1-7])(\s{2,}|\s*$)", "", x).strip()
        for x in salida_layout.splitlines()
    ]
    return " ".join(" ".join(re.sub(r"^D\s+", "", x) for x in lineas).split())


def estandares_de_pagina(texto: str, marcas: tuple[str, str, str]) -> dict[str, str]:
    """Estándares de los ciclos VII y VI: cada uno llega hasta el siguiente."""
    for marca in marcas:
        if texto.count(marca) != 1:
            fallar(f"CNEB: «{marca[:45]}…» aparece {texto.count(marca)} veces y no una")
    siete, seis, cinco = (texto.index(m) for m in marcas)
    if not siete < seis < cinco:
        fallar("CNEB: los niveles 7, 6 y 5 no van en ese orden")
    salida = {"VII": texto[siete:seis].strip(), "VI": texto[seis:cinco].strip()}
    for ciclo, estandar in salida.items():
        sueltos = [w for w in estandar.split() if w.isdigit() or w == "D"]
        if not estandar.endswith(".") or sueltos:
            fallar(f"CNEB: el estándar del ciclo {ciclo} salió cortado o con rótulos")
    return salida


def estandares_cneb(pdf: Path) -> dict[tuple[str, str], dict]:
    salida = {}
    for competencia, (pagina, *marcas) in ESTANDARES.items():
        orden = ["pdftotext", "-layout", "-f", str(pagina), "-l", str(pagina)]
        texto = texto_de_estandares(ejecutar([*orden, str(pdf), "-"]).stdout)
        for ciclo, estandar in estandares_de_pagina(texto, tuple(marcas)).items():
            salida[competencia, ciclo] = {
                "nivel": NIVEL_CNEB[ciclo],
                "pagina": pagina,
                "texto": estandar,
            }
    return salida


# --- Controles ---------------------------------------------------------------------


def controlar_conteos(unidades: list[dict]) -> None:
    conteo = {c: [0] * 5 for c in ESTRUCTURA_PE}
    ejemplos: dict[tuple[str, int], int] = {}
    for u in unidades:
        conteo[u["competencia"]][u["grado"] - 1] += 1
        if u["ejemplo"] is not None:
            clave = (u["competencia"], u["grado"])
            ejemplos[clave] = ejemplos.get(clave, 0) + 1
    if conteo != ESTRUCTURA_PE:
        fallar(
            "Perú: desempeños por competencia y grado distintos de los del piloto. "
            f"Leído: {conteo}. Esperado: {ESTRUCTURA_PE}"
        )
    if ejemplos != EJEMPLOS_PE:
        fallar(f"Perú: ejemplos {ejemplos}, esperados {EJEMPLOS_PE}")


def controlar_textos(unidades: list[dict]) -> None:
    """Todos terminan en punto y no traen restos del sello ni de encabezados."""
    for u in unidades:
        donde = f"p{u['paginas'][0]}, grado {u['grado']}"
        textos = [u["texto"]]
        if u["ejemplo"] is not None:
            textos.append(u["ejemplo"])
        for t in textos:
            if len(t.split()) < 3 or not t[:1].isupper() or not t.endswith("."):
                fallar(f"{donde}: texto vacío, cortado o sin punto: …{t[-40:]!r}")
            ajenos = sorted(set(RE_CARACTER_AJENO.findall(t)))
            mayusculas = [
                w
                for w in (x.strip(".,;:()“”") for x in t.split())
                if len(w) > 1 and w.isupper() and w not in SIGLAS
            ]
            restos = [r for r in RESTOS if r in t]
            if ajenos or mayusculas or restos:
                fallar(
                    f"{donde}: restos del sello o de encabezados: "
                    f"{ajenos + mayusculas + restos}"
                )
        if u["texto"].split()[0].strip(",") not in V.VERBOS:
            fallar(f"{donde}: el desempeño no empieza por un verbo de la lista")


# --- Salida ------------------------------------------------------------------------


def extraer(hash_pdf: str) -> tuple[list[dict], dict[int, tuple[str, str]]]:
    """Los desempeños armados, corregidos y controlados, y el ciclo de cada página."""
    filas = cargar_vinetas(hash_pdf)
    fichas = V.fichas_del_ocr(hash_pdf)
    palabras = {n: palabras_de_pagina(fichas[n]) for n in V.PAGINAS}
    unidades = armar(filas, palabras)
    en_vinetas = sum(len(c["vinetas"]) for f in filas for c in f["columnas"])
    if len(unidades) != en_vinetas:
        fallar(f"Perú: {len(unidades)} desempeños y el YAML trae {en_vinetas} viñetas")
    aplicar_correcciones(unidades, cargar_correcciones())
    separar_ejemplos(unidades)
    ciclos = ciclos_de_paginas(palabras)
    asignar_ciclos(unidades, ciclos)
    controlar_conteos(unidades)
    controlar_textos(unidades)
    return unidades, ciclos


def origen_ocr(paginas: list[int], fichas: dict[int, dict]) -> dict:
    """De qué OCR sale un desempeño: el registro y los TSV de sus páginas."""
    tsv = []
    for n in paginas:
        nombre = f"p{n:03d}.tsv"
        salida = fichas[n]["salidas"][nombre]
        tsv.append(
            {"archivo": relativa(V.DESTINO / nombre), "sha256": salida["sha256"]}
        )
    return {
        "registro": relativa(V.OCR_JSON),
        "sha256_registro": sha256_de(V.OCR_JSON),
        "tsv": tsv,
    }


def registros_pe(
    doc: dict,
    cneb: dict,
    unidades: list[dict],
    estandares: dict[tuple[str, str], dict],
    fichas: dict[int, dict],
) -> list[dict]:
    veces: dict[tuple[str, int], int] = {}
    salida = []
    for u in unidades:
        clave = (u["competencia"], u["grado"])
        veces[clave] = veces.get(clave, 0) + 1
        estandar = estandares[u["competencia"], u["ciclo"]]
        salida.append(
            {
                "id_unidad": (
                    f"{doc['id']}:S{u['grado']}.{u['competencia']}.{veces[clave]}"
                ),
                **procedencia(doc),
                # el del grado, no la lista de niveles de todo el documento
                "nivel_cine": [CINE_DEL_GRADO[u["grado"]]],
                "tipo_unidad": "desempeno_pe",
                "grado": u["grado"],
                "etapa": "secundaria",
                "ciclo": u["ciclo"],
                "competencia": COMPETENCIAS[u["competencia"]],
                "competencia_id": u["competencia"],
                "texto": u["texto"],
                "texto_es": u["texto"],
                "idioma": "es",
                "ejemplo": u["ejemplo"],
                "pagina": u["paginas"][0],
                "paginas": u["paginas"],
                "origen": "OCR",
                "ocr": origen_ocr(u["paginas"], fichas),
                "estandar_cneb": {
                    "documento": cneb["id"],
                    "archivo": cneb["ruta_local"],
                    "sha256_archivo": cneb["sha256"],
                    **estandar,
                },
            }
        )
    return salida


def conteos(registros: list[dict], ciclos: dict[int, tuple[str, str]]) -> dict:
    por_competencia = {c: [0] * 5 for c in ESTRUCTURA_PE}
    por_ciclo: dict[str, int] = {}
    por_cine: dict[str, int] = {}
    for r in registros:
        por_competencia[r["competencia_id"]][r["grado"] - 1] += 1
        por_ciclo[r["ciclo"]] = por_ciclo.get(r["ciclo"], 0) + 1
        cine = str(r["nivel_cine"][0])
        por_cine[cine] = por_cine.get(cine, 0) + 1
    return {
        "desempenos": len(registros),
        "por_competencia_y_grado": por_competencia,
        "por_ciclo": por_ciclo,
        "por_nivel_cine": por_cine,
        "con_ejemplo": sum(r["ejemplo"] is not None for r in registros),
        "ciclo_por_pagina": {
            str(n): {"ciclo": c, "origen": o} for n, (c, o) in ciclos.items()
        },
    }


def archivo_y_hash(ruta: Path) -> dict:
    return {"archivo": relativa(ruta), "sha256": sha256_de(ruta)}


def correr(salida_datos: Path, salida_resumen: Path) -> dict:
    for ruta in (salida_datos, salida_resumen):
        if ruta.exists():
            fallar(f"ya existe {ruta}; no se sobrescribe una extracción anterior")
    doc, cneb = (documento_del_inventario(i) for i in (ID_PCS, ID_CNEB))
    pdf_verificado(doc)
    estandares = estandares_cneb(pdf_verificado(cneb))
    unidades, ciclos = extraer(doc["sha256"])
    fichas = V.fichas_del_ocr(doc["sha256"])
    registros = registros_pe(doc, cneb, unidades, estandares, fichas)
    version = version_pdftotext()  # antes de escribir: si falla, no queda nada a medias
    salida_datos.parent.mkdir(parents=True, exist_ok=True)
    with salida_datos.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    corregidas = [
        r["id_unidad"]
        for r, u in zip(registros, unidades, strict=True)
        if u["corregida"]
    ]
    resumen = {
        "decision": "D60",
        "fecha": date.today().isoformat(),
        "pdftotext": version,
        "origen": "OCR",
        "entradas": {
            "inventario": archivo_y_hash(INVENTARIO),
            "ocr": archivo_y_hash(V.OCR_JSON),
            "vinetas": archivo_y_hash(VINETAS),
            "referencia_ciclos": archivo_y_hash(CICLOS),
            "correcciones": archivo_y_hash(CORRECCIONES),
        },
        "documentos": {
            ID_PCS: resumen_documento(
                doc,
                (min(V.PAGINAS), max(V.PAGINAS)),
                conteos(registros, ciclos),
            ),
            ID_CNEB: resumen_documento(
                cneb,
                (ESTANDARES["indaga"][0], ESTANDARES["disena"][0]),
                {"estandares": len(estandares), "unidades": 0},
            ),
        },
        "unidades_corregidas": corregidas,
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
    print(f"unidades: {r['unidades']} · corregidas: {len(r['unidades_corregidas'])}")


if __name__ == "__main__":
    main()
