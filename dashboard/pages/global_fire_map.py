"""World annual and Tunisia monthly geographic fire exploration."""

import math

import pydeck as pdk
import streamlit as st

from dashboard.countries import get_zone_country_map, get_zone_display_positions
from dashboard.data import (
    DataValidationError,
    prepare_zone_map_data,
    ranked_zone_csv_bytes,
    rank_zone_map_data,
)
from dashboard.data_access import get_fire_data
from dashboard.map_config import world_map_view
from dashboard.spark_data import (
    get_tunisia_zone_month_stats,
    months_for_zone_stats,
    prepare_tunisia_month,
)


TOP_N_OPTIONS = [10, 20, 50, 100, 500, "All cells"]
RANKING_LABELS = {
    "count": "Detection Count",
    "avg_frp": "Average FRP",
    "max_frp": "Maximum FRP",
}
MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"


def _interpolate_color(value: float, minimum: float, maximum: float) -> list[int]:
    """Map a metric onto a warm orange-red ramp using a log scale."""
    low = [253, 186, 116]
    middle = [249, 115, 22]
    high = [220, 38, 38]
    log_value = math.log1p(value)
    log_min, log_max = math.log1p(minimum), math.log1p(maximum)
    position = 0.5 if log_max == log_min else (log_value - log_min) / (log_max - log_min)
    start, end, local = (
        (low, middle, position * 2)
        if position <= 0.5
        else (middle, high, (position - 0.5) * 2)
    )
    return [round(start[index] + (end[index] - start[index]) * local) for index in range(3)] + [220]


def _format_metric(value: float, ranking: str) -> str:
    if ranking == "count":
        return "{:,.0f}".format(value)
    return "{:.2f} MW".format(value)


def _save_widget_state(widget_key):
    st.session_state["_saved_{}".format(widget_key)] = st.session_state[widget_key]


def _restore_widget_state(widget_key, default, choices=None):
    saved_key = "_saved_{}".format(widget_key)
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state.get(saved_key, default)
    if choices is not None and st.session_state[widget_key] not in choices:
        st.session_state[widget_key] = default


def _add_geographic_context(map_data):
    """Add unchanged country assignments and cached display-only marker positions."""
    zones = tuple(map_data["zone"].astype(str))
    country_by_zone = get_zone_country_map(zones)
    map_data["country"] = map_data["zone"].map(country_by_zone)
    center_countries = tuple(map_data["country"].astype(str))
    display_positions = get_zone_display_positions(zones, center_countries)
    map_data["display_longitude"] = [display_positions[zone][0] for zone in zones]
    map_data["display_latitude"] = [display_positions[zone][1] for zone in zones]
    map_data["display_position_note"] = [display_positions[zone][2] for zone in zones]
    return map_data


