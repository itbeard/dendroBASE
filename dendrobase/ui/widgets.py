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

from .theme import PALETTE, app_font

_WHEEL_CANVASES: set[tk.Canvas] = set()


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

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0)


# ------------------------------------------------------------------ падказкі
_ACTIVE_TOOLTIPS: set["Tooltip"] = set()


def hide_all_tooltips() -> None:
    for tooltip in list(_ACTIVE_TOOLTIPS):
        tooltip.hide()


def _bind_global_tooltip_hide(widget: tk.Misc) -> None:
    """Любы клік, клавіша або змена фокусу хаваюць усе падказкі: страховка ад «завіслай» падказкі."""
    app_root = widget.nametowidget(".")
    if getattr(app_root, "_dendrobase_tooltips_bound", False):
        return
    for sequence in ("<ButtonPress>", "<Key>", "<FocusOut>", "<Unmap>"):
        app_root.bind_all(sequence, lambda _e: hide_all_tooltips(), add="+")
    setattr(app_root, "_dendrobase_tooltips_bound", True)


class Tooltip:
    """Усплывальная падказка каля курсора.

    Паказваецца з затрымкай, хаваецца пры выхадзе курсора, кліку, клавішы, уваходзе курсора
    ў само акенца падказкі і праз AUTO_HIDE_MS. Так яна ніколі не перакрывае суседнія кнопкі надоўга.
    """

    AUTO_HIDE_MS = 4000

    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 600) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after: str | None = None
        self._auto_hide: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Motion>", self._on_motion, add="+")
        for sequence in ("<Leave>", "<ButtonPress>", "<Destroy>"):
            widget.bind(sequence, self.hide, add="+")
        _bind_global_tooltip_hide(widget)

    def _on_motion(self, event: tk.Event) -> None:
        if self._tip is None:
            self._schedule(event)

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._cancel_timer()
        self._after = self.widget.after(self.delay_ms, self._show)

    def _cancel_timer(self) -> None:
        for name in ("_after", "_auto_hide"):
            handle = getattr(self, name)
            if handle is not None:
                try:
                    self.widget.after_cancel(handle)
                except tk.TclError:
                    pass
                setattr(self, name, None)

    def _show(self) -> None:
        self._after = None
        if self._tip is not None or not self.text:
            return
        try:
            if not self.widget.winfo_exists() or not self.widget.winfo_ismapped():
                return
            x, y = self.widget.winfo_pointerxy()
            tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            try:
                tip.attributes("-topmost", True)
            except tk.TclError:
                pass
            tk.Label(tip, text=self.text, justify="left", background=PALETTE["tooltip_bg"],
                     foreground=PALETTE["text"], relief="solid", borderwidth=1, padx=6, pady=3,
                     font=app_font(size_delta=-1), wraplength=340).pack()
            tip.update_idletasks()
            width, height = tip.winfo_reqwidth(), tip.winfo_reqheight()
            x = min(x + 14, self.widget.winfo_screenwidth() - width - 8)
            y = y + 20
            if y + height > self.widget.winfo_screenheight() - 8:
                y = y - height - 28
            tip.wm_geometry(f"+{max(0, x)}+{max(0, y)}")
            tip.bind("<Enter>", self.hide)
            tip.bind("<ButtonPress>", self.hide)
        except tk.TclError:
            return
        self._tip = tip
        _ACTIVE_TOOLTIPS.add(self)
        self._auto_hide = self.widget.after(self.AUTO_HIDE_MS, self.hide)

    def hide(self, _event: tk.Event | None = None) -> None:
        self._cancel_timer()
        _ACTIVE_TOOLTIPS.discard(self)
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None

    @property
    def visible(self) -> bool:
        return self._tip is not None


def add_tooltip(widget: tk.Widget, text: str) -> None:
    if text:
        Tooltip(widget, text)


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
