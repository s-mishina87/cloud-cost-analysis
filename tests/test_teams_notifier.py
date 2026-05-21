from src.teams_notifier import send_notifications_to_teams


def _notification(ref: str = "a-1", actual: float = 350.0, baseline: float = 100.0, threshold: float = 150.0) -> dict:
    return {
        "anomaly_ref_key": ref,
        "notification_date": "2026-01-01T12:00:00+00:00",
        "severity": "MEDIUM",
        "status": "NEW",
        "message": (
            "Cost anomaly in payments (retail-prod/cluster-eu-west-1) "
            f"on 2026-01-08: actual={actual}, baseline={baseline}, threshold={threshold}"
        ),
    }


def test_empty_notifications_returns_empty_summary(monkeypatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.webhook")

    summary = send_notifications_to_teams([])

    assert summary["total"] == 0
    assert summary["sent"] == 0
    assert summary["failed"] == 0
    assert "No notifications" in summary["message"]


def test_missing_teams_webhook_url_disables_delivery(monkeypatch) -> None:
    monkeypatch.delenv("TEAMS_WEBHOOK_URL", raising=False)

    summary = send_notifications_to_teams([_notification()])

    assert summary["enabled"] is False
    assert summary["sent"] == 0
    assert summary["failed"] == 0
    assert "not configured" in summary["message"]


def test_successful_send_of_one_notification(monkeypatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.webhook")

    calls: list[tuple[str, dict]] = []

    def fake_post(url: str, payload: dict) -> tuple[bool, str]:
        calls.append((url, payload))
        return True, "ok"

    monkeypatch.setattr("src.teams_notifier._post_teams_message", fake_post)

    summary = send_notifications_to_teams([_notification()])

    assert summary["sent"] == 1
    assert summary["failed"] == 0
    assert len(calls) == 1


def test_successful_send_of_multiple_notifications(monkeypatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.webhook")

    calls: list[tuple[str, dict]] = []

    def fake_post(url: str, payload: dict) -> tuple[bool, str]:
        calls.append((url, payload))
        return True, "ok"

    monkeypatch.setattr("src.teams_notifier._post_teams_message", fake_post)

    notifications = [_notification("a-1"), _notification("a-2")]
    summary = send_notifications_to_teams(notifications)

    assert summary["total"] == 2
    assert summary["sent"] == 2
    assert summary["failed"] == 0
    assert len(calls) == 2


def test_http_failure_is_handled_gracefully_and_continues(monkeypatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.webhook")

    call_count = {"value": 0}

    def flaky_post(url: str, payload: dict) -> tuple[bool, str]:
        call_count["value"] += 1
        if call_count["value"] == 1:
            return False, "HTTP 500"
        return True, "ok"

    monkeypatch.setattr("src.teams_notifier._post_teams_message", flaky_post)

    notifications = [_notification("a-1"), _notification("a-2")]
    summary = send_notifications_to_teams(notifications)

    assert summary["total"] == 2
    assert summary["sent"] == 1
    assert summary["failed"] == 1
    assert "Completed" in summary["message"]


def test_returned_result_summary_shape(monkeypatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://example.webhook")

    def fake_post(url: str, payload: dict) -> tuple[bool, str]:
        return True, "ok"

    monkeypatch.setattr("src.teams_notifier._post_teams_message", fake_post)

    summary = send_notifications_to_teams([_notification()])

    assert {"enabled", "total", "sent", "failed", "message"}.issubset(summary)
    assert summary["enabled"] is True
