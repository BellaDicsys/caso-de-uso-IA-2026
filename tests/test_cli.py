"""Tests de la CLI (modo mock)."""

import pytest

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


def test_live_sin_api_key_falla_con_mensaje(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit) as salida:
        main(["ask", "--live", "hola"])
    assert salida.value.code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
