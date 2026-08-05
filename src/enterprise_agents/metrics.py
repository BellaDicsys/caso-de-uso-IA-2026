"""Métricas y alertas tempranas para el tablero de control.

Reglas determinísticas sobre los datos de `data/` (mismo principio que las
herramientas de los agentes: código puro, testeable y auditable). El tablero
web (`/tablero`) consume el JSON de `calcular_metricas()` vía `/metricas`.

Las alertas usan tres severidades:
- ``critica``: requiere acción inmediata (p. ej. proyecto por sobrepasar horas).
- ``seria``: hay plata o compromiso en juego (p. ej. facturas vencidas).
- ``advertencia``: señal temprana a monitorear (vencimientos próximos,
  concentración de ingresos, capacidad ociosa).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from enterprise_agents.config import DATA_DIR

UMBRAL_CONSUMO_PROYECTO = 90  # % de horas consumidas que dispara alerta
DIAS_VENCIMIENTO_PROXIMO = 30
UMBRAL_CONCENTRACION = 30  # % de facturación en un solo cliente
MIN_PERSONAS_OCIOSAS = 2


def _leer(nombre: str) -> list[dict[str, str]]:
    with (DATA_DIR / nombre).open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def _fecha(texto: str) -> date:
    return datetime.strptime(texto, "%Y-%m-%d").date()


def calcular_metricas(hoy: date | None = None) -> dict[str, Any]:
    """Calcula KPIs, series para gráficos y alertas tempranas.

    ``hoy`` permite fijar la fecha de referencia (tests y reproducibilidad);
    por defecto se usa la fecha actual.
    """
    hoy = hoy or date.today()
    ventas = _leer("ventas.csv")
    proyectos = _leer("proyectos.csv")
    facturas = _leer("facturas.csv")
    empleados = _leer("empleados.csv")

    alertas: list[dict[str, str]] = []

    # --- Ventas ---
    facturacion_total = sum(float(v["monto_usd"]) for v in ventas)
    ventas_por_mes: dict[str, float] = defaultdict(float)
    ventas_por_cliente: dict[str, float] = defaultdict(float)
    for v in ventas:
        ventas_por_mes[v["fecha"][:7]] += float(v["monto_usd"])
        ventas_por_cliente[v["cliente"]] += float(v["monto_usd"])

    for cliente, monto in ventas_por_cliente.items():
        pct = monto / facturacion_total * 100
        if pct > UMBRAL_CONCENTRACION:
            alertas.append(
                {
                    "id": f"concentracion-{cliente}",
                    "severidad": "advertencia",
                    "titulo": f"Concentración de ingresos en {cliente}",
                    "detalle": (
                        f"{cliente} representa el {pct:.0f}% de la facturación "
                        f"({monto:,.0f} USD). Umbral: {UMBRAL_CONCENTRACION}%."
                    ),
                }
            )

    # --- Proyectos ---
    consumo_proyectos = []
    for p in proyectos:
        presupuestadas = float(p["horas_presupuestadas"])
        pct = float(p["horas_consumidas"]) / presupuestadas * 100 if presupuestadas else 0
        en_alerta = pct > UMBRAL_CONSUMO_PROYECTO and p["estado"] != "Finalizado"
        consumo_proyectos.append(
            {
                "codigo": p["codigo"],
                "nombre": p["nombre"],
                "cliente": p["cliente"],
                "pct": round(pct),
                "alerta": en_alerta,
            }
        )
        if en_alerta:
            alertas.append(
                {
                    "id": f"proyecto-{p['codigo']}",
                    "severidad": "critica",
                    "titulo": f"Proyecto {p['codigo']} por agotar horas",
                    "detalle": (
                        f"{p['nombre']} ({p['cliente']}) consumió el {pct:.0f}% de las "
                        f"horas presupuestadas y sigue {p['estado'].lower()}."
                    ),
                }
            )
    proyectos_en_riesgo = sum(1 for c in consumo_proyectos if c["alerta"])

    # --- Facturas / cobranzas ---
    deuda_por_cliente: dict[str, dict[str, float]] = defaultdict(
        lambda: {"pendiente": 0.0, "vencida": 0.0}
    )
    total_vencido = 0.0
    cantidad_vencidas = 0
    atrasadas_sin_registrar: list[str] = []
    monto_atrasado = 0.0
    por_vencer_monto = 0.0
    por_vencer_cantidad = 0

    for f in facturas:
        monto = float(f["monto_usd"])
        vencimiento = _fecha(f["fecha_vencimiento"])
        if f["estado"] == "Vencida":
            deuda_por_cliente[f["cliente"]]["vencida"] += monto
            total_vencido += monto
            cantidad_vencidas += 1
        elif f["estado"] == "Pendiente":
            if vencimiento < hoy:
                # Señal temprana: la factura figura pendiente pero ya venció.
                deuda_por_cliente[f["cliente"]]["vencida"] += monto
                atrasadas_sin_registrar.append(f["numero"])
                monto_atrasado += monto
            else:
                deuda_por_cliente[f["cliente"]]["pendiente"] += monto
                if (vencimiento - hoy).days <= DIAS_VENCIMIENTO_PROXIMO:
                    por_vencer_monto += monto
                    por_vencer_cantidad += 1

    if cantidad_vencidas:
        alertas.append(
            {
                "id": "facturas-vencidas",
                "severidad": "seria",
                "titulo": f"{cantidad_vencidas} facturas vencidas sin cobrar",
                "detalle": f"Total vencido: {total_vencido:,.0f} USD. Priorizar reclamo.",
            }
        )
    if atrasadas_sin_registrar:
        alertas.append(
            {
                "id": "cobranza-atrasada",
                "severidad": "seria",
                "titulo": "Facturas pendientes con fecha de vencimiento pasada",
                "detalle": (
                    f"{', '.join(atrasadas_sin_registrar)} por {monto_atrasado:,.0f} USD "
                    "figuran pendientes pero ya vencieron: revisar registro de cobranzas."
                ),
            }
        )
    if por_vencer_cantidad:
        alertas.append(
            {
                "id": "vencimientos-proximos",
                "severidad": "advertencia",
                "titulo": (
                    f"{por_vencer_cantidad} facturas vencen en ≤{DIAS_VENCIMIENTO_PROXIMO} días"
                ),
                "detalle": f"Monto por cobrar en el período: {por_vencer_monto:,.0f} USD.",
            }
        )

    por_cobrar = sum(d["pendiente"] + d["vencida"] for d in deuda_por_cliente.values())

    # --- Personal ---
    sin_asignar = [e for e in empleados if int(e["disponibilidad_pct"]) >= 100]
    if len(sin_asignar) >= MIN_PERSONAS_OCIOSAS:
        nombres = ", ".join(e["nombre"] for e in sin_asignar)
        alertas.append(
            {
                "id": "capacidad-ociosa",
                "severidad": "advertencia",
                "titulo": f"{len(sin_asignar)} personas sin asignación",
                "detalle": f"Capacidad disponible para nuevos proyectos: {nombres}.",
            }
        )

    orden_severidad = {"critica": 0, "seria": 1, "advertencia": 2}
    alertas.sort(key=lambda a: orden_severidad[a["severidad"]])

    return {
        "generado": hoy.isoformat(),
        "kpis": {
            "facturacion_total": facturacion_total,
            "por_cobrar": por_cobrar,
            "vencido": total_vencido + monto_atrasado,
            "proyectos_en_riesgo": proyectos_en_riesgo,
            "personas_sin_asignar": len(sin_asignar),
        },
        "series": {
            "ventas_por_mes": [
                {"mes": mes, "monto": monto} for mes, monto in sorted(ventas_por_mes.items())
            ],
            "deuda_por_cliente": sorted(
                (
                    {"cliente": c, "pendiente": d["pendiente"], "vencida": d["vencida"]}
                    for c, d in deuda_por_cliente.items()
                ),
                key=lambda x: x["pendiente"] + x["vencida"],
                reverse=True,
            ),
            "consumo_proyectos": sorted(consumo_proyectos, key=lambda c: c["pct"], reverse=True),
        },
        "alertas": alertas,
    }
