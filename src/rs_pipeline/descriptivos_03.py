"""Descriptivos de la matriz normalizada (Paso C).

Lee la matriz de data/processed/ (la que escribió normalizar_01), comprueba que no
cambió desde que se normalizó y escribe tablas de frecuencias en outputs/tablas/, cada
una con su .json de trazabilidad. Base: 201 informes. Las tablas de atributos que son
del estudio (disciplina, herramientas) muestran además la base de 198 estudios.
Falla (código 1) si falta un archivo o una columna, si la matriz cambió, si un año no
se puede leer o si los informes de un mismo estudio no coinciden en un atributo
contado por estudio.
"""

from __future__ import annotations

import json
import sys
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from rs_pipeline import normalizar_01, prisma_02
from rs_pipeline.prisma_02 import ErrorPipeline, fallar

RAIZ_REPO = prisma_02.RAIZ_REPO
BASE_INFORMES = "201 informes"
BASE_ESTUDIOS = "198 estudios"
COLUMNAS_MATRIZ = [
    "id",
    "cita_apa",
    "idioma",
    "estudio_compartido_con",
    "pais_norm",
    "nivel",
    "nivel_norm",
    "nivel_en_revision",
    "contexto",
    "alertas",
    "disciplina_norm",
    "mmat_categoria_norm",
    "pre_post_un_grupo",
    "oe1_direccion_norm",
]


# --- Entradas ------------------------------------------------------------------


def cargar_matriz(params: dict) -> dict:
    """Lee la matriz normalizada y comprueba que su hash sigue siendo el registrado."""
    ruta = RAIZ_REPO / params["salidas"]["procesados"] / normalizar_01.nombre_matriz(
        params
    )
    ruta_json = ruta.with_suffix(".json")
    for archivo in (ruta, ruta_json):
        if not archivo.is_file():
            fallar(f"Falta {archivo}: ejecuta primero normalizar_01")
    registro = json.loads(ruta_json.read_text(encoding="utf-8"))
    hash_actual = prisma_02.sha256(ruta)
    if hash_actual != registro["salida"]["sha256"]:
        fallar("La matriz cambió desde que se normalizó: vuelve a correr normalizar_01")
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8")
    categorias = normalizar_01.cargar_categorias(RAIZ_REPO / params["categorias"])
    columnas_0_1 = [
        *categorias["oe2_tipo_herramienta"]["columnas"].values(),
        *categorias["oe1_resultado_tipo"]["columnas"].values(),
    ]
    faltan = [c for c in [*COLUMNAS_MATRIZ, *columnas_0_1] if c not in tabla.columns]
    if faltan:
        fallar(f"La matriz normalizada no tiene las columnas {faltan}")
    return {
        "tabla": tabla,
        "ruta": ruta,
        "sha256": hash_actual,
        "registro": registro,
        "herramientas": categorias["oe2_tipo_herramienta"]["columnas"],
        "resultados": categorias["oe1_resultado_tipo"]["columnas"],
        "categorias_en_revision": categorias["nivel"]["revision_elegibilidad"][
            "categorias"
        ],
        "ids_adicionales": categorias["nivel"]["revision_elegibilidad"][
            "ids_adicionales"
        ],
        "exclusiones": {
            fila["id"]: f"excluir {fila['codigo']}"
            for fila in prisma_02.cargar_exclusiones_nivel(
                RAIZ_REPO / params["exclusiones_nivel"]
            )
        },
    }


def asignar_estudios(tabla: pd.DataFrame, esperados: int) -> pd.Series:
    """Id de estudio por informe: el menor id del par que comparte estudio."""
    socio = tabla["estudio_compartido_con"].str.strip()
    por_id = dict(zip(tabla["id"], socio, strict=True))
    for id_informe, otro in por_id.items():
        if otro and por_id.get(otro) != id_informe:
            fallar(f"{id_informe}: estudio_compartido_con '{otro}' no es recíproco")
    estudios = pd.Series(
        [min(i, o) if o else i for i, o in zip(tabla["id"], socio, strict=True)],
        index=tabla.index,
    )
    if estudios.nunique() != esperados:
        fallar(f"Hay {estudios.nunique()} estudios y prisma_counts declara {esperados}")
    return estudios


