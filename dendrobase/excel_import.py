"""Імпарт пробных плошчаў з Excel-файлаў: адзін файл = адна ПП, лісты title, crn, series.

Запуск:  python -m dendrobase.excel_import --folder "шлях/да/папкі"
Папка па змаўчанні бярэцца з DENDROBASE_EXCEL_FOLDER (.env).

У папцы з файламі вядзецца стан імпарту (гл. import_state): пры паўторным запуску нязменныя
апрацаваныя файлы прапускаюцца; --reimport апрацоўвае ўсё нанова.
"""
from __future__ import annotations

import argparse
import logging
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import pandas as pd

from .config import ConfigError, Settings
from .db import GEO_POLYGON_TABLE, DatabaseError, DatabaseManager
from .i18n import set_language, tr
from .import_state import (EXCEL_SUFFIXES, JOURNAL_FILE, STATE_FILE, STATE_FORMAT, ImportState,  # noqa: F401
                           excel_files, file_digest)
from .logging_setup import setup_logging
from .models import CrnRow, SeriesValue
from .parsing import cell_to_text, coerce_title_values, parse_float, parse_int
from .reference import CRN_COLUMNS, EXCEL_PARAM_MAPPING, PROBE_KEY

log = logging.getLogger("dendrobase.excel_import")

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


@dataclass
class FileResult:
    """Вынік апрацоўкі аднаго файла для стану імпарту і акна ходу працы."""
    probe: str
    status: str = "done"  # done | skipped (няма ліста title) | error
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    crn_rows: int = 0     # запісана радкоў CRN (у стан імпарту не трапляе)
    series_rows: int = 0  # запісана значэнняў SERIES


@dataclass(frozen=True)
class ImportProgress:
    """Падзея ходу імпарту для інтэрфейсу. Без Tk: як яе паказаць, вырашае атрымальнік.

    stage: "scan" (файлы палічаны, зададзены total); "file" (файл апрацаваны, падрабязнасці ў result);
    "unchanged" (нязменны файл прапушчаны па стане імпарту); "journal", "geometry", "geobotany"
    (этапы пасля файлаў: count = колькасць абноўленых ПП або None, калі этап не выконваўся).
    """
    stage: str
    done: int = 0   # файлаў пройдзена, разам з прапушчанымі
    total: int = 0  # файлаў у папцы
    file: str = ""
    result: FileResult | None = None
    count: int | None = None


ProgressCallback = Callable[[ImportProgress], None]
StopCheck = Callable[[], bool]


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
    cancelled: bool = False  # спынены па запыце (should_stop), не ўсе файлы пройдзены

    def summary(self) -> str:
        return tr(
            "Файлаў: {files}; прапушчана ўжо апрацаваных: {skipped}; абноўлена ПП: {titles}; "
            "CRN: {crn_rows} радкоў з {crn_files} файлаў; SERIES: {series_rows} значэнняў з {series_files} файлаў; "
            "папярэджанняў: {warnings}; памылак: {errors}"
        ).format(files=self.files, skipped=self.skipped, titles=self.title_updated,
                 crn_rows=self.crn_rows, crn_files=self.crn_files,
                 series_rows=self.series_rows, series_files=self.series_files,
                 warnings=self.warnings, errors=self.errors)


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
                    result.crn_rows = written
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
                    result.series_rows = written
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


