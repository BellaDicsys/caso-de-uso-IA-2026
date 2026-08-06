"""Motor de recuperación híbrido: BM25 + espacio latente, fusionados por RRF.

Ninguna de las dos ramas alcanza sola. BM25 acierta cuando la consulta trae el
término exacto —un código de factura, un acrónimo— y falla cuando el usuario
pregunta con otras palabras. El espacio latente hace lo contrario: entiende la
paráfrasis y diluye los términos raros, que aparecen poco y quedan mal
representados en la descomposición.

La fusión usa **Reciprocal Rank Fusion**: cada rama vota con el inverso del
puesto en su ranking, no con su puntaje. Es deliberado — los puntajes de BM25 y
del coseno no son comparables entre sí ni estables entre consultas, y
normalizarlos exige elegir constantes arbitrarias. El puesto, en cambio, siempre
significa lo mismo.

    RRF(f) = Σ_ramas 1 / (K + puesto_rama(f))

`K` amortigua la diferencia entre los primeros puestos: con K=60, el primero y el
segundo aportan casi lo mismo, y un fragmento que sale segundo en las dos ramas
le gana a uno que sale primero en una sola. Es justo lo que se quiere de un
consenso.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from enterprise_agents.config import DOCS_DIR
from enterprise_agents.recuperacion.fragmentos import Fragmento, fragmentar_corpus
from enterprise_agents.recuperacion.lexico import IndiceBM25
from enterprise_agents.recuperacion.terminos import terminos
from enterprise_agents.recuperacion.vectorial import IndiceSemantico

# Constante de amortiguación de RRF. 60 es el valor del trabajo original de
# Cormack y es notablemente insensible: entre 20 y 100 los rankings casi no cambian.
K_RRF = 60
# Cuántos candidatos aporta cada rama antes de fusionar. Más profundidad da mejor
# consenso; más allá de ~50 el aporte es marginal en un corpus de este tamaño.
PROFUNDIDAD = 40
# Fracción mínima de la consulta que el corpus debe poder resolver para que la
# búsqueda se considere dentro de dominio. Con 0,5 se exige que al menos la mitad
# de lo preguntado exista: alcanza para descartar consultas ajenas sin castigar a
# las que traen un término desconocido junto a varios buenos.
UMBRAL_COBERTURA = 0.5


@dataclass(frozen=True)
class Resultado:
    """Un fragmento recuperado, con su procedencia."""

    fragmento: Fragmento
    puntaje: float
    puesto_lexico: int | None
    puesto_semantico: int | None

    @property
    def origen(self) -> str:
        """De qué rama vino, para poder explicar por qué se recuperó."""
        if self.puesto_lexico is not None and self.puesto_semantico is not None:
            return "ambas"
        if self.puesto_lexico is not None:
            return "léxica"
        return "semántica"


def _fusion_rrf(
    rankings: list[list[tuple[int, float]]],
) -> dict[int, tuple[float, list[int | None]]]:
    """Fusiona rankings por RRF. Devuelve id → (puntaje, puestos por rama)."""
    puestos: dict[int, list[int | None]] = {}
    for rama, ranking in enumerate(rankings):
        for puesto, (indice, _) in enumerate(ranking, start=1):
            if indice not in puestos:
                puestos[indice] = [None] * len(rankings)
            puestos[indice][rama] = puesto

    fusionado: dict[int, tuple[float, list[int | None]]] = {}
    for indice, por_rama in puestos.items():
        puntaje = sum(1.0 / (K_RRF + p) for p in por_rama if p is not None)
        fusionado[indice] = (puntaje, por_rama)
    return fusionado


class MotorRecuperacion:
    """Índice híbrido sobre un conjunto de fragmentos."""

    def __init__(self, fragmentos: list[Fragmento]) -> None:
        self.fragmentos = fragmentos
        tokenizados = [f.tokens() for f in fragmentos]
        self.lexico = IndiceBM25(tokenizados)
        self.semantico = IndiceSemantico(tokenizados)

    @classmethod
    def desde_directorio(cls, directorio: Path | None = None) -> MotorRecuperacion:
        return cls(fragmentar_corpus(directorio or DOCS_DIR))

    def cobertura(self, consulta: str) -> float:
        """Proporción de los términos de la consulta que el corpus puede resolver.

        Es la defensa contra el modo de falla clásico de la recuperación: el
        índice **siempre** devuelve sus mejores k, por irrelevante que sea la
        consulta, y el modelo responde con seguridad sobre pasajes que no vienen
        a cuento. "¿Va a llover mañana?" se colaba con un puntaje alto porque
        *llover* y *mañana* no existen en el corpus y quedaba solo *va*, que sí:
        la consulta terminaba resuelta por su palabra menos significativa.

        Mide la fracción del contenido de la consulta que existe en el corpus, y
        es explicable: no es un umbral sobre un puntaje sin unidades.
        """
        pedidos = terminos(consulta)
        if not pedidos:
            return 0.0
        return len(self.expandir(consulta)) / len(pedidos)

    def expandir(self, consulta: str) -> list[str]:
        """Términos de la consulta, con los desconocidos llevados a su forma del corpus.

        Se hace **una sola vez y para las dos ramas**. Al principio la expansión
        vivía solo en la rama semántica, y el resultado era que BM25 descartaba en
        silencio los términos que más importaban: en "¿cada cuánto se respalda la
        base de datos?" tiraba `respalda` —el corpus dice *respaldo*— y puntuaba
        únicamente por `base` y `dato`, que aparecen en media docena de políticas.
        La consulta terminaba resuelta por sus palabras menos informativas.
        """
        expandidos = []
        for termino in terminos(consulta):
            if termino in self.semantico.vocabulario.indices:
                expandidos.append(termino)
                continue
            vecino = self.semantico.vocabulario.mas_cercano(termino)
            if vecino:
                expandidos.append(vecino)
        return expandidos

    def buscar(self, consulta: str, k: int = 5) -> list[Resultado]:
        """Recupera los `k` fragmentos más relevantes fusionando ambas ramas."""
        if not self.fragmentos:
            return []
        if self.cobertura(consulta) < UMBRAL_COBERTURA:
            return []
        expandidos = self.expandir(consulta)
        ranking_lexico = self.lexico.buscar(expandidos, PROFUNDIDAD)
        ranking_semantico = self.semantico.buscar_terminos(expandidos, PROFUNDIDAD)

        fusionado = _fusion_rrf([ranking_lexico, ranking_semantico])
        ordenado = sorted(fusionado.items(), key=lambda par: (-par[1][0], par[0]))

        return [
            Resultado(
                fragmento=self.fragmentos[indice],
                puntaje=puntaje,
                puesto_lexico=puestos[0],
                puesto_semantico=puestos[1],
            )
            for indice, (puntaje, puestos) in ordenado[:k]
        ]

    def buscar_documentos(self, consulta: str, k: int = 5) -> list[tuple[str, float]]:
        """Agrega los fragmentos a nivel documento, sumando el aporte de cada uno."""
        acumulado: dict[str, float] = {}
        for resultado in self.buscar(consulta, k=PROFUNDIDAD):
            nombre = resultado.fragmento.documento
            acumulado[nombre] = acumulado.get(nombre, 0.0) + resultado.puntaje
        ordenado = sorted(acumulado.items(), key=lambda par: (-par[1], par[0]))
        return ordenado[:k]


@lru_cache(maxsize=1)
def motor() -> MotorRecuperacion:
    """Motor del corpus por defecto, construido una sola vez por proceso."""
    return MotorRecuperacion.desde_directorio()
