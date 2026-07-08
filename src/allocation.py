"""Split cluster overhead across NamespaceCost records."""


def apply_overhead_allocation(namespace_costs, cluster_overheads):
    """Split cluster overhead across namespaces by usage share per day."""
    overhead_map = {
        (row["cost_date"], row["project_name"], row["cluster_name"]): float(row.get("cluster_overhead_cost") or 0.0)
        for row in cluster_overheads
    }

    grouped = {}
    for row in namespace_costs:
        key = (row["cost_date"], row["project_name"], row["cluster_name"])
        grouped.setdefault(key, []).append(row)

    result = []
    for key, rows in grouped.items():
        total_usage = sum(float(r["usage_cost"]) for r in rows)
        overhead = overhead_map.get(key, 0.0)
        for row in rows:
            usage = round(float(row["usage_cost"]), 2)
            share = usage / total_usage if total_usage > 0 else 0.0
            updated = dict(row)
            updated["usage_cost"] = usage
            updated["overhead_cost"] = round(overhead * share, 2)
            updated["total_cost"] = round(usage + overhead * share, 2)
            result.append(updated)

    return result
