# Estándar de Arquitectura de Datos — Dicsys

**Versión:** 2.6 — Vigente desde febrero 2026
**Área responsable:** Ingeniería de Datos

## Capas del modelo

| Capa | Contenido | Quién consume |
|---|---|---|
| Ingesta | datos crudos, sin transformar | procesos de carga |
| Normalizada | datos tipados y deduplicados | ingeniería de datos |
| Analítica | modelo dimensional por dominio | analistas y tableros |
| Publicación | vistas y agregados de negocio | aplicaciones y clientes |

Ninguna aplicación consulta directamente la capa de ingesta.

## Linaje y trazabilidad

Todo indicador publicado debe poder rastrearse hasta sus fuentes originales. Un
indicador sin linaje documentado no se publica en un tablero de cliente.

## Calidad de datos

Se ejecutan controles automáticos en cada carga:

1. Completitud de campos obligatorios.
2. Unicidad de claves.
3. Rangos válidos en métricas numéricas.
4. Coherencia referencial entre entidades.
5. Frescura: antigüedad máxima tolerada por origen.

Una carga con controles en rojo no promueve a la capa analítica.

## Nomenclatura

Nombres en minúsculas separados por guion bajo, sin abreviaturas ambiguas, con
sufijo de tipo en las fechas (`_fecha`, `_marca_temporal`). El nombre de una
métrica debe indicar su unidad.

## Retención

Los datos crudos se conservan 90 días; los normalizados, según la política de
clasificación de datos; los agregados analíticos, sin límite salvo pedido del
cliente.

## Reprocesos

Todo proceso de carga debe ser idempotente: reprocesar un período no puede
duplicar registros ni alterar resultados previos.
