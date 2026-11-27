"""Medición de los recortes de las páginas de los DBA de Ciencias Naturales (D60).

Se mide UNA vez y los valores se congelan en config/recortes_dba_cn.yaml, como en D57:
el extractor (paso siguiente) leerá ese YAML y no volverá a medir. Esto solo PROPONE:
la persona que revisa confirma a ojo antes de llenar `verificado_por`.

Método: pdftotext -bbox da cada palabra con su caja, en puntos PDF. En cada página:
- el encabezado es lo que está a la altura de «V.1» (fin de «Derechos Básicos de
  Aprendizaje • V.1») o más arriba;
- el pie empieza en el número de página; debajo va la marca de InDesign
  («CienciasNaturales DBA_Final.indd N»), que repite ese número y no sirve de ancla;
- el texto es lo que queda entre los dos.
Las columnas se separan en el único hueco vertical que ninguna palabra del texto cruza
en ninguna de las 19 páginas. Cada recorte queda en la mitad del hueco más estrecho.
Como control, el texto leído por columnas (izquierda, derecha, página siguiente) debe
repetir siempre: número de DBA, «Evidencias», viñetas y «Ejemplo».

    PYTHONPATH=src .venv/bin/python -m rs_pipeline.recortes_dba_09

Escribe el YAML (si ya existe, FALLA: puede traer una verificación) y la evidencia
para revisar (cada página con los recortes en rojo) en data/processed/curriculo/.
"""

from __future__ import annotations

import html
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import NamedTuple

import yaml

from rs_pipeline.extraccion_09 import (
    documento_del_inventario,
    pdf_verificado,
    version_pdftotext,
)
from rs_pipeline.ocr_pe_09 import ejecutar
from rs_pipeline.recortes_pe_09 import escribir_png_rgb, hoja_de_contacto, leer_pgm
from rs_pipeline.semantico_texto import fallar

RAIZ_REPO = Path(__file__).resolve().parents[2]
ID_DBA = "CO-DBA-CN"
PAGINAS = range(21, 40)  # grados 6.º a 11.º
CONFIG = RAIZ_REPO / "config" / "recortes_dba_cn.yaml"
EVIDENCIA = RAIZ_REPO / "data" / "processed" / "curriculo" / "CO-DBA-CN_recortes"
ANCLA_ENCABEZADO = "V.1"
ANCLA_MARCA = "CienciasNaturales"  # junta: solo así aparece en la marca de InDesign
HUECO_MINIMO = 6.0  # pt; con un hueco menor no hay margen seguro para cortar
ALTO_MIN_NUMERO = 25.0  # pt; el número de un DBA es mucho más alto que el texto
DPI_EVIDENCIA = 70
METODO = "propuesto por medición de coordenadas (pdftotext -bbox), verificado a ojo"

RE_PAGINA = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">')
RE_CAJA = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">'
    r"([^<]*)</word>"
)
RE_NUMERO_DBA = re.compile(r"^(\d)\.$")


class Palabra(NamedTuple):
    texto: str
    x0: float
    y0: float
    x1: float
    y1: float


def paginas_con_cajas(bbox_html: str) -> list[tuple[float, list[Palabra]]]:
    """Por página: ancho en puntos y sus palabras con la caja completa."""
    paginas = []
    for bloque in bbox_html.split("<page ")[1:]:
        cabecera = RE_PAGINA.match("<page " + bloque)
        leidas = RE_CAJA.findall(bloque)
        if cabecera is None or len(leidas) != bloque.count("<word "):
            fallar("pdftotext -bbox: hay una página o palabras que no se pudieron leer")
        palabras = [
            Palabra(html.unescape(t), float(a), float(b), float(c), float(d))
            for a, b, c, d, t in leidas
        ]
        paginas.append((float(cabecera.group(1)), palabras))
    return paginas


def unica(palabras: list[Palabra], texto: str, pagina: int) -> Palabra:
    encontradas = [p for p in palabras if p.texto == texto]
    if len(encontradas) != 1:
        fallar(f"p{pagina}: se esperaba un «{texto}» y hay {len(encontradas)}")
    return encontradas[0]


