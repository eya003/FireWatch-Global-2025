"""Module C readers for the Live Monitoring page.

Two real sources are supported:

* ``DockerAlertReader`` reads the alerts that Spark Streaming writes to HDFS
  (``/fires/stream/alerts``) inside the ``hadoop-master`` container, through
  ``docker exec``. It also inspects the running services and can query HBase.
* ``SnapshotAlertReader`` reads ``module_C_streaming_hbase/exports/alerts_snapshot.csv``,
  a recorded output of the same pipeline (replay of the real 2025 Tunisia
  detections). It is a clearly labelled fallback when the cluster is not running.

The source is chosen with the ``FIREWATCH_LIVE_SOURCE`` environment variable:
``auto`` (default), ``docker``, ``snapshot`` or ``off``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable, Protocol

import pandas as pd

from dashboard.data import PROJECT_ROOT


LIVE_ALERT_COLUMNS = (
    "alert_id",
    "timestamp",
    "latitude",
    "longitude",
    "country",
    "frp_mw",
)
# Module C alert contract (one CSV line per alert, without header).
MODULE_C_ALERT_FIELDS = ("zone", "acq_date", "acq_time", "latitude", "longitude", "frp", "confidence")
EXTRA_ALERT_COLUMNS = ("zone", "confidence", "acq_date", "acq_time")
ALERT_FRP_THRESHOLD_MW = 20.0

DEFAULT_CONTAINER = os.environ.get("FIREWATCH_CONTAINER", "hadoop-master")
HDFS_ALERTS_GLOB = "/fires/stream/alerts/*/part-*"
SNAPSHOT_PATH = PROJECT_ROOT / "module_C_streaming_hbase" / "exports" / "alerts_snapshot.csv"

# Process signatures (Java main classes) checked inside the container.
SERVICE_SIGNATURES = {
    "HDFS NameNode": "namenode.NameNode",
    "ZooKeeper": "QuorumPeerMain",
    "Kafka": "kafka.Kafka",
    "Spark Streaming": "org.apache.spark.deploy.SparkSubmit",
    "HBase Master": "hbase.master.HMaster",
    "HBase RegionServer": "regionserver.HRegionServer",
}
CORE_SERVICES = ("HDFS NameNode", "ZooKeeper", "Kafka", "HBase Master", "HBase RegionServer")

HBASE_CHECK_COMMANDS = "count 'fire_alerts'\nget 'fire_monthly', '2025-09'\nexit\n"


class ReaderUnavailable(RuntimeError):
    """Raised when the configured live source cannot be reached."""


class LiveMonitoringReader(Protocol):
    """Interface expected by the Live Monitoring page."""

    label: str
    is_live: bool

    def pipeline_status(self) -> str:
        """Return the reader's observed pipeline state."""

    def read_alerts(self, limit: int = 100) -> pd.DataFrame:
        """Return recent real alerts using LIVE_ALERT_COLUMNS (+ EXTRA_ALERT_COLUMNS)."""


def empty_alerts() -> pd.DataFrame:
    columns = list(LIVE_ALERT_COLUMNS) + list(EXTRA_ALERT_COLUMNS)
    return pd.DataFrame({column: pd.Series(dtype="object") for column in columns})


