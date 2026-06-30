"""Comparison-only anomaly detection using a rolling standard deviation threshold."""

from __future__ import annotations

from math import sqrt

from src.anomaly_detection import severity_from_ratio


def _total_cost(row: dict) -> float:
    """Return total_cost as a float with a safe default."""
    return float(row.get("total_cost", 0.0) or 0.0)


def _average_absolute_change(rows: list[dict]) -> float:
    """Return the average size of recent day-to-day changes."""
    if len(rows) < 2:
        return 0.0

    absolute_changes = [
        abs(_total_cost(rows[index]) - _total_cost(rows[index - 1])) for index in range(1, len(rows))
    ]
    return sum(absolute_changes) / len(absolute_changes)


def _rolling_stddev(rows: list[dict], average: float) -> float:
    """Return population standard deviation for the rolling history window."""
    if not rows:
        return 0.0

    variance = sum((_total_cost(row) - average) ** 2 for row in rows) / len(rows)
    return sqrt(variance)


def _group_records(records: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    """Group records by namespace identity."""
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in records:
        namespace_key = (row["project_name"], row["cluster_name"], row["namespace_name"])
        grouped.setdefault(namespace_key, []).append(row)
    return grouped


def calculate_rolling_stddev_summary(records: list[dict], window_size: int = 7) -> dict:
    """Summarize rolling standard deviations for comparison output."""
    if not records:
        return {
            "average_stddev_per_namespace": 0.0,
            "minimum_stddev": 0.0,
            "maximum_stddev": 0.0,
        }
    if window_size <= 0:
        raise ValueError("window_size must be > 0")

    namespace_averages: list[float] = []
    all_stddevs: list[float] = []

    for _, namespace_rows in _group_records(records).items():
        sorted_rows = sorted(namespace_rows, key=lambda item: item["cost_date"])
        namespace_stddevs: list[float] = []

        for index in range(window_size, len(sorted_rows)):
            history = sorted_rows[index - window_size : index]
            rolling_average = sum(_total_cost(item) for item in history) / window_size
            rolling_stddev = _rolling_stddev(history, rolling_average)
            namespace_stddevs.append(rolling_stddev)
            all_stddevs.append(rolling_stddev)

        if namespace_stddevs:
            namespace_averages.append(sum(namespace_stddevs) / len(namespace_stddevs))

    if not all_stddevs:
        return {
            "average_stddev_per_namespace": 0.0,
            "minimum_stddev": 0.0,
            "maximum_stddev": 0.0,
        }

    return {
        "average_stddev_per_namespace": round(sum(namespace_averages) / len(namespace_averages), 2),
        "minimum_stddev": round(min(all_stddevs), 2),
        "maximum_stddev": round(max(all_stddevs), 2),
    }


def calculate_namespace_rolling_stddev_details(
    records: list[dict],
    window_size: int = 7,
    stddev_factor: float = 2.0,
    limit: int = 20,
) -> list[dict]:
    """Return per-namespace rolling standard deviation details for comparison output."""
    if not records:
        return []
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if stddev_factor <= 0:
        raise ValueError("stddev_factor must be > 0")
    if limit <= 0:
        raise ValueError("limit must be > 0")

    namespace_details: list[dict] = []

    for namespace_key, namespace_rows in _group_records(records).items():
        sorted_rows = sorted(namespace_rows, key=lambda item: item["cost_date"])
        namespace_stddevs: list[float] = []

        for index in range(window_size, len(sorted_rows)):
            history = sorted_rows[index - window_size : index]
            rolling_average = sum(_total_cost(item) for item in history) / window_size
            namespace_stddevs.append(_rolling_stddev(history, rolling_average))

        if not namespace_stddevs:
            continue

        project_name, cluster_name, namespace_name = namespace_key
        latest_history = sorted_rows[-window_size - 1 : -1]
        latest_actual = _total_cost(sorted_rows[-1])
        latest_rolling_mean = sum(_total_cost(item) for item in latest_history) / window_size
        latest_rolling_stddev = _rolling_stddev(latest_history, latest_rolling_mean)
        latest_threshold = latest_rolling_mean + (latest_rolling_stddev * stddev_factor)
        namespace_details.append(
            {
                "project_name": project_name,
                "cluster_name": cluster_name,
                "namespace_name": namespace_name,
                "rolling_mean": round(latest_rolling_mean, 2),
                "rolling_stddev": round(latest_rolling_stddev, 2),
                "threshold": round(latest_threshold, 2),
                "actual_value": round(latest_actual, 2),
                "actual_minus_threshold": round(latest_actual - latest_threshold, 2),
                "average_stddev": round(sum(namespace_stddevs) / len(namespace_stddevs), 2),
                "minimum_stddev": round(min(namespace_stddevs), 2),
                "maximum_stddev": round(max(namespace_stddevs), 2),
                "window_count": len(namespace_stddevs),
            }
        )

    return sorted(namespace_details, key=lambda item: item["average_stddev"], reverse=True)[:limit]


def detect_anomalies_rolling_stddev(
    records: list[dict],
    window_size: int = 7,
    stddev_factor: float = 2.0,
    change_factor: float = 2.0,
) -> list[dict]:
    """Detect anomalies using rolling mean plus rolling standard deviation."""
    if not records:
        return []
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if stddev_factor <= 0:
        raise ValueError("stddev_factor must be > 0")
    if change_factor <= 0:
        raise ValueError("change_factor must be > 0")

    anomalies: list[dict] = []

    for _, namespace_rows in _group_records(records).items():
        sorted_rows = sorted(namespace_rows, key=lambda item: item["cost_date"])

        for index in range(window_size, len(sorted_rows)):
            history = sorted_rows[index - window_size : index]
            rolling_average = sum(_total_cost(item) for item in history) / window_size
            rolling_stddev = _rolling_stddev(history, rolling_average)
            threshold = rolling_average + (rolling_stddev * stddev_factor)
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
                    f"{source['cluster_name']}|{source['namespace_name']}|rolling_stddev_threshold"
                )
                anomaly = {
                    "cost_date": source["cost_date"],
                    "project_name": source["project_name"],
                    "cluster_name": source["cluster_name"],
                    "namespace_name": source["namespace_name"],
                    "anomaly_ref_key": anomaly_ref_key,
                    "method": "rolling_stddev_threshold",
                    "actual_value": round(actual_value, 2),
                    "baseline_value": round(rolling_average, 2),
                    "threshold_value": round(threshold, 2),
                    "severity": severity_from_ratio(actual_value, threshold),
                    "is_anomaly": 1,
                    "daily_change": round(daily_change, 2),
                    "average_absolute_change": round(average_absolute_change, 2),
                    "change_threshold": round(change_threshold, 2),
                    "is_fast_change": is_fast_change,
                    "rolling_average": round(rolling_average, 2),
                    "rolling_stddev": round(rolling_stddev, 2),
                    "threshold": round(threshold, 2),
                }
                anomalies.append(anomaly)

    return anomalies
