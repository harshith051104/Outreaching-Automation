"""
Dashboard metrics — operational counters.
"""

from __future__ import annotations

import time
from typing import Dict, List

from dashboard.models import DashboardMetrics


class MetricsCollector:
    """In-memory metrics collector for the dashboard subsystem."""

    def __init__(self):
        self._metrics = DashboardMetrics()
        self._api_latencies: List[float] = []
        self._ws_latencies: List[float] = []
        self._start_time = time.time()

    def record_api_request(self, latency_ms: float, is_error: bool = False) -> None:
        self._metrics.api_requests += 1
        if is_error:
            self._metrics.api_errors += 1
        self._api_latencies.append(latency_ms)
        if len(self._api_latencies) > 1000:
            self._api_latencies = self._api_latencies[-500:]

    def record_ws_message(self, latency_ms: float, is_error: bool = False) -> None:
        if is_error:
            self._metrics.ws_messages_failed += 1
        else:
            self._metrics.ws_messages_sent += 1
        self._ws_latencies.append(latency_ms)
        if len(self._ws_latencies) > 1000:
            self._ws_latencies = self._ws_latencies[-500:]

    def record_event_routed(self) -> None:
        self._metrics.events_routed += 1

    def record_notification_pushed(self) -> None:
        self._metrics.notifications_pushed += 1

    def update_ws_connections(self, count: int) -> None:
        self._metrics.ws_connections = count

    def get_metrics(self) -> DashboardMetrics:
        if self._api_latencies:
            self._metrics.avg_api_latency_ms = sum(self._api_latencies) / len(self._api_latencies)
        if self._ws_latencies:
            self._metrics.avg_ws_latency_ms = sum(self._ws_latencies) / len(self._ws_latencies)
        return self._metrics

    def get_dict(self) -> Dict:
        return self.get_metrics().to_dict()

    def reset(self) -> None:
        self._metrics = DashboardMetrics()
        self._api_latencies.clear()
        self._ws_latencies.clear()


# Module-level singleton
metrics_collector = MetricsCollector()
