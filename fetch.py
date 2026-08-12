#!/usr/bin/env python3
"""Збирач сетлістів з YouTube-каналів церков.

Для кожної церкви з churches.json (auto=true) читає останні стріми,
витягує пісні з таймкодів (chapters) і зливає у data/<church>.json.
Вже збережені служіння (за video id) не перезаписуються, тож ручні
правки (видалені пісні тощо) зберігаються.

Використання:
    ./venv/bin/python fetch.py --church gateway --months 6
    ./venv/bin/python fetch.py --all --months 6
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
YTDLP = str(ROOT / "venv" / "bin" / "yt-dlp")
DATA = ROOT / "data"

PLAYER_ARGS = ["--extractor-args", "youtube:player_client=android"]

# --- Парсери: chapter title -> (song_title, leader) або None, якщо не пісня ---

GATEWAY_SKIP = re.compile(
    r"countdown|welcome|exhortation|meet and greet|announcement|annoucement|"
    r"message|altar call|closing|prayer|offering|communion|baptism|testimon|"
    r"greeting|intro|sermon|scripture|series|moment|encouraging word|"
    r"vision|dedication|recap|update",
    re.I,
)

ALFA_SKIP = re.compile(
    r"^(вступ|інтро|intro(duction)?|привітання|welcome|"
    r"поклоніння|прославлення)\W*$|^words?\b|ordination|ординац|"
    r"молитв|prayer|"
    r"слов|пожертв|новин|оголошен|announce|проповід|sermon|свідоцтв|"
    r"testimon|вечер|причаст|communion|анонс|donate|\bnews\b|тема|"
    r"хрещен|baptism|greeting|збір|десятин|offering",
    re.I,
)


def parse_gateway(chapters):
    songs = []
    for ch in chapters or []:
        title = (ch.get("title") or "").strip()
        if not title or title.startswith("<") or GATEWAY_SKIP.search(title):
            continue
        m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", title)
        if m:
            name, leader = m.group(1).strip(), m.group(2).strip()
        else:
            name, leader = title, ""
        if not name:
            continue
        songs.append({"title": name, "leader": leader})
    return songs


def parse_alfa(chapters):
    songs = []
    for ch in chapters or []:
        title = (ch.get("title") or "").strip()
        if not title:
            continue
        # Формат: "The Lord Almighty// Прославлення" або просто назва;
        # буває "Хрещення + Rest On Us" — розбиваємо і фільтруємо частини
        name = re.split(r"\s*//\s*", title)[0].strip()
        for part in re.split(r"\s*\+\s*", name):
            part = part.strip(" .,")
            if part and not ALFA_SKIP.search(part):
                songs.append({"title": part, "leader": ""})
    return songs


DYOUTH_SKIP = re.compile(
    r"інтро|закуліс|привітан|оголошен|молитв|проповід|пожертв|причаст|"
    r"вітаємо|свідоцтв|новин|qr|untitled|продовження|закінчення|збір|"
    r"вечеря|хрещен|анонс|реклам",
    re.I,
)


def parse_dyouth(chapters):
    songs = []
    seen = set()
    for ch in chapters or []:
        title = (ch.get("title") or "").strip()
        if not title or DYOUTH_SKIP.search(title):
            continue
        key = title.lower()
        if key in seen:  # реприза тієї ж пісні в кінці служіння
            continue
        seen.add(key)
        songs.append({"title": title, "leader": ""})
    return songs


PARSERS = {"gateway": parse_gateway, "alfa": parse_alfa, "dyouth": parse_dyouth}


# --- Розпізнавання пісень з автосубтитрів (для церков без таймкодів) ---

def load_signatures():
    return json.loads((ROOT / "data" / "song_signatures.json").read_text())


def parse_vtt(path):
    """VTT -> (нормалізований текст, мапа позиція->секунди)."""
    import html as html_mod
    cues, t = [], None
    for line in open(path, encoding="utf-8"):
        m = re.match(r"(\d+):(\d+):(\d+)\.\d+ --> ", line)
        if m:
            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            continue
        if t is None or "-->" in line or not line.strip():
            continue
        txt = html_mod.unescape(re.sub(r"<[^>]+>", "", line))
        txt = re.sub(r"\[[^\]]*\]", " ", txt)   # [music], [singing]
        txt = txt.replace(">>", " ").lower()
        txt = re.sub(r"[^a-z' ]", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt and (not cues or cues[-1][1] != txt):
            cues.append((t, txt))
    full, pos2t, pos = [], [], 0
    for t, txt in cues:
        pos2t.append((pos, t))
        full.append(txt)
        pos += len(txt) + 1
    return " ".join(full), pos2t


def detect_songs(video_id, signatures):
    """Тягне автосубтитри відео і шукає в них сигнатурні фрази пісень."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        run_ytdlp([
            *PLAYER_ARGS, "--skip-download", "--write-auto-subs",
            "--sub-langs", "en", "--sub-format", "vtt",
            "-o", f"{tmp}/cap",
            f"https://www.youtube.com/watch?v={video_id}",
        ], timeout=180)
        vtt = Path(tmp) / "cap.en.vtt"
        if not vtt.exists():
            return []
        text, pos2t = parse_vtt(vtt)

    def time_at(pos):
        best = 0
        for p, t in pos2t:
            if p <= pos:
                best = t
            else:
                break
        return best

    found = []
    for song, phrases in signatures.items():
        hits = [(m.start(), ph) for ph in phrases
                for m in re.finditer(re.escape(ph), text)]
        if not hits:
            continue
        long_hit = any(len(ph.split()) >= 5 for _, ph in hits)
        if len(hits) >= 2 or long_hit:
            found.append((min(h[0] for h in hits), song))
    return [{"title": song, "leader": ""}
            for _, song in sorted((time_at(p), s) for p, s in found)]


