"""Дапаможныя віджэты: пракрутка, падказкі, поле з плейсхолдэрам, табліцы з сартаваннем, буфер абмену.

Усё, што залежыць ад платформы (кола мышы, буфер, файлы), сабрана тут.
"""
from __future__ import annotations

import csv
import sys
import tkinter as tk
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tkinter import ttk
from typing import Callable, Iterable, Mapping, Sequence

from .theme import PALETTE

_WHEEL_CANVASES: set[tk.Canvas] = set()


# ----------------------------------------------------------------- кола мышы
def _wheel_step(event: tk.Event) -> int:
    """Windows і Tk 9 даюць delta кратна 120, macOS/Tk 8 — малыя лікі, X11 — кнопкі 4/5."""
    number = getattr(event, "num", None)
    if number == 4:
        return -1
    if number == 5:
        return 1
    delta = getattr(event, "delta", 0) or 0
    if sys.platform == "darwin" and tk.TkVersion < 9:
        return -int(delta)
    return -int(delta / 120)


def _dispatch_wheel(event: tk.Event, *, touchpad: bool = False) -> str | None:
    """Знайсці зарэгістраваны canvas пад курсорам і пракруціць яго.

    На Windows падзея кола прыходзіць у віджэт з фокусам, таму шукаем па каардынатах курсора.
    """
    widget = event.widget if isinstance(event.widget, tk.Misc) else None
    if widget is None:
        return None
    try:
        target: tk.Misc | None = widget.winfo_containing(event.x_root, event.y_root)
    except tk.TclError:
        return None
    while target is not None:
        if target in _WHEEL_CANVASES:
            if touchpad:
                # Tk 9 перадае дакладную пракрутку асобнай падзеяй, з двума
                # запакаванымі зрухамі ў пікселях. Canvas пракручваецца без страты дакладнасці.
                _, dy = target.tk.call("tk::PreciseScrollDeltas", event.delta)
                bounds = target.bbox("all")
                if bounds and bounds[3] > bounds[1] and dy:
                    target.yview_moveto(target.yview()[0] - int(dy) / (bounds[3] - bounds[1]))
            else:
                step = _wheel_step(event)
                if step:
                    target.yview_scroll(step, "units")
            return "break"
        target = getattr(target, "master", None)
    return None


def enable_mousewheel(canvas: tk.Canvas) -> None:
    """Уключыць пракрутку колам для canvas на ўсіх платформах."""
    _WHEEL_CANVASES.add(canvas)
    canvas.bind("<Destroy>", lambda _e: _WHEEL_CANVASES.discard(canvas), add="+")
    app_root = canvas.nametowidget(".")  # корань таго ж інтэрпрэтатара Tk
    if not getattr(app_root, "_dendrobase_wheel_bound", False):
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            app_root.bind_all(sequence, _dispatch_wheel, add="+")
        if tk.TkVersion >= 9:
            app_root.bind_all("<TouchpadScroll>", lambda event: _dispatch_wheel(event, touchpad=True), add="+")
        setattr(app_root, "_dendrobase_wheel_bound", True)


