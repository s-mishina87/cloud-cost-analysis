"""Overhead allocation for NamespaceCost records.

This module applies the agreed formula:
namespace_overhead = cluster_overhead * namespace_usage_share
where namespace_usage_share = namespace_usage / total_cluster_usage.
"""

from __future__ import annotations


def apply_overhead_allocation(namespace_costs: list[dict], cluster_overheads: list[dict]) -> list[dict]:
    """Distribute cluster overhead proportionally across namespaces for each day."""
    overhead_map = {
        (row["cost_date"], row["project_name"], row["cluster_name"]): float(row.get("cluster_overhead_cost", 0.0) or 0.0)
        for row in cluster_overheads
    }

    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in namespace_costs:
        key = (row["cost_date"], row["project_name"], row["cluster_name"])
        grouped.setdefault(key, []).append(row)

    allocated_rows: list[dict] = []

    for key, rows in grouped.items():
        sanitized_rows: list[dict] = []

        # Apply edge-case rules before allocation: missing -> 0, negative -> skip.
        for row in rows:
            usage_cost = float(row.get("usage_cost", 0.0) or 0.0)
            if usage_cost < 0:
                continue

            normalized = dict(row)
            normalized["usage_cost"] = round(usage_cost, 2)
            sanitized_rows.append(normalized)

        total_cluster_usage = sum(item["usage_cost"] for item in sanitized_rows)
        cluster_overhead_cost = max(0.0, overhead_map.get(key, 0.0))

        for row in sanitized_rows:
            if total_cluster_usage <= 0:
                overhead_cost = 0.0
            else:
                usage_share = row["usage_cost"] / total_cluster_usage
                overhead_cost = cluster_overhead_cost * usage_share

            row["overhead_cost"] = round(overhead_cost, 2)
            row["total_cost"] = round(row["usage_cost"] + row["overhead_cost"], 2)
            allocated_rows.append(row)

    return allocated_rows
