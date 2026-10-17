"""Простыя тыпы даных, агульныя для БД, разбору і інтэрфейсу."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from .reference import CRN_VALUE_COLUMNS


class CrnRow(NamedTuple):
    """Радок абагульненай храналогіі за адзін год."""
    year: int
    num: float | None = None
    raw: float | None = None
    std: float | None = None
    res: float | None = None
    ars: float | None = None


class SeriesValue(NamedTuple):
    """Значэнне адной індывідуальнай серыі за адзін год."""
    year: int
    series_name: str
    value: float


class ProbePoint(NamedTuple):
    """Пробная плошча з каардынатамі для мапы."""
    name: str
    lat: float
    lon: float
    poroda: str | None = None
    first_year: int | None = None
    last_year: int | None = None
    trees: int | None = None


class ProbeSummary(NamedTuple):
    """Радок спіса пробных плошчаў."""
    name: str
    poroda: str | None = None
    drevesnaya_poroda: str | None = None
    first_year: int | None = None
    last_year: int | None = None
    trees: int | None = None
    has_coords: bool = False

    @property
    def years(self) -> str:
        if self.first_year is None and self.last_year is None:
            return ""
        return f"{self.first_year or '?'}–{self.last_year or '?'}"


@dataclass
class SeriesMatrix:
    """Серыі ў выглядзе матрыцы год x серыя."""
    years: list[int]
    series: list[str]
    values: dict[tuple[int, str], float]

    def value(self, year: int, series_name: str) -> float | None:
        return self.values.get((year, series_name))

    def row(self, year: int) -> list[float | None]:
        return [self.values.get((year, name)) for name in self.series]


@dataclass
class FilterCriteria:
    """Крытэрыі ўкладкі «Фільтры і пошук»."""
    drevesnaya_poroda: str | None = None
    geo_zona: str | None = None
    geo_podzona: str | None = None
    geo_okrug: str | None = None
    geo_rajon: str | None = None
    tip_lesa_keyword: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    crn_columns: tuple[str, ...] = CRN_VALUE_COLUMNS

    def __post_init__(self) -> None:
        unknown = [c for c in self.crn_columns if c not in CRN_VALUE_COLUMNS]
        if unknown:
            raise ValueError(f"Невядомыя слупкі CRN: {', '.join(unknown)}")


@dataclass
class QueryResult:
    """Вынік адвольнага SQL-запыту з акна «SQL-запыт»."""
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    rowcount: int = 0

    @property
    def has_rows(self) -> bool:
        return bool(self.columns)
