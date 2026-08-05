"""Agentes especialistas de dominio."""

from __future__ import annotations

from enterprise_agents.agents.base import Agent
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.tools.analytics import HERRAMIENTAS_ANALITICA
from enterprise_agents.tools.documents import HERRAMIENTAS_DOCUMENTOS
from enterprise_agents.tools.finance import HERRAMIENTAS_FINANZAS
from enterprise_agents.tools.hr import HERRAMIENTAS_PERSONAL

_PROMPT_ANALISTA = """\
Sos el analista de datos de Dicsys, una consultora de servicios tecnológicos.
Respondés consultas sobre ventas, facturación y estado de proyectos usando las
herramientas disponibles, que consultan los datos operativos reales.

Basá cada afirmación en el resultado de las herramientas: no inventes cifras.
Respondé en español, con los números clave primero y el detalle después. Si
detectás un riesgo (por ejemplo, un proyecto con consumo de horas alto),
mencionalo explícitamente.
"""

_PROMPT_DOCUMENTAL = """\
Sos el gestor documental de Dicsys. Respondés consultas sobre políticas
internas, manuales, contratos y procesos usando el repositorio documental.

Flujo recomendado: primero buscar_documentos para identificar el documento
correcto, después leer_documento si necesitás el contenido completo. Citá
siempre el documento fuente (nombre y versión si está disponible) y respondé
en español. Si la respuesta no está en los documentos, decilo claramente.
"""

_PROMPT_PERSONAL = """\
Sos el gestor de personal de Dicsys. Respondés consultas sobre perfiles,
habilidades, asignaciones y disponibilidad del equipo usando las herramientas
disponibles.

Tratá los datos de personas con cuidado: informá solo lo necesario para la
consulta (rol, habilidades, disponibilidad) y no especules sobre desempeño.
Respondé en español y, cuando propongas una asignación, priorizá a las
personas con mayor disponibilidad.
"""


def crear_analista_datos(llm: LLMClient, max_iterations: int = 8) -> Agent:
    return Agent(
        name="analista_datos",
        system_prompt=_PROMPT_ANALISTA,
        tools=HERRAMIENTAS_ANALITICA,
        llm=llm,
        max_iterations=max_iterations,
    )


def crear_gestor_documental(llm: LLMClient, max_iterations: int = 8) -> Agent:
    return Agent(
        name="gestor_documental",
        system_prompt=_PROMPT_DOCUMENTAL,
        tools=HERRAMIENTAS_DOCUMENTOS,
        llm=llm,
        max_iterations=max_iterations,
    )


def crear_gestor_personal(llm: LLMClient, max_iterations: int = 8) -> Agent:
    return Agent(
        name="gestor_personal",
        system_prompt=_PROMPT_PERSONAL,
        tools=HERRAMIENTAS_PERSONAL,
        llm=llm,
        max_iterations=max_iterations,
    )


_PROMPT_FINANZAS = """\
Sos el analista financiero de la empresa. Respondés consultas sobre cobranzas,
facturas y deuda de clientes usando las herramientas disponibles.

Basá cada cifra en el resultado de las herramientas: no inventes montos.
Respondé en español, con el total relevante primero. Si hay facturas vencidas,
señalá cuáles conviene reclamar primero (las más antiguas y de mayor monto).
"""


def crear_analista_finanzas(llm: LLMClient, max_iterations: int = 8) -> Agent:
    return Agent(
        name="analista_finanzas",
        system_prompt=_PROMPT_FINANZAS,
        tools=HERRAMIENTAS_FINANZAS,
        llm=llm,
        max_iterations=max_iterations,
    )
