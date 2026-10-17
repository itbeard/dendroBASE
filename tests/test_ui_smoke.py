"""Дымавыя тэсты інтэрфейсу: віджэты будуюцца і рэагуюць, БД падменена дублем.

Патрэбны дысплей (Tk). Без яго тэсты прапускаюцца.
"""
from __future__ import annotations

import threading
import time
import tkinter as tk

import pytest

from dendrobase.config import DatabaseSettings, Settings
from dendrobase.models import CrnRow, ProbePoint, ProbeSummary, QueryResult, SeriesMatrix
from dendrobase.reference import PROBE_KEY
from dendrobase.ui import feedback


class FakeDb:
    def __init__(self):
        self.calls = []
        self.titles = {
            "p1": {"id": 1, PROBE_KEY: "p1", "shirota_grd": 53.9, "dolgota_grd": 27.5, "glavnaya_poroda": "С",
                   "tip_lesa": None, "pervyy_god": 1900, "posledniy_god": 2020, "geom": None},
            "p2": {"id": 2, PROBE_KEY: "p2", "shirota_grd": None, "dolgota_grd": None, "glavnaya_poroda": None,
                   "tip_lesa": None, "pervyy_god": None, "posledniy_god": None, "geom": None},
        }

    def get_title_columns(self, refresh=False):
        return ["id", PROBE_KEY, "shirota_grd", "dolgota_grd", "glavnaya_poroda", "tip_lesa", "pervyy_god",
                "posledniy_god", "geom"]

    def get_all_probes(self):
        return sorted(self.titles)

    def search_probes(self, text):
        return [p for p in self.get_all_probes() if text.lower() in p.lower()]

    def list_probes(self, search=""):
        return [
            ProbeSummary(name, info.get("glavnaya_poroda"), None, info.get("pervyy_god"), info.get("posledniy_god"),
                         None, bool(info.get("shirota_grd") and info.get("dolgota_grd")))
            for name, info in sorted(self.titles.items()) if search.lower() in name.lower()
        ]

    def get_probe_info(self, probe):
        return self.titles.get(probe)

    def get_crn(self, probe, year_from=None, year_to=None):
        rows = [CrnRow(1900, 5, 1.2, 1.0, 0.98, 1.01), CrnRow(1901, 5, 1.3)]
        return [r for r in rows if (year_from is None or r.year >= year_from) and (year_to is None or r.year <= year_to)]

    def get_series_matrix(self, probe, year_from=None, year_to=None):
        return SeriesMatrix([1900], ["1a", "2"], {(1900, "1a"): 1.5}) if probe == "p1" else None

    def get_unique_drevesnaya_poroda(self):
        return ["Pinus sylvestris L."]

    def get_filtered_crn(self, criteria):
        self.calls.append(("filter", criteria))
        return ["probe_name", "year", "raw"], [("p1", 1900, 1.2)]

    def get_probe_points(self):
        return [ProbePoint(name, info["shirota_grd"], info["dolgota_grd"], info.get("glavnaya_poroda"),
                           info.get("pervyy_god"), info.get("posledniy_god"))
                for name, info in self.titles.items() if info.get("shirota_grd") and info.get("dolgota_grd")]

    def has_postgis(self):
        return False

    def has_geometry_column(self):
        return True

    def upsert_title(self, data):
        self.calls.append(("upsert_title", dict(data)))
        self.titles.setdefault(data[PROBE_KEY], {PROBE_KEY: data[PROBE_KEY]}).update(data)

    def upsert_crn(self, probe, row):
        self.calls.append(("upsert_crn", probe, row))
        return 1

    def upsert_crn_rows(self, probe, rows, *, overwrite=True):
        rows = list(rows)
        self.calls.append(("upsert_crn_rows", probe, rows))
        return len(rows)

    def upsert_series_values(self, probe, values, *, overwrite=True):
        values = list(values)
        self.calls.append(("upsert_series_values", probe, values))
        return len(values)

    def delete_crn(self, probe, year):
        self.calls.append(("delete_crn", probe, year))
        return 1

    def execute_sql(self, query):
        self.calls.append(("sql", query))
        return QueryResult(columns=["n"], rows=[(1,)], rowcount=1)

    def count_with_coords(self):
        return 1

    def close(self):
        self.calls.append(("close",))


@pytest.fixture()
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk недаступны: {exc}")
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


