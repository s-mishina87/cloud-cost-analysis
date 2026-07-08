import pytest

from src.alerting import generate_notifications


def test_generate_notifications_keeps_anomaly_reference_key():
    anomalies = [
        {
            "anomaly_ref_key": "2026-01-08|retail-prod|cluster-eu-west-1|payments|moving_average_threshold",
            "cost_date": "2026-01-08",
            "project_name": "retail-prod",
            "cluster_name": "cluster-eu-west-1",
            "namespace_name": "payments",
            "actual_value": 160.0,
            "moving_average": 100.0,
            "threshold_value": 120.0,
            "is_anomaly": 1,
        }
    ]

    notifications = generate_notifications(anomalies, notification_threshold=50.0)

    assert len(notifications) == 1
    assert notifications[0]["anomaly_ref_key"] == anomalies[0]["anomaly_ref_key"]
    assert "anomaly_id" not in notifications[0]


def _anomaly(actual: float, baseline: float, threshold: float):
    return {
        "anomaly_ref_key": "2026-01-08|retail-prod|cluster-eu-west-1|payments|moving_average_threshold",
        "cost_date": "2026-01-08",
        "project_name": "retail-prod",
        "cluster_name": "cluster-eu-west-1",
        "namespace_name": "payments",
        "actual_value": actual,
        "moving_average": baseline,
        "threshold_value": threshold,
        "is_anomaly": 1,
    }


def test_empty_anomaly_input_returns_empty_list():
    assert generate_notifications([]) == []


def test_negative_notification_threshold_raises_value_error():
    with pytest.raises(ValueError, match="notification_threshold must be >= 0"):
        generate_notifications([_anomaly(actual=301.0, baseline=100.0, threshold=120.0)], notification_threshold=-1.0)


def test_zero_notification_threshold_is_allowed():
    notifications = generate_notifications(
        [_anomaly(actual=100.1, baseline=100.0, threshold=80.0)],
        notification_threshold=0.0,
    )

    assert len(notifications) == 1


def test_absolute_difference_at_or_below_default_threshold_skips_notification():
    anomalies = [_anomaly(actual=300.0, baseline=100.0, threshold=120.0)]

    notifications = generate_notifications(anomalies)

    assert notifications == []


def test_absolute_difference_above_default_threshold_creates_notification():
    anomalies = [_anomaly(actual=301.0, baseline=100.0, threshold=120.0)]

    notifications = generate_notifications(anomalies)

    assert len(notifications) == 1


def test_notification_threshold_is_configurable():
    anomalies = [_anomaly(actual=250.0, baseline=100.0, threshold=120.0)]

    notifications = generate_notifications(anomalies, notification_threshold=100.0)

    assert len(notifications) == 1


def test_severity_is_assigned_for_created_notifications():
    low = generate_notifications([_anomaly(actual=131.0, baseline=-100.0, threshold=120.0)])[0]
    medium = generate_notifications([_anomaly(actual=171.0, baseline=-100.0, threshold=120.0)])[0]
    high = generate_notifications([_anomaly(actual=250.0, baseline=-100.0, threshold=120.0)])[0]

    assert low["severity"] == "LOW"
    assert medium["severity"] == "MEDIUM"
    assert high["severity"] == "HIGH"


def test_notification_reuses_existing_anomaly_severity():
    anomaly = _anomaly(actual=250.0, baseline=0.0, threshold=120.0)
    anomaly["severity"] = "MEDIUM"

    notification = generate_notifications([anomaly], notification_threshold=0.0)[0]

    assert notification["severity"] == "MEDIUM"


def test_notification_contains_required_fields():
    notifications = generate_notifications([_anomaly(actual=301.0, baseline=100.0, threshold=120.0)])

    assert len(notifications) == 1
    notification = notifications[0]
    assert {
        "anomaly_ref_key",
        "notification_date",
        "severity",
        "status",
        "message",
    }.issubset(notification)
    assert notification["status"] == "NEW"
    assert isinstance(notification["notification_date"], str)


def test_notification_includes_change_metadata_and_message_details():
    anomalies = [
        {
            "anomaly_ref_key": "2026-01-08|retail-prod|cluster-eu-west-1|payments|moving_average_threshold",
            "cost_date": "2026-01-08",
            "project_name": "retail-prod",
            "cluster_name": "cluster-eu-west-1",
            "namespace_name": "payments",
            "actual_value": 301.0,
            "moving_average": 100.0,
            "threshold_value": 120.0,
            "is_anomaly": 1,
            "daily_change": 75.0,
            "average_absolute_change": 20.0,
            "change_threshold": 40.0,
            "is_fast_change": True,
            "change_type": "FAST_CHANGE",
        }
    ]

    notifications = generate_notifications(anomalies, notification_threshold=0.0)

    assert len(notifications) == 1
    notification = notifications[0]
    assert notification["daily_change"] == 75.0
    assert notification["average_absolute_change"] == 20.0
    assert notification["change_threshold"] == 40.0
    assert notification["is_fast_change"] is True
    assert notification["change_type"] == "FAST_CHANGE"
    assert "change_type=FAST_CHANGE" in notification["message"]
    assert "daily_change=75.0" in notification["message"]
    assert "change_threshold=40.0" in notification["message"]
