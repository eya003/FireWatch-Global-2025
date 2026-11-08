"""Historical trends for global, Maghreb, and Tunisia scopes."""

import calendar

import streamlit as st

from dashboard.data import DataValidationError, prepare_monthly
from dashboard.data_access import get_fire_data
from dashboard.trends_data import (
    EXPECTED_COUNTRIES,
    get_spark_trends_data,
    monthly_changes,
    regional_country_comparison,
)
from dashboard.visuals import (
    country_ranking_chart,
    monthly_change_chart,
    regional_monthly_chart,
    tunisia_monthly_trend_chart,
    tunisia_top_days_chart,
    world_trends_chart,
)


st.markdown(
    """
    <div class="page-header">
      <div class="page-eyebrow">FireWatch | Global Fire Intelligence</div>
      <div class="page-title">Trends &amp; Insights</div>
      <div class="page-description">Compare the 2025 global signal with Maghreb country trends and detailed Tunisia activity.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

scope = st.selectbox(
    "Analysis scope",
    ["World | Global Trends", "Maghreb | Regional Comparison", "Tunisia | Detailed Trends"],
    key="trends_scope",
)


def _show_world_trends():
    try:
        fire_data = get_fire_data()
    except DataValidationError as error:
        st.error("Global monthly data could not be loaded. {}".format(error))
        return

    monthly = prepare_monthly(fire_data.monthly)
    changes = monthly_changes(monthly, month_column="month")
    peak = monthly.loc[monthly["count"].idxmax()]
    low = monthly.loc[monthly["count"].idxmin()]
    mean_count = float(monthly["count"].mean())
    upper_quartile = float(monthly["count"].quantile(0.75))
    high_months = monthly.loc[monthly["count"] >= upper_quartile, "month_label"].tolist()

    st.markdown(
        "<div class='map-context-note'>World annual scope · MapReduce type 0 detections · 2025. "
        "The high-activity guide marks the upper quartile of the twelve monthly values.</div>",
        unsafe_allow_html=True,
    )
    metrics = st.columns(4, gap="medium")
    metrics[0].metric("Most active month", "{} · {:,.0f}".format(peak["month_label"], peak["count"]))
    metrics[1].metric("Least active month", "{} · {:,.0f}".format(low["month_label"], low["count"]))
    metrics[2].metric("Monthly average", "{:,.0f}".format(mean_count))
    metrics[3].metric("Year total", "{:,.0f}".format(monthly["count"].sum()))

    st.markdown(
        "<div class='section-heading'>Global activity pattern</div>"
        "<div class='section-note'>Monthly detections, period threshold, and month-over-month movement.</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(world_trends_chart(monthly), use_container_width=True, key="global_trends_monthly_chart")

    left, right = st.columns([1.25, 1], gap="large")
    with left:
        st.plotly_chart(monthly_change_chart(changes), use_container_width=True, key="global_trends_change_chart")
    with right:
        st.markdown("<div class='section-heading'>Descriptive summary</div>", unsafe_allow_html=True)
        st.markdown(
            "The peak was **{}** with **{:,.0f}** detections; the low was **{}** with **{:,.0f}**. "
            "The average month recorded **{:,.0f}** detections. Months at or above the upper-quartile "
            "threshold ({:,.0f}) were **{}**.".format(
                peak["month_label"], peak["count"], low["month_label"], low["count"],
                mean_count, upper_quartile, ", ".join(high_months),
            )
        )
        st.caption("Monthly percentage change uses the previous month as its denominator. January has no prior month in this export.")

    display = changes.rename(
        columns={"month_label": "Month", "month": "Year-month", "count": "Detections", "change": "Change", "change_percent": "Change (%)"}
    )[["Year-month", "Month", "Detections", "Change", "Change (%)"]]
    st.markdown("<div class='section-heading'>Monthly change table</div>", unsafe_allow_html=True)
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Detections": st.column_config.NumberColumn(format="%d"),
            "Change": st.column_config.NumberColumn(format="%+d"),
            "Change (%)": st.column_config.NumberColumn(format="%+.1f%%"),
        },
    )


def _show_maghreb_trends(data):
    summary = data.country_summary
    monthly = data.country_monthly
    selected = st.multiselect(
        "Countries",
        options=list(EXPECTED_COUNTRIES),
        default=list(EXPECTED_COUNTRIES),
        key="trends_maghreb_countries",
    )
    st.markdown(
        "<div class='map-context-note'>Maghreb scope · Spark type 0 detections assigned to the four country boundaries. "
        "Country and monthly totals retain the existing Spark export definitions.</div>",
        unsafe_allow_html=True,
    )
    if not selected:
        st.info("Select at least one country to compare regional trends.")
        return

    filtered_monthly = monthly.loc[monthly["country"].isin(selected)].copy()
    filtered_summary = summary.loc[summary["country"].isin(selected)].copy()
    if filtered_monthly.empty or filtered_summary.empty:
        st.info("No Spark country trend rows are available for the selected countries.")
        return

    comparison = regional_country_comparison(filtered_summary, filtered_monthly)
    left, right = st.columns([1, 1.35], gap="large")
    with left:
        st.plotly_chart(country_ranking_chart(comparison), use_container_width=True, key="maghreb_country_ranking_chart")
    with right:
        st.plotly_chart(regional_monthly_chart(filtered_monthly, selected), use_container_width=True, key="maghreb_monthly_chart")

    display = comparison.rename(
        columns={"rank": "Rank", "country": "Country", "count": "2025 detections", "peak_month": "Peak month", "peak_month_detections": "Peak-month detections"}
    )[["Rank", "Country", "2025 detections", "Peak month", "Peak-month detections"]]
    st.markdown("<div class='section-heading'>Country comparison</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-note'>Ranked by annual total; peak month is the month with the highest Spark count for each selected country.</div>", unsafe_allow_html=True)
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Rank": st.column_config.NumberColumn(format="%d"),
            "2025 detections": st.column_config.NumberColumn(format="%d"),
            "Peak-month detections": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.download_button(
        "Download selected country comparison as CSV",
        data=display.to_csv(index=False).encode("utf-8"),
        file_name="firewatch_maghreb_country_comparison_2025.csv",
        mime="text/csv",
        key="maghreb_trends_download",
    )


def _show_tunisia_trends(data):
    monthly = data.tunisia_monthly.copy()
    monthly["month_label"] = monthly["year_month"].str[-2:].map(
        lambda value: calendar.month_abbr[int(value)]
    )
    peak = monthly.loc[monthly["count"].idxmax()]
    top_days = data.tunisia_top_days
    peak_day = top_days.iloc[0]

    st.markdown(
        "<div class='map-context-note'>Tunisia scope · Spark type 0 detections within the Tunisia boundary · 2025. "
        "The daily view contains only the ten highest-count dates; it is not a complete daily time series.</div>",
        unsafe_allow_html=True,
    )
    metrics = st.columns(3, gap="medium")
    metrics[0].metric("Most active month", "{} · {:,.0f}".format(peak["month_label"], peak["count"]))
    metrics[1].metric("Annual detections", "{:,.0f}".format(monthly["count"].sum()))
    metrics[2].metric("Top day", "{} · {:,.0f}".format(peak_day["date"], peak_day["count"]))

    left, right = st.columns([1, 1.1], gap="large")
    with left:
        st.plotly_chart(tunisia_monthly_trend_chart(monthly), use_container_width=True, key="tunisia_monthly_trend_chart")
    with right:
        st.plotly_chart(tunisia_top_days_chart(top_days), use_container_width=True, key="tunisia_top_days_chart")

    display = top_days.rename(
        columns={"date": "Date", "count": "Detections", "max_frp": "Maximum FRP (MW)"}
    )
    st.markdown("<div class='section-heading'>Top 10 detection days</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-note'>Ranked by daily detection count; FRP is the maximum observed value for that day, in megawatts.</div>", unsafe_allow_html=True)
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Detections": st.column_config.NumberColumn(format="%d"),
            "Maximum FRP (MW)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.download_button(
        "Download Tunisia top 10 days as CSV",
        data=display.to_csv(index=False).encode("utf-8"),
        file_name="firewatch_tunisia_top10_days_2025.csv",
        mime="text/csv",
        key="tunisia_trends_download",
    )


if scope == "World | Global Trends":
    _show_world_trends()
elif scope == "Maghreb | Regional Comparison":
    try:
        spark_trends = get_spark_trends_data()
    except DataValidationError as error:
        st.error("Maghreb trend data could not be loaded. {}".format(error))
    else:
        _show_maghreb_trends(spark_trends)
else:
    try:
        spark_trends = get_spark_trends_data()
    except DataValidationError as error:
        st.error("Tunisia trend data could not be loaded. {}".format(error))
    else:
        _show_tunisia_trends(spark_trends)
