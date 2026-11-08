"""Connection point for a future Module C live-alert reader."""

from typing import Protocol

import pandas as pd


LIVE_ALERT_COLUMNS = (
    "alert_id",
    "timestamp",
    "latitude",
    "longitude",
    "country",
    "frp_mw",
)


class LiveMonitoringReader(Protocol):
    """Interface expected from a future service that reads real HBase alerts."""

    def pipeline_status(self) -> str:
        """Return the reader's observed pipeline state."""

    def read_alerts(self, limit: int = 100) -> pd.DataFrame:
        """Return recent real alerts using LIVE_ALERT_COLUMNS."""


def get_live_monitoring_reader() -> LiveMonitoringReader | None:
    """No Module C adapter is configured in the dashboard yet."""
    return None
