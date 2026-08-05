"""Contrato común entre el orquestador y los proveedores de LLM.

Los mensajes y bloques de contenido usan el formato de la Messages API de
Anthropic (dicts serializables), de modo que un único bucle agéntico sirve
tanto para el cliente real como para el mock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    """Pedido de ejecución de una herramienta por parte del modelo."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class LLMReply:
    """Respuesta normalizada de un turno del modelo."""

    content: list[dict[str, Any]]
    stop_reason: str

    @property
    def text(self) -> str:
        return "\n".join(
            block["text"] for block in self.content if block.get("type") == "text"
        ).strip()

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [
            ToolCall(id=block["id"], name=block["name"], input=block.get("input", {}))
            for block in self.content
            if block.get("type") == "tool_use"
        ]


class LLMClient(Protocol):
    """Interfaz mínima que necesita el bucle agéntico."""

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMReply:
        """Ejecuta un turno del modelo y devuelve la respuesta normalizada."""
        ...
