"""Налады праграмы: чытаюцца з пераменных асяроддзя і файла .env.

Парадак прыярытэту: пераменныя асяроддзя > .env у бягучай папцы > .env у корані праекту.
Усе пераменныя маюць прэфікс DENDROBASE_ (гл. .env.example).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PREFIX = "DENDROBASE_"

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ConfigError(ValueError):
    """Некарэктнае значэнне ў наладах."""


@dataclass(frozen=True)
class DatabaseSettings:
    host: str = "localhost"
    port: int = 5432
    dbname: str = "postgres"
    user: str = "postgres"
    password: str = ""

    def connect_kwargs(self) -> dict[str, object]:
        """Аргументы для psycopg2.connect()."""
        kwargs: dict[str, object] = {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
        }
        if self.password:
            kwargs["password"] = self.password
        return kwargs

    def describe(self) -> str:
        """Радок для логаў і паведамленняў, без пароля."""
        return f"{self.user}@{self.host}:{self.port}/{self.dbname}"


@dataclass(frozen=True)
class Settings:
    db: DatabaseSettings
    log_level: str = "INFO"
    log_dir: Path | None = None
    excel_folder: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, dotenv: bool = True) -> "Settings":
        """Сабраць налады з асяроддзя.

        :param env: слоўнік замест os.environ (для тэстаў).
        :param dotenv: ці падгружаць файлы .env перад чытаннем os.environ.
        """
        if env is None:
            if dotenv:
                load_dotenv_files()
            env = os.environ

        def get(name: str, default: str = "") -> str:
            return env.get(ENV_PREFIX + name, default).strip()

        port_text = get("DB_PORT", "5432")
        try:
            port = int(port_text)
        except ValueError:
            raise ConfigError(f"{ENV_PREFIX}DB_PORT павінен быць лікам, атрымана: {port_text!r}") from None
        if not 1 <= port <= 65535:
            raise ConfigError(f"{ENV_PREFIX}DB_PORT па-за дыяпазонам 1..65535: {port}")

        level = get("LOG_LEVEL", "INFO").upper()
        if level not in _LOG_LEVELS:
            raise ConfigError(f"{ENV_PREFIX}LOG_LEVEL павінен быць адным з {', '.join(_LOG_LEVELS)}, атрымана: {level!r}")

        log_dir = Path(get("LOG_DIR")).expanduser() if get("LOG_DIR") else None
        excel_folder = Path(get("EXCEL_FOLDER")).expanduser() if get("EXCEL_FOLDER") else None

        return cls(
            db=DatabaseSettings(
                host=get("DB_HOST", "localhost") or "localhost",
                port=port,
                dbname=get("DB_NAME", "postgres") or "postgres",
                user=get("DB_USER", "postgres") or "postgres",
                password=get("DB_PASSWORD"),
            ),
            log_level=level,
            log_dir=log_dir,
            excel_folder=excel_folder,
        )


def dotenv_candidates() -> list[Path]:
    """Файлы .env у парадку прыярытэту (першы перамагае)."""
    candidates = [Path.cwd() / ".env", PROJECT_ROOT / ".env"]
    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return unique


def load_dotenv_files() -> list[Path]:
    """Падгрузіць знойдзеныя .env без перазапісу ўжо зададзеных пераменных."""
    loaded: list[Path] = []
    for path in dotenv_candidates():
        if path.is_file():
            load_dotenv(path, override=False, encoding="utf-8")
            loaded.append(path)
    if loaded:
        logging.getLogger(__name__).debug("Падгружаны .env: %s", ", ".join(map(str, loaded)))
    return loaded
