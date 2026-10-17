"""Укладка «Карта храналогій»: карта будуецца folium і адкрываецца ў сістэмным браўзеры."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, ttk

from ..db import DatabaseError, DatabaseManager
from ..maps import build_map, open_in_browser, save_map, temp_map_path
from .feedback import show_error, show_info, show_warning


class MapTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager) -> None:
        self.db = db
        self.frame = ttk.Frame(notebook)

        panel = ttk.Frame(self.frame)
        panel.pack(fill="x", padx=8, pady=8)
        ttk.Button(panel, text="Адкрыць карту ў браўзеры", command=self.open_map).pack(side="left", padx=4)
        ttk.Button(panel, text="Захаваць карту як HTML...", command=self.save_as).pack(side="left", padx=4)
        self.status = ttk.Label(panel, text="", foreground="blue")
        self.status.pack(side="left", padx=12)

        ttk.Label(
            self.frame, justify="left", wraplength=800,
            text=(
                "Карта паказвае ўсе пробныя плошчы, у якіх зададзены шырата і даўгата. "
                "Маркер падпісаны кодам ПП, у падказцы парода і дыяпазон гадоў храналогіі. "
                "Карта адкрываецца ў сістэмным браўзеры (патрэбны інтэрнэт для падкладкі OpenStreetMap)."
            ),
        ).pack(anchor="w", padx=12, pady=8)

    def _build(self):
        try:
            points = self.db.get_probe_points()
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць каардынаты:\n{exc}", exc)
            return None, 0
        if not points:
            show_warning("Увага", "Няма пробных плошчаў з каардынатамі.")
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
            show_error("Памылка", f"Не атрымалася стварыць карту:\n{exc}", exc)
            return
        if opened:
            self.status.configure(text=f"Карта адкрыта ў браўзеры: {count} ПП")
        else:
            show_info("Карта захавана", f"Браўзер не адкрыўся. Адкрыйце файл уручную:\n{path}")

    def save_as(self) -> None:
        target = filedialog.asksaveasfilename(
            title="Захаваць карту", defaultextension=".html",
            filetypes=[("HTML", "*.html"), ("Усе файлы", "*.*")], initialfile="dendrobase_map.html",
        )
        if not target:
            return
        fmap, count = self._build()
        if fmap is None:
            return
        try:
            save_map(fmap, Path(target))
        except OSError as exc:
            show_error("Памылка", f"Не атрымалася захаваць карту:\n{exc}", exc)
            return
        show_info("Поспех", f"Карта з {count} ПП захавана:\n{target}")
