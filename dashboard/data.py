"""Loading, validating, and preparing the MapReduce CSV exports."""

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "module_A_mapreduce" / "exports"

MONTH_COLUMNS = {"month", "count"}
TYPE_COLUMNS = {"type", "count"}
ZONE_COLUMNS = {"zone", "count"}
FRP_COLUMNS = {"zone", "avg_frp_mw"}
EXPECTED_MONTHS = ["2025-{month:02d}".format(month=month) for month in range(1, 13)]
ZONE_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?_-?\d+(?:\.\d+)?$")


class DataValidationError(ValueError):
    """Raised when an export is missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class FireData:
    monthly: pd.DataFrame
    types: pd.DataFrame
    zones: pd.DataFrame
    frp_by_zone: pd.DataFrame


def _read_csv(data_dir: Path, filename: str, required_columns: set[str]) -> pd.DataFrame:
    path = data_dir / filename
    if not path.is_file():
        raise DataValidationError("Required data file was not found: {}".format(path))

    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeError) as error:
        raise DataValidationError("Could not read {}: {}".format(filename, error)) from error

    missing_columns = required_columns - set(frame.columns)
    if missing_columns:
        raise DataValidationError(
            "{} is missing required columns: {}".format(
                filename, ", ".join(sorted(missing_columns))
            )
        )
    if frame.empty:
        raise DataValidationError("{} contains no data rows.".format(filename))
    if frame[list(required_columns)].isna().any().any():
        raise DataValidationError("{} contains missing required values.".format(filename))
    return frame


def _numeric_column(frame: pd.DataFrame, column: str, filename: str, integer: bool) -> pd.Series:
    try:
        values = pd.to_numeric(frame[column], errors="raise")
    except (TypeError, ValueError) as error:
        raise DataValidationError(
            "{} contains non-numeric values in '{}'.".format(filename, column)
        ) from error

    if not values.map(lambda value: pd.notna(value) and float("-inf") < value < float("inf")).all():
        raise DataValidationError("{} contains non-finite values in '{}'.".format(filename, column))
    if (values < 0).any():
        raise DataValidationError("{} contains negative values in '{}'.".format(filename, column))
    if integer and (values % 1 != 0).any():
        raise DataValidationError("{} contains non-integer values in '{}'.".format(filename, column))
    return values.astype("int64" if integer else "float64")


def _validate_unique(frame: pd.DataFrame, column: str, filename: str) -> None:
    if frame[column].duplicated().any():
        raise DataValidationError("{} contains duplicate '{}' keys.".format(filename, column))


def load_fire_data(data_dir: Path | str = DEFAULT_DATA_DIR) -> FireData:
    """Load the four checked-in Module A exports and validate their contract."""
    data_dir = Path(data_dir)
    monthly = _read_csv(data_dir, "fires_by_month.csv", MONTH_COLUMNS)
    types = _read_csv(data_dir, "fires_by_type.csv", TYPE_COLUMNS)
    zones = _read_csv(data_dir, "fires_by_zone.csv", ZONE_COLUMNS)
    frp_by_zone = _read_csv(data_dir, "frp_by_zone.csv", FRP_COLUMNS)

    monthly["month"] = monthly["month"].astype(str).str.strip()
    if monthly["month"].tolist() != EXPECTED_MONTHS:
        raise DataValidationError(
            "fires_by_month.csv must contain the twelve 2025 months in chronological order."
        )
    monthly["count"] = _numeric_column(monthly, "count", "fires_by_month.csv", integer=True)

    types["type"] = pd.to_numeric(types["type"], errors="coerce")
    if types["type"].isna().any() or (types["type"] % 1 != 0).any():
        raise DataValidationError("fires_by_type.csv contains invalid type identifiers.")
    types["type"] = types["type"].astype("int64")
    if set(types["type"]) != {0, 1, 2, 3}:
        raise DataValidationError("fires_by_type.csv must contain NASA types 0, 1, 2, and 3.")
    _validate_unique(types, "type", "fires_by_type.csv")
    types["count"] = _numeric_column(types, "count", "fires_by_type.csv", integer=True)
    types = types.sort_values("type").reset_index(drop=True)

    for frame, filename in ((zones, "fires_by_zone.csv"), (frp_by_zone, "frp_by_zone.csv")):
        frame["zone"] = frame["zone"].astype(str).str.strip()
        if not frame["zone"].map(lambda zone: bool(ZONE_PATTERN.fullmatch(zone))).all():
            raise DataValidationError("{} contains an invalid zone identifier.".format(filename))
        _validate_unique(frame, "zone", filename)

    zones["count"] = _numeric_column(zones, "count", "fires_by_zone.csv", integer=True)
    frp_by_zone["avg_frp_mw"] = _numeric_column(
        frp_by_zone, "avg_frp_mw", "frp_by_zone.csv", integer=False
    )

    if set(zones["zone"]) != set(frp_by_zone["zone"]):
        raise DataValidationError("Zone keys do not match between count and FRP exports.")
    if int(monthly["count"].sum()) != int(types.loc[types["type"] == 0, "count"].iloc[0]):
        raise DataValidationError("Monthly total does not match the type 0 detection total.")
    if int(zones["count"].sum()) != int(types.loc[types["type"] == 0, "count"].iloc[0]):
        raise DataValidationError("Geographic total does not match the type 0 detection total.")

    return FireData(
        monthly=monthly.sort_values("month").reset_index(drop=True),
        types=types,
        zones=zones,
        frp_by_zone=frp_by_zone,
    )


def prepare_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    """Return monthly counts in chronological order with display labels."""
    result = monthly.copy().sort_values("month").reset_index(drop=True)
    result["month_label"] = pd.to_datetime(result["month"], format="%Y-%m").dt.strftime("%b")
    return result


def prepare_type_distribution(types: pd.DataFrame) -> pd.DataFrame:
    """Add descriptive NASA type labels and the share of all detections."""
    labels = {
        0: "Type 0 — Presumed Vegetation Fire",
        1: "Type 1 — Active Volcano",
        2: "Type 2 — Other Static Land Source",
        3: "Type 3 — Offshore Source",
    }
    result = types.copy().sort_values("type").reset_index(drop=True)
    result["category"] = result["type"].map(labels)
    result["share"] = result["count"] / result["count"].sum()
    return result


def prepare_top_zones(zones: pd.DataFrame, frp_by_zone: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    """Join zone counts to FRP means and return the most active grid cells."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    result = zones.merge(frp_by_zone, on="zone", how="left", validate="one_to_one")
    if result["avg_frp_mw"].isna().any():
        raise DataValidationError("One or more zone counts have no matching FRP value.")
    return result.sort_values(["count", "zone"], ascending=[False, True]).head(limit).reset_index(drop=True)