def separar(palabras: list[Palabra], pagina: int) -> tuple[list, list, list]:
    """Encabezado, texto y pie de una página."""
    ancla = unica(palabras, ANCLA_ENCABEZADO, pagina)
    marca_indesign = unica(palabras, ANCLA_MARCA, pagina)
    numeros = [
        p for p in palabras if p.texto == str(pagina) and p.y0 < marca_indesign.y0
    ]
    if not numeros:
        fallar(f"p{pagina}: no está el número de página en el pie")
    pie_y = max(p.y0 for p in numeros)  # el de más abajo, sin contar la marca
    encabezado = [p for p in palabras if p.y0 < ancla.y1]
    pie = [p for p in palabras if p.y0 >= pie_y]
    texto = [p for p in palabras if ancla.y1 <= p.y0 < pie_y]
    if not texto:
        fallar(f"p{pagina}: no hay texto entre el encabezado y el pie")
    return encabezado, texto, pie


def intervalos_x(palabras: list[Palabra]) -> list[tuple[float, float]]:
    """Tramos horizontales ocupados por alguna palabra (los que se tocan, unidos)."""
    tramos: list[list[float]] = []
    for x0, x1 in sorted((p.x0, p.x1) for p in palabras):
        if tramos and x0 <= tramos[-1][1]:
            tramos[-1][1] = max(tramos[-1][1], x1)
        else:
            tramos.append([x0, x1])
    return [(a, b) for a, b in tramos]


def mitad_del_hueco(fin: float, inicio: float, nombre: str) -> int:
    if inicio - fin < HUECO_MINIMO:
        fallar(
            f"hueco de {nombre} insuficiente: termina en {fin} y lo siguiente "
            f"empieza en {inicio} (mínimo {HUECO_MINIMO} pt)"
        )
    return round((fin + inicio) / 2)


def medir(paginas: dict[int, list[Palabra]]) -> tuple[dict, list[dict], dict]:
    """Recortes comunes, medidas de cada página y el texto de cada una."""
    textos: dict[int, list[Palabra]] = {}
    medidas = []
    for n, palabras in paginas.items():
        encabezado, textos[n], pie = separar(palabras, n)
        medidas.append(
            {
                "pagina": n,
                "fin_encabezado_y": max(p.y1 for p in encabezado),
                "inicio_texto_y": min(p.y0 for p in textos[n]),
                "fin_texto_y": max(p.y1 for p in textos[n]),
                "inicio_pie_y": min(p.y0 for p in pie),
            }
        )
    tramos = intervalos_x([p for t in textos.values() for p in t])
    if len(tramos) != 2:
        fallar(f"se esperaban 2 columnas y hay {len(tramos)} tramos: {tramos}")
    cortes = {
        "x_columnas": mitad_del_hueco(tramos[0][1], tramos[1][0], "columnas"),
        "y_superior": mitad_del_hueco(
            max(m["fin_encabezado_y"] for m in medidas),
            min(m["inicio_texto_y"] for m in medidas),
            "encabezado",
        ),
        "y_inferior": mitad_del_hueco(
            max(m["fin_texto_y"] for m in medidas),
            min(m["inicio_pie_y"] for m in medidas),
            "pie",
        ),
    }
    x = cortes["x_columnas"]
    for m in medidas:
        t = textos[m["pagina"]]
        # None: la página no tiene texto en esa columna (36: solo líneas en blanco)
        m["fin_izquierda_x"] = max((p.x1 for p in t if p.x1 <= x), default=None)
        m["inicio_derecha_x"] = min((p.x0 for p in t if p.x0 >= x), default=None)
    return cortes, medidas, textos


def marca(p: Palabra) -> str:
    """N: número de DBA; E: «Evidencias»; q: viñeta; J: «Ejemplo»; vacío: lo demás."""
    if RE_NUMERO_DBA.match(p.texto) and p.y1 - p.y0 > ALTO_MIN_NUMERO:
        return "N"
    return {"Evidencias": "E", "q": "q", "Ejemplo": "J"}.get(p.texto, "")


def controlar_orden(textos: dict[int, list[Palabra]], x: int) -> list[list[int]]:
    """Lee por columnas y comprueba la secuencia; devuelve las evidencias por DBA.

    El resultado es una lista por grupo de numeración (un grado): cada grupo empieza
    en el DBA 1 y trae el número de viñetas de cada DBA.
    """
    marcas: list[tuple[str, str]] = []
    for n in sorted(textos):
        for izquierda in (True, False):
            columna = [p for p in textos[n] if (p.x0 < x) == izquierda]
            for p in sorted(columna, key=lambda p: (p.y0, p.x0)):
                if marca(p):
                    marcas.append((marca(p), p.texto))
    secuencia = "".join(m for m, _ in marcas)
    if re.fullmatch(r"(NEq+J)+", secuencia) is None:
        fallar(f"orden de lectura roto; secuencia leída: {secuencia}")
    return agrupar_por_numeracion(marcas)


