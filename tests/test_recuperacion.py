"""Tests del motor de recuperación híbrido."""

from __future__ import annotations

import math

import pytest

from enterprise_agents.recuperacion import algebra
from enterprise_agents.recuperacion.fragmentos import (
    OBJETIVO_PALABRAS,
    fragmentar_documento,
    titulo_de,
)
from enterprise_agents.recuperacion.lexico import IndiceBM25
from enterprise_agents.recuperacion.motor import MotorRecuperacion
from enterprise_agents.recuperacion.terminos import raiz, terminos
from enterprise_agents.recuperacion.vectorial import IndiceSemantico, Vocabulario, svd_aleatorizada

DOCUMENTO = """# Política de Ejemplo — Dicsys

**Versión:** 1.0

## Primera sección

Contenido de la primera sección, con un tope de 90.000 por día.

## Segunda sección

Contenido de la segunda sección sobre respaldos y continuidad.
"""


# --- Fragmentación ----------------------------------------------------------


def test_fragmenta_por_seccion():
    fragmentos = fragmentar_documento("ejemplo.md", DOCUMENTO)
    secciones = [f.seccion for f in fragmentos]
    assert "Primera sección" in secciones
    assert "Segunda sección" in secciones
    assert all(f.documento == "ejemplo.md" for f in fragmentos)
    assert [f.orden for f in fragmentos] == list(range(len(fragmentos)))


def test_la_migaja_conserva_el_contexto_del_fragmento():
    """Sin la migaja, "el tope es 90.000" no es recuperable: no dice de qué."""
    fragmentos = fragmentar_documento("ejemplo.md", DOCUMENTO)
    primero = next(f for f in fragmentos if f.seccion == "Primera sección")
    assert primero.migaja == "Política de Ejemplo — Dicsys › Primera sección"
    assert "Política de Ejemplo" in primero.texto_indexable()


def test_una_seccion_larga_se_parte_con_solapamiento():
    largo = "# Doc\n\n## Sección\n\n" + " ".join(
        f"palabra{i}" for i in range(OBJETIVO_PALABRAS * 2)
    )
    fragmentos = fragmentar_documento("largo.md", largo)
    assert len(fragmentos) > 1
    # El solapamiento hace que el final de un fragmento reaparezca en el siguiente.
    primero, segundo = fragmentos[0].texto.split(), fragmentos[1].texto.split()
    assert set(primero) & set(segundo)


def test_titulo_de_documento_sin_encabezado():
    assert titulo_de("texto suelto\nmás texto") == "texto suelto"
    assert titulo_de("") == ""


# --- Preprocesamiento léxico ------------------------------------------------


@pytest.mark.parametrize(
    ("palabra", "esperada"),
    [
        ("vacaciones", "vacacion"),
        ("licencias", "licencia"),
        ("respaldos", "respaldo"),
        ("actualizaciones", "actualiz"),
        ("seguridad", "segur"),
        # Demasiado corta: recortar destruiría la palabra.
        ("mes", "mes"),
        ("base", "base"),
    ],
)
def test_raiz_recorta_sufijos_sin_destruir_la_palabra(palabra, esperada):
    assert raiz(palabra) == esperada


def test_terminos_descarta_vocabulario_vacio():
    assert terminos("¿qué dice la política de vacaciones?") == ["politica", "vacacion"]


def test_terminos_conserva_los_numeros():
    """En este corpus los números son datos (montos, plazos), no ruido."""
    assert "90" in terminos("el tope es de 90 por día")


# --- BM25 -------------------------------------------------------------------


def test_bm25_prefiere_el_documento_con_el_termino_raro():
    documentos = [
        ["contrato", "cliente", "servicio"],
        ["vacacion", "licencia", "cliente"],
        ["cliente", "cliente", "cliente"],
    ]
    indice = IndiceBM25(documentos)
    resultado = indice.buscar(["vacacion"], k=3)
    assert resultado[0][0] == 1


def test_bm25_ignora_terminos_ausentes():
    indice = IndiceBM25([["uno", "dos"], ["tres"]])
    assert indice.buscar(["inexistente"]) == []


def test_bm25_penaliza_los_documentos_largos():
    """Con la misma frecuencia absoluta, el documento corto es más relevante."""
    corto = ["clave"]
    largo = ["clave"] + ["relleno"] * 50
    indice = IndiceBM25([corto, largo])
    puntajes = dict(indice.buscar(["clave"], k=2))
    assert puntajes[0] > puntajes[1]


# --- Álgebra ----------------------------------------------------------------


