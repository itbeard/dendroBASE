"""Чысты разбор тэксту: лікі з коскай, даты, табліцы з буфера абмену.

Модуль не залежыць ні ад Tk, ні ад БД, таму цалкам пакрыты тэстамі.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping, Sequence

from .models import CrnRow, SeriesValue
from .reference import CRN_COLUMNS, field_kind, field_label

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%Y")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]")
_DIGITS = re.compile(r"(\d+)")


def parse_float(value: object) -> float | None:
    """Лік з радка. Прымае коску як дзесятковы раздзяляльнік і прабелы-раздзяляльнікі тысяч.

    Пустое значэнне дае None, непарсабельнае выклікае ValueError.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"не лік: {value!r}")
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        raise ValueError(f"не лік: {text!r}") from None


def parse_int(value: object) -> int | None:
    """Цэлы лік; «1900.0» і «1 900» таксама прымаюцца."""
    number = parse_float(value)
    if number is None:
        return None
    if not number.is_integer():
        raise ValueError(f"не цэлы лік: {value!r}")
    return int(number)


def parse_date(value: object) -> date | None:
    """Дата ў фарматах дд.мм.гггг, гггг-мм-дд, дд.мм.гг, дд/мм/гггг або аб'ект date/datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if _ISO_DATETIME.match(text):
        text = text[:10]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"не дата: {value!r}")


def cell_to_text(value: object) -> str:
    """Тэкст з ячэйкі: лікі без хваста «.0», астатняе як ёсць, без прабелаў па краях."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def coerce_title_values(raw: Mapping[str, object]) -> tuple[dict[str, object], list[str]]:
    """Прывесці значэнні палёў title да тыпаў слупкоў паводле reference.TITLE_FIELDS.

    Вяртае (даныя, памылкі). Палі з памылкамі ў даныя не трапляюць;
    пустыя значэнні захоўваюцца як None, каб іх можна было ачысціць у БД.
    """
    data: dict[str, object] = {}
    errors: list[str] = []
    for column, value in raw.items():
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "":
            data[column] = None
            continue
        kind = field_kind(column)
        try:
            if kind == "number":
                data[column] = parse_float(value)
            elif kind == "integer":
                data[column] = parse_int(value)
            elif kind == "date":
                data[column] = parse_date(value)
            else:
                data[column] = cell_to_text(value)
        except ValueError:
            errors.append(f"{field_label(column)}: {value!r}")
    return data, errors


def values_equal(old: object, new: object) -> bool:
    """Ці аднолькавыя значэнне з БД і новае значэнне з формы (лікі параўноўваюцца як лікі)."""
    old_empty = old is None or old == ""
    new_empty = new is None or new == ""
    if old_empty or new_empty:
        return old_empty and new_empty
    numeric = (int, float, Decimal)
    if isinstance(old, numeric) and isinstance(new, numeric) and not isinstance(old, bool):
        return float(old) == float(new)
    if isinstance(old, (date, datetime)) or isinstance(new, (date, datetime)):
        try:
            return parse_date(old) == parse_date(new)
        except ValueError:
            return False
    return str(old).strip() == str(new).strip()


def parse_clipboard_table(text: str) -> list[list[str]]:
    """Табліца з буфера абмену: радкі па пераносах, ячэйкі па табуляцыі (як капіюе Excel)
    або па прабелах, калі табуляцый няма. Пустыя радкі прапускаюцца."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cells = line.split("\t") if "\t" in line else line.split()
        rows.append([cell.strip() for cell in cells])
    return rows


def _is_header(cells: Sequence[str]) -> bool:
    if not cells:
        return False
    try:
        return parse_float(cells[0]) is None
    except ValueError:
        return True


def parse_crn_table(rows: Sequence[Sequence[str]]) -> tuple[list[CrnRow], list[str]]:
    """Радкі CRN з табліцы. Загаловак неабавязковы; калі ён ёсць і назвы супадаюць з
    year/num/raw/std/res/ars, слупкі бяруцца па назвах, іначай па парадку."""
    result: list[CrnRow] = []
    errors: list[str] = []
    if not rows:
        return result, errors
    columns: list[str] = list(CRN_COLUMNS)
    start = 0
    if _is_header(rows[0]):
        header = [cell.lower() for cell in rows[0]]
        if header and all(name in CRN_COLUMNS for name in header if name):
            columns = header
        start = 1
    for number, cells in enumerate(rows[start:], start + 1):
        record: dict[str, object] = {}
        try:
            for name, cell in zip(columns, cells):
                if name == "year":
                    record["year"] = parse_int(cell)
                elif name in CRN_COLUMNS:
                    record[name] = parse_float(cell)
            if record.get("year") is None:
                raise ValueError("няма года")
        except ValueError as exc:
            errors.append(f"радок {number}: {exc}")
            continue
        result.append(CrnRow(**record))  # type: ignore[arg-type]
    return result, errors


def parse_series_table(rows: Sequence[Sequence[str]]) -> tuple[list[SeriesValue], list[str]]:
    """Серыі з табліцы: першы радок загаловак (year, назвы серый), далей радкі па гадах."""
    values: list[SeriesValue] = []
    errors: list[str] = []
    if len(rows) < 2:
        errors.append("патрэбны радок загалоўка з назвамі серый і хаця б адзін радок даных")
        return values, errors
    names = [cell.strip() for cell in rows[0][1:]]
    if not names:
        errors.append("у загалоўку няма назваў серый")
        return values, errors
    duplicates = sorted({n for n in names if n and names.count(n) > 1})
    if duplicates:
        errors.append(f"назвы серый паўтараюцца: {', '.join(duplicates)}")
        return values, errors
    for number, cells in enumerate(rows[1:], 2):
        try:
            year = parse_int(cells[0])
        except ValueError:
            errors.append(f"радок {number}: год {cells[0]!r} не лік")
            continue
        if year is None:
            continue
        for name, cell in zip(names, cells[1:]):
            if not name or cell == "":
                continue
            try:
                value = parse_float(cell)
            except ValueError:
                errors.append(f"радок {number}, серыя {name}: {cell!r} не лік")
                continue
            if value is not None:
                values.append(SeriesValue(year, name, value))
    return values, errors


def natural_key(text: object) -> list[object]:
    """Ключ для натуральнай сартыроўкі назваў серый: 1, 1a, 2, 10, 13b."""
    return [int(part) if part.isdigit() else part.lower() for part in _DIGITS.split(str(text))]
