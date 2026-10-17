"""Стан імпарту з Excel у папцы з файламі: што ўжо апрацавана і што яшчэ чакае імпарту.

У папцы з файламі вядзецца STATE_FILE: для кожнага файла SHA-256 змесціва, статус, папярэджанні
і памылка. Па ім excel_import прапускае нязменныя апрацаваныя файлы, а галоўнае акно на старце
правярае, ці з'явілася што імпартаваць (pending_files). Модуль наўмысна без pandas: праверка
на старце не павінна цягнуць цяжкія бібліятэкі.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .excel_import import FileResult

log = logging.getLogger("dendrobase.import_state")

EXCEL_SUFFIXES = (".xlsx", ".xlsm")
JOURNAL_FILE = "dendro_point_living.xlsx"
STATE_FILE = "dendrobase_import_state.json"
STATE_FORMAT = 1


def excel_files(folder: Path) -> list[Path]:
    """Excel-файлы папкі для імпарту: без часовых ~$ і без журнала dendro_point_living.xlsx."""
    return sorted(
        path for path in Path(folder).iterdir()
        if path.suffix.lower() in EXCEL_SUFFIXES
        and not path.name.startswith("~$")
        and path.name.lower() != JOURNAL_FILE
    )


def file_digest(path: Path) -> str:
    """SHA-256 змесціва файла: па ім стан імпарту вызначае, ці змяніўся файл."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


@dataclass(frozen=True)
class PendingFiles:
    """Файлы папкі, якія звычайны імпарт (без «нанова» і «перапісваць») апрацаваў бы цяпер.

    new: яшчэ не фігуруюць у стане імпарту. changed: змяніліся пасля імпарту, скончыліся памылкай
    або іх ПП больш няма ў базе. Нязменныя апрацаваныя файлы не ўлічваюцца.
    """
    folder: Path
    new: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return len(self.new) + len(self.changed)

    def __bool__(self) -> bool:
        return self.count > 0


def pending_files(folder: Path, probes: set[str]) -> PendingFiles:
    """Якія файлы папкі імпарт апрацаваў бы цяпер (гл. ImportState.is_done з overwrite=False).

    probes: коды ПП, якія ёсць у базе. Файлы, якіх няма ў стане, не хэшуюцца: яны новыя і так.
    OSError, калі папку нельга прачытаць.
    """
    folder = Path(folder)
    state = ImportState.load(folder)
    new: list[str] = []
    changed: list[str] = []
    for path in excel_files(folder):
        if path.name not in state.files:
            new.append(path.name)
            continue
        try:
            digest = file_digest(path)
        except OSError as exc:
            log.warning("Файл %s не прачытаны: %s", path, exc)
            changed.append(path.name)  # імпарт паспрабуе яго зноў і пакажа памылку
            continue
        if not state.is_done(path.name, digest, probes=probes, overwrite=False):
            changed.append(path.name)
    return PendingFiles(folder, tuple(new), tuple(changed))
