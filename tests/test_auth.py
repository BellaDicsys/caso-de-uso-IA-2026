"""Tests de autenticación, usuarios y roles."""

import pytest

from conftest import entrar
from enterprise_agents.auth import crear_usuario, verificar_credenciales


def test_credenciales_validas_e_invalidas(usuarios_temporales):
    assert verificar_credenciales("admin", "admin2026") == "admin"
    assert verificar_credenciales("admin", "incorrecta") is None
    assert verificar_credenciales("inexistente", "loquesea") is None


def test_login_invalido_devuelve_401(cliente):
    respuesta = cliente.post("/entrar", json={"usuario": "admin", "clave": "mala"})
    assert respuesta.status_code == 401


def test_sesion_devuelve_usuario_y_rol(cliente):
    entrar(cliente, "gestion")
    datos = cliente.get("/sesion").json()
    assert datos["usuario"] == "gestion"
    assert datos["rol"] == "gestor"


def test_salir_invalida_la_sesion(cliente):
    entrar(cliente, "consulta")
    assert cliente.get("/sesion").status_code == 200
    cliente.post("/salir", follow_redirects=False)
    assert cliente.get("/sesion").status_code == 401


def test_gestion_de_usuarios_solo_admin(cliente):
    entrar(cliente, "gestion")
    assert cliente.get("/usuarios/api").status_code == 403

    entrar(cliente, "admin")
    usuarios = cliente.get("/usuarios/api").json()
    assert {"usuario": "admin", "rol": "admin"} in usuarios
    # Las claves y hashes nunca se exponen por la API.
    assert all(set(u) == {"usuario", "rol"} for u in usuarios)


def test_alta_y_baja_de_usuario(cliente):
    entrar(cliente, "admin")
    alta = cliente.post(
        "/usuarios/api",
        json={"usuario": "nuevo", "clave": "clave-segura-1", "rol": "consulta"},
    )
    assert alta.status_code == 201

    # El usuario nuevo puede iniciar sesión con su rol.
    entrar(cliente, "nuevo", "clave-segura-1")
    assert cliente.get("/sesion").json()["rol"] == "consulta"
    assert cliente.get("/metricas").status_code == 403

    entrar(cliente, "admin")
    assert cliente.delete("/usuarios/api/nuevo").status_code == 200
    assert (
        cliente.post("/entrar", json={"usuario": "nuevo", "clave": "clave-segura-1"}).status_code
        == 401
    )


def test_no_se_puede_eliminar_el_propio_usuario_ni_el_ultimo_admin(cliente):
    entrar(cliente, "admin")
    assert cliente.delete("/usuarios/api/admin").status_code == 400


def test_validaciones_de_alta(usuarios_temporales):
    with pytest.raises(ValueError, match="al menos 8"):
        crear_usuario("corto", "corta", "consulta")
    with pytest.raises(ValueError, match="Rol inválido"):
        crear_usuario("otro", "clave-segura-1", "superusuario")
    with pytest.raises(ValueError, match="ya existe"):
        crear_usuario("admin", "clave-segura-1", "admin")


def test_login_bloquea_tras_intentos_fallidos(cliente):
    """Rate limiting: 5 fallos bloquean temporalmente (anti fuerza bruta)."""
    for _ in range(5):
        assert (
            cliente.post("/entrar", json={"usuario": "admin", "clave": "mala"}).status_code == 401
        )
    respuesta = cliente.post("/entrar", json={"usuario": "admin", "clave": "mala"})
    assert respuesta.status_code == 429
    # También se bloquea la clave correcta mientras dura el bloqueo.
    assert (
        cliente.post("/entrar", json={"usuario": "admin", "clave": "admin2026"}).status_code == 429
    )


def test_cookie_de_sesion_es_httponly_y_secure(cliente):
    respuesta = cliente.post(
        "/entrar", json={"usuario": "admin", "clave": "admin2026"}, follow_redirects=False
    )
    cookie = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" in cookie


def test_eliminar_usuario_revoca_sus_sesiones(cliente):
    """Revocación efectiva: la sesión del usuario eliminado deja de servir."""
    from fastapi.testclient import TestClient

    entrar(cliente, "admin")
    cliente.post(
        "/usuarios/api", json={"usuario": "temporal", "clave": "clave-segura-1", "rol": "consulta"}
    )

    # Sesión independiente del usuario temporal (mismo app, otro jar de cookies).
    otro = TestClient(cliente.app, base_url="https://testserver")
    otro.post(
        "/entrar",
        json={"usuario": "temporal", "clave": "clave-segura-1"},
        follow_redirects=False,
    )
    assert otro.get("/sesion").status_code == 200

    cliente.delete("/usuarios/api/temporal")
    assert otro.get("/sesion").status_code == 401


def test_metricas_con_fecha_invalida_devuelve_422(cliente):
    entrar(cliente, "gestion")
    assert cliente.get("/metricas?hoy=no-es-fecha").status_code == 422
