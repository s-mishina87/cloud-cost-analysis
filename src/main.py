"""
Pipeline model:
Project -> Cluster -> Namespace -> NamespaceCost -> Anomaly -> Notification
"""

from __future__ import annotations

from pathlib import Path

from src.alerting import generate_notifications
from src.allocation import apply_overhead_allocation
from src.anomaly_detection import detect_anomalies
from src.data_generator import generate_structured_data
from src.email_notifier import send_notifications_by_email
from src.paths import DB_PATH
from src.standard_deviation_detection import (
    calculate_namespace_rolling_stddev_details,
    calculate_rolling_stddev_summary,
    detect_anomalies_rolling_stddev,
)
from src.storage import debug_sqlite, persist_pipeline_data
from src.teams_notifier import send_notifications_to_teams


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


def _print_namespace_stddev_details(rows: list[dict]) -> None:
    """Print per-namespace rolling standard deviation comparison details."""
    print("Rolling stddev details by namespace, top 20 by average stddev:")
    if not rows:
        print("  (no namespace stddev details)")
        return

    for row in rows:
        namespace_label = f"{row['project_name']}/{row['cluster_name']}/{row['namespace_name']}"
        print(
            f"  - {namespace_label}: "
            f"rolling_mean={row['rolling_mean']}, "
            f"rolling_stddev={row['rolling_stddev']}, "
            f"threshold={row['threshold']}, "
            f"actual_value={row['actual_value']}, "
            f"actual-threshold={row['actual_minus_threshold']}"
        )


def _print_rolling_stddev_anomaly_details(rows: list[dict]) -> None:
    """Print details for anomalies found by the rolling standard deviation comparison."""
    print("Rolling stddev detected anomaly details:")
    if not rows:
        print("  (no rolling stddev anomalies)")
        return

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row["project_name"],
            row["cluster_name"],
            row["namespace_name"],
            row["cost_date"],
        ),
    )
    for row in sorted_rows:
        namespace_label = f"{row['project_name']}/{row['cluster_name']}/{row['namespace_name']}"
        actual_minus_threshold = round(row["actual_value"] - row["threshold_value"], 2)
        print(
            f"  - {row['cost_date']} {namespace_label}: "
            f"rolling_mean={row['rolling_average']}, "
            f"rolling_stddev={row['rolling_stddev']}, "
            f"threshold={row['threshold_value']}, "
            f"actual_value={row['actual_value']}, "
            f"actual-threshold={actual_minus_threshold}, "
            f"severity={row['severity']}"
        )


def main() -> None:
    """Run the corrected local prototype end-to-end with clear step output."""
    # Step 1 starts here: generate synthetic source data for the full pipeline.
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)

    print("\n[Step 1: Data generation]")
    print(f"Projects: {len(dataset['projects'])}")
    print(f"Clusters: {len(dataset['clusters'])}")
    print(f"Namespaces: {len(dataset['namespaces'])}")
    print(f"NamespaceCost records: {len(dataset['namespace_costs'])}")
    _preview_rows(dataset["namespace_costs"], "Example NamespaceCost rows:")
    print("Target tables: Project, Cluster, Namespace, NamespaceCost")

    # Step 2 starts here: distribute cluster overhead to namespace-level costs.
    allocated_costs = apply_overhead_allocation(dataset["namespace_costs"], dataset["cluster_overheads"])

    print("\n[Step 2: Allocation]")
    print("Overhead distribution applied per cluster/day using usage share.")
    print(f"Processed NamespaceCost records: {len(allocated_costs)}")
    _preview_rows(allocated_costs, "Example allocated rows:")
    print("Updated fields: usage_cost, overhead_cost, total_cost")

    # Step 3 starts here: detect anomalous namespace total costs over time.
    anomalies = detect_anomalies(allocated_costs, window_size=7, deviation_factor=1.5)
    rolling_stddev_anomalies = detect_anomalies_rolling_stddev(
        allocated_costs,
        window_size=7,
        stddev_factor=2.0,
    )
    rolling_stddev_summary = calculate_rolling_stddev_summary(allocated_costs, window_size=7)
    rolling_stddev_namespace_details = calculate_namespace_rolling_stddev_details(
        allocated_costs,
        window_size=7,
        stddev_factor=2.0,
        limit=20,
    )

    print("\n[Step 3: Anomaly detection]")
    print(f"Detected anomalies: {len(anomalies)}")
    print(f"Rolling stddev comparison anomalies: {len(rolling_stddev_anomalies)}")
    print(
        "Rolling stddev comparison stats: "
        f"avg per namespace={rolling_stddev_summary['average_stddev_per_namespace']}, "
        f"min={rolling_stddev_summary['minimum_stddev']}, "
        f"max={rolling_stddev_summary['maximum_stddev']}"
    )
    _print_namespace_stddev_details(rolling_stddev_namespace_details)
    _print_rolling_stddev_anomaly_details(rolling_stddev_anomalies)
    _preview_rows(anomalies, "Example anomaly rows:")
    print("Target table: Anomaly")

    # Step 4 starts here: convert detected anomalies into notifications.
    notifications = generate_notifications(anomalies)

    print("\n[Step 4: Notification generation]")
    print(f"Notifications created: {len(notifications)}")
    _preview_rows(notifications, "Example notification rows:")
    print("Target table: Notification")

    # Step 4b is optional: send internal notifications to Teams webhook.
    teams_result = send_notifications_to_teams(notifications)
    print("\n[Step 4b: Optional Teams delivery]")
    print(teams_result["message"])

    # Step 4c is optional: send internal notifications by email.
    #email_result = send_notifications_by_email(notifications)
    #print("\n[Step 4c: Optional email delivery]")
    #print(email_result["message"])

    # Step 5 starts here: persist all entities into normalized SQLite tables.
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
    # Application entry point starts here.
    main()
