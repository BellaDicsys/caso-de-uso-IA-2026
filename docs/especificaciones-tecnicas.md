# Especificaciones técnicas — Enterprise Agent Suite

**Versión:** 1.1 — Agosto 2026
**Proyecto:** Caso de uso IA 2026 — Suite agéntica de gestión empresarial

---

## 1. Stack tecnológico

| Componente | Tecnología | Versión / Detalle |
|---|---|---|
| Lenguaje | Python | ≥ 3.10 (probado en 3.10 y 3.12 en CI) |
| Modelo de IA | Claude (Anthropic) | `claude-opus-5` por defecto, configurable |
| SDK | `anthropic` (oficial) | ≥ 0.116.0 — única dependencia de runtime del núcleo |
| API HTTP (opcional) | FastAPI + uvicorn | extra `[api]`; sirve REST + chat web |
| Empaquetado | `pyproject.toml` (setuptools) | layout `src/`, consola `enterprise-agents` |
| Testing | pytest + pytest-cov | ≥ 8.0 — 269 tests, cobertura 94 % (umbral 85 % en CI) |
| Calidad de código | ruff (lint + formato) | reglas E, F, W, I, N, UP, B, SIM; línea 100 |
| CI/CD | GitHub Actions | lint + tests + demo offline en cada push |
| Versionado | propio (`versionado.py`) | semver derivado de Conventional Commits; tag, changelog y release en CI |

**Sin dependencias de frameworks de orquestación** (LangChain, CrewAI, etc.): la
orquestación se implementa directamente sobre la Messages API con *tool use*
(justificación en ADR-0002).

## 2. Arquitectura de módulos

