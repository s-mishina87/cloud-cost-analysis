from src.anomaly_detection import detect_anomalies


def _record(day: int, total_cost: float, namespace_name: str = "payments") -> dict:
    return {
        "cost_date": f"2026-01-{day:02d}",
        "project_name": "retail-prod",
        "cluster_name": "main",
        "namespace_name": namespace_name,
        "usage_cost": max(total_cost - 10.0, 0.0),
        "overhead_cost": 10.0,
        "total_cost": total_cost,
    }


def test_returns_empty_for_empty_input() -> None:
    assert detect_anomalies([]) == []


def test_detects_spike_above_moving_average_threshold() -> None:
    records = [
        _record(1, 10.0),
        _record(2, 10.0),
        _record(3, 10.0),
        _record(4, 10.0),
        _record(5, 10.0),
        _record(6, 10.0),
        _record(7, 10.0),
        _record(8, 16.0),
    ]

    anomalies = detect_anomalies(records, window_size=7, deviation_factor=1.5)

    assert len(anomalies) == 1
    assert anomalies[0]["cost_date"] == "2026-01-08"
    assert anomalies[0]["actual_value"] == 16.0
    assert anomalies[0]["moving_average"] == 10.0
    assert anomalies[0]["threshold"] == 15.0


def test_value_equal_to_threshold_is_not_anomaly() -> None:
    records = [
        _record(1, 10.0),
        _record(2, 10.0),
        _record(3, 10.0),
        _record(4, 10.0),
        _record(5, 10.0),
        _record(6, 10.0),
        _record(7, 10.0),
        _record(8, 15.0),
    ]

    anomalies = detect_anomalies(records, window_size=7, deviation_factor=1.5)

    assert anomalies == []


def test_uses_configurable_parameters() -> None:
    records = [
        _record(1, 20.0),
        _record(2, 20.0),
        _record(3, 20.0),
        _record(4, 25.0),
    ]

    anomalies = detect_anomalies(records, window_size=3, deviation_factor=1.2)

    assert len(anomalies) == 1
    assert anomalies[0]["cost_date"] == "2026-01-04"
    assert anomalies[0]["threshold"] == 24.0
