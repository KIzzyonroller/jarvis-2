// The living desktop. Jarvis, Juno and Ultron live on the wallpaper; whoever he is right now reacts to what he's
// doing (listening, thinking, talking, opening something, asking for approval). Events arrive from livedesk.py
// through window.J, the same way the main window gets them.
"use strict";
(() => {
  const svg = document.getElementById("desk"), cvs = document.getElementById("intro");
  const NAMES = ["jarvis", "ultron", "juno"];
  const COLOR = { jarvis: "#8ff3ff", ultron: "#ff2a45", juno: "#c13dff" };
  const S = {
    monitors: [{ x: 0, y: 0, w: 1, h: 1, wx: 0, wy: 0, ww: 1, wh: 1, primary: true }],
    persona: "jarvis", merged: false, speaker: null, state: "booting", confirm: false,
    oneShot: null, oneShotWho: null, oneShotUntil: 0, level: 0, levelT: 0, paused: false, shown: false, built: false,
  };
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------------ scene
  const px = (m) => ({ x: m.x * innerWidth, y: m.y * innerHeight, w: m.w * innerWidth, h: m.h * innerHeight,
    wx: m.wx * innerWidth, wy: m.wy * innerHeight, ww: m.ww * innerWidth, wh: m.wh * innerHeight });
  const primary = () => px(S.monitors.find((m) => m.primary) || S.monitors[0]);
  const others = () => S.monitors.filter((m) => !m.primary).map(px);
  let bars = [], motes = [];

  function build() {
    const W = innerWidth, H = innerHeight;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    let s = defs() + `<defs>
      <radialGradient id="sky" cx=".5" cy=".38" r=".8"><stop offset="0" stop-color="#2a1747"/><stop offset=".55" stop-color="#140d24"/><stop offset="1" stop-color="#07050c"/></radialGradient>
      <linearGradient id="horizon" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b44dff" stop-opacity="0"/><stop offset=".5" stop-color="#b44dff" stop-opacity=".35"/><stop offset="1" stop-color="#b44dff" stop-opacity="0"/></linearGradient>
    </defs>`;
    s += el("rect", { width: W, height: H, fill: "#07050c" });
    const mons = S.monitors.map(px);
    for (const m of mons) {                                           // each monitor: sky, horizon glow, grid floor
      const ground = m.wy + m.wh * .88;
      s += el("rect", { x: m.x, y: m.y, width: m.w, height: m.h, fill: "url(#sky)" });
      s += el("rect", { x: m.x, y: ground - 40, width: m.w, height: 80, fill: "url(#horizon)" });
      s += el("g", { transform: `translate(${m.x + m.w / 2},${ground}) scale(${m.w / 2400},${Math.max(.2, (m.y + m.h - ground) / 220)})` }, junoFloor());
    }
    // the cast stands on the main monitor
    const p = primary(), ground = p.wy + p.wh * .88, k = p.wh * .64 / 860;
    const place = (name, fx, scale) => el("g", { id: `place-${name}`, transform: `translate(${p.x + p.w * fx},${ground}) scale(${k * scale})`, style: `opacity:${S.shown ? 1 : 0}` },
      el("g", { id: name }, { jarvis, ultron, juno }[name]()));
    // the voice visualizer: on the second monitor if there is one, otherwise faint behind Juno
    const o = others()[0];
    const vc = o ? { x: o.x + o.w / 2, y: o.wy + o.wh * .45, r: Math.min(o.w, o.wh) * .2, a: 1 } : { x: p.x + p.w / 2, y: p.wy + p.wh * .36, r: p.wh * .2, a: .35 };
    let v = `<g id="viz" opacity="${vc.a}">`;
    v += el("circle", { cx: vc.x, cy: vc.y, r: vc.r * .62, fill: "none", stroke: "#c13dff", "stroke-width": 1.5, opacity: .5, filter: "url(#glow)" });
    v += el("circle", { id: "viz-core", cx: vc.x, cy: vc.y, r: vc.r * .18, fill: "#c13dff", opacity: .7, filter: "url(#bigglow)" });
    v += path(P([[vc.x, vc.y - vc.r * .3], [vc.x + vc.r * .12, vc.y], [vc.x, vc.y + vc.r * .3], [vc.x - vc.r * .12, vc.y]]), { id: "viz-gem", fill: "#0d0a14", stroke: "#ff5ae0", "stroke-width": 2, filter: "url(#glow)" });
    for (let i = 0; i < 72; i++) v += el("line", { class: "bar", "stroke-linecap": "round", "stroke-width": Math.max(2, vc.r * .03), stroke: "#c13dff", filter: "url(#glow)" });
    v += "</g>";
    s += v;
    // drifting shards over every monitor
    let ms = '<g id="motes">';
    const nM = 14 * mons.length;
    for (let i = 0; i < nM; i++) ms += el("g", {}, path(P([[0, -9], [3.5, 0], [0, 9], [-3.5, 0]]), { fill: ["#46f0ff", "#ff5ae0", "#c13dff"][i % 3], filter: "url(#glow)" }));
    ms += "</g>";
    s += ms;
    s += place("jarvis", .2, 1.05) + place("ultron", .8, 1.05) + place("juno", .5, 1);
    svg.innerHTML = s;
    bars = [...svg.querySelectorAll("#viz .bar")].map((e, i) => ({ e, a: i / 72 * Math.PI * 2 }));
    bars.forEach((b) => { b.cx = vc.x; b.cy = vc.y; b.r = vc.r; });
    motes = [...svg.querySelectorAll("#motes > g")].map((e, i) => {
      const m = mons[i % mons.length];
      return { e, m, fx: Math.random(), fy: Math.random(), sp: .006 + Math.random() * .012, ph: Math.random() * 6.28, r: Math.random() * 360 };
    });
    S.built = true;
    refresh();
  }

  // ------------------------------------------------------------------ who does what
  const active = () => (S.merged ? "juno" : (S.speaker || S.persona));
  function stateAnim() {
    if (S.confirm) return "battle";
    return { listening: "listen", awaiting: "listen", dictating: "listen", thinking: "think", speaking: "talk" }[S.state] || "idle";
  }
  function refresh() {
    if (!S.built) return;
    const a = active(), now = performance.now();
    for (const n of NAMES) {
      let anim = "idle";
      if (S.oneShot && now < S.oneShotUntil && n === S.oneShotWho) anim = S.oneShot;
      else if (n === a) anim = stateAnim();
      CastEngine.play(n, anim);
    }
  }
  function oneShot(anim, who, secs) { S.oneShot = anim; S.oneShotWho = who; S.oneShotUntil = performance.now() + secs * 1000; refresh(); setTimeout(refresh, secs * 1000 + 30); }
  const OPENERS = /^(open|spotify|youtube|netflix|apple_music|launch|browser)/;

  const handlers = {
    desk_init(e) {
      S.monitors = e.monitors && e.monitors.length ? e.monitors : S.monitors;
      S.persona = e.persona || S.persona; S.merged = !!e.merged;
      build();
      if (e.intro && !still) playIntro(e.shot); else reveal(0);
    },
    desk_layout(e) { S.monitors = e.monitors; build(); },
    desk_pause(e) { S.paused = !!e.on; if (!S.paused) kick(); },
    persona(e) { S.persona = e.key || S.persona; refresh(); },
    merged(e) { S.merged = !!e.on; if (S.merged) oneShot("happy", "juno", 3); refresh(); },
    state(e) { S.state = e.state; if (S.state === "idle") S.speaker = null; refresh(); },
    voice(e) { S.level = e.v || 0; S.levelT = performance.now(); },
    turn_start(e) { const k = String(e.who || "").toLowerCase(); S.speaker = NAMES.includes(k) ? k : null; refresh(); },
    turn_end() { S.speaker = null; refresh(); },
    activity(e) { const d = e.data || {}; if (e.kind === "tool_start" && OPENERS.test(String(d.name || ""))) oneShot("summon", active(), 3.4); },
    confirm() { S.confirm = true; refresh(); },
    confirm_done() { S.confirm = false; refresh(); },
  };
  window.J = {
    on(e) { const h = handlers[e && e.type]; if (h) try { h(e); } catch (err) { console.error(err); } },
    batch(list) { list.forEach((e) => window.J.on(e)); },
  };

  // ------------------------------------------------------------------ the frame loop (30 fps is plenty for a wallpaper)
  let last = performance.now(), running = false, lvl = 0;
  function kick() { if (!running && !S.paused) { running = true; last = performance.now(); requestAnimationFrame(frame); } }
  function frame(now) {
    if (S.paused) { running = false; return; }
    requestAnimationFrame(frame);
    if (now - last < 32) return;
    const dt = Math.min(.1, (now - last) / 1000); last = now;
    if (!S.built) return;
    const fresh = now - S.levelT < 400 ? S.level : 0;
    lvl += (fresh - lvl) * Math.min(1, dt * 12);
    const voices = { jarvis: 0, ultron: 0, juno: 0 }; voices[active()] = lvl;
    CastEngine.step(now, dt, voices);
    const t = now / 1000, col = COLOR[active()];
    for (const b of bars) {
      const len = b.r * (.08 + .05 * Math.sin(t * 2 + b.a * 3) + lvl * .55 * (.5 + .5 * Math.sin(b.a * 7 + t * 9)));
      const c = Math.cos(b.a - t * .15), s2 = Math.sin(b.a - t * .15), r0 = b.r * .7;
      b.e.setAttribute("x1", (b.cx + c * r0).toFixed(1)); b.e.setAttribute("y1", (b.cy + s2 * r0).toFixed(1));
      b.e.setAttribute("x2", (b.cx + c * (r0 + len)).toFixed(1)); b.e.setAttribute("y2", (b.cy + s2 * (r0 + len)).toFixed(1));
      b.e.setAttribute("stroke", col);
    }
    const core = document.getElementById("viz-core");
    if (core) { core.setAttribute("fill", col); core.setAttribute("opacity", (.45 + lvl * .55).toFixed(2)); }
    for (const m of motes) {
      m.fy -= m.sp * dt * 3; if (m.fy < -.05) { m.fy = 1.05; m.fx = Math.random(); }
      const x = m.m.x + (m.fx + Math.sin(t * .5 + m.ph) * .02) * m.m.w, y = m.m.y + m.fy * m.m.h;
      m.e.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${(m.r + t * 20) % 360})`);
      m.e.setAttribute("opacity", (.25 + .35 * Math.sin(t + m.ph) ** 2).toFixed(2));
    }
  }
  function reveal(ms) {
    S.shown = true;
    for (const n of NAMES) { const g = document.getElementById(`place-${n}`); if (g) { g.style.transition = `opacity ${ms}ms`; g.style.opacity = 1; } }
  }

  // ------------------------------------------------------------------ Juno takes the screen (startup)
  // Your desktop as it was a moment ago; her hands grip its edges, her face rises, her eyes snap open, she grins,
  // and the screen shatters away into her world.
  function playIntro(shotUrl) {
    const ctx = cvs.getContext("2d"), DPR = devicePixelRatio || 1;
    cvs.width = innerWidth * DPR; cvs.height = innerHeight * DPR; ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    const W = innerWidth, H = innerHeight, p = primary();
    const img = new Image(); let ok = false;
    img.onload = () => { ok = true; };
    if (shotUrl) img.src = shotUrl;
    const head = new Path2D("M 0 -604 L 30 -584 L 26 -540 L 0 -514 L -26 -540 L -30 -584 Z");
    const mane = new Path2D("M -6 -560 L -40 -620 L -150 -640 L -60 -660 L -190 -760 L -50 -700 L -60 -820 L 10 -712 L 60 -860 L 70 -720 L 170 -800 L 110 -690 L 260 -720 L 140 -650 L 300 -600 L 150 -610 L 250 -500 L 120 -560 L 160 -420 L 80 -530 L 40 -470 L 30 -548 Z");
    const grin = new Path2D("M -20 -548 Q 0 -526 22 -550 L 17 -546 L 13 -540 L 9 -544 L 5 -536 L 1 -541 L -3 -535 L -7 -540 L -11 -536 L -15 -543 Z");
    const eyeL = new Path2D("M -24 -582 L -4 -574 L -22 -563 L -14 -573 Z"), eyeR = new Path2D("M 24 -582 L 4 -574 L 22 -563 L 14 -573 Z");
    // the screen, cut into jagged triangles
    const cols = Math.max(10, Math.round(W / 150)), rows = Math.max(6, Math.round(H / 150));
    const pts = [];
    for (let j = 0; j <= rows; j++) for (let i = 0; i <= cols; i++) {
      const edge = i === 0 || j === 0 || i === cols || j === rows;
      pts.push([i / cols * W + (edge ? 0 : (Math.random() - .5) * W / cols * .7), j / rows * H + (edge ? 0 : (Math.random() - .5) * H / rows * .7)]);
    }
    const fc = { x: p.x + p.w / 2, y: p.y + p.h * .5 };
    const tris = [];
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
      const a = pts[j * (cols + 1) + i], b = pts[j * (cols + 1) + i + 1], c = pts[(j + 1) * (cols + 1) + i], d = pts[(j + 1) * (cols + 1) + i + 1];
      for (const tri of [[a, b, d], [a, d, c]]) {
        const cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3, cy = (tri[0][1] + tri[1][1] + tri[2][1]) / 3;
        const dx = cx - fc.x, dy = cy - fc.y, dist = Math.hypot(dx, dy) || 1;
        tris.push({ tri, cx, cy, ux: dx / dist, uy: dy / dist, sp: 600 + Math.random() * 900, rot: (Math.random() - .5) * 4, delay: dist / Math.hypot(W, H) * .45 });
      }
    }
    const hand = (side, reach, grip) => {                    // her hand over the screen's edge: four blade fingers and a thumb
      const x0 = side < 0 ? 0 : W, y0 = p.y + p.h * .5, L = p.h * .34 * reach, sc = p.h / 1080;
      ctx.save(); ctx.translate(x0, y0); ctx.scale(side < 0 ? 1 : -1, 1);
      ctx.shadowColor = "#a24dff"; ctx.shadowBlur = 24 * sc;
      const fingers = [[-150, 0], [-55, .04], [45, .08], [140, .12], [260, .35]];
      fingers.forEach(([dy, curl], i) => {
        const yy = dy * sc, len = (i === 4 ? L * .55 : L) * (1 - grip * .12), w = (i === 4 ? 30 : 24) * sc;
        const tipY = yy + (curl + grip * .25) * len * .5;
        ctx.beginPath(); ctx.moveTo(-40 * sc, yy - w); ctx.lineTo(len * .78, yy - w * .6 + (tipY - yy) * .5); ctx.lineTo(len, tipY); ctx.lineTo(len * .78, yy + w * .6 + (tipY - yy) * .5); ctx.lineTo(-40 * sc, yy + w); ctx.closePath();
        ctx.fillStyle = "#0d0a14"; ctx.fill(); ctx.lineWidth = 4 * sc; ctx.strokeStyle = "#a24dff"; ctx.stroke();
        ctx.beginPath(); ctx.moveTo(len * .8, (yy + tipY) / 2 - 3 * sc); ctx.lineTo(len, tipY); ctx.lineTo(len * .8, (yy + tipY) / 2 + 6 * sc); ctx.closePath(); ctx.fillStyle = "#46f0ff"; ctx.fill();
        ctx.beginPath(); ctx.moveTo(0, yy); ctx.lineTo(len * .7, yy + (tipY - yy) * .4); ctx.strokeStyle = "#46f0ff"; ctx.lineWidth = 2 * sc; ctx.stroke();
      });
      ctx.restore();
    };
    const T0 = performance.now();
    let face = 0;
    (function step(now) {
      const t = (now - T0) / 1000;
      ctx.clearRect(0, 0, W, H);
      const shatter = Math.max(0, t - 2.7);
      // the old screen (whole until it breaks)
      if (shatter <= 0) {
        const shake = t > 1.1 ? (Math.random() - .5) * 6 * Math.min(1, (t - 1.1) * 2) : 0;
        if (ok) ctx.drawImage(img, shake, shake * .6, W, H); else { ctx.fillStyle = "#07050c"; ctx.fillRect(0, 0, W, H); }
      } else {
        for (const s of tris) {
          const k = Math.max(0, shatter - s.delay); if (k > 1.4) continue;
          const ox = s.ux * s.sp * k * k, oy = s.uy * s.sp * k * k + 300 * k * k, a = 1 - k / 1.4;
          ctx.save(); ctx.globalAlpha = a;
          ctx.translate(s.cx + ox, s.cy + oy); ctx.rotate(s.rot * k); ctx.translate(-s.cx, -s.cy);
          ctx.beginPath(); ctx.moveTo(...s.tri[0]); ctx.lineTo(...s.tri[1]); ctx.lineTo(...s.tri[2]); ctx.closePath();
          ctx.clip();
          if (ok) ctx.drawImage(img, 0, 0, W, H); else { ctx.fillStyle = "#07050c"; ctx.fill(); }
          ctx.strokeStyle = `rgba(193,61,255,${a})`; ctx.lineWidth = 2; ctx.stroke();
          ctx.restore();
        }
      }
      // her hands grip the edges, then rip outward
      const reach = Math.min(1, Math.max(0, (t - .35) / .6)), grip = Math.min(1, Math.max(0, (t - 1.0) / .4));
      const out = Math.min(1, shatter / .5);
      if (reach > 0 && out < 1) { ctx.save(); ctx.globalAlpha = 1 - out; hand(-1, reach * (1 - out * .9), grip); hand(1, reach * (1 - out * .9), grip); ctx.restore(); }
      // her face rises up the main monitor, eyes snap open, then the grin
      const rise = Math.min(1, Math.max(0, (t - .9) / .9)), ease = 1 - (1 - rise) ** 3;
      face = Math.max(0, 1 - Math.max(0, shatter - .2) / .7);
      if (rise > 0 && face > 0) {
        const k = p.h * .5 / 90, cx = fc.x, cy = fc.y + (1 - ease) * p.h * .9 + 560 * k;
        ctx.save(); ctx.globalAlpha = face; ctx.translate(cx, cy); ctx.scale(k * (1 + (1 - face) * .3), k * (1 + (1 - face) * .3));
        ctx.shadowColor = "#3a1cff"; ctx.shadowBlur = 0;
        ctx.save(); ctx.translate(14, 12); ctx.fillStyle = "#3a1cff"; ctx.fill(mane); ctx.restore();
        const g = ctx.createLinearGradient(-100, -420, 200, -860); g.addColorStop(0, "#7b2bff"); g.addColorStop(.5, "#c13dff"); g.addColorStop(1, "#ff5ae0");
        ctx.fillStyle = g; ctx.fill(mane);
        ctx.shadowColor = "#a24dff"; ctx.shadowBlur = 30; ctx.lineWidth = 3; ctx.strokeStyle = "#a24dff";
        ctx.fillStyle = "#0d0a14"; ctx.fill(head); ctx.stroke(head); ctx.shadowBlur = 0;
        ctx.fillStyle = "#1d1430"; ctx.fillRect(-30, -584, 60, 24);
        const open = t < 1.85 ? .06 : t < 2.05 ? .06 + (t - 1.85) / .2 * 1.4 : 1.46 - Math.min(.46, (t - 2.05) * 1.2);
        ctx.save(); ctx.translate(0, -573); ctx.scale(1, open); ctx.translate(0, 573);
        ctx.shadowBlur = 18; ctx.shadowColor = "#46f0ff"; ctx.fillStyle = "#46f0ff"; ctx.fill(eyeL);
        ctx.shadowColor = "#ff2a45"; ctx.fillStyle = "#ff2a45"; ctx.fill(eyeR); ctx.restore();
        const gr = Math.min(1, Math.max(0, (t - 2.1) / .35));
        if (gr > 0) { ctx.save(); ctx.translate(0, -543); ctx.scale(gr, gr); ctx.translate(0, 543); ctx.shadowBlur = 0; ctx.fillStyle = "#fff"; ctx.fill(grin); ctx.restore(); }
        ctx.restore();
      }
      if (t > 3.1 && !S.shown) { reveal(900); oneShot("happy", "juno", 2.2); }
      if (t < 4.3) requestAnimationFrame(step); else { ctx.clearRect(0, 0, W, H); cvs.width = cvs.height = 0; }
    })(T0);
  }

  // ------------------------------------------------------------------ start
  addEventListener("resize", () => { if (S.built) build(); });
  const hello = () => { try { window.pywebview.api.ready(); } catch (e) { /* not inside Jarvis */ } };
  if (window.pywebview && window.pywebview.api) hello(); else addEventListener("pywebviewready", hello);
  kick();
  // opened on its own in a browser (no Jarvis): show the scene with a made-up monitor so it can be looked at
  setTimeout(() => { if (!S.built && !window.pywebview) handlers.desk_init({ intro: true, persona: "jarvis" }); }, 400);
})();
