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
LIBROS_HISTORICOS = ("v0", "v1", "v2")  # ya usados para codificar: no se reescriben
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
# Cambios tras el piloto (v2, D47).
REGLAS_V2 = [
    *REGLAS_V1,
    "Si el grupo de comparación también tuvo el componente, no se puede atribuir "
    "el resultado a ese componente: se codifica 1, no 2.",
    "C08: predecir y luego comparar con lo observado (predecir-observar-explicar), "
    "o comparar resultados con valores de referencia o con la teoría, cuenta como "
    "1. Es 2 solo si el estudio relaciona ese contraste con un resultado.",
]
EJEMPLOS_REGLAS_V2 = [
    *EJEMPLOS_REGLAS_V1,
    "Regla d. Ejemplo: «El grupo control también usó hojas de trabajo guiadas y "
    "ambos grupos mejoraron» → la guía = 1, no 2.",
    "Regla C08. Ejemplo: «Los estudiantes predecían la trayectoria y luego la "
    "comparaban con lo que mostraba la simulación» → 1; «quienes comparaban con la "
    "teoría corrigieron más errores en el postest, según los autores» → 2.",
]
EJEMPLOS_POR_VERSION = {"v1": EJEMPLOS_REGLAS_V1, "v2": EJEMPLOS_REGLAS_V2}
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


# Libro v3 (D50): escala principal = presencia (0/1); la atribución no se codifica.
ESCALA_V3 = {
    0: "No aparece, o la ficha dice explícitamente que no se reporta o que no se "
    "documenta.",
    1: "Aparece: la ficha menciona el componente como parte de la actividad o del "
    "laboratorio, con o sin resultado.",
}
REGLAS_V3 = [
    "Codificar solo lo que dice la ficha; no completar con conocimiento propio.",
    "Ante duda entre 0 y 1, el 0.",
    "Un informe recibe un código por criterio (C01 a C09), siempre los nueve.",
    "«1» exige que la ficha mencione el componente. Si no lo menciona, o dice que "
    "no se reporta o no se documenta, es 0, aunque se pueda suponer que existía.",
    "No se codifica atribución: da igual si el estudio vincula el componente con un "
    "resultado, si el resultado es del paquete completo o si el grupo de "
    "comparación también tuvo el componente.",
    "Un dato descriptivo de contexto o de barrera (p. ej., el porcentaje de "
    "estudiantes sin internet en casa) cuenta como presencia (1).",
    "Los criterios C01, C06 y C09 siguen en borrador: se codifican igual y, si el "
    "enunciado no alcanza para decidir, se dice en la justificación de una línea.",
    "C05, C06 y C08 se deciden con su lista «cuenta / no cuenta»; si un caso no "
    "está en ninguna lista, se aplica la regla de duda (0).",
    "La corrección o los comentarios del docente o de pares se codifican en C04, "
    "no en C06.",
]
# Ejemplos inventados (no son texto de artículos) del libro v3: códigos 0 y 1.
EJEMPLOS_V3 = {
    "C02": {
        0: EJEMPLOS["C02"][0],
        1: EJEMPLOS["C02"][1],
    },
    "C04": {
        0: EJEMPLOS["C04"][0],
        1: EJEMPLOS["C04"][1],
    },
    "C05": {
        0: "Ejemplo: «Los estudiantes exploraban la simulación y explicaban lo que "
        "veían; no se menciona registro de datos.»",
        1: "Ejemplo: «Los estudiantes registraban voltaje y corriente en una tabla y "
        "calculaban la resistencia.»",
    },
    "C06": {
        0: "Ejemplo: «La simulación mostraba gráficas de energía mientras el "
        "estudiante cambiaba la altura.»",
        1: "Ejemplo: «La simulación marcaba en rojo las conexiones erróneas del "
        "circuito y daba un puntaje.»",
    },
    "C08": {
        0: "Ejemplo: «Los estudiantes observaban que la energía mecánica se "
        "conservaba.»",
        1: "Ejemplo: «Los estudiantes calculaban el alcance a mano y lo comparaban "
        "con el que mostraba la simulación.»",
    },
    "C09": {
        0: EJEMPLOS["C09"][0],
        1: EJEMPLOS["C09"][1],
    },
}
# Listas «cuenta / no cuenta» aprobadas por Luis Fer (D50).
LISTAS_V3 = {
    "C05": {
        "cuenta": [
            "Mide con un instrumento, real o virtual.",
            "Registra datos en una tabla o informe.",
            "Calcula a partir de datos.",
            "Grafica o interpreta datos propios.",
            "Concluye a partir de datos.",
        ],
        "no_cuenta": [
            "Solo manipula parámetros y observa.",
            "Ve gráficas que genera el sistema, sin que el estudiante las procese.",
            "Responde preguntas conceptuales.",
            "«Realiza experimentos» sin mención de datos.",
            "Explica o argumenta con lo observado, sin datos registrados.",
        ],
    },
    "C06": {
        "cuenta": [
            "Un puntaje o una calificación automática del trabajo del estudiante.",
            "Una marca o un mensaje de error del sistema.",
            "Un indicador de estado o de riesgo que cambia según lo que hizo.",
            "Un resultado del sistema que, según la ficha, deja ver el error del "
            "estudiante.",
        ],
        "no_cuenta": [
            "Tener gráficos, animaciones o representaciones del fenómeno.",
            "La respuesta visual al mover parámetros.",
            "«Retroalimentación inmediata» sin decir qué muestra.",
            "La corrección o los comentarios del docente o de pares (van a C04).",
        ],
    },
    "C08": {
        "cuenta": [
            "Predice y luego compara con lo observado (predecir-observar-explicar).",
            "Compara su resultado con un valor de referencia o con la teoría.",
            "Compara su cálculo a mano con el simulador.",
            "Verifica una ley o un resultado conocido.",
            "Contrasta lo esperado con lo obtenido.",
            "Recrea el montaje real para contrastarlo con la simulación.",
        ],
        "no_cuenta": [
            "Observar un principio (p. ej., la conservación) sin compararlo con nada.",
            "Comparar grupos o condiciones del estudio: es diseño del estudio, no "
            "actividad del estudiante.",
            "Que el docente corrija las respuestas (va a C04).",
            "La clave de un cuestionario, salvo que la ficha diga que el estudiante "
            "contrasta su respuesta con ella.",
        ],
    },
}
NOTAS_V3 = {
    "C01": "Casi universal en la muestra de 40 (D49); en el marco será una "
    "condición base (D50).",
    "C02": "Casi universal en la muestra de 40 (D49); en el marco será una "
    "condición base (D50).",
    "C04": "Incluye la corrección y los comentarios del docente o de pares (D50).",
}

