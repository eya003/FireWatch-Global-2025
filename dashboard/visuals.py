"""Reusable Plotly charts for the dashboard."""

import calendar

import pandas as pd
import plotly.express as px


CHART_TEMPLATE = "plotly_dark"
ACCENT_ORANGE = "#f97316"
TYPE_COLORS = ["#f97316", "#ef4444", "#f59e0b", "#fb7185"]


def monthly_detections_chart(monthly):
    figure = px.bar(
        monthly,
        x="month_label",
        y="count",
        custom_data=["month"],
        template=CHART_TEMPLATE,
        labels={"month_label": "Month", "count": "Detections", "month": "Year-month"},
        title="Worldwide type 0 detections by month · 2025",
        color_discrete_sequence=[ACCENT_ORANGE],
    )
    figure.update_traces(
        hovertemplate="%{customdata[0]}<br>Detections: %{y:,}<extra></extra>",
        marker_line_width=0,
    )
    figure.update_layout(
        title_x=0.02,
        margin=dict(l=12, r=12, t=55, b=12),
        xaxis=dict(categoryorder="array", categoryarray=monthly["month_label"].tolist()),
        yaxis=dict(title="Detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        showlegend=False,
    )
    return figure


def type_distribution_chart(types):
    chart_data = types.copy()
    chart_data["chart_label"] = chart_data.apply(
        lambda row: "Type {} · {:,} · {:.2%}".format(
            row["type"], row["count"], row["share"]
        ),
        axis=1,
    )
    figure = px.pie(
        chart_data,
        names="chart_label",
        values="count",
        hole=0.62,
        custom_data=["category", "count", "share"],
        color="chart_label",
        color_discrete_sequence=TYPE_COLORS,
        template=CHART_TEMPLATE,
        title="Thermal detections by NASA category",
    )
    figure.update_traces(
        textinfo="none",
        customdata=chart_data[["category", "count", "share"]].to_numpy(),
        hovertemplate="%{customdata[0]}<br>Detections: %{customdata[1]:,}<br>Share: %{customdata[2]:.2%}<extra></extra>",
    )
    figure.update_layout(
        title_x=0.02,
        margin=dict(l=8, r=8, t=55, b=8),
        uniformtext=dict(minsize=10, mode="hide"),
        legend=dict(
            orientation="v",
            x=0.53,
            y=0.5,
            xanchor="left",
            yanchor="middle",
            font=dict(size=10),
            title=dict(text="Type · detections · share"),
        ),
    )
    figure.update_traces(domain=dict(x=[0, 0.5], y=[0, 1]))
    return figure


def world_trends_chart(monthly):
    """Interactive 2025 global series with an upper-quartile activity guide."""
    figure = px.line(
        monthly,
        x="month_label",
        y="count",
        custom_data=["month"],
        template=CHART_TEMPLATE,
        markers=True,
        labels={"month_label": "Month", "count": "Type 0 detections", "month": "Year-month"},
        color_discrete_sequence=[ACCENT_ORANGE],
    )
    figure.update_traces(
        line=dict(width=3),
        marker=dict(size=9, color=ACCENT_ORANGE, line=dict(width=1, color="#fed7aa")),
        hovertemplate="%{customdata[0]}<br>Detections: %{y:,}<extra></extra>",
    )
    threshold = float(monthly["count"].quantile(0.75))
    figure.add_hline(
        y=threshold,
        line_dash="dash",
        line_color="#94a3b8",
        annotation_text="Upper quartile · {:,.0f}".format(threshold),
        annotation_position="top left",
    )
    figure.update_layout(
        title="Monthly global detections · 2025",
        title_x=0.02,
        margin=dict(l=12, r=18, t=60, b=12),
        xaxis=dict(categoryorder="array", categoryarray=monthly["month_label"].tolist()),
        yaxis=dict(title="Type 0 detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        showlegend=False,
    )
    return figure


def monthly_change_chart(changes):
    """Display month-over-month count changes, with direction encoded by color."""
    chart = changes.loc[changes["change"].notna()].copy()
    chart["direction"] = chart["change"].map(lambda value: "Increase" if value >= 0 else "Decrease")
    figure = px.bar(
        chart,
        x="month_label",
        y="change",
        color="direction",
        custom_data=["month", "change_percent"],
        template=CHART_TEMPLATE,
        labels={"month_label": "Month", "change": "Change in detections", "direction": "Direction"},
        color_discrete_map={"Increase": ACCENT_ORANGE, "Decrease": "#64748b"},
    )
    figure.update_traces(
        hovertemplate=(
            "%{customdata[0]}<br>Change: %{y:+,}<br>Change: %{customdata[1]:+.1f}%"
            "<extra></extra>"
        )
    )
    figure.update_layout(
        title="Change from previous month",
        title_x=0.02,
        margin=dict(l=12, r=12, t=55, b=12),
        xaxis=dict(categoryorder="array", categoryarray=chart["month_label"].tolist()),
        yaxis=dict(title="Detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        legend_title_text="",
    )
    return figure


def regional_monthly_chart(monthly, countries):
    """Compare the selected Spark country series on a shared monthly axis."""
    data = monthly.loc[monthly["country"].isin(countries)].copy()
    data["month_label"] = data["year_month"].str[-2:].map(
        lambda value: calendar.month_abbr[int(value)]
    )
    figure = px.line(
        data,
        x="month_label",
        y="count",
        color="country",
        markers=True,
        custom_data=["year_month"],
        template=CHART_TEMPLATE,
        labels={"month_label": "Month", "count": "Detections", "country": "Country", "year_month": "Year-month"},
        color_discrete_sequence=["#f97316", "#38bdf8", "#a78bfa", "#34d399"],
    )
    figure.update_traces(
        hovertemplate="%{customdata[0]}<br>%{fullData.name}: %{y:,}<extra></extra>"
    )
    figure.update_layout(
        title="Monthly detections by country · 2025",
        title_x=0.02,
        margin=dict(l=12, r=12, t=55, b=12),
        xaxis=dict(categoryorder="array", categoryarray=[calendar.month_abbr[m] for m in range(1, 13)]),
        yaxis=dict(title="Type 0 detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        legend_title_text="Country",
    )
    return figure


def country_ranking_chart(comparison):
    data = comparison.sort_values("count", ascending=True)
    figure = px.bar(
        data,
        x="count",
        y="country",
        orientation="h",
        text="count",
        template=CHART_TEMPLATE,
        labels={"count": "2025 detections", "country": "Country"},
        color_discrete_sequence=[ACCENT_ORANGE],
    )
    figure.update_traces(
        texttemplate="%{x:,}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>Detections: %{x:,}<extra></extra>",
    )
    figure.update_layout(
        title="Country ranking · 2025",
        title_x=0.02,
        margin=dict(l=12, r=42, t=55, b=12),
        xaxis=dict(title="Type 0 detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        yaxis=dict(title="", automargin=True),
        showlegend=False,
    )
    return figure


def world_top_countries_chart(countries):
    """Horizontal Top 10 chart for the worldwide top-countries export."""
    data = countries.sort_values(["count", "country"], ascending=[True, True]).copy()
    figure = px.bar(
        data,
        x="count",
        y="country",
        orientation="h",
        text="count",
        template=CHART_TEMPLATE,
        labels={"count": "Type 0 detections", "country": "Country"},
        color_discrete_sequence=[ACCENT_ORANGE],
    )
    figure.update_traces(
        texttemplate="%{x:,}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>Type 0 detections: %{x:,}<extra></extra>",
    )
    figure.update_layout(
        title="Top 10 countries by fire detections · 2025",
        title_x=0.02,
        margin=dict(l=12, r=42, t=55, b=12),
        xaxis=dict(title="Type 0 detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        yaxis=dict(title="", automargin=True),
        showlegend=False,
        height=460,
    )
    return figure


def tunisia_monthly_trend_chart(monthly):
    figure = px.area(
        monthly,
        x="month_label",
        y="count",
        custom_data=["year_month"],
        template=CHART_TEMPLATE,
        labels={"month_label": "Month", "count": "Detections", "year_month": "Year-month"},
        color_discrete_sequence=[ACCENT_ORANGE],
    )
    figure.update_traces(
        line=dict(color=ACCENT_ORANGE, width=3),
        fillcolor="rgba(249,115,22,0.22)",
        hovertemplate="%{customdata[0]}<br>Detections: %{y:,}<extra></extra>",
    )
    figure.update_layout(
        title="Tunisia detections by month · 2025",
        title_x=0.02,
        margin=dict(l=12, r=12, t=55, b=12),
        xaxis=dict(categoryorder="array", categoryarray=monthly["month_label"].tolist()),
        yaxis=dict(title="Type 0 detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        showlegend=False,
    )
    return figure


def tunisia_top_days_chart(top_days):
    data = top_days.sort_values(["count", "date"], ascending=[True, False]).copy()
    data["date_label"] = pd.to_datetime(data["date"]).dt.strftime("%b %d")
    figure = px.bar(
        data,
        x="count",
        y="date_label",
        orientation="h",
        custom_data=["date", "max_frp"],
        template=CHART_TEMPLATE,
        labels={"count": "Detections", "date_label": "Date", "date": "Date", "max_frp": "Maximum FRP (MW)"},
        color_discrete_sequence=[ACCENT_ORANGE],
    )
    figure.update_traces(
        hovertemplate="%{customdata[0]}<br>Detections: %{x:,}<br>Maximum FRP: %{customdata[1]:.2f} MW<extra></extra>"
    )
    figure.update_layout(
        title="Top 10 detection days · Tunisia, 2025",
        title_x=0.02,
        margin=dict(l=12, r=24, t=55, b=12),
        xaxis=dict(title="Detections", gridcolor="rgba(148,163,184,0.12)", tickformat=","),
        yaxis=dict(title="", automargin=True),
        showlegend=False,
    )
    return figure
