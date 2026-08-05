"""Tests de la API HTTP (FastAPI) en modo mock, con autenticación."""

from conftest import entrar


def test_salud_es_publico_y_no_filtra_el_modelo(cliente):
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    # El healthcheck público no revela modo ni modelo (fingerprinting).
    assert respuesta.json() == {"estado": "ok"}


def test_paginas_protegidas_redirigen_a_login(cliente):
    for ruta in ("/", "/movil", "/tablero", "/usuarios"):
        respuesta = cliente.get(ruta, follow_redirects=False)
        assert respuesta.status_code == 303, ruta
        assert respuesta.headers["location"].startswith("/login"), ruta


def test_consultar_sin_sesion_devuelve_401(cliente):
    respuesta = cliente.post("/consultar", json={"pregunta": "¿ventas?"})
    assert respuesta.status_code == 401


def test_chat_web_se_sirve_con_sesion(cliente):
    entrar(cliente, "consulta")
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "Enterprise Agent Suite" in respuesta.text


def test_movil_incluye_chat_de_voz(cliente):
    entrar(cliente, "consulta")
    respuesta = cliente.get("/movil")
    assert respuesta.status_code == 200
    assert "SpeechRecognition" in respuesta.text
    assert "speechSynthesis" in respuesta.text


def test_consultar_devuelve_respuesta_del_orquestador(cliente):
    entrar(cliente, "gestion")
    respuesta = cliente.post(
        "/consultar", json={"pregunta": "¿Qué facturas vencidas hay que reclamar?"}
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["modo"] == "demo"
    assert "FC-2026" in datos["respuesta"]


def test_rol_consulta_no_accede_a_finanzas_ni_personal_por_el_chat(cliente):
    """El chat no debe ser una vía alternativa a los datos que el tablero reserva."""
    entrar(cliente, "consulta")

    finanzas = cliente.post(
        "/consultar", json={"pregunta": "¿Qué facturas vencidas hay que reclamar?"}
    ).json()["respuesta"]
    assert "FC-2026" not in finanzas

    personal = cliente.post(
        "/consultar", json={"pregunta": "¿Qué perfiles con Python tienen disponibilidad?"}
    ).json()["respuesta"]
    assert "Martina" not in personal

    # Los dominios permitidos para ese rol sí responden.
    ventas = cliente.post("/consultar", json={"pregunta": "¿Cuánto facturamos?"}).json()[
        "respuesta"
    ]
    assert "USD" in ventas


def test_consultar_valida_entrada(cliente):
    entrar(cliente, "consulta")
    assert cliente.post("/consultar", json={"pregunta": ""}).status_code == 422
    assert cliente.post("/consultar", json={}).status_code == 422


def test_metricas_requiere_rol_de_gestion(cliente):
    entrar(cliente, "consulta")
    assert cliente.get("/metricas").status_code == 403

    entrar(cliente, "gestion")
    respuesta = cliente.get("/metricas?hoy=2026-08-05")
    assert respuesta.status_code == 200
    assert respuesta.json()["kpis"]["facturacion_total"] == 471100


def test_tablero_sin_rol_redirige_al_chat(cliente):
    entrar(cliente, "consulta")
    respuesta = cliente.get("/tablero", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/?error")
