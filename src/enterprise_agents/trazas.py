"""Registro de lo que hizo el sistema al resolver una consulta.

Un agente sin trazas es inauditable: se ve la respuesta pero no de dónde salió,
qué herramientas se ejecutaron ni cuánto tardó cada una. Este módulo captura esa
información sin que los agentes tengan que saber nada al respecto: el bucle
agéntico emite eventos y quien quiera escucharlos abre un `capturar()`.

Se usa una variable de contexto en lugar de pasar la traza por parámetro para no
contaminar la firma de `Agent.run()` ni la de las herramientas, y porque el
anidamiento —orquestador que delega en un especialista que llama a una
herramienta— se resuelve solo.

Primer consumidor: el verificador de fundamentación de `evaluacion/`, que
necesita saber qué texto produjo cada herramienta para comprobar que la respuesta
final no contiene datos que ninguna informó.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

_actual: ContextVar[Traza | None] = ContextVar("traza_actual", default=None)


@dataclass
class Span:
    """Una operación registrada: una llamada a herramienta dentro de un agente."""

    agente: str
    herramienta: str
    argumentos: dict[str, Any]
    resultado: str
    milisegundos: float
    error: bool = False


@dataclass
class Traza:
    """Todo lo ocurrido durante la resolución de una consulta."""

    consulta: str = ""
    spans: list[Span] = field(default_factory=list)

    @property
    def herramientas(self) -> list[str]:
        """Nombres de las herramientas ejecutadas, en orden."""
        return [s.herramienta for s in self.spans]

    @property
    def evidencia(self) -> list[str]:
        """Salidas de las herramientas que leyeron datos.

        Se excluyen las delegaciones: su "resultado" es la respuesta redactada
        por un especialista, no un dato leído de una fuente. Tomarla como
        evidencia haría circular la verificación —el texto del modelo se
        justificaría a sí mismo—, que es exactamente lo que hay que evitar.
        """
        return [s.resultado for s in self.spans if not s.herramienta.startswith("delegar_")]

    @property
    def milisegundos(self) -> float:
        return sum(s.milisegundos for s in self.spans)


@contextmanager
def capturar(consulta: str = "") -> Iterator[Traza]:
    """Captura en una `Traza` todo lo que ocurra dentro del bloque."""
    traza = Traza(consulta=consulta)
    testigo = _actual.set(traza)
    try:
        yield traza
    finally:
        _actual.reset(testigo)


@contextmanager
def registrar(agente: str, herramienta: str, argumentos: dict[str, Any]) -> Iterator[list[str]]:
    """Registra una llamada a herramienta si hay una captura activa.

    El bloque recibe una lista de un elemento donde depositar el resultado; se
    hace así para poder medir el tiempo y capturar el error sin que el llamador
    cambie su estructura.
    """
    traza = _actual.get()
    if traza is None:
        yield [""]
        return

    caja = [""]
    inicio = time.perf_counter()
    error = False
    try:
        yield caja
    except Exception:
        error = True
        raise
    finally:
        traza.spans.append(
            Span(
                agente=agente,
                herramienta=herramienta,
                argumentos=argumentos,
                resultado=caja[0],
                milisegundos=(time.perf_counter() - inicio) * 1000,
                error=error,
            )
        )
