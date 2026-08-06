"""Fragmentación del corpus documental en unidades recuperables.

Un documento entero es mala unidad de recuperación: la política de vacaciones
habla de días, de licencias especiales y de contacto, y una consulta solo apunta
a una de esas partes. Se fragmenta respetando la estructura del markdown —cada
sección `##` es una unidad de sentido— y se parte por ventana deslizante cuando
una sección es demasiado larga.

Cada fragmento conserva su *migaja*: el título del documento y el de la sección.
Sin eso, un fragmento que dice "el tope es de 90.000 por día" no es interpretable
ni recuperable, porque el término "viáticos" solo aparece en el encabezado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from enterprise_agents.recuperacion.terminos import terminos

# Tamaños en palabras. Una sección típica de estos documentos entra entera;
# el corte solo actúa en las secciones largas.
OBJETIVO_PALABRAS = 180
SOLAPAMIENTO_PALABRAS = 40

_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class Fragmento:
    """Unidad mínima de recuperación."""

    id: str
    documento: str
    titulo_documento: str
    seccion: str
    texto: str
    orden: int

    @property
    def migaja(self) -> str:
        """Contexto jerárquico legible: documento › sección."""
        return (
            f"{self.titulo_documento} › {self.seccion}" if self.seccion else self.titulo_documento
        )

    def texto_indexable(self) -> str:
        """Texto que se indexa: incluye la migaja para no perder el contexto."""
        return f"{self.migaja}\n{self.texto}"

    def tokens(self) -> list[str]:
        """Términos indexables: sin vocabulario vacío y reducidos a su raíz."""
        return terminos(self.texto_indexable())


def _ventanas(palabras: list[str]) -> list[list[str]]:
    """Parte una lista de palabras en ventanas solapadas."""
    if len(palabras) <= OBJETIVO_PALABRAS:
        return [palabras]
    paso = OBJETIVO_PALABRAS - SOLAPAMIENTO_PALABRAS
    ventanas = []
    inicio = 0
    while inicio < len(palabras):
        ventanas.append(palabras[inicio : inicio + OBJETIVO_PALABRAS])
        if inicio + OBJETIVO_PALABRAS >= len(palabras):
            break
        inicio += paso
    return ventanas


def _secciones(texto: str) -> list[tuple[str, str]]:
    """Divide un markdown en (título de sección, cuerpo), respetando encabezados."""
    lineas = texto.splitlines()
    secciones: list[tuple[str, list[str]]] = []
    actual_titulo = ""
    actual_cuerpo: list[str] = []

    for linea in lineas:
        encabezado = _ENCABEZADO.match(linea)
        # El `#` de nivel 1 es el título del documento, no una sección.
        if encabezado and len(encabezado.group(1)) >= 2:
            if actual_cuerpo:
                secciones.append((actual_titulo, actual_cuerpo))
            actual_titulo = encabezado.group(2).strip()
            actual_cuerpo = []
        elif not (encabezado and len(encabezado.group(1)) == 1):
            actual_cuerpo.append(linea)

    if actual_cuerpo:
        secciones.append((actual_titulo, actual_cuerpo))

    return [(t, "\n".join(c).strip()) for t, c in secciones if "\n".join(c).strip()]


def titulo_de(texto: str) -> str:
    """Primer encabezado de nivel 1, o la primera línea no vacía."""
    for linea in texto.splitlines():
        encabezado = _ENCABEZADO.match(linea)
        if encabezado and len(encabezado.group(1)) == 1:
            return encabezado.group(2).strip()
        if linea.strip():
            return linea.strip()
    return ""


def fragmentar_documento(nombre: str, texto: str) -> list[Fragmento]:
    """Fragmenta un documento markdown en unidades recuperables."""
    titulo = titulo_de(texto)
    fragmentos: list[Fragmento] = []
    for seccion, cuerpo in _secciones(texto):
        for ventana in _ventanas(cuerpo.split()):
            orden = len(fragmentos)
            fragmentos.append(
                Fragmento(
                    id=f"{nombre}#{orden}",
                    documento=nombre,
                    titulo_documento=titulo,
                    seccion=seccion,
                    texto=" ".join(ventana),
                    orden=orden,
                )
            )
    return fragmentos


def fragmentar_corpus(directorio: Path) -> list[Fragmento]:
    """Fragmenta todos los markdown de un directorio, en orden estable."""
    fragmentos: list[Fragmento] = []
    for path in sorted(directorio.glob("*.md")):
        fragmentos.extend(fragmentar_documento(path.name, path.read_text(encoding="utf-8")))
    return fragmentos
