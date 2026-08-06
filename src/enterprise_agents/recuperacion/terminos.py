"""Preprocesamiento léxico en español para la recuperación.

Sin este paso el motor puntúa por palabras que no significan nada: la consulta
"¿qué dice la política de vacaciones?" recupera "Guía de Revisión de Código › Qué
se revisa" porque comparten *qué*, *se* y *de*. Dos operaciones lo resuelven:

1. **Vocabulario vacío** — se descartan artículos, preposiciones, pronombres,
   interrogativos y verbos auxiliares, que aparecen en todos los documentos y por
   lo tanto no discriminan ninguno.
*Deber* quedó deliberadamente fuera del vocabulario vacío aunque parezca un
auxiliar: en este dominio "¿cuánto nos **debe** ese cliente?" es contenido, no
soporte. La ambigüedad la resuelve el contexto —qué otras palabras trae la
consulta—, no descartar el término.

2. **Reducción de la palabra a su raíz** — un recortador de sufijos conservador
   para el español, que hace que *vacaciones* y *vacación*, o *licencias* y
   *licencia*, sean el mismo término. Es deliberadamente tímido: prefiere no
   recortar antes que fusionar dos palabras de significado distinto, porque un
   recorte agresivo confunde *contratación* con *contrato*.

No se usa un lematizador con diccionario: sería una dependencia externa y un
diccionario del español pesa más que todo este repositorio.
"""

from __future__ import annotations

from enterprise_agents.text import tokenizar

# Palabras vacías del español, ampliadas con los interrogativos y las formas
# verbales de soporte que abundan en consultas en lenguaje natural.
VACIAS = frozenset(
    [
        "a",
        "al",
        "algo",
        "algun",
        "alguna",
        "algunas",
        "alguno",
        "algunos",
        "ante",
        "antes",
        "aquel",
        "aquella",
        "aquellas",
        "aquello",
        "aquellos",
        "aqui",
        "asi",
        "aun",
        "aunque",
        "cada",
        "como",
        "con",
        "contra",
        "cual",
        "cuales",
        "cuando",
        "cuanta",
        "cuantas",
        "cuanto",
        "cuantos",
        "cuyo",
        "de",
        "del",
        "desde",
        "donde",
        "dos",
        "e",
        "el",
        "ella",
        "ellas",
        "ello",
        "ellos",
        "en",
        "entre",
        "era",
        "eran",
        "es",
        "esa",
        "esas",
        "ese",
        "eso",
        "esos",
        "esta",
        "estan",
        "estas",
        "este",
        "esto",
        "estos",
        "estoy",
        "fue",
        "fueron",
        "ha",
        "habia",
        "han",
        "hasta",
        "hay",
        "la",
        "las",
        "le",
        "les",
        "lo",
        "los",
        "mas",
        "me",
        "mi",
        "mientras",
        "mis",
        "misma",
        "mismo",
        "mucha",
        "mucho",
        "muy",
        "nada",
        "ni",
        "no",
        "nos",
        "nosotros",
        "o",
        "os",
        "otra",
        "otras",
        "otro",
        "otros",
        "para",
        "pero",
        "poco",
        "por",
        "porque",
        "pues",
        "que",
        "quien",
        "quienes",
        "se",
        "sea",
        "sean",
        "segun",
        "ser",
        "si",
        "sido",
        "siempre",
        "sin",
        "sobre",
        "solo",
        "son",
        "su",
        "sus",
        "tal",
        "tambien",
        "tan",
        "tanto",
        "te",
        "tiene",
        "tienen",
        "todo",
        "todos",
        "tu",
        "tus",
        "un",
        "una",
        "unas",
        "uno",
        "unos",
        "vos",
        "y",
        "ya",
        "dice",
        "decir",
        "dar",
        "da",
        "dan",
        "hacer",
        "hace",
        "hacen",
        "puede",
        "pueden",
        "tener",
        "puedo",
        "quiero",
        "necesito",
        "tengo",
        "debo",
        "hago",
        "voy",
        "soy",
        "estoy",
        "me",
        "mis",
        "conmigo",
    ]
)

# Sufijos ordenados de más largo a más corto: se recorta el primero que aplique.
# Solo formas nominales y adjetivas frecuentes; no se tocan las conjugaciones,
# donde el riesgo de fusionar significados distintos es mucho mayor.
_SUFIJOS = (
    "amientos",
    "imientos",
    "amiento",
    "imiento",
    "aciones",
    "uciones",
    "iciones",
    "acion",
    "ucion",
    "icion",
    "ancia",
    "encia",
    "idades",
    "idad",
    "anzas",
    "anza",
    "ismos",
    "ismo",
    "ables",
    "ibles",
    "able",
    "ible",
    "eses",
    "es",
    "s",
)

# Longitud mínima de la raíz resultante: por debajo de esto el recorte destruye
# la palabra ("mes" → "m") y genera colisiones absurdas.
_MINIMO_RAIZ = 4


def raiz(palabra: str) -> str:
    """Recorta el sufijo más largo aplicable, si queda una raíz utilizable."""
    for sufijo in _SUFIJOS:
        if palabra.endswith(sufijo) and len(palabra) - len(sufijo) >= _MINIMO_RAIZ:
            return palabra[: -len(sufijo)]
    return palabra


def terminos(texto: str) -> list[str]:
    """Tokeniza, descarta vocabulario vacío y reduce cada palabra a su raíz.

    Los números se conservan tal cual: en este corpus son datos (montos, plazos,
    porcentajes), no ruido.
    """
    salida = []
    for token in tokenizar(texto):
        if token in VACIAS or len(token) < 2:
            continue
        salida.append(token if token.isdigit() else raiz(token))
    return salida
