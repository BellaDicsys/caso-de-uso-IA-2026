"""Métricas de calidad de recuperación, como funciones puras sobre rankings.

Las tres responden preguntas distintas y por eso se reportan las tres:

- **recall@k** — ¿lo relevante entró entre los primeros k? Es lo que importa
  cuando el resultado alimenta a un modelo: si el pasaje correcto no está en el
  contexto, no hay respuesta correcta posible.
- **MRR** — ¿en qué puesto apareció el primer acierto? Penaliza tener razón
  tarde, que es lo que ocurre cuando un método "encuentra todo" pero mal
  ordenado.
- **nDCG@k** — ¿cuán buena es la ordenación completa? Es la única de las tres que
  distingue entre acertar en el puesto 1 y acertar en el 5 cuando ambos entran
  en el corte.

Todas operan sobre `(ranking, relevantes)`: una lista ordenada de identificadores
y el conjunto de los correctos. No saben nada del motor, así que se pueden probar
con listas escritas a mano.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def recall_en_k(ranking: Sequence[str], relevantes: set[str], k: int) -> float:
    """Fracción de los relevantes que aparece entre los primeros `k`."""
    if not relevantes:
        return 1.0
    encontrados = len(set(ranking[:k]) & relevantes)
    return encontrados / len(relevantes)


def acierto_en_k(ranking: Sequence[str], relevantes: set[str], k: int) -> bool:
    """¿Hay al menos un relevante entre los primeros `k`?"""
    return bool(set(ranking[:k]) & relevantes)


def rango_reciproco(ranking: Sequence[str], relevantes: set[str]) -> float:
    """1 / puesto del primer acierto; 0 si no hay ninguno."""
    for puesto, elemento in enumerate(ranking, start=1):
        if elemento in relevantes:
            return 1.0 / puesto
    return 0.0


def ndcg_en_k(ranking: Sequence[str], relevantes: set[str], k: int) -> float:
    """Ganancia acumulada descontada, normalizada contra la ordenación ideal.

    Relevancia binaria: cada acierto aporta 1, descontado por el logaritmo de su
    puesto. El ideal es tener todos los relevantes arriba de todo.
    """
    if not relevantes:
        return 1.0
    ganancia = sum(
        1.0 / math.log2(puesto + 1)
        for puesto, elemento in enumerate(ranking[:k], start=1)
        if elemento in relevantes
    )
    ideal = sum(1.0 / math.log2(puesto + 1) for puesto in range(1, min(len(relevantes), k) + 1))
    return ganancia / ideal if ideal else 0.0


def promedio(valores: Sequence[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0
