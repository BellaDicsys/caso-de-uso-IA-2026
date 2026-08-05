# ADR-0002 — SDK oficial de Anthropic, modelo Claude Opus 5 y bucle agéntico propio

**Estado:** Aceptada — agosto 2026

## Contexto

Hay varias formas de construir el agente: SDK oficial de Anthropic con bucle propio,
el tool runner beta del SDK, frameworks de orquestación de terceros, o el Claude
Agent SDK (el harness completo de Claude Code como librería).

## Decisión

- **SDK oficial `anthropic`** como única dependencia de runtime, llamando a la
  Messages API con *tool use*.
- **Modelo `claude-opus-5`** por defecto (configurable vía `ENTERPRISE_AGENTS_MODEL`),
  con razonamiento adaptativo activo por defecto (en Opus 5 no requiere parámetro).
- **Bucle agéntico implementado en el proyecto** (`agents/base.py`) en lugar del
  tool runner beta del SDK.

## Justificación

- El SDK oficial evita el lock-in y la superficie de fallas de frameworks
  intermedios; la Messages API con tool use cubre todo lo que el caso necesita.
- El bucle propio se justifica por dos razones documentadas como válidas:
  1. permite **intercambiar el cliente real por el mock** detrás de la interfaz
     `LLMClient` con un único bucle (el tool runner está acoplado al cliente real);
  2. evita una **dependencia beta** en el corazón del sistema.
- Detalles de implementación alineados con las guías vigentes de la API:
  - `stop_reason == "refusal"` se maneja antes de leer `content` (la API puede
    declinar con HTTP 200);
  - los resultados de múltiples herramientas vuelven en **un único** mensaje de
    usuario (requisito para tool use en paralelo);
  - los bloques de *thinking* se reenvían intactos en turnos posteriores;
  - el system prompt lleva `cache_control` para abaratar los turnos del bucle.

## Consecuencias

- Mantenemos ~80 líneas de bucle propio; a cambio, el mismo código sirve para mock
  y live, y no dependemos de betas.
- Si en el futuro conviene el Claude Agent SDK (para agentes con filesystem/bash),
  la capa `LLMClient` localiza el cambio.
