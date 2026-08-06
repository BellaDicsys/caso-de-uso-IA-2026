"""Recuperación léxica: BM25 Okapi implementado sobre la biblioteca estándar.

BM25 es el criterio léxico de referencia y sigue siendo difícil de superar en
consultas con términos precisos —códigos, nombres propios, acrónimos— donde los
métodos semánticos suelen diluir la señal. Por eso el motor lo conserva como una
de las dos ramas de la búsqueda híbrida en lugar de reemplazarlo.

Fórmula: para cada término *t* de la consulta,

    IDF(t) · (f(t,d) · (k1+1)) / (f(t,d) + k1 · (1 - b + b · |d| / media(|d|)))

con el IDF de Robertson corregido para no dar negativo en términos muy
frecuentes.
"""

from __future__ import annotations

import math
from collections import Counter

# Valores clásicos: k1 controla la saturación por frecuencia, b la penalización
# por longitud del documento.
K1 = 1.5
B = 0.75


class IndiceBM25:
    """Índice invertido con puntuación BM25."""

    def __init__(self, documentos: list[list[str]]) -> None:
        self.n = len(documentos)
        self.longitudes = [len(d) for d in documentos]
        self.longitud_media = (sum(self.longitudes) / self.n) if self.n else 0.0

        # Índice invertido: término → {documento: frecuencia}
        self.postings: dict[str, dict[int, int]] = {}
        for i, tokens in enumerate(documentos):
            for termino, frecuencia in Counter(tokens).items():
                self.postings.setdefault(termino, {})[i] = frecuencia

        # IDF precalculado por término (no depende de la consulta).
        self.idf: dict[str, float] = {}
        for termino, docs in self.postings.items():
            df = len(docs)
            # Robertson: log(1 + (N - df + 0.5)/(df + 0.5)); el +1 evita negativos.
            self.idf[termino] = math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def puntuar(self, consulta: list[str]) -> dict[int, float]:
        """Puntaje BM25 por documento, solo para los que contienen algún término."""
        puntajes: dict[int, float] = {}
        for termino in consulta:
            docs = self.postings.get(termino)
            if not docs:
                continue
            idf = self.idf[termino]
            for doc, frecuencia in docs.items():
                norma = 1 - B + B * (self.longitudes[doc] / self.longitud_media)
                incremento = idf * (frecuencia * (K1 + 1)) / (frecuencia + K1 * norma)
                puntajes[doc] = puntajes.get(doc, 0.0) + incremento
        return puntajes

    def buscar(self, consulta: list[str], k: int = 10) -> list[tuple[int, float]]:
        """Los `k` documentos con mayor puntaje, de mayor a menor."""
        puntajes = self.puntuar(consulta)
        ordenados = sorted(puntajes.items(), key=lambda par: (-par[1], par[0]))
        return ordenados[:k]
