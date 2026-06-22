import sqlite3

from src.storage import persist_pipeline_data


def test_persist_pipeline_data_stores_anomaly_severity(tmp_path) -> None:
    db_path = tmp_path / "cloud_costs.db"
    projects = [{"project_name": "retail-prod"}]
    clusters = [{"project_name": "retail-prod", "cluster_name": "main"}]
    namespaces = [
        {
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "payments",
        }
    ]
    namespace_costs = [
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "payments",
            "usage_cost": 90.0,
            "overhead_cost": 10.0,
            "total_cost": 100.0,
        }
    ]
    anomalies = [
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "payments",
            "anomaly_ref_key": "2026-01-01|retail-prod|main|payments|moving_average_threshold",
            "method": "moving_average_threshold",
            "actual_value": 100.0,
            "baseline_value": 40.0,
            "threshold_value": 50.0,
            "severity": "HIGH",
            "is_anomaly": 1,
        }
    ]

    persist_pipeline_data(
        db_path=db_path,
        projects=projects,
        clusters=clusters,
        namespaces=namespaces,
        namespace_costs=namespace_costs,
        anomalies=anomalies,
        notifications=[],
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT severity FROM Anomaly").fetchone()

    assert row == ("HIGH",)
