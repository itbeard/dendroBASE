"""Форма палёў табліцы title, згрупаваных па секцыях.

Адна рэалізацыя для анкеты новай ПП і ўкладкі «Інфармацыя аб ПП»: сочыць за зменамі,
умее хаваць пустыя палі і падсвечваць памылковыя.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Mapping, Sequence

from ..reference import TitleField
from .theme import PAD
from .widgets import add_tooltip, format_value

Sections = Sequence[tuple[str, Sequence[TitleField]]]


class TitleForm:
    def __init__(self, parent: tk.Misc, sections: Sections, *, columns: int = 2, readonly: Iterable[str] = (),
                 on_change: Callable[[], None] | None = None, label_width: int = 30) -> None:
        self.frame = ttk.Frame(parent)
        self.fields: list[TitleField] = []
        self.readonly = set(readonly)
        self.on_change = on_change
        self.widgets: dict[str, tk.Widget] = {}
        self.labels: dict[str, ttk.Label] = {}
        self._sections: list[tuple[ttk.LabelFrame, list[str]]] = []
        self._snapshot: dict[str, str] = {}
        self._suspend = False
        self._only_filled = False
        self.frame.columnconfigure(0, weight=1)

        for index, (title, fields) in enumerate(sections):
            fields = list(fields)
            if not fields:
                continue
            box = ttk.LabelFrame(self.frame, text=title, style="Section.TLabelframe", padding=(PAD, 2, PAD, PAD))
            box.grid(row=index, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))
            for column in range(columns):
                box.columnconfigure(column * 2 + 1, weight=1, uniform="field")
            row = column = 0
            names: list[str] = []
            for field in fields:
                self.fields.append(field)
                names.append(field.name)
                label = ttk.Label(box, text=f"{field.label}{' *' if field.required else ''}:",
                                  width=label_width, anchor="w")
                if field.kind == "multiline":
                    if column:
                        row, column = row + 1, 0
                    label.grid(row=row, column=0, sticky="nw", padx=(0, 6), pady=3)
                    widget: tk.Widget = tk.Text(box, height=3, wrap="word", undo=True)
                    widget.grid(row=row, column=1, columnspan=columns * 2 - 1, sticky="ew", pady=3)
                    row += 1
                else:
                    label.grid(row=row, column=column * 2, sticky="w", padx=(0, 6), pady=3)
                    widget = self._entry(box, field)
                    widget.grid(row=row, column=column * 2 + 1, sticky="ew", padx=(0, PAD), pady=3)
                    column += 1
                    if column >= columns:
                        row, column = row + 1, 0
                widget.bind("<KeyRelease>", self._changed, add="+")
                add_tooltip(label, field.hint)
                self.widgets[field.name] = widget
                self.labels[field.name] = label
                if field.name in self.readonly:
                    self._set_state(widget, "readonly")
            self._sections.append((box, names))
        self.snapshot()

    def _entry(self, parent: tk.Misc, field: TitleField) -> tk.Widget:
        if field.kind == "choice":
            combo = ttk.Combobox(parent, values=list(field.options))
            combo.bind("<<ComboboxSelected>>", self._changed, add="+")
            return combo
        return ttk.Entry(parent)

    # ------------------------------------------------------------------ стан
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

    def _changed(self, _event: tk.Event | None = None) -> None:
        if not self._suspend and self.on_change:
            self.on_change()

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
        self._suspend = True
        try:
            for field in self.fields:
                self._write(field.name, format_value(data.get(field.name)))
        finally:
            self._suspend = False
        self.snapshot()
        self.mark_errors(())
        self._apply_visibility()
        self._changed()

    def clear(self) -> None:
        self.set_values({})

    def snapshot(self) -> None:
        """Запомніць бягучыя значэнні як «захаваныя»."""
        self._snapshot = self.values(include_readonly=True)

    def is_dirty(self) -> bool:
        return self.values(include_readonly=True) != self._snapshot

    # ------------------------------------------------------------ навігацыя
    def focus_first(self) -> None:
        for field in self.fields:
            if field.name not in self.readonly:
                self.widgets[field.name].focus_set()
                return

    def focus_field(self, name: str) -> None:
        widget = self.widgets.get(name)
        if widget is not None:
            widget.focus_set()

    def mark_errors(self, names: Iterable[str]) -> None:
        """Падсвяціць подпісы памылковых палёў (і зняць падсветку з астатніх)."""
        wrong = set(names)
        for name, label in self.labels.items():
            label.configure(style="Error.TLabel" if name in wrong else "TLabel")

    def show_only_filled(self, enabled: bool) -> None:
        """Хаваць пустыя палі: карысна для прагляду ПП, у якой запоўнена 10 палёў з 60."""
        self._only_filled = enabled
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        for box, names in self._sections:
            visible = 0
            for name in names:
                field = next(f for f in self.fields if f.name == name)
                show = not self._only_filled or field.required or bool(self.get_text(name))
                for widget in (self.labels[name], self.widgets[name]):
                    if show:
                        widget.grid()
                    else:
                        widget.grid_remove()
                visible += show
            if visible:
                box.grid()
            else:
                box.grid_remove()
