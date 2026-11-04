// ============================================================================ Juno's startup, and the desktop she becomes
// 0.0  a violet seam opens down the middle of a black screen
// 0.5  her hands reach in from both sides and grip the edges of the screen
// 1.0  her face rises into view, eyes closed
// 2.0  her eyes snap open
// 2.4  she smiles
// 3.2  light pours out of her and floods the screen
// 4.0  the light clears: the desktop is her world now (no icons), with them standing on the taskbar
"use strict";
const INTRO = { pose: null, stars: null, isles: null };

function introPose() {
  if (!INTRO.pose) INTRO.pose = newPose();
  return INTRO.pose;
}

function bigHand(side, reach, grip, t) {
  // a huge gloved hand coming in from the screen edge; fingers curl round onto the screen
  const S = Math.min(W, H) / 120, x = side < 0 ? lerp(-26 * S, 4 * S, reach) : lerp(W + 26 * S, W - 4 * S, reach);
  const y = H * .42 + Math.sin(t * 2 + side) * S * .6;
  ctx.save(); ctx.translate(x, y);
  // a sleek armoured forearm coming in from off screen, a ring of light at the wrist
  const ang = side < 0 ? 0 : Math.PI, ax = -side * 46 * S, wx = -side * 3 * S;
  fs(capsule(ax, 2 * S, wx, 0, 9 * S, 6.5 * S), chrome(ax, -9 * S, wx, 9 * S, JU.body.plate), JU.line, 2.2);
  neon(line([[ax * .8, 0], [-side * 9 * S, 0]]), "190,140,255", 1.6, 1);
  neon((() => { const p = new Path2D(); p.ellipse(-side * 7 * S, 0, 2.2 * S, 7.5 * S, 0, 0, TAU); return p; })(), "255,140,230", 1.6, 1);
  drawHand(JU, wx, 0, ang - side * .25 * grip, side < 0 ? -1 : 1, grip > .5 ? "claw" : "open", S * .9);
  ctx.restore();
}

