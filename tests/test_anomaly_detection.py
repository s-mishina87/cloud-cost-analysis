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


def _records(costs: list[float], namespace_name: str = "payments") -> list[dict]:
    """Build a small ordered time series for one namespace."""
    return [_record(day=index + 1, total_cost=value, namespace_name=namespace_name) for index, value in enumerate(costs)]


def test_returns_empty_for_empty_input() -> None:
    assert detect_anomalies([]) == []


def test_rejects_non_positive_window_size() -> None:
    try:
        detect_anomalies([_record(1, 10.0)], window_size=0)
    except ValueError as exc:
        assert "window_size must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive window_size")


def test_rejects_non_positive_change_factor() -> None:
    try:
        detect_anomalies([_record(1, 10.0)], change_factor=0)
    except ValueError as exc:
        assert "change_factor must be > 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive change_factor")


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


def test_anomaly_output_includes_change_fields() -> None:
    records = _records([10.0, 10.0, 10.0, 16.0], namespace_name="payments")

    anomalies = detect_anomalies(records, window_size=3, deviation_factor=1.5, change_factor=1.5)

    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly["baseline_value"] == 10.0
    assert anomaly["threshold_value"] == 15.0
    assert anomaly["moving_average"] == 10.0
    assert anomaly["threshold"] == 15.0
    assert anomaly["daily_change"] == 6.0
    assert anomaly["average_absolute_change"] == 0.0
    assert anomaly["change_threshold"] == 0.0
    assert anomaly["is_fast_change"] is True


def test_payments_spike_is_marked_as_fast_change() -> None:
    records = _records([100.0, 101.0, 99.0, 100.0, 300.0], namespace_name="payments")

    anomalies = detect_anomalies(records, window_size=4, deviation_factor=1.5, change_factor=2.0)

    assert len(anomalies) == 1
    assert anomalies[0]["namespace_name"] == "payments"
    assert anomalies[0]["is_fast_change"] is True
    assert anomalies[0]["daily_change"] > anomalies[0]["change_threshold"]


def test_checkout_jump_is_marked_as_fast_change() -> None:
    records = _records([80.0, 82.0, 81.0, 79.0, 140.0], namespace_name="checkout")

    anomalies = detect_anomalies(records, window_size=4, deviation_factor=1.4, change_factor=2.0)

    assert len(anomalies) == 1
    assert anomalies[0]["namespace_name"] == "checkout"
    assert anomalies[0]["is_fast_change"] is True


def test_monitoring_gradual_increase_can_be_anomaly_without_fast_change() -> None:
    records = _records([10.0, 10.0, 10.0, 12.0, 14.0, 17.0], namespace_name="monitoring")

    anomalies = detect_anomalies(records, window_size=3, deviation_factor=1.2, change_factor=2.0)

    assert len(anomalies) == 2
    assert anomalies[-1]["namespace_name"] == "monitoring"
    assert anomalies[-1]["is_fast_change"] is False
    assert anomalies[-1]["actual_value"] > anomalies[-1]["threshold_value"]


def test_large_jump_after_small_recent_variation_is_fast_change() -> None:
    records = _records([50.0, 51.0, 50.0, 51.0, 70.0], namespace_name="orders")

    anomalies = detect_anomalies(records, window_size=4, deviation_factor=1.2, change_factor=2.0)

    assert len(anomalies) == 1
    assert anomalies[0]["is_fast_change"] is True
    assert anomalies[0]["average_absolute_change"] < anomalies[0]["daily_change"]


def test_short_history_for_change_calculation_behaves_sensibly() -> None:
    records = _records([10.0, 20.0], namespace_name="payments")

    anomalies = detect_anomalies(records, window_size=1, deviation_factor=1.5, change_factor=2.0)

    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly["daily_change"] == 10.0
    assert anomaly["average_absolute_change"] == 0.0
    assert anomaly["change_threshold"] == 0.0
    assert anomaly["is_fast_change"] is True
