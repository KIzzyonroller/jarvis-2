// The holographic panels from her main window (web search radar, PowerShell terminal, launch sequence, now playing,
// weather and the rest), popping up on the desktop beside the big visualizer while she works. Built from the same
// code as the main window (index.html), so they look and behave the same. Display only: the desktop takes no clicks.
"use strict";
window.DeskHolo = (() => {
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const sfx = { play() {} };                          // the desktop stays quiet; her window makes the sounds
const toolName = (n) => n.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const STEP_LABEL = { web_search: "Searching the web", screen: "Looking at your screen", look_at_screen: "Looking at your screen", look_at_camera: "Looking at you",
  run_command: "Running PowerShell", open: "Opening", close_app: "Closing", self_control: "Window", window_control: "Windows", keyboard_input: "Typing",
  clipboard: "Clipboard", mouse: "Mouse", display: "Display", media_control: "Media", set_volume: "Volume", system_power: "Power",
  system_info: "Checking the system", files: "Files", memory: "Memory", reminders: "Reminders", spotify: "Spotify", youtube: "YouTube", blender: "Blender",
  blender_expert: "Blender expert", unreal_expert: "Unreal expert", blender_lookup: "Checking the Blender API", unreal_lookup: "Checking the Unreal API",
  unreal_python: "Working in Unreal", unreal_status: "Checking Unreal", unreal_log: "Reading Unreal's log", unreal_look: "Looking at Unreal" };
const stepLabel = (n) => STEP_LABEL[n] || toolName(n);
function shortDetail(name, a) {
  if (!a) return "";
  if (name === "web_search") return a.query ? `"${a.query}"` : "";
  if (name === "run_command") return a.command || "";
  if (name === "blender") return (a.action || "") + (a.name ? ": " + a.name : "");
  if (name === "blender_expert" || name === "unreal_expert") return a.task ? (a.task.length > 70 ? a.task.slice(0, 70) + "…" : a.task) : "";
  if (name === "unreal_python") return a.what || "";
  if (name === "mouse") return (a.action || "").replace(/_/g, " ") + (a.what ? ": " + a.what : "");
  const v = Object.entries(a).filter(([k, x]) => typeof x !== "object" && typeof x !== "boolean" && !["content", "code", "steps", "question"].includes(k)).map(([, x]) => x).join(", ");
  return v.length > 70 ? v.slice(0, 70) + "…" : v;
}
// ================================================================ holographic panels
// While he works, panels materialise beside him showing what he's doing (a terminal for commands, a radar for
// web searches, the frame he's looking at, what's playing...). They dissolve a few seconds after each step.
const holoBox = $("#holo");
const duoOn = false;
const HK = { web_search: "search", screen: "scan", look_at_screen: "scan", look_at_camera: "scan", run_command: "term",
  files: "list", open: "launch", close_app: "launch", self_control: "launch", youtube: "media", spotify: "media", media_control: "media",
  set_volume: "level", display: "level", system_info: "gauges", memory: "note", reminders: "note", clipboard: "note",
  blender: "cube", mouse: "target", keyboard_input: "target", window_control: "target" };
const HTITLE = { search: "Web search", scan: "Visual analysis", term: "PowerShell", list: "File system", launch: "Launch sequence",
  media: "Now playing", level: "Levels", gauges: "Diagnostics", note: "Memory", cube: "Blender", target: "Targeting",
  think: "Analysis", discord: "Discord", generic: "Working" };
const holo = { on: true, panels: [], byName: {}, results: {}, think: null, tele: null };
const ytId = (t) => (String(t || "").match(/youtu\.be\/([A-Za-z0-9_-]{11})/) || [])[1];
const eqBars = () => `<div class="eq">${Array.from({ length: 18 }, (_, i) => `<i style="animation-delay:${(-(i * 137) % 900) / 1000}s;animation-duration:${.55 + (i * 53 % 50) / 100}s"></i>`).join("")}</div>`;
function holoBody(kind, name, a) {
  a = a || {};
  const q = esc(a.query || a.target || a.name || a.action || "");
  switch (kind) {
    case "search": return `<div class="row"><svg class="radar" viewBox="0 0 100 100" style="color:var(--c)"><circle cx="50" cy="50" r="46"/><circle cx="50" cy="50" r="30"/>
      <circle cx="50" cy="50" r="14"/><line x1="4" y1="50" x2="96" y2="50"/><line x1="50" y1="4" x2="50" y2="96"/>
      <g class="sw"><path d="M50 50 L50 4 A46 46 0 0 1 89 26 Z"/></g><circle class="bl" cx="68" cy="30" r="2.2"/>
      <circle class="bl" cx="30" cy="66" r="2.2" style="animation-delay:.8s"/><circle class="bl" cx="74" cy="64" r="2.2" style="animation-delay:1.2s"/></svg>
      <div style="min-width:0"><div class="sub">Query</div><div class="big">${q || "…"}</div></div></div>`;
    case "scan": return `<div class="shot"><div class="ph">${name === "look_at_camera" ? "Opening camera…" : "Capturing screen…"}</div></div>`;
    case "term": return `<pre class="term"><b>PS&gt;</b> ${esc(a.command || "")}\n<span class="cur"></span></pre>`;
    case "list": return `<div class="sub">${esc([a.action, a.query || a.path || a.folder].filter(Boolean).join(": "))}</div><ul class="hl"></ul>`;
    case "launch": return `<div class="big">${esc(a.target || a.name || a.action || "")}</div><div class="seg">${"<i></i>".repeat(14)}</div>`;
    case "media": return `<div class="sub">${esc(name === "media_control" ? (a.action || "").replace(/_/g, " ") : (name === "youtube" ? "YouTube" : "Spotify"))}</div>
      <div class="big">${esc(a.query || "")}</div>${eqBars()}`;
    case "level": { const v = a.level ?? a.value ?? a.brightness; return `<div class="sub">${esc(name === "display" ? "Display" : "Volume")}</div>
      <div class="lvl">${v != null ? esc(v) : (a.mute ? "Muted" : "…")}</div><div class="lvlbar"><i style="width:${Number(v) || 0}%"></i></div>`; }
    case "gauges": { const t = holo.tele || {}; const g = (l, v) => `<span>${l}</span><i><b style="width:${Math.round(v || 0)}%"></b></i><span>${Math.round(v || 0)}%</span>`;
      return `<div class="gs">${g("Processor", t.cpu)}${g("Memory", t.ram)}${g("Drive", t.disk)}</div>`; }
    case "note": return `<div class="sub">${esc((a.action || name).replace(/_/g, " "))}</div><div class="big" style="font-size:14px">${esc(a.text || a.message || a.content || a.name || "")}</div>`;
    case "cube": return `<div class="cube3"><div>${"<span></span>".repeat(6)}</div></div><div class="sub" style="text-align:center">${esc((a.action || "") + (a.name ? ": " + a.name : ""))}</div>`;
    case "target": return `<div class="row"><svg class="tgt" viewBox="0 0 64 64"><circle cx="32" cy="32" r="22"/><g class="rot"><line x1="32" y1="2" x2="32" y2="14"/>
      <line x1="32" y1="50" x2="32" y2="62"/><line x1="2" y1="32" x2="14" y2="32"/><line x1="50" y1="32" x2="62" y2="32"/></g><circle cx="32" cy="32" r="2.5" style="fill:var(--c)"/></svg>
      <div style="min-width:0"><div class="big" style="font-size:14px">${esc((a.action || "").replace(/_/g, " "))}</div>
      <div class="sub">${esc(a.what || a.window || (a.x != null ? `x ${a.x}  y ${a.y}` : (a.keys || []).join("+") || a.text || ""))}</div></div></div>`;
    case "think": return `<div class="think"></div>`;
    case "discord": return `<div class="sub">${esc(a.from || "")}${a.channel ? " in #" + esc(a.channel) : ""}</div><div class="big" style="font-size:14px;-webkit-line-clamp:3">${esc(a.text || "")}</div>`;
    default: return `<div class="big" style="font-size:14px">${esc(stepLabel(name))}</div><div class="sub">${esc(shortDetail(name, a))}</div><div class="seg">${"<i></i>".repeat(14)}</div>`;
  }
}
function holoAdd(kind, name, args) {
  if (!holo.on) return null;
  const el = document.createElement("div");
  el.className = "hp k-" + kind;
  el.innerHTML = `<div class="hh"><i></i>${esc(HTITLE[kind] || HTITLE.generic)}<span>0.0s</span></div><div class="bd">${holoBody(kind, name, args)}</div>`;
  el.querySelectorAll(".seg i").forEach((x, i) => x.style.animationDelay = (i * .07) + "s");
  holoBox.appendChild(el);
  const P = { el, kind, name, t0: performance.now(), done: false, slot: -1 };
  holo.panels.push(P);
  if (kind !== "think") sfx.play("panel");
  while (holo.panels.length > 4) holoDrop(holo.panels.find((p) => p.done) || holo.panels[0], true);
  holoLayout();
  return P;
}
function holoDrop(P, now = false) {
  if (!P || P.gone) return;
  P.gone = true; holo.panels = holo.panels.filter((x) => x !== P);
  if (holo.think === P) holo.think = null;
  P.el.classList.add("out"); setTimeout(() => P.el.remove(), now ? 300 : 750);
  holoLayout();
}
function holoDone(P, ok = true, linger = 6000) {
  if (!P || P.done) return;
  P.done = true; P.el.classList.add("done"); if (!ok) P.el.classList.add("fail");
  if (P.kind !== "think" && P.name !== "briefing" && P.kind !== "discord") sfx.play(ok ? "done" : "fail");
  P.el.querySelector(".hh span").textContent = ok ? `${((performance.now() - P.t0) / 1000).toFixed(1)}s` : "Failed";
  setTimeout(() => holoDrop(P), linger);
}
function holoLayout() {
  // On the desktop: two rows of panels either side of the big visualizer in the middle of your main monitor.
  if (!holo.panels.length) return;
  const G = (window.deskGeom && window.deskGeom()) || { cx: innerWidth / 2, cy: innerHeight * .45, R: innerHeight * .2, left: 0, right: innerWidth };
  const w = 300, excl = G.R * 1.25 + 30;
  const SLOTS = [[1, 0], [-1, 0], [1, 1], [-1, 1]];
  const used = new Set(holo.panels.map((p) => p.slot).filter((s) => s >= 0));
  holo.panels.forEach((p) => { if (p.slot < 0) { p.slot = [0, 1, 2, 3].find((s) => !used.has(s)) ?? 0; used.add(p.slot); } });
  holo.panels.forEach((p) => {
    const [side, row] = SLOTS[p.slot];
    p.el.style.setProperty("--w", w + "px");
    p.el.style.left = Math.max(G.left + 16, Math.min(G.right - w - 16, side > 0 ? G.cx + excl : G.cx - excl - w)) + "px";
    p.el.style.top = (row ? G.cy + 10 : G.cy - 206) + "px";
    p.el.style.maxHeight = "196px";
  });
}
setInterval(() => holo.panels.forEach((p) => { if (!p.done) p.el.querySelector(".hh span").textContent = ((performance.now() - p.t0) / 1000).toFixed(1) + "s"; }), 200);
addEventListener("resize", holoLayout);
function holoStart(name, args) {
  if (holo.think) holoDone(holo.think, true, 1500);
  const kind = HK[name] || "generic";
  const P = holoAdd(kind, name, args); if (!P) return;
  (holo.byName[name] = holo.byName[name] || []).push(P);
}
function holoFinish(name, ok, result, args) {
  const P = (holo.byName[name] || []).shift(); if (!P) return;
  const full = holo.results[name] ?? result ?? ""; delete holo.results[name];
  const bd = P.el.querySelector(".bd");
  if (P.kind === "term") {
    const pre = bd.querySelector(".term"), lines = String(full).replace(/^Exit code \d+\.\s*/, "").split("\n").filter((l) => l.trim()).slice(0, 8);
    pre.querySelector(".cur")?.remove();
    lines.forEach((l, i) => setTimeout(() => { pre.append(l.slice(0, 120) + "\n"); }, 60 * i));
  } else if (P.kind === "list") {
    const ul = bd.querySelector(".hl");
    String(full).split(/\n|;\s+(?=\S)/).map((x) => x.trim()).filter(Boolean).slice(0, 6)
      .forEach((l, i) => { const li = document.createElement("li"); li.textContent = l; li.style.animationDelay = (i * .07) + "s"; ul.appendChild(li); });
  } else if (P.kind === "media") {
    const id = ytId(full), title = (String(full).match(/^Playing (.+?)(?: by | on |\.)/) || [])[1];
    if (title) bd.querySelector(".big").textContent = title;
    if (id && !bd.querySelector(".thumb")) {
      const img = new Image(); img.className = "thumb"; img.alt = ""; img.src = `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;
      img.onerror = () => img.remove(); bd.insertBefore(img, bd.firstChild);
    }
  } else if (P.kind === "launch") {
    const big = bd.querySelector(".big"); if (ok && big) big.textContent += name === "close_app" ? " closed" : " online";
  } else if (P.kind === "search" && args && args.query) {
    const big = bd.querySelector(".big"); if (big) big.textContent = args.query;
  } else if (P.kind === "gauges" && holo.tele) {
    bd.innerHTML = holoBody("gauges", name, args);
  }
  holoDone(P, ok, P.kind === "media" || P.kind === "scan" ? 9000 : 6000);
}
function holoImage(name, src) {
  const P = (holo.byName[name] || [])[0] || holo.panels.slice().reverse().find((p) => p.kind === "scan" || p.kind === "cube");
  if (!P) return;
  const box = P.el.querySelector(".shot") || P.el.querySelector(".bd");
  box.classList.add("shot");
  box.innerHTML = ""; const img = new Image(); img.src = src; img.alt = ""; box.appendChild(img);
}
function holoThinking(text) {
  if (!holo.on) return;
  if (!holo.think) { holo.think = holoAdd("think", "thinking", {}); if (!holo.think) return; }
  const t = holo.think.el.querySelector(".think");
  holo.think.text = ((holo.think.text || "") + text).slice(-420);
  t.textContent = holo.think.text;
}
function holoInstant(e) {
  const log = String(e.log || ""), id = ytId(log);
  if (id || /^Playing /.test(log)) { holoStart(id ? "youtube" : "spotify", { query: e.text }); holoFinish(id ? "youtube" : "spotify", true, log); return; }
  const v = log.match(/^Volume (\d+)/);
  if (v) { holoStart("set_volume", { level: Number(v[1]) }); holoFinish("set_volume", true, log); return; }
  if (/^Opened /.test(log)) { holoStart("open", { target: log.replace(/^Opened (settings: )?/, "").split(".")[0] }); holoFinish("open", true, log); }
}
// ================================================================ briefing panels
const WXI = (code) => {
  const sun = '<circle cx="24" cy="24" r="8"/><path d="M24 6v5M24 37v5M6 24h5M37 24h5M11 11l3.5 3.5M33.5 33.5L37 37M37 11l-3.5 3.5M14.5 33.5L11 37"/>';
  const cloud = '<path d="M14 34h20a8 8 0 0 0 0-16 11 11 0 0 0-21 3 6.5 6.5 0 0 0 1 13z"/>';
  if (code == null) return cloud;
  if (code <= 1) return sun;
  if (code === 2) return '<circle cx="17" cy="17" r="6"/><path d="M17 5v3M5 17h3M8.5 8.5l2 2M25.5 8.5l-2 2"/>' + '<path d="M18 36h18a7 7 0 0 0 0-14 9.5 9.5 0 0 0-18 2.5 5.8 5.8 0 0 0 0 11.5z"/>';
  if (code >= 95) return cloud + '<path d="M24 36l-4 6h6l-3 5"/>';
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return cloud + '<path d="M17 40v.1M24 43v.1M31 40v.1M20 46v.1M28 46v.1"/>';
  if (code >= 51) return cloud + '<path d="M17 39l-2 5M24 39l-2 5M31 39l-2 5"/>';
  if (code === 45 || code === 48) return '<path d="M8 18h32M6 25h36M10 32h28M14 39h20"/>';
  return cloud;
};
function briefingPanels(e) {
  if (!holo.on) return;
  const add = (title, html, linger = 15000) => {
    const P = holoAdd("generic", "briefing", {}); if (!P) return;
    P.el.querySelector(".hh").childNodes[1].textContent = title;
    P.el.querySelector(".bd").innerHTML = html;
    holoDone(P, true, linger); P.el.querySelector(".hh span").textContent = "";
  };
  const w = e.weather;
  if (w) add(w.place || "Weather", `<div class="wx"><svg viewBox="0 0 48 48">${WXI(w.code)}</svg><div class="t">${esc(w.now)}<span class="u">${esc(w.unit)}</span></div>
    <div class="l">${esc(w.label || "")}${w.feels !== w.now ? `, feels like ${esc(w.feels)}°` : ""}</div>
    <div class="r">${w.high != null ? `<span>High <b>${esc(w.high)}°</b></span><span>Low <b>${esc(w.low)}°</b></span>` : ""}${w.rain >= 20 ? `<span>Precip <b>${esc(w.rain)}%</b></span>` : ""}</div></div>`);
  const rem = e.reminders || [];
  add("Today", rem.length ? `<ul class="hl">${rem.slice(0, 5).map((r, i) => `<li style="animation-delay:${i * .08}s"><b>${esc(r.time)}</b>${esc(r.text)}</li>`).join("")}</ul>`
                          : `<div class="sub" style="white-space:normal">Nothing else on your reminders today.</div>`);
  const dc = e.discord || [];
  if (dc.length) add("Discord", `<ul class="hl">${dc.slice(-4).map((m, i) => `<li style="animation-delay:${i * .08}s"><b>${esc(m.from)}</b>${esc(m.text)}</li>`).join("")}</ul>`);
  const hl = e.headlines || [];
  if (hl.length) add("Headlines", `<ul class="hl plain">${hl.slice(0, 3).map((h, i) => `<li style="animation-delay:${i * .08}s;white-space:normal">${esc(h)}</li>`).join("")}</ul>`);
}



// Check-ins (evening wrap-up, rain heads-up, break reminders...): a few cards, same look as the briefing.
function cardPanels(e) {
  if (!holo.on) return;
  const wxHtml = (w) => `<div class="wx"><svg viewBox="0 0 48 48">${WXI(w.code)}</svg><div class="t">${esc(w.high ?? w.now)}<span class="u">${esc(w.unit)}</span></div>
    <div class="l">${esc(w.label || "")}</div>
    <div class="r">${w.low != null ? `<span>Low <b>${esc(w.low)}°</b></span>` : ""}${w.rain >= 20 ? `<span>Precip <b>${esc(w.rain)}%</b></span>` : ""}</div></div>`;
  for (const c of e.cards || []) {
    const P = holoAdd("generic", "briefing", {}); if (!P) continue;
    P.el.querySelector(".hh").childNodes[1].textContent = c.title || "";
    let html = "";
    if (c.weather) html = wxHtml(c.weather);
    else if (c.list) html = c.list.length ? `<ul class="hl">${c.list.slice(0, 6).map((r, i) => `<li style="animation-delay:${i * .08}s"><b>${esc(r.time || "")}</b>${esc(r.text)}</li>`).join("")}</ul>`
                                          : `<div class="sub" style="white-space:normal">${esc(c.empty || "Nothing.")}</div>`;
    else html = `${c.big ? `<div class="big">${esc(c.big)}</div>` : ""}${c.text ? `<div class="sub" style="white-space:normal">${esc(c.text)}</div>` : ""}`;
    P.el.querySelector(".bd").innerHTML = html;
    holoDone(P, true, e.linger || 14000); P.el.querySelector(".hh span").textContent = "";
  }
}
const turnText = {};
function on(e) {
  switch (e.type) {
    case "activity": {
      const d = e.data || {};
      if (e.kind === "thinking") { if (typeof d === "string" && d.length) holoThinking(d); break; }
      if (e.kind === "tool_pending") { if (d.name === "web_search") holoStart(d.name, {}); break; }
      if (e.kind === "tool_start") { holoStart(d.name, d.args); break; }
      if (e.kind === "tool_done") { holoFinish(d.name, d.ok !== false, d.result, d.args); break; }
      break;
    }
    case "reply_delta": case "turn_end": if (holo.think) holoDone(holo.think, true, 1500); break;
    case "telemetry": holo.tele = e; break;
    case "instant": holoInstant(e); break;
    case "briefing": briefingPanels(e); break;
    case "cards": cardPanels(e); break;
    case "discord": { const P = holoAdd("discord", "discord", e); if (P) holoDone(P, true, 9000); break; }
    case "holo_on": holo.on = !!e.on; break;
  }
}
return { on, layout: holoLayout };
})();
