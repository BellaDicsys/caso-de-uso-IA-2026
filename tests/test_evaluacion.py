"""Tests del arnés de evaluación: métricas, fundamentación y trazas."""

from __future__ import annotations

from decimal import Decimal

import pytest

from enterprise_agents import trazas
from enterprise_agents.config import load_settings
from enterprise_agents.evaluacion import metricas
from enterprise_agents.evaluacion.arnes import UMBRALES, evaluar_recuperacion, imprimir_reporte
from enterprise_agents.evaluacion.conjuntos import CONSULTAS
from enterprise_agents.evaluacion.fundamentacion import a_decimal, extraer, verificar
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.orchestrator import crear_orquestador

# --- Métricas ---------------------------------------------------------------


def test_recall_cuenta_los_relevantes_recuperados():
    ranking = ["a", "b", "c", "d"]
    assert metricas.recall_en_k(ranking, {"a", "c"}, 4) == 1.0
    assert metricas.recall_en_k(ranking, {"a", "c"}, 2) == 0.5
    assert metricas.recall_en_k(ranking, {"z"}, 4) == 0.0


def test_recall_sin_relevantes_es_perfecto():
    """Una consulta sin documento correcto no puede fallar el recall."""
    assert metricas.recall_en_k(["a"], set(), 5) == 1.0


def test_rango_reciproco_premia_acertar_temprano():
    assert metricas.rango_reciproco(["a", "b"], {"a"}) == 1.0
    assert metricas.rango_reciproco(["b", "a"], {"a"}) == 0.5
    assert metricas.rango_reciproco(["b", "c"], {"a"}) == 0.0


def test_ndcg_distingue_el_orden_dentro_del_corte():
    """Recall no ve la diferencia entre acertar primero o último; nDCG sí."""
    primero = metricas.ndcg_en_k(["a", "x", "y"], {"a"}, 3)
    ultimo = metricas.ndcg_en_k(["x", "y", "a"], {"a"}, 3)
    assert metricas.recall_en_k(["a", "x", "y"], {"a"}, 3) == metricas.recall_en_k(
        ["x", "y", "a"], {"a"}, 3
    )
    assert primero > ultimo
    assert primero == pytest.approx(1.0)


def test_ndcg_ideal_con_todos_los_relevantes_arriba():
    assert metricas.ndcg_en_k(["a", "b", "z"], {"a", "b"}, 3) == pytest.approx(1.0)


def test_promedio_de_lista_vacia():
    assert metricas.promedio([]) == 0.0


# --- Interpretación de números ----------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("471,100", Decimal(471100)),  # formato inglés de miles
        ("90.000", Decimal(90000)),  # formato español de miles
        ("1.234.567", Decimal(1234567)),
        ("99,5", Decimal("99.5")),  # decimal español
        ("12.75", Decimal("12.75")),  # decimal inglés
        ("21", Decimal(21)),
        ("", None),
        ("abc", None),
    ],
)
def test_interpreta_ambos_formatos_numericos(texto, esperado):
    assert a_decimal(texto) == esperado


# --- Extracción de afirmaciones ---------------------------------------------


def test_extrae_identificadores_fechas_y_numeros():
    afirmaciones = extraer("La FC-2026-0115 venció el 2026-01-15 por 11,500 USD")
    tipos = {a.tipo: a.texto for a in afirmaciones}
    assert tipos["identificador"] == "FC-2026-0115"
    assert tipos["fecha"] == "2026-01-15"
    assert tipos["numero"] == "11,500"


def test_no_lee_los_digitos_de_una_fecha_como_numeros():
    """ "2026" dentro de una fecha no es una afirmación cuantitativa aparte."""
    afirmaciones = extraer("El 2026-01-15 se venció")
    assert [a.tipo for a in afirmaciones] == ["fecha"]


def test_ignora_enteros_chicos_pero_no_los_decimales():
    textos = {a.texto for a in extraer("son 3 facturas de 2 clientes con 99,5 % de SLA")}
    assert "3" not in textos and "2" not in textos
    assert "99,5" in textos


def test_no_duplica_la_misma_cifra_escrita_distinto():
    afirmaciones = extraer("total 90.000, repetido 90.000 y también 90000")
    assert len([a for a in afirmaciones if a.tipo == "numero"]) == 1


# --- Verificación de fundamentación -----------------------------------------


EVIDENCIA = [
    "Facturas vencidas: 3 por un total de 47,700 USD. "
    "FC-2026-0115 Salud Integral: 11,500 USD (venció el 2026-01-15)."
]


def test_respuesta_fundada():
    veredicto = verificar(
        "Hay 3 vencidas por 47,700 USD; la más antigua es la FC-2026-0115 del 2026-01-15.",
        EVIDENCIA,
    )
    assert veredicto.fundada
    assert veredicto.proporcion == 1.0