def run_ytdlp(args, timeout=120):
    res = subprocess.run(
        [YTDLP, "--no-warnings", *args],
        capture_output=True, text=True, timeout=timeout,
    )
    return res.stdout.strip(), res.stderr.strip()


def list_streams(channel_url, limit=40):
    out, err = run_ytdlp([
        "--flat-playlist", "--playlist-end", str(limit),
        "--print", "%(id)s\t%(title)s", channel_url,
    ], timeout=180)
    videos = []
    for line in out.splitlines():
        if "\t" in line:
            vid, title = line.split("\t", 1)
            videos.append({"id": vid, "title": title})
    if not videos and err:
        print(f"  ! {err.splitlines()[-1]}", file=sys.stderr)
    return videos


def fetch_video(video_id):
    out, _ = run_ytdlp([
        *PLAYER_ARGS, "--skip-download",
        "--print", "%(upload_date)s\t%(duration)s\t%(chapters)j",
        f"https://www.youtube.com/watch?v={video_id}",
    ])
    if not out or "\t" not in out:
        return None
    upload_date, duration, chapters_json = out.split("\t", 2)
    try:
        chapters = json.loads(chapters_json)
    except (ValueError, TypeError):
        chapters = None
    return {
        "date": f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}",
        "duration": int(float(duration)) if duration not in ("NA", "") else 0,
        "chapters": chapters if isinstance(chapters, list) else [],
    }


def load_data(church_id):
    path = DATA / f"{church_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"services": []}


def save_data(church_id, data):
    data["services"].sort(key=lambda s: s.get("date", ""), reverse=True)
    path = DATA / f"{church_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def fetch_church(church, months):
    use_captions = church["parser"] == "captions"
    parser = None if use_captions else PARSERS[church["parser"]]
    signatures = load_signatures() if use_captions else None
    months = church.get("months", months)
    cutoff = (date.today() - timedelta(days=months * 31)).isoformat()
    data = load_data(church["id"])
    known = {s.get("video_id") for s in data["services"]}

    print(f"== {church['name']}: список стрімів…")
    videos = list_streams(church["channel"])
    added = 0
    for v in videos:
        if v["id"] in known:
            continue
        meta = fetch_video(v["id"])
        if not meta:
            print(f"  ? пропущено (нема метаданих): {v['title'][:60]}")
            continue
        if meta["date"] < cutoff:
            break  # стріми йдуть від нових до старих
        if use_captions:
            songs = detect_songs(v["id"], signatures)
        else:
            songs = parser(meta["chapters"])
        if church.get("skip_empty") and not songs:
            print(f"  - {meta['date']} — без таймкодів, пропущено: {v['title'][:50]}")
            continue
        data["services"].append({
            "id": v["id"],
            "video_id": v["id"],
            "date": meta["date"],
            "title": v["title"],
            "url": f"https://www.youtube.com/watch?v={v['id']}",
            "source": "youtube",
            "songs": songs,
        })
        added += 1
        print(f"  + {meta['date']} — {len(songs):2d} пісень — {v['title'][:60]}")
    save_data(church["id"], data)
    print(f"== {church['name']}: додано {added}, всього {len(data['services'])}")
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--church", help="id церкви з churches.json")
    ap.add_argument("--all", action="store_true", help="усі auto-церкви")
    ap.add_argument("--months", type=int, default=6)
    args = ap.parse_args()

    churches = json.loads((ROOT / "churches.json").read_text())
    targets = [c for c in churches if c.get("auto")]
    if args.church:
        targets = [c for c in targets if c["id"] == args.church]
        if not targets:
            sys.exit(f"Немає auto-церкви з id={args.church}")
    elif not args.all:
        ap.error("вкажіть --church <id> або --all")

    for church in targets:
        fetch_church(church, args.months)


if __name__ == "__main__":
    main()
