"""Configuración central de la suite.

Toda la configuración proviene de variables de entorno para que el
comportamiento sea reproducible y no haya secretos en el código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Raíz del repositorio (dos niveles arriba de este archivo: src/enterprise_agents/)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = DATA_DIR / "documentos"

DEFAULT_MODEL = "claude-opus-5"


@dataclass(frozen=True)
class Settings:
    """Parámetros de ejecución de la suite."""

    model: str = field(default_factory=lambda: os.getenv("ENTERPRISE_AGENTS_MODEL", DEFAULT_MODEL))
    max_iterations: int = field(
        default_factory=lambda: int(os.getenv("ENTERPRISE_AGENTS_MAX_ITERATIONS", "8"))
    )
    api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None)

    @property
    def has_api_key(self) -> bool:
        return self.api_key is not None


def load_settings() -> Settings:
    return Settings()
