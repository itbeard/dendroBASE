"""Укладка «SERIES (Матрыца)»: індывідуальныя серыі ў выглядзе матрыцы год x серыя."""
from __future__ import annotations

from tkinter import ttk

from ..db import DatabaseError, DatabaseManager
from ..parsing import parse_int
from .feedback import show_error, show_warning
from .widgets import copy_to_clipboard, fill_tree, make_treeview, set_columns, tree_to_tsv


class SeriesTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager) -> None:
        self.db = db
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
        ttk.Button(filters, text="Паказаць матрыцу", command=self.load).pack(side="left", padx=8)
        ttk.Button(filters, text="Капіраваць у буфер", command=self.copy).pack(side="right", padx=4)
        self.info = ttk.Label(filters, text="", foreground="blue")
        self.info.pack(side="right", padx=8)

        self.tree = make_treeview(self.frame)
        self.tree.master.pack(fill="both", expand=True, padx=6, pady=4)

    def set_probe(self, probe: str | None) -> None:
        self.probe = probe
        self.load()

    def load(self) -> None:
        set_columns(self.tree, [])
        self.info.configure(text="")
        if not self.probe:
            return
        try:
            year_from, year_to = parse_int(self.year_from.get()), parse_int(self.year_to.get())
        except ValueError:
            show_warning("Папярэджанне", "Гады фільтра павінны быць цэлымі лікамі.")
            return
        try:
            matrix = self.db.get_series_matrix(self.probe, year_from, year_to)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць SERIES:\n{exc}", exc)
            return
        if matrix is None:
            self.info.configure(text="Няма даных")
            return
        set_columns(self.tree, ["year", *matrix.series], width=80)
        fill_tree(self.tree, ([year, *matrix.row(year)] for year in matrix.years))
        self.info.configure(text=f"Гадоў: {len(matrix.years)}, серый: {len(matrix.series)}")

    def copy(self) -> None:
        if not self.tree.get_children():
            show_warning("Папярэджанне", "Няма даных для капіравання.")
            return
        copy_to_clipboard(self.frame, tree_to_tsv(self.tree))
        self.info.configure(text=f"Скапіравана радкоў: {len(self.tree.get_children())}")
