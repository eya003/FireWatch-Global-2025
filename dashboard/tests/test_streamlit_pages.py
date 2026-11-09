from pathlib import Path

from streamlit.testing.v1 import AppTest

from dashboard import visuals
from dashboard.world_country_data import WORLD_TOP_COUNTRIES_PATH, load_world_top_countries


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_trends_page_plotly_helpers_import_from_dashboard_visuals():
    expected_helpers = (
        "country_ranking_chart",
        "monthly_change_chart",
        "regional_monthly_chart",
        "tunisia_monthly_trend_chart",
        "tunisia_top_days_chart",
        "world_trends_chart",
    )

    assert Path(visuals.__file__).resolve() == APP_PATH.parent / "visuals.py"
    assert all(callable(getattr(visuals, name, None)) for name in expected_helpers)


def test_world_top_countries_renders_on_overview():
    assert WORLD_TOP_COUNTRIES_PATH.exists()
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    assert not app.exception
    assert any("Top 10 Countries by Fire Detections" in item.value for item in app.markdown)
    assert not any("world_top_countries.csv" in item.value for item in app.info)
    assert not any("Most active geographic cells" in item.value for item in app.markdown)


def test_world_top_countries_loader_reports_missing_and_rejects_bad_contract(tmp_path):
    import pandas as pd
    import pytest

    from dashboard.data import DataValidationError

    missing = tmp_path / "world_top_countries.csv"
    with pytest.raises(DataValidationError, match="not available"):
        load_world_top_countries(missing)

    pd.DataFrame(
        {"rank": [1, 2], "country": ["A", "B"], "fire_count": [2, 4]}
    ).to_csv(missing, index=False)
    summary = load_world_top_countries(missing)
    assert summary["country"].tolist() == ["B", "A"]
    assert summary["count"].tolist() == [4, 2]

    pd.DataFrame(
        {"rank": [1, 2], "country": ["A", "A"], "fire_count": [2, 1]}
    ).to_csv(missing, index=False)
    with pytest.raises(DataValidationError, match="duplicate countries"):
        load_world_top_countries(missing)


def test_overview_page_renders_without_streamlit_errors():
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    assert not app.exception
    assert any("Worldwide Fire Detection Overview" in item.value for item in app.markdown)
    assert any("About the Dataset" in item.value for item in app.markdown)


def test_global_fire_map_page_renders_without_streamlit_errors():
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app.switch_page("pages/global_fire_map.py").run()

    assert not app.exception
    assert any("Fire Explorer" in item.value for item in app.markdown)
    assert any("Download filtered cells as CSV" in item.label for item in app.get("download_button"))


def test_fire_explorer_switches_between_world_and_tunisia_modes():
    app = AppTest.from_file(str(APP_PATH), default_timeout=45).run()
    app.switch_page("pages/global_fire_map.py").run()

    assert not app.exception
    assert app.selectbox(key="fire_explorer_scope").value == "World — Annual"
    assert any("World · Annual · 2025" in item.value for item in app.markdown)
    world_ranking = app.selectbox(key="world_annual_ranking")
    assert world_ranking.options == ["Detection Count", "Average FRP"]
    assert world_ranking.value == "count"
    app.multiselect(key="world_annual_countries").set_value(["Tunisia"]).run()
    assert not app.exception
    assert set(app.dataframe[0].value["Country"]) == {"Tunisia"}
    all_countries = app.multiselect(key="world_annual_countries").options
    app.multiselect(key="world_annual_countries").set_value(all_countries).run()
    assert not app.exception
    app.selectbox(key="world_annual_ranking").set_value("count").run()
    assert not app.exception
    world_table = app.dataframe[0].value
    assert world_table["Detections"].is_monotonic_decreasing

    app.selectbox(key="world_annual_ranking").set_value("avg_frp").run()
    assert not app.exception
    assert app.selectbox(key="world_annual_ranking").value == "avg_frp"
    assert app.dataframe[0].value["Avg FRP (MW)"].is_monotonic_decreasing

    app.selectbox(key="world_annual_top_n").set_value(10).run()
    app.number_input(key="world_annual_minimum_count").set_value(1000).run()
    assert not app.exception
    world_filtered = app.dataframe[0].value
    assert len(world_filtered) <= 10
    assert (world_filtered["Detections"] >= 1000).all()
    assert world_filtered["Avg FRP (MW)"].is_monotonic_decreasing
    assert any("Download filtered cells as CSV" in item.label for item in app.get("download_button"))

    app.number_input(key="world_annual_minimum_count").set_value(1_000_000_000).run()
    assert not app.exception
    assert any(
        "No geographic cells match the selected detection threshold." in item.value
        for item in app.info
    )
    app.number_input(key="world_annual_minimum_count").set_value(1000).run()

    app.selectbox(key="fire_explorer_scope").set_value("Tunisia — Monthly").run()
    assert not app.exception
    assert app.selectbox(key="tunisia_month").value == "2025-09"
    assert any("Tunisia · Monthly · 2025-09" in item.value for item in app.markdown)
    assert any("Download filtered cells as CSV" in item.label for item in app.get("download_button"))

    tunisia_ranking = app.selectbox(key="tunisia_monthly_ranking")
    assert tunisia_ranking.options == ["Detection Count", "Average FRP", "Maximum FRP"]
    assert tunisia_ranking.value == "count"
    app.selectbox(key="tunisia_monthly_ranking").set_value("count").run()
    assert not app.exception
    assert app.dataframe[0].value["Detections"].is_monotonic_decreasing

    app.selectbox(key="tunisia_monthly_ranking").set_value("avg_frp").run()
    assert not app.exception
    assert app.dataframe[0].value["Avg FRP (MW)"].is_monotonic_decreasing

    app.selectbox(key="tunisia_monthly_ranking").set_value("max_frp").run()
    assert not app.exception
    assert app.selectbox(key="tunisia_monthly_ranking").value == "max_frp"
    assert app.dataframe[0].value["Max FRP (MW)"].is_monotonic_decreasing

    app.selectbox(key="tunisia_monthly_top_n").set_value(10).run()
    app.number_input(key="tunisia_monthly_minimum_count").set_value(5).run()
    assert not app.exception
    tunisia_filtered = app.dataframe[0].value
    assert len(tunisia_filtered) <= 10
    assert (tunisia_filtered["Detections"] >= 5).all()
    assert tunisia_filtered["Max FRP (MW)"].is_monotonic_decreasing
    app.selectbox(key="fire_explorer_scope").set_value("World — Annual").run()
    assert app.selectbox(key="world_annual_ranking").value == "avg_frp"


