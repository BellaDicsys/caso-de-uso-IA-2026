# Especificaciones técnicas — Enterprise Agent Suite

**Versión:** 2.0 — Agosto 2026
**Proyecto:** Caso de uso IA 2026 — Suite agéntica de gestión empresarial

---

## 1. Stack tecnológico

| Componente | Tecnología | Versión / Detalle |
|---|---|---|
| Lenguaje | Python | ≥ 3.10 (probado en 3.10 y 3.12 en CI) |
| Modelo de IA | Claude (Anthropic) | `claude-opus-5` por defecto, configurable |
| SDK | `anthropic` (oficial) | ≥ 0.116.0 — **única dependencia de runtime del núcleo** |
| API HTTP (opcional) | FastAPI + uvicorn | extra `[api]`; sirve REST + páginas web |
| Recuperación | propia (`recuperacion/`) | BM25 + espacio latente por SVD del corpus, fusión RRF; **sin dependencias ni pesos preentrenados** |
| Evaluación | propia (`evaluacion/`) | métricas de recuperación + verificador de fundamentación |
| Seguridad de agentes | propia (`seguridad/`) | detección y saneamiento de inyección de prompt |
| Observabilidad | propia (`trazas.py`, `tokens.py`) | árbol de spans, estimación de tokens |
| Memoria conversacional | propia (`memoria.py`) | presupuesto de contexto y compactación extractiva |
| Empaquetado | `pyproject.toml` (setuptools) | layout `src/`, versión dinámica, consola `enterprise-agents` |
| Testing | pytest + pytest-cov | ≥ 8.0 — 305 tests, cobertura 95 % (umbral 85 % en CI) |
| Calidad de código | ruff (lint + formato) | reglas E, F, W, I, N, UP, B, SIM; línea 100 |
| CI/CD | GitHub Actions | lint, tests, demo, **evaluación completa** y **suite de seguridad** en cada push |
| Versionado | propio (`versionado.py`) | semver derivado de Conventional Commits; tag, changelog y release en CI |

**Sin frameworks de orquestación** (LangChain, CrewAI, etc.): la orquestación se
implementa directamente sobre la Messages API con *tool use* (ADR-0002).

**Sin bibliotecas científicas ni modelos de embeddings.** Toda la maquinaria de
recuperación —incluida la descomposición SVD— está sobre la biblioteca estándar.
Es una decisión, no una carencia: preserva la propiedad de clonar y correr sin red
y mantiene el sistema determinístico y testeable (ADR-0007).

## 2. Arquitectura de módulos

```
src/enterprise_agents/
├── config.py             # Settings (env vars), rutas de datos, modelo default
├── text.py               # Normalización compartida (acentos, palabra, prefijo)
├── datos.py              # Lector único de CSV con caché por fecha de modificación
├── cli.py                # demo / ask / eval / seguridad / serve / version
├── api.py                # API HTTP (FastAPI) y páginas protegidas por sesión
├── auth.py               # Usuarios, sesiones, RBAC, control de intentos
├── metrics.py            # KPIs y alertas tempranas del tablero
├── evals.py              # Escenarios de negocio con criterios verificables
├── versionado.py         # Conventional Commits → semver + changelog + release
├── trazas.py             # Trazas jerárquicas de ejecución (spans, tiempos, tokens)
├── tokens.py             # Estimador de tokens sin llamadas externas
├── registro.py           # Buffer en memoria de las últimas trazas
├── memoria.py            # Memoria conversacional: presupuesto, compactación, contexto
├── orchestrator.py       # crear_orquestador(): agente coordinador con RBAC
├── agents/
│   ├── base.py           # class Agent: bucle agéntico común
│   └── specialists.py    # Fábricas de los 4 especialistas + system prompts
├── tools/
│   ├── base.py           # ToolDef: esquema JSON + handler + ejemplos de intención
│   ├── analytics.py      # resumen_ventas(), avance_proyectos()
│   ├── finance.py        # estado_cobranzas(), facturas_vencidas(), deuda_por_cliente()
│   ├── documents.py      # buscar_documentos(), leer_documento()
│   └── hr.py             # buscar_por_habilidad(), disponibilidad_equipo()
├── recuperacion/
│   ├── terminos.py       # Vocabulario vacío y recorte de sufijos en español
│   ├── fragmentos.py     # Fragmentación por sección con solapamiento y migaja
│   ├── lexico.py         # BM25 Okapi
│   ├── algebra.py        # Álgebra mínima: Gram-Schmidt, Jacobi, dispersa×densa
│   ├── vectorial.py      # TF-IDF + SVD aleatorizada + contrato Embedder
│   └── motor.py          # Fusión RRF, expansión de consulta, compuerta de cobertura
├── evaluacion/
│   ├── metricas.py       # recall@k, MRR, nDCG@k (funciones puras)
│   ├── conjuntos.py      # 55 consultas etiquetadas, con criterio documentado
│   ├── arnes.py          # Corrida, reporte y umbrales de aceptación
│   └── fundamentacion.py # Verificador de cifras inventadas
├── seguridad/
│   ├── deteccion.py      # 6 categorías de inyección de prompt
│   ├── saneamiento.py    # Delimitación, escape y neutralización marcada
│   └── ataques.py        # Suite de ataques + defensas estructurales
├── llm/
│   ├── base.py           # Protocolo LLMClient + LLMReply + ToolCall
│   ├── anthropic_client.py  # Cliente real (Messages API)
│   ├── mock_client.py       # Cliente determinístico offline
│   └── router.py            # Ruteo semántico de herramientas
└── static/               # DS propio (ds.css/ds.js) + 6 páginas
```

