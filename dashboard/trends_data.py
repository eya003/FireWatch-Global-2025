"""Load and validate Spark exports used by Trends & Insights."""

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd
import streamlit as st

from dashboard.data import DataValidationError, PROJECT_ROOT


DEFAULT_SPARK_FINAL_DIR = PROJECT_ROOT / "module_B_spark" / "results" / "final"
EXPECTED_COUNTRIES = ("Tunisia", "Algeria", "Libya", "Morocco")
YEAR_MONTH_PATTERN = re.compile(r"^2025-(0[1-9]|1[0-2])$")
DATE_PATTERN = re.compile(r"^2025-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")


@dataclass(frozen=True)
class SparkTrendsData:
    country_summary: pd.DataFrame
    country_monthly: pd.DataFrame
    tunisia_monthly: pd.DataFrame
    tunisia_top_days: pd.DataFrame


def _read_csv(data_dir: Path, filename: str, required: set[str]) -> pd.DataFrame:
    path = data_dir / filename
    if not path.is_file():
        raise DataValidationError("Required Spark data file was not found: {}".format(path))
    try:
        frame = pd.read_csv(path, dtype={"country": "string", "year_month": "string", "date": "string"})
    except (OSError, pd.errors.ParserError, UnicodeError) as error:
        raise DataValidationError("Could not read {}: {}".format(filename, error)) from error
    missing = required - set(frame.columns)
    if missing:
        raise DataValidationError(
            "{} is missing required columns: {}".format(filename, ", ".join(sorted(missing)))
        )
    if frame.empty:
        raise DataValidationError("{} contains no data rows.".format(filename))
    if frame[list(required)].isna().any().any():
        raise DataValidationError("{} contains missing required values.".format(filename))
    return frame


def _numeric(frame: pd.DataFrame, column: str, filename: str, integer: bool) -> pd.Series:
    try:
        values = pd.to_numeric(frame[column], errors="raise")
    except (TypeError, ValueError) as error:
        raise DataValidationError(
            "{} contains non-numeric values in '{}'.".format(filename, column)
        ) from error
    finite = values.map(lambda value: pd.notna(value) and float("-inf") < value < float("inf"))
    if not finite.all() or (values < 0).any():
        raise DataValidationError(
            "{} contains invalid or negative values in '{}'.".format(filename, column)
        )
    if integer and (values % 1 != 0).any():
        raise DataValidationError(
            "{} contains non-integer values in '{}'.".format(filename, column)
        )
    return values.astype("int64" if integer else "float64")


