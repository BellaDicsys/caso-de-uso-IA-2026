# Plan de Respuesta a Incidentes de Seguridad — Dicsys

**Versión:** 2.0 — Vigente desde febrero 2026
**Área responsable:** IT y Seguridad

## Clasificación de severidad

| Nivel | Descripción | Tiempo de respuesta |
|---|---|---|
| S1 — Crítico | Compromiso de datos de clientes o indisponibilidad total | 30 minutos |
| S2 — Alto | Compromiso de sistemas internos sin datos de clientes | 2 horas |
| S3 — Medio | Intento de intrusión contenido, malware aislado | 8 horas |
| S4 — Bajo | Anomalía sin impacto confirmado | 48 horas |

## Fases

1. **Detección y registro.** Todo incidente se registra al detectarse, aun sin confirmar.
2. **Contención.** Aislar el activo afectado antes de investigar en profundidad.
3. **Erradicación.** Eliminar la causa raíz, no solo el síntoma.
4. **Recuperación.** Restituir el servicio con verificación de integridad.
5. **Lecciones aprendidas.** Informe dentro de los 10 días hábiles del cierre.

## Roles

- **Coordinador del incidente:** decide y comunica. Es siempre una única persona.
- **Equipo técnico:** ejecuta la contención y la erradicación.
- **Enlace con el cliente:** único canal de comunicación externa.
- **Legales:** evalúa obligaciones de notificación.

## Notificación a clientes

Ante un incidente S1 que afecte datos de un cliente, la notificación se cursa
dentro de las **24 horas** de confirmado el alcance, con los hechos conocidos,
las medidas tomadas y los próximos pasos. No se especula sobre causas.

## Ejercicios

Se realiza un simulacro semestral. Los resultados alimentan la revisión anual
de este plan.
