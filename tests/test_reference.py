import re

from dendrobase.config import PROJECT_ROOT
from dendrobase.reference import (EXCEL_PARAM_MAPPING, FIELD_BY_NAME, GEO_ZONA_LIST, PORODA_DICT, PORODA_LIST,
                                  TITLE_FIELDS, ZONA_NORMALIZATION, field_kind)


def schema_title_columns() -> set[str]:
    schema = (PROJECT_ROOT / "schema.sql").read_text(encoding="utf-8")
    body = schema.split("CREATE TABLE IF NOT EXISTS title (")[1].split(");")[0]
    columns = set()
    for line in body.splitlines():
        match = re.match(r"\s*([a-z_][a-z0-9_]*)\s+\w", line)
        if match:
            columns.add(match.group(1))
    columns.add("geom")
    return columns


def test_every_title_field_exists_in_schema():
    missing = [f.name for f in TITLE_FIELDS if f.name not in schema_title_columns()]
    assert missing == []


def test_field_names_are_unique():
    names = [f.name for f in TITLE_FIELDS]
    assert len(names) == len(set(names))


def test_excel_mapping_targets_known_columns():
    unknown = sorted({c for c in EXCEL_PARAM_MAPPING.values() if c not in FIELD_BY_NAME})
    assert unknown == []
    assert all(key == key.lower() for key in EXCEL_PARAM_MAPPING)


def test_poroda_list_and_dict_agree():
    assert set(PORODA_LIST) == set(PORODA_DICT)


def test_zone_normalization_targets_are_in_zone_list():
    assert set(ZONA_NORMALIZATION.values()) <= set(GEO_ZONA_LIST)


def test_field_kind_for_unknown_column_is_text():
    assert field_kind("geom") == "text"
    assert field_kind("shirota_grd") == "number"
