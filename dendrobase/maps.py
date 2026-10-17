"""Карта пробных плошчаў (folium) і яе адкрыццё ў браўзеры."""
from __future__ import annotations

import html
import logging
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .models import ProbePoint

if TYPE_CHECKING:  # folium цягне pandas і numpy, таму імпартуецца толькі калі карта сапраўды будуецца
    import folium

log = logging.getLogger(__name__)


def popup_html(point: ProbePoint) -> str:
    years = f"{point.first_year or '?'}–{point.last_year or '?'}"
    return (
        f"<b>{html.escape(point.name)}</b><br>"
        f"Парода: {html.escape(point.poroda or 'н/д')}<br>"
        f"Гады: {years}"
    )


def build_map(points: Sequence[ProbePoint], *, zoom_start: int = 7,
              tiles: str = "OpenStreetMap") -> "folium.Map":
    """Карта з маркерамі ўсіх ПП. Цэнтр: сярэдняе каардынат."""
    import folium  # лянівы імпарт, гл. каментар уверсе

    if not points:
        raise ValueError("Няма пробных плошчаў з каардынатамі")
    center_lat = sum(p.lat for p in points) / len(points)
    center_lon = sum(p.lon for p in points) / len(points)
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles=tiles)
    for point in points:
        folium.Marker(
            [point.lat, point.lon],
            popup=folium.Popup(popup_html(point), max_width=260),
            tooltip=point.name,
        ).add_to(fmap)
    return fmap


def temp_map_path() -> Path:
    """Унікальны шлях для часовай карты ў сістэмнай папцы temp."""
    directory = Path(tempfile.gettempdir()) / "dendrobase"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"map_{time.strftime('%Y%m%d_%H%M%S')}.html"


def save_map(fmap: "folium.Map", path: Path) -> Path:
    """Захаваць карту ў HTML. Файл пішацца пасля закрыцця ўсіх дэскрыптараў, таму працуе і на Windows."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(path))
    log.info("Карта захавана: %s", path)
    return path


def open_in_browser(path: Path) -> bool:
    """Адкрыць файл у сістэмным браўзеры. file:// URI працуе аднолькава на Windows і macOS."""
    uri = Path(path).resolve().as_uri()
    opened = webbrowser.open(uri)
    if not opened:
        log.warning("Браўзер не адкрыўся для %s", uri)
    return opened