def agrupar_por_numeracion(marcas: list[tuple[str, str]]) -> list[list[int]]:
    """Viñetas por DBA, agrupados cada vez que la numeración vuelve a 1."""
    grupos: list[list[int]] = []
    for m, texto in marcas:
        if m == "N":
            numero = int(texto.rstrip("."))
            if numero == 1:
                grupos.append([])
            if not grupos or numero != len(grupos[-1]) + 1:
                fallar(f"numeración de DBA no consecutiva en el {texto}")
            grupos[-1].append(0)
        elif m == "q":
            grupos[-1][-1] += 1
    return grupos


def pagina_con_lineas(pdf: Path, pagina: int, ancho_pts: float, c: dict) -> list:
    """La página en RGB (filas de bytes) con los tres recortes en rojo."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "pagina"
        orden = ["pdftoppm", "-r", str(DPI_EVIDENCIA), "-f", str(pagina), "-l"]
        orden += [str(pagina), "-gray", "-singlefile", str(pdf), str(base)]
        ejecutar(orden)
        ancho, alto, grises = leer_pgm(base.with_suffix(".pgm").read_bytes())
    escala = DPI_EVIDENCIA / 72
    # las líneas solo valen si la imagen usa las mismas coordenadas que -bbox
    if abs(ancho - ancho_pts * escala) > 1:
        fallar(f"p{pagina}: la imagen ({ancho} px) no corresponde a {ancho_pts} pt")
    x, y0, y1 = (
        round(c[k] * escala) for k in ("x_columnas", "y_superior", "y_inferior")
    )
    rojo = b"\xff\x00\x00"
    filas = []
    for i, g in enumerate(grises):
        rgb = bytearray(3 * ancho)
        rgb[0::3], rgb[1::3], rgb[2::3] = g, g, g
        if y0 <= i <= y1:
            rgb[3 * x : 3 * (x + 2)] = rojo * 2
        filas.append(bytes(rgb))
    for y in (y0, y0 + 1, y1, y1 + 1):
        if y < alto:
            filas[y] = rojo * ancho
    return filas


def main() -> None:
    if CONFIG.exists():
        fallar(f"{CONFIG.name} ya existe; no se sobrescribe (puede estar verificado)")
    doc = documento_del_inventario(ID_DBA)
    pdf = pdf_verificado(doc)
    a, b = PAGINAS[0], PAGINAS[-1]
    orden = ["pdftotext", "-bbox", "-f", str(a), "-l", str(b), str(pdf), "-"]
    leidas = paginas_con_cajas(ejecutar(orden).stdout)
    if len(leidas) != len(PAGINAS):
        fallar(f"se leyeron {len(leidas)} páginas y se esperaban {len(PAGINAS)}")
    anchos = {n: ancho for n, (ancho, _) in zip(PAGINAS, leidas, strict=True)}
    paginas = {n: pal for n, (_, pal) in zip(PAGINAS, leidas, strict=True)}
    cortes, medidas, textos = medir(paginas)
    grupos = controlar_orden(textos, cortes["x_columnas"])
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    imagenes = []
    for n in PAGINAS:
        filas = pagina_con_lineas(pdf, n, anchos[n], cortes)
        escribir_png_rgb(EVIDENCIA / f"p{n}.png", filas)
        imagenes.append(filas)
    escribir_png_rgb(EVIDENCIA / "todas.png", hoja_de_contacto(imagenes))
    config = {
        "id": ID_DBA,
        "decision": "D60",
        "entrada": {"archivo": doc["ruta_local"], "sha256": doc["sha256"]},
        "pdftotext": version_pdftotext(),
        "unidades": "puntos PDF sobre la MediaBox, como los da pdftotext -bbox",
        "metodo": METODO,
        "paginas": [
            {
                "pagina": m["pagina"],
                **cortes,
                "verificado_por": "",
                "fecha": date.today().isoformat(),
                "medido": {k: v for k, v in m.items() if k != "pagina"},
            }
            for m in medidas
        ],
    }
    CONFIG.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"recortes: {cortes}")
    print(f"DBA por grupo de numeración: {[len(g) for g in grupos]}")
    print(f"evidencias por DBA: {grupos}")
    print(f"total: {sum(map(len, grupos))} DBA, {sum(map(sum, grupos))} evidencias")
    print(f"config: {CONFIG.relative_to(RAIZ_REPO)}")
    print(f"evidencia: {EVIDENCIA.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()
