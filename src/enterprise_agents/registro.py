"""Registro en memoria de las últimas trazas, para el visor de observabilidad.

**Por qué en memoria y no en SQLite.** La tentación es persistir: es lo que haría
un sistema real. Pero acá agregaría un archivo que administrar, un esquema que
migrar y una política de retención que implementar, para una demo que corre en la
máquina de quien la evalúa y con un solo proceso. Sería demostrar una técnica en
lugar de resolver un problema —el mismo criterio con el que se descartó el índice
aproximado en el ADR-0007.

Es coherente además con el resto del estado de la demo: las sesiones y el control
de intentos ya viven en memoria, y está documentado como riesgo aceptado.

En producción esto se reemplaza por el sistema de trazas de la organización
(OpenTelemetry hacia un colector), no por SQLite. La forma de `Traza.a_dict()`
está pensada para que ese salto sea un exportador y no una reescritura.
"""

from __future__ import annotations

from collections import deque
from threading import Lock

from enterprise_agents.trazas import Traza

# Cuántas trazas se conservan. Suficiente para revisar una sesión de uso o una
# demostración en vivo, y acotado para que la memoria no crezca sin límite.
CAPACIDAD = 50


class RegistroTrazas:
    """Buffer circular de trazas, seguro entre hilos."""

    def __init__(self, capacidad: int = CAPACIDAD) -> None:
        self._trazas: deque[Traza] = deque(maxlen=capacidad)
        self._lock = Lock()

    def agregar(self, traza: Traza) -> None:
        with self._lock:
            self._trazas.append(traza)

    def recientes(self, limite: int = 20, usuario: str | None = None) -> list[Traza]:
        """Las últimas trazas, de la más reciente a la más antigua.

        Con `usuario`, solo las de esa persona. El visor lo usa siempre salvo
        para el rol admin: una consulta es contenido del usuario que la hizo, y
        un gestor no tiene por qué leer lo que preguntó otro empleado.
        """
        with self._lock:
            trazas = list(reversed(self._trazas))
        if usuario is not None:
            trazas = [t for t in trazas if t.usuario == usuario]
        return trazas[:limite]

    def resumen(self, usuario: str | None = None) -> dict[str, float | int]:
        """Agregados sobre lo registrado, para el encabezado del visor."""
        with self._lock:
            trazas = list(self._trazas)
        if usuario is not None:
            trazas = [t for t in trazas if t.usuario == usuario]
        if not trazas:
            return {"consultas": 0, "ms_promedio": 0.0, "tokens_promedio": 0, "con_error": 0}
        return {
            "consultas": len(trazas),
            "ms_promedio": round(sum(t.milisegundos_total for t in trazas) / len(trazas), 1),
            "tokens_promedio": round(sum(t.tokens_contexto for t in trazas) / len(trazas)),
            "con_error": sum(1 for t in trazas if t.hubo_error),
        }

    def limpiar(self) -> None:
        with self._lock:
            self._trazas.clear()

    def __len__(self) -> int:
        return len(self._trazas)
