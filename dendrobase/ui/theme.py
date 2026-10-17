"""Тэма інтэрфейсу: натыўны стыль ttk для кожнай АС, шрыфты, палітра, адступы."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont, ttk

PAD = 8            # базавы крок адступаў
PALETTE = {
    "text": "#111827",
    "muted": "#6B7280",
    "accent": "#2563EB",
    "danger": "#B91C1C",
    "ok": "#15803D",
    "warn": "#B45309",
    "stripe": "#F3F4F6",
    "grid": "#E5E7EB",
    "axis": "#9CA3AF",
    "chart_bg": "#FFFFFF",
    "tooltip_bg": "#FFFBE6",
    "series": "#C4C8CF",
    "highlight": "#D62728",
}
# Колеры відаў храналогіі (палітра Tableau 10: адрозніваюцца і для дальтонікаў)
CRN_COLORS = {"raw": "#4C78A8", "std": "#F58518", "res": "#54A24B", "ars": "#B279A2"}

_FONTS: dict[str, tkfont.Font] = {}


def app_font(*, bold: bool = False, size_delta: int = 0, fixed: bool = False) -> tkfont.Font:
    """Сістэмны шрыфт Tk з мадыфікацыямі. Аб'екты кэшуюцца: Tk выдаляе шрыфт разам з аб'ектам."""
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


def _fixed_map(style: ttk.Style, option: str) -> list:
    """Абыход хібы Tk 8.6.9+: без гэтага тэгі радкоў Treeview (зебра) не афарбоўваюцца."""
    return [item for item in style.map("Treeview", query_opt=option) if item[:2] != ("!disabled", "!selected")]


def apply_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    preferred = {"darwin": "aqua", "win32": "vista"}.get(sys.platform, "clam")
    if preferred in style.theme_names() and style.theme_use() != preferred:
        try:
            style.theme_use(preferred)
        except tk.TclError:
            pass
    base = tkfont.nametofont("TkDefaultFont")
    style.configure("Title.TLabel", font=app_font(bold=True, size_delta=5))
    style.configure("Heading.TLabel", font=app_font(bold=True, size_delta=1))
    style.configure("Subtitle.TLabel", foreground=PALETTE["muted"])
    style.configure("Hint.TLabel", foreground=PALETTE["muted"], font=app_font(size_delta=-1))
    style.configure("Error.TLabel", foreground=PALETTE["danger"])
    style.configure("Ok.TLabel", foreground=PALETTE["ok"])
    style.configure("Warn.TLabel", foreground=PALETTE["warn"])
    style.configure("Status.TLabel", foreground=PALETTE["muted"])
    style.configure("Section.TLabelframe.Label", font=app_font(bold=True))
    style.configure("Treeview", rowheight=base.metrics("linespace") + 8)
    style.configure("Treeview.Heading", font=app_font(bold=True))
    style.map("Treeview", foreground=_fixed_map(style, "foreground"), background=_fixed_map(style, "background"))
    return style
