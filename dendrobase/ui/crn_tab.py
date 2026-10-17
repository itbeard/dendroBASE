"""Укладка «CRN Храналогія»: прагляд па гадах, даданне, рэдагаванне і выдаленне радкоў."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..models import CrnRow
from ..parsing import parse_float, parse_int
from ..reference import CRN_COLUMNS
from .feedback import ask_yes_no, show_error, show_warning
from .widgets import clear_tree, copy_to_clipboard, fill_tree, format_value, make_treeview, tree_to_tsv


class CrnTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, on_change: Callable[[str], None]) -> None:
        self.db = db
        self.on_change = on_change
        self.probe: str | None = None
        self.frame = ttk.Frame(notebook)

        filters = ttk.Frame(self.frame)
        filters.pack(fill="x", padx=6, pady=6)
        ttk.Label(filters, text="Год з:").pack(side="left", padx=4)
        self.year_from = ttk.Entry(filters, width=8)
        self.year_from.pack(side="left", padx=4)
        ttk.Label(filters, text="Год па:").pack(side="left", padx=4)
        self.year_to = ttk.Entry(filters, width=8)
        self.year_to.pack(side="left", padx=4)
        ttk.Button(filters, text="Фільтраваць", command=self.load).pack(side="left", padx=8)
        ttk.Button(filters, text="Паказаць усе", command=self.clear_filter).pack(side="left", padx=4)
        ttk.Button(filters, text="Капіраваць у буфер", command=self.copy).pack(side="right", padx=4)
        self.info = ttk.Label(filters, text="", foreground="blue")
        self.info.pack(side="right", padx=8)

        self.tree = make_treeview(self.frame, CRN_COLUMNS, horizontal=False)
        self.tree.master.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        editor = ttk.LabelFrame(self.frame, text="Дадаць або змяніць запіс")
        editor.pack(fill="x", padx=6, pady=6)
        self.entries: dict[str, ttk.Entry] = {}
        for index, column in enumerate(CRN_COLUMNS):
            ttk.Label(editor, text=f"{column}:").grid(row=index // 3, column=(index % 3) * 2, padx=6, pady=3, sticky="e")
            entry = ttk.Entry(editor, width=14)
            entry.grid(row=index // 3, column=(index % 3) * 2 + 1, padx=6, pady=3, sticky="w")
            self.entries[column] = entry
        buttons = ttk.Frame(editor)
        buttons.grid(row=2, column=0, columnspan=6, pady=6)
        ttk.Button(buttons, text="Дадаць / Абнавіць", command=self.add_record).pack(side="left", padx=4)
        ttk.Button(buttons, text="Выдаліць выбраны", command=self.delete_record).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ачысціць форму", command=self.clear_form).pack(side="left", padx=4)

    # ------------------------------------------------------------------ даныя
    def set_probe(self, probe: str | None) -> None:
        self.probe = probe
        self.clear_form()
        self.load()

    def _year_range(self) -> tuple[int | None, int | None] | None:
        try:
            return parse_int(self.year_from.get()), parse_int(self.year_to.get())
        except ValueError:
            show_warning("Папярэджанне", "Гады фільтра павінны быць цэлымі лікамі.")
            return None

    def load(self) -> None:
        clear_tree(self.tree)
        self.info.configure(text="")
        if not self.probe:
            return
        years = self._year_range()
        if years is None:
            return
        try:
            rows = self.db.get_crn(self.probe, *years)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць CRN:\n{exc}", exc)
            return
        fill_tree(self.tree, rows)
        self.info.configure(text=f"Радкоў: {len(rows)}")

    def clear_filter(self) -> None:
        self.year_from.delete(0, "end")
        self.year_to.delete(0, "end")
        self.load()

    def copy(self) -> None:
        if not self.tree.get_children():
            show_warning("Папярэджанне", "Няма даных для капіравання.")
            return
        copy_to_clipboard(self.frame, tree_to_tsv(self.tree))
        self.info.configure(text=f"Скапіравана радкоў: {len(self.tree.get_children())}")

    # -------------------------------------------------------------- рэдактар
    def _on_select(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        for column, value in zip(CRN_COLUMNS, values):
            self.entries[column].delete(0, "end")
            self.entries[column].insert(0, format_value(value))

    def clear_form(self) -> None:
        for entry in self.entries.values():
            entry.delete(0, "end")

    def _read_form(self) -> CrnRow | None:
        try:
            year = parse_int(self.entries["year"].get())
            if year is None:
                show_warning("Папярэджанне", "Увядзіце год.")
                return None
            values = {column: parse_float(self.entries[column].get()) for column in CRN_COLUMNS[1:]}
        except ValueError as exc:
            show_warning("Папярэджанне", f"Некарэктнае значэнне: {exc}")
            return None
        return CrnRow(year, **values)

    def add_record(self) -> None:
        if not self.probe:
            show_warning("Папярэджанне", "Спачатку выберыце пробную плошчу.")
            return
        row = self._read_form()
        if row is None:
            return
        try:
            self.db.upsert_crn(self.probe, row)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася захаваць запіс:\n{exc}", exc)
            return
        self.load()
        self.clear_form()
        self.on_change(self.probe)

    def delete_record(self) -> None:
        selected = self.tree.selection()
        if not selected or not self.probe:
            show_warning("Папярэджанне", "Выберыце радок у табліцы.")
            return
        year = parse_int(self.tree.item(selected[0], "values")[0])
        if year is None or not ask_yes_no("Пацверджанне", f"Выдаліць запіс за {year} год?"):
            return
        try:
            self.db.delete_crn(self.probe, year)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася выдаліць запіс:\n{exc}", exc)
            return
        self.load()
        self.on_change(self.probe)
