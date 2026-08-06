"""Trazas de ejecución: qué hizo el sistema para responder una consulta.

Un agente sin trazas es inauditable. Se ve la respuesta, pero no de dónde salió,
qué herramientas corrieron, en qué orden, cuánto tardó cada una ni cuánto
contexto consumió. Cuando algo sale mal —una cifra rara, una latencia de diez
segundos, una respuesta vacía— sin traza solo queda volver a ejecutar y mirar.

Diseño:

- **Los agentes no saben que existe.** El bucle agéntico emite eventos y quien
  quiera escucharlos abre un `capturar()`. Fuera de una captura, registrar no
  cuesta nada.
- **Variable de contexto en vez de parámetro.** No contamina la firma de
  `Agent.run()` ni la de las herramientas, y el anidamiento —orquestador que
  delega en un especialista que llama a una herramienta— se resuelve solo.
- **Jerarquía real.** Cada span conoce a su padre, así que la traza se puede
  dibujar como el árbol que efectivamente fue, y no como una lista plana donde
  el orden de finalización confunde: las herramientas internas terminan *antes*
  que la delegación que las contiene.

Consumidores: el verificador de fundamentación (`evaluacion/`), que necesita
saber qué produjo cada herramienta, y el visor de `/trazas`.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from enterprise_agents import tokens as tokens_mod

_actual: ContextVar[Traza | None] = ContextVar("traza_actual", default=None)
_padre: ContextVar[int | None] = ContextVar("span_padre", default=None)


@dataclass
class Span:
    """Una operación registrada: una llamada a herramienta dentro de un agente."""

    id: int
    padre: int | None
    agente: str
    herramienta: str
    argumentos: dict[str, Any]
    resultado: str = ""
    milisegundos: float = 0.0
    error: bool = False

    @property
    def es_delegacion(self) -> bool:
        return self.herramienta.startswith("delegar_")

    @property
    def tokens_resultado(self) -> int:
        """Tokens estimados que este resultado agrega al contexto del modelo."""
        return tokens_mod.estimar(self.resultado)

    def resumen(self, ancho: int = 70) -> str:
        """Primeras palabras del resultado, salteando la envoltura de saneamiento.

        El contenido documental viaja envuelto en un preámbulo de seguridad (ver
        `seguridad/saneamiento.py`). Mostrarlo en el visor sería ruido: todos los
        spans documentales se verían iguales y ninguno diría qué devolvió. Se
        arranca después de la marca de apertura, que termina en `>>>`.
        """
        texto = self.resultado
        marca = texto.find(">>>\n")
        if marca != -1:
            texto = texto[marca + 4 :]
        texto = " ".join(texto.split())
        return texto[:ancho] + ("…" if len(texto) > ancho else "")


@dataclass
class Traza:
    """Todo lo ocurrido durante la resolución de una consulta."""

    consulta: str = ""
    spans: list[Span] = field(default_factory=list)
    respuesta: str = ""
    milisegundos_total: float = 0.0
    modo: str = ""

    # --- Vistas -------------------------------------------------------------

    @property
    def herramientas(self) -> list[str]:
        """Nombres de las herramientas ejecutadas, en orden de invocación."""
        return [s.herramienta for s in self.spans]

    @property
    def evidencia(self) -> list[str]:
        """Salidas de las herramientas que leyeron datos.

        Se excluyen las delegaciones: su "resultado" es la respuesta redactada
        por un especialista, no un dato leído de una fuente. Tomarla como
        evidencia haría circular la verificación —el texto del modelo se
        justificaría a sí mismo—, que es exactamente lo que hay que evitar.
        """
        return [s.resultado for s in self.spans if not s.es_delegacion]

    @property
    def milisegundos(self) -> float:
        """Tiempo dentro de herramientas. No suma los anidados dos veces."""
        return sum(s.milisegundos for s in self.spans if s.padre is None)

    @property
    def tokens_contexto(self) -> int:
        """Tokens estimados que las herramientas inyectaron en algún contexto.

        Suma **todos** los spans, incluidas las delegaciones, y eso es
        deliberado: cada agente tiene su propio contexto, así que la salida de
        una herramienta cuenta una vez en el especialista que la llamó y otra
        vez —dentro de la respuesta del especialista— en el orquestador. No es
        doble conteo: es la carga total que el sistema procesó, que es lo que
        determina el costo. Para ver el aporte de un solo nivel está
        `tokens_por_agente`.
        """
        return sum(s.tokens_resultado for s in self.spans)

    @property
    def tokens_por_agente(self) -> dict[str, int]:
        """Tokens que entraron al contexto de cada agente."""
        por_agente: dict[str, int] = {}
        for span in self.spans:
            por_agente[span.agente] = por_agente.get(span.agente, 0) + span.tokens_resultado
        return por_agente

    @property
    def tokens_respuesta(self) -> int:
        return tokens_mod.estimar(self.respuesta)

    @property
    def hubo_error(self) -> bool:
        return any(s.error for s in self.spans)

    @property
    def agentes(self) -> list[str]:
        """Agentes que intervinieron, sin repetir y en orden de aparición."""
        vistos: list[str] = []
        for span in self.spans:
            if span.agente not in vistos:
                vistos.append(span.agente)
        return vistos

    def hijos(self, padre: int | None) -> list[Span]:
        """Spans directos de un padre (None para la raíz)."""
        return [s for s in self.spans if s.padre == padre]

    def arbol(self) -> list[tuple[int, Span]]:
        """La traza aplanada como `(profundidad, span)`, en orden de ejecución."""
        salida: list[tuple[int, Span]] = []

        def recorrer(padre: int | None, nivel: int) -> None:
            for span in self.hijos(padre):
                salida.append((nivel, span))
                recorrer(span.id, nivel + 1)

        recorrer(None, 0)
        return salida

    def a_dict(self) -> dict[str, Any]:
        """Forma serializable, para la API y el visor web."""
        return {
            "consulta": self.consulta,
            "respuesta": self.respuesta,
            "modo": self.modo,
            "milisegundos": round(self.milisegundos_total or self.milisegundos, 1),
            "tokens_contexto": self.tokens_contexto,
            "tokens_por_agente": self.tokens_por_agente,
            "tokens_respuesta": self.tokens_respuesta,
            "hubo_error": self.hubo_error,
            "spans": [
                {
                    "nivel": nivel,
                    "agente": span.agente,
                    "herramienta": span.herramienta,
                    "argumentos": {k: str(v)[:200] for k, v in span.argumentos.items()},
                    "resumen": span.resumen(),
                    "milisegundos": round(span.milisegundos, 1),
                    "tokens": span.tokens_resultado,
                    "error": span.error,
                }
                for nivel, span in self.arbol()
            ],
        }

    def imprimir(self) -> str:
        """Representación de texto del árbol, para la CLI y los logs."""
        lineas = [f"consulta: {self.consulta}"]
        for nivel, span in self.arbol():
            sangria = "  " * (nivel + 1)
            marca = "✗" if span.error else "•"
            medida = tokens_mod.formatear(span.tokens_resultado)
            lineas.append(
                f"{sangria}{marca} [{span.agente}] {span.herramienta} "
                f"— {span.milisegundos:.0f} ms, ~{medida} tokens"
            )
        lineas.append(
            f"total: {self.milisegundos:.0f} ms · "
            f"~{tokens_mod.formatear(self.tokens_contexto)} tokens de contexto"
        )
        return "\n".join(lineas)


@contextmanager
def capturar(consulta: str = "", modo: str = "") -> Iterator[Traza]:
    """Captura en una `Traza` todo lo que ocurra dentro del bloque."""
    traza = Traza(consulta=consulta, modo=modo)
    testigo_traza = _actual.set(traza)
    testigo_padre = _padre.set(None)
    inicio = time.perf_counter()
    try:
        yield traza
    finally:
        traza.milisegundos_total = (time.perf_counter() - inicio) * 1000
        _padre.reset(testigo_padre)
        _actual.reset(testigo_traza)


@dataclass
class Salida:
    """Buzón donde el llamador deja lo que produjo la herramienta.

    Se usa un objeto y no el valor de retorno porque el bucle agéntico **atrapa
    las excepciones de las herramientas a propósito** —el error vuelve al modelo
    como `tool_result` para que se recupere— así que la traza nunca las vería
    propagarse. El llamador marca `error` explícitamente.
    """

    resultado: str = ""
    error: bool = False


@contextmanager
def registrar(agente: str, herramienta: str, argumentos: dict[str, Any]) -> Iterator[Salida]:
    """Registra una llamada a herramienta si hay una captura activa.

    El span se agrega **al entrar**, no al salir: así conserva el orden de
    invocación y sus hijos pueden apuntarlo como padre. Si se agregara al final,
    una herramienta anidada quedaría registrada antes que la delegación que la
    contiene.
    """
    traza = _actual.get()
    if traza is None:
        yield Salida()
        return

    span = Span(
        id=len(traza.spans),
        padre=_padre.get(),
        agente=agente,
        herramienta=herramienta,
        argumentos=dict(argumentos),
    )
    traza.spans.append(span)

    salida = Salida()
    testigo = _padre.set(span.id)
    inicio = time.perf_counter()
    try:
        yield salida
    except Exception:
        # Una excepción que sí se propaga (no debería, pero por si acaso).
        salida.error = True
        raise
    finally:
        span.resultado = salida.resultado
        span.error = salida.error
        span.milisegundos = (time.perf_counter() - inicio) * 1000
        _padre.reset(testigo)
