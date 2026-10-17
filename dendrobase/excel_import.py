"""Імпарт пробных плошчаў з Excel-файлаў: адзін файл = адна ПП, лісты title, crn, series.

Запуск:  python -m dendrobase.excel_import --folder "шлях/да/папкі"
Папка па змаўчанні бярэцца з DENDROBASE_EXCEL_FOLDER (.env).

У папцы з файламі вядзецца стан імпарту (STATE_FILE): для кожнага файла SHA-256 змесціва,
статус, папярэджанні і памылка. Пры паўторным запуску нязменныя апрацаваныя файлы
прапускаюцца; --reimport апрацоўвае ўсё нанова.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pandas as pd

from .config import ConfigError, Settings
from .db import GEO_POLYGON_TABLE, DatabaseError, DatabaseManager
from .i18n import set_language
from .logging_setup import setup_logging
from .models import CrnRow, SeriesValue
from .parsing import cell_to_text, coerce_title_values, parse_float, parse_int
from .reference import CRN_COLUMNS, EXCEL_PARAM_MAPPING, PROBE_KEY

log = logging.getLogger("dendrobase.excel_import")

EXCEL_SUFFIXES = (".xlsx", ".xlsm")
JOURNAL_FILE = "dendro_point_living.xlsx"
STATE_FILE = "dendrobase_import_state.json"
STATE_FORMAT = 1
ExcelSource = "pd.ExcelFile | Path | str"  # шлях або адкрыты pd.ExcelFile


def normalize_param(text: object) -> str:
    return " ".join(str(text).lower().split())


def map_param(param: object) -> str | None:
    """Слупок БД па назве параметра з ліста title.

    Спачатку дакладнае супадзенне, потым самы доўгі ключ, які змяшчаецца ў назве
    (таму «коэфф. состава» ідзе ў koef_sostava, а не ў sostav_drevoj).
    """
    key = normalize_param(param)
    if not key:
        return None
    if key in EXCEL_PARAM_MAPPING:
        return EXCEL_PARAM_MAPPING[key]
    matches = [known for known in EXCEL_PARAM_MAPPING if known in key]
    if not matches:
        return None
    return EXCEL_PARAM_MAPPING[max(matches, key=len)]


def probe_name_from_file(path: Path) -> str:
    return Path(path).stem.strip().lower()


@contextmanager
def _workbook(source: ExcelSource) -> Iterator[pd.ExcelFile]:
    if isinstance(source, pd.ExcelFile):
        yield source
    else:
        with pd.ExcelFile(source) as workbook:
            yield workbook


def find_sheet(workbook: pd.ExcelFile, name: str) -> str | None:
    """Сапраўдная назва ліста без уліку рэгістру і лішніх прабелаў, або None."""
    wanted = normalize_param(name)
    for actual in workbook.sheet_names:
        if normalize_param(actual) == wanted:
            return actual
    return None


def _read(source: ExcelSource, sheet: str, **kwargs) -> pd.DataFrame:
    with _workbook(source) as workbook:
        actual = find_sheet(workbook, sheet)
        if actual is None:
            raise ValueError(f"У файле няма ліста «{sheet}»")
        return pd.read_excel(workbook, sheet_name=actual, **kwargs)


def _is_missing(value: object) -> bool:
    return value is None or (not isinstance(value, str) and pd.isna(value))


def read_title_sheet(source: ExcelSource, probe: str, sheet: str = "title") -> tuple[dict[str, object], list[str]]:
    """Параметры ПП з ліста «параметр | значэнне». Вяртае (даныя, памылкі пераўтварэння)."""
    frame = _read(source, sheet, header=None)
    raw: dict[str, object] = {PROBE_KEY: probe}
    for row in frame.itertuples(index=False):
        if len(row) < 2 or _is_missing(row[0]) or _is_missing(row[1]):
            continue
        column = map_param(row[0])
        if column is None:
            log.debug("[%s] невядомы параметр у title: %r", probe, row[0])
            continue
        if column == PROBE_KEY:
            continue  # код ПП заўсёды бярэцца з назвы файла
        raw[column] = row[1]
    return coerce_title_values(raw)


def read_crn_sheet(source: ExcelSource, probe: str, sheet: str = "crn") -> tuple[list[CrnRow], list[str]]:
    """CRN з ліста: першы слупок год, далей num/raw/std/res/ars па назвах загалоўкаў."""
    frame = _read(source, sheet)
    rows: list[CrnRow] = []
    errors: list[str] = []
    if frame.empty:
        return rows, errors
    columns = [normalize_param(c) for c in frame.columns]
    columns[0] = "year"
    seen: set[int] = set()
    for number, values in enumerate(frame.itertuples(index=False), 2):
        record: dict[str, object] = {}
        try:
            for name, value in zip(columns, values):
                if name not in CRN_COLUMNS or _is_missing(value):
                    continue
                record[name] = parse_int(value) if name == "year" else parse_float(value)
            year = record.get("year")
            if year is None:
                continue
            if not 0 < year < 3000:  # type: ignore[operator]
                raise ValueError(f"дзіўны год {year}")
        except ValueError as exc:
            errors.append(f"crn, радок {number}: {exc}")
            continue
        if year in seen:
            errors.append(f"crn, радок {number}: год {year} паўтараецца, узяты першы")
            continue
        seen.add(year)  # type: ignore[arg-type]
        rows.append(CrnRow(**record))  # type: ignore[arg-type]
    return rows, errors


def read_series_sheet(source: ExcelSource, probe: str, sheet: str = "series") -> tuple[list[SeriesValue], list[str]]:
    """Серыі з ліста: першы слупок год, наступныя слупкі - назвы серый (тэкст)."""
    frame = _read(source, sheet)
    values: list[SeriesValue] = []
    errors: list[str] = []
    if frame.empty or len(frame.columns) < 2:
        return values, errors
    names = [cell_to_text(c) for c in frame.columns[1:]]
    for number, row in enumerate(frame.itertuples(index=False), 2):
        if _is_missing(row[0]):
            continue
        try:
            year = parse_int(row[0])
        except ValueError:
            errors.append(f"series, радок {number}: год {row[0]!r} не лік")
            continue
        if year is None:
            continue
        for name, cell in zip(names, row[1:]):
            if not name or _is_missing(cell):
                continue
            try:
                value = parse_float(cell)
            except ValueError:
                errors.append(f"series, радок {number}, серыя {name}: {cell!r} не лік")
                continue
            if value is not None:
                values.append(SeriesValue(year, name, value))
    return values, errors


def file_digest(path: Path) -> str:
    """SHA-256 змесціва файла: па ім стан імпарту вызначае, ці змяніўся файл."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class FileResult:
    """Вынік апрацоўкі аднаго файла для стану імпарту."""
    probe: str
    status: str = "done"  # done | skipped (няма ліста title) | error
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class ImportState:
    """Стан імпарту ў папцы з Excel (STATE_FILE): якія файлы ўжо апрацаваны і з якімі папярэджаннямі.

    Файл прапускаецца пры паўторным запуску, калі яго змесціва не змянілася (SHA-256), ён быў
    апрацаваны без памылак, яго ПП ёсць у базе і яго імпартавалі з не менш поўным рэжымам
    (запуск з --overwrite пакрывае звычайны, але не наадварот).
    """

    def __init__(self, path: Path, files: dict[str, dict[str, object]] | None = None) -> None:
        self.path = Path(path)
        self.files: dict[str, dict[str, object]] = dict(files or {})
        self.writable = True

    @classmethod
    def load(cls, folder: Path) -> "ImportState":
        """Прачытаць стан з папкі. Няма файла або ён пашкоджаны: пачынаем з пустога."""
        path = Path(folder) / STATE_FILE
        if not path.is_file():
            return cls(path)
        try:
            files = json.loads(path.read_text(encoding="utf-8"))["files"]
            if not isinstance(files, dict):
                raise ValueError("«files» не слоўнік")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Стан імпарту %s не прачытаны (%s): усе файлы будуць апрацаваны", path, exc)
            return cls(path)
        return cls(path, {name: entry for name, entry in files.items() if isinstance(entry, dict)})

    def is_done(self, name: str, digest: str, *, probes: set[str], overwrite: bool) -> bool:
        entry = self.files.get(name)
        if entry is None or entry.get("sha256") != digest:
            return False
        if overwrite and not entry.get("overwrite"):
            return False
        status = entry.get("status")
        if status == "skipped":
            return True
        return status == "done" and entry.get("probe") in probes

    def record(self, name: str, digest: str, result: FileResult, *, overwrite: bool) -> None:
        entry: dict[str, object] = {
            "status": result.status,
            "probe": result.probe,
            "sha256": digest,
            "imported": datetime.now().isoformat(timespec="seconds"),
            "overwrite": overwrite,
            "warnings": list(result.warnings),
        }
        if result.error is not None:
            entry["error"] = result.error
        self.files[name] = entry

    def save(self) -> None:
        """Запісаць стан атамарна. Памылка запісу (папка толькі для чытання) не спыняе імпарт."""
        if not self.writable:
            return
        payload = {
            "format": STATE_FORMAT,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "files": dict(sorted(self.files.items())),
        }
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            self.writable = False
            log.warning("Стан імпарту не захаваны ў %s: %s", self.path, exc)
            try:
                tmp.unlink()
            except OSError:
                pass


