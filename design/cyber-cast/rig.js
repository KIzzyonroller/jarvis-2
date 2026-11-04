// ============================================================================ the shared 2D rig
// World units: feet on the ground at (0, 0), up is negative y. A character is about 500 units tall.
// draw(g, t, pose, look) paints one character; the pose says where the limbs are and what the face is doing.
"use strict";
const TAU = Math.PI * 2;
const lerp = (a, b, t) => a + (b - a) * t, clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const smooth = (x) => x * x * (3 - 2 * x);
let g = null;                                   // the 2D context being drawn into (set by the scene)
function useCtx(ctx) { g = ctx; }

function fs(path, fill, line, lw) {             // fill, then outline
  if (fill) { g.fillStyle = fill; g.fill(path); }
  if (line) { g.strokeStyle = line; g.lineWidth = lw || 2.2; g.lineJoin = "round"; g.lineCap = "round"; g.stroke(path); }
}
function fsUnion(paths, fill, line, lw) {      // several shapes as one: outline round the outside only
  if (line) { g.strokeStyle = line; g.lineWidth = (lw || 2.2) * 2; g.lineJoin = "round"; paths.forEach((p) => g.stroke(p)); }
  g.fillStyle = fill; paths.forEach((p) => g.fill(p));
}
function lin(x0, y0, x1, y1, stops) { const gr = g.createLinearGradient(x0, y0, x1, y1); stops.forEach(([o, c]) => gr.addColorStop(o, c)); return gr; }
function rad(x, y, r, stops) { const gr = g.createRadialGradient(x, y, 0, x, y, r); stops.forEach(([o, c]) => gr.addColorStop(o, c)); return gr; }
function glow(x, y, r, c, a) {
  if (r <= 0 || a <= 0) return;
  g.save(); g.globalCompositeOperation = "lighter";
  g.fillStyle = rad(x, y, r, [[0, `rgba(${c},${a})`], [1, `rgba(${c},0)`]]); g.beginPath(); g.arc(x, y, r, 0, TAU); g.fill(); g.restore();
}
function capsule(ax, ay, bx, by, w0, w1) {      // a tapered limb with round ends
  const a = Math.atan2(by - ay, bx - ax), p = new Path2D();
  p.arc(bx, by, w1, a - Math.PI / 2, a + Math.PI / 2);
  p.arc(ax, ay, w0, a + Math.PI / 2, a + Math.PI * 1.5);
  p.closePath();
  return p;
}
// a pointed hair strand / feather / blade: root (with width), tip, bend sideways
function strand(rx, ry, tx, ty, w, bend) {
  const mx = (rx + tx) / 2, my = (ry + ty) / 2, dx = tx - rx, dy = ty - ry, L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L, ny = dx / L, p = new Path2D();
  p.moveTo(rx - nx * w, ry - ny * w);
  p.quadraticCurveTo(mx + nx * (bend - w * .6), my + ny * (bend - w * .6), tx, ty);
  p.quadraticCurveTo(mx + nx * (bend + w * .6), my + ny * (bend + w * .6), rx + nx * w, ry + ny * w);
  p.closePath();
  return p;
}
// forward kinematics for an arm or leg. side: -1 = screen left, +1 = screen right.
// a1: angle at the root from straight down (positive swings outward / up), a2: bend at the middle joint.
function chain(sx, sy, side, a1, a2, L1, L2) {
  const e = [sx + side * Math.sin(a1) * L1, sy + Math.cos(a1) * L1], a = a1 + a2;
  const w = [e[0] + side * Math.sin(a) * L2, e[1] + Math.cos(a) * L2];
  return { s: [sx, sy], e, w, a, dir: Math.atan2(w[1] - e[1], w[0] - e[0]) };
}

// ============================================================================ poses
const BASE = {
  bob: 0, lean: 0, turn: 0, tilt: 0, nod: 0,
  aL: [.14, -.08], aR: [.14, -.08],            // arms: [shoulder, elbow]
  fL: 0, fR: 0, stepL: 0, stepR: 0,            // feet: lift (0..1), step sideways
  blink: 0, open: 1, happy: 0, lookX: 0, lookY: 0, brow: 0, angry: 0,
  mo: 0, mw: .3, mr: 0, smile: .3, skew: 0, blush: .25,
  handL: "open", handR: "open", sway: 0, hairWind: 0, fx: 0, sleep: 0, star: 0, blades: 0,
};
const NUMERIC = Object.keys(BASE).filter((k) => typeof BASE[k] === "number");

