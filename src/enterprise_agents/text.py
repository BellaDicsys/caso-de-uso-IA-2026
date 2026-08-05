"""Utilidades de texto compartidas.

`normalizar` unifica el plegado de acentos/mayúsculas usado por el mock, las
herramientas y el set de evaluación (antes estaba duplicado en 4 módulos).
`coincide_palabra` compara por palabra completa para evitar falsos positivos
por subcadena (p. ej. "debe" dentro de "debemos").
"""

from __future__ import annotations

import re
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas sin tildes ni signos combinantes (NFKD)."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def tokenizar(texto: str) -> list[str]:
    """Palabras normalizadas de un texto (para matching por palabra completa)."""
    return re.findall(r"\w+", normalizar(texto))


def coincide_palabra(clave: str, texto_norm: str) -> bool:
    """True si `clave` aparece como palabra completa dentro de `texto_norm`.

    Uso: comparar habilidades ('SQL' no debe matchear 'PostgreSQL').
    `clave` puede ser multi-palabra (p. ej. "power bi").
    """
    return re.search(r"\b" + re.escape(clave) + r"\b", texto_norm) is not None


def coincide_prefijo(clave: str, texto_norm: str) -> bool:
    """True si alguna palabra de `texto_norm` empieza con `clave`.

    Uso: keywords de ruteo, donde una raíz debe cubrir sus derivados
    ('factur' → 'facturamos', 'facturación'), pero sin matchear en medio de
    otra palabra ('sql' no matchea 'postgresql').
    """
    return re.search(r"\b" + re.escape(clave), texto_norm) is not None
