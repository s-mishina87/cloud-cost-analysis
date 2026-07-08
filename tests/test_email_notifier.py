from src.email_notifier import _build_summary_body, send_notifications_by_email


def _notification(ref: str = "a-1", severity: str = "MEDIUM"):
    return {
        "anomaly_ref_key": ref,
        "notification_date": "2026-01-10T12:00:00+00:00",
        "severity": severity,
        "status": "NEW",
        "message": (
            "Cost anomaly in payments (retail-prod/cluster-eu-west-1) "
            "on 2026-01-10: actual=400.0, baseline=100.0, threshold=150.0"
        ),
    }


def _set_valid_smtp_env(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USERNAME", "alerts@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("SMTP_FROM", "alerts@example.com")
    monkeypatch.setenv(
        "SMTP_TO",
        "christina.seidl@stud.hcw.ac.at, svetlana.mishina@stud.hcw.ac.at",
    )


def _clear_smtp_env(monkeypatch):
    for key in [
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_TO",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_empty_notification_list_returns_empty_result(monkeypatch):
    _set_valid_smtp_env(monkeypatch)

    summary = send_notifications_by_email([])

    assert summary["enabled"] is False
    assert summary["total"] == 0
    assert summary["sent"] == 0
    assert summary["failed"] == 0
    assert "No notifications" in summary["message"]


def test_missing_smtp_configuration_disables_delivery(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_TO", raising=False)

    summary = send_notifications_by_email([_notification()])

    assert summary["enabled"] is False
    assert summary["sent"] == 0
    assert summary["failed"] == 0
    assert "not configured" in summary["message"]


def test_successful_send_with_mocked_smtp(monkeypatch):
    _set_valid_smtp_env(monkeypatch)

    captured = {"logged_in": None, "message": None}

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username: str, password: str):
            captured["logged_in"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    summary = send_notifications_by_email([_notification()])

    assert summary["enabled"] is True
    assert summary["total"] == 1
    assert summary["sent"] == 1
    assert summary["failed"] == 0
    assert captured["logged_in"] == ("alerts@example.com", "app-password")
    assert captured["message"]["Subject"] == "Cloud Cost Alerts"


def test_explicit_smtp_from_is_used(monkeypatch):
    _set_valid_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_FROM", "alerts-from@example.com")

    captured = {"from": ""}

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            captured["from"] = message["From"]

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    summary = send_notifications_by_email([_notification()])

    assert summary["sent"] == 1
    assert captured["from"] == "alerts-from@example.com"


def test_missing_smtp_from_falls_back_to_smtp_username(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _set_valid_smtp_env(monkeypatch)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    captured = {"from": ""}

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            captured["from"] = message["From"]

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    summary = send_notifications_by_email([_notification()])

    assert summary["sent"] == 1
    assert captured["from"] == "alerts@example.com"


def test_multiple_notifications_are_in_one_email_body(monkeypatch):
    _set_valid_smtp_env(monkeypatch)

    captured = {"body": ""}

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            captured["body"] = message.get_content()

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    notifications = [_notification(ref="a-1", severity="LOW"), _notification(ref="a-2", severity="HIGH")]
    summary = send_notifications_by_email(notifications)

    assert summary["sent"] == 1
    assert "a-1" in captured["body"]
    assert "a-2" in captured["body"]
    assert "LOW" in captured["body"]
    assert "HIGH" in captured["body"]


def test_build_summary_body_includes_change_metadata():
    body = _build_summary_body(
        [
            {
                "anomaly_ref_key": "2026-01-08|retail-prod|cluster-eu-west-1|payments|moving_average_threshold",
                "notification_date": "2026-01-10T12:00:00+00:00",
                "severity": "HIGH",
                "status": "NEW",
                "message": "Spike detected",
                "daily_change": 75.0,
                "average_absolute_change": 20.0,
                "change_threshold": 40.0,
                "is_fast_change": True,
                "change_type": "FAST_CHANGE",
            }
        ]
    )

    assert "Change type: FAST_CHANGE" in body
    assert "Daily change: 75.0" in body
    assert "Average absolute change: 20.0" in body
    assert "Change threshold: 40.0" in body
    assert "Fast change: True" in body


def test_multiple_recipients_are_parsed_correctly(monkeypatch):
    _set_valid_smtp_env(monkeypatch)
    monkeypatch.setenv(
        "SMTP_TO",
        "christina.seidl@stud.hcw.ac.at, , svetlana.mishina@stud.hcw.ac.at  ,",
    )

    captured = {"to": ""}

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            captured["to"] = message["To"]

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    summary = send_notifications_by_email([_notification()])

    assert summary["recipients"] == [
        "christina.seidl@stud.hcw.ac.at",
        "svetlana.mishina@stud.hcw.ac.at",
    ]
    assert captured["to"] == "christina.seidl@stud.hcw.ac.at, svetlana.mishina@stud.hcw.ac.at"


def test_smtp_failure_is_handled_gracefully(monkeypatch):
    _set_valid_smtp_env(monkeypatch)

    class FailingSMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            raise RuntimeError("SMTP send failed")

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", FailingSMTP)

    summary = send_notifications_by_email([_notification()])

    assert summary["enabled"] is True
    assert summary["total"] == 1
    assert summary["sent"] == 0
    assert summary["failed"] == 1
    assert "failed" in summary["message"].lower()


def test_result_summary_shape(monkeypatch):
    _set_valid_smtp_env(monkeypatch)

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            return None

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    summary = send_notifications_by_email([_notification()])

    assert {"enabled", "total", "sent", "failed", "recipients", "message"}.issubset(summary)


def test_reads_smtp_values_from_dotenv_when_os_env_is_missing(monkeypatch, tmp_path):
    _clear_smtp_env(monkeypatch)

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "# local smtp settings",
                "SMTP_HOST=smtp.gmail.com",
                "SMTP_PORT=465",
                "SMTP_USERNAME=dotenv-user@example.com",
                "SMTP_PASSWORD=dotenv-password",
                "SMTP_FROM=dotenv-from@example.com",
                "SMTP_TO=first@example.com, second@example.com",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    captured = {"logged_in": None, "from": "", "to": ""}

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            captured["logged_in"] = (username, password)

        def send_message(self, message):
            captured["from"] = message["From"]
            captured["to"] = message["To"]

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    summary = send_notifications_by_email([_notification()])

    assert summary["enabled"] is True
    assert summary["sent"] == 1
    assert captured["logged_in"] == ("dotenv-user@example.com", "dotenv-password")
    assert captured["from"] == "dotenv-from@example.com"
    assert captured["to"] == "first@example.com, second@example.com"


def test_os_env_vars_take_priority_over_dotenv(monkeypatch, tmp_path):
    _clear_smtp_env(monkeypatch)

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "SMTP_HOST=smtp.gmail.com",
                "SMTP_PORT=465",
                "SMTP_USERNAME=dotenv-user@example.com",
                "SMTP_PASSWORD=dotenv-password",
                "SMTP_FROM=dotenv-from@example.com",
                "SMTP_TO=dotenv-to@example.com",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    # OS environment should override .env values.
    monkeypatch.setenv("SMTP_USERNAME", "os-user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "os-password")
    monkeypatch.setenv("SMTP_FROM", "os-from@example.com")
    monkeypatch.setenv("SMTP_TO", "os-to@example.com")

    captured = {"logged_in": None, "from": "", "to": ""}

    class DummySMTP:
        def __init__(self, host: str, port: int, context=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            captured["logged_in"] = (username, password)

        def send_message(self, message):
            captured["from"] = message["From"]
            captured["to"] = message["To"]

    monkeypatch.setattr("src.email_notifier.smtplib.SMTP_SSL", DummySMTP)

    summary = send_notifications_by_email([_notification()])

    assert summary["enabled"] is True
    assert summary["sent"] == 1
    assert captured["logged_in"] == ("os-user@example.com", "os-password")
    assert captured["from"] == "os-from@example.com"
    assert captured["to"] == "os-to@example.com"
