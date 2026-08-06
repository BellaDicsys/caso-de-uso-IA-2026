"""Memoria conversacional con presupuesto de contexto y compactación.

Hasta acá cada consulta se resolvía de cero: el historial que se veía en pantalla
era del navegador, no del asistente. Repreguntar "¿y la más antigua?" no
funcionaba, y estaba declarado como límite conocido.

Dos piezas resuelven cosas distintas:

**1. Historial con presupuesto.** La conversación crece y el contexto no es
gratis: cada turno viejo que se arrastra se paga en cada turno nuevo. Cuando la
estimación supera el presupuesto, los turnos más antiguos se **compactan** en un
resumen y los recientes quedan intactos, porque la referencia de una repregunta
casi siempre apunta al turno inmediato anterior.

El resumen es **extractivo**: selecciona oraciones que ya existen, no redacta
nuevas. Es una decisión de seguridad, no de simplicidad. Un resumen generativo
necesitaría el modelo, costaría una llamada por compactación y —peor— podría
introducir afirmaciones que ninguna herramienta produjo, justo lo que el
verificador de fundamentación existe para impedir. Un extractivo no puede
inventar: en el peor caso elige mal qué conservar.

**2. Contextualización de la consulta.** Una repregunta como "¿y la más antigua?"
no dice de qué habla. Antes de rutearla o recuperar con ella, se la completa con
los términos informativos del turno anterior. Es la técnica estándar de búsqueda
conversacional, y tiene la ventaja de funcionar sin modelo: se apoya en el mismo
preprocesamiento léxico que el motor de recuperación.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from enterprise_agents import tokens as tokens_mod
from enterprise_agents.recuperacion.terminos import terminos

# Presupuesto de contexto para el historial. Generoso para una conversación de
# trabajo y acotado para que una sesión larga no crezca sin techo.
PRESUPUESTO_TOKENS = 2000
# Turnos que nunca se compactan. Una repregunta se apoya casi siempre en el turno
# inmediato anterior, así que perder ese detalle rompe justo el caso de uso.
TURNOS_INTACTOS = 4
# Consultas con menos términos informativos que esto se consideran una
# repregunta: no se sostienen solas y necesitan el contexto anterior.
#
# Dos, no tres. Con tres, "¿qué dice la política de vacaciones?" —que aporta
# exactamente dos términos informativos, *política* y *vacación*— quedaba
# clasificada como repregunta y se le anexaba el tema anterior, así que un cambio
# de tema volvía al tema viejo. El costo de errar hacia abajo es no contextualizar
# una repregunta rara; el de errar hacia arriba es desviar consultas legítimas, que
# es mucho peor.
MINIMO_AUTOSUFICIENTE = 2

_ORACION = re.compile(r"(?<=[.:;!?])\s+|\n+")


@dataclass
class Turno:
    rol: str  # "user" | "assistant"
    texto: str

    @property
    def tokens(self) -> int:
        return tokens_mod.estimar(self.texto)

    def a_mensaje(self) -> dict[str, str]:
        return {"role": self.rol, "content": self.texto}


def _oraciones(texto: str) -> list[str]:
    return [o.strip() for o in _ORACION.split(texto) if o.strip()]


def resumir_extractivo(textos: list[str], max_tokens: int) -> str:
    """Resumen por selección de oraciones, sin generar texto nuevo.

    Puntúa cada oración por la rareza de sus términos dentro del propio conjunto
    —una oración con términos que aparecen en todas partes aporta poco— y
    conserva las mejores hasta agotar el presupuesto, **respetando el orden
    original** para que el resumen se lea como una secuencia y no como una
    lista de fragmentos sueltos.
    """
    oraciones = [o for texto in textos for o in _oraciones(texto)]
    if not oraciones:
        return ""

    frecuencias: dict[str, int] = {}
    por_oracion = []
    for oracion in oraciones:
        propios = set(terminos(oracion))
        por_oracion.append(propios)
        for termino in propios:
            frecuencias[termino] = frecuencias.get(termino, 0) + 1

    total = len(oraciones)
    puntajes = []
    for indice, propios in enumerate(por_oracion):
        if not propios:
            puntajes.append((indice, 0.0))
            continue
        # Rareza media de los términos: 1 si aparecen solo acá, 0 si en todas.
        rareza = sum(1 - frecuencias[t] / total for t in propios) / len(propios)
        puntajes.append((indice, rareza))

    elegidas: list[int] = []
    consumido = 0
    for indice, _ in sorted(puntajes, key=lambda par: (-par[1], par[0])):
        costo = tokens_mod.estimar(oraciones[indice])
        if consumido + costo > max_tokens:
            continue
        elegidas.append(indice)
        consumido += costo
        if consumido >= max_tokens:
            break

    return " ".join(oraciones[i] for i in sorted(elegidas))


@dataclass
class Conversacion:
    """Historial de una sesión, acotado por presupuesto de contexto."""

    turnos: list[Turno] = field(default_factory=list)
    resumen: str = ""
    presupuesto: int = PRESUPUESTO_TOKENS
    intactos: int = TURNOS_INTACTOS
    compactaciones: int = 0

    def agregar(self, rol: str, texto: str) -> None:
        self.turnos.append(Turno(rol=rol, texto=texto))
        self._compactar_si_hace_falta()

    @property
    def tokens(self) -> int:
        return tokens_mod.estimar(self.resumen) + sum(t.tokens for t in self.turnos)

    def _compactar_si_hace_falta(self) -> None:
        while self.tokens > self.presupuesto and len(self.turnos) > self.intactos:
            viejos = self.turnos[: -self.intactos]
            self.turnos = self.turnos[-self.intactos :]
            # El resumen previo entra al nuevo: la compactación es acumulativa y
            # no descarta lo ya condensado.
            material = ([self.resumen] if self.resumen else []) + [t.texto for t in viejos]
            self.resumen = resumir_extractivo(material, self.presupuesto // 3)
            self.compactaciones += 1

    def mensajes(self) -> list[dict[str, str]]:
        """Historial en formato Messages API, con el resumen al frente si existe."""
        salida: list[dict[str, str]] = []
        if self.resumen:
            salida.append(
                {
                    "role": "user",
                    "content": (
                        "Resumen de lo conversado antes (contexto, no una consulta "
                        f"nueva): {self.resumen}"
                    ),
                }
            )
            salida.append({"role": "assistant", "content": "Entendido, tengo el contexto."})
        salida.extend(t.a_mensaje() for t in self.turnos)
        return salida

    def ultima_del_usuario(self) -> str:
        for turno in reversed(self.turnos):
            if turno.rol == "user":
                return turno.texto
        return ""

    def limpiar(self) -> None:
        self.turnos.clear()
        self.resumen = ""
        self.compactaciones = 0


def es_autosuficiente(consulta: str) -> bool:
    """¿La consulta se entiende sola, sin el turno anterior?"""
    return len(terminos(consulta)) >= MINIMO_AUTOSUFICIENTE


def contextualizar(consulta: str, conversacion: Conversacion | None) -> str:
    """Completa una repregunta con los términos informativos del turno anterior.

    "¿Y la más antigua?" no dice de qué habla: no se puede rutear ni recuperar
    con ella. Se le anexan los términos de la última consulta del usuario, que
    es donde está el referente en la enorme mayoría de los casos.

    Devuelve la consulta original si ya se sostiene sola, para no ensuciar con
    contexto ajeno lo que no lo necesita —anexar términos viejos a una consulta
    de otro tema la desviaría hacia el tema anterior.
    """
    if conversacion is None or es_autosuficiente(consulta):
        return consulta
    anterior = conversacion.ultima_del_usuario()
    if not anterior:
        return consulta
    contexto = " ".join(terminos(anterior))
    return f"{consulta} {contexto}".strip() if contexto else consulta
