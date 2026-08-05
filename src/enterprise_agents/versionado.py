"""Versionado automático a partir de Conventional Commits.

El repositorio no lleva la versión a mano: se deriva de los mensajes de commit
desde el último tag publicado, siguiendo *semantic versioning*.

    fix: / perf: / refactor: ...   → parche   (0.3.0 → 0.3.1)
    feat: ...                      → menor    (0.3.0 → 0.4.0)
    feat!: ... o BREAKING CHANGE:  → mayor    (0.3.0 → 1.0.0)

Mientras la versión mayor sea 0 (API todavía inestable), un cambio de ruptura
sube la **menor** en lugar de la mayor, como recomienda semver 2.0.0 §4.

Todo el análisis vive en funciones puras y testeables (`analizar`,
`siguiente_version`, `notas_de_version`, `actualizar_changelog`); las únicas
funciones que tocan el entorno son las que consultan git y las que escriben los
archivos, y se apoyan en las anteriores.

Uso:
    enterprise-agents version              # versión actual
    enterprise-agents version --proximo    # versión que correspondería publicar
    enterprise-agents version --notas      # notas de esa versión
    enterprise-agents version --aplicar    # escribe __init__.py y CHANGELOG.md
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO_VERSION = Path(__file__).resolve().parent / "__init__.py"
ARCHIVO_CHANGELOG = RAIZ / "CHANGELOG.md"

# Tipo de commit → salto de versión que provoca. Los tipos que no figuran
# (docs, test, build, ci, chore, style) no publican versión por sí solos.
SALTOS: dict[str, str] = {
    "feat": "minor",
    "fix": "patch",
    "perf": "patch",
    "refactor": "patch",
    "revert": "patch",
}

# Orden y título de las secciones del changelog.
SECCIONES: tuple[tuple[str, str], ...] = (
    ("ruptura", "⚠ Cambios de ruptura"),
    ("feat", "Nuevas funcionalidades"),
    ("fix", "Correcciones"),
    ("perf", "Rendimiento"),
    ("refactor", "Refactors"),
    ("revert", "Reversiones"),
    ("docs", "Documentación"),
)

_PRIORIDAD = {"patch": 1, "minor": 2, "major": 3}
_CABECERA_COMMIT = re.compile(
    r"^(?P<tipo>[a-z]+)"  # tipo: feat, fix, docs...
    r"(?:\((?P<alcance>[^)]+)\))?"  # alcance opcional: (api), (tablero)...
    r"(?P<ruptura>!)?: "  # "!" marca cambio de ruptura
    r"(?P<descripcion>.+)$"
)
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

ENCABEZADO_CHANGELOG = """# Changelog

