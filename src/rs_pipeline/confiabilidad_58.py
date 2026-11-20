"""D58, paso C: registro de las corridas y confiabilidad entre modelos.

--registrar CARPETA --nombre NOMBRE valida los tres JSON de un codificador
(NOMBRE_lote1..3.json: exactamente los informes de cada lote según el manifiesto,
los nueve criterios en orden, códigos 0/1 y justificación de una línea) y los agrega
a logs/codificacion_d58.jsonl (privado). Nunca reescribe: si el codificador ya está
registrado, falla.

--calcular compara, sobre presencia 0/1 y con IC 95 % por bootstrap de informes:
(1) los tres modelos entre sí (AC1 de Gwet para varios codificadores, la medida
principal de D58) y por pares; (2) Claude Sonnet de D58 frente a su corrida original;
(3) cada modelo frente a los códigos de Luis Fer (muestra de 40 y verificación de 20).
A git van solo números (outputs/tablas/d58_confiabilidad.csv y .json).

Falla (código 1) si falta un archivo, un informe, un codificador o un código.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from rs_pipeline import semantico_04 as S
from rs_pipeline.codificacion_claude import CRITERIOS, validar_codificacion
from rs_pipeline.confiabilidad_40 import (
    BINARIAS,
    REMUESTREOS,
    SEMILLA,
    _percentiles,
    _redondeo,
    ac1_gwet,
    kappa_cohen,
)
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ = S.RAIZ_REPO
RUTA_CONFIG = RAIZ / "config" / "d58.yaml"
UMBRAL_ROBUSTO = 0.60
UMBRAL_MODERADO = 0.40

__all__ = ["ErrorPipeline"]


# --- Estadística -------------------------------------------------------------------


def ac1_varios(matriz: np.ndarray) -> float:
    """AC1 de Gwet para r codificadores y códigos 0/1 (filas = unidades).

    pa: proporción media de pares de codificadores que coinciden en cada unidad;
    pe: 2·π·(1−π), con π la proporción de 1 entre todos los códigos.
    Con r = 2 coincide con ac1_gwet de dos codificadores.
    """
    r = matriz.shape[1]
    unos = matriz.sum(axis=1)
    ceros = r - unos
    pares = (unos * (unos - 1) + ceros * (ceros - 1)) / (r * (r - 1))
    pa = float(pares.mean())
    pi = float(matriz.mean())
    pe = 2 * pi * (1 - pi)
    return (pa - pe) / (1 - pe)


def veredicto(ac1: float) -> str:
    if ac1 >= UMBRAL_ROBUSTO:
        return "robusto"
    if ac1 >= UMBRAL_MODERADO:
        return "moderado"
    return "sensible al modelo"


def indices_bootstrap(n: int) -> np.ndarray:
    return np.random.default_rng(SEMILLA).integers(0, n, size=(REMUESTREOS, n))


def _apilar(tabla: pd.DataFrame, criterios: list[str]) -> np.ndarray:
    """Bloques por criterio: filas = informes × criterios, columnas = codificadores."""
    return np.concatenate([np.stack(list(tabla[c]), axis=0) for c in criterios])


def fila_varios(nombre: str, bloques: list[np.ndarray], idx: np.ndarray) -> dict:
    """bloques: una matriz (informes × codificadores) por criterio incluido."""
    total = np.concatenate(bloques)
    ac1s = [ac1_varios(np.concatenate([b[i] for b in bloques])) for i in idx]
    bajo, alto, desc = _percentiles([v for v in ac1s if not math.isnan(v)])
    ac1 = ac1_varios(total)
    acuerdo = float((total.min(axis=1) == total.max(axis=1)).mean())
    return {
        "criterio": nombre,
        "n": len(total),
        "pct_acuerdo_todos": round(100 * acuerdo, 1),
        "prevalencias": [round(float(p), 3) for p in total.mean(axis=0)],
        "ac1_gwet": _redondeo(ac1),
        "ac1_ic_bajo": bajo,
        "ac1_ic_alto": alto,
        "ac1_remuestreos_descartados": desc,
        "veredicto": veredicto(ac1),
    }


def fila_par(nombre: str, bloques: list[np.ndarray], idx: np.ndarray) -> dict:
    """Como fila_varios para dos codificadores, con kappa de Cohen además del AC1."""
    fila = fila_varios(nombre, bloques, idx)
    total = np.concatenate(bloques)
    a, b = total[:, 0].tolist(), total[:, 1].tolist()
    fila["kappa_cohen"] = _redondeo(kappa_cohen(a, b))
    fila["ac1_dos"] = _redondeo(ac1_gwet(a, b, BINARIAS))
    return fila


def tabla_de_filas(
    comparacion: str,
    codigos: dict[str, pd.DataFrame],
    criterios: list[str],
    par: bool,
) -> list[dict]:
    """Una fila por criterio y una total.

    codigos: codificador -> tabla de informes (filas) × criterios (columnas).
    """
    nombres = list(codigos)
    ids = sorted(set.intersection(*(set(t.index) for t in codigos.values())))
    if not ids:
        fallar(f"{comparacion}: no hay informes en común")
    bloques = {
        c: np.column_stack([codigos[n].loc[ids, c].to_numpy() for n in nombres])
        for c in criterios
    }
    idx = indices_bootstrap(len(ids))
    hacer = fila_par if par else fila_varios
    filas = [hacer(c, [bloques[c]], idx) for c in criterios]
    filas.append(hacer("total", [bloques[c] for c in criterios], idx))
    for f in filas:
        f["comparacion"] = comparacion
        f["codificadores"] = " | ".join(nombres)
    return filas


# --- Registro ----------------------------------------------------------------------


def lotes_del_manifiesto(cfg: dict) -> dict[int, list[str]]:
    ruta = RAIZ / cfg["salidas"]["manifiesto"]
    if not ruta.is_file():
        fallar(f"No existe el manifiesto {ruta}")
    m = json.loads(ruta.read_text(encoding="utf-8"))
    return {x["lote"]: x["ids"] for x in m["paquete"]["lotes"]}


def leer_lote(ruta: Path, lote: int, ids: list[str]) -> dict:
    if not ruta.is_file():
        fallar(f"No existe {ruta}")
    try:
        dato = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fallar(f"{ruta.name} no es un JSON válido: {e}")
    if dato.get("lote") != lote or not str(dato.get("modelo", "")).strip():
        fallar(f"{ruta.name}: falta el modelo o el número de lote no es {lote}")
    if sorted(dato.get("informes", {})) != sorted(ids):
        fallar(f"{ruta.name}: no trae exactamente los 20 informes del lote {lote}")
    for id_ciego, d in dato["informes"].items():
        validar_codificacion(id_ciego, d["codigos"], d["justificaciones"], BINARIAS)
    return dato


def leer_registro(ruta: Path) -> list[dict]:
    if not ruta.is_file():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()]


def registrar(carpeta: Path, nombre: str, cfg: dict) -> int:
    if nombre not in cfg["codificadores"]:
        fallar(f"{nombre} no es uno de los codificadores de D58")
    ruta_log = RAIZ / cfg["registro_d58"]
    if any(x["codificador"] == nombre for x in leer_registro(ruta_log)):
        fallar(f"{nombre} ya está registrado; otro intento requiere decisión aparte")
    fecha = datetime.now().astimezone().isoformat(timespec="seconds")
    lineas = []
    for lote, ids in lotes_del_manifiesto(cfg).items():
        ruta = carpeta / f"{nombre}_lote{lote}.json"
        dato = leer_lote(ruta, lote, ids)
        sha = hashlib.sha256(ruta.read_bytes()).hexdigest()
        for id_ciego, d in sorted(dato["informes"].items()):
            lineas.append(
                {
                    "fecha_registro": fecha,
                    "codificador": nombre,
                    "modelo": dato["modelo"],
                    "modelo_incierto": bool(dato.get("modelo_incierto", False)),
                    "lote": lote,
                    "sha256_json": sha,
                    "id_ciego": id_ciego,
                    "codigos": d["codigos"],
                    "justificaciones": d["justificaciones"],
                }
            )
    ruta_log.parent.mkdir(exist_ok=True)
    with ruta_log.open("a", encoding="utf-8") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in lineas)
    return len(lineas)


# --- Fuentes de códigos ------------------------------------------------------------


def codigos_d58(cfg: dict) -> dict[str, pd.DataFrame]:
    lineas = leer_registro(RAIZ / cfg["registro_d58"])
    out = {}
    for nombre in cfg["codificadores"]:
        filas = {
            x["id_ciego"]: x["codigos"] for x in lineas if x["codificador"] == nombre
        }
        if len(filas) != cfg["n_informes"]:
            fallar(
                f"{nombre}: hay {len(filas)} informes registrados, "
                f"no {cfg['n_informes']}"
            )
        out[nombre] = pd.DataFrame.from_dict(filas, orient="index")[CRITERIOS]
    return out


def correspondencia(cfg: dict) -> pd.DataFrame:
    ruta = RAIZ / cfg["salidas"]["correspondencia"]
    if not ruta.is_file():
        fallar(f"No existe {ruta}")
    return pd.read_csv(ruta, dtype=str, encoding="utf-8-sig").set_index("id_ciego")


def codigos_originales(cfg: dict, corr: pd.DataFrame) -> pd.DataFrame:
    """Códigos de la corrida original (libro v3) re-etiquetados con los X."""
    largo = pd.read_csv(RAIZ / cfg["codigos_originales"], dtype=str)
    if largo.duplicated(["id_ciego", "criterio"]).any():
        fallar("La corrida original trae códigos repetidos por informe y criterio")
    ancho = largo.pivot(index="id_ciego", columns="criterio", values="codigo")
    t_a_x = {t: x for x, t in corr["id_t"].items()}
    ancho = ancho.loc[[t for t in ancho.index if t in t_a_x]].rename(index=t_a_x)
    if len(ancho) != len(corr):
        fallar("Faltan informes de la muestra en la corrida original")
    return ancho[CRITERIOS].astype(int)


def codigos_humanos(
    ruta: Path, corr: pd.DataFrame, criterios: list[str]
) -> pd.DataFrame:
    """Códigos de Luis Fer (0/1/2 → presencia), re-etiquetados con los X."""
    tabla = pd.read_csv(ruta, dtype=str, encoding="utf-8-sig").set_index("id_ciego")
    origen_a_x = {o: x for x, o in corr["id_origen"].items()}
    faltan = [i for i in tabla.index if i not in origen_a_x]
    if faltan:
        fallar(f"{ruta.name}: informes fuera de la muestra: {', '.join(faltan)}")
    datos = tabla[criterios]
    if not datos.isin(["0", "1", "2"]).all().all():
        fallar(f"{ruta.name}: hay códigos vacíos o distintos de 0, 1 y 2")
    return (datos.astype(int) > 0).astype(int).rename(index=origen_a_x)


# --- Cálculo -----------------------------------------------------------------------


def calcular(cfg: dict) -> list[dict]:
    modelos = codigos_d58(cfg)
    corr = correspondencia(cfg)
    filas = tabla_de_filas("entre_modelos", modelos, CRITERIOS, par=False)
    for a, b in combinations(modelos, 2):
        pares = {a: modelos[a], b: modelos[b]}
        filas += tabla_de_filas("par", pares, CRITERIOS, par=True)
    retest = {
        cfg["retest"]: modelos[cfg["retest"]],
        "original": codigos_originales(cfg, corr),
    }
    filas += tabla_de_filas("repeticion", retest, CRITERIOS, par=True)
    h40 = codigos_humanos(RAIZ / cfg["codigos_luis_40"], corr, CRITERIOS)
    tres = ["C05", "C06", "C08"]
    h20 = codigos_humanos(RAIZ / cfg["codigos_luis_20"], corr, tres)
    for nombre, tabla in modelos.items():
        con_40 = {"luis": h40, nombre: tabla}
        filas += tabla_de_filas("humano_40", con_40, CRITERIOS, par=True)
        con_20 = {"luis": h20, nombre: tabla}
        filas += tabla_de_filas("humano_20", con_20, tres, par=True)
    return filas


def guardar(cfg: dict, filas: list[dict]) -> None:
    base = RAIZ / cfg["resultados"]
    pd.DataFrame(filas).to_csv(base.with_suffix(".csv"), index=False)
    entradas = [
        cfg["registro_d58"],
        cfg["salidas"]["correspondencia"],
        cfg["codigos_originales"],
        cfg["codigos_luis_40"],
        cfg["codigos_luis_20"],
    ]
    registro = leer_registro(RAIZ / cfg["registro_d58"])
    modelos = sorted({(x["codificador"], x["modelo"]) for x in registro})
    meta = {
        "decision": "D58",
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "remuestreos": REMUESTREOS,
        "semilla": SEMILLA,
        "umbrales": {"robusto": UMBRAL_ROBUSTO, "moderado": UMBRAL_MODERADO},
        "modelos": [{"codificador": c, "modelo": m} for c, m in modelos],
        "entradas_sha256": {e: S.sha256(RAIZ / e) for e in entradas},
        "filas": filas,
    }
    texto = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    base.with_suffix(".json").write_text(texto, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registrar", type=Path)
    parser.add_argument("--nombre")
    parser.add_argument("--calcular", action="store_true")
    args = parser.parse_args()
    cfg = yaml.safe_load(RUTA_CONFIG.read_text(encoding="utf-8"))
    try:
        if args.registrar:
            n = registrar(args.registrar.expanduser(), args.nombre, cfg)
            print(f"{args.nombre}: {n} informes registrados")
        if args.calcular:
            filas = calcular(cfg)
            guardar(cfg, filas)
            for f in filas:
                if f["comparacion"] == "entre_modelos":
                    print(f"{f['criterio']}: AC1 {f['ac1_gwet']} → {f['veredicto']}")
    except ErrorPipeline as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