function blendPose(cur, target, k) {
  for (const key of NUMERIC) cur[key] += ((target[key] ?? BASE[key]) - cur[key]) * k;
  for (const key of ["aL", "aR"]) {
    const tv = target[key] || BASE[key];
    cur[key][0] += (tv[0] - cur[key][0]) * k; cur[key][1] += (tv[1] - cur[key][1]) * k;
  }
  cur.handL = target.handL || BASE.handL; cur.handR = target.handR || BASE.handR;
}
function newPose() { const p = JSON.parse(JSON.stringify(BASE)); return p; }

// ============================================================================ the face
// Head-local units: head centre (0, 0), the face is about 62 wide; eyes on y = 2, mouth on y = 26.
function drawFace(C, P, t) {
  const L = C.line, turn = P.turn, dx = turn * 7;
  // face shape
  const face = new Path2D();
  face.moveTo(-31 + dx * .2, -14);
  const jw = C.jaw || 0;
  face.bezierCurveTo(-32 + dx * .3, 8, -26 - jw * 3 + dx * .5, 26 + jw * 2, -10 - jw * 4 + dx * .8, 37);
  face.quadraticCurveTo(0 + dx, 43 - jw, 10 + jw * 4 + dx * .8, 37);
  face.bezierCurveTo(26 + jw * 3 + dx * .5, 26 + jw * 2, 32 + dx * .3, 8, 31 + dx * .2, -14);
  face.bezierCurveTo(30, -44, -30, -44, -31 + dx * .2, -14);
  fs(face, lin(0, -40, 0, 42, [[0, C.skin], [1, C.skin2 || C.skin]]), L, 1.9);
  g.save(); g.clip(face);
  // soft shading on the far cheek, and the shadow the bangs throw on the forehead
  g.fillStyle = lin(-40 + dx, 0, 40 + dx, 0, [[0, C.shade + "00"], [turn > 0 ? 0 : 1, C.shade + "55"], [turn > 0 ? 1 : 0, C.shade + "00"]]);
  g.fillRect(-40, -50, 80, 100);
  if (C.bangsPaths) { g.save(); g.translate(1, 6); g.fillStyle = C.shade + "99"; C.bangsPaths(t, P).forEach((p) => g.fill(p)); g.restore(); }
  g.restore();
  // blush
  const bl = P.blush + P.happy * .25;
  if (bl > .02) [-1, 1].forEach((s) => { g.fillStyle = rad(s * 18 + dx, 17, 10, [[0, `rgba(255,120,150,${bl * .7})`], [1, "rgba(255,120,150,0)"]]); g.beginPath(); g.ellipse(s * 18 + dx, 17, 10, 6, 0, 0, TAU); g.fill(); });
  // eyes
  [-1, 1].forEach((s) => drawEye(C, P, s, s * 14.5 + dx * (s === Math.sign(turn) ? 1.1 : .8), 4, t));
  // brows
  [-1, 1].forEach((s) => {
    const x = s * 14.5 + dx, y = -13 - P.brow * 4 - P.open * 1.5 + (P.happy > .5 ? -2 : 0);
    const inner = y + P.angry * 4 - P.brow * 1.5, outer = y - P.angry * 1.5;
    g.strokeStyle = C.brow || L; g.lineWidth = 2.6; g.lineCap = "round"; g.beginPath();
    g.moveTo(x - s * 7, inner); g.quadraticCurveTo(x, Math.min(inner, outer) - 3, x + s * 9, outer + 1.5); g.stroke();
  });
  // nose: a tiny tick and a shine
  g.strokeStyle = C.shade; g.lineWidth = 1.6; g.beginPath(); g.moveTo(dx * 1.2 + 1, 12); g.lineTo(dx * 1.2 - 1, 16); g.stroke();
  // mouth
  drawMouth(C, P, dx * 1.05, 26);
  if (C.faceExtra) C.faceExtra(t, P, dx);
}

