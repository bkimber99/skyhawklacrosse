#!/usr/bin/env python3
"""Refresh the varsity schedule embedded in index.html from MaxPreps.

There's no MaxPreps API, so this scrapes the public schedule page (same
approach as the stats app's parseMaxPrepsSchedule), reads each game page's
schema.org JSON-LD for the venue, saves opponent logos to ./logos/, and
rewrites the SCHEDULE_DATA block in index.html. Re-run whenever MaxPreps
changes, then commit and push:

    python3 scripts/update_schedule.py            # current season
    python3 scripts/update_schedule.py 26-27      # explicit season
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.request

ORIGIN = "https://www.maxpreps.com"
TEAM_URL = f"{ORIGIN}/ut/salem/salem-hills-skyhawks/lacrosse/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
LOGO_DIR = os.path.join(ROOT, "logos")
START, END = "/* SCHEDULE_DATA:START */", "/* SCHEDULE_DATA:END */"


def current_season(today=None):
    # Spring sport: from July on, next spring's schedule is the one being built.
    today = today or datetime.date.today()
    year = today.year + 1 if today.month >= 7 else today.year
    return f"{(year - 1) % 100:02d}-{year % 100:02d}"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_schedule(page):
    games = {}
    for table in re.findall(r"<table[\s\S]*?</table>", page, re.I):
        for row in re.findall(r"<tr[\s\S]*?</tr>", table, re.I):
            link = re.search(r'href="(/[^"]*/game/[^"]*/(\d{1,2})-(\d{1,2})-(\d{4})/\?c=([0-9a-f-]{36}))"', row, re.I)
            if not link or link.group(5) in games:
                continue
            path, month, day, year, contest_id = link.groups()
            name = re.search(r'<span class="name">([\s\S]*?)</span>', row, re.I)
            if not name:
                continue
            date_cell = re.search(r"<td[^>]*>([\s\S]*?)</td>", row, re.I).group(1)
            spans = [text(s) for s in re.findall(r"<span[^>]*>([\s\S]*?)</span>", date_cell, re.I)]
            hat = re.search(r'<span class="hat">([\s\S]*?)</span>', row, re.I)
            opp_link = re.search(r'class="OpponentLink[^"]*"[^>]*href="([^"]*)"', row)
            img = re.search(r'<img src="([^"]*)"', row)
            raw_name = text(name.group(1))
            games[contest_id] = {
                "date": f"{int(year):04d}-{int(month):02d}-{int(day):02d}",
                "time": spans[1] if len(spans) > 1 else "TBA",
                "home": not (hat and text(hat.group(1)) == "@"),
                # Trailing * marks region games, ** playoffs, *** tournaments.
                "opponent": raw_name.rstrip("*").strip(),
                "region": raw_name.endswith("*") and not raw_name.endswith("**"),
                "opponentPath": opp_link.group(1) if opp_link else None,
                "logoSrc": html.unescape(img.group(1)) if img else None,
                "url": ORIGIN + html.unescape(path),
            }
    return sorted(games.values(), key=lambda g: g["date"])


def venue(game_url):
    page = fetch(game_url).decode("utf-8", "replace")
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>([\s\S]*?)</script>', page):
        data = json.loads(block)
        if data.get("@type") != "SportsEvent":
            continue
        loc = data.get("location") or {}
        addr = loc.get("address") or {}
        street = (addr.get("streetAddress") or "").strip()
        city = ", ".join(p for p in [addr.get("addressLocality"), "UT"] if p)
        return {"name": (loc.get("name") or "").strip(), "address": ", ".join(p for p in [street, city] if p)}
    return {"name": "", "address": ""}


def save_logo(game):
    """Download the opponent's mascot as a PNG; returns its relative path.

    A hand-picked replacement saved as logos/<slug>-vN.png wins over the
    MaxPreps download (highest N), and existing files are never re-downloaded.
    """
    if not game["logoSrc"]:
        return None
    slug = (game["opponentPath"] or game["opponent"]).strip("/").split("/")
    slug = slug[2] if len(slug) >= 3 else re.sub(r"[^a-z0-9]+", "-", game["opponent"].lower())
    versions = [int(m.group(1)) for f in os.listdir(LOGO_DIR) if (m := re.fullmatch(rf"{re.escape(slug)}-v(\d+)\.png", f))]
    if versions:
        return f"logos/{slug}-v{max(versions)}.png"
    rel = f"logos/{slug}.png"
    dest = os.path.join(ROOT, rel)
    if not os.path.exists(dest):
        base = game["logoSrc"].split("?")[0]
        with open(dest, "wb") as f:
            f.write(fetch(f"{base}?width=256&height=256&format=png"))
    return rel


def main():
    season = sys.argv[1] if len(sys.argv) > 1 else current_season()
    url = f"{TEAM_URL}{season}/schedule/"
    games = parse_schedule(fetch(url).decode("utf-8", "replace"))
    if not games:
        sys.exit(f"No games found at {url}; leaving index.html unchanged.")

    os.makedirs(LOGO_DIR, exist_ok=True)
    out = []
    for g in games:
        out.append({
            "date": g["date"],
            "time": g["time"],
            "home": g["home"],
            "opponent": g["opponent"],
            "region": g["region"],
            "logo": "./" + save_logo(g) if g["logoSrc"] else None,
            "venue": venue(g["url"]),
            "url": g["url"],
        })
        print(f'{g["date"]}  {"vs" if g["home"] else "@ "} {g["opponent"]}')

    block = f"{START}\n    const SCHEDULE_SEASON = {json.dumps(season)};\n    const SCHEDULE = {json.dumps(out, indent=2)};\n    {END}"
    with open(INDEX) as f:
        page = f.read()
    if START not in page or END not in page:
        sys.exit("SCHEDULE_DATA markers not found in index.html.")
    page = re.sub(re.escape(START) + r"[\s\S]*?" + re.escape(END), lambda _: block, page)
    with open(INDEX, "w") as f:
        f.write(page)
    print(f"Wrote {len(out)} games for {season} to index.html")


if __name__ == "__main__":
    main()
