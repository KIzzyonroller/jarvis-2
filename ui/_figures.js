// generated from the design preview: the three figures
// ======================================================================== JARVIS (his own: the sentinel)
// drawn around (0, 0) = the point under his hem; about 1000 units tall
const JC = { CY: [127, 231, 255], HOT: [228, 248, 255], GOLD: [255, 222, 168] };
seed = 3;
const J_RAYS = Array.from({ length: 30 }, (_, i) => ({ a: -Math.PI / 2 + (i / 30 - .5) * 3.0, len: 200 + rnd() * 140, w: .01 + rnd() * .02, base: .08 + rnd() * .06, ph: rnd() * TAU }));
const J_FALL = Array.from({ length: 260 }, () => ({ x: -330 + rnd() * 660, y0: rnd(), sp: .05 + rnd() * .12, s: rnd() > .9 ? 3 : 1.6, c: rnd() > .8 ? JC.GOLD : rnd() > .5 ? JC.HOT : JC.CY, a: .25 + rnd() * .6 }));
const J_FOLDS = Array.from({ length: 22 }, (_, i) => ({ fx: -260 + i * 24, sw: Math.sin(i * 1.7) * 14, ph: i * .7 }));
let jHalo = 0;
function drawJarvis(t, dt, v, th, li) {
  const { CY, HOT, GOLD } = JC, breath = Math.sin(t * .9);
  const CX = 0, HEADY = -860, HEM = 0, oy = -1330;      // the old drawing's coordinates, shifted so the hem sits at 0
  g.save(); g.translate(0, -oy - 1330);
  const Y = (y) => y + oy + 1330 - 1330;               // identity helper (kept for clarity)
  // his own aura: a soft halo of light and short rays, nothing more
  glow(CX, HEADY + 80, 420, CY, .07 + .04 * v); glow(CX, HEADY, 200, HOT, .1 + .06 * v + .04 * th);
  g.save(); g.globalCompositeOperation = "lighter";
  J_RAYS.forEach((r) => { const a = r.a + Math.sin(t * .15 + r.ph) * .02 + t * .01 * (1 + th * 3), al = r.base * (.7 + .3 * Math.sin(t * .7 + r.ph)) * (1 + v * .8 + th * .4), L = r.len * (1 + v * .2);
    const ray = g.createLinearGradient(CX, HEADY, CX + Math.cos(a) * L, HEADY + Math.sin(a) * L); ray.addColorStop(0, rgba(HOT, al)); ray.addColorStop(1, rgba(CY, 0));
    g.fillStyle = ray; g.beginPath(); g.moveTo(CX, HEADY); g.lineTo(CX + Math.cos(a - r.w) * L, HEADY + Math.sin(a - r.w) * L); g.lineTo(CX + Math.cos(a + r.w) * L, HEADY + Math.sin(a + r.w) * L); g.closePath(); g.fill(); });
  g.restore();
  // halo
  jHalo += dt * (.04 + th * .5);
  (function () {
    const R = 270 + breath * 3 + v * 6;
    ell(CX, HEADY, R, R, 0, CY, .28, 1.2); ell(CX, HEADY, R - 14, R - 14, 0, GOLD, .35 + .2 * th, 2.4);
    g.save(); g.translate(CX, HEADY); g.rotate(jHalo);
    for (let i = 0; i < 120; i++) { const a = i / 120 * TAU, l = i % 10 === 0 ? 16 : 6; g.strokeStyle = rgba(i % 10 === 0 ? GOLD : CY, i % 10 === 0 ? .7 : .3); g.lineWidth = i % 10 === 0 ? 2 : 1;
      g.beginPath(); g.moveTo(Math.cos(a) * (R - 28), Math.sin(a) * (R - 28)); g.lineTo(Math.cos(a) * (R - 28 - l), Math.sin(a) * (R - 28 - l)); g.stroke(); }
    g.rotate(-jHalo * 2.2);
    for (let i = 0; i < 48; i++) { if (i % 4 === 3) continue; const a = i / 48 * TAU, rr = R - 58, flick = th > .2 ? (Math.sin(t * 9 + i * 2.7) > .3 ? 1 : .25) : 1;
      g.save(); g.rotate(a); g.fillStyle = rgba(HOT, .4 * flick + .2 * th); g.fillRect(rr, -1, 10 + (i * 7) % 9, 2); if (i % 3 === 0) g.fillRect(rr + 4, -5, 2, 10); g.restore(); }
    g.rotate(jHalo * 1.2);
    for (let i = 0; i < 12; i++) { g.save(); g.rotate(i / 12 * TAU); g.fillStyle = rgba(GOLD, .75); g.beginPath(); g.moveTo(R + 4, 0); g.lineTo(R + 30, -6); g.lineTo(R + 46 + v * 12, 0); g.lineTo(R + 30, 6); g.closePath(); g.fill(); g.restore(); }
    g.restore();
  })();
  // wings
  function wing(base, angle, len, spread, n, alpha, ph) {
    for (let i = 0; i < n; i++) {
      const tt = i / (n - 1), a = angle + (tt - .5) * spread * (1 + li * .12) + Math.sin(t * .9 + ph + tt * 1.5) * .025, L = len * (.62 + .38 * Math.sin(tt * Math.PI)) * (1 - tt * .15) * (1 + v * .08 + li * .05);
      const ex = base[0] + Math.cos(a) * L, ey = base[1] + Math.sin(a) * L, nx = -Math.sin(a), ny = Math.cos(a), w = 9 + 7 * Math.sin(tt * Math.PI);
      const fg = g.createLinearGradient(base[0], base[1], ex, ey); fg.addColorStop(0, rgba(HOT, 0)); fg.addColorStop(.18, rgba(HOT, .55 * alpha * (1 + v * .5))); fg.addColorStop(.7, rgba(CY, .35 * alpha)); fg.addColorStop(1, rgba(CY, 0));
      g.fillStyle = fg; g.beginPath(); g.moveTo(base[0], base[1]); g.quadraticCurveTo(base[0] + Math.cos(a) * L * .5 + nx * w, base[1] + Math.sin(a) * L * .5 + ny * w, ex, ey);
      g.quadraticCurveTo(base[0] + Math.cos(a) * L * .5 - nx * w * .4, base[1] + Math.sin(a) * L * .5 - ny * w * .4, base[0], base[1]); g.fill();
      g.strokeStyle = rgba(HOT, .5 * alpha); g.lineWidth = 1; g.beginPath(); g.moveTo(base[0] + Math.cos(a) * L * .2, base[1] + Math.sin(a) * L * .2); g.lineTo(ex, ey); g.stroke();
    }
  }
  g.save(); g.globalCompositeOperation = "lighter";
  const lift = breath * .03 - li * .08;
  [1, -1].forEach((d) => { g.save(); g.scale(d, 1); wing([-70, HEADY + 170], -2.55 + lift, 430, .9, 12, 1, 0); wing([-80, HEADY + 230], -2.95 + lift * .6, 390, .7, 10, .85, 1); wing([-70, HEADY + 290], 2.6 - lift * .4, 320, .7, 9, .6, 2); g.restore(); });
  g.restore();
  // mantle
  const M0 = HEADY + 170;
  (function () {
    const sway = Math.sin(t * .7) * 10, p = new Path2D();
    p.moveTo(CX - 92, M0); p.bezierCurveTo(CX - 190, M0 + 180, CX - 250 + sway * .5, M0 + 460, CX - 310 + sway, HEM + 10);
    p.bezierCurveTo(CX - 200 + sway, HEM - 30, CX - 120 + sway, HEM + 30, CX + sway * .5, HEM - 10); p.bezierCurveTo(CX + 120 + sway, HEM + 30, CX + 200 + sway, HEM - 30, CX + 310 + sway, HEM + 10);
    p.bezierCurveTo(CX + 250 + sway * .5, M0 + 460, CX + 190, M0 + 180, CX + 92, M0); p.closePath();
    let gr2 = g.createLinearGradient(0, M0, 0, HEM); gr2.addColorStop(0, "rgba(14,64,82,1)"); gr2.addColorStop(.5, "rgba(8,40,54,.98)"); gr2.addColorStop(.85, "rgba(10,60,80,.8)"); gr2.addColorStop(1, "rgba(127,231,255,.3)");
    g.fillStyle = gr2; g.fill(p); g.save(); g.clip(p);
    J_FOLDS.forEach((f, i) => { const sw = f.sw + Math.sin(t * .8 + f.ph) * 8 + sway;
      g.strokeStyle = "rgba(0,8,14,.3)"; g.lineWidth = 10; g.beginPath(); g.moveTo(CX + f.fx * .25, M0 + 40); g.quadraticCurveTo(CX + f.fx * .7 + sw, M0 + 360, CX + f.fx * 1.15 + sway, HEM + 20); g.stroke();
      if (i % 3 === 1) { g.strokeStyle = rgba(HOT, .12 + .1 * Math.sin(t * 1.4 + f.ph) + .15 * v); g.lineWidth = 2; g.beginPath(); g.moveTo(CX + f.fx * .4, M0 + 220); g.quadraticCurveTo(CX + f.fx * .78 + sw, M0 + 440, CX + f.fx * 1.15 + sway, HEM + 20); g.stroke(); } });
    g.restore(); g.strokeStyle = rgba(GOLD, .8); g.lineWidth = 2.2; g.stroke(p); g.strokeStyle = rgba(CY, .35); g.lineWidth = 6; g.stroke(p);
  })();
  // inner robe + embroidered panel
  (function () {
    const p = new Path2D(); p.moveTo(CX - 64, M0 + 60); p.lineTo(CX - 120, HEM - 30); p.quadraticCurveTo(CX, HEM + 10, CX + 120, HEM - 30); p.lineTo(CX + 64, M0 + 60); p.closePath();
    let gr2 = g.createLinearGradient(0, M0 + 60, 0, HEM); gr2.addColorStop(0, "rgba(220,244,252,.95)"); gr2.addColorStop(.6, "rgba(160,214,232,.75)"); gr2.addColorStop(1, "rgba(127,231,255,.15)");
    g.fillStyle = gr2; g.fill(p);
    const tp = new Path2D(); tp.moveTo(CX - 40, M0 + 120); tp.lineTo(CX - 62, HEM - 90); tp.lineTo(CX, HEM - 40); tp.lineTo(CX + 62, HEM - 90); tp.lineTo(CX + 40, M0 + 120); tp.closePath();
    g.fillStyle = "rgba(10,48,64,.96)"; g.fill(tp); g.strokeStyle = rgba(GOLD, .85); g.lineWidth = 2; g.stroke(tp);
    g.save(); g.clip(tp); let j = 0;
    for (let y = M0 + 150; y < HEM - 70; y += 64, j++) { const wave = Math.max(0, Math.sin(t * 4 - j * .7)) * (v + th * .6); if (wave > .05) glow(CX, y + 20, 30, HOT, wave * .6);
      ell(CX, y + 20, 18, 18, 0, GOLD, .7, 1.4); ell(CX, y + 20, 9, 9, 0, CY, .8 + wave * .2, 1.2); ell(CX, y + 20, 26, 8, t * .5 + j, CY, .4, 1);
      g.strokeStyle = rgba(GOLD, .45); g.lineWidth = 1.2; g.beginPath(); g.moveTo(CX - 40, y + 50); g.lineTo(CX, y + 62); g.lineTo(CX + 40, y + 50); g.stroke(); }
    g.restore();
  })();
  // hem dissolving into falling light
  g.save(); g.globalCompositeOperation = "lighter";
  J_FALL.forEach((f) => { const p = (f.y0 + t * f.sp) % 1, y = HEM - 30 + Math.pow(p, 1.6) * 170, a = (1 - p) * f.a; g.fillStyle = rgba(f.c, a); g.fillRect(f.x + Math.sin(t + f.y0 * 9) * 4, y, f.s, f.s); });
  g.restore();
  // shoulders, sleeves, collar
  [1, -1].forEach((d) => { g.save(); g.scale(d, 1);
    for (let kk = 0; kk < 3; kk++) { const p = new Path2D(), o = kk * 16; p.moveTo(-70, M0 - 22 + o); p.quadraticCurveTo(-160 - o * .6, M0 - 40 + o, -178 - o * .4, M0 + 50 + o); p.quadraticCurveTo(-140, M0 + 36 + o, -82, M0 + 28 + o); p.closePath();
      const gr2 = g.createLinearGradient(-170, M0 - 40, -80, M0 + 50); gr2.addColorStop(0, "rgba(236,248,252,.98)"); gr2.addColorStop(1, "rgba(120,180,200,.95)"); g.fillStyle = gr2; g.fill(p); g.strokeStyle = rgba(GOLD, .9); g.lineWidth = 1.6; g.stroke(p); }
    const s = new Path2D(); s.moveTo(-150, M0 + 50); s.bezierCurveTo(-220, M0 + 160, -250, M0 + 260, -290, M0 + 360); s.lineTo(-190, M0 + 370); s.bezierCurveTo(-180, M0 + 260, -150, M0 + 160, -110, M0 + 80); s.closePath();
    const gr3 = g.createLinearGradient(0, M0 + 50, 0, M0 + 370); gr3.addColorStop(0, "rgba(14,64,82,1)"); gr3.addColorStop(1, "rgba(127,231,255,.35)"); g.fillStyle = gr3; g.fill(s); g.strokeStyle = rgba(GOLD, .7); g.lineWidth = 1.6; g.stroke(s);
    g.restore(); });
  for (let i = 0; i < 9; i++) { const a = Math.PI + .25 + i / 8 * (Math.PI - .5), px = CX + Math.cos(a) * 70, py = M0 - 40 + Math.sin(a) * 34, fl = 1 + .08 * Math.sin(t * 2 + i) + v * .15;
    g.save(); g.translate(px, py); g.rotate(a + Math.PI / 2); g.scale(1, fl); const gr2 = g.createLinearGradient(0, 0, 0, -70); gr2.addColorStop(0, rgba(HOT, .9)); gr2.addColorStop(1, rgba(CY, .05));
    g.fillStyle = gr2; g.beginPath(); g.moveTo(-9, 0); g.quadraticCurveTo(0, -80, 9, 0); g.closePath(); g.fill(); g.restore(); }
  // staff (when he's opening something: he raises it toward the spot, it flares, and a ring flies off it)
  const RH = [CX + 240, M0 + 360], LH = [CX - 240, M0 + 360];
  const ap = actP("jarvis", t + 0), JA = ap >= 0 ? ACT : null;
  let tilt = 0, flare = 0, slift = 0;
  if (JA) {
    const aim = Math.atan2(JA.local[1] - (HEADY - 120), JA.local[0] - RH[0]) + Math.PI / 2;        // staff points up by default
    const up = easeInOut(seg(ap, 0, .22)), down = easeInOut(seg(ap, .78, 1));
    tilt = Math.max(-.3, Math.min(.3, aim)) * (up - down); slift = -60 * (up - down); flare = Math.sin(seg(ap, .18, .42) * Math.PI);
  }
  g.save(); g.translate(RH[0], RH[1]); g.rotate(tilt); g.translate(-RH[0], -RH[1] - slift);
  (function () {
    const x = RH[0], top = HEADY - 140 + Math.sin(t * .9) * 4, bot = HEM;
    g.save(); g.globalCompositeOperation = "lighter";
    const gr2 = g.createLinearGradient(0, top, 0, bot); gr2.addColorStop(0, rgba(HOT, .95)); gr2.addColorStop(.75, rgba(CY, .8)); gr2.addColorStop(1, rgba(CY, 0));
    g.fillStyle = rgba(CY, .12 + .2 * v); g.fillRect(x - 9 - v * 4, top + 40, 18 + v * 8, bot - top - 40); g.fillStyle = gr2; g.fillRect(x - 2.5, top + 40, 5, bot - top - 40);
    const len = bot - top - 120;
    for (let i = 0; i < 9; i++) { const yy = bot - 60 - ((i * len / 9 + t * len * (.03 + th * .25)) % len); ell(x, yy, 13, 4, 0, i % 2 ? GOLD : HOT, .75, 1.6); }
    const hy = top + 20, pulse = 1 + v * .35 + th * .1 * Math.sin(t * 6);
    glow(x, hy, 110 * pulse, HOT, .35); glow(x, hy, 46, HOT, .6); ell(x, hy, 50 * pulse, 50 * pulse, 0, GOLD, .85, 2);
    ell(x, hy, 38, 13, .5 + t * (.6 + th * 2), CY, .9, 1.6); ell(x, hy, 38, 13, -.5 - t * (.6 + th * 2), CY, .9, 1.6); ell(x, hy, 15, 44, t * .4, HOT, .7, 1.4);
    g.save(); g.translate(x, hy); g.rotate(t * .3); g.fillStyle = rgba(HOT, 1); g.beginPath();
    for (let i = 0; i < 8; i++) { const a = i / 8 * TAU - Math.PI / 2, r = (i % 2 ? 7 : 23) * pulse; i ? g.lineTo(Math.cos(a) * r, Math.sin(a) * r) : g.moveTo(Math.cos(a) * r, Math.sin(a) * r); }
    g.closePath(); g.fill(); g.restore(); g.restore();
    if (flare > 0) { glow(x, hy, 220 * flare, HOT, .55 * flare); ell(x, hy, 90 * flare + 50, 90 * flare + 50, 0, HOT, .7 * flare, 2); }
  })();
  g.restore();
  if (JA && INFIG_FX) {                   // the ring (on the desktop the overlay draws it)
    const hx = RH[0] + Math.sin(tilt) * (RH[1] - (HEADY - 120)) , hy = RH[1] + slift - Math.cos(tilt) * (RH[1] - (HEADY - 120));
    const f = easeInOut(seg(ap, .3, .62));
    if (f > 0 && f < 1) {
      const [tx, ty] = JA.local, mx = (hx + tx) / 2, my = Math.min(hy, ty) - 260;
      const x = (1 - f) * (1 - f) * hx + 2 * (1 - f) * f * mx + f * f * tx, y = (1 - f) * (1 - f) * hy + 2 * (1 - f) * f * my + f * f * ty;
      glow(x, y, 90, HOT, .5); ell(x, y, 42, 14, t * 9, GOLD, .95, 3); ell(x, y, 42, 14, -t * 9, CY, .9, 2.4);
      for (let i = 1; i < 6; i++) { const ff = Math.max(0, f - i * .04), xx = (1 - ff) * (1 - ff) * hx + 2 * (1 - ff) * ff * mx + ff * ff * tx, yy = (1 - ff) * (1 - ff) * hy + 2 * (1 - ff) * ff * my + ff * ff * ty; glow(xx, yy, 30 - i * 4, CY, .3 - i * .05); }
    }
  }
  [RH, LH].forEach(([hx, hy]) => { glow(hx, hy, 56 + 10 * v, HOT, .5); g.fillStyle = rgba(HOT, .95); g.beginPath(); g.ellipse(hx, hy, 14, 18, 0, 0, TAU); g.fill(); });
  (function () { const x = LH[0], y = LH[1] - 70 + Math.sin(t * 1.3) * 5, sp = t * (1 + th * 3);
    glow(x, y, 80 + li * 40, HOT, .4 + li * .3); ell(x, y, 38, 12, -.3 + Math.sin(t) * .1, GOLD, .9, 1.8); ell(x, y, 30, 30 * Math.cos(sp), .9, CY, .85, 1.4); ell(x, y, 30 * Math.cos(sp * .8), 30, -.9, CY, .7, 1.2);
    g.fillStyle = rgba(HOT, 1); g.beginPath(); g.arc(x, y, 6 + li * 2, 0, TAU); g.fill();
    if (li > .05) for (let i = 0; i < 3; i++) { const p = ((t * .6 + i / 3) % 1), r = 110 * (1 - p); ell(x, y, r, r, 0, CY, li * .4 * p, 1.2); } })();
  // chest core
  (function () { const y = M0 + 95, beat = 1 + .06 * Math.pow(Math.max(0, Math.sin(t * 2.2)), 8) + v * .25;
    glow(CX, y, 86 * beat, HOT, .45 + .3 * v); g.fillStyle = rgba(HOT, .98); g.beginPath(); g.moveTo(CX, y - 30 * beat); g.lineTo(CX + 16 * beat, y); g.lineTo(CX, y + 30 * beat); g.lineTo(CX - 16 * beat, y); g.closePath(); g.fill();
    ell(CX, y, 34, 34, 0, GOLD, .85, 1.6); ell(CX, y, 46, 18, t * .4, CY, .6, 1.2); })();
  // head
  (function () { const y = HEADY + 70;
    g.save(); g.translate(CX, y + 50); g.rotate(-li * .1 + Math.sin(t * .5) * .015); g.translate(-CX, -(y + 50));
    glow(CX, y, 110, CY, .25 + .2 * v);
    const gr2 = g.createLinearGradient(CX - 40, y - 60, CX + 40, y + 60); gr2.addColorStop(0, "#f2fbfe"); gr2.addColorStop(.6, "#c4e2ec"); gr2.addColorStop(1, "#7fb0c2");
    g.fillStyle = gr2; g.beginPath(); g.ellipse(CX, y, 44, 62, 0, 0, TAU); g.fill(); g.strokeStyle = rgba(GOLD, .85); g.lineWidth = 1.6; g.stroke();
    g.strokeStyle = "rgba(60,120,140,.45)"; g.lineWidth = 1.1; for (let kk = 0; kk < 3; kk++) { g.beginPath(); g.ellipse(CX, y + 14, 30 - kk * 8, 34 - kk * 9, 0, Math.PI * 1.1, Math.PI * 1.9); g.stroke(); }
    g.beginPath(); g.moveTo(CX, y - 58); g.lineTo(CX, y - 16); g.stroke();
    const lw = 30 + v * 6 + th * 4 * Math.sin(t * 8); glow(CX, y + 2, 60 + v * 30, CY, .55 + .3 * v);
    g.strokeStyle = rgba(HOT, 1); g.lineWidth = 3.4 + v * 2.5; g.beginPath(); g.moveTo(CX - lw, y + 2); g.lineTo(CX + lw, y + 2); g.stroke();
    g.strokeStyle = rgba(CY, .35 + .3 * v); g.lineWidth = 8 + v * 6; g.stroke(); g.restore(); })();
  // crown
  (function () { const y = HEADY - 30 + Math.sin(t * .9) * 3, sp = t * (.5 + th * 2.5);
    glow(CX, y, 100 + v * 30, HOT, .35); ell(CX, y, 86, 22, 0, GOLD, .95, 2.6); ell(CX, y, 86, 22, 0, HOT, .5, 7);
    ell(CX, y, 62, 58 * Math.cos(sp), .95, CY, .85, 1.8); ell(CX, y, 62 * Math.cos(sp * .7), 58, -.95, CY, .7, 1.6);
    for (let i = 0; i < 7; i++) { const a = Math.PI + i / 6 * Math.PI, x = CX + Math.cos(a) * 86, yy = y + Math.sin(a) * 22; g.fillStyle = rgba(GOLD, .95); g.beginPath(); g.moveTo(x, yy - 14 - (i === 3 ? 12 : 0)); g.lineTo(x + 4, yy); g.lineTo(x - 4, yy); g.closePath(); g.fill(); }
    g.fillStyle = rgba(HOT, 1); g.beginPath(); g.arc(CX, y, 7, 0, TAU); g.fill(); })();
  if (S.speak > .05) for (let i = 0; i < 3; i++) { const p = ((t * .7 + i / 3) % 1), r = 100 + p * 300; ell(CX, HEADY + 72, r, r * .9, 0, CY, S.speak * (.16 + v * .2) * (1 - p), 1.4); }
  // two moons
  const a1 = t * .5, a2 = -t * .35 + 2;
  ell(CX, M0 + 260, 330, 64, -.12, CY, .26, 1.3);
  const m1 = [CX + Math.cos(a1) * 330 * Math.cos(-.12) - Math.sin(a1) * 64 * Math.sin(-.12), M0 + 260 + Math.cos(a1) * 330 * Math.sin(-.12) + Math.sin(a1) * 64 * Math.cos(-.12)];
  glow(m1[0], m1[1], 28, HOT, .7); g.fillStyle = rgba(HOT, 1); g.beginPath(); g.arc(m1[0], m1[1], 7, 0, TAU); g.fill();
  const m2 = [CX + Math.cos(a2) * 380, M0 + 400 + Math.sin(a2) * 80]; glow(m2[0], m2[1], 22, GOLD, .7); g.fillStyle = rgba(GOLD, 1); g.beginPath(); g.arc(m2[0], m2[1], 5, 0, TAU); g.fill();
  g.restore();
}