### 2.1 Contratos internos

**`LLMClient` (protocolo)** — contrato único entre bucle agéntico y proveedor:

```python
def complete(*, system: str,
             messages: list[dict],      # formato Messages API de Anthropic
             tools: list[dict]) -> LLMReply
```

**`LLMReply`** — respuesta normalizada: `content` (bloques dict), `stop_reason`,
propiedades derivadas `text` y `tool_calls`.

**`ToolDef`** — herramienta invocable: `name`, `description` (incluye el criterio
de *cuándo* usarla), `input_schema` (JSON Schema), `handler` (callable → `str`) y
`ejemplos` (enunciados típicos que deberían activarla).

Dos serializaciones distintas, y la diferencia es deliberada:

| Método | Qué produce | Quién lo consume |
|---|---|---|
| `to_api()` | El esquema **exacto** que acepta la Messages API | `AnthropicLLMClient` |
| `to_esquema()` | `to_api()` más los `ejemplos` | El bucle agéntico → ambos clientes |

Los ejemplos no viajan al modelo real —la API rechaza campos que no conoce y el
modelo elige por la descripción— pero le dan al cliente simulado el material sobre
el cual medir similitud. `AnthropicLLMClient` filtra antes de llamar, así que el
contrato queda explícito en un solo lugar en vez de repartido entre los clientes.

**`Embedder` (protocolo)** — contrato de codificación a vectores densos:

```python
@property
def dimension(self) -> int: ...
def codificar(self, texto: str) -> list[float]: ...
```

La implementación por defecto (`IndiceSemantico`) no necesita nada externo. Una
que envuelva un modelo local o remoto se enchufa sin tocar el motor, con la misma
lógica con la que `MockLLMClient` y `AnthropicLLMClient` comparten `LLMClient`.

### 2.2 Bucle agéntico (`agents/base.py`)

Algoritmo por consulta (idéntico para orquestador y especialistas):

1. `messages = [*historial, {"role": "user", "content": tarea}]`
2. Llamar `llm.complete(system, messages, tools)`.
3. Si `stop_reason != "tool_use"` → devolver el texto (fin).
4. Si pide herramientas: anexar el turno assistant completo al historial,
   ejecutar **todas** las llamadas y devolver los `tool_result` en **un único**
   mensaje `user` (requisito de la API para tool use en paralelo).
5. Repetir desde (2) hasta `max_iterations` (default 8, configurable).
6. Si se agota el límite → mensaje de corte controlado (nunca bucle infinito).

`historial` solo lo recibe el orquestador. Los especialistas siguen recibiendo
tareas autocontenidas y por lo tanto siguen siendo *stateless*, que es lo que
permite construirlos una vez y reusarlos entre requests.

Manejo de errores de herramienta: la excepción se captura, se loguea y vuelve al
modelo como `tool_result` con `is_error: true` para que pueda recuperarse. Como
**no se propaga**, el llamador marca el error explícitamente en el buzón de la
traza; si no, los fallos no quedarían registrados (ver ADR-0011).

### 2.3 Integración con la API de Claude (`anthropic_client.py`)

- Endpoint: `POST /v1/messages` vía SDK oficial (`client.messages.create`).
- `max_tokens = 4096` por turno (respuestas de gestión, no generación larga).
- **Razonamiento adaptativo** activo por defecto en Opus 5 (no se envía `thinking`).
- **Prompt caching**: el system prompt de cada agente lleva
  `cache_control: {"type": "ephemeral"}` — los turnos siguientes del bucle leen el
  prefijo cacheado (~90 % menos costo sobre esa porción).
