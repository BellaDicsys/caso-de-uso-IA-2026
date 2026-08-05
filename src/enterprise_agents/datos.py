"""Lectura centralizada de los CSV de `data/`.

Un único `leer_csv` reemplaza los cuatro lectores que estaban duplicados en
las herramientas y en metrics. Incluye una caché invalidada por fecha de
modificación (mtime): en la demo evita releer los mismos archivos en cada
llamada de herramienta y en cada refresco del tablero, y se invalida sola si
el archivo cambia en disco.
"""

from __future__ import annotations

from enterprise_agents.config import DATA_DIR

# Caché: nombre -> (mtime, filas). Se invalida si cambia el mtime del archivo.
_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}


def leer_csv(nombre: str) -> list[dict[str, str]]:
    """Devuelve las filas de `data/<nombre>` como lista de dicts (con caché)."""
    import csv

    path = DATA_DIR / nombre
    mtime = path.stat().st_mtime
    cacheado = _cache.get(nombre)
    if cacheado is not None and cacheado[0] == mtime:
        return cacheado[1]

    with path.open(newline="", encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    _cache[nombre] = (mtime, filas)
    return filas
