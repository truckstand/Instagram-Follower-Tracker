# Instagram Follower Tracker 📈

A tiny, self-hosted tracker that records a **public** Instagram account's
follower count over time and publishes an auto-updating **widget image** plus a
**web dashboard** — perfect for putting on a Pixel 9 (or any Android/iOS) home
screen.

No app to build or sideload: a GitHub Action fetches the count on a schedule,
saves the history in this repo, renders `widget.png`, and serves everything via
GitHub Pages. Your phone just shows that image with a free "image widget" app.

| Widget image | Web dashboard |
| --- | --- |
| `docs/widget.png` (big count + 24h change + sparkline) | `docs/index.html` (live count, trends, chart) |

---

## How it works

```
GitHub Action (hourly)
   └─ tracker/fetch.py   → read public follower count from instagram.com
   └─ tracker/update.py  → append to data/history.json
   └─ tracker/render.py  → draw docs/widget.png
   └─ commit history + deploy docs/ to GitHub Pages
                                   │
            Pixel 9 image widget ──┘  (reloads the image URL on a timer)
```

---

## Setup (one time)

### 1. Set the account to track
Edit [`config.json`](config.json):

```json
{
  "username": "your_wifes_handle",
  "display_name": "Her Name",
  "timezone": "UTC"
}
```

> You can instead set repo **Variables** `IG_USERNAME` / `IG_DISPLAY`
> (Settings → Secrets and variables → Actions → *Variables*), which override
> `config.json`. Handy if you don't want the handle committed in the repo.

### 2. Enable GitHub Pages
Settings → **Pages** → *Build and deployment* → **Source: GitHub Actions**.

### 3. Turn on the schedule
Scheduled workflows only run on the repository's **default branch**, so merge
this branch into your default branch (e.g. `main`). The action then runs every
hour automatically. You can also run it any time from the **Actions** tab →
*Track Instagram followers* → **Run workflow**.

### 4. (Optional but recommended) Add a login session for reliability
Instagram sometimes blocks anonymous requests coming from cloud IPs. If you see
runs that "keep last known reading", add an authenticated session cookie:

1. Log into Instagram in a browser (use the wife's account, or any account that
   can view the profile).
2. Open DevTools → Application/Storage → Cookies → `https://www.instagram.com`
   → copy the value of **`sessionid`**.
3. Add it as a repo **Secret** named `IG_SESSIONID`
   (Settings → Secrets and variables → Actions → *Secrets*).

The session is sent only to instagram.com and never written to the repo.

---

## Put it on your Pixel 9 📱

After the action has run at least once, your files are live at:

```
Dashboard:     https://<your-username>.github.io/<repo-name>/
Widget image:  https://<your-username>.github.io/<repo-name>/widget.png
```

For `truckstand/instagram-follower-tracker` that's:
`https://truckstand.github.io/instagram-follower-tracker/widget.png`

Then on the phone:

1. Install a free image-widget app, e.g. **“Image Widget”** / **“Web Image
   Widget”** (or use **KWGT** if you already have it).
2. Add the widget to your home screen and point it at the **widget image URL**
   above.
3. Set its refresh interval (e.g. every 1–6 hours). Done — the count updates by
   itself.

Prefer a glanceable full page? Just add a **browser shortcut** to the dashboard
URL to your home screen instead.

---

## Run / test locally

```bash
pip install -r requirements.txt

# Fetch once and print the JSON (no files written):
python -m tracker.fetch instagram

# Full update: fetch → append history → render docs/widget.png
IG_USERNAME=your_wifes_handle python -m tracker.update
```

`data/history.json` is the source of truth for the trend; it's committed on each
run so your history survives. The widget re-renders every run so the timestamp
stays current even when the count hasn't moved.

---

## Notes & limits

- **Public profiles only** by design. Private accounts require the
  `IG_SESSIONID` session of an account that follows them.
- Instagram has no official API for this and may rate-limit. The tracker fails
  *safe*: on a blocked fetch it keeps the last good number and marks the image
  as a stale reading rather than recording garbage.
- Hourly is plenty for a follower count and stays well within reason. History is
  capped at the most recent 5000 points to keep the JSON small.
- This is a personal, hobby tool. Use it on accounts you have permission to
  track, and be respectful of Instagram's terms.
