// The living desktop. Jarvis, Juno and Ultron live on the wallpaper; whoever he is right now reacts to what he's
// doing (listening, thinking, talking, opening something, asking for approval). Events arrive from livedesk.py
// through window.J, the same way the main window gets them.
"use strict";
(() => {
  const svg = document.getElementById("desk"), cvs = document.getElementById("intro");
  const NAMES = ["juno"];                                   // she's the only one now
  const COLOR = { jarvis: "#8ff3ff", ultron: "#ff2a45", juno: "#c13dff" };
  // Each AI has their own desktop. Juno: a purple glowing world. Jarvis: cold blue, clean lab light.
  // Ultron: a red furnace sky over a burnt-orange grid. The panels on the desktop take the same colours.
  const THEMES = {
    juno: { sky: ["#2a1747", "#140d24", "#07050c"], base: "#07050c", horizon: "#b44dff", floor: "#b44dff",
            motes: ["#2ee59d", "#ff5ae0", "#c13dff"], ring: "rgba(193,61,255,.45)", core: "#ff5ae0", icon: "diamond",
            css: { c: "#c97bff", crgb: "201,123,255", vrgb: "7,4,13", ink: "#f1e6ff", dim: "#8a76a3", alarm: "#ff5ae0", argb: "255,90,224" } },
    jarvis: { sky: ["#0f2c3d", "#08161f", "#02060b"], base: "#02060b", horizon: "#46c8ff", floor: "#46c8ff",
            motes: ["#8ff3ff", "#dff6ff", "#46c8ff"], ring: "rgba(127,231,255,.45)", core: "#dff6ff", icon: "reactor",
            css: { c: "#7fe7ff", crgb: "127,231,255", vrgb: "2,6,11", ink: "#dff6ff", dim: "#5f7f8f", alarm: "#ff9d2e", argb: "255,157,46" } },
    ultron: { sky: ["#3d0a12", "#1c0408", "#060102"], base: "#060102", horizon: "#ff3046", floor: "#ff5a2a",
            motes: ["#ff3046", "#ff8a3d", "#ffd34d"], ring: "rgba(255,48,70,.5)", core: "#ff8a3d", icon: "eye",
            css: { c: "#ff3046", crgb: "255,48,70", vrgb: "8,2,3", ink: "#f4e9e4", dim: "#86636a", alarm: "#ffd34d", argb: "255,211,77" } },
  };
  const theme = () => THEMES[S.persona] || THEMES.juno;
  function applyTheme() {
    const T = theme(), st = document.documentElement.style;
    for (const [k, v] of Object.entries(T.css)) st.setProperty("--" + k, v);
    document.body.style.background = T.base;
  }
  function themedFloor(c) {
    let s = "";
    for (let i = -10; i <= 10; i++) s += path(PL([[i * 30, 0], [i * 140, 220]]), { stroke: c, "stroke-opacity": .35, "stroke-width": 1.4 });
    for (let k = 0; k < 7; k++) { const y = Math.pow(k / 6, 1.8) * 220; s += path(PL([[-1400, y], [1400, y]]), { stroke: c, "stroke-opacity": .18 + k * .06, "stroke-width": 1.2 }); }
    return s;
  }
  const S = {
    monitors: [{ x: 0, y: 0, w: 1, h: 1, wx: 0, wy: 0, ww: 1, wh: 1, primary: true }],
    persona: "juno", merged: false, speaker: null, state: "booting", confirm: false,
    oneShot: null, oneShotWho: null, oneShotUntil: 0, level: 0, levelT: 0, paused: false, shown: false, built: false,
    quality: "medium", viz: "both",
  };
  // Settings > Appearance & animations: frame rates (busy, idle) and how many drifting shards per monitor
  const QUALITY = { low: [15, 6, 3], medium: [24, 10, 8], high: [30, 15, 14] };
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------------ scene
  const px = (m) => ({ x: m.x * innerWidth, y: m.y * innerHeight, w: m.w * innerWidth, h: m.h * innerHeight,
    wx: m.wx * innerWidth, wy: m.wy * innerHeight, ww: m.ww * innerWidth, wh: m.wh * innerHeight });
  const primary = () => px(S.monitors.find((m) => m.primary) || S.monitors[0]);
  const others = () => S.monitors.filter((m) => !m.primary).map(px);
  let VIZ = [], motes = [];
  // one small canvas per visualizer, just big enough for it: redrawing a whole-screen canvas costs more than it saves
  function sizeViz() {
    const box = document.getElementById("vizbox"), d = devicePixelRatio || 1;
    box.innerHTML = "";
    for (const vc of VIZ) {
      const half = Math.ceil(vc.r * 1.6), c = document.createElement("canvas");      // room for the bars at full voice
      c.style.left = vc.x - half + "px"; c.style.top = vc.y - half + "px"; c.style.width = c.style.height = half * 2 + "px";
      c.width = c.height = Math.ceil(half * 2 * d);
      const g = c.getContext("2d"); g.setTransform(d, 0, 0, d, half - vc.x, half - vc.y);   // draw in page coordinates
      box.appendChild(c); vc.g = g; vc.half = half;
    }
  }
  const hexRGB = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  // The voice visualizers, drawn on a plain canvas: far cheaper than redrawing a hundred SVG lines every frame.
  function drawViz(t, lvl, col) {
    const [r, g, b] = hexRGB(col);
    for (const vc of VIZ) {
      const vg = vc.g; if (!vg) continue;
      vg.clearRect(vc.x - vc.half, vc.y - vc.half, vc.half * 2, vc.half * 2);
      const glow = vg.createRadialGradient(vc.x, vc.y, 0, vc.x, vc.y, vc.r * .5);
      glow.addColorStop(0, `rgba(${r},${g},${b},${(.35 + lvl * .5).toFixed(2)})`); glow.addColorStop(1, `rgba(${r},${g},${b},0)`);
      vg.fillStyle = glow; vg.beginPath(); vg.arc(vc.x, vc.y, vc.r * .5, 0, 6.283); vg.fill();
      const T = theme();
      vg.strokeStyle = T.ring; vg.lineWidth = 1.5; vg.beginPath(); vg.arc(vc.x, vc.y, vc.r * .62, 0, 6.283); vg.stroke();
      // the emblem in the middle: Juno's diamond, Jarvis's reactor, Ultron's eye
      vg.beginPath();
      if (T.icon === "reactor") {
        vg.arc(vc.x, vc.y, vc.r * .22, 0, 6.283);
        vg.fillStyle = T.base; vg.fill(); vg.strokeStyle = T.core; vg.lineWidth = 2; vg.stroke();
        vg.beginPath(); for (let k = 0; k < 3; k++) { const a = -Math.PI / 2 + k * 2.094; vg[k ? "lineTo" : "moveTo"](vc.x + Math.cos(a) * vc.r * .14, vc.y + Math.sin(a) * vc.r * .14); }
        vg.closePath(); vg.fillStyle = `rgba(${r},${g},${b},${(.5 + lvl * .5).toFixed(2)})`; vg.fill();
      } else if (T.icon === "eye") {
        vg.moveTo(vc.x - vc.r * .3, vc.y); vg.quadraticCurveTo(vc.x, vc.y - vc.r * .2, vc.x + vc.r * .3, vc.y);
        vg.quadraticCurveTo(vc.x, vc.y + vc.r * .2, vc.x - vc.r * .3, vc.y); vg.closePath();
        vg.fillStyle = T.base; vg.fill(); vg.strokeStyle = T.core; vg.lineWidth = 2; vg.stroke();
        vg.beginPath(); vg.ellipse(vc.x, vc.y, vc.r * .035, vc.r * (.1 + lvl * .04), 0, 0, 6.283); vg.fillStyle = T.core; vg.fill();
      } else {
        vg.moveTo(vc.x, vc.y - vc.r * .3); vg.lineTo(vc.x + vc.r * .12, vc.y); vg.lineTo(vc.x, vc.y + vc.r * .3); vg.lineTo(vc.x - vc.r * .12, vc.y); vg.closePath();
        vg.fillStyle = "#0d0a14"; vg.fill(); vg.strokeStyle = T.core; vg.lineWidth = 2; vg.stroke();
      }
      const w = Math.max(2, vc.r * .035), r0 = vc.r * .7;
      vg.lineCap = "round";
      for (const [lw, a] of [[w * 2.6, .18], [w, .95]]) {          // a soft wide pass, then the bright bar: a glow without blur
        vg.lineWidth = lw; vg.strokeStyle = `rgba(${r},${g},${b},${a})`; vg.beginPath();
        for (let i = 0; i < vc.n; i++) {
          const an = i / vc.n * 6.283 - t * .15;
          const len = vc.r * (.08 + .05 * Math.sin(t * 2 + an * 3) + lvl * .55 * (.5 + .5 * Math.sin(an * 7 + t * 9)));
          const c = Math.cos(an), s2 = Math.sin(an);
          vg.moveTo(vc.x + c * r0, vc.y + s2 * r0); vg.lineTo(vc.x + c * (r0 + len), vc.y + s2 * (r0 + len));
        }
        vg.stroke();
      }
    }
  }

  const glc = document.getElementById("juno-gl"), fxc = document.getElementById("juno-fx");
  let JG = null;
  // She lives on the music player now; these only run if her desktop scripts are loaded again.
  if (window.JunoGL) try { JG = JunoGL.create(glc, fxc, "juno.png"); } catch (e) { console.error("Juno's renderer:", e); }
  // Most of the time she's her standing picture, and now and then she walks somewhere else on the screen (both from
  // juno_rig.js), pointing when she opens something, pointing up while she thinks. The leaping picture
  // (juno_gl.js) is her entrance.
  const rigc = document.getElementById("juno-rig");
  let RIG = null;
  if (window.JunoRig) try {
    RIG = JunoRig.create(rigc, async (name) => { const x = window.pywebview && window.pywebview.api; return x && x.picture ? await x.picture(name) : ""; });
  } catch (e) { console.error("Juno's rig:", e); }
  const ME = { x: 0, ground: 0, scale: 1, wscale: 1, minX: 0, maxX: 1, facing: 1, walkTo: null, ph: 0, glitch: 0,
               nextWalk: performance.now() + 25000, anim: "idle", leaping: null };
  const LEAP_ONLY = new Set();                  // the old leaping picture now only draws the pixel blocks
  function placeJuno() {
    const r = S.junoRect; if (!r) return;
    for (const c of [glc, fxc]) { c.style.left = r.left + "px"; c.style.top = r.top + "px"; c.style.width = r.w + "px"; c.style.height = r.h + "px"; }
    if (JG) JG.size(r.w, r.h);
    const q = S.rigRect;
    if (q && RIG) { rigc.style.left = q.left + "px"; rigc.style.top = q.top + "px"; rigc.style.width = q.w + "px"; rigc.style.height = q.h + "px"; RIG.size(q.w, q.h); }
    if (!S.shown) for (const c of [glc, fxc, rigc]) { c.style.opacity = 0; c.style.transform = "scale(1.6) translateY(8%)"; }
  }
  window.junoWalk = () => { ME.nextWalk = 0; };            // for testing: send her for a walk now
  function followHer() {                       // the leaping picture and the pixel blocks go wherever she is
    const r = S.junoRect, q = S.rigRect; if (!r || !q) return;
    const left = q.left + ME.x - r.w / 2;
    if (Math.abs(left - r.left) > .5) { r.left = left; for (const c of [glc, fxc]) c.style.left = left + "px"; }
  }
  function stepHer(now, dt, lvl) {
    if (!RIG || !S.rigRect) return;
    if (S.music && rigc.style.opacity === "0") return;      // away on the music player: nothing to draw
    const t = now / 1000;
    const leap = S.oneShot && LEAP_ONLY.has(S.oneShot) && now < S.oneShotUntil;
    if (leap !== ME.leaping) {                 // swap pictures behind a glitch
      ME.leaping = leap; ME.glitch = .8;
      glc.style.visibility = leap ? "visible" : "hidden"; rigc.style.visibility = leap ? "hidden" : "visible";
      if (JG) JG.glitch(.8);
      if (leap && ME.walkTo != null) ME.walkTo = null;
    }
    ME.glitch = Math.max(0, ME.glitch - dt * 2.2);
    if (leap) return;
    const idle = ME.anim === "idle";
    if (ME.walkTo != null) {
      if (!idle) { ME.walkTo = null; ME.glitch = .5; }
      else {
        const half = .55, speed = 255 * ME.wscale / half;       // one step every ~half second, feet roughly planted
        ME.ph = (ME.ph + dt * Math.PI / half) % (Math.PI * 2);
        const dir = Math.sign(ME.walkTo - ME.x), nx = ME.x + dir * speed * dt;
        if ((ME.walkTo - nx) * dir <= 0) { ME.x = ME.walkTo; ME.walkTo = null; ME.glitch = .5; ME.nextWalk = now + 30000 + Math.random() * 50000; }
        else ME.x = nx;
        followHer();
      }
    } else if (idle && S.shown && now > ME.nextWalk && !still) {
      let to = ME.minX + Math.random() * (ME.maxX - ME.minX);
      if (Math.abs(to - ME.x) < (ME.maxX - ME.minX) * .2) to = ME.x < (ME.minX + ME.maxX) / 2 ? ME.maxX - Math.random() * 60 : ME.minX + Math.random() * 60;
      ME.walkTo = to; ME.facing = to > ME.x ? 1 : -1; ME.ph = 0; ME.glitch = .5;
    }
    // her entrance: she leaps in from the right in an arc and lands standing
    if (ME.anim === "leap" && S.rigRect) {
      const u = Math.min(1, (now - (S.oneShotUntil - 1800)) / 1100);
      if (u < 1) {
        if (ME.pic !== "dash") { ME.pic = "dash"; ME.glitch = .6; }
        const e = 1 - Math.pow(1 - u, 2), p = primary();
        RIG.draw("dash", JunoRig.heroPose(t, 0, "dash"), ME.x + (1 - e) * p.ww * .45, ME.ground - Math.sin(u * Math.PI) * p.wh * .2,
                 ME.scale * 555 / RIG.faceToFoot("dash"), -1, t, ME.glitch, 1);
        return;
      }
    }
    // which picture: walking, pointing (opening something), pointing up (thinking), or standing
    const pic = ME.walkTo != null ? "walk" : ME.anim === "summon" ? "point" : ME.anim === "think" ? "up" : "stand";
    if (pic !== ME.pic) { if (ME.pic) ME.glitch = Math.max(ME.glitch, .6); ME.pic = pic; }
    const k = ME.scale * 555 / RIG.faceToFoot(pic);          // same body height whichever picture it is
    const pose = pic === "walk" ? JunoRig.walkPose(ME.ph, t) : pic === "stand" ? JunoRig.standPose(ME.anim === "leap" ? "happy" : ME.anim, t, lvl) : JunoRig.heroPose(t, lvl, pic);
    RIG.draw(pic, pose, ME.x, ME.ground, k, pic === "walk" ? ME.facing : 1, t, ME.glitch, 1);
  }
  function build() {
    const W = innerWidth, H = innerHeight, TH = theme();
    applyTheme();
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    let s = defs() + `<defs>
      <radialGradient id="sky" cx=".5" cy=".38" r=".8"><stop offset="0" stop-color="${TH.sky[0]}"/><stop offset=".55" stop-color="${TH.sky[1]}"/><stop offset="1" stop-color="${TH.sky[2]}"/></radialGradient>
      <linearGradient id="horizon" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${TH.horizon}" stop-opacity="0"/><stop offset=".5" stop-color="${TH.horizon}" stop-opacity=".35"/><stop offset="1" stop-color="${TH.horizon}" stop-opacity="0"/></linearGradient>
    </defs>`;
    s += el("rect", { width: W, height: H, fill: TH.base });
    const mons = S.monitors.map(px);
    for (const m of mons) {                                           // each monitor: sky, horizon glow, grid floor
      const ground = m.wy + m.wh * .88;
      s += el("rect", { x: m.x, y: m.y, width: m.w, height: m.h, fill: "url(#sky)" });
      s += el("rect", { x: m.x, y: ground - 40, width: m.w, height: 80, fill: "url(#horizon)" });
      s += el("g", { transform: `translate(${m.x + m.w / 2},${ground}) scale(${m.w / 2400},${Math.max(.2, (m.y + m.h - ground) / 220)})` }, themedFloor(TH.floor));
    }
    // the cast stands on the main monitor
    const p = primary(), ground = p.wy + p.wh * .88, k = p.wh * .64 / 860;
    const place = (name, fx, scale) => el("g", { id: `place-${name}`, transform: `translate(${p.x + p.w * fx},${ground}) scale(${k * scale})`, style: `opacity:${S.shown ? 1 : 0}` },
      el("g", { id: name }, { jarvis, ultron, juno }[name]()));
    // the voice visualizer: small in the main monitor's bottom-left corner, big in the middle of the second one
    const o = others()[0], vr = p.wh * .075;
    const vizzes = [];
    // She isn't standing on the desktop any more, so the visualizers take centre stage: big in the middle of each monitor.
    const mid = (m) => ({ x: m.wx + m.ww / 2, y: m.wy + m.wh * .45, r: Math.min(m.ww, m.wh) * .2, a: 1, n: 72 });
    if (S.viz === "both" || S.viz === "main") vizzes.push(mid(p));
    if (S.viz === "corner" || (S.viz === "second" && !o)) vizzes.push({ x: p.wx + vr * 1.7, y: p.wy + p.wh - vr * 1.7, r: vr, a: 1, n: 40 });
    if (S.viz === "both" || S.viz === "second") for (const m of others()) vizzes.push(mid(m));
    VIZ = vizzes;
    // where the pop-up panels go: either side of the middle of the main monitor
    const gm = mid(p);
    window.deskGeom = () => ({ cx: gm.x, cy: gm.y, R: gm.r, left: p.wx, right: p.wx + p.ww });
    window.deskMonitors = () => ({ p, o });
    if (window.DeskWidgets) setTimeout(DeskWidgets.layout, 0);
    if (window.DeskHolo) setTimeout(DeskHolo.layout, 0);
    // drifting shards over every monitor
    let ms = '<g id="motes">';
    const nM = (QUALITY[S.quality] || QUALITY.medium)[2] * mons.length;
    for (let i = 0; i < nM; i++) ms += el("g", {}, path(P([[0, -9], [3.5, 0], [0, 9], [-3.5, 0]]), { fill: TH.motes[i % 3] }));
    ms += "</g>";
    s += ms;
    // Juno herself: her artwork on the graphics card (juno_gl.js), standing on the main monitor's floor
    const jh = p.wh * .86, jw = jh * (JG ? JG.aspect : .78);
    S.rigRect = { left: p.x, top: p.y, w: p.w, h: p.h };
    ME.ground = ground - p.y + p.wh * .015;
    ME.scale = p.wh * .7 / 753; ME.wscale = ME.scale * 555 / 533;      // same body height in every picture
    ME.minX = p.wx - p.x + p.ww * .15; ME.maxX = p.wx - p.x + p.ww * .85;
    if (!ME.x || ME.x < ME.minX || ME.x > ME.maxX) ME.x = p.wx - p.x + p.ww * .5;
    S.junoRect = { left: p.x + ME.x - jw / 2, top: ground + p.wh * .02 - jh * (JG ? JG.footFrac : .93), w: jw, h: jh };
    svg.innerHTML = s;
    sizeViz();
    placeJuno();
    placeGlass();
    motes = [...svg.querySelectorAll("#motes > g")].map((e, i) => {
      const m = mons[i % mons.length];
      return { e, m, fx: Math.random(), fy: Math.random(), sp: .006 + Math.random() * .012, ph: Math.random() * 6.28, r: Math.random() * 360 };
    });
    S.built = true;
    refresh();
  }

  // ------------------------------------------------------------------ who does what
  const active = () => S.speaker || S.persona;            // Juno included: she's a persona now
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
      if (JG) JG.play(anim === "leap" ? "summon" : anim);
      ME.anim = anim;
    }
  }
  function oneShot(anim, who, secs) { S.oneShot = anim; S.oneShotWho = who; S.oneShotUntil = performance.now() + secs * 1000; refresh(); setTimeout(refresh, secs * 1000 + 30); }
  const OPENERS = /^(open|spotify|youtube|netflix|apple_music|launch|browser|glass)/;
  const SAYS_OPEN = /\b(open|opening|summon|launch|start up|pull up|bring up|boot up|fire up|load up|put on|play)\b/i;
  let lastSummon = 0;
  function summon() { const now = performance.now(); if (now - lastSummon < 2500) return; lastSummon = now; oneShot("summon", active(), 3.4); }

  // ------------------------------------------------------------------ glass mode on the desktop
  // Its page (from our own localhost server) floats over her world on the main monitor's work area. No camera picture:
  // her world shows through. The desktop gets no clicks, so it's hands only there.
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
      S.persona = THEMES[e.persona] ? e.persona : "juno"; S.merged = !!e.merged;
      if (e.quality) S.quality = e.quality; if (e.viz) S.viz = e.viz; if (e.fps) S.fps = +e.fps;
      build();
      if (e.intro && !still) playIntro(e.shot); else reveal(0);
    },
    desk_layout(e) { if (JSON.stringify(e.monitors) !== JSON.stringify(S.monitors)) { S.monitors = e.monitors; build(); } },
    music(e) {                                  // her music player is up: she's sitting on it, so she leaves the desktop
      S.music = !!e.on; ME.glitch = .8; if (JG) JG.glitch(.8);
      for (const c of [rigc, fxc]) { c.style.transition = "opacity 450ms"; c.style.opacity = S.music ? 0 : (S.shown ? 1 : 0); }
      if (S.music) ME.walkTo = null;
    },
    fps(e) { S.fps = Math.max(5, Math.min(60, +e.fps || 30)); },
    desk_viz(e) { if (e.viz) { S.viz = e.viz; build(); } },
    desk_pause(e) { S.paused = !!e.on; if (!S.paused) kick(); },
    persona(e) {                                 // switching AI swaps the whole desktop to theirs
      const k = THEMES[e.key] ? e.key : "juno";
      if (k !== S.persona) { S.persona = k; if (S.built) { build(); sizeViz(); } }
      refresh();
    },
    merged(e) { S.merged = !!e.on; if (S.merged) oneShot("happy", "juno", 3); refresh(); },
    state(e) { S.state = e.state; if (S.state === "idle") S.speaker = null; refresh(); },
    voice(e) { S.level = e.v || 0; S.levelT = performance.now(); },
    turn_start() { refresh(); },
    turn_end() { S.speaker = null; refresh(); },
    activity(e) { const d = e.data || {}; if (e.kind === "tool_start" && OPENERS.test(String(d.name || ""))) summon(); },
    msg(e) { if (e.role === "user" && SAYS_OPEN.test(String(e.text || ""))) summon(); },
    confirm() { S.confirm = true; refresh(); },
    confirm_done() { S.confirm = false; refresh(); },
  };
  window.J = {
    on(e) {
      const h = handlers[e && e.type]; if (h) try { h(e); } catch (err) { console.error(err); }
      const dupe = e && (e.type === "discord" || e.type === "phone_note") && window.DeskWidgets && DeskWidgets.has("discord");   // the widget has it already
      const he = e && e.type === "phone_note" ? { type: "discord", from: "📱 " + (e.from || "Phone"), channel: "", text: e.text } : e;
      if (window.DeskHolo && !S.paused && !dupe) try { DeskHolo.on(he); } catch (err) { console.error(err); }      // pop-up panels
      if (window.DeskWidgets) try { DeskWidgets.on(e); } catch (err) { console.error(err); }               // widgets
    },
    batch(list) { list.forEach((e) => window.J.on(e)); },
  };

  // ------------------------------------------------------------------ the frame loop (30 fps is plenty for a wallpaper)
  let last = performance.now(), running = false, lvl = 0;
  function kick() { if (!running && !S.paused) { running = true; last = performance.now(); requestAnimationFrame(frame); } }
  function frame(now) {
    if (S.paused) { running = false; return; }
    requestAnimationFrame(frame);
    const busy = S.state !== "idle" && S.state !== "booting" || (S.oneShot && now < S.oneShotUntil) || S.confirm || ME.walkTo != null;
    const q = QUALITY[S.quality] || QUALITY.medium;
    if (now - last < 1000 / (S.fps || (busy ? q[0] : q[1])) - 2) return;      // her frame rate (Settings, or ask her)
    const dt = Math.min(.1, (now - last) / 1000); last = now;
    if (!S.built) return;
    const fresh = now - S.levelT < 400 ? S.level : 0;
    lvl += (fresh - lvl) * Math.min(1, dt * 12);
    const voices = { jarvis: 0, ultron: 0, juno: 0 }; voices[active()] = lvl;
    if (JG) JG.step(now, dt, lvl);
    stepHer(now, dt, lvl);
    const t = now / 1000, col = COLOR[active()];
    drawViz(t, lvl, col);
    for (const m of motes) {
      m.fy -= m.sp * dt * 3; if (m.fy < -.05) { m.fy = 1.05; m.fx = Math.random(); }
      const x = m.m.x + (m.fx + Math.sin(t * .5 + m.ph) * .02) * m.m.w, y = m.m.y + m.fy * m.m.h;
      m.e.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${(m.r + t * 20) % 360})`);
      m.e.setAttribute("opacity", (.25 + .35 * Math.sin(t + m.ph) ** 2).toFixed(2));
    }
  }
  function reveal(ms) {
    S.shown = true;
    for (const c of [glc, fxc, rigc]) { c.style.transition = `opacity ${ms}ms, transform ${ms}ms cubic-bezier(.2,1.4,.4,1)`; c.style.opacity = S.music && c !== glc ? 0 : 1; c.style.transform = "none"; }
    if (JG && ms) { JG.glitch(1); oneShot("leap", "juno", 1.8); }      // she leaps in, then lands standing
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
        ctx.beginPath(); ctx.moveTo(len * .8, (yy + tipY) / 2 - 3 * sc); ctx.lineTo(len, tipY); ctx.lineTo(len * .8, (yy + tipY) / 2 + 6 * sc); ctx.closePath(); ctx.fillStyle = "#20d27e"; ctx.fill();
        ctx.beginPath(); ctx.moveTo(0, yy); ctx.lineTo(len * .7, yy + (tipY - yy) * .4); ctx.strokeStyle = "#20d27e"; ctx.lineWidth = 2 * sc; ctx.stroke();
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
      // her pixel blocks start eating the screen before it breaks
      if (t > 1.0 && shatter <= .2) {
        const n = Math.min(160, Math.floor((t - 1.0) * 70)), cs = Math.max(18, p.h / 34);
        for (let i = 0; i < n; i++) {
          const rx = ((Math.sin(i * 12.9898) * 43758.5453) % 1 + 1) % 1, ry = ((Math.sin(i * 78.233) * 12345.678) % 1 + 1) % 1;
          const x = Math.floor(rx * W / cs) * cs, y = Math.floor(ry * H / cs) * cs, run = 1 + (i % 4);
          ctx.fillStyle = "#2a0e63"; ctx.fillRect(x + 5, y + 5, cs * run, cs);
          ctx.fillStyle = i % 3 === 0 ? "#20d27e" : "#4b1fa3"; ctx.fillRect(x, y, cs * run, cs);
        }
      }
      // her hands grip the edges, then rip outward
      const reach = Math.min(1, Math.max(0, (t - .35) / .6)), grip = Math.min(1, Math.max(0, (t - 1.0) / .4));
      const out = Math.min(1, shatter / .5);
      if (reach > 0 && out < 1) { ctx.save(); ctx.globalAlpha = 1 - out; hand(-1, reach * (1 - out * .9), grip); hand(1, reach * (1 - out * .9), grip); ctx.restore(); }
      // her face rises up the main monitor, eyes snap open, then the grin
      const rise = Math.min(1, Math.max(0, (t - .9) / .9)), ease = 1 - (1 - rise) ** 3;
      face = Math.max(0, 1 - Math.max(0, shatter - .2) / .7);
      if (false && rise > 0 && face > 0) {          // (the old drawn face; she now leaps in for real, see reveal)
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
      if (t > 2.75 && !S.shown) { reveal(700); oneShot("happy", "juno", 2.2); }
      if (t < 4.3) requestAnimationFrame(step); else { ctx.clearRect(0, 0, W, H); cvs.width = cvs.height = 0; }
    })(T0);
  }

  // ------------------------------------------------------------------ start
  let rz = 0, lastWH = "";
  addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { const wh = innerWidth + "x" + innerHeight; if (S.built && wh !== lastWH) { lastWH = wh; build(); } }, 250); });
  const hello = () => { try { window.pywebview.api.ready(); } catch (e) { /* not inside Jarvis */ } };
  if (window.pywebview && window.pywebview.api) hello(); else addEventListener("pywebviewready", hello);
  kick();
  // opened on its own in a browser (no Jarvis): show the scene with a made-up monitor so it can be looked at
  setTimeout(() => { if (!S.built && !window.pywebview) handlers.desk_init({ intro: true }); }, 400);
})();
