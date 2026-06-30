from src.standard_deviation_detection import (
    calculate_namespace_rolling_stddev_details,
    calculate_rolling_stddev_summary,
    detect_anomalies_rolling_stddev,
)


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
    assert detect_anomalies_rolling_stddev([]) == []


def test_detects_value_above_rolling_stddev_threshold() -> None:
    records = [
        _record(1, 10.0),
        _record(2, 12.0),
        _record(3, 14.0),
        _record(4, 20.0),
    ]

    anomalies = detect_anomalies_rolling_stddev(records, window_size=3, stddev_factor=2.0)

    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly["cost_date"] == "2026-01-04"
    assert anomaly["method"] == "rolling_stddev_threshold"
    assert anomaly["actual_value"] == 20.0
    assert anomaly["baseline_value"] == 12.0
    assert anomaly["rolling_average"] == 12.0
    assert anomaly["rolling_stddev"] == 1.63
    assert anomaly["threshold_value"] == 15.27
    assert anomaly["is_anomaly"] == 1


def test_value_equal_to_threshold_is_not_anomaly() -> None:
    records = [
        _record(1, 10.0),
        _record(2, 10.0),
        _record(3, 10.0),
        _record(4, 10.0),
    ]

    anomalies = detect_anomalies_rolling_stddev(records, window_size=3, stddev_factor=2.0)

    assert anomalies == []


def test_rejects_invalid_parameters() -> None:
    records = [_record(1, 10.0)]

    for kwargs, expected_message in [
        ({"window_size": 0}, "window_size must be > 0"),
        ({"stddev_factor": 0}, "stddev_factor must be > 0"),
        ({"change_factor": 0}, "change_factor must be > 0"),
    ]:
        try:
            detect_anomalies_rolling_stddev(records, **kwargs)
        except ValueError as exc:
            assert expected_message in str(exc)
        else:
            raise AssertionError(f"Expected ValueError containing {expected_message!r}")


def test_calculates_rolling_stddev_summary() -> None:
    records = [
        _record(1, 10.0, namespace_name="payments"),
        _record(2, 12.0, namespace_name="payments"),
        _record(3, 14.0, namespace_name="payments"),
        _record(4, 20.0, namespace_name="payments"),
        _record(1, 20.0, namespace_name="checkout"),
        _record(2, 20.0, namespace_name="checkout"),
        _record(3, 20.0, namespace_name="checkout"),
        _record(4, 20.0, namespace_name="checkout"),
    ]

    summary = calculate_rolling_stddev_summary(records, window_size=3)

    assert summary == {
        "average_stddev_per_namespace": 0.82,
        "minimum_stddev": 0.0,
        "maximum_stddev": 1.63,
    }


def test_rolling_stddev_summary_returns_zeroes_when_no_windows_exist() -> None:
    summary = calculate_rolling_stddev_summary([_record(1, 10.0)], window_size=7)

    assert summary == {
        "average_stddev_per_namespace": 0.0,
        "minimum_stddev": 0.0,
        "maximum_stddev": 0.0,
    }


def test_calculates_namespace_rolling_stddev_details_sorted_by_average() -> None:
    records = [
        _record(1, 10.0, namespace_name="payments"),
        _record(2, 12.0, namespace_name="payments"),
        _record(3, 14.0, namespace_name="payments"),
        _record(4, 20.0, namespace_name="payments"),
        _record(1, 20.0, namespace_name="checkout"),
        _record(2, 20.0, namespace_name="checkout"),
        _record(3, 20.0, namespace_name="checkout"),
        _record(4, 20.0, namespace_name="checkout"),
    ]

    details = calculate_namespace_rolling_stddev_details(records, window_size=3, limit=20)

    assert details == [
        {
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "payments",
            "rolling_mean": 12.0,
            "rolling_stddev": 1.63,
            "threshold": 15.27,
            "actual_value": 20.0,
            "actual_minus_threshold": 4.73,
            "average_stddev": 1.63,
            "minimum_stddev": 1.63,
            "maximum_stddev": 1.63,
            "window_count": 1,
        },
        {
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "checkout",
            "rolling_mean": 20.0,
            "rolling_stddev": 0.0,
            "threshold": 20.0,
            "actual_value": 20.0,
            "actual_minus_threshold": 0.0,
            "average_stddev": 0.0,
            "minimum_stddev": 0.0,
            "maximum_stddev": 0.0,
            "window_count": 1,
        },
    ]


def test_namespace_rolling_stddev_details_respects_limit() -> None:
    records = []
    for namespace_index in range(3):
        namespace_name = f"namespace-{namespace_index}"
        records.extend(
            [
                _record(1, 10.0, namespace_name=namespace_name),
                _record(2, 10.0, namespace_name=namespace_name),
            ]
        )

    details = calculate_namespace_rolling_stddev_details(records, window_size=1, limit=2)

    assert len(details) == 2
