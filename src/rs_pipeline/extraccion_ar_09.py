"""Extracción de los NAP de Ciencias Naturales de Argentina (Bloque 9; D56, D60).

Dos documentos con texto digital:
- AR-NAP-CB (Res. CFCyE 249/05, ciclo básico, CINE 2): una unidad por viñeta «•», las
  generales del ciclo y las de 7.º, 8.º y 9.º, por eje.
- AR-NAP-CO (Res. CFE 180/12, ciclo orientado, CINE 3): una unidad por párrafo, las
  generales y las de Biología, Física y Química, por eje (Física no tiene ejes).

Con pdftotext -bbox se deja fuera el encabezado de página (por su altura en la hoja) y
las notas al pie (letra más pequeña); los números de nota pegados al texto se quitan.
Las frases que abren las generales son contexto, no unidades. El texto no se corrige;
los nombres de los ejes se normalizan.

Los textos van a data/processed/curriculo/ (fuera de git); a outputs/tablas/ va solo
el resumen.

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.extraccion_ar_09
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import NamedTuple

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
from rs_pipeline.recortes_dba_09 import Palabra, paginas_con_cajas
from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
CURRICULO = RAIZ_REPO / "data" / "processed" / "curriculo"
SALIDA_DATOS = CURRICULO / "enunciados_09_ar_v1.jsonl"
SALIDA_RESUMEN = RAIZ_REPO / "outputs" / "tablas" / "extraccion_09_ar_v1.json"
ID_CB, ID_CO = "AR-NAP-CB", "AR-NAP-CO"


class Formato(NamedTuple):
    paginas: int
    sin_unidades: tuple[int, ...]  # portadas
    y_encabezado: float  # pt; más arriba solo está el encabezado de la página
    alto_texto: float  # pt; las notas al pie y las llamadas miden menos
    notas: int  # llamadas a nota esperadas en el texto, numeradas desde 1
    nivel_cine: list[int]


FORMATOS = {
    ID_CB: Formato(11, (1,), 140.0, 10.05, 2, [2]),  # texto ≥ 10,2; notas ≤ 9,9
    ID_CO: Formato(10, (1, 3, 6, 8), 160.0, 9.0, 10, [3]),
}
PORTADAS = {ID_CB: "NÚCLEOS DE APRENDIZAJES", ID_CO: "Campo de Formación General"}
# pt; palabras a menos de esto en altura son de la misma línea. La viñeta «•» empieza
# entre 3,2 y 4,2 pt más arriba que su texto, y dos líneas distan 11 pt o más.
TOLERANCIA_LINEA = 5.0
SALTO_PARRAFO = 18.0  # pt; en el CO una línea dista 12 y un párrafo 24 o más
GENERAL = "general"
MARCA_7 = "varía según jurisdicción"  # 7.º año (decisión de D60)
ETAPAS = {ID_CB: "Tercer Ciclo EGB / Nivel Medio", ID_CO: "Ciclo Orientado"}
ENTRADILLAS = {ID_CB: "La escuela ofrecerá", ID_CO: "Durante el Ciclo Orientado"}

# Eje normalizado: encabezado en mayúsculas -> (identificador, nombre)
EJES_CB = {
    "EN RELACIÓN CON LOS SERES VIVOS: DIVERSIDAD, UNIDAD, INTERRELACIONES Y CAMBIOS": (
        "seres_vivos",
        "En relación con los seres vivos: diversidad, unidad, interrelaciones y "
        "cambios",
    ),
    "EN RELACIÓN CON LOS MATERIALES Y SUS CAMBIOS": (
        "materiales",
        "En relación con los materiales y sus cambios",
    ),
    "LOS FENÓMENOS DEL MUNDO FÍSICO": ("fisicos", "Los fenómenos del mundo físico"),
    "LA TIERRA, EL UNIVERSO Y SUS CAMBIOS": (
        "tierra_universo",
        "La Tierra, el universo y sus cambios",
    ),
}
EJES_CO = {
    "EN RELACIÓN CON EL FLUJO DE LA INFORMACIÓN GENÉTICA": (
        "informacion_genetica",
        "En relación con el flujo de la información genética",
    ),
    "EN RELACIÓN CON LOS PROCESOS EVOLUTIVOS": (
        "procesos_evolutivos",
        "En relación con los procesos evolutivos",
    ),
    "EN RELACIÓN CON LAS PROPIEDADES, ESTRUCTURA Y USOS DE LOS MATERIALES": (
        "propiedades_materiales",
        "En relación con las propiedades, estructura y usos de los materiales",
    ),
    "EN RELACIÓN CON LAS TRANSFORMACIONES QUÍMICAS DE LOS MATERIALES": (
        "transformaciones_quimicas",
        "En relación con las transformaciones químicas de los materiales",
    ),
}
DISCIPLINAS = {
    "CIENCIAS NATURALES": None,  # las generales del área
    "BIOLOGÍA": "Biología",
    "FÍSICA": "Física",
    "QUÍMICA": "Química",
}
# Piloto aprobado (D60): (documento, grado, disciplina, eje) -> unidades
ESTRUCTURA_AR = {
    (ID_CB, None, None, GENERAL): 14,
    (ID_CB, 7, None, "seres_vivos"): 9,
    (ID_CB, 7, None, "materiales"): 5,
    (ID_CB, 7, None, "fisicos"): 3,
    (ID_CB, 7, None, "tierra_universo"): 1,
    (ID_CB, 8, None, "seres_vivos"): 7,
    (ID_CB, 8, None, "materiales"): 6,
    (ID_CB, 8, None, "fisicos"): 4,
    (ID_CB, 8, None, "tierra_universo"): 2,
    (ID_CB, 9, None, "seres_vivos"): 6,
    (ID_CB, 9, None, "materiales"): 7,
    (ID_CB, 9, None, "fisicos"): 5,
    (ID_CB, 9, None, "tierra_universo"): 5,
    (ID_CO, None, None, GENERAL): 6,
    (ID_CO, None, "Biología", "informacion_genetica"): 5,
    (ID_CO, None, "Biología", "procesos_evolutivos"): 3,
    (ID_CO, None, "Física", None): 4,
    (ID_CO, None, "Química", "propiedades_materiales"): 3,
    (ID_CO, None, "Química", "transformaciones_quimicas"): 4,
}
# Si algo de esto aparece en un texto, se coló un encabezado o una nota al pie
RESTOS = (
    "•",
    "Ministerio",
    "Consejo Federal",
    "Antonio Berni",
    "Documento aprobado",
    "Resolución CFE",
    "NÚCLEOS",
    "EJE:",
    "CICLO ORIENTADO",
    " AÑO",
    "Este enunciado",
    "Jurisdicción",
)


class Linea(NamedTuple):
    pagina: int
    y: float
    texto: str


# --- Páginas y líneas ----------------------------------------------------------


def _alto(p: Palabra) -> float:
    return p.y1 - p.y0


def _agrupar(palabras: list[Palabra]) -> list[list[Palabra]]:
    lineas: list[list[Palabra]] = []
    for p in sorted(palabras, key=lambda p: (p.y0, p.x0)):
        if lineas and p.y0 - lineas[-1][0].y0 <= TOLERANCIA_LINEA:
            lineas[-1].append(p)
        else:
            lineas.append([p])
    return lineas


def _es_llamada(p: Palabra, linea: list[Palabra], alto_texto: float) -> bool:
    """Un número pequeño pegado a la derecha de una palabra de la línea."""
    if _alto(p) >= alto_texto or not p.texto.isdigit():
        return False
    arriba = min(q.y0 for q in linea)
    abajo = max(q.y1 for q in linea)
    dentro = arriba - 3 <= (p.y0 + p.y1) / 2 <= abajo
    return dentro and any(-1 <= p.x0 - q.x1 <= 3 for q in linea)


def unir_linea(palabras: list[Palabra], llamadas: set[Palabra]) -> str:
    """Las palabras por x, sin las llamadas; la puntuación que las sigue va pegada."""
    texto = ""
    tras_llamada = False
    for p in sorted(palabras, key=lambda p: p.x0):
        if p in llamadas:
            tras_llamada = True
            continue
        pegada = tras_llamada and p.texto[:1] in ",.;:"
        texto += p.texto if pegada or not texto else f" {p.texto}"
        tras_llamada = False
    return texto


def lineas_de_pagina(
    palabras: list[Palabra], formato: Formato, pagina: int
) -> tuple[list[Linea], list[int]]:
    """Las líneas del texto (sin encabezado ni notas) y las llamadas que traían."""
    cuerpo = [p for p in palabras if p.y0 >= formato.y_encabezado]
    grandes = [p for p in cuerpo if _alto(p) >= formato.alto_texto]
    pequenas = [p for p in cuerpo if _alto(p) < formato.alto_texto]
    lineas, numeros = [], []
    for grupo in _agrupar(grandes):
        llamadas = {p for p in pequenas if _es_llamada(p, grupo, formato.alto_texto)}
        numeros += [int(p.texto) for p in llamadas]
        texto = unir_linea([*grupo, *llamadas], llamadas)
        lineas.append(Linea(pagina, grupo[0].y0, texto))
    return lineas, numeros


# --- Ciclo básico: viñetas ------------------------------------------------------


def unidad(doc: str, linea: Linea, texto: str, **campos) -> dict:
    base = {"documento": doc, "grado": None, "disciplina": None, "eje": None}
    return base | campos | {"paginas": [linea.pagina], "lineas": [texto]}


def seguir(u: dict, linea: Linea) -> None:
    u["lineas"].append(linea.texto)
    if linea.pagina not in u["paginas"]:
        u["paginas"].append(linea.pagina)


def es_encabezado_cb(texto: str) -> bool:
    """En mayúsculas, o el eje de 9.º que el original escribe en minúsculas."""
    return texto == texto.upper() or texto.upper() in EJES_CB


class LectorCB:
    """Recorre las líneas del ciclo básico guardando año, eje y viñeta abierta."""

    def __init__(self) -> None:
        self.unidades: list[dict] = []
        self.entradilla: list[str] = []
        self.grado: int | None = None
        self.eje: str | None = GENERAL
        self.pendiente = ""  # encabezado de eje partido en dos líneas
        self.abierta: dict | None = None

    def leer(self, linea: Linea) -> None:
        anio = re.fullmatch(r"(\d) ?° AÑO", linea.texto)
        sin_romano = re.sub(r"^I{1,3}\. ", "", linea.texto)
        if anio:
            self._exigir_eje_completo(linea)
            self.grado, self.eje, self.abierta = int(anio.group(1)), None, None
        elif linea.texto.startswith("• "):
            self._vineta(linea)
        elif es_encabezado_cb(sin_romano):
            self._encabezado(sin_romano, linea)
        else:
            self._continuacion(linea)

    def _exigir_eje_completo(self, linea: Linea) -> None:
        if self.pendiente:
            fallar(f"p{linea.pagina}: encabezado de eje incompleto: {self.pendiente!r}")

    def _vineta(self, linea: Linea) -> None:
        self._exigir_eje_completo(linea)
        if self.eje is None:
            fallar(f"p{linea.pagina}: viñeta sin eje en el grado {self.grado}")
        self.abierta = unidad(
            ID_CB, linea, linea.texto[2:], grado=self.grado, eje=self.eje
        )
        self.unidades.append(self.abierta)

    def _encabezado(self, texto: str, linea: Linea) -> None:
        self.pendiente = f"{self.pendiente} {texto.upper()}".strip()
        self.abierta = None
        if self.pendiente in EJES_CB:
            self.eje, self.pendiente = EJES_CB[self.pendiente][0], ""
        elif not any(e.startswith(self.pendiente) for e in EJES_CB):
            fallar(f"p{linea.pagina}: encabezado desconocido: {self.pendiente!r}")

    def _continuacion(self, linea: Linea) -> None:
        self._exigir_eje_completo(linea)
        if self.abierta:
            seguir(self.abierta, linea)
        elif not self.unidades:
            self.entradilla.append(linea.texto)
        else:
            fallar(f"p{linea.pagina}: texto fuera de toda viñeta: {linea.texto!r}")


def leer_cb(lineas: list[Linea]) -> tuple[list[dict], str]:
    lector = LectorCB()
    for linea in lineas:
        lector.leer(linea)
    return lector.unidades, " ".join(lector.entradilla)


# --- Ciclo orientado: párrafos ----------------------------------------------------


class LectorCO:
    """Recorre las líneas del ciclo orientado separando párrafos por el salto."""

    def __init__(self) -> None:
        self.unidades: list[dict] = []
        self.entradilla: list[str] = []
        self.disciplina: str | None = None
        self.eje: str | None = GENERAL
        self.pendiente = ""
        self.abierta: dict | None = None
        self.previa: Linea | None = None
        self.en_entradilla = False

    def leer(self, linea: Linea) -> None:
        texto = linea.texto
        if texto in DISCIPLINAS:
            self.disciplina = DISCIPLINAS[texto]
            self.eje = GENERAL if self.disciplina is None else None
            self._cerrar()
        elif texto.startswith("CICLO ORIENTADO"):
            self._cerrar()
        elif texto.startswith("EJE:") or (self.pendiente and texto == texto.upper()):
            self._encabezado(linea)
        else:
            self._parrafo(linea)

    def _cerrar(self) -> None:
        if self.pendiente:
            fallar(f"encabezado de eje desconocido o incompleto: {self.pendiente!r}")
        self.abierta, self.previa, self.en_entradilla = None, None, False

    def _encabezado(self, linea: Linea) -> None:
        trozo = linea.texto.removeprefix("EJE:").strip()
        self.pendiente = f"{self.pendiente} {trozo}".strip()
        self.abierta, self.previa = None, None
        if self.pendiente in EJES_CO:
            self.eje, self.pendiente = EJES_CO[self.pendiente][0], ""
        elif not any(e.startswith(self.pendiente) for e in EJES_CO):
            fallar(f"p{linea.pagina}: encabezado desconocido: {self.pendiente!r}")

    def _parrafo(self, linea: Linea) -> None:
        if self.pendiente:
            self._cerrar()
        otra_pagina = self.previa is not None and linea.pagina != self.previa.pagina
        salto = (
            self.previa is None
            or otra_pagina
            or linea.y - self.previa.y > SALTO_PARRAFO
        )
        # un párrafo que pasa de página sigue en minúscula
        sigue = not salto or (otra_pagina and linea.texto[:1].islower())
        self.previa = linea
        if linea.texto.startswith(ENTRADILLAS[ID_CO]):
            self.en_entradilla, self.abierta = True, None
        elif salto and not sigue:
            self.en_entradilla = False
        if self.en_entradilla:
            self.entradilla.append(linea.texto)
        elif sigue and self.abierta:
            seguir(self.abierta, linea)
        elif linea.texto[:1].isupper():
            self.abierta = unidad(
                ID_CO, linea, linea.texto, disciplina=self.disciplina, eje=self.eje
            )
            self.unidades.append(self.abierta)
        else:
            fallar(f"p{linea.pagina}: párrafo que no empieza en mayúscula")


def leer_co(lineas: list[Linea]) -> tuple[list[dict], str]:
    lector = LectorCO()
    for linea in lineas:
        lector.leer(linea)
    return lector.unidades, " ".join(lector.entradilla)


# --- Documento y controles --------------------------------------------------------

LECTORES = {ID_CB: leer_cb, ID_CO: leer_co}


def texto_de_documento(doc_id: str, paginas: list[list[Palabra]]) -> list[Linea]:
    """Las líneas de las páginas con unidades; comprueba portadas y llamadas a nota."""
    formato = FORMATOS[doc_id]
    if len(paginas) != formato.paginas:
        fallar(f"{doc_id}: {len(paginas)} páginas y se esperaban {formato.paginas}")
    lineas: list[Linea] = []
    numeros: list[int] = []
    for n, palabras in enumerate(paginas, start=1):
        if n in formato.sin_unidades:
            if PORTADAS[doc_id] not in " ".join(p.texto for p in palabras):
                fallar(f"{doc_id} p{n}: no es la portada esperada")
            continue
        de_pagina, llamadas = lineas_de_pagina(palabras, formato, n)
        lineas += de_pagina
        numeros += llamadas
    if sorted(numeros) != list(range(1, formato.notas + 1)):
        fallar(
            f"{doc_id}: llamadas a nota {sorted(numeros)}, esperadas 1 a "
            f"{formato.notas}"
        )
    return lineas


def extraer_documento(doc_id: str, paginas: list[list[Palabra]]) -> list[dict]:
    """Las unidades de un documento, con su texto y su entradilla."""
    unidades, entradilla = LECTORES[doc_id](texto_de_documento(doc_id, paginas))
    if not entradilla.startswith(ENTRADILLAS[doc_id]) or entradilla[-1:] != ":":
        fallar(f"{doc_id}: no se leyó bien la frase que abre las generales")
    for u in unidades:
        u["texto"] = " ".join(" ".join(u.pop("lineas")).split())
        u["contexto"] = entradilla if u["eje"] == GENERAL else None
    return unidades


def controlar_vinetas(unidades: list[dict], paginas: list[list[Palabra]]) -> None:
    en_pdf = sum(p.texto == "•" for pagina in paginas for p in pagina)
    if len(unidades) != en_pdf:
        fallar(f"{ID_CB}: {len(unidades)} unidades y el PDF tiene {en_pdf} viñetas")


def controlar_estructura(unidades: list[dict]) -> None:
    leida: dict[tuple, int] = {}
    for u in unidades:
        clave = (u["documento"], u["grado"], u["disciplina"], u["eje"])
        leida[clave] = leida.get(clave, 0) + 1
    if leida != ESTRUCTURA_AR:
        distintas = {
            k: (leida.get(k, 0), ESTRUCTURA_AR.get(k, 0))
            for k in leida.keys() | ESTRUCTURA_AR.keys()
            if leida.get(k, 0) != ESTRUCTURA_AR.get(k, 0)
        }
        fallar(
            "Argentina: unidades distintas de las del piloto "
            f"(leídas, esperadas): {distintas}"
        )


def controlar_textos(unidades: list[dict]) -> None:
    """Textos completos, sin números de nota y sin restos de encabezados o notas."""
    for u in unidades:
        donde = f"{u['documento']} p{u['paginas'][0]}"
        t = u["texto"]
        if len(t.split()) < 3 or not t[:1].isupper() or not t.endswith("."):
            fallar(f"{donde}: texto vacío, cortado o sin punto: …{t[-40:]!r}")
        if re.search(r"\d| [,.;:]", t):
            fallar(f"{donde}: quedó un número de nota o un signo suelto")
        restos = [r for r in RESTOS if r in t]
        if restos:
            fallar(f"{donde}: restos de encabezado o de nota al pie: {restos}")


# --- Salida ------------------------------------------------------------------------

NOMBRES_DE_EJE = dict((*EJES_CB.values(), *EJES_CO.values()), general=GENERAL)


def leer_pdf(pdf: Path) -> list[list[Palabra]]:
    salida = ejecutar(["pdftotext", "-bbox", str(pdf), "-"]).stdout
    return [palabras for _, palabras in paginas_con_cajas(salida)]


def extraer(documentos: dict[str, dict]) -> list[dict]:
    unidades: list[dict] = []
    for doc_id, doc in documentos.items():
        esperado = FORMATOS[doc_id].nivel_cine
        if doc["nivel_cine"] != esperado:
            fallar(f"{doc_id}: el inventario dice CINE {doc['nivel_cine']}")
        paginas = leer_pdf(pdf_verificado(doc))
        suyas = extraer_documento(doc_id, paginas)
        if doc_id == ID_CB:
            controlar_vinetas(suyas, paginas)
        unidades += suyas
    controlar_estructura(unidades)
    controlar_textos(unidades)
    return unidades


def identificador(u: dict) -> str:
    """P. ej. «AR-NAP-CB:G7.seres_vivos» o «AR-NAP-CO:fisica»."""
    partes = []
    if u["grado"] is not None:
        partes.append(f"G{u['grado']}")
    if u["disciplina"] is not None:
        partes.append(
            {"Biología": "biologia", "Física": "fisica", "Química": "quimica"}[
                u["disciplina"]
            ]
        )
    if u["eje"] is not None:
        partes.append(u["eje"])
    return f"{u['documento']}:{'.'.join(partes)}"


def registros_ar(documentos: dict[str, dict], unidades: list[dict]) -> list[dict]:
    veces: dict[str, int] = {}
    salida = []
    for u in unidades:
        base = identificador(u)
        veces[base] = veces.get(base, 0) + 1
        salida.append(
            {
                "id_unidad": f"{base}.{veces[base]}",
                **procedencia(documentos[u["documento"]]),
                "tipo_unidad": "nap_argentina",
                "grado": u["grado"],
                "etapa": ETAPAS[u["documento"]],
                "marca_nivel": MARCA_7 if u["grado"] == 7 else None,
                "disciplina": u["disciplina"],
                "eje_id": u["eje"],
                "eje": None if u["eje"] is None else NOMBRES_DE_EJE[u["eje"]],
                "contexto": u["contexto"],
                "texto": u["texto"],
                "texto_es": u["texto"],
                "idioma": "es",
                "pagina": u["paginas"][0],
                "paginas": u["paginas"],
            }
        )
    return salida


def conteos(doc_id: str, registros: list[dict]) -> dict:
    suyos = [r for r in registros if r["documento"] == doc_id]
    por_grupo: dict[str, int] = {}
    for r in suyos:
        grupo = r["id_unidad"].split(":")[1].rsplit(".", 1)[0]
        por_grupo[grupo] = por_grupo.get(grupo, 0) + 1
    return {
        "unidades": len(suyos),
        "generales": sum(r["eje_id"] == GENERAL for r in suyos),
        "por_grupo": por_grupo,
        "con_marca_de_nivel": sum(r["marca_nivel"] is not None for r in suyos),
        "llamadas_a_nota_quitadas": FORMATOS[doc_id].notas,
        "unidades_en_dos_paginas": [
            r["id_unidad"] for r in suyos if len(r["paginas"]) > 1
        ],
    }


def correr(salida_datos: Path, salida_resumen: Path) -> dict:
    for ruta in (salida_datos, salida_resumen):
        if ruta.exists():
            fallar(f"ya existe {ruta}; no se sobrescribe una extracción anterior")
    documentos = {i: documento_del_inventario(i) for i in (ID_CB, ID_CO)}
    registros = registros_ar(documentos, extraer(documentos))
    version = version_pdftotext()  # antes de escribir: si falla, no queda nada a medias
    salida_datos.parent.mkdir(parents=True, exist_ok=True)
    with salida_datos.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    resumen = {
        "decision": "D60",
        "fecha": date.today().isoformat(),
        "pdftotext": version,
        "inventario": {
            "archivo": relativa(INVENTARIO),
            "sha256": sha256_de(INVENTARIO),
        },
        "documentos": {
            i: resumen_documento(doc, (1, FORMATOS[i].paginas), conteos(i, registros))
            for i, doc in documentos.items()
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
