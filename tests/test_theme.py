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


@pytest.fixture()
def themed_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk недаступны: {exc}")
    root.withdraw()
    yield root
    try:
        apply_theme(root, "system")
        root.destroy()
    except tk.TclError:
        pass


def test_light_and_dark_modes_change_palette_on_every_platform(themed_root):
    from dendrobase.ui import theme
    apply_theme(themed_root, "dark")
    assert theme.current_mode() == "dark"
    assert is_dark(PALETTE["table_bg"]) and not is_dark(PALETTE["text"])
    assert luminance(resolve_rgb(PALETTE["stripe"])) > luminance(resolve_rgb(PALETTE["table_bg"]))
    apply_theme(themed_root, "light")
    assert theme.current_mode() == "light"
    assert not is_dark(PALETTE["table_bg"]) and is_dark(PALETTE["text"])
    apply_theme(themed_root, "nonsense")  # невядомы рэжым = як у сістэме
    assert theme.current_mode() == "system"


def test_portable_dark_theme_is_used_where_aqua_appearance_is_unavailable(themed_root, monkeypatch):
    from tkinter import ttk
    from dendrobase.ui import theme
    monkeypatch.setattr(theme, "_mac_appearance", lambda root, mode: False)
    style = apply_theme(themed_root, "dark")
    assert style.theme_use() == theme.DARK_THEME_NAME
    assert is_dark(PALETTE["table_bg"]) and is_dark(style.lookup("Treeview", "background"))
    assert style.lookup("TEntry", "fieldbackground") and is_dark(style.lookup("TEntry", "fieldbackground"))
    text = tk.Text(themed_root)  # класічныя віджэты атрымліваюць колеры праз базу опцый
    if themed_root.tk.call("tk", "windowingsystem") != "aqua":
        assert is_dark(text.cget("background"), themed_root)
    apply_theme(themed_root, "light")
    assert style.theme_use() != theme.DARK_THEME_NAME  # назад да натыўнай тэмы платформы
    assert ttk.Style(themed_root).theme_use() in ("aqua", "vista", "clam")
    if style.theme_use() != "aqua":  # без кіравання выглядам Aqua светлы рэжым там застаецца за сістэмай
        assert not is_dark(PALETTE["table_bg"])


def test_new_toplevels_follow_chosen_appearance_on_macos(themed_root):
    from dendrobase.ui.theme import prepare_toplevel
    if themed_root.tk.call("tk", "windowingsystem") != "aqua":
        pytest.skip("толькі macOS")
    try:
        apply_theme(themed_root, "dark")
        window = tk.Toplevel(themed_root)
        window.withdraw()
        prepare_toplevel(window)
        themed_root.update_idletasks()
        assert int(themed_root.tk.call("::tk::unsupported::MacWindowStyle", "isdark", str(window))) == 1
        apply_theme(themed_root, "light")  # ужо адкрытыя вокны таксама пераключаюцца
        themed_root.update_idletasks()
        assert int(themed_root.tk.call("::tk::unsupported::MacWindowStyle", "isdark", str(window))) == 0
    except tk.TclError as exc:
        pytest.skip(f"MacWindowStyle недаступны: {exc}")
