"""Fetch the current follower count, append it to the history, and rerender
the widget image and the data file used by the web page.

Run with:  python -m tracker.update

Configuration is read from ``config.json`` and can be overridden with
environment variables (handy for CI):
  IG_USERNAME   - the account to track
  IG_SESSIONID  - optional authenticated session cookie (improves reliability)
  IG_DISPLAY    - optional display name override
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone

from tracker.fetch import fetch_profile
from tracker.notify import check_and_notify
from tracker.render import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
HISTORY_PATH = os.path.join(ROOT, "data", "history.json")
NOTIFIED_PATH = os.path.join(ROOT, "data", "notified.json")
DOCS_DIR = os.path.join(ROOT, "docs")
WIDGET_PATH = os.path.join(DOCS_DIR, "widget.png")
DOCS_HISTORY_PATH = os.path.join(DOCS_DIR, "history.json")

# Keep history bounded so the JSON file stays small over the years.
MAX_ENTRIES = 5000
# Only record a new point if the count changed or this long has elapsed,
# so frequent runs don't bloat the file with identical readings.
MIN_INTERVAL_HOURS = 6


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def should_append(history, followers, now):
    if not history:
        return True
    last = history[-1]
    if last["followers"] != followers:
        return True
    last_ts = datetime.fromisoformat(last["timestamp"])
    elapsed_h = (now - last_ts).total_seconds() / 3600
    return elapsed_h >= MIN_INTERVAL_HOURS


def main() -> int:
    config = load_json(CONFIG_PATH, {})
    username = os.environ.get("IG_USERNAME") or config.get("username", "")
    display = os.environ.get("IG_DISPLAY") or config.get("display_name", "")
    session_id = os.environ.get("IG_SESSIONID")

    history = load_json(HISTORY_PATH, [])
    now = datetime.now(timezone.utc)

    profile = fetch_profile(username, session_id)
    stale = False

    if profile is None:
        if not history:
            print("[update] fetch failed and no prior history exists; "
                  "nothing to render yet.", file=sys.stderr)
            return 1
        print("[update] fetch failed; keeping last known reading.")
        stale = True
    else:
        if should_append(history, profile.followers, now):
            history.append({
                "timestamp": now.isoformat(timespec="seconds"),
                "username": profile.username,
                "full_name": profile.full_name,
                "followers": profile.followers,
                "following": profile.following,
                "posts": profile.posts,
            })
            history = history[-MAX_ENTRIES:]
            save_json(HISTORY_PATH, history)
            print(f"[update] recorded {profile.followers:,} followers")
        else:
            print(f"[update] no change ({profile.followers:,}); "
                  "skipping new history point.")

        # Fire milestone notifications based on the freshly fetched count.
        check_and_notify(config, profile.followers, NOTIFIED_PATH,
                         display_name=display or profile.full_name)

    # Always (re)render so the widget reflects the latest run/time.
    render(history, WIDGET_PATH, display_name=display, stale=stale)
    shutil.copyfile(HISTORY_PATH, DOCS_HISTORY_PATH)
    print("[update] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
