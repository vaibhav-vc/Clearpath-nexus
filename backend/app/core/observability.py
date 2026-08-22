from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        return
    for handler in root.handlers:
        handler.setFormatter(JsonFormatter())


class ProviderStatusRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Any]] = {}

    def record_success(self, provider: str) -> None:
        self._providers[provider] = {
            "status": "available",
            "last_success_at": datetime.now(timezone.utc).isoformat(),
            "last_failure_at": self._providers.get(provider, {}).get("last_failure_at"),
        }

    def record_failure(self, provider: str) -> None:
        self._providers[provider] = {
            "status": "unavailable",
            "last_success_at": self._providers.get(provider, {}).get("last_success_at"),
            "last_failure_at": datetime.now(timezone.utc).isoformat(),
        }

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return self._providers.copy()


class MetricsRegistry:
    def __init__(self) -> None:
        self._request_counts: dict[tuple[str, str, int], int] = {}
        self._request_duration_sum: dict[tuple[str, str], float] = {}
        self._request_duration_count: dict[tuple[str, str], int] = {}
        self._route_evaluations_total: int = 0
        self._clearance_blocks_total: int = 0
        self._prediction_requests_total: int = 0
        self._prediction_fallback_total: int = 0
        self._prediction_errors_total: int = 0
        self._prediction_latency_sum: float = 0.0
        self._active_model_version: str = "deterministic"

    def record_request(
        self, method: str, path_group: str, status_code: int, duration_sec: float
    ) -> None:
        key = (method, path_group, status_code)
        self._request_counts[key] = self._request_counts.get(key, 0) + 1

        dur_key = (method, path_group)
        self._request_duration_sum[dur_key] = (
            self._request_duration_sum.get(dur_key, 0.0) + duration_sec
        )
        self._request_duration_count[dur_key] = self._request_duration_count.get(dur_key, 0) + 1

    def record_route_evaluation(self, blocked: bool = False) -> None:
        self._route_evaluations_total += 1
        if blocked:
            self._clearance_blocks_total += 1

    def record_prediction(
        self, latency_sec: float, fallback: bool, error: bool, model_version: str
    ) -> None:
        self._prediction_requests_total += 1
        self._prediction_latency_sum += latency_sec
        self._prediction_fallback_total += int(fallback)
        self._prediction_errors_total += int(error)
        self._active_model_version = model_version

    def export_prometheus_text(self) -> str:
        lines: list[str] = [
            "# HELP nexus_http_requests_total Total number of HTTP requests processed.",
            "# TYPE nexus_http_requests_total counter",
        ]
        for (method, path_group, code), count in self._request_counts.items():
            lines.append(
                f'nexus_http_requests_total{{method="{method}",path="{path_group}",status="{code}"}} {count}'
            )

        lines.extend(
            [
                "# HELP nexus_http_request_duration_seconds Total time spent processing HTTP requests in seconds.",
                "# TYPE nexus_http_request_duration_seconds summary",
            ]
        )
        for (method, path_group), sum_val in self._request_duration_sum.items():
            count_val = self._request_duration_count.get((method, path_group), 1)
            lines.append(
                f'nexus_http_request_duration_seconds_sum{{method="{method}",path="{path_group}"}} {sum_val:.4f}'
            )
            lines.append(
                f'nexus_http_request_duration_seconds_count{{method="{method}",path="{path_group}"}} {count_val}'
            )

        lines.extend(
            [
                "# HELP nexus_route_evaluations_total Total cargo route evaluations conducted.",
                "# TYPE nexus_route_evaluations_total counter",
                f"nexus_route_evaluations_total {self._route_evaluations_total}",
                "# HELP nexus_clearance_blocks_total Total cargo routes rejected due to physical clearance violations.",
                "# TYPE nexus_clearance_blocks_total counter",
                f"nexus_clearance_blocks_total {self._clearance_blocks_total}",
                "# HELP nexus_provider_available Operational status of integrated external providers (1=available, 0=unavailable).",
                "# TYPE nexus_provider_available gauge",
            ]
        )
        for provider_name, status_dict in provider_status.snapshot().items():
            val = 1 if status_dict.get("status") == "available" else 0
            lines.append(f'nexus_provider_available{{provider="{provider_name}"}} {val}')

        lines.extend(
            [
                "# HELP nexus_ml_prediction_requests_total Delay prediction requests.",
                "# TYPE nexus_ml_prediction_requests_total counter",
                f"nexus_ml_prediction_requests_total {self._prediction_requests_total}",
                "# HELP nexus_ml_prediction_fallback_total Deterministic fallback count.",
                "# TYPE nexus_ml_prediction_fallback_total counter",
                f"nexus_ml_prediction_fallback_total {self._prediction_fallback_total}",
                "# HELP nexus_ml_prediction_errors_total Prediction errors.",
                "# TYPE nexus_ml_prediction_errors_total counter",
                f"nexus_ml_prediction_errors_total {self._prediction_errors_total}",
                "# HELP nexus_ml_prediction_latency_seconds_sum Total prediction latency.",
                "# TYPE nexus_ml_prediction_latency_seconds_sum counter",
                f"nexus_ml_prediction_latency_seconds_sum {self._prediction_latency_sum:.6f}",
                "# HELP nexus_ml_active_model_info Active model version.",
                "# TYPE nexus_ml_active_model_info gauge",
                f'nexus_ml_active_model_info{{version="{self._active_model_version}"}} 1',
            ]
        )

        return "\n".join(lines) + "\n"


provider_status = ProviderStatusRegistry()

metrics_registry = MetricsRegistry()


def request_duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)
