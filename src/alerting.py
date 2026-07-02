"""Internal notification generation for detected anomalies.

Notifications remain local text records for v1, matching the project scope
without external integrations like email or Slack.
"""

from __future__ import annotations

from datetime import datetime, UTC

from src.anomaly_detection import severity_from_ratio


def _change_type(anomaly: dict) -> str | None:
    """Classify anomaly change speed when source data has no precomputed label."""
    daily_change = anomaly.get("daily_change")
    if daily_change is None:
        return None

    if float(daily_change) == 0:
        return "NO_SIGNIFICANT_CHANGE"

    if bool(anomaly.get("is_fast_change")):
        return "FAST_CHANGE"

    return "GRADUAL_CHANGE"


def generate_notifications(
    anomalies: list[dict],
    notification_threshold: float = 200.0,
) -> list[dict]:
    """Create local notifications for materially important anomalies."""
    # anomaly detection finds suspicious cases; alerting decides if they matter enough to notify.
    if not anomalies:
        return []
    if notification_threshold < 0:
        raise ValueError("notification_threshold must be >= 0")

    notifications: list[dict] = []

    for anomaly in anomalies:
        actual = float(anomaly.get("actual_value", 0.0) or 0.0)
        baseline = float(anomaly.get("baseline_value", 0.0) or 0.0)
        threshold = float(anomaly.get("threshold_value", 0.0) or 0.0)

        # Only materially relevant anomalies become notifications.
        absolute_difference = actual - baseline
        if absolute_difference <= notification_threshold:
            continue

        severity = anomaly.get("severity") or severity_from_ratio(actual, threshold)
        change_type = anomaly.get("change_type") or _change_type(anomaly)

        notification = {
            "anomaly_ref_key": anomaly.get("anomaly_ref_key"),
            "notification_date": datetime.now(UTC).isoformat(),
            "severity": severity,
            "status": "NEW",
            "daily_change": anomaly.get("daily_change"),
            "average_absolute_change": anomaly.get("average_absolute_change"),
            "change_threshold": anomaly.get("change_threshold"),
            "is_fast_change": anomaly.get("is_fast_change"),
            "change_type": change_type,
            "message": (
                f"Cost anomaly in {anomaly['namespace_name']} ({anomaly['project_name']}/{anomaly['cluster_name']}) "
                f"on {anomaly['cost_date']}: actual={round(actual, 2)}, "
                f"baseline={round(baseline, 2)}, threshold={round(threshold, 2)}, "
                f"daily_change={anomaly.get('daily_change')}, "
                f"change_threshold={anomaly.get('change_threshold')}, "
                f"change_type={change_type}"
            ),
        }
        notifications.append(notification)

    return notifications
