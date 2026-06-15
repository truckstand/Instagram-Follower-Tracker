"""Milestone push notifications via ntfy.sh.

When the follower count crosses a configured milestone (e.g. 777, 1000, 1250)
a push notification is sent to a private ntfy topic, which the ntfy app on the
phone is subscribed to.

Already-fired milestones are remembered in ``data/notified.json`` so each one
notifies exactly once, even if the count wobbles up and down around it. The
first time this runs it *seeds* that file with every milestone already at or
below the current count (silently), so you don't get a flood of retroactive
alerts for milestones she passed long ago.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

import requests

DEFAULT_SERVER = "https://ntfy.sh"


def build_milestones(notif_cfg: dict) -> List[int]:
    """Combine the explicit milestone list with an optional ``auto_step``."""
    values = set(int(m) for m in notif_cfg.get("milestones", []))
    step = notif_cfg.get("auto_step")
    until = notif_cfg.get("auto_until")
    if step and until:
        step, until = int(step), int(until)
        if step > 0:
            values.update(range(step, until + 1, step))
    return sorted(values)


def _send(server: str, topic: str, title: str, message: str,
          tags: str = "tada", priority: str = "high") -> bool:
    url = f"{server.rstrip('/')}/{topic}"
    # HTTP headers must be latin-1; ntfy renders emoji from Tags, not Title.
    safe_title = title.encode("latin-1", "replace").decode("latin-1")
    try:
        resp = requests.post(
            url,
            data=message.encode("utf-8"),
            headers={
                "Title": safe_title,
                "Tags": tags,
                "Priority": priority,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[notify] failed to send to ntfy: {exc}")
        return False


def check_and_notify(config: dict, current: int, state_path: str,
                     display_name: str = "") -> None:
    """Send notifications for any newly-crossed milestones."""
    notif = config.get("notifications", {}) or {}
    topic = os.environ.get("NTFY_TOPIC") or notif.get("ntfy_topic", "")
    server = os.environ.get("NTFY_SERVER") or notif.get("ntfy_server") or DEFAULT_SERVER

    if not topic or topic == "CHANGE_ME":
        print("[notify] no ntfy topic configured; skipping notifications.")
        return

    milestones = build_milestones(notif)
    if not milestones:
        return

    # Load remembered milestones (None => first ever run).
    notified: Optional[List[int]] = None
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as fh:
                notified = list(json.load(fh))
        except (ValueError, OSError):
            notified = None

    name = display_name or "She"

    if notified is None:
        # First run: baseline everything already reached, no alerts.
        seeded = [m for m in milestones if m <= current]
        _save_state(state_path, seeded)
        print(f"[notify] seeded {len(seeded)} past milestone(s); no alerts sent.")
        return

    done = set(notified)
    newly = [m for m in milestones if m <= current and m not in done]
    if not newly:
        return

    for m in newly:
        title = f"{name} hit {m:,} followers!"
        message = f"🎉 {name} just reached {m:,} Instagram followers (now {current:,})."
        if _send(server, topic, title, message, tags="tada,partying_face"):
            done.add(m)
            print(f"[notify] sent milestone alert: {m:,}")

    _save_state(state_path, sorted(done))


def _save_state(path: str, values: List[int]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sorted(values), fh, indent=2)
        fh.write("\n")
