from io import StringIO

import pandas as pd
import pytest

from dashboard.data import DataValidationError, rank_zone_map_data
from dashboard.spark_data import (
    DEFAULT_TUNISIA_ZONE_MONTH_PATH,
    get_tunisia_zone_month_stats,
    load_tunisia_zone_month_stats,
    months_for_zone_stats,
    prepare_tunisia_month,
)


def test_real_tunisia_zone_month_sums_match_country_monthly_export():
    zone_month = load_tunisia_zone_month_stats()
    country_monthly = pd.read_csv(
        DEFAULT_TUNISIA_ZONE_MONTH_PATH.parents[0] / "country_monthly.csv"
    )
    tunisia_monthly = country_monthly.loc[
        country_monthly["country"] == "Tunisia", ["year_month", "count"]
    ].set_index("year_month")["count"]
    zone_totals = zone_month.groupby("year_month")["count"].sum()

    assert len(zone_month) == 280
    assert zone_month[["zone", "year_month"]].duplicated().sum() == 0
    pd.testing.assert_series_equal(
        zone_totals.sort_index().rename("count"), tunisia_monthly.sort_index()
    )


def test_month_preparation_preserves_spark_values_and_handles_empty_month():
    source = load_tunisia_zone_month_stats()
    original = source.copy(deep=True)
    months = months_for_zone_stats(source)
    september = prepare_tunisia_month(source, "2025-09")
    january = prepare_tunisia_month(source, "2025-01")
    without_january = source.loc[source["year_month"] != "2025-01"].copy()
    empty_month = prepare_tunisia_month(without_january, "2025-01")

    assert months == ["2025-{:02d}".format(month) for month in range(1, 13)]
    assert len(september) == 32
    assert int(september["count"].sum()) == 430
    assert (september["avg_frp_mw"] == september["avg_frp"]).all()
    assert (september["max_frp_mw"] == september["max_frp"]).all()
    assert (september["cell_center_latitude"] % 0.5 == 0.25).all()
    assert (september["cell_center_longitude"] % 0.5 == 0.25).all()
    assert len(january) == 9
    assert empty_month.empty
    pd.testing.assert_frame_equal(source, original)

    filtered = rank_zone_map_data(
        september, ranking="Maximum FRP", top_n=10, minimum_count=5
    )
    export = pd.read_csv(
        StringIO(
            filtered[
                ["zone", "year_month", "count", "avg_frp", "max_frp"]
            ].to_csv(index=False)
        )
    )
    assert export["zone"].tolist() == filtered["zone"].tolist()
    assert export["max_frp"].tolist() == filtered["max_frp"].tolist()


def test_monthly_filters_and_maximum_frp_ranking():
    frame = pd.DataFrame(
        {
            "zone": ["0.0_0.0", "0.5_0.0", "1.0_0.0"],
            "count": [8, 30, 20],
            "avg_frp_mw": [8.0, 2.0, 5.0],
            "max_frp_mw": [12.0, 30.0, 20.0],
        }
    )

    ranked = rank_zone_map_data(
        frame, ranking="Maximum FRP", top_n=2, minimum_count=10
    )
    assert ranked["zone"].tolist() == ["0.5_0.0", "1.0_0.0"]
    assert ranked["max_frp_mw"].tolist() == [30.0, 20.0]
    assert rank_zone_map_data(frame, ranking="Detection Count", top_n=1)["zone"].tolist() == [
        "0.5_0.0"
    ]
    with pytest.raises(ValueError, match="requires the 'max_frp_mw' column"):
        rank_zone_map_data(frame.drop(columns="max_frp_mw"), ranking="Maximum FRP")


def test_spark_loader_rejects_duplicate_zone_month_keys(tmp_path):
    path = tmp_path / "zone_month_stats.csv"
    pd.DataFrame(
        {
            "zone": ["36.5_9.0", "36.5_9.0"],
            "year_month": ["2025-09", "2025-09"],
            "count": [1, 2],
            "avg_frp": [1.0, 2.0],
            "max_frp": [1.5, 2.5],
        }
    ).to_csv(path, index=False)

    with pytest.raises(DataValidationError, match="duplicate zone/month"):
        load_tunisia_zone_month_stats(path)
