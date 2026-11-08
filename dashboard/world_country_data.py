"""Optional loader for the forthcoming Spark worldwide country summary."""

from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.data import DataValidationError, PROJECT_ROOT


WORLD_COUNTRY_SUMMARY_PATH = (
    PROJECT_ROOT / "module_B_spark" / "results" / "final" / "world_country_summary.csv"
)


def load_world_country_summary(path: Path | str = WORLD_COUNTRY_SUMMARY_PATH) -> pd.DataFrame:
    """Read a country,count export and return its top ten rows.

    The CSV schema cannot establish source scope on its own. The Spark producer
    must be verified as global, year 2025, and type 0 before this data is released.
    """
    path = Path(path)
    if not path.is_file():
        raise DataValidationError("World country summary is not available: {}".format(path))
    try:
        frame = pd.read_csv(path, dtype={"country": "string"})
    except (OSError, pd.errors.ParserError, UnicodeError) as error:
        raise DataValidationError("Could not read world_country_summary.csv: {}".format(error)) from error
    if set(frame.columns) != {"country", "count"}:
        raise DataValidationError(
            "world_country_summary.csv must contain exactly the columns country,count."
        )
    if frame.empty or frame[["country", "count"]].isna().any().any():
        raise DataValidationError("world_country_summary.csv is empty or contains missing values.")
    frame["country"] = frame["country"].astype(str).str.strip()
    if (frame["country"] == "").any() or frame["country"].duplicated().any():
        raise DataValidationError("world_country_summary.csv contains blank or duplicate countries.")
    try:
        counts = pd.to_numeric(frame["count"], errors="raise")
    except (TypeError, ValueError) as error:
        raise DataValidationError("world_country_summary.csv contains invalid counts.") from error
    finite = counts.map(lambda value: pd.notna(value) and float("-inf") < value < float("inf"))
    if not finite.all() or (counts < 0).any() or (counts % 1 != 0).any():
        raise DataValidationError("world_country_summary.csv counts must be finite non-negative integers.")
    frame["count"] = counts.astype("int64")
    return frame.sort_values(["count", "country"], ascending=[False, True]).head(10).reset_index(drop=True)


@st.cache_data(show_spinner="Loading worldwide country summary...")
def _cached_world_country_summary(path: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return load_world_country_summary(path)


def get_world_country_summary(path: Path | str = WORLD_COUNTRY_SUMMARY_PATH) -> pd.DataFrame:
    path = Path(path)
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        modified_ns = 0
    return _cached_world_country_summary(str(path), modified_ns)
