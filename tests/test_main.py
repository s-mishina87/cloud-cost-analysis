from __future__ import annotations

from src import main as main_module


def test_main_runs_with_email_only(monkeypatch):
    dataset = {
        "projects": [{"project_id": "p1"}],
        "clusters": [{"cluster_id": "c1", "project_id": "p1"}],
        "namespaces": [{"namespace_id": "n1", "cluster_id": "c1"}],
        "namespace_costs": [
            {
                "namespace_id": "n1",
                "date": "2026-01-01",
                "usage_cost": 100.0,
                "total_cost": 120.0,
            }
        ],
        "cluster_overheads": [{"cluster_id": "c1", "date": "2026-01-01", "overhead_cost": 20.0}],
    }

    allocated_rows = [
        {
            "namespace_id": "n1",
            "date": "2026-01-01",
            "usage_cost": 100.0,
            "overhead_cost": 20.0,
            "total_cost": 120.0,
        }
    ]

    anomalies = [
        {
            "anomaly_ref_key": "n1|2026-01-01",
            "namespace_id": "n1",
            "date": "2026-01-01",
            "severity": "HIGH",
            "message": "Spike detected",
        }
    ]

    notifications = [
        {
            "anomaly_ref_key": "n1|2026-01-01",
            "severity": "HIGH",
            "message": "Spike detected",
        }
    ]

    persisted = {"NamespaceCost": 1, "Anomaly": 1, "Notification": 1}

    calls = {
        "detect": None,
        "notify": None,
        "email": 0,
    }

    monkeypatch.setattr(main_module, "generate_structured_data", lambda **kwargs: dataset)
    monkeypatch.setattr(main_module, "apply_overhead_allocation", lambda costs, overheads: allocated_rows)

    def fake_detect(costs, window_size, deviation_factor, change_factor):
        calls["detect"] = {
            "window_size": window_size,
            "deviation_factor": deviation_factor,
            "change_factor": change_factor,
        }
        return anomalies

    def fake_generate_notifications(items, notification_threshold):
        calls["notify"] = {"notification_threshold": notification_threshold}
        return notifications

    def fake_email(items):
        calls["email"] += 1
        return {
            "message": "ok",
            "enabled": True,
            "total": len(items),
            "sent": 1,
            "failed": 0,
            "recipients": ["demo@example.com"],
        }

    monkeypatch.setattr(main_module, "detect_anomalies", fake_detect)
    monkeypatch.setattr(main_module, "generate_notifications", fake_generate_notifications)
    monkeypatch.setattr(main_module, "send_notifications_by_email", fake_email)
    monkeypatch.setattr(main_module, "persist_pipeline_data", lambda **kwargs: persisted)
    monkeypatch.setattr(main_module, "debug_sqlite", lambda path: [])

    main_module.main()

    assert calls["detect"] == {
        "window_size": main_module.WINDOW_SIZE,
        "deviation_factor": main_module.DEVIATION_FACTOR,
        "change_factor": main_module.CHANGE_FACTOR,
    }
    assert calls["notify"] == {"notification_threshold": main_module.NOTIFICATION_THRESHOLD}
    assert calls["email"] == 1
    assert not hasattr(main_module, "send_notifications_to_teams")
