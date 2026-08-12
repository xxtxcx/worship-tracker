#!/usr/bin/env python3
"""Worship Tracker — Flask API з MongoDB"""
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from pymongo import MongoClient
from bson.objectid import ObjectId

load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# MongoDB
MONGO_URI = os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGODB_DB", "worship_tracker")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")


def get_churches():
    """Завантажити список церков з JSON (конфіг)"""
    path = ROOT / "churches.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def ensure_collections():
    """Створити collections якщо не існують"""
    if "songs" not in db.list_collection_names():
        db.create_collection("songs")
    if "services" not in db.list_collection_names():
        db.create_collection("services")
    if "todos" not in db.list_collection_names():
        db.create_collection("todos")


@app.before_request
def init_db():
    """Ініціалізація при першому запиті"""
    ensure_collections()


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/data")
def api_data():
    """Завантажити всі дані: церкви + служіння + пісні"""
    churches = get_churches()

    services = {}
    for church in churches:
        church_id = church["id"]
        # Завантажити служіння цієї церкви з MongoDB
        svc_list = list(db.services.find({"church_id": church_id}).sort("date", -1))
        # Денормалізувати: підставити дані про пісні
        for svc in svc_list:
            svc["_id"] = str(svc["_id"])  # ObjectId → string
            songs = []
            for song_ref in svc.get("songs", []):
                if "song_id" in song_ref:
                    song_data = db.songs.find_one({"id": song_ref["song_id"]})
                    if song_data:
                        songs.append({
                            "title": song_data.get("title"),
                            "artist": song_data.get("artist"),
                            "leader": song_ref.get("leader"),
                        })
                else:
                    # Старий формат (перехідний)
                    songs.append(song_ref)
            svc["songs"] = songs
        services[church_id] = svc_list

    return jsonify({
        "churches": churches,
        "services": services,
    })


@app.get("/api/songs")
def get_songs():
    """Завантажити всі пісні з MongoDB"""
    songs = list(db.songs.find().sort("id", 1))
    for song in songs:
        song.pop("_id", None)
    return jsonify(songs)


@app.post("/api/songs/<song_id>")
def update_song(song_id):
    """Оновити пісню (artist)"""
    body = request.get_json(force=True)
    result = db.songs.update_one(
        {"id": song_id},
        {"$set": {
            "artist": body.get("artist") or None,
            "title": body.get("title", ""),
            "updated_at": datetime.utcnow(),
        }}
    )
    return jsonify({"ok": result.modified_count > 0})


@app.post("/api/services")
def add_service():
    """Додати служіння"""
    body = request.get_json(force=True)
    church_id = body["church"]

    service = {
        "_id": ObjectId(),
        "id": str(ObjectId()),
        "church_id": church_id,
        "date": body["date"],
        "title": body.get("title", ""),
        "url": body.get("url", ""),
        "source": "manual",
        "songs": [
            {
                "song_id": s.get("song_id"),
                "leader": s.get("leader", ""),
            }
            for s in body.get("songs", [])
            if s.get("song_id")
        ],
        "created_at": datetime.utcnow(),
    }

    db.services.insert_one(service)
    service["_id"] = str(service["_id"])
    return jsonify({"ok": True, "service": service})


@app.delete("/api/services/<service_id>")
def delete_service(service_id):
    """Видалити служіння"""
    result = db.services.delete_one({"id": service_id})
    return jsonify({"ok": result.deleted_count > 0})


@app.post("/api/services/<service_id>/add_song")
def add_song_to_service(service_id):
    """Додати пісню до служіння"""
    body = request.get_json(force=True)

    # Якщо пісні немає — створити нову
    song_id = body.get("song_id")
    if not song_id:
        song_id = f"song_{uuid.uuid4().hex[:8]}"
        song_doc = {
            "id": song_id,
            "title": body.get("title", "").strip(),
            "artist": body.get("artist", "").strip() or None,
            "normalized_title": body.get("title", "").lower(),
            "churches": [],
            "created_at": datetime.utcnow(),
        }
        db.songs.insert_one(song_doc)

    # Додати пісню до служіння
    result = db.services.update_one(
        {"id": service_id},
        {"$push": {"songs": {
            "song_id": song_id,
            "leader": body.get("leader", "").strip() or None,
        }}}
    )

    return jsonify({"ok": result.modified_count > 0})


@app.post("/api/services/<service_id>/remove_song")
def remove_song(service_id):
    """Видалити пісню з служіння"""
    body = request.get_json(force=True)
    idx = body.get("index", 0)

    # Отримати служіння, видалити пісню по індексу, зберегти назад
    service = db.services.find_one({"id": service_id})
    if service and 0 <= idx < len(service.get("songs", [])):
        songs = service["songs"]
        songs.pop(idx)
        db.services.update_one({"id": service_id}, {"$set": {"songs": songs}})
        return jsonify({"ok": True})

    return jsonify({"ok": False}), 404


@app.get("/api/todos")
def get_todos():
    """Завантажити todos"""
    todos = list(db.todos.find().sort("_id", 1))
    for todo in todos:
        todo["_id"] = str(todo["_id"])
    return jsonify({"items": todos})


@app.post("/api/todos")
def add_todo():
    """Додати todo"""
    body = request.get_json(force=True)
    todo = {
        "_id": ObjectId(),
        "id": uuid.uuid4().hex[:12],
        "text": body["text"].strip(),
        "done": False,
        "created_at": datetime.utcnow(),
    }
    db.todos.insert_one(todo)
    todo["_id"] = str(todo["_id"])
    return jsonify({"ok": True})


@app.post("/api/todos/<todo_id>")
def update_todo(todo_id):
    """Оновити todo"""
    body = request.get_json(force=True)
    update = {}
    if "done" in body:
        update["done"] = bool(body["done"])
    if "text" in body:
        update["text"] = body["text"].strip()

    if update:
        result = db.todos.update_one({"id": todo_id}, {"$set": update})
        return jsonify({"ok": result.modified_count > 0})
    return jsonify({"ok": False})


@app.delete("/api/todos/<todo_id>")
def delete_todo(todo_id):
    """Видалити todo"""
    result = db.todos.delete_one({"id": todo_id})
    return jsonify({"ok": result.deleted_count > 0})


@app.post("/api/refresh/<church_id>")
def refresh(church_id):
    """Оновити дані церкви з YouTube (fetch.py)"""
    import subprocess
    import sys

    churches = get_churches()
    if not any(c["id"] == church_id and c.get("auto") for c in churches):
        return jsonify({"ok": False, "error": "not an auto church"}), 400

    try:
        res = subprocess.run(
            [sys.executable, str(ROOT / "fetch.py"), "--church", church_id, "--months", "6"],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        return jsonify({
            "ok": res.returncode == 0,
            "log": (res.stdout + res.stderr).strip()[-3000:],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    ensure_collections()
    app.run(host="127.0.0.1", port=8777, debug=False)