function drawEye(C, P, s, cx, cy, t) {
  const L = C.line, iris = (C.eyes && C.eyes[s < 0 ? 0 : 1]) || C.eye;
  const happy = P.happy, shut = Math.max(P.blink, P.sleep);
  if (happy > .55 || shut > .85) {                   // ^ ^ or closed
    g.strokeStyle = L; g.lineWidth = 2.8; g.lineCap = "round"; g.beginPath();
    if (happy > .55 && shut < .85) { g.moveTo(cx - 9, cy + 3); g.quadraticCurveTo(cx, cy - 8, cx + 9, cy + 3); }
    else { g.moveTo(cx - 9, cy); g.quadraticCurveTo(cx, cy + 5, cx + 9, cy); g.moveTo(cx + s * 9, cy); g.lineTo(cx + s * 12, cy - 2); }
    g.stroke();
    return;
  }
  const open = clamp(P.open * (1 - shut) * (1 - happy * .6), .12, 1.35);
  const h = 13.5 * open * (C.eyeH || 1), top = cy + 6 - h * 1.55, bot = cy + 8;
  const ew = 11.2 * (C.eyeW || 1);
  // the white of the eye
  const white = new Path2D();
  white.moveTo(cx - s * ew, cy + 3);
  white.bezierCurveTo(cx - s * ew, top + 2, cx + s * ew * .6, top - 1, cx + s * (ew + 1.5), top + 4);
  white.bezierCurveTo(cx + s * (ew + 1), cy + 4, cx + s * 5, bot + 1, cx, bot);
  white.bezierCurveTo(cx - s * 5, bot + 1, cx - s * ew, cy + 6, cx - s * ew, cy + 3);
  fs(white, "#fffaf8", null);
  g.save(); g.clip(white);
  // iris
  const ix = cx + P.lookX * 3.2, iy = cy + 2.5 + P.lookY * 2.2, ir = 7.8 * (C.irisR || 1);
  g.fillStyle = lin(ix, iy - ir * 1.2, ix, iy + ir * 1.2, [[0, iris[2] || iris[1]], [.45, iris[1]], [1, iris[0]]]);
  g.beginPath(); g.ellipse(ix, iy, ir * .92, ir * 1.15, 0, 0, TAU); g.fill();
  g.strokeStyle = iris[2] || L; g.lineWidth = 1.2; g.stroke();
  // pupil (round or a slit)
  g.fillStyle = iris[3] || "#170615";
  g.beginPath();
  if (C.slit) g.ellipse(ix, iy + .5, 1.5, ir * .95, 0, 0, TAU); else g.ellipse(ix, iy + .8, ir * .42, ir * .55, 0, 0, TAU);
  g.fill();
  // a ring of light, then the highlights
  g.strokeStyle = "rgba(255,255,255,.28)"; g.lineWidth = 1; g.beginPath(); g.ellipse(ix, iy + 1, ir * .65, ir * .82, 0, .3, Math.PI - .3); g.stroke();
  g.fillStyle = "#fff";
  if (C.starEye) { star(ix - 2.5, iy - 3.5, 3.2 + P.star * 1.5, 1.2, t * .5); } else { g.beginPath(); g.ellipse(ix - 2.6, iy - 3.6, 2.4, 2.8, -.4, 0, TAU); g.fill(); }
  g.beginPath(); g.arc(ix + 2.8, iy + 3.4, 1.1, 0, TAU); g.fill();
  // the upper lid's shadow on the eye
  g.fillStyle = lin(0, top, 0, top + 6, [[0, "rgba(60,20,60,.35)"], [1, "rgba(60,20,60,0)"]]); g.fillRect(cx - 14, top - 2, 28, 8);
  g.restore();
  // lashes: a thick upper line with a flick at the outer corner, a light lower line
  // the upper lash line: thin at the inner corner, heavy towards the outer corner, with a flick
  g.strokeStyle = L; g.lineCap = "round"; g.lineJoin = "round";
  const lash = (w, from) => {
    g.lineWidth = w; g.beginPath();
    const p0 = [cx - s * (ew - 1), cy + 1], c1 = [cx - s * ew * .8, top + 1], c2 = [cx + s * ew * .6, top - 2], p1 = [cx + s * (ew + 2), top + 4];
    const B = (u) => [0, 1].map((k) => (1 - u) ** 3 * p0[k] + 3 * (1 - u) ** 2 * u * c1[k] + 3 * (1 - u) * u * u * c2[k] + u ** 3 * p1[k]);
    for (let i = 0; i <= 12; i++) { const u = from + (1 - from) * i / 12, q = B(u); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }
    g.lineTo(cx + s * (ew + 5.5), top + 1); g.stroke();
  };
  lash(1.4, 0); lash(3, .3);
  if (C.lashes) { g.lineWidth = 1.6; g.beginPath(); g.moveTo(cx + s * (ew + 1), top + 4.5); g.lineTo(cx + s * (ew + 6), top + 6); g.moveTo(cx + s * ew * .4, top); g.lineTo(cx + s * ew * .55, top - 3.5); g.stroke(); }
  g.lineWidth = 1.2; g.strokeStyle = C.shade; g.beginPath(); g.moveTo(cx + s * 2, bot + .5); g.quadraticCurveTo(cx + s * 7, bot, cx + s * (ew + .5), cy + 5); g.stroke();
  // the crease above
  g.strokeStyle = C.shade; g.lineWidth = 1.1; g.beginPath(); g.moveTo(cx - s * 4, top - 3.5); g.quadraticCurveTo(cx + s * 4, top - 5.5, cx + s * 10, top - 1); g.stroke();
}

