# Instrucciones para el codificador · D58

Eres un codificador en una revisión sistemática sobre laboratorios virtuales de ciencias naturales. Tu tarea es aplicar un **libro de códigos cerrado** a 60 fichas de extracción. Otros codificadores hacen la misma tarea por separado; no conoces sus códigos ni debes buscarlos.

## Qué puedes leer (solo esto)
1. Este archivo (`LEEME_CODIFICADOR.md`).
2. `libro_codigos_v3.md`, completo, antes de codificar nada.
3. Los lotes de `lotes/` (`lote1.csv`, `lote2.csv`, `lote3.csv`): una fila por ficha, con `id_ciego` (X01…X60) y 19 campos de la ficha.

## Qué no puedes hacer
- Abrir cualquier otro archivo o carpeta, incluido el contenido de `salidas/` y el historial de git.
- Usar internet o buscar información sobre los estudios.
- Ejecutar código para decidir los códigos. Puedes escribir el archivo JSON de salida.

## Cómo codificar
1. Lee el libro v3 completo: escala 0/1, reglas, los criterios C01 a C09 y las listas «cuenta / no cuenta» de C05, C06 y C08.
2. Codifica **solo con lo que dice cada ficha**. Ante la duda entre 0 y 1, pon **0** (regla del libro).
3. Para cada ficha, los nueve criterios **C01 a C09, en ese orden**, cada uno con un código 0 o 1 y **una justificación de una sola línea**. No copies frases de la ficha.

## Orden de trabajo y salida
- Procesa `lote1.csv`, luego `lote2.csv` y luego `lote3.csv`.
- Al terminar **cada** lote, escribe de inmediato `salidas/<MODELO>_loteN.json` (N = 1, 2 o 3; `<MODELO>` es el nombre que te indicaron en el mensaje inicial). Solo JSON, sin texto alrededor, con exactamente las fichas de ese lote:

```json
{"modelo": "<identificador exacto del modelo que estás usando>",
 "lote": 1,
 "informes": {"X01": {"codigos": {"C01": 1, "C02": 0, "C03": 1, "C04": 0, "C05": 0, "C06": 0, "C07": 1, "C08": 0, "C09": 1},
                      "justificaciones": {"C01": "una línea", "C02": "una línea", "C03": "una línea", "C04": "una línea", "C05": "una línea", "C06": "una línea", "C07": "una línea", "C08": "una línea", "C09": "una línea"}}}}
```

- Si no sabes el identificador exacto de tu modelo, escribe el nombre que te muestra la herramienta y agrega `"modelo_incierto": true`.
- No modifiques un JSON ya escrito. Si te equivocas, avísalo al final en lugar de reescribirlo.

## Al terminar
Responde solo: «Terminé: lote1, lote2, lote3» y el identificador de tu modelo. No resumas ni comentes los resultados.
