"""Loader for the Spark worldwide top-countries export."""

from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.data import DataValidationError, PROJECT_ROOT


WORLD_TOP_COUNTRIES_PATH = (
    PROJECT_ROOT / "module_B_spark" / "results" / "final" / "world_top_countries.csv"
)


def load_world_top_countries(path: Path | str = WORLD_TOP_COUNTRIES_PATH) -> pd.DataFrame:
    """Read the worldwide top-countries export and return its top ten rows.

    The export is produced by Spark as ``rank,country,fire_count``. The ``rank``
    column is optional; the frame is re-sorted by detections so the chart always
    reflects fire_count rather than a pre-computed ordering.
    """
    path = Path(path)
    if not path.is_file():
        raise DataValidationError("World top countries export is not available: {}".format(path))
    try:
        frame = pd.read_csv(path, dtype={"country": "string"})
    except (OSError, pd.errors.ParserError, UnicodeError) as error:
        raise DataValidationError("Could not read world_top_countries.csv: {}".format(error)) from error
    if not {"country", "fire_count"}.issubset(frame.columns):
        raise DataValidationError(
            "world_top_countries.csv must contain the columns country,fire_count."
        )
    if frame.empty or frame[["country", "fire_count"]].isna().any().any():
        raise DataValidationError("world_top_countries.csv is empty or contains missing values.")
    frame["country"] = frame["country"].astype(str).str.strip()
    if (frame["country"] == "").any() or frame["country"].duplicated().any():
        raise DataValidationError("world_top_countries.csv contains blank or duplicate countries.")
    try:
        counts = pd.to_numeric(frame["fire_count"], errors="raise")
    except (TypeError, ValueError) as error:
        raise DataValidationError("world_top_countries.csv contains invalid fire counts.") from error
    finite = counts.map(lambda value: pd.notna(value) and float("-inf") < value < float("inf"))
    if not finite.all() or (counts < 0).any() or (counts % 1 != 0).any():
        raise DataValidationError("world_top_countries.csv counts must be finite non-negative integers.")
    result = pd.DataFrame(
        {"country": frame["country"].to_numpy(), "count": counts.astype("int64").to_numpy()}
    )
    return result.sort_values(["count", "country"], ascending=[False, True]).head(10).reset_index(drop=True)


@st.cache_data(show_spinner="Loading worldwide top countries...")
def _cached_world_top_countries(path: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return load_world_top_countries(path)


def get_world_top_countries(path: Path | str = WORLD_TOP_COUNTRIES_PATH) -> pd.DataFrame:
    path = Path(path)
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        modified_ns = 0
    return _cached_world_top_countries(str(path), modified_ns)
