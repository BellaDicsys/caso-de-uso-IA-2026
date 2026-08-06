# Política de Respaldos y Continuidad Operativa — Dicsys

**Versión:** 2.1 — Vigente desde febrero 2026
**Área responsable:** IT y Seguridad

## Esquema de respaldo

| Tipo de dato | Frecuencia | Retención | Copia externa |
|---|---|---|---|
| Bases de datos productivas | cada 6 horas | 35 días | sí |
| Repositorios de código | continua | indefinida | sí |
| Documentación corporativa | diaria | 90 días | sí |
| Equipos de trabajo | diaria | 30 días | no |

Se aplica el criterio de tres copias en dos soportes distintos, con una fuera de
la ubicación principal.

## Verificación

Un respaldo no verificado no es un respaldo. Se realiza una **restauración de
prueba mensual** sobre una muestra, y una restauración completa semestral.

## Objetivos de recuperación

| Servicio | Tiempo objetivo (RTO) | Pérdida máxima tolerada (RPO) |
|---|---|---|
| Sistemas de clientes con SLA crítico | 4 horas | 1 hora |
| ERP interno | 8 horas | 6 horas |
| Documentación y correo | 24 horas | 24 horas |
| Entornos de desarrollo | 72 horas | 24 horas |

## Continuidad

Existe un plan de continuidad que contempla: indisponibilidad de la oficina,
caída prolongada del proveedor de nube y ausencia simultánea de personal clave.
Cada escenario tiene responsable y procedimiento documentado.

## Ejercicios

Se ejercita un escenario de continuidad por semestre, con informe de resultados y
acciones correctivas con plazo asignado.
