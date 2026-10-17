"""Дапаможныя віджэты: пракручвальная рамка, табліцы, шрыфты, буфер абмену.

Усё, што залежыць ад платформы (кола мышы, буфер), сабрана тут.
"""
from __future__ import annotations

import sys
import tkinter as tk
from datetime import date, datetime
from decimal import Decimal
from tkinter import font as tkfont, ttk
from typing import Iterable, Sequence

_WHEEL_CANVASES: set[tk.Canvas] = set()
_FONTS: dict[str, tkfont.Font] = {}


# ----------------------------------------------------------------- кола мышы
def _wheel_step(event: tk.Event) -> int:
    """Крок пракруткі ў радках: Windows дае delta кратна 120, macOS - малыя лікі, X11 - кнопкі 4/5."""
    number = getattr(event, "num", None)
    if number == 4:
        return -1
    if number == 5:
        return 1
    delta = getattr(event, "delta", 0) or 0
    if sys.platform == "darwin":
        return -int(delta)
    return -int(delta / 120)


def _dispatch_wheel(event: tk.Event) -> str | None:
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


# -------------------------------------------------------------------- шрыфты
def app_font(*, bold: bool = False, size_delta: int = 0, fixed: bool = False) -> tkfont.Font:
    """Сістэмны шрыфт Tk з мадыфікацыямі. Аб'екты кэшуюцца, бо Tk выдаляе шрыфт разам з аб'ектам."""
    key = f"{'fixed' if fixed else 'default'}:{bold}:{size_delta}"
    if key not in _FONTS:
        font = tkfont.nametofont("TkFixedFont" if fixed else "TkDefaultFont").copy()
        options: dict[str, object] = {}
        if bold:
            options["weight"] = "bold"
        if size_delta:
            options["size"] = abs(int(font.cget("size"))) + size_delta
        if options:
            font.configure(**options)
        _FONTS[key] = font
    return _FONTS[key]


# -------------------------------------------------------------------- табліцы
def format_value(value: object) -> str:
    """Паказ значэння з БД у табліцы або полі: None -> пуста, даты дд.мм.гггг, 85.0 -> 85."""
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


def make_treeview(parent: tk.Misc, columns: Sequence[str] = (), *, height: int | None = None,
                  horizontal: bool = True) -> ttk.Treeview:
    """Treeview з палосамі пракруткі ў асобнай рамцы. Рамка даступная як tree.master."""
    frame = ttk.Frame(parent)
    options: dict[str, object] = {"show": "headings"}
    if height is not None:
        options["height"] = height
    tree = ttk.Treeview(frame, **options)
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


def set_columns(tree: ttk.Treeview, columns: Sequence[str], *, width: int = 100, stretch: bool = True) -> None:
    clear_tree(tree)
    tree["columns"] = list(columns)
    for column in columns:
        tree.heading(column, text=str(column))
        tree.column(column, width=width, minwidth=40, stretch=stretch, anchor="w")


def clear_tree(tree: ttk.Treeview) -> None:
    tree.delete(*tree.get_children())


def fill_tree(tree: ttk.Treeview, rows: Iterable[Sequence[object]]) -> int:
    count = 0
    for row in rows:
        tree.insert("", "end", values=[format_value(v) for v in row])
        count += 1
    return count


def tree_rows(tree: ttk.Treeview) -> list[list[str]]:
    return [[str(v) for v in tree.item(item, "values")] for item in tree.get_children()]


def tree_to_tsv(tree: ttk.Treeview) -> str:
    """Табліца як тэкст з табуляцыямі: уставляецца ў Excel без дадатковых крокаў."""
    header = [str(c) for c in tree["columns"]]
    lines = ["\t".join(header)] + ["\t".join(row) for row in tree_rows(tree)]
    return "\n".join(lines)


def copy_to_clipboard(widget: tk.Misc, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)
    widget.update()  # каб на Windows буфер застаўся пасля закрыцця акна


def read_clipboard(widget: tk.Misc) -> str:
    try:
        return widget.clipboard_get()
    except tk.TclError:
        return ""