def _render_ranked_map(
    map_data,
    *,
    ranking_options,
    scope_label,
    source_label,
    csv_columns,
    csv_filename,
    map_tooltip,
    view_state,
    key_prefix,
    table_columns,
):
    controls = st.columns([1.2, 1, 1.5], gap="medium")
    ranking_key = "{}_ranking".format(key_prefix)
    top_n_key = "{}_top_n".format(key_prefix)
    minimum_key = "{}_minimum_count".format(key_prefix)
    _restore_widget_state(ranking_key, ranking_options[0], ranking_options)
    _restore_widget_state(top_n_key, TOP_N_OPTIONS[4], TOP_N_OPTIONS)
    _restore_widget_state(minimum_key, 0)
    ranking = controls[0].selectbox(
        "Rank cells by",
        ranking_options,
        format_func=RANKING_LABELS.__getitem__,
        key=ranking_key,
        on_change=_save_widget_state,
        args=(ranking_key,),
    )
    top_n_choice = controls[1].selectbox(
        "Show top N",
        TOP_N_OPTIONS,
        key=top_n_key,
        on_change=_save_widget_state,
        args=(top_n_key,),
    )
    minimum_count = controls[2].number_input(
        "Minimum detections per cell",
        min_value=0,
        value=0,
        step=1,
        key=minimum_key,
        on_change=_save_widget_state,
        args=(minimum_key,),
        help="This optional threshold applies before ranking and Top N selection.",
    )
    top_n = None if top_n_choice == "All cells" else int(top_n_choice)
    if top_n is None:
        st.warning(
            "All {:,} cells are selected. Rendering the full map may take longer on slower devices.".format(
                len(map_data)
            )
        )

    filtered_map_data = rank_zone_map_data(
        map_data,
        ranking=ranking,
        top_n=top_n,
        minimum_count=int(minimum_count),
    )
    if filtered_map_data.empty:
        st.info("No geographic cells match the selected detection threshold.")
        return

    ranking_columns = {
        "count": "count",
        "avg_frp": "avg_frp_mw",
        "max_frp": "max_frp_mw",
    }
    metric_column = ranking_columns[ranking]
    metric_values = filtered_map_data[metric_column].astype(float)
    metric_min, metric_max = float(metric_values.min()), float(metric_values.max())
    deck_data = filtered_map_data.copy()
    deck_data["point_color"] = [
        _interpolate_color(value, metric_min, metric_max) for value in metric_values
    ]
    deck_data["count_display"] = deck_data["count"].map(
        lambda value: "{:,.0f}".format(value)
    )
    deck_data["frp_display"] = deck_data["avg_frp_mw"].map(
        lambda value: "{:.2f}".format(value)
    )
    deck_data["map_position_note"] = deck_data["display_position_note"]
    deck_data["cell_center_display"] = deck_data.apply(
        lambda row: "{:.2f}°, {:.2f}°".format(
            row["cell_center_latitude"], row["cell_center_longitude"]
        ),
        axis=1,
    )
    deck_data["map_marker_display"] = deck_data.apply(
        lambda row: "{:.2f}°, {:.2f}°".format(
            row["display_latitude"], row["display_longitude"]
        ),
        axis=1,
    )
    if "max_frp_mw" in deck_data:
        deck_data["max_frp_display"] = deck_data["max_frp_mw"].map(
            lambda value: "{:.2f}".format(value)
        )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=deck_data,
        get_position="[display_longitude, display_latitude]",
        get_fill_color="point_color",
        get_radius=5600,
        radius_min_pixels=2,
        radius_max_pixels=15,
        pickable=True,
        auto_highlight=True,
        stroked=True,
        get_line_color=[255, 237, 213, 210],
        line_width_min_pixels=0.5,
    )
    deck = pdk.Deck(
        layers=[layer],
        views=[world_map_view()],
        initial_view_state=view_state,
        map_style=MAP_STYLE,
        tooltip={
            "html": map_tooltip,
            "style": {
                "backgroundColor": "#111820",
                "color": "#f8fafc",
                "border": "1px solid #f97316",
            },
        },
        height=620,
    )

    metric_label = RANKING_LABELS[ranking].lower()
    st.markdown(
        "<div class='section-heading'>{}</div>".format(scope_label),
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='section-note'>{:,} of {:,} cells shown · ranked by {} · source: {}</div>".format(
            len(filtered_map_data), len(map_data), metric_label, source_label
        ),
        unsafe_allow_html=True,
    )
    st.pydeck_chart(deck, use_container_width=True)

    legend_start = _format_metric(metric_min, ranking)
    legend_end = _format_metric(metric_max, ranking)
    st.markdown(
        "<div style='display:flex;align-items:center;gap:.8rem;max-width:520px;margin:.2rem 0 1rem;'>"
        "<span style='color:#cbd5e1;font-size:.8rem;'>Lower {}</span>"
        "<div style='height:10px;flex:1;border-radius:99px;background:linear-gradient(90deg,#fdba74,#f97316,#dc2626);'></div>"
        "<span style='color:#cbd5e1;font-size:.8rem;'>Higher {}</span></div>".format(
            metric_label, metric_label
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        "Displayed metric range: {} to {}. Point color uses a logarithmic orange-to-red scale.".format(
            legend_start, legend_end
        )
    )
    st.markdown("<div class='section-heading'>Ranked geographic cells</div>", unsafe_allow_html=True)
    table_data = filtered_map_data[table_columns[0]].rename(columns=table_columns[1])
    st.dataframe(
        table_data,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Detections": st.column_config.NumberColumn(format="%d"),
            "Avg FRP (MW)": st.column_config.NumberColumn(format="%.2f"),
            "Max FRP (MW)": st.column_config.NumberColumn(format="%.2f"),
            "Cell center latitude": st.column_config.NumberColumn(format="%.2f°"),
            "Cell center longitude": st.column_config.NumberColumn(format="%.2f°"),
            "Map marker latitude": st.column_config.NumberColumn(format="%.2f°"),
            "Map marker longitude": st.column_config.NumberColumn(format="%.2f°"),
        },
    )
    csv_bytes = ranked_zone_csv_bytes(filtered_map_data, csv_columns)
    st.download_button(
        "Download filtered cells as CSV",
        data=csv_bytes,
        file_name=csv_filename,
        mime="text/csv",
        key="{}_download".format(key_prefix),
    )