// ======================================================================== ULTRON (his own: the shadow on the stage)
const UC = { RED: [255, 48, 70], EMBER: [255, 120, 60], BLOOD: [120, 8, 22], GILT: [196, 150, 92], BONE: [236, 222, 214] };
seed = 9;
const U_SMOKE = Array.from({ length: 140 }, () => ({ side: rnd() > .5 ? 1 : -1, p0: rnd(), sp: .05 + rnd() * .1, r: 3 + rnd() * 9, dx: rnd(), red: rnd() > .75 }));
const U_EMBERS = Array.from({ length: 70 }, () => ({ x: -260 + rnd() * 520, p0: rnd(), sp: .08 + rnd() * .14, s: .8 + rnd() * 2, wob: rnd() * TAU }));
const U_HEM = Array.from({ length: 60 }, () => ({ x: -290 + rnd() * 580, r: 8 + rnd() * 16, ph: rnd() * TAU }));
let uRuff = 0;
function drawUltron(t, dt, v, th, li) {
  const { RED, EMBER, BLOOD, GILT, BONE } = UC, breath = Math.sin(t * .8);
  const HEADY = -900;
  // his shadow-self: a darker echo of him, lagging a little behind, flickering
  g.save(); g.globalAlpha = .28 + .1 * Math.sin(t * 3.1) * th; g.translate(Math.sin(t * .6) * 26 - 30, -10 + Math.cos(t * .5) * 10); g.scale(1.06, 1.04);
  g.fillStyle = "#000"; g.beginPath(); g.moveTo(-60, -830); g.bezierCurveTo(-400, -820, -420, -200, -330, 20); g.lineTo(330, 20); g.bezierCurveTo(420, -200, 400, -820, 60, -830); g.closePath(); g.fill();
  g.restore();
  // his own footlights: small embers floating under him, lighting him from below
  for (let i = 0; i < 5; i++) { const x = -220 + i * 110, y = 40 + Math.sin(t * 1.3 + i) * 6, fl = .7 + .3 * Math.sin(t * 9 + i * 3) * Math.sin(t * 5.3 + i);
    glow(x, y, 70, EMBER, .22 * fl + .1 * v); glow(x, y, 14, [255, 200, 150], .8 * fl); }
  glow(0, -100, 380, EMBER, .07 + .05 * v);
  // smoke sleeves, curling
  [-1, 1].forEach((dir) => {
    const x0 = dir * 150, y0 = -660, s1 = Math.sin(t * .9 + dir) * 40, s2 = Math.cos(t * .7 + dir) * 50, open = li * 60 + v * 30;
    for (let k = 0; k < 7; k++) {
      g.strokeStyle = `rgba(${k % 2 ? "44,4,14" : "10,0,4"},${.6 - k * .07})`; g.lineWidth = 46 - k * 5; g.lineCap = "round";
      g.beginPath(); g.moveTo(x0, y0); g.bezierCurveTo(x0 + dir * (160 + k * 30 + open), y0 + 120 + k * 20 + s1, x0 + dir * (120 + k * 40 + s2), y0 + 380, x0 + dir * (240 + k * 25 + open * .5), y0 + 560 + k * 30 + s1 * .5); g.stroke();
    }
    g.strokeStyle = rgba(GILT, .55); g.lineWidth = 2; g.beginPath(); g.moveTo(x0, y0); g.bezierCurveTo(x0 + dir * (150 + open), y0 + 110 + s1, x0 + dir * (110 + s2), y0 + 370, x0 + dir * (230 + open * .5), y0 + 550 + s1 * .5); g.stroke();
  });
  U_SMOKE.forEach((s) => { const p = (s.p0 + t * s.sp * (1 + th * 1.5)) % 1, x = s.side * (230 + p * 220 + s.dx * 90 + Math.sin(t + s.p0 * 9) * 20), y = -360 + p * 380 - p * p * 260, a = Math.sin(p * Math.PI) * .45;
    g.fillStyle = s.red ? rgba(RED, a * .7) : `rgba(30,2,10,${a.toFixed(3)})`; g.beginPath(); g.arc(x, y, s.r * (1 + p), 0, TAU); g.fill(); });
  // underskirt of shadow, its hem pooling into smoke on the "stage" he carries with him
  const sway = Math.sin(t * .6) * 14;
  let p = new Path2D(); p.moveTo(-110, -560); p.bezierCurveTo(-210, -320, -270 + sway * .4, -140, -310 + sway, 10); p.lineTo(300 + sway, 10); p.bezierCurveTo(260 + sway * .4, -140, 200, -320, 110, -560); p.closePath();
  let gr = g.createLinearGradient(0, -560, 0, 10); gr.addColorStop(0, "#0d0105"); gr.addColorStop(1, "#26040c"); g.fillStyle = gr; g.fill(p);
  U_HEM.forEach((h) => { const r = h.r * (1 + .25 * Math.sin(t * 1.5 + h.ph)); g.fillStyle = "rgba(24,2,8,.75)"; g.beginPath(); g.arc(h.x + sway, 6 + Math.sin(t + h.ph) * 5, r, 0, TAU); g.fill(); });
  // draped, uneven tiers of lacquered costume-armor, each swinging a little differently
  [[-500, 120, 220, "#3c0410", .9], [-390, 150, 280, "#5e0614", 1.2], [-260, 185, 340, "#7e0a1c", 1.5]].forEach(([y, w0, w1, col, swing], tier) => {
    const sw = Math.sin(t * .8 + tier * 1.3) * 12 * swing, h = 150, q = new Path2D();
    q.moveTo(-w0, y); q.bezierCurveTo(-w0 - 40, y + 50, -w1 - 10 + sw, y + h * .7, -w1 + sw, y + h + 10);
    for (let i = 1; i <= 10; i++) { const x0 = -w1 + (i - 1) * (w1 * 2 / 10) + sw, x1 = -w1 + i * (w1 * 2 / 10) + sw, dip = (i % 3 === 0 ? 44 : i % 2 ? 18 : 30) + Math.sin(t * 1.2 + i + tier) * 6;
      q.quadraticCurveTo((x0 + x1) / 2, y + h + dip, x1, y + h + (i === 10 ? -6 : 4)); }
    q.bezierCurveTo(w1 + 20 + sw, y + h * .6, w0 + 50, y + 40, w0, y); q.closePath();
    gr = g.createLinearGradient(0, y, 0, y + h + 40); gr.addColorStop(0, col); gr.addColorStop(1, "#120208"); g.fillStyle = gr; g.fill(q);
    g.strokeStyle = rgba(GILT, .7); g.lineWidth = 1.8; g.stroke(q);
    g.save(); g.clip(q);
    for (let i = -7; i <= 7; i++) { const x = i * (w1 / 7) + sw * .5; g.strokeStyle = rgba(GILT, .32); g.lineWidth = 1.2; g.beginPath(); g.arc(x, y + 30, 11, Math.PI, TAU); g.stroke(); g.beginPath(); g.arc(x, y + 30, 4, 0, TAU); g.stroke(); }
    for (let i = 0; i < 6; i++) { const x = -w1 + 40 + i * (w1 * 2 - 80) / 5 + sw; g.strokeStyle = "rgba(0,0,0,.35)"; g.lineWidth = 9; g.beginPath(); g.moveTo(x * .6, y + 40); g.quadraticCurveTo(x * .9, y + 100, x, y + h + 30); g.stroke(); }
    g.restore();
  });
  // embers rising off him (faster while he thinks)
  g.save(); g.globalCompositeOperation = "lighter";
  U_EMBERS.forEach((e) => { const pp = (e.p0 + t * e.sp * (1 + th)) % 1, y = 0 - pp * 900, x = e.x * (1 - pp * .3) + Math.sin(t * 2 + e.wob) * 14; g.fillStyle = rgba(pp > .6 ? RED : EMBER, Math.sin(pp * Math.PI) * .8); g.beginPath(); g.arc(x, y, e.s, 0, TAU); g.fill(); });
  g.restore();
  // cuirass and the cracked heart
  p = new Path2D(); p.moveTo(-120, -680); p.bezierCurveTo(-140, -600, -90, -520, -60, -480); p.lineTo(0, -450); p.lineTo(60, -480); p.bezierCurveTo(90, -520, 140, -600, 120, -680); p.closePath();
  gr = g.createLinearGradient(-120, -680, 120, -460); gr.addColorStop(0, "#2a0510"); gr.addColorStop(.5, "#0a0104"); gr.addColorStop(1, "#3a0612"); g.fillStyle = gr; g.fill(p); g.strokeStyle = rgba(GILT, .85); g.lineWidth = 2; g.stroke(p);
  g.save(); g.clip(p); for (let r = 30; r < 200; r += 22) { g.strokeStyle = rgba(GILT, .2); g.lineWidth = 1; g.beginPath(); g.arc(0, -420, r, Math.PI * 1.15, Math.PI * 1.85); g.stroke(); } g.restore();
  const beat = 1 + .1 * Math.pow(Math.max(0, Math.sin(t * 1.8)), 10) + v * .35;
  glow(0, -580, 70 * beat, RED, .5 + .3 * v); g.fillStyle = rgba(RED, .95); g.beginPath(); g.moveTo(0, -614 * 1 - 4 * beat); g.lineTo(14 * beat, -580); g.lineTo(0, -544 + 4 * beat); g.lineTo(-14 * beat, -580); g.closePath(); g.fill();
  g.strokeStyle = rgba([255, 210, 190], .5 + .5 * v); g.lineWidth = 1; g.beginPath(); g.moveTo(-4, -608); g.lineTo(3, -585); g.lineTo(-5, -568); g.lineTo(2, -548); g.stroke();
  // upswept shoulders that rise when he's listening
  [1, -1].forEach((d) => { g.save(); g.scale(d, 1); g.translate(0, -li * 10); g.rotate(li * -.04 + Math.sin(t * .8) * .01);
    for (let k = 0; k < 4; k++) { const q = new Path2D(), o = k * 18; q.moveTo(-110, -700 + o); q.quadraticCurveTo(-210 - o, -750 + o * .5, -270 - o * .8, -760 + o * 1.4); q.quadraticCurveTo(-210, -680 + o, -120, -652 + o); q.closePath();
      gr = g.createLinearGradient(-270, -760, -110, -660); gr.addColorStop(0, k % 2 ? "#7a0a1c" : "#1a0208"); gr.addColorStop(1, "#0a0104"); g.fillStyle = gr; g.fill(q); g.strokeStyle = rgba(GILT, .75); g.lineWidth = 1.5; g.stroke(q); }
    g.restore(); });
  // ruff of blades: breathes out, turns slowly while he thinks
  uRuff += dt * th * .6;
  for (let layer = 0; layer < 2; layer++) for (let i = 0; i < 22; i++) {
    const a = Math.PI + .05 + ((i / 21 + uRuff * (layer ? -1 : 1) * .05) % 1) * (Math.PI - .1), r0 = 54, r1 = (132 - layer * 30 + (i % 2 ? 0 : 16)) * (1 + .04 * breath + .1 * v + .08 * li);
    g.save(); g.translate(0, -720); g.rotate(a);
    gr = g.createLinearGradient(r0, 0, r1, 0); gr.addColorStop(0, layer ? "#5a0612" : "#16020a"); gr.addColorStop(1, layer ? rgba(RED, .9) : rgba(BONE, .85));
    g.fillStyle = gr; g.beginPath(); g.moveTo(r0, -7); g.lineTo(r1, 0); g.lineTo(r0, 7); g.closePath(); g.fill(); g.strokeStyle = rgba(GILT, .5); g.lineWidth = .8; g.stroke(); g.restore();
  }
  // reaching out: a jointed lacquer arm slides out of the smoke of his sleeve, the clawed hand opens, a thread shoots out
  const up2 = actP("ultron", t), UA = up2 >= 0 ? ACT : null;
  if (UA) {
    const [tx, ty] = UA.local, dir = tx < 0 ? -1 : 1, sx = dir * 200, sy = -690, L = 250;
    const out = easeOut(seg(up2, 0, .28)) * (1 - easeInOut(seg(up2, .8, 1)));
    if (out > .01) {
      const dx = tx - sx, dy = ty - sy, dl = Math.hypot(dx, dy) || 1, ux_ = dx / dl, uy_ = dy / dl;
      const reach = Math.min(2 * L - 20, dl) * (.25 + .75 * out), wx = sx + ux_ * reach, wy = sy + uy_ * reach;
      const bend = Math.sqrt(Math.max(0, L * L - reach * reach / 4)), nx = -uy_ * dir, ny = ux_ * dir;      // elbow drops below the line
      const elx = (sx + wx) / 2 + nx * bend * (ny > 0 ? 1 : -1), ely = (sy + wy) / 2 + ny * bend * (ny > 0 ? 1 : -1);
      g.save(); g.globalAlpha = Math.min(1, out * 2.5);
      // smoke pouring off the sleeve
      for (let i = 0; i < 7; i++) { const k = ((t * .7 + i / 7) % 1); glow(sx + (elx - sx) * k * .6 + Math.sin(t * 2 + i) * 14, sy + (ely - sy) * k * .6 + k * 40, 70 - k * 40, BLOOD, .35 * (1 - k)); }
      const limb = (x0, y0, x1, y1, w0, w1) => {
        const a = Math.atan2(y1 - y0, x1 - x0), px = Math.sin(a), py = -Math.cos(a);
        const pth = new Path2D(); pth.moveTo(x0 + px * w0, y0 + py * w0); pth.quadraticCurveTo((x0 + x1) / 2 + px * w0 * 1.15, (y0 + y1) / 2 + py * w0 * 1.15, x1 + px * w1, y1 + py * w1);
        pth.lineTo(x1 - px * w1, y1 - py * w1); pth.quadraticCurveTo((x0 + x1) / 2 - px * w0 * 1.05, (y0 + y1) / 2 - py * w0 * 1.05, x0 - px * w0, y0 - py * w0); pth.closePath();
        const gr = g.createLinearGradient(x0 + px * w0, y0 + py * w0, x0 - px * w0, y0 - py * w0); gr.addColorStop(0, "#5a0717"); gr.addColorStop(.45, "#2a020b"); gr.addColorStop(1, "#0c0004");
        g.fillStyle = gr; g.fill(pth); g.strokeStyle = rgba(GILT, .55); g.lineWidth = 1.6; g.stroke(pth);
        g.strokeStyle = rgba(RED, .25); g.lineWidth = 2; g.beginPath(); g.moveTo(x0 + px * w0 * .5, y0 + py * w0 * .5); g.lineTo(x1 + px * w1 * .5, y1 + py * w1 * .5); g.stroke();
        return a;
      };
      const band = (x, y, a, w) => { g.save(); g.translate(x, y); g.rotate(a); g.fillStyle = rgba(GILT, .9); g.fillRect(-5, -w, 10, w * 2); g.fillStyle = "rgba(0,0,0,.4)"; g.fillRect(-1, -w, 2, w * 2); g.restore(); };
      const a1 = limb(sx, sy, elx, ely, 34, 26);
      band(sx + (elx - sx) * .35, sy + (ely - sy) * .35, a1, 34);
      const a2 = limb(elx, ely, wx, wy, 26, 18);
      g.fillStyle = "#1a0208"; g.beginPath(); g.arc(elx, ely, 24, 0, TAU); g.fill(); g.strokeStyle = rgba(GILT, .8); g.lineWidth = 2; g.stroke();
      glow(elx, ely, 26, RED, .35);
      for (const k of [.55, .7, .85]) band(elx + (wx - elx) * k, ely + (wy - ely) * k, a2, 22 - k * 4);
      // the hand: palm, three jointed claws and a thumb, curled shut then flared open toward the spot
      const open = easeOut(seg(up2, .16, .34)) * (1 - seg(up2, .78, 1));
      g.save(); g.translate(wx, wy); g.rotate(a2);
      g.fillStyle = "#14010a"; g.beginPath(); g.ellipse(18, 0, 32, 26, 0, 0, TAU); g.fill(); g.strokeStyle = rgba(GILT, .85); g.lineWidth = 1.8; g.stroke();
      glow(26, 0, 30 + 40 * open, RED, .25 + .45 * open);
      const finger = (base, spread, len) => {
        g.save(); g.translate(42, base); g.rotate(spread);
        const curl = (1 - open) * 1.1;
        g.fillStyle = rgba(GILT, .95); g.strokeStyle = "#2a0a06"; g.lineWidth = 1;
        g.beginPath(); g.moveTo(0, -6); g.lineTo(len * .5, -4); g.lineTo(len * .5, 4); g.lineTo(0, 6); g.closePath(); g.fill(); g.stroke();
        g.translate(len * .5, 0); g.rotate(curl);
        g.beginPath(); g.moveTo(0, -4); g.quadraticCurveTo(len * .3, -3, len * .55, 2 + curl * 4); g.lineTo(0, 4); g.closePath(); g.fill(); g.stroke();
        g.restore();
      };
      finger(-15, -.32 * open - .05, 74); finger(0, 0, 84); finger(15, .32 * open + .05, 74);
      g.save(); g.translate(14, -22 * dir); g.rotate(-1.1 * dir * (.4 + .6 * open)); g.fillStyle = rgba(GILT, .95); g.beginPath(); g.moveTo(0, -5); g.lineTo(52, 0); g.lineTo(0, 5); g.closePath(); g.fill(); g.restore();
      g.restore();
      g.restore();
      // the thread: shot from the palm to the spot
      const hx = wx + Math.cos(a2) * 60, hy = wy + Math.sin(a2) * 60;
      const f = seg(up2, .3, .48), fade = 1 - seg(up2, .62, .78);
      if (INFIG_FX && f > 0 && fade > 0) {
        const lx = hx + (tx - hx) * easeOut(f), ly = hy + (ty - hy) * easeOut(f), jit = Math.sin(t * 50) * 6;
        g.save(); g.globalCompositeOperation = "lighter"; g.lineCap = "round";
        g.strokeStyle = rgba(EMBER, .28 * fade); g.lineWidth = 16; g.beginPath(); g.moveTo(hx, hy); g.quadraticCurveTo((hx + lx) / 2 + jit, (hy + ly) / 2 - 40, lx, ly); g.stroke();
        g.strokeStyle = rgba(RED, .95 * fade); g.lineWidth = 4; g.stroke();
        g.strokeStyle = rgba(BONE, .8 * fade); g.lineWidth = 1.2; g.stroke();
        glow(lx, ly, 60, RED, .8 * fade); g.restore();
      }
    }
  }
  // the head: a true void, with plumes above and the slit burning through it
  const y = HEADY + 80, tilt = li * .08 + Math.sin(t * .4) * .02;
  g.save(); g.translate(0, y + 60); g.rotate(tilt); g.translate(0, -(y + 60));
  for (let i = 0; i < 9; i++) {
    const side = i - 4, shiver = Math.sin(t * (6 + i) + i) * .015 * (1 + v * 3) + Math.sin(t * .7 + i * .5) * .03, fan = 1 + li * .25 + v * .1;
    const a = -Math.PI / 2 + side * .2 * fan + shiver, len = (380 - Math.abs(side) * 30) * (1 + .03 * breath);
    const bx = side * 10, by = y - 60, ex = bx + Math.cos(a) * len + side * 40, ey = by + Math.sin(a) * len;
    g.strokeStyle = rgba(i % 2 ? BLOOD : [40, 0, 8], .95); g.lineWidth = 6; g.lineCap = "round";
    g.beginPath(); g.moveTo(bx, by); g.quadraticCurveTo(bx + side * 70, by - len * .6, ex, ey); g.stroke();
    for (let f = 0; f < 24; f++) { const tt = .25 + f / 24 * .75, px = bx + (ex - bx) * tt + side * 30 * Math.sin(tt * Math.PI), py = by + (ey - by) * tt, fl = 1 + .3 * Math.sin(t * 8 + f + i) * v;
      g.strokeStyle = rgba(f % 3 ? RED : BONE, (.35 + tt * .4) * fl); g.lineWidth = 1.2; g.beginPath(); g.moveTo(px, py); g.lineTo(px + 14 + side * 2, py + 10); g.moveTo(px, py); g.lineTo(px - 14 + side * 2, py + 10); g.stroke(); }
  }
  g.fillStyle = "#12020a"; g.beginPath(); g.moveTo(-74, y - 40); g.quadraticCurveTo(0, y - 110, 74, y - 40); g.lineTo(64, y - 20); g.quadraticCurveTo(0, y - 78, -64, y - 20); g.closePath(); g.fill();
  g.strokeStyle = rgba(GILT, .9); g.lineWidth = 2; g.stroke();
  for (let i = 0; i < 9; i++) { const tt = i / 8, x = -68 + tt * 136, yy = y - 32 - Math.sin(tt * Math.PI) * 30, fl = .6 + .4 * Math.sin(t * 4 + i * 1.7); glow(x, yy, 10, EMBER, .7 * fl); g.fillStyle = rgba(EMBER, fl); g.beginPath(); g.arc(x, yy, 3.4, 0, TAU); g.fill(); }
  [1, -1].forEach((d) => { for (let s = 0; s < 3; s++) for (let b2 = 0; b2 < 8; b2++) { const sw2 = Math.sin(t * 1.6 + s) * b2 * 1.2, x = d * (-70 - s * 9) + sw2, yy = y - 26 + b2 * 18 + s * 6; g.fillStyle = rgba(b2 % 2 ? GILT : RED, .85); g.beginPath(); g.arc(x, yy, 3, 0, TAU); g.fill(); } });
  // the void: pure black, with smoke spilling off its rim
  g.fillStyle = "#000"; g.beginPath(); g.ellipse(0, y + 4, 52, 70, 0, 0, TAU); g.fill();
  g.strokeStyle = rgba(GILT, .45); g.lineWidth = 1.2; g.stroke();
  for (let i = 0; i < 26; i++) { const a = i / 26 * TAU + t * .3, r = 56 + Math.sin(t * 2 + i) * 6; g.fillStyle = "rgba(6,0,2,.7)"; g.beginPath(); g.arc(Math.cos(a) * r, y + 4 + Math.sin(a) * r * 1.3, 7 + 4 * Math.sin(t * 1.7 + i * 2), 0, TAU); g.fill(); }
  // the slit: scans while thinking, flares wide while talking
  const sx = th > .1 ? Math.sin(t * 2.4) * 14 * th : 0, sh = 2.2 + v * 5 + li * 1.4, sl = 30 + v * 10;
  glow(sx, y, 80 + v * 50, RED, .45 + .3 * v); glow(sx, y, 30, EMBER, .6);
  g.fillStyle = rgba([255, 228, 214], 1); g.beginPath(); g.ellipse(sx, y, sl, sh, -.04, 0, TAU); g.fill();
  g.strokeStyle = rgba(RED, .5 + .3 * v); g.lineWidth = 6 + v * 6; g.beginPath(); g.moveTo(sx - sl - 4, y + 1); g.lineTo(sx + sl + 4, y - 1); g.stroke();
  g.restore();
  // talking: a crimson pulse ripples out from him
  if (S.speak > .05) for (let i = 0; i < 3; i++) { const pp = ((t * .8 + i / 3) % 1), r = 90 + pp * 320; ell(0, y, r, r * .85, 0, RED, S.speak * (.18 + v * .25) * (1 - pp), 1.5); }
}


