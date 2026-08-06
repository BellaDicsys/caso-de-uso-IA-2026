"""API HTTP de la suite (FastAPI).

Superficie web completa:
- Chat (`/`) sobre el orquestador — requiere sesión (cualquier rol).
- Tablero de control (`/tablero`, datos en `/metricas`) — roles admin/gestor.
- Gestión de usuarios (`/usuarios`, API en `/usuarios/api`) — rol admin.
- Autenticación por sesión (`/login`, `/entrar`, `/salir`, `/sesion`).

Igual que la CLI, el chat funciona en modo demo (mock) sin ANTHROPIC_API_KEY.

Ejecución:
    enterprise-agents serve            # http://localhost:8000
"""

from __future__ import annotations

import os
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from enterprise_agents import __version__, trazas
from enterprise_agents.auth import (
    DURACION_SESION_SEG,
    ROLES_TABLERO,
    AlmacenSesiones,
    ControlIntentos,
    crear_usuario,
    eliminar_usuario,
    listar_usuarios,
    verificar_credenciales,
)
from enterprise_agents.config import Settings, load_settings
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.memoria import Conversacion
from enterprise_agents.metrics import calcular_metricas
from enterprise_agents.orchestrator import crear_orquestador
from enterprise_agents.registro import RegistroTrazas

_STATIC = Path(__file__).parent / "static"
_COOKIE = "sesion"
# Cookie Secure salvo en desarrollo local (ENTERPRISE_AGENTS_INSEGURO=1).
_COOKIE_SEGURA = os.getenv("ENTERPRISE_AGENTS_INSEGURO", "") != "1"


@lru_cache(maxsize=16)
def _pagina_html(archivo: str) -> str:
    """Lee una página estática una sola vez (son inmutables en runtime)."""
    return (_STATIC / archivo).read_text(encoding="utf-8")


class Consulta(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)


class Respuesta(BaseModel):
    respuesta: str
    modo: str
    # Estado de la memoria conversacional, para que la interfaz pueda mostrarlo.
    turnos: int = 0
    tokens_memoria: int = 0


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)
    clave: str = Field(min_length=1, max_length=120)


class AltaUsuario(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)
    clave: str = Field(min_length=8, max_length=120)
    rol: str


def _crear_llm(settings: Settings) -> tuple[LLMClient, str]:
    if settings.has_api_key:
        from enterprise_agents.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(model=settings.model), f"live ({settings.model})"
    return MockLLMClient(), "demo"


