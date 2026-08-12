#!/usr/bin/env python3
"""Дедуплікація пісень: видалити варіанти з лідером в дужках"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def clean_song_title(title):
    """Видалити ім'я лідера в дужках від кінця назви"""
    # Видалити "(Leader Name)" від кінця
    return re.sub(r'\s*\([A-Za-z\s]+\)\s*$', '', title).strip()


def dedupe():
    songs_file = DATA / "songs.json"
    songs = json.loads(songs_file.read_text())

    # Мапа: cleaned_title -> song_id (найдавніший залишається)
    cleaned_map = {}
    duplicates = []

    for song in songs:
        cleaned = clean_song_title(song["title"])
        key = (cleaned, song["normalized_title"][:10])  # перших 10 символів norm_title

        if key in cleaned_map:
            # Це дублікат
            duplicates.append((song["id"], song["title"], cleaned_map[key]))
        else:
            # Перший раз бачимо цю пісню
            cleaned_map[key] = song["id"]

    # Покажи дублікати
    print(f"Знайдено {len(duplicates)} дублікатів:\n")
    for dup_id, dup_title, original_id in duplicates[:20]:
        orig_title = next((s["title"] for s in songs if s["id"] == original_id), "?")
        print(f"  ДУБЛІКАТ: '{dup_title}' (ID: {dup_id})")
        print(f"    → ОРИГІНАЛ: '{orig_title}' (ID: {original_id})\n")

    if len(duplicates) > 20:
        print(f"  ... та ще {len(duplicates) - 20} дублікатів")

    # Видалити дублікати
    dup_ids = {d[0] for d in duplicates}
    cleaned_songs = [s for s in songs if s["id"] not in dup_ids]

    songs_file.write_text(json.dumps(cleaned_songs, ensure_ascii=False, indent=2))
    print(f"\n✓ Видалено {len(duplicates)} дублікатів. Залишилось {len(cleaned_songs)} пісень")

    # Тепер потрібно обновити service.songs: замінити song_id що видалили на оригінальні
    for church_file in DATA.glob("*.json"):
        if church_file.name in ["todos.json", "song_signatures.json", "songs.json"]:
            continue

        try:
            data = json.loads(church_file.read_text())
            services = data.get("services", []) if isinstance(data, dict) else data

            for svc in services:
                for song_ref in svc.get("songs", []):
                    if isinstance(song_ref, dict) and "song_id" in song_ref:
                        # Знайти чи цей song_id у дублікатах
                        for dup_id, _, original_id in duplicates:
                            if song_ref["song_id"] == dup_id:
                                song_ref["song_id"] = original_id
                                break

            church_file.write_text(json.dumps(services if isinstance(data, list) else data,
                                             ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Помилка в {church_file.name}: {e}")


if __name__ == "__main__":
    dedupe()
