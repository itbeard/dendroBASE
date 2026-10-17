"""Інтэграцыйныя тэсты DatabaseManager на сапраўднай базе (гл. conftest.test_db)."""
from datetime import date
from decimal import Decimal

import pytest

from dendrobase.db import DatabaseError, DatabaseManager
from dendrobase.models import CrnRow, FilterCriteria, SeriesValue

pytestmark = pytest.mark.usefixtures("clean_db")


def add_probe(db: DatabaseManager, name="test01", **extra) -> None:
    db.upsert_title({"n_probnoy_ploshchadi": name, "shirota_grd": 53.9, "dolgota_grd": 27.5,
                     "glavnaya_poroda": "С", "drevesnaya_poroda": "Pinus sylvestris L.",
                     "pervyy_god": 1900, "posledniy_god": 2020, "tip_lesa": "Pinetum myrtillosum", **extra})


def test_schema_is_complete(test_db):
    assert test_db.check_schema() == []
    assert "n_probnoy_ploshchadi" in test_db.get_title_columns()
    assert test_db.table_exists("title") and not test_db.table_exists("nope")


def test_upsert_title_inserts_and_updates(test_db):
    add_probe(test_db, data_otbora_obraztsov=date(2020, 7, 1), kvartal="12")
    test_db.upsert_title({"n_probnoy_ploshchadi": "test01", "vozrast": 85.0, "polnota": None})
    info = test_db.get_probe_info("test01")
    assert info["vozrast"] == 85.0 and info["polnota"] is None
    assert info["shirota_grd"] == 53.9 and info["kvartal"] == "12"
    assert info["data_otbora_obraztsov"] == date(2020, 7, 1)
    assert test_db.get_all_probes() == ["test01"]


def test_upsert_title_with_only_key_is_noop_on_conflict(test_db):
    add_probe(test_db)
    test_db.upsert_title({"n_probnoy_ploshchadi": "test01"})
    assert test_db.get_probe_info("test01")["shirota_grd"] == 53.9


def test_upsert_title_validates_input(test_db):
    with pytest.raises(ValueError):
        test_db.upsert_title({"shirota_grd": 1})
    with pytest.raises(ValueError):
        test_db.upsert_title({"n_probnoy_ploshchadi": "x", "no_such_column": 1})
    test_db.upsert_title({"n_probnoy_ploshchadi": "x", "id": 999})  # id ігнаруецца
    assert test_db.get_probe_info("x")["id"] != 999


def test_search_is_case_insensitive(test_db):
    add_probe(test_db, "Alpha-1")
    add_probe(test_db, "beta-2")
    assert test_db.search_probes("ALPHA") == ["Alpha-1"]
    assert test_db.search_probes("") == ["Alpha-1", "beta-2"]


def test_crn_round_trip(test_db):
    add_probe(test_db)
    rows = [CrnRow(1900, 5, 1.2, 1.0, 0.98, 1.01), CrnRow(1901, 5, 1.3, 1.1, 1.02, None)]
    assert test_db.upsert_crn_rows("test01", rows) == 2
    assert test_db.upsert_crn("test01", CrnRow(1901, num=6, raw=1.35)) == 1
    assert test_db.get_crn("test01") == [CrnRow(1900, 5, 1.2, 1.0, 0.98, 1.01), CrnRow(1901, 6, 1.35, None, None, None)]
    assert test_db.get_crn("test01", year_from=1901) == [CrnRow(1901, 6, 1.35, None, None, None)]
    assert test_db.get_crn("test01", year_to=1900) == [CrnRow(1900, 5, 1.2, 1.0, 0.98, 1.01)]
    assert test_db.upsert_crn_rows("test01", [CrnRow(1900, raw=9)], overwrite=False) == 0
    assert test_db.get_crn("test01")[0].raw == 1.2
    assert test_db.delete_crn("test01", 1900) == 1
    assert [r.year for r in test_db.get_crn("test01")] == [1901]


def test_get_crn_converts_decimal_to_float(test_db, monkeypatch):
    """У сапраўднай базе калонкі crn бываюць numeric: psycopg2 аддае Decimal, графік чакае float."""
    row = (1900, Decimal("5"), Decimal("1.2"), None, Decimal("0.98"), Decimal("1.01"))
    monkeypatch.setattr(test_db, "_fetchall", lambda query, params=None: [row])
    (result,) = test_db.get_crn("test01")
    assert result == CrnRow(1900, 5.0, 1.2, None, 0.98, 1.01)
    assert all(isinstance(value, float) for value in (result.num, result.raw, result.res, result.ars))


def test_crn_requires_existing_probe(test_db):
    with pytest.raises(DatabaseError):
        test_db.upsert_crn_rows("ghost", [CrnRow(1900)])
    assert test_db.is_connected  # пасля памылкі злучэнне жывое і транзакцыя адкачана
    assert test_db.get_all_probes() == []


def test_series_matrix_uses_natural_order(test_db):
    add_probe(test_db)
    values = [SeriesValue(1900, "10", 1.0), SeriesValue(1900, "2", 1.4), SeriesValue(1901, "1a", 1.6),
              SeriesValue(1900, "1a", 1.5)]
    assert test_db.upsert_series_values("test01", values) == 4
    matrix = test_db.get_series_matrix("test01")
    assert matrix.years == [1900, 1901]
    assert matrix.series == ["1a", "2", "10"]
    assert matrix.row(1900) == [1.5, 1.4, 1.0]
    assert matrix.row(1901) == [1.6, None, None]
    assert test_db.get_series_matrix("test01", year_from=1901).years == [1901]
    assert test_db.get_series_matrix("nobody") is None
    assert [v.series_name for v in test_db.get_series_values("test01", name_filter="1A")] == ["1a", "1a"]
    assert test_db.delete_series("test01", "1a", 1900) == 1


