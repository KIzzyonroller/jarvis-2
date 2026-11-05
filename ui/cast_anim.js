// Moves the parts of Jarvis, Juno and Ultron. Each animation gives a target pose; the real pose eases towards it,
// so switching animations is always smooth. v = voice level 0..1 while talking.
"use strict";
const $ = (id) => document.getElementById(id);
const sin = Math.sin, abs = Math.abs, clamp = (x, a, b) => Math.max(a, Math.min(b, x)), sm = (x) => x * x * (3 - 2 * x);
const voice = (t) => clamp(sin(t * 11) * .5 + sin(t * 6.3) * .35 + sin(t * 2.1) * .3, 0, 1);
const blink = (t, ph) => { const k = (t + ph) % 4.2; return k < .14 ? abs(k - .07) / .07 : 1; };
const cyc = (t, len = 3.4) => { const p = (t % len) / len; return { p, up: sm(clamp(p / .22, 0, 1)) * (1 - sm(clamp((p - .78) / .22, 0, 1))) }; };

const DEFAULTS = {
  jarvis: { bob: 0, lean: 0, head: 0, headY: 0, eyes: .85, eyeOpen: 1, halo: 6, haloS: 1, haloA: .9, swordX: 0, sword: 0, swordR: 0, swordGlow: .5, cloak: 0, sash: 0, breath: 0, ring: 0 },
  ultron: { bob: 0, lean: 0, head: 0, shake: 0, eyes: .85, hi: 0, lo: 0, cloak: 0, sash: 0, breath: 0, core: .8, smoke: .75, rift: 0 },
  juno: { bob: 0, sway: 0, head: 0, headY: 0, eyeOpen: 1, look: 0, grin: 1, armU: 0, armD: 0, legL: 0, legR: 0, maneS: 1, maneR: 0, glitch: 0, breath: 0, heart: 1, spin: .4, orbit: 1 },
};

