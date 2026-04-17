from datetime import date

from src.data_generator import (
    ANOMALY_CRITICAL_NAMESPACES,
    APPLICATION_NAMESPACES,
    CLUSTER_NAME_POOL,
    SYSTEM_NAMESPACES,
    generate_structured_data,
)


def test_generate_structured_data_returns_agreed_entities() -> None:
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


def test_generator_creates_90_days_per_namespace() -> None:
    dataset = generate_structured_data(days=90, project_count=3, clusters_per_project=2, seed=11)

    namespace_count = len(dataset["namespaces"])
    assert len(dataset["namespace_costs"]) == namespace_count * 90


def test_generator_uses_fixed_default_start_date_for_reproducibility() -> None:
    dataset = generate_structured_data(days=3, project_count=1, clusters_per_project=1, seed=5)
    dates = sorted({row["cost_date"] for row in dataset["namespace_costs"]})

    assert dates == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_generator_accepts_explicit_start_date() -> None:
    dataset = generate_structured_data(
        days=2,
        project_count=1,
        clusters_per_project=1,
        seed=5,
        start_date=date(2026, 4, 1),
    )
    dates = sorted({row["cost_date"] for row in dataset["namespace_costs"]})

    assert dates == ["2026-04-01", "2026-04-02"]


def test_cluster_pool_does_not_overlap_namespace_pools() -> None:
    namespace_names = set(SYSTEM_NAMESPACES) | set(APPLICATION_NAMESPACES)
    assert set(CLUSTER_NAME_POOL).isdisjoint(namespace_names)


def test_anomaly_critical_namespaces_are_present_in_every_cluster() -> None:
    dataset = generate_structured_data(days=5, project_count=3, clusters_per_project=2, seed=17)

    namespaces_by_cluster: dict[tuple[str, str], set[str]] = {}
    for row in dataset["namespaces"]:
        key = (row["project_name"], row["cluster_name"])
        namespaces_by_cluster.setdefault(key, set()).add(row["namespace_name"])

    for names in namespaces_by_cluster.values():
        assert set(ANOMALY_CRITICAL_NAMESPACES).issubset(names)


def test_generator_rejects_namespace_count_below_anomaly_requirements() -> None:
    try:
        generate_structured_data(
            days=3,
            project_count=1,
            clusters_per_project=1,
            min_namespaces=2,
            max_namespaces=2,
            seed=17,
        )
    except ValueError as exc:
        assert "min_namespaces must be >= 3" in str(exc)
    else:
        raise AssertionError("Expected ValueError when namespace count is below required anomaly namespaces")


def test_generator_rejects_invalid_project_count() -> None:
    try:
        generate_structured_data(project_count=0)
    except ValueError as exc:
        assert "project_count must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive project_count")

    try:
        generate_structured_data(project_count=999)
    except ValueError as exc:
        assert "project_count must be <=" in str(exc)
    else:
        raise AssertionError("Expected ValueError when project_count exceeds project pool")


def test_generator_rejects_invalid_clusters_per_project() -> None:
    try:
        generate_structured_data(clusters_per_project=0)
    except ValueError as exc:
        assert "clusters_per_project must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive clusters_per_project")

    try:
        generate_structured_data(clusters_per_project=999)
    except ValueError as exc:
        assert "clusters_per_project must be <=" in str(exc)
    else:
        raise AssertionError("Expected ValueError when clusters_per_project exceeds cluster pool")


def test_generator_rejects_invalid_namespace_bounds() -> None:
    try:
        generate_structured_data(min_namespaces=0)
    except ValueError as exc:
        assert "min_namespaces must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive min_namespaces")

    try:
        generate_structured_data(max_namespaces=0)
    except ValueError as exc:
        assert "max_namespaces must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive max_namespaces")

    try:
        generate_structured_data(min_namespaces=7, max_namespaces=5)
    except ValueError as exc:
        assert "min_namespaces must be <= max_namespaces" in str(exc)
    else:
        raise AssertionError("Expected ValueError when min_namespaces is greater than max_namespaces")
