"""Tests de las herramientas de personal."""

from dicsys_agents.tools.hr import buscar_por_habilidad, disponibilidad_equipo


def test_buscar_por_habilidad_ordena_por_disponibilidad():
    resultado = buscar_por_habilidad("Python")
    assert "Camila Duarte" not in resultado  # Camila no sabe Python
    lineas = [linea for linea in resultado.splitlines() if linea.startswith("  - ")]
    assert lineas, "debe devolver al menos un perfil"
    # Los perfiles sin asignar (100%) deben aparecer antes que los ocupados.
    assert "100%" in lineas[0]


def test_buscar_por_habilidad_es_insensible_a_mayusculas():
    def perfiles(resultado: str) -> list[str]:
        return [linea for linea in resultado.splitlines() if linea.startswith("  - ")]

    assert perfiles(buscar_por_habilidad("python")) == perfiles(buscar_por_habilidad("PYTHON"))


def test_buscar_habilidad_inexistente():
    resultado = buscar_por_habilidad("COBOL")
    assert "Ningún perfil" in resultado


def test_disponibilidad_equipo_respeta_umbral():
    resultado = disponibilidad_equipo(minimo_pct=100)
    assert "Martina López" in resultado
    assert "Valentina Ríos" not in resultado  # 10% de disponibilidad
