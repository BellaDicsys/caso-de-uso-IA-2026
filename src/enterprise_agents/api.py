"""API HTTP de la suite (FastAPI).

Expone el orquestador como servicio REST y sirve la interfaz de chat web.
Igual que la CLI, funciona en modo demo (mock) sin ANTHROPIC_API_KEY.

Ejecución:
    enterprise-agents serve            # http://localhost:8000
    enterprise-agents serve --port 9000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from enterprise_agents.config import Settings, load_settings
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.orchestrator import crear_orquestador

_STATIC = Path(__file__).parent / "static"


class Consulta(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)


class Respuesta(BaseModel):
    respuesta: str
    modo: str


def _crear_llm(settings: Settings) -> tuple[LLMClient, str]:
    if settings.has_api_key:
        from enterprise_agents.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(model=settings.model), f"live ({settings.model})"
    return MockLLMClient(), "demo"


def crear_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    llm, modo = _crear_llm(settings)

    app = FastAPI(
        title="Enterprise Agent Suite",
        description="Suite agéntica de gestión empresarial — API de consulta.",
        version="0.2.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def chat() -> str:
        return (_STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok", "modo": modo}

    @app.post("/consultar", response_model=Respuesta)
    def consultar(consulta: Consulta) -> Respuesta:
        orquestador = crear_orquestador(llm, settings)
        return Respuesta(respuesta=orquestador.run(consulta.pregunta), modo=modo)

    return app


def servir(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Levanta el servidor (usado por `enterprise-agents serve`)."""
    import uvicorn

    uvicorn.run(crear_app(), host=host, port=port)
