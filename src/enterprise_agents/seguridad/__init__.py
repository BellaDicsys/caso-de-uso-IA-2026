"""Seguridad de agentes: detección y saneamiento de inyecciones de prompt.

El contenido que un agente recupera es entrada no confiable. Este paquete lo
trata como tal antes de que llegue al modelo.
"""

from enterprise_agents.seguridad.deteccion import Hallazgo, analizar, hay_inyeccion
from enterprise_agents.seguridad.saneamiento import Saneado, sanear

__all__ = ["Hallazgo", "Saneado", "analizar", "hay_inyeccion", "sanear"]
