/* Worship Tracker — дашборд */
let DB = { churches: [], services: {} };
let activeTab = "all";

/* Період метрик: дата "від" (до — завжди сьогодні) */
const PRESETS = [
  ["3m", "3 міс", 3], ["6m", "6 міс", 6], ["1y", "Рік", 12], ["all", "Весь час", null],
];
function presetDate(months) {
  if (months === null) return "";
  const d = new Date();
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
}
let period = { preset: "6m", date: presetDate(6) };
try {
  const saved = JSON.parse(localStorage.getItem("wt.period") || "null");
  if (saved && "date" in saved) period = saved;
  if (saved && saved.preset !== "custom") period.date = presetDate(PRESETS.find(p => p[0] === saved.preset)?.[2] ?? 6);
} catch {}
function setPeriod(p) {
  period = p;
  localStorage.setItem("wt.period", JSON.stringify(p));
  render();
}

const MONTHS_UA = ["січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру"];

/* Нормалізація назв пісень: обʼєднує варіанти написання */
const ALIASES = {
  "angus dei": "agnus dei",
  "worhty of it all": "worthy of it all",
  "what a worth name": "what a beautiful name",
  "heres to the one": "here's to the one",
  "here's to the one": "here's to the one",
  "i've witnessed": "i've witnessed it",
  "i witnessed it": "i've witnessed it",
  "o come to altar": "o come to the altar",
  "make me brave": "you make me brave",
  "thank you jesus for blood": "thank you jesus for the blood",
  "this is living now": "this is living",
  "forever & amen": "forever and amen",
  "no one like the lord 2": "no one like the lord",
  "glorious": "glorious day",
  "pure": "pursue",
  "draw me close": "draw me close to you",
};
function normTitle(t) {
  let n = t.toLowerCase()
    .replace(/['’‘`"«»“”]/g, "")
    .replace(/\s*\([^)]*\)\s*/g, " ")
    .replace(/\s*\/\s*/g, "/")
    .replace(/[!?.]+$/, "")
    .replace(/\s+/g, " ")
    .trim();
  return ALIASES[n] || n;
}

const fmtDate = (iso) => {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
};

let TODOS = { items: [] };
let SONGS = [];
async function loadData() {
  const [d, t, s] = await Promise.all([fetch("/api/data"), fetch("/api/todos"), fetch("/api/songs")]);
  DB = await d.json();
  TODOS = await t.json();
  SONGS = await s.json();
}

/* ---------- агрегація ---------- */

function servicesOf(churchId) {
  if (churchId === "all") {
    return Object.entries(DB.services).flatMap(([cid, list]) =>
      list.map((s) => ({ ...s, church: cid }))
    );
  }
  return (DB.services[churchId] || []).map((s) => ({ ...s, church: churchId }));
}

/* Зведення по піснях: {key, title, plays, first, last, leaders, churches} */
function songStats(services) {
  const map = new Map();
  for (const svc of services) {
    for (const song of svc.songs || []) {
      const key = normTitle(song.title);
      if (!key) continue;
      let rec = map.get(key);
      if (!rec) {
        rec = { key, titles: {}, plays: 0, first: svc.date, last: svc.date, leaders: new Set(), churches: new Set() };
        map.set(key, rec);
      }
      rec.titles[song.title] = (rec.titles[song.title] || 0) + 1;
      rec.plays++;
      if (svc.date < rec.first) rec.first = svc.date;
      if (svc.date > rec.last) rec.last = svc.date;
      if (song.leader) rec.leaders.add(song.leader);
      rec.churches.add(svc.church);
    }
  }
  return [...map.values()].map((r) => ({
    ...r,
    title: Object.entries(r.titles).sort((a, b) => b[1] - a[1])[0][0],
    leaders: [...r.leaders],
    churches: [...r.churches],
  }));
}

/* Нові пісні по місяцях (перша поява) */
function newSongsByMonth(stats, monthsBack = 6) {
  const buckets = [];
  const now = new Date();
  for (let i = monthsBack - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = monthsBack > 6 ? `${MONTHS_UA[d.getMonth()]} ${String(d.getFullYear()).slice(2)}` : MONTHS_UA[d.getMonth()];
    buckets.push({ ym, label, count: 0 });
  }
  for (const s of stats) {
    const b = buckets.find((b) => s.first.startsWith(b.ym));
    if (b) b.count++;
  }
  return buckets;
}

/* ---------- рендер ---------- */

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function renderTabs() {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  const tabs = [{ id: "all", name: "Всі церкви" }, ...DB.churches, { id: "songs", name: "🎵 Пісні" }, { id: "todo", name: "✓ Todo" }];
  for (const t of tabs) {
    const n = t.id === "all"
      ? Object.values(DB.services).reduce((a, l) => a + l.length, 0)
      : t.id === "songs"
        ? SONGS.length
        : t.id === "todo"
        ? TODOS.items.filter((i) => !i.done).length
        : (DB.services[t.id] || []).length;
    const btn = el(`<button class="tab ${t.id === activeTab ? "active" : ""}">${esc(t.name)}<span class="count">${n}</span></button>`);
    btn.onclick = () => { activeTab = t.id; render(); };
    nav.appendChild(btn);
  }
}

function tile(value, label, hint = "") {
  return `<div class="tile"><div class="value">${value}</div><div class="label">${label}</div>${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
}

function attachTooltip(node, html) {
  const tip = document.getElementById("tooltip");
  node.addEventListener("mousemove", (e) => {
    tip.innerHTML = html;
    tip.hidden = false;
    tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 280) + "px";
    tip.style.top = e.clientY + 14 + "px";
  });
  node.addEventListener("mouseleave", () => { tip.hidden = true; });
}

function barList(stats, topN = 12) {
  const top = [...stats].sort((a, b) => b.plays - a.plays || (a.title > b.title ? 1 : -1)).slice(0, topN);
  if (!top.length) return el(`<div class="empty">Ще немає даних</div>`);
  const max = top[0].plays;
  const wrap = el(`<div class="barlist"></div>`);
  for (const s of top) {
    wrap.appendChild(el(`<div class="song-name" title="${esc(s.title)}">${esc(s.title)}</div>`));
    const track = el(`<div class="bar-track"><div class="bar" style="width:${(s.plays / max) * 100}%"></div><span class="bar-value">${s.plays}</span></div>`);
    attachTooltip(track.querySelector(".bar"),
      `<b>${esc(s.title)}</b><br>Виконань: ${s.plays}<br>Вперше: ${fmtDate(s.first)}<br>Востаннє: ${fmtDate(s.last)}` +
      (s.leaders.length ? `<br>Лідери: ${esc(s.leaders.join(", "))}` : ""));
    wrap.appendChild(track);
  }
  return wrap;
}

function colChart(buckets, tooltipLabel) {
  const max = Math.max(...buckets.map((b) => b.count), 1);
  const wrap = el(`<div></div>`);
  const chart = el(`<div class="colchart"></div>`);
  for (const b of buckets) {
    const col = el(`<div class="col"><span class="v">${b.count || ""}</span><div class="bar" style="height:${Math.max((b.count / max) * 100, 2)}%"></div></div>`);
    attachTooltip(col.querySelector(".bar"), `<b>${b.label}</b>: ${b.count} ${tooltipLabel}`);
    chart.appendChild(col);
  }
  wrap.appendChild(chart);
  const thin = buckets.length > 14;  // при довгому періоді підписуємо через місяць
  wrap.appendChild(el(`<div class="colchart-labels">${buckets.map((b, i) => `<span>${thin && i % 2 ? "" : b.label}</span>`).join("")}</div>`));
  return wrap;
}

let sortKey = "plays", sortDir = -1;
function songTable(stats, showChurches) {
  const cols = [
    ["title", "Пісня"], ["plays", "Виконань"], ["first", "Вперше"], ["last", "Востаннє"],
    showChurches ? ["churches", "Церкви"] : ["leaders", "Лідери"],
  ];
  const rows = [...stats].sort((a, b) => {
    const va = a[sortKey], vb = b[sortKey];
    return (va > vb ? 1 : va < vb ? -1 : 0) * sortDir;
  });
  const churchName = (id) => (DB.churches.find((c) => c.id === id) || { name: id }).name;
  const table = el(`<table>
    <thead><tr>${cols.map(([k, l]) => `<th data-k="${k}">${l}${k === sortKey ? (sortDir < 0 ? " ↓" : " ↑") : ""}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((s) => `<tr>
      <td>${esc(s.title)}</td>
      <td class="num">${s.plays}</td>
      <td class="num">${fmtDate(s.first)}</td>
      <td class="num">${fmtDate(s.last)}</td>
      <td>${showChurches ? esc(s.churches.map(churchName).join(", ")) : esc(s.leaders.join(", "))}</td>
    </tr>`).join("")}</tbody>
  </table>`);
  table.querySelectorAll("th").forEach((th) => {
    th.onclick = () => {
      const k = th.dataset.k;
      if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = k === "title" ? 1 : -1; }
      render();
    };
  });
  return table;
}

function serviceList(services, churchId) {
  const wrap = el(`<div class="services"></div>`);
  if (!services.length) {
    wrap.appendChild(el(`<div class="empty">Служінь ще немає — додайте перше кнопкою вгорі</div>`));
    return wrap;
  }
  const church = DB.churches.find(c => c.id === churchId);
  for (const svc of [...services].sort((a, b) => (a.date < b.date ? 1 : -1))) {
    const node = el(`<div class="service" data-service-id="${svc.id}">
      <div class="service-head">
        <span class="date">${fmtDate(svc.date)}</span>
        <span class="title">${esc(svc.title || "")}</span>
        ${svc.url ? `<a href="${esc(svc.url)}" target="_blank" rel="noopener">відео ↗</a>` : ""}
        <button class="btn-edit-service" title="Редагувати пісні">✎</button>
        <button class="del" title="Видалити служіння">видалити</button>
      </div>
      <div class="chips"></div>
    </div>`);

    const chips = node.querySelector(".chips");
    const renderSongs = (editMode) => {
      chips.innerHTML = "";
      (svc.songs || []).forEach((song, i) => {
        const chip = el(`<span class="chip" data-idx="${i}">${esc(song.title)}${song.leader ? `<span class="leader">${esc(song.leader)}</span>` : ""}${editMode ? `<button class="btn-del-song" data-idx="${i}">×</button>` : ""}</span>`);
        if (editMode) {
          chip.style.cursor = "pointer";
          chip.onclick = (e) => {
            if (e.target.classList.contains("btn-del-song")) return;
            editSongInline(chip, svc, i, church?.worship_leaders || []);
          };
          chip.querySelector(".btn-del-song").onclick = async (e) => {
            e.stopPropagation();
            await fetch(`/api/services/${svc.church}/${svc.id}/remove_song`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ index: i }),
            });
            await loadData(); render();
          };
        }
        chips.appendChild(chip);
      });
      if (!(svc.songs || []).length) {
        chips.appendChild(el(`<span class="chip"><span class="leader">пісні не розпізнані</span></span>`));
      }
    };
    renderSongs(false);

    const editBtn = node.querySelector(".btn-edit-service");
    editBtn.onclick = () => {
      node.classList.toggle("edit-mode");
      if (node.classList.contains("edit-mode")) {
        renderSongs(true);
        const addForm = el(`<div class="service-add-song">
          <input type="text" class="add-title" placeholder="Назва пісні">
          <input type="text" class="add-leader" placeholder="Лідер" list="leaders-list-${svc.id}">
          <datalist id="leaders-list-${svc.id}">
            ${(church?.worship_leaders || []).map(l => `<option value="${esc(l)}">`).join("")}
          </datalist>
          <button class="btn btn-primary btn-add">+ Додати</button>
          <button class="btn btn-done">Готово</button>
        </div>`);
        node.appendChild(addForm);

        addForm.querySelector(".btn-add").onclick = async () => {
          const title = addForm.querySelector(".add-title").value.trim();
          if (!title) { alert("Введіть назву пісні"); return; }
          await fetch(`/api/services/${svc.church}/${svc.id}/add_song`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, leader: addForm.querySelector(".add-leader").value.trim() }),
          });
          await loadData(); render();
        };

        addForm.querySelector(".btn-done").onclick = () => {
          node.classList.remove("edit-mode");
          renderSongs(false);
          addForm.remove();
        };
      } else {
        renderSongs(false);
        node.querySelector(".service-add-song")?.remove();
      }
    };

    node.querySelector(".del").onclick = async () => {
      if (!confirm(`Видалити служіння ${fmtDate(svc.date)}?`)) return;
      await fetch(`/api/services/${svc.church}/${svc.id}`, { method: "DELETE" });
      await loadData(); render();
    };
    wrap.appendChild(node);
  }
  return wrap;
}

