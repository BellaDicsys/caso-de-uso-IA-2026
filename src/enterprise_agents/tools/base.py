"""Definición de herramienta: esquema para el modelo + función ejecutable."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDef:
    """Una herramienta invocable por el modelo.

    `handler` recibe los argumentos que produjo el modelo y devuelve un texto
    que se envía de vuelta como `tool_result`.

    `ejemplos` son enunciados típicos que deberían activar esta herramienta. **No
    se envían al modelo real**: la Messages API no los usa, y el modelo elige por
    la descripción. Existen para el ruteo del cliente simulado, que necesita
    material sobre el cual medir similitud semántica —son exactamente los
    ejemplos que alimentarían a un clasificador de intención—. Ponerlos acá, al
    lado de la herramienta, evita que se desincronicen de ella.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., str]
    ejemplos: tuple[str, ...] = field(default_factory=tuple)

    def to_api(self) -> dict[str, Any]:
        """Formato de la Messages API de Anthropic."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_esquema(self) -> dict[str, Any]:
        """Esquema enriquecido que reciben los clientes LLM.

        Es `to_api()` más los enunciados de ejemplo. El cliente simulado los usa
        para rutear; `AnthropicLLMClient` los descarta antes de llamar a la API,
        que rechaza campos que no conoce. El contrato queda explícito en un solo
        lugar en vez de repartido entre los dos clientes.
        """
        esquema = self.to_api()
        if self.ejemplos:
            esquema["ejemplos"] = list(self.ejemplos)
        return esquema

    def texto_de_intencion(self) -> str:
        """Todo lo que describe *cuándo* usar esta herramienta, para el ruteo."""
        partes = [self.name.replace("_", " "), self.description, *self.ejemplos]
        for propiedad in self.input_schema.get("properties", {}).values():
            if propiedad.get("description"):
                partes.append(propiedad["description"])
        return " ".join(partes)

    def run(self, arguments: dict[str, Any]) -> str:
        return self.handler(**arguments)
