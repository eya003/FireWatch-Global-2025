"""Loading and validating the checked-in Tunisia Spark batch export."""

from pathlib import Path
import re

import pandas as pd
import streamlit as st

from dashboard.data import DataValidationError, PROJECT_ROOT, ZONE_PATTERN


DEFAULT_TUNISIA_ZONE_MONTH_PATH = (
    PROJECT_ROOT / "module_B_spark" / "results" / "final" / "zone_month_stats.csv"
)
ZONE_MONTH_COLUMNS = {"zone", "year_month", "count", "avg_frp", "max_frp"}
YEAR_MONTH_PATTERN = re.compile(r"^2025-(0[1-9]|1[0-2])$")


def load_tunisia_zone_month_stats(
    path: Path | str = DEFAULT_TUNISIA_ZONE_MONTH_PATH,
) -> pd.DataFrame:
    """Read the Spark export and validate its monthly zone-statistics contract."""
    path = Path(path)
    if not path.is_file():
        raise DataValidationError("Required Spark data file was not found: {}".format(path))
    try:
        frame = pd.read_csv(path, dtype={"zone": "string", "year_month": "string"})
    except (OSError, pd.errors.ParserError, UnicodeError) as error:
        raise DataValidationError("Could not read zone_month_stats.csv: {}".format(error)) from error

    missing = ZONE_MONTH_COLUMNS - set(frame.columns)
    if missing:
        raise DataValidationError(
            "zone_month_stats.csv is missing required columns: {}".format(
                ", ".join(sorted(missing))
            )
        )
    if frame.empty:
        raise DataValidationError("zone_month_stats.csv contains no data rows.")
    if frame[list(ZONE_MONTH_COLUMNS)].isna().any().any():
        raise DataValidationError("zone_month_stats.csv contains missing required values.")

    frame["zone"] = frame["zone"].astype(str).str.strip()
    frame["year_month"] = frame["year_month"].astype(str).str.strip()
    if not frame["zone"].map(lambda zone: bool(ZONE_PATTERN.fullmatch(zone))).all():
        raise DataValidationError("zone_month_stats.csv contains an invalid zone identifier.")
    if not frame["year_month"].map(lambda value: bool(YEAR_MONTH_PATTERN.fullmatch(value))).all():
        raise DataValidationError("zone_month_stats.csv must contain valid 2025 year_month values.")
    if frame.duplicated(["zone", "year_month"]).any():
        raise DataValidationError("zone_month_stats.csv contains duplicate zone/month keys.")

    for column, integer in (("count", True), ("avg_frp", False), ("max_frp", False)):
        try:
            values = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as error:
            raise DataValidationError(
                "zone_month_stats.csv contains non-numeric values in '{}'.".format(column)
            ) from error
        finite = values.map(lambda value: pd.notna(value) and float("-inf") < value < float("inf"))
        if not finite.all():
            raise DataValidationError(
                "zone_month_stats.csv contains non-finite values in '{}'.".format(column)
            )
        if (values < 0).any():
            raise DataValidationError(
                "zone_month_stats.csv contains negative values in '{}'.".format(column)
            )
        if integer and (values % 1 != 0).any():
            raise DataValidationError("zone_month_stats.csv contains non-integer detection counts.")
        frame[column] = values.astype("int64" if integer else "float64")

    return frame.sort_values(["year_month", "zone"]).reset_index(drop=True)


@st.cache_data(show_spinner="Loading Tunisia monthly Spark statistics…")
def _cached_tunisia_zone_month_stats(path: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns  # Part of the cache key so replacing the export invalidates it.
    return load_tunisia_zone_month_stats(path)


def get_tunisia_zone_month_stats(
    path: str | Path = DEFAULT_TUNISIA_ZONE_MONTH_PATH,
) -> pd.DataFrame:
    """Return cached, validated Tunisia monthly statistics."""
    path = Path(path)
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        modified_ns = 0
    return _cached_tunisia_zone_month_stats(str(path), modified_ns)


def months_for_zone_stats(frame: pd.DataFrame) -> list[str]:
    """List all months in each represented year so empty months remain selectable."""
    years = sorted({int(value[:4]) for value in frame["year_month"].astype(str)})
    return ["{}-{:02d}".format(year, month) for year in years for month in range(1, 13)]


def prepare_tunisia_month(frame: pd.DataFrame, year_month: str) -> pd.DataFrame:
    """Return a copy of one month with canonical FRP aliases and cell centers."""
    result = frame.loc[frame["year_month"] == year_month].copy()
    result["avg_frp_mw"] = result["avg_frp"].astype("float64")
    result["max_frp_mw"] = result["max_frp"].astype("float64")
    if result.empty:
        result["cell_center_latitude"] = pd.Series(dtype="float64")
        result["cell_center_longitude"] = pd.Series(dtype="float64")
        return result.reset_index(drop=True)
    coordinates = result["zone"].str.split("_", n=1, expand=True)
    result["cell_center_latitude"] = pd.to_numeric(coordinates[0], errors="raise") + 0.25
    result["cell_center_longitude"] = pd.to_numeric(coordinates[1], errors="raise") + 0.25
    return result.reset_index(drop=True)
