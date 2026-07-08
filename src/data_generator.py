"""Generate synthetic cloud cost data for the pipeline.

It creates projects, clusters, namespaces, namespace costs, and cluster
overhead. The overhead is allocated later in allocation.py.
"""

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


def _pick_cluster_names(rng: Random, count: int):
    """Pick unique cluster names from the name list."""
    return rng.sample(CLUSTER_NAME_POOL, k=count)


def _pick_namespace_names(rng: Random, count: int):
    """Pick namespace names and always include the anomaly namespaces."""
    if count < len(ANOMALY_CRITICAL_NAMESPACES):
        raise ValueError(
            f"count must be >= {len(ANOMALY_CRITICAL_NAMESPACES)} to include all anomaly-critical namespaces"
        )

    all_ns = SYSTEM_NAMESPACES + APPLICATION_NAMESPACES
    rest_ns = [name for name in all_ns if name not in ANOMALY_CRITICAL_NAMESPACES]
    extra_n = count - len(ANOMALY_CRITICAL_NAMESPACES)
    extra_ns = rng.sample(rest_ns, k=extra_n)

    names = ANOMALY_CRITICAL_NAMESPACES + extra_ns
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
    """Check if the generator inputs are valid."""
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

    ns_cap = len(set(SYSTEM_NAMESPACES + APPLICATION_NAMESPACES))
    if max_namespaces > ns_cap:
        raise ValueError(f"max_namespaces must be <= {ns_cap}")
    if min_namespaces < len(ANOMALY_CRITICAL_NAMESPACES):
        raise ValueError(
            f"min_namespaces must be >= {len(ANOMALY_CRITICAL_NAMESPACES)} to include anomaly-critical namespaces"
        )


def _namespace_base_cost(namespace_name: str, namespace_type: str, rng: Random) -> float:
    """Return a base cost for one namespace.

    Payments and checkout are a bit larger so their anomaly cases are easier to see.
    """
    if namespace_name in {"payments", "checkout"}:
        return rng.uniform(150.0, 200.0)
    if namespace_name in {"orders", "catalog"}:
        return rng.uniform(80.0, 120.0)
    if namespace_name == "monitoring":
        return rng.uniform(50.0, 70.0)
    if namespace_type == "system":
        return rng.uniform(12.0, 25.0)
    return rng.uniform(35.0, 60.0)


def _usage_for_day(
    namespace_name: str,
    namespace_type: str,
    day_index: int,
    base_cost: float,
    rng: Random,
    day_of_week: int,
) -> float:
    """Generate one daily usage value with normal variation and planned anomalies."""
    if namespace_name == "monitoring" or namespace_type == "system":
        variation = rng.uniform(-0.06, 0.06)
    elif namespace_name in {"payments", "checkout", "search"}:
        variation = rng.uniform(-0.20, 0.20)
    elif namespace_name in {"orders", "catalog"}:
        variation = rng.uniform(-0.12, 0.12)
    else:
        variation = rng.uniform(-0.18, 0.18)

    value = base_cost * (1 + variation)

    if day_of_week >= 5:
        if namespace_type == "system":
            value *= rng.uniform(0.88, 0.96)
        else:
            value *= rng.uniform(0.60, 0.75)

    if namespace_name == "payments" and day_index in {55, 56, 57}:
        value *= 3.0

    if namespace_name == "monitoring" and day_index >= 60:
        value += (day_index - 59) * 0.8

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
):
    """Generate input data for the full pipeline.

    A fixed seed and start date help keep tests and demos consistent.
    """
    _validate_generation_inputs(
        days=days,
        project_count=project_count,
        clusters_per_project=clusters_per_project,
        min_namespaces=min_namespaces,
        max_namespaces=max_namespaces,
    )

    rng = Random(seed)
    start = start_date or DEFAULT_START_DATE

    proj_names = PROJECT_NAME_POOL[:project_count]
    projects = [{"project_name": name} for name in proj_names]

    clusters = []
    namespaces = []
    namespace_costs = []
    cluster_overheads = []

    for project_name in proj_names:
        cl_names = _pick_cluster_names(rng, clusters_per_project)
        for cluster_name in cl_names:
            clusters.append({"project_name": project_name, "cluster_name": cluster_name})

            ns_count = rng.randint(min_namespaces, max_namespaces)
            ns_names = _pick_namespace_names(rng, ns_count)
            ns_meta = []

            for namespace_name in ns_names:
                ns_type = "system" if _is_system_namespace(namespace_name) else "application"
                ns_row = {
                    "project_name": project_name,
                    "cluster_name": cluster_name,
                    "namespace_name": namespace_name,
                    "namespace_type": ns_type,
                }
                namespaces.append(ns_row)
                ns_meta.append(
                    {
                        **ns_row,
                        "base_cost": _namespace_base_cost(namespace_name, ns_type, rng),
                    }
                )

            for day_index in range(days):
                dt_obj = start + timedelta(days=day_index)
                dt = dt_obj.isoformat()
                dow = dt_obj.weekday()

                day_rows = []
                for meta in ns_meta:
                    usage_cost = _usage_for_day(
                        namespace_name=meta["namespace_name"],
                        namespace_type=meta["namespace_type"],
                        day_index=day_index,
                        base_cost=meta["base_cost"],
                        rng=rng,
                        day_of_week=dow,
                    )
                    row = {
                        "cost_date": dt,
                        "project_name": meta["project_name"],
                        "cluster_name": meta["cluster_name"],
                        "namespace_name": meta["namespace_name"],
                        "usage_cost": usage_cost,
                        "overhead_cost": 0.0,
                        "total_cost": usage_cost,
                    }
                    day_rows.append(row)

                usage_sum = sum(item["usage_cost"] for item in day_rows)
                oh_rate = rng.uniform(0.14, 0.28)
                oh_cost = round(usage_sum * oh_rate, 2)
                cluster_overheads.append(
                    {
                        "cost_date": dt,
                        "project_name": project_name,
                        "cluster_name": cluster_name,
                        "cluster_overhead_cost": oh_cost,
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
