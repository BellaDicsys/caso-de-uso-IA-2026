"""Motor de recuperación híbrido sobre el corpus documental.

Combina una rama léxica (BM25) con una semántica (espacio latente construido
desde el propio corpus por SVD) y las fusiona por *Reciprocal Rank Fusion*.
Sin dependencias externas ni pesos preentrenados: determinístico y testeable.
"""

from enterprise_agents.recuperacion.fragmentos import Fragmento, fragmentar_corpus
from enterprise_agents.recuperacion.motor import MotorRecuperacion, Resultado, motor

__all__ = ["Fragmento", "MotorRecuperacion", "Resultado", "fragmentar_corpus", "motor"]
