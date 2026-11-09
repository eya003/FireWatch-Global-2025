"""Live Monitoring: Module C alerts (Kafka -> Spark Streaming -> HDFS -> HBase)."""

import math

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from dashboard.data import DataValidationError
from dashboard.live_data import (
    ALERT_FRP_THRESHOLD_MW,
    DockerAlertReader,
    ReaderUnavailable,
    SnapshotAlertReader,
    get_live_monitoring_reader,
)
from dashboard.spark_data import get_tunisia_zone_month_stats


MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
REFRESH_SECONDS = 8
STATUS_LABELS = {
    "streaming": ("Streaming", "#22c55e", "All services are up and Spark Streaming is consuming Kafka."),
    "ready": ("Ready", "#f59e0b", "Services are up. Start Spark Streaming and the producer to stream alerts."),
    "degraded": ("Degraded", "#ef4444", "At least one core service (HDFS, ZooKeeper, Kafka, HBase) is down."),
    "snapshot": ("Recorded replay", "#38bdf8", "Recorded output of the pipeline (replay of the real 2025 detections)."),
}


st.markdown(
    """
    <div class="page-header">
      <div class="page-eyebrow">FireWatch | Global Fire Intelligence</div>
      <div class="page-title">Live Monitoring</div>
      <div class="page-description">Tunisia alert pipeline: NASA FIRMS detections streamed through Kafka,
      filtered by Spark Streaming and stored in HBase.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def _render_disconnected() -> None:
    st.warning("Data source not connected")
    st.markdown(
        "<div class='map-context-note'>Live Monitoring is a preparatory interface. "
        "Kafka, Spark Streaming, and HBase are not connected to this dashboard.</div>",
        unsafe_allow_html=True,
    )
    status_column, alerts_column = st.columns(2, gap="large")
    with status_column:
        st.markdown("<div class='section-heading'>Pipeline status</div>", unsafe_allow_html=True)
        st.info("Unavailable until a real Module C status reader is provided.")
    with alerts_column:
        st.markdown("<div class='section-heading'>Alert feed</div>", unsafe_allow_html=True)
        st.info("Recent alerts will appear after the HBase reader is connected.")


def _kpi(column, label: str, value: str) -> None:
    column.markdown(
        "<div class='kpi-card'><div class='kpi-label'>{}</div><div class='kpi-value'>{}</div></div>".format(
            label, value
        ),
        unsafe_allow_html=True,
    )


def _service_pills(services: dict[str, bool]) -> str:
    pills = []
    for name, running in services.items():
        color = "#22c55e" if running else "#ef4444"
        pills.append(
            "<span class='meta-pill'><span style='color:{};'>&#9679;</span> {}</span>".format(color, name)
        )
    return "".join(pills)


def _alerts_map(alerts: pd.DataFrame) -> pdk.Deck:
    data = alerts.copy()
    data["radius"] = data["frp_mw"].clip(lower=20, upper=450) * 60
    data["time_display"] = data["timestamp"].dt.strftime("%Y-%m-%d %H:%M UTC")
    data["frp_display"] = data["frp_mw"].map("{:.1f}".format)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="[longitude, latitude]",
        get_radius="radius",
        radius_min_pixels=4,
        radius_max_pixels=28,
        get_fill_color=[239, 68, 68, 190],
        get_line_color=[255, 237, 213, 220],
        stroked=True,
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )
    return pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=36.0, longitude=9.4, zoom=6.2, pitch=0),
        map_style=MAP_STYLE,
        tooltip={
            "html": "<b>Zone {zone}</b><br/>{time_display}<br/>FRP: {frp_display} MW<br/>Confidence: {confidence}",
            "style": {"backgroundColor": "#111820", "color": "#f8fafc", "border": "1px solid #f97316"},
        },
        height=430,
    )


def _frp_chart(alerts: pd.DataFrame) -> go.Figure:
    data = alerts.sort_values("timestamp")
    figure = go.Figure(
        go.Scatter(
            x=data["timestamp"],
            y=data["frp_mw"],
            mode="markers",
            marker=dict(
                color="#f97316",
                size=(data["frp_mw"].clip(upper=450) ** 0.5) * 1.6 + 4,
                line=dict(color="#fed7aa", width=1),
                opacity=0.85,
            ),
            customdata=data[["zone"]],
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Zone %{customdata[0]}<br>FRP %{y:.1f} MW<extra></extra>",
        )
    )
    max_frp = max(float(data["frp_mw"].max()), ALERT_FRP_THRESHOLD_MW)
    figure.add_hline(
        y=ALERT_FRP_THRESHOLD_MW,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text="Alert threshold · {:.0f} MW".format(ALERT_FRP_THRESHOLD_MW),
        annotation_position="top left",
    )
    figure.update_layout(
        template="plotly_dark",
        title="Fire Radiative Power of each alert",
        title_x=0.02,
        margin=dict(l=12, r=12, t=55, b=12),
        yaxis=dict(
            title="FRP (MW, log scale)",
            type="log",
            range=[1.0, math.log10(max_frp * 1.6)],
            gridcolor="rgba(148,163,184,0.12)",
        ),
        xaxis=dict(title="Detection time (UTC)"),
        showlegend=False,
        height=430,
    )
    return figure


def _zone_context(alerts: pd.DataFrame) -> None:
    """Real-time reflexes vs batch memory: compare an alert with its zone history (Spark)."""
    st.markdown("<div class='section-heading'>Zone context · batch history</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-note'>The alert (real time) compared with the zone history computed by Spark "
        "(zone_month_stats.csv, Tunisia 2025).</div>",
        unsafe_allow_html=True,
    )
    zones = alerts["zone"].value_counts().index.tolist()
    zone = st.selectbox("Zone", zones, key="live_context_zone")
    latest = alerts.loc[alerts["zone"] == zone].iloc[0]
    try:
        stats = get_tunisia_zone_month_stats()
    except DataValidationError as error:
        st.info("Spark zone statistics unavailable: {}".format(error))
        return
    history = stats.loc[stats["zone"] == zone].sort_values("year_month")
    if history.empty:
        st.info("No Spark history for zone {}.".format(zone))
        return

    yearly_avg = (history["avg_frp"] * history["count"]).sum() / history["count"].sum()
    ratio = latest["frp_mw"] / yearly_avg if yearly_avg else float("nan")
    left, middle, right = st.columns(3)
    _kpi(left, "Latest alert FRP", "{:.1f} MW".format(latest["frp_mw"]))
    _kpi(middle, "Zone average FRP (2025)", "{:.1f} MW".format(yearly_avg))
    _kpi(right, "Intensity vs zone average", "× {:.1f}".format(ratio))

    figure = go.Figure()
    figure.add_bar(x=history["year_month"], y=history["count"], name="Detections", marker_color="#f97316")
    figure.add_scatter(
        x=history["year_month"], y=history["max_frp"], name="Max FRP (MW)",
        yaxis="y2", mode="lines+markers", line=dict(color="#fde68a"),
    )
    figure.update_layout(
        template="plotly_dark",
        title="Zone {} · monthly detections and maximum FRP (Spark)".format(zone),
        title_x=0.02,
        margin=dict(l=12, r=12, t=55, b=12),
        yaxis=dict(title="Detections", gridcolor="rgba(148,163,184,0.12)"),
        yaxis2=dict(title="Max FRP (MW)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=-0.2),
        height=380,
    )
    st.plotly_chart(figure, use_container_width=True)


def _render(reader) -> None:
    status = reader.pipeline_status()
    if reader.is_live:
        if status == "streaming":
            st.session_state["live_seen_streaming"] = True
        elif st.session_state.get("live_seen_streaming") and st.session_state.get("live_auto_refresh", True):
            # Spark Streaming has just stopped (end of the demo): freeze the page.
            st.session_state["live_seen_streaming"] = False
            st.session_state["live_auto_refresh"] = False
            st.session_state["live_auto_stopped"] = True
            st.rerun(scope="app")
    label, color, explanation = STATUS_LABELS.get(status, ("Unknown", "#94a3b8", ""))
    st.markdown(
        "<div class='section-heading'>Pipeline status · <span style='color:{};'>{}</span></div>"
        "<div class='section-note'>{}</div>".format(color, label, explanation),
        unsafe_allow_html=True,
    )
    if isinstance(reader, DockerAlertReader):
        st.markdown(_service_pills(reader.services()), unsafe_allow_html=True)

    alerts = reader.read_alerts(limit=0)
    if alerts.empty:
        st.info(
            "No alert written yet. Start Spark Streaming, then the producer "
            "(replay or NASA API): alerts appear here automatically."
        )
        return

    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, "Alerts", "{:,}".format(len(alerts)))
    _kpi(k2, "Zones in alert", "{:,}".format(alerts["zone"].nunique()))
    _kpi(k3, "Max FRP", "{:.1f} MW".format(alerts["frp_mw"].max()))
    _kpi(k4, "Latest detection", alerts["timestamp"].max().strftime("%Y-%m-%d %H:%M"))

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("<div class='section-heading'>Alert locations</div>", unsafe_allow_html=True)
        st.pydeck_chart(_alerts_map(alerts), use_container_width=True)
    with right:
        st.markdown("<div class='section-heading'>Fire Radiative Power</div>", unsafe_allow_html=True)
        st.plotly_chart(_frp_chart(alerts), use_container_width=True)

    st.markdown("<div class='section-heading'>Alert feed · most recent first</div>", unsafe_allow_html=True)
    feed = alerts.head(15)[["timestamp", "zone", "latitude", "longitude", "frp_mw", "confidence"]].copy()
    feed["timestamp"] = feed["timestamp"].dt.strftime("%Y-%m-%d %H:%M UTC")
    st.dataframe(
        feed.rename(columns={
            "timestamp": "Detection time", "zone": "Zone", "latitude": "Latitude",
            "longitude": "Longitude", "frp_mw": "FRP (MW)", "confidence": "Confidence",
        }),
        hide_index=True,
        use_container_width=True,
    )

    _zone_context(alerts)


# ---------------------------------------------------------------- source choice
default_reader = get_live_monitoring_reader()
if default_reader is None:
    _render_disconnected()
    st.stop()

SOURCES = {
    "Live cluster (Docker)": DockerAlertReader,
    "Recorded replay (snapshot)": SnapshotAlertReader,
}
default_label = "Live cluster (Docker)" if isinstance(default_reader, DockerAlertReader) else "Recorded replay (snapshot)"
source_label = st.selectbox(
    "Data source",
    list(SOURCES),
    index=list(SOURCES).index(default_label),
    key="live_source",
)
reader = default_reader if source_label == default_label else SOURCES[source_label]()

st.markdown(
    "<span class='meta-pill'>Source | {}</span>"
    "<span class='meta-pill'>Rule | latitude ≥ 35.5 · FRP ≥ {:.0f} MW · confidence ≠ low</span>".format(
        reader.label, ALERT_FRP_THRESHOLD_MW
    ),
    unsafe_allow_html=True,
)
if not reader.is_live:
    st.markdown(
        "<div class='map-context-note'>Recorded output of the streaming pipeline: the real 2025 NASA FIRMS "
        "detections were replayed through Kafka and Spark Streaming (70 alerts). Use “Live cluster” "
        "when the hadoop-master container is running.</div>",
        unsafe_allow_html=True,
    )


def _set_auto_refresh(value: bool) -> None:
    st.session_state["live_auto_refresh"] = value
    st.session_state["live_auto_stopped"] = False


auto_refresh = False
if reader.is_live:
    # Keep the page fully visible while it refreshes (no grey "stale" effect).
    st.markdown(
        "<style>[data-stale='true']{opacity:1 !important;transition:none !important;}</style>",
        unsafe_allow_html=True,
    )
    auto_refresh = st.session_state.get("live_auto_refresh", True)
    note_column, button_column = st.columns([4, 1])
    with note_column:
        if auto_refresh:
            st.caption("Auto-refresh every {} s · pauses automatically when Spark Streaming stops.".format(REFRESH_SECONDS))
        elif st.session_state.get("live_auto_stopped"):
            st.caption("Streaming finished · auto-refresh paused. Resume it before starting a new demo.")
        else:
            st.caption("Auto-refresh paused.")
    with button_column:
        if auto_refresh:
            st.button("Pause refresh", key="live_pause", on_click=_set_auto_refresh, args=(False,), use_container_width=True)
        else:
            st.button("Resume refresh", key="live_resume", on_click=_set_auto_refresh, args=(True,), use_container_width=True)


@st.fragment(run_every=REFRESH_SECONDS if auto_refresh else None)
def _live_section() -> None:
    try:
        _render(reader)
    except ReaderUnavailable as error:
        st.error("Live source unreachable: {} Switch to “Recorded replay”.".format(error))


_live_section()

if isinstance(reader, DockerAlertReader):
    with st.expander("Verify the data stored in HBase"):
        st.caption("Runs `count 'fire_alerts'` and `get 'fire_monthly', '2025-09'` in the HBase shell (≈10 s).")
        if st.button("Query HBase", key="live_hbase_check"):
            with st.spinner("Querying HBase…"):
                try:
                    st.code(reader.hbase_check(), language="text")
                except ReaderUnavailable as error:
                    st.error(str(error))