REGLAS_POR_VERSION = {"v0": REGLAS, "v1": REGLAS_V1, "v2": REGLAS_V2, "v3": REGLAS_V3}
DECISION_POR_VERSION = {"v0": "D44", "v1": "D45", "v2": "D47", "v3": "D50"}

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
    ejemplos = EJEMPLOS_V3 if version == "v3" else EJEMPLOS
    for c in marco["criterios"]:
        entrada = {k: c[k] for k in ("id", "dimension", "criterio_corto", "enunciado")}
        entrada["estado"] = c["estado"]
        if c["id"] in ejemplos:
            entrada["ejemplos"] = {k: v for k, v in ejemplos[c["id"]].items()}
        if version == "v3":
            entrada |= LISTAS_V3.get(c["id"], {})
            if c["id"] in NOTAS_V3:
                entrada["nota"] = NOTAS_V3[c["id"]]
        criterios.append(entrada)
    libro = {
        "version": version,
        "decision": DECISION_POR_VERSION[version],
        "fuente_criterios": {"archivo": "config/criterios_v0.yaml", "sha256": sha},
        "escala": ESCALA_V3 if version == "v3" else ESCALA,
        "reglas": REGLAS_POR_VERSION[version],
        "campos_ficha": cfg["campos_ficha"],
        "campos_excluidos": {
            "oe2_criterios_candidatos": "inferencias del extractor (sesgan el código)",
            "lf_*": "notas de Luis Fer",
        },
        "criterios": criterios,
    }
    if version in EJEMPLOS_POR_VERSION:
        libro["ejemplos_de_reglas"] = EJEMPLOS_POR_VERSION[version]
    return libro


