// The living part of his world: small things that move in each scene, slowly, at a low frame rate.
//   station     stars that twinkle, a shooting star now and then
//   archive     dust drifting through the moon shafts, the desk lamp breathing
//   signal      the waterfall display scrolling, the band dial sweeping
//   chart       glints on the sea, a little ship working along the route
//   bench       dust in the lamp's beam
//   greenhouse  rain on the glass, drops running down, the bulbs flickering
// Plus, everywhere: the light follows your real sunrise and sunset, rain or snow when it's actually raining or
// snowing where you are, and a few small things on a few days of the year.
//
// Costs almost nothing: 10 frames a second on a canvas the size of the screen, nothing at all in performance mode,
// while a game or fullscreen app is up (the desktop is paused then), or with "reduce motion" on in Windows.
// Used by the living desktop (desktop.js) and the screensaver (saver.html). Both call DeskAmbient.attach().
"use strict";
(() => {
  const FPS = 10;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const R = (a, b) => a + Math.random() * (b - a);
  const A = { on: true, paused: false, scene: "bench", facts: {}, layers: [], timer: 0, t0: performance.now(), parts: null };

  // ------------------------------------------------------------------ the time of day, as a colour over the scene
  // Every scene is drawn at night. In the day it lifts a little, at golden hour it warms, in the small hours it sinks.
  function grade(now = new Date()) {
    const f = A.facts || {}, day = new Date(now); day.setHours(0, 0, 0, 0);
    const rise = f.rise ? new Date(f.rise) : new Date(+day + 6.5 * 3.6e6);
    const set = f.set ? new Date(f.set) : new Date(+day + 19 * 3.6e6);
    const h = (d) => d.getHours() + d.getMinutes() / 60;
    const t = h(now), r = h(rise), s = h(set);
    if (t >= r - .7 && t < r + .7) return { c: "#ff9fb0", a: .16, m: "soft-light", name: "dawn" };
    if (t >= r + .7 && t < s - 1) return { c: "#cfe6ff", a: .2, m: "soft-light", name: "day" };
    if (t >= s - 1 && t < s + .5) return { c: "#ff9a3c", a: .22, m: "soft-light", name: "golden" };
    if (t < r - .7 && t < 5) return { c: "#0b1630", a: .22, m: "multiply", name: "small hours" };
    return { c: "#000", a: 0, m: "normal", name: "night" };
  }

  // ------------------------------------------------------------------ what today is
  function season(now = new Date()) {
    const m = now.getMonth() + 1, d = now.getDate();
    if (m === 10 && d === 31) return "halloween";
    if ((m === 12 && d === 31) || (m === 1 && d === 1)) return "newyear";
    if (m === 12 && d >= 20 && d <= 26) return "snowdays";
    return "";
  }

  // ------------------------------------------------------------------ the particles for each scene
  function make(key) {
    const P = { key, list: [], extra: {} };
    const add = (o) => P.list.push(o);
    if (key === "station") {
      for (let i = 0; i < 90; i++) add({ k: "star", x: R(0, 3840), y: R(0, 1500), r: R(1.2, 3), p: R(0, 6.28), s: R(.4, 1.6) });
    } else if (key === "archive") {
      for (let i = 0; i < 70; i++) add({ k: "mote", x: R(1100, 2700), y: R(1180, 2140), r: R(1.2, 3), vx: R(-6, 6), vy: R(-4, 2), p: R(0, 6.28) });
    } else if (key === "bench") {
      for (let i = 0; i < 45; i++) add({ k: "mote", x: R(200, 1500), y: R(80, 900), r: R(1, 2.4), vx: R(-5, 5), vy: R(-3, 3), p: R(0, 6.28) });
    } else if (key === "chart") {
      for (let i = 0; i < 80; i++) {
        let x, y;
        do { x = R(160, 3680); y = R(180, 1980); } while (((x - 1800) / 1500) ** 2 + ((y - 1100) / 900) ** 2 < 1);
        add({ k: "glint", x, y, p: R(0, 6.28), s: R(.3, 1) });
      }
      P.extra.route = [[1150, 1540], [1350, 1420], [1560, 1290], [1800, 1100], [2120, 960], [2480, 880], [2860, 980]];
    } else if (key === "signal") {
      P.extra.rows = [];
    } else if (key === "greenhouse") {
      for (let i = 0; i < 14; i++) add({ k: "runner", x: R(780, 3060), y: R(380, 1300), v: R(10, 40), L: R(20, 60) });
    }
    return P;
  }

  // ------------------------------------------------------------------ drawing
  function rain(g, t, heavy) {
    g.strokeStyle = "rgba(210,232,255,.22)"; g.lineWidth = 2; g.beginPath();
    const n = heavy ? 260 : 140;
    for (let i = 0; i < n; i++) {
      const sp = 900 + (i * 37) % 500, x = ((i * 523.7) % 3900) - 30, y = ((i * 311.3 + t * sp) % 2300) - 80, L = 28 + (i % 5) * 9;
      g.moveTo(x, y); g.lineTo(x - L * .14, y + L);
    }
    g.stroke();
  }
  function snow(g, t) {
    g.fillStyle = "rgba(240,246,255,.7)";
    for (let i = 0; i < 160; i++) {
      const x = ((i * 523.7) % 3900) + Math.sin(t * .6 + i) * 30, y = ((i * 211.3 + t * (60 + (i % 7) * 12)) % 2260) - 50;
      g.beginPath(); g.arc(x, y, 2 + (i % 3), 0, 6.283); g.fill();
    }
  }
  function bats(g, t) {
    g.fillStyle = "rgba(10,10,14,.85)";
    for (let i = 0; i < 3; i++) {
      const T = (t * .04 + i * .33) % 1, x = -200 + T * 4300, y = 300 + i * 160 + Math.sin(T * 30 + i) * 40, w = 26 + 10 * Math.sin(t * 14 + i);
      g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x - 20, y - w, x - 44, y - 4); g.quadraticCurveTo(x - 22, y - 4, x, y + 6);
      g.quadraticCurveTo(x + 22, y - 4, x + 44, y - 4); g.quadraticCurveTo(x + 20, y - w, x, y); g.fill();
    }
  }
  function fireworks(g, t, P) {
    const fw = P.extra.fw || (P.extra.fw = []);
    if (Math.random() < .03) fw.push({ x: R(500, 3300), y: R(200, 700), t: t, c: ["#ffd36b", "#ff7aa8", "#7ad8ff", "#b8ff8a"][fw.length % 4] });
    for (let i = fw.length - 1; i >= 0; i--) {
      const f = fw[i], a = t - f.t;
      if (a > 2.2) { fw.splice(i, 1); continue; }
      g.fillStyle = f.c; g.globalAlpha = Math.max(0, 1 - a / 2.2) * .8;
      for (let k = 0; k < 28; k++) {
        const an = k / 28 * 6.283, d = a * 180;
        g.beginPath(); g.arc(f.x + Math.cos(an) * d, f.y + Math.sin(an) * d + a * a * 30, 3, 0, 6.283); g.fill();
      }
      g.globalAlpha = 1;
    }
  }

  function draw(g, t, dt, P) {
    const key = P.key;
    if (key === "station") {
      for (const s of P.list) {
        const a = .25 + .75 * Math.max(0, Math.sin(t * s.s + s.p)) ** 3;
        g.fillStyle = `rgba(235,244,255,${(a * .8).toFixed(2)})`; g.beginPath(); g.arc(s.x, s.y, s.r, 0, 6.283); g.fill();
      }
      const sh = P.extra.shoot;
      if (!sh && Math.random() < dt / 25) P.extra.shoot = { x: R(400, 3000), y: R(80, 600), t, a: R(.25, .5) };
      if (sh) {
        const a = (t - sh.t) / 1.1, L = 420;
        if (a > 1) P.extra.shoot = null;
        else {
          const x = sh.x + a * 1500 * Math.cos(sh.a), y = sh.y + a * 1500 * Math.sin(sh.a);
          const gr = g.createLinearGradient(x, y, x - L * Math.cos(sh.a), y - L * Math.sin(sh.a));
          gr.addColorStop(0, `rgba(255,255,255,${(1 - a).toFixed(2)})`); gr.addColorStop(1, "rgba(255,255,255,0)");
          g.strokeStyle = gr; g.lineWidth = 3; g.beginPath(); g.moveTo(x, y); g.lineTo(x - L * Math.cos(sh.a), y - L * Math.sin(sh.a)); g.stroke();
        }
      }
    } else if (key === "archive" || key === "bench") {
      const col = key === "archive" ? "219,232,255" : "255,214,150";
      for (const m of P.list) {
        m.x += (m.vx + Math.sin(t * .3 + m.p) * 4) * dt; m.y += (m.vy + Math.cos(t * .2 + m.p) * 3) * dt;
        if (key === "archive") {                       // stay inside the moonlight
          const w = 220 + (m.y - 1180) * .98;           // the shaft widens towards the floor
          if (m.y < 1180 || m.y > 2150 || Math.abs(m.x - 1920) > w) { m.y = R(1200, 2100); m.x = 1920 + R(-1, 1) * (220 + (m.y - 1180) * .9); }
        } else if (m.x < 150 || m.x > 1600 || m.y < 60 || m.y > 950) { m.x = R(250, 1400); m.y = R(100, 850); }
        const a = .2 + .25 * Math.sin(t + m.p);
        g.fillStyle = `rgba(${col},${a.toFixed(2)})`; g.beginPath(); g.arc(m.x, m.y, m.r, 0, 6.283); g.fill();
      }
      if (key === "archive") {                         // the banker's lamp, breathing
        const a = .07 + .03 * Math.sin(t * 1.3) + (Math.random() < .01 ? .05 : 0);
        const gr = g.createRadialGradient(1060, 1760, 0, 1060, 1760, 420);
        gr.addColorStop(0, `rgba(255,211,138,${a.toFixed(3)})`); gr.addColorStop(1, "rgba(255,211,138,0)");
        g.fillStyle = gr; g.fillRect(640, 1340, 840, 840);
      }
    } else if (key === "signal") {
      const rows = P.extra.rows, cols = ["#0a3b2c", "#118a62", "#34d39a", "#b8ffe3"];
      const line = (tt) => {                           // one line of signal across the band
        const row = [];
        for (let c = 0; c < 1000; c += 16) {
          let v = Math.abs(Math.sin(c / 70 + tt * .8)) * .55 + Math.random() * .4;
          v *= .4 + .6 * Math.exp(-(((c - 500 - 160 * Math.sin(tt * .2)) / 240) ** 2));
          row.push(Math.min(cols.length, Math.floor(v * (cols.length + 1))));
        }
        return row;
      };
      while (rows.length < 35) rows.push(line(t - rows.length * .15));   // full from the first frame
      P.extra.acc = (P.extra.acc || 0) + dt;
      if (P.extra.acc > .15) { P.extra.acc = 0; rows.unshift(line(t)); rows.pop(); }   // new lines arrive at the top
      g.fillStyle = "#03120e"; g.fillRect(240, 260, 1000, 420);
      rows.forEach((row, ri) => row.forEach((v, ci) => {
        if (v) { g.fillStyle = cols[v - 1]; g.globalAlpha = .85; g.fillRect(240 + ci * 16, 260 + ri * 12, 16, 12); }
      }));
      g.globalAlpha = 1;
      const sx = 2600 + ((t * 90) % 1000);              // the band dial's scan line
      const gr = g.createLinearGradient(sx - 120, 0, sx, 0);
      gr.addColorStop(0, "rgba(140,255,210,0)"); gr.addColorStop(1, "rgba(140,255,210,.22)");
      g.fillStyle = gr; g.fillRect(sx - 120, 262, 120, 416);
    } else if (key === "chart") {
      for (const s of P.list) {
        const a = Math.max(0, Math.sin(t * s.s + s.p)) ** 6 * .55;
        if (a > .02) { g.fillStyle = `rgba(200,250,240,${a.toFixed(2)})`; g.fillRect(s.x - 7, s.y, 14, 2.5); }
      }
      const rt = P.extra.route, seg = rt.length - 1, u = (t / 240) % 1 * seg, i = Math.floor(u), f = u - i;
      const [x0, y0] = rt[i], [x1, y1] = rt[i + 1], x = x0 + (x1 - x0) * f, y = y0 + (y1 - y0) * f, an = Math.atan2(y1 - y0, x1 - x0);
      g.save(); g.translate(x, y - 26); g.rotate(an * .15);
      g.fillStyle = "#ffcf9a"; g.strokeStyle = "#071a1e"; g.lineWidth = 3;
      g.beginPath(); g.moveTo(-34, 0); g.lineTo(34, 0); g.lineTo(22, 16); g.lineTo(-22, 16); g.closePath(); g.fill(); g.stroke();
      g.beginPath(); g.moveTo(0, -2); g.lineTo(0, -52); g.lineTo(26, -10); g.closePath(); g.fill(); g.stroke();
      g.restore();
      g.strokeStyle = "rgba(255,207,154,.35)"; g.lineWidth = 2; g.beginPath();
      g.moveTo(x - 50 * Math.cos(an), y - 50 * Math.sin(an) - 6); g.lineTo(x - 140 * Math.cos(an), y - 140 * Math.sin(an) - 6); g.stroke();
    } else if (key === "greenhouse") {
      rain(g, t, false);
      g.strokeStyle = "rgba(220,240,255,.3)"; g.lineWidth = 3;
      for (const d of P.list) {
        d.y += d.v * dt * (1 + Math.random());
        if (d.y > 1380) { d.y = R(380, 600); d.x = R(780, 3060); }
        g.beginPath(); g.moveTo(d.x, d.y - d.L); g.lineTo(d.x, d.y); g.stroke();
        g.fillStyle = "rgba(230,245,255,.4)"; g.beginPath(); g.arc(d.x, d.y, 4, 0, 6.283); g.fill();
      }
      for (const [bx, by, k] of [[1100, 520, 0], [1920, 380, 1], [2740, 520, 2], [1500, 640, 3], [2340, 640, 4]]) {
        const a = .06 + .05 * Math.sin(t * (1.1 + k * .3) + k) + (Math.random() < .004 ? .1 : 0);
        const gr = g.createRadialGradient(bx, by, 0, bx, by, 240);
        gr.addColorStop(0, `rgba(255,213,154,${a.toFixed(3)})`); gr.addColorStop(1, "rgba(255,213,154,0)");
        g.fillStyle = gr; g.fillRect(bx - 240, by - 240, 480, 480);
      }
    }
    // the weather where you are, and the day of the year (not in space: the station has no weather)
    const wx = (A.facts || {}).wx, day = season();
    if (key !== "station" && key !== "greenhouse" && wx === "rain") rain(g, t, false);
    if (key === "greenhouse" && wx === "rain") rain(g, t + 7, true);
    if (key !== "station" && (wx === "snow" || day === "snowdays")) snow(g, t);
    if (day === "halloween" && key !== "station") bats(g, t);
    if (day === "newyear") fireworks(g, t, P);
  }

  // ------------------------------------------------------------------ one canvas per scene picture
  function attach(holders, key, size) {
    detach();
    A.scene = key;
    A.parts = make(key);
    const sz = size || [3840, 2160];
    for (const el of holders) {
      const c = document.createElement("canvas"), tod = document.createElement("div");
      c.className = "ambient"; tod.className = "tod";
      c.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
      tod.style.cssText = "position:absolute;inset:0;pointer-events:none;transition:background-color 60s linear,opacity 60s linear";
      el.appendChild(tod); el.appendChild(c);
      A.layers.push({ el, c, tod, sz });
    }
    resize();
    tint();
    start();
  }
  function detach() {
    stop();
    for (const L of A.layers) { L.c.remove(); L.tod.remove(); }
    A.layers = [];
  }
  function resize() {
    const d = Math.min(1.5, devicePixelRatio || 1);       // a soft layer: it doesn't need the full pixel density
    for (const L of A.layers) {
      const w = L.el.clientWidth || innerWidth, h = L.el.clientHeight || innerHeight;
      L.c.width = Math.ceil(w * d); L.c.height = Math.ceil(h * d);
      const k = Math.max(w / L.sz[0], h / L.sz[1]) * d;
      const ox = (w * d - L.sz[0] * k) / 2, oy = (h * d - L.sz[1] * k) / 2;
      L.g = L.c.getContext("2d"); L.g.setTransform(k, 0, 0, k, ox, oy); L.k = k; L.ox = ox; L.oy = oy;
    }
  }
  function tint() {
    const gr = grade();
    for (const L of A.layers) {
      L.tod.style.backgroundColor = gr.c; L.tod.style.opacity = gr.a; L.tod.style.mixBlendMode = gr.m;
    }
  }
  let last = 0;
  function tick() {
    A.timer = 0;
    if (!A.on || A.paused || reduced || !A.layers.length) return;
    const now = performance.now(), t = (now - A.t0) / 1000, dt = Math.min(.3, (now - (last || now)) / 1000);
    last = now;
    A.layers.forEach((L, i) => {
      const g = L.g; if (!g) return;
      g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, L.c.width, L.c.height);
      g.setTransform(L.k, 0, 0, L.k, L.ox, L.oy);
      try { draw(g, t, i ? 0 : dt, A.parts); } catch (e) { console.error(e); }   // the world moves once, however many screens
    });
    A.timer = setTimeout(tick, 1000 / FPS);
  }
  function start() { if (!A.timer && A.on && !A.paused && !reduced) { last = 0; A.timer = setTimeout(tick, 50); } }
  function stop() {
    clearTimeout(A.timer); A.timer = 0;
    for (const L of A.layers) if (L.g) { L.g.setTransform(1, 0, 0, 1, 0, 0); L.g.clearRect(0, 0, L.c.width, L.c.height); }
  }
  setInterval(tint, 60000);
  addEventListener("resize", () => { if (A.layers.length) resize(); });

  window.DeskAmbient = {
    attach, detach, grade, season,
    set(o) {
      if ("on" in o) A.on = !!o.on;
      if ("paused" in o) A.paused = !!o.paused;
      if ("facts" in o) { A.facts = o.facts || {}; tint(); }
      if (A.on && !A.paused) start(); else stop();
    },
  };
})();
