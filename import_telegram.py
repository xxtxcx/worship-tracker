#!/usr/bin/env python3
"""Імпорт сетлістів D.Youth з HTML-експорту Telegram Desktop.

Використання:
    ./venv/bin/python import_telegram.py "/шлях/до/ChatExport_.../messages.html"

Правила датування служіння:
  1) явна дата в тексті (dd.mm або dd.mm.yy) в перших рядках;
     якщо вона нереалістична (понад 60 днів у майбутнє або
     більш як 3 дні в минулому від дати повідомлення) — ігнорується;
  2) інакше — найближча наступна неділя від дати публікації
     (якщо опубліковано в неділю — той самий день).

Якщо на одну дату є кілька версій списку (чернетка «доповнюється»,
фінал, структура служіння) — береться повідомлення з найбільшою
кількістю розпізнаних пісень, при рівності — новіше.
"""
import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# Рядки/частини, які не є піснями
NOISE = re.compile(
    r"інтро|intro|заклик|спікер|молитв|привітан|вітання|оголошен|проповід|"
    r"трансляц|екран|таймер|світло|звук|переклад|дитячий|клуб|причаст|"
    r"пожертв|модератор|бінго|тема[:\s]|брідж|bridge|приспів|куплет|соло|"
    r"ending|енд(інг|инг)|перехід|шум|swell|відео|структура|деталі|повтор|"
    r"зациклення|молодіжне служіння|конференція|список|початок|закінч|"
    r"хвилин|секунд|акорди|темп|клік|обговорення|репетиц|breakdown|chorus|"
    r"verse|interlude|hard stop|грає|граєм|виходь|виход|зійде|стоїмо|остання|"
    r"^після|вітаємо|worship team|^вступ|кюар|\bqr\b|^пісня\s*\d*$|^україна$",
    re.I,
)

# У тональностях трапляються кириличні двійники: А В С Е Н
KEYCHARS = r"[A-HАВСЕН]"
KEY = re.compile(
    rf"\s+[-–—]\s*\(?({KEYCHARS}[b#♭♯]?m?)\)?(?=$|[\s,.)(])"  # " - D", " - (B)"
    rf"|\s*\(\s*({KEYCHARS}[b#♭♯]?m?)\s*\)",                   # "(C)", "(Bm)"
)
NUMBERED = re.compile(r"^\s*\d{1,2}[.)]\s+")
SONG_PREFIX = re.compile(r"^пісня\s*№?\s*\d*\s*[-–—:]\s*", re.I)
DRUM = re.compile(r"^\s*[🥁🎵🎶🎸🎹🎤]+\s*")
DUR = re.compile(r"\b\d{1,2}\s*хв\b\.?", re.I)
MENTION = re.compile(r"@\w+")
TIMEMARK = re.compile(r"\b\d{1,2}:\d{2}\b")


def extract_messages(path):
    src = open(path, encoding="utf-8").read()
    blocks = re.split(r'(?=<div class="message default)', src)[1:]
    msgs, last_from = [], ""
    for b in blocks:
        mid = re.search(r'id="(message\d+)"', b)
        mdate = re.search(r'class="[^"]*date details[^"]*"[^>]*title="([^"]+)"', b)
        mfrom = re.search(r'class="from_name">\s*([^<]+?)\s*<', b)
        if mfrom:
            last_from = mfrom.group(1).strip()
        mtext = re.search(r'<div class="text">(.*?)</div>', b, re.S)
        if not (mid and mdate and mtext):
            continue
        t = re.sub(r"<br\s*/?>", "\n", mtext.group(1))
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
        t = "\n".join(l.strip() for l in t.split("\n")).strip()
        dt = datetime.strptime(mdate.group(1).split(" UTC")[0], "%d.%m.%Y %H:%M:%S")
        msgs.append({"id": mid.group(1), "dt": dt, "from": last_from, "text": t})
    return msgs


