"""Tests de la API HTTP (FastAPI) en modo mock."""

from fastapi.testclient import TestClient

from enterprise_agents.api import crear_app
from enterprise_agents.config import Settings


def _cliente() -> TestClient:
    # Settings sin API key → la app corre en modo mock.
    return TestClient(crear_app(Settings(api_key=None)))


def test_salud_reporta_modo_demo():
    respuesta = _cliente().get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "modo": "demo"}


def test_chat_web_se_sirve_en_raiz():
    respuesta = _cliente().get("/")
    assert respuesta.status_code == 200
    assert "Enterprise Agent Suite" in respuesta.text
    assert "/consultar" in respuesta.text


def test_consultar_devuelve_respuesta_del_orquestador():
    respuesta = _cliente().post(
        "/consultar", json={"pregunta": "¿Qué facturas vencidas hay que reclamar?"}
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["modo"] == "demo"
    assert "FC-2026" in datos["respuesta"]


def test_consultar_valida_entrada():
    assert _cliente().post("/consultar", json={"pregunta": ""}).status_code == 422
    assert _cliente().post("/consultar", json={}).status_code == 422
