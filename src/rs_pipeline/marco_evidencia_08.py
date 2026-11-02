"""Tabla de evidencia del marco de criterios v0 con los códigos de presencia (D54).

Cruza los códigos de Claude de los 196 informes (libro v3) con el peso de evidencia
(D43), el nivel, la disciplina y la dirección del efecto. Un estudio tiene un criterio
«presente» si lo tiene alguno de sus informes; sus atributos salen del informe de más
puntos (como en el Bloque 6). La prueba exacta de Fisher es solo descriptiva: se
reportan las cinco direcciones de los nueve criterios, sin corrección por comparaciones
múltiples. A git van solo números. Falla (código 1) si falta un archivo o una columna,
si las bases no son 196 informes y 193 estudios, o si un código no es 0 ni 1.
"""

from __future__ import annotations

import json
import sys
from math import comb

import pandas as pd
import yaml

from rs_pipeline import criterios_05 as C
from rs_pipeline import semantico_04 as S
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ_REPO = S.RAIZ_REPO
CODIGOS = "codigos_claude_196_v3.csv"
CORRESPONDENCIA = "hoja_codificacion_196_correspondencia.csv"
SALIDA = "marco_evidencia_v0"
N_INFORMES, N_ESTUDIOS = 196, 193
ETIQUETAS = {
    "C01": "condición base",
    "C02": "condición base",
    "C06": "brecha de diseño",
}
CON_NOTA_D52 = ["C05", "C06", "C08"]
NOTA_D52 = (
    "D52: la prevalencia depende del umbral; con la lectura amplia del investigador "
    "era 0,85-0,95 y con la definición estricta (libro v3) es la reportada"
)


def fisher_dos_colas(a: int, b: int, c: int, d: int) -> float:
    """Fisher exacto bilateral de [[a, b], [c, d]] (tablas no más probables)."""
    f1, f2, c1, n = a + b, c + d, a + c, a + b + c + d
    denominador = comb(n, c1)

    def prob(k: int) -> float:
        return comb(f1, k) * comb(f2, c1 - k) / denominador

    observada = prob(a)
    posibles = range(max(0, c1 - f2), min(f1, c1) + 1)
    total = sum(p for p in map(prob, posibles) if p <= observada * (1 + 1e-9))
    return min(1.0, total)


