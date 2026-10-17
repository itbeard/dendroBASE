from pathlib import Path

import pytest

from dendrobase.config import ConfigError, DatabaseSettings, Settings


def test_defaults_without_environment():
    settings = Settings.from_env({}, dotenv=False)
    assert settings.db == DatabaseSettings()
    assert settings.db.port == 5432
    assert settings.log_level == "INFO"
    assert settings.log_dir is None
    assert settings.excel_folder is None


def test_values_from_environment():
    settings = Settings.from_env({
        "DENDROBASE_DB_HOST": "db.local",
        "DENDROBASE_DB_PORT": "5433",
        "DENDROBASE_DB_NAME": "dendro",
        "DENDROBASE_DB_USER": "alex",
        "DENDROBASE_DB_PASSWORD": "secret",
        "DENDROBASE_LOG_LEVEL": "debug",
        "DENDROBASE_LOG_DIR": "/tmp/logs",
        "DENDROBASE_EXCEL_FOLDER": "/data/excel",
    }, dotenv=False)
    assert settings.db.describe() == "alex@db.local:5433/dendro"
    assert settings.db.connect_kwargs()["password"] == "secret"
    assert "secret" not in settings.db.describe()
    assert settings.log_level == "DEBUG"
    assert settings.log_dir == Path("/tmp/logs")
    assert settings.excel_folder == Path("/data/excel")


def test_empty_password_is_not_sent():
    assert "password" not in DatabaseSettings().connect_kwargs()


@pytest.mark.parametrize("env", [
    {"DENDROBASE_DB_PORT": "abc"},
    {"DENDROBASE_DB_PORT": "70000"},
    {"DENDROBASE_LOG_LEVEL": "LOUD"},
])
def test_invalid_values_raise_config_error(env):
    with pytest.raises(ConfigError):
        Settings.from_env(env, dotenv=False)


def test_dotenv_file_is_loaded(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("DENDROBASE_DB_PORT=5999\nDENDROBASE_DB_PASSWORD=from-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DENDROBASE_DB_PORT", raising=False)
    monkeypatch.delenv("DENDROBASE_DB_PASSWORD", raising=False)
    monkeypatch.setenv("DENDROBASE_DB_PASSWORD", "from-env")
    settings = Settings.from_env()
    assert settings.db.port == 5999
    assert settings.db.password == "from-env"  # асяроддзе мае прыярытэт над .env
