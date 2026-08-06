# ADR-0007 — Recuperación híbrida con embeddings derivados del corpus

**Estado:** Aceptada — agosto 2026

## Contexto

La gestión documental resolvía las consultas contando coincidencias de subcadena
por documento. Con tres documentos de ejemplo el método parecía razonable. Al
llevar el corpus a treinta documentos dejó de funcionar de forma evidente: la
consulta *"¿qué dice la política de vacaciones?"* devolvía primero
`politica-teletrabajo.md`, porque la palabra "política" aparece en casi todos los
títulos y el conteo la premiaba en todos por igual. El documento correcto ni
siquiera entraba en los primeros puestos.

Era además la debilidad estructural que señalaba la evaluación del proyecto: sin
búsqueda semántica, la parte documental de la suite demostraba el *patrón*
agéntico pero no capacidad real de recuperación.

La alternativa obvia —un modelo de embeddings preentrenado— tiene un costo que
para este repositorio es prohibitivo: rompe la propiedad de **clonar y correr sin
red**, agrega cientos de megabytes de pesos o una descarga en la instalación, y
vuelve no determinístico lo que hoy se puede testear en milisegundos.

## Decisión

Implementar un motor de recuperación híbrido propio, sin dependencias nuevas ni
pesos preentrenados, con los vectores semánticos **derivados del propio corpus**:

1. **Fragmentación** por sección de markdown con ventana deslizante y
   solapamiento, conservando la *migaja* (documento › sección) dentro del texto
   indexable.
2. **Preprocesamiento** en español: vocabulario vacío y recorte conservador de
   sufijos.
3. **Rama léxica**: BM25 Okapi.
4. **Rama semántica**: análisis semántico latente — matriz TF-IDF dispersa y SVD
   truncada por el método aleatorizado (proyección aleatoria, ortonormalización
   de Gram-Schmidt modificada, y eigendescomposición de Jacobi sobre la matriz
   chica resultante), todo sobre listas de Python.
5. **Fusión por Reciprocal Rank Fusion**, que combina puestos y no puntajes.
6. **Expansión de consulta** por trigramas de caracteres para los términos fuera
   de vocabulario, aplicada **una sola vez y a las dos ramas**.
7. **Compuerta de cobertura**: si el corpus no puede resolver al menos la mitad
   de los términos de la consulta, el motor no devuelve nada.

El contrato `Embedder` queda definido: una implementación sobre un modelo local
se enchufa sin tocar el motor, igual que `MockLLMClient` y `AnthropicLLMClient`
comparten `LLMClient`.

## Justificación

- **La semántica no requiere pesos ajenos.** La SVD captura co-ocurrencia: dos
  términos que nunca coinciden pero comparten contexto colapsan a la misma
  posición del espacio latente. El mecanismo es el truncamiento, y está cubierto
  por un test que lo demuestra.
- **Determinismo.** Semilla fija en la proyección aleatoria: el índice es
  reproducible y por lo tanto testeable. Un modelo externo no lo sería.
- **Híbrido y no solo semántico.** BM25 sigue ganando en consultas con términos
  precisos —acrónimos, códigos—, que son justo donde el espacio latente diluye la
  señal por baja frecuencia.
- **RRF en lugar de suma ponderada.** Los puntajes de BM25 y del coseno no son
  comparables ni estables entre consultas; normalizarlos exige constantes
  arbitrarias. El puesto siempre significa lo mismo.
- **La compuerta de cobertura es explicable.** No es un umbral sobre un puntaje
  sin unidades: es "qué fracción de lo que preguntaste existe en el corpus".

## Consecuencias

- El índice se construye al arrancar el proceso (~1,5 s para 190 fragmentos) y se
  cachea. En los tests se comparte por módulo.
- `buscar_documentos` pasó a devolver **pasajes** con su procedencia en lugar de
  una lista de nombres: el agente suele poder responder sin llamar a
  `leer_documento`.
- El espacio latente depende del corpus. Agregar documentos cambia los vectores,
  lo cual es correcto conceptualmente pero implica que las aserciones de
  recuperación son sensibles al contenido de `data/documentos/`.
- **No se implementó un índice aproximado (ANN).** Con 190 fragmentos la búsqueda
  exhaustiva es un producto interno por fragmento: agregar cuantización o un
  índice invertido de celdas sería más código, más superficie de error y **peor
  latencia** por el sobrecosto de la estructura. Se deja anotado el umbral a
  partir del cual valdría la pena (del orden de decenas de miles de fragmentos);
  implementarlo antes sería demostrar una técnica, no resolver un problema.