@pytest.fixture()
def quiet_messages(monkeypatch):
    """Усе messagebox не блакуюць тэст, а запісваюцца. Пытанні адказваюцца «так» / «не захоўваць»."""
    shown = []
    for name in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(feedback.messagebox, name, lambda title, message, **kw: shown.append((title, message)))
    monkeypatch.setattr(feedback.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(feedback.messagebox, "askyesnocancel", lambda *a, **kw: False)
    return shown


@pytest.fixture()
def isolated_ui_state(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.json"
    monkeypatch.setattr("dendrobase.ui.ui_state.STATE_FILE", path)
    path.write_text('{"language": "be"}', encoding="utf-8")  # інакш праграма стартуе па-англійску
    return path


@pytest.fixture()
def app(root, quiet_messages, isolated_ui_state):
    from dendrobase.ui.app import DendroApp
    settings = Settings(db=DatabaseSettings())
    return DendroApp(root, FakeDb(), settings)


def status_text(app) -> str:
    return app.status.message.cget("text")


def test_app_builds_and_lists_probes(app):
    assert app.listed_probes() == ["p1", "p2"]
    assert app.notebook.index("end") == 5
    assert app.probe_list.item("p1", "values")[2] == "1900–2020"
    assert app.map_tab.status.cget("text") == "ПП з каардынатамі: 1 з 2"


def test_selecting_probe_fills_tabs(app):
    assert app.select_probe("p1")
    app.root.update_idletasks()
    assert app.info_tab.title_label.cget("text") == "p1"
    assert "С (Сасна)" in app.info_tab.subtitle.cget("text") and "1900–2020" in app.info_tab.subtitle.cget("text")
    assert app.info_tab.form.get_text(PROBE_KEY) == "p1"
    assert app.info_tab.form.get_text("shirota_grd") == "53.9"
    assert len(app.crn_tab.tree.get_children()) == 2
    assert app.crn_tab.tree.item(app.crn_tab.tree.get_children()[0], "values")[2] == "1.200"
    assert app.crn_tab.chart.visible_names() == ["raw", "std"]
    assert list(app.series_tab.tree["columns"]) == ["year", "1a", "2"]
    assert app.status.probe.cget("text") == "ПП: p1"
    app.select_probe("p2")
    assert app.series_tab.info.cget("text") == "Няма даных"
    assert "без каардынат" in app.info_tab.subtitle.cget("text")


def test_search_filters_list(app):
    app.search.set_text("P2")
    app.refresh_probes()
    assert app.listed_probes() == ["p2"]
    assert app.count_label.cget("text") == "1 знойдзена"


def test_info_tab_saves_only_changed_fields(app):
    app.select_probe("p1")
    assert not app.info_tab.is_dirty()
    app.info_tab.form.widgets["shirota_grd"].delete(0, "end")
    app.info_tab.form.widgets["shirota_grd"].insert(0, "54,0")
    assert app.info_tab.is_dirty()
    assert app.info_tab.save()
    saved = [c for c in app.db.calls if c[0] == "upsert_title"]
    assert saved == [("upsert_title", {PROBE_KEY: "p1", "shirota_grd": 54.0})]
    assert "захавана палёў: 1" in status_text(app)
    assert not app.info_tab.is_dirty()


def test_info_tab_rejects_bad_numbers_inline(app):
    app.select_probe("p1")
    app.info_tab.form.widgets["shirota_grd"].delete(0, "end")
    app.info_tab.form.widgets["shirota_grd"].insert(0, "abc")
    assert not app.info_tab.save()
    assert not [c for c in app.db.calls if c[0] == "upsert_title"]
    assert "Шырата" in app.info_tab.error_label.cget("text")
    assert app.info_tab.form.labels["shirota_grd"].cget("style") == "Error.TLabel"


def test_unsaved_changes_guard(app, monkeypatch):
    app.select_probe("p1")
    app.info_tab.form.widgets["glavnaya_poroda"].set("Е")
    monkeypatch.setattr(feedback.messagebox, "askyesnocancel", lambda *a, **kw: None)  # адмена
    assert not app.select_probe("p2")
    assert app.current_probe == "p1"
    monkeypatch.setattr(feedback.messagebox, "askyesnocancel", lambda *a, **kw: True)  # захаваць
    assert app.select_probe("p2")
    assert app.current_probe == "p2"
    assert ("upsert_title", {PROBE_KEY: "p1", "glavnaya_poroda": "Е"}) in app.db.calls


def test_only_filled_hides_empty_fields(app):
    app.select_probe("p1")
    app.info_tab.form.show_only_filled(True)
    assert app.info_tab.form.widgets["tip_lesa"].winfo_manager() == ""
    assert app.info_tab.form.widgets["shirota_grd"].winfo_manager() == "grid"
    assert app.info_tab.form.widgets[PROBE_KEY].winfo_manager() == "grid"  # абавязковае поле заўсёды відаць
    app.info_tab.form.show_only_filled(False)
    assert app.info_tab.form.widgets["tip_lesa"].winfo_manager() == "grid"


def test_crn_tab_year_filter_and_add(app):
    app.select_probe("p1")
    app.crn_tab.year_from.insert(0, "1901")
    app.crn_tab.load()
    assert len(app.crn_tab.tree.get_children()) == 1
    app.crn_tab.entries["year"].insert(0, "1902")
    app.crn_tab.entries["raw"].insert(0, "1,5")
    app.crn_tab.add_record()
    assert ("upsert_crn", "p1", CrnRow(1902, raw=1.5)) in app.db.calls
    assert "1902" in status_text(app)
    app.crn_tab.year_from.delete(0, "end")
    app.crn_tab.year_from.insert(0, "x")
    app.crn_tab.load()
    assert app.crn_tab.info.cget("text").startswith("Гады фільтра")


def test_filter_tab_applies_criteria(app):
    app.filter_tab.combos["drevesnaya_poroda"].set("Pinus sylvestris L.")
    app.filter_tab.year_to.insert(0, "1950")
    app.filter_tab.crn_vars["ars"].set(False)
    app.filter_tab.apply()
    criteria = app.db.calls[-1][1]
    assert criteria.drevesnaya_poroda == "Pinus sylvestris L."
    assert criteria.year_to == 1950 and criteria.crn_columns == ("raw", "std", "res")
    assert len(app.filter_tab.result.get_children()) == 1
    assert "ПП: 1" in app.filter_tab.status.cget("text")


def test_dialogs_build_and_parse_clipboard(app):
    from dendrobase.ui.dialogs import AddProbeDialog, CrnDialog, SeriesDialog, SqlQueryDialog
    add = AddProbeDialog(app.root, app.db, on_change=app.on_data_changed, notify=app.notify)
    add.save_only()  # без кода ПП
    assert "абавязковае" in add.error_label.cget("text") and add.saved_probe is None
    add.form.widgets[PROBE_KEY].insert(0, "p3")
    add.form.widgets["shirota_grd"].insert(0, "52.5")
    add.save_only()
    assert "p3" in app.db.titles and app.current_probe == "p3"
    assert app.listed_probes() == ["p1", "p2", "p3"]

    crn = CrnDialog(app.root, app.db, "p3", notify=app.notify)
    app.root.clipboard_clear()
    app.root.clipboard_append("1900\t5\t1,2\n1901\t6\t1.3\n")
    crn.paste()
    assert [r.year for r in crn.rows] == [1900, 1901]
    crn.save_only()
    assert app.db.calls[-1][0] == "upsert_crn_rows"

    series = SeriesDialog(app.root, app.db, "p3", notify=app.notify)
    app.root.clipboard_clear()
    app.root.clipboard_append("year\t1\t1a\n1900\t1.5\t1.6\n")
    series.paste()
    assert list(series.tree["columns"]) == ["year", "1", "1a"]
    series.save()
    assert app.db.calls[-1][0] == "upsert_series_values"

    sql = SqlQueryDialog(app.root, app.db)
    sql.text.delete("1.0", "end")
    sql.text.insert("1.0", "SELECT 1 AS n")
    sql.execute()
    assert list(sql.result["columns"]) == ["n"]
    sql.dialog.destroy()


def test_sorting_table_by_header(app):
    app.select_probe("p1")
    from dendrobase.ui.widgets import sort_tree
    sort_tree(app.crn_tab.tree, "year", reverse=True)
    years = [app.crn_tab.tree.item(i, "values")[0] for i in app.crn_tab.tree.get_children()]
    assert years == ["1901", "1900"]
    assert app.crn_tab.tree.heading("year", "text") == "year ▼"


def test_exit_saves_state_and_closes_database(app, isolated_ui_state):
    app.select_probe("p2")
    app.on_exit()
    assert ("close",) in app.db.calls
    from dendrobase.ui.ui_state import load_ui_state
    assert load_ui_state(isolated_ui_state)["last_probe"] == "p2"


def test_main_starts_with_real_database(test_db, tmp_path, monkeypatch, quiet_messages, isolated_ui_state):
    """Поўная праводка: .env -> налады -> БД -> праверка схемы -> галоўнае акно."""
    from dendrobase.__main__ import main
    monkeypatch.setenv("DENDROBASE_DB_NAME", test_db.settings.dbname)
    monkeypatch.setenv("DENDROBASE_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(tk.Tk, "mainloop", lambda self: self.destroy())
    assert main() == 0
    assert (tmp_path / "dendrobase.log").exists()
    assert quiet_messages == []


def test_main_reports_connection_failure(tmp_path, monkeypatch, quiet_messages, isolated_ui_state):
    from dendrobase.__main__ import main
    monkeypatch.setenv("DENDROBASE_DB_NAME", "dendrobase_no_such_database")
    monkeypatch.setenv("DENDROBASE_LOG_DIR", str(tmp_path))
    assert main() == 1
    assert quiet_messages[-1][0] == "Няма злучэння з базай даных"
    assert ".env" in quiet_messages[-1][1]


def test_hints_go_to_status_bar_and_dialog_hint_row(app):
    from dendrobase.ui.dialogs import AddProbeDialog
    app.notify("захавана", kind="ok")
    before = app.status.message.cget("text")
    app.info_tab.save_button.event_generate("<Enter>")
    assert app.status.message.cget("text").startswith("Ctrl+S")
    app.info_tab.save_button.event_generate("<Leave>")
    assert app.status.message.cget("text") == before  # паведамленне вярнулася

    add = AddProbeDialog(app.root, app.db)
    label = add.form.labels["shirota_grd"]
    label.event_generate("<Enter>")
    assert "градусы" in add.hint.cget("text")
    assert app.status.message.cget("text") == before  # падказка дыялога не трапляе ў галоўнае акно
    label.event_generate("<Leave>")
    assert add.hint.cget("text") == ""
    assert add.dialog.grab_status() is None  # дыялогі не мадальныя
    add.dialog.destroy()


def test_same_dialog_is_not_opened_twice(app):
    app.add_new_probe()
    first = app._dialogs["new_probe"]
    app.add_new_probe()
    assert app._dialogs["new_probe"] is first
    first.destroy()
    app.add_new_probe()
    assert app._dialogs["new_probe"] is not first
    app._dialogs["new_probe"].destroy()


def test_button_clicks_across_surface_after_resize(app):
    """Правярае Tcl-bindings і макет; натыўныя падзеі macOS патрабуюць асобнай праверкі мышшу."""
    app.select_probe("p1")
    button = app.info_tab.save_button
    clicks = []
    button.configure(command=lambda: clicks.append(True))
    app.root.deiconify()
    for width in (1400, 1000):
        app.root.geometry(f"{width}x740")
        app.root.update_idletasks()
        w, h = button.winfo_width(), button.winfo_height()
        for x, y in ((5, h // 2), (w // 2, h // 2), (w - 6, h // 2),
                     (w // 2, 5), (w // 2, h - 6)):
            before = len(clicks)
            button.event_generate("<Enter>", x=x, y=y)
            app.root.update_idletasks()  # падказка таксама не павінна зрушыць кнопку
            assert app.root.winfo_containing(button.winfo_rootx() + x, button.winfo_rooty() + y) is button
            button.event_generate("<ButtonPress-1>", x=x, y=y)
            button.event_generate("<ButtonRelease-1>", x=x, y=y)
            assert len(clicks) == before + 1
            button.event_generate("<Leave>", x=x, y=y)

    button.state(["disabled"])
    button.event_generate("<ButtonPress-1>", x=w // 2, y=h // 2)
    button.event_generate("<ButtonRelease-1>", x=w // 2, y=h // 2)
    assert len(clicks) == 10


def test_settings_dialog_switches_language_and_theme_live(app, isolated_ui_state):
    from dendrobase import i18n
    from dendrobase.ui.preferences import Preferences, load_preferences
    from dendrobase.ui.theme import PALETTE, is_dark
    app.select_probe("p1")
    app.notify("тэст", kind="info")  # адкладзеная ачыстка не павінна зваліцца пасля перабудовы
    old_info_tab = app.info_tab

    app.open_settings()
    dialog = app._dialogs["settings"]
    assert app.menubar.entrycget(0, "label") == "Файл"

    applied = app.apply_preferences(Preferences(language="en", theme="dark"))
    assert applied and i18n.get_language() == "en"
    assert load_preferences(isolated_ui_state) == Preferences(language="en", theme="dark")
    assert app.menubar.entrycget(0, "label") == "File"
    assert app.notebook.tab(0, "text").strip() == "Plot info"
    assert app.info_tab is not old_info_tab and not old_info_tab.frame.winfo_exists()
    assert app.current_probe == "p1" and app.info_tab.title_label.cget("text") == "p1"
    assert app.info_tab.form.labels["shirota_grd"].cget("text").startswith("Latitude")
    assert "Pine" in app.info_tab.subtitle.cget("text")
    assert app.status.probe.cget("text") == "Plot: p1"
    assert is_dark(PALETTE["table_bg"]) and not is_dark(PALETTE["text"])
    assert dialog.winfo_exists()  # дыялог налад жыве, пакуль карыстальнік яго не зачыніў
    app.root.update()  # прагнаць адкладзеныя after-калбэкі старога радка стану

    assert app.apply_preferences(Preferences(language="be", theme="light"))
    assert app.menubar.entrycget(0, "label") == "Файл"
    assert not is_dark(PALETTE["table_bg"])
    assert app.apply_preferences(app.preferences)  # без змен нічога не перабудоўваецца
    dialog.destroy()


def test_settings_dialog_collects_values_and_closes_on_apply(app):
    from dendrobase.ui.dialogs import SettingsDialog
    from dendrobase.ui.preferences import Preferences
    received = []
    dialog = SettingsDialog(app.root, Preferences(language="be", theme="system"), on_apply=lambda p: (received.append(p), True)[1])
    assert dialog.language.get() == "be" and dialog.theme.get() == "system"
    dialog.language.set("en")
    dialog.theme.set("dark")
    dialog.save()
    assert received == [Preferences(language="en", theme="dark")]
    assert not dialog.dialog.winfo_exists()

    refused = SettingsDialog(app.root, Preferences(), on_apply=lambda p: False)
    refused.save()
    assert refused.dialog.winfo_exists()  # адмова (незахаваныя змены) пакідае дыялог адкрытым
    refused.dialog.destroy()


def test_unsaved_changes_block_preference_change(app, monkeypatch):
    from dendrobase.ui.preferences import Preferences
    app.select_probe("p1")
    app.info_tab.form.widgets["shirota_grd"].insert(0, "1")
    monkeypatch.setattr(feedback.messagebox, "askyesnocancel", lambda *a, **kw: None)  # адмена
    assert not app.apply_preferences(Preferences(language="en"))
    assert app.preferences.language == "be" and app.info_tab.is_dirty()


def test_main_starts_in_english_by_default(test_db, tmp_path, monkeypatch, quiet_messages, isolated_ui_state):
    from dendrobase import i18n
    from dendrobase.__main__ import main
    isolated_ui_state.write_text("{}", encoding="utf-8")  # першы запуск: налад яшчэ няма
    monkeypatch.setenv("DENDROBASE_DB_NAME", test_db.settings.dbname)
    monkeypatch.setenv("DENDROBASE_LOG_DIR", str(tmp_path))
    seen = {}
    monkeypatch.setattr(tk.Tk, "mainloop", lambda self: (seen.update(language=i18n.get_language()), self.destroy()))
    assert main() == 0
    assert seen["language"] == "en"


# ----------------------------------------------------------------- імпарт з Excel

def pump_until_finished(app, dialog, timeout: float = 20.0) -> None:
    """Пракручваць цыкл падзей Tk, пакуль фонавы паток імпарту не скончыцца і акно не забярэ вынік."""
    deadline = time.monotonic() + timeout
    while dialog.running and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.02)
    assert not dialog.running, "імпарт не завяршыўся за адведзены час"


def tools_menu_labels(app) -> list[str]:
    tools = app.menubar.nametowidget(app.menubar.entrycget(2, "menu"))
    return [tools.entrycget(i, "label") for i in range(tools.index("end") + 1) if tools.type(i) == "command"]


def test_import_menu_item_opens_dialog_once(app):
    assert tools_menu_labels(app)[0] == "Імпарт даных…"
    dialog = app.open_import()
    assert dialog is not None and dialog.dialog is app._dialogs["import"]
    assert dialog.folder_var.get() == ""  # у наладах тэсту DENDROBASE_EXCEL_FOLDER не зададзена
    assert dialog.stop_button.instate(["disabled"]) and not dialog.start_button.instate(["disabled"])
    assert app.open_import() is None  # другі раз толькі падымае існуючае акно
    dialog.dialog.destroy()
    assert app.apply_preferences(app.preferences.__class__(language="en", theme=app.preferences.theme))
    assert tools_menu_labels(app)[0] == "Import data…"


def test_import_dialog_requires_existing_folder(app, tmp_path):
    from dendrobase.ui.import_dialog import ImportDialog
    calls = []
    dialog = ImportDialog(app.root, app.settings, runner=lambda *a, **k: calls.append(a))
    dialog.folder_var.set("")
    dialog.start()
    assert not dialog.running and dialog.status.cget("text") == "Задайце папку з Excel-файламі."
    dialog.folder_var.set(str(tmp_path / "няма такой папкі"))
    dialog.start()
    assert not dialog.running and dialog.status.cget("text").startswith("Папка не існуе")
    assert calls == []
    dialog.dialog.destroy()


def test_import_dialog_runs_in_background_and_refreshes_main_window(app, tmp_path):
    """Дубль каманды імпарту дадае ПП у «базу»; акно паказвае ход працы, спіс ПП абнаўляецца сам."""
    from dendrobase.excel_import import FileResult, ImportProgress, ImportStats
    from dendrobase.ui.import_dialog import ImportDialog
    seen = {}

    def runner(settings, folder, *, progress, should_stop, **options):
        seen.update(settings=settings, folder=folder, options=options, thread=threading.current_thread().name)
        progress(ImportProgress("scan", total=3))
        progress(ImportProgress("file", 1, 3, "P9.xlsx", FileResult("p9", crn_rows=3, series_rows=4,
                                                                   warnings=["title, поле прапушчана: Паўната: 'x'"])))
        app.db.titles["p9"] = {PROBE_KEY: "p9", "shirota_grd": None, "dolgota_grd": None, "glavnaya_poroda": "Е",
                               "tip_lesa": None, "pervyy_god": 1800, "posledniy_god": 1900, "geom": None}
        progress(ImportProgress("unchanged", 2, 3, "p1.xlsx"))
        progress(ImportProgress("file", 3, 3, "bad.xlsx", FileResult("bad", "error", error="памылка БД: штучная")))
        progress(ImportProgress("journal", count=1))
        progress(ImportProgress("geometry"))
        return ImportStats(files=2, skipped=1, title_updated=1, crn_rows=3, crn_files=1, series_rows=4, series_files=1,
                           warnings=1, errors=1)

    app.select_probe("p1")
    dialog = ImportDialog(app.root, app.settings, on_change=app.on_import_finished, notify=app.notify, runner=runner)
    dialog.folder_var.set(str(tmp_path))
    dialog.overwrite_var.set(True)
    dialog.start()
    assert dialog.running and dialog.start_button.instate(["disabled"]) and not dialog.stop_button.instate(["disabled"])
    assert dialog.folder_entry.instate(["disabled"]) and dialog.option_checks[0].instate(["disabled"])
    pump_until_finished(app, dialog)

    assert seen["settings"] is app.settings and seen["folder"] == tmp_path and seen["thread"] != "MainThread"
    assert seen["options"] == {"overwrite": True, "reimport": False, "journal": True, "geometry": True}
    text = dialog.log_text()
    assert f"Папка: {tmp_path}" in text
    assert "Знойдзена Excel-файлаў: 3" in text
    assert "P9.xlsx → ПП p9: CRN 3 радкоў, SERIES 4 значэнняў" in text
    assert "    ⚠ title, поле прапушчана: Паўната: 'x'" in text
    assert "p1.xlsx: без змен, прапушчаны" in text
    assert "bad.xlsx: памылка БД: штучная" in text
    assert "№ журнала абноўлены для 1 ПП." in text and "геаметрыя не абноўлена" in text
    assert float(dialog.progress["value"]) == 3 and float(dialog.progress["maximum"]) == 3
    assert dialog.counter.cget("text") == "3 з 3"
    assert dialog.status.cget("text").startswith("Імпарт завершаны з памылкамі. Файлаў: 2; прапушчана ўжо апрацаваных: 1")
    assert str(dialog.status.cget("style")) == "Warn.TLabel"
    assert dialog.stats.title_updated == 1 and dialog.error is None
    assert not dialog.start_button.instate(["disabled"]) and dialog.stop_button.instate(["disabled"])

    assert app.listed_probes() == ["p1", "p2", "p9"]  # галоўнае акно перачытала базу само
    assert app.probe_list.item("p9", "values")[1:] == ("Е", "1800–1900")
    assert app.current_probe == "p1" and app.info_tab.title_label.cget("text") == "p1"
    assert "Імпарт завершаны з памылкамі" in status_text(app)
    dialog.dialog.destroy()


def test_import_dialog_keeps_unsaved_form_edits_on_refresh(app, tmp_path):
    from dendrobase.excel_import import ImportStats
    from dendrobase.ui.import_dialog import ImportDialog
    app.select_probe("p1")
    app.info_tab.form.widgets["shirota_grd"].delete(0, "end")
    app.info_tab.form.widgets["shirota_grd"].insert(0, "55")
    dialog = ImportDialog(app.root, app.settings, on_change=app.on_import_finished, notify=app.notify,
                          runner=lambda *a, **k: ImportStats())
    dialog.folder_var.set(str(tmp_path))
    dialog.start()
    pump_until_finished(app, dialog)
    assert app.info_tab.is_dirty() and app.info_tab.form.get_text("shirota_grd") == "55"
    assert dialog.status.cget("text").startswith("Імпарт завершаны. Файлаў: 0")
    dialog.dialog.destroy()


def slow_runner(started: threading.Event):
    from dendrobase.excel_import import FileResult, ImportProgress, ImportStats

    def runner(settings, folder, *, progress, should_stop, **options):
        progress(ImportProgress("scan", total=5))
        progress(ImportProgress("file", 1, 5, "a.xlsx", FileResult("a")))
        started.set()
        while not should_stop():  # «доўгі» імпарт: чакае запыту на спыненне
            time.sleep(0.01)
        return ImportStats(files=1, cancelled=True)

    return runner


def test_import_dialog_stop_button_cancels_import(app, tmp_path):
    from dendrobase.ui.import_dialog import ImportDialog
    started = threading.Event()
    dialog = ImportDialog(app.root, app.settings, on_change=app.on_import_finished, notify=app.notify,
                          runner=slow_runner(started))
    dialog.folder_var.set(str(tmp_path))
    dialog.start()
    assert started.wait(5)
    dialog.cancel()
    assert dialog.status.cget("text").startswith("Спыняецца") and dialog.stop_button.instate(["disabled"])
    pump_until_finished(app, dialog)
    assert dialog.stats.cancelled
    assert dialog.status.cget("text").startswith("Імпарт спынены. Файлаў: 1")
    assert dialog.counter.cget("text") == "1 з 5"
    assert "Імпарт спынены" in status_text(app)
    assert dialog.dialog.winfo_exists()  # кнопка «Спыніць» акно не зачыняе
    dialog.dialog.destroy()


def test_closing_dialog_during_import_stops_it_and_closes_when_done(app, tmp_path, monkeypatch):
    from dendrobase.ui.import_dialog import ImportDialog
    started = threading.Event()
    dialog = ImportDialog(app.root, app.settings, notify=app.notify, runner=slow_runner(started))
    dialog.folder_var.set(str(tmp_path))
    dialog.start()
    assert started.wait(5)
    monkeypatch.setattr(feedback.messagebox, "askyesno", lambda *a, **kw: False)  # «не спыняць»
    dialog.close()
    assert dialog.running and dialog.dialog.winfo_exists()
    monkeypatch.setattr(feedback.messagebox, "askyesno", lambda *a, **kw: True)
    dialog.close()
    pump_until_finished(app, dialog)
    app.root.update()
    assert dialog.stats.cancelled and not dialog.dialog.winfo_exists()


def test_import_dialog_reports_runner_error_and_still_refreshes(app, tmp_path):
    from dendrobase.db import DatabaseError
    from dendrobase.ui.import_dialog import ImportDialog
    refreshed = []

    def runner(*args, **kwargs):
        raise DatabaseError("У базе няма табліц: crn")

    dialog = ImportDialog(app.root, app.settings, on_change=lambda: refreshed.append(True), notify=app.notify,
                          runner=runner)
    dialog.folder_var.set(str(tmp_path))
    dialog.start()
    pump_until_finished(app, dialog)
    assert dialog.status.cget("text") == "Імпарт спынены памылкай: У базе няма табліц: crn"
    assert str(dialog.status.cget("style")) == "Error.TLabel"
    assert isinstance(dialog.error, DatabaseError) and dialog.stats is None
    assert refreshed == [True] and "няма табліц: crn" in status_text(app)
    assert not dialog.start_button.instate(["disabled"])  # можна выправіць і паўтарыць
    dialog.dialog.destroy()


def test_import_dialog_with_real_database_shows_new_probe(clean_db, root, quiet_messages, isolated_ui_state, tmp_path):
    """Поўная праводка: акно імпарту → excel_import.run → PostgreSQL → спіс ПП і ўкладкі галоўнага акна."""
    from dendrobase.ui.app import DendroApp
    from tests.test_excel_import import write_workbook
    write_workbook(tmp_path / "PP01.xlsx", title=[("Широта,грд", 54.1), ("Долгота, грд", 26.2), ("Главная порода", "С")],
                   crn=[("year", "raw", "std"), (1850, 1.1, 1.0), (1851, 1.2, 0.9)],
                   series=[("year", "1", "1a"), (1850, 1.5, 1.6)])
    app = DendroApp(root, clean_db, Settings(db=clean_db.settings))
    assert app.listed_probes() == []

    dialog = app.open_import()
    dialog.folder_var.set(str(tmp_path))
    dialog.start()
    pump_until_finished(app, dialog)

    assert dialog.error is None and (dialog.stats.title_updated, dialog.stats.crn_rows, dialog.stats.series_rows) == (1, 2, 2)
    assert "PP01.xlsx → ПП pp01: CRN 2 радкоў, SERIES 2 значэнняў" in dialog.log_text()
    assert app.listed_probes() == ["pp01"]
    assert app.probe_list.item("pp01", "values")[1:] == ("С", "")
    assert app.map_tab.status.cget("text") == "ПП з каардынатамі: 1 з 1"
    assert app.select_probe("pp01")
    assert len(app.crn_tab.tree.get_children()) == 2
    assert list(app.series_tab.tree["columns"]) == ["year", "1", "1a"]
    assert "Імпарт завершаны. Файлаў: 1" in status_text(app)

    dialog.start()  # паўторны запуск: файл не змяніўся і прапускаецца па стане імпарту
    pump_until_finished(app, dialog)
    assert (dialog.stats.files, dialog.stats.skipped) == (0, 1)
    assert "PP01.xlsx: без змен, прапушчаны" in dialog.log_text()
    dialog.dialog.destroy()


def test_gui_startup_does_not_import_folium_or_pandas():
    import subprocess
    import sys
    code = ("import sys, dendrobase.ui.app; "
            "print(sorted(m for m in ('folium', 'pandas', 'numpy') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


@pytest.mark.skipif(tk.TkVersion < 9, reason="TouchpadScroll з'явіўся ў Tk 9")
def test_tk9_touchpad_scrolls_form_under_pointer(root):
    from tkinter import ttk
    from dendrobase.ui.widgets import ScrollableFrame

    root.geometry("500x300")
    scroll = ScrollableFrame(root)
    scroll.pack(fill="both", expand=True)
    labels = [ttk.Label(scroll.inner, text=f"Радок {i}") for i in range(80)]
    for label in labels:
        label.pack()
    root.deiconify()
    root.update_idletasks()
    label = labels[0]
    assert scroll.canvas.yview()[0] == 0
    # %D: high 16 bits = X, low 16 bits = signed Y; event travels from a child to bind_all.
    label.event_generate("<TouchpadScroll>", delta=(-20 & 0xffff),
                         rootx=label.winfo_rootx() + 2, rooty=label.winfo_rooty() + 2)
    assert 0 < scroll.canvas.yview()[0] < 0.1


# ----------------------------------------------------- паласа «ёсць файлы для імпарту»

def wait_for_import_check(app, timeout: float = 10.0) -> None:
    """Пракручваць цыкл падзей, пакуль фонавая праверка папкі не аддасць вынік галоўнаму акну."""
    deadline = time.monotonic() + timeout
    while app._import_check is not None and not app._import_check.finished and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.02)
    assert app._import_check is None or app._import_check.finished, "праверка папкі не скончылася"


def mark_imported(folder, name: str, probe: str) -> None:
    from dendrobase.import_state import ImportState, file_digest
    state = ImportState.load(folder)
    state.files[name] = {"status": "done", "probe": probe, "sha256": file_digest(folder / name),
                         "overwrite": False, "warnings": []}
    state.save()


@pytest.fixture()
def excel_folder(tmp_path):
    """Папка з адным ужо імпартаваным файлам (p1) і адным новым (new)."""
    folder = tmp_path / "excel"
    folder.mkdir()
    (folder / "p1.xlsx").write_bytes(b"p1")
    (folder / "new.xlsx").write_bytes(b"new")
    mark_imported(folder, "p1.xlsx", "p1")
    return folder


@pytest.fixture()
def app_with_folder(root, quiet_messages, isolated_ui_state, excel_folder):
    from dendrobase.ui.app import DendroApp
    return DendroApp(root, FakeDb(), Settings(db=DatabaseSettings(), excel_folder=excel_folder))


def test_describe_pending_variants():
    from pathlib import Path
    from dendrobase.import_state import PendingFiles
    from dendrobase.ui.import_banner import describe_pending
    folder = Path("x")
    assert describe_pending(PendingFiles(folder, new=("a",))) == "Знойдзены новыя Excel-файлы для імпарту: 1."
    assert describe_pending(PendingFiles(folder, changed=("a", "b"))) == "Знойдзены змененыя Excel-файлы для імпарту: 2."
    assert (describe_pending(PendingFiles(folder, new=("a",), changed=("b",)))
            == "Знойдзены Excel-файлы для імпарту: новых 1, змененых 1.")


def test_no_excel_folder_means_no_check_and_no_banner(app):
    assert app._import_check is None and not app.import_banner.visible


def test_startup_check_shows_banner_and_its_buttons_work(app_with_folder, excel_folder):
    app = app_with_folder
    assert not app.import_banner.visible  # пакуль паток правярае папку, паласы няма
    wait_for_import_check(app)
    banner = app.import_banner
    assert banner.visible and app._pending_import.new == ("new.xlsx",)
    assert banner.message.cget("text") == "Знойдзены новыя Excel-файлы для імпарту: 1."
    assert banner.detail.cget("text") == "Папка: excel"
    app.root.update_idletasks()
    assert banner.winfo_y() < app.status.winfo_y()  # паласа над радком стану

    banner.import_button.invoke()
    dialog = app._dialogs["import"]
    assert dialog.winfo_exists() and dialog.title() == "Імпарт даных з Excel"
    assert banner.visible  # адкрытае акно імпарту паласу не хавае: імпарт яшчэ не зроблены
    dialog.destroy()

    banner.dismiss_button.invoke()
    assert not banner.visible and app._pending_import is None


def test_banner_survives_rebuild_and_hides_after_import(app_with_folder, excel_folder):
    from dendrobase.ui.preferences import Preferences
    app = app_with_folder
    wait_for_import_check(app)
    assert app.apply_preferences(Preferences(language="en", theme=app.preferences.theme))
    assert app.import_banner.visible
    assert app.import_banner.message.cget("text") == "New Excel files found for import: 1."
    assert app.apply_preferences(Preferences(language="be", theme=app.preferences.theme))

    # імпарт прайшоў: файл запісаны ў стан, ПП з'явілася ў базе; паласа знікае пасля паўторнай праверкі
    mark_imported(excel_folder, "new.xlsx", "new")
    app.db.titles["new"] = {PROBE_KEY: "new", "shirota_grd": None, "dolgota_grd": None, "glavnaya_poroda": None,
                            "tip_lesa": None, "pervyy_god": None, "posledniy_god": None, "geom": None}
    app.on_import_finished()
    assert app.import_banner.visible  # да заканчэння праверкі старое паведамленне застаецца
    wait_for_import_check(app)
    assert not app.import_banner.visible and app._pending_import is None


def test_banner_reports_changed_files_after_cancelled_import(app_with_folder, excel_folder):
    app = app_with_folder
    wait_for_import_check(app)
    (excel_folder / "p1.xlsx").write_bytes(b"p1 changed")
    app.on_import_finished()
    wait_for_import_check(app)
    assert app.import_banner.message.cget("text") == "Знойдзены Excel-файлы для імпарту: новых 1, змененых 1."


def test_unreadable_folder_is_logged_not_shown(root, quiet_messages, isolated_ui_state, tmp_path, caplog):
    """Папка з налад знікла да старту або нечытальная: без паласы і без памылак у акне."""
    from dendrobase.ui.app import DendroApp
    missing = tmp_path / "знікла"
    app = DendroApp(root, FakeDb(), Settings(db=DatabaseSettings(), excel_folder=missing))
    assert app._import_check is None and not app.import_banner.visible
    missing.mkdir()
    app.check_pending_import()
    missing.rmdir()  # знікла ўжо падчас праверкі ў патоку
    wait_for_import_check(app)
    assert not app.import_banner.visible and "не праверана" in caplog.text
    assert quiet_messages == []
