"""El set de evaluación completo debe pasar en modo mock.

Esto mantiene alineados los escenarios de evaluación con las herramientas y
las reglas del mock: si se desalinean, este test falla en CI.
"""

from enterprise_agents.config import Settings
from enterprise_agents.evals import ESCENARIOS, correr_evaluacion
from enterprise_agents.llm.mock_client import MockLLMClient


def test_evaluacion_completa_en_mock():
    resultados = correr_evaluacion(MockLLMClient(), Settings())
    fallidos = [r for r in resultados if not r.ok]
    detalle = {r.escenario.id: r.criterios_fallidos for r in fallidos}
    assert not fallidos, f"escenarios fallidos: {detalle}"
    assert len(resultados) == len(ESCENARIOS) == 6
