"""Experimental Streamlit dashboard for cloud cost and anomaly analysis.

This file intentionally sits next to ``dashboard.py`` so the existing simple
dashboard remains unchanged while richer visualisations can be tried out.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


DB_PATH = Path("data") / "cloud_costs.db"


def load_costs(connection: sqlite3.Connection) -> pd.DataFrame:
    """Load namespace-level costs with project and cluster context."""
    return pd.read_sql_query(
        """
        SELECT
            nc.id AS namespace_cost_id,
            nc.cost_date,
            p.project_name,
            c.cluster_name,
            n.namespace_name,
            nc.usage_cost,
            nc.overhead_cost,
            nc.total_cost
        FROM NamespaceCost nc
        JOIN Namespace n ON n.id = nc.namespace_id
        JOIN Cluster c ON c.id = n.cluster_id
        JOIN Project p ON p.id = c.project_id
        ORDER BY nc.cost_date
        """,
        connection,
        parse_dates=["cost_date"],
    )


def load_anomalies(connection: sqlite3.Connection) -> pd.DataFrame:
    """Load detected anomalies with their affected namespace context."""
    return pd.read_sql_query(
        """
        SELECT
            a.id AS anomaly_id,
            a.namespace_cost_id,
            a.anomaly_date,
            p.project_name,
            c.cluster_name,
            n.namespace_name,
            a.method,
            a.actual_value,
            a.baseline_value,
            a.threshold_value,
            a.is_anomaly
        FROM Anomaly a
        JOIN NamespaceCost nc ON nc.id = a.namespace_cost_id
        JOIN Namespace n ON n.id = nc.namespace_id
        JOIN Cluster c ON c.id = n.cluster_id
        JOIN Project p ON p.id = c.project_id
        WHERE a.is_anomaly = 1
        ORDER BY a.anomaly_date
        """,
        connection,
        parse_dates=["anomaly_date"],
    )


def build_dashboard() -> None:
    """Render the experimental dashboard."""
    st.title("Cloud Cost Analysis")

    if not DB_PATH.exists():
        st.warning("Database not found. Run the pipeline first with: python -m src.main")
        return

    with sqlite3.connect(DB_PATH) as connection:
        costs = load_costs(connection)
        anomalies = load_anomalies(connection)

    if costs.empty:
        st.info("No cost data found.")
        return

    projects = sorted(costs["project_name"].unique())
    namespaces = sorted(costs["namespace_name"].unique())

    selected_projects = st.sidebar.multiselect("Project", projects, default=projects)
    selected_namespaces = st.sidebar.multiselect("Namespace", namespaces, default=namespaces)

    filtered_costs = costs[
        costs["project_name"].isin(selected_projects)
        & costs["namespace_name"].isin(selected_namespaces)
    ]

    filtered_anomalies = anomalies[
        anomalies["project_name"].isin(selected_projects)
        & anomalies["namespace_name"].isin(selected_namespaces)
    ]

    if filtered_costs.empty:
        st.info("No data matches the selected filters.")
        return

    daily_costs = filtered_costs.groupby("cost_date", as_index=False)["total_cost"].sum()
    daily_costs["rolling_7_day_avg"] = (
        daily_costs["total_cost"].rolling(window=7, min_periods=1).mean()
    )

    total_cost = filtered_costs["total_cost"].sum()
    anomaly_count = len(filtered_anomalies)
    anomaly_day_count = filtered_anomalies["anomaly_date"].nunique()
    latest_cost = daily_costs["total_cost"].iloc[-1]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total cost", f"{total_cost:.2f}")
    col2.metric("Total anomalies", anomaly_count)
    col3.metric("Days with anomalies", anomaly_day_count)
    col4.metric("Latest daily cost", f"{latest_cost:.2f}")

    cost_fig = go.Figure()
    cost_fig.add_trace(
        go.Scatter(
            x=daily_costs["cost_date"],
            y=daily_costs["total_cost"],
            mode="lines",
            name="Total cost",
        )
    )
    cost_fig.add_trace(
        go.Scatter(
            x=daily_costs["cost_date"],
            y=daily_costs["rolling_7_day_avg"],
            mode="lines",
            name="7-day trend",
        )
    )

    if not filtered_anomalies.empty:
        anomaly_daily = (
            filtered_anomalies.groupby("anomaly_date", as_index=False)
            .agg(
                anomaly_count=("anomaly_id", "count"),
                anomalous_namespace_cost=("actual_value", "sum"),
            )
            .merge(
                daily_costs[["cost_date", "total_cost"]],
                left_on="anomaly_date",
                right_on="cost_date",
                how="left",
            )
        )
        cost_fig.add_trace(
            go.Scatter(
                x=anomaly_daily["anomaly_date"],
                y=anomaly_daily["total_cost"],
                mode="markers",
                name="Dates with anomalies",
                marker={"size": 10, "color": "red"},
                customdata=anomaly_daily[["anomaly_count", "anomalous_namespace_cost"]],
                hovertemplate=(
                    "Date: %{x}<br>"
                    "Total selected cost: %{y:.2f}<br>"
                    "Anomalies: %{customdata[0]}<br>"
                    "Anomalous namespace cost: %{customdata[1]:.2f}"
                    "<extra></extra>"
                ),
            )
        )

    cost_fig.update_layout(
        title="Costs over time",
        xaxis_title="Date",
        yaxis_title="Cost",
    )
    st.plotly_chart(cost_fig, width="stretch")

    st.subheader("Costs by namespace")
    namespace_costs = (
        filtered_costs.groupby("namespace_name", as_index=False)["total_cost"]
        .sum()
        .sort_values("total_cost", ascending=False)
    )
    namespace_fig = px.bar(
        namespace_costs,
        x="namespace_name",
        y="total_cost",
        title="Total cost by namespace",
    )
    st.plotly_chart(namespace_fig, width="stretch")

    if filtered_anomalies.empty:
        st.info("No anomalies found for the selected filters.")
        return

    st.subheader("Anomaly details")
    anomaly_columns = [
        "anomaly_date",
        "project_name",
        "cluster_name",
        "namespace_name",
        "actual_value",
        "baseline_value",
        "threshold_value",
        "method",
    ]
    st.dataframe(
        filtered_anomalies[anomaly_columns],
        width="stretch",
        hide_index=True,
    )

    anomaly_value_fig = go.Figure()
    anomaly_value_fig.add_trace(
        go.Scatter(
            x=filtered_anomalies["anomaly_date"],
            y=filtered_anomalies["actual_value"],
            mode="markers",
            name="Actual anomaly value",
            marker={"size": 10, "color": "red"},
            customdata=filtered_anomalies[
                ["project_name", "cluster_name", "namespace_name"]
            ],
            hovertemplate=(
                "Date: %{x}<br>"
                "Project: %{customdata[0]}<br>"
                "Cluster: %{customdata[1]}<br>"
                "Namespace: %{customdata[2]}<br>"
                "Actual: %{y:.2f}"
                "<extra></extra>"
            ),
        )
    )
    anomaly_value_fig.add_trace(
        go.Scatter(
            x=filtered_anomalies["anomaly_date"],
            y=filtered_anomalies["baseline_value"],
            mode="markers",
            name="Namespace baseline",
            marker={"size": 8, "color": "gray"},
        )
    )
    anomaly_value_fig.add_trace(
        go.Scatter(
            x=filtered_anomalies["anomaly_date"],
            y=filtered_anomalies["threshold_value"],
            mode="markers",
            name="Namespace threshold",
            marker={"size": 8, "color": "orange"},
        )
    )
    anomaly_value_fig.update_layout(
        title="Anomaly values compared with namespace baseline and threshold",
        xaxis_title="Date",
        yaxis_title="Namespace cost",
    )
    st.plotly_chart(anomaly_value_fig, width="stretch")

    anomalies_by_namespace = (
        filtered_anomalies.groupby("namespace_name", as_index=False)
        .agg(
            anomaly_count=("anomaly_id", "count"),
            max_actual_value=("actual_value", "max"),
            avg_baseline=("baseline_value", "mean"),
        )
        .sort_values("anomaly_count", ascending=False)
    )
    anomaly_fig = px.bar(
        anomalies_by_namespace,
        x="namespace_name",
        y="anomaly_count",
        hover_data=["max_actual_value", "avg_baseline"],
        title="Anomalies by namespace",
    )
    st.plotly_chart(anomaly_fig, width="stretch")


if __name__ == "__main__":
    build_dashboard()
