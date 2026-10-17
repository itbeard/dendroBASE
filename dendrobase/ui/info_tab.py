"""Укладка «Інфармацыя аб ПП»: прагляд і рэдагаванне ўсіх палёў табліцы title."""
from __future__ import annotations

from tkinter import ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..parsing import coerce_title_values, values_equal
from ..reference import FIELD_BY_NAME, PROBE_KEY, READONLY_COLUMNS, TITLE_FIELDS, TitleField, field_label
from .feedback import show_error, show_info, show_warning
from .title_form import TitleForm
from .widgets import ScrollableFrame


class InfoTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, on_change: Callable[[str], None]) -> None:
        self.db = db
        self.on_change = on_change
        self.probe: str | None = None
        self.frame = ttk.Frame(notebook)

        columns = db.get_title_columns()
        known = [field for field in TITLE_FIELDS if field.name in columns]
        extra = [TitleField(name, name) for name in columns if name not in FIELD_BY_NAME]
        self.readonly = (READONLY_COLUMNS | {PROBE_KEY}) & set(columns)

        buttons = ttk.Frame(self.frame)
        buttons.pack(side="bottom", fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="Захаваць змены", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Абнавіць", command=self.load).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ачысціць форму", command=self.clear).pack(side="left", padx=4)
        ttk.Label(buttons, text="Рэдагуйце палі і націсніце «Захаваць змены». Код ПП змяніць нельга.",
                  foreground="blue").pack(side="left", padx=10)

        scroll = ScrollableFrame(self.frame)
        scroll.pack(fill="both", expand=True)
        self.form = TitleForm(scroll.inner, known + extra, columns=3, readonly=self.readonly)
        self.form.frame.pack(fill="both", expand=True, padx=4, pady=4)

    def set_probe(self, probe: str | None) -> None:
        self.probe = probe
        self.load()

    def clear(self) -> None:
        self.form.clear()

    def load(self) -> None:
        if not self.probe:
            self.form.clear()
            return
        try:
            info = self.db.get_probe_info(self.probe)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць ПП {self.probe}:\n{exc}", exc)
            return
        self.form.set_values(info or {})

    def save(self) -> None:
        if not self.probe:
            show_warning("Папярэджанне", "Спачатку выберыце пробную плошчу.")
            return
        try:
            old = self.db.get_probe_info(self.probe) or {}
        except DatabaseError as exc:
            show_error("Памылка", str(exc), exc)
            return
        data, errors = coerce_title_values(self.form.values())
        if errors:
            show_warning("Праверце значэнні", "Гэтыя палі не ўдалося разабраць:\n" + "\n".join(errors))
            return
        changed = {name: value for name, value in data.items() if not values_equal(old.get(name), value)}
        if not changed:
            show_info("Інфармацыя", "Няма змен для захавання.")
            return
        try:
            self.db.upsert_title({PROBE_KEY: self.probe, **changed})
            if {"shirota_grd", "dolgota_grd"} & changed.keys() \
                    and self.db.has_postgis() and self.db.has_geometry_column():
                self.db.update_geometry(self.probe)
        except (DatabaseError, ValueError) as exc:
            show_error("Памылка захавання", f"Не атрымалася захаваць змены:\n{exc}", exc)
            return
        show_info("Змены захаваны", "Абноўлены палі: " + ", ".join(field_label(name) for name in changed))
        self.load()
        self.on_change(self.probe)
