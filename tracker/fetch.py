"""Fetch the public follower count for an Instagram account.

Strategy (most reliable first):
  1. Instagram's web profile API (``web_profile_info``) with a browser-like
     user agent and the public web app id. Works for public profiles from
     residential IPs and often (not always) from cloud IPs.
  2. If an ``IG_SESSIONID`` is provided (an authenticated session cookie),
     it is sent along to greatly improve reliability and allow access that
     anonymous requests are denied.

The function never raises for an "expected" failure (blocked / rate limited /
not found); it returns ``None`` so the caller can keep the last known value
instead of corrupting the history with a bogus reading.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import requests

WEB_PROFILE_URL = "https://www.instagram.com/api/v1/users/web_profile_info/"

# Public app id used by instagram.com's own web client.
IG_WEB_APP_ID = "936619743392459"

# A recent, realistic desktop browser user agent. Looking like a real browser
# meaningfully reduces the chance of being blocked.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class Profile:
    username: str
    full_name: str
    followers: int
    following: int
    posts: int
    is_private: bool


def fetch_profile(username: str, session_id: Optional[str] = None,
                  timeout: int = 20) -> Optional[Profile]:
    """Return a :class:`Profile` for ``username`` or ``None`` on failure."""
    username = username.strip().lstrip("@")
    if not username or username == "CHANGE_ME":
        raise ValueError(
            "No Instagram username configured. Set it in config.json "
            "(\"username\") or the IG_USERNAME environment variable."
        )

    headers = {
        "User-Agent": USER_AGENT,
        "x-ig-app-id": IG_WEB_APP_ID,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.instagram.com/{username}/",
    }
    cookies = {}
    if session_id:
        cookies["sessionid"] = session_id.strip()

    try:
        resp = requests.get(
            WEB_PROFILE_URL,
            params={"username": username},
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
    except requests.RequestException as exc:  # network error / timeout
        print(f"[fetch] request failed: {exc}")
        return None

    if resp.status_code != 200:
        print(f"[fetch] unexpected status {resp.status_code} "
              f"(Instagram may be rate-limiting or blocking this request)")
        return None

    try:
        user = resp.json()["data"]["user"]
    except (ValueError, KeyError, TypeError):
        print("[fetch] response was not the expected JSON "
              "(blocked, login wall, or username not found)")
        return None

    if user is None:
        print(f"[fetch] user '{username}' not found")
        return None

    return Profile(
        username=username,
        full_name=user.get("full_name") or username,
        followers=int(user["edge_followed_by"]["count"]),
        following=int(user["edge_follow"]["count"]),
        posts=int(user["edge_owner_to_timeline_media"]["count"]),
        is_private=bool(user.get("is_private", False)),
    )


if __name__ == "__main__":  # quick manual test: python -m tracker.fetch <user>
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("IG_USERNAME", "")
    profile = fetch_profile(name, os.environ.get("IG_SESSIONID"))
    print(json.dumps(profile.__dict__ if profile else None, indent=2))
