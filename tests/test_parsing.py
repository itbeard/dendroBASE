from datetime import date

import pytest

from dendrobase.models import CrnRow, SeriesValue
from dendrobase.parsing import (cell_to_text, coerce_title_values, natural_key, parse_clipboard_table,
                                parse_crn_table, parse_date, parse_float, parse_int, parse_series_table,
                                values_equal)


@pytest.mark.parametrize("text, expected", [
    ("1.5", 1.5), ("1,5", 1.5), (" 2 ", 2.0), ("1 234,5", 1234.5), ("", None), (None, None),
    ("-0.25", -0.25), (3, 3.0), (2.5, 2.5),
])
def test_parse_float(text, expected):
    assert parse_float(text) == expected


@pytest.mark.parametrize("text", ["abc", "1.2.3", "80-120", True])
def test_parse_float_rejects_garbage(text):
    with pytest.raises(ValueError):
        parse_float(text)


def test_parse_int():
    assert parse_int("1900") == 1900
    assert parse_int("1900.0") == 1900
    assert parse_int(1900.0) == 1900
    assert parse_int("") is None
    with pytest.raises(ValueError):
        parse_int("1900.5")


@pytest.mark.parametrize("text, expected", [
    ("15.08.2019", date(2019, 8, 15)),
    ("2019-08-15", date(2019, 8, 15)),
    ("2019-08-15 00:00:00", date(2019, 8, 15)),
    ("15.08.19", date(2019, 8, 15)),
    ("15/08/2019", date(2019, 8, 15)),
    ("", None),
    (date(2020, 1, 2), date(2020, 1, 2)),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_parse_date_rejects_garbage():
    with pytest.raises(ValueError):
        parse_date("лета 2019")


def test_cell_to_text():
    assert cell_to_text(12.0) == "12"
    assert cell_to_text(12.5) == "12.5"
    assert cell_to_text(" 3а ") == "3а"
    assert cell_to_text(None) == ""


def test_coerce_title_values_by_field_kind():
    data, errors = coerce_title_values({
        "n_probnoy_ploshchadi": " pp01 ",
        "shirota_grd": "53,9",
        "pervyy_god": "1900.0",
        "data_otbora_obraztsov": "01.07.2020",
        "kvartal": 12.0,
        "opisanie": "",
        "vozrast": "80-120",
    })
    assert data["n_probnoy_ploshchadi"] == "pp01"
    assert data["shirota_grd"] == 53.9
    assert data["pervyy_god"] == 1900
    assert data["data_otbora_obraztsov"] == date(2020, 7, 1)
    assert data["kvartal"] == "12"
    assert data["opisanie"] is None
    assert "vozrast" not in data
    assert errors == ["Сярэдні ўзрост: '80-120'"]


def test_values_equal():
    assert values_equal(None, "")
    assert values_equal(1900, 1900.0)
    assert values_equal("С", "С ")
    assert values_equal(date(2020, 7, 1), "01.07.2020")
    assert not values_equal(53.9, 53.91)
    assert not values_equal(None, "x")
    assert not values_equal("x", None)


def test_parse_clipboard_table_handles_tabs_crlf_and_blank_lines():
    text = "year\tnum\traw\r\n1900\t5\t1,2\r\n\r\n1901\t\t1.3\r\n"
    assert parse_clipboard_table(text) == [["year", "num", "raw"], ["1900", "5", "1,2"], ["1901", "", "1.3"]]
    assert parse_clipboard_table("1900 5 1.2\n1901 6 1.3") == [["1900", "5", "1.2"], ["1901", "6", "1.3"]]


def test_parse_crn_table_positional_without_header():
    rows, errors = parse_crn_table([["1900", "5", "1,2", "1.0", "0.98", "1.01"], ["1901", "6"]])
    assert errors == []
    assert rows == [CrnRow(1900, 5.0, 1.2, 1.0, 0.98, 1.01), CrnRow(1901, 6.0, None, None, None, None)]


def test_parse_crn_table_maps_columns_by_header_names():
    rows, errors = parse_crn_table([["year", "std", "raw"], ["1900", "1.0", "1.2"]])
    assert errors == []
    assert rows == [CrnRow(year=1900, raw=1.2, std=1.0)]


def test_parse_crn_table_reports_bad_rows():
    rows, errors = parse_crn_table([["abc", "1"], ["1900", "x"], ["1901", "2"]])
    assert [r.year for r in rows] == [1901]
    assert len(errors) == 1 and "радок 2" in errors[0]


def test_parse_series_table():
    rows = [["year", "1", "1a", "2"], ["1900", "1.5", "", "1,4"], ["1901", "1.6", "1.7", "x"]]
    values, errors = parse_series_table(rows)
    assert values == [
        SeriesValue(1900, "1", 1.5), SeriesValue(1900, "2", 1.4),
        SeriesValue(1901, "1", 1.6), SeriesValue(1901, "1a", 1.7),
    ]
    assert len(errors) == 1 and "серыя 2" in errors[0]


def test_parse_series_table_rejects_duplicate_names_and_missing_header():
    _, errors = parse_series_table([["year", "1", "1"], ["1900", "1", "2"]])
    assert errors and "паўтараюцца" in errors[0]
    _, errors = parse_series_table([["year", "1"]])
    assert errors


def test_natural_key_sorts_series_names_humanly():
    names = ["10", "2", "1a", "1", "13b", "13a"]
    assert sorted(names, key=natural_key) == ["1", "1a", "2", "10", "13a", "13b"]