def parse_alert_lines(lines: Iterable[str]) -> pd.DataFrame:
    """Convert Module C alert lines into the dashboard alert schema.

    Malformed lines are skipped. The most recent alerts come first.
    """
    records = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("zone,"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != len(MODULE_C_ALERT_FIELDS):
            continue
        zone, acq_date, acq_time, latitude, longitude, frp, confidence = parts
        try:
            timestamp = pd.to_datetime(
                acq_date + " " + acq_time.zfill(4), format="%Y-%m-%d %H%M", utc=True
            )
            record = {
                "alert_id": "{}#{}#{}".format(zone, acq_date, acq_time.zfill(4)),
                "timestamp": timestamp,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "country": "Tunisia",
                "frp_mw": float(frp),
                "zone": zone,
                "confidence": confidence,
                "acq_date": acq_date,
                "acq_time": acq_time.zfill(4),
            }
        except (TypeError, ValueError):
            continue
        records.append(record)

    if not records:
        return empty_alerts()
    frame = pd.DataFrame.from_records(records)
    return frame.sort_values(["timestamp", "frp_mw"], ascending=[False, False]).reset_index(drop=True)


class DockerAlertReader:
    """Reads Module C outputs from the running hadoop-master container."""

    label = "Live cluster · hadoop-master (Docker)"
    is_live = True

    def __init__(self, container: str = DEFAULT_CONTAINER, timeout: int = 20) -> None:
        self.container = container
        self.timeout = timeout

    def _run(self, args: list[str], stdin: str | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                args,
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout or self.timeout,
            )
        except FileNotFoundError as error:
            raise ReaderUnavailable("The 'docker' command was not found on this computer.") from error
        except subprocess.TimeoutExpired as error:
            raise ReaderUnavailable("The container did not answer in time.") from error

    def _exec(self, command: str, stdin: str | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
        return self._run(
            ["docker", "exec", "-i", self.container, "bash", "-lc", command],
            stdin=stdin,
            timeout=timeout,
        )

    def is_available(self) -> bool:
        try:
            result = self._run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self.container], timeout=8
            )
        except ReaderUnavailable:
            return False
        return result.returncode == 0 and result.stdout.strip() == "true"

    def services(self) -> dict[str, bool]:
        result = self._exec("ps -eo args", timeout=10)
        if result.returncode != 0:
            raise ReaderUnavailable("Could not list the processes of the container.")
        processes = result.stdout
        return {name: signature in processes for name, signature in SERVICE_SIGNATURES.items()}

    def pipeline_status(self) -> str:
        services = self.services()
        if not all(services[name] for name in CORE_SERVICES):
            return "degraded"
        return "streaming" if services["Spark Streaming"] else "ready"

    def read_alerts(self, limit: int = 100) -> pd.DataFrame:
        result = self._exec("hdfs dfs -cat {} 2>/dev/null".format(HDFS_ALERTS_GLOB), timeout=40)
        # A non-zero code with no output simply means that no alert was written yet.
        frame = parse_alert_lines(result.stdout.splitlines())
        return frame.head(limit) if limit else frame

    def hbase_check(self) -> str:
        result = self._exec("hbase shell 2>/dev/null", stdin=HBASE_CHECK_COMMANDS, timeout=90)
        lines = [
            line for line in result.stdout.splitlines()
            if line.strip()
            and not line.startswith(("SLF4J", "HBase Shell", "Use \"", "Version ", "hbase(main)", "["))
        ]
        if not lines:
            raise ReaderUnavailable("HBase did not return any result.")
        return "\n".join(lines)


class SnapshotAlertReader:
    """Reads the recorded output of the streaming pipeline (replay of 2025)."""

    label = "Recorded replay · real 2025 detections (snapshot)"
    is_live = False

    def __init__(self, path: Path | str = SNAPSHOT_PATH) -> None:
        self.path = Path(path)

    def is_available(self) -> bool:
        return self.path.is_file()

    def pipeline_status(self) -> str:
        return "snapshot"

    def read_alerts(self, limit: int = 100) -> pd.DataFrame:
        if not self.path.is_file():
            raise ReaderUnavailable("Snapshot file not found: {}".format(self.path))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        frame = parse_alert_lines(lines)
        return frame.head(limit) if limit else frame


def get_live_monitoring_reader(source: str | None = None) -> LiveMonitoringReader | None:
    """Return the configured reader, or None when no source is available."""
    source = (source or os.environ.get("FIREWATCH_LIVE_SOURCE", "auto")).strip().lower()
    if source == "off":
        return None
    if source in ("auto", "docker"):
        docker_reader = DockerAlertReader()
        if docker_reader.is_available():
            return docker_reader
        if source == "docker":
            return None
    if source in ("auto", "snapshot"):
        snapshot_reader = SnapshotAlertReader()
        if snapshot_reader.is_available():
            return snapshot_reader
    return None
