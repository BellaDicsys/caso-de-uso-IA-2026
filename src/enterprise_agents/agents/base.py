"""Bucle agéntico común a todos los agentes de la suite.

Se implementa el bucle manualmente (en lugar del tool runner beta del SDK)
para poder intercambiar el cliente real por el mock con la misma lógica y
sin dependencias beta. Ver ADR-0002.
"""

from __future__ import annotations

import logging
from typing import Any

from enterprise_agents import trazas
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.tools.base import ToolDef

logger = logging.getLogger(__name__)


class Agent:
    """Agente con system prompt propio y un conjunto de herramientas."""

    def __init__(
        self,
        *,
        name: str,
        system_prompt: str,
        tools: list[ToolDef],
        llm: LLMClient,
        max_iterations: int = 8,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.tools = {tool.name: tool for tool in tools}
        self.llm = llm
        self.max_iterations = max_iterations

    def run(self, task: str) -> str:
        """Ejecuta el bucle agéntico completo para una tarea y devuelve texto."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        tools_api = [tool.to_esquema() for tool in self.tools.values()]

        for _ in range(self.max_iterations):
            reply = self.llm.complete(system=self.system_prompt, messages=messages, tools=tools_api)

            if reply.stop_reason != "tool_use":
                return reply.text or "(sin respuesta del modelo)"

            messages.append({"role": "assistant", "content": reply.content})
            resultados = []
            for llamada in reply.tool_calls:
                logger.info("[%s] herramienta %s(%s)", self.name, llamada.name, llamada.input)
                resultados.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": llamada.id,
                        **self._ejecutar(llamada.name, llamada.input),
                    }
                )
            # Todos los resultados vuelven en un único mensaje de usuario,
            # como exige la API para llamadas en paralelo.
            messages.append({"role": "user", "content": resultados})

        return (
            f"[{self.name}] Se alcanzó el límite de {self.max_iterations} iteraciones "
            "sin una respuesta final. Reformulá la consulta o subí el límite."
        )

    def _ejecutar(self, nombre: str, argumentos: dict[str, Any]) -> dict[str, Any]:
        tool = self.tools.get(nombre)
        if tool is None:
            return {"content": f"Herramienta desconocida: {nombre}", "is_error": True}
        # La traza registra qué devolvió cada herramienta; si nadie está
        # capturando, `registrar` no hace nada y no cuesta nada.
        with trazas.registrar(self.name, nombre, argumentos) as caja:
            try:
                caja[0] = tool.run(argumentos)
                return {"content": caja[0]}
            except Exception as exc:  # noqa: BLE001 - el error vuelve al modelo
                logger.exception("[%s] error ejecutando %s", self.name, nombre)
                caja[0] = f"Error al ejecutar {nombre}: {exc}"
                return {"content": caja[0], "is_error": True}
