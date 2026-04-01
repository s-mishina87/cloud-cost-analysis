"""Structured synthetic data generator for the agreed v1 domain model.

This module creates realistic local test data for:
Project -> Cluster -> Namespace -> NamespaceCost inputs.
Overhead is generated per cluster/day and distributed later by allocation logic.
"""

from __future__ import annotations

from datetime import date, timedelta
from random import Random


PROJECT_NAME_POOL = [
    "retail-prod",
    "retail-dev",
    "retail-staging",
    "platform-prod",
    "platform-dev",
    "payments-prod",
    "payments-staging",
    "analytics-prod",
    "analytics-dev",
    "customer-prod",
]

CLUSTER_NAME_POOL = [
    "main",
    "shared",
    "core",
    "services",
    "backend",
    "frontend",
    "integration",
    "data",
    "monitoring",
    "internal",
]

SYSTEM_NAMESPACES = ["monitoring", "logging", "security", "ingress", "ci-runner"]
APPLICATION_NAMESPACES = ["frontend", "checkout", "payments", "catalog", "orders", "customer-api", "search"]


def _pick_cluster_names(rng: Random, count: int) -> list[str]:
    """Pick unique cluster names from the agreed name pool."""
    return rng.sample(CLUSTER_NAME_POOL, k=count)


def _pick_namespace_names(rng: Random, count: int) -> list[str]:
    """Build a namespace mix with both system and application namespaces."""
    system_count = max(2, count // 3)
    app_count = count - system_count

    chosen_system = rng.sample(SYSTEM_NAMESPACES, k=min(system_count, len(SYSTEM_NAMESPACES)))
    chosen_app = rng.sample(APPLICATION_NAMESPACES, k=min(app_count, len(APPLICATION_NAMESPACES)))

    names = chosen_system + chosen_app
    if "payments" not in names and len(names) < count:
        names.append("payments")
    if "checkout" not in names and len(names) < count:
        names.append("checkout")
    if "monitoring" not in names and len(names) < count:
        names.append("monitoring")

    while len(names) < count:
        fallback = rng.choice(APPLICATION_NAMESPACES + SYSTEM_NAMESPACES)
        if fallback not in names:
            names.append(fallback)

    rng.shuffle(names)
    return names[:count]


def _is_system_namespace(namespace_name: str) -> bool:
    return namespace_name in SYSTEM_NAMESPACES


def _namespace_base_cost(namespace_name: str, namespace_type: str, rng: Random) -> float:
    """Return a realistic baseline where application namespaces tend to cost more."""
    if namespace_name in {"payments", "checkout", "orders", "catalog"}:
        return rng.uniform(65.0, 95.0)
    if namespace_type == "system":
        return rng.uniform(20.0, 40.0)
    return rng.uniform(35.0, 70.0)


def _usage_for_day(
    namespace_name: str,
    namespace_type: str,
    day_index: int,
    base_cost: float,
    rng: Random,
) -> float:
    """Generate daily usage cost with realistic variance and intentional anomalies."""
    variation = rng.uniform(-0.06, 0.06) if namespace_type == "system" else rng.uniform(-0.20, 0.20)
    value = base_cost * (1 + variation)

    # Intentional scenario 1: sharp spike for payments.
    if namespace_name == "payments" and day_index in {55, 56, 57}:
        value *= 3.0

    # Intentional scenario 2: gradual increase for monitoring.
    if namespace_name == "monitoring" and day_index >= 60:
        value += (day_index - 59) * 0.8

    # Intentional scenario 3: temporary jump for checkout.
    if namespace_name == "checkout" and 40 <= day_index <= 43:
        value += 45.0

    return round(max(value, 0.0), 2)


def generate_structured_data(
    days: int = 90,
    project_count: int = 3,
    clusters_per_project: int = 2,
    min_namespaces: int = 5,
    max_namespaces: int = 8,
    seed: int = 42,
) -> dict[str, list[dict]]:
    """Generate v1 entities and daily NamespaceCost inputs for the full pipeline."""
    rng = Random(seed)
    start_date = date.today() - timedelta(days=days - 1)

    project_names = PROJECT_NAME_POOL[:project_count]
    projects: list[dict] = [{"project_name": project_name} for project_name in project_names]

    clusters: list[dict] = []
    namespaces: list[dict] = []
    namespace_costs: list[dict] = []
    cluster_overheads: list[dict] = []

    for project_name in project_names:
        selected_clusters = _pick_cluster_names(rng, clusters_per_project)
        for cluster_name in selected_clusters:
            clusters.append({"project_name": project_name, "cluster_name": cluster_name})

            namespace_count = rng.randint(min_namespaces, max_namespaces)
            selected_namespaces = _pick_namespace_names(rng, namespace_count)
            namespace_meta: list[dict] = []

            for namespace_name in selected_namespaces:
                namespace_type = "system" if _is_system_namespace(namespace_name) else "application"
                namespace_row = {
                    "project_name": project_name,
                    "cluster_name": cluster_name,
                    "namespace_name": namespace_name,
                    "namespace_type": namespace_type,
                }
                namespaces.append(namespace_row)
                namespace_meta.append(
                    {
                        **namespace_row,
                        "base_cost": _namespace_base_cost(namespace_name, namespace_type, rng),
                    }
                )

            for day_index in range(days):
                current_date = (start_date + timedelta(days=day_index)).isoformat()

                day_rows: list[dict] = []
                for meta in namespace_meta:
                    usage_cost = _usage_for_day(
                        namespace_name=meta["namespace_name"],
                        namespace_type=meta["namespace_type"],
                        day_index=day_index,
                        base_cost=meta["base_cost"],
                        rng=rng,
                    )
                    row = {
                        "cost_date": current_date,
                        "project_name": meta["project_name"],
                        "cluster_name": meta["cluster_name"],
                        "namespace_name": meta["namespace_name"],
                        "usage_cost": usage_cost,
                        "overhead_cost": 0.0,
                        "total_cost": usage_cost,
                    }
                    day_rows.append(row)

                cluster_usage_total = sum(item["usage_cost"] for item in day_rows)
                overhead_rate = rng.uniform(0.14, 0.28)
                cluster_overhead_cost = round(cluster_usage_total * overhead_rate, 2)
                cluster_overheads.append(
                    {
                        "cost_date": current_date,
                        "project_name": project_name,
                        "cluster_name": cluster_name,
                        "cluster_overhead_cost": cluster_overhead_cost,
                    }
                )

                namespace_costs.extend(day_rows)

    return {
        "projects": projects,
        "clusters": clusters,
        "namespaces": namespaces,
        "namespace_costs": namespace_costs,
        "cluster_overheads": cluster_overheads,
    }
