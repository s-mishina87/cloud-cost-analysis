import pytest
from datetime import date, timedelta

from src.data_generator import (
    ANOMALY_CRITICAL_NAMESPACES,
    APPLICATION_NAMESPACES,
    CLUSTER_NAME_POOL,
    DEFAULT_START_DATE,
    SYSTEM_NAMESPACES,
    generate_structured_data,
)


def test_generate_structured_data_returns_agreed_entities():
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=7)

    assert {"projects", "clusters", "namespaces", "namespace_costs", "cluster_overheads"}.issubset(dataset)
    assert len(dataset["projects"]) == 3
    assert len(dataset["clusters"]) == 6
    assert len(dataset["namespaces"]) >= 30
    assert len(dataset["namespaces"]) <= 48

    first_cost = dataset["namespace_costs"][0]
    assert {
        "cost_date",
        "project_name",
        "cluster_name",
        "namespace_name",
        "usage_cost",
        "overhead_cost",
        "total_cost",
    }.issubset(first_cost)


def test_generator_creates_90_days_per_namespace():
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=11)

    namespace_count = len(dataset["namespaces"])
    assert len(dataset["namespace_costs"]) == namespace_count * 90


def test_generator_uses_fixed_default_start_date_for_reproducibility():
    dataset = generate_structured_data(days=3, project_count=1, clusters_per_project=1, seed=5)
    dates = sorted({row["cost_date"] for row in dataset["namespace_costs"]})

    assert dates == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_generator_accepts_explicit_start_date():
    dataset = generate_structured_data(
        days=2,
        project_count=1,
        clusters_per_project=1,
        seed=5,
        start_date=date(2026, 4, 1),
    )
    dates = sorted({row["cost_date"] for row in dataset["namespace_costs"]})

    assert dates == ["2026-04-01", "2026-04-02"]


def test_cluster_pool_does_not_overlap_namespace_pools():
    namespace_names = set(SYSTEM_NAMESPACES) | set(APPLICATION_NAMESPACES)
    assert set(CLUSTER_NAME_POOL).isdisjoint(namespace_names)


def test_anomaly_critical_namespaces_are_present_in_every_cluster():
    dataset = generate_structured_data(days=5, project_count=3, clusters_per_project=2, seed=17)

    namespaces_by_cluster = {}
    for row in dataset["namespaces"]:
        key = (row["project_name"], row["cluster_name"])
        namespaces_by_cluster.setdefault(key, set()).add(row["namespace_name"])

    for names in namespaces_by_cluster.values():
        assert set(ANOMALY_CRITICAL_NAMESPACES).issubset(names)


def test_generator_rejects_namespace_count_below_anomaly_requirements():
    with pytest.raises(ValueError, match="min_namespaces must be >= 3"):
        generate_structured_data(
            days=3,
            project_count=1,
            clusters_per_project=1,
            min_namespaces=2,
            max_namespaces=2,
            seed=17,
        )


def test_generator_rejects_invalid_project_count():
    with pytest.raises(ValueError, match="project_count must be > 0"):
        generate_structured_data(project_count=0)
    with pytest.raises(ValueError, match="project_count must be <="):
        generate_structured_data(project_count=999)


def test_generator_rejects_invalid_clusters_per_project():
    with pytest.raises(ValueError, match="clusters_per_project must be > 0"):
        generate_structured_data(clusters_per_project=0)
    with pytest.raises(ValueError, match="clusters_per_project must be <="):
        generate_structured_data(clusters_per_project=999)


def test_generator_rejects_invalid_namespace_bounds():
    with pytest.raises(ValueError, match="min_namespaces must be > 0"):
        generate_structured_data(min_namespaces=0)
    with pytest.raises(ValueError, match="max_namespaces must be > 0"):
        generate_structured_data(max_namespaces=0)
    with pytest.raises(ValueError, match="min_namespaces must be <= max_namespaces"):
        generate_structured_data(min_namespaces=7, max_namespaces=5)


# ---------------------------------------------------------------------------
# Realistic data shape tests (TDD for generator improvements)
# ---------------------------------------------------------------------------


def _cv(costs):
    """Coefficient of variation: std / mean. Lower means more stable."""
    n = len(costs)
    if n < 2:
        return float("inf")
    mean = sum(costs) / n
    if mean == 0:
        return float("inf")
    variance = sum((c - mean) ** 2 for c in costs) / n
    return variance ** 0.5 / mean


def _avg_cost_by_namespace(dataset):
    """Return mean usage_cost per namespace name across all projects, clusters and days."""
    totals = {}
    for row in dataset["namespace_costs"]:
        totals.setdefault(row["namespace_name"], []).append(row["usage_cost"])
    return {ns: sum(v) / len(v) for ns, v in totals.items()}


def test_payments_and_checkout_are_among_larger_namespaces():
    """Payments and checkout should be clearly in the top tier by average cost.

    They are the anomaly-critical application namespaces and should dominate
    spend so that spike and jump scenarios stand out against a realistic baseline.
    """
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)
    avg_by_ns = _avg_cost_by_namespace(dataset)
    sorted_ns = sorted(avg_by_ns, key=lambda n: avg_by_ns[n], reverse=True)
    top_names = set(sorted_ns[:4])  # lenient: top-4 out of all namespaces

    assert "payments" in top_names, f"payments not in top-4 by avg cost; ranked: {sorted_ns}"
    assert "checkout" in top_names, f"checkout not in top-4 by avg cost; ranked: {sorted_ns}"