def test_detecta_un_total_inventado():
    """El modo de falla que importa: un número verosímil que nadie informó."""
    veredicto = verificar("El total vencido es de 52,300 USD.", EVIDENCIA)
    assert not veredicto.fundada
    assert [a.texto for a in veredicto.infundadas] == ["52,300"]


def test_detecta_un_identificador_inventado():
    veredicto = verificar("Reclamar la factura FC-2026-0999.", EVIDENCIA)
    assert not veredicto.fundada
    assert veredicto.infundadas[0].tipo == "identificador"


def test_detecta_una_fecha_corrida():
    veredicto = verificar("Venció el 2026-01-16.", EVIDENCIA)
    assert not veredicto.fundada
    assert veredicto.infundadas[0].tipo == "fecha"


def test_una_respuesta_sin_cifras_esta_fundada_por_vacuidad():
    veredicto = verificar("No encontré información sobre eso.", EVIDENCIA)
    assert veredicto.fundada
    assert veredicto.total == 0
    assert veredicto.proporcion == 1.0


def test_el_formato_no_afecta_la_verificacion():
    """El corpus mezcla 90.000 y 90,000: no puede depender de cómo se escriba."""
    assert verificar("el tope es 90,000", ["tope de 90.000 por día"]).fundada


def test_el_informe_nombra_las_cifras_sin_respaldo():
    informe = verificar("son 52,300 USD", EVIDENCIA).informe()
    assert "NO fundada" in informe
    assert "52,300" in informe


def test_la_proporcion_mide_cuanto_se_respalda():
    veredicto = verificar("47,700 correctos y 52,300 inventados", EVIDENCIA)
    assert veredicto.proporcion == 0.5


# --- Trazas -----------------------------------------------------------------


def test_la_traza_registra_las_herramientas_ejecutadas():
    orquestador = crear_orquestador(MockLLMClient(), load_settings())
    with trazas.capturar("¿qué facturas vencidas hay?") as traza:
        orquestador.run("¿qué facturas vencidas hay?")
    assert "facturas_vencidas" in traza.herramientas
    assert traza.milisegundos > 0


def test_la_evidencia_excluye_las_delegaciones():
    """Si la respuesta de otro agente contara como evidencia, se probaría sola."""
    orquestador = crear_orquestador(MockLLMClient(), load_settings())
    with trazas.capturar() as traza:
        orquestador.run("¿qué facturas vencidas hay?")
    assert any(h.startswith("delegar_") for h in traza.herramientas)
    assert len(traza.evidencia) < len(traza.spans)


def test_sin_captura_activa_no_falla_nada():
    """El registro es opt-in: fuera de un `capturar()` no cuesta ni rompe."""
    orquestador = crear_orquestador(MockLLMClient(), load_settings())
    assert orquestador.run("¿qué facturas vencidas hay?")


def test_las_respuestas_del_agente_estan_fundadas():
    """Verificación de punta a punta sobre una consulta real."""
    from enterprise_agents.evaluacion.fundamentacion import verificar_traza

    orquestador = crear_orquestador(MockLLMClient(), load_settings())
    with trazas.capturar() as traza:
        respuesta = orquestador.run("¿Cuánto facturamos este año?")
    veredicto = verificar_traza(respuesta, traza)
    assert veredicto.fundada, veredicto.informe()
    assert veredicto.total > 0


# --- Conjunto etiquetado y arnés --------------------------------------------


def test_el_conjunto_etiquetado_apunta_a_documentos_existentes():
    from enterprise_agents.config import DOCS_DIR

    existentes = {p.name for p in DOCS_DIR.glob("*.md")}
    for consulta in CONSULTAS:
        faltantes = consulta.relevantes - existentes
        assert not faltantes, f"{consulta.consulta}: {faltantes}"


def test_el_conjunto_incluye_consultas_fuera_de_dominio():
    """Sin ellas, la métrica premia al recuperador que siempre devuelve algo."""
    assert any(c.fuera_de_dominio for c in CONSULTAS)
    assert sum(not c.fuera_de_dominio for c in CONSULTAS) >= 40


@pytest.fixture(scope="module")
def reporte():
    return evaluar_recuperacion()


def test_la_recuperacion_cumple_los_umbrales(reporte):
    assert reporte.aprueba, reporte.incumplidos


@pytest.mark.parametrize("metrica", sorted(UMBRALES))
def test_cada_metrica_supera_su_umbral(reporte, metrica):
    assert reporte.metricas[metrica] >= UMBRALES[metrica]


def test_el_motor_se_abstiene_en_todas_las_consultas_ajenas(reporte):
    assert all(r.se_abstuvo for r in reporte.fuera_de_dominio)


def test_el_reporte_se_imprime_y_devuelve_su_veredicto(reporte, capsys):
    aprueba = imprimir_reporte(reporte)
    salida = capsys.readouterr().out
    assert aprueba is True
    assert "acierto@5" in salida
