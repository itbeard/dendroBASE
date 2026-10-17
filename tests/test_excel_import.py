from datetime import date
from pathlib import Path

import openpyxl
import pytest

from dendrobase.excel_import import (ImportStats, excel_files, fill_journal_numbers, import_folder, map_param,
                                     probe_name_from_file, read_crn_sheet, read_series_sheet, read_title_sheet)
from dendrobase.models import CrnRow, SeriesValue


def write_workbook(path: Path, *, title=None, crn=None, series=None) -> Path:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    if title is not None:
        sheet = workbook.create_sheet("Title")
        for row in title:
            sheet.append(row)
    if crn is not None:
        sheet = workbook.create_sheet("crn")
        for row in crn:
            sheet.append(row)
    if series is not None:
        sheet = workbook.create_sheet("series")
        for row in series:
            sheet.append(row)
    workbook.save(path)
    return path


@pytest.mark.parametrize("param, column", [
    ("Широта,грд", "shirota_grd"),
    ("  Главная   порода ", "glavnaya_poroda"),
    ("Коэфф. состава", "koef_sostava"),          # не блытаецца з «состав»
    ("Состав древостоя", "sostav_drevoj"),
    ("Геоботанический район (по карте)", "geobotanicheskij_rajon"),  # не «район»
    ("Район", "rayon"),
    ("N журнала", "n_journal"),
    ("Нешта невядомае", None),
    ("", None),
])
def test_map_param(param, column):
    assert map_param(param) == column


def test_probe_name_from_file():
    assert probe_name_from_file(Path("/x/PP_01.xlsx")) == "pp_01"


def test_read_title_sheet(tmp_path):
    path = write_workbook(tmp_path / "PP01.xlsx", title=[
        ("Широта,грд", 54.1), ("Долгота, грд", "26,2"), ("Главная порода", "Е"),
        ("Первый год", 1850.0), ("Дата отбора образцов", "15.08.2019"), ("Полнота", "0,8"),
        ("Коэфф. состава", 7), ("Состав", "7Е3С"), ("Квартал", 12.0), ("Возраст средний", "80-120"),
        ("N пробной площади", "іншая-назва"), (None, "пуста"), ("Площадь выдела", None),
    ])
    data, errors = read_title_sheet(path, "pp01")
    assert data["n_probnoy_ploshchadi"] == "pp01"  # з назвы файла, не з ліста
    assert data["shirota_grd"] == 54.1 and data["dolgota_grd"] == 26.2
    assert data["pervyy_god"] == 1850
    assert data["data_otbora_obraztsov"] == date(2019, 8, 15)
    assert data["polnota"] == 0.8
    assert data["koef_sostava"] == 7.0 and data["sostav_drevoj"] == "7Е3С"
    assert data["kvartal"] == "12"
    assert "vozrast" not in data and errors == ["Возраст средний: '80-120'"]
    assert "ploshchad_vydela" not in data


def test_read_crn_sheet(tmp_path):
    path = write_workbook(tmp_path / "pp.xlsx", crn=[
        ("Year", "num", "RAW", "std", "res", "ars", "lishniy"),
        (1850, 10, 1.1, 1.0, 0.99, 1.01, 5),
        (1851, None, "1,2", None, None, None, None),
        (1851, 1, 9, 9, 9, 9, 9),
        (None, 1, 1, 1, 1, 1, 1),
        ("abc", 1, 1, 1, 1, 1, 1),
    ])
    rows, errors = read_crn_sheet(path, "pp")
    assert rows == [CrnRow(1850, 10.0, 1.1, 1.0, 0.99, 1.01), CrnRow(1851, None, 1.2, None, None, None)]
    assert len(errors) == 2


def test_read_series_sheet(tmp_path):
    path = write_workbook(tmp_path / "pp.xlsx", series=[
        ("year", 1, "1a", "2"), (1850, 1.1, 1.2, "1,3"), (1851, 1.4, None, "x"), (None, 1, 1, 1),
    ])
    values, errors = read_series_sheet(path, "pp")
    assert values == [
        SeriesValue(1850, "1", 1.1), SeriesValue(1850, "1a", 1.2), SeriesValue(1850, "2", 1.3),
        SeriesValue(1851, "1", 1.4),
    ]
    assert len(errors) == 1 and "серыя 2" in errors[0]


