"""Very simple Streamlit dashboard for pipeline observability.

This view is intentionally minimal: it helps beginners inspect what the local
pipeline stored in SQLite, without adding advanced dashboard complexity.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st


DB_PATH = Path("data") / "cloud_costs.db"


def _get_table_names(connection: sqlite3.Connection) -> list[str]:
    """Return all user tables in the SQLite database."""
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [row[0] for row in rows]


def build_dashboard() -> None:
    """Render a compact dashboard with table counts and row previews."""
    st.title("Cloud Cost Prototype Dashboard")
    st.caption("Local, beginner-friendly observability view")

    if not DB_PATH.exists():
        st.warning(f"Database not found: {DB_PATH}. Run the pipeline first.")
        return

    with sqlite3.connect(DB_PATH) as connection:
        table_names = _get_table_names(connection)

        if not table_names:
            st.info("No tables found in SQLite yet.")
            return

        st.subheader("Tables")
        for table in table_names:
            row_count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            st.write(f"- {table}: {row_count} rows")

        st.subheader("Preview (first 5 rows per table)")
        for table in table_names:
            st.markdown(f"**{table}**")
            rows = connection.execute(f"SELECT * FROM {table} LIMIT 5").fetchall()
            if not rows:
                st.write("(empty)")
                continue

            column_names = [column[0] for column in connection.execute(f"SELECT * FROM {table} LIMIT 0").description]
            for row in rows:
                st.json(dict(zip(column_names, row)))


if __name__ == "__main__":
    build_dashboard()