@dataclass
class ImportStats:
    files: int = 0
    skipped: int = 0
    title_updated: int = 0
    crn_files: int = 0
    crn_rows: int = 0
    series_files: int = 0
    series_rows: int = 0
    warnings: int = 0
    errors: int = 0

    def summary(self) -> str:
        return (
            f"Файлаў: {self.files}; прапушчана ўжо апрацаваных: {self.skipped}; "
            f"абноўлена ПП: {self.title_updated}; "
            f"CRN: {self.crn_rows} радкоў з {self.crn_files} файлаў; "
            f"SERIES: {self.series_rows} значэнняў з {self.series_files} файлаў; "
            f"папярэджанняў: {self.warnings}; памылак: {self.errors}"
        )


def import_file(db: DatabaseManager, path: Path, stats: ImportStats, *, overwrite: bool = False) -> FileResult:
    """Імпартаваць адзін Excel-файл. Памылкі БД лічацца, але не спыняюць іншыя файлы."""
    probe = probe_name_from_file(path)
    result = FileResult(probe)
    stats.files += 1
    log.info("[%s] %s", probe, path.name)

    def warn(message: str) -> None:
        log.warning("[%s] %s", probe, message)
        result.warnings.append(message)
        stats.warnings += 1

    try:
        with pd.ExcelFile(path) as workbook:
            if find_sheet(workbook, "title") is None:
                warn("няма ліста title, файл прапушчаны")
                result.status = "skipped"
                return result

            title, errors = read_title_sheet(workbook, probe)
            for message in errors:
                warn(f"title, поле прапушчана: {message}")
            db.upsert_title(title)
            stats.title_updated += 1

            if find_sheet(workbook, "crn") is not None:
                rows, errors = read_crn_sheet(workbook, probe)
                for message in errors:
                    warn(message)
                if rows:
                    written = db.upsert_crn_rows(probe, rows, overwrite=overwrite)
                    stats.crn_rows += written
                    stats.crn_files += 1 if written else 0
                    if not written:
                        log.info("[%s] CRN: новых радкоў няма", probe)
            else:
                log.info("[%s] ліста crn няма", probe)

            if find_sheet(workbook, "series") is not None:
                values, errors = read_series_sheet(workbook, probe)
                for message in errors:
                    warn(message)
                if values:
                    written = db.upsert_series_values(probe, values, overwrite=overwrite)
                    stats.series_rows += written
                    stats.series_files += 1 if written else 0
                    if not written:
                        log.info("[%s] SERIES: новых значэнняў няма", probe)
            else:
                log.info("[%s] ліста series няма", probe)
    except DatabaseError as exc:
        result.status, result.error = "error", f"памылка БД: {exc}"
    except (ValueError, OSError) as exc:
        result.status, result.error = "error", f"файл не прачытаны: {exc}"
    if result.error is not None:
        stats.errors += 1
        log.error("[%s] %s", probe, result.error)
    return result