def test_ortonormalizar_produce_base_ortonormal():
    base = algebra.ortonormalizar([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]])
    columnas = [[fila[j] for fila in base] for j in range(len(base[0]))]
    for i, columna in enumerate(columnas):
        assert math.isclose(sum(x * x for x in columna), 1.0, abs_tol=1e-9)
        for otra in columnas[i + 1 :]:
            assert abs(sum(x * y for x, y in zip(columna, otra, strict=True))) < 1e-9


def test_ortonormalizar_descarta_columnas_dependientes():
    # La segunda columna es el doble de la primera: aporta una sola dirección.
    base = algebra.ortonormalizar([[1.0, 2.0], [2.0, 4.0]])
    assert len(base[0]) == 1


def test_eigen_simetrica_recupera_autovalores_conocidos():
    # Matriz diagonal: sus autovalores son la propia diagonal.
    valores, _ = algebra.eigen_simetrica([[3.0, 0.0], [0.0, 1.0]])
    assert [round(v, 9) for v in valores] == [3.0, 1.0]


def test_eigen_simetrica_reconstruye_la_matriz():
    matriz = [[4.0, 1.0], [1.0, 3.0]]
    valores, vectores = algebra.eigen_simetrica(matriz)
    # A = V Λ Vᵀ
    for i in range(2):
        for j in range(2):
            reconstruido = sum(vectores[i][p] * valores[p] * vectores[j][p] for p in range(2))
            assert math.isclose(reconstruido, matriz[i][j], abs_tol=1e-7)


def test_normalizar_vector_deja_pasar_el_nulo():
    assert algebra.normalizar_vector([0.0, 0.0]) == [0.0, 0.0]


# --- Espacio latente --------------------------------------------------------


def test_svd_aleatorizada_es_determinista():
    documentos = [["a", "b"], ["b", "c"], ["a", "c"], ["a", "b", "c"]]
    vocabulario = Vocabulario(documentos)
    matriz = [vocabulario.vector_tfidf(d) for d in documentos]
    primera = svd_aleatorizada(matriz, len(vocabulario), 2)
    segunda = svd_aleatorizada(matriz, len(vocabulario), 2)
    assert primera == segunda


def test_svd_valores_singulares_en_orden_decreciente():
    documentos = [["a", "b"], ["b", "c"], ["a", "c"], ["a", "b", "c"]]
    vocabulario = Vocabulario(documentos)
    matriz = [vocabulario.vector_tfidf(d) for d in documentos]
    _, singulares = svd_aleatorizada(matriz, len(vocabulario), 3)
    assert singulares == sorted(singulares, reverse=True)


def test_espacio_latente_acerca_terminos_que_coocurren():
    """Dos términos que nunca coinciden pero comparten contexto quedan cerca.

    El mecanismo es el **truncamiento**: las direcciones que distinguen a dos
    sinónimos son las de menor valor singular, así que quedan fuera del espacio
    latente y los términos colapsan a la misma posición. Con la dimensión sin
    truncar se separarían, que es exactamente lo que no se quiere de un sinónimo.
    """
    documentos = [
        ["respaldo", "copia", "diaria"],
        ["resguardo", "copia", "diaria"],
        ["factura", "cobranza", "vencida"],
        ["factura", "cobranza", "mora"],
    ]
    indice = IndiceSemantico(documentos, dimension=2)
    respaldo = indice.codificar_terminos(["respaldo"])
    resguardo = indice.codificar_terminos(["resguardo"])
    factura = indice.codificar_terminos(["factura"])
    # "respaldo" y "resguardo" no comparten ningún término, pero sí contexto.
    assert algebra.coseno(respaldo, resguardo) > 0.9
    assert algebra.coseno(respaldo, factura) < 0.5


def test_vocabulario_resuelve_terminos_emparentados():
    vocabulario = Vocabulario([["respaldo", "continuidad"], ["respaldo", "prueba"]])
    assert vocabulario.mas_cercano("respaldos") == "respaldo"
    assert vocabulario.mas_cercano("xyzabc") is None


def test_idf_de_termino_desconocido_es_cero():
    vocabulario = Vocabulario([["uno"]])
    assert vocabulario.idf("inexistente") == 0.0


# --- Motor híbrido ----------------------------------------------------------


@pytest.fixture(scope="module")
def motor_corpus():
    """El índice se construye una sola vez para todo el módulo (cuesta ~1 s)."""
    return MotorRecuperacion.desde_directorio()


