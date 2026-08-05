"""Definición de herramienta: esquema para el modelo + función ejecutable."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDef:
    """Una herramienta invocable por el modelo.

    `handler` recibe los argumentos que produjo el modelo y devuelve un texto
    que se envía de vuelta como `tool_result`.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., str]

    def to_api(self) -> dict[str, Any]:
        """Formato de la Messages API de Anthropic."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def run(self, arguments: dict[str, Any]) -> str:
        return self.handler(**arguments)