def clean_title(s):
    s = MENTION.sub("", s)
    s = DUR.sub("", s)
    s = s.replace("`", "'").replace("’", "'").replace("ʼ", "'")
    s = re.sub(r"\([^()]*\)", " ", s)              # усі дужки-примітки
    s = SONG_PREFIX.sub("", s.strip())             # "Пісня 2 - …"
    s = re.sub(r"^\d+\s+", "", s)                  # загублений номер
    for _ in range(2):  # "Washed Db - Квітка": лідер ховає тональність
        s = s.strip(" -–—\t")
        s = re.sub(rf"\s+{KEYCHARS}[b#♭♯]?m?\s*$", "", s)            # тональність
        s = re.sub(r"\s*[-–—]\s*[А-ЯІЇЄҐ][\w'іїєґ]{2,}\s*$", "", s)  # "- Наталя"
    s = s.strip(" -–—+,.:;!?\t")
    s = re.sub(r"\s+", " ", s)
    return s


def parse_songs(text):
    songs = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if ")" in line and "(" not in line:  # хвіст багаторядкової примітки
            continue
        numbered = bool(NUMBERED.match(line))
        drum = bool(DRUM.match(line))
        plus = line.startswith("+")
        line_body = NUMBERED.sub("", line)
        line_body = DRUM.sub("", line_body).lstrip("+").strip()

        m = KEY.search(line_body)
        if not (m or numbered or drum or plus):
            continue
        if m:
            title_part = line_body[: m.start()]
            rest = line_body[m.end():]
        else:
            title_part = line_body
            rest = ""
        if TIMEMARK.search(title_part):
            title_part = TIMEMARK.sub("", title_part)

        # лідер: @mention будь-де в рядку або " - Імʼя" після тональності
        leader = ""
        mm = MENTION.search(raw)
        if mm:
            leader = mm.group(0)
        else:
            lm = re.search(r"[-–—]\s*([А-ЯІЇЄA-Z][\w'’ʼіїєґ]+)\s*$", rest.strip())
            if lm:
                leader = lm.group(1)

        # медлі: "The blood + омитий я"
        title_part = re.sub(r"\([^)]*\)", " ", title_part)
        for part in re.split(r"\s*\+\s*", title_part):
            if ")" in part and "(" not in part:  # хвіст обірваної дужки
                continue
            t = clean_title(part)
            if not t or len(t) < 3 or NOISE.search(t):
                continue
            if not re.search(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]{3}", t):
                continue
            songs.append({"title": t, "leader": leader})
    # прибрати повтори в межах служіння
    seen, out = set(), []
    for s in songs:
        k = s["title"].lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def explicit_date(text, msg_dt):
    for line in text.split("\n")[:4]:
        m = re.search(r"\b(\d{1,2})\.\s?(\d{2})(?:\.(\d{2,4}))?\b(?!\d*:)", line)
        if not m:
            continue
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            continue
        years = [int(y) + 2000 if y and len(y) == 2 else int(y)] if y \
            else [msg_dt.year, msg_dt.year + 1]
        for year in years:
            try:
                cand = date(year, mo, d)
            except ValueError:
                continue
            delta = (cand - msg_dt.date()).days
            if not (-3 <= delta <= 60):
                continue
            # автор написав сьогоднішню дату публікації, а не дату служіння
            if cand == msg_dt.date() and cand.weekday() != 6:
                continue
            return cand
    return None


def nearest_sunday(d):
    return d + timedelta(days=(6 - d.weekday()) % 7)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    msgs = extract_messages(sys.argv[1])
    print(f"Повідомлень у експорті: {len(msgs)}")

    by_date = {}
    for m in msgs:
        songs = parse_songs(m["text"])
        if len(songs) < 2:
            continue
        service_date = explicit_date(m["text"], m["dt"]) or nearest_sunday(m["dt"].date())
        cur = by_date.get(service_date)
        if cur is None or (len(songs), m["dt"]) > (len(cur["n"]), cur["dt"]):
            by_date[service_date] = {"n": songs, "dt": m["dt"], "msg": m}

    services = []
    for d, rec in sorted(by_date.items(), reverse=True):
        services.append({
            "id": f"tg-{d.isoformat()}",
            "date": d.isoformat(),
            "title": "Молодіжне служіння",
            "url": "",
            "source": "telegram",
            "songs": rec["n"],
        })
        print(f"{d} ({len(rec['n'])} пісень): " +
              ", ".join(s["title"] for s in rec["n"]))

    out = {"services": services}
    (DATA / "dyouth.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nЗбережено {len(services)} служінь у data/dyouth.json")

    from link_dyouth_videos import link
    link()


if __name__ == "__main__":
    main()
