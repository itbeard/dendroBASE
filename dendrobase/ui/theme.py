"""Тэма інтэрфейсу: натыўны стыль ttk для кожнай АС, шрыфты, палітра, адступы.

Палітра падладжваецца пад светлую або цёмную тэму сістэмы: пасля apply_theme() у PALETTE
ляжаць колеры, разлічаныя ад рэальнага фону табліц, таму паласы «зебры» і вылучэнне
радка бачныя і на светлым, і на цёмным фоне.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont, ttk

PAD = 8            # базавы крок адступаў

_LIGHT = {
    "text": "#111827",
    "muted": "#6B7280",
    "accent": "#2563EB",
    "danger": "#B91C1C",
    "ok": "#15803D",
    "warn": "#B45309",
    "stripe": "#F3F4F6",       # пералічваецца ў apply_theme ад фону табліцы
    "select_bg": "#E8A878",    # прыглушаны аранжавы для вылучанага радка
    "select_fg": "#1F2937",
    "grid": "#E5E7EB",
    "axis": "#9CA3AF",
    "chart_bg": "#FFFFFF",
    "tooltip_bg": "#FFFBE6",
    "series": "#C4C8CF",
    "highlight": "#D62728",
}
_DARK = {
    "text": "#E5E7EB",
    "muted": "#9CA3AF",
    "accent": "#60A5FA",
    "danger": "#F87171",
    "ok": "#4ADE80",
    "warn": "#FBBF24",
    "select_bg": "#8F4F2F",    # прыглушаная тэракота для вылучанага радка
    "select_fg": "#FFFFFF",
    "grid": "#3A3A3C",
    "axis": "#6B7280",
    "tooltip_bg": "#2C2C2E",
    "series": "#6B7280",
    "highlight": "#F87171",
}
PALETTE: dict[str, str] = dict(_LIGHT)
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


# ------------------------------------------------------------------- колеры
def resolve_rgb(color: str, root: tk.Misc | None = None) -> tuple[float, float, float] | None:
    """Колер як (r, g, b) у дыяпазоне 0..1: #rrggbb напрамую, сістэмныя назвы праз Tk."""
    if not color:
        return None
    if color.startswith("#") and len(color) == 7:
        try:
            return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]
        except ValueError:
            return None
    if root is None:
        return None
    try:
        r, g, b = root.winfo_rgb(color)
    except tk.TclError:
        return None
    return (r / 65535, g / 65535, b / 65535)


def to_hex(rgb: tuple[float, float, float]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in rgb)


def luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def mix(color: str, other: str, amount: float, root: tk.Misc | None = None) -> str:
    """Змяшаць color з other: amount=0 дае color, amount=1 дае other."""
    first, second = resolve_rgb(color, root), resolve_rgb(other, root)
    if first is None or second is None:
        return color
    return to_hex(tuple(a + (b - a) * amount for a, b in zip(first, second)))  # type: ignore[arg-type]


def table_background(root: tk.Misc, style: ttk.Style) -> str:
    """Рэальны фон табліц бягучай тэмы ў выглядзе #rrggbb."""
    candidates = [style.lookup("Treeview", "background")]
    if root.tk.call("tk", "windowingsystem") == "aqua":
        candidates.append("systemTextBackgroundColor")
    candidates += [style.lookup(".", "background"), "white"]
    for candidate in candidates:
        rgb = resolve_rgb(candidate, root)
        if rgb is not None:
            return to_hex(rgb)
    return "#ffffff"


def is_dark(color: str, root: tk.Misc | None = None) -> bool:
    rgb = resolve_rgb(color, root)
    return rgb is not None and luminance(rgb) < 0.5


def _fixed_map(style: ttk.Style, option: str) -> list:
    """Абыход хібы Tk 8.6.9+: без гэтага тэгі радкоў Treeview (зебра) не афарбоўваюцца."""
    return [item for item in style.map("Treeview", query_opt=option)
            if item[:2] != ("!disabled", "!selected") and item[0] != "selected"]


def apply_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    preferred = {"darwin": "aqua", "win32": "vista"}.get(sys.platform, "clam")
    if preferred in style.theme_names() and style.theme_use() != preferred:
        try:
            style.theme_use(preferred)
        except tk.TclError:
            pass

    base = table_background(root, style)
    dark = is_dark(base)
    PALETTE.clear()
    PALETTE.update(_LIGHT)
    if dark:
        PALETTE.update(_DARK)
    # паласа «зебры»: ледзь святлейшая за цёмны фон або ледзь цямнейшая за светлы
    PALETTE["stripe"] = mix(base, "#ffffff", 0.10) if dark else mix(base, "#000000", 0.05)
    PALETTE["chart_bg"] = mix(base, "#ffffff", 0.03) if dark else "#ffffff"
    PALETTE["table_bg"] = base

    base_font = tkfont.nametofont("TkDefaultFont")
    style.configure("Title.TLabel", font=app_font(bold=True, size_delta=5))
    style.configure("Heading.TLabel", font=app_font(bold=True, size_delta=1))
    style.configure("Subtitle.TLabel", foreground=PALETTE["muted"])
    style.configure("Hint.TLabel", foreground=PALETTE["muted"], font=app_font(size_delta=-1))
    style.configure("Error.TLabel", foreground=PALETTE["danger"])
    style.configure("Ok.TLabel", foreground=PALETTE["ok"])
    style.configure("Warn.TLabel", foreground=PALETTE["warn"])
    style.configure("Status.TLabel", foreground=PALETTE["muted"])
    style.configure("Section.TLabelframe.Label", font=app_font(bold=True))
    style.configure("Treeview", rowheight=base_font.metrics("linespace") + 8)
    style.configure("Treeview.Heading", font=app_font(bold=True))
    style.map(
        "Treeview",
        background=[("selected", PALETTE["select_bg"])] + _fixed_map(style, "background"),
        foreground=[("selected", PALETTE["select_fg"])] + _fixed_map(style, "foreground"),
    )
    return style
