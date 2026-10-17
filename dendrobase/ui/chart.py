"""Лёгкі лінейны графік на tk.Canvas: храналогіі і серыі па гадах, без знешніх бібліятэк."""
from __future__ import annotations

import math
import tkinter as tk
from typing import Mapping, Sequence

from .theme import PALETTE, app_font


def nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """«Прыгожыя» дзяленні восі (1, 2, 2.5, 5 x 10^n), якія накрываюць [low, high]."""
    if not (math.isfinite(low) and math.isfinite(high)):
        return []
    if high < low:
        low, high = high, low
    if high == low:
        pad = abs(low) * 0.05 or 0.5
        low, high = low - pad, high + pad
    raw_step = (high - low) / max(1, count)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    residual = raw_step / magnitude
    for candidate in (1, 2, 2.5, 5, 10):
        if residual <= candidate:
            step = candidate * magnitude
            break
    start = math.floor(low / step) * step
    ticks: list[float] = []
    value = start
    while value <= high + step * 1e-9:
        if value >= low - step * 1e-9:
            ticks.append(round(value, 10))
        value += step
    return ticks


def _fmt(value: float | None) -> str:
    if value is None:
        return "–"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}"


class LineChart(tk.Canvas):
    """Некалькі ліній па агульнай восі X. Навядзенне курсора паказвае значэнні за год."""

    MARGIN_LEFT = 60
    MARGIN_RIGHT = 16
    MARGIN_TOP = 28
    MARGIN_BOTTOM = 30

    def __init__(self, master: tk.Misc, *, height: int = 200, title: str = "",
                 empty_text: str = "Няма даных для графіка", **kwargs) -> None:
        super().__init__(master, height=height, highlightthickness=0, background=PALETTE["chart_bg"], **kwargs)
        self.title = title
        self.empty_text = empty_text
        self.x: list[float] = []
        self.series: dict[str, list[float | None]] = {}
        self.colors: dict[str, str] = {}
        self.widths: dict[str, float] = {}
        self.visible: set[str] = set()
        self.legend_names: list[str] | None = None
        self._plot: tuple | None = None
        self._hover_items: list[int] = []
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _e: self._clear_hover())

    # ------------------------------------------------------------- даныя
    def set_data(self, x: Sequence[float], series: Mapping[str, Sequence[float | None]], *,
                 colors: Mapping[str, str] | None = None, widths: Mapping[str, float] | None = None,
                 visible: Sequence[str] | None = None, legend: Sequence[str] | None = None) -> None:
        self.x = list(x)
        self.series = {name: list(values) for name, values in series.items()}
        self.colors = dict(colors or {})
        self.widths = dict(widths or {})
        self.visible = set(visible) if visible is not None else set(self.series)
        self.legend_names = list(legend) if legend is not None else None
        self.redraw()

    def set_visible(self, names: Sequence[str]) -> None:
        self.visible = set(names) & set(self.series)
        self.redraw()

    def clear(self) -> None:
        self.set_data([], {})

    def visible_names(self) -> list[str]:
        return [name for name in self.series if name in self.visible]

    # ------------------------------------------------------------ маляванне
    def redraw(self) -> None:
        self.delete("all")
        self._hover_items = []
        self._plot = None
        width, height = self.winfo_width(), self.winfo_height()
        if width < 60 or height < 60:
            return
        small = app_font(size_delta=-1)
        if self.title:
            self.create_text(self.MARGIN_LEFT, 8, anchor="nw", text=self.title, font=app_font(bold=True),
                             fill=PALETTE["text"])
        names = self.visible_names()
        values = [v for name in names for v in self.series[name] if v is not None and math.isfinite(v)]
        if not self.x or not values:
            self.create_text(width / 2, height / 2, text=self.empty_text, fill=PALETTE["muted"], font=app_font())
            return

        xmin, xmax = min(self.x), max(self.x)
        if xmin == xmax:
            xmin, xmax = xmin - 1, xmax + 1
        ymin, ymax = min(values), max(values)
        pad = (ymax - ymin) * 0.05 or 0.5
        ymin, ymax = ymin - pad, ymax + pad
        x0, x1 = self.MARGIN_LEFT, width - self.MARGIN_RIGHT
        y0, y1 = self.MARGIN_TOP, height - self.MARGIN_BOTTOM

        def sx(value: float) -> float:
            return x0 + (value - xmin) / (xmax - xmin) * (x1 - x0)

        def sy(value: float) -> float:
            return y1 - (value - ymin) / (ymax - ymin) * (y1 - y0)

        self._plot = (x0, x1, y0, y1, xmin, xmax, sx, sy)

        for tick in nice_ticks(ymin, ymax, 5):
            y = sy(tick)
            self.create_line(x0, y, x1, y, fill=PALETTE["grid"])
            self.create_text(x0 - 6, y, anchor="e", text=_fmt(tick), fill=PALETTE["muted"], font=small)
        for tick in nice_ticks(xmin, xmax, 8):
            if not float(tick).is_integer():
                continue
            x = sx(tick)
            self.create_line(x, y0, x, y1, fill=PALETTE["grid"])
            self.create_text(x, y1 + 6, anchor="n", text=str(int(tick)), fill=PALETTE["muted"], font=small)
        self.create_line(x0, y1, x1, y1, fill=PALETTE["axis"])
        self.create_line(x0, y0, x0, y1, fill=PALETTE["axis"])

        for name in names:
            color = self.colors.get(name, PALETTE["accent"])
            line_width = self.widths.get(name, 1.5)
            points: list[float] = []
            for xv, yv in zip(self.x, self.series[name]):
                if yv is None or not math.isfinite(yv):
                    self._flush(points, color, line_width)
                    points = []
                else:
                    points += [sx(xv), sy(yv)]
            self._flush(points, color, line_width)

        legend = self.legend_names if self.legend_names is not None else names
        x = x1
        for name in reversed([n for n in legend if n in self.series]):
            color = self.colors.get(name, PALETTE["accent"])
            text_id = self.create_text(x, 8, anchor="ne", text=name, fill=color, font=app_font(bold=True, size_delta=-1))
            left = self.bbox(text_id)[0]
            self.create_rectangle(left - 14, 10, left - 6, 18, fill=color, outline="")
            x = left - 22

    def _flush(self, points: list[float], color: str, width: float) -> None:
        if len(points) >= 4:
            self.create_line(*points, fill=color, width=width)
        elif len(points) == 2:
            self.create_oval(points[0] - 2, points[1] - 2, points[0] + 2, points[1] + 2, fill=color, outline="")

    # ------------------------------------------------------------ курсор
    def _on_motion(self, event: tk.Event) -> None:
        if not self._plot or not self.x:
            return
        x0, x1, y0, y1, xmin, xmax, sx, sy = self._plot
        if not x0 <= event.x <= x1:
            self._clear_hover()
            return
        target = xmin + (event.x - x0) / (x1 - x0) * (xmax - xmin)
        index = min(range(len(self.x)), key=lambda i: abs(self.x[i] - target))
        year = self.x[index]
        self._clear_hover()
        px = sx(year)
        lines = [_fmt(year)]
        for name in self.visible_names():
            value = self.series[name][index]
            if value is not None:
                lines.append(f"{name}: {_fmt(value)}")
        on_left = px < (x0 + x1) / 2
        items = [self.create_line(px, y0, px, y1, fill=PALETTE["axis"], dash=(3, 3))]
        text_id = self.create_text(px + 10 if on_left else px - 10, y0 + 4, anchor="nw" if on_left else "ne",
                                   text="\n".join(lines), font=app_font(size_delta=-1), fill=PALETTE["text"])
        left, top, right, bottom = self.bbox(text_id)
        box_id = self.create_rectangle(left - 4, top - 2, right + 4, bottom + 2, fill=PALETTE["tooltip_bg"],
                                       outline=PALETTE["axis"])
        self.tag_raise(text_id, box_id)
        self._hover_items = items + [box_id, text_id]

    def _clear_hover(self) -> None:
        for item in self._hover_items:
            self.delete(item)
        self._hover_items = []
