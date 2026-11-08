"""Approximate country assignment for aggregated geographic cells."""

import json
import math
from pathlib import Path

import streamlit as st

from dashboard.data import PROJECT_ROOT


COUNTRIES_GEOJSON = PROJECT_ROOT / "module_B_spark" / "data" / "countries.geojson"
UNKNOWN_COUNTRY = "Unknown / International waters"
_LATITUDE_BANDS = 180
_LONGITUDE_BANDS = 360
_MAX_INDEXED_BINS = 1000


def _ring_bounds(ring):
    longitudes = [point[0] for point in ring]
    latitudes = [point[1] for point in ring]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def _index_ring(ring):
    """Index only the ring edges that can cross each one-degree latitude band."""
    ring = tuple((float(point[0]), float(point[1])) for point in ring)
    edges_by_band = {}
    for index, current in enumerate(ring):
        previous = ring[index - 1]
        first_band = _latitude_band(min(previous[1], current[1]))
        last_band = _latitude_band(max(previous[1], current[1]))
        for band in range(first_band, last_band + 1):
            edges_by_band.setdefault(band, []).append(index)
    return ring, {band: tuple(indices) for band, indices in edges_by_band.items()}


def _latitude_band(latitude):
    return max(0, min(_LATITUDE_BANDS - 1, int(math.floor(latitude + 90))))


def _inside_ring(longitude, latitude, indexed_ring, latitude_band):
    """Ray casting in GeoJSON longitude/latitude coordinates."""
    inside = False
    ring, edge_index = indexed_ring
    for index in edge_index.get(latitude_band, ()):
        current = ring[index]
        previous = ring[index - 1]
        x1, y1 = previous[0], previous[1]
        x2, y2 = current[0], current[1]
        if (y1 > latitude) != (y2 > latitude):
            crossing = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < crossing:
                inside = not inside
        previous = current
    return inside


@st.cache_data(show_spinner="Loading country boundaries…")
def _load_country_polygons(path: str, modified_ns: int):
    """Load polygon shells/holes and index them into one-degree latitude bands."""
    del modified_ns  # Included in the cache key so edits to the GeoJSON invalidate it.
    try:
        with Path(path).open(encoding="utf-8") as source:
            collection = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return tuple()

    wide_by_latitude = [[] for _ in range(_LATITUDE_BANDS)]
    grid = {}
    for feature in collection.get("features", []):
        name = (feature.get("properties") or {}).get("name")
        geometry = feature.get("geometry") or {}
        if not name:
            continue
        coordinates = geometry.get("coordinates") or []
        polygons = [coordinates] if geometry.get("type") == "Polygon" else coordinates
        if geometry.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        for polygon in polygons:
            if not polygon or not polygon[0] or len(polygon[0]) < 4:
                continue
            shell = polygon[0]
            try:
                min_lon, min_lat, max_lon, max_lat = _ring_bounds(shell)
                indexed_shell = _index_ring(shell)
                holes = tuple(_index_ring(ring) for ring in polygon[1:] if len(ring) >= 4)
            except (TypeError, ValueError, IndexError):
                continue
            entry = (str(name), indexed_shell, holes, min_lon, min_lat, max_lon, max_lat)
            first_lat_band, last_lat_band = _latitude_band(min_lat), _latitude_band(max_lat)
            first_lon_band = max(0, min(_LONGITUDE_BANDS - 1, int(math.floor(min_lon + 180))))
            last_lon_band = max(0, min(_LONGITUDE_BANDS - 1, int(math.floor(max_lon + 180))))
            bin_count = (last_lat_band - first_lat_band + 1) * (last_lon_band - first_lon_band + 1)
            if bin_count > _MAX_INDEXED_BINS:
                for lat_band in range(first_lat_band, last_lat_band + 1):
                    wide_by_latitude[lat_band].append(entry)
                continue
            for lat_band in range(first_lat_band, last_lat_band + 1):
                for lon_band in range(first_lon_band, last_lon_band + 1):
                    grid.setdefault((lat_band, lon_band), []).append(entry)
    return (
        tuple(tuple(entries) for entries in wide_by_latitude),
        {key: tuple(entries) for key, entries in grid.items()},
    )


