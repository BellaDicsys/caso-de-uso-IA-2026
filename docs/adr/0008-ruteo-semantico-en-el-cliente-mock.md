# ADR-0008 — Ruteo semántico de herramientas en el cliente simulado

**Estado:** Aceptada — agosto 2026
**Reemplaza parcialmente:** el mecanismo de selección descrito en el ADR-0003

## Contexto

El `MockLLMClient` elegía la herramienta con una tabla de palabras clave por
herramienta, comparadas como prefijo de palabra. Funcionaba, pero tenía tres
problemas de fondo:

1. **Mantenimiento manual.** Cada herramienta nueva exigía inventar sus keywords,
   y el procedimiento estaba documentado como paso obligatorio en `CLAUDE.md`.
2. **Desincronización.** Las keywords vivían aparte de las descripciones que sí
   ve el modelo real, así que ambos niveles podían enrutar distinto sin que nada
   lo detectara.
3. **Errores de ruteo reales.** La auditoría adversarial documentó dos: *"¿cuál
   es el monto de la deuda…?"* caía en el analista de datos, y *"¿qué le
   **debe**mos entregar según el contrato?"* caía en finanzas por coincidencia de
   subcadena.

Y sobre todo era el flanco más atacable del proyecto: quien corriera la demo sin
clave de API veía funcionando un `if/else` sofisticado, no un ruteo por intención.

## Decisión

Reemplazar la tabla de palabras clave por un **router semántico** que reusa el
motor de recuperación del ADR-0007: BM25 más espacio latente, fusionados por RRF,
con las **descripciones de las herramientas como corpus**.

La observación que lo habilita es que *rutear es recuperar*: elegir la
herramienta correcta para una consulta es el mismo problema que elegir el pasaje
correcto, cambiando el corpus. No hizo falta un segundo mecanismo.

Se agrega `ToolDef.ejemplos`: enunciados típicos que deberían activar cada
herramienta. **No viajan a la Messages API** —el modelo real elige por la
descripción, y la API rechaza campos que no conoce— pero le dan al router el
material sobre el cual medir similitud. Son exactamente los ejemplos que
alimentarían a un clasificador de intención, y viven al lado de la herramienta
para que no se desincronicen de ella.

El contrato queda explícito en `ToolDef`: `to_api()` devuelve el esquema exacto
de la API y `to_esquema()` le suma los ejemplos. El agente pasa el enriquecido, y
`AnthropicLLMClient` filtra antes de llamar.

## Justificación

- **Elimina la crítica estructural.** El modo offline pasa a demostrar ruteo
  semántico real, no coincidencia de prefijos.
- **Un solo mecanismo.** El mismo motor sirve para documentos y para
  herramientas; se prueba dos veces y se mantiene una.
- **Las regresiones de la auditoría quedan cubiertas** con tests explícitos: el
  "monto de la deuda" va a finanzas y "qué debemos entregar" va a documental.
- **Sabe decir que no.** Si ningún término de la consulta aparece en el
  vocabulario de las herramientas, no elige ninguna. Las consultas ajenas dan
  cobertura exactamente cero.
- **Compite solo contra alternativas reales.** El router se construye por
  conjunto de herramientas ofrecido, así que respeta el RBAC: con rol `consulta`
  las delegaciones de finanzas y personal ni siquiera están en el índice.

## Consecuencias

- `CLAUDE.md` cambia: al agregar un dominio ya no se escriben keywords, se
  escriben enunciados de ejemplo. Es la misma cantidad de trabajo pero en
  lenguaje natural y verificable con un test de ruteo.
- El mock construye un índice por conjunto de herramientas y lo cachea. Son
  índices minúsculos (~13 descripciones); el costo es despreciable.
- Dos cheats del mock quedaron eliminados por el camino: `leer_documento`
  devolvía un nombre de archivo **fijo** —cualquier consulta que cayera ahí
  respondía con la política de vacaciones y parecía acertar por casualidad— y su
  descripción mencionaba ese archivo de ejemplo, lo que contaminaba el ruteo.
  Ahora el documento lo resuelve el motor de recuperación.
- El vocabulario vacío es sensible al dominio: *deber* se sacó de la lista porque
  "¿cuánto nos **debe** ese cliente?" es contenido, no soporte gramatical.
- **La limitación del ADR-0003 sigue vigente**: el mock resuelve una delegación
  por consulta. El ruteo mejoró; la capacidad de planificar multi-dominio sigue
  siendo exclusiva del modelo real.
