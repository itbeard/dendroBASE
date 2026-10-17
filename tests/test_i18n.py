"""Пераклады: каталог поўны, tr() працуе для абедзвюх моў, у кодзе няма f-радкоў унутры tr()."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dendrobase import i18n
from dendrobase.config import PROJECT_ROOT
from dendrobase.i18n import LANGUAGE_NAMES, normalize_language, set_language, tr
from dendrobase.reference import PORODA_DICT, TITLE_FIELDS, TITLE_SECTIONS

SOURCES = sorted((PROJECT_ROOT / "dendrobase").rglob("*.py"))


def tr_literals() -> dict[str, list[str]]:
    """Усе літаральныя аргументы tr() у пакеце: {радок: [файлы]}. f-радок у tr() — памылка."""
    found: dict[str, list[str]] = {}
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" and node.args:
                argument = node.args[0]
                if isinstance(argument, ast.JoinedStr):
                    pytest.fail(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}: tr() з f-радком не перакладаецца; "
                                "выкарыстоўвайце tr(\"...{name}...\").format(name=...)")
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    found.setdefault(argument.value, []).append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
    return found


def reference_strings() -> set[str]:
    """Радкі з даведніка, якія перакладаюцца не праз літарал у tr(): подпісы, падказкі, секцыі, пароды."""
    strings = {title for title, _ in TITLE_SECTIONS} | {"Іншыя слупкі"}
    strings |= {field.label for field in TITLE_FIELDS} | {field.hint for field in TITLE_FIELDS if field.hint}
    strings |= set(PORODA_DICT.values())
    strings |= {label for _, label in __import__("dendrobase.ui.dialogs", fromlist=["SettingsDialog"]).SettingsDialog.THEME_LABELS}
    return strings


def test_every_source_string_has_english_translation():
    needed = set(tr_literals()) | reference_strings()
    missing = sorted(text for text in needed if text not in i18n._EN)
    assert missing == [], "Няма англійскага перакладу для:\n" + "\n".join(missing)


def test_catalog_has_no_stale_entries():
    used = set(tr_literals()) | reference_strings()
    stale = sorted(text for text in i18n._EN if text not in used)
    assert stale == [], "У каталогу ёсць радкі, якіх няма ў кодзе:\n" + "\n".join(stale)


def test_translations_keep_format_placeholders():
    import string
    formatter = string.Formatter()
    for source, translated in i18n._EN.items():
        expected = {name for _, name, _, _ in formatter.parse(source) if name is not None}
        actual = {name for _, name, _, _ in formatter.parse(translated) if name is not None}
        assert expected == actual, f"Падстаноўкі адрозніваюцца: {source!r} -> {translated!r}"
        assert translated.strip(), source


def test_tr_switches_languages_and_falls_back_to_source():
    assert set_language("be") == "be"
    assert tr("Файл") == "Файл"
    assert set_language("en") == "en"
    assert tr("Файл") == "File"
    assert tr("Радок, якога няма ў каталогу") == "Радок, якога няма ў каталогу"
    assert tr("") == ""
    assert tr("ПП: {probe}").format(probe="x") == "Plot: x"


def test_language_codes_are_normalized():
    assert normalize_language("BE") == "be"
    assert normalize_language("en_US") == "en"
    assert normalize_language("be-BY") == "be"
    assert normalize_language("de") == i18n.DEFAULT_LANGUAGE
    assert normalize_language(None) == i18n.DEFAULT_LANGUAGE
    assert i18n.DEFAULT_LANGUAGE == "en"
    assert set(i18n.available_languages()) == set(LANGUAGE_NAMES) == {"be", "en"}


def test_field_labels_and_species_follow_language():
    from dendrobase.reference import field_label
    set_language("en")
    assert field_label("shirota_grd") == "Latitude, deg"
    assert field_label("no_such_column") == "no_such_column"
    assert tr(PORODA_DICT["С"]) == "Pine"
    set_language("be")
    assert field_label("shirota_grd") == "Шырата, град"


def test_interface_strings_are_belarusian_not_russian():
    """Літары и, щ, ъ ёсць у рускай, але не ў беларускай: у подпісах і назвах парод іх быць не павінна."""
    russian_only = set("ищъИЩЪ")
    suspicious = [text for text in reference_strings() if russian_only & set(text)]
    assert suspicious == []
    literals = [text for text in tr_literals() if russian_only & set(text) and "SELECT" not in text]
    assert literals == []