// ======================================================================== the merged one: a new being, made of both of them
// His light and staff, her crown, claws and tiered stage robe, one violet body. Hem at (0, 0), like the others.
const MC = { VI: [170, 112, 255], MAG: [255, 92, 214], LIL: [244, 232, 255], GOLD: [255, 214, 160], DEEP: [44, 16, 78] };
const M_FALL = Array.from({ length: 180 }, () => ({ x: -340 + rnd() * 680, y0: rnd(), sp: .04 + rnd() * .1, s: rnd() > .9 ? 2.6 : 1.4, c: rnd() > .6 ? MC.VI : rnd() > .5 ? MC.MAG : MC.LIL, a: .2 + rnd() * .6 }));
function drawMerged(t, dt, v, th, li) {
  const { VI, MAG, LIL, GOLD, DEEP } = MC, HEADY = -860, HEM = 0, M0 = HEADY + 170, breath = Math.sin(t * .9), sway = Math.sin(t * .7) * 10;
  const ap = actP("fused", t);
  glow(0, HEADY + 320, 720, VI, .1 + .05 * v); glow(0, HEADY + 40, 280, LIL, .1 + .08 * v + .05 * th);
  // the fan behind: shafts of light that end in feathered plumes
  const N = 19;
  for (let i = 0; i < N; i++) {
    const k = i / (N - 1), a = -Math.PI / 2 + (k - .5) * 2.6 + Math.sin(t * .6 + i * 1.7) * .015 + breath * .02 * (k - .5);
    const L = (380 + Math.sin(k * Math.PI) * 170) * (1 - li * .12) + v * 50, bx = 0, by = HEADY + 110, ex = bx + Math.cos(a) * L, ey = by + Math.sin(a) * L;
    const c = i % 2 ? VI : MAG, gr = g.createLinearGradient(bx, by, ex, ey);
    gr.addColorStop(0, rgba(LIL, 0)); gr.addColorStop(.35, rgba(c, .5 + .2 * v)); gr.addColorStop(1, rgba(c, .05));
    g.strokeStyle = gr; g.lineWidth = 2.5; g.beginPath(); g.moveTo(bx + Math.cos(a) * 60, by + Math.sin(a) * 60); g.lineTo(ex, ey); g.stroke();
    g.strokeStyle = rgba(c, .32); g.lineWidth = 1.4;
    for (let j = 0; j < 7; j++) { const q = .5 + j * .07, px = bx + Math.cos(a) * L * q, py = by + Math.sin(a) * L * q, w = 20 - j * 2;
      g.beginPath(); g.moveTo(px + Math.cos(a + 2.6) * w, py + Math.sin(a + 2.6) * w); g.lineTo(px, py); g.lineTo(px + Math.cos(a - 2.6) * w, py + Math.sin(a - 2.6) * w); g.stroke(); }
    glow(ex, ey, 10 + v * 6, LIL, .5);
  }
  // wings: three rows of long feathers on each side, his light and her plumes in one shape
  [-1, 1].forEach((d) => {
    const ox = d * 90, oy = M0 + 10;
    for (let row = 2; row >= 0; row--) {
      const n = 9 - row * 2, len0 = 420 - row * 110;
      for (let i = 0; i < n; i++) {
        const k = i / (n - 1), a = -Math.PI / 2 + d * (.3 + k * 1.45) - d * (breath * .04 + li * .12 - v * .04) + Math.sin(t * .9 + i + row) * .012;
        const L = len0 * (1 - k * .3), w = 30 - row * 5;
        const ex = ox + Math.cos(a) * L, ey = oy + Math.sin(a) * L, nx = -Math.sin(a), ny = Math.cos(a);
        const fe = new Path2D(); fe.moveTo(ox, oy);
        fe.quadraticCurveTo(ox + Math.cos(a) * L * .5 + nx * w, oy + Math.sin(a) * L * .5 + ny * w, ex, ey);
        fe.quadraticCurveTo(ox + Math.cos(a) * L * .5 - nx * w * .6, oy + Math.sin(a) * L * .5 - ny * w * .6, ox, oy);
        const fg = g.createLinearGradient(ox, oy, ex, ey); fg.addColorStop(0, `rgba(40,12,74,${.9 - row * .15})`); fg.addColorStop(.6, rgba(row === 0 ? VI : DEEP, .75 - row * .12)); fg.addColorStop(1, rgba(MAG, .55));
        g.fillStyle = fg; g.fill(fe); g.strokeStyle = rgba(row === 0 ? LIL : VI, .45); g.lineWidth = 1.1; g.stroke(fe);
        g.strokeStyle = rgba(GOLD, .3); g.beginPath(); g.moveTo(ox, oy); g.lineTo(ex, ey); g.stroke();
        if (row === 0) glow(ex, ey, 14 + 10 * v, MAG, .5);
      }
    }
  });
  // halo: an outer ring with turning marks, an inner broken ring the other way, glyphs orbiting when thinking
  g.save(); g.translate(0, HEADY); g.rotate(t * .12);
  ell(0, 0, 240, 240, 0, LIL, .5, 1.6); for (let i = 0; i < 36; i++) { g.save(); g.rotate(i / 36 * TAU); g.fillStyle = rgba(i % 3 ? VI : GOLD, .7); g.fillRect(246, -1.2, i % 3 ? 8 : 16, 2.4); g.restore(); }
  g.rotate(-t * .3); for (let i = 0; i < 6; i++) ell(0, 0, 205, 205, 0, MAG, .55, 2.4, i / 6 * TAU, i / 6 * TAU + .7);
  g.restore();
  if (th > .02) for (let i = 0; i < 8; i++) { const a = t * 1.4 + i / 8 * TAU, x = Math.cos(a) * 300, y = HEADY + Math.sin(a) * 110;
    g.save(); g.translate(x, y); g.rotate(a); g.fillStyle = rgba(i % 2 ? LIL : MAG, .8 * th); g.beginPath(); g.moveTo(0, -9); g.lineTo(6, 0); g.lineTo(0, 9); g.lineTo(-6, 0); g.closePath(); g.fill(); g.restore(); }
  // the cape: wider than the robe, falling behind it
  const cape = new Path2D(); cape.moveTo(-120, M0 + 10); cape.bezierCurveTo(-300, M0 + 220, -330 + sway, M0 + 520, -400 + sway * 1.4, HEM + 18);
  for (let j = 0; j < 8; j++) { const x0 = -400 + j * 100 + sway * 1.4; cape.quadraticCurveTo(x0 + 50, HEM - 18 + (j % 2) * 34, x0 + 100, HEM + 18); }
  cape.bezierCurveTo(330 + sway, M0 + 520, 300, M0 + 220, 120, M0 + 10); cape.closePath();
  let gr = g.createLinearGradient(-400, 0, 400, 0); gr.addColorStop(0, "rgba(20,4,36,.95)"); gr.addColorStop(.5, "rgba(70,20,120,.95)"); gr.addColorStop(1, "rgba(20,4,36,.95)");
  g.fillStyle = gr; g.fill(cape); g.strokeStyle = rgba(MAG, .35); g.lineWidth = 1.5; g.stroke(cape);
  // the high collar: blades fanning up behind the head
  for (let i = 0; i < 9; i++) { const k = i / 8 - .5, a = -Math.PI / 2 + k * 1.9, L = 210 - Math.abs(k) * 90, bx = k * 60, by = M0 + 20;
    const ex = bx + Math.cos(a) * L, ey = by + Math.sin(a) * L, nx = -Math.sin(a) * 16, ny = Math.cos(a) * 16;
    g.fillStyle = i % 2 ? "#3a1262" : "#24083e"; g.beginPath(); g.moveTo(bx + nx, by + ny); g.lineTo(ex, ey); g.lineTo(bx - nx, by - ny); g.closePath(); g.fill();
    g.strokeStyle = rgba(GOLD, .55); g.lineWidth = 1.2; g.stroke(); }
  g.fillStyle = "#2a0b4a"; g.beginPath(); g.moveTo(-30, HEADY + 50); g.lineTo(-44, M0 + 20); g.lineTo(44, M0 + 20); g.lineTo(30, HEADY + 50); g.closePath(); g.fill();
  for (let y = HEADY + 70; y < M0 + 10; y += 18) { g.strokeStyle = rgba(VI, .6); g.lineWidth = 1.4; g.beginPath(); g.moveTo(-34, y); g.quadraticCurveTo(0, y + 6, 34, y); g.stroke(); }
  // the robe: one long flowing body that breaks into three tiers of scalloped hems at the bottom
  const robe = new Path2D();
  robe.moveTo(-96, M0); robe.bezierCurveTo(-200, M0 + 200, -250 + sway * .5, M0 + 470, -330 + sway, HEM + 6);
  robe.lineTo(330 + sway, HEM + 6); robe.bezierCurveTo(250 + sway * .5, M0 + 470, 200, M0 + 200, 96, M0); robe.closePath();
  gr = g.createLinearGradient(-330, 0, 330, 0); gr.addColorStop(0, "#1a0730"); gr.addColorStop(.3, "#3b1468"); gr.addColorStop(.5, "#52208a"); gr.addColorStop(.7, "#3b1468"); gr.addColorStop(1, "#1a0730");
  g.fillStyle = gr; g.fill(robe); g.strokeStyle = rgba(VI, .6); g.lineWidth = 2; g.stroke(robe);
  g.save(); g.clip(robe);
  for (let i = -5; i <= 5; i++) { const sw = Math.sin(t * .8 + i) * 6; g.strokeStyle = "rgba(10,0,20,.3)"; g.lineWidth = 9; g.beginPath(); g.moveTo(i * 18, M0 + 60); g.quadraticCurveTo(i * 40 + sw, M0 + 380, i * 64 + sway, HEM + 10); g.stroke(); }
  [[M0 + 320, .62], [M0 + 490, .8], [M0 + 640, .97]].forEach(([y, wk], n) => {
    const w = 330 * wk, sc = 7 + n, cv = (x) => y + 22 * (1 - Math.min(1, (x / w) ** 2)), X = (j) => -w + (2 * w) * (j / sc) + sway * .7;
    const band = new Path2D(); band.moveTo(-w - 20 + sway * .6, cv(0) - 70); band.quadraticCurveTo(sway * .6, cv(0) - 40, w + 20 + sway * .6, cv(0) - 70); band.lineTo(X(sc), cv(w));
    for (let j = sc; j > 0; j--) band.quadraticCurveTo((X(j) + X(j - 1)) / 2, cv((X(j) + X(j - 1)) / 2) + 40, X(j - 1), cv(X(j - 1)));
    band.closePath();
    const bg = g.createLinearGradient(0, y - 70, 0, y + 50); bg.addColorStop(0, "rgba(60,18,104,0)"); bg.addColorStop(.5, n % 2 ? "rgba(96,36,156,.85)" : "rgba(70,22,120,.85)"); bg.addColorStop(1, "rgba(40,10,70,.9)");
    g.fillStyle = bg; g.fill(band);
    g.strokeStyle = rgba(GOLD, .8); g.lineWidth = 2; g.beginPath(); g.moveTo(X(0), cv(X(0)));
    for (let j = 1; j <= sc; j++) g.quadraticCurveTo((X(j) + X(j - 1)) / 2, cv((X(j) + X(j - 1)) / 2) + 40, X(j), cv(X(j))); g.stroke();
    for (let j = 0; j < sc; j++) { const x = (X(j) + X(j + 1)) / 2; glow(x, cv(x) + 26, 12 + v * 10, MAG, .35 + .3 * v); g.fillStyle = rgba(GOLD, .9); g.beginPath(); g.arc(x, cv(x) + 30, 2.5, 0, TAU); g.fill(); }
  });
  g.restore();
  // the panel down the middle with glyph rings that light up as it talks
  const pnl = new Path2D(); pnl.moveTo(-58, M0 + 70); pnl.lineTo(-90, HEM - 20); pnl.quadraticCurveTo(0, HEM + 20, 90, HEM - 20); pnl.lineTo(58, M0 + 70); pnl.closePath();
  gr = g.createLinearGradient(0, M0, 0, HEM); gr.addColorStop(0, "rgba(244,232,255,.9)"); gr.addColorStop(.5, "rgba(190,150,255,.6)"); gr.addColorStop(1, "rgba(120,60,220,.3)");
  g.fillStyle = gr; g.fill(pnl); g.strokeStyle = rgba(GOLD, .6); g.lineWidth = 1.5; g.stroke(pnl);
  for (let y = M0 + 150, j = 0; y < HEM - 60; y += 70, j++) { const wave = Math.max(0, Math.sin(t * 4 - j * .7)) * (v + th * .6);
    ell(0, y, 16, 16, 0, DEEP, .8, 2); ell(0, y, 7, 7, 0, MAG, .5 + wave, 2); if (wave > .05) glow(0, y, 34, MAG, wave * .6); }
  // shoulders: three stacked plates each side
  [-1, 1].forEach((d) => { for (let i = 2; i >= 0; i--) { const y = M0 + 6 + i * 26, w = 150 - i * 18;
    g.fillStyle = i % 2 ? "#3a1262" : "#4e1d86"; g.beginPath(); g.moveTo(d * 40, y - 14); g.quadraticCurveTo(d * (w + 10), y - 24, d * (w + 30), y + 30); g.quadraticCurveTo(d * (w - 10), y + 10, d * 40, y + 20); g.closePath(); g.fill();
    g.strokeStyle = rgba(i ? VI : GOLD, .8); g.lineWidth = 1.6; g.stroke(); } });
  // the core: a diamond held in two rings
  const cy = M0 + 70, cp = .6 + .4 * Math.sin(t * 3) * (.3 + v);
  glow(0, cy, 70 + 60 * v, MAG, .5 + .3 * v); ell(0, cy, 44, 44, t * .8, LIL, .6, 1.4); ell(0, cy, 32, 12, -t * 1.6, VI, .8, 1.6);
  g.fillStyle = rgba(LIL, .9 * cp + .1); g.beginPath(); g.moveTo(0, cy - 26); g.lineTo(14, cy); g.lineTo(0, cy + 26); g.lineTo(-14, cy); g.closePath(); g.fill();
  // crown: thin plumes rising off the head, gold-tipped
  for (let i = 0; i < 11; i++) { const k = i / 10 - .5, a = -Math.PI / 2 + k * 1.5 + Math.sin(t * 1.3 + i) * .03, L = 150 - Math.abs(k) * 120 + v * 20, bx = Math.sin(k * 2) * 40, by = HEADY - 56;
    const ex = bx + Math.cos(a) * L, ey = by + Math.sin(a) * L; g.strokeStyle = rgba(i % 2 ? VI : MAG, .9); g.lineWidth = 4 - Math.abs(k) * 3; g.beginPath(); g.moveTo(bx, by); g.lineTo(ex, ey); g.stroke(); glow(ex, ey, 8, GOLD, .9); }
  // the head: his smooth face of light, crossed by her dark band with one slit eye
  gr = g.createRadialGradient(-14, HEADY - 20, 6, 0, HEADY, 80); gr.addColorStop(0, "#fbf6ff"); gr.addColorStop(.6, "#c9a8ff"); gr.addColorStop(1, "#6d3cc2");
  g.fillStyle = gr; g.beginPath(); g.ellipse(0, HEADY, 52, 72, 0, 0, TAU); g.fill(); g.strokeStyle = rgba(GOLD, .7); g.lineWidth = 2; g.stroke();
  g.fillStyle = "rgba(24,6,44,.92)"; g.beginPath(); g.moveTo(-56, HEADY - 18); g.quadraticCurveTo(0, HEADY - 30, 56, HEADY - 18); g.lineTo(52, HEADY + 8); g.quadraticCurveTo(0, HEADY - 2, -52, HEADY + 8); g.closePath(); g.fill();
  const sl = 1.2 + 3 * li + 3 * v + (ap > 0 ? 3 * Math.sin(seg(ap, 0, .3) * Math.PI) : 0);
  glow(0, HEADY - 9, 40 + 30 * v, MAG, .55 + .3 * v); g.fillStyle = "#fff0fb"; g.beginPath(); g.ellipse(0, HEADY - 9, 34, sl, 0, 0, TAU); g.fill();
  g.strokeStyle = rgba(GOLD, .85); g.lineWidth = 1.6;
  [-1, 1].forEach((d) => { g.beginPath(); g.moveTo(d * 8, HEADY - 34); g.quadraticCurveTo(d * 30, HEADY - 56, d * 50, HEADY - 30); g.stroke();
    g.beginPath(); g.moveTo(d * 20, HEADY + 18); g.quadraticCurveTo(d * 34, HEADY + 30, d * 28, HEADY + 50); g.stroke();
    g.fillStyle = rgba(MAG, .7); g.beginPath(); g.moveTo(d * 36, HEADY + 14); g.lineTo(d * 40, HEADY + 30); g.lineTo(d * 32, HEADY + 22); g.closePath(); g.fill(); });
  g.beginPath(); g.moveTo(0, HEADY + 30); g.lineTo(0, HEADY + 66); g.stroke(); g.fillStyle = rgba(GOLD, .9); g.beginPath(); g.moveTo(0, HEADY - 42); g.lineTo(5, HEADY - 34); g.lineTo(0, HEADY - 26); g.lineTo(-5, HEADY - 34); g.closePath(); g.fill();
  // the right hand holds the staff; it lifts and flares when it opens something
  const SX = 230, SH = M0 + 360; let tilt = 0, slift = 0, flare = 0;
  if (ap >= 0) { const up = easeInOut(seg(ap, 0, .2)), dn = easeInOut(seg(ap, .78, 1)); tilt = .22 * (up - dn); slift = -50 * (up - dn); flare = Math.sin(seg(ap, .1, .35) * Math.PI); }
  g.save(); g.translate(SX, SH); g.rotate(tilt); g.translate(-SX, -SH - slift);
  const top = HEADY - 150 + Math.sin(t * .9) * 4;
  gr = g.createLinearGradient(0, top, 0, HEM); gr.addColorStop(0, rgba(LIL, .95)); gr.addColorStop(1, rgba(VI, .3));
  g.strokeStyle = gr; g.lineWidth = 6; g.beginPath(); g.moveTo(SX, top + 40); g.lineTo(SX, HEM - 10); g.stroke();
  for (let y = top + 110; y < HEM - 40; y += 90) { g.fillStyle = rgba(GOLD, .8); g.fillRect(SX - 7, y, 14, 4); }
  // the head of the staff: a sharp crescent cradling a star
  g.save(); g.translate(SX, top + 20); g.rotate(Math.sin(t * .5) * .05);
  g.fillStyle = rgba(VI, .95); g.beginPath(); g.arc(0, 0, 46, Math.PI * .15, Math.PI * .85, true); g.arc(0, -14, 38, Math.PI * .8, Math.PI * .2, false); g.closePath(); g.fill(); g.strokeStyle = rgba(GOLD, .9); g.lineWidth = 1.5; g.stroke();
  glow(0, -16, 60 + 40 * v + 160 * flare, LIL, .7 + .3 * flare);
  g.fillStyle = "#fff"; g.beginPath(); for (let i = 0; i < 8; i++) { const r = i % 2 ? 6 : 20 + 4 * v, a = i / 8 * TAU + t * .4; g.lineTo(Math.cos(a) * r, -16 + Math.sin(a) * r); } g.closePath(); g.fill();
  if (flare > 0) ell(0, -16, 80 * flare + 30, 80 * flare + 30, 0, MAG, .7 * flare, 2);
  g.restore(); g.restore();
  // sleeves, then hands: the right one wrapped round the staff, the left a gilt claw holding a small orb of light
  [-1, 1].forEach((d) => { const hx = d > 0 ? SX : -170, hy = d > 0 ? SH + slift : M0 + 250 + breath * 6;
    const sg2 = g.createLinearGradient(d * 70, M0, hx, hy); sg2.addColorStop(0, "#3d1470"); sg2.addColorStop(1, "#1e0638"); g.fillStyle = sg2;
    g.beginPath(); g.moveTo(d * 150, M0 + 20); g.quadraticCurveTo(d * 250, M0 + 150, hx + d * 50, hy + 40); g.quadraticCurveTo(hx, hy + 90, hx - d * 46, hy + 30); g.quadraticCurveTo(d * 110, M0 + 170, d * 60, M0 + 60); g.closePath(); g.fill();
    g.strokeStyle = rgba(VI, .55); g.lineWidth = 1.5; g.stroke(); });
  g.save(); g.translate(SX, SH + slift);
  g.fillStyle = "#24083e"; g.beginPath(); g.ellipse(-6, 0, 20, 26, 0, 0, TAU); g.fill(); g.strokeStyle = rgba(GOLD, .8); g.lineWidth = 1.4; g.stroke();
  for (let i = 0; i < 4; i++) { const y = -16 + i * 11; g.fillStyle = rgba(GOLD, .95); g.beginPath(); g.moveTo(-8, y); g.quadraticCurveTo(16, y - 6, 18, y + 4); g.lineTo(10, y + 3); g.quadraticCurveTo(4, y + 2, -8, y + 6); g.closePath(); g.fill(); }
  g.restore();
  const ohx = -170, ohy = M0 + 250 + breath * 6;
  g.save(); g.translate(ohx, ohy);
  g.scale(1.6, 1.6);
  for (let i = 0; i < 4; i++) { const a = -Math.PI / 2 + (i - 1.5) * .42 + Math.sin(t * 1.5 + i) * .04; g.save(); g.rotate(a); g.fillStyle = rgba(GOLD, .95); g.beginPath(); g.moveTo(-5, 0); g.quadraticCurveTo(-3, -30, 2, -48 + Math.abs(i - 1.5) * 6); g.lineTo(5, 0); g.closePath(); g.fill(); g.restore(); }
  g.fillStyle = "#24083e"; g.beginPath(); g.ellipse(0, 6, 20, 14, 0, 0, TAU); g.fill(); g.strokeStyle = rgba(GOLD, .8); g.lineWidth = 1; g.stroke(); g.scale(1 / 1.6, 1 / 1.6);
  const ob = 20 + 4 * Math.sin(t * 2) + 10 * v; glow(0, -60, ob * 3.4, MAG, .65); g.fillStyle = rgba(LIL, .95); g.beginPath(); g.arc(0, -60, ob * .55, 0, TAU); g.fill();
  ell(0, -60, ob, ob * .35, t * 2, VI, .85, 1.6); ell(0, -60, ob * .9, ob * .3, -t * 1.4 + 1, MAG, .6, 1.2);
  g.restore();
  // falling motes off the hem
  M_FALL.forEach((f) => { const q = (f.y0 + t * f.sp) % 1, y = HEM - 30 + Math.pow(q, 1.6) * 170, a = (1 - q) * f.a; g.fillStyle = rgba(f.c, a); g.fillRect(f.x + Math.sin(t + f.y0 * 9) * 4, y, f.s, f.s); });
}