def test_visible_size_hierarchy():
    """The top-2 namespaces by average cost should be at least 3x more expensive
    than the bottom-3, creating the few-large / many-small pattern.
    """
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)
    avg_by_ns = _avg_cost_by_namespace(dataset)
    sorted_avgs = sorted(avg_by_ns.values(), reverse=True)

    top_2_avg = sum(sorted_avgs[:2]) / 2
    bottom_3_avg = sum(sorted_avgs[-3:]) / 3

    assert top_2_avg > bottom_3_avg * 3, (
        f"Hierarchy too flat: top-2 avg={top_2_avg:.2f}, bottom-3 avg={bottom_3_avg:.2f}"
    )


def test_monitoring_is_more_stable_than_application_namespaces():
    """Monitoring (system-like) should have lower day-to-day variability than
    application namespaces.

    Uses only the first 30 days to avoid the intentional gradual-increase
    scenario inflating monitoring's coefficient of variation.
    """
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)

    cutoff = (DEFAULT_START_DATE + timedelta(days=30)).isoformat()
    costs_by_ns = {}
    for row in dataset["namespace_costs"]:
        if row["cost_date"] < cutoff:
            costs_by_ns.setdefault(row["namespace_name"], []).append(row["usage_cost"])

    monitoring_cv = _cv(costs_by_ns.get("monitoring", []))

    app_cvs = [
        _cv(costs)
        for ns, costs in costs_by_ns.items()
        if ns in APPLICATION_NAMESPACES
    ]
    assert app_cvs, "No application namespaces found in first-30-day window"
    avg_app_cv = sum(app_cvs) / len(app_cvs)

    assert monitoring_cv < avg_app_cv, (
        f"Expected monitoring (CV={monitoring_cv:.3f}) < application avg (CV={avg_app_cv:.3f})"
    )


def test_weekday_costs_higher_than_weekend_costs():
    """Average usage cost on weekdays should exceed the weekend average.

    This reflects lower application traffic on Saturdays and Sundays.
    """
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)

    weekday_costs = []
    weekend_costs = []
    for row in dataset["namespace_costs"]:
        d = date.fromisoformat(row["cost_date"])
        if d.weekday() < 5:  # Monday=0 … Friday=4
            weekday_costs.append(row["usage_cost"])
        else:
            weekend_costs.append(row["usage_cost"])

    avg_weekday = sum(weekday_costs) / len(weekday_costs)
    avg_weekend = sum(weekend_costs) / len(weekend_costs)

    assert avg_weekday > avg_weekend, (
        f"Expected weekday avg ({avg_weekday:.2f}) > weekend avg ({avg_weekend:.2f})"
    )


def test_payments_spike_anomaly_is_clearly_elevated():
    """Days 55-57 should show a sharp spike in payments cost versus the baseline.

    The generator multiplies payments by 3x on those days; even accounting for
    normal noise the spike should be well above 2x the non-spike average.
    """
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)

    spike_dates = {
        (DEFAULT_START_DATE + timedelta(days=d)).isoformat() for d in (55, 56, 57)
    }

    spike_costs = []
    normal_costs = []
    for row in dataset["namespace_costs"]:
        if row["namespace_name"] != "payments":
            continue
        (spike_costs if row["cost_date"] in spike_dates else normal_costs).append(row["usage_cost"])

    avg_spike = sum(spike_costs) / len(spike_costs)
    avg_normal = sum(normal_costs) / len(normal_costs)

    assert avg_spike > avg_normal * 2.0, (
        f"payments spike avg={avg_spike:.2f} should be >2x normal avg={avg_normal:.2f}"
    )


def test_checkout_jump_anomaly_is_elevated():
    """Days 40-43 should show elevated checkout cost versus other days.

    The generator adds a fixed upward jump on those days; on average the
    spike window should be at least 10 % above the non-spike average.
    """
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)

    jump_dates = {
        (DEFAULT_START_DATE + timedelta(days=d)).isoformat() for d in range(40, 44)
    }

    jump_costs = []
    normal_costs = []
    for row in dataset["namespace_costs"]:
        if row["namespace_name"] != "checkout":
            continue
        (jump_costs if row["cost_date"] in jump_dates else normal_costs).append(row["usage_cost"])

    avg_jump = sum(jump_costs) / len(jump_costs)
    avg_normal = sum(normal_costs) / len(normal_costs)

    assert avg_jump > avg_normal * 1.10, (
        f"checkout jump avg={avg_jump:.2f} should be >1.10x normal avg={avg_normal:.2f}"
    )


def test_monitoring_gradual_increase_anomaly_exists():
    """Monitoring costs after day 60 should be visibly higher than before day 60.

    The generator adds a linear increment starting at day_index 60, so the
    second period's average should exceed the first period's average.
    """
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=42)

    boundary = (DEFAULT_START_DATE + timedelta(days=60)).isoformat()

    before = []
    after = []
    for row in dataset["namespace_costs"]:
        if row["namespace_name"] != "monitoring":
            continue
        (after if row["cost_date"] >= boundary else before).append(row["usage_cost"])

    avg_before = sum(before) / len(before)
    avg_after = sum(after) / len(after)

    assert avg_after > avg_before * 1.10, (
        f"monitoring after-day-60 avg={avg_after:.2f} should be >1.10x before avg={avg_before:.2f}"
    )
