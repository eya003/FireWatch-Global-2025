"""Worldwide detections and category Overview."""

import streamlit as st

from dashboard.data import (
    DataValidationError,
    prepare_monthly,
    prepare_type_distribution,
)
from dashboard.data_access import get_fire_data
from dashboard.visuals import (
    monthly_detections_chart,
    type_distribution_chart,
    world_top_countries_chart,
)
from dashboard.world_country_data import get_world_top_countries


try:
    fire_data = get_fire_data()
except DataValidationError as error:
    st.error("The dashboard could not load valid source data. {}".format(error))
    st.stop()

monthly = prepare_monthly(fire_data.monthly)
type_distribution = prepare_type_distribution(fire_data.types)

total_detections = int(fire_data.types["count"].sum())
vegetation_count = int(fire_data.types.loc[fire_data.types["type"] == 0, "count"].iloc[0])
grid_cells = int(fire_data.zones["zone"].nunique())
peak_row = monthly.loc[monthly["count"].idxmax()]

st.markdown(
    """
    <div class="page-header">
      <div class="page-eyebrow">FireWatch | Global Fire Intelligence</div>
      <div class="page-title">Worldwide Fire Detection Overview</div>
      <div class="page-description">A global view of satellite thermal detections and presumed vegetation fires.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "<span class='meta-pill'>Year | 2025</span><span class='meta-pill'>Source | NASA FIRMS VIIRS S-NPP</span>",
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div style="background:#111820;border:1px solid #263442;border-radius:14px;padding:1rem 1.2rem;margin:.5rem 0 1.25rem;">
      <div class="section-heading">About the Dataset</div>
      <div class="section-note">Worldwide active fire and thermal anomaly observations from NASA FIRMS.</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:.8rem 1.4rem;">
        <div><div class="kpi-label">Source</div><div style="color:#f8fafc;font-weight:650;">NASA FIRMS</div></div>
        <div><div class="kpi-label">Instrument</div><div style="color:#f8fafc;font-weight:650;">VIIRS S-NPP</div></div>
        <div><div class="kpi-label">Year</div><div style="color:#f8fafc;font-weight:650;">2025</div></div>
        <div><div class="kpi-label">Coverage &amp; format</div><div style="color:#f8fafc;font-weight:650;">Worldwide · 219 CSV files · 15 columns</div></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def render_kpi(column, label, value):
    column.markdown(
        "<div class='kpi-card'><div class='kpi-label'>{}</div><div class='kpi-value'>{}</div></div>".format(
            label, value
        ),
        unsafe_allow_html=True,
    )


kpi_columns = st.columns(4, gap="medium")
render_kpi(kpi_columns[0], "Total thermal detections", "{:,.0f}".format(total_detections))
render_kpi(kpi_columns[1], "Presumed vegetation fire detections", "{:,.0f}".format(vegetation_count))
render_kpi(kpi_columns[2], "Geographic grid cells", "{:,.0f}".format(grid_cells))
render_kpi(kpi_columns[3], "Peak detection month", "{} · {:,.0f}".format(peak_row["month_label"], peak_row["count"]))

left, right = st.columns([1.4, 1], gap="large")

with left:
    st.markdown("<div class='section-heading'>Monthly detections</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-note'>Worldwide type 0 detections · grouped by acquisition month</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(monthly_detections_chart(monthly), use_container_width=True, config={"displayModeBar": False})

with right:
    st.markdown("<div class='section-heading'>Category distribution</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-note'>All thermal detection categories · count and share</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(type_distribution_chart(type_distribution), use_container_width=True, config={"displayModeBar": False})

st.markdown("<div class='section-heading'>Top 10 Countries by Fire Detections</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='section-note'>Worldwide type 0 detections | Spark country summary | 2025.</div>",
    unsafe_allow_html=True,
)
try:
    world_countries = get_world_top_countries()
except DataValidationError as error:
    st.info(
        "Worldwide country ranking is unavailable: {} No geographic-cell estimate is substituted.".format(error)
    )
else:
    st.plotly_chart(
        world_top_countries_chart(world_countries),
        use_container_width=True,
        config={"displayModeBar": False},
    )

st.caption("Counts are satellite detections, not counts of individually confirmed ground fires. Average FRP is reported in megawatts.")
