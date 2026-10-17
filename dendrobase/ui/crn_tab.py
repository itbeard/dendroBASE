"""Укладка «CRN Храналогія»: графік, табліца па гадах, рэдактар радка."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..i18n import tr
from ..models import CrnRow
from ..parsing import parse_float, parse_int
from ..reference import CRN_COLUMNS, CRN_VALUE_COLUMNS
from .chart import LineChart
from .feedback import ask_yes_no, show_error
from .theme import CRN_COLORS, PAD
from .widgets import (add_tooltip, clear_tree, copy_to_clipboard, export_filetypes, fill_tree, format_value,
                      make_treeview, save_tree_file, tree_to_tsv)

NUMERIC = {"year": 0, "num": 0, "raw": 3, "std": 3, "res": 3, "ars": 3}
Notify = Callable[..., None]


class CrnTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, on_change: Callable[[str], None],
                 notify: Notify | None = None) -> None:
        self.db = db
        self.on_change = on_change
        self.notify: Notify = notify or (lambda text, **kwargs: None)
        self.probe: str | None = None
        self.rows: list[CrnRow] = []
        self.frame = ttk.Frame(notebook, padding=(PAD, PAD, PAD, 0))

        header = ttk.Frame(self.frame)
        header.pack(fill="x")
        ttk.Label(header, text=tr("Абагульненая храналогія"), style="Heading.TLabel").pack(side="left")
        self.info = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.info.pack(side="left", padx=(PAD * 2, 0))

        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill="x", pady=(6, 4))
        ttk.Label(toolbar, text=tr("Гады з")).pack(side="left")
        self.year_from = ttk.Entry(toolbar, width=7)
        self.year_from.pack(side="left", padx=4)
        ttk.Label(toolbar, text=tr("па")).pack(side="left")
        self.year_to = ttk.Entry(toolbar, width=7)
        self.year_to.pack(side="left", padx=4)
        for entry in (self.year_from, self.year_to):
            entry.bind("<Return>", lambda _e: self.load())
        apply = ttk.Button(toolbar, text=tr("Прымяніць"), command=self.load)
        apply.pack(side="left", padx=(4, 0))
        add_tooltip(apply, tr("Enter у полі года таксама прымяняе фільтр."))
        ttk.Button(toolbar, text=tr("Усе гады"), command=self.clear_filter).pack(side="left", padx=4)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=PAD, pady=2)
        ttk.Label(toolbar, text=tr("На графіку:")).pack(side="left")
        self.chart_vars = {column: tk.BooleanVar(value=column in ("raw", "std")) for column in CRN_VALUE_COLUMNS}
        for column, variable in self.chart_vars.items():
            ttk.Checkbutton(toolbar, text=column, variable=variable, command=self._update_chart).pack(side="left", padx=3)
        export = ttk.Button(toolbar, text=tr("Экспарт…"), command=self.export)
        export.pack(side="right")
        add_tooltip(export, tr("Захаваць табліцу ў CSV або тэкставы файл."))
        copy = ttk.Button(toolbar, text=tr("Капіраваць"), command=self.copy)
        copy.pack(side="right", padx=4)
        add_tooltip(copy, tr("Скапіраваць табліцу ў буфер абмену для ўстаўкі ў Excel."))

        paned = ttk.PanedWindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True)
        self.chart = LineChart(paned, height=220)
        paned.add(self.chart, weight=0)
        # height=3: табліца ўсё роўна расцягваецца на вольнае месца, а пры мінімальным памеры акна
        # рэдактар радка ніжэй не выціскаецца за межы
        self.tree = make_treeview(paned, CRN_COLUMNS, numeric=NUMERIC, height=3, horizontal=False)
        paned.add(self.tree.master, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        editor = ttk.LabelFrame(self.frame, text=tr("Дадаць або змяніць радок"), style="Section.TLabelframe",
                                padding=(PAD, 2, PAD, 6))
        editor.pack(fill="x", pady=(6, PAD))
        fields = ttk.Frame(editor)  # палі асобным радком: кнопкі ніжэй не абразаюцца пры вузкім акне
        fields.pack(fill="x")
        self.entries: dict[str, ttk.Entry] = {}
        for column in CRN_COLUMNS:
            ttk.Label(fields, text=f"{column}:").pack(side="left", padx=(0, 3))
            entry = ttk.Entry(fields, width=9)
            entry.pack(side="left", padx=(0, PAD))
            entry.bind("<Return>", lambda _e: self.add_record())
            self.entries[column] = entry
        actions = ttk.Frame(editor)
        actions.pack(fill="x", pady=(4, 0))
        ttk.Button(actions, text=tr("Захаваць радок"), command=self.add_record).pack(side="left")
        ttk.Button(actions, text=tr("Выдаліць выбраны"), command=self.delete_record).pack(side="left", padx=4)
        ttk.Button(actions, text=tr("Ачысціць"), command=self.clear_form).pack(side="left", padx=(0, PAD))
        ttk.Label(actions, text=tr("Клік па радку табліцы запаўняе форму. Год з існуючым запісам абнаўляе яго."),
                  style="Hint.TLabel").pack(side="left", padx=(PAD, 0))

    # ------------------------------------------------------------------ даныя
    def set_probe(self, probe: str | None) -> None:
        self.probe = probe
        self.clear_form()
        self.load()

    def _year_range(self) -> tuple[int | None, int | None] | None:
        try:
            return parse_int(self.year_from.get()), parse_int(self.year_to.get())
        except ValueError:
            self.info.configure(text=tr("Гады фільтра павінны быць цэлымі лікамі."), style="Error.TLabel")
            return None

    def load(self) -> None:
        clear_tree(self.tree)
        self.rows = []
        self.info.configure(text="", style="Subtitle.TLabel")
        if not self.probe:
            self.chart.clear()
            return
        years = self._year_range()
        if years is None:
            self.chart.clear()
            return
        try:
            self.rows = self.db.get_crn(self.probe, *years)
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася прачытаць CRN:\n{error}").format(error=exc), exc)
            return
        fill_tree(self.tree, self.rows)
        self.info.configure(text=self._stats(), style="Subtitle.TLabel")
        self._update_chart()

    def _stats(self) -> str:
        if not self.rows:
            return tr("Няма радкоў CRN для гэтай ПП.")
        parts = [tr("{count} гадоў").format(count=len(self.rows)), f"{self.rows[0].year}–{self.rows[-1].year}"]
        raw = [row.raw for row in self.rows if row.raw is not None]
        if raw:
            parts.append(tr("сярэдняе raw {mean}").format(mean=f"{sum(raw) / len(raw):.3f}"))
        return "  ·  ".join(parts)

    def _update_chart(self) -> None:
        if not self.rows:
            self.chart.clear()
            return
        visible = [column for column, variable in self.chart_vars.items() if variable.get()]
        self.chart.set_data(
            [row.year for row in self.rows],
            {column: [getattr(row, column) for row in self.rows] for column in CRN_VALUE_COLUMNS},
            colors=CRN_COLORS, visible=visible,
        )

    def clear_filter(self) -> None:
        self.year_from.delete(0, "end")
        self.year_to.delete(0, "end")
        self.load()

    def copy(self) -> None:
        if not self.tree.get_children():
            self.notify(tr("Няма даных для капіравання."), kind="warn")
            return
        copy_to_clipboard(self.frame, tree_to_tsv(self.tree))
        self.notify(tr("CRN: скапіравана радкоў: {count}").format(count=len(self.tree.get_children())), kind="ok")

    def export(self) -> None:
        if not self.tree.get_children():
            self.notify(tr("Няма даных для экспарту."), kind="warn")
            return
        target = filedialog.asksaveasfilename(title=tr("Экспарт CRN"), defaultextension=".csv",
                                              filetypes=export_filetypes(), initialfile=f"{self.probe}_crn.csv")
        if not target:
            return
        try:
            count = save_tree_file(self.tree, Path(target))
        except OSError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася захаваць файл:\n{error}").format(error=exc), exc)
            return
        self.notify(tr("CRN: захавана радкоў: {count} у {path}").format(count=count, path=target), kind="ok")

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
                self.notify(tr("Увядзіце год."), kind="warn")
                self.entries["year"].focus_set()
                return None
            values = {column: parse_float(self.entries[column].get()) for column in CRN_COLUMNS[1:]}
        except ValueError as exc:
            self.notify(tr("Некарэктнае значэнне: {error}").format(error=exc), kind="warn")
            return None
        return CrnRow(year, **values)

    def add_record(self) -> None:
        if not self.probe:
            self.notify(tr("Спачатку выберыце пробную плошчу."), kind="warn")
            return
        row = self._read_form()
        if row is None:
            return
        try:
            self.db.upsert_crn(self.probe, row)
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася захаваць запіс:\n{error}").format(error=exc), exc)
            return
        self.notify(tr("CRN {probe}: запіс за {year} год захаваны.").format(probe=self.probe, year=row.year), kind="ok")
        self.load()
        self.clear_form()
        self.on_change(self.probe)

    def delete_record(self) -> None:
        selected = self.tree.selection()
        if not selected or not self.probe:
            self.notify(tr("Выберыце радок у табліцы."), kind="warn")
            return
        year = parse_int(self.tree.item(selected[0], "values")[0])
        if year is None or not ask_yes_no(tr("Пацверджанне"), tr("Выдаліць запіс CRN за {year} год?").format(year=year)):
            return
        try:
            self.db.delete_crn(self.probe, year)
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася выдаліць запіс:\n{error}").format(error=exc), exc)
            return
        self.notify(tr("CRN {probe}: запіс за {year} год выдалены.").format(probe=self.probe, year=year), kind="ok")
        self.load()
        self.on_change(self.probe)
