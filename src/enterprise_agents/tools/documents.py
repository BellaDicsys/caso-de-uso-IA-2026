"""Herramientas de gestión documental sobre `data/documentos/`.

Búsqueda léxica simple por términos. En un despliegue real este módulo se
reemplaza por búsqueda semántica sobre el repositorio documental del cliente
(ver docs/arquitectura.md).
"""

from __future__ import annotations

import unicodedata

from enterprise_agents.config import DOCS_DIR
from enterprise_agents.tools.base import ToolDef


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def buscar_documentos(consulta: str) -> str:
    terminos = [t for t in _normalizar(consulta).split() if len(t) > 3]
    resultados = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        texto = path.read_text(encoding="utf-8")
        texto_norm = _normalizar(texto)
        coincidencias = sum(texto_norm.count(t) for t in terminos)
        if coincidencias:
            primera_linea = texto.strip().splitlines()[0].lstrip("# ")
            resultados.append((coincidencias, path.name, primera_linea))

    if not resultados:
        disponibles = ", ".join(p.name for p in sorted(DOCS_DIR.glob("*.md")))
        return f"Sin coincidencias para '{consulta}'. Documentos disponibles: {disponibles}."

    resultados.sort(reverse=True)
    lineas = [f"  - {nombre} ({titulo}) — {n} coincidencias" for n, nombre, titulo in resultados]
    return "Documentos relevantes (usar leer_documento para el contenido completo):\n" + "\n".join(
        lineas
    )


def leer_documento(nombre: str) -> str:
    # El nombre viene del modelo: se valida que resuelva dentro del
    # repositorio documental para impedir path traversal.
    path = (DOCS_DIR / nombre).resolve()
    if not path.is_relative_to(DOCS_DIR.resolve()) or path.suffix != ".md":
        return f"Nombre de documento inválido: {nombre}"
    if not path.exists():
        disponibles = ", ".join(p.name for p in sorted(DOCS_DIR.glob("*.md")))
        return f"No existe '{nombre}'. Documentos disponibles: {disponibles}."
    return path.read_text(encoding="utf-8")


HERRAMIENTAS_DOCUMENTOS = [
    ToolDef(
        name="buscar_documentos",
        description=(
            "Busca en el repositorio documental interno (políticas, manuales, "
            "contratos) y devuelve los documentos más relevantes para una consulta. "
            "Llamala primero cuando la consulta refiera a normativa interna, "
            "beneficios, contratos o procesos."
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
    ),
    ToolDef(
        name="leer_documento",
        description=(
            "Devuelve el contenido completo de un documento del repositorio "
            "interno. Llamala después de buscar_documentos, con el nombre exacto "
            "del archivo (por ejemplo 'politica-vacaciones.md')."
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
    ),
]
