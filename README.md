# Worship Tracker

Локальний дашборд для відстеження пісень прославлення по церквах:
сетлісти, частота виконань, нові пісні, спільний репертуар.

## Церкви

| Церква | Джерело даних |
|---|---|
| Gateway Church (Dallas–Fort Worth) | авто: таймкоди YouTube-стрімів [@gatewaychurchtv](https://www.youtube.com/@gatewaychurchtv/streams) |
| Alfa Church (Київ) | авто: таймкоди YouTube-стрімів каналу Alfa Church |
| Bethel Church (Redding) | авто: розпізнавання пісень з автосубтитрів стрімів [ibetheltv](https://www.youtube.com/user/ibetheltv/streams) за сигнатурними фразами (`data/song_signatures.json`) |
| Ecclesia Church (Київ) | вручну (канал не архівує повні служіння) |
| D.Youth (Львів) | імпорт списків із Telegram-групи команди + посилання на стріми [@dyouthlviv](https://www.youtube.com/@dyouthlviv/streams) |
| Elevation (Charlotte) | знімки офіційного плейліста «Sunday Set List» — `fetch_elevation_playlist.py` (ротація без дат служінь) |
| Planetshakers (Melbourne) | недоступно: YouTube-архіву нема, Facebook-реплеї yt-dlp наразі не парсить |

## Розпізнавання з субтитрів (Bethel та подібні)

Для церков без таймкодів пісень парсер `captions` тягне англійські
автосубтитри стріму і шукає в них сигнатурні фрази пісень (приспіви
повторюються — тому детекція надійна). Словник: `data/song_signatures.json`
(`"Назва пісні": ["фраза 1", "фраза 2"]`) — доповнюйте його, якщо якась
пісня не розпізналась: додайте характерний рядок приспіву малими літерами.
Той самий механізм підходить для Life.Church, Hillsong, Lakewood, VOUS тощо —
достатньо додати церкву в `churches.json` з `"parser": "captions"`.

## Імпорт D.Youth з Telegram

Telegram Desktop → група команди → ⋮ → «Експорт історії чату» (HTML, медіа не потрібні), потім:

```bash
./venv/bin/python import_telegram.py "~/Downloads/Telegram Desktop/ChatExport_<дата>/messages.html"
```

Дата служіння: явна дата в повідомленні, інакше найближча наступна неділя
від дати публікації. З кількох версій списку на ту саму неділю береться
найповніша. Після імпорту `link_dyouth_videos.py` автоматично підставляє
посилання на YouTube-стріми (індекс — `data/dyouth_videos.json`;
перезібрати: див. скрипт). Імпорт перезаписує `data/dyouth.json`.

## Запуск

```bash
./venv/bin/python app.py
# → http://127.0.0.1:8777
```

## Оновлення даних з YouTube

Кнопка «↻ Оновити з YouTube» на вкладці церкви, або з термінала:

```bash
./venv/bin/python fetch.py --all --months 6
```

Уже збережені служіння не перезаписуються, тож ручні правки
(видалені зайві «пісні» з парсингу) зберігаються.

## Дані

`data/<church>.json` — по файлу на церкву, звичайний JSON, можна
правити руками. Нормалізація назв пісень (обʼєднання варіантів
написання) — у `static/app.js` (`ALIASES`).

## Встановлення з нуля

```bash
python3 -m venv venv && ./venv/bin/pip install flask yt-dlp
```
