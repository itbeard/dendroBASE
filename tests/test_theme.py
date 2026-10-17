import re
import tkinter as tk

import pytest

from dendrobase.ui.theme import PALETTE, apply_theme, is_dark, luminance, mix, resolve_rgb, to_hex

HEX = re.compile(r"^#[0-9a-f]{6}$")


def test_colour_helpers():
    assert resolve_rgb("#ff0000") == (1.0, 0.0, 0.0)
    assert resolve_rgb("nope") is None
    assert to_hex((1.0, 0.5, 0.0)) == "#ff8000"
    assert mix("#000000", "#ffffff", 0.5) == "#808080"
    assert mix("#202020", "#ffffff", 0.10) == "#363636"
    assert luminance((1.0, 1.0, 1.0)) == pytest.approx(1.0)
    assert is_dark("#1e1e1e") and not is_dark("#ffffff")


def test_apply_theme_derives_stripe_and_selection_from_background():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk недаступны: {exc}")
    try:
        root.withdraw()
        style = apply_theme(root)
        assert HEX.match(PALETTE["stripe"]) and HEX.match(PALETTE["table_bg"])
        base_dark = is_dark(PALETTE["table_bg"])
        stripe_l, base_l = luminance(resolve_rgb(PALETTE["stripe"])), luminance(resolve_rgb(PALETTE["table_bg"]))
        assert (stripe_l > base_l) if base_dark else (stripe_l < base_l)  # паласа заўсёды кантрастуе з фонам
        assert abs(stripe_l - base_l) < 0.12  # але не моцна
        background_map = style.map("Treeview", query_opt="background")
        assert background_map[0] == ("selected", PALETTE["select_bg"])
        assert style.map("Treeview", query_opt="foreground")[0] == ("selected", PALETTE["select_fg"])
        assert is_dark(PALETTE["text"]) != base_dark  # тэкст графіка кантрастуе з фонам
    finally:
        root.destroy()
