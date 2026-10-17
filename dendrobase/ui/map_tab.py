"""Укладка «Карта храналогій»: спіс ПП з каардынатамі і карта folium у браўзеры."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..i18n import tr
from ..maps import build_map, open_in_browser, save_map, temp_map_path
from .feedback import show_error, show_info
from .theme import PAD
from .widgets import add_tooltip, fill_tree, make_treeview

Notify = Callable[..., None]


class MapTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, notify: Notify | None = None,
                 on_pick: Callable[[str], None] | None = None) -> None:
        self.db = db
        self.notify: Notify = notify or (lambda text, **kwargs: None)
        self.on_pick = on_pick
        self.frame = ttk.Frame(notebook, padding=(PAD, PAD, PAD, 0))

        header = ttk.Frame(self.frame)
        header.pack(fill="x")
        ttk.Label(header, text=tr("Карта храналогій"), style="Heading.TLabel").pack(side="left")
        self.status = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.status.pack(side="left", padx=(PAD * 2, 0))

        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill="x", pady=(6, 4))
        open_button = ttk.Button(toolbar, text=tr("Адкрыць карту ў браўзеры"), command=self.open_map)
        open_button.pack(side="left")
        add_tooltip(open_button, tr("Інтэрактыўная карта (падкладка OpenTopoMap на даных OpenStreetMap) з маркерамі ўсіх ПП, якія маюць каардынаты."))
        ttk.Button(toolbar, text=tr("Захаваць як HTML…"), command=self.save_as).pack(side="left", padx=4)
        ttk.Button(toolbar, text=tr("Абнавіць спіс"), command=self.refresh).pack(side="left", padx=4)
        ttk.Label(self.frame, style="Hint.TLabel", wraplength=900, justify="left",
                  text=tr("Ніжэй толькі ПП з каардынатамі. Падвойны клік адкрывае ПП. "
                          "Каардынаты ўводзяцца на ўкладцы «Інфармацыя аб ПП» у дзесятковых градусах.")).pack(anchor="w")

        code, species, lat, lon, years = tr("Код"), tr("Парода"), tr("Шырата"), tr("Даўгата"), tr("Гады")
        self.tree = make_treeview(self.frame, (code, species, lat, lon, years),
                                  numeric={lat: 4, lon: 4}, horizontal=False, selectmode="browse")
        self.tree.column(code, width=140)
        self.tree.column(species, width=80)
        self.tree.column(years, width=100)
        self.tree.master.pack(fill="both", expand=True, pady=(6, PAD))
        self.tree.bind("<Double-1>", self._on_double_click)

    def refresh(self) -> None:
        try:
            summaries = self.db.list_probes()
            points = {point.name: point for point in self.db.get_probe_points()}
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася прачытаць каардынаты:\n{error}").format(error=exc), exc)
            return
        rows = [
            (point.name, point.poroda or "", point.lat, point.lon,
             f"{point.first_year or '?'}–{point.last_year or '?'}" if point.first_year or point.last_year else "")
            for point in points.values()
        ]
        self.tree.delete(*self.tree.get_children())
        fill_tree(self.tree, rows)
        self.status.configure(text=tr("ПП з каардынатамі: {with_coords} з {total}").format(with_coords=len(points), total=len(summaries)))

    def _on_double_click(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if selected and self.on_pick:
            self.on_pick(str(self.tree.item(selected[0], "values")[0]))

    def _build(self):
        try:
            points = self.db.get_probe_points()
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася прачытаць каардынаты:\n{error}").format(error=exc), exc)
            return None, 0
        if not points:
            self.notify(tr("Няма пробных плошчаў з каардынатамі."), kind="warn")
            return None, 0
        return build_map(points), len(points)

    def open_map(self) -> None:
        fmap, count = self._build()
        if fmap is None:
            return
        try:
            path = save_map(fmap, temp_map_path())
            opened = open_in_browser(path)
        except OSError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася стварыць карту:\n{error}").format(error=exc), exc)
            return
        if opened:
            self.notify(tr("Карта з {count} ПП адкрыта ў браўзеры.").format(count=count), kind="ok")
        else:
            show_info(tr("Карта захавана"), tr("Браўзер не адкрыўся. Адкрыйце файл уручную:\n{path}").format(path=path))

    def save_as(self) -> None:
        target = filedialog.asksaveasfilename(
            title=tr("Захаваць карту"), defaultextension=".html",
            filetypes=[("HTML", "*.html"), (tr("Усе файлы"), "*.*")], initialfile="dendrobase_map.html",
        )
        if not target:
            return
        fmap, count = self._build()
        if fmap is None:
            return
        try:
            save_map(fmap, Path(target))
        except OSError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася захаваць карту:\n{error}").format(error=exc), exc)
            return
        self.notify(tr("Карта з {count} ПП захавана: {path}").format(count=count, path=target), kind="ok")
