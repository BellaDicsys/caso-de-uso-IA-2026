# Política de Calidad de Software — Dicsys

**Versión:** 2.7 — Vigente desde marzo 2026
**Área responsable:** Ingeniería

## Criterios mínimos de aceptación

Ningún desarrollo se entrega a un cliente sin cumplir:

1. Cobertura de pruebas automatizadas de al menos **80 %** sobre el código propio.
2. Análisis estático sin hallazgos de severidad alta.
3. Revisión de código por al menos una persona distinta de quien lo escribió.
4. Documentación de instalación y operación actualizada.

## Pruebas

| Tipo | Responsable | Cuándo |
|---|---|---|
| Unitarias | quien desarrolla | en cada cambio |
| Integración | equipo de proyecto | en cada entrega |
| Aceptación | cliente | antes de aprobar el entregable |
| Regresión | automatizada | en cada integración continua |

## Integración continua

Cada repositorio ejecuta, en cada envío de código: análisis estático, pruebas
automatizadas y construcción del artefacto. Una integración en rojo bloquea la
incorporación de cambios.

## Deuda técnica

La deuda técnica se registra explícitamente y se asigna al menos el **15 %** de
la capacidad de cada iteración a reducirla. La deuda no registrada se considera
un defecto de proceso.

## Definición de terminado

Una tarea está terminada cuando: el código está integrado, las pruebas pasan, la
documentación está actualizada y la funcionalidad fue verificada por alguien
distinto de quien la desarrolló.
