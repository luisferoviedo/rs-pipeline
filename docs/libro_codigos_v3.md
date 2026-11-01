# Libro de códigos v3 (D50)

Codificación deductiva de cada informe frente a cada criterio del marco v0: presencia (0/1).

## Escala (por informe y criterio)

- **0** = No aparece, o la ficha dice explícitamente que no se reporta o que no se documenta.
- **1** = Aparece: la ficha menciona el componente como parte de la actividad o del laboratorio, con o sin resultado.

## Reglas

- Codificar solo lo que dice la ficha; no completar con conocimiento propio.
- Ante duda entre 0 y 1, el 0.
- Un informe recibe un código por criterio (C01 a C09), siempre los nueve.
- «1» exige que la ficha mencione el componente. Si no lo menciona, o dice que no se reporta o no se documenta, es 0, aunque se pueda suponer que existía.
- No se codifica atribución: da igual si el estudio vincula el componente con un resultado, si el resultado es del paquete completo o si el grupo de comparación también tuvo el componente.
- Un dato descriptivo de contexto o de barrera (p. ej., el porcentaje de estudiantes sin internet en casa) cuenta como presencia (1).
- Los criterios C01, C06 y C09 siguen en borrador: se codifican igual y, si el enunciado no alcanza para decidir, se dice en la justificación de una línea.
- C05, C06 y C08 se deciden con su lista «cuenta / no cuenta»; si un caso no está en ninguna lista, se aplica la regla de duda (0).
- La corrección o los comentarios del docente o de pares se codifican en C04, no en C06.

## Campos de la ficha que se leen (en este orden)

`tema`, `nivel_norm`, `disciplina_norm`, `diseno`, `comparacion`, `oe1_hallazgo`, `oe1_condiciones`, `oe1_direccion_norm`, `oe2_herramienta`, `oe2_andamiaje`, `oe2_retroalimentacion`, `oe2_interactividad`, `oe2_dispositivo`, `oe2_conectividad`, `oe2_idioma_accesibilidad`, `oe2_costo_licencia`, `oe2_usabilidad_calidad`, `oe4_secuencia`, `oe4_rol_docente`

No se leen `oe2_criterios_candidatos` (inferencias del extractor) ni `lf_*` (notas de Luis Fer). Se quitan las marcas [F]/[I] y las citas de página.

## Criterios

### C01 · Mediación docente y participación activa del estudiante

- **Dimensión:** Acompañamiento y mediación pedagógica del aprendizaje
- **Enunciado:** El laboratorio virtual debe integrar sus funcionalidades tecnológicas con decisiones didácticas explícitas sobre su uso, de modo que el estudiante participe en un proceso guiado, autónomo y reflexivo, y no sea un usuario pasivo que solo ejecuta la simulación.
- **Estado:** borrador: revisar Luis Fer
- **Nota:** Casi universal en la muestra de 40 (D49); en el marco será una condición base (D50).

### C02 · Estructuración y secuenciación guiada de las experiencias de aprendizaje experimental.

- **Dimensión:** Estructuración didáctica y niveles de orientación de las actividades experimentales.
- **Enunciado:** El laboratorio virtual debe ofrecer experiencias experimentales organizadas mediante guías didácticas estructuradas, con objetivos de aprendizaje, fundamentación conceptual, procedimientos, preguntas orientadoras y actividades de análisis que conduzcan progresivamente al estudiante desde la exploración hasta la interpretación y comunicación de resultados.
- **Estado:** aprobado
- **Código 0.** Ejemplo: «Se usó el simulador en una clase; no reporta guía ni estructura de las actividades.»
- **Código 1.** Ejemplo: «Cada práctica tenía una guía con objetivo, pasos numerados y preguntas finales; no se analiza su efecto.»
- **Nota:** Casi universal en la muestra de 40 (D49); en el marco será una condición base (D50).

### C03 · Manipulación de variables y exploración experimental interactiva.

- **Dimensión:** Interactividad y manipulación experimental en entornos de simulación.
- **Enunciado:** El laboratorio virtual debe permitir que el estudiante manipule variables independientes, modifique las condiciones de los sistemas simulados, utilice instrumentos virtuales y observe los cambios producidos en los fenómenos estudiados, facilitando la exploración de relaciones entre variables, la formulación de predicciones y la comprensión de procesos científicos.
- **Estado:** aprobado

### C04 · Retroalimentación formativa y seguimiento del aprendizaje experimental.

- **Dimensión:** Retroalimentación y evaluación formativa en entornos de experimentación virtual.
- **Enunciado:** El laboratorio virtual debe favorecer procesos de retroalimentación continua mediante respuestas del sistema ante las acciones del estudiante, orientaciones del docente, espacios de discusión y mecanismos de autoevaluación que permitan reconocer avances, identificar errores y mejorar la comprensión de los fenómenos científicos.
- **Estado:** aprobado
- **Código 0.** Ejemplo: «Retroalimentación de la herramienta: no reporta.»
- **Código 1.** Ejemplo: «El docente comentaba las respuestas al cierre de la sesión; el estudio no evalúa ese comentario.»
- **Nota:** Incluye la corrección y los comentarios del docente o de pares (D50).

### C05 · Desarrollo de habilidades de medición, análisis e interpretación experimental.

