"""Tests del ruteo semántico de herramientas (reemplazo de las palabras clave)."""

from __future__ import annotations

import pytest

from enterprise_agents.config import load_settings
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.llm.router import RouterSemantico
from enterprise_agents.orchestrator import crear_orquestador
from enterprise_agents.tools.documents import HERRAMIENTAS_DOCUMENTOS
from enterprise_agents.tools.finance import HERRAMIENTAS_FINANZAS


@pytest.fixture(scope="module")
def router_orquestador():
    orquestador = crear_orquestador(MockLLMClient(), load_settings())
    return RouterSemantico({n: t.texto_de_intencion() for n, t in orquestador.tools.items()})


@pytest.fixture(scope="module")
def router_documental():
    return RouterSemantico({t.name: t.texto_de_intencion() for t in HERRAMIENTAS_DOCUMENTOS})


@pytest.fixture(scope="module")
def router_finanzas():
    return RouterSemantico({t.name: t.texto_de_intencion() for t in HERRAMIENTAS_FINANZAS})


# --- Delegación desde el orquestador ----------------------------------------


@pytest.mark.parametrize(
    ("consulta", "esperada"),
    [
        ("¿Cuánto facturamos este año?", "delegar_analista_datos"),
        ("¿Qué proyectos están en riesgo?", "delegar_analista_datos"),
        ("¿Qué facturas vencidas hay que reclamar?", "delegar_analista_finanzas"),
        ("¿Cuánto nos debe Retail Sur?", "delegar_analista_finanzas"),
        ("¿Qué dice la política de vacaciones?", "delegar_gestor_documental"),
        ("¿Puedo trabajar desde casa?", "delegar_gestor_documental"),
        ("¿Quién sabe Python y está libre?", "delegar_gestor_personal"),
        ("¿Hay personas sin asignar?", "delegar_gestor_personal"),
    ],
)
def test_delega_en_el_especialista_correcto(router_orquestador, consulta, esperada):
    eleccion = router_orquestador.elegir(consulta)
    assert eleccion is not None, consulta
    assert eleccion.nombre == esperada


def test_regresion_monto_de_la_deuda_va_a_finanzas(router_orquestador):
    """Caso de la auditoría: con palabras clave caía en el analista de datos."""
    eleccion = router_orquestador.elegir("¿cuál es el monto de la deuda de los clientes?")
    assert eleccion is not None
    assert eleccion.nombre == "delegar_analista_finanzas"


def test_regresion_debemos_entregar_va_a_documental(router_orquestador):
    """Caso de la auditoría: "debemos" matcheaba dentro de las keywords de finanzas."""
    eleccion = router_orquestador.elegir("¿qué le debemos entregar según el contrato marco?")
    assert eleccion is not None
    assert eleccion.nombre == "delegar_gestor_documental"


@pytest.mark.parametrize(
    "consulta",
    ["¿va a llover mañana?", "recetas de cocina italiana", "¿cuánto mide el edificio?"],
)
def test_rechaza_consultas_ajenas_a_toda_herramienta(router_orquestador, consulta):
    assert router_orquestador.elegir(consulta) is None


# --- Ruteo dentro de un especialista ----------------------------------------


@pytest.mark.parametrize(
    ("consulta", "esperada"),
    [
        ("¿qué dice la política de vacaciones?", "buscar_documentos"),
        ("¿cuántos días de vacaciones con 7 años de antigüedad?", "buscar_documentos"),
        ("¿cada cuánto se respalda la base de datos?", "buscar_documentos"),
        ("mostrame el texto completo del documento", "leer_documento"),
    ],
)
def test_ruteo_documental(router_documental, consulta, esperada):
    eleccion = router_documental.elegir(consulta)
    assert eleccion is not None, consulta
    assert eleccion.nombre == esperada


@pytest.mark.parametrize(
    ("consulta", "esperada"),
    [
        ("¿qué facturas están impagas?", "facturas_vencidas"),
        ("¿cuánto nos adeuda cada cliente?", "deuda_por_cliente"),
        ("¿cómo está la cobranza en general?", "estado_cobranzas"),
    ],
)
def test_ruteo_dentro_de_finanzas(router_finanzas, consulta, esperada):
    eleccion = router_finanzas.elegir(consulta)
    assert eleccion is not None, consulta
    assert eleccion.nombre == esperada


# --- Propiedades del router -------------------------------------------------


def test_router_sin_herramientas_no_elige():
    assert RouterSemantico({}).elegir("lo que sea") is None


def test_la_eleccion_reporta_su_respaldo(router_orquestador):
    eleccion = router_orquestador.elegir("¿qué facturas vencidas hay?")
    assert eleccion is not None
    assert eleccion.puntaje > 0
    assert 0 < eleccion.cobertura <= 1


def test_el_ruteo_es_determinista(router_orquestador):
    consulta = "¿cuánto facturamos y a qué clientes?"
    elecciones = {router_orquestador.elegir(consulta).nombre for _ in range(5)}
    assert len(elecciones) == 1


def test_el_router_solo_compite_entre_las_herramientas_ofrecidas():
    """Con rol `consulta` no existen finanzas ni personal: no puede elegirlas."""
    orquestador = crear_orquestador(MockLLMClient(), load_settings(), rol="consulta")
    router = RouterSemantico({n: t.texto_de_intencion() for n, t in orquestador.tools.items()})
    eleccion = router.elegir("¿qué facturas vencidas hay que reclamar?")
    assert eleccion is None or eleccion.nombre in {
        "delegar_analista_datos",
        "delegar_gestor_documental",
    }


# --- Integración con el cliente simulado ------------------------------------


def test_el_mock_reusa_el_router_por_conjunto_de_herramientas():
    """El índice se construye una vez por conjunto ofrecido, no por consulta."""
    cliente = MockLLMClient()
    orquestador = crear_orquestador(cliente, load_settings())
    orquestador.run("¿cuánto facturamos?")
    orquestador.run("¿qué facturas vencidas hay?")
    # Un router para el orquestador y uno por cada especialista que intervino.
    assert len(cliente._routers) <= 3


def test_el_mock_resuelve_el_documento_con_el_motor_de_recuperacion():
    """leer_documento ya no responde con un nombre de archivo fijo."""
    cliente = MockLLMClient()
    argumentos = cliente._armar_argumentos(
        "leer_documento", "el texto completo del plan de respuesta a incidentes", ""
    )
    assert argumentos["nombre"] == "plan-respuesta-incidentes.md"
