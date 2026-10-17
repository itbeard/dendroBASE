"""Налады інтэрфейсу, якія выбірае карыстальнік: мова і тэма.

Захоўваюцца ў тым жа файле, што і стан акна (ui_state.json у папцы праграмы), таму перажываюць
перазапуск. Некарэктныя значэнні ціха замяняюцца на значэнні па змаўчанні.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..i18n import DEFAULT_LANGUAGE, normalize_language
from .theme import DEFAULT_THEME, normalize_theme
from .ui_state import load_ui_state, save_ui_state


@dataclass(frozen=True)
class Preferences:
    language: str = DEFAULT_LANGUAGE   # "be" | "en"
    theme: str = DEFAULT_THEME         # "system" | "light" | "dark"

    def normalized(self) -> "Preferences":
        return Preferences(language=normalize_language(self.language), theme=normalize_theme(self.theme))


def load_preferences(path: Path | None = None) -> Preferences:
    state = load_ui_state(path)
    return Preferences(language=state.get("language"), theme=state.get("theme")).normalized()  # type: ignore[arg-type]


def save_preferences(preferences: Preferences, path: Path | None = None) -> None:
    preferences = preferences.normalized()
    save_ui_state({"language": preferences.language, "theme": preferences.theme}, path)
