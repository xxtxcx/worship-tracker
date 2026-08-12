#!/usr/bin/env python3
"""Міграція JSON → MongoDB"""
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGODB_DB", "worship_tracker")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]


def migrate():
    """Мігрувати всі дані з JSON в MongoDB"""

    # 1. Мігрувати пісні
    songs_file = DATA / "songs.json"
    if songs_file.exists():
        songs = json.loads(songs_file.read_text())
        db.songs.delete_many({})  # Очистити
        db.songs.insert_many(songs)
        print(f"✓ Мігровано {len(songs)} пісень")

    # 2. Мігрувати служіння для кожної церкви
    churches_file = ROOT / "churches.json"
    churches = json.loads(churches_file.read_text())

    db.services.delete_many({})  # Очистити
    total_services = 0

    for church in churches:
        church_id = church["id"]
        church_file = DATA / f"{church_id}.json"

        if not church_file.exists():
            continue

        raw_data = json.loads(church_file.read_text())
        services = raw_data if isinstance(raw_data, list) else raw_data.get("services", [])

        for svc in services:
            doc = {
                "id": svc.get("id", ""),
                "church_id": church_id,
                "date": svc.get("date", ""),
                "title": svc.get("title", ""),
                "url": svc.get("url", ""),
                "source": svc.get("source", "manual"),
                "created_at": datetime.utcnow(),
            }

            # Конвертувати пісні: inline → song_id + leader
            songs = []
            for song in svc.get("songs", []):
                if isinstance(song, dict):
                    if "song_id" in song:
                        # Вже нормалізована
                        songs.append({
                            "song_id": song["song_id"],
                            "leader": song.get("leader"),
                        })
                    else:
                        # Старий формат: {title, artist, leader}
                        # Найти song_id по назві
                        title = song.get("title", "")
                        # Простий пошук по точній назві (можна покращити)
                        song_doc = db.songs.find_one({"title": title})
                        if song_doc:
                            songs.append({
                                "song_id": song_doc["id"],
                                "leader": song.get("leader"),
                            })

            doc["songs"] = songs
            db.services.insert_one(doc)
            total_services += 1

        print(f"✓ Мігровано {len(services)} служінь для {church_id}")

    print(f"\n✓ ВСЬОГО: {total_services} служінь мігровано в MongoDB")


if __name__ == "__main__":
    migrate()