def test_trends_insights_page_renders_all_three_scopes():
    app = AppTest.from_file(str(APP_PATH), default_timeout=45).run()
    app.switch_page("pages/trends_insights.py").run()

    assert not app.exception
    assert app.selectbox(key="trends_scope").value == "World | Global Trends"
    assert any("Global activity pattern" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) == 2

    app.selectbox(key="trends_scope").set_value("Maghreb | Regional Comparison").run()
    assert not app.exception
    assert app.multiselect(key="trends_maghreb_countries").value == [
        "Tunisia", "Algeria", "Libya", "Morocco"
    ]
    assert any("Country comparison" in item.value for item in app.markdown)
    assert any(item.label == "Download selected country comparison as CSV" for item in app.get("download_button"))
    assert len(app.get("plotly_chart")) == 2
    app.multiselect(key="trends_maghreb_countries").set_value(["Tunisia", "Morocco"]).run()
    assert not app.exception
    assert app.multiselect(key="trends_maghreb_countries").value == ["Tunisia", "Morocco"]

    app.selectbox(key="trends_scope").set_value("Tunisia | Detailed Trends").run()
    assert not app.exception
    assert any("Top 10 detection days" in item.value for item in app.markdown)
    assert any(item.label == "Download Tunisia top 10 days as CSV" for item in app.get("download_button"))
    assert len(app.get("plotly_chart")) == 2


def test_live_monitoring_is_explicitly_disconnected_without_alert_data(monkeypatch):
    monkeypatch.setenv("FIREWATCH_LIVE_SOURCE", "off")
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app.switch_page("pages/live_monitoring.py").run()

    assert not app.exception
    assert any("Data source not connected" in item.value for item in app.warning)
    assert any("Kafka, Spark Streaming, and HBase are not connected" in item.value for item in app.markdown)
    assert any("Recent alerts will appear after the HBase reader is connected." in item.value for item in app.info)
    assert len(app.dataframe) == 0
    assert len(app.get("plotly_chart")) == 0


def test_live_monitoring_renders_recorded_replay_snapshot(monkeypatch):
    monkeypatch.setenv("FIREWATCH_LIVE_SOURCE", "snapshot")
    app = AppTest.from_file(str(APP_PATH), default_timeout=45).run()
    app.switch_page("pages/live_monitoring.py").run()

    assert not app.exception
    assert app.selectbox(key="live_source").value == "Recorded replay (snapshot)"
    assert any("Recorded replay" in item.value for item in app.markdown)
    assert any(">70<" in item.value for item in app.markdown)
    assert len(app.dataframe) == 1
    assert len(app.dataframe[0].value) == 15
    assert app.selectbox(key="live_context_zone").value == "36.5_9.0"
    assert len(app.get("plotly_chart")) == 2
