"""Cliente simulado para demos offline y tests (ver ADR-0003).

No llama a ningún servicio externo: elige herramientas por palabras clave y
resume los resultados de forma determinística. Permite ejecutar la demo y la
suite de tests sin una clave de API, y hace reproducible el flujo agéntico
completo (selección de herramienta → ejecución → síntesis).

Limitación conocida (ver ADR-0003): el mock ejecuta una sola delegación por
consulta; las consultas que cruzan dominios solo las resuelve el modelo real
(modo `--live`).
"""

from __future__ import annotations

from typing import Any

from enterprise_agents.llm.base import LLMReply
from enterprise_agents.text import coincide_palabra, coincide_prefijo, normalizar

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

# Keywords por dominio, definidas una sola vez y reusadas por la herramienta de
# delegación del orquestador y por las herramientas del especialista, para que
# ambos niveles enruten igual.
_KW_ANALITICA = ["venta", "factur", "ingreso", "proyecto"]
_KW_FINANZAS = ["cobranza", "cobrar", "vencid", "deuda", "adeuda", "impaga"]
_KW_DOCUMENTAL = ["politica", "vacacion", "documento", "contrato", "onboarding", "sla", "licencia"]
_KW_PERSONAL = ["empleado", "personal", "habilidad", "perfil", "equipo", "disponib"]

# Palabras clave por herramienta. Se comparan como PREFIJO DE PALABRA (no
# subcadena libre): 'factur' cubre 'facturamos'/'facturación', pero 'sql' no
# matchea dentro de 'postgresql' ni 'deuda' dentro de otra palabra.
_KEYWORDS: dict[str, list[str]] = {
    "delegar_analista_datos": [*_KW_ANALITICA, "avance", "hora", "riesgo"],
    "delegar_analista_finanzas": [*_KW_FINANZAS, "reclamar", "mora"],
    "delegar_gestor_documental": _KW_DOCUMENTAL,
    "delegar_gestor_personal": [*_KW_PERSONAL, "asignar", "asignacion"],
    "resumen_ventas": ["venta", "factur", "ingreso", "cliente"],
    "avance_proyectos": ["proyecto", "avance", "hora", "riesgo", "estado"],
    "estado_cobranzas": ["cobranza", "cobrar", "total"],
    "facturas_vencidas": ["vencid", "mora", "reclamar", "antigua", "impaga"],
    "deuda_por_cliente": ["deuda", "adeuda", "cliente"],
    "buscar_documentos": _KW_DOCUMENTAL,
    "leer_documento": ["leer", "texto completo"],
    "buscar_por_habilidad": ["habilidad", "sabe", "perfil", *_HABILIDADES_CONOCIDAS],
    "disponibilidad_equipo": ["disponib", "asignar", "libre", "capacidad", "equipo"],
}


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
                            "Probá preguntar por ventas, proyectos, cobranzas, documentos "
                            "internos o disponibilidad del equipo."
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
        texto_norm = normalizar(texto)
        mejor: tuple[int, str] | None = None
        for tool in tools:
            nombre = tool["name"]
            puntaje = sum(1 for kw in _KEYWORDS.get(nombre, []) if coincide_prefijo(kw, texto_norm))
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
                if coincide_palabra(habilidad, texto_norm):
                    return {"habilidad": habilidad}
            # Sin habilidad reconocida: usar la última palabra significativa en
            # lugar de un default fijo, para no responder con un perfil ajeno.
            palabras = [p for p in texto_norm.split() if len(p) >= 3]
            return {"habilidad": palabras[-1] if palabras else texto.strip()}
        if nombre == "leer_documento":
            return {"nombre": "politica-vacaciones.md"}
        return {}