function star(x, y, r, inner, rot) {
  g.beginPath();
  for (let i = 0; i < 8; i++) { const a = rot + i * Math.PI / 4, rr = i % 2 ? inner : r; g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
  g.closePath(); g.fill();
}

function drawMouth(C, P, x, y) {
  const L = C.line, o = P.mo;
  if (o < .06) {                                         // closed: a smile line (with a smirk to one side)
    const sm = P.smile, sk = P.skew;
    g.strokeStyle = L; g.lineWidth = 2; g.lineCap = "round"; g.beginPath();
    g.moveTo(x - 6 - sm * 1.5, y - sm * 1.5 + sk * 1.5); g.quadraticCurveTo(x + sk * 2, y + sm * 4.5, x + 6 + sm * 1.5, y - sm * 1.5 - sk * 2.5); g.stroke();
    if (sm > .55) { g.lineWidth = 1.2; g.beginPath(); g.moveTo(x + 7 + sm, y - sm * 2 - sk * 2); g.lineTo(x + 8.5 + sm, y - sm * 2 - 1.5 - sk * 2); g.stroke(); }
    return;
  }
  const w = 4 + P.mw * 5 + P.smile * 2 - P.mr * 2.5, h = 2 + o * 9 + P.mr * 2;
  const m = new Path2D();
  m.moveTo(x - w, y - P.smile * 1.5);
  m.bezierCurveTo(x - w * .6, y - h * .35 - P.smile, x + w * .6, y - h * .35 - P.smile, x + w, y - P.smile * 1.5);
  m.bezierCurveTo(x + w * .8, y + h, x - w * .8, y + h, x - w, y - P.smile * 1.5);
  fs(m, "#5c1424", L, 1.8);
  g.save(); g.clip(m);
  g.fillStyle = "#ff8a9a"; g.beginPath(); g.ellipse(x, y + h * .9, w * .75, h * .5, 0, 0, TAU); g.fill();
  if (o > .25 && P.mw > .25) { g.fillStyle = "#fff"; g.fillRect(x - w * .7, y - h * .45 - P.smile, w * 1.4, 2.4); }
  g.restore();
}

// ============================================================================ hands
// at the wrist (x, y), pointing along angle a. kind: open, fist, point, claw, grip
function drawHand(C, x, y, a, side, kind, size) {
  const S = size || 1;
  g.save(); g.translate(x, y); g.rotate(a - Math.PI / 2); g.scale(side * S, S);
  const fill = C.glove || C.skin, L = C.line;
  const palm = new Path2D(); palm.ellipse(0, 9, 8.5, 10, 0, 0, TAU);
  const fingers = [];
  if (kind === "fist") { fingers.push(capsule(-6, 14, 6, 15, 4.5, 4.5)); }
  else {
    const spread = kind === "open" ? .16 : kind === "claw" ? .24 : .08, len = kind === "claw" ? 15 : 13;
    for (let i = 0; i < 4; i++) {
      const fx = -5.5 + i * 3.7, ang = (i - 1.5) * spread, l = len - Math.abs(i - 1.5) * 1.8 - (kind === "point" && i !== 0 ? 7 : 0);
      fingers.push(capsule(fx, 14, fx + Math.sin(ang) * l, 14 + Math.cos(ang) * l, 2.2, 1.9));
    }
  }
  const thumb = capsule(-7, 7, -13, 15, 2.6, 2.2);
  fs(thumb, fill, L, 1.5);
  fs(palm, fill, L, 1.5);
  fingers.forEach((f) => fs(f, fill, L, 1.4));
  if (C.claws && kind !== "fist") {                      // gilt claw tips
    g.fillStyle = C.claws;
    for (let i = 0; i < 4; i++) {
      const spread = kind === "open" ? .16 : kind === "claw" ? .24 : .08, len = kind === "claw" ? 15 : 13;
      const fx = -5.5 + i * 3.7, ang = (i - 1.5) * spread, l = len - Math.abs(i - 1.5) * 1.8 - (kind === "point" && i !== 0 ? 7 : 0);
      const tx = fx + Math.sin(ang) * l, ty = 14 + Math.cos(ang) * l;
      g.beginPath(); g.moveTo(tx - 2, ty - 1); g.lineTo(tx + Math.sin(ang) * 6, ty + Math.cos(ang) * 6); g.lineTo(tx + 2, ty - 1); g.closePath(); g.fill();
    }
  }
  g.restore();
}

// ============================================================================ the whole body
// C: the character (sizes, colours and its own drawing hooks). P: the pose.
function drawCharacter(C, P, t) {
  const hipY = -C.legLen - 12 + P.bob;
  const lean = P.lean, sway = P.sway;
  const side = (s) => s;                                             // readability
  g.save();
  g.scale(1 - Math.abs(P.turn) * .08, 1);
  // things behind everything (capes, back hair, wings, halo)
  const upper = (fn) => { g.save(); g.translate(0, hipY); g.rotate(lean); fn(); g.restore(); };
  const headAt = () => { g.translate(0, -C.neckLen - C.torsoLen); g.rotate(P.tilt); g.translate(P.turn * 3, -C.headUp + P.nod); };
  if (C.ground) C.ground(t, P);
  upper(() => { if (C.behind) C.behind(t, P); g.save(); headAt(); if (C.hairBack) C.hairBack(t, P); g.restore(); });
  // legs
  const legs = [-1, 1].map((s) => {
    const lift = s < 0 ? P.fL : P.fR, step = s < 0 ? P.stepL : P.stepR;
    const hx = s * C.hipW, hy = hipY, ax = s * (C.hipW + 1) + step * 14, ay = -12 - lift * 26;
    const d = Math.hypot(ax - hx, ay - hy), L1 = C.legLen * .51, L2 = C.legLen * .49;
    const k = Math.sqrt(Math.max(0, L1 * L1 - (d / 2) ** 2)) * .25;            // a slight outward knee
    const kx = (hx + ax) / 2 + s * k + lift * s * 6, ky = (hy + ay) / 2 - lift * 8;
    return { s, hx, hy, kx, ky, ax, ay, lift };
  });
  legs.forEach((l) => C.leg(l, t, P));
  // body and skirt (in the upper-body frame)
  upper(() => {
    C.torso(t, P);
    if (C.skirt) C.skirt(t, P);
  });
  // arms, then the head on top
  upper(() => {
    const sy = -C.torsoLen + 4;
    const arms = [-1, 1].map((s) => {
      const a = s < 0 ? P.aL : P.aR;
      return chain(s * C.shoulderW, sy, s, a[0], a[1], C.arm[0], C.arm[1]);
    });
    C._arms = arms;
    const order = arms.map((a, i) => ({ a, i, front: a.w[1] < sy + 40 && Math.abs(a.w[0]) < C.shoulderW * 1.2 }))
      .sort((x, y) => (x.front ? 1 : 0) - (y.front ? 1 : 0));
    order.forEach(({ a, i }) => C.armDraw(a, i ? 1 : -1, t, P, i ? P.handR : P.handL));
    g.save(); headAt();
    C._headMatrix = g.getTransform();
    (C.faceFn || drawFace)(C, P, t);
    if (C.hairFront) C.hairFront(t, P);
    g.restore();
    if (C.front) C.front(t, P);
  });
  g.restore();
}
