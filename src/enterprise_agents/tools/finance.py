"""Herramientas de finanzas: cobranzas y facturas sobre `data/facturas.csv`.

En un despliegue real, estas funciones consultan el ERP o el sistema de
facturación en lugar de un CSV local.
"""

from __future__ import annotations

import csv
from collections import defaultdict

from enterprise_agents.config import DATA_DIR
from enterprise_agents.tools.base import ToolDef


def _leer_facturas() -> list[dict[str, str]]:
    with (DATA_DIR / "facturas.csv").open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def estado_cobranzas() -> str:
    filas = _leer_facturas()
    por_estado: dict[str, float] = defaultdict(float)
    cantidad: dict[str, int] = defaultdict(int)
    for f in filas:
        por_estado[f["estado"]] += float(f["monto_usd"])
        cantidad[f["estado"]] += 1

    lineas = [
        f"  - {estado}: {cantidad[estado]} facturas por {monto:,.0f} USD"
        for estado, monto in sorted(por_estado.items(), key=lambda kv: kv[1], reverse=True)
    ]
    por_cobrar = por_estado.get("Pendiente", 0) + por_estado.get("Vencida", 0)
    return (
        f"Estado de cobranzas ({len(filas)} facturas emitidas):\n"
        + "\n".join(lineas)
        + f"\nTotal por cobrar (pendiente + vencida): {por_cobrar:,.0f} USD"
    )


def facturas_vencidas() -> str:
    vencidas = [f for f in _leer_facturas() if f["estado"] == "Vencida"]
    if not vencidas:
        return "No hay facturas vencidas."
    vencidas.sort(key=lambda f: f["fecha_vencimiento"])
    total = sum(float(f["monto_usd"]) for f in vencidas)
    lineas = [
        f"  - {f['numero']} {f['cliente']}: {float(f['monto_usd']):,.0f} USD "
        f"(venció el {f['fecha_vencimiento']})"
        for f in vencidas
    ]
    return (
        f"Facturas vencidas: {len(vencidas)} por un total de {total:,.0f} USD "
        "(ordenadas de más antigua a más reciente):\n" + "\n".join(lineas)
    )


def deuda_por_cliente(cliente: str = "") -> str:
    filas = [f for f in _leer_facturas() if f["estado"] in ("Pendiente", "Vencida")]
    if cliente:
        objetivo = cliente.strip().lower()
        filas = [f for f in filas if objetivo in f["cliente"].lower()]
        if not filas:
            return f"El cliente '{cliente}' no tiene facturas pendientes ni vencidas."

    por_cliente: dict[str, float] = defaultdict(float)
    for f in filas:
        por_cliente[f["cliente"]] += float(f["monto_usd"])
    lineas = [
        f"  - {nombre}: {monto:,.0f} USD"
        for nombre, monto in sorted(por_cliente.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return "Deuda por cliente (facturas pendientes + vencidas):\n" + "\n".join(lineas)


HERRAMIENTAS_FINANZAS = [
    ToolDef(
        name="estado_cobranzas",
        description=(
            "Devuelve el estado general de cobranzas: facturas pagadas, pendientes "
            "y vencidas con sus montos, y el total por cobrar. Llamala cuando la "
            "consulta sea sobre cobranzas, cuentas por cobrar o salud financiera."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=estado_cobranzas,
    ),
    ToolDef(
        name="facturas_vencidas",
        description=(
            "Lista las facturas vencidas con cliente, monto y fecha de vencimiento, "
            "ordenadas por antigüedad. Llamala cuando la consulta sea sobre mora, "
            "facturas vencidas o clientes a reclamar."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=facturas_vencidas,
    ),
    ToolDef(
        name="deuda_por_cliente",
        description=(
            "Devuelve la deuda (facturas pendientes + vencidas) agrupada por "
            "cliente; acepta un cliente específico como filtro opcional. Llamala "
            "cuando se pregunte cuánto debe un cliente o quiénes deben más."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cliente": {
                    "type": "string",
                    "description": "Nombre (o parte) del cliente a filtrar. Vacío = todos.",
                }
            },
            "required": [],
        },
        handler=deuda_por_cliente,
    ),
]
