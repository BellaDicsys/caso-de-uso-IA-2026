"""Tests de la CLI (modo mock)."""

import pytest

from enterprise_agents import __version__
from enterprise_agents.cli import main


def test_ask_responde_en_modo_mock(capsys):
    codigo = main(["ask", "¿Cuánto facturamos este año?"])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "demo (mock" in salida
    assert "USD" in salida


def test_demo_corre_los_cinco_escenarios(capsys):
    assert main(["demo"]) == 0
    salida = capsys.readouterr().out
    assert salida.count("=== Escenario") == 5


def test_eval_pasa_en_mock(capsys):
    assert main(["eval"]) == 0
    assert "6/6 escenarios OK" in capsys.readouterr().out


def test_version_imprime_la_version_actual(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_version_proximo_calcula_desde_el_historial(capsys):
    assert main(["version", "--proximo"]) == 0
    salida = capsys.readouterr().out.strip()
    # Es una versión semántica y nunca retrocede respecto de la actual.
    partes = [int(p) for p in salida.split(".")]
    assert len(partes) == 3
    assert partes >= [int(p) for p in __version__.split(".")]


def test_version_notas_genera_el_bloque_de_changelog(capsys):
    assert main(["version", "--notas"]) == 0
    assert capsys.readouterr().out.startswith("## ")


def test_live_sin_api_key_falla_con_mensaje(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit) as salida:
        main(["ask", "--live", "hola"])
    assert salida.value.code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