class ScrollableFrame(ttk.Frame):
    """Рамка з вертыкальнай пракруткай. Змесціва кладзецца ў self.inner."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        enable_mousewheel(self.canvas)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0)


# ------------------------------------------------------------------ падказкі
# Падказкі не ствараюць асобных вокнаў (на macOS з Tk 8.6.12 такія акенцы часам перахопліваюць
# клікі). Замест гэтага тэкст падказкі перадаецца «прыёмніку» бліжэйшага акна: у галоўным акне
# гэта радок стану, у дыялогах радок унізе.
_HINT_SINK_ATTR = "_dendrobase_hint_sink"


def set_hint_sink(window: tk.Misc, sink: Callable[[str | None], None]) -> None:
    """Прызначыць акну прыёмнік падказак: sink(text) пры навядзенні, sink(None) пры выхадзе."""
    setattr(window, _HINT_SINK_ATTR, sink)


def find_hint_sink(widget: tk.Misc) -> Callable[[str | None], None] | None:
    current: tk.Misc | None = widget
    while current is not None:
        sink = getattr(current, _HINT_SINK_ATTR, None)
        if sink is not None:
            return sink
        current = getattr(current, "master", None)
    return None


def add_tooltip(widget: tk.Widget, text: str) -> None:
    """Паказваць text у прыёмніку падказак, пакуль курсор над віджэтам."""
    if not text:
        return

    def emit(value: str | None) -> None:
        sink = find_hint_sink(widget)
        if sink is not None:
            sink(value)

    widget.bind("<Enter>", lambda _e: emit(text), add="+")
    widget.bind("<Leave>", lambda _e: emit(None), add="+")
    widget.bind("<Destroy>", lambda _e: emit(None), add="+")


class HintLabel(ttk.Label):
    """Радок падказак для дыялогаў: паказвае тэкст пры навядзенні на віджэты акна."""

    def __init__(self, master: tk.Misc, window: tk.Misc, default: str = "", **kwargs) -> None:
        super().__init__(master, text=default, style="Hint.TLabel", **kwargs)
        self.default = default
        set_hint_sink(window, self.show)

    def show(self, text: str | None) -> None:
        try:
            self.configure(text=text if text else self.default)
        except tk.TclError:
            pass


class PlaceholderEntry(ttk.Entry):
    """Поле ўводу з шэрай падказкай, пакуль яно пустое."""

    def __init__(self, master: tk.Misc, placeholder: str = "", **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self._showing = False
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        if self.placeholder and not super().get():
            self._showing = True
            super().insert(0, self.placeholder)
            self.configure(foreground=PALETTE["muted"])

    def _on_focus_in(self, _event: tk.Event) -> None:
        if self._showing:
            super().delete(0, "end")
            self.configure(foreground="")
            self._showing = False

    def _on_focus_out(self, _event: tk.Event) -> None:
        self._show_placeholder()

    def get(self) -> str:  # type: ignore[override]
        return "" if self._showing else super().get()

    def set_text(self, text: str) -> None:
        super().delete(0, "end")
        self._showing = False
        self.configure(foreground="")
        if text:
            super().insert(0, text)
        elif self.focus_get() is not self:
            self._show_placeholder()


# -------------------------------------------------------------------- фармат
def format_value(value: object) -> str:
    """Паказ значэння з БД у полі або табліцы: None -> пуста, даты дд.мм.гггг, 85.0 -> 85."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def format_number(value: object, decimals: int = 3) -> str:
    """Лік з фіксаванай колькасцю знакаў, каб слупок у табліцы выраўноўваўся па коме."""
    if value is None or value == "":
        return ""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
    if decimals <= 0:
        return str(int(round(number)))
    return f"{number:.{decimals}f}"


# -------------------------------------------------------------------- табліцы
def make_treeview(parent: tk.Misc, columns: Sequence[str] = (), *, numeric: Mapping[str, int] | None = None,
                  height: int | None = None, horizontal: bool = True, sortable: bool = True,
                  selectmode: str = "extended") -> ttk.Treeview:
    """Treeview з палосамі пракруткі, зебрай і сартаваннем па клiку на загаловак.

    numeric: {слупок: колькасць знакаў пасля коскі}; такія слупкі выраўноўваюцца ўправа.
    Рамка з палосамі пракруткі даступная як tree.master.
    """
    frame = ttk.Frame(parent)
    options: dict[str, object] = {"show": "headings", "selectmode": selectmode}
    if height is not None:
        options["height"] = height
    tree = ttk.Treeview(frame, **options)
    tree.numeric_columns = dict(numeric or {})  # type: ignore[attr-defined]
    tree.sortable = sortable  # type: ignore[attr-defined]
    tree.sort_state = (None, False)  # type: ignore[attr-defined]
    tree.tag_configure("odd", background=PALETTE["stripe"])
    vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vertical.set)
    if horizontal:
        hscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=hscroll.set)
        hscroll.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)
    vertical.pack(side="right", fill="y")
    if columns:
        set_columns(tree, columns)
    return tree


