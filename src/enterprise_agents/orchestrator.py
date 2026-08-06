"""Orquestador: agente coordinador que delega en los especialistas.

Patrón "agente como herramienta": cada especialista se expone al orquestador
como una herramienta de delegación. El orquestador decide a qué dominio
pertenece la consulta, delega, y sintetiza la respuesta final. Ver ADR-0001.
"""

from __future__ import annotations

from enterprise_agents.agents.base import Agent
from enterprise_agents.agents.specialists import (
    crear_analista_datos,
    crear_analista_finanzas,
    crear_gestor_documental,
    crear_gestor_personal,
)
from enterprise_agents.auth import ROLES_TABLERO
from enterprise_agents.config import Settings
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.tools.base import ToolDef

_PROMPT_ORQUESTADOR = """\
Sos el asistente de gestión empresarial de Dicsys, una consultora de servicios
tecnológicos (analítica de datos, BI, ERP y gestión documental).
Los dominios que cubrís son: analítica (ventas/proyectos), finanzas
(cobranzas/facturas), documental (políticas/contratos) y personal (perfiles).

Coordinás un equipo de agentes especialistas y tu trabajo es:
1. Entender la consulta del usuario.
2. Delegar en el o los especialistas correctos mediante las herramientas
   de delegación. Si la consulta cruza dominios (por ejemplo "armá un equipo
   para el proyecto nuevo y decime cuánto facturamos a ese cliente"),
   delegá en varios especialistas.
3. Sintetizar una única respuesta clara en español, empezando por la
   conclusión y citando los datos que aportó cada especialista.

No inventes datos: todo lo fáctico debe salir de los especialistas. Si la
consulta está fuera de estos dominios —o requiere un dominio para el que no
tenés herramienta de delegación disponible— decilo y sugerí a quién contactar.
"""


def _agente_como_herramienta(
    nombre: str, descripcion: str, agente: Agent, ejemplos: tuple[str, ...] = ()
) -> ToolDef:
    return ToolDef(
        name=nombre,
        description=descripcion,
        ejemplos=ejemplos,
        input_schema={
            "type": "object",
            "properties": {
                "tarea": {
                    "type": "string",
                    "description": (
                        "La tarea o pregunta a delegar, redactada de forma "
                        "autocontenida con todo el contexto necesario."
                    ),
                }
            },
            "required": ["tarea"],
        },
        handler=lambda tarea: agente.run(tarea),
    )


def crear_orquestador(llm: LLMClient, settings: Settings, rol: str | None = None) -> Agent:
    """Arma el orquestador con sus especialistas.

    `rol` limita qué dominios puede consultar la sesión (RBAC a nivel de
    herramienta): con rol `consulta` no se exponen finanzas ni personal, para
    que el chat no sea una vía alternativa a los datos que el tablero reserva
    a gestor/admin. `None` (CLI) habilita todos los dominios.
    """
    analista = crear_analista_datos(llm, settings.max_iterations)
    finanzas = crear_analista_finanzas(llm, settings.max_iterations)
    documental = crear_gestor_documental(llm, settings.max_iterations)
    personal = crear_gestor_personal(llm, settings.max_iterations)

    herramientas = [
        _agente_como_herramienta(
            "delegar_analista_datos",
            "Delegá en el analista de datos consultas sobre ventas, facturación, "
            "ingresos por cliente o servicio, y estado/avance de proyectos.",
            analista,
            (
                '"¿cuánto facturamos este año?"',
                '"¿quiénes son nuestros principales clientes?"',
                '"¿qué proyectos están en riesgo por consumo de horas?"',
                '"¿cómo viene el avance de los proyectos?"',
            ),
        ),
        _agente_como_herramienta(
            "delegar_gestor_documental",
            "Delegá en el gestor documental consultas sobre políticas internas, "
            "manuales, contratos, SLA y procesos documentados.",
            documental,
            (
                '"¿qué dice la política de vacaciones?"',
                '"¿cuál es el procedimiento de compras?"',
                '"¿qué SLA tenemos comprometido con los clientes?"',
                '"¿puedo trabajar desde casa?"',
                '"¿cada cuánto se hacen los respaldos?"',
                '"¿qué dice el código de conducta sobre regalos?"',
            ),
        ),
    ]

    if rol is None or rol in ROLES_TABLERO:
        herramientas.extend(
            [
                _agente_como_herramienta(
                    "delegar_analista_finanzas",
                    "Delegá en el analista financiero consultas sobre cobranzas, "
                    "cuentas por cobrar, facturas vencidas, mora y deuda de clientes.",
                    finanzas,
                    (
                        '"¿qué facturas vencidas hay que reclamar?"',
                        '"¿cuánto nos debe cada cliente?"',
                        '"¿cómo está la cobranza este mes?"',
                        '"¿cuál es el monto de la deuda impaga?"',
                        '"¿cuánto nos debe ese cliente?"',
                    ),
                ),
                _agente_como_herramienta(
                    "delegar_gestor_personal",
                    "Delegá en el gestor de personal consultas sobre perfiles, "
                    "habilidades, disponibilidad y asignación de equipos.",
                    personal,
                    (
                        '"¿quién sabe Python y está disponible?"',
                        '"¿qué perfiles tenemos para armar un equipo?"',
                        '"¿hay personas sin asignar?"',
                        '"buscar gente con experiencia en SQL"',
                    ),
                ),
            ]
        )

    return Agent(
        name="orquestador",
        system_prompt=_PROMPT_ORQUESTADOR,
        tools=herramientas,
        llm=llm,
        max_iterations=settings.max_iterations,
    )
