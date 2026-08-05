"""Fixtures compartidas de la suite de tests."""

import shutil

import pytest
from fastapi.testclient import TestClient

import enterprise_agents.auth as auth
from enterprise_agents.api import crear_app
from enterprise_agents.config import Settings


@pytest.fixture
def usuarios_temporales(tmp_path, monkeypatch):
    """Copia data/usuarios.json a un tmp para que los tests no lo modifiquen."""
    copia = tmp_path / "usuarios.json"
    shutil.copy(auth.ARCHIVO_USUARIOS, copia)
    monkeypatch.setattr(auth, "ARCHIVO_USUARIOS", copia)
    return copia


@pytest.fixture
def cliente(usuarios_temporales):
    """TestClient de la app en modo mock (sin API key).

    Usa https como base porque la cookie de sesión es `Secure`: sobre http el
    cliente no la reenviaría, igual que un navegador real.
    """
    return TestClient(crear_app(Settings(api_key=None)), base_url="https://testserver")


def entrar(cliente: TestClient, usuario: str = "admin", clave: str | None = None) -> None:
    """Inicia sesión en el TestClient (la cookie queda en el jar del cliente)."""
    respuesta = cliente.post(
        "/entrar",
        json={"usuario": usuario, "clave": clave or f"{usuario}2026"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303, f"login falló para {usuario}"