function drawWorld(t, beat, alpha) {
  ctx.save(); ctx.globalAlpha = alpha;
  // sky
  const sky = ctx.createLinearGradient(0, 0, 0, H);
  sky.addColorStop(0, "#0c0624"); sky.addColorStop(.45, "#2a0f5c"); sky.addColorStop(.75, "#5a1a7c"); sky.addColorStop(1, "#ff5cd6");
  ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);
  // stars
  if (!INTRO.stars) INTRO.stars = Array.from({ length: 180 }, (_, i) => ({ x: Math.random(), y: Math.random() * .7, s: Math.random() * 1.6 + .4, p: Math.random() * TAU }));
  INTRO.stars.forEach((s) => { ctx.fillStyle = `rgba(255,240,255,${.35 + .45 * Math.sin(t * 2 + s.p) ** 2})`; ctx.fillRect(s.x * W, s.y * H, s.s, s.s); });
  // aurora ribbons
  for (let k = 0; k < 3; k++) {
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    const y0 = H * (.18 + k * .1), col = ["170,112,255", "255,92,214", "127,231,255"][k];
    const gr = ctx.createLinearGradient(0, y0 - 60, 0, y0 + 80); gr.addColorStop(0, `rgba(${col},0)`); gr.addColorStop(.5, `rgba(${col},${.16 + beat * .08})`); gr.addColorStop(1, `rgba(${col},0)`);
    ctx.fillStyle = gr; ctx.beginPath(); ctx.moveTo(0, y0);
    for (let x = 0; x <= W; x += 24) ctx.lineTo(x, y0 + Math.sin(x * .004 + t * .4 + k * 2) * 40 + Math.sin(x * .011 - t * .3) * 14);
    for (let x = W; x >= 0; x -= 24) ctx.lineTo(x, y0 + 90 + Math.sin(x * .005 + t * .35 + k) * 30);
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  // her moon: a crescent cradling a star, with a ring of bars that dances to the music
  const mx = W * .78, my = H * .24, mr = Math.min(W, H) * .085;
  glow(mx, my, mr * 3.2, "220,180,255", .25 + beat * .15);
  ctx.fillStyle = "#f6ecff"; ctx.beginPath(); ctx.arc(mx, my, mr, Math.PI * .25, Math.PI * 1.75); ctx.arc(mx + mr * .4, my, mr * .8, Math.PI * 1.65, Math.PI * .35, true); ctx.fill();
  ctx.fillStyle = "#fff"; star(mx + mr * .45, my, mr * .45, mr * .16, t * .2);
  for (let i = 0; i < 64; i++) {
    const a = i / 64 * TAU - Math.PI / 2, lv = spectrum(t, i % 32), r0 = mr * 1.5, r1 = r0 + 6 + lv * mr * 1.1;
    ctx.strokeStyle = `rgba(${i % 2 ? "255,92,214" : "199,164,255"},${.55 + lv * .4})`; ctx.lineWidth = 3; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(mx + Math.cos(a) * r0, my + Math.sin(a) * r0); ctx.lineTo(mx + Math.cos(a) * r1, my + Math.sin(a) * r1); ctx.stroke();
  }
  // floating islands with crystal spires, three layers deep
  if (!INTRO.isles) INTRO.isles = Array.from({ length: 7 }, (_, i) => ({ x: Math.random(), y: .38 + Math.random() * .28, s: .5 + Math.random() * .9, d: i % 3, p: Math.random() * TAU }));
  INTRO.isles.forEach((I) => {
    const s = I.s * Math.min(W, H) * .06 * (1 + I.d * .4), x = ((I.x * W + t * (6 + I.d * 6)) % (W + 300)) - 150, y = I.y * H + Math.sin(t * .6 + I.p) * 8;
    ctx.save(); ctx.globalAlpha = alpha * (.45 + I.d * .25);
    ctx.fillStyle = ["#2a1060", "#3a1680", "#4a1f9a"][I.d];
    ctx.beginPath(); ctx.moveTo(x - s * 1.6, y); ctx.lineTo(x + s * 1.6, y); ctx.lineTo(x + s * .5, y + s * 1.1); ctx.lineTo(x, y + s * 1.8); ctx.lineTo(x - s * .7, y + s * 1); ctx.closePath(); ctx.fill();
    [[-.8, 1.2], [-.2, 2.1], [.5, 1.5], [1, .9]].forEach(([dx, h]) => { ctx.beginPath(); ctx.moveTo(x + dx * s - s * .18, y); ctx.lineTo(x + dx * s, y - h * s); ctx.lineTo(x + dx * s + s * .18, y); ctx.closePath(); ctx.fill(); });
    glow(x - .2 * s, y - 2.1 * s, s * .8, "255,92,214", .25 + beat * .2);
    ctx.restore();
  });
  // a visualizer lying along the horizon, mirrored like water
  const n = 48, bw = W / n;
  for (let i = 0; i < n; i++) {
    const lv = spectrum(t, Math.floor(i * 32 / n)), h = 8 + lv * H * .12, x = i * bw + bw * .2, y = H - 44;
    ctx.fillStyle = lin(0, y - h, 0, y, [[0, "rgba(255,240,255,.8)"], [1, "rgba(199,164,255,.25)"]]); ctx.fillRect(x, y - h, bw * .6, h);
    ctx.fillStyle = "rgba(255,92,214,.12)"; ctx.fillRect(x, y, bw * .6, h * .35);
  }
  // little orbs drifting up
  for (let i = 0; i < 26; i++) { const q = (t * .05 + i * .173) % 1, x = (Math.sin(i * 9.1) * .5 + .5) * W, y = H - q * H; glow(x, y, 10 + beat * 6, i % 2 ? "255,92,214" : "127,231,255", .35 * Math.sin(q * Math.PI)); }
  // the taskbar stays, see-through
  ctx.fillStyle = "rgba(10,4,24,.55)"; ctx.fillRect(0, H - 44, W, 44); ctx.fillStyle = "rgba(255,255,255,.1)"; ctx.fillRect(0, H - 44, W, 1);
  ctx.restore();
}