- **Manejo de `stop_reason == "refusal"`**: la API puede declinar con HTTP 200;
  se chequea antes de leer `content` y se devuelve un mensaje controlado.
- **Bloques de thinking**: se serializan con `model_dump()` y se reenvían intactos
  en los turnos siguientes (requisito de la API).
- **Filtrado de esquemas**: se descartan los campos que agrega `to_esquema()`.
- Credenciales: resueltas por el SDK desde el entorno; nunca se hardcodean.

### 2.4 Cliente mock y ruteo semántico (`mock_client.py`, `router.py`)

Simulación determinística para demo offline y tests. **La selección de herramienta
ya no es por palabras clave**: el router compara la consulta contra el *texto de
intención* de cada herramienta —nombre, descripción, ejemplos y descripciones de
sus argumentos— reusando el mismo motor híbrido de `recuperacion/`.

La observación que lo habilita es que **rutear es recuperar**: elegir la
herramienta correcta para una consulta es el mismo problema que elegir el pasaje
correcto, con las descripciones como corpus.

- **Un índice por conjunto de herramientas ofrecido**, cacheado. Como el rol
  recorta qué delegaciones existen, el router respeta el RBAC por construcción:
  compite solo contra alternativas reales.
- **Abstención**: si ningún término de la consulta aparece en el vocabulario de
  las herramientas, no elige ninguna.
- **Contextualización**: una repregunta se completa con los términos del turno
  anterior antes de rutear, y la tarea que se delega va contextualizada —el
  esquema de la delegación pide una tarea "autocontenida con todo el contexto".
- **Síntesis**: cuando el último mensaje contiene `tool_result`, devuelve su
  contenido como respuesta final (`end_turn`).

Produce mensajes en el formato de la Messages API, así que ejercita exactamente el
mismo bucle que el cliente real. **Limitación vigente**: resuelve una delegación
por consulta; las multi-dominio requieren el modelo real (ADR-0003).

### 2.5 Motor de recuperación (`recuperacion/`)

Pipeline por consulta:

| Paso | Qué hace |
|---|---|
| Fragmentación | Corta por sección de markdown con ventana deslizante y solapamiento, conservando la migaja *documento › sección* dentro del texto indexable |
| Preprocesamiento | Descarta vocabulario vacío del español y recorta sufijos nominales de forma conservadora |
| Expansión | Lleva los términos fuera de vocabulario a su forma del corpus por trigramas de caracteres, **una vez y para ambas ramas** |
| Compuerta de cobertura | Si el corpus no resuelve al menos la mitad de la consulta, no devuelve nada |
| Rama léxica | BM25 Okapi (k1 = 1.5, b = 0.75) |
| Rama semántica | TF-IDF disperso → SVD truncada de rango 96 por método aleatorizado → coseno |
| Fusión | Reciprocal Rank Fusion con K = 60, que combina **puestos y no puntajes** |

La SVD aleatorizada sigue el método de Halko-Martinsson-Tropp: proyección
aleatoria con semilla fija, ortonormalización por Gram-Schmidt modificado y
eigendescomposición de Jacobi sobre la matriz chica resultante. La semilla fija es
lo que hace el índice reproducible, y por lo tanto lo que hace comparables las
métricas entre corridas.

El índice se reconstruye solo si cambia la firma temporal del corpus, con el mismo
criterio que `datos.leer_csv()`.

### 2.6 Trazas y memoria (`trazas.py`, `memoria.py`)

**Trazas.** El bucle emite eventos y quien quiera escucharlos abre un `capturar()`;
fuera de una captura no cuesta nada. Se usa una variable de contexto para no
contaminar la firma de `Agent.run()` ni la de las herramientas. Cada span conoce a
su padre y **se registra al entrar, no al salir**: si se agregara al final, una
herramienta anidada quedaría antes que la delegación que la contiene y el árbol
saldría invertido.

**Memoria.** Historial por sesión con presupuesto de tokens. Al superarlo, los
turnos viejos se compactan y los recientes quedan intactos. El resumen es
**extractivo** —selecciona oraciones existentes— por seguridad: uno generativo
podría introducir afirmaciones que ninguna herramienta produjo, justo lo que el
verificador de fundamentación existe para impedir.

## 3. Configuración

| Variable de entorno | Default | Efecto |
|---|---|---|
| `ANTHROPIC_API_KEY` | (vacía) | Si está definida → modo live; si no → modo mock |
| `ENTERPRISE_AGENTS_MODEL` | `claude-opus-5` | Modelo a usar en modo live |
| `ENTERPRISE_AGENTS_MAX_ITERATIONS` | `8` | Tope de iteraciones del bucle por consulta |
| `ENTERPRISE_AGENTS_INSEGURO` | (vacía) | `1` desactiva el atributo `Secure` de la cookie (solo desarrollo local; el servidor lo advierte) |

