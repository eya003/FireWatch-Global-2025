import subprocess

import pandas as pd

from dashboard import live_data
from dashboard.live_data import (
    DockerAlertReader,
    SnapshotAlertReader,
    get_live_monitoring_reader,
    parse_alert_lines,
)


def test_parse_alert_lines_maps_module_c_contract_and_skips_bad_lines():
    lines = [
        "36.5_9.0,2025-10-16,1252,36.50188,9.05777,57.17,n",
        "36.0_9.5,2025-10-11,1206,36.25912,9.80654,432.32,h",
        "broken line",
        "36.0_9.5,2025-10-11,xx,36.2,9.8,12,n",
        "",
    ]
    alerts = parse_alert_lines(lines)

    assert len(alerts) == 2
    assert set(live_data.LIVE_ALERT_COLUMNS) <= set(alerts.columns)
    assert alerts.loc[0, "alert_id"] == "36.5_9.0#2025-10-16#1252"
    assert alerts.loc[0, "timestamp"] == pd.Timestamp("2025-10-16 12:52", tz="UTC")
    assert alerts["country"].eq("Tunisia").all()
    assert alerts["frp_mw"].tolist() == [57.17, 432.32]


def test_parse_alert_lines_returns_empty_schema_without_data():
    alerts = parse_alert_lines([])
    assert alerts.empty
    assert set(live_data.LIVE_ALERT_COLUMNS) <= set(alerts.columns)


def test_snapshot_contains_the_70_validated_alerts():
    alerts = SnapshotAlertReader().read_alerts(limit=0)

    assert len(alerts) == 70
    assert alerts["zone"].nunique() == 10
    assert alerts["zone"].value_counts().idxmax() == "36.5_9.0"
    assert alerts["frp_mw"].max() == 432.32
    assert (alerts["latitude"] >= 35.5).all()
    assert (alerts["frp_mw"] >= 20).all()
    assert not alerts["confidence"].eq("l").any()


def test_docker_reader_is_unavailable_without_docker(monkeypatch):
    def missing_docker(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", missing_docker)
    assert DockerAlertReader().is_available() is False
    assert isinstance(get_live_monitoring_reader("auto"), SnapshotAlertReader)
    assert get_live_monitoring_reader("docker") is None
    assert get_live_monitoring_reader("off") is None


def test_docker_reader_parses_services_and_hdfs_alerts(monkeypatch):
    ps_output = "\n".join([
        "java ... org.apache.hadoop.hdfs.server.namenode.NameNode",
        "java ... org.apache.zookeeper.server.quorum.QuorumPeerMain config",
        "java ... kafka.Kafka config/server.properties",
        "java ... org.apache.hadoop.hbase.master.HMaster start",
        "java ... org.apache.hadoop.hbase.regionserver.HRegionServer start",
    ])

    def fake_run(args, **kwargs):
        command = args[-1]
        if args[1] == "inspect":
            stdout = "true\n"
        elif command.startswith("ps"):
            stdout = ps_output
        else:
            stdout = "36.5_9.0,2025-10-16,1252,36.50188,9.05777,57.17,n\n"
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    reader = DockerAlertReader()

    assert reader.is_available()
    assert reader.pipeline_status() == "ready"
    assert reader.services()["Spark Streaming"] is False
    assert len(reader.read_alerts()) == 1


def test_live_page_pauses_refresh_when_streaming_stops(monkeypatch):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    state = {"spark": True}

    def fake_run(args, **kwargs):
        command = args[-1]
        if args[1] == "inspect":
            stdout = "true\n"
        elif command.startswith("ps"):
            names = ["namenode.NameNode", "QuorumPeerMain", "kafka.Kafka", "hbase.master.HMaster",
                     "regionserver.HRegionServer"]
            if state["spark"]:
                names.append("org.apache.spark.deploy.SparkSubmit")
            stdout = "\n".join(names)
        else:
            stdout = "36.5_9.0,2025-10-16,1252,36.50188,9.05777,57.17,n\n"
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("FIREWATCH_LIVE_SOURCE", "docker")
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=45).run()
    app.switch_page("pages/live_monitoring.py").run()

    assert not app.exception
    assert app.selectbox(key="live_source").value == "Live cluster (Docker)"
    assert app.session_state["live_seen_streaming"] is True
    assert any(button.label == "Pause refresh" for button in app.button)

    state["spark"] = False  # end of the demo: Spark Streaming stops
    app.run()

    assert not app.exception
    assert app.session_state["live_auto_refresh"] is False
    assert any(button.label == "Resume refresh" for button in app.button)
    assert any("Streaming finished" in caption.value for caption in app.caption)
