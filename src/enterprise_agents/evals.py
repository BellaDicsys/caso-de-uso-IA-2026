"""Set de evaluación de escenarios de negocio.

Cada escenario define una consulta y criterios verificables (subcadenas que la
respuesta debe contener). El mismo set corre contra el mock (CI, gratis) y
contra el modelo real (`enterprise-agents eval --live`), lo que permite detectar
regresiones de comportamiento al cambiar prompts, herramientas o modelo.

Además de los criterios, cada escenario se verifica por **fundamentación**: toda
cifra de la respuesta tiene que aparecer en la salida de alguna herramienta de
esa misma ejecución (ver `evaluacion/fundamentacion.py`). Es la comprobación que
detecta el modo de falla propio de un sistema agéntico —inventar un número al
sintetizar— y corre igual en modo mock que en modo live.

La calidad de la recuperación se mide aparte, en `evaluacion/arnes.py`.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from enterprise_agents import trazas
from enterprise_agents.config import Settings
from enterprise_agents.evaluacion.fundamentacion import Veredicto, verificar_traza
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.orchestrator import crear_orquestador


@dataclass(frozen=True)
class Escenario:
    id: str
    pregunta: str
    criterios: list[str]  # subcadenas esperadas en la respuesta (sin tildes, minúsculas)


ESCENARIOS = [
    Escenario(
        id="ventas-total",
        pregunta="¿Cuánto facturamos este año y quiénes son nuestros principales clientes?",
        criterios=["471,100", "banco andino"],
    ),
    Escenario(
        id="proyectos-riesgo",
        pregunta="¿Qué proyectos están en riesgo por consumo de horas?",
        criterios=["p-2026-05", "consumo alto"],
    ),
    Escenario(
        id="cobranzas-vencidas",
        pregunta="¿Qué facturas vencidas hay que reclamar primero?",
        criterios=["fc-2026-0115", "47,700"],
    ),
    Escenario(
        id="documental-vacaciones",
        pregunta="¿Qué dice la política de vacaciones sobre la anticipación?",
        criterios=["politica-vacaciones.md"],
    ),
    Escenario(
        id="personal-python",
        pregunta="¿Qué perfiles con Python tienen disponibilidad para un proyecto nuevo?",
        criterios=["martina lopez", "disponibilidad"],
    ),
    Escenario(
        id="fuera-de-dominio",
        pregunta="¿Va a llover mañana en Córdoba?",
        criterios=["dominio"],
    ),
]


@dataclass(frozen=True)
class Resultado:
    escenario: Escenario
    respuesta: str
    criterios_fallidos: list[str]
    veredicto: Veredicto
    herramientas: list[str]

    @property
    def ok(self) -> bool:
        """Un escenario pasa si cumple sus criterios **y** está fundado."""
        return not self.criterios_fallidos and self.veredicto.fundada


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def correr_evaluacion(llm: LLMClient, settings: Settings) -> list[Resultado]:
    resultados = []
    for escenario in ESCENARIOS:
        orquestador = crear_orquestador(llm, settings)
        with trazas.capturar(escenario.pregunta) as traza:
            respuesta = orquestador.run(escenario.pregunta)
        respuesta_norm = _normalizar(respuesta)
        fallidos = [c for c in escenario.criterios if _normalizar(c) not in respuesta_norm]
        resultados.append(
            Resultado(
                escenario=escenario,
                respuesta=respuesta,
                criterios_fallidos=fallidos,
                veredicto=verificar_traza(respuesta, traza),
                herramientas=traza.herramientas,
            )
        )
    return resultados


def imprimir_reporte(resultados: list[Resultado]) -> bool:
    """Imprime el reporte y devuelve True si todos los escenarios pasaron."""
    ok_total = 0
    for r in resultados:
        estado = "PASÓ " if r.ok else "FALLÓ"
        print(f"[{estado}] {r.escenario.id}: {r.escenario.pregunta}")
        print(f"         herramientas: {' → '.join(r.herramientas) or '(ninguna)'}")
        print(f"         fundamentación: {r.veredicto.informe()}")
        if not r.ok:
            if r.criterios_fallidos:
                print(f"         criterios no encontrados: {r.criterios_fallidos}")
            print(f"         respuesta: {r.respuesta[:200]}...")
        else:
            ok_total += 1
    print(f"\nResultado: {ok_total}/{len(resultados)} escenarios OK")
    return ok_total == len(resultados)
