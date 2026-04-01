from src.data_generator import generate_structured_data


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
