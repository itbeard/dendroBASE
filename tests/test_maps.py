import pytest

from dendrobase.maps import build_map, popup_html, save_map
from dendrobase.models import ProbePoint


def test_build_map_centers_and_adds_markers(tmp_path):
    points = [ProbePoint("a", 52.0, 26.0, "С", 1900, 2000), ProbePoint("b <x>", 54.0, 28.0)]
    fmap = build_map(points)
    assert fmap.location == [53.0, 27.0]
    html = save_map(fmap, tmp_path / "map.html").read_text(encoding="utf-8")
    assert html.count("L.marker(") == 2
    assert "&lt;x&gt;" in html  # назвы экрануюцца


def test_popup_contains_species_and_years():
    text = popup_html(ProbePoint("a", 52.0, 26.0, "С", 1900, 2000))
    assert "С" in text and "1900" in text and "2000" in text
    assert "н/д" in popup_html(ProbePoint("a", 52.0, 26.0))


def test_build_map_requires_points():
    with pytest.raises(ValueError):
        build_map([])
