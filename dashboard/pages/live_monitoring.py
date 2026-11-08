"""Preparatory Live Monitoring interface; it does not simulate Module C."""

import streamlit as st

from dashboard.live_data import get_live_monitoring_reader


st.markdown(
    """
    <div class="page-header">
      <div class="page-eyebrow">FireWatch | Global Fire Intelligence</div>
      <div class="page-title">Live Monitoring</div>
      <div class="page-description">Operational view for the future Tunisia alert pipeline.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

reader = get_live_monitoring_reader()
if reader is None:
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

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("<div class='section-heading'>Alert locations</div>", unsafe_allow_html=True)
        st.caption("Map unavailable while the data source is disconnected.")
    with right:
        st.markdown("<div class='section-heading'>Fire Radiative Power</div>", unsafe_allow_html=True)
        st.caption("FRP in MW will be shown for real alerts when available.")
else:
    st.error(
        "A reader was configured, but this dashboard build has no validated rendering adapter for it yet."
    )