const ANIMS = {
  idle: {
    jarvis: (t) => ({ bob: sin(t * 1.1) * 3, cloak: sin(t * .9) * .02, sash: sin(t * 1.4) * 4, breath: sin(t * 1.6) * 1.2, swordGlow: .5 + sin(t * 2) * .15 }),
    ultron: (t) => ({ bob: sin(t * 1.0 + 1) * 3, hi: sin(t * .8) * 1.5, lo: sin(t * .9 + 1) * 2, cloak: sin(t * .8) * .025, sash: sin(t * 1.3) * 5, breath: sin(t * 1.5) * 1.4, eyes: .8 + sin(t * 7) * .05 + sin(t * 13) * .04 }),
    juno: (t) => ({ bob: sin(t * 1.6) * 4, sway: sin(t * .8) * 1.5, armU: sin(t * 1.3) * 4, armD: sin(t * 1.1 + 1) * 4, maneR: sin(t * .9) * 2, breath: sin(t * 1.8) * 1.5, head: sin(t * .7) * 3 }),
  },
  talk: {
    jarvis: (t, v) => ({ bob: sin(t * 1.1) * 3, head: sin(t * 1.3) * 3, headY: -v * 2, eyes: .8 + v * .7, haloS: 1 + v * .06, haloA: .8 + v * .4, swordGlow: .5 + v * .6, sash: sin(t * 1.4) * 4, cloak: sin(t * .9) * .02 }),
    ultron: (t, v) => ({ bob: sin(t * 1.0) * 3, head: sin(t * 1.7) * 3 + v * 2, eyes: .8 + v * .9, core: .7 + v * .6, lo: sin(t * .9) * 3, hi: -v * 3, sash: sin(t * 1.3) * 5, cloak: sin(t * .8) * .025 }),
    juno: (t, v) => { const g = Math.floor(t / 2.6) % 2; return { bob: sin(t * 1.6) * 4, head: sin(t * 2) * 5 + v * 4, headY: -v * 3, grin: 1 + v * .35, heart: 1 + v * .4, armD: g ? -28 + sin(t * 3) * 8 : sin(t * 1.1) * 4, armU: g ? sin(t * 1.3) * 4 : 12 + sin(t * 3.2) * 10, maneS: 1 + v * .05, glitch: v > .7 ? 1 : 0 }; },
  },
  listen: {
    jarvis: (t) => ({ bob: sin(t * 1.1) * 2, head: 7, headY: 2, eyes: 1.2, haloS: 1.05, lean: .6, sash: sin(t * 1.4) * 3 }),
    ultron: (t) => ({ bob: sin(t) * 2, head: -9, eyes: 1.15, lean: -.8, lo: 3 }),
    juno: (t) => ({ bob: sin(t * 1.6) * 2, head: 13, eyeOpen: 1.2, armU: -52, armD: 6, maneR: 4, sway: 2 }),
  },
  think: {
    jarvis: (t) => ({ bob: sin(t * .9) * 2, head: -6, eyes: .45 + sin(t * 3) * .15, halo: 40, haloS: .95, swordGlow: .3 }),
    ultron: (t) => ({ bob: sin(t * .8) * 2, head: 7, eyes: .45 + sin(t * 2.5) * .1, hi: 4, lo: -4, core: .5 }),
    juno: (t) => ({ bob: sin(t * 1.2) * 2, head: -10, look: 3, armU: -128, armD: -14, maneR: -3, spin: .15, eyeOpen: .7 }),
  },
  happy: {
    jarvis: (t) => ({ bob: -abs(sin(t * 3.4)) * 8, halo: 120, haloS: 1.1 + sin(t * 6.8) * .05, haloA: 1.2, eyes: 1.3, eyeOpen: .45, swordGlow: 1, sash: sin(t * 3) * 8, cloak: sin(t * 3.4) * .03 }),
    ultron: (t) => ({ bob: sin(t * 22) * 2, head: -6 + sin(t * 20) * 3, shake: sin(t * 25) * 1.5, eyes: 1.4, hi: -10, lo: 8, core: 1.2, cloak: sin(t * 3) * .03 }),
    juno: (t) => { const b = t * 4.2; return { bob: -abs(sin(b)) * 16, sway: sin(b / 2) * 5, armU: sin(b) * 26, armD: -34 + sin(b + 1) * 30, legL: sin(b / 2) * 9, legR: -sin(b / 2) * 9, grin: 1.25, maneS: 1.05 + abs(sin(b)) * .06, head: sin(b / 2) * 8, spin: 1.6, heart: 1.2 }; },
  },
  summon: {
    jarvis: (t) => { const { p, up } = cyc(t); return { swordX: -150 * up, sword: -110 * up, swordR: 180 * up, swordGlow: .6 + up * .9, haloS: 1 + up * .15, haloA: .9 + up * .5, eyes: 1 + up * .6, head: -4 * up, ring: up > .9 ? clamp((p - .3) / .45, 0, 1) : 0 }; },
    ultron: (t) => { const { p, up } = cyc(t); return { hi: -24 * up, lo: 10 * up, head: -6 * up, lean: .8 * up, eyes: 1 + up * .7, core: .8 + up * .6, rift: clamp((p - .25) / .3, 0, 1) * (1 - sm(clamp((p - .8) / .2, 0, 1))) }; },
    juno: (t) => { const { up } = cyc(t); return { armU: -40 * up, head: -6 * up, look: -3 * up, maneS: 1 + up * .1, glitch: up > .5 ? 1 : 0, spin: .4 + up * 2.4, orbit: 1 + up * .45, grin: 1.15 }; },
  },
  battle: {
    jarvis: (t) => ({ bob: sin(t * 1.4) * 2 + 4, sword: -40, swordR: -150 + sin(t * 1.6) * 3, swordGlow: 1.2, haloS: 1.12, haloA: 1.2, eyes: 1.4, head: 3, lean: -1, cloak: .03 + sin(t * 1.2) * .01, sash: 10 + sin(t * 2) * 4 }),
    ultron: (t) => ({ bob: sin(t * 1.4) * 2 + 5, hi: -16 + sin(t * 1.5) * 2, lo: 20 + sin(t * 1.5) * 3, lean: 1.5, eyes: 1.5, head: -4, core: 1.2, cloak: -.03, smoke: 1 }),
    juno: (t) => ({ bob: 8 + sin(t * 2) * 2, armD: -58 + sin(t * 1.6) * 3, armU: -30, legL: -7, legR: 7, maneS: 1.1, glitch: sin(t * 3) > .6 ? 1 : 0, head: -4, spin: 1, sway: -2 }),
  },
};
const ANIM_ORDER = ["idle", "talk", "listen", "think", "happy", "summon", "battle"];
const LABELS = { idle: "Idle", talk: "Talk", listen: "Listen", think: "Think", happy: "Happy", summon: "Summon", battle: "Battle" };

