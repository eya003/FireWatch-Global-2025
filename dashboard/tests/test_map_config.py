import json

import pydeck as pdk

from dashboard.map_config import WEB_MERCATOR_LATITUDE_LIMIT, WORLD_BOUNDS, world_map_view


def test_world_view_serializes_repeat_and_longitude_bounds():
    deck = pdk.Deck(views=[world_map_view()])
    view = json.loads(deck.to_json())["views"][0]

    assert view["@@type"] == "MapView"
    assert view["repeat"] is False
    assert view["controller"]["maxBounds"] == WORLD_BOUNDS
    assert WORLD_BOUNDS == [[-180, -WEB_MERCATOR_LATITUDE_LIMIT], [180, WEB_MERCATOR_LATITUDE_LIMIT]]
    assert view["controller"]["dragPan"] is True
    assert view["controller"]["scrollZoom"] is True
    assert view["controller"]["doubleClickZoom"] is True
