"""Tests de la memoria conversacional: historial, compactación y contextualización."""

from __future__ import annotations

import pytest

from enterprise_agents.config import load_settings
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.memoria import (
    Conversacion,
    contextualizar,
    es_autosuficiente,
    resumir_extractivo,
)
from enterprise_agents.orchestrator import crear_orquestador

# --- Historial --------------------------------------------------------------


def test_acumula_turnos_en_orden():
    conversacion = Conversacion()
    conversacion.agregar("user", "¿cuánto facturamos?")
    conversacion.agregar("assistant", "471,100 USD")
    assert [t.rol for t in conversacion.turnos] == ["user", "assistant"]
    assert conversacion.mensajes()[0]["content"] == "¿cuánto facturamos?"


def test_los_mensajes_salen_en_formato_de_la_api():
    conversacion = Conversacion()
    conversacion.agregar("user", "hola")
    mensaje = conversacion.mensajes()[0]
    assert set(mensaje) == {"role", "content"}


def test_limpiar_borra_historial_y_resumen():
    conversacion = Conversacion(presupuesto=60, intactos=1)
    for i in range(12):
        conversacion.agregar("user", f"consulta larga número {i} sobre facturación y cobranzas")
    assert conversacion.resumen
    conversacion.limpiar()
    assert not conversacion.turnos and not conversacion.resumen


# --- Compactación -----------------------------------------------------------


def test_no_compacta_mientras_entra_en_el_presupuesto():
    conversacion = Conversacion(presupuesto=10_000)
    for i in range(6):
        conversacion.agregar("user", f"consulta {i}")
    assert conversacion.compactaciones == 0
    assert not conversacion.resumen


def test_compacta_al_pasarse_del_presupuesto():
    conversacion = Conversacion(presupuesto=120, intactos=2)
    for i in range(10):
        conversacion.agregar(
            "user", f"Turno {i}: consulta sobre facturación, cobranzas y proyectos en riesgo."
        )
    assert conversacion.compactaciones > 0
    assert conversacion.resumen
    assert conversacion.tokens <= conversacion.presupuesto


def test_los_turnos_recientes_quedan_intactos():
    """Una repregunta apunta al turno inmediato anterior: perderlo rompe el caso de uso."""
    conversacion = Conversacion(presupuesto=120, intactos=3)
    for i in range(10):
        conversacion.agregar("user", f"Turno {i} con bastante texto sobre cobranzas y facturas.")
    assert len(conversacion.turnos) >= 3
    assert "Turno 9" in conversacion.turnos[-1].texto


def test_la_compactacion_es_acumulativa():
    """El resumen previo entra al nuevo: no se descarta lo ya condensado."""
    conversacion = Conversacion(presupuesto=100, intactos=2)
    for i in range(20):
        conversacion.agregar("user", f"Turno {i} sobre viáticos, respaldos y contratos marco.")
    assert conversacion.compactaciones >= 2
    assert conversacion.resumen


def test_el_resumen_se_presenta_como_contexto_y_no_como_consulta():
    conversacion = Conversacion(presupuesto=100, intactos=2)
    for i in range(12):
        conversacion.agregar("user", f"Turno {i} sobre facturación y cobranzas de clientes.")
    primero = conversacion.mensajes()[0]["content"]
    assert "contexto" in primero.lower()
    assert "no una consulta" in primero.lower()


# --- Resumen extractivo -----------------------------------------------------


def test_el_resumen_no_inventa_texto():
    """Es extractivo por seguridad: un generativo podría introducir datos falsos."""
    textos = [
        "El tope de alojamiento es 90.000 por día.",
        "La rendición se presenta dentro de los 10 días hábiles.",
        "Los gastos sin comprobante no se reintegran.",
    ]
    resumen = resumir_extractivo(textos, max_tokens=200)
    for oracion in resumen.split(". "):
        assert oracion.strip(". ") in " ".join(textos)


def test_el_resumen_respeta_el_presupuesto():
    textos = [f"Oración número {i} con contenido variado sobre el dominio." for i in range(30)]
    resumen = resumir_extractivo(textos, max_tokens=60)
    from enterprise_agents import tokens

    assert tokens.estimar(resumen) <= 80  # margen por la última oración incluida


def test_el_resumen_conserva_el_orden_original():
    textos = ["Primero viene esto.", "Después aquello otro.", "Finalmente lo último."]
    resumen = resumir_extractivo(textos, max_tokens=200)
    assert resumen.index("Primero") < resumen.index("Finalmente")


