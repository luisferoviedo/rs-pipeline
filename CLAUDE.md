# Reglas para agentes — rs-pipeline (Tesis 04)

## Forma de trabajo
- Primero propone un plan y espera aprobación. Implementa en pasos pequeños. Un commit por paso.
- Explica cada decisión no obvia en lenguaje sencillo. Luis Fer debe poder explicar cada línea.
- Implementa SOLO lo pedido. Nada de abstracciones, clases base o refactors no solicitados.
- Commits con trailer: `Assisted-by: Claude Code`.
- Push a origin al cerrar cada bloque.

## Datos
- La carpeta del Google Drive es SOLO LECTURA. Nunca escribir, mover ni borrar ahí sin aprobación explícita.
- Nunca subir a git textos completos, PDF ni data/raw/.
- Los outputs con texto de los artículos (citas, fragmentos) no se versionan: van a `.gitignore`.
- Cada salida registra de qué archivo y versión viene (ruta + hash).

## Errores
- Prohibido `except:` / `except Exception: pass` y los valores por defecto que oculten fallas.
- Si falta una columna, un archivo o un ID, o un conteo no cuadra: el script FALLA con un mensaje claro.

## Dependencias y versiones
- PROHIBIDO agregar paquetes sin permiso. Si propones uno: nombre exacto, enlace a PyPI, versión y por qué hace falta.
- Versiones fijadas en requirements.txt. Python ≥3.10.
- Si no estás seguro de la API vigente (pandas, anthropic SDK, BERTopic), DETENTE y pregunta.

## Tests
- NO modifiques tests existentes para que pasen. Si un test parece incorrecto, DETENTE y explícalo.
- Los tests verifican números reales contra los CSV fuente, no "que no explote".

## API de Claude (solo para un uso futuro; no aplica a la codificación, D46)
- La llave solo en .env (en .gitignore). Nunca en código ni en logs.
- Cada llamada queda en logs/llm_calls.jsonl: modelo exacto, parámetros, hash de la entrada, respuesta cruda, tokens y fecha.
- Ninguna llamada a la API sin que Luis Fer apruebe el lote y el costo estimado.

## Codificación asistida por Claude Code (D46)
La codificación deductiva (piloto, muestra de 40 y los 196 informes) la hace Claude Code con la suscripción de Luis Fer, **no la API**.
- Cada informe codificado deja una línea en `logs/codificacion_claude.jsonl` con: fecha, modelo que se está usando (ID exacto), versión del libro de códigos (hash del YAML), `id_ciego`, hash de la ficha leída, los 9 códigos y la justificación de una línea por código.
- `logs/` sigue fuera de git (tiene justificaciones con contenido de fichas); a git va solo un resumen numérico.
- Se codifica por lotes (máximo 50 informes por sesión) y cada lote termina con commit.
- Nunca se recodifica sobre un registro anterior: un nuevo intento es una nueva línea con su fecha.

## Calidad
- Ruff (reglas E, F, B, S, BLE, TRY, C901 con máx. 10) antes de cada commit. pip-audit cada vez que cambie requirements.txt y antes de cada push.
- gitleaks en pre-commit.
- `ruff format` SOLO sobre los archivos modificados en el paso, listándolos uno por uno; nunca sobre carpetas (`src`, `tests`). Antes de cada commit, revisar `git status` y confirmar que solo cambiaron archivos del paso.

## Documentación
- `docs/PROCEDIMIENTO.md`: al cerrar cada bloque, añade su sección con este formato: Objetivo del paso · Entradas (archivo, versión, hash) · Proceso (qué hace el script en lenguaje sencillo y el comando exacto para ejecutarlo) · Decisiones aplicadas (enlaces a los D-xx de `docs/decisiones.md`) · Controles (qué verifica, cuándo falla, tests) · Salidas (archivo y dónde queda).
- `docs/flujograma.mmd` (Mermaid) y `docs/flujograma.svg`: flujograma tipo ingeniería del pipeline completo, con entradas (paralelogramos), procesos y scripts (rectángulos), decisiones y controles (rombos "¿cuadra?" → sí / no → falla), salidas (documentos) y la frontera Drive solo lectura / repositorio. Se actualizan al cerrar cada bloque.
- El documento final de presentación del proceso se hace al cierre del proceso, no antes.
