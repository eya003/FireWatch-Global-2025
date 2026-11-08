import shutil

import pandas as pd
import pytest

from dashboard.data import DataValidationError, load_fire_data, prepare_monthly
from dashboard.trends_data import (
    EXPECTED_COUNTRIES,
    DEFAULT_SPARK_FINAL_DIR,
    load_spark_trends_data,
    monthly_changes,
    regional_country_comparison,
)


def test_spark_trend_exports_reconcile_schemas_totals_and_tunisia_series():
    data = load_spark_trends_data()

    assert set(data.country_summary["country"]) == set(EXPECTED_COUNTRIES)
    assert len(data.country_monthly) == 48
    assert data.country_monthly.groupby("country").size().eq(12).all()
    summary_totals = data.country_summary.set_index("country")["count"].sort_index()
    monthly_totals = data.country_monthly.groupby("country")["count"].sum().sort_index()
    pd.testing.assert_series_equal(summary_totals, monthly_totals)
    tunisia_country = data.country_monthly.loc[
        data.country_monthly["country"] == "Tunisia", ["year_month", "count"]
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(data.tunisia_monthly, tunisia_country)
    assert data.tunisia_monthly["count"].sum() == 1495
    assert len(data.tunisia_top_days) == 10


def test_world_monthly_changes_are_chronological_and_use_previous_month():
    prepared = prepare_monthly(load_fire_data().monthly)
    changes = monthly_changes(prepared, month_column="month")

    assert changes["month"].tolist() == ["2025-{:02d}".format(m) for m in range(1, 13)]
    assert pd.isna(changes.loc[0, "change"])
    assert changes.loc[1, "change"] == -325106
    assert changes.loc[1, "change_percent"] == pytest.approx(-325106 / 1629374 * 100)
    assert changes.loc[7, "change"] == 885692


def test_country_comparison_ranks_totals_and_uses_each_country_peak_month():
    data = load_spark_trends_data()
    comparison = regional_country_comparison(data.country_summary, data.country_monthly)

    assert comparison["country"].tolist() == ["Algeria", "Libya", "Tunisia", "Morocco"]
    assert comparison["rank"].tolist() == [1, 2, 3, 4]
    for row in comparison.itertuples(index=False):
        series = data.country_monthly.loc[data.country_monthly["country"] == row.country]
        peak = series.sort_values(["count", "year_month"], ascending=[False, True]).iloc[0]
        assert row.peak_month == peak["year_month"]
        assert row.peak_month_detections == peak["count"]

    selected = data.country_monthly.loc[data.country_monthly["country"].isin(["Tunisia", "Morocco"])]
    assert set(selected["country"]) == {"Tunisia", "Morocco"}


def test_top_days_are_valid_ranked_2025_dates_with_max_frp_values():
    top = load_spark_trends_data().tunisia_top_days
    assert top["date"].str.startswith("2025-").all()
    assert top["date"].is_unique
    assert top["count"].tolist() == sorted(top["count"], reverse=True)
    assert top.iloc[0]["date"] == "2025-09-13"
    assert top.iloc[0]["max_frp"] == pytest.approx(52.51)
    assert top.loc[top["date"] == "2025-08-27", "max_frp"].iloc[0] == pytest.approx(362.21)


def test_spark_trend_loader_rejects_duplicate_daily_dates(tmp_path):
    for name in ("country_summary.csv", "country_monthly.csv", "monthly_spark.csv", "top10_days.csv"):
        shutil.copy(DEFAULT_SPARK_FINAL_DIR / name, tmp_path / name)
    top = pd.read_csv(tmp_path / "top10_days.csv")
    top.loc[1, "date"] = top.loc[0, "date"]
    top.to_csv(tmp_path / "top10_days.csv", index=False)

    with pytest.raises(DataValidationError, match="duplicate dates"):
        load_spark_trends_data(tmp_path)