def _country_at(longitude, latitude, bands):
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return UNKNOWN_COUNTRY
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return UNKNOWN_COUNTRY
    lat_band = _latitude_band(latitude)
    lon_band = max(0, min(_LONGITUDE_BANDS - 1, int(math.floor(longitude + 180))))
    wide_by_latitude, grid = bands
    candidates = grid.get((lat_band, lon_band), ()) + wide_by_latitude[lat_band]
    for name, shell, holes, min_lon, min_lat, max_lon, max_lat in candidates:
        if not (min_lon <= longitude <= max_lon and min_lat <= latitude <= max_lat):
            continue
        if not _inside_ring(longitude, latitude, shell, lat_band):
            continue
        if any(_inside_ring(longitude, latitude, hole, lat_band) for hole in holes):
            continue
        return name
    return UNKNOWN_COUNTRY


@st.cache_data(show_spinner="Assigning countries to geographic cells…")
def _cached_zone_country_map(zones: tuple[str, ...], path: str, modified_ns: int):
    """Calculate cell assignments, keyed by zones and the boundary file version."""
    bands = _load_country_polygons(path, modified_ns)
    result = {}
    for zone in zones:
        try:
            lower_latitude, lower_longitude = (float(value) for value in zone.split("_", 1))
            latitude, longitude = lower_latitude + 0.25, lower_longitude + 0.25
        except (TypeError, ValueError):
            result[zone] = UNKNOWN_COUNTRY
            continue
        result[zone] = _country_at(longitude, latitude, bands)
    return result


def get_zone_country_map(zones: tuple[str, ...], path: str = str(COUNTRIES_GEOJSON)):
    """Return cached approximate country names keyed by cell identifier."""
    try:
        modified_ns = Path(path).stat().st_mtime_ns
    except OSError:
        modified_ns = 0
    return _cached_zone_country_map(zones, path, modified_ns)


def _ring_edges_in_latitude_range(indexed_ring, min_latitude, max_latitude):
    """Select only indexed ring edges relevant to a cell's latitude range."""
    ring, edges_by_band = indexed_ring
    first_band = _latitude_band(min_latitude)
    last_band = _latitude_band(max_latitude)
    edge_indices = set()
    for band in range(first_band, last_band + 1):
        edge_indices.update(edges_by_band.get(band, ()))
    edge_indices = tuple(
        index
        for index in edge_indices
        if max(ring[index - 1][1], ring[index][1]) >= min_latitude
        and min(ring[index - 1][1], ring[index][1]) <= max_latitude
    )
    return ring, edge_indices


def _ring_intervals(ring, edge_indices, latitude):
    """Return the longitude intervals inside a ring at one latitude."""
    crossings = []
    for index in edge_indices:
        current = ring[index]
        previous = ring[index - 1]
        if (previous[1] > latitude) != (current[1] > latitude):
            crossing = (current[0] - previous[0]) * (latitude - previous[1]) / (
                current[1] - previous[1]
            ) + previous[0]
            crossings.append(crossing)
    crossings.sort()
    return list(zip(crossings[::2], crossings[1::2]))


def _segment_inside_cell_midpoint(first, second, min_lon, min_lat, max_lon, max_lat):
    """Return a boundary point where a polygon segment touches the cell."""
    x0, y0 = first
    dx, dy = second[0] - x0, second[1] - y0
    lower, upper = 0.0, 1.0
    for p, q in (
        (-dx, x0 - min_lon),
        (dx, max_lon - x0),
        (-dy, y0 - min_lat),
        (dy, max_lat - y0),
    ):
        if p == 0:
            if q < 0:
                return None
            continue
        fraction = q / p
        if p < 0:
            lower = max(lower, fraction)
        else:
            upper = min(upper, fraction)
        if lower > upper:
            return None
    parameter = (lower + upper) / 2
    return x0 + parameter * dx, y0 + parameter * dy


