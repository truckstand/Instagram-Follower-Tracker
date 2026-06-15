"""Render the follower count as a widget image (PNG).

The image is a 2:1 card (640x320) showing:
  * the account name
  * the current follower count (big)
  * the change over the last ~24h
  * a sparkline of recent history
  * the last-updated time

Designed to be displayed by an "image widget" app on Android that periodically
reloads an image from a URL.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

W, H = 640, 320

# Candidate font files across CI runners / desktops. First hit wins.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (_BOLD_CANDIDATES if bold else []) + _FONT_CANDIDATES
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _gradient(size: Tuple[int, int],
              top: Tuple[int, int, int],
              bottom: Tuple[int, int, int]) -> Image.Image:
    """Vertical gradient image."""
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        base.putpixel((0, y), tuple(
            int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)
        ))
    return base.resize((w, h))


def _fmt(n: int) -> str:
    return f"{n:,}"


def _text_w(draw: ImageDraw.ImageDraw, text: str,
            font: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(text, font=font))


def _sparkline(draw: ImageDraw.ImageDraw, points: List[int],
               box: Tuple[int, int, int, int],
               color: Tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    if len(points) < 2:
        return
    lo, hi = min(points), max(points)
    span = max(hi - lo, 1)
    n = len(points)
    coords = []
    for i, v in enumerate(points):
        px = x0 + (x1 - x0) * i / (n - 1)
        py = y1 - (y1 - y0) * (v - lo) / span
        coords.append((px, py))
    draw.line(coords, fill=color, width=3, joint="curve")
    # marker on the latest point
    lx, ly = coords[-1]
    r = 4
    draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=color)


def _delta_since(history: List[dict], hours: float) -> Optional[int]:
    """Follower change between now and ~``hours`` ago."""
    if not history:
        return None
    current = history[-1]["followers"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    baseline = None
    for entry in history:
        ts = datetime.fromisoformat(entry["timestamp"])
        if ts <= cutoff:
            baseline = entry["followers"]
        else:
            break
    if baseline is None:
        baseline = history[0]["followers"]
    return current - baseline


def render(history: List[dict], out_path: str,
           display_name: str = "", stale: bool = False) -> None:
    """Render the latest reading in ``history`` to ``out_path`` (PNG)."""
    if not history:
        raise ValueError("No history to render yet.")

    latest = history[-1]
    followers = latest["followers"]
    name = display_name or latest.get("full_name") or latest.get("username", "")
    username = latest.get("username", "")

    img = _gradient((W, H), (131, 58, 180), (253, 89, 73))  # IG purple -> red
    # warm corner glow
    glow = _gradient((W, H), (253, 89, 73), (252, 175, 69))
    img = Image.blend(img, glow, 0.35)
    draw = ImageDraw.Draw(img)

    white = (255, 255, 255)
    soft = (255, 255, 255, 0)

    # --- header: name + @username ---
    f_name = _load_font(30, bold=True)
    f_user = _load_font(20)
    draw.text((36, 30), name, font=f_name, fill=white)
    if username:
        draw.text((36, 68), f"@{username}", font=f_user, fill=(255, 255, 255))

    # --- big follower count ---
    f_count = _load_font(92, bold=True)
    count_str = _fmt(followers)
    draw.text((34, 110), count_str, font=f_count, fill=white)
    f_label = _load_font(22)
    draw.text((40, 212), "followers", font=f_label, fill=(245, 240, 255))

    # --- 24h delta ---
    delta = _delta_since(history, 24)
    if delta is not None:
        if delta > 0:
            arrow, dcolor, sign = "▲", (190, 255, 190), "+"
        elif delta < 0:
            arrow, dcolor, sign = "▼", (255, 200, 200), ""
        else:
            arrow, dcolor, sign = "—", (235, 235, 235), ""
        f_delta = _load_font(24, bold=True)
        dtext = f"{arrow} {sign}{_fmt(delta)} (24h)"
        dw = _text_w(draw, dtext, f_delta)
        draw.text((W - 36 - dw, 36), dtext, font=f_delta, fill=dcolor)

    # --- sparkline of recent history ---
    pts = [e["followers"] for e in history[-60:]]
    _sparkline(draw, pts, (W - 250, 150, W - 36, 235), (255, 255, 255))

    # --- footer: updated time / stale flag ---
    f_foot = _load_font(16)
    ts = datetime.fromisoformat(latest["timestamp"]).astimezone(timezone.utc)
    foot = f"updated {ts:%Y-%m-%d %H:%M} UTC"
    if stale:
        foot += "  • (last good reading)"
    draw.text((36, H - 32), foot, font=f_foot, fill=(240, 235, 250))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, "PNG")
    print(f"[render] wrote {out_path}")