```
src/enterprise_agents/
├── config.py            # Settings (env vars), rutas de datos, modelo default
├── cli.py               # Entrada CLI: demo / ask / eval / serve / version
├── api.py               # API HTTP (FastAPI): POST /consultar, GET /salud, chat web
├── evals.py             # Set de evaluación: 6 escenarios con criterios verificables
├── versionado.py        # Conventional Commits → semver + changelog + release
├── static/index.html    # Interfaz de chat web (autocontenida, sin dependencias)
├── orchestrator.py      # crear_orquestador(): agente coordinador
├── agents/
│   ├── base.py          # class Agent: bucle agéntico común (≈80 líneas)
│   └── specialists.py   # Fábricas de los 4 especialistas + system prompts
├── tools/
│   ├── base.py          # ToolDef: esquema JSON + handler ejecutable
│   ├── analytics.py     # resumen_ventas(), avance_proyectos()
│   ├── finance.py       # estado_cobranzas(), facturas_vencidas(), deuda_por_cliente()
│   ├── documents.py     # buscar_documentos(), leer_documento()
│   └── hr.py            # buscar_por_habilidad(), disponibilidad_equipo()
└── llm/
    ├── base.py          # Protocolo LLMClient + LLMReply + ToolCall
    ├── anthropic_client.py  # Cliente real (Messages API)
    └── mock_client.py       # Cliente determinístico offline
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

**`ToolDef`** — herramienta invocable: `name`, `description` (incluye el criterio de
*cuándo* usarla), `input_schema` (JSON Schema), `handler` (callable → `str`).
`to_api()` produce el formato que consume la Messages API.

### 2.2 Bucle agéntico (`agents/base.py`)

Algoritmo por consulta (idéntico para orquestador y especialistas):

1. `messages = [{"role": "user", "content": tarea}]`
2. Llamar `llm.complete(system, messages, tools)`.
3. Si `stop_reason != "tool_use"` → devolver el texto (fin).
4. Si pide herramientas: anexar el turno assistant completo al historial,
   ejecutar **todas** las llamadas y devolver los `tool_result` en **un único**
   mensaje `user` (requisito de la API para tool use en paralelo).
5. Repetir desde (2) hasta `max_iterations` (default 8, configurable).
6. Si se agota el límite → mensaje de corte controlado (nunca bucle infinito).

Manejo de errores de herramienta: la excepción se captura, se loguea y vuelve al
modelo como `tool_result` con `is_error: true` para que pueda recuperarse.

### 2.3 Integración con la API de Claude (`anthropic_client.py`)

- Endpoint: `POST /v1/messages` vía SDK oficial (`client.messages.create`).
- `max_tokens = 4096` por turno (respuestas de gestión, no generación larga).
- **Razonamiento adaptativo** activo por defecto en Opus 5 (no se envía `thinking`).
- **Prompt caching**: el system prompt de cada agente lleva
  `cache_control: {"type": "ephemeral"}` — los turnos siguientes del bucle leen el
  prefijo cacheado (~90% menos costo sobre esa porción).
- **Manejo de `stop_reason == "refusal"`**: la API puede declinar con HTTP 200;
  se chequea antes de leer `content` y se devuelve un mensaje controlado con la
  categoría del rechazo si está disponible.
- **Bloques de thinking**: se serializan con `model_dump()` y se reenvían intactos
  en los turnos siguientes (requisito de la API).
- Credenciales: resueltas por el SDK desde el entorno (`ANTHROPIC_API_KEY`);
  nunca se hardcodean.

### 2.4 Cliente mock (`mock_client.py`)

Simulación determinística para demo offline y tests:

- **Selección de herramienta**: puntaje por coincidencia de palabras clave
  (normalizadas sin tildes) contra un diccionario `_KEYWORDS` por herramienta;
  funciona igual para herramientas de dominio y de delegación.
- **Inferencia de argumentos**: reglas por herramienta (p. ej. detecta la habilidad
  mencionada entre 14 conocidas para `buscar_por_habilidad`).
- **Síntesis**: cuando el último mensaje contiene `tool_result`, devuelve su
  contenido como respuesta final (`end_turn`).
- Produce mensajes en el mismo formato de la Messages API → ejercita exactamente
  el mismo bucle que el cliente real.

## 3. Configuración

| Variable de entorno | Default | Efecto |
|---|---|---|
| `ANTHROPIC_API_KEY` | (vacía) | Si está definida → modo live; si no → modo mock |
| `ENTERPRISE_AGENTS_MODEL` | `claude-opus-5` | Modelo a usar en modo live |
| `ENTERPRISE_AGENTS_MAX_ITERATIONS` | `8` | Tope de iteraciones del bucle por consulta |

Plantilla en `.env.example`; `.env` está en `.gitignore`.

## 4. Seguridad

- **Validación de argumentos del modelo**: `leer_documento` resuelve la ruta y
  verifica que quede dentro de `data/documentos/` y con extensión `.md`
  (bloqueo de path traversal, con test que lo demuestra).
- **Sin acceso directo del modelo a datos/filesystem**: siempre media una función
  con contrato explícito.
- **Sin secretos en el repo**: solo variables de entorno; datos 100% sintéticos.
- **Límite de iteraciones** en todos los bucles (protección de costo y de loops).
- **Minimización en RRHH**: el prompt del gestor de personal restringe la
  información a rol/habilidades/disponibilidad y prohíbe especular sobre desempeño.

## 5. Testing y calidad

| Suite | Archivos | Qué verifica |
|---|---|---|
| Unitarios de herramientas | `test_tools_analytics.py`, `test_tools_finance.py`, `test_tools_documents.py`, `test_tools_hr.py` | Cálculos, ordenamientos, umbrales, alertas de riesgo, path traversal, insensibilidad a mayúsculas |
| Integración agéntica | `test_orchestrator.py`, `test_api.py`, `test_evals.py` | Flujo completo orquestador→especialista→herramienta→síntesis; propagación de errores como `tool_result`; corte por límite de iteraciones; consultas fuera de dominio |

Ejecución: `python -m pytest --cov` (269 tests, ~17 s, sin red). CI corre además
`ruff check`, `ruff format --check` y `python -m enterprise_agents demo` como smoke
test, en Python 3.10 y 3.12.

## 5.1 Versionado y publicación

La versión es **única** (`enterprise_agents.__version__`): `pyproject.toml` la
declara como `dynamic` y la lee de ahí, y la API HTTP la expone en su esquema
OpenAPI. `versionado.py` la deriva de los mensajes de commit:

| Entrada | Salida |
|---|---|
| `fix:` · `perf:` · `refactor:` · `revert:` | salto de parche |
| `feat:` | salto menor |
| `feat!:` / `BREAKING CHANGE:` | salto mayor (menor mientras la versión sea `0.x`) |
| `docs:` · `test:` · `ci:` · `build:` · `chore:` · `style:` | sin salto (pero `docs:` figura en el changelog) |

El análisis son funciones puras (`analizar`, `siguiente_version`,
`notas_de_version`, `actualizar_changelog`) cubiertas al 100 %; las únicas
operaciones con efectos son `git describe` / `git log` y la escritura de
`__init__.py` y `CHANGELOG.md`. El workflow `release.yml` corre en la rama por
defecto, commitea con `[skip ci]`, crea el tag `vX.Y.Z` y publica la release.
Detalle en ADR-0006.

## 6. Rendimiento y costos (modo live)

- Una consulta mono-dominio ≈ 4 llamadas a la API (2 del orquestador + 2 del
  especialista). Multi-dominio agrega ~2 llamadas por dominio extra.
- El prompt caching reduce el costo de los turnos 2..n de cada bucle.
- `max_tokens` acotado (4096) y efort del modelo por defecto; ajustables si un
  despliegue requiere respuestas más largas o menor latencia.

## 7. Extensibilidad

Alta de un dominio nuevo (procedimiento completo en `CLAUDE.md`):
herramientas puras en `tools/<dominio>.py` → especialista en `specialists.py` →
alta en `orchestrator.py` → keywords en `mock_client.py` → tests. Ningún otro
módulo se modifica.
