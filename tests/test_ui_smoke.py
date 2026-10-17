"""Дымавыя тэсты інтэрфейсу: віджэты будуюцца і рэагуюць, БД падменена дублем.

Патрэбны дысплей (Tk). Без яго тэсты прапускаюцца.
"""
from __future__ import annotations

import tkinter as tk

import pytest

from dendrobase.config import DatabaseSettings, Settings
from dendrobase.models import CrnRow, ProbePoint, QueryResult, SeriesMatrix
from dendrobase.reference import PROBE_KEY
from dendrobase.ui import feedback


class FakeDb:
    def __init__(self):
        self.calls = []
        self.titles = {
            "p1": {"id": 1, PROBE_KEY: "p1", "shirota_grd": 53.9, "dolgota_grd": 27.5, "glavnaya_poroda": "С",
                   "tip_lesa": None, "pervyy_god": 1900, "geom": None},
            "p2": {"id": 2, PROBE_KEY: "p2", "shirota_grd": None, "dolgota_grd": None, "glavnaya_poroda": None,
                   "tip_lesa": None, "pervyy_god": None, "geom": None},
        }

    def get_title_columns(self, refresh=False):
        return ["id", PROBE_KEY, "shirota_grd", "dolgota_grd", "glavnaya_poroda", "tip_lesa", "pervyy_god", "geom"]

    def get_all_probes(self):
        return sorted(self.titles)

    def search_probes(self, text):
        return [p for p in self.get_all_probes() if text.lower() in p.lower()]

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
        return [ProbePoint("p1", 53.9, 27.5, "С", 1900, 2020)]

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
    """Усе messagebox не блакуюць тэст, а запісваюцца."""
    shown = []
    for name in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(feedback.messagebox, name, lambda title, message, **kw: shown.append((title, message)))
    monkeypatch.setattr(feedback.messagebox, "askyesno", lambda *a, **kw: True)
    return shown


@pytest.fixture()
def app(root, quiet_messages):
    from dendrobase.ui.app import DendroApp
    settings = Settings(db=DatabaseSettings())
    return DendroApp(root, FakeDb(), settings)


def test_app_builds_and_lists_probes(app):
    assert app.listbox.size() == 2
    assert app.notebook.index("end") == 5


def test_selecting_probe_fills_tabs(app):
    app.select_probe("p1")
    app.root.update_idletasks()
    assert app.info_tab.form.get_text(PROBE_KEY) == "p1"
    assert app.info_tab.form.get_text("shirota_grd") == "53.9"
    assert len(app.crn_tab.tree.get_children()) == 2
    assert list(app.series_tab.tree["columns"]) == ["year", "1a", "2"]
    app.select_probe("p2")
    assert app.series_tab.info.cget("text") == "Няма даных"


def test_search_filters_list(app):
    app.search.insert(0, "P2")
    app.refresh_probes()
    assert app.listbox.get(0, "end") == ("p2",)


def test_info_tab_saves_only_changed_fields(app, quiet_messages):
    app.select_probe("p1")
    app.info_tab.form.widgets["shirota_grd"].delete(0, "end")
    app.info_tab.form.widgets["shirota_grd"].insert(0, "54,0")
    app.info_tab.save()
    saved = [c for c in app.db.calls if c[0] == "upsert_title"]
    assert saved == [("upsert_title", {PROBE_KEY: "p1", "shirota_grd": 54.0})]
    assert quiet_messages[-1][0] == "Змены захаваны"


def test_info_tab_rejects_bad_numbers(app, quiet_messages):
    app.select_probe("p1")
    app.info_tab.form.widgets["shirota_grd"].delete(0, "end")
    app.info_tab.form.widgets["shirota_grd"].insert(0, "abc")
    app.info_tab.save()
    assert not [c for c in app.db.calls if c[0] == "upsert_title"]
    assert quiet_messages[-1][0] == "Праверце значэнні"


