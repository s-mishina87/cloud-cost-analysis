"""Create notifications from detected anomalies."""

from datetime import datetime, UTC

from src.anomaly_detection import severity_from_ratio


def generate_notifications(anomalies, notification_threshold: float = 200.0):
    """Create notifications for anomalies that are important enough."""
    if not anomalies:
        return []
    if notification_threshold < 0:
        raise ValueError("notification_threshold must be >= 0")

    notifications = []
    for anomaly in anomalies:
        actual = float(anomaly.get("actual_value") or 0.0)
        mov_avg = float(anomaly.get("moving_average") or 0.0)
        thr = float(anomaly.get("threshold_value") or 0.0)

        if actual - mov_avg <= notification_threshold:
            continue

        sev = anomaly.get("severity") or severity_from_ratio(actual, thr)
        chg_type = anomaly.get("change_type")

        notifications.append({
            "anomaly_ref_key": anomaly.get("anomaly_ref_key"),
            "notification_date": datetime.now(UTC).isoformat(),
            "severity": sev,
            "status": "NEW",
            "daily_change": anomaly.get("daily_change"),
            "average_absolute_change": anomaly.get("average_absolute_change"),
            "change_threshold": anomaly.get("change_threshold"),
            "is_fast_change": anomaly.get("is_fast_change"),
            "change_type": chg_type,
            "message": (
                f"Cost anomaly in {anomaly['namespace_name']} ({anomaly['project_name']}/{anomaly['cluster_name']}) "
                f"on {anomaly['cost_date']}: actual={round(actual, 2)}, "
                f"moving_average={round(mov_avg, 2)}, threshold={round(thr, 2)}, "
                f"daily_change={anomaly.get('daily_change')}, "
                f"change_threshold={anomaly.get('change_threshold')}, "
                f"change_type={chg_type}"
            ),
        })

    return notifications
