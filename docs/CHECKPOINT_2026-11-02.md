# Checkpoint · 2 de noviembre de 2026

Estado del pipeline de la revisión sistemática (Tesis 04, PRISMA 2020) al cierre del Bloque 8. Documento de estado, no de resultados finales.

## 1. Estado del pipeline
- **Bloques 1 a 8 cerrados**, cada uno con su sección en `docs/PROCEDIMIENTO.md` y el flujograma (`docs/flujograma.mmd/.svg`) actualizado.
- **Decisiones D1 a D54** registradas en `docs/decisiones.md`.
- **PRISMA:** 196 informes / 193 estudios incluidos (5 informes excluidos por nivel de la población).
- **Codificación:** codificación asistida por IA con libro de códigos cerrado (libro v3, `claude-sonnet-5-5`, registro en `logs/codificacion_claude.jsonl`, local). Calibración del libro con el piloto de 5 y la muestra de 40; verificación humana de C05, C06 y C08 en 20 informes; revisión de discrepancias por el investigador con adopción de la definición operacional estricta (D51–D53).
- **Pruebas:** 187 pasan; ruff, gitleaks y pip-audit limpios. Último commit antes de este documento: `8b243f4`.

## 2. Resultados clave del Bloque 8 (D54)
Fuente: `outputs/tablas/marco_evidencia_v0.csv/.json`. Base 196 informes / 193 estudios; estudio «presente» si algún informe suyo lo tiene.

| Criterio | % informes presentes | % estudios presentes | % peso alto entre presentes (suma) |
|---|---|---|---|
| C01 | 94,4 | 94,8 | 16,4 |
| C02 | 82,7 | 82,9 | 18,1 |
| C03 | 82,7 | 83,4 | 17,4 |
| C04 | 75,0 | 75,1 | 18,6 |
| C05 | 39,3 | 39,9 | 15,6 |
| C06 | 12,2 | 12,4 | 20,8 |
| C07 | 58,7 | 59,6 | 13,9 |
| C08 | 21,9 | 22,3 | 27,9 |
| C09 | 70,9 | 72,0 | 13,7 |

- **Brecha en C05, C06 y C08:** son los criterios menos presentes (39 %, 12 % y 22 % de los informes). Su prevalencia depende del umbral: con la lectura amplia del investigador era 0,85–0,95 y con la definición estricta del libro v3 es la de la tabla (D52, D53). Se reporta siempre con esa nota de calibración.
- **Sin asociación presencia–efecto:** al comparar la dirección del efecto entre estudios con el criterio presente y ausente, la prueba exacta de Fisher (descriptiva, 45 pruebas, sin corrección) da una sola p < 0,05 (C01, «mixto», p = 0,015, con 10 estudios ausentes), cifra compatible con el azar. No hay base para atribuir diferencias de efecto a un criterio.
- **Peso de evidencia bajo:** entre los estudios con cada criterio presente, el peso alto (regla suma de D43) va de 13,7 % a 27,9 %; con la regla del mínimo es casi nulo (0 % a 4,7 %).
- **Límites:** descripción de cobertura y de evidencia disponible, no comparación de eficacia entre criterios; los criterios C01, C06 y C09 siguen en estado borrador.

## 3. Estructura del marco aprobada por Luis Fer (3 niveles)
| Nivel | Criterios |
|---|---|
| **Base** | C01, C02, C03 |
| **Calidad** | C04, C07, C09 |
| **Innovación** | C05, C06, C08 |

(C01 y C02 se etiquetaron «condición base» en D54 por ser casi universales; C06 «brecha de diseño».) Esta estructura aún no está volcada en `config/criterios_v0.yaml`; queda como paso pendiente.

## 4. Pendientes
1. **Aprobar los enunciados de C01, C06 y C09** (siguen en borrador).
2. **Sprint de fundamentación teórica:** autores clásicos y recientes que sostengan cada nivel y criterio del marco.
3. **Comparación curricular regional:** Colombia, Perú, Brasil, Argentina y México, partiendo de ERCE-UNESCO y PISA.
4. **Tabla de correspondencia** criterio ↔ competencia ICFES ↔ DBA ↔ PISA, con versión y fecha de cada documento fuente.
5. **Redacción de los resultados del OE2.**
6. **Entregable final:** procedimiento replicable + flujograma limpio (el documento de presentación del proceso se hace al cierre, no antes).
