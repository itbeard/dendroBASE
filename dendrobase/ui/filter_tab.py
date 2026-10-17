"""Укладка «Фільтры і пошук»: выбарка CRN па пародзе, раянаванні, тыпу лесу і гадах."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..db import DatabaseError, DatabaseManager
from ..models import FilterCriteria
from ..parsing import parse_int
from ..reference import (CRN_VALUE_COLUMNS, DREVESNAYA_PORODA_LIST, GEO_OKRUG_LIST, GEO_PODZONA_LIST,
                         GEO_RAJON_LIST, GEO_ZONA_LIST)
from .feedback import show_error, show_warning
from .widgets import app_font, copy_to_clipboard, fill_tree, make_treeview, set_columns, tree_to_tsv


class FilterTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager) -> None:
        self.db = db
        self.frame = ttk.Frame(notebook)

        left = ttk.LabelFrame(self.frame, text="Фільтры", width=360)
        left.pack(side="left", fill="y", padx=6, pady=6)
        left.pack_propagate(False)

        self.combos: dict[str, ttk.Combobox] = {}
        self.combos["drevesnaya_poroda"] = self._combo(left, "Дрэвавая парода:", self._poroda_values())
        self.combos["geo_zona"] = self._combo(left, "Геабатанічная зона:", GEO_ZONA_LIST)
        self.combos["geo_podzona"] = self._combo(left, "Геабатанічная падзона:", GEO_PODZONA_LIST)
        self.combos["geo_okrug"] = self._combo(left, "Геабатанічная акруга:", GEO_OKRUG_LIST)
        self.combos["geo_rajon"] = self._combo(left, "Геабатанічны раён:", GEO_RAJON_LIST)

        ttk.Label(left, text="Тып лесу (ключавое слова):", font=app_font(bold=True)).pack(anchor="w", padx=6, pady=(6, 2))
        self.tip_lesa = ttk.Entry(left, width=32)
        self.tip_lesa.pack(fill="x", padx=6, pady=2)

        years = ttk.Frame(left)
        years.pack(fill="x", padx=6, pady=6)
        ttk.Label(years, text="Год з:", font=app_font(bold=True)).pack(side="left")
        self.year_from = ttk.Entry(years, width=8)
        self.year_from.pack(side="left", padx=4)
        ttk.Label(years, text="Год па:", font=app_font(bold=True)).pack(side="left")
        self.year_to = ttk.Entry(years, width=8)
        self.year_to.pack(side="left", padx=4)

        ttk.Label(left, text="Від храналогіі (CRN):", font=app_font(bold=True)).pack(anchor="w", padx=6, pady=(6, 2))
        checks = ttk.Frame(left)
        checks.pack(fill="x", padx=10, pady=2)
        self.crn_vars = {column: tk.BooleanVar(value=True) for column in CRN_VALUE_COLUMNS}
        for column, variable in self.crn_vars.items():
            ttk.Checkbutton(checks, text=column, variable=variable).pack(side="left", padx=4)

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", padx=6, pady=10)
        ttk.Button(buttons, text="Выканаць пошук", command=self.apply).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ачысціць фільтры", command=self.clear).pack(side="left", padx=4)

        right = ttk.LabelFrame(self.frame, text="Вынікі пошуку")
        right.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.result = make_treeview(right)
        self.result.master.pack(fill="both", expand=True, padx=6, pady=6)
        self.status = ttk.Label(right, text="", foreground="blue")
        self.status.pack(pady=4)
        ttk.Button(right, text="Капіраваць вынік у буфер", command=self.copy).pack(pady=4)

    def _combo(self, parent: tk.Misc, label: str, values: list[str]) -> ttk.Combobox:
        ttk.Label(parent, text=label, font=app_font(bold=True)).pack(anchor="w", padx=6, pady=(6, 2))
        combo = ttk.Combobox(parent, values=[""] + list(values), width=30)
        combo.pack(fill="x", padx=6, pady=2)
        return combo

    def _poroda_values(self) -> list[str]:
        try:
            values = self.db.get_unique_drevesnaya_poroda()
        except DatabaseError:
            values = []
        return values or list(DREVESNAYA_PORODA_LIST)

    def criteria(self) -> FilterCriteria | None:
        try:
            year_from, year_to = parse_int(self.year_from.get()), parse_int(self.year_to.get())
        except ValueError:
            show_warning("Папярэджанне", "Гады павінны быць цэлымі лікамі.")
            return None
        columns = tuple(column for column, variable in self.crn_vars.items() if variable.get())
        values = {name: combo.get().strip() or None for name, combo in self.combos.items()}
        return FilterCriteria(
            drevesnaya_poroda=values["drevesnaya_poroda"],
            geo_zona=values["geo_zona"],
            geo_podzona=values["geo_podzona"],
            geo_okrug=values["geo_okrug"],
            geo_rajon=values["geo_rajon"],
            tip_lesa_keyword=self.tip_lesa.get().strip() or None,
            year_from=year_from,
            year_to=year_to,
            crn_columns=columns,
        )

    def apply(self) -> None:
        criteria = self.criteria()
        if criteria is None:
            return
        self.status.configure(text="Выкананне запыту...", foreground="orange")
        self.frame.update_idletasks()
        try:
            columns, rows = self.db.get_filtered_crn(criteria)
        except DatabaseError as exc:
            self.status.configure(text="Памылка запыту", foreground="red")
            show_error("Памылка", f"Не атрымалася выканаць пошук:\n{exc}", exc)
            return
        set_columns(self.result, columns, width=120)
        fill_tree(self.result, rows)
        self.status.configure(text=f"Знойдзена запісаў: {len(rows)}", foreground="green")

    def clear(self) -> None:
        for combo in self.combos.values():
            combo.set("")
        self.tip_lesa.delete(0, "end")
        self.year_from.delete(0, "end")
        self.year_to.delete(0, "end")
        for variable in self.crn_vars.values():
            variable.set(True)
        set_columns(self.result, [])
        self.status.configure(text="")

    def copy(self) -> None:
        if not self.result.get_children():
            show_warning("Папярэджанне", "Няма даных для капіравання.")
            return
        copy_to_clipboard(self.frame, tree_to_tsv(self.result))
        self.status.configure(text=f"Скапіравана радкоў: {len(self.result.get_children())}", foreground="blue")
