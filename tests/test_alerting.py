from src.alerting import generate_notifications


def test_generate_notifications_keeps_anomaly_reference_key() -> None:
    anomalies = [
        {
            "anomaly_ref_key": "2026-01-08|retail-prod|cluster-eu-west-1|payments|moving_average_threshold",
            "cost_date": "2026-01-08",
            "project_name": "retail-prod",
            "cluster_name": "cluster-eu-west-1",
            "namespace_name": "payments",
            "actual_value": 160.0,
            "baseline_value": 100.0,
            "threshold_value": 120.0,
            "is_anomaly": 1,
        }
    ]

    notifications = generate_notifications(anomalies)

    assert len(notifications) == 1
    assert notifications[0]["anomaly_ref_key"] == anomalies[0]["anomaly_ref_key"]
    assert "anomaly_id" not in notifications[0]
