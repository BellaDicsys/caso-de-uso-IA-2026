"""Tests de la API HTTP (FastAPI) en modo mock, con autenticación."""

import re

from conftest import entrar


def test_salud_es_publico_y_no_filtra_el_modelo(cliente):
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    # El healthcheck público no revela modo ni modelo (fingerprinting).
    assert respuesta.json() == {"estado": "ok"}


def test_paginas_protegidas_redirigen_a_login(cliente):
    for ruta in ("/", "/movil", "/ayuda", "/tablero", "/usuarios"):
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


def test_ayuda_disponible_para_todos_los_roles(cliente):
    """La inducción al usuario no depende del rol: los tres deben poder leerla."""
    for usuario in ("consulta", "gestion", "admin"):
        entrar(cliente, usuario)
        respuesta = cliente.get("/ayuda")
        assert respuesta.status_code == 200, usuario
        assert "Ayuda y primeros pasos" in respuesta.text


def test_ayuda_oculta_por_defecto_los_bloques_por_rol(cliente):
    """Se sirven ocultos y el cliente revela solo los del rol: nadie ve de más."""
    entrar(cliente, "consulta")
    texto = cliente.get("/ayuda").text
    bloques = re.findall(r'data-rol="[^"]+"(.{0,8})', texto)
    assert bloques, "la ayuda debería tener bloques segmentados por rol"
    assert all(resto.startswith(" hidden") for resto in bloques)


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


# --- Observabilidad ---------------------------------------------------------


def test_la_consulta_queda_registrada_en_las_trazas(cliente):
    entrar(cliente, "gestion")
    cliente.post("/consultar", json={"pregunta": "¿Qué facturas vencidas hay?"})
    datos = cliente.get("/trazas/api").json()
    assert datos["resumen"]["consultas"] >= 1
    traza = datos["trazas"][0]
    assert traza["consulta"] == "¿Qué facturas vencidas hay?"
    assert any(s["herramienta"] == "facturas_vencidas" for s in traza["spans"])
    # La jerarquía llega al visor: la herramienta va anidada bajo la delegación.
    niveles = {s["herramienta"]: s["nivel"] for s in traza["spans"]}
    assert niveles["facturas_vencidas"] > niveles["delegar_analista_finanzas"]


def test_las_trazas_son_de_gestor_y_admin(cliente):
    entrar(cliente, "consulta")
    assert cliente.get("/trazas/api").status_code == 403
    assert cliente.get("/trazas", follow_redirects=False).status_code == 303


def test_el_limite_de_trazas_se_acota(cliente):
    entrar(cliente, "admin")
    assert cliente.get("/trazas/api?limite=999").status_code == 200
    assert cliente.get("/trazas/api?limite=0").status_code == 200


# --- Memoria conversacional -------------------------------------------------


def test_el_asistente_recuerda_dentro_de_la_sesion(cliente):
    entrar(cliente, "gestion")
    cliente.post("/consultar", json={"pregunta": "¿Qué facturas vencidas hay que reclamar?"})
    datos = cliente.post("/consultar", json={"pregunta": "¿y la más antigua?"}).json()
    assert "FC-2026" in datos["respuesta"]
    assert datos["turnos"] == 4  # dos preguntas y dos respuestas
    assert datos["tokens_memoria"] > 0


def test_reiniciar_borra_la_memoria_sin_cerrar_la_sesion(cliente):
    entrar(cliente, "gestion")
    cliente.post("/consultar", json={"pregunta": "¿Qué facturas vencidas hay?"})
    assert cliente.post("/conversacion/reiniciar").json()["estado"] == "reiniciada"
    datos = cliente.post("/consultar", json={"pregunta": "¿Cuánto facturamos este año?"}).json()
    assert datos["turnos"] == 2  # arrancó de cero
    assert cliente.get("/sesion").status_code == 200  # la sesión sigue viva


def test_reiniciar_requiere_sesion(cliente):
    assert cliente.post("/conversacion/reiniciar").status_code == 401


def test_cada_sesion_tiene_su_propia_memoria(cliente, usuarios_temporales):
    from fastapi.testclient import TestClient

    entrar(cliente, "gestion")
    cliente.post("/consultar", json={"pregunta": "¿Qué facturas vencidas hay?"})

    otro = TestClient(cliente.app, base_url="https://testserver")
    entrar(otro, "admin")
    datos = otro.post("/consultar", json={"pregunta": "¿Cuánto facturamos?"}).json()
    assert datos["turnos"] == 2  # no heredó la conversación de la otra sesión


def test_salir_descarta_la_memoria(cliente):
    entrar(cliente, "gestion")
    cliente.post("/consultar", json={"pregunta": "¿Qué facturas vencidas hay?"})
    cliente.post("/salir")
    entrar(cliente, "gestion")
    datos = cliente.post("/consultar", json={"pregunta": "¿Cuánto facturamos?"}).json()
    assert datos["turnos"] == 2


# --- Regresiones de la segunda ronda de auditoría ---------------------------


def test_un_gestor_no_ve_las_consultas_de_otro_usuario(cliente):
    """Hallazgo: el registro de trazas era global y filtraba conversaciones ajenas."""
    from fastapi.testclient import TestClient

    entrar(cliente, "consulta")
    cliente.post("/consultar", json={"pregunta": "¿cuántos días de vacaciones me corresponden?"})

    gestor = TestClient(cliente.app, base_url="https://testserver")
    entrar(gestor, "gestion")
    datos = gestor.get("/trazas/api").json()
    assert datos["alcance"] == "propias"
    assert all("vacaciones me corresponden" not in t["consulta"] for t in datos["trazas"])


def test_cada_uno_ve_sus_propias_trazas(cliente):
    entrar(cliente, "gestion")
    cliente.post("/consultar", json={"pregunta": "¿Qué facturas vencidas hay?"})
    datos = cliente.get("/trazas/api").json()
    assert [t["consulta"] for t in datos["trazas"]] == ["¿Qué facturas vencidas hay?"]
    assert all(t["usuario"] == "gestion" for t in datos["trazas"])


def test_el_admin_ve_todas_las_trazas_y_el_visor_lo_declara(cliente):
    """Ver todo es una capacidad de administración, pero tiene que ser explícita."""
    from fastapi.testclient import TestClient

    entrar(cliente, "consulta")
    cliente.post("/consultar", json={"pregunta": "¿Cuánto facturamos este año?"})

    admin = TestClient(cliente.app, base_url="https://testserver")
    entrar(admin, "admin")
    datos = admin.get("/trazas/api").json()
    assert datos["alcance"] == "todas"
    assert any(t["usuario"] == "consulta" for t in datos["trazas"])


def test_las_conversaciones_de_sesiones_muertas_se_purgan(cliente):
    """Hallazgo: solo se borraban al salir; una sesión expirada dejaba la suya."""
    from fastapi.testclient import TestClient

    entrar(cliente, "gestion")
    cliente.post("/consultar", json={"pregunta": "¿Qué facturas vencidas hay?"})
    # Se revoca la sesión por detrás, como haría una expiración.
    cliente.app.state.sesiones.cerrar_de_usuario("gestion")

    otro = TestClient(cliente.app, base_url="https://testserver")
    entrar(otro, "admin")
    otro.post("/consultar", json={"pregunta": "¿Cuánto facturamos?"})
    # La entrada huérfana no sobrevive a la siguiente conversación.
    assert len(cliente.app.state.conversaciones) == 1
