#!/usr/bin/env python3
"""Міграція на нормалізовану структуру: витягує унікальні пісні в songs.json"""
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

def norm_title(t):
    """Нормалізація як у app.js"""
    n = t.lower().replace("'", "").replace('"', "").strip()
    n = n.replace("ʼ", "").replace("`", "").replace("«", "").replace("»", "")
    return n

def migrate():
    # 1. Витягти всі пісні з існуючих файлів
    songs_map = {}  # norm_title -> {title, artist, church_ids}

    for church_file in DATA.glob("*.json"):
        if church_file.name in ["todos.json", "song_signatures.json", "songs.json"]:
            continue

        try:
            data = json.loads(church_file.read_text())
            services = data.get("services", []) if isinstance(data, dict) else data

            for svc in services:
                for song in svc.get("songs", []):
                    title = song.get("title", "").strip()
                    if not title:
                        continue

                    normalized = norm_title(title)
                    if normalized not in songs_map:
                        songs_map[normalized] = {
                            "title": title,
                            "artist": song.get("artist", "").strip() or None,
                            "churches": set(),
                        }
                    songs_map[normalized]["churches"].add(church_file.stem)
        except Exception as e:
            print(f"Помилка в {church_file.name}: {e}")

    # 2. Створити songs.json з ID
    songs_list = []
    song_by_title = {}  # для миграції: old_title -> song_id

    for i, (normalized, info) in enumerate(sorted(songs_map.items())):
        song_id = f"song_{i:04d}"
        song_record = {
            "id": song_id,
            "title": info["title"],
            "normalized_title": normalized,
            "artist": info["artist"],
            "churches": sorted(info["churches"]),
        }
        songs_list.append(song_record)
        song_by_title[info["title"]] = song_id

    songs_file = DATA / "songs.json"
    songs_file.write_text(json.dumps(songs_list, ensure_ascii=False, indent=2))
    print(f"✓ Створено songs.json: {len(songs_list)} пісень")

    # 3. Обновити церковні файли: замінити inline songs на song_id + leader
    for church_file in DATA.glob("*.json"):
        if church_file.name in ["todos.json", "song_signatures.json", "songs.json"]:
            continue

        try:
            data = json.loads(church_file.read_text())
            services = data.get("services", []) if isinstance(data, dict) else data

            for svc in services:
                new_songs = []
                for song in svc.get("songs", []):
                    title = song.get("title", "").strip()
                    if not title or title not in song_by_title:
                        continue

                    new_songs.append({
                        "song_id": song_by_title[title],
                        "leader": song.get("leader", "").strip() or None,
                    })
                svc["songs"] = new_songs

            church_file.write_text(json.dumps(services if isinstance(data, list) else data,
                                             ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Помилка при обновленні {church_file.name}: {e}")

    print(f"✓ Обновлено церковні файли")
    print("\nЗразок нової структури:")
    print("  songs.json: {id, title, normalized_title, artist, churches}")
    print("  service.songs: [{song_id, leader}, ...]")

if __name__ == "__main__":
    migrate()
