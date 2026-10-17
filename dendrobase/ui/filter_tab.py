"""Укладка «Фільтры і пошук»: выбарка CRN па пародзе, раянаванні, тыпу лесу і гадах."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..i18n import tr
from ..models import FilterCriteria
from ..parsing import parse_int
from ..reference import (CRN_VALUE_COLUMNS, DREVESNAYA_PORODA_LIST, GEO_OKRUG_LIST, GEO_PODZONA_LIST,
                         GEO_RAJON_LIST, GEO_ZONA_LIST)
from .feedback import show_error
from .theme import PAD
from .widgets import (add_tooltip, copy_to_clipboard, export_filetypes, fill_tree, make_treeview, save_tree_file,
                      set_columns, tree_to_tsv)

Notify = Callable[..., None]
RESULT_NUMERIC = {"year": 0, "raw": 3, "std": 3, "res": 3, "ars": 3}


class FilterTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, notify: Notify | None = None) -> None:
        self.db = db
        self.notify: Notify = notify or (lambda text, **kwargs: None)
        self.frame = ttk.Frame(notebook, padding=(PAD, PAD, PAD, 0))

        left = ttk.Frame(self.frame, width=380)
        left.pack(side="left", fill="y", padx=(0, PAD))
        left.pack_propagate(False)
        ttk.Label(left, text=tr("Умовы выбаркі"), style="Heading.TLabel").pack(anchor="w")
        ttk.Label(left, text=tr("Пустое поле не абмяжоўвае выбарку. Enter запускае пошук."),
                  style="Hint.TLabel", wraplength=360, justify="left").pack(anchor="w", pady=(2, PAD))

        where = ttk.LabelFrame(left, text=tr("Парода і раянаванне"), style="Section.TLabelframe", padding=(PAD, 2, PAD, PAD))
        where.pack(fill="x")
        where.columnconfigure(1, weight=1)
        self.combos: dict[str, ttk.Combobox] = {}
        rows = (
            ("drevesnaya_poroda", tr("Дрэвавая парода:"), self._poroda_values()),
            ("geo_zona", tr("Геабатанічная зона:"), GEO_ZONA_LIST),
            ("geo_podzona", tr("Падзона:"), GEO_PODZONA_LIST),
            ("geo_okrug", tr("Акруга:"), GEO_OKRUG_LIST),
            ("geo_rajon", tr("Раён:"), GEO_RAJON_LIST),
        )
        for index, (name, label, values) in enumerate(rows):
            ttk.Label(where, text=label).grid(row=index, column=0, sticky="w", padx=(0, 6), pady=3)
            combo = ttk.Combobox(where, values=[""] + list(values))
            combo.grid(row=index, column=1, sticky="ew", pady=3)
            combo.bind("<Return>", lambda _e: self.apply())
            self.combos[name] = combo
        ttk.Label(where, text=tr("Тып лесу змяшчае:")).grid(row=len(rows), column=0, sticky="w", padx=(0, 6), pady=3)
        self.tip_lesa = ttk.Entry(where)
        self.tip_lesa.grid(row=len(rows), column=1, sticky="ew", pady=3)
        self.tip_lesa.bind("<Return>", lambda _e: self.apply())
        add_tooltip(self.tip_lesa, tr("Пошук па частцы назвы без уліку рэгістру, напрыклад «мш»."))

        years = ttk.LabelFrame(left, text=tr("Гады і від храналогіі"), style="Section.TLabelframe", padding=(PAD, 2, PAD, PAD))
        years.pack(fill="x", pady=(PAD, 0))
        line = ttk.Frame(years)
        line.pack(fill="x", pady=3)
        ttk.Label(line, text=tr("Гады з")).pack(side="left")
        self.year_from = ttk.Entry(line, width=7)
        self.year_from.pack(side="left", padx=4)
        ttk.Label(line, text=tr("па")).pack(side="left")
        self.year_to = ttk.Entry(line, width=7)
        self.year_to.pack(side="left", padx=4)
        for entry in (self.year_from, self.year_to):
            entry.bind("<Return>", lambda _e: self.apply())
        checks = ttk.Frame(years)
        checks.pack(fill="x", pady=3)
        ttk.Label(checks, text=tr("Слупкі CRN:")).pack(side="left")
        self.crn_vars = {column: tk.BooleanVar(value=True) for column in CRN_VALUE_COLUMNS}
        for column, variable in self.crn_vars.items():
            ttk.Checkbutton(checks, text=column, variable=variable).pack(side="left", padx=4)

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=PAD)
        ttk.Button(buttons, text=tr("Знайсці"), command=self.apply).pack(side="left")
        ttk.Button(buttons, text=tr("Скінуць"), command=self.clear).pack(side="left", padx=4)

        right = ttk.Frame(self.frame)
        right.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(right)
        header.pack(fill="x")
        ttk.Label(header, text=tr("Вынікі"), style="Heading.TLabel").pack(side="left")
        self.status = ttk.Label(header, text=tr("Задайце ўмовы і націсніце «Знайсці»."), style="Subtitle.TLabel")
        self.status.pack(side="left", padx=(PAD * 2, 0))
        ttk.Button(header, text=tr("Экспарт…"), command=self.export).pack(side="right")
        ttk.Button(header, text=tr("Капіраваць"), command=self.copy).pack(side="right", padx=4)
        self.result = make_treeview(right, numeric=RESULT_NUMERIC)
        self.result.master.pack(fill="both", expand=True, pady=(6, PAD))

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
            self.status.configure(text=tr("Гады павінны быць цэлымі лікамі."), style="Error.TLabel")
            return None
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
            crn_columns=tuple(column for column, variable in self.crn_vars.items() if variable.get()),
        )

    def apply(self) -> None:
        criteria = self.criteria()
        if criteria is None:
            return
        self.status.configure(text=tr("Выкананне запыту..."), style="Subtitle.TLabel")
        self.frame.update_idletasks()
        try:
            columns, rows = self.db.get_filtered_crn(criteria)
        except DatabaseError as exc:
            self.status.configure(text=tr("Памылка запыту"), style="Error.TLabel")
            show_error(tr("Памылка"), tr("Не атрымалася выканаць пошук:\n{error}").format(error=exc), exc)
            return
        set_columns(self.result, columns, width=110)
        fill_tree(self.result, rows)
        probes = len({row[0] for row in rows})
        self.status.configure(text=tr("Знойдзена радкоў: {rows}  ·  ПП: {probes}").format(rows=len(rows), probes=probes),
                              style="Subtitle.TLabel")

    def clear(self) -> None:
        for combo in self.combos.values():
            combo.set("")
        self.tip_lesa.delete(0, "end")
        self.year_from.delete(0, "end")
        self.year_to.delete(0, "end")
        for variable in self.crn_vars.values():
            variable.set(True)
        set_columns(self.result, [])
        self.status.configure(text=tr("Задайце ўмовы і націсніце «Знайсці»."), style="Subtitle.TLabel")

    def copy(self) -> None:
        if not self.result.get_children():
            self.notify(tr("Няма даных для капіравання."), kind="warn")
            return
        copy_to_clipboard(self.frame, tree_to_tsv(self.result))
        self.notify(tr("Фільтры: скапіравана радкоў: {count}").format(count=len(self.result.get_children())), kind="ok")

    def export(self) -> None:
        if not self.result.get_children():
            self.notify(tr("Няма даных для экспарту."), kind="warn")
            return
        target = filedialog.asksaveasfilename(title=tr("Экспарт выбаркі"), defaultextension=".csv",
                                              filetypes=export_filetypes(), initialfile="dendrobase_vybarka.csv")
        if not target:
            return
        try:
            count = save_tree_file(self.result, Path(target))
        except OSError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася захаваць файл:\n{error}").format(error=exc), exc)
            return
        self.notify(tr("Выбарка: захавана радкоў: {count} у {path}").format(count=count, path=target), kind="ok")
