"""Estimación de tokens sin llamar a ningún servicio.

Para poder decir cuánto cuesta una consulta hay que contar tokens, y el conteo
exacto lo define el tokenizador del proveedor: no se puede reproducir sin su
vocabulario, que es un archivo grande y externo. La API de Anthropic ofrece
`count_tokens`, pero es una llamada de red y este repositorio tiene que poder
medirse sin credenciales.

Se usa entonces un **estimador declarado como tal**. La regla es la relación
empírica entre caracteres y tokens del español y el inglés en modelos con
vocabulario BPE, ajustada por dos observaciones:

- Las palabras largas y con tildes se parten en más piezas de las que sugiere su
  longitud, y el español tiene muchas.
- Los números, la puntuación y los símbolos casi siempre son tokens propios.

No pretende exactitud: pretende ser **estable y del orden correcto**, que es lo
que hace falta para comparar consultas entre sí, detectar una que se fue de
escala y estimar el costo antes de gastarlo. Las mediciones se etiquetan como
estimadas en toda la interfaz, para que nadie las confunda con facturación.
"""

from __future__ import annotations

import math
import re

# Caracteres por token para texto corriente. El valor típico que se reporta para
# el inglés es ~4; el español rinde algo menos por la longitud media de palabra
# y por los diacríticos, que suelen costar una pieza extra.
CARACTERES_POR_TOKEN = 3.6

_NUMEROS = re.compile(r"\d+(?:[.,]\d+)*")
_SIMBOLOS = re.compile(r"[^\w\s]")


def estimar(texto: str) -> int:
    """Tokens estimados de un texto. Siempre ≥ 1 para texto no vacío."""
    if not texto:
        return 0
    # Los símbolos y los números se cuentan aparte porque su relación con la
    # longitud es distinta: "1.234.567" son varios tokens pese a ser corto.
    simbolos = len(_SIMBOLOS.findall(texto))
    numeros = sum(math.ceil(len(n) / 3) for n in _NUMEROS.findall(texto))
    resto = _SIMBOLOS.sub("", _NUMEROS.sub("", texto))
    return max(1, int(len(resto) / CARACTERES_POR_TOKEN) + simbolos + numeros)


def estimar_mensajes(mensajes: list[dict]) -> int:
    """Tokens estimados de una conversación en formato Messages API."""
    total = 0
    for mensaje in mensajes:
        contenido = mensaje.get("content")
        if isinstance(contenido, str):
            total += estimar(contenido)
        elif isinstance(contenido, list):
            for bloque in contenido:
                if not isinstance(bloque, dict):
                    continue
                for clave in ("text", "content"):
                    valor = bloque.get(clave)
                    if isinstance(valor, str):
                        total += estimar(valor)
                if bloque.get("type") == "tool_use":
                    total += estimar(str(bloque.get("input", "")))
    return total


def formatear(tokens: int) -> str:
    """Cantidad legible: 1.2k en lugar de 1234."""
    if tokens < 1000:
        return str(tokens)
    return f"{tokens / 1000:.1f}k"
