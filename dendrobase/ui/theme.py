"""Тэма інтэрфейсу: натыўны стыль ttk для кожнай АС, светлы або цёмны рэжым, шрыфты, палітра, адступы.

Рэжымы: "system" (як у сістэме), "light", "dark". На macOS светлы і цёмны выгляд пераключаецца
выглядам (appearance) вокнаў Aqua, таму віджэты застаюцца натыўнымі; новыя вокны ідуць за сістэмай,
і дыялогі выклікаюць prepare_toplevel(). На Windows і Linux натыўныя тэмы ttk цёмнага варыянту не маюць,
таму для «цёмнай» ствараецца ўласная тэма на базе clam, а tk.Text, tk.Canvas і tk.Menu атрымліваюць
яе колеры праз базу опцый.

Палітра PALETTE пералічваецца ў apply_theme() ад рэальнага фону табліц бягучай тэмы, таму паласы
«зебры» і вылучэнне радка бачныя і на светлым, і на цёмным фоне.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont, ttk
from typing import Iterator

PAD = 8            # базавы крок адступаў

THEMES = ("system", "light", "dark")
DEFAULT_THEME = "system"
DARK_THEME_NAME = "dendrobase-dark"
_MAC_APPEARANCE = {"system": "auto", "light": "aqua", "dark": "darkaqua"}
_current_mode = DEFAULT_THEME

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

# Колеры ўласнай цёмнай тэмы для Windows і Linux
_DARK_UI = {
    "bg": "#2B2B2B", "fg": "#E5E7EB", "field": "#1E1E1E", "border": "#454545", "raised": "#3A3A3A",
    "active": "#4A4A4A", "pressed": "#262626", "disabled": "#7A7A7A", "trough": "#242424",
}

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


# -------------------------------------------------------------------- рэжымы
def normalize_theme(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in THEMES else DEFAULT_THEME


def current_mode() -> str:
    """Рэжым, прыменены апошнім выклікам apply_theme()."""
    return _current_mode


def _toplevels(root: tk.Misc) -> Iterator[tk.Misc]:
    """Карэннае акно і ўсе вокны Toplevel у ім (у тым ліку ўкладзеныя ў дыялогі)."""
    yield root
    stack = list(root.winfo_children())
    while stack:
        widget = stack.pop()
        if isinstance(widget, tk.Toplevel):
            yield widget
        stack.extend(widget.winfo_children())


def _set_mac_appearance(window: tk.Misc, mode: str) -> bool:
    try:
        window.tk.call("::tk::unsupported::MacWindowStyle", "appearance", str(window), _MAC_APPEARANCE[mode])
    except tk.TclError:
        return False
    return True


def _mac_appearance(root: tk.Misc, mode: str) -> bool:
    """Светлы або цёмны выгляд усіх вокнаў Aqua. False, калі гэты Tk яго не падтрымлівае."""
    root.update_idletasks()  # інакш Tk скардзіцца, што не можа прачытаць выгляд яшчэ не адмаляванага акна
    if not all(_set_mac_appearance(window, mode) for window in _toplevels(root)):
        return False
    root.update_idletasks()  # сістэмныя колеры пералічваюцца пасля змены выгляду
    return True


def prepare_toplevel(window: tk.Misc) -> None:
    """Новае акно пераймае выбраны рэжым: на macOS новыя вокны інакш ідуць за сістэмай, а не за праграмай."""
    if window.tk.call("tk", "windowingsystem") == "aqua":
        _set_mac_appearance(window, _current_mode)


def _ensure_dark_theme(style: ttk.Style) -> None:
    """Уласная цёмная тэма на базе clam для платформ без натыўнага цёмнага рэжыму ttk."""
    if DARK_THEME_NAME in style.theme_names():
        return
    c = _DARK_UI
    flat = {"bordercolor": c["border"], "lightcolor": c["bg"], "darkcolor": c["bg"]}
    field = {"fieldbackground": c["field"], "foreground": c["fg"], "insertcolor": c["fg"],
             "bordercolor": c["border"], "lightcolor": c["border"], "darkcolor": c["border"]}
    style.theme_create(DARK_THEME_NAME, parent="clam", settings={
        ".": {"configure": {
            "background": c["bg"], "foreground": c["fg"], "fieldbackground": c["field"],
            "troughcolor": c["trough"], "selectbackground": _DARK["select_bg"], "selectforeground": _DARK["select_fg"],
            "insertcolor": c["fg"], "focuscolor": _DARK["accent"], **flat,
        }, "map": {"foreground": [("disabled", c["disabled"])]}},
        "TButton": {"configure": {"background": c["raised"], "lightcolor": c["raised"], "darkcolor": c["raised"],
                                  "bordercolor": c["border"]},
                    "map": {"background": [("disabled", c["bg"]), ("pressed", c["pressed"]), ("active", c["active"])],
                            "lightcolor": [("pressed", c["pressed"])], "darkcolor": [("pressed", c["pressed"])]}},
        "TEntry": {"configure": field,
                   "map": {"fieldbackground": [("readonly", c["bg"]), ("disabled", c["bg"])]}},
        "TCombobox": {"configure": {**field, "background": c["raised"], "arrowcolor": c["fg"]},
                      "map": {"fieldbackground": [("readonly", c["raised"]), ("disabled", c["bg"])],
                              "background": [("active", c["active"])]}},
        "TSpinbox": {"configure": {**field, "background": c["raised"], "arrowcolor": c["fg"]}},
        "TCheckbutton": {"configure": {"indicatorbackground": c["field"], "indicatorforeground": c["fg"]},
                         "map": {"indicatorbackground": [("disabled", c["bg"])]}},
        "TRadiobutton": {"configure": {"indicatorbackground": c["field"], "indicatorforeground": c["fg"]},
                         "map": {"indicatorbackground": [("disabled", c["bg"])]}},
        "TNotebook": {"configure": {"background": c["bg"], "tabmargins": (2, 4, 2, 0), **flat}},
        "TNotebook.Tab": {"configure": {"background": c["raised"], "foreground": c["fg"], "bordercolor": c["border"],
                                        "lightcolor": c["raised"], "padding": (8, 4)},
                          "map": {"background": [("selected", c["bg"]), ("active", c["active"])],
                                  "lightcolor": [("selected", c["bg"])]}},
        "Treeview": {"configure": {"background": c["field"], "fieldbackground": c["field"], "foreground": c["fg"],
                                   "bordercolor": c["border"], "lightcolor": c["border"], "darkcolor": c["border"]}},
        "Treeview.Heading": {"configure": {"background": c["raised"], "foreground": c["fg"], "bordercolor": c["border"],
                                           "lightcolor": c["raised"], "darkcolor": c["raised"], "relief": "flat"},
                             "map": {"background": [("active", c["active"])]}},
        "TLabelframe": {"configure": {"background": c["bg"], **flat}},
        "TLabelframe.Label": {"configure": {"background": c["bg"], "foreground": c["fg"]}},
        "TScrollbar": {"configure": {"background": c["raised"], "troughcolor": c["trough"], "arrowcolor": c["fg"],
                                     "bordercolor": c["trough"], "lightcolor": c["raised"], "darkcolor": c["raised"]},
                       "map": {"background": [("active", c["active"]), ("pressed", c["active"])]}},
        "TSeparator": {"configure": {"background": c["border"]}},
        "TPanedwindow": {"configure": {"background": c["bg"]}},
        "Sash": {"configure": {"sashthickness": 6, "gripcount": 0}},
    })


def _select_theme(root: tk.Misc, style: ttk.Style, mode: str) -> None:
    if root.tk.call("tk", "windowingsystem") == "aqua" and _mac_appearance(root, mode):
        wanted = "aqua"
    elif mode == "dark":
        _ensure_dark_theme(style)
        wanted = DARK_THEME_NAME
    else:
        wanted = {"darwin": "aqua", "win32": "vista"}.get(sys.platform, "clam")
    if wanted in style.theme_names() and style.theme_use() != wanted:
        try:
            style.theme_use(wanted)
        except tk.TclError:
            pass


def _configure_classic_widgets(root: tk.Misc, style: ttk.Style) -> None:
    """tk.Text, tk.Canvas і tk.Menu не ведаюць пра ttk: даём ім колеры бягучай тэмы праз базу опцый.

    Дзейнічае на віджэты, створаныя пасля выкліку (інтэрфейс перабудоўваецца пры змене тэмы).
    На macOS не патрэбна: там класічныя віджэты малююцца сістэмнымі колерамі.
    """
    background = style.lookup(".", "background")
    foreground = style.lookup(".", "foreground") or PALETTE["text"]
    field = style.lookup("TEntry", "fieldbackground") or style.lookup(".", "fieldbackground") or PALETTE["table_bg"]
    active = style.lookup("TButton", "background", ("active",)) or background
    options = {
        "*Canvas.background": background,
        "*Canvas.highlightBackground": background,
        "*Text.background": field,
        "*Text.foreground": foreground,
        "*Text.insertBackground": foreground,
        "*Text.selectBackground": PALETTE["select_bg"],
        "*Text.selectForeground": PALETTE["select_fg"],
        "*Text.highlightBackground": background,
        "*Text.highlightColor": PALETTE["accent"],
        "*Menu.background": background,
        "*Menu.foreground": foreground,
        "*Menu.activeBackground": active,
        "*Menu.activeForeground": foreground,
        "*Menu.disabledForeground": PALETTE["muted"],
    }
    for pattern, value in options.items():
        if value:
            root.option_add(pattern, value)


def apply_theme(root: tk.Misc, mode: str = DEFAULT_THEME) -> ttk.Style:
    """Прымяніць тэму і пералічыць PALETTE. Можна выклікаць паўторна, каб змяніць рэжым на хаду."""
    global _current_mode
    mode = normalize_theme(mode)
    _current_mode = mode
    style = ttk.Style(root)
    _select_theme(root, style, mode)

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
    # фон вокнаў як яго разумее ttk (на macOS сімвалічная назва, якая сочыць за выглядам акна)
    PALETTE["window_bg"] = style.lookup(".", "background") or (_DARK_UI["bg"] if dark else "#F0F0F0")
    if root.tk.call("tk", "windowingsystem") != "aqua":
        _configure_classic_widgets(root, style)

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
