"""Tests de las métricas y alertas tempranas del tablero."""

from datetime import date

from enterprise_agents.metrics import calcular_metricas

HOY = date(2026, 8, 5)  # fecha de referencia fija para reproducibilidad


def _alertas_por_id(metricas):
    return {a["id"]: a for a in metricas["alertas"]}


def test_kpis_principales():
    kpis = calcular_metricas(HOY)["kpis"]
    assert kpis["facturacion_total"] == 471100
    assert kpis["por_cobrar"] == 187100
    # Vencidas por estado (47.700) + pendientes con fecha pasada (48.300).
    assert kpis["vencido"] == 96000
    assert kpis["proyectos_en_riesgo"] == 1
    assert kpis["personas_sin_asignar"] == 3


def test_alerta_critica_de_proyecto():
    alertas = _alertas_por_id(calcular_metricas(HOY))
    alerta = alertas["proyecto-P-2026-05"]
    assert alerta["severidad"] == "critica"
    assert "96%" in alerta["detalle"]


def test_alertas_de_cobranzas():
    alertas = _alertas_por_id(calcular_metricas(HOY))
    assert alertas["facturas-vencidas"]["severidad"] == "seria"
    # FC-2026-0107 y FC-2026-0110 figuran pendientes con vencimiento pasado.
    assert "FC-2026-0107" in alertas["cobranza-atrasada"]["detalle"]
    # Pendientes que vencen el 30/8 (3 facturas por 91.100 USD).
    assert "91,100" in alertas["vencimientos-proximos"]["detalle"]


def test_alertas_tempranas_de_negocio():
    alertas = _alertas_por_id(calcular_metricas(HOY))
    assert "concentracion-Banco Andino" in alertas  # 32% de la facturación
    assert alertas["capacidad-ociosa"]["severidad"] == "advertencia"


def test_alertas_ordenadas_por_severidad():
    severidades = [a["severidad"] for a in calcular_metricas(HOY)["alertas"]]
    orden = {"critica": 0, "seria": 1, "advertencia": 2}
    assert severidades == sorted(severidades, key=orden.__getitem__)


def test_series_para_graficos():
    series = calcular_metricas(HOY)["series"]
    assert len(series["ventas_por_mes"]) == 7
    # Retail Sur: 21.000 pendiente + 31.000 vencida efectiva (FC-2026-0107) = 52.000.
    assert series["deuda_por_cliente"][0]["cliente"] == "Retail Sur"
    assert series["consumo_proyectos"][0]["codigo"] in ("P-2025-18", "P-2026-05")
