# Contexto para agentes de código

Suite agéntica de gestión empresarial de Dicsys (demo, sin deploy). Un orquestador
delega en tres especialistas (analítica, documental, personal) que ejecutan
herramientas sobre datos de ejemplo en `data/`.

## Comandos

```bash
pip install -e ".[dev]"   # instalación
python -m pytest          # tests (deben pasar siempre; no requieren red ni API key)
ruff check . && ruff format --check .   # lint y formato (CI los exige)
python -m dicsys_agents demo            # smoke test offline
```

## Convenciones

- **Idioma**: código con nombres en español para el dominio (herramientas, agentes),
  documentación y mensajes al usuario en español.
- **Arquitectura**: el modelo decide, el código ejecuta. Toda lógica de datos vive en
  `src/dicsys_agents/tools/` como funciones puras testeables; los agentes solo
  orquestan. No darle al modelo acceso directo a filesystem/datos sin una función
  intermedia que valide argumentos.
- **Capa LLM**: cualquier cambio en el bucle agéntico (`agents/base.py`) debe seguir
  funcionando con ambos clientes (`AnthropicLLMClient` y `MockLLMClient`). Los tests
  usan el mock; no agregar tests que llamen a la API real.
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
