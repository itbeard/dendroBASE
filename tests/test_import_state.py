"""Стан імпарту ў папцы і праверка «што імпарт апрацаваў бы цяпер» (паласа ў галоўным акне)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import dendrobase.import_state as import_state
from dendrobase.import_state import STATE_FILE, ImportState, PendingFiles, file_digest, pending_files


def entry(path: Path, probe: str, status: str = "done") -> dict[str, object]:
    return {"status": status, "probe": probe, "sha256": file_digest(path), "imported": "2026-10-17T10:00:00",
            "overwrite": False, "warnings": []}


def write_state(folder: Path, files: dict[str, dict[str, object]]) -> None:
    payload = {"format": 1, "updated": "2026-10-17T10:00:00", "files": files}
    (folder / STATE_FILE).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_without_state_every_excel_file_is_new(tmp_path):
    (tmp_path / "PP01.xlsx").write_bytes(b"a")
    (tmp_path / "pp02.XLSM").write_bytes(b"b")
    (tmp_path / "~$PP01.xlsx").write_bytes(b"")  # часовы файл Excel
    (tmp_path / "dendro_point_living.xlsx").write_bytes(b"j")  # журнал, а не ПП
    (tmp_path / "notes.txt").write_bytes(b"")
    pending = pending_files(tmp_path, {"pp01"})
    assert pending == PendingFiles(tmp_path, new=("PP01.xlsx", "pp02.XLSM"))
    assert pending.count == 2 and pending


def test_unchanged_done_and_skipped_files_are_not_pending(tmp_path):
    done = tmp_path / "a.xlsx"
    done.write_bytes(b"a")
    skipped = tmp_path / "b.xlsx"
    skipped.write_bytes(b"b")
    write_state(tmp_path, {"a.xlsx": entry(done, "a"), "b.xlsx": entry(skipped, "b", "skipped")})
    pending = pending_files(tmp_path, {"a"})
    assert not pending and pending.count == 0
    assert pending == PendingFiles(tmp_path)


def test_changed_failed_and_orphaned_files_are_pending(tmp_path):
    changed = tmp_path / "changed.xlsx"
    changed.write_bytes(b"old")
    failed = tmp_path / "failed.xlsx"
    failed.write_bytes(b"f")
    orphan = tmp_path / "orphan.xlsx"
    orphan.write_bytes(b"o")
    (tmp_path / "fresh.xlsx").write_bytes(b"n")
    write_state(tmp_path, {"changed.xlsx": entry(changed, "changed"), "failed.xlsx": entry(failed, "failed", "error"),
                           "orphan.xlsx": entry(orphan, "orphan")})
    changed.write_bytes(b"new")
    pending = pending_files(tmp_path, {"changed", "failed"})  # ПП orphan у базе больш няма
    assert pending.new == ("fresh.xlsx",)
    assert pending.changed == ("changed.xlsx", "failed.xlsx", "orphan.xlsx")
    assert pending.count == 4


def test_new_files_are_not_hashed(tmp_path, monkeypatch):
    """Пры першым запуску са шматлікімі файламі праверка не чытае іх змесціва: дастаткова назваў."""
    known = tmp_path / "known.xlsx"
    known.write_bytes(b"k")
    (tmp_path / "new.xlsx").write_bytes(b"n")
    write_state(tmp_path, {"known.xlsx": entry(known, "known")})
    hashed: list[str] = []
    original = import_state.file_digest
    monkeypatch.setattr(import_state, "file_digest", lambda path: (hashed.append(path.name), original(path))[1])
    assert pending_files(tmp_path, {"known"}) == PendingFiles(tmp_path, new=("new.xlsx",))
    assert hashed == ["known.xlsx"]


def test_unreadable_file_counts_as_changed(tmp_path, monkeypatch, caplog):
    path = tmp_path / "a.xlsx"
    path.write_bytes(b"a")
    write_state(tmp_path, {"a.xlsx": entry(path, "a")})

    def fail(_path):
        raise OSError("няма доступу")

    monkeypatch.setattr(import_state, "file_digest", fail)
    assert pending_files(tmp_path, {"a"}).changed == ("a.xlsx",)
    assert "не прачытаны" in caplog.text


def test_corrupt_state_means_everything_is_new(tmp_path, caplog):
    (tmp_path / "a.xlsx").write_bytes(b"a")
    (tmp_path / STATE_FILE).write_text("{не json", encoding="utf-8")
    assert pending_files(tmp_path, set()).new == ("a.xlsx",)
    assert "не прачытаны" in caplog.text


def test_missing_folder_raises_os_error(tmp_path):
    with pytest.raises(OSError):
        pending_files(tmp_path / "няма такой папкі", set())


def test_excel_import_keeps_reexporting_state_api():
    """Каманда імпарту і яе тэсты бяруць стан з excel_import, як і раней."""
    from dendrobase import excel_import
    assert excel_import.ImportState is ImportState
    assert excel_import.STATE_FILE == STATE_FILE and excel_import.file_digest is file_digest
