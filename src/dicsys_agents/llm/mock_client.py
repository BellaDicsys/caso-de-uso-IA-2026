"""Cliente simulado para demos offline y tests (ver ADR-0003).

No llama a ningún servicio externo: elige herramientas por palabras clave y
resume los resultados de forma determinística. Permite ejecutar la demo y la
suite de tests sin una clave de API, y hace reproducible el flujo agéntico
completo (selección de herramienta → ejecución → síntesis).
"""

from __future__ import annotations

import unicodedata
from typing import Any

from dicsys_agents.llm.base import LLMReply

# Habilidades reconocidas en los datos de ejemplo, para inferir argumentos.
_HABILIDADES_CONOCIDAS = [
    "python",
    "sql",
    "power bi",
    "tableau",
    "sap",
    "aws",
    "mlops",
    "airflow",
    "spark",
    "dbt",
    "snowflake",
    "terraform",
    "docker",
    "scrum",
]

# Palabras clave por herramienta. La selección funciona igual para las
# herramientas de dominio y para las de delegación del orquestador.
_KEYWORDS: dict[str, list[str]] = {
    "delegar_analista_datos": ["venta", "factur", "ingreso", "monto", "proyecto", "avance"],
    "delegar_gestor_documental": [
        "politic",
        "vacacion",
        "documento",
        "contrato",
        "onboarding",
        "sla",
        "licencia",
    ],
    "delegar_gestor_personal": [
        "empleado",
        "personal",
        "habilidad",
        "disponib",
        "asignar",
        "equipo",
        "perfil",
    ],
    "resumen_ventas": ["venta", "factur", "ingreso", "monto", "cliente"],
    "avance_proyectos": ["proyecto", "avance", "hora", "riesgo", "estado"],
    "buscar_documentos": [
        "politic",
        "vacacion",
        "documento",
        "contrato",
        "onboarding",
        "sla",
        "licencia",
    ],
    "leer_documento": ["leer", "texto completo"],
    "buscar_por_habilidad": ["habilidad", "sabe", "perfil", *_HABILIDADES_CONOCIDAS],
    "disponibilidad_equipo": ["disponib", "asignar", "libre", "capacidad", "equipo"],
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


class MockLLMClient:
    """Implementación determinística de `LLMClient` sin llamadas externas."""

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMReply:
        ultimo = messages[-1]
        contenido = ultimo.get("content")

        # Si el último mensaje trae resultados de herramientas, se sintetiza
        # una respuesta final a partir de ellos.
        if isinstance(contenido, list):
            resultados = [b for b in contenido if b.get("type") == "tool_result"]
            if resultados:
                cuerpo = "\n\n".join(str(r.get("content", "")) for r in resultados)
                return LLMReply(
                    content=[{"type": "text", "text": cuerpo.strip()}],
                    stop_reason="end_turn",
                )

        texto_usuario = self._texto_del_usuario(messages)
        eleccion = self._elegir_herramienta(texto_usuario, tools)
        if eleccion is None:
            return LLMReply(
                content=[
                    {
                        "type": "text",
                        "text": (
                            "(modo demo) No identifiqué un dominio para esta consulta. "
                            "Probá preguntar por ventas, proyectos, documentos internos "
                            "o disponibilidad del equipo."
                        ),
                    }
                ],
                stop_reason="end_turn",
            )

        nombre, argumentos = eleccion
        return LLMReply(
            content=[
                {
                    "type": "tool_use",
                    "id": f"mock_{nombre}",
                    "name": nombre,
                    "input": argumentos,
                }
            ],
            stop_reason="tool_use",
        )

    @staticmethod
    def _texto_del_usuario(messages: list[dict[str, Any]]) -> str:
        for mensaje in reversed(messages):
            if mensaje.get("role") != "user":
                continue
            contenido = mensaje.get("content")
            if isinstance(contenido, str):
                return contenido
            if isinstance(contenido, list):
                textos = [b.get("text", "") for b in contenido if b.get("type") == "text"]
                if textos:
                    return "\n".join(textos)
        return ""

    def _elegir_herramienta(
        self, texto: str, tools: list[dict[str, Any]]
    ) -> tuple[str, dict[str, Any]] | None:
        texto_norm = _normalizar(texto)
        mejor: tuple[int, str] | None = None
        for tool in tools:
            nombre = tool["name"]
            puntaje = sum(1 for kw in _KEYWORDS.get(nombre, []) if kw in texto_norm)
            if puntaje > 0 and (mejor is None or puntaje > mejor[0]):
                mejor = (puntaje, nombre)
        if mejor is None:
            return None
        nombre = mejor[1]
        return nombre, self._armar_argumentos(nombre, texto, texto_norm)

    @staticmethod
    def _armar_argumentos(nombre: str, texto: str, texto_norm: str) -> dict[str, Any]:
        if nombre.startswith("delegar_"):
            return {"tarea": texto}
        if nombre == "buscar_documentos":
            return {"consulta": texto}
        if nombre == "buscar_por_habilidad":
            for habilidad in _HABILIDADES_CONOCIDAS:
                if habilidad in texto_norm:
                    return {"habilidad": habilidad}
            return {"habilidad": "python"}
        if nombre == "leer_documento":
            return {"nombre": "politica-vacaciones.md"}
        return {}
