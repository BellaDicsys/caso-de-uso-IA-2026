"""Autenticación y gestión de usuarios/roles de la superficie web.

Prácticas aplicadas (versión demo, con camino documentado a producción):
- Claves con hash PBKDF2-HMAC-SHA256 (200k iteraciones) y salt por usuario;
  nunca se almacenan en claro.
- Sesiones con token aleatorio (`secrets`) entregado en cookie HttpOnly +
  SameSite=Lax, con expiración.
- Control de acceso por rol en el servidor (RBAC): `consulta` (chat),
  `gestor` (chat + tablero), `admin` (todo + gestión de usuarios).

En producción: reemplazar el almacén JSON por el directorio corporativo
(SSO/OIDC o passkeys) y las sesiones en memoria por un almacén compartido.
La CLI no pasa por esta capa: es una herramienta de operación local.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time

from enterprise_agents.config import DATA_DIR

ARCHIVO_USUARIOS = DATA_DIR / "usuarios.json"
ROLES = ("admin", "gestor", "consulta")
ROLES_TABLERO = ("admin", "gestor")
ITERACIONES = 200_000
DURACION_SESION_SEG = 8 * 60 * 60


def _hash_clave(clave: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(salt), ITERACIONES).hex()


def _leer_usuarios() -> list[dict[str, str]]:
    return json.loads(ARCHIVO_USUARIOS.read_text(encoding="utf-8"))["usuarios"]


def _escribir_usuarios(usuarios: list[dict[str, str]]) -> None:
    ARCHIVO_USUARIOS.write_text(
        json.dumps({"usuarios": usuarios}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def verificar_credenciales(usuario: str, clave: str) -> str | None:
    """Devuelve el rol si las credenciales son válidas; None si no."""
    for u in _leer_usuarios():
        if u["usuario"] == usuario:
            if secrets.compare_digest(_hash_clave(clave, u["salt"]), u["hash"]):
                return u["rol"]
            return None
    # Igualar el costo aunque el usuario no exista (evita enumeración por timing).
    _hash_clave(clave, "00" * 16)
    return None


def listar_usuarios() -> list[dict[str, str]]:
    return [{"usuario": u["usuario"], "rol": u["rol"]} for u in _leer_usuarios()]


def crear_usuario(usuario: str, clave: str, rol: str) -> None:
    usuario = usuario.strip().lower()
    if not usuario.isidentifier():
        raise ValueError("El nombre de usuario debe ser alfanumérico (sin espacios).")
    if rol not in ROLES:
        raise ValueError(f"Rol inválido: {rol}. Válidos: {', '.join(ROLES)}.")
    if len(clave) < 8:
        raise ValueError("La clave debe tener al menos 8 caracteres.")
    usuarios = _leer_usuarios()
    if any(u["usuario"] == usuario for u in usuarios):
        raise ValueError(f"El usuario '{usuario}' ya existe.")
    salt = secrets.token_hex(16)
    usuarios.append(
        {"usuario": usuario, "rol": rol, "salt": salt, "hash": _hash_clave(clave, salt)}
    )
    _escribir_usuarios(usuarios)


def eliminar_usuario(usuario: str) -> None:
    usuarios = _leer_usuarios()
    restantes = [u for u in usuarios if u["usuario"] != usuario]
    if len(restantes) == len(usuarios):
        raise ValueError(f"No existe el usuario '{usuario}'.")
    if not any(u["rol"] == "admin" for u in restantes):
        raise ValueError("No se puede eliminar el último administrador.")
    _escribir_usuarios(restantes)


class AlmacenSesiones:
    """Sesiones en memoria: token → (usuario, rol, expiración)."""

    def __init__(self) -> None:
        self._sesiones: dict[str, dict] = {}

    def crear(self, usuario: str, rol: str) -> str:
        token = secrets.token_urlsafe(32)
        self._sesiones[token] = {
            "usuario": usuario,
            "rol": rol,
            "expira": time.time() + DURACION_SESION_SEG,
        }
        return token

    def obtener(self, token: str | None) -> dict | None:
        if not token:
            return None
        sesion = self._sesiones.get(token)
        if sesion is None:
            return None
        if sesion["expira"] < time.time():
            del self._sesiones[token]
            return None
        return {"usuario": sesion["usuario"], "rol": sesion["rol"]}

    def cerrar(self, token: str | None) -> None:
        if token:
            self._sesiones.pop(token, None)