function card(title, note, child) {
  const c = el(`<section class="card"><h2>${title}</h2>${note ? `<p class="card-note">${note}</p>` : ""}</section>`);
  c.appendChild(child);
  return c;
}

function editSongInline(chipEl, svc, songIdx, worshipLeaders = []) {
  const song = svc.songs[songIdx];
  const form = el(`<div class="chip-edit-form">
    <input class="edit-title" value="${esc(song.title)}" placeholder="Назва пісні">
    <input class="edit-leader" value="${esc(song.leader || "")}" placeholder="Лідер" list="leaders-list-edit">
    <datalist id="leaders-list-edit">
      ${worshipLeaders.map(l => `<option value="${esc(l)}">`).join("")}
    </datalist>
    <input class="edit-artist" value="${esc(song.artist || "")}" placeholder="Виконавець">
    <button class="btn btn-primary btn-save">✓</button>
    <button class="btn btn-cancel">✕</button>
  </div>`);

  chipEl.replaceWith(form);

  form.querySelector(".btn-save").onclick = async () => {
    const title = form.querySelector(".edit-title").value.trim();
    if (!title) { alert("Введіть назву пісні"); return; }
    await fetch(`/api/services/${svc.church}/${svc.id}/song/${songIdx}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        leader: form.querySelector(".edit-leader").value.trim(),
        artist: form.querySelector(".edit-artist").value.trim(),
      }),
    });
    await loadData(); render();
  };

  form.querySelector(".btn-cancel").onclick = () => {
    render();
  };

  form.querySelector(".edit-title").focus();
}

function showAddSongModal(churchId, serviceId, worshipLeaders = []) {
  const dialog = el(`<dialog>
    <h2>Додати пісню</h2>
    <label>Назва пісні
      <input type="text" id="song-title" placeholder="наприклад, Worthy Is The Lamb" autofocus>
    </label>
    <label>Лідер прославлення (опціонально)
      <input type="text" id="song-leader" placeholder="ім'я лідера" list="leaders-list">
      <datalist id="leaders-list">
        ${worshipLeaders.map(l => `<option value="${esc(l)}">`).join("")}
      </datalist>
    </label>
    <label>Оригінальний виконавець (опціонально)
      <input type="text" id="song-artist" placeholder="наприклад, Jenn Johnson">
    </label>
    <div class="form-actions">
      <button class="btn">Скасувати</button>
      <button class="btn btn-primary" id="save-song">Додати</button>
    </div>
  </dialog>`);

  dialog.querySelector(".btn").onclick = () => dialog.close();
  dialog.querySelector("#save-song").onclick = async () => {
    const title = dialog.querySelector("#song-title").value.trim();
    if (!title) {
      alert("Введіть назву пісні");
      return;
    }
    await fetch(`/api/services/${churchId}/${serviceId}/add_song`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        leader: dialog.querySelector("#song-leader").value.trim(),
        artist: dialog.querySelector("#song-artist").value.trim(),
      }),
    });
    await loadData();
    render();
    dialog.close();
  };

  document.body.appendChild(dialog);
  dialog.showModal();
  dialog.addEventListener("close", () => dialog.remove());
  dialog.querySelector("#song-title").focus();
}

function periodBar() {
  const bar = el(`<div class="period-bar"><span class="period-label">Показувати від:</span></div>`);
  for (const [id, label] of PRESETS) {
    const b = el(`<button class="tab ${period.preset === id ? "active" : ""}">${label}</button>`);
    b.onclick = () => setPeriod({ preset: id, date: presetDate(PRESETS.find(p => p[0] === id)[2]) });
    bar.appendChild(b);
  }
  const input = el(`<input type="date" class="period-input" title="Власна дата «від»">`);
  input.value = period.preset === "custom" ? period.date : "";
  input.onchange = () => { if (input.value) setPeriod({ preset: "custom", date: input.value }); };
  bar.appendChild(input);
  if (period.date) bar.appendChild(el(`<span class="period-note">від ${fmtDate(period.date)} до сьогодні</span>`));
  return bar;
}

function renderSongs(view) {
  const wrap = el(`<section class="card"><h2>База пісень</h2><p class="card-note">${SONGS.length} унікальних пісень — редагуйте виконавця, бо більшість без нього</p></section>`);

  const table = el(`<table>
    <thead>
      <tr>
        <th>Назва пісні</th>
        <th>Оригінальний виконавець</th>
        <th style="width: 120px;">Церкви</th>
        <th style="width: 60px;">Дія</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>`);

  const tbody = table.querySelector("tbody");
  for (const song of SONGS) {
    const row = el(`<tr data-song-id="${song.id}">
      <td>${esc(song.title)}</td>
      <td class="song-artist">${song.artist ? esc(song.artist) : '<span style="color: var(--muted); font-style: italic;">не вказано</span>'}</td>
      <td style="font-size: 12px; color: var(--ink-2);">${(song.churches || []).join(", ")}</td>
      <td><button class="btn btn-edit-song" data-id="${song.id}">✎</button></td>
    </tr>`);

    row.querySelector(".btn-edit-song").onclick = () => {
      editSongModal(song);
    };
    tbody.appendChild(row);
  }

  wrap.appendChild(table);
  view.appendChild(wrap);
}

function editSongModal(song) {
  const dialog = el(`<dialog>
    <h2>Редагувати пісню</h2>
    <label>Назва
      <input type="text" id="edit-song-title" value="${esc(song.title)}">
    </label>
    <label>Оригінальний виконавець
      <input type="text" id="edit-song-artist" value="${esc(song.artist || "")}" placeholder="напр. Jenn Johnson">
    </label>
    <p style="color: var(--muted); font-size: 13px; margin-top: 12px;">
      Церкви де виконується: ${(song.churches || []).join(", ")}
    </p>
    <div class="form-actions">
      <button class="btn">Скасувати</button>
      <button class="btn btn-primary" id="save-edit-song">Зберегти</button>
    </div>
  </dialog>`);

  dialog.querySelector(".btn").onclick = () => dialog.close();
  dialog.querySelector("#save-edit-song").onclick = async () => {
    const artist = dialog.querySelector("#edit-song-artist").value.trim();
    await fetch(`/api/songs/${song.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ artist: artist || null }),
    });
    await loadData();
    render();
    dialog.close();
  };

  document.body.appendChild(dialog);
  dialog.showModal();
  dialog.addEventListener("close", () => dialog.remove());
  dialog.querySelector("#edit-song-artist").focus();
}

