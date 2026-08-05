"""Autenticación y gestión de usuarios/roles de la superficie web.

Prácticas aplicadas (versión demo, con camino documentado a producción):
- Claves con hash PBKDF2-HMAC-SHA256 (200k iteraciones) y salt por usuario;
  nunca se almacenan en claro.
- Sesiones con token aleatorio (`secrets`) entregado en cookie HttpOnly +
  SameSite=Lax (+ Secure fuera de desarrollo), con expiración.
- Control de acceso por rol en el servidor (RBAC): `consulta` (chat),
  `gestor` (chat + tablero + datos de finanzas/RRHH), `admin` (todo +
  gestión de usuarios).
- Revocación efectiva: al eliminar un usuario se cierran sus sesiones activas.
- Límite de intentos de login por usuario/IP para frenar fuerza bruta.
- Escrituras atómicas del almacén de usuarios (tmp + replace) bajo lock.

En producción: reemplazar el almacén JSON por el directorio corporativo
(SSO/OIDC o passkeys) y las sesiones en memoria por un almacén compartido
(Redis) para soportar varios workers. La CLI no pasa por esta capa: es una
herramienta de operación local.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import threading
import time

from enterprise_agents.config import DATA_DIR

ARCHIVO_USUARIOS = DATA_DIR / "usuarios.json"
ROLES = ("admin", "gestor", "consulta")
# Roles que pueden ver datos de gestión (tablero, finanzas, personal).
ROLES_TABLERO = ("admin", "gestor")
ITERACIONES = 200_000
DURACION_SESION_SEG = 8 * 60 * 60

# Anti fuerza bruta: N intentos fallidos por clave (usuario|ip) bloquean por M seg.
MAX_INTENTOS = 5
BLOQUEO_SEG = 300

_lock_usuarios = threading.Lock()


def _hash_clave(clave: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(salt), ITERACIONES).hex()


def _leer_usuarios() -> list[dict[str, str]]:
    return json.loads(ARCHIVO_USUARIOS.read_text(encoding="utf-8"))["usuarios"]


def _escribir_usuarios(usuarios: list[dict[str, str]]) -> None:
    """Escritura atómica: escribe a un temporal y reemplaza (evita corrupción)."""
    contenido = json.dumps({"usuarios": usuarios}, indent=2, ensure_ascii=False) + "\n"
    directorio = ARCHIVO_USUARIOS.parent
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directorio, delete=False
    ) as temporal:
        temporal.write(contenido)
        temporal.flush()
        os.fsync(temporal.fileno())
        ruta_temporal = temporal.name
    os.replace(ruta_temporal, ARCHIVO_USUARIOS)


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
    salt = secrets.token_hex(16)
    nuevo = {"usuario": usuario, "rol": rol, "salt": salt, "hash": _hash_clave(clave, salt)}
    with _lock_usuarios:
        usuarios = _leer_usuarios()
        if any(u["usuario"] == usuario for u in usuarios):
            raise ValueError(f"El usuario '{usuario}' ya existe.")
        usuarios.append(nuevo)
        _escribir_usuarios(usuarios)


def eliminar_usuario(usuario: str) -> None:
    with _lock_usuarios:
        usuarios = _leer_usuarios()
        restantes = [u for u in usuarios if u["usuario"] != usuario]
        if len(restantes) == len(usuarios):
            raise ValueError(f"No existe el usuario '{usuario}'.")
        if not any(u["rol"] == "admin" for u in restantes):
            raise ValueError("No se puede eliminar el último administrador.")
        _escribir_usuarios(restantes)


class ControlIntentos:
    """Contador de intentos fallidos de login con bloqueo temporal."""

    def __init__(self, maximo: int = MAX_INTENTOS, bloqueo: int = BLOQUEO_SEG) -> None:
        self._maximo = maximo
        self._bloqueo = bloqueo
        self._fallos: dict[str, tuple[int, float]] = {}

    def bloqueado(self, clave: str) -> bool:
        registro = self._fallos.get(clave)
        if registro is None:
            return False
        intentos, ultimo = registro
        if time.time() - ultimo > self._bloqueo:
            del self._fallos[clave]
            return False
        return intentos >= self._maximo

    def registrar_fallo(self, clave: str) -> None:
        intentos, ultimo = self._fallos.get(clave, (0, 0.0))
        if time.time() - ultimo > self._bloqueo:
            intentos = 0
        self._fallos[clave] = (intentos + 1, time.time())

    def limpiar(self, clave: str) -> None:
        self._fallos.pop(clave, None)


class AlmacenSesiones:
    """Sesiones en memoria: token → (usuario, rol, expiración)."""

    def __init__(self) -> None:
        self._sesiones: dict[str, dict] = {}
        self._lock = threading.Lock()

    def crear(self, usuario: str, rol: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._purgar_expiradas()
            self._sesiones[token] = {
                "usuario": usuario,
                "rol": rol,
                "expira": time.time() + DURACION_SESION_SEG,
            }
        return token

    def obtener(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._lock:
            sesion = self._sesiones.get(token)
            if sesion is None:
                return None
            if sesion["expira"] < time.time():
                del self._sesiones[token]
                return None
            return {"usuario": sesion["usuario"], "rol": sesion["rol"]}

    def cerrar(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sesiones.pop(token, None)

    def cerrar_de_usuario(self, usuario: str) -> int:
        """Revoca todas las sesiones de un usuario (al eliminarlo o cambiar su rol)."""
        with self._lock:
            tokens = [t for t, s in self._sesiones.items() if s["usuario"] == usuario]
            for token in tokens:
                del self._sesiones[token]
            return len(tokens)

    def _purgar_expiradas(self) -> None:
        """Elimina sesiones vencidas (evita crecimiento indefinido del dict)."""
        ahora = time.time()
        for token in [t for t, s in self._sesiones.items() if s["expira"] < ahora]:
            del self._sesiones[token]


CLAVES_DEMO = {"admin": "admin2026", "gestion": "gestion2026", "consulta": "consulta2026"}


def usuarios_con_clave_demo() -> list[str]:
    """Usuarios que aún tienen la clave de demostración documentada.

    Se usa para advertir al iniciar el servidor: estas credenciales están
    publicadas en el README y en la pantalla de login, así que un despliegue
    real debe rotarlas antes de exponer la aplicación.
    """
    activos = []
    for u in _leer_usuarios():
        demo = CLAVES_DEMO.get(u["usuario"])
        if demo and secrets.compare_digest(_hash_clave(demo, u["salt"]), u["hash"]):
            activos.append(u["usuario"])
    return activos