def test_crn_tab_year_filter_and_add(app, quiet_messages):
    app.select_probe("p1")
    app.crn_tab.year_from.insert(0, "1901")
    app.crn_tab.load()
    assert len(app.crn_tab.tree.get_children()) == 1
    app.crn_tab.entries["year"].insert(0, "1902")
    app.crn_tab.entries["raw"].insert(0, "1,5")
    app.crn_tab.add_record()
    assert ("upsert_crn", "p1", CrnRow(1902, raw=1.5)) in app.db.calls
    app.crn_tab.year_from.delete(0, "end")
    app.crn_tab.year_from.insert(0, "x")
    app.crn_tab.load()
    assert quiet_messages[-1][1].startswith("Гады фільтра")


def test_filter_tab_applies_criteria(app):
    app.filter_tab.combos["drevesnaya_poroda"].set("Pinus sylvestris L.")
    app.filter_tab.year_to.insert(0, "1950")
    app.filter_tab.crn_vars["ars"].set(False)
    app.filter_tab.apply()
    criteria = app.db.calls[-1][1]
    assert criteria.drevesnaya_poroda == "Pinus sylvestris L."
    assert criteria.year_to == 1950 and criteria.crn_columns == ("raw", "std", "res")
    assert len(app.filter_tab.result.get_children()) == 1


def test_dialogs_build_and_parse_clipboard(app, quiet_messages):
    from dendrobase.ui.dialogs import AddProbeDialog, CrnDialog, SeriesDialog, SqlQueryDialog
    add = AddProbeDialog(app.root, app.db, on_change=app.on_data_changed)
    add.form.widgets[PROBE_KEY].insert(0, "p3")
    add.form.widgets["shirota_grd"].insert(0, "52.5")
    add.save_only()
    assert "p3" in app.db.titles and app.current_probe == "p3"

    crn = CrnDialog(app.root, app.db, "p3")
    app.root.clipboard_clear()
    app.root.clipboard_append("1900\t5\t1,2\n1901\t6\t1.3\n")
    crn.paste()
    assert [r.year for r in crn.rows] == [1900, 1901]
    crn.save_only()
    assert app.db.calls[-1][0] == "upsert_crn_rows"

    series = SeriesDialog(app.root, app.db, "p3")
    app.root.clipboard_clear()
    app.root.clipboard_append("year\t1\t1a\n1900\t1.5\t1.6\n")
    series.paste()
    assert list(series.tree["columns"]) == ["year", "1", "1a"]
    series.save()
    assert app.db.calls[-1][0] == "upsert_series_values"

    sql = SqlQueryDialog(app.root, app.db)
    sql.text.insert("1.0", "SELECT 1 AS n")
    sql.execute()
    assert list(sql.result["columns"]) == ["n"]
    sql.dialog.destroy()


def test_exit_closes_database(app):
    app.on_exit()
    assert ("close",) in app.db.calls


def test_main_starts_with_real_database(test_db, tmp_path, monkeypatch, quiet_messages):
    """Поўная праводка: .env -> налады -> БД -> праверка схемы -> галоўнае акно."""
    from dendrobase.__main__ import main
    monkeypatch.setenv("DENDROBASE_DB_NAME", test_db.settings.dbname)
    monkeypatch.setenv("DENDROBASE_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(tk.Tk, "mainloop", lambda self: self.destroy())
    assert main() == 0
    assert (tmp_path / "dendrobase.log").exists()
    assert quiet_messages == []


def test_main_reports_connection_failure(tmp_path, monkeypatch, quiet_messages):
    from dendrobase.__main__ import main
    monkeypatch.setenv("DENDROBASE_DB_NAME", "dendrobase_no_such_database")
    monkeypatch.setenv("DENDROBASE_LOG_DIR", str(tmp_path))
    assert main() == 1
    assert quiet_messages[-1][0] == "Няма злучэння з базай даных"
    assert ".env" in quiet_messages[-1][1]
