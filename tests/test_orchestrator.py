"""Tests de integración del bucle agéntico con el cliente mock.

Verifican el flujo completo orquestador → especialista → herramienta →
síntesis, sin llamadas externas.
"""

from enterprise_agents.agents.base import Agent
from enterprise_agents.config import Settings
from enterprise_agents.llm.base import LLMReply
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.orchestrator import crear_orquestador
from enterprise_agents.tools.base import ToolDef


def _orquestador() -> Agent:
    return crear_orquestador(MockLLMClient(), Settings())


def test_consulta_de_ventas_llega_al_analista():
    respuesta = _orquestador().run("¿Cuánto facturamos y a qué clientes?")
    assert "USD" in respuesta
    assert "Banco Andino" in respuesta


def test_consulta_documental_cita_el_documento():
    respuesta = _orquestador().run("¿Qué dice la política de vacaciones?")
    assert "politica-vacaciones.md" in respuesta


def test_consulta_de_personal_devuelve_perfiles():
    respuesta = _orquestador().run("Busco perfiles con Python disponibles para asignar")
    assert "disponibilidad" in respuesta.lower()


def test_consulta_fuera_de_dominio_no_inventa():
    respuesta = _orquestador().run("¿Va a llover mañana?")
    assert "modo demo" in respuesta


def test_error_de_herramienta_vuelve_al_modelo_como_tool_result():
    def explota() -> str:
        raise ValueError("falla controlada")

    class LLMGuionado:
        """Primero pide la herramienta, después responde con el resultado."""

        def __init__(self) -> None:
            self.turno = 0

        def complete(self, *, system, messages, tools):
            self.turno += 1
            if self.turno == 1:
                return LLMReply(
                    content=[{"type": "tool_use", "id": "t1", "name": "fragil", "input": {}}],
                    stop_reason="tool_use",
                )
            resultado = messages[-1]["content"][0]
            assert resultado["is_error"] is True
            return LLMReply(
                content=[{"type": "text", "text": f"hubo un error: {resultado['content']}"}],
                stop_reason="end_turn",
            )

    agente = Agent(
        name="prueba",
        system_prompt="test",
        tools=[
            ToolDef(
                name="fragil",
                description="herramienta que falla",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=explota,
            )
        ],
        llm=LLMGuionado(),
    )
    respuesta = agente.run("ejecutá la herramienta")
    assert "falla controlada" in respuesta


def test_limite_de_iteraciones_corta_el_bucle():
    class LLMInsistente:
        """Siempre pide una herramienta: fuerza el corte por límite."""

        def complete(self, *, system, messages, tools):
            return LLMReply(
                content=[{"type": "tool_use", "id": "t1", "name": "eco", "input": {}}],
                stop_reason="tool_use",
            )

    agente = Agent(
        name="prueba",
        system_prompt="test",
        tools=[
            ToolDef(
                name="eco",
                description="devuelve ok",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=lambda: "ok",
            )
        ],
        llm=LLMInsistente(),
        max_iterations=3,
    )
    respuesta = agente.run("loop")
    assert "límite de 3 iteraciones" in respuesta
