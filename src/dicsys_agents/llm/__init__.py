"""Capa de acceso a modelos de lenguaje.

Expone una interfaz única (`LLMClient`) con dos implementaciones:

- `AnthropicLLMClient`: llama a la API de Claude (requiere ANTHROPIC_API_KEY).
- `MockLLMClient`: simula respuestas de forma determinística para demos
  offline y para la suite de tests.
"""

from dicsys_agents.llm.base import LLMClient, LLMReply, ToolCall
from dicsys_agents.llm.mock_client import MockLLMClient

__all__ = ["LLMClient", "LLMReply", "MockLLMClient", "ToolCall"]
