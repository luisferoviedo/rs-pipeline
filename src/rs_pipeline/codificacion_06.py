"""Libro de códigos v0 y piloto de codificación deductiva (Bloque 7; D44).

Arma el libro de códigos (config/libro_codigos_v0.yaml y docs/libro_codigos_v0.md) a
partir de config/criterios_v0.yaml, elige con semilla fija el piloto (5 informes) y la
muestra de confiabilidad (40), escribe la hoja de codificación del piloto con los 19
campos de la ficha y estima el costo de codificar los 196 informes. No llama a la API.
Falla (código 1) si falta un archivo o una columna, o si un conteo no cuadra.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import yaml

from rs_pipeline import criterios_05 as K
from rs_pipeline import semantico_04 as S
from rs_pipeline import semantico_texto as T
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ_REPO = S.RAIZ_REPO
CRITERIOS = [f"C0{n}" for n in range(1, 10)]
ESCALA = {
    0: "No aparece, o la ficha dice explícitamente que no se reporta.",
    1: "Descrito: el laboratorio o la actividad lo tenía, pero el estudio no "
    "reporta su efecto.",
    2: "Con resultado: el estudio lo vincula a un resultado (mejoró algo, o su "
    "ausencia causó problemas).",
}
REGLAS = [
    "Codificar solo lo que dice la ficha; no completar con conocimiento propio.",
    "Ante duda entre dos códigos, el menor.",
    "Un informe recibe un código por criterio (C01 a C09), siempre los nueve.",
    "El código 2 exige un vínculo con un resultado dicho en la ficha; que el "
    "estudio tenga resultados en general no basta.",
    "Los criterios C01 y C09 siguen en borrador: se codifican igual y se marcan "
    "en la nota si el enunciado no alcanza para decidir.",
]
# Reglas nuevas del piloto (v1, D45).
REGLAS_V1 = [
    *REGLAS,
    "«2» exige que los autores atribuyan el resultado, aunque sea en parte, a ESE "
    "componente. Que la intervención en conjunto funcione no basta: un paquete "
    "cuenta como 1 para los componentes a los que no se atribuye el resultado.",
    "Un dato descriptivo de contexto o de barrera (p. ej., el porcentaje de "
    "estudiantes sin internet en casa) es 1. Solo es 2 si el estudio dice que "
    "influyó en la actividad o en el aprendizaje.",
    "«1» exige que la ficha mencione el componente. Si no lo menciona, o dice que "
    "no se documenta, es 0, aunque se pueda suponer que existía.",
]
# Ejemplos inventados de las reglas nuevas (no son texto de artículos).
EJEMPLOS_REGLAS_V1 = [
    "Regla a. Ejemplo: «El grupo con simulación, guía y trabajo en parejas mejoró "
    "frente al control; los autores no atribuyen la mejora a ninguna parte» → "
    "retroalimentación, guía e interactividad = 1, no 2.",
    "Regla b. Ejemplo: «El 30 % de los estudiantes no tenía internet en casa» → 1; "
    "«quienes no tenían internet no pudieron terminar la práctica» → 2.",
    "Regla c. Ejemplo: «Costo y licencia: no se documenta» → 0, aunque la "
    "herramienta fuera gratuita en la práctica.",
]
# Ejemplos inventados (no son texto de artículos) para tres criterios.
EJEMPLOS = {
    "C02": {
        0: "Ejemplo: «Se usó el simulador en una clase; no reporta guía ni "
        "estructura de las actividades.»",
        1: "Ejemplo: «Cada práctica tenía una guía con objetivo, pasos numerados y "
        "preguntas finales; no se analiza su efecto.»",
        2: "Ejemplo: «El grupo con guía estructurada terminó más prácticas y "
        "mejoró en el postest; el grupo sin guía se perdió en la exploración.»",
    },
    "C04": {
        0: "Ejemplo: «Retroalimentación de la herramienta: no reporta.»",
        1: "Ejemplo: «El docente comentaba las respuestas al cierre de la sesión; "
        "el estudio no evalúa ese comentario.»",
        2: "Ejemplo: «Los estudiantes que recibieron corrección inmediata de la "
        "simulación corrigieron más errores en la segunda práctica.»",
    },
    "C09": {
        0: "Ejemplo: «Idioma, costo y conectividad: no reporta.»",
        1: "Ejemplo: «La simulación se descargó para usarla sin conexión en el "
        "aula; no se informa si cambió la participación.»",
        2: "Ejemplo: «Cuatro estudiantes sin internet en casa no pudieron repetir "
        "la práctica y quedaron fuera del análisis.»",
    },
}


# --- Libro de códigos ----------------------------------------------------------------


def cargar_marco() -> tuple[dict, str]:
    ruta = RAIZ_REPO / "config" / "criterios_v0.yaml"
    marco = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if [c["id"] for c in marco["criterios"]] != CRITERIOS:
        fallar("config/criterios_v0.yaml no trae C01 a C09 en orden")
    return marco, S.sha256(ruta)


def construir_libro(cfg: dict, version: str = "v0") -> dict:
    marco, sha = cargar_marco()
    criterios = []
    for c in marco["criterios"]:
        entrada = {k: c[k] for k in ("id", "dimension", "criterio_corto", "enunciado")}
        entrada["estado"] = c["estado"]
        if c["id"] in EJEMPLOS:
            entrada["ejemplos"] = {k: v for k, v in EJEMPLOS[c["id"]].items()}
        criterios.append(entrada)
    v1 = version == "v1"
    libro = {
        "version": version,
        "decision": "D45" if v1 else "D44",
        "fuente_criterios": {"archivo": "config/criterios_v0.yaml", "sha256": sha},
        "escala": ESCALA,
        "reglas": REGLAS_V1 if v1 else REGLAS,
        "campos_ficha": cfg["campos_ficha"],
        "campos_excluidos": {
            "oe2_criterios_candidatos": "inferencias del extractor (sesgan el código)",
            "lf_*": "notas de Luis Fer",
        },
        "criterios": criterios,
    }
    if v1:
        libro["ejemplos_de_reglas"] = EJEMPLOS_REGLAS_V1
    return libro


def libro_a_markdown(libro: dict) -> str:
    lineas = [
        f"# Libro de códigos {libro['version']} ({libro['decision']})",
        "",
        "Codificación deductiva de cada informe frente a cada criterio del marco v0.",
        "",
        "## Escala (por informe y criterio)",
        "",
        *[f"- **{k}** = {v}" for k, v in libro["escala"].items()],
        "",
        "## Reglas",
        "",
        *[f"- {r}" for r in libro["reglas"]],
        "",
        "## Campos de la ficha que se leen (en este orden)",
        "",
        ", ".join(f"`{c}`" for c in libro["campos_ficha"]),
        "",
        "No se leen `oe2_criterios_candidatos` (inferencias del extractor) ni `lf_*` "
        "(notas de Luis Fer). Se quitan las marcas [F]/[I] y las citas de página.",
        "",
        "## Criterios",
    ]
    if "ejemplos_de_reglas" in libro:
        lineas += ["", "## Ejemplos de las reglas nuevas (inventados)", ""]
        lineas += [f"- {e}" for e in libro["ejemplos_de_reglas"]]
        lineas.append("")
    for c in libro["criterios"]:
        lineas += [
            "",
            f"### {c['id']} · {c['criterio_corto']}",
            "",
            f"- **Dimensión:** {c['dimension']}",
            f"- **Enunciado:** {c['enunciado']}",
            f"- **Estado:** {c['estado']}",
        ]
        for codigo, texto in c.get("ejemplos", {}).items():
            lineas.append(f"- **Código {codigo}.** {texto}")
    return "\n".join(lineas) + "\n"


def escribir_libro(cfg: dict, version: str = "v0") -> dict:
    libro = construir_libro(cfg, version)
    ruta_yaml = RAIZ_REPO / "config" / f"libro_codigos_{version}.yaml"
    with ruta_yaml.open("w", encoding="utf-8") as f:
        f.write(
            f"# Libro de códigos {version}. Texto de los criterios: criterios_v0.yaml\n"
        )
        yaml.safe_dump(libro, f, allow_unicode=True, sort_keys=False, width=100)
    ruta_md = RAIZ_REPO / "docs" / f"libro_codigos_{version}.md"
    ruta_md.write_text(libro_a_markdown(libro), encoding="utf-8")
    return {"yaml": S.sha256(ruta_yaml), "md": S.sha256(ruta_md)}


# --- Muestras ------------------------------------------------------------------------


def informes_con_peso(params: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Matriz de los 196 y su tabla de pesos (suma) por informe."""
    tabla = S.cargar_matriz(params)["tabla"]
    conteos = json.loads((RAIZ_REPO / params["prisma_counts_vigente"]).read_text())
    estudios = K.asignar_estudios(tabla, conteos["incluidos_estudios"])
    pesos = K.tabla_de_informes(tabla, estudios)
    idioma = tabla.set_index("id")["idioma"]
    pesos["idioma"] = pesos["id"].map(idioma)
    return tabla, pesos


