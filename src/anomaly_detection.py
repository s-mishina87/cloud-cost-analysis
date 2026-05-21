"""Anomaly detection using the confirmed v1 method.

Current method: moving average baseline with multiplicative threshold.
Change-rate metadata is added on top so anomalies also show how quickly
costs moved from one day to the next.
"""

from __future__ import annotations


def _total_cost(row: dict) -> float:
    """Return total_cost as a float with a safe default."""
    return float(row.get("total_cost", 0.0) or 0.0)


def _average_absolute_change(rows: list[dict]) -> float:
    """Return the average size of recent day-to-day changes.

    Uses absolute differences so rises and drops do not cancel each other out.
    """
    if len(rows) < 2:
        return 0.0

    absolute_changes = [
        abs(_total_cost(rows[index]) - _total_cost(rows[index - 1])) for index in range(1, len(rows))
    ]
    return sum(absolute_changes) / len(absolute_changes)


def detect_anomalies(
    records: list[dict],
    window_size: int = 7,
    deviation_factor: float = 1.5,
    change_factor: float = 2.0,
) -> list[dict]:
    """Detect anomalies using a moving average plus change-rate metadata."""
    if not records:
        return []
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if change_factor <= 0:
        raise ValueError("change_factor must be > 0")

    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in records:
        namespace_key = (row["project_name"], row["cluster_name"], row["namespace_name"])
        grouped.setdefault(namespace_key, []).append(row)

    anomalies: list[dict] = []

    # Evaluate each namespace as an independent daily time series.
    for _, namespace_rows in grouped.items():
        sorted_rows = sorted(namespace_rows, key=lambda item: item["cost_date"])

        for index in range(window_size, len(sorted_rows)):
            history = sorted_rows[index - window_size : index]
            moving_average = sum(_total_cost(item) for item in history) / window_size
            threshold = moving_average * deviation_factor
            actual_value = _total_cost(sorted_rows[index])

            if actual_value > threshold:
                source = sorted_rows[index]
                previous_value = _total_cost(sorted_rows[index - 1])
                daily_change = actual_value - previous_value
                average_absolute_change = _average_absolute_change(history)
                change_threshold = average_absolute_change * change_factor
                is_fast_change = abs(daily_change) > change_threshold
                anomaly_ref_key = (
                    f"{source['cost_date']}|{source['project_name']}|"
                    f"{source['cluster_name']}|{source['namespace_name']}|moving_average_threshold"
                )
                anomaly = {
                    "cost_date": source["cost_date"],
                    "project_name": source["project_name"],
                    "cluster_name": source["cluster_name"],
                    "namespace_name": source["namespace_name"],
                    "anomaly_ref_key": anomaly_ref_key,
                    "method": "moving_average_threshold",
                    "actual_value": round(actual_value, 2),
                    "baseline_value": round(moving_average, 2),
                    "threshold_value": round(threshold, 2),
                    "is_anomaly": 1,
                    # daily_change = current cost - previous day's cost.
                    "daily_change": round(daily_change, 2),
                    # average_absolute_change = normal recent change size.
                    "average_absolute_change": round(average_absolute_change, 2),
                    "change_threshold": round(change_threshold, 2),
                    "is_fast_change": is_fast_change,
                    # Kept for beginner visibility and test readability.
                    "moving_average": round(moving_average, 2),
                    "threshold": round(threshold, 2),
                }
                anomalies.append(anomaly)

    return anomalies
