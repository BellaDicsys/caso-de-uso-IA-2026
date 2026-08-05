"""Tests de las herramientas de analítica."""

from enterprise_agents.tools.analytics import avance_proyectos, resumen_ventas


def test_resumen_ventas_incluye_total_y_clientes():
    resultado = resumen_ventas()
    assert "20 operaciones" in resultado
    assert "Banco Andino" in resultado
    assert "Analitica de Datos" in resultado
    assert "Por mes:" in resultado


def test_avance_proyectos_marca_riesgo_de_consumo():
    resultado = avance_proyectos()
    # P-2026-05 consumió 1150/1200 horas (96%) y sigue abierto.
    assert "P-2026-05" in resultado
    assert "consumo alto" in resultado
    # Un proyecto finalizado con consumo alto no debe alertar.
    linea_finalizado = next(linea for linea in resultado.splitlines() if "P-2025-18" in linea)
    assert "consumo alto" not in linea_finalizado
