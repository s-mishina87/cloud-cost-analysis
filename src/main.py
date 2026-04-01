"""Beginner-friendly pipeline entry point for the corrected v1 model.

Pipeline model:
Project -> Cluster -> Namespace -> NamespaceCost -> Anomaly -> Notification
"""

from __future__ import annotations

from pathlib import Path

from src.alerting import generate_notifications
from src.allocation import apply_overhead_allocation
from src.anomaly_detection import detect_anomalies
from src.data_generator import generate_structured_data
from src.storage import debug_sqlite, persist_pipeline_data


DB_PATH = Path("data") / "cloud_costs.db"


def _preview_rows(rows: list[dict], label: str, sample_size: int = 5) -> None:
    """Print a compact sample block to keep each step understandable."""
    print(label)
    if not rows:
        print("  (no rows)")
        return
    for row in rows[:sample_size]:
        print(f"  - {row}")


def _print_sqlite_debug(db_path: Path) -> None:
    """Print table names, row counts, and first five rows per table."""
    print("\n[SQLite debug]")
    summary = debug_sqlite(db_path)
    if not summary:
        print("No database content found.")
        return

    for entry in summary:
        print(f"- {entry['table']}: {entry['row_count']} rows")
        print("  first 5 rows:")
        if not entry["sample"]:
            print("    (empty)")
            continue
        for sample_row in entry["sample"]:
            print(f"    {sample_row}")


def main() -> None:
    """Run the corrected local prototype end-to-end with clear step output."""
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)

    print("\n[Step 1: Data generation]")
    print(f"Projects: {len(dataset['projects'])}")
    print(f"Clusters: {len(dataset['clusters'])}")
    print(f"Namespaces: {len(dataset['namespaces'])}")
    print(f"NamespaceCost records: {len(dataset['namespace_costs'])}")
    _preview_rows(dataset["namespace_costs"], "Example NamespaceCost rows:")
    print("Target tables: Project, Cluster, Namespace, NamespaceCost")

    allocated_costs = apply_overhead_allocation(dataset["namespace_costs"], dataset["cluster_overheads"])

    print("\n[Step 2: Allocation]")
    print("Overhead distribution applied per cluster/day using usage share.")
    print(f"Processed NamespaceCost records: {len(allocated_costs)}")
    _preview_rows(allocated_costs, "Example allocated rows:")
    print("Updated fields: usage_cost, overhead_cost, total_cost")

    anomalies = detect_anomalies(allocated_costs, window_size=7, deviation_factor=1.5)

    print("\n[Step 3: Anomaly detection]")
    print(f"Detected anomalies: {len(anomalies)}")
    _preview_rows(anomalies, "Example anomaly rows:")
    print("Target table: Anomaly")

    notifications = generate_notifications(anomalies)

    print("\n[Step 4: Notification generation]")
    print(f"Notifications created: {len(notifications)}")
    _preview_rows(notifications, "Example notification rows:")
    print("Target table: Notification")

    persisted = persist_pipeline_data(
        db_path=DB_PATH,
        projects=dataset["projects"],
        clusters=dataset["clusters"],
        namespaces=dataset["namespaces"],
        namespace_costs=allocated_costs,
        anomalies=anomalies,
        notifications=notifications,
    )

    print("\n[Final summary]")
    print(f"Total generated NamespaceCost records: {persisted['NamespaceCost']}")
    print(f"Total anomalies: {persisted['Anomaly']}")
    print(f"Total notifications: {persisted['Notification']}")
    print(f"Database file: {DB_PATH}")

    _print_sqlite_debug(DB_PATH)


if __name__ == "__main__":
    main()