def _land_point_in_cell(cell, bands):
    """Find an interior point of polygon land intersecting a 0.5-degree cell."""
    lower_latitude, lower_longitude = cell
    min_latitude, max_latitude = lower_latitude, lower_latitude + 0.5
    min_longitude, max_longitude = lower_longitude, lower_longitude + 0.5
    wide_by_latitude, grid = bands
    first_lat_band = _latitude_band(min_latitude)
    last_lat_band = _latitude_band(max_latitude)
    first_lon_band = max(0, min(_LONGITUDE_BANDS - 1, int(math.floor(min_longitude + 180))))
    last_lon_band = max(0, min(_LONGITUDE_BANDS - 1, int(math.floor(max_longitude + 180))))

    candidates = []
    seen = set()
    for latitude_band in range(first_lat_band, last_lat_band + 1):
        entries = list(wide_by_latitude[latitude_band])
        for longitude_band in range(first_lon_band, last_lon_band + 1):
            entries.extend(grid.get((latitude_band, longitude_band), ()))
        for entry in entries:
            identity = id(entry)
            if identity in seen:
                continue
            seen.add(identity)
            _, shell, holes, min_lon, min_lat, max_lon, max_lat = entry
            if max_lon < min_longitude or min_lon > max_longitude:
                continue
            if max_lat < min_latitude or min_lat > max_latitude:
                continue
            indexed_shell = _ring_edges_in_latitude_range(
                shell, min_latitude, max_latitude
            )
            indexed_holes = tuple(
                _ring_edges_in_latitude_range(hole, min_latitude, max_latitude)
                for hole in holes
            )
            candidates.append((indexed_shell, indexed_holes))

    for shell, holes in candidates:
        shell_ring, shell_edges = shell
        scanlines = {min_latitude, max_latitude}
        scanlines.update(
            latitude
            for index in shell_edges
            for latitude in (shell_ring[index - 1][1], shell_ring[index][1])
            if min_latitude < latitude < max_latitude
        )
        for hole_ring, hole_edges in holes:
            scanlines.update(
                latitude
                for index in hole_edges
                for latitude in (hole_ring[index - 1][1], hole_ring[index][1])
                if min_latitude < latitude < max_latitude
            )
        scanlines = sorted(scanlines)

        for lower, upper in zip(scanlines, scanlines[1:]):
            if upper <= lower:
                continue
            latitude = (lower + upper) / 2
            for shell_left, shell_right in _ring_intervals(
                shell_ring, shell_edges, latitude
            ):
                left = max(min_longitude, shell_left)
                right = min(max_longitude, shell_right)
                if right <= left:
                    continue
                land_intervals = [(left, right)]
                for hole, hole_edges in holes:
                    for hole_left, hole_right in _ring_intervals(
                        hole, hole_edges, latitude
                    ):
                        next_intervals = []
                        for interval_left, interval_right in land_intervals:
                            if hole_right <= interval_left or hole_left >= interval_right:
                                next_intervals.append((interval_left, interval_right))
                                continue
                            if hole_left > interval_left:
                                next_intervals.append((interval_left, min(hole_left, interval_right)))
                            if hole_right < interval_right:
                                next_intervals.append((max(hole_right, interval_left), interval_right))
                        land_intervals = next_intervals
                        if not land_intervals:
                            break
                for interval_left, interval_right in land_intervals:
                    width = interval_right - interval_left
                    if width > 1e-12:
                        return (interval_left + interval_right) / 2, latitude, False

    # Include polygons that touch a cell only along its closed boundary.
    for shell, holes in candidates:
        for indexed_ring in (shell,) + holes:
            ring, edge_indices = indexed_ring
            for index in edge_indices:
                point = _segment_inside_cell_midpoint(
                    ring[index - 1],
                    ring[index],
                    min_longitude,
                    min_latitude,
                    max_longitude,
                    max_latitude,
                )
                if point is not None:
                    return point[0], point[1], True
    return None


@st.cache_data(show_spinner="Positioning coastal cell markers…")
def _cached_zone_display_positions(
    zones: tuple[str, ...],
    center_countries: tuple[str, ...],
    path: str,
    modified_ns: int,
):
    """Cache display-only cell positions without changing source coordinates."""
    bands = _load_country_polygons(path, modified_ns)
    result = {}
    for zone, country in zip(zones, center_countries):
        try:
            lower_latitude, lower_longitude = (float(value) for value in zone.split("_", 1))
        except (TypeError, ValueError):
            result[zone] = (None, None, "Review: invalid cell coordinates")
            continue

        center = (lower_longitude + 0.25, lower_latitude + 0.25)
        if country != UNKNOWN_COUNTRY:
            result[zone] = (*center, "Original cell center retained")
            continue

        land_point = _land_point_in_cell((lower_latitude, lower_longitude), bands)
        if land_point is None:
            result[zone] = (*center, "Review: no land intersection found in boundary data")
        else:
            longitude, latitude, boundary_only = land_point
            note = (
                "Representative point on land-cell boundary; verify the contact"
                if boundary_only
                else "Representative point in land-cell intersection"
            )
            result[zone] = (longitude, latitude, note)
    return result


def get_zone_display_positions(
    zones: tuple[str, ...],
    center_countries: tuple[str, ...],
    path: str = str(COUNTRIES_GEOJSON),
):
    """Return cached display positions while keeping original cell centers intact."""
    try:
        modified_ns = Path(path).stat().st_mtime_ns
    except OSError:
        modified_ns = 0
    if len(zones) != len(center_countries):
        raise ValueError("Each cell must have one corresponding center-country assignment.")
    return _cached_zone_display_positions(zones, center_countries, path, modified_ns)
