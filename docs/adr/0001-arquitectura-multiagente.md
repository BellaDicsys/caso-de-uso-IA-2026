# ADR-0001 — Arquitectura multi-agente: orquestador + especialistas

**Estado:** Aceptada — agosto 2026

## Contexto

La suite debe cubrir tres dominios de negocio distintos (analítica, documental,
personal) y demostrar un diseño que escale a más dominios. Las alternativas eran:

1. **Un único agente** con todas las herramientas de todos los dominios.
2. **Orquestador + especialistas**: un agente coordinador que delega en agentes de
   dominio, cada uno con su prompt y sus herramientas.

## Decisión

Se adopta la opción 2, con el patrón *agente-como-herramienta*: cada especialista se
expone al orquestador como una herramienta de delegación (`delegar_*`) cuyo handler
ejecuta el bucle agéntico completo del especialista.

## Justificación

- **Calidad de decisión**: un agente con pocas herramientas bien descriptas elige
  mejor que uno con muchas; cada especialista además lleva un system prompt con las
  reglas de su dominio (por ejemplo, cuidado de datos de personas en RRHH).
- **Escalabilidad organizacional**: agregar un dominio nuevo = crear un especialista
  y sumarlo a la lista del orquestador; nada más cambia.
- **Aislamiento de contexto**: cada delegación corre con su propio historial, evitando
  que el contexto de un dominio contamine a otro.
- **Es el patrón dominante** en los despliegues empresariales 2025–2026 relevados en
  [casos-innovacion.md](../casos-innovacion.md).

## Consecuencias

- Una consulta multi-dominio implica varios bucles agénticos (más latencia y tokens
  en modo live). Aceptable para el caso de uso; en producción se mitiga con caching
  de prompts (ya implementado) y delegaciones en paralelo.
- El orquestador depende de buenas descripciones de las herramientas de delegación;
  se documentan criterios de uso explícitos en cada descripción.
