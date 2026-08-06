"""Ejecución del conjunto etiquetado y reporte de resultados.

Corre las consultas contra el motor de recuperación, calcula las métricas y las
compara contra umbrales. Los umbrales están para que CI falle ante una regresión:
sin ellos el reporte es un número lindo que nadie mira.
"""

from __future__ import annotations

from dataclasses import dataclass

from enterprise_agents.evaluacion.conjuntos import CONSULTAS, ConsultaEtiquetada
from enterprise_agents.evaluacion.metricas import (
    acierto_en_k,
    ndcg_en_k,
    promedio,
    rango_reciproco,
    recall_en_k,
)
from enterprise_agents.recuperacion.motor import MotorRecuperacion, motor_por_defecto

# Profundidad de corte. 5 es lo que la herramienta documental le pasa al modelo,
# así que es la medida que importa: si el documento correcto no está entre los 5,
# el agente no lo puede usar.
K = 5

# Umbrales de aceptación. Se fijan por debajo del rendimiento medido para dejar
# margen a variaciones legítimas del corpus, pero lo bastante altos como para que
# una regresión real los rompa.
UMBRALES = {
    "acierto@5": 0.85,
    "recall@5": 0.80,
    "mrr": 0.70,
    "ndcg@5": 0.75,
    "abstencion": 1.00,
}


@dataclass(frozen=True)
class ResultadoConsulta:
    consulta: ConsultaEtiquetada
    recuperados: list[str]

    @property
    def acierto(self) -> bool:
        return acierto_en_k(self.recuperados, set(self.consulta.relevantes), K)

    @property
    def se_abstuvo(self) -> bool:
        return not self.recuperados


@dataclass(frozen=True)
class Reporte:
    """Métricas agregadas sobre el conjunto etiquetado."""

    resultados: list[ResultadoConsulta]
    metricas: dict[str, float]

    @property
    def en_dominio(self) -> list[ResultadoConsulta]:
        return [r for r in self.resultados if not r.consulta.fuera_de_dominio]

    @property
    def fuera_de_dominio(self) -> list[ResultadoConsulta]:
        return [r for r in self.resultados if r.consulta.fuera_de_dominio]

    @property
    def fallidas(self) -> list[ResultadoConsulta]:
        """Consultas del dominio cuyo documento correcto no entró en el corte."""
        return [r for r in self.en_dominio if not r.acierto]

    @property
    def incumplidos(self) -> dict[str, tuple[float, float]]:
        """Métricas por debajo de su umbral: nombre → (obtenido, exigido)."""
        return {
            nombre: (self.metricas[nombre], umbral)
            for nombre, umbral in UMBRALES.items()
            if self.metricas.get(nombre, 0.0) < umbral
        }

    @property
    def aprueba(self) -> bool:
        return not self.incumplidos


def evaluar_recuperacion(
    consultas: tuple[ConsultaEtiquetada, ...] = CONSULTAS,
    indice: MotorRecuperacion | None = None,
) -> Reporte:
    """Corre el conjunto etiquetado y devuelve las métricas agregadas."""
    indice = indice or motor_por_defecto()
    resultados = [
        ResultadoConsulta(
            consulta=consulta,
            recuperados=[nombre for nombre, _ in indice.buscar_documentos(consulta.consulta, k=K)],
        )
        for consulta in consultas
    ]

    dominio = [r for r in resultados if not r.consulta.fuera_de_dominio]
    ajenas = [r for r in resultados if r.consulta.fuera_de_dominio]

    metricas = {
        "acierto@5": promedio([float(r.acierto) for r in dominio]),
        "recall@5": promedio(
            [recall_en_k(r.recuperados, set(r.consulta.relevantes), K) for r in dominio]
        ),
        "mrr": promedio(
            [rango_reciproco(r.recuperados, set(r.consulta.relevantes)) for r in dominio]
        ),
        "ndcg@5": promedio(
            [ndcg_en_k(r.recuperados, set(r.consulta.relevantes), K) for r in dominio]
        ),
        # Proporción de consultas ajenas ante las que el motor no devolvió nada.
        "abstencion": promedio([float(r.se_abstuvo) for r in ajenas]),
    }
    return Reporte(resultados=resultados, metricas=metricas)


def imprimir_reporte(reporte: Reporte, detallado: bool = False) -> bool:
    """Imprime el reporte y devuelve si aprueba los umbrales."""
    print(
        f"Recuperación — {len(reporte.en_dominio)} consultas del dominio "
        f"y {len(reporte.fuera_de_dominio)} ajenas\n"
    )
    for nombre, umbral in UMBRALES.items():
        obtenido = reporte.metricas.get(nombre, 0.0)
        marca = "OK " if obtenido >= umbral else "BAJO"
        print(f"  [{marca}] {nombre:<12} {obtenido:.3f}   (umbral {umbral:.2f})")

    if reporte.fallidas:
        print(f"\n  Sin acierto en el top-{K}:")
        for fallida in reporte.fallidas:
            esperados = ", ".join(sorted(fallida.consulta.relevantes))
            obtenido = ", ".join(fallida.recuperados[:2]) or "(nada)"
            print(f"    - {fallida.consulta.consulta}")
            print(f"      esperaba {esperados} · devolvió {obtenido}")

    if detallado:
        print("\n  Detalle por consulta:")
        for resultado in reporte.en_dominio:
            marca = "ok" if resultado.acierto else "NO"
            print(f"    [{marca}] {resultado.consulta.consulta}")

    if reporte.aprueba:
        print("\nResultado: todas las métricas por encima del umbral.")
    else:
        print("\nResultado: métricas por debajo del umbral:")
        for nombre, (obtenido, umbral) in reporte.incumplidos.items():
            print(f"  - {nombre}: {obtenido:.3f} < {umbral:.2f}")
    return reporte.aprueba
