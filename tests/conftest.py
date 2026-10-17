"""Агульныя фікстуры.

Інтэграцыйныя тэсты БД ствараюць асобную базу dendrobase_test на серверы з налад
(.env / DENDROBASE_DB_*) і выдаляюць яе пасля. Калі сервер недаступны, яны прапускаюцца.
"""
from __future__ import annotations

import os
from dataclasses import replace

import psycopg2
import pytest
from psycopg2 import sql

from dendrobase import i18n
from dendrobase.config import PROJECT_ROOT, Settings
from dendrobase.db import DatabaseError, DatabaseManager


@pytest.fixture(autouse=True)
def belarusian_interface():
    """Чаканыя радкі ў тэстах беларускія; па змаўчанні ж праграма англамоўная."""
    i18n.set_language("be")
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


@pytest.fixture(scope="session")
def test_db() -> DatabaseManager:
    settings = Settings.from_env()
    try:
        admin = psycopg2.connect(**settings.db.connect_kwargs(), connect_timeout=3)
    except psycopg2.Error as exc:
        pytest.skip(f"PostgreSQL недаступны ({settings.db.describe()}): {exc}")
    admin.autocommit = True
    name = os.environ.get("DENDROBASE_TEST_DB_NAME", "dendrobase_test")
    with admin.cursor() as cur:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
        cur.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(sql.Identifier(name)))

    manager = DatabaseManager(replace(settings.db, dbname=name))
    schema = (PROJECT_ROOT / "schema.sql").read_text(encoding="utf-8")
    marker = "CREATE EXTENSION IF NOT EXISTS postgis;"
    core, _, postgis_part = schema.partition(marker)
    with manager.transaction() as cur:
        cur.execute(core)
    try:
        with manager.transaction() as cur:
            cur.execute(marker + postgis_part)
    except DatabaseError:
        pass  # PostGIS не ўсталяваны: тэсты геаметрыі прапусцяцца самі

    yield manager

    manager.close()
    with admin.cursor() as cur:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    admin.close()


@pytest.fixture()
def clean_db(test_db: DatabaseManager) -> DatabaseManager:
    """База без радкоў перад кожным тэстам."""
    with test_db.transaction() as cur:
        cur.execute("TRUNCATE series, crn, title RESTART IDENTITY CASCADE")
    return test_db
