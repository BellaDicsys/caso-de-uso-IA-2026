# Guía de Revisión de Código — Dicsys

**Versión:** 1.4 — Vigente desde febrero 2026
**Área responsable:** Ingeniería

## Propósito

La revisión busca detectar defectos, difundir conocimiento y sostener la
coherencia del código. No es un examen de la persona que escribió el cambio.

## Qué se revisa, en orden de prioridad

1. **Correctitud.** ¿Hace lo que dice? ¿Qué pasa en los casos límite?
2. **Seguridad.** ¿Valida las entradas? ¿Expone información que no debería?
3. **Legibilidad.** ¿Se entiende sin explicación oral?
4. **Pruebas.** ¿Hay una prueba que falle si el cambio se rompe?
5. **Estilo.** Lo resuelve el formateador automático, no la discusión.

## Tamaño y tiempos

| Tamaño del cambio | Tiempo de respuesta esperado |
|---|---|
| Menos de 100 líneas | 4 horas hábiles |
| Entre 100 y 400 líneas | 1 día hábil |
| Más de 400 líneas | pedir que se divida |

Un cambio grande no se revisa bien: la tasa de detección de defectos cae de forma
marcada por encima de las 400 líneas.

## Cómo comentar

- Distinguir lo bloqueante de la sugerencia. Marcar explícitamente cuál es cuál.
- Preguntar antes de afirmar cuando no se conoce el contexto.
- Proponer la alternativa concreta en lugar de señalar solo el problema.

## Aprobación

Aprobar significa hacerse corresponsable del cambio. Ante la duda, no se aprueba:
se pide la aclaración.