def load_spark_trends_data(data_dir: Path | str = DEFAULT_SPARK_FINAL_DIR) -> SparkTrendsData:
    """Read and reconcile country, monthly, and Tunisia daily Spark exports."""
    data_dir = Path(data_dir)
    summary = _read_csv(data_dir, "country_summary.csv", {"country", "count"})
    country_monthly = _read_csv(
        data_dir, "country_monthly.csv", {"country", "year_month", "count"}
    )
    monthly = _read_csv(data_dir, "monthly_spark.csv", {"year_month", "count"})
    top_days = _read_csv(data_dir, "top10_days.csv", {"date", "count", "max_frp"})

    for frame in (summary, country_monthly):
        frame["country"] = frame["country"].astype(str).str.strip()
        if not frame["country"].isin(EXPECTED_COUNTRIES).all():
            raise DataValidationError("Spark country exports contain unexpected country names.")

    if summary["country"].duplicated().any():
        raise DataValidationError("country_summary.csv contains duplicate countries.")
    if set(summary["country"]) != set(EXPECTED_COUNTRIES):
        raise DataValidationError("country_summary.csv must contain the four Maghreb countries.")
    summary["count"] = _numeric(summary, "count", "country_summary.csv", integer=True)

    country_monthly["year_month"] = country_monthly["year_month"].astype(str).str.strip()
    if not country_monthly["year_month"].map(lambda value: bool(YEAR_MONTH_PATTERN.fullmatch(value))).all():
        raise DataValidationError("country_monthly.csv contains an invalid 2025 month.")
    if country_monthly.duplicated(["country", "year_month"]).any():
        raise DataValidationError("country_monthly.csv contains duplicate country/month keys.")
    country_monthly["count"] = _numeric(
        country_monthly, "count", "country_monthly.csv", integer=True
    )
    country_monthly = country_monthly.sort_values(["country", "year_month"]).reset_index(drop=True)
    month_keys = set(country_monthly["year_month"])
    if month_keys != {"2025-{:02d}".format(month) for month in range(1, 13)}:
        raise DataValidationError("country_monthly.csv must cover all twelve 2025 months.")
    summary_totals = summary.set_index("country")["count"].sort_index()
    monthly_totals = country_monthly.groupby("country")["count"].sum().sort_index()
    if not summary_totals.equals(monthly_totals):
        raise DataValidationError("country_summary totals do not match country_monthly totals.")
    month_counts = country_monthly.groupby("country").size()
    if not (month_counts == 12).all():
        raise DataValidationError("country_monthly.csv must have one row per country and month.")

    monthly["year_month"] = monthly["year_month"].astype(str).str.strip()
    if monthly["year_month"].tolist() != ["2025-{:02d}".format(m) for m in range(1, 13)]:
        raise DataValidationError("monthly_spark.csv must contain the twelve 2025 months in order.")
    monthly["count"] = _numeric(monthly, "count", "monthly_spark.csv", integer=True)
    tunisia_monthly = country_monthly.loc[
        country_monthly["country"] == "Tunisia", ["year_month", "count"]
    ].reset_index(drop=True)
    if not monthly.reset_index(drop=True).equals(tunisia_monthly):
        raise DataValidationError("monthly_spark.csv does not match Tunisia in country_monthly.csv.")

    top_days["date"] = top_days["date"].astype(str).str.strip()
    if not top_days["date"].map(lambda value: bool(DATE_PATTERN.fullmatch(value))).all():
        raise DataValidationError("top10_days.csv contains an invalid 2025 date.")
    parsed_dates = pd.to_datetime(top_days["date"], format="%Y-%m-%d", errors="coerce")
    if parsed_dates.isna().any() or top_days["date"].duplicated().any():
        raise DataValidationError("top10_days.csv contains invalid or duplicate dates.")
    top_days["count"] = _numeric(top_days, "count", "top10_days.csv", integer=True)
    top_days["max_frp"] = _numeric(top_days, "max_frp", "top10_days.csv", integer=False)
    if len(top_days) > 10:
        raise DataValidationError("top10_days.csv must contain no more than ten days.")
    ranked_days = top_days.sort_values(
        ["count", "max_frp"], ascending=[False, False]
    )
    if top_days["date"].tolist() != ranked_days["date"].tolist():
        raise DataValidationError("top10_days.csv is not ranked by count and maximum FRP.")
    top_days = ranked_days.reset_index(drop=True)

    summary = summary.sort_values(["count", "country"], ascending=[False, True]).reset_index(drop=True)
    return SparkTrendsData(
        country_summary=summary,
        country_monthly=country_monthly,
        tunisia_monthly=monthly,
        tunisia_top_days=top_days,
    )


@st.cache_data(show_spinner="Loading and validating Spark trend exports...")
def _cached_spark_trends(path: str, modified: tuple[int, ...]) -> SparkTrendsData:
    del modified
    return load_spark_trends_data(path)


def get_spark_trends_data(data_dir: Path | str = DEFAULT_SPARK_FINAL_DIR) -> SparkTrendsData:
    data_dir = Path(data_dir)
    names = ("country_summary.csv", "country_monthly.csv", "monthly_spark.csv", "top10_days.csv")
    modified = tuple((data_dir / name).stat().st_mtime_ns if (data_dir / name).exists() else 0 for name in names)
    return _cached_spark_trends(str(data_dir), modified)


def monthly_changes(monthly: pd.DataFrame, month_column: str = "month") -> pd.DataFrame:
    """Calculate month-over-month absolute and percentage changes chronologically."""
    result = monthly.copy()
    result[month_column] = result[month_column].astype(str)
    result = result.sort_values(month_column).reset_index(drop=True)
    previous = result["count"].shift(1)
    result["change"] = result["count"] - previous
    result["change_percent"] = (result["change"] / previous.where(previous != 0)) * 100
    return result


def regional_country_comparison(summary: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Join each country total to its peak month and peak-month detections."""
    peaks = (
        monthly.sort_values(["country", "count", "year_month"], ascending=[True, False, True])
        .drop_duplicates("country")
        .rename(columns={"year_month": "peak_month", "count": "peak_month_detections"})
    )
    result = summary.merge(peaks, on="country", how="left", validate="one_to_one")
    result["rank"] = result["count"].rank(method="min", ascending=False).astype(int)
    return result.sort_values(["rank", "country"]).reset_index(drop=True)
