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
    "cluster-eu-west-1",
    "cluster-eu-central-1",
    "cluster-us-east-1",
    "cluster-us-west-2",
    "cluster-ap-south-1",
    "cluster-sa-east-1",
    "cluster-shared-a",
    "cluster-shared-b",
    "cluster-batch-a",
    "cluster-batch-b",
]

SYSTEM_NAMESPACES = ["monitoring", "logging", "security", "ingress", "ci-runner"]
APPLICATION_NAMESPACES = ["frontend", "checkout", "payments", "catalog", "orders", "customer-api", "search"]
ANOMALY_CRITICAL_NAMESPACES = ["payments", "checkout", "monitoring"]
DEFAULT_START_DATE = date(2026, 1, 1)


def _pick_cluster_names(rng: Random, count: int) -> list[str]:
    """Pick unique cluster names from the agreed name pool."""
    return rng.sample(CLUSTER_NAME_POOL, k=count)


def _pick_namespace_names(rng: Random, count: int) -> list[str]:
    """Build namespace names and always include anomaly-critical namespaces."""
    if count < len(ANOMALY_CRITICAL_NAMESPACES):
        raise ValueError(
            f"count must be >= {len(ANOMALY_CRITICAL_NAMESPACES)} to include all anomaly-critical namespaces"
        )

    all_candidates = SYSTEM_NAMESPACES + APPLICATION_NAMESPACES
    remaining_candidates = [name for name in all_candidates if name not in ANOMALY_CRITICAL_NAMESPACES]
    extra_count = count - len(ANOMALY_CRITICAL_NAMESPACES)
    selected_extra = rng.sample(remaining_candidates, k=extra_count)

    names = ANOMALY_CRITICAL_NAMESPACES + selected_extra
    rng.shuffle(names)
    return names


def _is_system_namespace(namespace_name: str) -> bool:
    return namespace_name in SYSTEM_NAMESPACES


def _validate_generation_inputs(
    days: int,
    project_count: int,
    clusters_per_project: int,
    min_namespaces: int,
    max_namespaces: int,
) -> None:
    """Validate generator inputs and fail fast with beginner-friendly errors."""
    if days <= 0:
        raise ValueError("days must be > 0")
    if project_count <= 0:
        raise ValueError("project_count must be > 0")
    if project_count > len(PROJECT_NAME_POOL):
        raise ValueError(f"project_count must be <= {len(PROJECT_NAME_POOL)}")

    if clusters_per_project <= 0:
        raise ValueError("clusters_per_project must be > 0")
    if clusters_per_project > len(CLUSTER_NAME_POOL):
        raise ValueError(f"clusters_per_project must be <= {len(CLUSTER_NAME_POOL)}")

    if min_namespaces <= 0:
        raise ValueError("min_namespaces must be > 0")
    if max_namespaces <= 0:
        raise ValueError("max_namespaces must be > 0")
    if min_namespaces > max_namespaces:
        raise ValueError("min_namespaces must be <= max_namespaces")

    namespace_capacity = len(set(SYSTEM_NAMESPACES + APPLICATION_NAMESPACES))
    if max_namespaces > namespace_capacity:
        raise ValueError(f"max_namespaces must be <= {namespace_capacity}")
    if min_namespaces < len(ANOMALY_CRITICAL_NAMESPACES):
        raise ValueError(
            f"min_namespaces must be >= {len(ANOMALY_CRITICAL_NAMESPACES)} to include anomaly-critical namespaces"
        )


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
    start_date: date | None = None,
) -> dict[str, list[dict]]:
    """Generate v1 entities and daily NamespaceCost inputs for the full pipeline.

    By default, generation starts from a fixed calendar date to keep datasets
    fully reproducible across different execution days. Pass ``start_date`` to
    anchor output to another date while keeping deterministic values.
    """
    _validate_generation_inputs(
        days=days,
        project_count=project_count,
        clusters_per_project=clusters_per_project,
        min_namespaces=min_namespaces,
        max_namespaces=max_namespaces,
    )

    rng = Random(seed)
    effective_start_date = start_date or DEFAULT_START_DATE

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
                current_date = (effective_start_date + timedelta(days=day_index)).isoformat()

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
