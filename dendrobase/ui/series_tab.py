"""Укладка «SERIES (Матрыца)»: графік серый з вылучэннем адной і матрыца год x серыя."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..i18n import tr
from ..models import SeriesMatrix
from ..parsing import parse_int
from .chart import LineChart
from .feedback import show_error
from .theme import PAD, PALETTE
from .widgets import (add_tooltip, copy_to_clipboard, export_filetypes, fill_tree, make_treeview, save_tree_file,
                      set_columns, tree_to_tsv)

Notify = Callable[..., None]


class SeriesTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, notify: Notify | None = None) -> None:
        self.db = db
        self.notify: Notify = notify or (lambda text, **kwargs: None)
        self.probe: str | None = None
        self.matrix: SeriesMatrix | None = None
        self.frame = ttk.Frame(notebook, padding=(PAD, PAD, PAD, 0))

        header = ttk.Frame(self.frame)
        header.pack(fill="x")
        ttk.Label(header, text=tr("Індывідуальныя серыі"), style="Heading.TLabel").pack(side="left")
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
        ttk.Button(toolbar, text=tr("Прымяніць"), command=self.load).pack(side="left", padx=(4, 0))
        ttk.Button(toolbar, text=tr("Усе гады"), command=self.clear_filter).pack(side="left", padx=4)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=PAD, pady=2)
        ttk.Label(toolbar, text=tr("Вылучыць серыю:")).pack(side="left")
        self.highlight = ttk.Combobox(toolbar, width=10, state="readonly", values=[""])
        self.highlight.pack(side="left", padx=4)
        self.highlight.bind("<<ComboboxSelected>>", lambda _e: self._update_chart())
        add_tooltip(self.highlight, tr("Вылучаная серыя малюецца тоўстай чырвонай лініяй, астатнія шэрыя."))
        ttk.Button(toolbar, text=tr("Экспарт…"), command=self.export).pack(side="right")
        ttk.Button(toolbar, text=tr("Капіраваць"), command=self.copy).pack(side="right", padx=4)

        paned = ttk.PanedWindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True, pady=(0, PAD))
        self.chart = LineChart(paned, height=220)
        paned.add(self.chart, weight=0)
        self.tree = make_treeview(paned)
        paned.add(self.tree.master, weight=1)

    def set_probe(self, probe: str | None) -> None:
        self.probe = probe
        self.load()

    def load(self) -> None:
        set_columns(self.tree, [])
        self.matrix = None
        self.info.configure(text="", style="Subtitle.TLabel")
        if not self.probe:
            self.chart.clear()
            self.highlight.configure(values=[""])
            self.highlight.set("")
            return
        try:
            year_from, year_to = parse_int(self.year_from.get()), parse_int(self.year_to.get())
        except ValueError:
            self.info.configure(text=tr("Гады фільтра павінны быць цэлымі лікамі."), style="Error.TLabel")
            return
        try:
            self.matrix = self.db.get_series_matrix(self.probe, year_from, year_to)
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася прачытаць SERIES:\n{error}").format(error=exc), exc)
            return
        if self.matrix is None:
            self.info.configure(text=tr("Няма даных"))
            self.chart.clear()
            self.highlight.configure(values=[""])
            self.highlight.set("")
            return
        matrix = self.matrix
        set_columns(self.tree, ["year", *matrix.series], width=80,
                    numeric={"year": 0, **{name: 3 for name in matrix.series}})
        fill_tree(self.tree, ([year, *matrix.row(year)] for year in matrix.years))
        self.info.configure(text=tr("{years} гадоў  ·  {series} серый  ·  {first}–{last}").format(
            years=len(matrix.years), series=len(matrix.series), first=matrix.years[0], last=matrix.years[-1]))
        current = self.highlight.get()
        self.highlight.configure(values=[""] + matrix.series)
        self.highlight.set(current if current in matrix.series else "")
        self._update_chart()

    def _update_chart(self) -> None:
        matrix = self.matrix
        if matrix is None:
            self.chart.clear()
            return
        chosen = self.highlight.get()
        names = [name for name in matrix.series if name != chosen] + ([chosen] if chosen in matrix.series else [])
        self.chart.set_data(
            matrix.years,
            {name: [matrix.value(year, name) for year in matrix.years] for name in names},
            colors={name: PALETTE["highlight"] if name == chosen else PALETTE["series"] for name in names},
            widths={name: 2.5 if name == chosen else 1 for name in names},
            legend=[chosen] if chosen in matrix.series else [],
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
        self.notify(tr("SERIES: скапіравана радкоў: {count}").format(count=len(self.tree.get_children())), kind="ok")

    def export(self) -> None:
        if not self.tree.get_children():
            self.notify(tr("Няма даных для экспарту."), kind="warn")
            return
        target = filedialog.asksaveasfilename(title=tr("Экспарт SERIES"), defaultextension=".csv",
                                              filetypes=export_filetypes(), initialfile=f"{self.probe}_series.csv")
        if not target:
            return
        try:
            count = save_tree_file(self.tree, Path(target))
        except OSError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася захаваць файл:\n{error}").format(error=exc), exc)
            return
        self.notify(tr("SERIES: захавана радкоў: {count} у {path}").format(count=count, path=target), kind="ok")
