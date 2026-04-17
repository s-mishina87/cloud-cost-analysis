"""Anomaly detection using the confirmed v1 method.

Current method: moving average baseline with multiplicative threshold.
No second anomaly method is implemented at this stage.
"""

from __future__ import annotations

def detect_anomalies(
    records: list[dict],
    window_size: int = 7,
    deviation_factor: float = 1.5,
) -> list[dict]:
    """Detect anomalies on NamespaceCost.total_cost using moving average."""
    if not records or window_size <= 0:
        return []

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
            moving_average = sum(float(item.get("total_cost", 0.0) or 0.0) for item in history) / window_size
            threshold = moving_average * deviation_factor
            actual_value = float(sorted_rows[index].get("total_cost", 0.0) or 0.0)

            if actual_value > threshold:
                source = sorted_rows[index]
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
                    # Kept for beginner visibility and test readability.
                    "moving_average": round(moving_average, 2),
                    "threshold": round(threshold, 2),
                }
                anomalies.append(anomaly)

    return anomalies