def import_folder(db: DatabaseManager, folder: Path, *, overwrite: bool = False, reimport: bool = False,
                  progress: ProgressCallback | None = None, should_stop: StopCheck | None = None) -> ImportStats:
    """Імпартаваць усе Excel-файлы папкі, прапускаючы ўжо апрацаваныя паводле ImportState.

    reimport=True апрацоўвае ўсе файлы нанова; стан пры гэтым усё роўна абнаўляецца.
    progress выклікаецца пасля падліку файлаў і пасля кожнага файла (гл. ImportProgress).
    should_stop правяраецца перад кожным файлам: True спыняе імпарт, stats.cancelled становіцца True;
    зробленае да гэтага застаецца ў базе і ў стане імпарту.
    """
    stats = ImportStats()
    folder = Path(folder)
    files = excel_files(folder)
    state = ImportState.load(folder)
    probes = set(db.get_all_probes())
    report = progress or (lambda event: None)
    total = len(files)
    log.info("Знойдзена Excel-файлаў: %d у %s (у стане імпарту: %d)", total, folder, len(state.files))
    report(ImportProgress("scan", total=total))
    for index, path in enumerate(files, 1):
        if should_stop is not None and should_stop():
            stats.cancelled = True
            log.warning("Імпарт спынены па запыце: пройдзена %d з %d файлаў", index - 1, total)
            break
        try:
            digest = file_digest(path)
        except OSError as exc:
            stats.files += 1
            stats.errors += 1
            result = FileResult(probe_name_from_file(path), "error", error=f"файл не прачытаны: {exc}")
            log.error("[%s] %s", result.probe, result.error)
            report(ImportProgress("file", index, total, path.name, result))
            continue
        if not reimport and state.is_done(path.name, digest, probes=probes, overwrite=overwrite):
            log.debug("[%s] ужо апрацаваны, прапушчаны", probe_name_from_file(path))
            stats.skipped += 1
            report(ImportProgress("unchanged", index, total, path.name))
            continue
        result = import_file(db, path, stats, overwrite=overwrite)
        state.record(path.name, digest, result, overwrite=overwrite)
        state.save()  # пасля кожнага файла, каб перапынены запуск не губляў зробленае
        report(ImportProgress("file", index, total, path.name, result))
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
        geometry: bool = True, geobotany: bool = False, overwrite: bool = False, reimport: bool = False,
        progress: ProgressCallback | None = None, should_stop: StopCheck | None = None) -> ImportStats:
    """Поўны імпарт, як яго выконвае каманда: схема, файлы, n_journal, геаметрыя, зводка.

    Адкрывае ўласнае злучэнне з БД і зачыняе яго ў канцы, таму можа працаваць у асобным патоку, пакуль
    інтэрфейс карыстаецца сваім злучэннем. progress і should_stop гл. у import_folder; пасля спынення
    этапы journal / geometry / geobotany не выконваюцца.
    """
    report = progress or (lambda event: None)
    db = DatabaseManager(settings.db)
    try:
        missing = db.check_schema()
        if missing:
            raise DatabaseError(f"У базе няма табліц: {', '.join(missing)}. Выканайце schema.sql.")
        if constraints:
            for message in db.ensure_constraints():
                log.info("Схема: %s", message)
        stats = import_folder(db, Path(folder), overwrite=overwrite, reimport=reimport,
                              progress=progress, should_stop=should_stop)
        if stats.cancelled:
            return stats
        if journal:  # пасля імпарту, каб нумары трапілі і ў толькі што дададзеныя ПП
            journal_path = Path(folder) / JOURNAL_FILE
            if journal_path.is_file():
                updated = fill_journal_numbers(db, journal_path)
                log.info("n_journal абноўлены для %d ПП", updated)
                report(ImportProgress("journal", count=updated))
            else:
                log.info("Файла %s няма, n_journal не абнаўляецца", JOURNAL_FILE)
                report(ImportProgress("journal"))
        if geometry:
            if db.has_postgis() and db.has_geometry_column():
                updated = db.update_geometry_all(only_missing=True)
                log.info("Геаметрыя разлічана для %d ПП", updated)
                report(ImportProgress("geometry", count=updated))
            else:
                log.warning("PostGIS не ўсталяваны або няма слупка geom: геаметрыя не абноўлена")
                report(ImportProgress("geometry"))
        if geobotany:
            assigned = db.assign_geobotany_from_polygons()
            log.info("Геабатанічныя палі запоўнены для %d ПП", assigned)
            log.info("Нармалізавана напісанне зоны ў %d ПП", db.normalize_zones())
            report(ImportProgress("geobotany", count=assigned))
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