function spectrum(t, i) {             // stand-in music for the preview (the real one listens to what your PC plays)
  const bass = Math.max(0, Math.sin(t * 2 * Math.PI * 2.1)) ** 3, f = i / 32;
  return Math.min(1, (1 - f) * bass * .9 + Math.abs(Math.sin(t * (3 + i * .7) + i)) * (.15 + f * .25) + Math.random() * .05);
}

function drawStartup(st, t, dt) {
  const beat = Math.max(0, Math.sin(t * 2 * Math.PI * 2.1)) ** 3;
  const flood = smooth(clamp((st - 3.2) / .7, 0, 1)), clear = smooth(clamp((st - 4.0) / 1.0, 0, 1));
  // the world underneath, once the light clears
  if (clear > 0) {
    drawWorld(t, beat, clear);
    const sc = Math.min((H - 120) / 560, W / 1100) * .7;
    STATE.forEach((s, i) => drawAt(s, W * .5 + (i - 1) * 260 * sc, H - 44, sc, t + i * 1.3));
  } else { ctx.fillStyle = "#04020a"; ctx.fillRect(0, 0, W, H); }
  if (st > 5.2) return;
  // the seam
  const seam = clamp(st / .5, 0, 1) * (1 - clamp((st - 1.4) / .4, 0, 1));
  if (seam > 0) { glow(W / 2, H / 2, H * .5 * seam, "170,112,255", .35 * seam); ctx.fillStyle = `rgba(240,220,255,${seam})`; ctx.fillRect(W / 2 - 1.5, H / 2 - H * .48 * seam, 3, H * .96 * seam); }
  // her face, rising
  const rise = smooth(clamp((st - 1.0) / 1.0, 0, 1)), out = 1 - flood;
  if (rise > 0 && out > 0) {
    const P = introPose(), sc = H * .62 / 100;
    blendPose(P, {}, 1);
    P.sleep = st < 2.0 ? 1 : 0; P.blink = 0;
    const pop = clamp((st - 2.0) / .35, 0, 1);
    P.open = st < 2.0 ? 1 : lerp(1.45, 1.15, pop); P.star = 1 - pop * .6;
    const sm = smooth(clamp((st - 2.35) / .8, 0, 1));
    P.smile = .1 + sm * .95; P.mo = sm * .35; P.mw = .75; P.blush = .3 + sm * .4; P.tilt = sm * .06; P.lookX = 0; P.lookY = 0;
    ctx.save(); ctx.globalAlpha = out;
    ctx.translate(W / 2, H * .5 + (1 - rise) * H * .7 + 430 * sc); ctx.scale(sc, sc);
    drawCharacter(JU, P, t);
    ctx.restore();
    if (st > 2.0 && st < 2.5) {             // the glint as her eyes open
      const k = 1 - (st - 2.0) / .5;
      [-1, 1].forEach((s) => { const x = W / 2 + s * 14.5 * sc, y = H * .5 + 6 * sc; glow(x, y, 40 * sc * .1 + 30, s < 0 ? "127,231,255" : "255,63,108", .8 * k); ctx.fillStyle = `rgba(255,255,255,${k})`; star(x - 3 * sc, y - 3 * sc, 6 * sc * k + 4, 2, 0); });
    }
  }
  // her hands on the edges of the screen
  const reach = smooth(clamp((st - .5) / .6, 0, 1)) * (1 - smooth(clamp((st - 3.3) / .5, 0, 1)));
  const grip = smooth(clamp((st - .9) / .3, 0, 1)) + Math.max(0, Math.sin((st - 2.4) * 8)) * .2 * (st > 2.4 && st < 3.2 ? 1 : 0);
  if (reach > 0) { bigHand(-1, reach, grip, t); bigHand(1, reach, grip, t); }
  // the flood of light
  if (flood > 0) {
    const r = Math.hypot(W, H) * flood;
    ctx.save(); ctx.globalAlpha = 1 - clear;
    const gr = ctx.createRadialGradient(W / 2, H * .5, 0, W / 2, H * .5, r + 1);
    gr.addColorStop(0, "rgba(255,245,255,1)"); gr.addColorStop(.5, "rgba(214,184,255,1)"); gr.addColorStop(1, "rgba(170,112,255,0)");
    ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H); ctx.restore();
  }
}