def test_motor_indexa_el_corpus_completo(motor_corpus):
    documentos = {f.documento for f in motor_corpus.fragmentos}
    assert len(documentos) >= 30
    assert len(motor_corpus.fragmentos) > len(documentos)


@pytest.mark.parametrize(
    ("consulta", "documento"),
    [
        ("¿qué dice la política de vacaciones?", "politica-vacaciones.md"),
        ("¿cuántos días de licencia por mudanza?", "politica-vacaciones.md"),
        ("¿cada cuánto se respalda la base de datos?", "politica-respaldos-y-continuidad.md"),
        ("¿puedo trabajar desde casa?", "politica-teletrabajo.md"),
        ("¿quién autoriza una compra de 3 millones?", "politica-compras.md"),
        ("¿me cubren un posgrado?", "politica-capacitacion.md"),
    ],
)
def test_recupera_el_documento_correcto(motor_corpus, consulta, documento):
    recuperados = [r.fragmento.documento for r in motor_corpus.buscar(consulta, k=3)]
    assert documento in recuperados


def test_la_expansion_rescata_terminos_fuera_de_vocabulario(motor_corpus):
    """El corpus dice "respaldo"; la consulta, "respalda"."""
    assert "respalda" not in motor_corpus.semantico.vocabulario.indices
    assert "respaldo" in motor_corpus.expandir("¿cada cuánto se respalda?")


def test_el_resultado_declara_su_procedencia(motor_corpus):
    resultados = motor_corpus.buscar("¿qué dice la política de vacaciones?", k=5)
    assert all(r.origen in {"ambas", "léxica", "semántica"} for r in resultados)
    assert all(r.puesto_lexico is not None or r.puesto_semantico is not None for r in resultados)


def test_los_resultados_vienen_ordenados_por_puntaje(motor_corpus):
    puntajes = [r.puntaje for r in motor_corpus.buscar("cobranzas y facturación", k=5)]
    assert puntajes == sorted(puntajes, reverse=True)


def test_agregacion_a_nivel_documento(motor_corpus):
    documentos = motor_corpus.buscar_documentos("¿qué dice la política de vacaciones?", k=3)
    assert documentos[0][0] == "politica-vacaciones.md"
    assert len(documentos) <= 3


def test_motor_vacio_no_falla():
    vacio = MotorRecuperacion([])
    assert vacio.buscar("cualquier cosa") == []


def test_consulta_sin_terminos_utiles_no_rompe(motor_corpus):
    """Una consulta que es toda vocabulario vacío no debe reventar el motor."""
    assert motor_corpus.buscar("¿y qué de lo que se ha de ser?", k=3) is not None


# --- Rechazo de consultas fuera de dominio ----------------------------------


@pytest.mark.parametrize(
    "consulta",
    [
        "blockchain cuántico",
        "recetas de cocina italiana",
        "el partido de fútbol del domingo",
        "¿va a llover mañana?",
    ],
)
def test_rechaza_consultas_fuera_de_dominio(motor_corpus, consulta):
    """El recuperador debe poder decir "no sé", no devolver siempre su top-k."""
    assert motor_corpus.buscar(consulta, k=3) == []


@pytest.mark.parametrize(
    "consulta",
    [
        "¿qué dice la política de vacaciones?",
        "¿cada cuánto se respalda la base de datos?",
        "¿qué SLA tenemos comprometido?",
    ],
)
def test_acepta_consultas_del_dominio(motor_corpus, consulta):
    assert motor_corpus.cobertura(consulta) >= 0.5
    assert motor_corpus.buscar(consulta, k=3)


def test_cobertura_de_consulta_vacia_es_cero(motor_corpus):
    assert motor_corpus.cobertura("de la que se") == 0.0


def test_el_indice_se_reconstruye_si_cambia_el_corpus(tmp_path, monkeypatch):
    """Hallazgo: era un lru_cache perpetuo mientras los CSV sí se invalidaban."""
    from enterprise_agents.recuperacion import motor as mod

    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "uno.md").write_text(
        "# Uno\n\n## Tema\n\nContenido sobre viáticos.", encoding="utf-8"
    )
    monkeypatch.setattr(mod, "DOCS_DIR", corpus)
    monkeypatch.setattr(mod, "_cache", None)

    assert len(mod.motor_por_defecto().fragmentos) == 1
    (corpus / "dos.md").write_text(
        "# Dos\n\n## Tema\n\nContenido sobre respaldos.", encoding="utf-8"
    )
    assert len(mod.motor_por_defecto().fragmentos) == 2
