import json

import pandas as pd

from dashboard.countries import (
    UNKNOWN_COUNTRY,
    get_zone_country_map,
    get_zone_display_positions,
)
from dashboard.data import load_fire_data, rank_zone_map_data


def test_country_lookup_uses_cell_centers_holes_and_unknown_fallback(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Testland"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
                        [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4], [0.1, 0.1]],
                    ],
                },
            }
        ],
    }
    path = tmp_path / "countries.geojson"
    path.write_text(json.dumps(geojson), encoding="utf-8")

    countries = get_zone_country_map(("0.5_0.5", "0.0_0.0", "2.0_2.0"), str(path))

    assert countries["0.5_0.5"] == "Testland"
    assert countries["0.0_0.0"] == UNKNOWN_COUNTRY  # its center falls in the hole
    assert countries["2.0_2.0"] == UNKNOWN_COUNTRY


def test_country_lookup_covers_all_real_mapreduce_cells():
    fire_data = load_fire_data()
    zones = tuple(fire_data.zones["zone"].astype(str))

    countries = get_zone_country_map(zones)

    assert len(countries) == 37_790
    assert set(countries) == set(zones)
    assert countries["36.5_10.0"] == "Tunisia"
    assert all(isinstance(country, str) and country for country in countries.values())


def test_display_positions_move_only_centers_in_water_into_cell_land(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Testland"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.35, 0], [1.5, 0], [1.5, 1.5], [0.35, 1.5], [0.35, 0]]],
                },
            }
        ],
    }
    path = tmp_path / "countries.geojson"
    path.write_text(json.dumps(geojson), encoding="utf-8")
    zones = ("0.0_0.0", "0.5_0.5", "2.0_2.0")
    countries = get_zone_country_map(zones, str(path))
    positions = get_zone_display_positions(
        zones, tuple(countries[zone] for zone in zones), str(path)
    )

    # The first cell's center is offshore, so its marker moves into land within that cell.
    longitude, latitude, note = positions["0.0_0.0"]
    assert 0.0 <= longitude <= 0.5
    assert 0.0 <= latitude <= 0.5
    assert longitude > 0.35  # Inside Testland, not merely closer to its coast.
    assert note == "Representative point in land-cell intersection"

    # A center already assigned to land is unchanged.
    assert positions["0.5_0.5"][:2] == (0.75, 0.75)
    assert positions["0.5_0.5"][2] == "Original cell center retained"

    # A cell without any land intersection retains its center and is flagged for review.
    assert positions["2.0_2.0"][:2] == (2.25, 2.25)
    assert positions["2.0_2.0"][2].startswith("Review:")


def test_display_positions_do_not_change_ranking_inputs(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Testland"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.35, 0], [1.5, 0], [1.5, 1.5], [0.35, 1.5], [0.35, 0]]],
                },
            }
        ],
    }
    path = tmp_path / "countries.geojson"
    path.write_text(json.dumps(geojson), encoding="utf-8")
    zones = ("0.0_0.0", "0.5_0.5")
    countries = get_zone_country_map(zones, str(path))
    get_zone_display_positions(zones, tuple(countries[zone] for zone in zones), str(path))

    source = pd.DataFrame(
        {
            "zone": list(zones),
            "count": [10, 20],
            "avg_frp_mw": [1.25, 2.5],
            "cell_center_latitude": [0.25, 0.75],
            "cell_center_longitude": [0.25, 0.75],
        }
    )
    before = rank_zone_map_data(source, ranking="Detection count", top_n=1)
    source["display_longitude"] = [0.425, 0.75]
    source["display_latitude"] = [0.25, 0.75]
    after = rank_zone_map_data(source, ranking="Detection count", top_n=1)

    assert before[["zone", "count", "avg_frp_mw"]].equals(
        after[["zone", "count", "avg_frp_mw"]]
    )
    assert source["cell_center_longitude"].tolist() == [0.25, 0.75]


def test_boundary_touch_is_kept_inside_cell_and_identified_for_review(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Testland"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.5, 0], [1, 0], [1, 1], [0.5, 1], [0.5, 0]]],
                },
            }
        ],
    }
    path = tmp_path / "countries.geojson"
    path.write_text(json.dumps(geojson), encoding="utf-8")
    zones = ("0.0_0.0",)
    countries = get_zone_country_map(zones, str(path))
    longitude, latitude, note = get_zone_display_positions(
        zones, (countries[zones[0]],), str(path)
    )[zones[0]]

    assert longitude == 0.5
    assert 0.0 <= latitude <= 0.5
    assert note == "Representative point on land-cell boundary; verify the contact"
