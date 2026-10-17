"""Галоўнае акно: спіс пробных плошчаў злева, укладкі з данымі справа, меню."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .. import __version__
from ..config import Settings
from ..db import DatabaseError, DatabaseManager
from .crn_tab import CrnTab
from .dialogs import AddProbeDialog, CrnDialog, PorodaHelpDialog, SeriesDialog, SqlQueryDialog
from .feedback import ask_yes_no, show_error, show_info, show_warning
from .filter_tab import FilterTab
from .info_tab import InfoTab
from .map_tab import MapTab
from .series_tab import SeriesTab

APP_TITLE = "DendroBASE: база дэндрахраналагічных даных"


class DendroApp:
    def __init__(self, root: tk.Tk, db: DatabaseManager, settings: Settings | None = None,
                 log_path: Path | None = None) -> None:
        self.root = root
        self.db = db
        self.settings = settings
        self.log_path = log_path
        self.current_probe: str | None = None

        root.title(APP_TITLE)
        root.geometry("1400x820")
        root.minsize(1000, 620)
        root.protocol("WM_DELETE_WINDOW", self.on_exit)

        self._build_menu()
        self._build_layout()
        self.refresh_probes()

    # ----------------------------------------------------------------- меню
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Абнавіць спіс ПП", command=self.refresh_probes, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label="Выйсці", command=self.on_exit)
        self.root.bind("<F5>", lambda _e: self.refresh_probes())

        tools = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Інструменты", menu=tools)
        tools.add_command(label="SQL Запыт...", command=self.open_sql)
        tools.add_command(label="Адкрыць карту ў браўзеры", command=lambda: self.map_tab.open_map())
        tools.add_separator()
        tools.add_command(label="Абнавіць геаметрыю выбранай ПП", command=self.update_selected_geometry)
        tools.add_command(label="Абнавіць геаметрыю ўсіх ПП", command=self.update_all_geometry)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Даведка", menu=help_menu)
        help_menu.add_command(label="Расшыфроўка пародаў", command=lambda: PorodaHelpDialog(self.root))
        help_menu.add_command(label="Дзе файл логаў", command=self.show_log_location)
        help_menu.add_separator()
        help_menu.add_command(label="Аб праграме", command=self.show_about)

    # --------------------------------------------------------------- макет
    def _build_layout(self) -> None:
        left = ttk.Frame(self.root, width=260)
        left.pack(side="left", fill="y", padx=6, pady=6)
        left.pack_propagate(False)

        ttk.Label(left, text="Пошук ПП:").pack(anchor="w")
        self.search = ttk.Entry(left)
        self.search.pack(fill="x", pady=(0, 6))
        self.search.bind("<KeyRelease>", lambda _e: self.refresh_probes())

        ttk.Label(left, text="Пробныя плошчы:").pack(anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, exportselection=False)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)
        self.count_label = ttk.Label(left, text="", foreground="blue")
        self.count_label.pack(anchor="w", pady=(2, 6))

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=4)
        ttk.Button(buttons, text="+ Дадаць новую ПП", command=self.add_new_probe).pack(fill="x", pady=2)
        ttk.Button(buttons, text="Дадаць CRN да выбранай ПП", command=self.add_crn).pack(fill="x", pady=2)
        ttk.Button(buttons, text="Дадаць SERIES да выбранай ПП", command=self.add_series).pack(fill="x", pady=2)

        geo = ttk.LabelFrame(left, text="Геаметрыя (PostGIS)")
        geo.pack(fill="x", pady=6)
        ttk.Button(geo, text="Абнавіць геаметрыю выбранай ПП", command=self.update_selected_geometry).pack(fill="x", padx=6, pady=2)
        ttk.Button(geo, text="Абнавіць геаметрыю ўсіх ПП", command=self.update_all_geometry).pack(fill="x", padx=6, pady=2)
        if self.db.has_postgis() and self.db.has_geometry_column():
            ttk.Label(geo, text="PostGIS: усталяваны", foreground="green").pack(pady=2)
        else:
            ttk.Label(geo, text="PostGIS: не ўсталяваны", foreground="red").pack(pady=2)

        right = ttk.Frame(self.root)
        right.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self.info_tab = InfoTab(self.notebook, self.db, self.on_data_changed)
        self.crn_tab = CrnTab(self.notebook, self.db, self.on_data_changed)
        self.series_tab = SeriesTab(self.notebook, self.db)
        self.filter_tab = FilterTab(self.notebook, self.db)
        self.map_tab = MapTab(self.notebook, self.db)
        self.notebook.add(self.info_tab.frame, text="Інфармацыя аб ПП")
        self.notebook.add(self.crn_tab.frame, text="CRN Храналогія")
        self.notebook.add(self.series_tab.frame, text="SERIES (Матрыца)")
        self.notebook.add(self.filter_tab.frame, text="Фільтры і пошук")
        self.notebook.add(self.map_tab.frame, text="Карта храналогій")

    # ----------------------------------------------------------- спіс ПП
    def refresh_probes(self) -> None:
        text = self.search.get().strip()
        try:
            probes = self.db.search_probes(text)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць спіс ПП:\n{exc}", exc)
            return
        self.listbox.delete(0, "end")
        for probe in probes:
            self.listbox.insert("end", probe)
        self.count_label.configure(text=f"Паказана ПП: {len(probes)}")
        if self.current_probe in probes:
            index = probes.index(self.current_probe)
            self.listbox.selection_set(index)
            self.listbox.see(index)

    def _on_listbox_select(self, _event: tk.Event) -> None:
        selection = self.listbox.curselection()
        if selection:
            self.select_probe(self.listbox.get(selection[0]))

    def select_probe(self, probe: str | None) -> None:
        self.current_probe = probe
        self.info_tab.set_probe(probe)
        self.crn_tab.set_probe(probe)
        self.series_tab.set_probe(probe)

    def on_data_changed(self, probe: str) -> None:
        """Выклікаецца дыялогамі і ўкладкамі пасля любога захавання."""
        self.current_probe = probe
        self.refresh_probes()
        self.select_probe(probe)

    def _require_probe(self) -> str | None:
        if not self.current_probe:
            show_warning("Папярэджанне", "Спачатку выберыце пробную плошчу са спіса.")
            return None
        return self.current_probe

    # --------------------------------------------------------------- дзеянні
    def add_new_probe(self) -> None:
        AddProbeDialog(self.root, self.db, on_change=self.on_data_changed)

    def add_crn(self) -> None:
        probe = self._require_probe()
        if probe:
            CrnDialog(self.root, self.db, probe, on_change=self.on_data_changed)

    def add_series(self) -> None:
        probe = self._require_probe()
        if probe:
            SeriesDialog(self.root, self.db, probe, on_change=self.on_data_changed)

    def open_sql(self) -> None:
        SqlQueryDialog(self.root, self.db)

    def update_selected_geometry(self) -> None:
        probe = self._require_probe()
        if not probe:
            return
        try:
            info = self.db.get_probe_info(probe) or {}
            if not info.get("shirota_grd") or not info.get("dolgota_grd"):
                show_warning("Увага", f"Для ПП {probe} не зададзены каардынаты. Спачатку ўвядзіце шырату і даўгату.")
                return
            count = self.db.update_geometry(probe)
        except DatabaseError as exc:
            show_error("Памылка", str(exc), exc)
            return
        if count:
            show_info("Поспех", f"Геаметрыя для {probe} абноўлена.")
            self.info_tab.load()
        else:
            show_warning("Увага", "Геаметрыя не абноўлена. Праверце, што каардынаты не нулявыя.")

    def update_all_geometry(self) -> None:
        try:
            total = self.db.count_with_coords()
            if total == 0:
                show_warning("Увага", "Няма ПП з каардынатамі для абнаўлення.")
                return
            if not ask_yes_no("Пацверджанне", f"Будзе абноўлена геаметрыя для {total} ПП. Працягнуць?"):
                return
            count = self.db.update_geometry_all()
        except DatabaseError as exc:
            show_error("Памылка", str(exc), exc)
            return
        show_info("Поспех", f"Геаметрыя абноўлена для {count} ПП.")
        self.info_tab.load()

    # ---------------------------------------------------------------- даведка
    def show_log_location(self) -> None:
        if self.log_path:
            show_info("Файл логаў", str(self.log_path))
        else:
            show_info("Файл логаў", "Файл логаў не ствараўся, логі ідуць толькі ў кансоль.")

    def show_about(self) -> None:
        connection = self.settings.db.describe() if self.settings else "?"
        show_info(
            "Аб праграме",
            f"DendroBASE {__version__}\n\n"
            "База дэндрахраналагічных даных Беларусі: пробныя плошчы, храналогіі CRN "
            "і індывідуальныя серыі ў PostgreSQL/PostGIS.\n\n"
            f"Падключэнне: {connection}",
        )

    def on_exit(self) -> None:
        self.db.close()
        self.root.destroy()
