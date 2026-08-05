"""Cliente real contra la API de Claude (Anthropic).

Decisiones de implementación (ver ADR-0002):

- Modelo por defecto `claude-opus-5`, con razonamiento adaptativo activo por
  defecto (en Opus 5 no hace falta enviar el parámetro `thinking`).
- Se maneja explícitamente `stop_reason == "refusal"`: la API puede declinar
  un pedido devolviendo HTTP 200, por lo que nunca se debe leer `content`
  sin chequear el motivo de corte.
"""

from __future__ import annotations

from typing import Any

import anthropic

from enterprise_agents.llm.base import LLMReply

DEFAULT_MAX_TOKENS = 4096


class AnthropicLLMClient:
    """Implementación de `LLMClient` sobre el SDK oficial de Anthropic."""

    def __init__(self, model: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
        # El SDK resuelve credenciales del entorno (ANTHROPIC_API_KEY).
        self._client = anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMReply:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system,
                    # El system prompt es estable por agente: se cachea para
                    # abaratar los turnos siguientes del bucle agéntico.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
            tools=tools or anthropic.NOT_GIVEN,
        )

        if response.stop_reason == "refusal":
            detail = ""
            if response.stop_details and response.stop_details.category:
                detail = f" (categoría: {response.stop_details.category})"
            return LLMReply(
                content=[
                    {
                        "type": "text",
                        "text": "El modelo declinó responder esta consulta"
                        f"{detail}. Reformulá el pedido o consultá al equipo.",
                    }
                ],
                stop_reason="refusal",
            )

        # Los bloques se serializan a dicts para mantener un historial uniforme.
        # Los bloques de thinking se conservan intactos: la API exige que se
        # reenvíen sin modificaciones en turnos posteriores del mismo modelo.
        content = [block.model_dump(exclude_none=True) for block in response.content]
        return LLMReply(content=content, stop_reason=response.stop_reason or "end_turn")