def set_columns(tree: ttk.Treeview, columns: Sequence[str], *, width: int = 100, stretch: bool = True,
                numeric: Mapping[str, int] | None = None) -> None:
    clear_tree(tree)
    if numeric is not None:
        tree.numeric_columns = dict(numeric)  # type: ignore[attr-defined]
    numeric_columns = getattr(tree, "numeric_columns", {})
    tree["columns"] = list(columns)
    for column in columns:
        anchor = "e" if column in numeric_columns else "w"
        command: Callable[[], None] | str = ""
        if getattr(tree, "sortable", False):
            command = (lambda col=column: sort_tree(tree, col))
        tree.heading(column, text=str(column), anchor=anchor, command=command)
        tree.column(column, width=width, minwidth=40, stretch=stretch, anchor=anchor)
    tree.sort_state = (None, False)  # type: ignore[attr-defined]


def _cell_text(tree: ttk.Treeview, column: str, value: object) -> str:
    numeric_columns = getattr(tree, "numeric_columns", {})
    if column in numeric_columns and isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return format_number(value, numeric_columns[column])
    return format_value(value)


def clear_tree(tree: ttk.Treeview) -> None:
    tree.delete(*tree.get_children())


def fill_tree(tree: ttk.Treeview, rows: Iterable[Sequence[object]]) -> int:
    columns = list(tree["columns"])
    count = 0
    for row in rows:
        values = [_cell_text(tree, column, value) for column, value in zip(columns, row)]
        tree.insert("", "end", values=values, tags=("odd",) if count % 2 else ())
        count += 1
    return count


def restripe(tree: ttk.Treeview) -> None:
    for index, item in enumerate(tree.get_children()):
        tree.item(item, tags=("odd",) if index % 2 else ())


def _sort_key(text: str) -> tuple[int, float | str]:
    if text == "":
        return (2, "")
    try:
        return (0, float(text.replace(",", ".")))
    except ValueError:
        return (1, text.lower())


def sort_tree(tree: ttk.Treeview, column: str, reverse: bool | None = None) -> None:
    """Сартаваць радкі па слупку; паўторны клік мяняе напрамак. Стрэлка ў загалоўку паказвае стан."""
    previous_column, previous_reverse = getattr(tree, "sort_state", (None, False))
    if reverse is None:
        reverse = not previous_reverse if previous_column == column else False
    items = [(_sort_key(tree.set(item, column)), item) for item in tree.get_children()]
    items.sort(key=lambda pair: pair[0], reverse=reverse)
    for index, (_key, item) in enumerate(items):
        tree.move(item, "", index)
    for name in tree["columns"]:
        base = str(tree.heading(name, "text")).rstrip(" ▲▼")
        tree.heading(name, text=base + (" ▼" if reverse else " ▲") if name == column else base)
    tree.sort_state = (column, reverse)  # type: ignore[attr-defined]
    restripe(tree)


def tree_rows(tree: ttk.Treeview) -> list[list[str]]:
    return [[str(v) for v in tree.item(item, "values")] for item in tree.get_children()]


def tree_headers(tree: ttk.Treeview) -> list[str]:
    return [str(tree.heading(c, "text")).rstrip(" ▲▼") for c in tree["columns"]]


def tree_to_tsv(tree: ttk.Treeview) -> str:
    """Табліца як тэкст з табуляцыямі: уставляецца ў Excel без дадатковых крокаў."""
    lines = ["\t".join(tree_headers(tree))] + ["\t".join(row) for row in tree_rows(tree)]
    return "\n".join(lines)


def save_tree_file(tree: ttk.Treeview, path: Path) -> int:
    """Захаваць табліцу ў файл: .csv з коскай або .tsv/.txt з табуляцыямі, UTF-8 з BOM для Excel."""
    path = Path(path)
    delimiter = "," if path.suffix.lower() == ".csv" else "\t"
    rows = tree_rows(tree)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(tree_headers(tree))
        writer.writerows(rows)
    return len(rows)


EXPORT_FILETYPES = [("CSV (коска)", "*.csv"), ("Тэкст з табуляцыямі", "*.tsv"), ("Усе файлы", "*.*")]


# ------------------------------------------------------------------ буфер
def copy_to_clipboard(widget: tk.Misc, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)
    widget.update()  # каб на Windows буфер застаўся пасля закрыцця акна


def read_clipboard(widget: tk.Misc) -> str:
    try:
        return widget.clipboard_get()
    except tk.TclError:
        return ""