Plantilla en `.env.example`; `.env` está en `.gitignore`.

## 4. Seguridad

### 4.1 Control de acceso

- **RBAC a nivel de herramienta.** El rol no solo define qué páginas se ven:
  `crear_orquestador(..., rol)` no expone las delegaciones de finanzas ni personal
  al rol `consulta`. El chat no puede ser una vía alternativa a lo que el tablero
  reserva.
- **Aislamiento por dato, no solo por página.** Las trazas se filtran por usuario;
  el rol admin ve todas y la respuesta lo declara en un campo `alcance`.
- **Sesiones**: PBKDF2-HMAC-SHA256 con 200 000 iteraciones y salt por usuario,
  cookie `HttpOnly` + `SameSite=Lax` + `Secure`, comparación en tiempo constante,
  bloqueo por intentos fallidos y revocación efectiva al dar de baja un usuario.

### 4.2 Entrada no confiable

Todo texto documental que llega al modelo pasa por `seguridad.sanear()`:

1. **Delimitación siempre**, se detecte algo o no: el contenido viaja envuelto en
   un bloque marcado con una advertencia de que es dato y no instrucciones. Es la
   única capa que cubre las inyecciones que el detector no reconoce.
2. **Escape del delimitador**: sin esto la capa anterior sería decorativa —
   bastaría escribir la marca en el documento para salir del bloque.
3. **Neutralización marcada**: las líneas señaladas se reemplazan por una marca
   visible con su categoría, nunca por un borrado silencioso.

Seis categorías detectadas: anulación de instrucciones, suplantación de bloque de
sistema, cambio de rol, exfiltración, abuso de herramientas y autoridad falsa.

### 4.3 Validación y minimización

- **Path traversal**: `leer_documento` resuelve la ruta y verifica que quede
  dentro de `data/documentos/` con extensión `.md`, con test que lo demuestra.
- **Sin acceso directo del modelo a datos o filesystem**: siempre media una
  función con contrato explícito.
- **Solo lectura**: ninguna herramienta escribe, borra ni envía datos afuera, así
  que una instrucción inyectada no tiene efecto que provocar.
- **Límite de iteraciones** en todos los bucles.
- **Minimización en RRHH**: el prompt del gestor de personal restringe la
  información a rol/habilidades/disponibilidad y prohíbe especular sobre desempeño.
- **Sin secretos en el repo**: solo variables de entorno; datos 100 % sintéticos.

## 5. Testing y calidad

| Suite | Archivos | Qué verifica |
|---|---|---|
| Herramientas de dominio | `test_tools_*.py` (4) | Cálculos, ordenamientos, umbrales, alertas de riesgo, path traversal |
| Integración agéntica | `test_orchestrator.py`, `test_evals.py` | Flujo orquestador→especialista→herramienta→síntesis; errores como `tool_result`; corte por iteraciones; fuera de dominio |
| API y web | `test_api.py`, `test_auth.py`, `test_metrics.py` | Autenticación, RBAC, aislamiento de trazas, memoria por sesión, validación de entrada, KPIs |
| Recuperación | `test_recuperacion.py` | Fragmentación, BM25, álgebra, determinismo de la SVD, fusión, abstención, invalidación del índice |
| Ruteo | `test_router.py` | Delegación correcta por dominio, regresiones de mis-ruteo de la auditoría, respeto del RBAC |
| Evaluación | `test_evaluacion.py` | Métricas, interpretación de formatos numéricos, fundamentación, umbrales |
| Seguridad | `test_seguridad.py` | Seis categorías de inyección, escape del delimitador, defensas estructurales |
| Observabilidad | `test_trazas.py` | Jerarquía, orden de invocación, tokens por agente, marcado de errores |
| Memoria | `test_memoria.py` | Compactación, resumen extractivo, contextualización, aislamiento |
| Versionado | `test_versionado.py` | Conventional Commits → semver, changelog, integración con git |

Ejecución: `python -m pytest --cov` (305 tests, ~12 s, **sin red**).

CI corre además, en Python 3.10 y 3.12:

```bash
ruff check . && ruff format --check .
python -m enterprise_agents demo         # smoke test
python -m enterprise_agents eval         # escenarios + fundamentación + recuperación
python -m enterprise_agents seguridad    # suite de inyección de prompt
```

### 5.1 Umbrales de aceptación

