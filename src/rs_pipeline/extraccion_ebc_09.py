"""Extracción de los Estándares básicos de competencias 2004 (Bloque 9; D60).

Una unidad por viñeta «•», con su grupo de grados, su columna y subcolumna, su nivel
CINE 2011 (D56) y los estándares generales del grupo como contexto (no son unidades).
Usa los recortes aprobados de config/recortes_ebc_2004.yaml: no vuelve a medir.

Lectura: pdftotext -bbox da cada palabra con su caja. En cada página, cada columna y
cada globo es un recorte del YAML (una palabra es de un recorte si cabe a lo ancho y el
centro de su alto está entre sus límites). En una columna, cada «•» abre una viñeta y
las líneas siguientes la continúan. Los globos «Al final de … grado…» no entran al
contexto: sirven para comprobar que la tabla es del grupo que dice.

Los textos van a data/processed/curriculo/ (fuera de git); a outputs/tablas/ va solo
el resumen.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.extraccion_ebc_09
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from rs_pipeline import recortes_ebc_09 as R
from rs_pipeline.extraccion_09 import (
    INVENTARIO,
    documento_del_inventario,
    lineas_de_columna,
    pdf_verificado,
    procedencia,
    relativa,
    resumen_documento,
    version_pdftotext,
)
from rs_pipeline.extraccion_dba_09 import nivel_cine_del_grado
from rs_pipeline.ocr_pe_09 import sha256_de
from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
RECORTES = R.CONFIG
CURRICULO = RAIZ_REPO / "data" / "processed" / "curriculo"
SALIDA_DATOS = CURRICULO / "enunciados_09_ebc_v1.jsonl"
SALIDA_RESUMEN = RAIZ_REPO / "outputs" / "tablas" / "extraccion_09_ebc_v1.json"

# Piloto aprobado (D60): viñetas por grupo de grados y columna
ESTRUCTURA_EBC = {
    "6-7": {
        R.APROXIMO: 22,
        R.VIVO: 16,
        R.FISICO: 16,
        R.CTS: 13,
        R.COMPROMISOS: 11,
    },
    "8-9": {
        R.APROXIMO: 21,
        R.VIVO: 15,
        R.FISICO: 12,
        R.CTS: 15,
        R.COMPROMISOS: 12,
    },
    "10-11": {
        R.APROXIMO: 19,
        R.VIVO: 12,
        R.FISICO: 24,
        R.CTS: 11,
        R.COMPROMISOS: 12,
    },
}
ESTANDARES_GENERALES = {"6-7": 3, "8-9": 4, "10-11": 5}
# Si algo de esto aparece en un texto, se coló un encabezado, el pie o una viñeta.
# Distingue mayúsculas: «ciencias naturales» sí está dentro de algunas viñetas.
RESTOS = (
    "•",
    "…",
    "CIENCIAS",
    "NATURALES",
    "lograrlo",
    "propios de las ciencias",
    "Entorno vivo",
    "Entorno físico",
    "Procesos ",
    "Al final de",
)


# --- Recortes y páginas ---------------------------------------------------------


def cargar_recortes(sha_pdf: str) -> list[dict]:
    """Las páginas del YAML aprobado, en orden."""
    if not RECORTES.is_file():
        fallar(f"no existe {RECORTES}")
    config = yaml.safe_load(RECORTES.read_text(encoding="utf-8"))
    if config["entrada"]["sha256"] != sha_pdf:
        fallar(f"{RECORTES.name}: los recortes se midieron sobre otro PDF")
    filas = config["paginas"]
    numeros = [f["pagina"] for f in filas]
    if numeros != list(R.PAGINAS):
        fallar(f"{RECORTES.name}: faltan o sobran páginas, o van en otro orden")
    for f in filas:
        n = f["pagina"]
        if not str(f.get("verificado_por") or "").strip():
            fallar(f"p{n}: recorte sin verificar (verificado_por vacío)")
        columnas = tuple(c["columna"] for c in f["columnas"])
        if f["grupo"] != R.PAGINAS[n].grupo or columnas != R.PAGINAS[n].columnas:
            fallar(f"p{n}: el grupo o las columnas del recorte no son los esperados")
    return filas


def del_recorte(palabras: list, recorte: dict) -> list:
    return [p for p in palabras if R.dentro(p, recorte)]


def controlar_encabezado_y_pie(palabras: list, fila: dict) -> None:
    """Los recortes deben dejar justo el texto de columnas y globos.

    No vuelve a medir: compara los recortes aprobados con una segunda definición, la de
    las anclas de la página (pie, palabra del encabezado y primera viñeta de columna).
    """
    n = fila["pagina"]
    partes = R.separar(palabras, n)
    columnas = R.textos_de_columna(partes["resto"], n)
    for r, esperado in zip(fila["columnas"], columnas, strict=True):
        if set(del_recorte(palabras, r)) != set(esperado):
            fallar(
                f"p{n}, {r['columna']}: el recorte deja encabezado o pie, o quita "
                "texto de la columna"
            )
    en_globos = [p for r in fila["contexto"] for p in del_recorte(palabras, r)]
    if sorted(en_globos) != sorted(partes["globos"]):
        fallar(f"p{n}: los recortes de globos no dejan justo el texto de los globos")


def texto_en_lineas(palabras: list) -> list[str]:
    """Las líneas de un recorte, de arriba abajo."""
    tuplas = [(p.texto, p.x0, p.y0) for p in palabras]
    return [" ".join(ws) for _, ws in lineas_de_columna(tuplas, 0, float("inf"))]


# --- Viñetas y contexto ----------------------------------------------------------


def vinetas(lineas: list[str], donde: str) -> list[str]:
    """Cada «•» abre una viñeta; las líneas siguientes la continúan."""
    unidades: list[list[str]] = []
    for linea in lineas:
        if linea.startswith("•"):
            unidades.append([linea.removeprefix("•").strip()])
        elif unidades:
            unidades[-1].append(linea)
        else:
            fallar(f"{donde}: hay texto antes de la primera viñeta")
    return [" ".join(u) for u in unidades]


def vinetas_de_pagina(palabras: list, fila: dict) -> list[dict]:
    salida = []
    for r in fila["columnas"]:
        donde = f"p{fila['pagina']}, {r['columna']}"
        textos = vinetas(texto_en_lineas(del_recorte(palabras, r)), donde)
        if len(textos) != r["vinetas"]:
            fallar(
                f"{donde}: {len(textos)} viñetas y el recorte aprobado tiene "
                f"{r['vinetas']}"
            )
        salida += [
            {
                "grupo": fila["grupo"],
                "columna": r["columna"],
                "subcolumna": r["subcolumna"],
                "pagina": fila["pagina"],
                "texto": t,
            }
            for t in textos
        ]
    return salida


def globos_de_pagina(palabras: list, fila: dict) -> tuple[list[str], int]:
    """Estándares generales de la página y cuántas introducciones válidas trae."""
    n = fila["pagina"]
    estandares, introducciones = [], 0
    for r in fila["contexto"]:
        texto = " ".join(texto_en_lineas(del_recorte(palabras, r)))
        if r["tipo"] == "estandar_general":
            estandares.append(texto)
            continue
        grado = R.ULTIMO_GRADO.get(n)
        if grado is None or not texto.startswith(R.INTRODUCCION) or grado not in texto:
            fallar(f"p{n}: la introducción no es la del grupo {fila['grupo']}")
        introducciones += 1
    return estandares, introducciones


# --- Controles -------------------------------------------------------------------


def controlar_conteos(unidades: list[dict]) -> None:
    leida: dict[str, dict[str, int]] = {}
    for u in unidades:
        grupo = leida.setdefault(u["grupo"], {})
        grupo[u["columna"]] = grupo.get(u["columna"], 0) + 1
    if leida != ESTRUCTURA_EBC:
        fallar(
            "EBC: viñetas por grupo y columna distintas de las del piloto. "
            f"Leído: {leida}. Esperado: {ESTRUCTURA_EBC}"
        )


def controlar_textos(unidades: list[dict], contexto: dict[str, list[str]]) -> None:
    """Cantidad de estándares generales, y textos completos y sin restos."""
    cuantos = {g: len(v) for g, v in contexto.items()}
    if cuantos != ESTANDARES_GENERALES:
        fallar(
            f"EBC: estándares generales por grupo {cuantos}, "
            f"esperados {ESTANDARES_GENERALES}"
        )
    textos = [(f"viñeta de la p{u['pagina']}", u["texto"]) for u in unidades]
    textos += [(f"estándar general {g}", t) for g, v in contexto.items() for t in v]
    for donde, t in textos:
        restos = [r for r in RESTOS if r in t]
        if restos:
            fallar(f"{donde}: hay restos de encabezado, pie o viñeta: {restos}")
        if len(t.split()) < 3 or not t[:1].isupper() or not t.endswith("."):
            fallar(f"{donde}: texto vacío, cortado o con algo pegado: {t[:40]!r}")


def extraer(pdf: Path, sha_pdf: str) -> tuple[list[dict], dict[str, list[str]]]:
    """Viñetas y estándares generales leídos con los recortes aprobados."""
    filas = cargar_recortes(sha_pdf)
    _, paginas = R.leer_paginas(pdf)
    unidades: list[dict] = []
    contexto: dict[str, list[str]] = {}
    introducciones: list[str] = []
    for fila in filas:
        palabras = paginas[fila["pagina"]]
        controlar_encabezado_y_pie(palabras, fila)
        unidades += vinetas_de_pagina(palabras, fila)
        estandares, intros = globos_de_pagina(palabras, fila)
        contexto.setdefault(fila["grupo"], []).extend(estandares)
        introducciones += [fila["grupo"]] * intros
    if introducciones != list(ESTANDARES_GENERALES):
        fallar(f"EBC: se esperaba una introducción por grupo y hay {introducciones}")
    en_pdf = sum(p.texto.count("•") for pal in paginas.values() for p in pal)
    if len(unidades) != en_pdf:
        fallar(f"EBC: {len(unidades)} unidades y el PDF tiene {en_pdf} viñetas")
    controlar_conteos(unidades)
    controlar_textos(unidades, contexto)
    return unidades, contexto


# --- Salida -----------------------------------------------------------------------


def nivel_cine_del_grupo(grupo: str) -> int:
    """El nivel CINE común a los dos grados del grupo (D56)."""
    niveles = {nivel_cine_del_grado(int(g)) for g in grupo.split("-")}
    if len(niveles) != 1:
        fallar(f"el grupo {grupo} mezcla niveles CINE: {sorted(niveles)}")
    return niveles.pop()


def registros_ebc(
    doc: dict, unidades: list[dict], contexto: dict[str, list[str]]
) -> list[dict]:
    veces: dict[tuple[str, str], int] = {}
    salida = []
    for u in unidades:
        clave = (u["grupo"], u["columna"])
        veces[clave] = veces.get(clave, 0) + 1
        salida.append(
            {
                "id_unidad": (
                    f"{doc['id']}:G{u['grupo']}.{u['columna']}.{veces[clave]}"
                ),
                **procedencia(doc),
                # el del grupo, no la lista de niveles de todo el documento
                "nivel_cine": [nivel_cine_del_grupo(u["grupo"])],
                "tipo_unidad": "vineta_ebc",
                "grupo_grados": u["grupo"],
                "columna": u["columna"],
                "subcolumna": u["subcolumna"],
                "estandares_generales": contexto[u["grupo"]],
                "texto": u["texto"],
                "texto_es": u["texto"],
                "idioma": "es",
                "pagina": u["pagina"],
            }
        )
    return salida


def conteos(unidades: list[dict], contexto: dict[str, list[str]]) -> dict:
    por_grupo = {}
    for grupo, estandares in contexto.items():
        del_grupo = [u for u in unidades if u["grupo"] == grupo]
        columnas: dict[str, int] = {}
        subcolumnas: dict[str, int] = {}
        for u in del_grupo:
            columnas[u["columna"]] = columnas.get(u["columna"], 0) + 1
            if u["subcolumna"]:
                sub = u["subcolumna"]
                subcolumnas[sub] = subcolumnas.get(sub, 0) + 1
        por_grupo[grupo] = {
            "nivel_cine": nivel_cine_del_grupo(grupo),
            "vinetas": len(del_grupo),
            "estandares_generales": len(estandares),
            "por_columna": columnas,
            "por_subcolumna": subcolumnas,
        }
    return {"vinetas": len(unidades), "por_grupo": por_grupo}


def correr(salida_datos: Path, salida_resumen: Path) -> dict:
    for ruta in (salida_datos, salida_resumen):
        if ruta.exists():
            fallar(f"ya existe {ruta}; no se sobrescribe una extracción anterior")
    doc = documento_del_inventario(R.ID_EBC)
    unidades, contexto = extraer(pdf_verificado(doc), doc["sha256"])
    registros = registros_ebc(doc, unidades, contexto)
    version = version_pdftotext()  # antes de escribir: si falla, no queda nada a medias
    salida_datos.parent.mkdir(parents=True, exist_ok=True)
    with salida_datos.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    paginas = (min(R.PAGINAS), max(R.PAGINAS))
    resumen = {
        "decision": "D60",
        "fecha": date.today().isoformat(),
        "pdftotext": version,
        "inventario": {
            "archivo": relativa(INVENTARIO),
            "sha256": sha256_de(INVENTARIO),
        },
        "recortes": {"archivo": relativa(RECORTES), "sha256": sha256_de(RECORTES)},
        "documentos": {
            R.ID_EBC: resumen_documento(doc, paginas, conteos(unidades, contexto))
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