def exigir_atributo_de_estudio(
    tabla: pd.DataFrame, estudios: pd.Series, columnas: list[str]
) -> None:
    """Los informes de un mismo estudio deben coincidir en lo contado por estudio."""
    for columna in columnas:
        distintos = tabla.groupby(estudios)[columna].nunique()
        if (distintos > 1).any():
            fallar(
                f"Los informes de {sorted(distintos[distintos > 1].index)} no "
                f"coinciden en '{columna}': no se puede contar por estudio"
            )


def anios_de_la_cita(tabla: pd.DataFrame) -> pd.Series:
    """Año de la referencia APA (primer '(AAAA)' de cita_apa)."""
    extraido = tabla["cita_apa"].str.extract(r"\((\d{4})[a-z]?\)")[0]
    if extraido.isna().any():
        fallar(f"cita_apa sin año en: {sorted(tabla.loc[extraido.isna(), 'id'])}")
    return extraido.astype(int)


def anios_de_la_base_de_datos(
    tabla: pd.DataFrame, ruta_elegibilidad: Path, ventana: list[int]
) -> pd.Series:
    """Año del registro buscado (elegibilidad). Debe caer en la ventana de búsqueda."""
    elegibilidad = prisma_02.leer_csv(
        ruta_elegibilidad, ["id_revision", "anio"], "id_revision"
    ).set_index("id_revision")["anio"]
    faltan = sorted(set(tabla["id"]) - set(elegibilidad.index))
    if faltan:
        fallar(f"Informes sin fila en elegibilidad: {faltan}")
    anios = tabla["id"].map(elegibilidad)
    malos = sorted(tabla.loc[~anios.str.fullmatch(r"\d{4}"), "id"])
    if malos:
        fallar(f"Año de la base de datos ilegible en: {malos}")
    anios = anios.astype(int)
    fuera = sorted(tabla.loc[(anios < ventana[0]) | (anios > ventana[1]), "id"])
    if fuera:
        fallar(f"Informes fuera de la ventana {ventana[0]}-{ventana[1]}: {fuera}")
    return anios


def discrepancias_de_anio(
    tabla: pd.DataFrame, anios_base: pd.Series, anios_apa: pd.Series
) -> list[dict]:
    """Informes cuyo año APA difiere del año de la base de datos."""
    return [
        {"id": i, "anio_base_de_datos": int(b), "anio_cita_apa": int(a)}
        for i, b, a in zip(tabla["id"], anios_base, anios_apa, strict=True)
        if a != b
    ]


# --- Tablas ----------------------------------------------------------------------


def porcentaje(n: int, base: int) -> float:
    return round(100 * n / base, 1)


def tabla_unica(
    serie: pd.Series, etiqueta: str, estudios: pd.Series | None = None, por: str = "n"
) -> pd.DataFrame:
    """Frecuencias de una categoría única. Con `estudios` agrega la base de estudios."""
    conteo = serie.value_counts().rename_axis(etiqueta).reset_index(name="n_informes")
    if por == "n":
        conteo = conteo.sort_values(["n_informes", etiqueta], ascending=[False, True])
    else:
        conteo = conteo.sort_values(etiqueta)
    conteo["pct_informes"] = [porcentaje(n, len(serie)) for n in conteo["n_informes"]]
    if estudios is not None:
        por_estudio = serie.groupby(estudios).first().value_counts()
        conteo["n_estudios"] = conteo[etiqueta].map(por_estudio).fillna(0).astype(int)
        conteo["pct_estudios"] = [
            porcentaje(n, estudios.nunique()) for n in conteo["n_estudios"]
        ]
    return conteo.reset_index(drop=True)


def tabla_multietiqueta(
    tabla: pd.DataFrame,
    columnas: dict[str, str],
    etiqueta: str,
    estudios: pd.Series | None = None,
) -> pd.DataFrame:
    """Una fila por etiqueta 0/1. Un informe puede estar en varias filas."""
    filas = []
    for rotulo, columna in columnas.items():
        marca = tabla[columna] == "1"
        fila = {
            etiqueta: rotulo,
            "n_informes": int(marca.sum()),
            "pct_informes": porcentaje(int(marca.sum()), len(tabla)),
        }
        if estudios is not None:
            n_estudios = int(estudios[marca].nunique())
            fila |= {
                "n_estudios": n_estudios,
                "pct_estudios": porcentaje(n_estudios, estudios.nunique()),
            }
        filas.append(fila)
    return pd.DataFrame(filas)