// ---------------------------------------------------------------- applying a pose
const set = (id, tr) => { const e = $(id); if (e) e.setAttribute("transform", tr); };
const op = (id, o) => { const e = $(id); if (e) e.setAttribute("opacity", clamp(o, 0, 1).toFixed(3)); };

function applyJarvis(q, t) {
  set("jarvis", `translate(0,${q.bob}) rotate(${q.lean})`);
  const head = `translate(0,${q.headY}) rotate(${q.head} 0 -515)`;
  set("j-head", head); set("j-head2", head);
  set("j-halo", `${head} rotate(${haloAng} 0 -588) translate(0 -588) scale(${q.haloS}) translate(0 588)`); op("j-halo", q.haloA);
  set("j-eyes", `translate(0 -580) scale(1 ${q.eyeOpen * blink(t, 0)}) translate(0 580)`); op("j-eyes", q.eyes);
  set("j-cloak", `translate(0 -508) skewX(${q.cloak * 57}) translate(0 508)`);
  set("j-tabard", `translate(0 -360) skewX(${q.cloak * 30}) translate(0 360)`);
  set("j-sash", `rotate(${q.sash} 62 -362)`);
  set("j-chest", `translate(0 ${q.breath})`);
  set("j-sword", `translate(${q.swordX} ${q.sword}) rotate(${q.swordR} 0 -340)`);
  // (a CSS glow redrawn every frame cost more than everything else on him; the blade's own aura does the job)
  // once the sword floats up out of his hands it moves in front of him
  const sw = $("j-sword"), front = q.sword < -25;
  if (front !== sw._front) { sw._home = sw._home || sw.nextSibling; sw.parentNode.insertBefore(sw, front ? $("j-fx") : sw._home); sw._front = front; }
  const fx = $("j-fx");
  if (q.ring > .01 && q.ring < .99) fx.innerHTML = [0, .12].map((d) => { const r = clamp(q.ring - d, 0, 1); return `<circle cx="${q.swordX}" cy="-660" r="${30 + r * 320}" fill="none" stroke="#bff8ff" stroke-width="${6 * (1 - r) + 1}" opacity="${(1 - r) * .9}" filter="url(#glow)"/>`; }).join("");
  else fx.innerHTML = "";
}

function applyUltron(q, t) {
  set("ultron", `translate(${q.shake},${q.bob}) rotate(${q.lean})`);
  set("u-head", `rotate(${q.head} 0 -515)`);
  op("u-eyes", q.eyes * (.92 + .08 * sin(t * 31)));
  const hi = `rotate(${q.hi} 100 -495)`, lo = `rotate(${q.lo} -100 -495)`;
  set("u-hisword", hi); set("u-larm", hi);
  set("u-losword", lo); set("u-rarm", lo); set("u-claws", lo);
  set("u-cloak", `translate(0 -506) skewX(${q.cloak * 57}) translate(0 506)`);
  set("u-sash", `rotate(${q.sash} -60 -356)`);
  set("u-chest", `translate(0 ${q.breath})`);
  op("u-core", q.core);
  set("u-smoke", `translate(${sin(t * .6) * 8} ${sin(t * .4) * 5})`); op("u-smoke", q.smoke);
  const em = $("u-embers").children;
  for (let i = 0; i < em.length; i++) { const sp = 30 + (i % 5) * 12, rise = (t * sp + i * 97) % 640; em[i].setAttribute("transform", `translate(${sin(t * 1.3 + i) * 6} ${-rise + ((i * 97) % 640)})`); em[i].setAttribute("opacity", (clamp(1 - rise / 640, 0, 1) * .9).toFixed(2)); }
  // the tear he rips open in the air
  const r = q.rift, rift = $("u-rift");
  if (r > .01) {
    const w = 150 * sm(r), x0 = 0, top = -780, bot = -60;
    const edge = (side) => { let pts = []; for (let k = 0; k <= 16; k++) { const y = top + (bot - top) * k / 16, j = (k % 2 ? 14 : -10); pts.push([x0 + side * (w * Math.sin(Math.PI * k / 16)) + j * (k > 0 && k < 16 ? 1 : 0), y]); } return pts; };
    const L = edge(-1), R = edge(1), hole = [...L, ...R.reverse()];
    rift.innerHTML = `<path d="${P(hole)}" fill="#050206" stroke="#ff2a45" stroke-width="4" filter="url(#glow)" opacity="${clamp(r * 1.5, 0, 1)}"/>`
      + `<path d="${P(hole)}" fill="none" stroke="#ffd0d6" stroke-width="1.5" opacity="${r}"/>`
      + `<path d="M ${x0 - w * .3} ${-420} L ${x0 + w * .2} ${-380} L ${x0 - w * .1} ${-330}" stroke="#ff2a45" stroke-width="2" fill="none" filter="url(#glow)" opacity="${r * .8}"/>`;
  } else rift.innerHTML = "";
}

