#!/usr/bin/env python3
"""Знімок плейліста Elevation Worship «Sunday Set List» (Spotify).

Elevation не архівує служіння з прославленням, але сама веде плейліст
пісень, які зараз у недільній ротації. Скрипт зберігає датований знімок
у data/elevation_playlist/YYYY-MM-DD.json і показує різницю з попереднім —
тобто «що додали / прибрали з ротації». Запускати раз на тиждень-два.
"""
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

PLAYLIST = "46z98oo8Z3QXbDgBE9tSen"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "elevation_playlist"


def fetch_tracks():
    url = f"https://open.spotify.com/embed/playlist/{PLAYLIST}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode()
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                  html, re.S)
    if not m:
        raise SystemExit("Не знайшов __NEXT_DATA__ — Spotify змінив розмітку")
    data = json.loads(m.group(1))

    def walk(o):
        if isinstance(o, dict):
            if "trackList" in o and isinstance(o["trackList"], list):
                yield o["trackList"]
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    for tl in walk(data):
        tracks = [{"title": t.get("title", ""), "artist": t.get("subtitle", "")}
                  for t in tl if t.get("title")]
        if tracks:
            return tracks
    raise SystemExit("Плейліст порожній або формат змінився")


def main():
    OUT.mkdir(exist_ok=True)
    tracks = fetch_tracks()
    today = date.today().isoformat()
    (OUT / f"{today}.json").write_text(
        json.dumps(tracks, ensure_ascii=False, indent=1))
    print(f"Знімок {today}: {len(tracks)} треків")

    snaps = sorted(OUT.glob("*.json"))
    if len(snaps) >= 2:
        prev = json.loads(snaps[-2].read_text())
        old = {t["title"] for t in prev}
        new = {t["title"] for t in tracks}
        added, removed = new - old, old - new
        if added:
            print("Додано в ротацію:", ", ".join(sorted(added)))
        if removed:
            print("Прибрано з ротації:", ", ".join(sorted(removed)))
        if not added and not removed:
            print("Ротація не змінилась з", snaps[-2].stem)


if __name__ == "__main__":
    main()