def _render_world_annual():
    try:
        fire_data = get_fire_data()
        map_data = prepare_zone_map_data(fire_data.zones, fire_data.frp_by_zone)
        map_data = _add_geographic_context(map_data)
    except DataValidationError as error:
        st.error("The global map could not load valid geographic data. {}".format(error))
        return

    st.markdown(
        "<div class='map-context-note'>World annual records are MapReduce aggregates of type 0 detections. "
        "Map markers show cell centers or representative points in coastal cells, not exact detection coordinates. "
        "Country attribution follows cell centers and is approximate. These exports contain no month field.</div>",
        unsafe_allow_html=True,
    )
    countries = sorted(map_data["country"].dropna().astype(str).unique().tolist())
    selected_countries = st.multiselect(
        "Filter countries",
        options=countries,
        default=countries,
        key="world_annual_countries",
        help="Country is assigned approximately from each aggregated cell center.",
    )
    map_data = map_data.loc[map_data["country"].isin(selected_countries)].copy()
    _render_ranked_map(
        map_data,
        ranking_options=["count", "avg_frp"],
        scope_label="World · Annual · 2025",
        source_label="MapReduce exports",
        csv_columns=[
            "zone",
            "country",
            "count",
            "avg_frp_mw",
            "cell_center_latitude",
            "cell_center_longitude",
        ],
        csv_filename="firewatch_global_fire_map.csv",
        map_tooltip=(
            "<b>Grid cell {zone}</b><br/>Country: {country}<br/>Detections: {count_display}"
            "<br/>Avg FRP: {frp_display} MW<br/>Cell center: {cell_center_display}"
            "<br/>Map marker: {map_marker_display} ({map_position_note})"
            "<br/>Aggregated representative coordinates, not exact detection locations."
        ),
        view_state=pdk.ViewState(
            latitude=20, longitude=0, zoom=1, min_zoom=0, max_zoom=12, pitch=0
        ),
        key_prefix="world_annual",
        table_columns=(
            [
                "zone",
                "country",
                "count",
                "avg_frp_mw",
                "cell_center_latitude",
                "cell_center_longitude",
            ],
            {
                "zone": "Grid cell",
                "country": "Country",
                "count": "Detections",
                "avg_frp_mw": "Avg FRP (MW)",
                "cell_center_latitude": "Cell center latitude",
                "cell_center_longitude": "Cell center longitude",
            },
        ),
    )