def libro_a_markdown(libro: dict) -> str:
    lineas = [
        f"# Libro de códigos {libro['version']} ({libro['decision']})",
        "",
        "Codificación deductiva de cada informe frente a cada criterio del marco v0"
        + (": presencia (0/1)." if libro["version"] == "v3" else "."),
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
        titulo = "las reglas nuevas" if libro["version"] == "v1" else "las reglas"
        lineas += ["", f"## Ejemplos de {titulo} (inventados)", ""]
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
        for clave, rotulo in (("cuenta", "Cuenta (1)"), ("no_cuenta", "No cuenta (0)")):
            if clave in c:
                lineas.append(f"- **{rotulo}:**")
                lineas += [f"  - {x}" for x in c[clave]]
        if "nota" in c:
            lineas.append(f"- **Nota:** {c['nota']}")
    return "\n".join(lineas) + "\n"


def escribir_libro(cfg: dict, version: str = "v0") -> dict:
    libro = construir_libro(cfg, version)
    ruta_yaml = RAIZ_REPO / "config" / f"libro_codigos_{version}.yaml"
    if ruta_yaml.is_file() and version in LIBROS_HISTORICOS:
        fallar(f"{ruta_yaml.name} es un libro histórico: no se reescribe (D50)")
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
    pesos: pd.DataFrame,
    piloto: list[str],
    cantidad: int,
    semilla: int,
    desplazamiento: int = 1,
) -> pd.DataFrame:
    """40 informes estratificados por peso y nivel; sin el piloto ni su estudio."""
    estudios_piloto = set(pesos[pesos["id"].isin(piloto)]["estudio"])
    pool = pesos[~pesos["estudio"].isin(estudios_piloto)].copy()
    pool["estrato"] = pool["peso_suma"] + " | " + pool["nivel"]
    cuota = cuotas(pool.groupby("estrato").size(), cantidad)
    azar = np.random.default_rng(semilla + desplazamiento)
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


def exigir_hoja_sin_codificar(ruta, vacias: list[str] | None = None) -> None:  # noqa: ANN001
    """No pisa una hoja donde Luis Fer ya escribió códigos o notas."""
    if not ruta.is_file():
        return
    hoja = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    columnas = vacias or [*CRITERIOS, "nota"]
    if (hoja[columnas] != "").to_numpy().any():
        fallar(f"{ruta.name} ya tiene códigos o notas: no se sobrescribe")


def filas_del_piloto(
    tabla: pd.DataFrame,
    piloto: list[str],
    cfg: dict,
    semilla: int,
    prefijo: str = "P",
    desplazamiento: int = 2,
    ancho: int = 2,
):
    azar = np.random.default_rng(semilla + desplazamiento)
    orden = list(azar.permutation(piloto))
    por_id = tabla.set_index("id")
    faltan = [c for c in cfg["campos_ficha"] if c not in por_id]
    if faltan:
        fallar(f"La matriz no tiene las columnas {faltan}")
    hoja, correspondencia = [], []
    for k, id_real in enumerate(orden, start=1):
        ciego = f"{prefijo}{k:0{ancho}d}"
        fila = {"id_ciego": ciego}
        fila |= {
            c: T.limpiar_ficha(por_id.loc[id_real, c]) for c in cfg["campos_ficha"]
        }
        fila |= dict.fromkeys([*CRITERIOS, "nota"], "")
        hoja.append(fila)
        correspondencia.append({"id_ciego": ciego, "id": id_real})
    return pd.DataFrame(hoja), pd.DataFrame(correspondencia)


def hoja_codificacion_40(params: dict) -> int:
    """Hoja de la muestra de confiabilidad (M01…M40), sin códigos ni anclajes."""
    cfg = params["codificacion"]
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    ruta = privada / "hoja_codificacion_40.csv"
    exigir_hoja_sin_codificar(ruta)
    muestra = pd.read_csv(privada / "muestra_confiabilidad_40.csv")
    if len(muestra) != cfg["n_confiabilidad"]:
        fallar(f"La muestra tiene {len(muestra)} informes, no {cfg['n_confiabilidad']}")
    tabla = S.cargar_matriz(params)["tabla"]
    hoja, correspondencia = filas_del_piloto(
        tabla, list(muestra["id"]), cfg, cfg["semilla"], prefijo="M", desplazamiento=3
    )
    hoja.to_csv(
        ruta,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
        columns=columnas_hoja(cfg),
    )
    correspondencia.to_csv(
        privada / "hoja_codificacion_40_correspondencia.csv",
        index=False,
        lineterminator="\n",
    )
    return len(hoja)


# --- Verificación de presencia y codificación completa (D50) --------------------------

CRITERIOS_VERIFICADOS = ["C05", "C06", "C08"]


