"""Verificador de fundamentación: detecta cifras inventadas, sin modelo y sin red.

El riesgo específico de un sistema agéntico sobre datos de negocio no es que
razone mal: es que en el paso de **síntesis** —cuando el modelo redacta la
respuesta final a partir de lo que devolvieron las herramientas— aparezca un
número que ninguna herramienta informó. Un total mal sumado, un porcentaje
verosímil, una fecha corrida. Eso es indistinguible de un dato correcto para
quien lee, y es exactamente lo que un sistema de gestión no puede permitirse.

La formulación que hace verificable el problema: **toda afirmación cuantitativa
de la respuesta debe aparecer en la salida de alguna herramienta de esa misma
ejecución**. No se compara contra los datos crudos —el agente puede legítimamente
agregar, filtrar y ordenar— sino contra lo que efectivamente se leyó. Y las
delegaciones se excluyen de la evidencia (ver `trazas.Traza.evidencia`): tomar
como prueba el texto que redactó otro agente haría circular la verificación.

Es exacto, cuesta microsegundos y no necesita un modelo juez. La contrapartida es
que no evalúa si la respuesta es *pertinente*, solo si es *fundada*. Son dos
propiedades distintas y esta es la que se puede medir sin ambigüedad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from enterprise_agents.trazas import Traza

# Identificadores del dominio: facturas (FC-2026-0115), proyectos (P-2026-05).
# Se comparan como texto, no como número.
_IDENTIFICADOR = re.compile(r"\b[A-Z]{1,4}-\d{2,4}(?:-\d+)+\b")
# Fechas ISO, que también se comparan literalmente.
_FECHA = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Números con separadores de miles o decimales, en formato español o inglés.
_NUMERO = re.compile(r"\b\d[\d.,]*\b")

# Enteros chicos no son afirmaciones verificables: posiciones de una
# enumeración, "3 facturas", "2 clientes". Exigir que "3" figure en la evidencia
# genera ruido sin detectar ninguna invención real. Los números con decimales sí
# se verifican aunque sean chicos: "99,5 %" es una cifra, no una cantidad casual.
_MINIMO_VERIFICABLE = Decimal(100)


@dataclass(frozen=True)
class Afirmacion:
    """Un dato cuantitativo extraído de una respuesta."""

    texto: str
    tipo: str  # "numero" | "identificador" | "fecha"
    valor: Decimal | None = None


@dataclass(frozen=True)
class Veredicto:
    """Resultado de verificar una respuesta contra su evidencia."""

    afirmaciones: list[Afirmacion]
    infundadas: list[Afirmacion]

    @property
    def fundada(self) -> bool:
        return not self.infundadas

    @property
    def total(self) -> int:
        return len(self.afirmaciones)

    @property
    def proporcion(self) -> float:
        """Fracción de afirmaciones respaldadas; 1.0 si no hay ninguna que verificar."""
        if not self.afirmaciones:
            return 1.0
        return 1 - len(self.infundadas) / len(self.afirmaciones)

    def informe(self) -> str:
        if self.fundada:
            return f"fundada ({self.total} afirmaciones verificadas)"
        detalle = ", ".join(a.texto for a in self.infundadas)
        return f"NO fundada: {len(self.infundadas)}/{self.total} sin respaldo → {detalle}"


def a_decimal(texto: str) -> Decimal | None:
    """Interpreta un número escrito en formato español o inglés.

    El corpus mezcla ambos —"471,100 USD" en las salidas de herramientas y
    "90.000" en los documentos— así que hay que decidir por la forma y no por
    una convención fija: un separador seguido de exactamente tres dígitos y
    repetible es de miles; uno o dos dígitos finales son decimales.
    """
    limpio = texto.strip().rstrip(".,")
    if not limpio:
        return None
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", limpio):  # 471,100 · 90.000
        limpio = re.sub(r"[.,]", "", limpio)
    elif re.fullmatch(r"\d+[.,]\d{1,2}", limpio):  # 99,5 · 12.75
        limpio = limpio.replace(",", ".")
    elif not re.fullmatch(r"\d+", limpio):
        return None
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def extraer(texto: str) -> list[Afirmacion]:
    """Afirmaciones cuantitativas de un texto, sin duplicados y en orden de aparición."""
    afirmaciones: list[Afirmacion] = []
    vistos: set[str] = set()
    restante = texto

    def agregar(valor: str, tipo: str, numero: Decimal | None = None) -> None:
        clave = f"{tipo}:{numero if numero is not None else valor.lower()}"
        if clave not in vistos:
            vistos.add(clave)
            afirmaciones.append(Afirmacion(texto=valor, tipo=tipo, valor=numero))

    # Identificadores y fechas primero: contienen dígitos que no deben leerse
    # como números sueltos ("2026" de una fecha no es una afirmación).
    for patron, tipo in ((_IDENTIFICADOR, "identificador"), (_FECHA, "fecha")):
        for encontrado in patron.findall(restante):
            agregar(encontrado, tipo)
        restante = patron.sub(" ", restante)

    for encontrado in _NUMERO.findall(restante):
        numero = a_decimal(encontrado)
        if numero is None:
            continue
        if numero >= _MINIMO_VERIFICABLE or numero != numero.to_integral_value():
            agregar(encontrado, "numero", numero)

    return afirmaciones


def _respaldos(evidencia: list[str]) -> tuple[set[Decimal], str]:
    """Valores numéricos y texto plano de la evidencia disponible."""
    unido = "\n".join(evidencia)
    numeros = {
        valor
        for encontrado in _NUMERO.findall(_FECHA.sub(" ", _IDENTIFICADOR.sub(" ", unido)))
        if (valor := a_decimal(encontrado)) is not None
    }
    return numeros, unido.lower()


def verificar(respuesta: str, evidencia: list[str]) -> Veredicto:
    """Comprueba que cada dato cuantitativo de la respuesta esté en la evidencia."""
    afirmaciones = extraer(respuesta)
    numeros, texto = _respaldos(evidencia)

    infundadas = []
    for afirmacion in afirmaciones:
        if afirmacion.tipo == "numero":
            respaldada = afirmacion.valor in numeros
        else:
            respaldada = afirmacion.texto.lower() in texto
        if not respaldada:
            infundadas.append(afirmacion)

    return Veredicto(afirmaciones=afirmaciones, infundadas=infundadas)


def verificar_traza(respuesta: str, traza: Traza) -> Veredicto:
    """Verifica una respuesta contra la evidencia registrada en su traza."""
    return verificar(respuesta, traza.evidencia)
