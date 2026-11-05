// The live widgets on her desktop (deskwidgets.py feeds them): PC stats, now playing, weather, today, notes & timers,
// Discord. A column on the right or left of the main monitor, or on your other monitor. Look-only: the wallpaper
// never gets clicks. Every widget hides itself when it has nothing to show.
window.DeskWidgets = (() => {
  const root = document.createElement("div");
  root.id = "widgets"; root.setAttribute("aria-hidden", "true");
  document.body.appendChild(root);
  const W = { on: [], where: "right", paused: false, el: {}, data: {}, hist: [], tel: null, gpu: null, discord: [] };
  const ORDER = ["stats", "music", "weather", "calendar", "notes", "discord"];
  const TITLE = { stats: "System", music: "Now playing", weather: "Weather", calendar: "Today", notes: "Notes", discord: "Messages" };
  const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const pad = (n) => String(n).padStart(2, "0");
  const clock = (ms) => { ms = Math.max(0, ms); const s = Math.floor(ms / 1000), hh = Math.floor(s / 3600), m = Math.floor(s / 60) % 60;
    return (hh ? hh + ":" + pad(m) : m) + ":" + pad(s % 60); };
  const until = (ms) => { const m = Math.round(ms / 60000); return m < 1 ? "now" : m < 60 ? `in ${m} min` : `in ${Math.floor(m / 60)} h ${pad(m % 60)}`; };
  const ago = (t) => { const s = (Date.now() - t) / 1000; return s < 60 ? "now" : s < 3600 ? Math.round(s / 60) + "m" : Math.round(s / 3600) + "h"; };
  const net = (k) => k >= 1024 ? (k / 1024).toFixed(1) + " MB/s" : Math.round(k) + " KB/s";
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  function card(kind) {
    if (W.el[kind]) return W.el[kind];
    const c = h("section", "wd wd-" + kind); c.hidden = true;
    const hd = h("div", "wh"); hd.append(h("i"), h("b", null, TITLE[kind]), h("span"));
    c.append(hd, h("div", "wb"));
    W.el[kind] = c; return c;
  }
  const body = (kind) => card(kind).querySelector(".wb");
  const side = (kind, text) => { card(kind).querySelector(".wh span").textContent = text || ""; };
  function show(kind, yes) { const c = card(kind); if (c.hidden === !yes) return; c.hidden = !yes; layout(); }

  // ------------------------------------------------------------------ stats: rings for processor and graphics card
  function ring(label) {
    const NS = "http://www.w3.org/2000/svg", s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", "0 0 100 100"); s.classList.add("gauge");
    s.innerHTML = `<circle cx="50" cy="50" r="42" class="g0"/><circle cx="50" cy="50" r="42" class="g1"/>` +
      `<text x="50" y="53" class="gv">--</text><text x="50" y="70" class="gl">${label}</text>`;
    return s;
  }
  const setRing = (s, v, txt) => { s.querySelector(".g1").style.strokeDashoffset = String(264 * (1 - clamp(v, 0, 100) / 100)); s.querySelector(".gv").textContent = txt; s.classList.toggle("hot", v > 90); };
  function buildStats() {
    const b = body("stats"); if (b.firstChild) return;
    const rings = h("div", "rings"); rings.append(ring("CPU"), ring("GPU"), ring("RAM")); b.append(rings);
    const rows = h("div", "bars");
    for (const [k, l] of [["gtemp", "GPU temp"], ["vram", "Video memory"], ["disk", "Disk"]]) {
      const r = h("div", "br"); r.dataset.k = k; r.append(h("span", null, l), h("b", null, "--"), h("i")); r.querySelector("i").append(h("em")); rows.append(r);
    }
    b.append(rows);
    const NS = "http://www.w3.org/2000/svg", sp = document.createElementNS(NS, "svg");
    sp.setAttribute("viewBox", "0 0 120 26"); sp.setAttribute("preserveAspectRatio", "none"); sp.classList.add("spark");
    sp.innerHTML = '<polyline class="sc" points=""/><polyline class="sg" points=""/>';
    const foot = h("div", "foot"); foot.append(h("span", "dn"), h("span", "up"), h("span", "upt"));
    b.append(sp, foot);
  }
  function bar(k, pct, txt, hot) {
    const r = body("stats").querySelector(`[data-k="${k}"]`); if (!r) return;
    r.hidden = txt == null; if (txt == null) return;
    r.querySelector("b").textContent = txt; r.querySelector("em").style.width = clamp(pct, 0, 100) + "%"; r.classList.toggle("hot", !!hot);
  }
  function drawStats() {
    if (!W.on.includes("stats")) return;
    const t = W.tel, g = W.gpu; if (!t && !g) return;
    buildStats(); const b = body("stats"), rs = b.querySelectorAll(".gauge");
    if (t) {
      setRing(rs[0], t.cpu, Math.round(t.cpu) + "%");
      setRing(rs[2], t.ram, Math.round(t.ram) + "%");
      bar("disk", t.disk, t.disk_free != null ? `${t.disk_free} GB free` : Math.round(t.disk) + "%", t.disk > 92);
      b.querySelector(".dn").textContent = "↓ " + net(t.down_kbps || 0);
      b.querySelector(".up").textContent = "↑ " + net(t.up_kbps || 0);
      if (t.uptime) { const d = Math.floor(t.uptime / 86400), hh = Math.floor(t.uptime / 3600) % 24; b.querySelector(".upt").textContent = "up " + (d ? `${d}d ${hh}h` : `${hh}h ${Math.floor(t.uptime / 60) % 60}m`); }
      side("stats", t.ram_total ? `${t.ram_used} / ${t.ram_total} GB` : "");
    }
    rs[1].style.display = g ? "" : "none";
    if (g) {
      setRing(rs[1], g.gpu, Math.round(g.gpu) + "%");
      bar("gtemp", g.gpu_temp, Math.round(g.gpu_temp) + "°C", g.gpu_temp > 82);
      bar("vram", g.vram / (g.vram_total || 1) * 100, `${g.vram} / ${g.vram_total} GB`);
    } else { bar("gtemp", 0, null); bar("vram", 0, null); }
    const pts = (key) => W.hist.map((s, i) => `${(i / Math.max(1, W.hist.length - 1) * 120).toFixed(1)},${(25 - (s[key] || 0) / 100 * 24).toFixed(1)}`).join(" ");
    b.querySelector(".sc").setAttribute("points", pts("cpu"));
    b.querySelector(".sg").setAttribute("points", g ? pts("gpu") : "");
    show("stats", true);
  }

  // ------------------------------------------------------------------ now playing
  function drawMusic() {
    const d = W.data.np, b = body("music");
    if (!W.on.includes("music") || !d || !d.title) { show("music", false); return; }
    if (!b.firstChild) { b.append(h("div", "np-t"), h("div", "np-a"), h("div", "pbar"), h("div", "np-time")); b.querySelector(".pbar").append(h("em")); }
    b.querySelector(".np-t").textContent = d.title; b.querySelector(".np-a").textContent = d.artist || "";
    side("music", d.playing ? d.app || "" : "Paused");
    card("music").classList.toggle("paused", !d.playing);
    show("music", true); tickMusic();
  }
  function tickMusic() {
    const d = W.data.np; if (!d || !d.title || !W.el.music || W.el.music.hidden) return;
    const p = Math.min(d.dur || 0, (d.pos || 0) + (d.playing ? (Date.now() - d.at) / 1000 : 0)), b = body("music");
    b.querySelector(".pbar em").style.width = (d.dur ? p / d.dur * 100 : 0) + "%";
    b.querySelector(".np-time").textContent = d.dur ? `${clock(p * 1000)} / ${clock(d.dur * 1000)}` : "";
  }

  // ------------------------------------------------------------------ weather
  const WX = { sun: "M24 14a10 10 0 1 0 .01 0Z", part: "M20 12a9 9 0 1 0 .01 0Z M26 30h14a6 6 0 0 0 0-12 9 9 0 0 0-17 3",
    cloud: "M14 34h22a8 8 0 0 0 0-16 11 11 0 0 0-21 4 7 7 0 0 0-1 12Z", rain: "M14 28h22a8 8 0 0 0 0-16 11 11 0 0 0-21 4 7 7 0 0 0-1 12Z M18 34l-2 6 M25 34l-2 6 M32 34l-2 6",
    snow: "M14 28h22a8 8 0 0 0 0-16 11 11 0 0 0-21 4 7 7 0 0 0-1 12Z M18 36h.1 M25 38h.1 M32 36h.1", storm: "M14 26h22a8 8 0 0 0 0-16 11 11 0 0 0-21 4 7 7 0 0 0-1 12Z M24 28l-4 8h6l-3 7" };
  const wxKey = (c) => c === 0 ? "sun" : c <= 2 ? "part" : c >= 95 ? "storm" : (c >= 71 && c <= 77) || c === 85 || c === 86 ? "snow" : c >= 51 ? "rain" : "cloud";
  const icon = (c, s) => `<svg viewBox="0 0 48 48" class="wxi" style="width:${s}px;height:${s}px"><path d="${WX[wxKey(c)]}"/></svg>`;
  function drawWeather() {
    const d = W.data.weather;
    if (!W.on.includes("weather") || !d) { show("weather", false); return; }
    const b = body("weather"); b.replaceChildren();
    const top = h("div", "wx-top"); top.innerHTML = icon(d.code, 46);
    const t = h("div"); t.append(h("div", "wx-now", d.now + d.unit), h("div", "wx-l", `${d.label} · feels ${d.feels}°`)); top.append(t);
    const hl = h("div", "wx-hl"); hl.append(h("b", null, d.high + "°"), h("span", null, d.low + "°")); top.append(hl);
    const strip = h("div", "wx-strip");
    (d.hours || []).slice(1, 7).forEach((x) => { const c = h("div", "wx-h"); c.innerHTML = `<span></span>${icon(x.code, 18)}<b></b>`;
      c.querySelector("span").textContent = x.h; c.querySelector("b").textContent = x.t + "°"; if (x.rain >= 50) c.classList.add("wet"); strip.append(c); });
    b.append(top, strip); side("weather", d.place || ""); show("weather", true);
  }

  // ------------------------------------------------------------------ today
  function drawCal() {
    const d = W.data.cal;
    if (!W.on.includes("calendar") || !d) { show("calendar", false); return; }
    const b = body("calendar"); b.replaceChildren();
    b.append(h("div", "cal-next"));
    const ol = h("ol", "cal");
    d.items.slice(0, 6).forEach((it) => { const li = h("li"); li.dataset.at = it.at; if (it.all_day) li.dataset.all = 1; li.append(h("b", null, it.time), h("span", null, it.text)); ol.append(li); });
    if (d.items.length) b.append(ol); else b.append(h("div", "empty", "Nothing on today."));
    side("calendar", d.day || ""); show("calendar", true); tickCal();
  }
  function tickCal() {
    if (!W.el.calendar || W.el.calendar.hidden) return;
    const now = Date.now(), d = W.data.cal, next = d.items.find((i) => !i.all_day && i.at > now), b = body("calendar");
    b.querySelector(".cal-next").textContent = next ? `${next.text} ${until(next.at - now)}` : "Nothing else today";
    b.querySelectorAll("li").forEach((li) => li.classList.toggle("past", !li.dataset.all && +li.dataset.at < now));
  }

  // ------------------------------------------------------------------ notes, lists, timers
  function drawNotes() {
    const d = W.data.notes;
    const any = d && (d.notes.length || d.lists.length || d.timers.length);
    if (!W.on.includes("notes") || !any) { show("notes", false); return; }
    const b = body("notes"); b.replaceChildren();
    d.timers.forEach((t) => { const r = h("div", "tm"); r.dataset.end = t.end; r.dataset.total = t.total;
      r.append(h("span", null, t.label), h("b", null, ""), h("i")); r.querySelector("i").append(h("em")); b.append(r); });
    d.notes.forEach((n) => { const s = h("div", "sticky"); s.append(h("b", null, n.title), h("p", null, n.text)); b.append(s); });
    d.lists.forEach((l) => {
      const done = l.items.filter((i) => i.done).length, box = h("div", "lst");
      box.append(h("b", null, `${l.title} · ${done}/${l.items.length}`));
      const ul = h("ul"); l.items.slice(0, 6).forEach((i) => { const li = h("li", i.done ? "done" : "", i.t); ul.append(li); }); box.append(ul); b.append(box);
    });
    side("notes", d.timers.length ? `${d.timers.length} timer${d.timers.length > 1 ? "s" : ""}` : "");
    show("notes", true); tickTimers();
  }
  function tickTimers() {
    if (!W.el.notes || W.el.notes.hidden) return;
    body("notes").querySelectorAll(".tm").forEach((r) => {
      const left = +r.dataset.end - Date.now(), tot = (+r.dataset.total || 1) * 1000;
      r.querySelector("b").textContent = left > 0 ? clock(left + 999) : "Done";
      r.querySelector("em").style.width = clamp(left / tot * 100, 0, 100) + "%"; r.classList.toggle("ring", left <= 0);
    });
  }

  // ------------------------------------------------------------------ Discord
  function drawDiscord() {
    if (!W.on.includes("discord") || !W.discord.length) { show("discord", false); return; }
    const b = body("discord"); b.replaceChildren();
    W.discord.slice(-4).reverse().forEach((m) => { const r = h("div", "dm"); r.append(h("b", null, (m.src === "Phone" ? "📱 " : "") + m.who + (m.channel ? " · #" + m.channel : "")), h("em", null, ago(m.at)), h("p", null, m.text)); b.append(r); });
    side("discord", ""); show("discord", true);
  }

  // ------------------------------------------------------------------ placement
  function layout() {
    const M = window.deskMonitors && window.deskMonitors(); if (!M) return;
    const mon = W.where === "second" && M.o ? M.o : M.p;
    // a column down the edge; if they don't all fit, a second column grows inwards
    const w = Math.round(clamp(mon.wh * .27, 270, 380)), right = W.where !== "left";
    root.style.setProperty("--ww", w + "px");
    root.classList.toggle("rt", right);
    root.style.left = right ? "auto" : mon.wx + 22 + "px";
    root.style.right = right ? innerWidth - (mon.wx + mon.ww) + 22 + "px" : "auto";
    root.style.top = mon.wy + 22 + "px"; root.style.height = mon.wh - 44 + "px";
    ORDER.forEach((k) => { if (W.el[k]) root.appendChild(W.el[k]); });
    root.classList.toggle("off", !W.on.length);
  }

  function redrawAll() { drawStats(); drawMusic(); drawWeather(); drawCal(); drawNotes(); drawDiscord(); ORDER.forEach((k) => { if (!W.on.includes(k) && W.el[k]) show(k, false); }); layout(); }

  setInterval(() => { if (W.paused) return; tickMusic(); tickTimers(); }, 1000);
  setInterval(() => { if (W.paused) return; tickCal(); if (W.discord.length) drawDiscord(); }, 30000);

  return {
    layout,
    has: (k) => W.on.includes(k),
    on(e) {
      switch (e.type) {
        case "widgets": W.on = e.on || []; W.where = e.where || "right"; redrawAll(); break;
        case "desk_pause": W.paused = !!e.on; break;
        case "telemetry": W.tel = e; W.hist.push({ cpu: e.cpu, gpu: W.gpu ? W.gpu.gpu : 0 }); if (W.hist.length > 60) W.hist.shift(); if (!W.paused) drawStats(); break;
        case "w_gpu": W.gpu = e; if (!W.paused) drawStats(); break;
        case "w_np": W.data.np = e.data ? Object.assign({}, e.data, { at: Date.now() }) : null; drawMusic(); break;
        case "w_weather": W.data.weather = e.data; drawWeather(); break;
        case "w_cal": W.data.cal = e.data; drawCal(); break;
        case "w_notes": W.data.notes = e.data; drawNotes(); break;
        case "discord": if (e.text) { W.discord.push({ who: e.from || e.who || "Someone", channel: e.channel || "", text: String(e.text).slice(0, 200), at: Date.now(), src: "Discord" }); if (W.discord.length > 12) W.discord.shift(); drawDiscord(); } break;
        case "phone_note": if (e.text || e.from) { W.discord.push({ who: e.from || "Phone", channel: "", text: String(e.text || "").slice(0, 200), at: Date.now(), src: "Phone" }); if (W.discord.length > 12) W.discord.shift(); drawDiscord(); } break;
        case "desk_init": case "desk_layout": setTimeout(layout, 0); break;
      }
    },
  };
})();