function renderTodo(view) {
  const open = TODOS.items.filter((i) => !i.done);
  const done = TODOS.items.filter((i) => i.done);
  const wrap = el(`<section class="card"><h2>Todo</h2><p class="card-note">задачі по джерелах даних; зберігаються на сервері (data/todos.json)</p></section>`);

  const addRow = el(`<div class="todo-add"><input type="text" placeholder="Нова задача…"><button class="btn btn-primary">Додати</button></div>`);
  const addInput = addRow.querySelector("input");
  const submit = async () => {
    if (!addInput.value.trim()) return;
    await fetch("/api/todos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: addInput.value }) });
    await loadData(); render();
  };
  addRow.querySelector("button").onclick = submit;
  addInput.onkeydown = (e) => { if (e.key === "Enter") submit(); };
  wrap.appendChild(addRow);

  const list = el(`<div class="todo-list"></div>`);
  for (const it of [...open, ...done]) {
    const row = el(`<label class="todo-item ${it.done ? "done" : ""}">
      <input type="checkbox" ${it.done ? "checked" : ""}>
      <span class="todo-text">${esc(it.text)}</span>
      <button class="x" title="Видалити">×</button>
    </label>`);
    row.querySelector("input").onchange = async (e) => {
      await fetch(`/api/todos/${it.id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: e.target.checked }) });
      await loadData(); render();
    };
    row.querySelector(".x").onclick = async (e) => {
      e.preventDefault();
      await fetch(`/api/todos/${it.id}`, { method: "DELETE" });
      await loadData(); render();
    };
    list.appendChild(row);
  }
  if (!TODOS.items.length) list.appendChild(el(`<div class="empty">Задач немає</div>`));
  wrap.appendChild(list);
  view.appendChild(wrap);
}

function render() {
  renderTabs();
  const view = document.getElementById("view");
  view.innerHTML = "";
  if (activeTab === "songs") { renderSongs(view); return; }
  if (activeTab === "todo") { renderTodo(view); return; }
  view.appendChild(periodBar());

  const services = servicesOf(activeTab).filter((s) => !period.date || s.date >= period.date);
  const withSongs = services.filter((s) => (s.songs || []).length);
  const stats = songStats(services);
  const church = DB.churches.find((c) => c.id === activeTab);

  /* Плитки */
  const avg = withSongs.length
    ? (withSongs.reduce((a, s) => a + s.songs.length, 0) / withSongs.length).toFixed(1)
    : "—";
  const days30 = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
  const new30 = stats.filter((s) => s.first >= days30).length;
  view.appendChild(el(`<div class="tiles">
    ${tile(services.length, "служінь", withSongs.length < services.length ? `${withSongs.length} із сетлістами` : "")}
    ${tile(stats.length, "унікальних пісень")}
    ${tile(avg, "пісень за служіння", "в середньому")}
    ${tile(new30, "нових пісень", "за останні 30 днів")}
  </div>`));

  /* Кнопка оновлення для auto-церков */
  if (church && church.auto) {
    const bar = el(`<div style="margin-bottom:16px; display:flex; gap:10px; align-items:center;">
      <button class="btn" id="btn-refresh">↻ Оновити з YouTube</button>
      <span style="color:var(--muted); font-size:13px;">канал: <a href="${esc(church.channel)}" target="_blank" rel="noopener" style="color:var(--series-1)">${esc(church.channel.replace("https://www.youtube.com/", ""))}</a></span>
    </div>`);
    bar.querySelector("#btn-refresh").onclick = async (e) => {
      const btn = e.target;
      btn.disabled = true; btn.textContent = "Оновлюю… (до 2 хв)";
      const res = await fetch(`/api/refresh/${church.id}`, { method: "POST" });
      const j = await res.json();
      btn.disabled = false; btn.textContent = "↻ Оновити з YouTube";
      let log = document.getElementById("refresh-log");
      if (!log) { log = el(`<pre class="refresh-log" id="refresh-log"></pre>`); bar.after(log); }
      log.textContent = j.log || (j.ok ? "Готово" : "Помилка");
      await loadData(); render();
    };
    view.appendChild(bar);
  }

  /* Графіки */
  const grid = el(`<div class="grid-2"></div>`);
  grid.appendChild(card("Топ пісень", "за кількістю виконань у вибраному періоді", barList(stats)));
  const oldest = services.length ? services.reduce((a, s) => (s.date < a ? s.date : a), "9999") : "";
  const monthsSpan = oldest
    ? Math.min(24, Math.max(6, (new Date().getFullYear() - +oldest.slice(0, 4)) * 12 + (new Date().getMonth() + 1 - +oldest.slice(5, 7)) + 1))
    : 6;
  grid.appendChild(card("Нові пісні по місяцях", "місяць першої появи в сетлістах у вибраному періоді", colChart(newSongsByMonth(stats, monthsSpan), "нових пісень")));
  view.appendChild(grid);

  /* Спільні пісні (тільки в огляді) */
  if (activeTab === "all") {
    const shared = stats.filter((s) => s.churches.length > 1).sort((a, b) => b.plays - a.plays);
    if (shared.length) {
      view.appendChild(card("Пісні, спільні для кількох церков", "одна пісня в репертуарі різних церков",
        songTable(shared, true)));
    }
  }

  /* Таблиця всіх пісень */
  view.appendChild(card(`Усі пісні (${stats.length})`, "клік по заголовку — сортування", songTable(stats, activeTab === "all")));

  /* Служіння */
  view.appendChild(card("Служіння та сетлісти", "× на пісні — прибрати зайве (шум парсингу); зміни зберігаються", serviceList(services, activeTab)));
}

/* ---------- форма додавання ---------- */

function setupForm() {
  const modal = document.getElementById("modal-add");
  const form = document.getElementById("form-add");
  document.getElementById("btn-add").onclick = () => {
    const sel = document.getElementById("add-church");
    sel.innerHTML = DB.churches.map((c) => `<option value="${c.id}" ${c.id === activeTab ? "selected" : ""}>${esc(c.name)}</option>`).join("");
    const preferred = DB.churches.find((c) => c.id === activeTab) ? activeTab : "dyouth";
    sel.value = preferred;
    form.reset();
    sel.value = preferred;
    modal.showModal();
  };
  document.getElementById("btn-cancel").onclick = () => modal.close();
  form.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const songs = String(fd.get("songs") || "").split("\n").map((line) => {
      const [title, leader] = line.split(/\s+—\s+|\s+-\s+/);
      return { title: (title || "").trim(), leader: (leader || "").trim() };
    }).filter((s) => s.title);
    await fetch("/api/services", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        church: fd.get("church"), date: fd.get("date"),
        title: fd.get("title"), songs,
      }),
    });
    modal.close();
    activeTab = fd.get("church");
    await loadData(); render();
  };
}

(async function init() {
  await loadData();
  setupForm();
  render();
})();