def test_filtered_crn(test_db):
    add_probe(test_db, "p1")
    add_probe(test_db, "p2", drevesnaya_poroda="Picea abies (L.) H.Karst.")
    test_db.upsert_crn_rows("p1", [CrnRow(1900, raw=1.0, std=2.0), CrnRow(1901, raw=1.1, std=2.1)])
    test_db.upsert_crn_rows("p2", [CrnRow(1900, raw=3.0)])
    columns, rows = test_db.get_filtered_crn(FilterCriteria(
        drevesnaya_poroda="Pinus sylvestris L.", tip_lesa_keyword="myrt", year_from=1901, crn_columns=("raw",)))
    assert columns[-2:] == ["year", "raw"]
    assert rows == [("p1", "С", "Pinus sylvestris L.", None, None, None, None, "Pinetum myrtillosum", 1901, 1.1)]
    _, rows = test_db.get_filtered_crn(FilterCriteria(crn_columns=()))
    assert len(rows) == 3
    with pytest.raises(ValueError):
        FilterCriteria(crn_columns=("raw", "oops"))


def test_probe_points_skip_zero_coordinates(test_db):
    add_probe(test_db, "p1")
    add_probe(test_db, "p2", shirota_grd=0, dolgota_grd=0)
    test_db.upsert_title({"n_probnoy_ploshchadi": "p3"})
    points = test_db.get_probe_points()
    assert [p.name for p in points] == ["p1"]
    assert points[0].lat == 53.9 and points[0].first_year == 1900
    assert test_db.count_with_coords() == 2


def test_execute_sql(test_db):
    add_probe(test_db)
    result = test_db.execute_sql("SELECT n_probnoy_ploshchadi FROM title")
    assert result.has_rows and result.rows == [("test01",)]
    result = test_db.execute_sql("UPDATE title SET oblast = 'x'")
    assert not result.has_rows and result.rowcount == 1
    with pytest.raises(DatabaseError):
        test_db.execute_sql("SELECT * FROM nope")


def test_ensure_constraints_is_idempotent(test_db):
    messages = test_db.ensure_constraints()
    assert all("ужо ёсць" in m or "прапушчана" in m or "дададзена" in m for m in messages)
    assert any("PRIMARY KEY title(id): ужо ёсць" == m for m in messages)
    again = test_db.ensure_constraints()
    assert not any("дададзена" in m for m in again if "INDEX" not in m)


def test_journal_and_zone_normalization(test_db):
    add_probe(test_db, "PP01", geobotanicheskaya_zona="Евразиатская таежная")
    assert test_db.set_journal_number("pp01", "42") == 1
    assert test_db.get_probe_info("PP01")["n_journal"] == "42"
    assert test_db.normalize_zones() == 1
    assert test_db.get_probe_info("PP01")["geobotanicheskaya_zona"] == "Евразиатская таёжная"


def test_geometry(test_db):
    add_probe(test_db)
    if not (test_db.has_postgis() and test_db.has_geometry_column()):
        with pytest.raises(DatabaseError):
            test_db.update_geometry("test01")
        pytest.skip("PostGIS не ўсталяваны")
    assert test_db.update_geometry("test01") == 1
    assert test_db.update_geometry_all(only_missing=True) == 0
    assert test_db.update_geometry_all() == 1
    with pytest.raises(DatabaseError):
        test_db.assign_geobotany_from_polygons("no_such_table")


def test_reconnects_after_connection_is_closed(test_db):
    test_db.close()
    assert not test_db.is_connected
    assert test_db.get_all_probes() == []
    assert test_db.is_connected


def test_list_probes_summaries(test_db):
    add_probe(test_db, "Alpha-1", kolichestvo_derevev_v_shkale_sht=25)
    add_probe(test_db, "beta-2", shirota_grd=None, dolgota_grd=None)
    summaries = test_db.list_probes()
    assert [s.name for s in summaries] == ["Alpha-1", "beta-2"]
    first, second = summaries
    assert first.poroda == "С" and first.years == "1900–2020" and first.trees == 25 and first.has_coords
    assert not second.has_coords
    assert [s.name for s in test_db.list_probes("ALPHA")] == ["Alpha-1"]


def test_excel_import_skips_unchanged_files_until_database_is_emptied(test_db, tmp_path):
    """Стан імпарту прапускае нязменны файл, але не пасля ачысткі базы (ПП больш няма)."""
    from dendrobase.excel_import import import_folder
    from tests.test_excel_import import write_workbook

    write_workbook(tmp_path / "PPDB.xlsx", title=[("Широта,грд", 54.1)], crn=[("year", "raw"), (1850, 1.1)])
    first = import_folder(test_db, tmp_path)
    assert (first.files, first.skipped, first.crn_rows) == (1, 0, 1)
    assert test_db.get_all_probes() == ["ppdb"]
    assert import_folder(test_db, tmp_path).skipped == 1

    with test_db.transaction() as cur:
        cur.execute("TRUNCATE series, crn, title RESTART IDENTITY CASCADE")
    again = import_folder(test_db, tmp_path)
    assert (again.files, again.skipped, again.crn_rows) == (1, 0, 1)
