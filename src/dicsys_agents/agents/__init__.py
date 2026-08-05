"""Agentes de la suite: especialistas de dominio y orquestador."""

from dicsys_agents.agents.base import Agent
from dicsys_agents.agents.specialists import (
    crear_analista_datos,
    crear_gestor_documental,
    crear_gestor_personal,
)

__all__ = [
    "Agent",
    "crear_analista_datos",
    "crear_gestor_documental",
    "crear_gestor_personal",
]