def repartir_en_lotes(ids: list[str], n_lotes: int, maximo: int) -> list[list[str]]:
    """Lotes consecutivos de tamaño parejo (el último puede ser más corto)."""
    ordenados = sorted(ids)
    tamano = -(-len(ordenados) // n_lotes)
    if tamano > maximo:
        fallar(f"Un lote tendría {tamano} informes y el máximo por sesión es {maximo}")
    lotes = [ordenados[i : i + tamano] for i in range(0, len(ordenados), tamano)]
    if sum(len(x) for x in lotes) != len(ordenados) or len(lotes) > n_lotes:
        fallar("El reparto en lotes no cuadra con los informes")
    return lotes


def ids_ya_usados(privada) -> list[str]:  # noqa: ANN001
    """Informes del piloto y de la muestra de 40 (para no repetirlos)."""
    piloto = pd.read_csv(privada / "hoja_codificacion_piloto_correspondencia.csv")
    muestra = pd.read_csv(privada / "muestra_confiabilidad_40.csv")
    return sorted(set(piloto["id"]) | set(muestra["id"]))


def hoja_presencia_20(params: dict) -> int:
    """Hoja de verificación de C05, C06 y C08: 20 informes nuevos (V01…V20)."""
    cfg = params["codificacion"]
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    ruta = privada / "hoja_codificacion_presencia_20.csv"
    columnas = [*CRITERIOS_VERIFICADOS, "modo_presencia", "nota"]
    exigir_hoja_sin_codificar(ruta, columnas)
    tabla, pesos = informes_con_peso(params)
    muestra = elegir_confiabilidad(
        pesos,
        ids_ya_usados(privada),
        cfg["n_verificacion_presencia"],
        cfg["semilla"],
        desplazamiento=4,
    )
    if len(muestra) != cfg["n_verificacion_presencia"]:
        fallar(f"La muestra tiene {len(muestra)} informes, no el pedido")
    hoja, correspondencia = filas_del_piloto(
        tabla, list(muestra["id"]), cfg, cfg["semilla"], prefijo="V", desplazamiento=5
    )
    hoja = hoja.assign(modo_presencia="")
    hoja.to_csv(
        ruta,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
        columns=["id_ciego", *cfg["campos_ficha"], *columnas],
    )
    correspondencia.to_csv(
        privada / "hoja_codificacion_presencia_20_correspondencia.csv",
        index=False,
        lineterminator="\n",
    )
    muestra.to_csv(
        privada / "muestra_verificacion_presencia_20.csv",
        index=False,
        lineterminator="\n",
    )
    return len(hoja)


def hoja_196(params: dict) -> list[int]:
    """Hoja de los 196 (T001…T196) y una hoja por lote; devuelve sus tamaños."""
    cfg = params["codificacion"]
    privada = RAIZ_REPO / params["semantico"]["salidas"]
    ruta = privada / "hoja_codificacion_196.csv"
    exigir_hoja_sin_codificar(ruta)
    tabla = S.cargar_matriz(params)["tabla"]
    hoja, correspondencia = filas_del_piloto(
        tabla,
        list(tabla["id"]),
        cfg,
        cfg["semilla"],
        prefijo="T",
        desplazamiento=6,
        ancho=3,
    )
    lotes = repartir_en_lotes(
        list(hoja["id_ciego"]), cfg["n_lotes_196"], cfg["max_por_lote"]
    )
    columnas = columnas_hoja(cfg)
    hoja.to_csv(
        ruta,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
        columns=columnas,
    )
    for n, ids in enumerate(lotes, start=1):
        hoja[hoja["id_ciego"].isin(ids)].to_csv(
            privada / f"hoja_codificacion_196_lote{n}.csv",
            index=False,
            encoding="utf-8-sig",
            lineterminator="\n",
            columns=columnas,
        )
    correspondencia.to_csv(
        privada / "hoja_codificacion_196_correspondencia.csv",
        index=False,
        lineterminator="\n",
    )
    return [len(x) for x in lotes]


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
        for version in ("v1", "v2", "v3"):
            if f"--libro-{version}" in sys.argv:
                print(escribir_libro(S.cargar_params()["codificacion"], version))
                return 0
        if "--hoja-presencia-20" in sys.argv:
            n = hoja_presencia_20(S.cargar_params())
            print(f"informes en la hoja: {n}")
            return 0
        if "--hoja-196" in sys.argv:
            print(f"lotes de la hoja de 196: {hoja_196(S.cargar_params())}")
            return 0
        if "--hoja-40" in sys.argv:
            print(f"informes en la hoja: {hoja_codificacion_40(S.cargar_params())}")
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