def test_el_resumen_prefiere_lo_distintivo():
    """Una oración repetida en todas partes aporta menos que una única."""
    textos = ["Se aplica la política."] * 5 + ["El tope de viáticos es 90.000 por día."]
    resumen = resumir_extractivo(textos, max_tokens=25)
    assert "90.000" in resumen


def test_resumir_sin_material_devuelve_vacio():
    assert resumir_extractivo([], 100) == ""
    assert resumir_extractivo(["   "], 100) == ""


# --- Contextualización de la consulta ---------------------------------------


@pytest.mark.parametrize(
    ("consulta", "esperado"),
    [
        ("¿qué facturas vencidas hay que reclamar?", True),
        ("¿y la más antigua?", False),
        ("¿y eso?", False),
        ("¿cuál es la política de vacaciones vigente?", True),
    ],
)
def test_distingue_consulta_autosuficiente_de_repregunta(consulta, esperado):
    assert es_autosuficiente(consulta) is esperado


def test_la_repregunta_se_completa_con_el_turno_anterior():
    conversacion = Conversacion()
    conversacion.agregar("user", "¿qué facturas vencidas hay que reclamar?")
    conversacion.agregar("assistant", "Hay 3 vencidas.")
    ampliada = contextualizar("¿y la más antigua?", conversacion)
    assert "factura" in ampliada and "vencid" in ampliada


def test_una_consulta_completa_no_se_ensucia_con_contexto_viejo():
    """Anexar términos del tema anterior desviaría una consulta de otro tema."""
    conversacion = Conversacion()
    conversacion.agregar("user", "¿qué facturas vencidas hay?")
    nueva = "¿qué dice la política de vacaciones?"
    assert contextualizar(nueva, conversacion) == nueva


def test_sin_conversacion_la_consulta_no_cambia():
    assert contextualizar("¿y la más antigua?", None) == "¿y la más antigua?"


def test_sin_turno_previo_la_consulta_no_cambia():
    assert contextualizar("¿y eso?", Conversacion()) == "¿y eso?"


# --- Integración con el agente ----------------------------------------------


@pytest.fixture
def orquestador():
    return crear_orquestador(MockLLMClient(), load_settings())


def _conversar(orquestador, conversacion, pregunta):
    historial = conversacion.mensajes()
    respuesta = orquestador.run(pregunta, historial=historial)
    conversacion.agregar("user", pregunta)
    conversacion.agregar("assistant", respuesta)
    return respuesta


def test_la_repregunta_se_resuelve_en_el_dominio_correcto(orquestador):
    """El caso que antes fallaba: "¿y la más antigua?" no ruteaba a ningún lado."""
    conversacion = Conversacion()
    _conversar(orquestador, conversacion, "¿Qué facturas vencidas hay que reclamar?")
    respuesta = _conversar(orquestador, conversacion, "¿y la más antigua?")
    assert "FC-2026" in respuesta
    assert "No identifiqué un dominio" not in respuesta


def test_la_repregunta_documental_recupera_la_seccion_correcta(orquestador):
    conversacion = Conversacion()
    _conversar(orquestador, conversacion, "¿qué dice la política de vacaciones?")
    respuesta = _conversar(orquestador, conversacion, "¿y sobre mudanza?")
    assert "Mudanza" in respuesta


def test_un_cambio_de_tema_no_arrastra_el_anterior(orquestador):
    conversacion = Conversacion()
    _conversar(orquestador, conversacion, "¿Qué facturas vencidas hay que reclamar?")
    respuesta = _conversar(orquestador, conversacion, "¿qué dice la política de vacaciones?")
    assert "vacaciones" in respuesta.lower()
    assert "FC-2026" not in respuesta


def test_sin_historial_el_agente_se_comporta_igual_que_antes(orquestador):
    """La memoria es opcional: el bucle sin historial no cambia."""
    assert "FC-2026" in orquestador.run("¿Qué facturas vencidas hay que reclamar?")


def test_los_especialistas_siguen_sin_estado(orquestador):
    """Solo el orquestador recibe historial; el especialista recibe tarea autocontenida."""
    from enterprise_agents.agents.specialists import crear_analista_finanzas

    especialista = crear_analista_finanzas(MockLLMClient(), 8)
    primera = especialista.run("¿qué facturas vencidas hay?")
    segunda = especialista.run("¿qué facturas vencidas hay?")
    assert primera == segunda
