"""PyDeck view configuration for a bounded, single-world map."""

import pydeck as pdk


WEB_MERCATOR_LATITUDE_LIMIT = 85.051129
WORLD_BOUNDS = [
    [-180, -WEB_MERCATOR_LATITUDE_LIMIT],
    [180, WEB_MERCATOR_LATITUDE_LIMIT],
]


def world_map_view() -> pdk.View:
    """Keep a single world copy and constrain panning to Web Mercator bounds."""
    return pdk.View(
        type="MapView",
        repeat=False,
        controller={
            "maxBounds": WORLD_BOUNDS,
            "dragPan": True,
            "scrollZoom": True,
            "doubleClickZoom": True,
            "keyboard": True,
        },
    )