const ORBIT = [0, .8, 1.6, 2.4, 3.2, 4.0, 4.8, 5.6];
let shardPh = 0, haloAng = 0;
function applyJuno(q, t, dt) {
  set("juno", `translate(0,${q.bob}) rotate(${q.sway} 0 0)`);
  const head = `translate(0 ${q.headY}) rotate(${q.head} 0 -512)`;
  set("n-head", head);
  set("n-mane", `${head} rotate(${q.maneR} 10 -560) translate(10 -600) scale(${q.maneS}) translate(-10 600)`);
  set("n-maneshadow", q.glitch > .5 ? `translate(${(Math.random() * 16 - 8).toFixed(1)} ${(Math.random() * 8 - 4).toFixed(1)})` : "");
  set("n-eyes", `translate(${q.look} 0) translate(0 -573) scale(1 ${q.eyeOpen * blink(t, 1.7)}) translate(0 573)`);
  set("n-grin", `translate(0 -543) scale(1 ${q.grin}) translate(0 543)`);
  set("n-heart", `translate(0 -442) scale(${q.heart}) translate(0 442)`);
  set("n-armU", `rotate(${q.armU} -48 -490)`); set("n-armD", `rotate(${q.armD} 48 -490)`);
  set("n-legL", `rotate(${q.legL} -26 -300)`); set("n-legR", `rotate(${q.legR} 26 -300)`);
  set("n-core", `translate(0 ${q.breath})`);
  shardPh += dt * q.spin;
  const sh = $("n-shards").children;
  for (let i = 0; i < sh.length; i++) {
    const a = ORBIT[i] + shardPh, rx = 190 * q.orbit, ry = 110 * q.orbit;
    sh[i].setAttribute("transform", `translate(${(Math.cos(a) * rx).toFixed(1)} ${(-420 + Math.sin(a) * ry + sin(t * 1.3 + i) * 30).toFixed(1)}) rotate(${(a * 57 + i * 40) % 360})`);
    sh[i].setAttribute("opacity", (.55 + .45 * (Math.sin(a) * .5 + .5)).toFixed(2));
  }
}

// ---------------------------------------------------------------- engine: who is doing what, eased every frame
const CastEngine = (() => {
  const cur = JSON.parse(JSON.stringify(DEFAULTS));
  const who = { jarvis: { anim: "idle", t0: 0 }, ultron: { anim: "idle", t0: 0 }, juno: { anim: "idle", t0: 0 } };
  function play(name, anim) {
    if (!ANIMS[anim]) anim = "idle";
    if (who[name].anim !== anim) { who[name].anim = anim; who[name].t0 = performance.now() / 1000; }
  }
  let frameN = 0;
  function step(now, dt, voices, focus) {
    const t = now / 1000;
    frameN++;
    for (const name of ["jarvis", "ultron", "juno"]) {
      // someone just idling in the background only needs half the frames (saves a lot on a big desktop)
      if (focus && name !== focus && who[name].anim === "idle" && frameN % 2) continue;
      const a = who[name].anim, ta = t - who[name].t0, v = (voices && voices[name]) || 0;
      const tgt = Object.assign({}, DEFAULTS[name], ANIMS[a][name](a === "summon" ? ta : t, a === "talk" ? (voices ? v : voice(t)) : 0));
      const k = 1 - Math.exp(-dt * (a === "happy" || a === "talk" ? 14 : 7));
      for (const key in tgt) cur[name][key] += (tgt[key] - cur[name][key]) * (key === "ring" || key === "rift" ? 1 : k);
    }
    haloAng += cur.jarvis.halo * dt;
    const half = (n) => focus && n !== focus && who[n].anim === "idle" && frameN % 2;
    const here = (n) => !!document.getElementById(n);              // only the ones actually on the page
    if (here("jarvis") && !half("jarvis")) applyJarvis(cur.jarvis, t);
    if (here("ultron") && !half("ultron")) applyUltron(cur.ultron, t);
    if (here("juno") && !half("juno")) applyJuno(cur.juno, t, dt);
  }
  return { play, step, who, cur };
})();