def elegir_piloto(pesos: pd.DataFrame, cantidad: int, semilla: int) -> list[str]:
    """Sorteo con semilla: estudios distintos y 3+ pesos, disciplinas e idiomas."""
    azar = np.random.default_rng(semilla)
    for _ in range(20000):
        pos = azar.choice(len(pesos), size=cantidad, replace=False)
        s = pesos.iloc[pos]
        variado = (
            s["peso_suma"].nunique() >= 3
            and s["disciplina"].nunique() >= 3
            and s["idioma"].nunique() >= 3
            and s["estudio"].nunique() == cantidad
        )
        if variado:
            return sorted(s["id"])
    fallar("No se encontró un piloto variado en peso, disciplina e idioma")


def cuotas(tamanos: pd.Series, total: int) -> dict:
    """Reparto proporcional (restos mayores) con al menos 1 por estrato no vacío."""
    exacto = total * tamanos / tamanos.sum()
    cuota = np.maximum(np.floor(exacto).astype(int), 1)
    while cuota.sum() < total:
        cuota[(exacto - cuota).idxmax()] += 1
    while cuota.sum() > total:
        candidatos = cuota[cuota > 1]
        cuota[(candidatos - exacto[candidatos.index]).idxmax()] -= 1
    return cuota.to_dict()


