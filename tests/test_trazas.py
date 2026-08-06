"""Tests de observabilidad: trazas jerárquicas, estimación de tokens y registro."""

from __future__ import annotations

import pytest

from enterprise_agents import tokens, trazas
from enterprise_agents.config import load_settings
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.orchestrator import crear_orquestador
from enterprise_agents.registro import RegistroTrazas

# --- Estimación de tokens ---------------------------------------------------


def test_el_texto_vacio_no_tiene_tokens():
    assert tokens.estimar("") == 0


def test_todo_texto_no_vacio_cuenta_al_menos_uno():
    assert tokens.estimar("a") >= 1


def test_la_estimacion_crece_con_la_longitud():
    corto = tokens.estimar("Las vacaciones se solicitan con anticipación.")
    largo = tokens.estimar("Las vacaciones se solicitan con anticipación. " * 10)
    assert largo > corto * 5


def test_los_numeros_pesan_mas_que_su_longitud():
    """ "1.234.567" son varias piezas pese a ser corto: no puede contarse como texto."""
    assert tokens.estimar("1.234.567") > tokens.estimar("abcdefghi") // 2


def test_la_estimacion_esta_en_el_orden_correcto():
    """Un párrafo de ~50 palabras debería rondar los 60-120 tokens."""
    parrafo = (
        "La rendición de gastos se presenta dentro de los diez días hábiles "
        "posteriores al regreso. Todo gasto requiere comprobante fiscal a nombre "
        "de la empresa. Los gastos sin comprobante no se reintegran, sin ninguna "
        "excepción prevista en esta política vigente."
    )
    assert 50 <= tokens.estimar(parrafo) <= 140


def test_estimar_mensajes_recorre_el_formato_de_la_api():
    mensajes = [
        {"role": "user", "content": "¿cuánto facturamos?"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Consulto las ventas."},
                {"type": "tool_use", "input": {"periodo": "2026"}},
            ],
        },
        {"role": "user", "content": [{"type": "tool_result", "content": "Total: 471,100"}]},
    ]
    assert tokens.estimar_mensajes(mensajes) > 10


def test_formatear_abrevia_los_miles():
    assert tokens.formatear(950) == "950"
    assert tokens.formatear(1500) == "1.5k"


# --- Jerarquía de la traza --------------------------------------------------


@pytest.fixture
def traza_de_consulta():
    orquestador = crear_orquestador(MockLLMClient(), load_settings())
    with trazas.capturar("¿qué facturas vencidas hay?", modo="demo") as traza:
        traza.respuesta = orquestador.run("¿qué facturas vencidas hay?")
    return traza


def test_la_delegacion_es_padre_de_la_herramienta(traza_de_consulta):
    """La lista plana engaña: la herramienta interna termina antes que su padre."""
    arbol = traza_de_consulta.arbol()
    niveles = {span.herramienta: nivel for nivel, span in arbol}
    assert niveles["delegar_analista_finanzas"] == 0
    assert niveles["facturas_vencidas"] == 1


def test_el_arbol_conserva_el_orden_de_invocacion(traza_de_consulta):
    """El span se registra al entrar, no al salir: si no, el orden se invierte."""
    orden = [span.herramienta for _, span in traza_de_consulta.arbol()]
    assert orden.index("delegar_analista_finanzas") < orden.index("facturas_vencidas")


def test_el_tiempo_total_no_suma_los_anidados_dos_veces(traza_de_consulta):
    raiz = sum(s.milisegundos for s in traza_de_consulta.spans if s.padre is None)
    todos = sum(s.milisegundos for s in traza_de_consulta.spans)
    assert traza_de_consulta.milisegundos == pytest.approx(raiz)
    assert todos > raiz  # hay anidamiento real


def test_registra_los_agentes_que_intervinieron(traza_de_consulta):
    assert traza_de_consulta.agentes == ["orquestador", "analista_finanzas"]


def test_los_tokens_se_reparten_por_agente(traza_de_consulta):
    por_agente = traza_de_consulta.tokens_por_agente
    assert set(por_agente) == {"orquestador", "analista_finanzas"}
    assert traza_de_consulta.tokens_contexto == sum(por_agente.values())


def test_la_traza_se_serializa_para_el_visor(traza_de_consulta):
    datos = traza_de_consulta.a_dict()
    assert datos["consulta"]
    assert datos["modo"] == "demo"
    assert datos["spans"][0]["nivel"] == 0
    assert all("resumen" in s for s in datos["spans"])


def test_la_impresion_dibuja_el_arbol(traza_de_consulta):
    salida = traza_de_consulta.imprimir()
    assert "delegar_analista_finanzas" in salida
    # La herramienta anidada va con más sangría que su padre.
    lineas = salida.splitlines()
    padre = next(i for i, x in enumerate(lineas) if "delegar_" in x)
    hijo = next(i for i, x in enumerate(lineas) if "facturas_vencidas" in x)
    assert len(lineas[hijo]) - len(lineas[hijo].lstrip()) > len(lineas[padre]) - len(
        lineas[padre].lstrip()
    )


def test_una_herramienta_que_falla_queda_marcada():
    from enterprise_agents.agents.base import Agent
    from enterprise_agents.tools.base import ToolDef

    def explota() -> str:
        raise RuntimeError("falla simulada")

    agente = Agent(
        name="prueba",
        system_prompt="",
        tools=[
            ToolDef(
                name="buscar_documentos",  # nombre que el router sabe elegir
                description="Busca en el repositorio documental interno políticas y manuales.",
                input_schema={"type": "object", "properties": {}},
                handler=lambda **_: explota(),
                ejemplos=('"¿qué dice la política de vacaciones?"',),
            )
        ],
        llm=MockLLMClient(),
    )
    with trazas.capturar() as traza:
        agente.run("¿qué dice la política de vacaciones?")
    assert traza.hubo_error
    assert traza.spans[0].error


def test_fuera_de_una_captura_no_se_registra_nada():
    orquestador = crear_orquestador(MockLLMClient(), load_settings())
    assert orquestador.run("¿qué facturas vencidas hay?")  # no explota ni cuesta


# --- Registro en memoria ----------------------------------------------------


def test_el_registro_devuelve_las_mas_recientes_primero():
    registro = RegistroTrazas(capacidad=10)
    for i in range(3):
        registro.agregar(trazas.Traza(consulta=f"consulta {i}"))
    assert [t.consulta for t in registro.recientes()] == ["consulta 2", "consulta 1", "consulta 0"]


def test_el_registro_descarta_las_viejas_al_llenarse():
    registro = RegistroTrazas(capacidad=2)
    for i in range(5):
        registro.agregar(trazas.Traza(consulta=f"c{i}"))
    assert len(registro) == 2
    assert [t.consulta for t in registro.recientes()] == ["c4", "c3"]


def test_el_resumen_de_un_registro_vacio_no_falla():
    assert RegistroTrazas().resumen()["consultas"] == 0


def test_el_resumen_promedia_y_cuenta_errores(traza_de_consulta):
    registro = RegistroTrazas()
    registro.agregar(traza_de_consulta)
    resumen = registro.resumen()
    assert resumen["consultas"] == 1
    assert resumen["ms_promedio"] > 0
    assert resumen["con_error"] == 0


def test_limpiar_vacia_el_registro(traza_de_consulta):
    registro = RegistroTrazas()
    registro.agregar(traza_de_consulta)
    registro.limpiar()
    assert len(registro) == 0
