"""Галоўнае акно: спіс пробных плошчаў злева, укладкі справа, радок стану, гарачыя клавішы."""
from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .. import __version__
from ..config import Settings
from ..db import DatabaseError, DatabaseManager
from .crn_tab import CrnTab
from .dialogs import AddProbeDialog, CrnDialog, PorodaHelpDialog, SeriesDialog, SqlQueryDialog
from .feedback import ask_yes_no, show_error, show_info
from .filter_tab import FilterTab
from .info_tab import InfoTab
from .map_tab import MapTab
from .series_tab import SeriesTab
from .statusbar import StatusBar
from .theme import PAD, apply_theme
from .ui_state import load_ui_state, save_ui_state
from .widgets import PlaceholderEntry, add_tooltip, make_treeview

APP_TITLE = "DendroBASE"
_GEOMETRY = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


class DendroApp:
    def __init__(self, root: tk.Tk, db: DatabaseManager, settings: Settings | None = None,
                 log_path: Path | None = None) -> None:
        self.root = root
        self.db = db
        self.settings = settings
        self.log_path = log_path
        self.current_probe: str | None = None
        self._search_after: str | None = None
        self._syncing_list = False
        self.state = load_ui_state()

        apply_theme(root)
        root.title(APP_TITLE)
        root.minsize(1000, 640)
        self._restore_geometry()
        root.protocol("WM_DELETE_WINDOW", self.on_exit)
        try:
            root.createcommand("::tk::mac::Quit", self.on_exit)  # Cmd+Q на macOS
        except tk.TclError:
            pass

        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self.refresh_probes()
        self.map_tab.refresh()
        last = self.state.get("last_probe")
        if isinstance(last, str) and last in self.listed_probes():
            self.select_probe(last)
        root.after(50, self._restore_sash)

    # ------------------------------------------------------------------ стан
    def _restore_geometry(self) -> None:
        geometry = self.state.get("geometry")
        match = _GEOMETRY.match(geometry) if isinstance(geometry, str) else None
        if match:
            width, height, x, y = map(int, match.groups())
            if 0 <= x < self.root.winfo_screenwidth() - 100 and 0 <= y < self.root.winfo_screenheight() - 100:
                self.root.geometry(geometry)
                return
            self.root.geometry(f"{width}x{height}")
            return
        self.root.geometry("1400x860")

    def _restore_sash(self) -> None:
        sash = self.state.get("sash")
        if isinstance(sash, int) and 200 <= sash <= 600:
            try:
                self.paned.sashpos(0, sash)
            except tk.TclError:
                pass

    def _save_state(self) -> None:
        try:
            sash = self.paned.sashpos(0)
        except tk.TclError:
            sash = None
        save_ui_state({"geometry": self.root.geometry(), "sash": sash, "last_probe": self.current_probe})

    # ----------------------------------------------------------------- меню
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Новая пробная плошча…", command=self.add_new_probe, accelerator="Ctrl+N")
        file_menu.add_command(label="Абнавіць спіс", command=self.refresh_probes, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label="Выйсці", command=self.on_exit, accelerator="Ctrl+Q")

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Праўка", menu=edit_menu)
        edit_menu.add_command(label="Захаваць змены ПП", command=lambda: self.info_tab.save(), accelerator="Ctrl+S")
        edit_menu.add_command(label="Дадаць CRN да выбранай ПП…", command=self.add_crn)
        edit_menu.add_command(label="Дадаць SERIES да выбранай ПП…", command=self.add_series)
        edit_menu.add_separator()
        edit_menu.add_command(label="Абнавіць геаметрыю выбранай ПП", command=self.update_selected_geometry)
        edit_menu.add_command(label="Абнавіць геаметрыю ўсіх ПП", command=self.update_all_geometry)

        tools = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Інструменты", menu=tools)
        tools.add_command(label="SQL Запыт…", command=self.open_sql)
        tools.add_command(label="Адкрыць карту ў браўзеры", command=lambda: self.map_tab.open_map())

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Даведка", menu=help_menu)
        help_menu.add_command(label="Расшыфроўка пародаў", command=lambda: PorodaHelpDialog(self.root))
        help_menu.add_command(label="Гарачыя клавішы", command=self.show_shortcuts)
        help_menu.add_command(label="Дзе файл логаў", command=self.show_log_location)
        help_menu.add_separator()
        help_menu.add_command(label="Аб праграме", command=self.show_about)

    def _bind_shortcuts(self) -> None:
        bindings = {
            "n": self.add_new_probe,
            "f": lambda: self.search.focus_set(),
            "s": lambda: self.info_tab.save(),
            "q": self.on_exit,
        }
        for key, handler in bindings.items():
            for modifier in ("Control", "Command"):
                self.root.bind(f"<{modifier}-{key}>", lambda _e, h=handler: h())
        self.root.bind("<F5>", lambda _e: self.refresh_probes())

    # ---------------------------------------------------------------- макет
    def _build_layout(self) -> None:
        connection = self.settings.db.describe() if self.settings else ""
        postgis = self.db.has_postgis() and self.db.has_geometry_column()
        self.status = StatusBar(self.root, connection=connection, postgis=postgis)
        self.status.pack(side="bottom", fill="x")
        ttk.Separator(self.root, orient="horizontal").pack(side="bottom", fill="x")

        self.paned = ttk.PanedWindow(self.root, orient="horizontal")
        self.paned.pack(fill="both", expand=True)

        left = ttk.Frame(self.paned, padding=(PAD, PAD, 0, PAD))
        self.paned.add(left, weight=0)
        head = ttk.Frame(left)
        head.pack(fill="x")
        ttk.Label(head, text="Пробныя плошчы", style="Heading.TLabel").pack(side="left")
        self.count_label = ttk.Label(head, text="", style="Subtitle.TLabel")
        self.count_label.pack(side="right")
        self.search = PlaceholderEntry(left, placeholder="Пошук па коду ПП…")
        self.search.pack(fill="x", pady=(6, 6))
        self.search.bind("<KeyRelease>", self._on_search_typed)
        self.search.bind("<Escape>", lambda _e: (self.search.set_text(""), self.refresh_probes()))
        add_tooltip(self.search, "Ctrl+F ставіць курсор сюды, Esc ачышчае.")

        self.probe_list = make_treeview(left, ("Код", "Парода", "Гады"), horizontal=False, selectmode="browse")
        self.probe_list.column("Код", width=120, minwidth=80)
        self.probe_list.column("Парода", width=64, minwidth=50, stretch=False)
        self.probe_list.column("Гады", width=92, minwidth=70, stretch=False)
        self.probe_list.master.pack(fill="both", expand=True)
        self.probe_list.bind("<<TreeviewSelect>>", self._on_list_select)

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(PAD, 0))
        new_button = ttk.Button(buttons, text="+  Новая пробная плошча", command=self.add_new_probe)
        new_button.pack(fill="x")
        add_tooltip(new_button, "Ctrl+N. Майстар у тры крокі: анкета ПП, CRN, SERIES.")
        ttk.Button(buttons, text="Дадаць CRN да выбранай…", command=self.add_crn).pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text="Дадаць SERIES да выбранай…", command=self.add_series).pack(fill="x", pady=(4, 0))

        right = ttk.Frame(self.paned, padding=(PAD, PAD, PAD, PAD))
        self.paned.add(right, weight=1)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self.info_tab = InfoTab(self.notebook, self.db, self.on_data_changed, notify=self.notify)
        self.crn_tab = CrnTab(self.notebook, self.db, self.on_data_changed, notify=self.notify)
        self.series_tab = SeriesTab(self.notebook, self.db, notify=self.notify)
        self.filter_tab = FilterTab(self.notebook, self.db, notify=self.notify)
        self.map_tab = MapTab(self.notebook, self.db, notify=self.notify, on_pick=self._pick_from_map)
        self.notebook.add(self.info_tab.frame, text="  Інфармацыя аб ПП  ")
        self.notebook.add(self.crn_tab.frame, text="  CRN храналогія  ")
        self.notebook.add(self.series_tab.frame, text="  SERIES  ")
        self.notebook.add(self.filter_tab.frame, text="  Фільтры і пошук  ")
        self.notebook.add(self.map_tab.frame, text="  Карта  ")

    # -------------------------------------------------------------- паведамленні
    def notify(self, text: str, *, kind: str = "info") -> None:
        self.status.notify(text, kind=kind)

    # ----------------------------------------------------------- спіс ПП
    def _on_search_typed(self, _event: tk.Event) -> None:
        if self._search_after is not None:
            self.root.after_cancel(self._search_after)
        self._search_after = self.root.after(250, self.refresh_probes)

    def refresh_probes(self) -> None:
        self._search_after = None
        text = self.search.get().strip()
        try:
            summaries = self.db.list_probes(text)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць спіс ПП:\n{exc}", exc)
            return
        self._syncing_list = True
        try:
            self.probe_list.delete(*self.probe_list.get_children())
            for index, summary in enumerate(summaries):
                self.probe_list.insert("", "end", iid=summary.name, tags=("odd",) if index % 2 else (),
                                       values=(summary.name, summary.poroda or "", summary.years))
            if self.current_probe and self.probe_list.exists(self.current_probe):
                self.probe_list.selection_set(self.current_probe)
                self.probe_list.see(self.current_probe)
        finally:
            self._syncing_list = False
        self.count_label.configure(text=f"{len(summaries)}" + (" знойдзена" if text else ""))

    def listed_probes(self) -> list[str]:
        return [str(iid) for iid in self.probe_list.get_children()]

    def _on_list_select(self, _event: tk.Event) -> None:
        if self._syncing_list:
            return
        selection = self.probe_list.selection()
        if selection:
            self.select_probe(str(selection[0]))

    def _sync_list_selection(self) -> None:
        self._syncing_list = True
        try:
            if self.current_probe and self.probe_list.exists(self.current_probe):
                self.probe_list.selection_set(self.current_probe)
                self.probe_list.see(self.current_probe)
            else:
                self.probe_list.selection_remove(*self.probe_list.selection())
        finally:
            self._syncing_list = False

    def select_probe(self, probe: str | None, *, force: bool = False) -> bool:
        """Зрабіць ПП бягучай. Вяртае False, калі карыстальнік адмяніў з-за незахаваных змен."""
        if probe == self.current_probe and not force:
            return True
        if probe != self.current_probe and not self.info_tab.check_unsaved():
            self._sync_list_selection()
            return False
        self.current_probe = probe
        self.info_tab.set_probe(probe)
        self.crn_tab.set_probe(probe)
        self.series_tab.set_probe(probe)
        self.status.set_probe(probe)
        self._sync_list_selection()
        return True

    def _pick_from_map(self, probe: str) -> None:
        if self.select_probe(probe):
            self.notebook.select(self.info_tab.frame)

    def on_data_changed(self, probe: str) -> None:
        """Выклікаецца дыялогамі і ўкладкамі пасля любога захавання."""
        self.current_probe = probe
        self.refresh_probes()
        self.map_tab.refresh()
        self.select_probe(probe, force=True)

    def _require_probe(self) -> str | None:
        if not self.current_probe:
            self.notify("Спачатку выберыце пробную плошчу са спіса.", kind="warn")
            return None
        return self.current_probe

    # --------------------------------------------------------------- дзеянні
    def add_new_probe(self) -> None:
        if self.info_tab.check_unsaved():
            AddProbeDialog(self.root, self.db, on_change=self.on_data_changed, notify=self.notify)

    def add_crn(self) -> None:
        probe = self._require_probe()
        if probe:
            CrnDialog(self.root, self.db, probe, on_change=self.on_data_changed, notify=self.notify)

    def add_series(self) -> None:
        probe = self._require_probe()
        if probe:
            SeriesDialog(self.root, self.db, probe, on_change=self.on_data_changed, notify=self.notify)

    def open_sql(self) -> None:
        SqlQueryDialog(self.root, self.db, notify=self.notify)

    def update_selected_geometry(self) -> None:
        probe = self._require_probe()
        if not probe:
            return
        try:
            info = self.db.get_probe_info(probe) or {}
            if not info.get("shirota_grd") or not info.get("dolgota_grd"):
                self.notify(f"Для ПП {probe} не зададзены каардынаты: спачатку ўвядзіце шырату і даўгату.", kind="warn")
                return
            count = self.db.update_geometry(probe)
        except DatabaseError as exc:
            show_error("Памылка", str(exc), exc)
            return
        if count:
            self.notify(f"Геаметрыя для {probe} абноўлена.", kind="ok")
            self.map_tab.refresh()
        else:
            self.notify("Геаметрыя не абноўлена: праверце, што каардынаты не нулявыя.", kind="warn")

    def update_all_geometry(self) -> None:
        try:
            total = self.db.count_with_coords()
            if total == 0:
                self.notify("Няма ПП з каардынатамі для абнаўлення.", kind="warn")
                return
            if not ask_yes_no("Пацверджанне", f"Будзе абноўлена геаметрыя для {total} ПП. Працягнуць?"):
                return
            count = self.db.update_geometry_all()
        except DatabaseError as exc:
            show_error("Памылка", str(exc), exc)
            return
        self.notify(f"Геаметрыя абноўлена для {count} ПП.", kind="ok")
        self.map_tab.refresh()

    # ---------------------------------------------------------------- даведка
    def show_shortcuts(self) -> None:
        show_info("Гарачыя клавішы",
                  "Ctrl+N   новая пробная плошча\n"
                  "Ctrl+F   пошук у спісе ПП\n"
                  "Ctrl+S   захаваць змены на ўкладцы «Інфармацыя аб ПП»\n"
                  "F5       абнавіць спіс\n"
                  "Enter    прымяніць фільтр па гадах / запусціць пошук\n"
                  "Ctrl+V   уставіць табліцу ў вокнах CRN і SERIES\n"
                  "Ctrl+Enter   выканаць SQL-запыт\n"
                  "Ctrl+Q   выйсці\n\n"
                  "На macOS замест Ctrl працуе Cmd.")

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
        if not self.info_tab.check_unsaved():
            return
        self._save_state()
        self.db.close()
        self.root.destroy()
