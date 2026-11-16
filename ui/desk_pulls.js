// What he pulls up: live panels on the desktop beside his ring while he answers (pulls.py sends them).
// Stocks with live charts, weather with radar, your day as a timeline, the sources he read, your PC's insides,
// a preview of a file he made, your network, a pre-game briefing, and trackers. One can take the middle of the
// screen (focus); "clear that" or "back" puts things away. Each kind can live left, right, centre or on the
// other monitor ("put the stocks on my second monitor"). Everything here is look-only: the wallpaper gets no clicks.
// All text goes in with textContent, never as HTML: titles come from the web.
"use strict";
window.DeskPulls = (() => {
  const root = document.createElement("div");
  root.id = "pulls"; root.setAttribute("aria-hidden", "true");
  document.body.appendChild(root);
  const NS = "http://www.w3.org/2000/svg";
  const P = { list: [], layout: {}, focus: null, tel: null, gpu: null, max: 3, hist: [] };
  const DEFAULT_WHERE = { pc: "right", network: "right", briefing: "right", weather: "right" };
  const TITLES = { stock: "Market", weather: "Weather", calendar: "Today", sources: "Sources", pc: "Your PC", file: "Made",
                   network: "Network", briefing: "Briefing", tracker: "Tracking" };
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------------ little builders
  const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const s = (tag, attrs, text) => { const e = document.createElementNS(NS, tag); for (const k in attrs || {}) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };
  const num = (v, d = 2) => v == null || isNaN(v) ? "--" : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : (+v).toFixed(d);
  const pct = (v) => v == null || isNaN(v) ? "" : (v >= 0 ? "+" : "") + (+v).toFixed(2) + "%";
  const okImg = (u) => typeof u === "string" && /^https:\/\/(tilecache\.rainviewer\.com|[abcd]\.basemaps\.cartocdn\.com)\//.test(u);

  function frame(kind, title, sub, live) {
    const el = h("section", "pl pl-" + kind);
    const hd = h("header", "plh");
    hd.append(h("i", "pli"), h("b", null, title || TITLES[kind] || kind), h("span", "pls", sub || ""));
    if (live) { const lv = h("em", "plive"); lv.append(h("i"), h("span", null, "live")); hd.append(lv); }
    const bd = h("div", "plb"), ft = h("footer", "plf");
    el.append(hd, bd, ft);
    for (const c of ["tl", "tr", "bl", "br"]) el.append(h("u", "plc " + c));     // corner marks, styled per scene
    return el;
  }
  const body = (el) => el.querySelector(".plb");
  const foot = (el, t) => { el.querySelector(".plf").textContent = t || ""; };

  // ------------------------------------------------------------------ 1. stocks: price, change, a real chart
  function chart(closes, prev, w, hgt, up) {
    const sv = s("svg", { viewBox: `0 0 ${w} ${hgt}`, class: "chart", preserveAspectRatio: "none" });
    const v = (closes || []).filter((x) => x != null);
    if (v.length < 2) return sv;
    const lo = Math.min(...v, prev ?? Infinity), hi = Math.max(...v, prev ?? -Infinity), pad = (hi - lo) * .08 || 1;
    const X = (i) => i / (v.length - 1) * w, Y = (x) => hgt - (x - lo + pad) / (hi - lo + pad * 2) * hgt;
    const line = v.map((x, i) => `${X(i).toFixed(1)},${Y(x).toFixed(1)}`).join(" ");
    for (let k = 1; k < 4; k++) sv.append(s("line", { x1: 0, x2: w, y1: hgt * k / 4, y2: hgt * k / 4, class: "grid" }));
    sv.append(s("polygon", { points: `0,${hgt} ${line} ${w},${hgt}`, class: "area " + (up ? "up" : "dn") }));
    if (prev != null) sv.append(s("line", { x1: 0, x2: w, y1: Y(prev), y2: Y(prev), class: "prev" }));
    sv.append(s("polyline", { points: line, class: "ln " + (up ? "up" : "dn") }));
    const li = v.length - 1;
    sv.append(s("circle", { cx: X(li), cy: Y(v[li]), r: 4, class: "dot " + (up ? "up" : "dn") }));
    return sv;
  }
  function renderStock(el, d) {
    const b = body(el); b.replaceChildren();
    const up = (d.pct ?? 0) >= 0;
    const top = h("div", "stk-top");
    top.append(h("strong", "big px", num(d.price)), h("span", "chg " + (up ? "up" : "dn"), `${up ? "▲" : "▼"} ${num(Math.abs(d.change ?? 0))}  ${pct(d.pct)}`));
    const cw = h("div", "cwrap"); cw.append(chart(d.closes, d.prev, 520, 170, up));
    const tape = h("ol", "tape");
    for (const t of (d.tape || []).slice(0, 6)) tape.append(tapeRow(t));
    b.append(h("div", "stk-name", d.name || d.sym || ""), top, cw, tape);
    const g = h("div", "stats");
    for (const [k, v] of [["Range", d.range || "1d"], ["Day", d.day_low != null ? `${num(d.day_low)} – ${num(d.day_high)}` : "--"],
                          ["52 wk", d.low52 != null ? `${num(d.low52)} – ${num(d.high52)}` : "--"], ["Market", d.state || "--"]]) {
      const c = h("div"); c.append(h("span", null, k), h("b", null, v)); g.append(c);
    }
    b.append(g);
    if (d.take) b.append(h("p", "take", d.take));
    el.querySelector(".pls").textContent = d.sym || "";
    foot(el, "Yahoo Finance · can be up to 15 min behind · not advice");
  }

  // live ticks (livefeed.py): just the numbers that changed, a green or red flash, the chart grows, the tape scrolls
  function tapeRow(t) {
    const li = h("li", t.dir > 0 ? "up" : t.dir < 0 ? "dn" : "");
    li.append(h("time", null, new Date(t.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })),
              h("b", null, num(t.price)), h("span", null, t.dir > 0 ? "▲" : t.dir < 0 ? "▼" : "·"));
    return li;
  }
  function flash(el, dir) {
    if (!el) return;
    el.classList.remove("flash-up", "flash-dn"); void el.offsetWidth;
    if (dir) el.classList.add(dir > 0 ? "flash-up" : "flash-dn");
  }
  function tickStock(it, e) {
    const d = it.data, el = it.el;
    d.price = e.price;
    if (e.change != null) d.change = e.change; else if (d.prev) d.change = e.price - d.prev;
    if (e.pct != null) d.pct = e.pct; else if (d.prev) d.pct = (e.price - d.prev) / d.prev * 100;
    if (e.high != null) d.day_high = e.high; if (e.low != null) d.day_low = e.low;
    const now = Date.now();
    if (d.range === "1d" || !d.range) {
      d.closes = d.closes || [];
      if (!d.lastPush || now - d.lastPush > 60000) { d.closes.push(e.price); d.lastPush = now; if (d.closes.length > 400) d.closes.shift(); }
      else d.closes[d.closes.length - 1] = e.price;
    }
    d.tape = [{ t: e.t || now, price: e.price, dir: e.dir }, ...(d.tape || [])].slice(0, 6);
    const up = (d.pct ?? 0) >= 0;
    const px = el.querySelector(".px"); if (!px) return;
    px.textContent = num(d.price); flash(px, e.dir);
    const ch = el.querySelector(".chg"); ch.className = "chg " + (up ? "up" : "dn");
    ch.textContent = `${up ? "▲" : "▼"} ${num(Math.abs(d.change ?? 0))}  ${pct(d.pct)}`;
    el.querySelector(".cwrap").replaceChildren(chart(d.closes, d.prev, 520, 170, up));
    const tape = el.querySelector(".tape"); tape.prepend(tapeRow(d.tape[0])); while (tape.children.length > 6) tape.lastChild.remove();
    it.lastTick = now; liveAge(it);
  }
  function liveAge(it) {
    const s = it.el.querySelector(".plive span"); if (!s || !it.lastTick) return;
    const a = (Date.now() - it.lastTick) / 1000;
    s.textContent = a < 3 ? "live" : a < 60 ? `${Math.round(a)}s` : `${Math.round(a / 60)}m`;
    it.el.classList.toggle("stale", a > 90);
    const dot = it.el.querySelector(".plive i"); if (dot && a < 1) flash(dot, 1);
  }
  setInterval(() => P.list.forEach(liveAge), 1000);

  // ------------------------------------------------------------------ weather: now, radar, the next hours
  function renderWeather(el, d) {
    const b = body(el); b.replaceChildren();
    const top = h("div", "wx-top");
    top.append(h("strong", "big", d.now != null ? `${Math.round(d.now)}°` : "--"),
               h("div", "wx-l", `${d.label || ""}${d.feels != null ? ` · feels ${Math.round(d.feels)}°` : ""}`));
    b.append(top);
    if (d.radar && d.radar.tiles && d.radar.tiles.length) {
      const box = h("div", "radar"), mo = h("div", "mosaic"), n = d.radar.n || 3;
      mo.style.setProperty("--n", n);
      for (const t of d.radar.tiles) {
        const cell = h("div", "tile");
        if (okImg(t.base)) { const im = h("img", "base"); im.src = t.base; im.alt = ""; im.referrerPolicy = "no-referrer"; cell.append(im); }
        (t.frames || (t.rain ? [t.rain] : [])).forEach((u, i) => { if (okImg(u)) { const im = h("img", "fr"); im.dataset.f = i; im.src = u; im.alt = ""; im.referrerPolicy = "no-referrer"; cell.append(im); } });
        mo.append(cell);
      }
      const stamp = h("b", "rstamp"); box.append(stamp);
      box.dataset.n = (d.radar.times || []).length || 1;
      const me = h("i", "you"); me.style.left = (d.radar.px * 100).toFixed(2) + "%"; me.style.top = (d.radar.py * 100).toFixed(2) + "%";
      mo.append(me);
      box.append(mo);
      b.append(box);
    }
    if (d.hours && d.hours.length) {
      const strip = h("div", "hours");
      const tmax = Math.max(...d.hours.map((x) => x.temp)), tmin = Math.min(...d.hours.map((x) => x.temp));
      for (const x of d.hours.slice(0, 12)) {
        const c = h("div", "hr");
        const bar = h("i"); bar.style.height = (20 + (x.temp - tmin) / Math.max(1, tmax - tmin) * 60) + "%";
        const rain = h("u"); rain.style.height = Math.min(100, x.rain || 0) + "%";
        c.append(h("b", null, Math.round(x.temp) + "°"), bar, rain, h("span", null, x.t));
        strip.append(c);
      }
      b.append(strip);
    }
    el.querySelector(".pls").textContent = d.place || "";
    foot(el, d.radar ? "Radar RainViewer · map © OpenStreetMap, © CARTO · Open-Meteo" : "Open-Meteo");
  }

  // the radar plays its last ~80 minutes on a loop (RainViewer frames every 10 minutes), holding on now
  setInterval(() => {
    for (const it of P.list) {
      if (it.kind !== "weather" || !it.data.radar) continue;
      const box = it.el.querySelector(".radar"); if (!box) continue;
      const n = +box.dataset.n || 1, times = it.data.radar.times || [], nowAt = (it.data.radar.now_from || n) - 1;
      it.rf = ((it.rf ?? -1) + 1) % (n + 3);                    // three extra beats parked on the latest frame
      const f = Math.min(it.rf, nowAt >= 0 ? (it.rf >= n ? nowAt : it.rf) : n - 1);
      box.querySelectorAll("img.fr").forEach((im) => { im.style.opacity = +im.dataset.f === f ? .85 : 0; });
      const st = box.querySelector(".rstamp"); if (st) st.textContent = times[f] ? (f >= nowAt + 1 ? "forecast " : "") + times[f] : "";
    }
  }, RM ? 4000 : 550);

  // ------------------------------------------------------------------ your day as a timeline
  const mins = (t) => { const m = /^(\d{1,2}):(\d{2})/.exec(t || ""); return m ? +m[1] * 60 + +m[2] : null; };
  function renderCalendar(el, d) {
    const b = body(el); b.replaceChildren();
    const ev = (d.events || []).filter((e) => mins(e.start) != null);
    const from = Math.min(7 * 60, ...ev.map((e) => mins(e.start))), to = Math.max(23 * 60, ...ev.map((e) => mins(e.end) || mins(e.start) + 60));
    const tl = h("div", "tline");
    for (let m = Math.ceil(from / 120) * 120; m <= to; m += 120) {
      const tk = h("span", "tk", `${(m / 60) % 24}`); tk.style.left = ((m - from) / (to - from) * 100) + "%"; tl.append(tk);
    }
    ev.forEach((e, i) => {
      const a = mins(e.start), z = mins(e.end) || a + 45;
      const blk = h("i", "blk"); blk.style.left = ((a - from) / (to - from) * 100) + "%";
      blk.style.width = Math.max(1.2, (z - a) / (to - from) * 100) + "%"; blk.style.top = (i % 3) * 30 + "%";
      tl.append(blk);
    });
    const nowM = mins(d.now);
    if (nowM != null && nowM >= from && nowM <= to) { const n = h("b", "now"); n.style.left = ((nowM - from) / (to - from) * 100) + "%"; tl.append(n); }
    b.append(tl);
    const ul = h("ul", "evs");
    if (!ev.length) ul.append(h("li", "none", d.empty || "Nothing on today."));
    for (const e of ev.slice(0, 7)) {
      const li = h("li"); li.append(h("time", null, e.start + (e.end ? "–" + e.end : "")), h("span", null, e.title || ""));
      if (e.where) li.append(h("em", null, e.where));
      if (nowM != null && mins(e.start) <= nowM && nowM < (mins(e.end) || mins(e.start) + 45)) li.classList.add("on");
      ul.append(li);
    }
    b.append(ul);
    el.querySelector(".pls").textContent = d.day || "";
  }

  // ------------------------------------------------------------------ sources he read
  function renderSources(el, d) {
    const b = body(el); b.replaceChildren();
    if (d.query) b.append(h("div", "q", "“" + d.query + "”"));
    const ol = h("ol", "src");
    for (const it of (d.items || []).slice(0, 6)) {
      const li = h("li"); li.append(h("b", null, it.domain || ""), h("span", null, it.title || "")); ol.append(li);
    }
    b.append(ol);
    el.querySelector(".pls").textContent = (d.items || []).length + " read";
  }

  // ------------------------------------------------------------------ 2. your PC, opened up (live from the telemetry)
  function renderPC(el, d) {
    const b = body(el); b.replaceChildren();
    const W = 560, H = 360, sv = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "pcmap" });
    sv.append(s("rect", { x: 6, y: 6, width: W - 12, height: H - 12, rx: 8, class: "board" }));
    for (let i = 0; i < 9; i++) sv.append(s("path", { d: `M ${30 + i * 58} 6 v 16`, class: "trace" }));
    for (let i = 0; i < 6; i++) sv.append(s("path", { d: `M 130 ${120 + i * 6} H ${300 + i * 4} V ${200 + i * 5} H 520`, class: "trace" }));
    // fans
    for (const [x, y] of [[70, 60], [150, 60]]) {
      sv.append(s("circle", { cx: x, cy: y, r: 30, class: "part" }));
      for (let k = 0; k < 5; k++) { const a = k * 1.2566; sv.append(s("path", { d: `M ${x} ${y} q ${Math.cos(a) * 18} ${Math.sin(a) * 4} ${Math.cos(a + .6) * 26} ${Math.sin(a + .6) * 26}`, class: "blade" })); }
    }
    // cpu socket
    sv.append(s("rect", { x: 210, y: 40, width: 120, height: 120, rx: 6, class: "part cpu" }));
    sv.append(s("rect", { x: 230, y: 60, width: 80, height: 80, rx: 3, class: "die" }));
    sv.append(s("text", { x: 270, y: 105, class: "val", id: "pc-cpu" }, "--"));
    sv.append(s("text", { x: 270, y: 180, class: "cap" }, "CPU"));
    // ram slots
    for (let i = 0; i < 4; i++) {
      sv.append(s("rect", { x: 360 + i * 22, y: 30, width: 14, height: 150, rx: 2, class: "part ram" + (i < (d.ram_sticks || 2) ? " full" : "") }));
    }
    sv.append(s("rect", { x: 360, y: 180, width: 80, height: 0, class: "ramfill", id: "pc-ramfill" }));
    sv.append(s("text", { x: 404, y: 200, class: "cap" }, "RAM"));
    sv.append(s("text", { x: 404, y: 108, class: "val", id: "pc-ram", transform: "rotate(-90 404 108)" }, "--"));
    // gpu card
    sv.append(s("rect", { x: 40, y: 230, width: 360, height: 90, rx: 6, class: "part gpu" }));
    for (const x of [110, 220, 330]) sv.append(s("circle", { cx: x, cy: 275, r: 34, class: "fan2" }));
    sv.append(s("text", { x: 220, y: 283, class: "val", id: "pc-gpu" }, "--"));
    sv.append(s("text", { x: 220, y: 342, class: "cap" }, "GPU"));
    // drives
    (d.drives || []).slice(0, 4).forEach((dr, i) => {
      const y = 230 + i * 30, used = dr.total ? 1 - dr.free / dr.total : 0;
      sv.append(s("rect", { x: 430, y, width: 110, height: 22, rx: 3, class: "part" }));
      sv.append(s("rect", { x: 430, y, width: 110 * used, height: 22, rx: 3, class: "drivefill" + (used > .9 ? " hot" : "") }));
      sv.append(s("text", { x: 436, y: y + 16, class: "dl" }, `${dr.name} ${Math.round(dr.free)} GB free`));
    });
    b.append(sv);
    const specs = h("div", "specs");
    for (const [k, v] of [["Processor", d.cpu], ["Graphics", d.gpu], ["Memory", d.ram], ["Windows", d.os]]) {
      if (!v) continue; const r = h("div"); r.append(h("span", null, k), h("b", null, v)); specs.append(r);
    }
    b.append(specs);
    const sp = h("div", "pcspark"); sp.append(h("span", null, "CPU"), h("i", "sc"), h("span", null, "GPU"), h("i", "sg"));
    b.insertBefore(sp, specs);
    el.querySelector(".pls").textContent = d.name || "";
    paintPC(el);
  }
  function paintPC(el) {
    const t = P.tel, g = P.gpu, q = (id) => el.querySelector("#" + id);
    if (!q("pc-cpu")) return;
    if (t) {
      q("pc-cpu").textContent = Math.round(t.cpu) + "%";
      q("pc-ram").textContent = Math.round(t.ram) + "%";
      const f = q("pc-ramfill"); f.setAttribute("y", 180 - 150 * t.ram / 100); f.setAttribute("height", 150 * t.ram / 100);
      el.classList.toggle("cpu-hot", t.cpu > 90);
    }
    if (g) q("pc-gpu").textContent = `${Math.round(g.gpu)}%  ${Math.round(g.gpu_temp)}°C`;
    const sc = el.querySelector(".pcspark .sc"), sg = el.querySelector(".pcspark .sg");
    if (sc) sc.replaceChildren(spark(P.hist.map((x) => x.cpu), 100));
    if (sg) sg.replaceChildren(spark(P.hist.map((x) => x.gpu), 100));
  }
  function spark(vals, max) {
    const w = 200, hh = 34, sv = s("svg", { viewBox: `0 0 ${w} ${hh}`, preserveAspectRatio: "none", class: "spk" });
    const v = vals.filter((x) => x != null); if (v.length < 2) return sv;
    const m = max || Math.max(...v, 1);
    const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(hh - x / m * (hh - 3) - 1).toFixed(1)}`).join(" ");
    sv.append(s("polygon", { points: `0,${hh} ${pts} ${w},${hh}`, class: "a" }), s("polyline", { points: pts, class: "l" }));
    return sv;
  }

  // ------------------------------------------------------------------ 3. a file he made, previewed
  function renderFile(el, d) {
    const b = body(el); b.replaceChildren();
    const sp = d.spec || {}, k = d.kind || "";
    if (k === "xlsx") {
      const sh = (sp.sheets || [])[0] || { rows: [] };
      const tb = h("table", "grid");
      (sh.rows || []).slice(0, 12).forEach((r, i) => {
        const tr = h("tr");
        (r || []).slice(0, 6).forEach((v) => { const t = v == null ? "" : String(v); tr.append(h(i ? "td" : "th", /^=/.test(t) ? "fx" : null, t)); });
        tb.append(tr);
      });
      b.append(h("div", "sheet-name", sh.name || "Sheet1"), tb);
    } else if (k === "pptx") {
      const deck = h("div", "deck");
      const slides = [{ title: sp.title, bullets: sp.subtitle ? [sp.subtitle] : [] }, ...(sp.slides || [])].filter((x) => x.title);
      for (const sl of slides.slice(0, 4)) {
        const c = h("div", "slide"); c.append(h("b", null, sl.title));
        for (const x of (sl.bullets || []).slice(0, 4)) c.append(h("span", null, x));
        deck.append(c);
      }
      b.append(deck);
    } else if (k === "text") {
      b.append(h("pre", "code", (d.text || "").split("\n").slice(0, 22).join("\n")));
    } else {                                                           // docx, pdf: a page
      const page = h("div", "page");
      if (sp.title) page.append(h("h3", null, sp.title));
      for (const bl of (sp.blocks || []).slice(0, 14)) {
        if (bl.h || bl.h2) page.append(h("h4", null, bl.h || bl.h2));
        else if (bl.p || bl.quote) page.append(h("p", bl.quote ? "qt" : null, bl.p || bl.quote));
        else if (bl.bullets || bl.numbers) { const ul = h("ul"); (bl.bullets || bl.numbers).slice(0, 5).forEach((x) => ul.append(h("li", null, x))); page.append(ul); }
        else if (bl.table) { const tb = h("table"); bl.table.slice(0, 5).forEach((r, i) => { const tr = h("tr"); r.slice(0, 4).forEach((v) => tr.append(h(i ? "td" : "th", null, String(v)))); tb.append(tr); }); page.append(tb); }
      }
      b.append(page);
    }
    el.querySelector(".pls").textContent = (k || "file").toUpperCase();
    foot(el, d.path || "");
  }

  // ------------------------------------------------------------------ 7. the network, as a map round the router
  function renderNetwork(el, d) {
    const b = body(el); b.replaceChildren();
    const W = 560, H = 380, cx = W / 2, cy = H / 2, sv = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "netmap" });
    for (const r of [70, 130, 175]) sv.append(s("circle", { cx, cy, r, class: "orbit" }));
    const devs = (d.devices || []).filter((x) => !x.gateway).slice(0, 24);
    sv.append(s("rect", { x: cx - 26, y: cy - 18, width: 52, height: 36, rx: 6, class: "router" }));
    sv.append(s("text", { x: cx, y: cy + 40, class: "cap" }, "router"));
    devs.forEach((x, i) => {
      const ring = x.me ? 70 : i % 2 ? 130 : 175, a = i / devs.length * 6.283 - 1.5708;
      const px = cx + ring * Math.cos(a) * 1.35, py = cy + ring * Math.sin(a);
      sv.append(s("line", { x1: cx, y1: cy, x2: px, y2: py, class: "link" + (x.new ? " new" : "") }));
      sv.append(s("circle", { cx: px, cy: py, r: x.me ? 9 : 6, class: "dev" + (x.new ? " new" : "") + (x.me ? " me" : "") + (x.joined ? " joined" : "") }));
      sv.append(s("text", { x: px, y: py - 12, class: "dn" + (x.new ? " new" : "") }, (x.me ? "this PC" : x.name || x.vendor || x.ip).slice(0, 18)));
    });
    b.append(sv);
    const fresh = (d.devices || []).filter((x) => x.new);
    const ul = h("ul", "newdev");
    if (fresh.length) for (const x of fresh.slice(-4)) { const li = h("li"); li.append(h("b", null, x.joined ? "joined " + x.joined : "new"), h("span", null, `${x.name || x.vendor || "unknown"} · ${x.ip}${x.mac ? " · " + x.mac : ""}`)); ul.append(li); }
    else ul.append(h("li", "none", "Nothing new since the last sweep."));
    b.append(ul);
    el.querySelector(".pls").textContent = `${(d.devices || []).length} devices${d.watching ? " · watching" : ""}`;
    foot(el, d.subnet || "");
  }

  // ------------------------------------------------------------------ 5. pre-game briefing
  function renderBriefing(el, d) {
    const b = body(el); b.replaceChildren();
    const grid = h("div", "brief");
    const cell = (title, lines, cls) => { const c = h("div", "cell " + (cls || "")); c.append(h("b", null, title)); for (const l of lines) c.append(h("span", null, l)); grid.append(c); };
    if (d.record) cell("Your form", [`${d.record.w}W ${d.record.l}L this week`, d.record.streak || ""], "rec");
    cell("Friends on", (d.friends || []).length ? d.friends.slice(0, 5).map((f) => `${f.name}${f.game ? " · " + f.game : ""}`) : ["nobody right now"]);
    if (d.queue) cell("Queues", d.queue.slice(0, 4));
    if (d.patch) cell("Latest patch", [d.patch.title || "", ...(d.patch.lines || []).slice(0, 3)], "patch");
    b.append(grid);
    el.querySelector(".pls").textContent = d.game || "";
  }

  // ------------------------------------------------------------------ 6. trackers: scores, downloads, flights, timers
  function renderTracker(el, d) {
    const b = body(el), before = el._prev || {}; b.replaceChildren();
    if (d.kind === "score" && d.teams) {
      const sc = h("div", "score");
      d.teams.slice(0, 2).forEach((t, i) => {
        const r = h("div", "team" + (t.win ? " win" : "")); r.append(h("span", null, t.name), h("strong", null, t.score ?? "-")); sc.append(r);
        const was = before.teams && before.teams[i] && before.teams[i].score;
        if (was != null && was !== t.score) { r.classList.add("scored"); }
      });
      if (d.live) el.classList.add("is-live");
      b.append(sc);
    } else if (d.kind === "flight" && d.lat != null) {
      b.append(flightMap(d));
      const row = h("div", "fl-nums");
      for (const [k, v, old] of [["Altitude", d.alt ? `${Math.round(d.alt).toLocaleString()} ft` : "--", before.alt], ["Speed", d.gs ? `${Math.round(d.gs)} kt` : "--", before.gs], ["Heading", d.track != null ? `${Math.round(d.track)}°` : "--", before.track]]) {
        const c = h("div"); c.append(h("span", null, k), h("b", null, v)); row.append(c);
      }
      b.append(row);
    } else {
      b.append(h("strong", "big", d.main || ""));
      if (d.spark && d.spark.length > 1) { const w = h("div", "dlspark"); w.append(spark(d.spark)); b.append(w); }
    }
    el._prev = JSON.parse(JSON.stringify(d));
    if (d.progress != null) { const pb = h("div", "pbar"); const i = h("i"); i.style.width = Math.max(0, Math.min(100, d.progress)) + "%"; pb.append(i); b.append(pb); }
    for (const l of (d.lines || []).slice(0, 4)) b.append(h("p", "tl", l));
    el.querySelector(".pls").textContent = d.status || "";
    foot(el, d.source || "");
  }

  function flightMap(d) {
    const W = 520, H = 220, sv = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "flmap" });
    const pts = (d.trail && d.trail.length ? d.trail : [[d.lat, d.lon]]);
    const lats = pts.map((p) => p[0]).concat(d.lat), lons = pts.map((p) => p[1]).concat(d.lon);
    const span = Math.max(.6, Math.max(...lats) - Math.min(...lats), (Math.max(...lons) - Math.min(...lons)) * .55) * 1.3;
    const cy = (Math.max(...lats) + Math.min(...lats)) / 2, cx = (Math.max(...lons) + Math.min(...lons)) / 2;
    const X = (lon) => W / 2 + (lon - cx) / (span / .55) * W, Y = (lat) => H / 2 - (lat - cy) / span * H;
    for (let g = Math.floor(cy - span); g <= cy + span; g += .5) sv.append(s("line", { x1: 0, x2: W, y1: Y(g), y2: Y(g), class: "gl" }));
    for (let g = Math.floor(cx - span * 2); g <= cx + span * 2; g += .5) sv.append(s("line", { y1: 0, y2: H, x1: X(g), x2: X(g), class: "gl" }));
    if (pts.length > 1) sv.append(s("polyline", { points: pts.map((p) => `${X(p[1]).toFixed(1)},${Y(p[0]).toFixed(1)}`).join(" "), class: "trail" }));
    const g = s("g", { transform: `translate(${X(d.lon).toFixed(1)} ${Y(d.lat).toFixed(1)}) rotate(${d.track || 0})` });
    g.append(s("path", { d: "M0 -11 L3 -2 L11 2 L11 4 L3 2 L2 8 L5 10 L5 11 L0 10 L-5 11 L-5 10 L-2 8 L-3 2 L-11 4 L-11 2 L-3 -2 Z", class: "plane" }));
    sv.append(g);
    sv.append(s("text", { x: 8, y: 16, class: "ll" }, `${d.lat.toFixed(2)}, ${d.lon.toFixed(2)}`));
    return sv;
  }

  const RENDER = { stock: renderStock, weather: renderWeather, calendar: renderCalendar, sources: renderSources, pc: renderPC,
                   file: renderFile, network: renderNetwork, briefing: renderBriefing, tracker: renderTracker };

  // ------------------------------------------------------------------ placement
  function geom() {
    const G = (window.deskGeom && window.deskGeom()) || { cx: innerWidth / 2, cy: innerHeight * .45, R: innerHeight * .15, left: 0, right: innerWidth };
    const M = (window.deskMonitors && window.deskMonitors()) || {};
    return { G, p: M.p || { wx: 0, wy: 0, ww: innerWidth, wh: innerHeight }, o: M.o };
  }
  function where(p) {
    const w = P.layout[p.kind] || p.where || DEFAULT_WHERE[p.kind] || "left";
    return w === "second" && !geom().o ? "left" : w;
  }
  function layout() {
    const { G, p, o } = geom(), k = p.wh / 1080;
    root.style.setProperty("--k", k.toFixed(3));
    const widgetsRight = window.DeskWidgets && DeskWidgets.side && DeskWidgets.side() === "right";
    const cols = {
      left: [p.wx + 36 * k, G.cx - G.R * 1.3 - 30 * k],
      right: [G.cx + G.R * 1.3 + 30 * k, p.wx + p.ww - (widgetsRight ? 360 : 36) * k],
    };
    const slots = { left: [], right: [], second: [] };
    for (const it of P.list) if (it !== P.focus) slots[where(it)] ? slots[where(it)].push(it) : slots.left.push(it);
    // a column too narrow for panels: they move to the other side
    for (const side of ["left", "right"]) {
      const wid = cols[side][1] - cols[side][0];
      if (wid < 300 * k) { const other = side === "left" ? "right" : "left"; slots[other].push(...slots[side]); slots[side] = []; }
    }
    const place = (items, x0, x1, y0, ybottom) => {
      const w = Math.min(560 * k, x1 - x0), x = x0 + (x1 - x0 - w) / 2;
      let y = y0;
      for (const it of items) {
        it.el.style.left = x + "px"; it.el.style.width = w + "px"; it.el.style.top = y + "px";
        it.el.style.maxHeight = Math.max(160 * k, ybottom - y) + "px";
        y += it.el.offsetHeight + 18 * k;
      }
    };
    const top = p.wy + 150 * k;
    // a column that would run off the bottom hands its oldest panel to the other side (if that side has room)
    const avail = p.wh - 190 * k, hOf = (list) => list.reduce((a, it) => a + it.el.offsetHeight + 18 * k, 0);
    for (const [a, b] of [["left", "right"], ["right", "left"]]) {
      const bw = cols[b][1] - cols[b][0];
      while (slots[a].length > 1 && hOf(slots[a]) > avail && bw >= 300 * k && hOf(slots[b]) + slots[a][0].el.offsetHeight < avail) slots[b].push(slots[a].shift());
    }
    place(slots.left.slice(-P.max), cols.left[0], cols.left[1], top, p.wy + p.wh - 40 * k);
    place(slots.right.slice(-P.max), cols.right[0], cols.right[1], top, p.wy + p.wh - 40 * k);
    if (o) place(slots.second.slice(-P.max), o.wx + o.ww * .3, o.wx + o.ww * .7, o.wy + 80 * k, o.wy + o.wh - 40 * k);
    if (P.focus) {
      const f = P.focus.el, w = Math.min(1100 * k, p.ww * .62);
      f.style.width = w + "px"; f.style.left = (p.wx + (p.ww - w) / 2) + "px";
      f.style.maxHeight = (p.wh - 140 * k) + "px";
      f.style.top = (p.wy + Math.max(60 * k, (p.wh - f.offsetHeight) / 2)) + "px";
    }
    document.body.classList.toggle("has-pulls", P.list.length > 0);
    document.body.classList.toggle("focusing", !!P.focus);
  }

  // ------------------------------------------------------------------ lifecycle
  function drop(it, now) {
    if (!it || it.gone) return;
    it.gone = true; clearTimeout(it.timer);
    P.list = P.list.filter((x) => x !== it);
    if (P.focus === it) P.focus = null;
    it.el.classList.add("out");
    setTimeout(() => it.el.remove(), now || RM ? 0 : 260);
    layout();
  }
  function arm(it, ttl) {
    clearTimeout(it.timer);
    if (ttl > 0 && !it.pinned) it.timer = setTimeout(() => drop(it), ttl * 1000);
  }
  function pull(e) {
    const kind = e.kind, R = RENDER[kind]; if (!R) return;
    let it = P.list.find((x) => x.id === e.id);
    if (!it) {
      it = { id: e.id || kind + Date.now(), kind, where: e.where, pinned: !!e.pinned, el: frame(kind, e.title, "", !!e.live) };
      it.el.classList.add("in");
      root.append(it.el);
      P.list.push(it);
      const same = P.list.filter((x) => where(x) === where(it) && x !== P.focus);
      while (same.length > P.max) drop(same.shift(), true);
      if (!RM) setTimeout(() => it.el.classList.remove("in"), 620); else it.el.classList.remove("in");
    }
    if (e.title) it.el.querySelector(".plh b").textContent = e.title;
    it.data = e.data || {};
    if (e.live) it.lastTick = Date.now();
    try { R(it.el, it.data); } catch (err) { console.error(err); }
    if (e.focus) focus(it); else layout();
    arm(it, e.ttl == null ? 120 : e.ttl);
  }
  function focus(it) {
    if (P.focus && P.focus !== it) P.focus.el.classList.remove("focus");
    P.focus = it || null;
    if (it) it.el.classList.add("focus");
    layout();
  }

  addEventListener("resize", () => setTimeout(layout, 50));

  return {
    layout,
    on(e) {
      switch (e.type) {
        case "pull": pull(e); break;
        case "pull_update": { const it = P.list.find((x) => x.id === e.id); if (it) {
          const keep = it.kind === "stock" ? { tape: it.data.tape, closes: it.data.closes, lastPush: it.data.lastPush } : {};
          it.data = Object.assign(it.data || {}, e.data, it.kind === "stock" && keep.closes && e.data.range === "1d" ? {} : {}, it.kind === "stock" ? { tape: keep.tape } : {});
          if (it.kind === "weather") it.rf = -1;
          RENDER[it.kind](it.el, it.data); it.lastTick = Date.now(); liveAge(it); layout(); arm(it, e.ttl == null ? 120 : e.ttl); } break; }
        case "pull_clear": if (e.id) drop(P.list.find((x) => x.id === e.id)); else if (e.kind) P.list.filter((x) => x.kind === e.kind).forEach((x) => drop(x)); else [...P.list].forEach((x) => drop(x)); break;
        case "pull_focus": if (e.off) { if (P.focus) P.focus.el.classList.remove("focus"); P.focus = null; layout(); } else focus(P.list.find((x) => x.id === e.id || x.kind === e.kind) || P.list[P.list.length - 1]); break;
        case "pull_layout": P.layout = Object.assign({}, e.map || {}); layout(); break;
        case "telemetry": P.tel = e; P.hist.push({ cpu: e.cpu, gpu: P.gpu ? P.gpu.gpu : null }); if (P.hist.length > 90) P.hist.shift();
          P.list.filter((x) => x.kind === "pc").forEach((x) => paintPC(x.el)); break;
        case "tick": P.list.filter((x) => x.kind === "stock" && x.data && x.data.sym === e.sym).forEach((x) => { try { tickStock(x, e); } catch (err) { console.error(err); } }); break;
        case "w_gpu": P.gpu = e; P.list.filter((x) => x.kind === "pc").forEach((x) => paintPC(x.el)); break;
        case "desk_init": case "desk_layout": case "widgets": setTimeout(layout, 30); break;
      }
    },
  };
})();
