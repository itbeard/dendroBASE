import math
import tkinter as tk
from decimal import Decimal

import pytest

from dendrobase.ui.chart import LineChart, nice_ticks


def test_nice_ticks_cover_range_with_round_steps():
    assert nice_ticks(0.87, 1.31, 5) == [0.9, 1.0, 1.1, 1.2, 1.3]
    assert nice_ticks(1850, 2019, 8) == [1850, 1875, 1900, 1925, 1950, 1975, 2000]
    assert nice_ticks(5, 5)  # роўныя межы даюць хаця б адно дзяленне
    assert nice_ticks(math.nan, 1) == []
    assert nice_ticks(3, 1) == nice_ticks(1, 3)


@pytest.fixture()
def shown_root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk недаступны: {exc}")
    window.geometry("500x300+0+0")
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


def test_line_chart_draws_lines_legend_and_hover(shown_root):
    chart = LineChart(shown_root, width=480, height=240, title="CRN")
    chart.pack(fill="both", expand=True)
    shown_root.update()
    assert chart.find_all() and chart.x == []  # пусты стан: подпіс «няма даных»
    chart.set_data([1900, 1901, 1902, 1903], {"raw": [1.0, None, 1.2, 1.3], "std": [0.9, 1.0, 1.1, 1.0]},
                   colors={"raw": "#4C78A8", "std": "#F58518"}, visible=["raw", "std"])
    shown_root.update()
    lines = [i for i in chart.find_all() if chart.type(i) == "line"]
    assert len(lines) > 4  # восі, сетка і дзве серыі
    texts = [chart.itemcget(i, "text") for i in chart.find_all() if chart.type(i) == "text"]
    assert "raw" in texts and "std" in texts and "CRN" in texts
    chart.set_visible(["std"])
    assert chart.visible_names() == ["std"]
    event = tk.Event()
    event.x, event.y = chart.MARGIN_LEFT + 5, 100
    chart._on_motion(event)
    hover_texts = [chart.itemcget(i, "text") for i in chart._hover_items if chart.type(i) == "text"]
    assert hover_texts and hover_texts[0].startswith("1900")
    chart._clear_hover()
    assert chart._hover_items == []
    chart.clear()
    assert chart.visible_names() == []


def test_line_chart_accepts_decimal_values(shown_root):
    """Значэнні numeric з базы прыходзяць як Decimal; графік не павінен падаць на арыфметыцы з float."""
    chart = LineChart(shown_root, width=480, height=240)
    chart.pack(fill="both", expand=True)
    shown_root.update()
    chart.set_data([1900, 1901, 1902], {"raw": [Decimal("1.2"), None, Decimal("1.35")]}, visible=["raw"])
    shown_root.update()
    assert chart.series["raw"] == [1.2, None, 1.35]
    assert all(isinstance(value, float) for value in chart.series["raw"] if value is not None)
    assert [item for item in chart.find_all() if chart.type(item) == "line"]
