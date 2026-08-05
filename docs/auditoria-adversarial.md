# Auditoría adversarial — Enterprise Agent Suite

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

## 4. Resultado

- **54 tests** al cierre de la auditoría (antes 49; hoy 94 tras sumar el versionado
  automático), con casos de regresión específicos para cada corrección
  de seguridad: bloqueo por intentos fallidos, atributos de la cookie, revocación
  de sesiones, validación del parámetro de fecha y aislamiento del rol `consulta`.
- **Cobertura 94 %**, con umbral del 85 % exigido en CI.
- Lint y formato limpios; verificación end-to-end en navegador de las cinco
  páginas tras el refactor.