def elegir_confiabilidad(
    pesos: pd.DataFrame, piloto: list[str], cantidad: int, semilla: int
) -> pd.DataFrame:
    """40 informes estratificados por peso y nivel; sin el piloto ni su estudio."""
    estudios_piloto = set(pesos[pesos["id"].isin(piloto)]["estudio"])
    pool = pesos[~pesos["estudio"].isin(estudios_piloto)].copy()
    pool["estrato"] = pool["peso_suma"] + " | " + pool["nivel"]
    cuota = cuotas(pool.groupby("estrato").size(), cantidad)
    azar = np.random.default_rng(semilla + 1)
    elegidos = []
    for estrato, n in sorted(cuota.items()):
        ids = sorted(pool[pool["estrato"] == estrato]["id"])
        elegidos += list(azar.choice(ids, size=n, replace=False))
    salida = pool[pool["id"].isin(elegidos)][["id", "estudio", "peso_suma", "nivel"]]
    salida = salida.assign(estrato=pool["estrato"])
    return salida.sort_values("id").reset_index(drop=True)


# --- Hoja del piloto -----------------------------------------------------------------


def columnas_hoja(cfg: dict) -> list[str]:
    return ["id_ciego", *cfg["campos_ficha"], *CRITERIOS, "nota"]


def exigir_hoja_sin_codificar(ruta) -> None:  # noqa: ANN001
    """No pisa una hoja donde Luis Fer ya escribió códigos o notas."""
    if not ruta.is_file():
        return
    hoja = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if (hoja[[*CRITERIOS, "nota"]] != "").to_numpy().any():
        fallar(f"{ruta.name} ya tiene códigos o notas: no se sobrescribe")


def filas_del_piloto(tabla: pd.DataFrame, piloto: list[str], cfg: dict, semilla: int):
    azar = np.random.default_rng(semilla + 2)
    orden = list(azar.permutation(piloto))
    por_id = tabla.set_index("id")
    faltan = [c for c in cfg["campos_ficha"] if c not in por_id]
    if faltan:
        fallar(f"La matriz no tiene las columnas {faltan}")
    hoja, correspondencia = [], []
    for k, id_real in enumerate(orden, start=1):
        ciego = f"P{k:02d}"
        fila = {"id_ciego": ciego}
        fila |= {
            c: T.limpiar_ficha(por_id.loc[id_real, c]) for c in cfg["campos_ficha"]
        }
        fila |= dict.fromkeys([*CRITERIOS, "nota"], "")
        hoja.append(fila)
        correspondencia.append({"id_ciego": ciego, "id": id_real})
    return pd.DataFrame(hoja), pd.DataFrame(correspondencia)


# --- Costo ---------------------------------------------------------------------------


def costo_por_modelo(
    tokens: dict, precios: dict, n: int, descuento: float
) -> dict[str, float]:
    """USD con Batch: con caché del libro (1 escritura de 1 h + lecturas) y sin."""
    p = {k: v * (1 - descuento) for k, v in precios.items()}
    fijo, var, salida = tokens["libro"], tokens["ficha"], tokens["salida"]
    por_millon = 1e6
    sin_cache = n * ((fijo + var) * p["entrada"] + salida * p["salida"]) / por_millon
    con_cache = (
        fijo * p["escritura_1h"]
        + (n - 1) * fijo * p["lectura_cache"]
        + n * (var * p["entrada"] + salida * p["salida"])
    ) / por_millon
    return {"con_cache": con_cache, "sin_cache": sin_cache}


