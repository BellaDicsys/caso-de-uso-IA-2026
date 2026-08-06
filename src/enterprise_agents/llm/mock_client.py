"""Cliente simulado para demos offline y tests (ver ADR-0003 y ADR-0008).

No llama a ningún servicio externo: elige la herramienta por **similitud
semántica** contra su descripción y sus enunciados de ejemplo —el mismo motor
híbrido que usa la recuperación documental, aplicado a herramientas en vez de
pasajes— y resume los resultados de forma determinística. Permite ejecutar la
demo y la suite de tests sin una clave de API, y hace reproducible el flujo
agéntico completo (selección de herramienta → ejecución → síntesis).

Hasta la versión anterior el ruteo era una tabla de prefijos mantenida a mano,
que había que sincronizar con cada herramienta nueva y que ya había producido
errores documentados en la auditoría. Ahora la elección se apoya en el mismo
texto que orienta al modelo real.

Limitación conocida (ver ADR-0003): el mock ejecuta una sola delegación por
consulta; las consultas que cruzan dominios solo las resuelve el modelo real
(modo `--live`).
"""

from __future__ import annotations

from typing import Any

from enterprise_agents.llm.base import LLMReply
from enterprise_agents.llm.router import RouterSemantico
from enterprise_agents.recuperacion.motor import motor
from enterprise_agents.text import coincide_palabra, normalizar

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


def _texto_de_intencion(tool: dict[str, Any]) -> str:
    """Texto de ruteo a partir del esquema que recibe el cliente.

    `ToolDef.texto_de_intencion()` incluye además los enunciados de ejemplo, que
    no viajan en el esquema de la API porque el modelo real no los usa. El
    orquestador los inyecta al construir el agente (ver `Agent.esquemas`).
    """
    partes = [tool["name"].replace("_", " "), tool.get("description", "")]
    partes.extend(tool.get("ejemplos", ()))
    for propiedad in tool.get("input_schema", {}).get("properties", {}).values():
        if propiedad.get("description"):
            partes.append(propiedad["description"])
    return " ".join(partes)


class MockLLMClient:
    """Implementación determinística de `LLMClient` sin llamadas externas."""

    def __init__(self) -> None:
        self._routers: dict[tuple[str, ...], RouterSemantico] = {}

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
        contexto = self._contexto_previo(messages)
        eleccion = self._elegir_herramienta(texto_usuario, tools, contexto)
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
    def _contexto_previo(messages: list[dict[str, Any]]) -> str:
        """Términos de la consulta anterior del usuario, si la hay.

        El modelo real entiende la referencia de una repregunta leyendo el
        historial. El cliente simulado no razona, así que necesita el referente
        explícito: se lo arma con los términos informativos del turno previo.
        """
        from enterprise_agents.memoria import es_autosuficiente
        from enterprise_agents.recuperacion.terminos import terminos

        anteriores = [m for m in messages if m.get("role") == "user"]
        if len(anteriores) < 2:
            return ""
        actual = anteriores[-1].get("content")
        if isinstance(actual, str) and es_autosuficiente(actual):
            return ""
        previa = anteriores[-2].get("content")
        return " ".join(terminos(previa)) if isinstance(previa, str) else ""

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

    def _router(self, tools: list[dict[str, Any]]) -> RouterSemantico:
        """Router del conjunto de herramientas ofrecido, construido una sola vez.

        Cada agente ofrece un conjunto distinto —el orquestador solo delegaciones,
        cada especialista las suyas— y el rol puede recortarlo todavía más, así
        que la clave de caché es el conjunto de nombres.
        """
        clave = tuple(sorted(t["name"] for t in tools))
        router = self._routers.get(clave)
        if router is None:
            router = RouterSemantico({t["name"]: _texto_de_intencion(t) for t in tools})
            self._routers[clave] = router
        return router

    def _elegir_herramienta(
        self, texto: str, tools: list[dict[str, Any]], contexto: str = ""
    ) -> tuple[str, dict[str, Any]] | None:
        # Una repregunta ("¿y la más antigua?") no se rutea sola: se la completa
        # con los términos del turno anterior antes de elegir herramienta.
        contextualizada = f"{texto} {contexto}".strip()
        eleccion = self._router(tools).elegir(contextualizada)
        if eleccion is None:
            return None
        # La tarea que se delega va contextualizada, no cruda: el esquema de la
        # herramienta de delegación pide una tarea "autocontenida con todo el
        # contexto necesario", y eso es justo lo que un modelo real redactaría.
        # Sin esto el orquestador rutea bien y el especialista recibe "¿y la más
        # antigua?" sin referente, así que falla un nivel más abajo.
        return eleccion.nombre, self._armar_argumentos(
            eleccion.nombre, contextualizada, normalizar(contextualizada)
        )

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
            # Antes devolvía un nombre de archivo fijo: cualquier consulta que
            # cayera acá respondía con la política de vacaciones, y parecía
            # acertar por casualidad. Ahora el documento lo resuelve el motor de
            # recuperación, igual que lo haría el modelo real tras buscar.
            documentos = motor().buscar_documentos(texto, k=1)
            return {"nombre": documentos[0][0] if documentos else "no-encontrado.md"}
        return {}
