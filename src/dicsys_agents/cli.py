"""Interfaz de línea de comandos de la suite.

Uso:
    dicsys-agents demo                # corre los escenarios de demostración
    dicsys-agents ask "pregunta"      # consulta libre al orquestador
    dicsys-agents ask --live "..."    # fuerza el uso de la API real

Sin ANTHROPIC_API_KEY, la suite corre en modo demo (mock) sin llamadas
externas, para que el repositorio sea evaluable sin credenciales.
"""

from __future__ import annotations

import argparse
import logging
import sys

from dicsys_agents.config import Settings, load_settings
from dicsys_agents.llm.base import LLMClient
from dicsys_agents.llm.mock_client import MockLLMClient
from dicsys_agents.orchestrator import crear_orquestador

ESCENARIOS_DEMO = [
    "¿Cuánto facturamos este año y quiénes son nuestros principales clientes?",
    "¿Cuántos días de vacaciones le corresponden a alguien con 7 años de antigüedad?",
    "Necesito armar un equipo con Python: ¿qué perfiles tienen disponibilidad?",
    "¿Qué proyectos están en riesgo por consumo de horas?",
]


def _crear_llm(settings: Settings, forzar_live: bool) -> tuple[LLMClient, str]:
    if forzar_live or settings.has_api_key:
        if not settings.has_api_key:
            print("ERROR: --live requiere ANTHROPIC_API_KEY en el entorno.", file=sys.stderr)
            raise SystemExit(2)
        # Import diferido: el SDK solo se necesita en modo live.
        from dicsys_agents.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(model=settings.model), f"live ({settings.model})"
    return MockLLMClient(), "demo (mock, sin llamadas externas)"


def _responder(pregunta: str, llm: LLMClient, settings: Settings) -> str:
    orquestador = crear_orquestador(llm, settings)
    return orquestador.run(pregunta)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dicsys-agents",
        description="Suite agéntica de gestión empresarial de Dicsys.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="muestra las llamadas a herramientas"
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("demo", help="ejecuta los escenarios de demostración")

    ask = sub.add_parser("ask", help="consulta libre al orquestador")
    ask.add_argument("pregunta", help="la consulta en lenguaje natural")
    ask.add_argument("--live", action="store_true", help="fuerza el uso de la API de Claude")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    settings = load_settings()
    llm, modo = _crear_llm(settings, getattr(args, "live", False))
    print(f"» Modo: {modo}\n")

    if args.comando == "demo":
        for i, pregunta in enumerate(ESCENARIOS_DEMO, 1):
            print(f"=== Escenario {i}: {pregunta}")
            print(_responder(pregunta, llm, settings))
            print()
    else:
        print(_responder(args.pregunta, llm, settings))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
