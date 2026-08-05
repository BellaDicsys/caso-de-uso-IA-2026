"""Herramientas de gestión de personal sobre `data/empleados.csv`.

En un despliegue real, estas funciones consultan el sistema de RRHH (por
ejemplo vía API del HRIS) en lugar de un CSV local.
"""

from __future__ import annotations

import csv
import unicodedata

from dicsys_agents.config import DATA_DIR
from dicsys_agents.tools.base import ToolDef


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _leer_empleados() -> list[dict[str, str]]:
    with (DATA_DIR / "empleados.csv").open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def _formatear(filas: list[dict[str, str]]) -> str:
    return "\n".join(
        f"  - {f['nombre']} ({f['rol']} {f['seniority']}) — "
        f"habilidades: {f['habilidades'].replace(';', ', ')} — "
        f"proyecto: {f['proyecto_actual']} — disponibilidad: {f['disponibilidad_pct']}%"
        for f in filas
    )


def buscar_por_habilidad(habilidad: str) -> str:
    objetivo = _normalizar(habilidad)
    filas = [
        f for f in _leer_empleados() if objetivo in _normalizar(f["habilidades"].replace(";", " "))
    ]
    if not filas:
        return f"Ningún perfil registra la habilidad '{habilidad}'."
    filas.sort(key=lambda f: int(f["disponibilidad_pct"]), reverse=True)
    return f"Perfiles con '{habilidad}' (ordenados por disponibilidad):\n" + _formatear(filas)


def disponibilidad_equipo(minimo_pct: int = 50) -> str:
    filas = [f for f in _leer_empleados() if int(f["disponibilidad_pct"]) >= minimo_pct]
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
    ),
]
