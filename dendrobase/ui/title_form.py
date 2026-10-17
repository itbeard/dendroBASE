"""Форма палёў табліцы title: адна рэалізацыя для анкеты новай ПП і ўкладкі «Інфармацыя аб ПП»."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, Mapping, Sequence

from ..reference import TitleField
from .widgets import format_value


class TitleForm:
    def __init__(self, parent: tk.Misc, fields: Sequence[TitleField], *, columns: int = 3,
                 readonly: Iterable[str] = (), label_width: int = 34) -> None:
        self.frame = ttk.Frame(parent)
        self.fields = list(fields)
        self.readonly = set(readonly)
        self.widgets: dict[str, tk.Widget] = {}

        column_frames = [ttk.Frame(self.frame) for _ in range(max(1, columns))]
        for column_frame in column_frames:
            column_frame.pack(side="left", fill="both", expand=True, padx=6)

        for index, field in enumerate(self.fields):
            row = ttk.Frame(column_frames[index % len(column_frames)])
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{field.label}:", width=label_width, anchor="w").pack(side="left", padx=4)
            widget: tk.Widget
            if field.kind == "choice":
                widget = ttk.Combobox(row, values=list(field.options), width=30)
            elif field.kind == "multiline":
                widget = tk.Text(row, height=3, width=30, wrap="word")
            else:
                widget = ttk.Entry(row, width=32)
            widget.pack(side="left", fill="x", expand=True, padx=4)
            self.widgets[field.name] = widget
            if field.name in self.readonly:
                self._set_state(widget, "readonly")

    # ---------------------------------------------------------------- стан
    @staticmethod
    def _set_state(widget: tk.Widget, state: str) -> None:
        if isinstance(widget, tk.Text):
            widget.configure(state="disabled" if state == "readonly" else "normal")
        else:
            widget.configure(state=state)

    def _write(self, name: str, text: str) -> None:
        widget = self.widgets[name]
        locked = name in self.readonly
        if locked:
            self._set_state(widget, "normal")
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
        else:
            widget.delete(0, "end")  # type: ignore[call-arg]
            widget.insert(0, text)  # type: ignore[call-arg]
        if locked:
            self._set_state(widget, "readonly")

    # -------------------------------------------------------------- значэнні
    def get_text(self, name: str) -> str:
        widget = self.widgets[name]
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end").strip()
        return widget.get().strip()  # type: ignore[attr-defined]

    def values(self, *, include_readonly: bool = False) -> dict[str, str]:
        """Радкі з усіх палёў (без пераўтварэння тыпаў)."""
        return {
            field.name: self.get_text(field.name)
            for field in self.fields
            if include_readonly or field.name not in self.readonly
        }

    def set_values(self, data: Mapping[str, object]) -> None:
        for field in self.fields:
            self._write(field.name, format_value(data.get(field.name)))

    def clear(self) -> None:
        for field in self.fields:
            self._write(field.name, "")

    def focus_first(self) -> None:
        if self.fields:
            self.widgets[self.fields[0].name].focus_set()