def _render_tunisia_monthly():
    try:
        spark_data = get_tunisia_zone_month_stats()
    except DataValidationError as error:
        st.error("Tunisia monthly Spark data could not be loaded. {}".format(error))
        return

    months = months_for_zone_stats(spark_data)
    totals = spark_data.groupby("year_month")["count"].sum()
    default_month = max(totals.index, key=lambda month: (int(totals[month]), month))
    month_key = "tunisia_month"
    _restore_widget_state(month_key, default_month, months)
    month = st.selectbox(
        "Month",
        months,
        key=month_key,
        on_change=_save_widget_state,
        args=(month_key,),
    )
    month_data = prepare_tunisia_month(spark_data, month)
    st.markdown(
        "<div class='map-context-note'>Tunisia monthly records are Spark aggregates by 0.5-degree cell. "
        "The selected month filters observations within Tunisia; boundary cells can extend beyond the country. "
        "Map coordinates are cell centers or representative land positions, not exact detection coordinates.</div>",
        unsafe_allow_html=True,
    )
    if month_data.empty:
        st.info(
            "No Tunisia Spark zone data is available for {}. Select another month to explore recorded cells.".format(
                month
            )
        )
        return

    try:
        map_data = _add_geographic_context(month_data)
    except (DataValidationError, ValueError) as error:
        st.error("Tunisia geographic cells could not be prepared. {}".format(error))
        return
    map_data["source_scope"] = "Tunisia"
    map_data["source_month"] = month
    _render_ranked_map(
        map_data,
        ranking_options=["count", "avg_frp", "max_frp"],
        scope_label="Tunisia · Monthly · {}".format(month),
        source_label="Spark zone_month_stats.csv",
        csv_columns=[
            "zone",
            "year_month",
            "count",
            "avg_frp",
            "max_frp",
            "cell_center_latitude",
            "cell_center_longitude",
            "display_latitude",
            "display_longitude",
            "display_position_note",
        ],
        csv_filename="firewatch_tunisia_{}.csv".format(month),
        map_tooltip=(
            "<b>Grid cell {zone}</b><br/>Source scope: Tunisia<br/>Month: {year_month}"
            "<br/>Detections: {count_display}<br/>Avg FRP: {frp_display} MW"
            "<br/>Max FRP: {max_frp_display} MW<br/>Cell center: {cell_center_display}"
            "<br/>Map marker: {map_marker_display} ({map_position_note})"
            "<br/>Aggregated representative coordinates, not exact detection locations."
        ),
        view_state=pdk.ViewState(
            latitude=34, longitude=9.5, zoom=5.2, min_zoom=3, max_zoom=12, pitch=0
        ),
        key_prefix="tunisia_monthly",
        table_columns=(
            [
                "zone",
                "year_month",
                "source_scope",
                "count",
                "avg_frp",
                "max_frp",
                "cell_center_latitude",
                "cell_center_longitude",
                "display_latitude",
                "display_longitude",
                "display_position_note",
            ],
            {
                "zone": "Grid cell",
                "year_month": "Month",
                "source_scope": "Source scope",
                "count": "Detections",
                "avg_frp": "Avg FRP (MW)",
                "max_frp": "Max FRP (MW)",
                "cell_center_latitude": "Cell center latitude",
                "cell_center_longitude": "Cell center longitude",
                "display_latitude": "Map marker latitude",
                "display_longitude": "Map marker longitude",
                "display_position_note": "Map position",
            },
        ),
    )


st.markdown(
    """
    <div class="page-header">
      <div class="page-eyebrow">FireWatch | Global Fire Intelligence</div>
      <div class="page-title">Fire Explorer</div>
      <div class="page-description">Explore annual worldwide fire cells or monthly Spark aggregates for Tunisia.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

exploration_scope = st.selectbox(
    "Explore",
    ["World — Annual", "Tunisia — Monthly"],
    key="fire_explorer_scope",
)
if exploration_scope == "World — Annual":
    _render_world_annual()
else:
    _render_tunisia_monthly()
