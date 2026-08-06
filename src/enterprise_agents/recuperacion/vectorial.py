"""Embeddings semánticos derivados del propio corpus (análisis semántico latente).

La decisión de fondo: **no se descargan pesos preentrenados**. Un modelo de
embeddings, por chico que sea, rompe la propiedad más valiosa del repositorio
—clonar y correr, sin red— y vuelve no determinístico lo que hoy se puede
testear. En su lugar se construyen los vectores desde el corpus:

1. Matriz TF-IDF dispersa de fragmentos × términos.
2. Descomposición SVD truncada de rango `k` por el método aleatorizado de
   Halko-Martinsson-Tropp: proyección aleatoria, ortonormalización, y SVD exacta
   de la matriz chica resultante.
3. La matriz `V` (términos × k) es la proyección al espacio latente. Tanto los
   fragmentos como las consultas se codifican con la misma operación: `x · V`.

Eso da similitud semántica real: dos términos que aparecen en contextos
parecidos —"licencia" y "permiso", "resguardo" y "respaldo"— quedan cerca en el
espacio latente aunque nunca coincidan literalmente, porque la SVD captura la
estructura de co-ocurrencia del corpus.

El contrato `Embedder` deja la puerta abierta: una implementación que envuelva un
modelo local se enchufa sin tocar el motor, igual que `MockLLMClient` y
`AnthropicLLMClient` comparten `LLMClient`.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Protocol, runtime_checkable

from enterprise_agents.recuperacion import algebra
from enterprise_agents.recuperacion.terminos import terminos

# Dimensión del espacio latente. Con un corpus de cientos de fragmentos, más allá
# de ~96 los valores singulares aportan ruido en lugar de señal.
DIMENSION = 96
# Muestras extra de la proyección aleatoria: mejoran la aproximación del subespacio
# dominante a un costo despreciable (recomendación estándar: 5-10).
SOBREMUESTREO = 10
SEMILLA = 20260806


def _trigramas(palabra: str) -> set[str]:
    """Trigramas de caracteres con marcas de borde, para comparar formas emparentadas."""
    acolchado = f"<{palabra}>"
    return {acolchado[i : i + 3] for i in range(len(acolchado) - 2)}


@runtime_checkable
class Embedder(Protocol):
    """Contrato de codificación a vectores densos.

    Implementarlo con un modelo local (o con un servicio remoto) no requiere
    ningún cambio en el motor de recuperación.
    """

    @property
    def dimension(self) -> int: ...

    def codificar(self, texto: str) -> list[float]: ...


class Vocabulario:
    """Términos del corpus con su frecuencia documental."""

    def __init__(self, documentos: list[list[str]], minimo_df: int = 1) -> None:
        conteo: Counter[str] = Counter()
        for tokens in documentos:
            conteo.update(set(tokens))
        # Los términos que aparecen en un solo fragmento no aportan estructura
        # latente y engordan el vocabulario; se conservan si el corpus es chico.
        self.indices: dict[str, int] = {
            termino: i
            for i, termino in enumerate(sorted(t for t, df in conteo.items() if df >= minimo_df))
        }
        self.df = {t: conteo[t] for t in self.indices}
        self.n_documentos = len(documentos)

        # Índice de trigramas de caracteres, para resolver términos que la
        # consulta trae y el corpus no tiene exactamente.
        self._trigramas: dict[str, set[str]] = {}
        for termino in self.indices:
            for trigrama in _trigramas(termino):
                self._trigramas.setdefault(trigrama, set()).add(termino)

    def __len__(self) -> int:
        return len(self.indices)

    def mas_cercano(self, termino: str, umbral: float = 0.45) -> str | None:
        """Término del vocabulario más parecido a uno desconocido, o None.

        Compara por trigramas de caracteres (Jaccard). Resuelve el problema
        clásico del espacio latente: la consulta dice "respalda", el corpus dice
        "respaldo", y como el recortador de sufijos no toca conjugaciones el
        término queda fuera de vocabulario y aporta cero. Con este retroceso
        aporta lo que aportaría su forma emparentada.

        El umbral es alto a propósito: es preferible ignorar un término a
        sustituirlo por otro de significado distinto.
        """
        consulta = _trigramas(termino)
        if not consulta:
            return None
        candidatos: Counter[str] = Counter()
        for trigrama in consulta:
            candidatos.update(self._trigramas.get(trigrama, ()))

        mejor, mejor_puntaje = None, 0.0
        for candidato, comunes in candidatos.items():
            union = len(consulta) + len(_trigramas(candidato)) - comunes
            puntaje = comunes / union if union else 0.0
            # El desempate por orden alfabético mantiene el resultado determinístico.
            if puntaje > mejor_puntaje or (
                puntaje == mejor_puntaje and mejor and candidato < mejor
            ):
                mejor, mejor_puntaje = candidato, puntaje
        return mejor if mejor_puntaje >= umbral else None

    def idf(self, termino: str) -> float:
        """IDF suavizado; un término desconocido pesa 0."""
        df = self.df.get(termino)
        if df is None:
            return 0.0
        return math.log((1 + self.n_documentos) / (1 + df)) + 1.0

    def vector_tfidf(
        self, tokens: list[str], resolver_desconocidos: bool = False
    ) -> dict[int, float]:
        """Vector TF-IDF disperso y normalizado (L2) de una lista de tokens.

        Con `resolver_desconocidos` (solo para consultas), los términos fuera de
        vocabulario se sustituyen por su forma emparentada más cercana.
        """
        if not tokens:
            return {}
        frecuencias = Counter(tokens)
        vector: dict[int, float] = {}
        for termino, tf in frecuencias.items():
            indice = self.indices.get(termino)
            if indice is None and resolver_desconocidos:
                vecino = self.mas_cercano(termino)
                indice = self.indices.get(vecino) if vecino else None
            if indice is None:
                continue
            # TF sublineal: la décima aparición de un término no vale como la primera.
            vector[indice] = (1 + math.log(tf)) * self.idf(termino)
        norma = math.sqrt(sum(v * v for v in vector.values()))
        return {i: v / norma for i, v in vector.items()} if norma else {}


def svd_aleatorizada(
    matriz: algebra.Disperso, columnas: int, rango: int, semilla: int = SEMILLA
) -> tuple[algebra.Denso, list[float]]:
    """SVD truncada A ≈ U Σ Vᵀ. Devuelve `(V, valores_singulares)`.

    `V` tiene forma (columnas × rango) y es la matriz de proyección: cualquier
    vector del espacio de términos se lleva al espacio latente multiplicándolo
    por ella.
    """
    filas = len(matriz)
    if filas == 0 or columnas == 0:
        return [], []
    objetivo = min(rango + SOBREMUESTREO, filas, columnas)

    # 1. Proyección aleatoria: Y = A·Ω captura el subespacio dominante de A.
    omega = algebra.matriz_aleatoria(columnas, objetivo, semilla)
    y = algebra.disperso_por_denso(matriz, omega, objetivo)

    # 2. Base ortonormal del rango de Y.
    q = algebra.ortonormalizar(y)
    if not q or not q[0]:
        return [], []
    efectivo = len(q[0])

    # 3. Proyección de A a la base: B = Qᵀ·A, de dimensión chica (efectivo × columnas).
    b = algebra.transpuesta_densa_por_dispersa(q, matriz, columnas)

    # 4. SVD exacta de B vía la eigendescomposición de B·Bᵀ (simétrica y chica).
    autovalores, autovectores = algebra.eigen_simetrica(algebra.por_transpuesta(b))

    rango_final = min(rango, efectivo)
    singulares = [math.sqrt(max(v, 0.0)) for v in autovalores[:rango_final]]

    # 5. V = Bᵀ·W·Σ⁻¹, con W los autovectores de B·Bᵀ.
    v = [[0.0] * rango_final for _ in range(columnas)]
    for p in range(rango_final):
        sigma = singulares[p]
        if sigma <= 1e-9:
            continue
        columna_w = [autovectores[i][p] for i in range(efectivo)]
        for j in range(columnas):
            total = sum(b[i][j] * columna_w[i] for i in range(efectivo))
            v[j][p] = total / sigma

    return v, singulares


class IndiceSemantico:
    """Espacio latente construido sobre el corpus, con los fragmentos ya proyectados."""

    def __init__(self, documentos: list[list[str]], dimension: int = DIMENSION) -> None:
        self.vocabulario = Vocabulario(documentos)
        matriz = [self.vocabulario.vector_tfidf(tokens) for tokens in documentos]
        # Norma de Frobenius al cuadrado: la "energía" total de la matriz, contra
        # la que se compara la que retienen los valores singulares conservados.
        self._energia_total = sum(v * v for fila in matriz for v in fila.values())
        self.proyeccion, self.valores_singulares = svd_aleatorizada(
            matriz, len(self.vocabulario), dimension
        )
        self._dimension = len(self.valores_singulares)
        self.vectores = [self._proyectar(fila) for fila in matriz]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def energia_explicada(self) -> float:
        """Proporción de la energía del corpus que retiene el espacio latente.

        Diagnóstico de cuánto se pierde al truncar: si es muy baja, la dimensión
        elegida se está quedando corta para este corpus.
        """
        if self._energia_total <= 0:
            return 0.0
        retenida = sum(v * v for v in self.valores_singulares)
        return min(1.0, retenida / self._energia_total)

    def _proyectar(self, disperso: dict[int, float]) -> list[float]:
        """Lleva un vector TF-IDF disperso al espacio latente y lo normaliza."""
        if not self.proyeccion or self._dimension == 0:
            return []
        acumulado = [0.0] * self._dimension
        for indice, valor in disperso.items():
            fila = self.proyeccion[indice]
            for p in range(self._dimension):
                acumulado[p] += valor * fila[p]
        return algebra.normalizar_vector(acumulado)

    def codificar_terminos(self, tokens: list[str]) -> list[float]:
        """Codifica una lista de términos ya preprocesados."""
        return self._proyectar(self.vocabulario.vector_tfidf(tokens))

    def codificar(self, texto: str) -> list[float]:
        """Codifica texto libre en el mismo espacio que los fragmentos (contrato `Embedder`)."""
        return self._proyectar(
            self.vocabulario.vector_tfidf(terminos(texto), resolver_desconocidos=True)
        )

    def buscar_terminos(self, tokens: list[str], k: int = 10) -> list[tuple[int, float]]:
        """Los `k` fragmentos más similares a unos términos ya expandidos."""
        return self._ordenar(self.codificar_terminos(tokens), k)

    def buscar(self, texto: str, k: int = 10) -> list[tuple[int, float]]:
        """Los `k` fragmentos más similares por coseno, de mayor a menor."""
        return self._ordenar(self.codificar(texto), k)

    def _ordenar(self, consulta: list[float], k: int) -> list[tuple[int, float]]:
        if not consulta:
            return []
        puntajes = [(i, algebra.coseno(consulta, v)) for i, v in enumerate(self.vectores)]
        puntajes.sort(key=lambda par: (-par[1], par[0]))
        return puntajes[:k]