def estimar_costo(tabla: pd.DataFrame, cfg: dict, libro_texto: str) -> dict:
    """Tokens y USD de codificar los 196 informes (estimado sin llamar a la API)."""
    caracteres = (
        tabla[cfg["campos_ficha"]]
        .map(T.limpiar_ficha)
        .apply(lambda fila: sum(len(x) for x in fila), axis=1)
    )
    instruccion = 400  # tokens aproximados de las instrucciones y el formato de salida
    resultado = {
        "n_informes": len(tabla),
        "caracteres_ficha_media": float(caracteres.mean()),
    }
    for rotulo, cpt in cfg["caracteres_por_token"].items():
        libro = int(len(libro_texto) / cpt) + instruccion
        ficha = float(caracteres.mean() / cpt)
        porcentaje = {}
        for escenario, salida in cfg["salida_tokens_por_informe"].items():
            tokens = {"libro": libro, "ficha": ficha, "salida": salida}
            porcentaje[escenario] = {
                "tokens_libro_en_cache": libro,
                "tokens_ficha_por_informe": round(ficha),
                "tokens_salida_por_informe": salida,
                "tokens_entrada_total": int(libro + ficha * len(tabla)),
                "usd": {
                    modelo: {
                        k: round(v, 2)
                        for k, v in costo_por_modelo(
                            tokens, precios, len(tabla), cfg["descuento_batch"]
                        ).items()
                    }
                    for modelo, precios in cfg["modelos_costo"].items()
                },
            }
        resultado[f"caracteres_por_token_{rotulo}={cpt}"] = porcentaje
    return resultado


# --- Ejecución -----------------------------------------------------------------------


def ejecutar(params: dict) -> dict:
    cfg = params["codificacion"]
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    tablas = RAIZ_REPO / params["salidas"]["tablas"]
    hashes = escribir_libro(cfg)
    tabla, pesos = informes_con_peso(params)
    piloto = elegir_piloto(pesos, cfg["n_piloto"], cfg["semilla"])
    confiabilidad = elegir_confiabilidad(
        pesos, piloto, cfg["n_confiabilidad"], cfg["semilla"]
    )
    ruta_hoja = privada / "hoja_codificacion_piloto.csv"
    exigir_hoja_sin_codificar(ruta_hoja)
    hoja, correspondencia = filas_del_piloto(tabla, piloto, cfg, cfg["semilla"])
    hoja.to_csv(
        ruta_hoja,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
        columns=columnas_hoja(cfg),
    )
    correspondencia.to_csv(
        privada / "hoja_codificacion_piloto_correspondencia.csv",
        index=False,
        lineterminator="\n",
    )
    confiabilidad.to_csv(
        privada / "muestra_confiabilidad_40.csv", index=False, lineterminator="\n"
    )
    libro_texto = (RAIZ_REPO / "docs" / "libro_codigos_v0.md").read_text(
        encoding="utf-8"
    )
    costo = estimar_costo(tabla, cfg, libro_texto) | {
        "fuente_precios": cfg["precios_fuente"],
        "consultado": cfg["precios_consultados"],
        "nota": "Estimación sin llamar a la API: tokens = caracteres / (caracteres "
        "por token); Batch con descuento de 50 % acumulado con el caché de 1 h",
        "hashes_libro": hashes,
    }
    ruta_costo = tablas / "costo_codificacion_estimado.json"
    marcado = {
        "estado": "no aplica (D46)",
        "motivo": "La codificación la hace Claude Code con la suscripción de Luis "
        "Fer, sin API; esta estimación de la API queda solo como registro histórico.",
        "estimacion_api_no_vigente": costo,
    }
    ruta_costo.write_text(
        json.dumps(marcado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "piloto": piloto,
        "confiabilidad": confiabilidad,
        "pesos": pesos,
        "costo": costo,
    }


def main() -> int:
    try:
        if "--libro-v1" in sys.argv:
            print(escribir_libro(S.cargar_params()["codificacion"], "v1"))
            return 0
        salida = ejecutar(S.cargar_params())
    except ErrorPipeline as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"piloto: {len(salida['piloto'])} informes; confiabilidad: "
        f"{len(salida['confiabilidad'])} informes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
