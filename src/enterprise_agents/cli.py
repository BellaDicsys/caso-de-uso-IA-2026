"""Interfaz de línea de comandos de la suite.

Uso:
    enterprise-agents demo                # corre los escenarios de demostración
    enterprise-agents ask "pregunta"      # consulta libre al orquestador
    enterprise-agents ask --live "..."    # fuerza el uso de la API real
    enterprise-agents eval [--live]       # set de evaluación (mock o modelo real)
    enterprise-agents serve [--port N]    # API HTTP + chat web
    enterprise-agents version [--proximo] # versión actual / próxima según los commits

Sin ANTHROPIC_API_KEY, la suite corre en modo demo (mock) sin llamadas
externas, para que el repositorio sea evaluable sin credenciales.
"""

from __future__ import annotations

import argparse
import logging
import sys

from enterprise_agents.config import Settings, load_settings
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.orchestrator import crear_orquestador

ESCENARIOS_DEMO = [
    "¿Cuánto facturamos este año y quiénes son nuestros principales clientes?",
    "¿Cuántos días de vacaciones le corresponden a alguien con 7 años de antigüedad?",
    "Necesito armar un equipo con Python: ¿qué perfiles tienen disponibilidad?",
    "¿Qué proyectos están en riesgo por consumo de horas?",
    "¿Qué facturas vencidas hay que reclamar?",
]


def _crear_llm(settings: Settings, forzar_live: bool) -> tuple[LLMClient, str]:
    if forzar_live or settings.has_api_key:
        if not settings.has_api_key:
            print("ERROR: --live requiere ANTHROPIC_API_KEY en el entorno.", file=sys.stderr)
            raise SystemExit(2)
        # Import diferido: el SDK solo se necesita en modo live.
        from enterprise_agents.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(model=settings.model), f"live ({settings.model})"
    return MockLLMClient(), "demo (mock, sin llamadas externas)"


def _responder(pregunta: str, llm: LLMClient, settings: Settings) -> str:
    orquestador = crear_orquestador(llm, settings)
    return orquestador.run(pregunta)


def _comando_version(args: argparse.Namespace) -> int:
    """Consulta o aplica el versionado automático (ver `versionado.py`)."""
    from enterprise_agents import versionado

    if not (args.proximo or args.notas or args.aplicar):
        print(versionado.leer_version())
        return 0

    publicacion = versionado.analizar_repo()
    if args.aplicar and publicacion.hay_cambios:
        versionado.aplicar(publicacion)
    print(publicacion.notas if args.notas else publicacion.version)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="enterprise-agents",
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

    ev = sub.add_parser("eval", help="corre el set de evaluación de escenarios")
    ev.add_argument("--live", action="store_true", help="evalúa contra la API de Claude")

    serve = sub.add_parser("serve", help="levanta la API HTTP y el chat web")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    ver = sub.add_parser("version", help="versionado automático (Conventional Commits)")
    ver.add_argument(
        "--proximo", action="store_true", help="versión que correspondería publicar hoy"
    )
    ver.add_argument("--notas", action="store_true", help="notas de esa versión (changelog)")
    ver.add_argument("--aplicar", action="store_true", help="escribe __version__ y CHANGELOG.md")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    if args.comando == "version":
        return _comando_version(args)

    if args.comando == "serve":
        # Import diferido: FastAPI/uvicorn solo se necesitan para la API.
        from enterprise_agents.api import servir

        print(f"» Chat web en http://{args.host}:{args.port}")
        servir(host=args.host, port=args.port)
        return 0

    settings = load_settings()
    llm, modo = _crear_llm(settings, getattr(args, "live", False))
    print(f"» Modo: {modo}\n")

    if args.comando == "eval":
        from enterprise_agents.evals import correr_evaluacion, imprimir_reporte

        return 0 if imprimir_reporte(correr_evaluacion(llm, settings)) else 1

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
