"""Tests de las herramientas documentales."""

from dicsys_agents.tools.documents import buscar_documentos, leer_documento


def test_buscar_documentos_encuentra_politica_de_vacaciones():
    resultado = buscar_documentos("¿cuántos días de vacaciones me corresponden?")
    assert "politica-vacaciones.md" in resultado


def test_buscar_documentos_sin_coincidencias_lista_disponibles():
    resultado = buscar_documentos("blockchain cuántico")
    assert "Sin coincidencias" in resultado
    assert "politica-vacaciones.md" in resultado


def test_leer_documento_devuelve_contenido():
    contenido = leer_documento("politica-vacaciones.md")
    assert "Política de Vacaciones" in contenido
    assert "15 días de anticipación" in contenido


def test_leer_documento_bloquea_path_traversal():
    resultado = leer_documento("../ventas.csv")
    assert "inválido" in resultado

    resultado = leer_documento("../../pyproject.toml")
    assert "inválido" in resultado
