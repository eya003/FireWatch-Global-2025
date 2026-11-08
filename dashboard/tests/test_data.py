from pathlib import Path
from io import StringIO
import shutil

import pandas as pd
import pytest

from dashboard.data import (
    DEFAULT_DATA_DIR,
    DataValidationError,
    load_fire_data,
    prepare_monthly,
    prepare_top_zones,
    prepare_type_distribution,
    prepare_zone_map_data,
    ranked_zone_csv_bytes,
    rank_zone_map_data,
)


def test_loads_and_validates_checked_in_exports():
    data = load_fire_data()

    assert list(data.monthly["month"]) == ["2025-{:02d}".format(month) for month in range(1, 13)]
    assert int(data.monthly["count"].sum()) == int(data.types.loc[data.types["type"] == 0, "count"].iloc[0])
    assert set(data.zones["zone"]) == set(data.frp_by_zone["zone"])


def test_prepares_months_categories_and_top_zones():
    data = load_fire_data()

    monthly = prepare_monthly(data.monthly)
    categories = prepare_type_distribution(data.types)
    top_zones = prepare_top_zones(data.zones, data.frp_by_zone)

    assert len(monthly) == 12
    assert monthly.iloc[0]["month_label"] == "Jan"
    assert categories["share"].sum() == pytest.approx(1.0)
    assert len(top_zones) == 5
    assert top_zones["count"].is_monotonic_decreasing
    assert top_zones["avg_frp_mw"].notna().all()


def test_geographic_exports_have_37790_unique_matching_zones():
    data = load_fire_data()

    assert len(data.zones) == 37_790
    assert data.zones["zone"].is_unique
    assert data.frp_by_zone["zone"].is_unique
    assert len(data.frp_by_zone) == 37_790
    assert set(data.zones["zone"]) == set(data.frp_by_zone["zone"])


def test_zone_map_centers_handle_negative_coordinates():
    zones = pd.DataFrame({"zone": ["-0.5_-48.5", "36.5_10.0"], "count": [4, 8]})
    frp = pd.DataFrame({"zone": ["-0.5_-48.5", "36.5_10.0"], "avg_frp_mw": [2.5, 3.5]})

    prepared = prepare_zone_map_data(zones, frp).set_index("zone")

    assert prepared.loc["-0.5_-48.5", "cell_center_latitude"] == pytest.approx(-0.25)
    assert prepared.loc["-0.5_-48.5", "cell_center_longitude"] == pytest.approx(-48.25)
    assert prepared.loc["36.5_10.0", "cell_center_latitude"] == pytest.approx(36.75)
    assert prepared.loc["36.5_10.0", "cell_center_longitude"] == pytest.approx(10.25)


def test_map_ranking_top_n_filter_and_source_immutability():
    zones = pd.DataFrame({"zone": ["0.0_0.0", "0.5_0.0", "1.0_0.0"], "count": [10, 30, 20]})
    frp = pd.DataFrame({"zone": ["0.0_0.0", "0.5_0.0", "1.0_0.0"], "avg_frp_mw": [8.0, 2.0, 5.0]})
    original_zones = zones.copy(deep=True)
    original_frp = frp.copy(deep=True)
    map_data = prepare_zone_map_data(zones, frp)
    original_map = map_data.copy(deep=True)

    count_top = rank_zone_map_data(map_data, "Detection count", top_n=2, minimum_count=15)
    frp_top = rank_zone_map_data(map_data, "Average FRP", top_n=None)

    assert count_top["zone"].tolist() == ["0.5_0.0", "1.0_0.0"]
    assert frp_top["zone"].tolist() == ["0.0_0.0", "1.0_0.0", "0.5_0.0"]
    pd.testing.assert_frame_equal(zones, original_zones)
    pd.testing.assert_frame_equal(frp, original_frp)
    pd.testing.assert_frame_equal(map_data, original_map)


def test_ranked_map_export_uses_the_same_filtered_order_and_columns():
    map_data = pd.DataFrame(
        {
            "zone": ["0.0_0.0", "0.5_0.0", "1.0_0.0"],
            "count": [10, 30, 20],
            "avg_frp_mw": [8.0, 2.0, 5.0],
        }
    )
    ranked = rank_zone_map_data(map_data, ranking="avg_frp", top_n=2, minimum_count=15)
    export = pd.read_csv(StringIO(ranked_zone_csv_bytes(ranked, ["zone", "count", "avg_frp_mw"]).decode("utf-8")))

    assert export.columns.tolist() == ["zone", "count", "avg_frp_mw"]
    assert export["zone"].tolist() == ranked["zone"].tolist()
    assert export["count"].tolist() == ranked["count"].tolist()
    assert export["avg_frp_mw"].tolist() == ranked["avg_frp_mw"].tolist()


def test_zone_map_rejects_duplicate_or_mismatched_keys():
    duplicate_zones = pd.DataFrame({"zone": ["0.0_0.0", "0.0_0.0"], "count": [1, 2]})
    frp = pd.DataFrame({"zone": ["0.0_0.0"], "avg_frp_mw": [1.0]})
    with pytest.raises(DataValidationError, match="unique"):
        prepare_zone_map_data(duplicate_zones, frp)

    zones = pd.DataFrame({"zone": ["0.0_0.0"], "count": [1]})
    mismatched_frp = pd.DataFrame({"zone": ["1.0_0.0"], "avg_frp_mw": [1.0]})
    with pytest.raises(DataValidationError, match="do not match"):
        prepare_zone_map_data(zones, mismatched_frp)


def test_rejects_missing_export(tmp_path: Path):
    with pytest.raises(DataValidationError, match="not found"):
        load_fire_data(tmp_path)


def test_rejects_missing_required_column(tmp_path: Path):
    for name in ("fires_by_month.csv", "fires_by_type.csv", "fires_by_zone.csv", "frp_by_zone.csv"):
        shutil.copy(DEFAULT_DATA_DIR / name, tmp_path / name)
    pd.DataFrame({"month": ["2025-01"], "total": [10]}).to_csv(
        tmp_path / "fires_by_month.csv", index=False
    )

    with pytest.raises(DataValidationError, match="missing required columns"):
        load_fire_data(tmp_path)
