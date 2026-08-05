"""Tests del versionado automático (Conventional Commits → semver)."""

from __future__ import annotations

import subprocess
from datetime import date

import pytest

from enterprise_agents import __version__, versionado

HOY = date(2026, 8, 5)


# --- Parseo de commits ------------------------------------------------------


def test_parsea_commit_simple():
    commit = versionado.parsear_commit("feat: agrega el tablero")
    assert commit is not None
    assert (commit.tipo, commit.alcance, commit.ruptura) == ("feat", None, False)
    assert commit.descripcion == "agrega el tablero"


def test_parsea_alcance_y_ruptura():
    commit = versionado.parsear_commit("feat(api)!: cambia el contrato de /consultar")
    assert commit is not None
    assert commit.alcance == "api"
    assert commit.ruptura is True
    assert commit.linea() == "- **api**: cambia el contrato de /consultar"


def test_ruptura_declarada_en_el_cuerpo():
    commit = versionado.parsear_commit(
        "fix: normaliza el formato de fechas\n\nBREAKING CHANGE: /metricas ahora exige ISO-8601."
    )
    assert commit is not None and commit.ruptura is True
    assert versionado.salto_de_commit(commit) == "major"


@pytest.mark.parametrize(
    "mensaje",
    ["arreglo varias cosas", "", "Feat: mayúscula no es convención", "feat:sin espacio"],
)
def test_ignora_commits_fuera_de_convencion(mensaje):
    assert versionado.parsear_commit(mensaje) is None


# --- Cálculo del salto y de la versión --------------------------------------


@pytest.mark.parametrize(
    ("mensaje", "esperado"),
    [
        ("fix: corrige el ruteo", "patch"),
        ("perf: cachea los CSV", "patch"),
        ("refactor: unifica la normalización", "patch"),
        ("feat: suma el dominio de finanzas", "minor"),
        ("feat!: reemplaza la CLI", "major"),
        ("docs: actualiza el README", None),
        ("chore(release): v0.3.0", None),
    ],
)
def test_salto_por_tipo_de_commit(mensaje, esperado):
    commit = versionado.parsear_commit(mensaje)
    assert commit is not None
    assert versionado.salto_de_commit(commit) == esperado


def test_calcular_salto_toma_el_mayor():
    commits = [versionado.parsear_commit(m) for m in ["fix: a", "feat: b", "docs: c", "fix: d"]]
    assert versionado.calcular_salto([c for c in commits if c]) == "minor"


def test_calcular_salto_sin_commits_publicables():
    commits = [versionado.parsear_commit("docs: solo documentación")]
    assert versionado.calcular_salto([c for c in commits if c]) is None
    assert versionado.calcular_salto([]) is None


@pytest.mark.parametrize(
    ("actual", "salto", "esperado"),
    [
        ("1.2.3", "patch", "1.2.4"),
        ("1.2.3", "minor", "1.3.0"),
        ("1.2.3", "major", "2.0.0"),
        ("1.2.3", None, "1.2.3"),
        # En 0.x la ruptura sube la menor (semver 2.0.0 §4).
        ("0.3.0", "major", "0.4.0"),
        ("0.3.1", "minor", "0.4.0"),
    ],
)
def test_siguiente_version(actual, salto, esperado):
    assert versionado.siguiente_version(actual, salto) == esperado


def test_siguiente_version_rechaza_versiones_no_semanticas():
    with pytest.raises(ValueError, match="no semántica"):
        versionado.siguiente_version("v1.2", "patch")


# --- Notas y changelog ------------------------------------------------------


def test_notas_agrupan_por_seccion_y_respetan_el_orden():
    commits = [
        versionado.parsear_commit(m)
        for m in [
            "docs: nota al pie",
            "fix(api): 422 en fechas inválidas",
            "feat!: nueva CLI",
            "feat(tablero): alertas tempranas",
        ]
    ]
    notas = versionado.notas_de_version("1.0.0", [c for c in commits if c], HOY)
    assert notas.startswith("## 1.0.0 — 2026-08-05")
    posiciones = [
        notas.index("⚠ Cambios de ruptura"),
        notas.index("Nuevas funcionalidades"),
        notas.index("Correcciones"),
        notas.index("Documentación"),
    ]
    assert posiciones == sorted(posiciones)
    # Un commit de ruptura va en su sección, no duplicado en la de su tipo.
    assert notas.count("nueva CLI") == 1
    assert "- **tablero**: alertas tempranas" in notas


def test_notas_sin_commits_relevantes():
    assert "Sin cambios destacables." in versionado.notas_de_version("0.3.0", [], HOY)


def test_changelog_inserta_arriba_conservando_lo_anterior():
    previo = versionado.ENCABEZADO_CHANGELOG + "\n## 0.3.0 — 2026-08-01\n\n- algo viejo\n"
    nuevo = versionado.actualizar_changelog(previo, "## 0.4.0 — 2026-08-05\n\n- algo nuevo\n")
    assert nuevo.index("## 0.4.0") < nuevo.index("## 0.3.0")
    assert "algo viejo" in nuevo
    assert nuevo.startswith("# Changelog")


