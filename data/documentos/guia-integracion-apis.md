# Guía de Integración de Interfaces (APIs) — Dicsys

**Versión:** 1.9 — Vigente desde marzo 2026
**Área responsable:** Ingeniería

## Principios de diseño

1. Contrato explícito y versionado antes de la implementación.
2. Compatibilidad hacia atrás dentro de una misma versión mayor.
3. Errores descriptivos y accionables, nunca genéricos.
4. Idempotencia en toda operación que modifique estado.

## Versionado

La versión va en la ruta (`/v1/...`). Un cambio incompatible obliga a una versión
nueva y a un período de convivencia de al menos **6 meses** con la anterior.

## Autenticación

| Escenario | Mecanismo |
|---|---|
| Integración entre sistemas | credenciales de cliente con token de corta duración |
| Aplicación de usuario final | delegación de identidad del proveedor corporativo |
| Consulta pública | ninguno, solo datos clasificados como públicos |

Las credenciales nunca viajan en la ruta ni en parámetros de consulta.

## Límites de uso

Se aplica un límite predeterminado de **120 peticiones por minuto** por
credencial. El exceso responde con el código 429 e indica cuándo reintentar.

## Errores

| Código | Significado | Reintentable |
|---|---|---|
| 400 | petición mal formada | no |
| 401 | credencial ausente o inválida | no |
| 403 | sin permiso para el recurso | no |
| 422 | petición válida con datos inconsistentes | no |
| 429 | límite de uso excedido | sí, con espera |
| 503 | servicio no disponible | sí, con espera creciente |

## Documentación

Toda interfaz publica su especificación legible por máquina. Una interfaz sin
especificación publicada se considera no entregada.