class RecordingDb:
    """Дубль DatabaseManager: запамінае выклікі, нічога не піша."""

    def __init__(self, fail_for: str | None = None):
        self.calls: list[tuple] = []
        self.fail_for = fail_for

    def upsert_title(self, data):
        from dendrobase.db import DatabaseError
        if data["n_probnoy_ploshchadi"] == self.fail_for:
            raise DatabaseError("штучная памылка")
        self.calls.append(("title", dict(data)))

    def upsert_crn_rows(self, probe, rows, *, overwrite=True):
        rows = list(rows)
        self.calls.append(("crn", probe, rows, overwrite))
        return len(rows)

    def upsert_series_values(self, probe, values, *, overwrite=True):
        values = list(values)
        self.calls.append(("series", probe, values, overwrite))
        return len(values)

    def set_journal_number(self, probe, value):
        self.calls.append(("journal", probe, value))
        return 1


def test_import_folder_processes_each_file_and_counts(tmp_path):
    write_workbook(tmp_path / "PP01.xlsx", title=[("Широта,грд", 54.1)],
                   crn=[("year", "raw"), (1850, 1.1)], series=[("year", "1"), (1850, 1.5)])
    write_workbook(tmp_path / "PP02.xlsx", title=[("Главная порода", "С")])
    write_workbook(tmp_path / "no_title.xlsx", crn=[("year", "raw"), (1850, 1.1)])
    write_workbook(tmp_path / "~$PP01.xlsx", title=[("Широта,грд", 1)])
    write_workbook(tmp_path / "dendro_point_living.xlsx", title=[("Широта,грд", 1)])
    (tmp_path / "notes.txt").write_text("x")

    assert [p.name for p in excel_files(tmp_path)] == ["PP01.xlsx", "PP02.xlsx", "no_title.xlsx"]

    db = RecordingDb()
    stats = import_folder(db, tmp_path)
    assert (stats.files, stats.title_updated, stats.crn_rows, stats.series_rows, stats.warnings, stats.errors) == (3, 2, 1, 1, 1, 0)
    kinds = [call[0] for call in db.calls]
    assert kinds == ["title", "crn", "series", "title"]
    assert db.calls[1][3] is False  # па змаўчанні існуючыя радкі не перапісваюцца
    assert db.calls[0][1]["n_probnoy_ploshchadi"] == "pp01"


def test_import_folder_continues_after_database_error(tmp_path):
    write_workbook(tmp_path / "bad.xlsx", title=[("Широта,грд", 1)])
    write_workbook(tmp_path / "good.xlsx", title=[("Широта,грд", 2)])
    db = RecordingDb(fail_for="bad")
    stats = import_folder(db, tmp_path)
    assert stats.errors == 1 and stats.title_updated == 1
    assert "памылак: 1" in stats.summary()


def test_fill_journal_numbers(tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Название пробной площади", "N журнала"])
    sheet.append(["PP01", 42])
    sheet.append(["PP02", 0])
    sheet.append([None, 7])
    path = tmp_path / "dendro_point_living.xlsx"
    workbook.save(path)
    db = RecordingDb()
    assert fill_journal_numbers(db, path) == 1
    assert db.calls == [("journal", "PP01", "42")]


def test_fill_journal_numbers_requires_columns(tmp_path):
    workbook = openpyxl.Workbook()
    workbook.active.append(["a", "b"])
    path = tmp_path / "dendro_point_living.xlsx"
    workbook.save(path)
    with pytest.raises(ValueError):
        fill_journal_numbers(RecordingDb(), path)


def test_import_stats_summary_mentions_all_counters():
    text = ImportStats(files=3, title_updated=2, crn_rows=5, series_rows=7, warnings=1, errors=0).summary()
    assert "Файлаў: 3" in text and "SERIES: 7" in text