def test_changelog_vacio_recibe_encabezado():
    nuevo = versionado.actualizar_changelog("", "## 0.1.0 — 2026-08-05\n")
    assert nuevo.startswith("# Changelog")
    assert "## 0.1.0" in nuevo


def test_changelog_sin_versiones_previas_agrega_al_final():
    nuevo = versionado.actualizar_changelog("# Changelog\n\nTexto suelto.", "## 0.1.0 — x\n")
    assert nuevo.endswith("## 0.1.0 — x\n")
    assert "Texto suelto." in nuevo


# --- Análisis completo ------------------------------------------------------


def test_analizar_de_mensajes_a_publicacion():
    publicacion = versionado.analizar(
        ["feat: suma finanzas", "fix: corrige el ruteo", "no convencional"], "0.3.0", HOY
    )
    assert publicacion.actual == "0.3.0"
    assert publicacion.version == "0.4.0"
    assert publicacion.salto == "minor"
    assert publicacion.hay_cambios is True
    assert "suma finanzas" in publicacion.notas
    assert "no convencional" not in publicacion.notas


def test_analizar_sin_cambios_publicables():
    publicacion = versionado.analizar(["docs: typo", "chore: limpieza"], "0.3.0", HOY)
    assert publicacion.hay_cambios is False
    assert publicacion.version == "0.3.0"


# --- Fuente única de verdad y escritura -------------------------------------


def test_version_del_paquete_es_la_del_archivo():
    assert versionado.leer_version() == __version__


def test_escribir_version_conserva_el_resto(tmp_path):
    archivo = tmp_path / "__init__.py"
    archivo.write_text('"""Docstring."""\n\n__version__ = "0.3.0"\n', encoding="utf-8")
    versionado.escribir_version("0.4.0", archivo)
    assert versionado.leer_version(archivo) == "0.4.0"
    assert '"""Docstring."""' in archivo.read_text(encoding="utf-8")


def test_leer_version_falla_si_no_esta_declarada(tmp_path):
    archivo = tmp_path / "__init__.py"
    archivo.write_text("# sin versión\n", encoding="utf-8")
    with pytest.raises(ValueError, match="__version__"):
        versionado.leer_version(archivo)


def test_aplicar_escribe_version_y_changelog(tmp_path):
    archivo_version = tmp_path / "__init__.py"
    archivo_version.write_text('__version__ = "0.3.0"\n', encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    publicacion = versionado.analizar(["feat: algo nuevo"], "0.3.0", HOY)

    versionado.aplicar(publicacion, archivo_version, changelog)

    assert versionado.leer_version(archivo_version) == "0.4.0"
    assert "## 0.4.0 — 2026-08-05" in changelog.read_text(encoding="utf-8")

    # Segunda publicación: se apila arriba sin perder la anterior.
    siguiente = versionado.analizar(["fix: un arreglo"], "0.4.0", HOY)
    versionado.aplicar(siguiente, archivo_version, changelog)
    texto = changelog.read_text(encoding="utf-8")
    assert texto.index("## 0.4.1") < texto.index("## 0.4.0")


# --- Integración con git ----------------------------------------------------


def _repo(tmp_path):
    """Crea un repo git de juguete para probar la lectura del historial."""

    def git(*args):
        subprocess.run(["git", *args], cwd=str(tmp_path), check=True, capture_output=True)

    git("init", "-q", "-b", "principal")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("1", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "feat: primera funcionalidad")
    git("tag", "-a", "v0.1.0", "-m", "v0.1.0")
    (tmp_path / "a.txt").write_text("2", encoding="utf-8")
    git("commit", "-qam", "fix: un arreglo posterior al tag")
    return tmp_path


def test_ultimo_tag_y_commits_desde(tmp_path):
    repo = _repo(tmp_path)
    assert versionado.ultimo_tag(repo) == "v0.1.0"
    mensajes = versionado.commits_desde("v0.1.0", repo)
    assert mensajes == ["fix: un arreglo posterior al tag"]
    assert len(versionado.commits_desde(None, repo)) == 2


def test_sin_tags_se_analiza_todo_el_historial(tmp_path):
    repo = tmp_path / "vacio"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True, capture_output=True)
    assert versionado.ultimo_tag(repo) is None
    # Repositorio sin commits: `git log` falla y no hay mensajes que analizar.
    assert versionado.commits_desde(None, repo) == []


def test_analizar_repo_usa_el_historial_real():
    publicacion = versionado.analizar_repo()
    assert publicacion.actual == __version__
    assert versionado.siguiente_version(publicacion.actual, publicacion.salto) == (
        publicacion.version
    )