def crear_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    llm, modo = _crear_llm(settings)
    sesiones = AlmacenSesiones()
    intentos = ControlIntentos()
    registro = RegistroTrazas()
    # Una conversación por sesión. En memoria, igual que las sesiones y las
    # trazas, y con el mismo riesgo aceptado: con varios workers haría falta un
    # almacén compartido.
    conversaciones: dict[str, Conversacion] = {}
    lock_conversaciones = Lock()
    # Los agentes son stateless: se construye un orquestador por rol una sola
    # vez y se reusa entre requests (evita rearmarlo en cada consulta).
    orquestadores = {
        rol: crear_orquestador(llm, settings, rol) for rol in ("admin", "gestor", "consulta")
    }

    app = FastAPI(
        title="Enterprise Agent Suite",
        description="Suite agéntica de gestión empresarial — chat, tablero y administración.",
        version=__version__,
    )

    # --- Helpers de autorización -------------------------------------------

    def _sesion(request: Request) -> dict | None:
        return sesiones.obtener(request.cookies.get(_COOKIE))

    def _requerir(request: Request, roles: tuple[str, ...] | None = None) -> dict:
        sesion = _sesion(request)
        if sesion is None:
            raise HTTPException(status_code=401, detail="Sesión requerida.")
        if roles and sesion["rol"] not in roles:
            raise HTTPException(status_code=403, detail="Rol sin permiso para este recurso.")
        return sesion

    def _pagina(request: Request, archivo: str, roles: tuple[str, ...] | None = None):
        """Sirve una página protegida o redirige al login."""
        sesion = _sesion(request)
        if sesion is None:
            return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
        if roles and sesion["rol"] not in roles:
            return RedirectResponse("/?error=sin-permiso", status_code=303)
        return HTMLResponse(_pagina_html(archivo))

    # --- Recursos estáticos y salud ----------------------------------------

    @app.get("/ds.css", include_in_schema=False)
    def ds_css() -> FileResponse:
        return FileResponse(_STATIC / "ds.css", media_type="text/css")

    @app.get("/ds.js", include_in_schema=False)
    def ds_js() -> FileResponse:
        return FileResponse(_STATIC / "ds.js", media_type="text/javascript")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        # Favicon inline: evita un 404 en cada carga de página.
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            '<text y="26" font-size="26">🧭</text></svg>'
        )
        return Response(svg, media_type="image/svg+xml")

    @app.get("/salud")
    def salud() -> dict[str, str]:
        # Healthcheck público: no expone el modelo ni si hay API key configurada.
        return {"estado": "ok"}

    # --- Autenticación ------------------------------------------------------

    @app.get("/login", response_class=HTMLResponse)
    def login() -> str:
        return _pagina_html("login.html")

    @app.post("/entrar")
    def entrar(request: Request, credenciales: Credenciales):
        origen = request.client.host if request.client else "desconocido"
        clave_intentos = f"{credenciales.usuario}|{origen}"
        if intentos.bloqueado(clave_intentos):
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos fallidos. Reintentá en unos minutos.",
            )

        rol = verificar_credenciales(credenciales.usuario, credenciales.clave)
        if rol is None:
            intentos.registrar_fallo(clave_intentos)
            raise HTTPException(status_code=401, detail="Usuario o clave incorrectos.")

        intentos.limpiar(clave_intentos)
        token = sesiones.crear(credenciales.usuario, rol)
        respuesta = RedirectResponse("/", status_code=303)
        respuesta.set_cookie(
            _COOKIE,
            token,
            httponly=True,
            samesite="lax",
            secure=_COOKIE_SEGURA,
            max_age=DURACION_SESION_SEG,
        )
        return respuesta

    @app.post("/salir")
    def salir(request: Request):
        token = request.cookies.get(_COOKIE)
        with lock_conversaciones:
            conversaciones.pop(token or "", None)
        sesiones.cerrar(token)
        respuesta = RedirectResponse("/login", status_code=303)
        respuesta.delete_cookie(_COOKIE)
        return respuesta

    @app.get("/sesion")
    def sesion(request: Request) -> dict[str, str]:
        datos = _requerir(request)
        return {**datos, "modo": modo}

    # --- Chat ---------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def chat(request: Request):
        return _pagina(request, "index.html")

    @app.get("/ayuda", response_class=HTMLResponse)
    def ayuda(request: Request):
        """Ayuda e inducción al usuario: qué preguntar, cómo leer el tablero, roles."""
        return _pagina(request, "ayuda.html")

    @app.get("/movil", response_class=HTMLResponse)
    def movil(request: Request):
        """Versión móvil: alcance reducido (solo chat) con entrada/salida por voz."""
        return _pagina(request, "movil.html")

    def _conversacion(token: str) -> Conversacion:
        with lock_conversaciones:
            return conversaciones.setdefault(token, Conversacion())

    @app.post("/consultar", response_model=Respuesta)
    def consultar(request: Request, consulta: Consulta) -> Respuesta:
        sesion = _requerir(request)
        # RBAC a nivel de herramienta: el rol define qué dominios puede consultar.
        orquestador = orquestadores[sesion["rol"]]
        conversacion = _conversacion(request.cookies.get(_COOKIE, ""))
        historial = conversacion.mensajes()

        # Toda consulta queda trazada: sin esto no hay forma de auditar por qué
        # el asistente respondió lo que respondió (ver ADR-0011).
        with trazas.capturar(consulta.pregunta, modo=modo) as traza:
            traza.respuesta = orquestador.run(consulta.pregunta, historial=historial)
        registro.agregar(traza)

        conversacion.agregar("user", consulta.pregunta)
        conversacion.agregar("assistant", traza.respuesta)
        return Respuesta(
            respuesta=traza.respuesta,
            modo=modo,
            turnos=len(conversacion.turnos),
            tokens_memoria=conversacion.tokens,
        )

    @app.post("/conversacion/reiniciar")
    def reiniciar_conversacion(request: Request) -> dict[str, str]:
        """Descarta la memoria de la sesión sin cerrarla."""
        _requerir(request)
        _conversacion(request.cookies.get(_COOKIE, "")).limpiar()
        return {"estado": "reiniciada"}

    # --- Observabilidad -----------------------------------------------------

    @app.get("/trazas", response_class=HTMLResponse)
    def trazas_pagina(request: Request):
        """Visor de trazas: qué hizo el sistema en cada consulta reciente."""
        return _pagina(request, "trazas.html", ROLES_TABLERO)

    @app.get("/trazas/api")
    def trazas_datos(request: Request, limite: int = 20) -> dict:
        _requerir(request, ROLES_TABLERO)
        return {
            "resumen": registro.resumen(),
            "trazas": [t.a_dict() for t in registro.recientes(max(1, min(limite, 50)))],
        }

    # --- Tablero ------------------------------------------------------------

    @app.get("/tablero", response_class=HTMLResponse)
    def tablero(request: Request):
        return _pagina(request, "tablero.html", ROLES_TABLERO)

    @app.get("/metricas")
    def metricas(request: Request, hoy: str | None = None) -> dict:
        _requerir(request, ROLES_TABLERO)
        try:
            referencia = date.fromisoformat(hoy) if hoy else None
        except ValueError as error:
            raise HTTPException(
                status_code=422, detail="Parámetro 'hoy' inválido: usar AAAA-MM-DD."
            ) from error
        return calcular_metricas(referencia)

    # --- Gestión de usuarios (solo admin) ----------------------------------

    @app.get("/usuarios", response_class=HTMLResponse)
    def usuarios_pagina(request: Request):
        return _pagina(request, "usuarios.html", ("admin",))

    @app.get("/usuarios/api")
    def usuarios_listar(request: Request) -> list[dict[str, str]]:
        _requerir(request, ("admin",))
        return listar_usuarios()

    @app.post("/usuarios/api", status_code=201)
    def usuarios_crear(request: Request, alta: AltaUsuario) -> dict[str, str]:
        _requerir(request, ("admin",))
        try:
            crear_usuario(alta.usuario, alta.clave, alta.rol)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"usuario": alta.usuario.strip().lower(), "rol": alta.rol}

    @app.delete("/usuarios/api/{usuario}")
    def usuarios_eliminar(request: Request, usuario: str) -> dict[str, str]:
        actual = _requerir(request, ("admin",))
        if actual["usuario"] == usuario:
            raise HTTPException(status_code=400, detail="No podés eliminar tu propio usuario.")
        try:
            eliminar_usuario(usuario)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        # Revocación efectiva: cerrar las sesiones activas del usuario eliminado.
        sesiones.cerrar_de_usuario(usuario)
        return {"eliminado": usuario}

    # Referencias internas para tests (evita repetir el login en cada uno).
    app.state.sesiones = sesiones
    app.state.registro = registro
    return app


def servir(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Levanta el servidor (usado por `enterprise-agents serve`)."""
    import uvicorn

    from enterprise_agents.auth import usuarios_con_clave_demo

    demo = usuarios_con_clave_demo()
    if demo:
        print(
            f"⚠  Usuarios con clave de demostración activa: {', '.join(demo)}.\n"
            "   Están publicadas en el README: rotalas antes de exponer la app.",
            file=sys.stderr,
        )
    if not _COOKIE_SEGURA:
        print("⚠  Cookie de sesión sin Secure (modo desarrollo).", file=sys.stderr)

    uvicorn.run(crear_app(), host=host, port=port)
