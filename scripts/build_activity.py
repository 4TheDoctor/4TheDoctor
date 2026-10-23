#!/usr/bin/env python3
"""Draw the contribution activity panel as a self-hosted SVG.

Reads the GitHub contribution calendar and renders two readings of it:
commits per month, and the weekday profile. Both are generated from the
same source, so the panel can never disagree with itself.

Usage:
    gh api graphql -f query='...' | python3 scripts/build_activity.py > assets/activity.svg
    python3 scripts/build_activity.py --user 4TheDoctor > assets/activity.svg
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

W, H = 1200, 290
PAD = 34
BASE = "#0A0A0A"
BORDER = "#2D2D2D"
ACCENT = "#00FF9F"
WARM = "#FF6B00"
INK = "#F0EDE8"
MUTED = "#8A8A8A"
FAINT = "#4A4A4A"
MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"

QUERY = """
{ user(login: "%s") { contributionsCollection { contributionCalendar {
  totalContributions
  weeks { contributionDays { date contributionCount weekday } }
} } } }
"""


def fetch(user: str) -> dict:
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY % user}"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def days_from(payload: dict) -> list[dict]:
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [d for week in cal["weeks"] for d in week["contributionDays"]]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(days: list[dict], user: str) -> str:
    total = sum(d["contributionCount"] for d in days)

    # Commits per month, oldest first, exactly the months the data covers.
    months: dict[str, int] = {}
    for d in days:
        months.setdefault(d["date"][:7], 0)
        months[d["date"][:7]] += d["contributionCount"]
    series = sorted(months.items())[-12:]

    # Weekday profile. GitHub's weekday 0 is Sunday; show Monday first.
    week = [0] * 7
    for d in days:
        week[d["weekday"]] += d["contributionCount"]
    order = [1, 2, 3, 4, 5, 6, 0]
    labels = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    profile = [week[i] for i in order]

    parts: list[str] = []
    add = parts.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Contribution activity for {esc(user)}: {total} contributions in the last year">')
    add(f'<title>Contribution activity for {esc(user)}</title>')

    add('<defs><style>')
    add(f'.mono{{font-family:{MONO}}}')
    add(f'.h{{fill:{ACCENT};letter-spacing:3px}}')
    add(f'.lab{{fill:{FAINT};letter-spacing:2px}}')
    add(f'.val{{fill:{MUTED};letter-spacing:1px}}')
    add(f'.big{{fill:{INK}}}')
    add('.bar{transform-origin:bottom;transform-box:fill-box;'
        'animation:grow .85s cubic-bezier(.22,1,.36,1) both}')
    add('@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}')
    add('.fade{animation:fade .7s ease-out both}')
    add('@keyframes fade{from{opacity:0}to{opacity:1}}')
    add('@media (prefers-reduced-motion:reduce){.bar,.fade{animation:none}}')
    add('</style></defs>')

    add(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="6" '
        f'fill="{BASE}" stroke="{BORDER}" />')

    # ---- left panel: commits per month -------------------------------------
    lx, lw = PAD, 760
    top, bottom = 92, 214
    add(f'<text class="mono h" x="{lx}" y="44" font-size="12">CONTRIBUTIONS PER MONTH</text>')
    add(f'<text class="mono lab" x="{lx}" y="64" font-size="10">'
        f'LAST {len(series)} MONTHS &#183; {total} TOTAL</text>')
    add(f'<line x1="{lx}" y1="{bottom}" x2="{lx+lw}" y2="{bottom}" stroke="{BORDER}" />')

    peak = max((v for _, v in series), default=1) or 1
    slot = lw / len(series)
    bw = min(46.0, slot * 0.66)
    for i, (month, value) in enumerate(series):
        h = max(2.0, value / peak * (bottom - top))
        x = lx + i * slot + (slot - bw) / 2
        y = bottom - h
        hot = value == peak
        add(f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" '
            f'fill="{WARM if hot else ACCENT}" opacity="{0.95 if hot else 0.34 + 0.56 * value / peak:.2f}" '
            f'style="animation-delay:{0.05 * i:.2f}s" />')
        add(f'<text class="mono fade val" x="{x + bw/2:.1f}" y="{y - 7:.1f}" font-size="10" '
            f'text-anchor="middle" style="animation-delay:{0.05*i + 0.4:.2f}s" '
            f'fill="{WARM if hot else MUTED}">{value}</text>')
        label = dt.date(int(month[:4]), int(month[5:7]), 1).strftime("%b").upper()
        add(f'<text class="mono lab" x="{x + bw/2:.1f}" y="{bottom + 17:.1f}" font-size="9" '
            f'text-anchor="middle">{label}</text>')

    # ---- divider ------------------------------------------------------------
    add(f'<line x1="836" y1="36" x2="836" y2="238" stroke="{BORDER}" />')

    # ---- right panel: weekday profile --------------------------------------
    rx, rw = 870, W - 870 - PAD
    add(f'<text class="mono h" x="{rx}" y="44" font-size="12">BY DAY OF WEEK</text>')
    add(f'<text class="mono lab" x="{rx}" y="64" font-size="10">SAME YEAR, SUMMED</text>')
    add(f'<line x1="{rx}" y1="{bottom}" x2="{rx+rw}" y2="{bottom}" stroke="{BORDER}" />')

    wpeak = max(profile) or 1
    wslot = rw / 7
    wbw = min(26.0, wslot * 0.56)
    for i, value in enumerate(profile):
        h = max(2.0, value / wpeak * (bottom - top))
        x = rx + i * wslot + (wslot - wbw) / 2
        y = bottom - h
        hot = value == wpeak
        add(f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{wbw:.1f}" height="{h:.1f}" '
            f'fill="{WARM if hot else ACCENT}" opacity="{0.95 if hot else 0.30 + 0.60 * value / wpeak:.2f}" '
            f'style="animation-delay:{0.65 + 0.05 * i:.2f}s" />')
        add(f'<text class="mono fade val" x="{x + wbw/2:.1f}" y="{y - 7:.1f}" font-size="9" '
            f'text-anchor="middle" style="animation-delay:{1.05 + 0.05*i:.2f}s" '
            f'fill="{WARM if hot else MUTED}">{value}</text>')
        add(f'<text class="mono lab" x="{x + wbw/2:.1f}" y="{bottom + 17:.1f}" font-size="9" '
            f'text-anchor="middle">{labels[i]}</text>')

    # ---- provenance: every figure says where it comes from ------------------
    first, last = days[0]["date"], days[-1]["date"]
    add(f'<text class="mono lab" x="{PAD}" y="{H - 16}" font-size="9">'
        f'SOURCE: GITHUB CONTRIBUTION CALENDAR, {first} TO {last} '
        f'&#183; REBUILT EVERY SIX HOURS &#183; ORANGE MARKS THE PEAK</text>')

    add('</svg>')
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="4TheDoctor")
    args = ap.parse_args()

    payload = json.load(sys.stdin) if not sys.stdin.isatty() else fetch(args.user)
    days = days_from(payload)
    if not days:
        print("no contribution days returned", file=sys.stderr)
        return 1
    sys.stdout.write(build(days, args.user))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
