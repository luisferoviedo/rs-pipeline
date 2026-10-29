"""Recalcula los conteos PRISMA desde los CSV del Drive y los compara con el JSON.

El Drive es solo lectura. El script no escribe nada: imprime un reporte y termina
con código 1 si algún conteo no cuadra o si falta algún archivo, columna o ID.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import NoReturn

import pandas as pd
import yaml

RAIZ_REPO = Path(__file__).resolve().parents[2]
CODIGOS_EXCLUSION = ["E1", "E2", "E3", "E4", "E5"]
DECISIONES_CRIBADO = {"I", "D", *CODIGOS_EXCLUSION}
DECISIONES_ELEGIBILIDAD = {"INCLUIDO", "EXCLUIDO", "NO_CORRESPONDE", "NO_RECUPERADO"}
OBTENIDO_VALIDOS = {"sí", "no", "duplicado"}
DUDOSOS_VALIDOS = {"ok", "excluir"}
PREFIJO_E4_DUDOSOS = "Excluir E4"

COLUMNAS = {
    "cribado": ["id_revision", "decision"],
    "recuperacion": ["id_revision", "decision_cribado", "obtenido"],
    "elegibilidad": ["id_revision", "decision", "codigo"],
    "dudosos": ["id", "sugerencia_automatica", "decision_luisfer"],
    "extraccion": ["id", "estudio_compartido_con"],
}
CLAVES_ESCALARES = [
    "cribados",
    "excluidos_cribado",
    "buscados_texto_completo",
    "no_recuperados",
    "evaluados",
    "excluidos_texto_completo",
    "incluidos_informes",
    "incluidos_estudios",
]
CLAVES_MOTIVOS = ["excluidos_cribado_motivos", "excluidos_texto_completo_motivos"]
CLAVES_DECLARADAS = [
    *CLAVES_ESCALARES,
    *CLAVES_MOTIVOS,
    "identificados",
    "duplicados",
]


class ErrorPipeline(Exception):
    """Falla esperada: falta un dato o un conteo no cuadra."""


def fallar(mensaje: str) -> NoReturn:
    raise ErrorPipeline(mensaje)


# --- Lectura de entradas -------------------------------------------------------


def leer_env(ruta: Path) -> dict[str, str]:
    """Lector mínimo de .env: líneas CLAVE=valor, con comillas opcionales."""
    valores: dict[str, str] = {}
    if not ruta.is_file():
        return valores
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "=" not in linea:
            fallar(f"{ruta.name} línea {numero}: se esperaba CLAVE=valor")
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip().strip("\"'")
    return valores


def raiz_drive(nombre_variable: str) -> Path:
    valor = os.environ.get(nombre_variable) or leer_env(RAIZ_REPO / ".env").get(
        nombre_variable, ""
    )
    if not valor:
        fallar(f"Falta {nombre_variable}: defínela en .env (ver .env.example)")
    raiz = Path(valor).expanduser()
    if not raiz.is_dir():
        fallar(f"{nombre_variable} apunta a una carpeta que no existe: {raiz}")
    return raiz


def sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def leer_csv(ruta: Path, columnas: list[str], col_id: str) -> pd.DataFrame:
    if not ruta.is_file():
        fallar(f"No existe el archivo: {ruta}")
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    faltan = [c for c in columnas if c not in tabla.columns]
    if faltan:
        fallar(f"{ruta.name}: faltan las columnas {faltan}")
    repetidos = sorted(tabla.loc[tabla[col_id].duplicated(), col_id])
    if repetidos:
        fallar(f"{ruta.name}: IDs repetidos en '{col_id}': {repetidos}")
    return tabla


def exigir_valores(serie: pd.Series, validos: set[str], nombre: str) -> None:
    inesperados = sorted(set(serie) - validos)
    if inesperados:
        fallar(f"{nombre}: valores inesperados {inesperados}")


def aplicar_reclasificaciones(cribado: pd.DataFrame, ruta: Path) -> pd.DataFrame:
    """Aplica en memoria los cambios D -> E2 de config/. No toca el CSV del Drive."""
    cambios = yaml.safe_load(ruta.read_text(encoding="utf-8"))["reclasificaciones"]
    cribado = cribado.copy()
    for cambio in cambios:
        fila = cribado["id_revision"] == cambio["id_revision"]
        if fila.sum() != 1:
            fallar(f"Reclasificación: {cambio['id_revision']} no está en el cribado")
        actual = cribado.loc[fila, "decision"].iloc[0]
        if actual != cambio["de"]:
            fallar(
                f"Reclasificación {cambio['id_revision']}: se esperaba "
                f"'{cambio['de']}' y el cribado dice '{actual}'"
            )
        cribado.loc[fila, "decision"] = cambio["a"]
    return cribado


def cargar_params() -> dict:
    ruta = RAIZ_REPO / "config" / "params.yaml"
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def leer_declarado(ruta: Path) -> dict:
    if not ruta.is_file():
        fallar(f"No existe el archivo: {ruta}")
    declarado = json.loads(ruta.read_text(encoding="utf-8"))
    faltan = [c for c in CLAVES_DECLARADAS if c not in declarado]
    if faltan:
        fallar(f"{ruta.name}: faltan las claves {faltan}")
    return declarado


def leer_pdfs_no_corresponde(carpeta: Path) -> dict[str, Path]:
    """PDF de otro documento ya separados: {id_revision: ruta}."""
    if not carpeta.is_dir():
        fallar(f"No existe la carpeta: {carpeta}")
    pdfs: dict[str, Path] = {}
    for ruta in sorted(carpeta.glob("*.pdf")):
        id_revision = ruta.name.split("_", 1)[0]
        if not re.fullmatch(r"R\d{4}", id_revision):
            fallar(f"_no_corresponde: el nombre no empieza con un ID: {ruta.name}")
        if id_revision in pdfs:
            fallar(f"_no_corresponde: hay dos PDF para {id_revision}")
        pdfs[id_revision] = ruta
    return pdfs


def cargar_entradas(params: dict) -> dict:
    raiz = raiz_drive(params["drive_root_env"])
    rutas = {nombre: raiz / rel for nombre, rel in params["archivos"].items()}
    ruta_reclas = RAIZ_REPO / params["reclasificaciones"]
    cribado = leer_csv(rutas["cribado"], COLUMNAS["cribado"], "id_revision")
    exigir_valores(cribado["decision"], DECISIONES_CRIBADO, "cribado.decision")
    recuperacion = leer_csv(
        rutas["recuperacion"], COLUMNAS["recuperacion"], "id_revision"
    )
    exigir_valores(recuperacion["obtenido"], OBTENIDO_VALIDOS, "recuperacion.obtenido")
    elegibilidad = leer_csv(
        rutas["elegibilidad"], COLUMNAS["elegibilidad"], "id_revision"
    )
    exigir_valores(
        elegibilidad["decision"], DECISIONES_ELEGIBILIDAD, "elegibilidad.decision"
    )
    dudosos = leer_csv(rutas["dudosos"], COLUMNAS["dudosos"], "id")
    exigir_valores(dudosos["decision_luisfer"], DUDOSOS_VALIDOS, "dudosos.decision")
    extraccion = leer_csv(rutas["extraccion"], COLUMNAS["extraccion"], "id")
    pdfs = leer_pdfs_no_corresponde(raiz / params["carpeta_no_corresponde"])
    declarado = leer_declarado(rutas["prisma_counts"])
    hashes = {
        str(ruta.relative_to(raiz)): sha256(ruta)
        for ruta in [*rutas.values(), *pdfs.values()]
    } | {params["reclasificaciones"]: sha256(ruta_reclas)}
    return {
        "cribado": aplicar_reclasificaciones(cribado, ruta_reclas),
        "recuperacion": recuperacion,
        "elegibilidad": elegibilidad,
        "dudosos": dudosos,
        "extraccion": extraccion,
        "pdfs_no_corresponde": set(pdfs),
        "declarado": declarado,
        "hashes": hashes,
    }


# --- Validación cruzada de IDs -------------------------------------------------


def validar_ids(entradas: dict) -> None:
    cribado = entradas["cribado"]
    recuperacion = entradas["recuperacion"]
    elegibilidad = entradas["elegibilidad"]
    dudosos = entradas["dudosos"]
    buscados = set(cribado.loc[cribado["decision"].isin(["I", "D"]), "id_revision"])
    ids_recuperacion = set(recuperacion["id_revision"])
    if buscados != ids_recuperacion:
        fallar(
            "Recuperación y cribado no tienen los mismos IDs buscados. "
            f"Solo en cribado: {sorted(buscados - ids_recuperacion)}. "
            f"Solo en recuperación: {sorted(ids_recuperacion - buscados)}"
        )
    ids_elegibilidad = set(elegibilidad["id_revision"])
    if not ids_elegibilidad <= ids_recuperacion:
        fallar(
            "Elegibilidad tiene IDs que no están en recuperación: "
            f"{sorted(ids_elegibilidad - ids_recuperacion)}"
        )
    incluidos = set(
        elegibilidad.loc[elegibilidad["decision"] == "INCLUIDO", "id_revision"]
    )
    ids_extraccion = set(entradas["extraccion"]["id"])
    if ids_extraccion != incluidos:
        fallar(
            "Extracción e INCLUIDOS de elegibilidad no tienen los mismos IDs. "
            f"Solo en extracción: {sorted(ids_extraccion - incluidos)}. "
            f"Solo en elegibilidad: {sorted(incluidos - ids_extraccion)}"
        )
    if not set(dudosos["id"]) <= incluidos:
        fallar(
            "Dudosos que no están INCLUIDOS en elegibilidad: "
            f"{sorted(set(dudosos['id']) - incluidos)}"
        )


# --- Cálculo de conteos --------------------------------------------------------


def contar_cribado(cribado: pd.DataFrame) -> dict:
    decision = cribado["decision"]
    motivos = {c: int((decision == c).sum()) for c in CODIGOS_EXCLUSION}
    return {
        "cribados": len(cribado),
        "excluidos_cribado": sum(motivos.values()),
        "excluidos_cribado_motivos": motivos,
        "buscados_texto_completo": int(decision.isin(["I", "D"]).sum()),
    }


def desglosar_no_recuperados(
    recuperacion: pd.DataFrame, elegibilidad: pd.DataFrame
) -> tuple[dict, dict]:
    """Devuelve (desglose, ids) según la definición D4 de docs/decisiones.md."""
    con_fila = recuperacion["id_revision"].isin(elegibilidad["id_revision"])
    obtenido = recuperacion["obtenido"]
    contradictorios = recuperacion.loc[con_fila & (obtenido != "sí"), "id_revision"]
    if len(contradictorios):
        fallar(
            "Tienen fila en elegibilidad pero recuperación dice que no se obtuvo: "
            f"{sorted(contradictorios)}"
        )
    ids_con_pdf = recuperacion.loc[~con_fila & (obtenido == "sí"), "id_revision"]
    sin_fila_con_pdf = sorted(ids_con_pdf)
    decision = elegibilidad["decision"]
    desglose = {
        "sin_acceso": int(obtenido.isin(["no", "duplicado"]).sum()),
        "pdf_otro_documento": int((decision == "NO_CORRESPONDE").sum())
        + len(sin_fila_con_pdf),
        "incompletos_ilegibles": int((decision == "NO_RECUPERADO").sum()),
    }
    ids = {
        "sin_fila_con_pdf": sin_fila_con_pdf,
        "duplicado": sorted(recuperacion.loc[obtenido == "duplicado", "id_revision"]),
    }
    return desglose, ids


def dudosos_e4(dudosos: pd.DataFrame) -> pd.DataFrame:
    """Dudosos que se excluyen por E4 (ok = acepto la sugerencia; ver D5)."""
    es_e4 = dudosos["sugerencia_automatica"].str.startswith(PREFIJO_E4_DUDOSOS)
    ambiguos = dudosos.loc[~es_e4 & (dudosos["decision_luisfer"] == "excluir"), "id"]
    if len(ambiguos):
        fallar(f"Dudosos con 'excluir' sin sugerencia E4: {sorted(ambiguos)}")
    return dudosos[es_e4]


def contar_elegibilidad(elegibilidad: pd.DataFrame, dudosos: pd.DataFrame) -> dict:
    decision = elegibilidad["decision"]
    excluidos = elegibilidad[decision == "EXCLUIDO"]
    exigir_valores(excluidos["codigo"], set(CODIGOS_EXCLUSION), "elegibilidad.codigo")
    motivos = {c: int((excluidos["codigo"] == c).sum()) for c in CODIGOS_EXCLUSION}
    e4_dudosos = dudosos_e4(dudosos)
    motivos["E4"] += len(e4_dudosos)
    return {
        "evaluados": int(decision.isin(["INCLUIDO", "EXCLUIDO"]).sum()),
        "excluidos_texto_completo": sum(motivos.values()),
        "excluidos_texto_completo_motivos": motivos,
        "incluidos_informes": int((decision == "INCLUIDO").sum()) - len(e4_dudosos),
    }


def verificar_pdfs_otro_documento(
    elegibilidad: pd.DataFrame, ids_sin_fila: list[str], pdfs: set[str]
) -> list[str]:
    """D11: todo 'PDF de otro documento' es NO_CORRESPONDE o tiene su PDF separado.

    Devuelve los PDF de la carpeta que no se cuentan como tales (observación).
    """
    no_corresponde = set(
        elegibilidad.loc[elegibilidad["decision"] == "NO_CORRESPONDE", "id_revision"]
    )
    contados = no_corresponde | set(ids_sin_fila)
    sin_respaldo = sorted(contados - no_corresponde - pdfs)
    if sin_respaldo:
        fallar(
            "Contados como 'PDF de otro documento' sin NO_CORRESPONDE ni PDF en "
            f"_no_corresponde/: {sin_respaldo}"
        )
    return sorted(pdfs - contados)


def contar_estudios(extraccion: pd.DataFrame, ids_excluidos: set[str]) -> dict:
    """Agrupa los informes incluidos que comparten estudio (estudio_compartido_con)."""
    informes = extraccion[~extraccion["id"].isin(ids_excluidos)]
    ids = set(informes["id"])
    grupos = {i: {i} for i in ids}
    for id_, otro in zip(
        informes["id"], informes["estudio_compartido_con"].str.strip(), strict=True
    ):
        if not otro:
            continue
        if otro not in ids:
            fallar(f"{id_}: estudio_compartido_con '{otro}' no es un informe incluido")
        union = grupos[id_] | grupos[otro]
        for miembro in union:
            grupos[miembro] = union
    estudios = {frozenset(g) for g in grupos.values()}
    return {
        "informes": len(ids),
        "incluidos_estudios": len(estudios),
        "pares": sorted(sorted(g) for g in estudios if len(g) > 1),
    }


def contrastar_decision_cribado(
    cribado: pd.DataFrame, recuperacion: pd.DataFrame
) -> dict:
    """Observación (no falla): I/D de recuperación frente a I/D del cribado."""
    unidas = recuperacion.merge(
        cribado[["id_revision", "decision"]], on="id_revision", how="left"
    )
    distintas = unidas[unidas["decision_cribado"] != unidas["decision"]]
    pares = zip(
        distintas["decision"], distintas["decision_cribado"], strict=True
    )
    return dict(Counter(f"{a}->{b}" for a, b in pares))


def calcular(params: dict | None = None) -> dict:
    """Recalcula todo y devuelve conteos, comparación, cascada y trazabilidad."""
    entradas = cargar_entradas(params or cargar_params())
    validar_ids(entradas)
    calculado = contar_cribado(entradas["cribado"])
    calculado |= contar_elegibilidad(entradas["elegibilidad"], entradas["dudosos"])
    desglose, ids = desglosar_no_recuperados(
        entradas["recuperacion"], entradas["elegibilidad"]
    )
    calculado["no_recuperados"] = sum(desglose.values())
    pdfs_sin_contar = verificar_pdfs_otro_documento(
        entradas["elegibilidad"],
        ids["sin_fila_con_pdf"],
        entradas["pdfs_no_corresponde"],
    )
    ids_e4 = set(dudosos_e4(entradas["dudosos"])["id"])
    estudios = contar_estudios(entradas["extraccion"], ids_e4)
    calculado["incluidos_estudios"] = estudios["incluidos_estudios"]
    calculado["informes_extraccion"] = estudios["informes"]
    declarado = entradas["declarado"]
    return {
        "calculado": calculado,
        "declarado": declarado,
        "desglose_no_recuperados": desglose,
        "ids": ids,
        "pares_estudio": estudios["pares"],
        "filas": filas_comparacion(calculado, declarado),
        "cascada": cascada(calculado, declarado),
        "observaciones": {
            "cribado_vs_recuperacion_I_D": contrastar_decision_cribado(
                entradas["cribado"], entradas["recuperacion"]
            ),
            "pdf_en_no_corresponde_sin_contar": pdfs_sin_contar,
        },
        "hashes": entradas["hashes"],
    }


# --- Comparación ---------------------------------------------------------------


def filas_comparacion(calculado: dict, declarado: dict) -> list[tuple]:
    """Filas (nombre, calculado, declarado) de cada conteo del JSON."""
    filas = [(c, calculado[c], declarado[c]) for c in CLAVES_ESCALARES]
    for clave in CLAVES_MOTIVOS:
        codigos = sorted(set(calculado[clave]) | set(declarado[clave]))
        filas += [
            (f"{clave}.{c}", calculado[clave].get(c), declarado[clave].get(c))
            for c in codigos
        ]
    return filas


def cascada(calculado: dict, declarado: dict) -> list[tuple]:
    """Filas (regla, esperado, obtenido): cada etapa debe sumar con la siguiente."""
    c, d = calculado, declarado
    return [
        ("identificados - duplicados = cribados",
         d["identificados"] - d["duplicados"], c["cribados"]),
        ("cribados - excluidos cribado = buscados",
         c["cribados"] - c["excluidos_cribado"], c["buscados_texto_completo"]),
        ("buscados - no recuperados = evaluados",
         c["buscados_texto_completo"] - c["no_recuperados"], c["evaluados"]),
        ("evaluados - excluidos texto completo = incluidos (informes)",
         c["evaluados"] - c["excluidos_texto_completo"], c["incluidos_informes"]),
        ("suma motivos cribado = excluidos cribado",
         sum(c["excluidos_cribado_motivos"].values()), c["excluidos_cribado"]),
        ("suma motivos texto completo = excluidos texto completo",
         sum(c["excluidos_texto_completo_motivos"].values()),
         c["excluidos_texto_completo"]),
        ("informes en extracción (sin E4) = incluidos (informes)",
         c["informes_extraccion"], c["incluidos_informes"]),
        ("incluidos (estudios) <= incluidos (informes)",
         True, c["incluidos_estudios"] <= c["incluidos_informes"]),
    ]


def hay_diferencias(resultado: dict) -> bool:
    return any(a != b for _, a, b in resultado["filas"]) or any(
        a != b for _, a, b in resultado["cascada"]
    )


# --- Reporte -------------------------------------------------------------------


def reporte(resultado: dict) -> list[str]:
    def marca(a: object, b: object) -> str:
        return "ok" if a == b else "DIFERENCIA"

    lineas = ["== Entradas (ruta relativa, sha256) =="]
    lineas += [f"  {ruta}  {h}" for ruta, h in resultado["hashes"].items()]
    lineas += ["", "== Calculado desde CSV vs prisma_counts JSON =="]
    lineas += [
        f"  {nombre:<48} {calc!s:>5} {decl!s:>5}  {marca(calc, decl)}"
        for nombre, calc, decl in resultado["filas"]
    ]
    d = resultado["declarado"]
    lineas += [
        "",
        "== Declarados en el JSON, NO verificados por script ==",
        f"  identificados={d['identificados']}  duplicados={d['duplicados']}",
        "",
        "== Estudios: informes que comparten estudio ==",
        f"  {resultado['calculado']['informes_extraccion']} informes -> "
        f"{resultado['calculado']['incluidos_estudios']} estudios; "
        f"{len(resultado['pares_estudio'])} pares: "
        f"{'; '.join(' + '.join(par) for par in resultado['pares_estudio'])}",
        "",
        "== Desglose de los no recuperados ==",
    ]
    lineas += [f"  {k}: {v}" for k, v in resultado["desglose_no_recuperados"].items()]
    lineas += [
        f"  total: {resultado['calculado']['no_recuperados']}",
        "  IDs con PDF (obtenido=sí) sin fila en elegibilidad "
        f"({len(resultado['ids']['sin_fila_con_pdf'])}): "
        f"{', '.join(resultado['ids']['sin_fila_con_pdf'])}",
        "  ID(s) duplicado(s) detectado(s) tarde: "
        f"{', '.join(resultado['ids']['duplicado'])}",
        "",
        "== Cascada: cada etapa suma con la siguiente ==",
    ]
    lineas += [
        f"  {regla:<60} {esp!s:>5} {obt!s:>5}  {marca(esp, obt)}"
        for regla, esp, obt in resultado["cascada"]
    ]
    lineas += ["", "== Observaciones (no cambian ningún conteo) =="]
    for nombre, valor in resultado["observaciones"].items():
        lineas.append(f"  {nombre}: {valor or 'sin diferencias'}")
    lineas += ["", f"RESULTADO: {'FALLA' if hay_diferencias(resultado) else 'OK'}"]
    return lineas


def main() -> int:
    try:
        resultado = calcular()
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("\n".join(reporte(resultado)))
    return 1 if hay_diferencias(resultado) else 0


if __name__ == "__main__":
    sys.exit(main())
