"""D58, paso A: paquete ciego para codificar 60 informes con varios modelos.

Arma, en una carpeta FUERA del repositorio (la que se abre en Orca), solo lo que un
codificador ciego puede leer: el protocolo, el libro de códigos v3 y 60 fichas en
3 lotes, con códigos nuevos X01–X60. Las fichas salen de la hoja de 196 y se comprueba
que son idénticas (mismo hash) a las que leyó Claude en la corrida original con el
libro v3. La correspondencia X → id real queda privada (outputs/semantico, ignorada) y
a git va solo un manifiesto con ids, conteos y hashes, sin texto de las fichas.

Falla (código 1) si falta un archivo, si el libro no tiene el hash esperado, si los 60
informes no cuadran (40 + 20, sin repetidos y todos entre los 196), si una ficha no
coincide con la del registro o si la carpeta de destino ya trae lotes o salidas.

Uso (desde la raíz del repositorio):
    PYTHONPATH=src .venv/bin/python -m rs_pipeline.multimodelo_58 \
        --destino ~/d58-corridas
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from rs_pipeline import semantico_04 as S
from rs_pipeline.codificacion_06 import repartir_en_lotes
from rs_pipeline.codificacion_claude import hash_ficha
from rs_pipeline.semantico_texto import ErrorPipeline, fallar

RAIZ = S.RAIZ_REPO
RUTA_CONFIG = RAIZ / "config" / "d58.yaml"
RUTA_PARAMS = RAIZ / "config" / "params.yaml"

__all__ = ["ErrorPipeline"]


def leer_csv(ruta: Path) -> pd.DataFrame:
    if not ruta.is_file():
        fallar(f"No existe {ruta}")
    return pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def exigir_hash(ruta: Path, esperado: str) -> str:
    if not ruta.is_file():
        fallar(f"No existe {ruta}")
    real = S.sha256(ruta)
    if real != esperado:
        fallar(
            f"{ruta.name} cambió: sha256 {real[:12]}… y se esperaba {esperado[:12]}…"
        )
    return real


def muestra_60(c40: pd.DataFrame, c20: pd.DataFrame, n: int) -> pd.DataFrame:
    """Une la calibración (M) y la verificación (V).

    Falla si no son 60 ids distintos.
    """
    a = c40.assign(origen="calibracion_40").rename(columns={"id_ciego": "id_origen"})
    b = c20.assign(origen="verificacion_20").rename(columns={"id_ciego": "id_origen"})
    muestra = pd.concat([a, b], ignore_index=True)
    if len(muestra) != n:
        fallar(f"La muestra tiene {len(muestra)} informes y deben ser {n}")
    if muestra["id"].duplicated().any() or (muestra["id"] == "").any():
        fallar("Hay informes repetidos o sin id entre la muestra de 40 y la de 20")
    return muestra


def asignar_ciegos(
    muestra: pd.DataFrame, c196: pd.DataFrame, semilla: int, prefijo: str
) -> pd.DataFrame:
    """Orden al azar (semilla fija), código X01… y el T de la hoja de 196."""
    a_t = dict(zip(c196["id"], c196["id_ciego"], strict=True))
    faltan = sorted(set(muestra["id"]) - set(a_t))
    if faltan:
        fallar(f"Informes que no están entre los 196: {', '.join(faltan)}")
    orden = np.random.default_rng(semilla).permutation(len(muestra))
    out = muestra.iloc[orden].reset_index(drop=True)
    out.insert(0, "id_ciego", [f"{prefijo}{i:02d}" for i in range(1, len(out) + 1)])
    out["id_t"] = out["id"].map(a_t)
    return out[["id_ciego", "id", "id_t", "origen", "id_origen"]]


def hashes_del_registro(registro: Path, libro_yaml_sha: str) -> dict[str, str]:
    """sha256 de la ficha leída por Claude en la corrida original (libro v3), por T."""
    if not registro.is_file():
        fallar(f"No existe {registro}")
    hashes: dict[str, str] = {}
    for linea in registro.read_text(encoding="utf-8").splitlines():
        dato = json.loads(linea)
        if dato["libro"]["sha256"] == libro_yaml_sha:
            hashes[dato["id_ciego"]] = dato["sha256_ficha"]
    return hashes


def fichas(
    mapa: pd.DataFrame, hoja: pd.DataFrame, campos: list[str], hashes: dict[str, str]
) -> pd.DataFrame:
    """Los 19 campos de cada X, tomados de su T y verificados contra el registro."""
    faltan_col = [c for c in campos if c not in hoja.columns]
    if faltan_col:
        fallar(f"A la hoja de 196 le faltan columnas: {', '.join(faltan_col)}")
    por_t = hoja.set_index("id_ciego")
    filas = []
    for x, t in zip(mapa["id_ciego"], mapa["id_t"], strict=True):
        ficha = {c: por_t.loc[t, c] for c in campos}
        if hashes.get(t) != hash_ficha(ficha):
            fallar(
                f"{x} ({t}): la ficha no coincide con la leída en la corrida original"
            )
        filas.append({"id_ciego": x, **ficha})
    return pd.DataFrame(filas)


def exigir_destino_libre(destino: Path) -> None:
    if not destino.is_dir():
        fallar(f"No existe la carpeta de destino {destino}")
    for sub in ("lotes", "salidas"):
        carpeta = destino / sub
        if carpeta.exists() and any(p.name != ".gitkeep" for p in carpeta.iterdir()):
            fallar(f"{carpeta} ya trae archivos; no se sobrescribe un paquete")


def escribir_paquete(
    destino: Path, tabla: pd.DataFrame, lotes: list[list[str]], cfg: dict
) -> list[dict]:
    (destino / "lotes").mkdir(exist_ok=True)
    (destino / "salidas").mkdir(exist_ok=True)
    (destino / "salidas" / ".gitkeep").touch()
    shutil.copyfile(RAIZ / cfg["libro"]["markdown"], destino / "libro_codigos_v3.md")
    shutil.copyfile(RAIZ / cfg["protocolo"], destino / "LEEME_CODIFICADOR.md")
    resumen = []
    por_id = tabla.set_index("id_ciego")
    for n, ids in enumerate(lotes, start=1):
        ruta = destino / "lotes" / f"lote{n}.csv"
        por_id.loc[ids].reset_index().to_csv(ruta, index=False, encoding="utf-8-sig")
        resumen.append({"lote": n, "ids": ids, "sha256": S.sha256(ruta)})
    return resumen


def manifiesto(
    cfg: dict, mapa: pd.DataFrame, resumen: list[dict], destino: Path, entradas: dict
) -> dict:
    return {
        "decision": "D58",
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "semilla": cfg["semilla"] + cfg["desplazamiento"],
        "n_informes": len(mapa),
        "por_origen": mapa["origen"].value_counts().sort_index().to_dict(),
        "entradas_sha256": entradas,
        "paquete": {
            "carpeta": destino.name,
            "libro_codigos_v3.md": S.sha256(destino / "libro_codigos_v3.md"),
            "LEEME_CODIFICADOR.md": S.sha256(destino / "LEEME_CODIFICADOR.md"),
            "lotes": resumen,
        },
        "fichas_identicas_a_la_corrida_original": True,
    }


def preparar(destino: Path, cfg: dict, params: dict) -> dict:
    exigir_destino_libre(destino)
    ent = cfg["entradas"]
    rutas = {k: RAIZ / v for k, v in ent.items()}
    exigir_hash(RAIZ / cfg["libro"]["markdown"], cfg["libro"]["markdown_sha256"])
    exigir_hash(RAIZ / cfg["libro"]["yaml"], cfg["libro"]["yaml_sha256"])
    muestra = muestra_60(
        leer_csv(rutas["correspondencia_40"]),
        leer_csv(rutas["correspondencia_20"]),
        cfg["n_informes"],
    )
    semilla = cfg["semilla"] + cfg["desplazamiento"]
    mapa = asignar_ciegos(
        muestra, leer_csv(rutas["correspondencia_196"]), semilla, cfg["prefijo"]
    )
    hashes = hashes_del_registro(rutas["registro"], cfg["libro"]["yaml_sha256"])
    campos = params["codificacion"]["campos_ficha"]
    tabla = fichas(mapa, leer_csv(rutas["hoja_196"]), campos, hashes)
    lotes = repartir_en_lotes(
        list(tabla["id_ciego"]), cfg["n_lotes"], cfg["max_por_lote"]
    )
    resumen = escribir_paquete(destino, tabla, lotes, cfg)
    ruta_c = RAIZ / cfg["salidas"]["correspondencia"]
    mapa.to_csv(ruta_c, index=False, encoding="utf-8-sig")
    entradas = {v: S.sha256(rutas[k]) for k, v in ent.items()}
    m = manifiesto(cfg, mapa, resumen, destino, entradas)
    ruta_m = RAIZ / cfg["salidas"]["manifiesto"]
    texto = json.dumps(m, ensure_ascii=False, indent=2) + "\n"
    ruta_m.write_text(texto, encoding="utf-8")
    return m


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destino", required=True, type=Path)
    args = parser.parse_args()
    cfg = yaml.safe_load(RUTA_CONFIG.read_text(encoding="utf-8"))
    params = yaml.safe_load(RUTA_PARAMS.read_text(encoding="utf-8"))
    try:
        m = preparar(args.destino.expanduser().resolve(), cfg, params)
    except ErrorPipeline as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(
        f"Paquete D58 listo en {args.destino}: {m['n_informes']} informes, "
        f"{len(m['paquete']['lotes'])} lotes, {m['por_origen']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
