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

from dotenv import dotenv_values

from .i18n import tr

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
            env = {**read_dotenv_files(), **os.environ} if dotenv else dict(os.environ)

        def get(name: str, default: str = "") -> str:
            return env.get(ENV_PREFIX + name, default).strip()

        port_text = get("DB_PORT", "5432")
        try:
            port = int(port_text)
        except ValueError:
            raise ConfigError(tr("{name} павінен быць лікам, атрымана: {value}")
                              .format(name=f"{ENV_PREFIX}DB_PORT", value=repr(port_text))) from None
        if not 1 <= port <= 65535:
            raise ConfigError(tr("{name} па-за дыяпазонам 1..65535: {value}").format(name=f"{ENV_PREFIX}DB_PORT", value=port))

        level = get("LOG_LEVEL", "INFO").upper()
        if level not in _LOG_LEVELS:
            raise ConfigError(tr("{name} павінен быць адным з {choices}, атрымана: {value}")
                              .format(name=f"{ENV_PREFIX}LOG_LEVEL", choices=", ".join(_LOG_LEVELS), value=repr(level)))

        log_dir = _path_setting(get("LOG_DIR"))
        excel_folder = _path_setting(get("EXCEL_FOLDER"))

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


def _path_setting(value: str) -> Path | None:
    """Шлях з налад: пусты -> None, ~ разгортваецца, адносны лічыцца ад кораня праекта (дзе ляжыць .env)."""
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def dotenv_candidates() -> list[Path]:
    """Файлы .env у парадку прыярытэту (першы перамагае)."""
    candidates = [Path.cwd() / ".env", PROJECT_ROOT / ".env"]
    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return unique


def read_dotenv_files() -> dict[str, str]:
    """Значэнні з усіх знойдзеных .env, аб'яднаныя па прыярытэце (гл. dotenv_candidates).

    os.environ не змяняецца: налады застаюцца лакальнымі для працэсу, а не «выцякаюць» далей.
    """
    values: dict[str, str] = {}
    loaded: list[Path] = []
    for path in reversed(dotenv_candidates()):  # ад найменш прыярытэтнага да найбольш
        if path.is_file():
            values.update({k: v for k, v in dotenv_values(path, encoding="utf-8").items() if v is not None})
            loaded.append(path)
    if loaded:
        logging.getLogger(__name__).debug("Прачытаны .env: %s", ", ".join(map(str, loaded)))
    return values