def leer_presencia(params: dict) -> pd.DataFrame:
    """Informe real × criterio (0/1), a partir de los códigos T001…T196."""
    carpeta = RAIZ_REPO / params["semantico"]["salidas"]
    for nombre in (CODIGOS, CORRESPONDENCIA):
        if not (carpeta / nombre).is_file():
            fallar(f"Falta {nombre}")
    codigos = pd.read_csv(
        carpeta / CODIGOS, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    corr = pd.read_csv(
        carpeta / CORRESPONDENCIA,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    faltan = [c for c in ["id_ciego", "criterio", "codigo"] if c not in codigos]
    if faltan or {"id_ciego", "id"} - set(corr):
        fallar(f"Faltan columnas en {CODIGOS} o {CORRESPONDENCIA}: {faltan}")
    if set(codigos["codigo"]) - {"0", "1"}:
        fallar(f"{CODIGOS} tiene un código que no es 0 ni 1")
    if codigos.duplicated(["id_ciego", "criterio"]).any():
        fallar(f"{CODIGOS} repite informe y criterio")
    ancha = codigos.pivot(index="id_ciego", columns="criterio", values="codigo")
    if ancha.shape[0] != N_INFORMES or ancha.isna().any().any():
        fallar(f"{CODIGOS} debería traer {N_INFORMES} informes con todos los criterios")
    ancha = ancha.astype(int)
    ancha.index = ancha.index.map(dict(zip(corr["id_ciego"], corr["id"], strict=True)))
    return ancha


def cruzar(presencia: pd.DataFrame, informes: pd.DataFrame) -> pd.DataFrame:
    """Informes (peso, nivel, disciplina, dirección) con su presencia por criterio."""
    if set(presencia.index) != set(informes["id"]):
        fallar("Los informes codificados no son los mismos de la matriz")
    return informes.join(presencia, on="id")


def contar_orden(serie: pd.Series, categorias: list[str]) -> list[int]:
    return [int((serie == c).sum()) for c in categorias]


def fila_de_criterio(cid: str, informes: pd.DataFrame, estudios: pd.DataFrame) -> dict:
    pres_inf = informes[cid] == 1
    por_estudio = informes.groupby("estudio")[cid].max().astype(bool)
    e = estudios.join(por_estudio.rename("presente"))
    pres, aus = e[e["presente"]], e[~e["presente"]]
    fila = {
        "id_criterio": cid,
        "etiqueta": ETIQUETAS.get(cid, ""),
        "nota_calibracion_d52": "sí" if cid in CON_NOTA_D52 else "",
        "n_informes_total": len(informes),
        "n_informes_presentes": int(pres_inf.sum()),
        "n_informes_ausentes": int((~pres_inf).sum()),
        "pct_informes_presentes": round(100 * pres_inf.mean(), 1),
        "n_estudios_total": len(e),
        "n_estudios_presentes": len(pres),
        "n_estudios_ausentes": len(aus),
        "pct_estudios_presentes": round(100 * len(pres) / len(e), 1),
    }
    for regla in ("peso_suma", "peso_minimo"):
        prefijo = regla.replace("peso_", "")
        for etiqueta in C.ETIQUETAS_PESO[::-1]:
            fila[f"{prefijo}_{etiqueta}"] = int((pres[regla] == etiqueta).sum())
        fila[f"pct_{prefijo}_alto"] = round(
            100 * fila[f"{prefijo}_alto"] / len(pres), 1
        )
    for columna, categorias, prefijo in (
        ("nivel", ["secundaria", "universitario", "otro"], "nivel"),
        ("disciplina", C.DISCIPLINAS, "disciplina"),
    ):
        for cat, n in zip(
            categorias, contar_orden(pres[columna], categorias), strict=True
        ):
            fila[f"{prefijo}_{cat}"] = n
    for direccion in C.DIRECCIONES:
        a = int((pres["direccion"] == direccion).sum())
        c = int((aus["direccion"] == direccion).sum())
        fila[f"dir_presente_{direccion}"] = a
        fila[f"dir_ausente_{direccion}"] = c
        fila[f"fisher_p_{direccion}"] = round(
            fisher_dos_colas(a, len(pres) - a, c, len(aus) - c), 4
        )
    return fila


def ejecutar(params: dict) -> tuple[pd.DataFrame, dict]:
    matriz = S.cargar_matriz(params)
    conteos = json.loads((RAIZ_REPO / params["prisma_counts_vigente"]).read_text())
    estudios_id = C.asignar_estudios(matriz["tabla"], conteos["incluidos_estudios"])
    informes = C.tabla_de_informes(matriz["tabla"], estudios_id)
    estudios = C.tabla_de_estudios(informes)
    if len(informes) != N_INFORMES or len(estudios) != N_ESTUDIOS:
        fallar(f"Las bases deben ser {N_INFORMES} informes y {N_ESTUDIOS} estudios")
    ruta_marco = RAIZ_REPO / "config" / "criterios_v0.yaml"
    marco = yaml.safe_load(ruta_marco.read_text(encoding="utf-8"))
    presencia = leer_presencia(params)
    completa = cruzar(presencia, informes)
    filas = [fila_de_criterio(c["id"], completa, estudios) for c in marco["criterios"]]
    carpeta = RAIZ_REPO / params["semantico"]["salidas"]
    entradas = {
        "codigos_claude": {"archivo": CODIGOS, "sha256": S.sha256(carpeta / CODIGOS)},
        "correspondencia": {
            "archivo": CORRESPONDENCIA,
            "sha256": S.sha256(carpeta / CORRESPONDENCIA),
        },
        "matriz_normalizada": {
            "archivo": str(matriz["ruta"].relative_to(RAIZ_REPO)),
            "sha256": matriz["sha256"],
        },
        "marco_de_criterios": {
            "archivo": "config/criterios_v0.yaml",
            "sha256": S.sha256(ruta_marco),
        },
        "libro_codigos": {
            "archivo": "config/libro_codigos_v3.yaml",
            "sha256": S.sha256(RAIZ_REPO / "config" / "libro_codigos_v3.yaml"),
        },
    }
    return pd.DataFrame(filas), entradas


def guardar(params: dict, tabla: pd.DataFrame, entradas: dict) -> None:
    carpeta = RAIZ_REPO / params["salidas"]["tablas"]
    ruta_csv = carpeta / f"{SALIDA}.csv"
    C.escribir_csv(ruta_csv, tabla, encoding="utf-8")
    traza = {
        "nota": "D54: presencia según los códigos de Claude (libro v3, codificación "
        "asistida por IA con libro de códigos cerrado). Solo números.",
        "base": {"informes": N_INFORMES, "estudios": N_ESTUDIOS},
        "estudio_presente": "algún informe del estudio con presencia",
        "atributos_del_estudio": "informe de más puntos (D43)",
        "pesos": "suma = regla principal de D43; mínimo = sensibilidad",
        "fisher": "exacta bilateral, descriptiva, sin corrección; cada dirección "
        "frente al resto, estudios con el criterio presente vs. ausente",
        "etiquetas": ETIQUETAS,
        "nota_calibracion_d52": {"criterios": CON_NOTA_D52, "texto": NOTA_D52},
        "entradas": entradas,
        "salida": {"archivo": ruta_csv.name, "sha256": S.sha256(ruta_csv)},
    }
    (carpeta / f"{SALIDA}.json").write_text(
        json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resumen(tabla: pd.DataFrame) -> str:
    cols = [
        "id_criterio",
        "etiqueta",
        "pct_informes_presentes",
        "pct_estudios_presentes",
    ]
    cols += ["pct_suma_alto", "pct_minimo_alto"]
    return tabla[cols].to_string(index=False)


def main() -> int:
    try:
        params = S.cargar_params()
        tabla, entradas = ejecutar(params)
        guardar(params, tabla, entradas)
        print(resumen(tabla))
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
