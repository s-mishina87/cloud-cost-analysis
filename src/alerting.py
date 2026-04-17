"""Internal notification generation for detected anomalies.

Notifications remain local text records for v1, matching the project scope
without external integrations like email or Slack.
"""

from __future__ import annotations

from datetime import datetime, UTC


def _severity_from_ratio(actual_value: float, threshold_value: float) -> str:
    """Classify anomaly severity using a simple ratio for beginner readability."""
    if threshold_value <= 0:
        return "MEDIUM"

    ratio = actual_value / threshold_value
    if ratio >= 2.0:
        return "HIGH"
    if ratio >= 1.3:
        return "MEDIUM"
    return "LOW"


def generate_notifications(anomalies: list[dict]) -> list[dict]:
    """Create Notification records for anomalies flagged by detection logic."""
    notifications: list[dict] = []

    for anomaly in anomalies:
        actual = float(anomaly.get("actual_value", 0.0) or 0.0)
        baseline = float(anomaly.get("baseline_value", 0.0) or 0.0)
        threshold = float(anomaly.get("threshold_value", 0.0) or 0.0)

        notification = {
            "anomaly_ref_key": anomaly.get("anomaly_ref_key"),
            "notification_date": datetime.now(UTC).isoformat(),
            "severity": _severity_from_ratio(actual, threshold),
            "status": "NEW",
            "message": (
                f"Cost anomaly in {anomaly['namespace_name']} ({anomaly['project_name']}/{anomaly['cluster_name']}) "
                f"on {anomaly['cost_date']}: actual={actual}, baseline={baseline}, threshold={round(threshold, 2)}"
            ),
        }
        notifications.append(notification)

    return notifications