- **Dimensión:** Desarrollo de habilidades científicas mediante la experimentación virtual.
- **Enunciado:** El laboratorio virtual debe proporcionar herramientas y escenarios que permitan al estudiante ejecutar procedimientos experimentales, utilizar instrumentos de medición, recolectar y procesar datos, representar resultados e interpretar fenómenos científicos para construir explicaciones sustentadas en evidencias.
- **Estado:** aprobado
- **Código 0.** Ejemplo: «Los estudiantes exploraban la simulación y explicaban lo que veían; no se menciona registro de datos.»
- **Código 1.** Ejemplo: «Los estudiantes registraban voltaje y corriente en una tabla y calculaban la resistencia.»
- **Cuenta (1):**
  - Mide con un instrumento, real o virtual.
  - Registra datos en una tabla o informe.
  - Calcula a partir de datos.
  - Grafica o interpreta datos propios.
  - Concluye a partir de datos.
- **No cuenta (0):**
  - Solo manipula parámetros y observa.
  - Ve gráficas que genera el sistema, sin que el estudiante las procese.
  - Responde preguntas conceptuales.
  - «Realiza experimentos» sin mención de datos.
  - Explica o argumenta con lo observado, sin datos registrados.

### C06 · Mecanismos multimodales de retroalimentación y visualización del aprendizaje experimental.

- **Dimensión:** Mecanismos multimodales de retroalimentación y visualización del aprendizaje experimental.
- **Enunciado:** El laboratorio virtual debe proporcionar información oportuna sobre las acciones y resultados del estudiante mediante representaciones visuales, gráficas y respuestas automáticas, facilitando la identificación de errores, la comprensión de los resultados y el mejoramiento progresivo del desempeño experimental.
- **Estado:** borrador: revisar Luis Fer
- **Código 0.** Ejemplo: «La simulación mostraba gráficas de energía mientras el estudiante cambiaba la altura.»
- **Código 1.** Ejemplo: «La simulación marcaba en rojo las conexiones erróneas del circuito y daba un puntaje.»
- **Cuenta (1):**
  - Un puntaje o una calificación automática del trabajo del estudiante.
  - Una marca o un mensaje de error del sistema.
  - Un indicador de estado o de riesgo que cambia según lo que hizo.
  - Un resultado del sistema que, según la ficha, deja ver el error del estudiante.
- **No cuenta (0):**
  - Tener gráficos, animaciones o representaciones del fenómeno.
  - La respuesta visual al mover parámetros.
  - «Retroalimentación inmediata» sin decir qué muestra.
  - La corrección o los comentarios del docente o de pares (van a C04).

### C07 · Usabilidad, eficiencia y fiabilidad del entorno tecnológico.

- **Dimensión:** Calidad técnica, usabilidad y condiciones de operación de los laboratorios virtuales.
- **Enunciado:** El laboratorio virtual debe garantizar una interacción sencilla, eficiente y confiable, considerando la facilidad de uso, los tiempos de respuesta, los requisitos técnicos, la compatibilidad con los dispositivos disponibles y su capacidad para mantener un funcionamiento adecuado ante diferentes condiciones de conectividad y demanda de usuarios.
- **Estado:** aprobado

### C08 · Verificación y contraste de resultados mediante representaciones experimentales.

- **Dimensión:** Contraste de resultados y validación del aprendizaje mediante la simulación.
- **Enunciado:** El laboratorio virtual debe permitir contrastar los resultados obtenidos por los estudiantes con representaciones, respuestas y soluciones de referencia, facilitando la verificación de procedimientos, la identificación de errores conceptuales y la autorregulación del aprendizaje mediante la interpretación de resultados y el diálogo pedagógico.
- **Estado:** aprobado
- **Código 0.** Ejemplo: «Los estudiantes observaban que la energía mecánica se conservaba.»
- **Código 1.** Ejemplo: «Los estudiantes calculaban el alcance a mano y lo comparaban con el que mostraba la simulación.»
- **Cuenta (1):**
  - Predice y luego compara con lo observado (predecir-observar-explicar).
  - Compara su resultado con un valor de referencia o con la teoría.
  - Compara su cálculo a mano con el simulador.
  - Verifica una ley o un resultado conocido.
  - Contrasta lo esperado con lo obtenido.
  - Recrea el montaje real para contrastarlo con la simulación.
- **No cuenta (0):**
  - Observar un principio (p. ej., la conservación) sin compararlo con nada.
  - Comparar grupos o condiciones del estudio: es diseño del estudio, no actividad del estudiante.
  - Que el docente corrija las respuestas (va a C04).
  - La clave de un cuestionario, salvo que la ficha diga que el estudiante contrasta su respuesta con ella.

### C09 · Acceso en contextos de baja conectividad y recursos limitados

- **Dimensión:** Accesibilidad y viabilidad tecnológica del laboratorio virtual
- **Enunciado:** El laboratorio virtual debe poder usarse con los dispositivos, la conectividad, el idioma y los recursos económicos disponibles en las instituciones, sin depender de equipos costosos, licencias pagas ni conexión permanente.
- **Estado:** borrador: revisar Luis Fer
- **Código 0.** Ejemplo: «Idioma, costo y conectividad: no reporta.»
- **Código 1.** Ejemplo: «La simulación se descargó para usarla sin conexión en el aula; no se informa si cambió la participación.»
