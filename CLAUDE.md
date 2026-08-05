# Contexto para agentes de código

Suite agéntica de gestión empresarial (demo, sin deploy). Un orquestador delega
en cuatro especialistas (analítica, finanzas, documental, personal) que ejecutan
herramientas sobre datos de ejemplo en `data/`. Interfaces: CLI, API HTTP
(FastAPI) y chat web.

## Comandos

```bash
pip install -e ".[dev]"   # instalación
python -m pytest          # tests (deben pasar siempre; no requieren red ni API key)
ruff check . && ruff format --check .   # lint y formato (CI los exige)
python -m enterprise_agents demo            # smoke test offline
python -m enterprise_agents eval            # set de evaluación (6 escenarios, mock)
python -m enterprise_agents version --proximo   # versión que se publicaría con los commits actuales
```

## Convenciones

- **Idioma**: código con nombres en español para el dominio (herramientas, agentes),
  documentación y mensajes al usuario en español.
- **Arquitectura**: el modelo decide, el código ejecuta. Toda lógica de datos vive en
  `src/enterprise_agents/tools/` como funciones puras testeables; los agentes solo
  orquestan. No darle al modelo acceso directo a filesystem/datos sin una función
  intermedia que valide argumentos.
- **Capa LLM**: cualquier cambio en el bucle agéntico (`agents/base.py`) debe seguir
  funcionando con ambos clientes (`AnthropicLLMClient` y `MockLLMClient`). Los tests
  usan el mock; no agregar tests que llamen a la API real.
- **Código compartido**: normalización de texto en `text.py` (`normalizar`,
  `coincide_palabra`, `coincide_prefijo`) y lectura de CSV en `datos.leer_csv()`.
  No reimplementar ninguno de los dos en un módulo nuevo.
- **Frontend**: los estilos y utilidades comunes viven en `static/ds.css` y
  `static/ds.js` (incluido `esc()` para escapar antes de cualquier `innerHTML`).
- **Commits**: obligatorio [Conventional Commits](https://www.conventionalcommits.org/es/)
  (`feat:`, `fix:`, `perf:`, `refactor:`, `docs:`, `test:`, `ci:`, `chore:`, con
  alcance opcional y `!` para rupturas). De ahí salen la versión y el `CHANGELOG.md`
  (ver `versionado.py`): un commit fuera de convención no aparece en el historial
  publicado. Nunca editar `__version__` ni `CHANGELOG.md` a mano.
- **Decisiones estructurales**: registrar en `docs/adr/` (formato de los existentes).
- **Secretos**: solo por variables de entorno; `.env` está en `.gitignore`. Nunca
  commitear claves ni datos reales de clientes/empleados.

## Al agregar un dominio nuevo

1. Crear las herramientas en `tools/<dominio>.py` (funciones puras + lista de
   `ToolDef` con descripciones que digan *cuándo* usarlas).
2. Crear el especialista en `agents/specialists.py` con su system prompt.
3. Sumarlo al orquestador en `orchestrator.py` como herramienta `delegar_*`.
4. Agregar keywords del dominio en `llm/mock_client.py` para que la demo offline
   lo cubra, y tests en `tests/`.
5. Sumar un escenario del dominio en `evals.py` (el test `test_evals` exige que
   todos los escenarios pasen en mock).
