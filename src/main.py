"""Main pipeline runner."""

from src.alerting import generate_notifications
from src.allocation import apply_overhead_allocation
from src.anomaly_detection import detect_anomalies
from src.data_generator import generate_structured_data
from src.email_notifier import send_notifications_by_email
from src.paths import DB_PATH
from src.storage import persist_pipeline_data


ALERT_THRESHOLD = 200.0


def main():
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)
    print(f"Generated {len(dataset['namespace_costs'])} cost records across {len(dataset['namespaces'])} namespaces")

    rows = apply_overhead_allocation(dataset["namespace_costs"], dataset["cluster_overheads"])
    anomalies = detect_anomalies(rows)
    print(f"Detected {len(anomalies)} anomalies")

    notifications = generate_notifications(anomalies, notification_threshold=ALERT_THRESHOLD)
    print(f"Generated {len(notifications)} notifications")

    persist_pipeline_data(
        db_path=DB_PATH,
        projects=dataset["projects"],
        clusters=dataset["clusters"],
        namespaces=dataset["namespaces"],
        namespace_costs=rows,
        anomalies=anomalies,
        notifications=notifications,
    )
    print(f"Saved to {DB_PATH}")

    result = send_notifications_by_email(notifications)
    print(result["message"])


if __name__ == "__main__":
    main()