def excel_files(folder: Path) -> list[Path]:
    return sorted(
        path for path in Path(folder).iterdir()
        if path.suffix.lower() in EXCEL_SUFFIXES
        and not path.name.startswith("~$")
        and path.name.lower() != JOURNAL_FILE
    )


def import_folder(db: DatabaseManager, folder: Path, *, overwrite: bool = False,
                  reimport: bool = False) -> ImportStats:
    """Імпартаваць усе Excel-файлы папкі, прапускаючы ўжо апрацаваныя паводле ImportState.

    reimport=True апрацоўвае ўсе файлы нанова; стан пры гэтым усё роўна абнаўляецца.
    """
    stats = ImportStats()
    folder = Path(folder)
    files = excel_files(folder)
    state = ImportState.load(folder)
    probes = set(db.get_all_probes())
    log.info("Знойдзена Excel-файлаў: %d у %s (у стане імпарту: %d)", len(files), folder, len(state.files))
    for path in files:
        try:
            digest = file_digest(path)
        except OSError as exc:
            stats.files += 1
            stats.errors += 1
            log.error("[%s] файл не прачытаны: %s", probe_name_from_file(path), exc)
            continue
        if not reimport and state.is_done(path.name, digest, probes=probes, overwrite=overwrite):
            log.debug("[%s] ужо апрацаваны, прапушчаны", probe_name_from_file(path))
            stats.skipped += 1
            continue
        result = import_file(db, path, stats, overwrite=overwrite)
        state.record(path.name, digest, result, overwrite=overwrite)
        state.save()  # пасля кожнага файла, каб перапынены запуск не губляў зробленае
    if stats.skipped:
        log.info("Прапушчана ўжо апрацаваных файлаў: %d (стан у %s)", stats.skipped, state.path)
    return stats


