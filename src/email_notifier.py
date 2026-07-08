"""Optional email delivery for internal notifications.

This module is separate from anomaly detection and alert generation.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def _read_local_dotenv(path: str = ".env") -> dict[str, str]:
    """Read simple KEY=VALUE pairs from a local .env file."""
    values: dict[str, str] = {}

    if not os.path.exists(path):
        return values

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                values[key] = value

    return values


def _read_email_config() -> tuple[bool, dict]:
    """Read SMTP config from environment and validate required values."""
    dotenv_values = _read_local_dotenv()

    def _get_config_value(key: str, default: str = "") -> str:
        os_value = os.getenv(key)
        if os_value is not None and os_value.strip() != "":
            return os_value.strip()
        return dotenv_values.get(key, default).strip()

    host = _get_config_value("SMTP_HOST", "smtp.gmail.com")
    port_raw = _get_config_value("SMTP_PORT", "465")
    username = _get_config_value("SMTP_USERNAME")
    password = _get_config_value("SMTP_PASSWORD")
    smtp_from = _get_config_value("SMTP_FROM")
    sender = smtp_from or username

    recipients_raw = _get_config_value("SMTP_TO")
    recipients = [item.strip() for item in recipients_raw.split(",") if item.strip()]

    try:
        port = int(port_raw)
    except ValueError:
        return False, {"message": "Email delivery disabled: SMTP not configured (invalid SMTP_PORT)."}

    required_missing = not username or not password or not sender or not recipients
    if required_missing:
        return False, {"message": "Email delivery disabled: SMTP not configured."}

    return True, {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "recipients": recipients,
    }


def _build_summary_body(notifications: list[dict]) -> str:
    """Build a simple plain-text summary body for all notifications."""
    lines = ["Cloud cost alert summary", "", f"Total notifications: {len(notifications)}", ""]

    for index, notification in enumerate(notifications, start=1):
        lines.append(f"{index}. Severity: {notification.get('severity', 'MEDIUM')}")
        lines.append(f"   Ref: {notification.get('anomaly_ref_key', 'n/a')}")
        lines.append(f"   Message: {notification.get('message', '')}")

        change_type = notification.get("change_type")
        if change_type is not None:
            lines.append(f"   Change type: {change_type}")

        daily_change = notification.get("daily_change")
        if daily_change is not None:
            lines.append(f"   Daily change: {daily_change}")

        average_absolute_change = notification.get("average_absolute_change")
        if average_absolute_change is not None:
            lines.append(f"   Average absolute change: {average_absolute_change}")

        change_threshold = notification.get("change_threshold")
        if change_threshold is not None:
            lines.append(f"   Change threshold: {change_threshold}")

        is_fast_change = notification.get("is_fast_change")
        if is_fast_change is not None:
            lines.append(f"   Fast change: {is_fast_change}")

        lines.append("")

    return "\n".join(lines).strip() + "\n"


def send_notifications_by_email(notifications: list[dict]) -> dict:
    """Send one summary email for generated notifications.

    If SMTP is missing or sending fails, this returns a status.
    The pipeline keeps running.
    """
    if not notifications:
        return {
            "enabled": False,
            "total": 0,
            "sent": 0,
            "failed": 0,
            "recipients": [],
            "message": "No notifications to send by email.",
        }

    enabled, config = _read_email_config()
    if not enabled:
        return {
            "enabled": False,
            "total": len(notifications),
            "sent": 0,
            "failed": 0,
            "recipients": [],
            "message": config["message"],
        }

    message = EmailMessage()
    message["Subject"] = "Cloud Cost Alerts"
    message["From"] = config["sender"]
    message["To"] = ", ".join(config["recipients"])
    message.set_content(_build_summary_body(notifications))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["host"], config["port"], context=context) as smtp:
            smtp.login(config["username"], config["password"])
            smtp.send_message(message)
    except Exception as exc:
        return {
            "enabled": True,
            "total": len(notifications),
            "sent": 0,
            "failed": 1,
            "recipients": config["recipients"],
            "message": f"Email delivery failed: {exc}",
        }

    return {
        "enabled": True,
        "total": len(notifications),
        "sent": 1,
        "failed": 0,
        "recipients": config["recipients"],
        "message": f"Email delivery completed: sent=1, failed=0 to {len(config['recipients'])} recipient(s).",
    }
