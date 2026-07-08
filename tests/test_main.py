from src import main as main_module


def test_main_runs_with_email_only(monkeypatch):
    dataset = {
        "projects": [{"project_name": "retail-prod"}],
        "clusters": [{"project_name": "retail-prod", "cluster_name": "main"}],
        "namespaces": [
            {
                "project_name": "retail-prod",
                "cluster_name": "main",
                "namespace_name": "payments",
            }
        ],
        "namespace_costs": [
            {
                "cost_date": "2026-01-01",
                "project_name": "retail-prod",
                "cluster_name": "main",
                "namespace_name": "payments",
                "usage_cost": 100.0,
                "overhead_cost": 0.0,
                "total_cost": 120.0,
            }
        ],
        "cluster_overheads": [
            {
                "cost_date": "2026-01-01",
                "project_name": "retail-prod",
                "cluster_name": "main",
                "cluster_overhead_cost": 20.0,
            }
        ],
    }

    rows = [
        {
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "payments",
            "usage_cost": 100.0,
            "overhead_cost": 20.0,
            "total_cost": 120.0,
        }
    ]

    anomalies = [
        {
            "anomaly_ref_key": "2026-01-01|retail-prod|main|payments|moving_average_threshold",
            "cost_date": "2026-01-01",
            "project_name": "retail-prod",
            "cluster_name": "main",
            "namespace_name": "payments",
            "method": "moving_average_threshold",
            "actual_value": 120.0,
            "moving_average": 90.0,
            "threshold_value": 100.0,
            "severity": "HIGH",
            "is_anomaly": 1,
        }
    ]

    notifications = [
        {
            "anomaly_ref_key": "2026-01-01|retail-prod|main|payments|moving_average_threshold",
            "severity": "HIGH",
            "message": "Spike detected",
        }
    ]

    persisted = {"NamespaceCost": 1, "Anomaly": 1, "Notification": 1}

    calls = {
        "detect_costs": None,
        "notify": None,
        "email": 0,
    }

    monkeypatch.setattr(main_module, "generate_structured_data", lambda **kwargs: dataset)
    monkeypatch.setattr(main_module, "apply_overhead_allocation", lambda costs, overheads: rows)

    def fake_detect(costs):
        calls["detect_costs"] = costs
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

    main_module.main()

    assert calls["detect_costs"] == rows
    assert calls["notify"] == {"notification_threshold": main_module.ALERT_THRESHOLD}
    assert calls["email"] == 1
    assert not hasattr(main_module, "send_notifications_to_teams")
