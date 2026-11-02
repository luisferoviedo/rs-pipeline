"""Cierre de la adjudicación de C05, C06 y C08 con la definición estricta (D52).

Lee la hoja del lector (outputs/semantico/adjudicacion_presencia_20_lector.csv, que
no se modifica) y, para los 37 desacuerdos de D51:
- A01 y A02 ya los decidió Luis Fer (código final 0);
- si la ficha contiene algún término de la lista «cuenta» del criterio, el caso queda
  en «revisar» para Luis Fer; si no, queda en 0 con la regla D52.
También cuenta, en los informes V de C05 con código final 0, cuántos tienen C03 = 1 en
la codificación de Claude, y calcula la prevalencia amplia (investigador), literal
(Claude) y final. A git van solo los números; las hojas con texto quedan en
outputs/semantico (ignorada). Falla (código 1) si falta un archivo o una columna.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

from rs_pipeline import semantico_04 as S
from rs_pipeline import verificacion_presencia_20 as V
from rs_pipeline.codificacion_claude import (
    RAIZ_REPO,
    RUTA_LOG,
    leer_registro,
    ultimas_por_informe,
)
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

LECTOR = "adjudicacion_presencia_20_lector.csv"
CIERRE = "adjudicacion_presencia_20_cierre.csv"
REVISAR = "adjudicacion_revisar.csv"
DECIDIDOS = {"A01", "A02"}  # decididos por Luis Fer: código final 0
REGLA = "claude (regla D52)"
NORMALIZADAS = {"nivel_norm", "disciplina_norm", "oe1_direccion_norm"}
RETRO = (
    r"retroaliment\w*\W+(?:\w+\W+){0,3}automatic"
    r"|automatic\w*\W+(?:\w+\W+){0,3}retroaliment"
)
# Lista «cuenta» de cada criterio (raíz al inicio de palabra, sin tildes ni mayúsculas).
TERMINOS = {
    "C05": {
        "medi-": r"\bmedi",
        "registr-": r"\bregistr",
        "calcul-": r"\bcalcul",
        "tabla": r"\btabla",
        "dato": r"\bdato",
    },
    "C06": {
        "puntaje": r"\bpuntaje",
        "error": r"\berror",
        "indicador": r"\bindicador",
        "retroaliment- automática": rf"\b(?:{RETRO})",
    },
    "C08": {
        "predic-": r"\bpredic",
        "compar-": r"\bcompar",
        "verific-": r"\bverific",
        "contrast-": r"\bcontrast",
        "referencia": r"\breferencia",
    },
}


def _sin_tildes(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto.lower())
    return base.encode("ascii", "ignore").decode()


def campos_de_ficha(lector: pd.DataFrame) -> list[str]:
    """Columnas de texto libre de la ficha (entre «tema» y «decision»)."""
    cols = list(lector.columns)
    ficha = cols[cols.index("tema") : cols.index("decision")]
    return [c for c in ficha if c not in NORMALIZADAS]


def terminos_hallados(fila: pd.Series, campos: list[str]) -> dict[str, list[str]]:
    """Término de la lista «cuenta» → campos de la ficha donde aparece."""
    hallados = {}
    for nombre, patron in TERMINOS[fila["criterio"]].items():
        donde = [c for c in campos if re.search(patron, _sin_tildes(fila[c]))]
        if donde:
            hallados[nombre] = donde
    return hallados


def cerrar(lector: pd.DataFrame) -> pd.DataFrame:
    """Hoja del lector + código final y la decisión de cada caso."""
    campos = campos_de_ficha(lector)
    hoja = lector.copy()
    hoja["codigo_final"] = ""
    for i, fila in lector.iterrows():
        hallados = terminos_hallados(fila, campos)
        if fila["caso"] in DECIDIDOS:
            nuevo = {"decision": "claude", "codigo_final": "0"}
            nuevo["razon"] = "decidido por Luis Fer"
        elif hallados:
            nuevo = {"decision": "revisar", "item_cuenta": ", ".join(hallados)}
            nuevo["razon"] = "la ficha contiene: " + "; ".join(
                f"{t} ({', '.join(c)})" for t, c in hallados.items()
            )
        else:
            nuevo = {"decision": REGLA, "codigo_final": "0"}
            nuevo["razon"] = "la ficha no menciona ningún término de la lista «cuenta»"
        for columna, valor in nuevo.items():
            hoja.loc[i, columna] = valor
    return hoja


def codigos_de_claude(params: dict) -> tuple[dict[str, str], dict[str, dict]]:
    """V → T y el registro de Claude con el libro v3 (como en D51)."""
    carpeta = RAIZ_REPO / params["semantico"]["salidas"]
    claves = ["id_ciego", "id"]
    corr20 = V._leer(carpeta / V.CORRESPONDENCIA_20, claves, claves)
    corr196 = V._leer(carpeta / V.CORRESPONDENCIA_196, claves, claves)
    cruce = V.cruzar_ids(corr20, corr196)
    libro = RAIZ_REPO / "config" / V.LIBRO
    claude = ultimas_por_informe(leer_registro(), S.sha256(libro))
    if set(claude) != set(corr196["id_ciego"]):
        fallar(f"El registro no trae los {V.N_TOTAL} informes T con el libro v3")
    return cruce, claude


def tabla_de_prevalencias(cierre, luis, cruce, claude) -> pd.DataFrame:
    """Prevalencia amplia (investigador), literal (Claude) y final, sobre los 20."""
    n = V.N_VERIFICACION
    filas = []
    for c in V.VERIFICADOS:
        sub = cierre[cierre["criterio"] == c]
        revisar = int((sub["decision"] == "revisar").sum())
        amplia = int(luis[c].astype(int).sum())
        literal = sum(claude[cruce[i]]["codigos"][c] for i in luis.index)
        # Los desacuerdos son todos Luis Fer 1 / Claude 0: el código final de los
        # decididos es 0; los «revisar» pueden quedar en 0 o en 1.
        base = amplia - len(sub)
        filas.append(
            {
                "criterio": c,
                "desacuerdos": len(sub),
                "decididos_a_0": len(sub) - revisar,
                "a_revisar": revisar,
                "n_amplia_investigador": amplia,
                "n_literal_claude": literal,
                "prevalencia_amplia_investigador": round(amplia / n, 3),
                "prevalencia_literal_claude": round(literal / n, 3),
                "prevalencia_final_minima": round(base / n, 3),
                "prevalencia_final_maxima": round((base + revisar) / n, 3),
            }
        )
    return pd.DataFrame(filas)


def calcular(params: dict) -> dict:
    carpeta = RAIZ_REPO / params["semantico"]["salidas"]
    lector = V._leer(
        carpeta / LECTOR, ["caso", "id_ciego", "criterio", "tema", "decision"], ["caso"]
    )
    if len(lector) != 37:
        fallar(f"{LECTOR} debería traer los 37 desacuerdos de D51 y trae {len(lector)}")
    cierre = cerrar(lector)
    cruce, claude = codigos_de_claude(params)
    c05 = sorted(cierre.loc[cierre["criterio"] == "C05", "id_ciego"])
    c03 = {i: claude[cruce[i]]["codigos"]["C03"] for i in c05}
    return {
        "cierre": cierre,
        "tabla": tabla_de_prevalencias(cierre, V.leer_luis(carpeta), cruce, claude),
        "c03_en_c05": c03,
        "c03_prevalencia_196": sum(r["codigos"]["C03"] for r in claude.values())
        / len(claude),
        "entrada": carpeta / LECTOR,
    }


def comprobar_revisar(ruta: Path) -> None:
    """No pisa una hoja de «revisar» en la que Luis Fer ya cargó decisiones."""
    if ruta.is_file():
        previa = pd.read_csv(ruta, dtype=str, keep_default_na=False)
        if (previa.get("decision", pd.Series(dtype=str)) != "revisar").any():
            fallar(f"{ruta.name} ya tiene decisiones de Luis Fer; no se sobrescribe")


def guardar(params: dict, r: dict) -> None:
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    cierre = r["cierre"]
    ruta_cierre = privada / CIERRE
    ruta_revisar = privada / REVISAR
    comprobar_revisar(ruta_revisar)
    salida = {"index": False, "encoding": "utf-8-sig", "lineterminator": "\n"}
    cierre.to_csv(ruta_cierre, **salida)
    columnas = [c for c in cierre.columns if c != "codigo_final"]
    cierre.loc[cierre["decision"] == "revisar", columnas].to_csv(ruta_revisar, **salida)
    carpeta = RAIZ_REPO / params["salidas"]["tablas"]
    ruta_csv = carpeta / "calibracion_presencia_20.csv"
    r["tabla"].to_csv(ruta_csv, index=False, lineterminator="\n")
    c03 = r["c03_en_c05"]
    traza = {
        "nota": "D52: definición estricta (literal) de C05, C06 y C08. Prevalencia "
        "amplia = códigos del investigador; literal = códigos de Claude (libro v3).",
        "n_informes": V.N_VERIFICACION,
        "terminos_cuenta": {c: list(t) for c, t in TERMINOS.items()},
        "regla_busqueda": "raíz al inicio de palabra, sin tildes ni mayúsculas, en los "
        "campos de texto de la ficha (sin nivel_norm, disciplina_norm ni "
        "oe1_direccion_norm); retroalimentación automática = ambas palabras a "
        "menos de 4 palabras",
        "decididos_por_luis_fer": sorted(DECIDIDOS),
        "casos_a_revisar": int((cierre["decision"] == "revisar").sum()),
        "casos_decididos_a_0": int((cierre["codigo_final"] == "0").sum()),
        "c03_en_los_c05_de_desacuerdo": {
            "informes": len(c03),
            "con_c03_igual_1": sum(c03.values()),
            "prevalencia_c03_claude_en_196": round(r["c03_prevalencia_196"], 3),
        },
        "entradas": [
            {"archivo": p.name, "sha256": S.sha256(p)} for p in (r["entrada"], RUTA_LOG)
        ],
        "salida": {"archivo": ruta_csv.name, "sha256": S.sha256(ruta_csv)},
    }
    (carpeta / "calibracion_presencia_20.json").write_text(
        json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    try:
        params = S.cargar_params()
        resultado = calcular(params)
        guardar(params, resultado)
        print(resultado["tabla"].to_string(index=False))
        print(
            "C03 en los C05:", resultado["c03_en_c05"], resultado["c03_prevalencia_196"]
        )
        print(resultado["cierre"]["decision"].value_counts().to_string())
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
