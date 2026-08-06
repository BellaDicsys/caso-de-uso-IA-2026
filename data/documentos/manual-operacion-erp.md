# Manual de Operación del ERP — Dicsys

**Versión:** 4.2 — Vigente desde enero 2026
**Área responsable:** Operaciones y Soporte

## Módulos en uso

| Módulo | Función | Responsable funcional |
|---|---|---|
| Ventas | pedidos, facturación, cuentas por cobrar | Administración |
| Compras | órdenes, recepción, cuentas por pagar | Administración |
| Proyectos | presupuestos, imputación de horas | Oficina de Proyectos |
| Personal | legajos, licencias, liquidación | Personas y Cultura |

## Cierres

El cierre mensual se ejecuta entre el **1 y el 8** del mes siguiente. Durante el
cierre el sistema queda en modo de solo lectura para los módulos contables.

## Circuito de una factura de venta

1. El líder de proyecto confirma los entregables aceptados del período.
2. Administración genera la factura desde el módulo de Ventas.
3. El sistema asigna número correlativo y registra el asiento contable.
4. Se envía al cliente por el canal acordado en el contrato.
5. La cobranza se imputa contra la factura, nunca contra el cliente en general.

## Errores frecuentes

- **Imputación a proyecto cerrado:** el sistema la rechaza; corresponde reabrir
  el proyecto con autorización de la Oficina de Proyectos.
- **Duplicación de orden de compra:** verificar el número de proveedor antes de
  generar una nueva.
- **Diferencias de cambio:** se registran automáticamente al cierre, no se cargan
  a mano.

## Interfaces

El ERP expone interfaces de lectura para el tablero de gestión. Las escrituras
automatizadas están deshabilitadas: todo asiento tiene origen humano trazable.

## Soporte

Los incidentes del ERP se registran en la mesa de ayuda con severidad según las
condiciones de servicio vigentes.
