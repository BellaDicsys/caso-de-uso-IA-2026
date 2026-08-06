"""Ruteo semántico de herramientas para el cliente simulado.

Reemplaza las listas de palabras clave que el mock mantenía a mano. Aquellas
tenían tres problemas de fondo: había que actualizarlas con cada herramienta
nueva, se desincronizaban de las descripciones que sí ve el modelo real, y ya
habían producido errores de ruteo documentados en la auditoría ("¿cuál es el
**monto** de la **deuda**?" caía en el analista de datos).

La idea es que **rutear es recuperar**: el problema de elegir la herramienta
correcta para una consulta es el mismo que elegir el pasaje correcto, con las
descripciones de las herramientas como corpus. Así que se reusa el motor de
`recuperacion/` —BM25 más espacio latente, fusionados por RRF— en lugar de
inventar un segundo mecanismo.

Esto no convierte al mock en un modelo: sigue eligiendo una herramienta por
consulta y sin razonar. Pero la elección deja de ser una tabla de prefijos y
pasa a ser una comparación semántica contra el mismo texto que orienta al modelo
real, que es una demostración honesta de ruteo por intención.
"""

from __future__ import annotations

from dataclasses import dataclass

from enterprise_agents.recuperacion.lexico import IndiceBM25
from enterprise_agents.recuperacion.terminos import terminos
from enterprise_agents.recuperacion.vectorial import IndiceSemantico

# Dimensión del espacio latente de intenciones. El "corpus" son ~13 descripciones
# cortas: con más dimensiones que herramientas la descomposición no aporta nada.
DIMENSION = 8
K_RRF = 60


@dataclass(frozen=True)
class Eleccion:
    """La herramienta elegida y con cuánto respaldo."""

    nombre: str
    puntaje: float
    cobertura: float


class RouterSemantico:
    """Elige la herramienta más afín a una consulta, sin palabras clave.

    Se construye por conjunto de herramientas: el orquestador ve solo las de
    delegación y cada especialista solo las suyas, así que cada agente tiene su
    propio índice y compite únicamente contra alternativas reales.
    """

    def __init__(self, herramientas: dict[str, str]) -> None:
        """`herramientas` mapea nombre → texto de intención."""
        self.nombres = list(herramientas)
        documentos = [terminos(herramientas[n]) for n in self.nombres]
        self.lexico = IndiceBM25(documentos)
        self.semantico = IndiceSemantico(documentos, dimension=DIMENSION)

    def _expandir(self, consulta: str) -> list[str]:
        vocabulario = self.semantico.vocabulario
        expandidos = []
        for termino in terminos(consulta):
            if termino in vocabulario.indices:
                expandidos.append(termino)
            elif (vecino := vocabulario.mas_cercano(termino)) is not None:
                expandidos.append(vecino)
        return expandidos

    def cobertura(self, consulta: str) -> float:
        pedidos = terminos(consulta)
        if not pedidos:
            return 0.0
        return len(self._expandir(consulta)) / len(pedidos)

    def elegir(self, consulta: str) -> Eleccion | None:
        """La herramienta más afín, o None si la consulta no corresponde a ninguna.

        Basta con que **un** término de la consulta exista en el vocabulario de
        las herramientas. El criterio es más laxo que el del motor documental
        —que exige la mitad— y a propósito: aquel indexa 1.300 términos de
        políticas corporativas, donde una coincidencia suelta puede ser
        accidental; acá el vocabulario son ~150 términos de descripciones
        escritas para distinguir dominios, así que una coincidencia ya es señal.
        En la práctica las consultas ajenas dan cobertura exactamente cero:
        "¿va a llover mañana?" no comparte una sola palabra con ninguna
        herramienta.
        """
        if not self.nombres:
            return None
        expandidos = self._expandir(consulta)
        if not expandidos:
            return None
        cobertura = self.cobertura(consulta)
        rankings = [
            self.lexico.buscar(expandidos, len(self.nombres)),
            self.semantico.buscar_terminos(expandidos, len(self.nombres)),
        ]
        puntajes: dict[int, float] = {}
        for ranking in rankings:
            for puesto, (indice, valor) in enumerate(ranking, start=1):
                # El coseno puede ser negativo: un puesto alto con similitud
                # negativa no es evidencia a favor, así que no vota.
                if valor <= 0:
                    continue
                puntajes[indice] = puntajes.get(indice, 0.0) + 1.0 / (K_RRF + puesto)

        if not puntajes:
            return None
        indice, puntaje = max(puntajes.items(), key=lambda par: (par[1], -par[0]))
        return Eleccion(nombre=self.nombres[indice], puntaje=puntaje, cobertura=cobertura)