La evaluación **hace fallar el pipeline** si la calidad baja:

| Métrica | Umbral | Medido |
|---|---|---|
| acierto@5 | 0,85 | 0,902 |
| recall@5 | 0,80 | 0,895 |
| MRR | 0,70 | 0,776 |
| nDCG@5 | 0,75 | 0,804 |
| abstención | 1,00 | 1,000 |

Sobre 55 consultas etiquetadas: 51 del dominio y 4 ajenas. Las ajenas miden que el
motor **sepa no responder**; sin ellas la métrica premiaría al recuperador que
siempre devuelve algo.

### 5.2 Verificación de fundamentación

Toda afirmación cuantitativa de una respuesta debe aparecer en la salida de alguna
herramienta de **esa misma ejecución**. No se compara contra los datos crudos —el
agente puede legítimamente agregar, filtrar y ordenar— sino contra lo que
efectivamente leyó.

Las delegaciones se excluyen de la evidencia: su resultado es texto redactado por
otro agente, y tomarlo como prueba haría circular la verificación.

Detecta totales inventados, identificadores inexistentes y fechas corridas, sin
modelo juez y en microsegundos. Interpreta formatos españoles e ingleses
(`471,100` y `90.000`) porque el corpus mezcla ambos.

## 5.3 Versionado y publicación

La versión es **única** (`enterprise_agents.__version__`): `pyproject.toml` la
declara como `dynamic` y la lee de ahí, y la API HTTP la expone en su esquema
OpenAPI. `versionado.py` la deriva de los mensajes de commit:

| Entrada | Salida |
|---|---|
| `fix:` · `perf:` · `refactor:` · `revert:` | salto de parche |
| `feat:` | salto menor |
| `feat!:` / `BREAKING CHANGE:` | salto mayor (menor mientras la versión sea `0.x`) |
| `docs:` · `test:` · `ci:` · `build:` · `chore:` · `style:` | sin salto (pero `docs:` figura en el changelog) |

El análisis son funciones puras cubiertas al 100 %; las únicas operaciones con
efectos son `git describe` / `git log` y la escritura de `__init__.py` y
`CHANGELOG.md`. El workflow `release.yml` corre en la rama por defecto, commitea
con `[skip ci]`, crea el tag `vX.Y.Z` y publica la release. Detalle en ADR-0006.

## 6. Rendimiento y costos

### 6.1 Modo live

- Una consulta mono-dominio ≈ 4 llamadas a la API (2 del orquestador + 2 del
  especialista). Multi-dominio agrega ~2 llamadas por dominio extra.
- El prompt caching reduce el costo de los turnos 2..n de cada bucle.
- La memoria conversacional arrastra contexto: por eso tiene presupuesto y
  compactación.
- `tokens.py` estima el consumo localmente. Es **una estimación**: el conteo exacto
  lo define el tokenizador del proveedor. Sirve para comparar consultas entre sí y
  detectar una que se fue de escala, no como medida de facturación.

### 6.2 Modo offline

| Operación | Costo |
|---|---|
| Construcción del índice (190 fragmentos, vocabulario de ~1.300) | ~1,5 s, una vez por proceso |
| Consulta al motor de recuperación | milisegundos (producto interno por fragmento) |
| Suite completa de tests | ~12 s |

**No hay índice aproximado (ANN)** a propósito: con 190 fragmentos la búsqueda
exhaustiva es más rápida que cualquier estructura con sobrecosto de construcción y
salto de punteros. El umbral a partir del cual convendría está anotado en el
ADR-0007.

## 7. Extensibilidad

**Alta de un dominio nuevo** (procedimiento completo en `CLAUDE.md`):

1. Herramientas puras en `tools/<dominio>.py`, con descripciones que digan *cuándo*
   usarlas.
2. Especialista en `specialists.py` con su system prompt.
3. Alta en `orchestrator.py` como herramienta `delegar_*`.
4. **Enunciados de ejemplo** en cada `ToolDef` — de ahí sale el ruteo del cliente
   simulado, que es semántico y no por palabras clave — más un test en
   `test_router.py`.
5. Escenario del dominio en `evals.py`.

Ningún otro módulo se modifica.

**Reemplazo de la recuperación** por un servicio del cliente: implementar
`Embedder` o sustituir `MotorRecuperacion`. El resto del sistema —herramientas,
router, evaluación— no cambia, porque todos consumen la misma interfaz.

**Conexión a sistemas reales**: las herramientas de dominio son el único punto de
cambio. El bucle agéntico, el RBAC, el saneamiento, las trazas y la evaluación son
independientes del origen de los datos.
