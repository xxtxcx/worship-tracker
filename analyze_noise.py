#!/usr/bin/env python3
"""Аналіз шуму: знаходить підозрілі 'пісні' які вірогідно помилки парсингу."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

NOISE_PATTERNS = [
    r"^(слід|сторінка|епізод|тайм|taym|глава|chapter|розділ|частина|part)",
    r"^\d+\s*[-–—]?\s*\d+",  # 123-456, 12-3 (діапазон часу чи хвилин)
    r"^[a-z]{1,3}$",  # Дуже короткі однолітерні коди: "c", "a", "e" (тональності?)
    r"^(fm|вм|вм|live|streaming|online|church|choir|intro|outro|interlude)$",
    r"^(read|read more|more|next|back|skip|pause|caption|translation)",
]

def check_noise(title):
    title_lower = title.lower().strip()
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, title_lower):
            return "pattern"
    # Дуже коротке або дивне
    if len(title_lower) < 2:
        return "too_short"
    if len(title_lower.split()) == 1 and len(title_lower) < 4:
        return "one_word_short"
    # Особливо для Bethel/captions парсингу: часто детектить фрази з проповіді
    if any(w in title_lower for w in [">> ", "[", "]", "applause", "laughter"]):
        return "caption_noise"
    return None

def analyze():
    all_songs = Counter()
    noisy = []
    for church_file in DATA.glob("*.json"):
        if church_file.name in ["todos.json", "song_signatures.json"]:
            continue
        data = json.loads(church_file.read_text())
        services = data.get("services", []) if isinstance(data, dict) else data
        for svc in services:
            for song in svc.get("songs", []):
                title = song.get("title", "").strip()
                if not title:
                    continue
                all_songs[title] += 1
                noise_type = check_noise(title)
                if noise_type:
                    noisy.append((title, noise_type, all_songs[title]))

    # Сортуємо по кількості, найновіші спочатку
    noisy_sorted = sorted(set(noisy), key=lambda x: x[2], reverse=True)

    print(f"Всього унікальних 'пісень': {len(all_songs)}")
    print(f"Виявлено шуму: {len(noisy_sorted)}\n")

    if noisy_sorted:
        print("=== Шум (очевидні помилки парсингу) ===\n")
        for title, noise_type, count in noisy_sorted[:50]:
            print(f"{count:2d}x | [{noise_type:15s}] {title}")
    else:
        print("Явного шуму не виявлено.\n")

    # Покажи можливі дублікати (варіанти написання)
    print("\n=== Можливі дублікати (варіанти однієї пісні) ===\n")
    from difflib import SequenceMatcher
    titles = list(all_songs.keys())
    potential_dupes = []
    for i, t1 in enumerate(titles):
        for t2 in titles[i + 1:]:
            similarity = SequenceMatcher(None, t1.lower(), t2.lower()).ratio()
            if 0.75 < similarity < 0.99:  # Дуже схожі, але не ідентичні
                potential_dupes.append((t1, t2, similarity))

    potential_dupes.sort(key=lambda x: x[2], reverse=True)
    for t1, t2, sim in potential_dupes[:30]:
        print(f"{sim:.2%} | '{t1}' ~ '{t2}'")

if __name__ == "__main__":
    analyze()