def tabla_cruce(
    tabla: pd.DataFrame, columnas: dict[str, str], estudios: pd.Series
) -> pd.DataFrame:
    """Disciplina x herramienta. El % es sobre la base de cada disciplina."""
    filas = []
    for disciplina in sorted(tabla["disciplina_norm"].unique()):
        de_la_disciplina = tabla["disciplina_norm"] == disciplina
        base_i = int(de_la_disciplina.sum())
        base_e = int(estudios[de_la_disciplina].nunique())
        for rotulo, columna in columnas.items():
            marca = de_la_disciplina & (tabla[columna] == "1")
            n_i, n_e = int(marca.sum()), int(estudios[marca].nunique())
            filas.append(
                {
                    "disciplina": disciplina,
                    "herramienta": rotulo,
                    "n_informes": n_i,
                    "pct_fila_informes": porcentaje(n_i, base_i),
                    "n_estudios": n_e,
                    "pct_fila_estudios": porcentaje(n_e, base_e),
                    "base_disciplina_informes": base_i,
                    "base_disciplina_estudios": base_e,
                }
            )
    return pd.DataFrame(filas)


def quinquenio(anio: int) -> str:
    inicio = anio // 5 * 5
    return f"{inicio}–{inicio + 4}"


def elemento(
    nombre: str, descripcion: str, tipo: str, base: str, tabla: pd.DataFrame
) -> dict:
    return {
        "nombre": nombre,
        "descripcion": descripcion,
        "tipo": tipo,
        "base": base,
        "tabla": tabla,
    }


def construir_tablas(datos: dict, estudios: pd.Series, anios: pd.Series) -> list[dict]:
    """Una entrada por tabla: nombre, descripción, tipo, base y el DataFrame."""
    t = datos["tabla"]
    ambas = f"{BASE_INFORMES} (n_informes) y {BASE_ESTUDIOS} (n_estudios)"
    mmat = tabla_unica(t["mmat_categoria_norm"], "categoria", por="etiqueta")
    con_pre_post = t["pre_post_un_grupo"] == "1"
    por_categoria = t.loc[con_pre_post, "mmat_categoria_norm"].value_counts()
    mmat["n_pre_post_un_grupo"] = mmat["categoria"].map(por_categoria).fillna(0)
    mmat["n_pre_post_un_grupo"] = mmat["n_pre_post_un_grupo"].astype(int)
    return [
        elemento(
            "anio", "Informes por año de la base de datos (registro buscado)",
            "única", BASE_INFORMES, tabla_unica(anios, "anio", por="etiqueta"),
        ),
        elemento(
            "anio_quinquenio",
            "Informes por quinquenio calendario del año de la base de datos",
            "única", BASE_INFORMES,
            tabla_unica(anios.map(quinquenio), "quinquenio", por="etiqueta"),
        ),
        elemento(
            "idioma", "Informes por idioma del informe",
            "única", BASE_INFORMES, tabla_unica(t["idioma"], "idioma"),
        ),
        elemento(
            "pais", "País donde se hizo el estudio (pais_norm)",
            "única", ambas, tabla_unica(t["pais_norm"], "pais", estudios),
        ),
        elemento(
            "nivel", "Nivel educativo según el texto del informe (nivel_norm)",
            "única", ambas, tabla_unica(t["nivel_norm"], "nivel", estudios),
        ),
        elemento(
            "disciplina", "Disciplina normalizada (disciplina_norm)",
            "única", ambas, tabla_unica(t["disciplina_norm"], "disciplina", estudios),
        ),
        elemento(
            "mmat_categoria",
            "Categoría MMAT normalizada y cuántos informes son pre-post de un grupo",
            "única", BASE_INFORMES, mmat,
        ),
        elemento(
            "oe1_direccion", "Dirección del efecto normalizada",
            "única", BASE_INFORMES, tabla_unica(t["oe1_direccion_norm"], "direccion"),
        ),
        elemento(
            "herramientas", "Tipo de herramienta (multi-etiqueta)",
            "multi-etiqueta", ambas,
            tabla_multietiqueta(t, datos["herramientas"], "herramienta", estudios),
        ),
        elemento(
            "resultados", "Tipo de resultado (multi-etiqueta)",
            "multi-etiqueta", BASE_INFORMES,
            tabla_multietiqueta(t, datos["resultados"], "resultado"),
        ),
        elemento(
            "disciplina_x_herramienta",
            "Cruce disciplina x herramienta (% sobre la base de cada disciplina)",
            "cruce multi-etiqueta", ambas,
            tabla_cruce(t, datos["herramientas"], estudios),
        ),
    ]


