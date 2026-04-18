from __future__ import annotations

from prometheus_client import Counter, Histogram

arbitrations_total = Counter(
    "saalis_arbitrations_total",
    "Total arbitrations processed",
    ["strategy", "status"],
)

arbitration_duration = Histogram(
    "saalis_arbitration_duration_seconds",
    "Arbitration duration in seconds",
)

audit_append_failures_total = Counter(
    "saalis_audit_append_failures_total",
    "Total audit append failures",
)


def record_arbitration(strategy: str, status: str, duration: float) -> None:
    arbitrations_total.labels(strategy=strategy, status=status).inc()
    arbitration_duration.observe(duration)
