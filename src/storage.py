"""Store pipeline results in SQLite tables."""

import sqlite3
from pathlib import Path


def initialize_database(db_path: Path) -> None:
    """Create the SQLite tables used in this project."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        cur.executescript(
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
                moving_average REAL,
                threshold_value REAL NOT NULL,
                severity TEXT NOT NULL,
                is_anomaly INTEGER NOT NULL,
                daily_change REAL,
                average_absolute_change REAL,
                change_threshold REAL,
                is_fast_change INTEGER,
                change_type TEXT,
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
        conn.commit()


def reset_database(db_path: Path) -> None:
    """Clear existing data so each pipeline run starts clean."""
    if not db_path.exists():
        return

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        cur = conn.cursor()

        table_rows = cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
        tables = {row[0] for row in table_rows}

        for table_name in ["Notification", "Anomaly", "NamespaceCost", "Namespace", "Cluster", "Project"]:
            if table_name in tables:
                cur.execute(f"DELETE FROM {table_name}")

        conn.commit()


def persist_pipeline_data(
    db_path: Path,
    projects,
    clusters,
    namespaces,
    namespace_costs,
    anomalies,
    notifications,
):
    """Save generated and processed data to SQLite."""
    reset_database(db_path)
    initialize_database(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        proj_ids = {}
        for project in projects:
            cur.execute(
                "INSERT INTO Project (project_name) VALUES (?)",
                (project["project_name"],),
            )
            proj_ids[project["project_name"]] = cur.lastrowid

        cl_ids = {}
        for cluster in clusters:
            proj_id = proj_ids[cluster["project_name"]]
            cur.execute(
                "INSERT INTO Cluster (cluster_name, project_id) VALUES (?, ?)",
                (cluster["cluster_name"], proj_id),
            )
            cl_key = (cluster["project_name"], cluster["cluster_name"])
            cl_ids[cl_key] = cur.lastrowid

        ns_ids = {}
        for namespace in namespaces:
            cl_key = (namespace["project_name"], namespace["cluster_name"])
            cl_id = cl_ids[cl_key]
            cur.execute(
                "INSERT INTO Namespace (namespace_name, cluster_id) VALUES (?, ?)",
                (namespace["namespace_name"], cl_id),
            )
            ns_key = (
                namespace["project_name"],
                namespace["cluster_name"],
                namespace["namespace_name"],
            )
            ns_ids[ns_key] = cur.lastrowid

        cost_ids = {}
        for row in namespace_costs:
            ns_key = (row["project_name"], row["cluster_name"], row["namespace_name"])
            ns_id = ns_ids[ns_key]
            cur.execute(
                """
                INSERT INTO NamespaceCost (cost_date, namespace_id, usage_cost, overhead_cost, total_cost)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["cost_date"],
                    ns_id,
                    float(row["usage_cost"]),
                    float(row["overhead_cost"]),
                    float(row["total_cost"]),
                ),
            )
            key = (row["cost_date"], row["project_name"], row["cluster_name"], row["namespace_name"])
            cost_ids[key] = cur.lastrowid

        anom_ids = []
        anom_by_ref = {}
        for anomaly in anomalies:
            cost_key = (
                anomaly["cost_date"],
                anomaly["project_name"],
                anomaly["cluster_name"],
                anomaly["namespace_name"],
            )
            cost_id = cost_ids[cost_key]
            cur.execute(
                """
                INSERT INTO Anomaly (
                    namespace_cost_id,
                    anomaly_date,
                    method,
                    actual_value,
                    moving_average,
                    threshold_value,
                    severity,
                    is_anomaly,
                    daily_change,
                    average_absolute_change,
                    change_threshold,
                    is_fast_change,
                    change_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cost_id,
                    anomaly["cost_date"],
                    anomaly["method"],
                    float(anomaly["actual_value"]),
                    float(anomaly["moving_average"]),
                    float(anomaly["threshold_value"]),
                    anomaly["severity"],
                    int(anomaly["is_anomaly"]),
                    anomaly.get("daily_change"),
                    anomaly.get("average_absolute_change"),
                    anomaly.get("change_threshold"),
                    None if anomaly.get("is_fast_change") is None else int(bool(anomaly.get("is_fast_change"))),
                    anomaly.get("change_type"),
                ),
            )
            anom_id = cur.lastrowid
            anom_ids.append(anom_id)

            ref_key = anomaly.get("anomaly_ref_key")
            if ref_key:
                anom_by_ref[str(ref_key)] = anom_id

        for index, notification in enumerate(notifications):
            anom_id = None
            ref_key = notification.get("anomaly_ref_key")
            if ref_key is not None:
                anom_id = anom_by_ref.get(str(ref_key))

            if anom_id is None and index < len(anom_ids):
                anom_id = anom_ids[index]

            if anom_id is None:
                continue

            cur.execute(
                """
                INSERT INTO Notification (anomaly_id, notification_date, severity, status, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    anom_id,
                    notification["notification_date"],
                    notification["severity"],
                    notification["status"],
                    notification["message"],
                ),
            )

        conn.commit()

    return {
        "Project": len(projects),
        "Cluster": len(clusters),
        "Namespace": len(namespaces),
        "NamespaceCost": len(namespace_costs),
        "Anomaly": len(anomalies),
        "Notification": len(notifications),
    }


def debug_sqlite(db_path: Path):
    """Return table names, row counts, and a small sample for debugging."""
    if not db_path.exists():
        return []

    summary = []
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        tables = cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        for (table_name,) in tables:
            n_rows = cur.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            sample = cur.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchall()
            summary.append({"table": table_name, "row_count": n_rows, "sample": sample})

    return summary