Todas las versiones publicadas de la Enterprise Agent Suite. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado es
[semántico](https://semver.org/lang/es/); las entradas se generan
automáticamente desde los *Conventional Commits* (ver
[docs/adr/0006-versionado-automatico.md](docs/adr/0006-versionado-automatico.md)).
"""


@dataclass(frozen=True)
class CommitConv:
    """Un commit que respeta la convención, ya parseado."""

    tipo: str
    alcance: str | None
    descripcion: str
    ruptura: bool

    def linea(self) -> str:
        if self.alcance:
            return f"- **{self.alcance}**: {self.descripcion}"
        return f"- {self.descripcion}"


# --- Análisis (puro) --------------------------------------------------------


def parsear_commit(mensaje: str) -> CommitConv | None:
    """Parsea un mensaje de commit completo; devuelve None si no sigue la convención."""
    lineas = mensaje.strip().splitlines()
    if not lineas:
        return None
    coincidencia = _CABECERA_COMMIT.match(lineas[0].strip())
    if coincidencia is None:
        return None
    cuerpo = "\n".join(lineas[1:])
    ruptura = bool(coincidencia.group("ruptura")) or "BREAKING CHANGE" in cuerpo
    return CommitConv(
        tipo=coincidencia.group("tipo"),
        alcance=coincidencia.group("alcance"),
        descripcion=coincidencia.group("descripcion").strip(),
        ruptura=ruptura,
    )


def salto_de_commit(commit: CommitConv) -> str | None:
    """Salto de versión que provoca un commit (None si no publica versión)."""
    if commit.ruptura:
        return "major"
    return SALTOS.get(commit.tipo)


def calcular_salto(commits: list[CommitConv]) -> str | None:
    """El mayor salto entre todos los commits; None si ninguno amerita publicar."""
    saltos = [s for s in (salto_de_commit(c) for c in commits) if s]
    return max(saltos, key=lambda s: _PRIORIDAD[s]) if saltos else None


def siguiente_version(actual: str, salto: str | None) -> str:
    """Aplica el salto sobre la versión actual (semver; en 0.x la ruptura sube la menor)."""
    coincidencia = _VERSION.match(actual)
    if coincidencia is None:
        raise ValueError(f"Versión no semántica: {actual!r}")
    mayor, menor, parche = (int(g) for g in coincidencia.groups())
    if salto is None:
        return actual
    if salto == "major":
        # Semver §4: mientras 0.x, un cambio de ruptura sube la menor.
        return f"0.{menor + 1}.0" if mayor == 0 else f"{mayor + 1}.0.0"
    if salto == "minor":
        return f"{mayor}.{menor + 1}.0"
    return f"{mayor}.{menor}.{parche + 1}"


def agrupar(commits: list[CommitConv]) -> dict[str, list[CommitConv]]:
    """Agrupa por sección del changelog, respetando el orden de `SECCIONES`."""
    grupos: dict[str, list[CommitConv]] = {}
    for commit in commits:
        clave = "ruptura" if commit.ruptura else commit.tipo
        if clave in dict(SECCIONES):
            grupos.setdefault(clave, []).append(commit)
    return grupos


def notas_de_version(version: str, commits: list[CommitConv], fecha: date) -> str:
    """Genera el bloque de changelog de una versión."""
    partes = [f"## {version} — {fecha.isoformat()}", ""]
    grupos = agrupar(commits)
    for clave, titulo in SECCIONES:
        if clave not in grupos:
            continue
        partes.append(f"### {titulo}")
        partes.append("")
        partes.extend(c.linea() for c in grupos[clave])
        partes.append("")
    if len(partes) == 2:
        partes.append("Sin cambios destacables.")
        partes.append("")
    return "\n".join(partes).rstrip() + "\n"


def actualizar_changelog(contenido: str, notas: str) -> str:
    """Inserta las notas arriba de todo, justo debajo del encabezado."""
    contenido = contenido.strip()
    if not contenido:
        return f"{ENCABEZADO_CHANGELOG}\n{notas}"
    marca = contenido.find("\n## ")
    if marca == -1:
        return f"{contenido}\n\n{notas}"
    return f"{contenido[:marca].rstrip()}\n\n{notas}\n{contenido[marca + 1 :].rstrip()}\n"


@dataclass(frozen=True)
class Publicacion:
    """Resultado del análisis: qué versión publicar y con qué notas."""

    actual: str
    version: str
    salto: str | None
    notas: str

    @property
    def hay_cambios(self) -> bool:
        return self.salto is not None


def analizar(mensajes: list[str], version_actual: str, hoy: date | None = None) -> Publicacion:
    """Núcleo puro: de mensajes de commit a la publicación que corresponde."""
    commits = [c for c in (parsear_commit(m) for m in mensajes) if c is not None]
    salto = calcular_salto(commits)
    version = siguiente_version(version_actual, salto)
    notas = notas_de_version(version, commits, hoy or date.today())
    return Publicacion(actual=version_actual, version=version, salto=salto, notas=notas)


# --- Integración con git y el repositorio -----------------------------------


def _git(*args: str, cwd: Path | None = None) -> str | None:
    """Ejecuta un comando git; None si falla (repo sin tags, sin git, etc.)."""
    try:
        salida = subprocess.run(
            ["git", *args],
            cwd=str(cwd or RAIZ),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - entorno sin git
        return None
    return salida.stdout.strip() if salida.returncode == 0 else None


def ultimo_tag(cwd: Path | None = None) -> str | None:
    """Último tag de versión alcanzable desde HEAD (None si todavía no hay ninguno)."""
    return _git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", cwd=cwd) or None


def commits_desde(tag: str | None, cwd: Path | None = None) -> list[str]:
    """Mensajes completos de los commits posteriores a `tag` (o de todo el historial)."""
    rango = f"{tag}..HEAD" if tag else "HEAD"
    salida = _git("log", rango, "--no-merges", "--format=%B%x00", cwd=cwd)
    if not salida:
        return []
    return [m.strip() for m in salida.split("\0") if m.strip()]


def leer_version(archivo: Path | None = None) -> str:
    """Lee la única fuente de verdad de la versión (`__version__`)."""
    texto = (archivo or ARCHIVO_VERSION).read_text(encoding="utf-8")
    coincidencia = re.search(r'^__version__ = "([^"]+)"$', texto, re.MULTILINE)
    if coincidencia is None:
        raise ValueError("No se encontró __version__ en el archivo de versión.")
    return coincidencia.group(1)


def escribir_version(version: str, archivo: Path | None = None) -> None:
    """Reescribe `__version__` conservando el resto del archivo."""
    destino = archivo or ARCHIVO_VERSION
    texto = destino.read_text(encoding="utf-8")
    nuevo = re.sub(
        r'^__version__ = "[^"]+"$', f'__version__ = "{version}"', texto, count=1, flags=re.MULTILINE
    )
    destino.write_text(nuevo, encoding="utf-8")


def analizar_repo(cwd: Path | None = None, hoy: date | None = None) -> Publicacion:
    """Analiza el repositorio real: commits desde el último tag vs versión actual."""
    tag = ultimo_tag(cwd)
    mensajes = commits_desde(tag, cwd)
    return analizar(mensajes, leer_version(), hoy)


def aplicar(
    publicacion: Publicacion,
    archivo_version: Path | None = None,
    archivo_changelog: Path | None = None,
) -> None:
    """Escribe la nueva versión y agrega su entrada al changelog."""
    escribir_version(publicacion.version, archivo_version)
    changelog = archivo_changelog or ARCHIVO_CHANGELOG
    actual = changelog.read_text(encoding="utf-8") if changelog.exists() else ""
    changelog.write_text(actualizar_changelog(actual, publicacion.notas), encoding="utf-8")
