"""Herramientas de gestión documental sobre `data/documentos/`.

La búsqueda usa el motor de recuperación híbrido (`recuperacion/`): BM25 y
espacio latente fusionados por RRF, sobre fragmentos y no sobre documentos
enteros. Devuelve el pasaje concreto además del nombre del archivo, de modo que
el agente pueda responder sin tener que leer el documento completo.

La versión anterior contaba coincidencias de subcadena por documento. Con tres
documentos alcanzaba; con treinta dejó de funcionar —"¿qué dice la política de
vacaciones?" devolvía primero la política de teletrabajo, porque "política"
aparece en casi todos los títulos— y ese fue el motivo del cambio.
"""

from __future__ import annotations

from enterprise_agents.config import DOCS_DIR
from enterprise_agents.recuperacion.motor import motor_por_defecto
from enterprise_agents.seguridad.saneamiento import sanear
from enterprise_agents.tools.base import ToolDef

# Cuántos pasajes se le devuelven al modelo. Suficientes para responder la
# mayoría de las consultas sin llamar a leer_documento, sin inundar el contexto.
PASAJES = 4


def buscar_documentos(consulta: str) -> str:
    resultados = motor_por_defecto().buscar(consulta, k=PASAJES)
    if not resultados:
        disponibles = ", ".join(p.name for p in sorted(DOCS_DIR.glob("*.md")))
        return f"Sin coincidencias para '{consulta}'. Documentos disponibles: {disponibles}."

    bloques = []
    for resultado in resultados:
        fragmento = resultado.fragmento
        bloques.append(f"[{fragmento.documento}] {fragmento.migaja}\n{fragmento.texto}")
    # El contenido documental es entrada no confiable: se sanea antes de que
    # llegue al modelo (ver seguridad/saneamiento.py y ADR-0010).
    return sanear(
        "Pasajes relevantes del repositorio documental "
        "(usar leer_documento si hace falta el texto completo):\n\n" + "\n\n".join(bloques),
        origen="buscar_documentos",
    ).texto


def leer_documento(nombre: str) -> str:
    # El nombre viene del modelo: se valida que resuelva dentro del
    # repositorio documental para impedir path traversal.
    path = (DOCS_DIR / nombre).resolve()
    if not path.is_relative_to(DOCS_DIR.resolve()) or path.suffix != ".md":
        return f"Nombre de documento inválido: {nombre}"
    if not path.exists():
        disponibles = ", ".join(p.name for p in sorted(DOCS_DIR.glob("*.md")))
        return f"No existe '{nombre}'. Documentos disponibles: {disponibles}."
    return sanear(path.read_text(encoding="utf-8"), origen=nombre).texto


HERRAMIENTAS_DOCUMENTOS = [
    ToolDef(
        name="buscar_documentos",
        description=(
            "Busca en el repositorio documental interno (políticas, manuales, "
            "contratos) y devuelve los pasajes más relevantes para una consulta, "
            "con el documento y la sección de la que salió cada uno. "
            "Llamala primero cuando la consulta refiera a normativa interna, "
            "beneficios, contratos o procesos. Los pasajes suelen alcanzar para "
            "responder: solo usá leer_documento si necesitás el texto completo."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": "Términos de búsqueda en lenguaje natural.",
                }
            },
            "required": ["consulta"],
        },
        handler=buscar_documentos,
        ejemplos=(
            "¿qué dice la política de vacaciones?",
            "¿cuál es el procedimiento de compras?",
            "¿qué SLA tenemos comprometido?",
            "¿cada cuánto se hacen los respaldos?",
            "¿puedo trabajar desde casa?",
            "¿qué dice el código de conducta?",
            "normativa interna sobre viáticos",
        ),
    ),
    ToolDef(
        name="leer_documento",
        description=(
            "Devuelve el contenido íntegro de un documento del repositorio "
            "interno. Llamala solo si los pasajes que devolvió buscar_documentos "
            "no alcanzan, usando el nombre de archivo exacto que ella informó."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nombre": {
                    "type": "string",
                    "description": "Nombre del archivo, incluida la extensión .md.",
                }
            },
            "required": ["nombre"],
        },
        handler=leer_documento,
        ejemplos=(
            "mostrame el texto completo de ese archivo",
            "abrí el documento entero",
            "quiero leer el contenido íntegro del md",
        ),
    ),
]
