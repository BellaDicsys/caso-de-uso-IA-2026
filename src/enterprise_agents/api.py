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

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from enterprise_agents.auth import (
    ROLES_TABLERO,
    AlmacenSesiones,
    crear_usuario,
    eliminar_usuario,
    listar_usuarios,
    verificar_credenciales,
)
from enterprise_agents.config import Settings, load_settings
from enterprise_agents.llm.base import LLMClient
from enterprise_agents.llm.mock_client import MockLLMClient
from enterprise_agents.metrics import calcular_metricas
from enterprise_agents.orchestrator import crear_orquestador

_STATIC = Path(__file__).parent / "static"
_COOKIE = "sesion"


class Consulta(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)


class Respuesta(BaseModel):
    respuesta: str
    modo: str


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

    app = FastAPI(
        title="Enterprise Agent Suite",
        description="Suite agéntica de gestión empresarial — chat, tablero y administración.",
        version="0.3.0",
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
        return HTMLResponse((_STATIC / archivo).read_text(encoding="utf-8"))

    # --- Recursos estáticos y salud ----------------------------------------

    @app.get("/ds.css", include_in_schema=False)
    def ds_css() -> FileResponse:
        return FileResponse(_STATIC / "ds.css", media_type="text/css")

    @app.get("/ds.js", include_in_schema=False)
    def ds_js() -> FileResponse:
        return FileResponse(_STATIC / "ds.js", media_type="text/javascript")

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok", "modo": modo}

    # --- Autenticación ------------------------------------------------------

    @app.get("/login", response_class=HTMLResponse)
    def login() -> str:
        return (_STATIC / "login.html").read_text(encoding="utf-8")

    @app.post("/entrar")
    def entrar(credenciales: Credenciales):
        rol = verificar_credenciales(credenciales.usuario, credenciales.clave)
        if rol is None:
            raise HTTPException(status_code=401, detail="Usuario o clave incorrectos.")
        token = sesiones.crear(credenciales.usuario, rol)
        respuesta = RedirectResponse("/", status_code=303)
        respuesta.set_cookie(_COOKIE, token, httponly=True, samesite="lax", max_age=8 * 60 * 60)
        return respuesta

    @app.post("/salir")
    def salir(request: Request):
        sesiones.cerrar(request.cookies.get(_COOKIE))
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

    @app.get("/movil", response_class=HTMLResponse)
    def movil(request: Request):
        """Versión móvil: alcance reducido (solo chat) con entrada/salida por voz."""
        return _pagina(request, "movil.html")

    @app.post("/consultar", response_model=Respuesta)
    def consultar(request: Request, consulta: Consulta) -> Respuesta:
        _requerir(request)
        orquestador = crear_orquestador(llm, settings)
        return Respuesta(respuesta=orquestador.run(consulta.pregunta), modo=modo)

    # --- Tablero ------------------------------------------------------------

    @app.get("/tablero", response_class=HTMLResponse)
    def tablero(request: Request):
        return _pagina(request, "tablero.html", ROLES_TABLERO)

    @app.get("/metricas")
    def metricas(request: Request, hoy: str | None = None) -> dict:
        _requerir(request, ROLES_TABLERO)
        referencia = date.fromisoformat(hoy) if hoy else None
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
        return {"eliminado": usuario}

    # Referencia interna para tests (evita repetir el login en cada uno).
    app.state.sesiones = sesiones
    return app


def servir(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Levanta el servidor (usado por `enterprise-agents serve`)."""
    import uvicorn

    uvicorn.run(crear_app(), host=host, port=port)
