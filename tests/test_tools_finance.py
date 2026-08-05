"""Tests de las herramientas de finanzas."""

from enterprise_agents.config import Settings
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.orchestrator import crear_orquestador
from enterprise_agents.tools.finance import (
    deuda_por_cliente,
    estado_cobranzas,
    facturas_vencidas,
)


def test_estado_cobranzas_totaliza_por_estado():
    resultado = estado_cobranzas()
    assert "15 facturas emitidas" in resultado
    assert "Pagada" in resultado
    assert "Vencida" in resultado
    # Pendientes: 31000+17300+45500+21000+24600 = 139400
    # Vencidas: 9800+26400+11500 = 47700 → por cobrar 187100
    assert "187,100 USD" in resultado


def test_facturas_vencidas_ordena_por_antiguedad():
    resultado = facturas_vencidas()
    assert "3 por un total de 47,700 USD" in resultado
    # La más antigua (FC-2026-0115, vence 2026-06-30) aparece primera.
    lineas = [linea for linea in resultado.splitlines() if linea.startswith("  - ")]
    assert "FC-2026-0115" in lineas[0]


def test_deuda_por_cliente_filtra_y_agrupa():
    todos = deuda_por_cliente()
    assert "Banco Andino" in todos
    banco = deuda_por_cliente("banco andino")
    assert "45,500 USD" in banco
    assert "Retail Sur" not in banco


def test_deuda_cliente_sin_facturas_pendientes():
    resultado = deuda_por_cliente("Cliente Inexistente")
    assert "no tiene facturas pendientes" in resultado


def test_consulta_de_cobranzas_llega_al_analista_financiero():
    orquestador = crear_orquestador(MockLLMClient(), Settings())
    respuesta = orquestador.run("¿Qué facturas vencidas hay que reclamar?")
    assert "FC-2026" in respuesta
    assert "USD" in respuesta
