"""SQLite storage layer for the agreed v1 entities.

This module persists pipeline data into normalized tables:
Project, Cluster, Namespace, NamespaceCost, Anomaly, Notification.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def initialize_database(db_path: Path) -> None:
    """Create the SQLite schema for the agreed v1 model."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS Project (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS Cluster (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT NOT NULL,
                project_id INTEGER NOT NULL,
                UNIQUE(cluster_name, project_id),
                FOREIGN KEY(project_id) REFERENCES Project(id)
            );

            CREATE TABLE IF NOT EXISTS Namespace (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace_name TEXT NOT NULL,
                cluster_id INTEGER NOT NULL,
                UNIQUE(namespace_name, cluster_id),
                FOREIGN KEY(cluster_id) REFERENCES Cluster(id)
            );

            CREATE TABLE IF NOT EXISTS NamespaceCost (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cost_date TEXT NOT NULL,
                namespace_id INTEGER NOT NULL,
                usage_cost REAL NOT NULL,
                overhead_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                FOREIGN KEY(namespace_id) REFERENCES Namespace(id)
            );

            CREATE TABLE IF NOT EXISTS Anomaly (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace_cost_id INTEGER NOT NULL,
                anomaly_date TEXT NOT NULL,
                method TEXT NOT NULL,
                actual_value REAL NOT NULL,
                baseline_value REAL,
                threshold_value REAL NOT NULL,
                is_anomaly INTEGER NOT NULL,
                FOREIGN KEY(namespace_cost_id) REFERENCES NamespaceCost(id)
            );

            CREATE TABLE IF NOT EXISTS Notification (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anomaly_id INTEGER NOT NULL,
                notification_date TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY(anomaly_id) REFERENCES Anomaly(id)
            );
            """
        )
        connection.commit()


def reset_database(db_path: Path) -> None:
    """Drop all user tables to guarantee a clean schema per pipeline run."""
    if not db_path.exists():
        return

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        cursor = connection.cursor()

        table_rows = cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

        for (table_name,) in table_rows:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")

        connection.commit()


def persist_pipeline_data(
    db_path: Path,
    projects: list[dict],
    clusters: list[dict],
    namespaces: list[dict],
    namespace_costs: list[dict],
    anomalies: list[dict],
    notifications: list[dict],
) -> dict[str, int]:
    """Persist generated and processed data into normalized SQLite tables."""
    reset_database(db_path)
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        project_ids: dict[str, int] = {}
        for project in projects:
            cursor.execute(
                "INSERT INTO Project (project_name) VALUES (?)",
                (project["project_name"],),
            )
            project_ids[project["project_name"]] = cursor.lastrowid

        cluster_ids: dict[tuple[str, str], int] = {}
        for cluster in clusters:
            project_id = project_ids[cluster["project_name"]]
            cursor.execute(
                "INSERT INTO Cluster (cluster_name, project_id) VALUES (?, ?)",
                (cluster["cluster_name"], project_id),
            )
            cluster_key = (cluster["project_name"], cluster["cluster_name"])
            cluster_ids[cluster_key] = cursor.lastrowid

        namespace_ids: dict[tuple[str, str, str], int] = {}
        for namespace in namespaces:
            cluster_key = (namespace["project_name"], namespace["cluster_name"])
            cluster_id = cluster_ids[cluster_key]
            cursor.execute(
                "INSERT INTO Namespace (namespace_name, cluster_id) VALUES (?, ?)",
                (namespace["namespace_name"], cluster_id),
            )
            namespace_key = (
                namespace["project_name"],
                namespace["cluster_name"],
                namespace["namespace_name"],
            )
            namespace_ids[namespace_key] = cursor.lastrowid

        namespace_cost_ids: dict[tuple[str, str, str, str], int] = {}
        for row in namespace_costs:
            namespace_key = (row["project_name"], row["cluster_name"], row["namespace_name"])
            namespace_id = namespace_ids[namespace_key]
            cursor.execute(
                """
                INSERT INTO NamespaceCost (cost_date, namespace_id, usage_cost, overhead_cost, total_cost)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["cost_date"],
                    namespace_id,
                    float(row["usage_cost"]),
                    float(row["overhead_cost"]),
                    float(row["total_cost"]),
                ),
            )
            key = (row["cost_date"], row["project_name"], row["cluster_name"], row["namespace_name"])
            namespace_cost_ids[key] = cursor.lastrowid

        anomaly_ids: list[int] = []
        for anomaly in anomalies:
            namespace_cost_key = (
                anomaly["cost_date"],
                anomaly["project_name"],
                anomaly["cluster_name"],
                anomaly["namespace_name"],
            )
            namespace_cost_id = namespace_cost_ids[namespace_cost_key]
            cursor.execute(
                """
                INSERT INTO Anomaly (
                    namespace_cost_id,
                    anomaly_date,
                    method,
                    actual_value,
                    baseline_value,
                    threshold_value,
                    is_anomaly
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    namespace_cost_id,
                    anomaly["cost_date"],
                    anomaly["method"],
                    float(anomaly["actual_value"]),
                    float(anomaly["baseline_value"]),
                    float(anomaly["threshold_value"]),
                    int(anomaly["is_anomaly"]),
                ),
            )
            anomaly_ids.append(cursor.lastrowid)

        for index, notification in enumerate(notifications):
            if index >= len(anomaly_ids):
                break
            cursor.execute(
                """
                INSERT INTO Notification (anomaly_id, notification_date, severity, status, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    anomaly_ids[index],
                    notification["notification_date"],
                    notification["severity"],
                    notification["status"],
                    notification["message"],
                ),
            )

        connection.commit()

    return {
        "Project": len(projects),
        "Cluster": len(clusters),
        "Namespace": len(namespaces),
        "NamespaceCost": len(namespace_costs),
        "Anomaly": len(anomalies),
        "Notification": len(notifications),
    }


def debug_sqlite(db_path: Path) -> list[dict]:
    """Return table names, row counts, and first five rows for debugging."""
    if not db_path.exists():
        return []

    summary: list[dict] = []
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        table_rows = cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        for (table_name,) in table_rows:
            row_count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            sample = cursor.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchall()
            summary.append({"table": table_name, "row_count": row_count, "sample": sample})

    return summary
