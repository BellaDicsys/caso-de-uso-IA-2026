# ADR-0003 — Modo demo offline (mock) como ciudadano de primera clase

**Estado:** Aceptada — agosto 2026

## Contexto

La entrega es vía repositorio, sin deploy. Quien evalúe el proyecto puede no tener
una clave de API de Anthropic, y los tests no deben depender de un servicio externo
(costo, latencia, no-determinismo).

## Decisión

Incluir `MockLLMClient`: una implementación determinística de la interfaz `LLMClient`
que selecciona herramientas por palabras clave y sintetiza los resultados. Es el modo
por defecto cuando no hay `ANTHROPIC_API_KEY`, y el modo en que corren los tests y el
smoke test de CI.

## Justificación

- **Evaluabilidad**: `pip install -e .` + `dicsys-agents demo` funciona en cualquier
  máquina, sin credenciales ni red.
- **Tests estables y gratis**: el flujo agéntico completo (orquestador → especialista
  → herramienta → síntesis) se verifica en milisegundos y sin costo.
- **Mismo código**: el mock produce mensajes en el formato de la Messages API, por lo
  que ejercita exactamente el mismo bucle que el modo live — no hay una rama "de
  mentira" sin cobertura.

## Consecuencias

- El mock no demuestra la calidad de razonamiento del modelo real (elige por
  keywords); el modo `--live` existe para eso.
- Las reglas de keywords deben mantenerse alineadas con los nombres de herramientas;
  los tests de integración fallan si se desalinean, lo que actúa de red de seguridad.
