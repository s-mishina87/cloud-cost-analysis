from src.allocation import apply_overhead_allocation


def test_apply_overhead_allocation_distributes_proportionally() -> None:
    namespace_costs = [
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "payments",
            "usage_cost": 80.0,
            "overhead_cost": 0.0,
            "total_cost": 80.0,
        },
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "checkout",
            "usage_cost": 20.0,
            "overhead_cost": 0.0,
            "total_cost": 20.0,
        },
    ]
    cluster_overheads = [
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "cluster_overhead_cost": 50.0,
        }
    ]

    allocated = apply_overhead_allocation(namespace_costs, cluster_overheads)

    by_namespace = {row["namespace_name"]: row for row in allocated}
    assert by_namespace["payments"]["overhead_cost"] == 40.0
    assert by_namespace["checkout"]["overhead_cost"] == 10.0
    assert by_namespace["payments"]["total_cost"] == 120.0
    assert by_namespace["checkout"]["total_cost"] == 30.0


def test_apply_overhead_allocation_zero_usage_sets_zero_overhead() -> None:
    namespace_costs = [
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "monitoring",
            "usage_cost": 0.0,
            "overhead_cost": 0.0,
            "total_cost": 0.0,
        }
    ]
    cluster_overheads = [
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "cluster_overhead_cost": 30.0,
        }
    ]

    allocated = apply_overhead_allocation(namespace_costs, cluster_overheads)

    assert allocated[0]["overhead_cost"] == 0.0
    assert allocated[0]["total_cost"] == 0.0