def fill_journal_numbers(db: DatabaseManager, path: Path) -> int:
    """Запоўніць n_journal па файле dendro_point_living.xlsx (слупкі з «журнал» і назвай ПП)."""
    frame = pd.read_excel(path, sheet_name=0)
    journal_col = next(
        (c for c in frame.columns if "journal" in str(c).lower() or "журнал" in str(c).lower()), None
    )
    probe_col = next(
        (c for c in frame.columns if any(k in str(c).lower() for k in ("пробной", "id_dend", "название"))), None
    )
    if journal_col is None or probe_col is None:
        raise ValueError(f"У {path.name} няма слупка нумара журнала або назвы ПП")
    updated = 0
    for number, probe in zip(frame[journal_col], frame[probe_col]):
        if _is_missing(number) or _is_missing(probe):
            continue
        probe_text, value = cell_to_text(probe), cell_to_text(number)
        if not probe_text or value in ("", "0"):
            continue
        updated += db.set_journal_number(probe_text, value)
    return updated


def run(settings: Settings, folder: Path, *, constraints: bool = True, journal: bool = True,
        geometry: bool = True, geobotany: bool = False, overwrite: bool = False,
        reimport: bool = False) -> ImportStats:
    db = DatabaseManager(settings.db)
    try:
        missing = db.check_schema()
        if missing:
            raise DatabaseError(f"У базе няма табліц: {', '.join(missing)}. Выканайце schema.sql.")
        if constraints:
            for message in db.ensure_constraints():
                log.info("Схема: %s", message)
        stats = import_folder(db, Path(folder), overwrite=overwrite, reimport=reimport)
        if journal:  # пасля імпарту, каб нумары трапілі і ў толькі што дададзеныя ПП
            journal_path = Path(folder) / JOURNAL_FILE
            if journal_path.is_file():
                log.info("n_journal абноўлены для %d ПП", fill_journal_numbers(db, journal_path))
            else:
                log.info("Файла %s няма, n_journal не абнаўляецца", JOURNAL_FILE)
        if geometry:
            if db.has_postgis() and db.has_geometry_column():
                log.info("Геаметрыя разлічана для %d ПП", db.update_geometry_all(only_missing=True))
            else:
                log.warning("PostGIS не ўсталяваны або няма слупка geom: геаметрыя не абноўлена")
        if geobotany:
            log.info("Геабатанічныя палі запоўнены для %d ПП", db.assign_geobotany_from_polygons())
            log.info("Нармалізавана напісанне зоны ў %d ПП", db.normalize_zones())
        for table in ("title", "crn", "series"):
            log.info("Усяго ў %s: %d радкоў", table, db.count_rows(table))
        return stats
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dendrobase.excel_import",
        description="Імпарт пробных плошчаў з Excel-файлаў у базу DendroBASE.",
    )
    parser.add_argument("--folder", type=Path, help="папка з Excel-файламі (па змаўчанні DENDROBASE_EXCEL_FOLDER)")
    parser.add_argument("--overwrite", action="store_true",
                        help="перапісваць існуючыя радкі CRN і SERIES (па змаўчанні яны не чапаюцца)")
    parser.add_argument("--reimport", action="store_true",
                        help=f"апрацаваць усе файлы нанова, не зважаючы на {STATE_FILE} "
                             "(па змаўчанні нязменныя апрацаваныя файлы прапускаюцца)")
    parser.add_argument("--geobotany", action="store_true",
                        help=f"запоўніць геабатанічныя палі па палігонах табліцы {GEO_POLYGON_TABLE} "
                             "(сцірае бягучыя значэнні ва ўсіх ПП!)")
    parser.add_argument("--no-constraints", action="store_true", help="не дадаваць ключы і індэксы")
    parser.add_argument("--no-journal", action="store_true", help=f"не чытаць {JOURNAL_FILE}")
    parser.add_argument("--no-geometry", action="store_true", help="не разлічваць geom")
    return parser


def main(argv: list[str] | None = None) -> int:
    set_language("be")  # паведамленні каманды і разбору беларускія незалежна ад налад інтэрфейсу
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"Памылка налад: {exc}", file=sys.stderr)
        return 2
    setup_logging(settings.log_level, settings.log_dir, filename="excel_import.log")

    folder = args.folder or settings.excel_folder
    if folder is None:
        log.error("Не зададзена папка з Excel-файламі: --folder або DENDROBASE_EXCEL_FOLDER у .env")
        return 2
    if not folder.is_dir():
        log.error("Папка не існуе: %s", folder)
        return 2

    try:
        stats = run(
            settings, folder,
            constraints=not args.no_constraints, journal=not args.no_journal,
            geometry=not args.no_geometry, geobotany=args.geobotany, overwrite=args.overwrite,
            reimport=args.reimport,
        )
    except (DatabaseError, ValueError, OSError) as exc:
        log.error("Імпарт спынены: %s", exc)
        return 1
    log.info("Вынік: %s", stats.summary())
    return 0 if stats.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
