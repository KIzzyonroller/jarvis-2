// The living desktop: Jarvis's world as your wallpaper. One still scene per monitor (ui/scenes/*.svg), his voice
// ring in the middle, and the pop-up panels and widgets on top. Nothing moves unless you two are talking: when he's
// idle there is no frame loop at all. Events arrive from livedesk.py through window.J, same as the main window.
"use strict";
(() => {
  const SC = window.SCENES || {};
  const S = {
    monitors: [{ x: 0, y: 0, w: 1, h: 1, wx: 0, wy: 0, ww: 1, wh: 1, primary: true }],
    scene: "bench", calm: true, state: "booting", confirm: false, level: 0, levelT: 0,
    paused: false, built: false, viz: "both", fps: 30, facts: {},
  };
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = () => SC[S.scene] || SC.bench || { bg: "#0b1b2e", ink: "#a9d4ff", accent: "#ffb347", text: "#e7f2ff",
    dim: "#9cb7d3", panel: "rgba(9,24,42,.88)", border: "rgba(169,212,255,.45)", viz: [.5, .45] };
  const hexRGB = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];

  // the panels and widgets take the scene's colours
  function applyScene() {
    const T = scene(), st = document.documentElement.style, [r, g, b] = hexRGB(T.ink), [ar, ag, ab] = hexRGB(T.accent),
      [vr, vg, vb] = hexRGB(T.bg);
    const css = { c: T.ink, crgb: `${r},${g},${b}`, vrgb: `${vr},${vg},${vb}`, ink: T.text, dim: T.dim, alarm: T.accent,
                  argb: `${ar},${ag},${ab}` };
    for (const [k, v] of Object.entries(css)) st.setProperty("--" + k, v);
    document.body.style.background = T.bg;
    document.body.classList.toggle("calm", S.calm);
    document.body.dataset.style = T.style || "sheet";
    st.setProperty("--panel", T.panel || "rgba(9,24,42,.9)"); st.setProperty("--border", T.border || "rgba(169,212,255,.5)");
  }

  const px = (m) => ({ x: m.x * innerWidth, y: m.y * innerHeight, w: m.w * innerWidth, h: m.h * innerHeight,
    wx: m.wx * innerWidth, wy: m.wy * innerHeight, ww: m.ww * innerWidth, wh: m.wh * innerHeight });
  const primary = () => px(S.monitors.find((m) => m.primary) || S.monitors[0]);
  const others = () => S.monitors.filter((m) => !m.primary).map(px);

  // ------------------------------------------------------------------ scene: one still picture per monitor
  let VIZ = [];
  function build() {
    applyScene();
    const box = document.getElementById("scenes");
    box.innerHTML = "";
    for (const m of S.monitors.map(px)) {
      const d = document.createElement("div");
      d.className = "scene";
      Object.assign(d.style, { left: m.x + "px", top: m.y + "px", width: m.w + "px", height: m.h + "px",
                               backgroundImage: `url(scenes/${encodeURIComponent(S.scene)}.svg)` });
      d.appendChild(labelLayer());
      box.appendChild(d);
    }
    // the voice ring sits where the scene leaves room for it (each scene says where), on each monitor you picked
    const T = scene(), p = primary(), o = others()[0];
    const at = (m, big) => {                    // where the scene put the ring, through the same cover-crop as the picture
      const sz = T.size || [1920, 1080], k = Math.max(m.w / sz[0], m.h / sz[1]);
      const ox = m.x + (m.w - sz[0] * k) / 2, oy = m.y + (m.h - sz[1] * k) / 2;
      return { x: ox + sz[0] * T.viz[0] * k, y: oy + sz[1] * T.viz[1] * k, r: Math.min(m.ww, m.wh) * (big ? (T.ring || .13) : .06), n: big ? 72 : 40 };
    };
    const v = [];
    if (S.viz === "both" || S.viz === "main") v.push(at(p, true));
    if (S.viz === "corner" || (S.viz === "second" && !o)) v.push({ x: p.wx + p.wh * .13, y: p.wy + p.wh * .87, r: p.wh * .075, n: 40 });
    if (S.viz === "both" || S.viz === "second") for (const m of others()) v.push(at(m, true));
    VIZ = v;
    sizeViz();
    const gm = v[0] || at(p, true);
    window.deskGeom = () => ({ cx: gm.x, cy: gm.y, R: gm.r * 1.5, left: p.wx, right: p.wx + p.ww });
    window.deskMonitors = () => ({ p, o });
    if (window.DeskWidgets) setTimeout(DeskWidgets.layout, 0);
    if (window.DeskHolo) setTimeout(DeskHolo.layout, 0);
    if (window.DeskPulls) setTimeout(DeskPulls.layout, 0);
    placeGlass();
    S.built = true;
    drawViz(0, 0, true);
    kick();
  }

  // The scene's live text (deskfacts.py): your real sunset, his real version, your most-used apps as place names.
  // Same coordinates and cropping as the picture underneath, so it sits exactly where the picture had it.
  const NS = "http://www.w3.org/2000/svg";
  function labelLayer() {
    const s = document.createElementNS(NS, "svg");
    const sz = scene().size || [1920, 1080];
    s.setAttribute("viewBox", `0 0 ${sz[0]} ${sz[1]}`); s.setAttribute("preserveAspectRatio", "xMidYMid slice");
    s.setAttribute("class", "labels");
    for (const L of scene().labels || []) {
      const t = document.createElementNS(NS, "text");
      for (const [k, v] of Object.entries(L.attrs || {})) t.setAttribute(k, v);
      t.dataset.k = L.k; s.appendChild(t);
    }
    fillLabels(s);
    return s;
  }
  function fillLabels(root) {
    const T = scene(), vals = Object.assign({}, T.defaults || {}, S.facts[S.scene] || {}, S.facts.all || {});
    for (const L of T.labels || []) {
      const txt = L.tpl.replace(/\{(\w+)\}/g, (_, k) => (vals[k] != null ? String(vals[k]) : "")).replace(/\s+$/, "");
      (root || document).querySelectorAll(`.labels text[data-k="${L.k}"]`).forEach((e) => { e.textContent = txt; });
    }
  }

  // one small canvas per ring, just big enough for it
  function sizeViz() {
    const box = document.getElementById("vizbox"), d = devicePixelRatio || 1;
    box.innerHTML = "";
    for (const vc of VIZ) {
      const half = Math.ceil(vc.r * 1.7), c = document.createElement("canvas");
      c.style.left = vc.x - half + "px"; c.style.top = vc.y - half + "px"; c.style.width = c.style.height = half * 2 + "px";
      c.width = c.height = Math.ceil(half * 2 * d);
      const g = c.getContext("2d"); g.setTransform(d, 0, 0, d, half - vc.x, half - vc.y);
      box.appendChild(c); vc.g = g; vc.half = half;
    }
  }

  // His ring: a thin circle with tick marks, like an instrument dial. Still when he's idle; while he listens the
  // ticks lean in, while he thinks a single arc sweeps, while he talks the ticks grow with his voice.
  function drawViz(t, lvl, idle) {
    const T = scene(), [r, g, b] = hexRGB(T.ink), [ar, ag, ab] = hexRGB(T.accent);
    const mode = S.confirm ? "ask" : idle ? "idle" : ({ listening: "listen", awaiting: "listen", dictating: "listen",
      thinking: "think", speaking: "talk" }[S.state] || "idle");
    for (const vc of VIZ) {
      const vg = vc.g; if (!vg) continue;
      const { x, y, r: R } = vc;
      vg.clearRect(x - vc.half, y - vc.half, vc.half * 2, vc.half * 2);
      const col = mode === "ask" ? `${ar},${ag},${ab}` : `${r},${g},${b}`;
      // the dial
      vg.lineWidth = 1.2; vg.strokeStyle = `rgba(${col},.55)`;
      vg.beginPath(); vg.arc(x, y, R, 0, 6.283); vg.stroke();
      vg.strokeStyle = `rgba(${col},.3)`; vg.beginPath(); vg.arc(x, y, R * .72, 0, 6.283); vg.stroke();
      // the core: a small filled disc that brightens with his voice
      const glow = vg.createRadialGradient(x, y, 0, x, y, R * .6);
      glow.addColorStop(0, `rgba(${col},${(.16 + lvl * .5).toFixed(2)})`); glow.addColorStop(1, `rgba(${col},0)`);
      vg.fillStyle = glow; vg.beginPath(); vg.arc(x, y, R * .6, 0, 6.283); vg.fill();
      vg.fillStyle = `rgba(${col},${(.65 + lvl * .35).toFixed(2)})`; vg.beginPath(); vg.arc(x, y, R * .06, 0, 6.283); vg.fill();
      // the ticks
      vg.lineCap = "round"; vg.lineWidth = Math.max(1.5, R * .018); vg.strokeStyle = `rgba(${col},.85)`;
      vg.beginPath();
      for (let i = 0; i < vc.n; i++) {
        const an = i / vc.n * 6.283 - 1.5708;
        let len = R * (i % 6 ? .05 : .1);
        if (mode === "talk") len += R * lvl * .5 * (.45 + .55 * Math.abs(Math.sin(an * 5 + t * 7)));
        if (mode === "listen") len += R * .05 * (.5 + .5 * Math.sin(t * 3 + i * .5));
        const c = Math.cos(an), s = Math.sin(an), r0 = R * 1.04;
        vg.moveTo(x + c * r0, y + s * r0); vg.lineTo(x + c * (r0 + len), y + s * (r0 + len));
      }
      vg.stroke();
      if (mode === "think" || mode === "ask") {              // one arc sweeping round the inner circle
        const a0 = mode === "think" ? t * 2.4 : -1.5708;
        vg.lineWidth = Math.max(2, R * .03); vg.strokeStyle = `rgba(${col},.9)`;
        vg.beginPath(); vg.arc(x, y, R * .72, a0, a0 + (mode === "ask" ? 6.283 * (.5 + .5 * Math.sin(t * 3)) : 1.1)); vg.stroke();
      }
    }
  }

  // ------------------------------------------------------------------ glass mode on the desktop
  let glassFrame = null;
  function placeGlass() {
    if (!glassFrame) return;
    const p = primary();
    Object.assign(glassFrame.style, { left: p.wx + "px", top: p.wy + "px", width: p.ww + "px", height: p.wh + "px" });
  }
  function glassOn(url) {
    if (!url) { if (glassFrame) { glassFrame.remove(); glassFrame = null; } document.body.classList.remove("glass-up"); return; }
    if (!/^http:\/\/127\.0\.0\.1:\d+\/glass\?/.test(url)) return;            // only ever our own glass page
    if (!glassFrame) {
      glassFrame = document.createElement("iframe");
      glassFrame.id = "glassfr"; glassFrame.title = "Glass mode";
      glassFrame.setAttribute("allow", "camera *; autoplay *");
      glassFrame.setAttribute("allowtransparency", "true");
      glassFrame.style.cssText = "position:fixed;border:0;z-index:50;background:transparent;color-scheme:normal";
      document.body.appendChild(glassFrame);
    }
    if (glassFrame.src !== url) glassFrame.src = url;
    document.body.classList.add("glass-up");
    placeGlass();
  }

  const handlers = {
    glass(e) { glassOn(e.url); },
    desk_init(e) {
      S.monitors = e.monitors && e.monitors.length ? e.monitors : S.monitors;
      if (e.viz) S.viz = e.viz; if (e.fps) S.fps = +e.fps;
      if (e.scene && SC[e.scene]) S.scene = e.scene;
      if (e.calm != null) S.calm = !!e.calm;
      build();
    },
    desk_layout(e) { if (JSON.stringify(e.monitors) !== JSON.stringify(S.monitors)) { S.monitors = e.monitors; build(); } },
    desk_scene(e) {
      if (e.scene && SC[e.scene]) S.scene = e.scene;
      if (e.calm != null) S.calm = !!e.calm;
      if (S.built) build();
    },
    desk_facts(e) { S.facts = e.facts || {}; fillLabels(); },
    fps(e) { S.fps = Math.max(5, Math.min(60, +e.fps || 30)); },
    desk_viz(e) { if (e.viz) { S.viz = e.viz; build(); } },
    desk_pause(e) { S.paused = !!e.on; if (!S.paused) kick(); },
    state(e) { S.state = e.state; kick(); },
    voice(e) { S.level = e.v || 0; S.levelT = performance.now(); kick(); },
    confirm() { S.confirm = true; kick(); },
    confirm_done() { S.confirm = false; kick(); },
  };
  window.J = {
    on(e) {
      const h = handlers[e && e.type]; if (h) try { h(e); } catch (err) { console.error(err); }
      const dupe = e && (e.type === "discord" || e.type === "phone_note") && window.DeskWidgets && DeskWidgets.has("discord");
      const he = e && e.type === "phone_note" ? { type: "discord", from: "📱 " + (e.from || "Phone"), channel: "", text: e.text } : e;
      if (window.DeskHolo && !S.paused && !dupe) try { DeskHolo.on(he); } catch (err) { console.error(err); }      // pop-up panels
      if (window.DeskWidgets) try { DeskWidgets.on(e); } catch (err) { console.error(err); }               // widgets
      if (window.DeskPulls) try { DeskPulls.on(e); } catch (err) { console.error(err); }                   // what he pulls up
    },
    batch(list) { list.forEach((e) => window.J.on(e)); },
  };

  // ------------------------------------------------------------------ frames: only while there's something to show
  let last = 0, running = false, lvl = 0;
  const busy = () => S.confirm || (S.state !== "idle" && S.state !== "booting") || lvl > .01 || performance.now() - S.levelT < 400;
  function kick() { if (!running && !S.paused && S.built) { running = true; last = performance.now(); requestAnimationFrame(frame); } }
  function frame(now) {
    if (S.paused || !busy()) { running = false; lvl = 0; drawViz(0, 0, true); return; }   // back to still, then sleep
    requestAnimationFrame(frame);
    if (now - last < 1000 / S.fps - 2) return;
    const dt = Math.min(.1, (now - last) / 1000); last = now;
    const fresh = now - S.levelT < 400 ? S.level : 0;
    lvl += (fresh - lvl) * Math.min(1, dt * 12);
    drawViz(still ? 0 : now / 1000, lvl, false);
  }

  // ------------------------------------------------------------------ start
  let rz = 0, lastWH = "";
  addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { const wh = innerWidth + "x" + innerHeight; if (S.built && wh !== lastWH) { lastWH = wh; build(); } }, 250); });
  const hello = () => { try { window.pywebview.api.ready(); } catch (e) { /* not inside Jarvis */ } };
  if (window.pywebview && window.pywebview.api) hello(); else addEventListener("pywebviewready", hello);
  // opened on its own in a browser (no Jarvis): show the scene so it can be looked at (?scene=archive&state=speaking)
  setTimeout(() => {
    if (S.built || window.pywebview) return;
    const q = new URLSearchParams(location.search);
    handlers.desk_init({ scene: q.get("scene") || "bench" });
    if (q.get("state")) { handlers.state({ state: q.get("state") }); if (q.get("state") === "speaking") setInterval(() => handlers.voice({ v: .3 + Math.random() * .6 }), 80); }
  }, 300);
})();
