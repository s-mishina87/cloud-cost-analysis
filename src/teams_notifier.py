"""Optional Microsoft Teams delivery for internal notifications.

This module is intentionally separate from anomaly detection and alert generation.
"""

from __future__ import annotations

import json
import os
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


def _teams_payload(notification: dict) -> dict:
    """Build a simple Teams webhook payload from one internal notification."""
    return {
        "text": (
            f"[{notification.get('severity', 'MEDIUM')}] "
            f"{notification.get('message', '')} "
            f"(ref={notification.get('anomaly_ref_key', 'n/a')})"
        )
    }


def _post_teams_message(webhook_url: str, payload: dict) -> tuple[bool, str]:
    """Send one payload to Teams webhook and return success flag with detail."""
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                return True, "ok"
            return False, f"HTTP {status_code}"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except URLError as exc:
        return False, f"Network error: {exc.reason}"
    except Exception as exc:  # defensive fallback for local robustness
        return False, f"Unexpected error: {exc}"


def send_notifications_to_teams(notifications: list[dict]) -> dict:
    """Send generated notifications to Teams using TEAMS_WEBHOOK_URL.

    Returns a small summary for logging and beginner-friendly visibility.
    """
    if not notifications:
        return {
            "enabled": False,
            "total": 0,
            "sent": 0,
            "failed": 0,
            "message": "No notifications to send to Teams.",
        }

    webhook_url = os.getenv("TEAMS_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return {
            "enabled": False,
            "total": len(notifications),
            "sent": 0,
            "failed": 0,
            "message": "Teams delivery disabled: TEAMS_WEBHOOK_URL not configured.",
        }

    sent = 0
    failed = 0

    for notification in notifications:
        payload = _teams_payload(notification)
        ok, _detail = _post_teams_message(webhook_url, payload)
        if ok:
            sent += 1
        else:
            failed += 1

    return {
        "enabled": True,
        "total": len(notifications),
        "sent": sent,
        "failed": failed,
        "message": f"Completed Teams delivery: sent={sent}, failed={failed}.",
    }
