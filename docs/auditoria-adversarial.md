# Auditoría adversarial — Enterprise Agent Suite

Este documento acumula **dos rondas** de revisión adversarial. La primera se hizo
sobre la suite original; la segunda, sobre los seis módulos que se agregaron
después (recuperación, ruteo semántico, evaluación, seguridad de agentes,
observabilidad y memoria conversacional).

Se conservan las dos con su fecha en lugar de reescribir la primera: el valor de
una auditoría está tanto en lo que encontró como en cuándo lo encontró, y una
segunda ronda que halla defectos *introducidos por las correcciones y las
funcionalidades nuevas* dice algo que una auditoría única no puede decir.

| Ronda | Alcance | Hallazgos corregidos |
|---|---|---|
| [1](#ronda-1--suite-original) | Suite original: agentes, API, auth, tablero, móvil | 7 de seguridad, 5 de correctitud, 8 de calidad, 7 de estabilidad |
| [2](#ronda-2--módulos-de-recuperación-evaluación-seguridad-y-memoria) | Los seis módulos nuevos | 4, uno de ellos de privacidad **introducido por una funcionalidad nueva** |

---

# Ronda 1 — suite original

**Fecha:** Agosto 2026 · **Método:** cuatro revisiones independientes en paralelo
(seguridad, correctitud, calidad/mantenibilidad, estabilidad/rendimiento), cada
una verificando sus hallazgos contra el código y los datos reales antes de
reportarlos. La revisión de seguridad se ejecutó dos veces con prompts distintos
para cross-validar.

Este documento registra qué se encontró, qué se corrigió y qué se aceptó como
riesgo conocido de una demo. Es parte de la entrega: una POC que se audita a sí
misma y documenta el resultado es más creíble que una que solo muestra la
funcionalidad.

---

## 1. Hallazgos corregidos

### Seguridad

| Hallazgo | Severidad | Corrección |
|---|---|---|
| **Open redirect** por el parámetro `next` del login (`?next=https://evil` redirigía fuera del sitio tras autenticar) | Alta | Se valida que el destino sea una ruta interna (empieza con `/`, no `//`, sin `:`), descartando también esquemas `javascript:`/`data:` |
| **Sesiones no revocadas** al eliminar un usuario: sus tokens seguían sirviendo hasta 8 h | Alta | `AlmacenSesiones.cerrar_de_usuario()`; la baja de un usuario cierra todas sus sesiones activas |
| **Sin límite de intentos** en el login (fuerza bruta y DoS de CPU por PBKDF2) | Alta | `ControlIntentos`: 5 fallos por usuario+IP bloquean 5 minutos (HTTP 429) |
| **Cookie de sesión sin `Secure`** (token interceptable sobre HTTP) | Media | `secure=True` por defecto; se desactiva solo con `ENTERPRISE_AGENTS_INSEGURO=1` para desarrollo local, y el servidor lo advierte al arrancar |
| **Bypass de autorización por el chat**: el rol `consulta` no veía el tablero, pero podía pedirle al asistente los mismos datos de finanzas y personal | Media | RBAC a nivel de herramienta: `crear_orquestador(..., rol)` no expone las delegaciones de finanzas ni personal al rol `consulta` |
| **`innerHTML` sin escapar** en tablero y gestión de usuarios (XSS latente si los datos dejaran de ser confiables) | Baja | Helper `esc()` en el design system, aplicado en todos los `innerHTML` con datos dinámicos |
| **`/salud` exponía el modelo** y si había API key configurada (fingerprinting) | Baja | El healthcheck público devuelve solo `{"estado": "ok"}` |

### Correctitud

| Hallazgo | Corrección |
|---|---|
| **Mis-ruteo por palabra clave**: "¿cuál es el **monto** de la **deuda**…?" iba al analista de datos y respondía con el resumen de ventas | Se depuraron las keywords por dominio y el ruteo pasó de subcadena libre a **prefijo de palabra** |
| **Falso positivo por subcadena**: "¿qué le **debe**mos entregar según el contrato?" (documental) se enrutaba a finanzas | Ídem: `debe` ya no matchea dentro de `debemos`; se eliminaron las keywords ambiguas |
| **Acrónimos descartados**: `buscar_documentos("SLA")` no encontraba nada porque el filtro exigía más de 3 letras, pese a que "sla" era keyword de ruteo | Umbral cambiado a ≥ 3 caracteres |
| **`buscar_por_habilidad("SQL")` matcheaba "PostgreSQL"** | Comparación por palabra completa (`coincide_palabra`) |
| **Default engañoso**: una habilidad desconocida (p. ej. "Java") devolvía perfiles de Python sin avisar | Se usa el término pedido en lugar de un default fijo |

### Calidad y mantenibilidad

- **`_normalizar` duplicada en 4 módulos** → módulo único `text.py` (`normalizar`, `tokenizar`, `coincide_palabra`, `coincide_prefijo`).
- **Lector de CSV reimplementado 4 veces** → `datos.leer_csv()` único, con caché invalidada por fecha de modificación.
- **Normalización inconsistente** entre finanzas (sin plegado de acentos) y personal (con plegado) → unificada.
- **CSS y JS de chat duplicados** entre la vista de escritorio y la móvil → componente compartido en el design system (`agregarMensaje`, `nodoEscribiendo`, estilos `.msj`/`.burbuja`).
- **Constante de sesión duplicada** (`8*60*60` hardcodeado en la cookie) → se reusa `DURACION_SESION_SEG`.
- **Versión inconsistente** (`0.3.0` en la API vs `0.1.0` en `pyproject`) → única fuente de verdad (`__version__`).
- **Accesibilidad**: `aria-label` en los botones solo-emoji (voz, envío, micrófono) y contraste de texto tenue subido a WCAG AA.
- **Documentación desactualizada** (conteo de tests) → sincronizada.

### Estabilidad y rendimiento

| Hallazgo | Corrección |
|---|---|
| **Orquestador reconstruido en cada request** de `/consultar` | Se construye uno por rol al iniciar la app y se reusa (los agentes son *stateless*) |
| **Páginas HTML leídas de disco en cada navegación** | Cacheadas en memoria (`lru_cache`); son inmutables en runtime |
| **Relectura de los CSV en cada llamada de herramienta y en cada refresco del tablero** | Caché por fecha de modificación en `datos.leer_csv()` |
| **Fuga de memoria**: las sesiones expiradas solo se limpiaban si alguien volvía a usarlas | Purga de expiradas al crear cada sesión |
| **Escritura del JSON de usuarios sin bloqueo** (dos altas concurrentes podían pisarse) | Escritura atómica (archivo temporal + `os.replace`) bajo lock |
| **`setInterval` del tablero**: seguía consultando con la pestaña oculta y podía solapar requests si el backend se ponía lento | Refresco encadenado con `setTimeout`, pausado con la Page Visibility API |
| **Parámetro `?hoy=` inválido** en `/metricas` devolvía HTTP 500 | Devuelve 422 con mensaje |

---

## 2. Controles verificados que ya estaban bien

Las revisiones confirmaron —intentando romperlos— que estos controles funcionan:

- **Path traversal** en `leer_documento`: `resolve()` + `is_relative_to()` + sufijo `.md` resiste `../`, rutas absolutas y symlinks.
- **XSS en las respuestas del asistente**: el chat pinta con `textContent`, así que ni una respuesta maliciosa del modelo (prompt injection) deriva en ejecución de HTML.
- **RBAC de endpoints**: no se halló ningún endpoint sensible sin verificación de rol.
- **Hashing y anti-enumeración**: PBKDF2 con salt por usuario, comparación en tiempo constante y costo uniforme cuando el usuario no existe.
- **Fijación de sesión**: el token siempre lo genera el servidor; nunca se acepta uno provisto por el cliente.
- **Aritmética del tablero**: los KPIs, alertas y series se verificaron dígito a dígito contra los CSV (no había el doble conteo que se sospechaba en el total vencido: los conjuntos son disjuntos).
- **Manejo de errores de herramienta**: el `except` amplio del bucle agéntico está justificado y cubierto por test — el error vuelve al modelo como `tool_result` para que se recupere.

---

## 3. Riesgos aceptados (propios de una demo sin deploy)

Se documentan explícitamente porque un despliegue real debe resolverlos:

1. **Credenciales de demostración en el repositorio.** `data/usuarios.json` trae tres
   usuarios con claves publicadas para que el proyecto sea evaluable sin setup.
   **Mitigación:** el servidor advierte al arrancar mientras esas claves sigan
   activas. En producción: rotarlas, no versionar el archivo y migrar al
   directorio corporativo (SSO/OIDC o passkeys).
2. **Sin token CSRF.** La defensa actual es `SameSite=Lax` + `Content-Type: application/json`,
   suficiente para el CSRF clásico pero sin profundidad. Producción debería sumar
   un token anti-CSRF o verificación de `Origin`.
3. **Estado en memoria (sesiones y control de intentos).** Funciona con un worker;
   con varios haría falta un almacén compartido (Redis).
4. **Endpoints síncronos.** En modo `live`, cada consulta ocupa un hilo mientras
   dura el bucle agéntico. Producción: SDK asíncrono y límite de concurrencia.
5. **El modo demo (mock) resuelve una sola delegación por consulta.** Las consultas
   multi-dominio solo las resuelve el modelo real (`--live`); queda anotado en el
   docstring del mock y en el ADR-0003.

---

## 4. Resultado de la ronda 1

- **54 tests** al cierre de la auditoría (antes 49), con casos de regresión
  específicos para cada corrección de seguridad: bloqueo por intentos fallidos,
  atributos de la cookie, revocación de sesiones, validación del parámetro de
  fecha y aislamiento del rol `consulta`.
- **Cobertura 94 %**, con umbral del 85 % exigido en CI.
- Lint y formato limpios; verificación end-to-end en navegador de las cinco
  páginas tras el refactor.

---

# Ronda 2 — módulos de recuperación, evaluación, seguridad y memoria

**Fecha:** Agosto 2026, tras incorporar seis módulos · **Método:** revisión
dirigida a las superficies nuevas, con verificación ejecutable de cada sospecha
antes de darla por cierta. Todo hallazgo confirmado se corrigió y quedó cubierto
por un test de regresión.

El criterio fue mirar lo que **nadie había mirado**: la primera ronda revisó el
sistema desde el usuario y desde los datos de entrada, pero los módulos nuevos
agregaron tres superficies que no existían entonces —un índice construido en
caliente, un registro de todo lo que se consulta, y estado conversacional por
sesión.

## 1. Hallazgos corregidos

### El registro de trazas exponía las consultas de otros usuarios

**Severidad: alta.** Es el hallazgo importante de esta ronda, y es un defecto
**introducido por una funcionalidad nueva**: el visor de observabilidad.

El registro era global y `/trazas/api` solo verificaba el rol. Cualquier usuario
con rol `gestor` veía la consulta de cualquier otro, con la salida completa de
las herramientas. Un empleado preguntando *"¿cuántos días de vacaciones me
corresponden?"* aparecía en el visor de su jefe.

Verificado con dos sesiones simultáneas antes de corregir:

```
consultas visibles para el gestor: ['¿cuántos días de vacaciones me corresponden?']
¿ve la consulta del empleado?: True
```

**Corrección:** cada traza registra a su autor y el visor devuelve solo las
propias. El rol `admin` sigue viendo todas —es una capacidad de administración
legítima— pero la respuesta lo declara explícitamente en un campo `alcance`, y el
test lo verifica. Ver *todo* no puede ser un efecto lateral silencioso de tener
un rol.

Es la misma clase de error que la ronda 1 encontró en el chat: un control de
acceso pensado a nivel de *página* y no a nivel de *dato*.

### Fuga de memoria en las conversaciones

**Severidad: media.** Las conversaciones se guardaban por token de sesión y solo
se borraban en `/salir`. Una sesión que expiraba a las 8 horas, o un navegador
que se cerraba sin desloguear, dejaba su entrada para siempre.

Es **exactamente la misma fuga** que la ronda 1 había encontrado en el almacén de
sesiones —"las sesiones expiradas solo se limpiaban si alguien volvía a usarlas"—
repetida en un módulo nuevo por no haber mirado el hallazgo anterior al escribirlo.

**Corrección:** purga de conversaciones huérfanas al crear cada conversación, con
el mismo criterio que ya usaba el almacén de sesiones.

### El índice documental no se invalidaba nunca

**Severidad: baja**, pero es una inconsistencia interna que confunde. El motor de
recuperación se cacheaba con `lru_cache` perpetuo, mientras que la lectura de CSV
invalida por fecha de modificación. Resultado: editar `ventas.csv` con el
servidor levantado se reflejaba en caliente, y editar un documento **no**. Dos
comportamientos distintos para el mismo gesto dentro de la misma aplicación, que
es peor que cualquiera de los dos por separado.

**Corrección:** el motor se reconstruye si cambia la firma temporal del corpus,
alineado con el resto del proyecto.

### Colisión de nombres entre módulo y función

**Severidad: baja.** El módulo `recuperacion/motor.py` exportaba una función
`motor()`, así que `enterprise_agents.recuperacion.motor` resolvía a la función y
**ocultaba el módulo**. Lo descubrió un test que intentaba importar el módulo para
manipular su caché.

**Corrección:** la función pasó a llamarse `motor_por_defecto()`.

## 2. Verificado y correcto

Se intentó romper esto sin éxito:

- **Determinismo del índice.** La SVD usa semilla fija: dos construcciones sobre
  el mismo corpus dan exactamente los mismos vectores, y hay un test que lo
  afirma. Sin esto las métricas de recuperación no serían comparables entre
  corridas.
- **Aislamiento de la memoria entre sesiones.** Dos sesiones concurrentes no
  comparten conversación, y salir la descarta.
- **La evidencia de fundamentación no es circular.** Las delegaciones se excluyen
  a propósito: si el texto redactado por un especialista contara como evidencia,
  el modelo se estaría justificando a sí mismo.
- **El saneamiento se aplica en las dos herramientas documentales**, no solo en
  la búsqueda: `leer_documento` también envuelve y neutraliza.
- **El escape del delimitador resiste.** Un documento que contiene la marca de
  cierre no logra salir del bloque; el test cuenta que la marca aparezca
  exactamente una vez.
- **La contextualización no desvía consultas de otro tema.** Está cubierto por
  test tras un fallo real durante el desarrollo (ver más abajo).

## 3. Límites declarados de los módulos nuevos

Se listan porque son las preguntas que corresponde hacerle a este código:

1. **La suite de inyección no prueba que el modelo obedezca.** Verifica las tres
   capas que son código —RBAC por herramienta, solo lectura, saneamiento— y
   declara explícitamente que la cuarta, la obediencia del modelo a la
   delimitación, requiere `--live`. Un informe de seguridad que afirma más de lo
   que probó vale menos que uno que declara su alcance.
2. **El detector de inyecciones es un filtro de superficie.** Un documento del
   corpus de ataques está redactado a propósito sin marcadores reconocibles y
   ningún patrón lo detecta; hay un test que lo afirma. Está ahí para justificar
   que la delimitación se aplique siempre, se detecte algo o no. Una inyección
   partida en dos líneas tampoco la detecta el análisis línea por línea.
3. **La comprobación de "solo lectura" es por nombre de herramienta.** Una
   herramienta de escritura llamada, por ejemplo, `emitir_factura` pasaría el
   control. Es una heurística de convención, no una garantía del sistema de
   tipos.
4. **El conteo de tokens es una estimación.** El exacto lo define el tokenizador
   del proveedor. Sirve para comparar consultas entre sí y detectar una que se
   fue de escala, no como medida de facturación, y así está etiquetado en toda la
   interfaz.
5. **Las trazas y las conversaciones viven en memoria.** Se pierden al reiniciar
   y no funcionarían con varios workers. Es el mismo riesgo aceptado que las
   sesiones, y en producción se reemplaza por el sistema de trazas de la
   organización, no por una base local.
6. **La contextualización de repreguntas es una heurística de superficie.** Una
   referencia a dos turnos atrás, o que dependa de la *respuesta* y no de la
   pregunta anterior, no la resuelve. El modelo real sí, porque recibe el
   historial completo.

## 4. Defectos encontrados durante el desarrollo por la propia instrumentación

No son hallazgos de la auditoría sino de las herramientas construidas en el
camino. Se registran porque muestran que los instrumentos funcionan:

| Qué lo encontró | Defecto |
|---|---|
| El arnés de evaluación | Una mejora "obvia" del recortador de sufijos resultó **neta negativa**: acierto igual, MRR 0,776 → 0,760 y nDCG 0,804 → 0,788. Se revirtió. Sin medición se habría incorporado por sensata. |
| El conjunto etiquetado | El recuperador **siempre devolvía su top-k**: *"blockchain cuántico"* recibía cuatro pasajes con total confianza. Se agregó la compuerta de cobertura. |
| Los tests del ruteo semántico | El mock devolvía un **nombre de archivo fijo** en `leer_documento`: cualquier consulta que cayera ahí respondía con la política de vacaciones y parecía acertar por casualidad. |
| Los tests de trazas | Los errores de herramienta **no quedaban marcados**: el bucle agéntico atrapa la excepción a propósito, así que la traza nunca la veía propagarse. |
| Los tests de memoria | El umbral de autosuficiencia estaba mal calibrado: *"¿qué dice la política de vacaciones?"* se clasificaba como repregunta y **un cambio de tema volvía al tema anterior**. |

## 5. Resultado de la ronda 2

- **305 tests** (eran 96 antes de los módulos nuevos), con regresión explícita
  para cada uno de los cuatro hallazgos: aislamiento de trazas por usuario,
  alcance declarado para el admin, purga de conversaciones huérfanas e
  invalidación del índice documental.
- **Cobertura 95 %**, umbral del 85 % en CI.
- CI ejecuta además la evaluación completa (escenarios, fundamentación y métricas
  de recuperación con umbrales) y la suite de inyección de prompt.
- Lint y formato limpios; verificación end-to-end en navegador de las seis
  páginas.

## 6. Lo que queda sin verificar

Honestidad sobre el alcance: **todo lo que depende del modelo real está sin
probar en este repositorio**, porque no hay clave de API en el entorno donde se
construyó. Concretamente:

- Que el modelo respete la delimitación del contenido recuperado.
- Que resuelva consultas multi-dominio, que el cliente simulado no cubre.
- Que la contextualización de repreguntas sea innecesaria con historial completo.

Se cierra corriendo `enterprise-agents eval --live` y
`enterprise-agents seguridad --live` con una clave, y versionando el resultado.
