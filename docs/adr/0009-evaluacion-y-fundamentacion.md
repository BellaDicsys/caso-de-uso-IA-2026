# ADR-0009 — Arnés de evaluación y verificación de fundamentación

**Estado:** Aceptada — agosto 2026

## Contexto

Tras incorporar el motor de recuperación (ADR-0007) y el ruteo semántico
(ADR-0008), el proyecto tenía dos componentes cuya calidad no se podía afirmar
sin medirla. "La búsqueda mejoró" era una opinión respaldada por media docena de
consultas probadas a mano.

Y faltaba cubrir el modo de falla propio de un sistema agéntico sobre datos de
negocio. No es que razone mal: es que en el paso de **síntesis** —cuando el
modelo redacta la respuesta final a partir de lo que devolvieron las
herramientas— aparezca un número que ninguna herramienta informó. Un total mal
sumado, un porcentaje verosímil, una fecha corrida. Para quien lee es
indistinguible de un dato correcto.

## Decisión

Dos instrumentos, ambos sin modelo juez y sin red.

### 1. Conjunto etiquetado y métricas de recuperación

55 consultas escritas como las formularía una persona, con los documentos que las
responden: 51 del dominio y 4 ajenas. Se reportan cuatro métricas porque
responden preguntas distintas —recall@5 (¿entró en el contexto?), MRR (¿en qué
puesto?), nDCG@5 (¿cuán buena es la ordenación?)— más la **abstención**, que mide
la proporción de consultas ajenas ante las que el motor no devuelve nada.

Cada métrica tiene un umbral y CI falla si baja. Sin umbrales el reporte es un
número lindo que nadie mira.

### 2. Verificador de fundamentación

La formulación que hace el problema verificable: **toda afirmación cuantitativa
de la respuesta debe aparecer en la salida de alguna herramienta de esa misma
ejecución**. No se compara contra los datos crudos —el agente puede legítimamente
agregar, filtrar y ordenar— sino contra lo que efectivamente leyó.

Requiere saber qué devolvió cada herramienta, así que se agrega `trazas.py`: el
bucle agéntico emite eventos y quien quiera escucharlos abre un `capturar()`. Se
usa una variable de contexto para no contaminar la firma de `Agent.run()` ni la
de las herramientas, y porque el anidamiento se resuelve solo.

**Las delegaciones se excluyen de la evidencia.** Su resultado es la respuesta
redactada por otro agente; tomarla como prueba haría circular la verificación —el
texto del modelo se justificaría a sí mismo—, que es exactamente lo que hay que
evitar.

Todo escenario del set de evaluación pasa ahora por esta comprobación, además de
sus criterios.

## Justificación

- **Exacto y gratis.** Comparar cifras contra la evidencia es determinístico y
  cuesta microsegundos. Un modelo juez costaría dinero, latencia y
  no-determinismo, y habría que evaluar al juez.
- **Mide lo que se puede medir sin ambigüedad.** No juzga si la respuesta es
  *pertinente*, solo si es *fundada*. Son propiedades distintas y esta es
  objetiva.
- **El conjunto etiquetado documenta el criterio**, no solo el resultado: incluye
  paráfrasis deliberadas, casos ambiguos con más de un documento aceptable y
  consultas fuera de dominio.

## Consecuencias

- `enterprise-agents eval` corre escenarios, fundamentación y recuperación;
  `eval --recuperacion` mide solo el motor y **no necesita modelo**.
- CI ejecuta la evaluación completa en cada push.
- **El arnés ya se ganó el sueldo.** La primera hipótesis de mejora que se probó
  con él —recortar terminaciones de infinitivo, para conectar *subcontratar* con
  *subcontratación*— parecía obvia y resultó **neta negativa**: el acierto quedó
  igual y MRR y nDCG empeoraron (0,776 → 0,760 y 0,804 → 0,788). Se revirtió. Sin
  medición se habría incorporado por sensata.
- También se verificó empíricamente la afirmación del ADR-0007 sobre la constante
  de RRF: entre K=10 y K=100 las cuatro métricas no se mueven.
- Línea de base al momento de escribir esto: acierto@5 0,902 · recall@5 0,895 ·
  MRR 0,776 · nDCG@5 0,804 · abstención 1,000.
- Los umbrales se fijaron por debajo de esa línea para tolerar variación
  legítima del corpus sin dejar pasar una regresión real.
