"""Cierre de la revisión de discrepancias de C05, C06 y C08 (D53).

Lee la hoja de cierre de D52 y fija en 0 los 15 casos que seguían en «revisar»:
el investigador adopta la definición operacional estricta del libro v3. Deja la
nota de revisión de A01, A04 y A11 y calcula la prevalencia final de C05, C06 y
C08 en los 20 informes de la verificación humana. No calcula kappa ni AC1 después
de la revisión: ya no hay codificadores independientes. A git van solo los números.
Falla (código 1) si falta un archivo o una columna, o si la hoja no trae los 37 casos.
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from rs_pipeline import adjudicacion_d52 as A
from rs_pipeline import semantico_04 as S
from rs_pipeline import verificacion_presencia_20 as V
from rs_pipeline.codificacion_claude import RAIZ_REPO
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

DECISION = "investigador (D53)"
RAZON = (
    "revisión de discrepancias por el investigador, con adopción de la definición "
    "operacional estricta"
)
# Notas de la revisión (texto de Luis Fer, 2 nov 2026), por caso de la hoja.
NOTAS = {
    "A01": "lo que el investigador veía en C05 lo asocia a C03; no se confirma con los "
    "códigos (D52); se deja anotado y no se recodifica",
    "A04": "V07, C05: la secuencia predicción → prueba es C08 y la manipulación es "
    "C03; no hay medición ni registro de datos",
    "A11": "V03, C06: la retroalimentación visual inmediata no dice qué muestra; la "
    "del docente o de pares es C04",
}
SALIDA = "prevalencia_final_presencia_20"


def aplicar(cierre: pd.DataFrame) -> pd.DataFrame:
    """Fija en 0 los casos «revisar» y agrega la nota de revisión."""
    if len(cierre) != 37 or "codigo_final" not in cierre.columns:
        fallar(f"{A.CIERRE} debería traer los 37 casos de D52 con codigo_final")
    hoja = cierre.copy()
    if "nota_d53" not in hoja.columns:
        hoja["nota_d53"] = ""
    pendientes = hoja["decision"] == "revisar"
    hoja.loc[pendientes, ["decision", "codigo_final", "razon"]] = [
        DECISION,
        "0",
        RAZON,
    ]
    for caso, nota in NOTAS.items():
        if caso not in set(hoja["caso"]):
            fallar(f"Falta el caso {caso} en {A.CIERRE}")
        hoja.loc[hoja["caso"] == caso, "nota_d53"] = nota
    if set(hoja["codigo_final"]) != {"0"}:
        fallar("Tras D53 los 37 casos deben quedar con codigo_final 0")
    return hoja


def prevalencias(cierre: pd.DataFrame, luis: pd.DataFrame) -> pd.DataFrame:
    """Prevalencia final: lo que el investigador marcó 1, menos los casos en 0."""
    n = V.N_VERIFICACION
    filas = []
    for c in V.VERIFICADOS:
        sub = cierre[cierre["criterio"] == c]
        amplia = int(luis[c].astype(int).sum())
        final = amplia - int((sub["codigo_final"] == "0").sum())
        filas.append(
            {
                "criterio": c,
                "n_informes": n,
                "n_amplia_investigador": amplia,
                "casos_adjudicados_a_0": len(sub),
                "n_final": final,
                "prevalencia_final": round(final / n, 3),
            }
        )
    return pd.DataFrame(filas)


def main() -> int:
    try:
        params = S.cargar_params()
        privada = RAIZ_REPO / params["semantico"]["salidas"]
        ruta = privada / A.CIERRE
        cierre = V._leer(
            ruta, ["caso", "criterio", "decision", "codigo_final"], ["caso"]
        )
        hoja = aplicar(cierre)
        tabla = prevalencias(hoja, V.leer_luis(privada))
        hoja.to_csv(ruta, index=False, encoding="utf-8-sig", lineterminator="\n")
        carpeta = RAIZ_REPO / params["salidas"]["tablas"]
        ruta_csv = carpeta / f"{SALIDA}.csv"
        tabla.to_csv(ruta_csv, index=False, lineterminator="\n")
        traza = {
            "nota": "D53: prevalencia final tras la revisión de discrepancias por el "
            "investigador. No se calcula kappa ni AC1 después de la revisión.",
            "casos_adjudicados_a_0": int((hoja["codigo_final"] == "0").sum()),
            "entradas": [{"archivo": ruta.name, "sha256": S.sha256(ruta)}],
            "salida": {"archivo": ruta_csv.name, "sha256": S.sha256(ruta_csv)},
        }
        (carpeta / f"{SALIDA}.json").write_text(
            json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(tabla.to_string(index=False))
        print(hoja["decision"].value_counts().to_string())
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
