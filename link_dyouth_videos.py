#!/usr/bin/env python3
"""Проставляє посилання на YouTube-стріми в служіннях D.Youth.

Дата завантаження стріму може відрізнятись від дати служіння на ±1 день
(трансляція неділі інколи зʼявляється в понеділок), тому матчимо
дату служіння на дату відео d, d+1, d-1 — у такому порядку.

Використання:
    ./venv/bin/python link_dyouth_videos.py
(індекс відео — data/dyouth_videos.json)
"""
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def link():
    videos_path = DATA / "dyouth_videos.json"
    if not videos_path.exists():
        print("Немає data/dyouth_videos.json — пропускаю лінкування відео")
        return
    by_date = {}
    for v in json.loads(videos_path.read_text()):
        d = v["date"]
        by_date.setdefault(f"{d[:4]}-{d[4:6]}-{d[6:]}", v)

    data = json.loads((DATA / "dyouth.json").read_text())
    linked = 0
    for s in data["services"]:
        if s.get("url"):
            continue
        d = date.fromisoformat(s["date"])
        for delta in (0, 1, -1):
            v = by_date.get((d + timedelta(days=delta)).isoformat())
            if v:
                s["url"] = f"https://www.youtube.com/watch?v={v['id']}"
                s["video_id"] = v["id"]
                if not s.get("title") or s["title"] == "Молодіжне служіння":
                    s["title"] = v["title"]
                linked += 1
                break
    (DATA / "dyouth.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2))
    no_url = sum(1 for s in data["services"] if not s.get("url"))
    print(f"Прилінковано відео: {linked}; без відео лишилось: {no_url}")


if __name__ == "__main__":
    link()
