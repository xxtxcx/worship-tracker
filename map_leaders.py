#!/usr/bin/env python3
"""Заміна ніків лідерів на правильні імена."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

LEADER_MAP = {
    # Ніки що потрібно замінити
    "@nneteli": "Наталя Вергун",
    "nneteli": "Наталя Вергун",
    "@netelii": "Наталя Вергун",
    "@mirahdzh": "Міра Гаджа",
    "@mi_i_mira": "Міра Гаджа",
    "mira": "Міра Гаджа",
    "@chkhvimiolanta": "Ілона Борщ",
    "iolanta": "Ілона Борщ",

    # Решта варіантів що вже близькі до правильних
    "@ganchukkv": "Квітка Ганчук",
    "@So_Fed": "Софія Федорчук",
    "@aniashtr": "Аня Грифель",
    "@annhryfel": "Анна Штереб",
    "@dizavadska": "Діана Завадська",
    "@andrcw": "Андрій Татач",
    "@aniashhh": "Аня Грифель",
    "@lidiya_nixon": "Ліdia",  # невідомо, залишити як є

    # Вже правильні імена - прибрати @
    "Ілона": "Ілона Борщ",
    "Андрій": "Андрій Татач",
    "Анна": "Анна Штереб",
    "Аня": "Аня Грифель",
    "Ді": "Діана Завадська",
}

def migrate():
    dyouth_file = DATA / "dyouth.json"
    if not dyouth_file.exists():
        print("dyouth.json не знайден")
        return

    data = json.loads(dyouth_file.read_text())
    services = data.get("services", []) if isinstance(data, dict) else data

    changed = 0
    for svc in services:
        for song in svc.get("songs", []):
            leader = song.get("leader", "").strip()
            if leader in LEADER_MAP:
                old = leader
                song["leader"] = LEADER_MAP[leader]
                print(f"  {old} → {song['leader']}")
                changed += 1

    dyouth_file.write_text(json.dumps(services if isinstance(data, list) else {"services": services}, ensure_ascii=False, indent=2))
    print(f"\nЗаміщено: {changed} пісень")

if __name__ == "__main__":
    migrate()