# --- Salida ----------------------------------------------------------------------


def escribir_tablas(
    tablas: list[dict], datos: dict, extra: dict, carpeta: Path
) -> list[Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    escritas = []
    for elemento in tablas:
        ruta = carpeta / f"{elemento['nombre']}.csv"
        elemento["tabla"].to_csv(
            ruta, index=False, encoding="utf-8", lineterminator="\n"
        )
        suma = int(elemento["tabla"]["n_informes"].sum())
        traza = {
            "tabla": elemento["nombre"],
            "descripcion": elemento["descripcion"],
            "tipo": elemento["tipo"],
            "base": elemento["base"],
            "suma_n_informes": suma,
            "suma_n_informes_debe_ser_201": elemento["tipo"] == "única",
            "entrada": {
                "matriz_normalizada": str(datos["ruta"].relative_to(RAIZ_REPO)),
                "sha256": datos["sha256"],
                "entradas_de_la_matriz": datos["registro"]["entradas_sha256"],
            },
            "versiones": {
                "pandas": version("pandas"),
                "python": sys.version.split()[0],
            },
            "salida": {"archivo": ruta.name, "sha256": prisma_02.sha256(ruta)},
        } | extra.get(elemento["nombre"], {})
        ruta.with_suffix(".json").write_text(
            json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        escritas.append(ruta)
    return escritas


def tabla_revision_nivel(datos: dict) -> pd.DataFrame:
    """Informes cuyo nivel revisa Luis Fer. No cambia el PRISMA ni excluye nada."""
    t = datos["tabla"]
    revision = t[t["nivel_en_revision"] == "1"].copy()
    orden = [*datos["categorias_en_revision"], "primer año universitario", "mixto"]
    revision["_orden"] = revision["nivel_norm"].map(orden.index)
    revision = revision.sort_values(["_orden", "id"])
    sin_fila = sorted(set(datos["exclusiones"]) - set(revision["id"]))
    if sin_fila:
        fallar(f"Exclusiones de nivel que no están en la revisión: {sin_fila}")

    def fragmento(fila: pd.Series) -> str:
        partes = [("Contexto", fila["contexto"]), ("Alertas", fila["alertas"])]
        return " | ".join(f"{nombre}: {texto}" for nombre, texto in partes if texto)

    def motivo(fila: pd.Series) -> str:
        if fila["nivel_norm"] in datos["categorias_en_revision"]:
            return f"Categoría: {fila['nivel_norm']}"
        if fila["id"] in datos["ids_adicionales"]:
            return "Añadido por Luis Fer: nivel mixto con estudiantes de pregrado"
        return "Primer año con aviso: el texto lo contradice o lo infiere"

    motivos = revision.apply(motivo, axis=1)
    return pd.DataFrame(
        {
            "id": revision["id"],
            "cita_apa": revision["cita_apa"],
            "nivel_crudo": revision["nivel"],
            "nivel_norm": revision["nivel_norm"],
            "fragmento_justificativo": revision.apply(fragmento, axis=1),
            "motivo_revision": motivos,
            "decision_luisfer": [
                datos["exclusiones"].get(id_, "incluir") for id_ in revision["id"]
            ],
        }
    ).reset_index(drop=True)


def escribir_revision_nivel(
    revision: pd.DataFrame, datos: dict, params: dict, carpeta: Path
) -> Path:
    ruta = carpeta / "revision_elegibilidad_nivel.csv"
    revision.to_csv(ruta, index=False, encoding="utf-8", lineterminator="\n")
    traza = {
        "tabla": "revision_elegibilidad_nivel",
        "descripcion": (
            "Informes cuyo nivel (según el texto) toca la elegibilidad. "
            "decision_luisfer: decisiones de Luis Fer del 29 oct 2026 (D33). "
            "No cambia el PRISMA: las exclusiones las aplica prisma_02.py desde "
            "config/exclusiones_nivel.yaml."
        ),
        "filas": len(revision),
        "filas_por_nivel_norm": revision["nivel_norm"].value_counts().to_dict(),
        "fuente_del_fragmento": "campos contexto y alertas de la matriz de extracción",
        "regla_3_de_elegibilidad": params["regla_3_elegibilidad"],
        "entrada": {
            "matriz_normalizada": str(datos["ruta"].relative_to(RAIZ_REPO)),
            "sha256": datos["sha256"],
            "entradas_de_la_matriz": datos["registro"]["entradas_sha256"],
        },
        "salida": {"archivo": ruta.name, "sha256": prisma_02.sha256(ruta)},
    }
    ruta.with_suffix(".json").write_text(
        json.dumps(traza, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return ruta


def generar(params: dict, carpeta: Path) -> dict:
    raiz = prisma_02.raiz_drive(params["drive_root_env"])
    declarado = prisma_02.leer_declarado(raiz / params["archivos"]["prisma_counts"])
    datos = cargar_matriz(params)
    tabla = datos["tabla"]
    if len(tabla) != declarado["incluidos_informes"]:
        fallar(
            f"La matriz tiene {len(tabla)} informes y prisma_counts declara "
            f"{declarado['incluidos_informes']}"
        )
    estudios = asignar_estudios(tabla, declarado["incluidos_estudios"])
    exigir_atributo_de_estudio(
        tabla,
        estudios,
        ["disciplina_norm", "pais_norm", "nivel_norm", *datos["herramientas"].values()],
    )
    anios = anios_de_la_base_de_datos(
        tabla, raiz / params["archivos"]["elegibilidad"], params["ventana_busqueda"]
    )
    discrepancias = discrepancias_de_anio(tabla, anios, anios_de_la_cita(tabla))
    nota_anio = {
        "fuente_del_anio": "año de la base de datos (registro buscado, elegibilidad)",
        "ventana_de_busqueda": params["ventana_busqueda"],
        "informes_con_cita_apa_de_otro_anio": discrepancias,
        "nota": (
            "el año APA queda en cita_apa; probable publicación en línea "
            "anterior a la impresa (D24)"
        ),
    }
    tablas = construir_tablas(datos, estudios, anios)
    rutas = escribir_tablas(
        tablas, datos, {"anio": nota_anio, "anio_quinquenio": nota_anio}, carpeta
    )
    revision = tabla_revision_nivel(datos)
    ruta_revision = escribir_revision_nivel(revision, datos, params, carpeta)
    return {
        "tablas": tablas,
        "rutas": rutas,
        "discrepancias_anio": discrepancias,
        "revision": revision,
        "ruta_revision": ruta_revision,
    }


def reporte(resultado: dict) -> list[str]:
    lineas = ["== Tablas escritas =="]
    for elemento, ruta in zip(resultado["tablas"], resultado["rutas"], strict=True):
        suma = int(elemento["tabla"]["n_informes"].sum())
        detalle = f"suma {suma}" if elemento["tipo"] == "única" else elemento["tipo"]
        lineas.append(f"  {ruta.name:<32} {detalle:<22} base: {elemento['base']}")
    lineas += [
        "",
        f"{resultado['ruta_revision'].name}: {len(resultado['revision'])} informes "
        "para revisión de elegibilidad (sin cambios en PRISMA)",
        "",
        "== Año de la base de datos distinto al año APA (se usa el primero) ==",
    ]
    lineas += [
        f"  {d['id']}: base de datos {d['anio_base_de_datos']} / "
        f"cita_apa {d['anio_cita_apa']}"
        for d in resultado["discrepancias_anio"]
    ]
    return lineas


def main() -> int:
    try:
        params = prisma_02.cargar_params()
        resultado = generar(params, RAIZ_REPO / params["salidas"]["tablas"])
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("\n".join(reporte(resultado)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
