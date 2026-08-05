"""Herramientas de analítica: ventas y avance de proyectos.

Leen los CSV de `data/` con la biblioteca estándar para mantener la demo sin
dependencias pesadas. En un despliegue real, estas funciones se reemplazan
por consultas al data warehouse del cliente (ver docs/arquitectura.md).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from enterprise_agents.config import DATA_DIR
from enterprise_agents.tools.base import ToolDef


def _leer_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def resumen_ventas() -> str:
    filas = _leer_csv(DATA_DIR / "ventas.csv")
    total = sum(float(f["monto_usd"]) for f in filas)

    por_cliente: dict[str, float] = defaultdict(float)
    por_servicio: dict[str, float] = defaultdict(float)
    por_mes: dict[str, float] = defaultdict(float)
    for fila in filas:
        monto = float(fila["monto_usd"])
        por_cliente[fila["cliente"]] += monto
        por_servicio[fila["servicio"]] += monto
        por_mes[fila["fecha"][:7]] += monto

    def _tabla(datos: dict[str, float]) -> str:
        orden = sorted(datos.items(), key=lambda kv: kv[1], reverse=True)
        return "\n".join(f"  - {nombre}: {monto:,.0f} USD" for nombre, monto in orden)

    meses = "\n".join(f"  - {mes}: {monto:,.0f} USD" for mes, monto in sorted(por_mes.items()))
    return (
        f"Ventas registradas: {len(filas)} operaciones por {total:,.0f} USD.\n"
        f"Por cliente:\n{_tabla(por_cliente)}\n"
        f"Por servicio:\n{_tabla(por_servicio)}\n"
        f"Por mes:\n{meses}"
    )


def avance_proyectos() -> str:
    filas = _leer_csv(DATA_DIR / "proyectos.csv")
    lineas = []
    for fila in filas:
        presupuestadas = float(fila["horas_presupuestadas"])
        consumidas = float(fila["horas_consumidas"])
        avance = consumidas / presupuestadas * 100 if presupuestadas else 0
        alerta = " ⚠ consumo alto" if avance > 90 and fila["estado"] != "Finalizado" else ""
        lineas.append(
            f"  - {fila['codigo']} {fila['nombre']} ({fila['cliente']}): "
            f"{fila['estado']}, {consumidas:.0f}/{presupuestadas:.0f} hs "
            f"({avance:.0f}%){alerta}"
        )
    return "Estado de proyectos:\n" + "\n".join(lineas)


HERRAMIENTAS_ANALITICA = [
    ToolDef(
        name="resumen_ventas",
        description=(
            "Devuelve el resumen de ventas de la consultora: total facturado y "
            "desglose por cliente, por servicio y por mes. Llamala cuando la "
            "consulta involucre facturación, ingresos, montos o ranking de clientes."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=resumen_ventas,
    ),
    ToolDef(
        name="avance_proyectos",
        description=(
            "Devuelve el estado de todos los proyectos: cliente, estado, horas "
            "presupuestadas vs consumidas y alertas de consumo. Llamala cuando la "
            "consulta involucre proyectos, avance, horas o riesgos de entrega."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=avance_proyectos,
    ),
]
