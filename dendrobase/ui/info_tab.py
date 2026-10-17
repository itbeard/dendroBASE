"""Укладка «Інфармацыя аб ПП»: карткa з загалоўкам, секцыі палёў, захаванне толькі змен."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..i18n import tr
from ..parsing import coerce_title_values, values_equal
from ..reference import (FIELD_BY_NAME, PORODA_DICT, PROBE_KEY, READONLY_COLUMNS, TITLE_SECTIONS, TitleField,
                         field_label)
from .feedback import ask_yes_no_cancel, show_error
from .theme import PAD
from .title_form import TitleForm
from .widgets import ScrollableFrame, add_tooltip

Notify = Callable[..., None]


def probe_summary(info: dict) -> str:
    """Радок пад загалоўкам: від, парода, гады шкалы, колькасць дрэў, каардынаты."""
    parts: list[str] = []
    if info.get("drevesnaya_poroda"):
        parts.append(str(info["drevesnaya_poroda"]))
    poroda = info.get("glavnaya_poroda")
    if poroda:
        full = PORODA_DICT.get(str(poroda))
        parts.append(f"{poroda} ({tr(full)})" if full else str(poroda))
    first, last = info.get("pervyy_god"), info.get("posledniy_god")
    if first or last:
        parts.append(f"{first or '?'}–{last or '?'}")
    if info.get("kolichestvo_derevev_v_shkale_sht"):
        parts.append(tr("{count} дрэў").format(count=int(info["kolichestvo_derevev_v_shkale_sht"])))
    lat, lon = info.get("shirota_grd"), info.get("dolgota_grd")
    parts.append(f"{float(lat):.4f}, {float(lon):.4f}" if lat and lon else tr("без каардынат"))
    return "  ·  ".join(parts)


class InfoTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, on_change: Callable[[str], None],
                 notify: Notify | None = None) -> None:
        self.db = db
        self.on_change = on_change
        self.notify: Notify = notify or (lambda text, **kwargs: None)
        self.probe: str | None = None
        self.frame = ttk.Frame(notebook, padding=(0, PAD, 0, 0))

        columns = db.get_title_columns()
        sections: list[tuple[str, list[TitleField]]] = [
            (title, [field for field in fields if field.name in columns]) for title, fields in TITLE_SECTIONS
        ]
        extra = [TitleField(name, name) for name in columns if name not in FIELD_BY_NAME and name not in READONLY_COLUMNS]
        if extra:
            sections.append(("Іншыя слупкі", extra))  # загаловак перакладае TitleForm
        self.readonly = {PROBE_KEY}

        header = ttk.Frame(self.frame)
        header.pack(fill="x", padx=PAD)
        self.title_label = ttk.Label(header, text=tr("Пробная плошча не выбрана"), style="Title.TLabel")
        self.title_label.pack(side="left")
        self.dirty_label = ttk.Label(header, text=tr("●  Незахаваныя змены"), style="Warn.TLabel")
        self.subtitle = ttk.Label(self.frame, text=tr("Выберыце ПП у спісе злева або стварыце новую (Ctrl+N)."),
                                  style="Subtitle.TLabel")
        self.subtitle.pack(fill="x", padx=PAD, pady=(2, 0))

        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill="x", padx=PAD, pady=(PAD, 2))
        self.save_button = ttk.Button(toolbar, text=tr("Захаваць змены"), command=self.save)
        self.save_button.pack(side="left")
        add_tooltip(self.save_button, tr("Ctrl+S. Захоўваюцца толькі змененыя палі."))
        self.revert_button = ttk.Button(toolbar, text=tr("Адкаціць"), command=self.load)
        self.revert_button.pack(side="left", padx=(4, 0))
        add_tooltip(self.revert_button, tr("Вярнуць значэнні з базы, адмяніўшы незахаваныя змены."))
        self.only_filled = tk.BooleanVar(value=False)
        check = ttk.Checkbutton(toolbar, text=tr("Толькі запоўненыя палі"), variable=self.only_filled,
                                command=lambda: self.form.show_only_filled(self.only_filled.get()))
        check.pack(side="left", padx=(PAD * 2, 0))
        add_tooltip(check, tr("Схаваць пустыя палі, каб бачыць толькі тое, што вядома пра ПП."))

        self.error_label = ttk.Label(self.frame, text="", style="Error.TLabel", justify="left", wraplength=900)
        self.error_label.pack(fill="x", padx=PAD)

        self.scroll = ScrollableFrame(self.frame)
        self.scroll.pack(fill="both", expand=True)
        self.form = TitleForm(self.scroll.inner, sections, columns=2, readonly=self.readonly,
                              on_change=self._update_dirty)
        self.form.frame.pack(fill="both", expand=True)
        self._update_dirty()

    # ---------------------------------------------------------------- стан
    def is_dirty(self) -> bool:
        return bool(self.probe) and self.form.is_dirty()

    def _update_dirty(self) -> None:
        if self.is_dirty():
            self.dirty_label.pack(side="right")
            self.save_button.state(["!disabled"])
        else:
            self.dirty_label.pack_forget()
            self.save_button.state(["disabled"] if not self.probe else ["!disabled"])

    def check_unsaved(self) -> bool:
        """Перад пераключэннем ПП або выхадам. Вяртае False, калі карыстальнік адмяніў дзеянне."""
        if not self.is_dirty():
            return True
        answer = ask_yes_no_cancel(tr("Незахаваныя змены"), tr("Захаваць змены ў ПП {probe}?").format(probe=self.probe))
        if answer is None:
            return False
        if answer:
            return self.save()
        self.form.set_values(self._last_info or {})
        return True

    # --------------------------------------------------------------- даныя
    def set_probe(self, probe: str | None) -> None:
        self.probe = probe
        self.load()

    def clear(self) -> None:
        self.form.clear()

    def load(self) -> None:
        self.error_label.configure(text="")
        self._last_info: dict | None = None
        if not self.probe:
            self.form.clear()
            self.title_label.configure(text=tr("Пробная плошча не выбрана"))
            self.subtitle.configure(text=tr("Выберыце ПП у спісе злева або стварыце новую (Ctrl+N)."))
            self._update_dirty()
            return
        try:
            info = self.db.get_probe_info(self.probe) or {}
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася прачытаць ПП {probe}:\n{error}").format(probe=self.probe, error=exc), exc)
            return
        self._last_info = info
        self.form.set_values(info)
        self.title_label.configure(text=str(self.probe))
        self.subtitle.configure(text=probe_summary(info))
        self.scroll.scroll_to_top()
        self._update_dirty()

    def save(self) -> bool:
        if not self.probe:
            self.notify(tr("Спачатку выберыце пробную плошчу."), kind="warn")
            return False
        try:
            old = self.db.get_probe_info(self.probe) or {}
        except DatabaseError as exc:
            show_error(tr("Памылка"), str(exc), exc)
            return False
        raw = self.form.values()
        data, errors = coerce_title_values(raw)
        if errors:
            invalid = [name for name, text in raw.items() if text and name not in data]
            self.form.mark_errors(invalid)
            self.error_label.configure(text=tr("Нельга захаваць, праверце палі: {errors}").format(errors="; ".join(errors)))
            if invalid:
                self.form.focus_field(invalid[0])
            return False
        self.form.mark_errors(())
        self.error_label.configure(text="")
        changed = {name: value for name, value in data.items() if not values_equal(old.get(name), value)}
        if not changed:
            self.notify(tr("Няма змен для захавання."))
            return True
        try:
            self.db.upsert_title({PROBE_KEY: self.probe, **changed})
            if {"shirota_grd", "dolgota_grd"} & changed.keys() \
                    and self.db.has_postgis() and self.db.has_geometry_column():
                self.db.update_geometry(self.probe)
        except (DatabaseError, ValueError) as exc:
            show_error(tr("Памылка захавання"), tr("Не атрымалася захаваць змены:\n{error}").format(error=exc), exc)
            return False
        labels = ", ".join(field_label(name) for name in changed)
        self.notify(tr("ПП {probe}: захавана палёў: {count} ({labels})").format(probe=self.probe, count=len(changed), labels=labels),
                    kind="ok")
        self.load()
        self.on_change(self.probe)
        return True