def prepare_zone_map_data(zones: pd.DataFrame, frp_by_zone: pd.DataFrame) -> pd.DataFrame:
    """Join zone statistics and derive representative 0.5-degree cell centers."""
    if zones["zone"].duplicated().any() or frp_by_zone["zone"].duplicated().any():
        raise DataValidationError("Zone identifiers must be unique in both geographic exports.")
    if set(zones["zone"]) != set(frp_by_zone["zone"]):
        raise DataValidationError("Zone keys do not match between count and FRP exports.")

    result = zones.merge(frp_by_zone, on="zone", how="left", validate="one_to_one")
    if result[["count", "avg_frp_mw"]].isna().any().any():
        raise DataValidationError("Geographic exports contain missing count or FRP values.")

    coordinates = result["zone"].str.split("_", n=1, expand=True)
    try:
        result["cell_center_latitude"] = pd.to_numeric(coordinates[0], errors="raise") + 0.25
        result["cell_center_longitude"] = pd.to_numeric(coordinates[1], errors="raise") + 0.25
    except (KeyError, TypeError, ValueError) as error:
        raise DataValidationError("Could not derive cell centers from zone identifiers.") from error
    return result


def rank_zone_map_data(
    map_data: pd.DataFrame,
    ranking: str = "count",
    top_n: int | None = 500,
    minimum_count: int = 0,
) -> pd.DataFrame:
    """Filter and rank a copy of map data, leaving source frames unchanged."""
    sort_columns = {
        "count": "count",
        "avg_frp": "avg_frp_mw",
        "max_frp": "max_frp_mw",
        # Keep accepting the previous display labels for existing callers.
        "Detection Count": "count",
        "Detection count": "count",
        "Average FRP": "avg_frp_mw",
        "Maximum FRP": "max_frp_mw",
    }
    if ranking not in sort_columns:
        raise ValueError(
            "ranking must be 'count', 'avg_frp', or 'max_frp'"
        )
    if sort_columns[ranking] not in map_data.columns:
        raise ValueError(
            "ranking '{}' requires the '{}' column.".format(ranking, sort_columns[ranking])
        )
    if top_n is not None and top_n < 1:
        raise ValueError("top_n must be None or at least 1")
    if minimum_count < 0:
        raise ValueError("minimum_count cannot be negative")

    result = map_data.loc[map_data["count"] >= minimum_count].copy()
    result = result.sort_values(
        [sort_columns[ranking], "zone"], ascending=[False, True]
    ).reset_index(drop=True)
    if top_n is not None:
        result = result.head(top_n).reset_index(drop=True)
    return result


def ranked_zone_csv_bytes(filtered_map_data: pd.DataFrame, columns: list[str]) -> bytes:
    """Serialize the already filtered and ranked rows shown by Fire Explorer."""
    missing = set(columns) - set(filtered_map_data.columns)
    if missing:
        raise DataValidationError(
            "Ranked map export is missing columns: {}".format(", ".join(sorted(missing)))
        )
    return filtered_map_data.loc[:, columns].to_csv(index=False).encode("utf-8")
