"""Галоўнае акно: спіс пробных плошчаў злева, укладкі справа, радок стану, гарачыя клавішы.

Мова і тэма мяняюцца на хаду: інтэрфейс перабудоўваецца нанова (гл. apply_preferences), а адкрытыя
дыялогі застаюцца як ёсць да закрыцця.
"""
from __future__ import annotations

import logging
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .. import __version__
from ..config import Settings
from ..db import DatabaseError, DatabaseManager
from ..i18n import set_language, tr
from ..import_state import PendingFiles
from .crn_tab import CrnTab
from .dialogs import AddProbeDialog, CrnDialog, PorodaHelpDialog, SeriesDialog, SettingsDialog, SqlQueryDialog
from .feedback import ask_yes_no, show_error, show_info
from .filter_tab import FilterTab
from .import_banner import ImportBanner, PendingImportCheck
from .import_dialog import ImportDialog
from .info_tab import InfoTab
from .map_tab import MapTab
from .preferences import Preferences, load_preferences, save_preferences
from .series_tab import SeriesTab
from .statusbar import StatusBar
from .theme import PAD, apply_theme
from .ui_state import load_ui_state, save_ui_state
from .widgets import PlaceholderEntry, add_tooltip, make_treeview, set_hint_sink

log = logging.getLogger("dendrobase.ui")
APP_TITLE = "DendroBASE"
_GEOMETRY = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


