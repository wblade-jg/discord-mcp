import pytest

from discord_mcp.config import load_config
from discord_mcp.exceptions import ConfigError
from discord_mcp.main import main


def test_load_config_returns_token_when_present(monkeypatch):
    monkeypatch.setenv("TOKEN", "test-token")

    config = load_config()

    assert config.bot_token == "test-token"


def test_load_config_raises_config_error_when_token_missing(monkeypatch):
    monkeypatch.delenv("TOKEN", raising=False)

    with pytest.raises(ConfigError, match="TOKEN"):
        load_config()


def test_main_exits_with_code_1_when_token_missing(monkeypatch, capsys):
    monkeypatch.delenv("TOKEN", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "TOKEN" in capsys.readouterr().err
