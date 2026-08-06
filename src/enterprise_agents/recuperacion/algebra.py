"""Álgebra lineal mínima para la descomposición SVD, sobre listas de Python.

No se usa numpy a propósito: el núcleo del proyecto tiene una sola dependencia de
runtime y el corpus es chico (cientos de fragmentos), así que el costo de estas
operaciones se mide en decenas de milisegundos. Todo lo que hay acá es lo
estrictamente necesario para la SVD aleatorizada de `vectorial.py`.

Convenciones:
- Una matriz densa es `list[list[float]]`, indexada `[fila][columna]`.
- Una matriz dispersa es `list[dict[int, float]]`: una fila por documento, con
  el índice de columna como clave. Es el formato natural de una matriz TF-IDF,
  donde cada fila tiene ~100 términos de un vocabulario de varios miles.
"""

from __future__ import annotations

import math
import random

Denso = list[list[float]]
Disperso = list[dict[int, float]]


def matriz_aleatoria(filas: int, columnas: int, semilla: int) -> Denso:
    """Matriz gaussiana reproducible: la semilla hace determinística a la SVD."""
    rng = random.Random(semilla)
    return [[rng.gauss(0.0, 1.0) for _ in range(columnas)] for _ in range(filas)]


def disperso_por_denso(a: Disperso, b: Denso, columnas_b: int) -> Denso:
    """A · B con A dispersa (m×n) y B densa (n×l). Devuelve m×l."""
    resultado = [[0.0] * columnas_b for _ in range(len(a))]
    for i, fila in enumerate(a):
        destino = resultado[i]
        for j, valor in fila.items():
            fila_b = b[j]
            for p in range(columnas_b):
                destino[p] += valor * fila_b[p]
    return resultado


def transpuesta_densa_por_dispersa(q: Denso, a: Disperso, columnas: int) -> Denso:
    """Qᵀ · A con Q densa (m×l) y A dispersa (m×n). Devuelve l×n."""
    filas_q = len(q[0]) if q else 0
    resultado = [[0.0] * columnas for _ in range(filas_q)]
    for i, fila in enumerate(a):
        fila_q = q[i]
        for j, valor in fila.items():
            for p in range(filas_q):
                resultado[p][j] += fila_q[p] * valor
    return resultado


def por_transpuesta(a: Denso) -> Denso:
    """A · Aᵀ. Se aprovecha la simetría: se calcula media matriz y se refleja."""
    n = len(a)
    resultado = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            total = sum(x * y for x, y in zip(a[i], a[j], strict=True))
            resultado[i][j] = resultado[j][i] = total
    return resultado


def ortonormalizar(a: Denso) -> Denso:
    """Base ortonormal de las columnas de A (Gram-Schmidt modificado).

    Se usa la variante modificada —restar cada proyección apenas se calcula, en
    vez de todas al final— porque la clásica pierde ortogonalidad por error de
    redondeo justo cuando las columnas están correlacionadas, que es el caso
    habitual al proyectar una matriz TF-IDF.
    """
    if not a:
        return []
    filas, columnas = len(a), len(a[0])
    base = [[a[i][j] for i in range(filas)] for j in range(columnas)]  # columnas como vectores
    ortogonales: list[list[float]] = []

    for vector in base:
        for previo in ortogonales:
            proyeccion = sum(x * y for x, y in zip(vector, previo, strict=True))
            for i in range(filas):
                vector[i] -= proyeccion * previo[i]
        norma = math.sqrt(sum(x * x for x in vector))
        # Una columna que colapsa a cero es linealmente dependiente: se descarta.
        if norma > 1e-10:
            ortogonales.append([x / norma for x in vector])

    return [[col[i] for col in ortogonales] for i in range(filas)]


def eigen_simetrica(
    matriz: Denso, iteraciones: int = 60, tolerancia: float = 1e-9
) -> tuple[list[float], Denso]:
    """Autovalores y autovectores de una matriz simétrica (Jacobi cíclico).

    Devuelve `(autovalores, autovectores)` ordenados de mayor a menor, con los
    autovectores **por columna**. Jacobi es más lento que los métodos de la
    literatura numérica, pero es corto, estable y acá opera sobre una matriz de
    unas decenas de filas: el costo es despreciable.
    """
    n = len(matriz)
    a = [fila[:] for fila in matriz]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    for _ in range(iteraciones):
        # Mayor elemento fuera de la diagonal: es el que se anula en esta pasada.
        mayor, p, q = 0.0, 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                if abs(a[i][j]) > mayor:
                    mayor, p, q = abs(a[i][j]), i, j
        if mayor < tolerancia or n < 2:
            break

        # Ángulo de la rotación que anula a[p][q].
        if a[p][p] == a[q][q]:
            theta = math.pi / 4
        else:
            theta = 0.5 * math.atan2(2 * a[p][q], a[p][p] - a[q][q])
        c, s = math.cos(theta), math.sin(theta)

        for k in range(n):
            akp, akq = a[k][p], a[k][q]
            a[k][p] = c * akp + s * akq
            a[k][q] = -s * akp + c * akq
        for k in range(n):
            apk, aqk = a[p][k], a[q][k]
            a[p][k] = c * apk + s * aqk
            a[q][k] = -s * apk + c * aqk
        for k in range(n):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p] = c * vkp + s * vkq
            v[k][q] = -s * vkp + c * vkq

    autovalores = [a[i][i] for i in range(n)]
    orden = sorted(range(n), key=lambda i: -autovalores[i])
    return (
        [autovalores[i] for i in orden],
        [[v[fila][i] for i in orden] for fila in range(n)],
    )


def normalizar_vector(vector: list[float]) -> list[float]:
    """Vector unitario; el vector nulo se devuelve tal cual."""
    norma = math.sqrt(sum(x * x for x in vector))
    return [x / norma for x in vector] if norma > 1e-12 else vector


def coseno(a: list[float], b: list[float]) -> float:
    """Similitud coseno. Asume vectores ya normalizados (producto interno)."""
    return sum(x * y for x, y in zip(a, b, strict=True))