class DendroApp:
    def __init__(self, root: tk.Tk, db: DatabaseManager, settings: Settings | None = None,
                 log_path: Path | None = None, preferences: Preferences | None = None) -> None:
        self.root = root
        self.db = db
        self.settings = settings
        self.log_path = log_path
        self.current_probe: str | None = None
        self._search_after: str | None = None
        self._dialogs: dict[str, tk.Toplevel] = {}
        self._syncing_list = False
        self._pending_import: PendingFiles | None = None  # вынік апошняй праверкі папкі з Excel
        self._import_check: PendingImportCheck | None = None
        self.state = load_ui_state()
        self.preferences = (preferences or load_preferences()).normalized()
        set_language(self.preferences.language)

        root.title(APP_TITLE)
        root.minsize(1000, 640)
        self._restore_geometry()
        root.protocol("WM_DELETE_WINDOW", self.on_exit)
        try:
            root.createcommand("::tk::mac::Quit", self.on_exit)  # Cmd+Q на macOS
            root.createcommand("::tk::mac::ShowPreferences", self.open_settings)  # Cmd+, і пункт у меню праграмы
        except tk.TclError:
            pass

        self._build_ui()
        last = self.state.get("last_probe")
        if isinstance(last, str) and last in self.listed_probes():
            self.select_probe(last)
        root.after(50, lambda: self._restore_sash(self.state.get("sash")))
        self.check_pending_import()

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

    def _restore_sash(self, sash: object) -> None:
        if isinstance(sash, int) and 200 <= sash <= 600:
            try:
                self.paned.sashpos(0, sash)
            except tk.TclError:
                pass

    def _current_sash(self) -> int | None:
        try:
            return int(self.paned.sashpos(0))
        except (tk.TclError, ValueError):
            return None

    def _save_state(self) -> None:
        save_ui_state({"geometry": self.root.geometry(), "sash": self._current_sash(), "last_probe": self.current_probe})

    # ---------------------------------------------------------------- налады
    def apply_preferences(self, preferences: Preferences) -> bool:
        """Захаваць мову і тэму і перабудаваць інтэрфейс. False, калі карыстальнік адмяніў з-за незахаваных змен."""
        preferences = preferences.normalized()
        if preferences == self.preferences:
            return True
        if not self.info_tab.check_unsaved():
            return False
        save_preferences(preferences)
        self.preferences = preferences
        set_language(preferences.language)
        self._rebuild_ui()
        self.notify(tr("Налады захаваны."), kind="ok")
        return True

    def _rebuild_ui(self) -> None:
        probe, sash = self.current_probe, self._current_sash()
        self._destroy_ui()
        self._build_ui()
        if probe and self.probe_list.exists(probe):
            self.select_probe(probe, force=True)
        else:
            self.select_probe(None, force=True)
        self.root.after(50, lambda: self._restore_sash(sash))

    def _destroy_ui(self) -> None:
        """Прыбраць меню і ўсё змесціва галоўнага акна; дыялогі (Toplevel) застаюцца."""
        if self._search_after is not None:
            self.root.after_cancel(self._search_after)
            self._search_after = None
        self.root.config(menu="")
        for child in list(self.root.winfo_children()):
            if not isinstance(child, tk.Toplevel):
                child.destroy()

    def _build_ui(self) -> None:
        apply_theme(self.root, self.preferences.theme)
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self.refresh_probes()
        self.map_tab.refresh()

    # ----------------------------------------------------------------- меню
    def _build_menu(self) -> None:
        self.menubar = menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=tr("Файл"), menu=file_menu)
        file_menu.add_command(label=tr("Новая пробная плошча…"), command=self.add_new_probe, accelerator="Ctrl+N")
        file_menu.add_command(label=tr("Абнавіць спіс"), command=self.refresh_probes, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label=tr("Выйсці"), command=self.on_exit, accelerator="Ctrl+Q")

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=tr("Праўка"), menu=edit_menu)
        edit_menu.add_command(label=tr("Захаваць змены ПП"), command=lambda: self.info_tab.save(), accelerator="Ctrl+S")
        edit_menu.add_command(label=tr("Дадаць CRN да выбранай ПП…"), command=self.add_crn)
        edit_menu.add_command(label=tr("Дадаць SERIES да выбранай ПП…"), command=self.add_series)
        edit_menu.add_separator()
        edit_menu.add_command(label=tr("Абнавіць геаметрыю выбранай ПП"), command=self.update_selected_geometry)
        edit_menu.add_command(label=tr("Абнавіць геаметрыю ўсіх ПП"), command=self.update_all_geometry)

        tools = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=tr("Інструменты"), menu=tools)
        tools.add_command(label=tr("Імпарт даных…"), command=self.open_import, accelerator="Ctrl+I")
        tools.add_command(label=tr("SQL-запыт…"), command=self.open_sql)
        tools.add_command(label=tr("Адкрыць мапу ў браўзеры"), command=lambda: self.map_tab.open_map())
        tools.add_separator()
        tools.add_command(label=tr("Налады…"), command=self.open_settings, accelerator="Ctrl+,")

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=tr("Даведка"), menu=help_menu)
        help_menu.add_command(label=tr("Расшыфроўка пародаў"), command=lambda: PorodaHelpDialog(self.root))
        help_menu.add_command(label=tr("Гарачыя клавішы"), command=self.show_shortcuts)
        help_menu.add_command(label=tr("Дзе файл логаў"), command=self.show_log_location)
        help_menu.add_separator()
        help_menu.add_command(label=tr("Аб праграме"), command=self.show_about)

    def _bind_shortcuts(self) -> None:
        bindings = {
            "n": self.add_new_probe,
            "f": lambda: self.search.focus_set(),
            "s": lambda: self.info_tab.save(),
            "i": self.open_import,
            "q": self.on_exit,
            "comma": self.open_settings,
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
        set_hint_sink(self.root, self.status.show_hint)
        separator = ttk.Separator(self.root, orient="horizontal")
        separator.pack(side="bottom", fill="x")
        # паласа «ёсць файлы для імпарту» над радком стану; відаць толькі пакуль ёсць што імпартаваць
        self.import_banner = ImportBanner(self.root, on_import=self.open_import,
                                          on_dismiss=self.dismiss_import_banner, after_widget=separator)
        if self._pending_import:
            self.import_banner.show(self._pending_import)

        self.paned = ttk.PanedWindow(self.root, orient="horizontal")
        self.paned.pack(fill="both", expand=True)

        left = ttk.Frame(self.paned, padding=(PAD, PAD, 0, PAD))
        self.paned.add(left, weight=0)
        head = ttk.Frame(left)
        head.pack(fill="x")
        ttk.Label(head, text=tr("Пробныя плошчы"), style="Heading.TLabel").pack(side="left")
        self.count_label = ttk.Label(head, text="", style="Subtitle.TLabel")
        self.count_label.pack(side="right")
        self.search = PlaceholderEntry(left, placeholder=tr("Пошук па коду ПП…"))
        self.search.pack(fill="x", pady=(6, 6))
        self.search.bind("<KeyRelease>", self._on_search_typed)
        self.search.bind("<Escape>", lambda _e: (self.search.set_text(""), self.refresh_probes()))
        add_tooltip(self.search, tr("Ctrl+F ставіць курсор сюды, Esc ачышчае."))

        code, species, years = tr("Код"), tr("Парода"), tr("Гады")
        self.probe_list = make_treeview(left, (code, species, years), horizontal=False, selectmode="browse")
        self.probe_list.column(code, width=120, minwidth=80)
        self.probe_list.column(species, width=64, minwidth=50, stretch=False)
        self.probe_list.column(years, width=92, minwidth=70, stretch=False)
        self.probe_list.master.pack(fill="both", expand=True)
        self.probe_list.bind("<<TreeviewSelect>>", self._on_list_select)

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(PAD, 0))
        new_button = ttk.Button(buttons, text=tr("+  Новая пробная плошча"), command=self.add_new_probe)
        new_button.pack(fill="x")
        add_tooltip(new_button, tr("Ctrl+N. Майстар у тры крокі: анкета ПП, CRN, SERIES."))
        ttk.Button(buttons, text=tr("Дадаць CRN да выбранай…"), command=self.add_crn).pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text=tr("Дадаць SERIES да выбранай…"), command=self.add_series).pack(fill="x", pady=(4, 0))

        right = ttk.Frame(self.paned, padding=(PAD, PAD, PAD, PAD))
        self.paned.add(right, weight=1)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self.info_tab = InfoTab(self.notebook, self.db, self.on_data_changed, notify=self.notify)
        self.crn_tab = CrnTab(self.notebook, self.db, self.on_data_changed, notify=self.notify)
        self.series_tab = SeriesTab(self.notebook, self.db, notify=self.notify)
        self.filter_tab = FilterTab(self.notebook, self.db, notify=self.notify)
        self.map_tab = MapTab(self.notebook, self.db, notify=self.notify, on_pick=self._pick_from_map)
        for tab, title in ((self.info_tab, tr("Інфармацыя аб ПП")), (self.crn_tab, tr("CRN храналогія")),
                           (self.series_tab, "SERIES"), (self.filter_tab, tr("Фільтры і пошук")),
                           (self.map_tab, tr("Мапа"))):
            self.notebook.add(tab.frame, text=f"  {title}  ")

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
            show_error(tr("Памылка"), tr("Не атрымалася прачытаць спіс ПП:\n{error}").format(error=exc), exc)
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
        count = len(summaries)
        self.count_label.configure(text=tr("{count} знойдзена").format(count=count) if text else str(count))

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
            self.notify(tr("Спачатку выберыце пробную плошчу са спіса."), kind="warn")
            return None
        return self.current_probe

    # --------------------------------------------------------------- дзеянні
    def _open_dialog(self, key: str, factory):
        """Дыялогі не мадальныя, таму адзін і той жа не адкрываецца двойчы: існуючы падымаецца наверх.

        Вяртае новы дыялог або None, калі падняты ўжо адкрыты.
        """
        existing = self._dialogs.get(key)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return None
        created = factory()
        self._dialogs[key] = created.dialog
        return created

    def add_new_probe(self) -> None:
        if self.info_tab.check_unsaved():
            self._open_dialog("new_probe", lambda: AddProbeDialog(
                self.root, self.db, on_change=self.on_data_changed, notify=self.notify))

    def add_crn(self) -> None:
        probe = self._require_probe()
        if probe:
            self._open_dialog(f"crn:{probe}", lambda: CrnDialog(
                self.root, self.db, probe, on_change=self.on_data_changed, notify=self.notify))

    def add_series(self) -> None:
        probe = self._require_probe()
        if probe:
            self._open_dialog(f"series:{probe}", lambda: SeriesDialog(
                self.root, self.db, probe, on_change=self.on_data_changed, notify=self.notify))

    def open_sql(self) -> None:
        self._open_dialog("sql", lambda: SqlQueryDialog(self.root, self.db, notify=self.notify))

    def open_import(self) -> ImportDialog | None:
        """Акно імпарту з Excel: тая ж каманда excel_import, але з папкай, опцыямі і журналам ходу працы."""
        settings = self.settings
        if settings is None:
            self.notify(tr("Імпарт недаступны: праграма запушчана без налад падключэння."), kind="warn")
            return None
        return self._open_dialog("import", lambda: ImportDialog(
            self.root, settings, on_change=self.on_import_finished, notify=self.notify))

    def on_import_finished(self) -> None:
        """Пасля імпарту ўсё, што паказвае базу, перачытваецца: спіс ПП, мапа, пароды ў фільтрах, укладкі бягучай ПП."""
        self.refresh_probes()
        self.map_tab.refresh()
        self.filter_tab.refresh_species()
        self.check_pending_import()  # стан імпарту змяніўся: паласа абновіцца або знікне
        probe = self.current_probe
        if not probe:
            return
        if self.info_tab.is_dirty():  # незахаваныя праўкі анкеты не губляюцца: абнаўляюцца толькі CRN і SERIES
            self.crn_tab.set_probe(probe)
            self.series_tab.set_probe(probe)
        else:
            self.select_probe(probe, force=True)

    # ------------------------------------------------------ файлы для імпарту
    def check_pending_import(self) -> None:
        """Параўнаць папку DENDROBASE_EXCEL_FOLDER са станам імпарту (у фоне) і паказаць паласу, калі ёсць што імпартаваць.

        Выклікаецца на старце і пасля кожнага імпарту: тады паласа абнаўляецца або знікае.
        """
        folder = self.settings.excel_folder if self.settings else None
        if folder is None or not folder.is_dir():
            return
        if self._import_check is not None:
            self._import_check.cancel()  # папярэдняя праверка яшчэ ідзе: яе вынік ужо састарэў
        try:
            probes = set(self.db.get_all_probes())
        except DatabaseError as exc:
            log.warning("Папка з Excel-файламі не праверана: спіс ПП не прачытаны (%s)", exc)
            return
        self._import_check = PendingImportCheck(self.root, folder, probes, self._on_import_check_done)
        self._import_check.start()

    def _on_import_check_done(self, pending: PendingFiles | None) -> None:
        self._pending_import = pending if pending else None
        if self._pending_import is None:
            self.import_banner.hide()
            return
        log.info("Папка %s: файлаў для імпарту %d (новых %d, змененых %d)", pending.folder, pending.count,
                 len(pending.new), len(pending.changed))
        self.import_banner.show(self._pending_import)

    def dismiss_import_banner(self) -> None:
        """Схаваць паласу да наступнай праверкі (перазапуск або імпарт)."""
        self._pending_import = None
        self.import_banner.hide()

    def open_settings(self) -> None:
        self._open_dialog("settings", lambda: SettingsDialog(self.root, self.preferences, on_apply=self.apply_preferences))

    def update_selected_geometry(self) -> None:
        probe = self._require_probe()
        if not probe:
            return
        try:
            info = self.db.get_probe_info(probe) or {}
            if not info.get("shirota_grd") or not info.get("dolgota_grd"):
                self.notify(tr("Для ПП {probe} не зададзены каардынаты: спачатку ўвядзіце шырату і даўгату.")
                            .format(probe=probe), kind="warn")
                return
            count = self.db.update_geometry(probe)
        except DatabaseError as exc:
            show_error(tr("Памылка"), str(exc), exc)
            return
        if count:
            self.notify(tr("Геаметрыя для {probe} абноўлена.").format(probe=probe), kind="ok")
            self.map_tab.refresh()
        else:
            self.notify(tr("Геаметрыя не абноўлена: праверце, што каардынаты не нулявыя."), kind="warn")

    def update_all_geometry(self) -> None:
        try:
            total = self.db.count_with_coords()
            if total == 0:
                self.notify(tr("Няма ПП з каардынатамі для абнаўлення."), kind="warn")
                return
            if not ask_yes_no(tr("Пацверджанне"),
                              tr("Будзе абноўлена геаметрыя для {count} ПП. Працягнуць?").format(count=total)):
                return
            count = self.db.update_geometry_all()
        except DatabaseError as exc:
            show_error(tr("Памылка"), str(exc), exc)
            return
        self.notify(tr("Геаметрыя абноўлена для {count} ПП.").format(count=count), kind="ok")
        self.map_tab.refresh()

    # ---------------------------------------------------------------- даведка
    def show_shortcuts(self) -> None:
        show_info(tr("Гарачыя клавішы"),
                  tr("Ctrl+N   новая пробная плошча\n"
                     "Ctrl+F   пошук у спісе ПП\n"
                     "Ctrl+S   захаваць змены на ўкладцы «Інфармацыя аб ПП»\n"
                     "F5       абнавіць спіс\n"
                     "Enter    прымяніць фільтр па гадах / запусціць пошук\n"
                     "Ctrl+V   уставіць табліцу ў вокнах CRN і SERIES\n"
                     "Ctrl+Enter   выканаць SQL-запыт\n"
                     "Ctrl+I   імпарт даных з Excel\n"
                     "Ctrl+,   налады\n"
                     "Ctrl+Q   выйсці\n\n"
                     "На macOS замест Ctrl працуе Cmd."))

    def show_log_location(self) -> None:
        if self.log_path:
            show_info(tr("Файл логаў"), str(self.log_path))
        else:
            show_info(tr("Файл логаў"), tr("Файл логаў не ствараўся, логі ідуць толькі ў кансоль."))

    def show_about(self) -> None:
        connection = self.settings.db.describe() if self.settings else "?"
        show_info(
            tr("Аб праграме"),
            tr("DendroBASE {version}\n\n"
               "База дэндрахраналагічных даных Беларусі: пробныя плошчы, храналогіі CRN "
               "і індывідуальныя серыі ў PostgreSQL/PostGIS.\n\n"
               "Падключэнне: {connection}").format(version=__version__, connection=connection),
        )

    def on_exit(self) -> None:
        if not self.info_tab.check_unsaved():
            return
        self._save_state()
        self.db.close()
        self.root.destroy()
