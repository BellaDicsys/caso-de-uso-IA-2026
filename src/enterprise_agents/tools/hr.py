"""Herramientas de gestión de personal sobre `data/empleados.csv`.

En un despliegue real, estas funciones consultan el sistema de RRHH (por
ejemplo vía API del HRIS) en lugar de un CSV local.
"""

from __future__ import annotations

from enterprise_agents.datos import leer_csv
from enterprise_agents.text import coincide_palabra, normalizar
from enterprise_agents.tools.base import ToolDef


def _formatear(filas: list[dict[str, str]]) -> str:
    return "\n".join(
        f"  - {f['nombre']} ({f['rol']} {f['seniority']}) — "
        f"habilidades: {f['habilidades'].replace(';', ', ')} — "
        f"proyecto: {f['proyecto_actual']} — disponibilidad: {f['disponibilidad_pct']}%"
        for f in filas
    )


def buscar_por_habilidad(habilidad: str) -> str:
    # Match por palabra completa: 'SQL' no debe matchear 'PostgreSQL'.
    objetivo = normalizar(habilidad)
    filas = [
        f
        for f in leer_csv("empleados.csv")
        if coincide_palabra(objetivo, normalizar(f["habilidades"].replace(";", " ")))
    ]
    if not filas:
        return f"Ningún perfil registra la habilidad '{habilidad}'."
    filas.sort(key=lambda f: int(f["disponibilidad_pct"]), reverse=True)
    return f"Perfiles con '{habilidad}' (ordenados por disponibilidad):\n" + _formatear(filas)


def disponibilidad_equipo(minimo_pct: int = 50) -> str:
    filas = [f for f in leer_csv("empleados.csv") if int(f["disponibilidad_pct"]) >= minimo_pct]
    if not filas:
        return f"Nadie tiene disponibilidad mayor o igual a {minimo_pct}%."
    filas.sort(key=lambda f: int(f["disponibilidad_pct"]), reverse=True)
    return f"Personas con disponibilidad ≥ {minimo_pct}%:\n" + _formatear(filas)


HERRAMIENTAS_PERSONAL = [
    ToolDef(
        name="buscar_por_habilidad",
        description=(
            "Busca empleados que tengan una habilidad técnica específica (por "
            "ejemplo Python, SQL, Power BI, SAP) y los ordena por disponibilidad. "
            "Llamala cuando se necesite armar un equipo o encontrar un perfil."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "habilidad": {
                    "type": "string",
                    "description": "Habilidad técnica a buscar, por ejemplo 'Python'.",
                }
            },
            "required": ["habilidad"],
        },
        handler=buscar_por_habilidad,
        ejemplos=(
            "¿quién sabe Python?",
            "perfiles con experiencia en SQL",
            "¿tenemos gente que maneje Power BI?",
            "buscar personas con una habilidad técnica",
        ),
    ),
    ToolDef(
        name="disponibilidad_equipo",
        description=(
            "Lista las personas con disponibilidad libre por encima de un umbral "
            "porcentual. Llamala cuando la consulta sea sobre capacidad libre, "
            "asignaciones o quién puede tomar un proyecto nuevo."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "minimo_pct": {
                    "type": "integer",
                    "description": "Umbral mínimo de disponibilidad (0-100). Por defecto 50.",
                }
            },
            "required": [],
        },
        handler=disponibilidad_equipo,
        ejemplos=(
            "¿quién está libre para un proyecto nuevo?",
            "¿cómo está la disponibilidad del equipo?",
            "¿hay personas sin asignar?",
            "capacidad ociosa del equipo",
        ),
    ),
]
