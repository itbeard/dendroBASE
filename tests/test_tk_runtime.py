"""Рэгрэсія страты клікаў у Tk Aqua 8.6.12: правяраем Tk, а не Tcl ці Python."""
import logging
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dendrobase.ui.runtime import UnsupportedTkError, check_tk_runtime


@pytest.mark.parametrize("window_system, version, rejected", [
    ("aqua", "8.6.9", True),
    ("aqua", "8.6.12", True),
    ("aqua", "8.6.13", False),
    ("aqua", "8.6.14", False),
    ("aqua", "8.6.16", False),
    ("aqua", "9.0.1", False),
    ("win32", "8.6.12", False),
    ("x11", "8.6.12", False),
])
def test_runtime_checks_actual_tk_and_only_rejects_old_aqua(window_system, version, rejected, caplog):
    # Tcl не патрабуе дысплея; выкарыстоўваем сапраўдны vcompare, у тым ліку для 8.6.9 / 9.x.
    interpreter = tk.Tcl()

    def call(*args):
        values = {
            ("package", "require", "Tk"): version,
            ("tk", "windowingsystem"): window_system,
            ("info", "patchlevel"): "8.6.16",  # навейшы Tcl не выпраўляе стары Tk
            ("tk", "scaling"): 2.0,
        }
        return values[args] if args in values else interpreter.call(*args)

    root = SimpleNamespace(tk=SimpleNamespace(call=call))
    with caplog.at_level(logging.INFO, logger="dendrobase.ui"):
        if rejected:
            with pytest.raises(UnsupportedTkError, match=f"Tk {version}"):
                check_tk_runtime(root)
        else:
            check_tk_runtime(root)
    assert f"Tcl 8.6.16; Tk {version}; window system: {window_system}" in caplog.text
    assert "Python executable:" in caplog.text


def test_main_stops_before_database_and_destroys_root_for_unsupported_tk(tmp_path, monkeypatch):
    from dendrobase import __main__ as entry
    from dendrobase.config import DatabaseSettings, Settings

    root = Mock()
    database = Mock()
    show_error = Mock()
    settings = Settings(db=DatabaseSettings(), log_dir=tmp_path)
    monkeypatch.setattr(entry.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(entry.tk, "Tk", lambda: root)
    monkeypatch.setattr(entry, "enable_high_dpi", lambda: None)
    monkeypatch.setattr(entry, "DatabaseManager", database)
    monkeypatch.setattr(entry, "show_error", show_error)
    monkeypatch.setattr(entry, "check_tk_runtime", Mock(side_effect=UnsupportedTkError("Tk 8.6.12")))

    assert entry.main() == 2
    database.assert_not_called()
    root.mainloop.assert_not_called()
    root.destroy.assert_called_once()
    show_error.assert_called_once_with("Несумяшчальная версія Tk", "Tk 8.6.12", parent=root)


@pytest.mark.parametrize("platform, tk_version, delta, num, expected", [
    ("darwin", 8.6, 1, None, -1),
    ("darwin", 8.6, -2, None, 2),
    ("darwin", 9.0, 120, None, -1),
    ("darwin", 9.0, -240, None, 2),
    ("win32", 8.6, 120, None, -1),
    ("win32", 9.0, -120, None, 1),
    ("linux", 8.6, 0, 4, -1),
    ("linux", 9.0, 0, 5, 1),
])
def test_wheel_units_remain_consistent_when_upgrading_tk(monkeypatch, platform, tk_version, delta, num, expected):
    from dendrobase.ui import widgets
    monkeypatch.setattr(widgets.sys, "platform", platform)
    monkeypatch.setattr(widgets.tk, "TkVersion", tk_version)
    assert widgets._wheel_step(SimpleNamespace(delta=delta, num=num)) == expected
