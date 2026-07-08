"""Streamlit dashboard for cloud cost and anomaly results."""

import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.paths import DB_PATH


CURRENCY_PREFIX = "\u20ac"
CURRENCY_TICK_FORMAT = ",.2f"
NAMESPACE_COLORS = px.colors.qualitative.Plotly
SIDEBAR_WIDTH_PX = 420
SEVERITY_ORDER = ["HIGH", "MEDIUM", "LOW"]
DEFAULT_THRESHOLD_FACTOR = 1.5
SEVERITY_COLORS = {
    "HIGH": "#dc2626",
    "MEDIUM": "#f59e0b",
    "LOW": "#2563eb",
}


def widen_sidebar() -> None:
    """Make the sidebar wider for long filter names."""
    st.markdown(
        f"""
        <style>
        section[data-testid="stSidebar"] {{
            min-width: {SIDEBAR_WIDTH_PX}px !important;
            max-width: {SIDEBAR_WIDTH_PX}px !important;
        }}

        section[data-testid="stSidebar"] > div {{
            min-width: {SIDEBAR_WIDTH_PX}px !important;
            max-width: {SIDEBAR_WIDTH_PX}px !important;
        }}

        section[data-testid="stSidebar"] [data-baseweb="tag"] {{
            max-width: 100% !important;
            height: auto !important;
            min-height: 28px !important;
            align-items: flex-start !important;
        }}

        section[data-testid="stSidebar"] [data-baseweb="tag"] span {{
            max-width: none !important;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            line-height: 1.25 !important;
        }}

        section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
            align-items: flex-start !important;
            max-height: 240px !important;
            overflow-y: auto !important;
        }}

        @media (max-width: 700px) {{
            section[data-testid="stSidebar"],
            section[data-testid="stSidebar"] > div {{
                min-width: 100vw !important;
                max-width: 100vw !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def add_namespace_series_label(data: pd.DataFrame) -> pd.DataFrame:
    """Add one combined label for filters and charts."""
    data = data.copy()
    data["namespace_series"] = (
        data["project_name"] + " / " + data["cluster_name"] + " / " + data["namespace_name"]
    )
    return data


def format_euro(value: float) -> str:
    """Format a number as euro currency."""
    return f"{CURRENCY_PREFIX}{value:,.2f}"


def load_costs(connection: sqlite3.Connection) -> pd.DataFrame:
    """Load namespace costs together with project and cluster names."""
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
    """Load anomalies together with their project, cluster, and namespace."""
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
            a.moving_average,
            a.threshold_value,
            a.severity,
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
    """Build and show the dashboard."""
    widen_sidebar()
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

    costs = add_namespace_series_label(costs)
    anomalies = add_namespace_series_label(anomalies)

    projects = sorted(costs["project_name"].unique())
    namespaces = sorted(costs["namespace_series"].unique())

    sel_projects = st.sidebar.multiselect("Project", projects, default=projects)
    sel_namespaces = st.sidebar.multiselect("Namespace", namespaces, default=namespaces)
    sev_opts = [
        severity for severity in SEVERITY_ORDER if severity in set(anomalies["severity"].unique())
    ]
    sel_severities = st.sidebar.multiselect(
        "Anomaly severity",
        sev_opts,
        default=sev_opts,
    )
    threshold_factor = st.sidebar.number_input(
        "Threshold factor",
        min_value=1.0,
        max_value=5.0,
        value=DEFAULT_THRESHOLD_FACTOR,
        step=0.1,
    )

    costs_f = costs[
        costs["project_name"].isin(sel_projects)
        & costs["namespace_series"].isin(sel_namespaces)
    ]

    anom_f = anomalies[
        anomalies["project_name"].isin(sel_projects)
        & anomalies["namespace_series"].isin(sel_namespaces)
        & anomalies["severity"].isin(sel_severities)
    ]

    if costs_f.empty:
        st.info("No data matches the selected filters.")
        return

    daily_costs = costs_f.groupby("cost_date", as_index=False)["total_cost"].sum()
    daily_costs["rolling_7_day_avg"] = (
        daily_costs["total_cost"].rolling(window=7, min_periods=1).mean()
    )

    total_cost = costs_f["total_cost"].sum()
    anomaly_count = len(anom_f)
    anomaly_day_count = anom_f["anomaly_date"].nunique()
    latest_cost = daily_costs["total_cost"].iloc[-1]

    col1, col2, col3, col4 = st.columns([1.6, 1.0, 1.0, 1.3])
    col1.metric("Total cost", format_euro(total_cost))
    col2.metric("Total anomalies", anomaly_count)
    col3.metric("Days with anomalies", anomaly_day_count)
    col4.metric("Latest daily cost", format_euro(latest_cost))

    severity_counts = anom_f["severity"].value_counts()
    severity_cols = st.columns(3)
    for index, severity in enumerate(SEVERITY_ORDER):
        severity_cols[index].metric(
            f"{severity.title()} severity",
            int(severity_counts.get(severity, 0)),
        )

    st.subheader("Costs over time")
    min_cost_date = daily_costs["cost_date"].min().date()
    max_cost_date = daily_costs["cost_date"].max().date()
    range_mode = st.radio(
        "Cost chart range",
        ["All data", "Custom range"],
        horizontal=True,
    )
    chart_start_date = min_cost_date
    chart_end_date = max_cost_date

    if range_mode == "Custom range":
        selected_range = st.date_input(
            "Date range",
            value=(min_cost_date, max_cost_date),
            min_value=min_cost_date,
            max_value=max_cost_date,
        )
        if isinstance(selected_range, (list, tuple)) and len(selected_range) == 2:
            chart_start_date, chart_end_date = selected_range

    if chart_start_date > chart_end_date:
        chart_start_date, chart_end_date = chart_end_date, chart_start_date

    chart_start_timestamp = pd.Timestamp(chart_start_date)
    chart_end_timestamp = pd.Timestamp(chart_end_date)
    chart_daily_costs = daily_costs[
        daily_costs["cost_date"].between(chart_start_timestamp, chart_end_timestamp)
    ]

    cost_fig = go.Figure()
    cost_fig.add_trace(
        go.Scatter(
            x=chart_daily_costs["cost_date"],
            y=chart_daily_costs["total_cost"],
            mode="lines",
            name="Total cost",
            hovertemplate=(
                "Date: %{x}<br>Total cost: "
                + CURRENCY_PREFIX
                + "%{y:,.2f}<extra></extra>"
            ),
        )
    )
    cost_fig.add_trace(
        go.Scatter(
            x=chart_daily_costs["cost_date"],
            y=chart_daily_costs["rolling_7_day_avg"],
            mode="lines",
            name="7-day trend",
            hovertemplate=(
                "Date: %{x}<br>7-day trend: "
                + CURRENCY_PREFIX
                + "%{y:,.2f}<extra></extra>"
            ),
        )
    )

    if not anom_f.empty:
        anomaly_daily = (
            anom_f.groupby("anomaly_date", as_index=False)
            .agg(
                anomaly_count=("anomaly_id", "count"),
                anomalous_namespace_cost=("actual_value", "sum"),
                highest_severity=(
                    "severity",
                    lambda values: min(values, key=lambda item: SEVERITY_ORDER.index(item)),
                ),
            )
            .merge(
                daily_costs[["cost_date", "total_cost"]],
                left_on="anomaly_date",
                right_on="cost_date",
                how="left",
            )
        )
        chart_anomaly_daily = anomaly_daily[
            anomaly_daily["anomaly_date"].between(chart_start_timestamp, chart_end_timestamp)
        ]
        cost_fig.add_trace(
            go.Scatter(
                x=chart_anomaly_daily["anomaly_date"],
                y=chart_anomaly_daily["total_cost"],
                mode="markers",
                name="Dates with anomalies",
                marker={
                    "size": 10,
                    "color": chart_anomaly_daily["highest_severity"].map(SEVERITY_COLORS),
                },
                customdata=chart_anomaly_daily[
                    ["anomaly_count", "anomalous_namespace_cost", "highest_severity"]
                ],
                hovertemplate=(
                    "Date: %{x}<br>"
                    "Total selected cost: "
                    + CURRENCY_PREFIX
                    + "%{y:,.2f}<br>"
                    "Anomalies: %{customdata[0]}<br>"
                    "Highest severity: %{customdata[2]}<br>"
                    "Anomalous namespace cost: "
                    + CURRENCY_PREFIX
                    + "%{customdata[1]:,.2f}"
                    "<extra></extra>"
                ),
            )
        )

    cost_fig.update_layout(
        title="Costs over time",
        xaxis_title="Date",
        yaxis_title="Cost (" + CURRENCY_PREFIX + ")",
        yaxis={"tickprefix": CURRENCY_PREFIX, "tickformat": CURRENCY_TICK_FORMAT},
    )
    st.plotly_chart(cost_fig, width="stretch")

    st.subheader("Costs by namespace")
    namespace_costs = (
        costs_f.groupby("namespace_series", as_index=False)["total_cost"]
        .sum()
        .sort_values("total_cost", ascending=False)
    )
    namespace_fig = px.bar(
        namespace_costs,
        x="namespace_series",
        y="total_cost",
        title="Total cost by namespace",
    )
    namespace_fig.update_traces(
        hovertemplate=(
            "Namespace: %{x}<br>Total cost: "
            + CURRENCY_PREFIX
            + "%{y:,.2f}<extra></extra>"
        )
    )
    namespace_fig.update_layout(
        yaxis_title="Cost (" + CURRENCY_PREFIX + ")",
        yaxis={"tickprefix": CURRENCY_PREFIX, "tickformat": CURRENCY_TICK_FORMAT},
    )
    st.plotly_chart(namespace_fig, width="stretch")

    if anom_f.empty:
        st.info("No anomalies found for the selected filters.")
        return

    st.subheader("Anomaly details")
    anomaly_columns = [
        "anomaly_date",
        "project_name",
        "cluster_name",
        "namespace_name",
        "severity",
        "actual_value",
        "moving_average",
        "threshold_value",
        "method",
    ]
    anomaly_table = anom_f[anomaly_columns].copy()
    for cost_column in ["actual_value", "moving_average", "threshold_value"]:
        anomaly_table[cost_column] = anomaly_table[cost_column].map(format_euro)

    st.dataframe(anomaly_table, width="stretch", hide_index=True)

    anomaly_namespace_keys = anom_f[
        ["project_name", "cluster_name", "namespace_name"]
    ].drop_duplicates()
    anomaly_cost_series = costs_f.merge(
        anomaly_namespace_keys,
        on=["project_name", "cluster_name", "namespace_name"],
        how="inner",
    ).sort_values("cost_date")
    anomaly_cost_series["moving_average"] = anomaly_cost_series.groupby(
        ["project_name", "cluster_name", "namespace_name"]
    )["total_cost"].transform(
        lambda values: values.shift(1).rolling(window=7, min_periods=7).mean()
    )
    anomaly_cost_series["threshold_value"] = anomaly_cost_series["moving_average"] * threshold_factor

    st.subheader("Namespace costs")
    min_anomaly_chart_date = anomaly_cost_series["cost_date"].min().date()
    max_anomaly_chart_date = anomaly_cost_series["cost_date"].max().date()
    anomaly_range_mode = st.radio(
        "Anomaly chart range",
        ["All data", "Custom range"],
        horizontal=True,
    )
    anomaly_chart_start_date = min_anomaly_chart_date
    anomaly_chart_end_date = max_anomaly_chart_date

    if anomaly_range_mode == "Custom range":
        selected_anomaly_range = st.date_input(
            "Anomaly chart date range",
            value=(min_anomaly_chart_date, max_anomaly_chart_date),
            min_value=min_anomaly_chart_date,
            max_value=max_anomaly_chart_date,
        )
        if (
            isinstance(selected_anomaly_range, (list, tuple))
            and len(selected_anomaly_range) == 2
        ):
            anomaly_chart_start_date, anomaly_chart_end_date = selected_anomaly_range

    if anomaly_chart_start_date > anomaly_chart_end_date:
        anomaly_chart_start_date, anomaly_chart_end_date = (
            anomaly_chart_end_date,
            anomaly_chart_start_date,
        )

    anomaly_chart_start_timestamp = pd.Timestamp(anomaly_chart_start_date)
    anomaly_chart_end_timestamp = pd.Timestamp(anomaly_chart_end_date)
    anomaly_cost_series = anomaly_cost_series[
        anomaly_cost_series["cost_date"].between(
            anomaly_chart_start_timestamp,
            anomaly_chart_end_timestamp,
        )
    ]

    anomaly_value_fig = go.Figure()
    moving_average_range = (
        anomaly_cost_series.dropna(subset=["moving_average"])
        .groupby("cost_date", as_index=False)
        .agg(
            moving_average_low=("moving_average", "min"),
            moving_average_high=("moving_average", "max"),
        )
    )
    if not moving_average_range.empty:
        anomaly_value_fig.add_trace(
            go.Scatter(
                x=moving_average_range["cost_date"],
                y=moving_average_range["moving_average_high"],
                mode="lines",
                name="Moving average baseline upper edge",
                legendgroup="moving_average_range",
                showlegend=False,
                line={"width": 0, "color": "rgba(107, 114, 128, 0)"},
                hoverinfo="skip",
            )
        )
        anomaly_value_fig.add_trace(
            go.Scatter(
                x=moving_average_range["cost_date"],
                y=moving_average_range["moving_average_low"],
                mode="lines",
                name="Moving average baseline",
                legendgroup="moving_average_range",
                fill="tonexty",
                fillcolor="rgba(107, 114, 128, 0.10)",
                line={"width": 0, "color": "rgba(107, 114, 128, 0)"},
                hoverinfo="skip",
            )
        )
    threshold_range = (
        anomaly_cost_series.dropna(subset=["threshold_value"])
        .groupby("cost_date", as_index=False)
        .agg(
            threshold_low=("threshold_value", "min"),
            threshold_high=("threshold_value", "max"),
        )
    )
    if not threshold_range.empty:
        anomaly_value_fig.add_trace(
            go.Scatter(
                x=threshold_range["cost_date"],
                y=threshold_range["threshold_high"],
                mode="lines",
                name="Threshold range upper edge",
                legendgroup="threshold_range",
                showlegend=False,
                line={"width": 0, "color": "rgba(245, 158, 11, 0)"},
                hoverinfo="skip",
            )
        )
        anomaly_value_fig.add_trace(
            go.Scatter(
                x=threshold_range["cost_date"],
                y=threshold_range["threshold_low"],
                mode="lines",
                name="Threshold range",
                legendgroup="threshold_range",
                fill="tonexty",
                fillcolor="rgba(245, 158, 11, 0.12)",
                line={"width": 0, "color": "rgba(245, 158, 11, 0)"},
                hoverinfo="skip",
            )
        )

    grouped_cost_series = anomaly_cost_series.groupby(
        ["project_name", "cluster_name", "namespace_name"],
        sort=False,
    )
    for index, ((project_name, cluster_name, namespace_name), namespace_costs) in enumerate(
        grouped_cost_series
    ):
        namespace_label = f"{project_name}/{cluster_name}/{namespace_name}"
        namespace_color = NAMESPACE_COLORS[index % len(NAMESPACE_COLORS)]
        anomaly_value_fig.add_trace(
            go.Scatter(
                x=namespace_costs["cost_date"],
                y=namespace_costs["total_cost"],
                mode="lines",
                name=f" {namespace_label}",
                legendgroup=f"actual_cost_{namespace_label}",
                line={"color": namespace_color, "width": 2},
                customdata=namespace_costs[
                    ["project_name", "cluster_name", "namespace_name"]
                ],
                hovertemplate=(
                    "Date: %{x}<br>"
                    "Project: %{customdata[0]}<br>"
                    "Cluster: %{customdata[1]}<br>"
                    "Namespace: %{customdata[2]}<br>"
                    "Actual cost: "
                    + CURRENCY_PREFIX
                    + "%{y:,.2f}"
                    "<extra></extra>"
                ),
            )
        )
        namespace_anomalies = anom_f[
            (anom_f["project_name"] == project_name)
            & (anom_f["cluster_name"] == cluster_name)
            & (anom_f["namespace_name"] == namespace_name)
        ].sort_values("anomaly_date")
        namespace_anomalies = namespace_anomalies[
            namespace_anomalies["anomaly_date"].between(
                anomaly_chart_start_timestamp,
                anomaly_chart_end_timestamp,
            )
        ]
        if namespace_anomalies.empty:
            continue

        anomaly_value_fig.add_trace(
            go.Scatter(
                x=namespace_anomalies["anomaly_date"],
                y=namespace_anomalies["actual_value"],
                mode="markers",
                name=f"Anomaly: {namespace_label}",
                legendgroup=f"actual_cost_{namespace_label}",
                showlegend=False,
                marker={
                    "size": 11,
                    "color": namespace_anomalies["severity"].map(SEVERITY_COLORS),
                    "line": {"color": namespace_color, "width": 2},
                },
                customdata=namespace_anomalies[
                    ["project_name", "cluster_name", "namespace_name", "severity"]
                ],
                hovertemplate=(
                    "Date: %{x}<br>"
                    "Project: %{customdata[0]}<br>"
                    "Cluster: %{customdata[1]}<br>"
                    "Namespace: %{customdata[2]}<br>"
                    "Severity: %{customdata[3]}<br>"
                    "Anomaly value: "
                    + CURRENCY_PREFIX
                    + "%{y:,.2f}"
                    "<extra></extra>"
                ),
            )
        )
    anomaly_value_fig.update_layout(
        title="Namespace costs",
        xaxis_title="Date",
        yaxis_title="Namespace cost (" + CURRENCY_PREFIX + ")",
        yaxis={"tickprefix": CURRENCY_PREFIX, "tickformat": CURRENCY_TICK_FORMAT},
        height=650,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.5,
        },
        margin={"b": 150},
    )
    st.plotly_chart(anomaly_value_fig, width="stretch")

    anomalies_by_namespace = (
        anom_f.groupby("namespace_series", as_index=False)
        .agg(
            anomaly_count=("anomaly_id", "count"),
            max_actual_value=("actual_value", "max"),
            avg_moving_average=("moving_average", "mean"),
        )
        .sort_values("anomaly_count", ascending=False)
    )
    anomaly_fig = px.bar(
        anomalies_by_namespace,
        x="namespace_series",
        y="anomaly_count",
        hover_data=["max_actual_value", "avg_moving_average"],
        title="Anomalies by namespace",
    )
    anomaly_fig.update_traces(
        hovertemplate=(
            "Namespace: %{x}<br>"
            "Anomalies: %{y}<br>"
            "Max actual value: "
            + CURRENCY_PREFIX
            + "%{customdata[0]:,.2f}<br>"
            "Average moving average: "
            + CURRENCY_PREFIX
            + "%{customdata[1]:,.2f}"
            "<extra></extra>"
        )
    )
    st.plotly_chart(anomaly_fig, width="stretch")

    severity_fig = px.bar(
        anom_f.groupby("severity", as_index=False)
        .size()
        .rename(columns={"size": "anomaly_count"}),
        x="severity",
        y="anomaly_count",
        category_orders={"severity": SEVERITY_ORDER},
        color="severity",
        color_discrete_map=SEVERITY_COLORS,
        title="Anomalies by severity",
    )
    severity_fig.update_traces(
        hovertemplate="Severity: %{x}<br>Anomalies: %{y}<extra></extra>"
    )
    st.plotly_chart(severity_fig, width="stretch")


if __name__ == "__main__":
    build_dashboard()
