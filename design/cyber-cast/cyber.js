// ============================================================================ the cyber cast
// Synthetic beings, cyberpunk-styled: chrome shells with hard specular bands, neon seams, a glass visor where
// a face would be (the eyes and mouth are light, so every expression is still there), techwear and cables.
//   Jarvis  light: white chrome, cyan neon, gold seams, two swords of hard light.
//   Ultron  shadow: black chrome cracked with crimson, smoke coming off her, two swords of shadow.
//   Juno    the one made of both: violet, a crown of rings, fibre-optic hair, shards of light and shadow orbiting her.
"use strict";

// ---------------------------------------------------------------- shared pieces
function chrome(x0, y0, x1, y1, c) {             // a metal fill with a hard bright band, the cyberpunk sheen
  return lin(x0, y0, x1, y1, [[0, c[2]], [.38, c[1]], [.46, c[0]], [.5, c[1]], [.82, c[2]], [1, c[3] || c[2]]]);
}
function neon(path, rgb, w, a) {                  // a glowing line: wide soft pass, then the bright core
  g.save(); g.lineCap = "round"; g.lineJoin = "round"; g.globalCompositeOperation = "lighter";
  g.strokeStyle = `rgba(${rgb},${.18 * (a ?? 1)})`; g.lineWidth = w * 4; g.stroke(path);
  g.strokeStyle = `rgba(${rgb},${.55 * (a ?? 1)})`; g.lineWidth = w * 1.8; g.stroke(path);
  g.strokeStyle = `rgba(255,255,255,${.85 * (a ?? 1)})`; g.lineWidth = w * .6; g.stroke(path);
  g.restore();
}
function line(pts) { const p = new Path2D(); pts.forEach(([x, y], i) => (i ? p.lineTo(x, y) : p.moveTo(x, y))); return p; }
function curve(x0, y0, cx, cy, x1, y1) { const p = new Path2D(); p.moveTo(x0, y0); p.quadraticCurveTo(cx, cy, x1, y1); return p; }

// a sword: hilt at (x, y), pointing along angle a. kind "light" or "shadow".
function blade(x, y, a, len, kind, t, power) {
  const k = power ?? 1;
  g.save(); g.translate(x, y); g.rotate(a);
  // grip and guard
  fs(capsule(-16, 0, 6, 0, 3, 3), kind === "light" ? "#e9f3f8" : "#14060a", kind === "light" ? "#0f2431" : "#000", 1.2);
  const guard = new Path2D(); guard.moveTo(6, -10); guard.lineTo(11, -2); guard.lineTo(11, 2); guard.lineTo(6, 10); guard.lineTo(9, 0); guard.closePath();
  fs(guard, kind === "light" ? "#f3cd7d" : "#3a0a14", kind === "light" ? "#0f2431" : "#000", 1.2);
  const b = new Path2D();
  if (kind === "light") {                          // straight, clean, tapering to a needle point
    b.moveTo(11, -3.2); b.lineTo(len * .86, -2.4); b.lineTo(len, 0); b.lineTo(len * .86, 2.4); b.lineTo(11, 3.2); b.closePath();
    g.save(); g.globalCompositeOperation = "lighter";
    g.fillStyle = `rgba(127,231,255,${.16 * k})`; g.beginPath(); g.ellipse(len / 2, 0, len / 2 + 10, 12, 0, 0, TAU); g.fill();
    g.restore();
    g.fillStyle = lin(0, -3, 0, 3, [[0, "#7fe7ff"], [.5, "#ffffff"], [1, "#7fe7ff"]]); g.fill(b);
    neon(line([[14, 0], [len * .95, 0]]), "127,231,255", 1.2, k);
    for (let i = 1; i < 5; i++) { g.fillStyle = `rgba(15,36,49,${.5})`; g.fillRect(14 + i * len * .16, -.6, 4, 1.2); }
  } else {                                         // black, jagged along one edge, crimson glow at the edge, smoking
    b.moveTo(11, -3.5);
    for (let i = 1; i <= 6; i++) b.lineTo(11 + (len - 11) * i / 7, -3.5 - (i % 2 ? 3 : 0) + i * .2);
    b.lineTo(len, 0); b.lineTo(len * .8, 3); b.lineTo(11, 3.5); b.closePath();
    g.save(); g.globalCompositeOperation = "lighter";
    g.fillStyle = `rgba(255,40,60,${.14 * k})`; g.beginPath(); g.ellipse(len / 2, 0, len / 2 + 10, 12, 0, 0, TAU); g.fill(); g.restore();
    fs(b, lin(0, -6, 0, 4, [[0, "#3a0a14"], [.5, "#050002"], [1, "#1a0308"]]), "#000", 1.2);
    neon(line([[11, 3.4], [len * .8, 3], [len, 0]]), "255,40,60", 1, k);
    for (let i = 0; i < 7; i++) { const q = (t * .6 + i / 7) % 1, x = 15 + (len - 15) * ((i * .37) % 1); g.fillStyle = `rgba(30,0,8,${.5 * (1 - q)})`; g.beginPath(); g.arc(x, -6 - q * 16, 3 + q * 4, 0, TAU); g.fill(); }
  }
  g.restore();
}

// ---------------------------------------------------------------- the face: a chrome shell with a glass visor
function cyberFace(C, P, t) {
  const turn = P.turn, dx = turn * 7, F = C.face;
  const shell = new Path2D();
  shell.moveTo(-31, -16); shell.bezierCurveTo(-33, 8, -24, 28, -9, 38); shell.quadraticCurveTo(0 + dx * .5, 44, 9, 38);
  shell.bezierCurveTo(24, 28, 33, 8, 31, -16); shell.bezierCurveTo(30, -46, -30, -46, -31, -16); shell.closePath();
  fs(shell, chrome(-32 + dx, -40, 32 + dx, 40, F.plate), C.line, 1.8);
  g.save(); g.clip(shell);
  // panel seams and a tiny marking on the cheek
  g.strokeStyle = F.seam; g.lineWidth = 1;
  g.beginPath(); g.moveTo(-30, 18); g.quadraticCurveTo(-18, 30, -6, 40); g.moveTo(30, 18); g.quadraticCurveTo(18, 30, 6, 40); g.stroke();
  g.fillStyle = F.seam; for (let i = 0; i < 5; i++) g.fillRect(18 + dx + i * 2.2, 24, 1.1, 4 - (i % 2) * 1.5);
  // the visor: dark glass across the eyes
  const v = new Path2D(); v.moveTo(-32, -12); v.quadraticCurveTo(0, -18, 32, -12); v.lineTo(31, 12); v.quadraticCurveTo(0, 18, -31, 12); v.closePath();
  g.fillStyle = lin(0, -16, 0, 16, [[0, F.visor[0]], [1, F.visor[1]]]); g.fill(v);
  g.strokeStyle = "rgba(255,255,255,.18)"; g.lineWidth = 1.4; g.beginPath(); g.moveTo(-26, -11); g.quadraticCurveTo(-8, -15, 10, -14); g.stroke();
  for (let y = -12; y < 14; y += 3) { g.fillStyle = "rgba(255,255,255,.03)"; g.fillRect(-32, y, 64, 1); }     // scanlines
  g.restore();
  neon(curve(-31, 12, 0, 18, 31, 12), F.neon, .9, .8);
  // eyes and brows, all light
  const eyeCol = (s) => (C.eyes ? C.eyes[s < 0 ? 0 : 1] : C.eyeRGB);
  [-1, 1].forEach((s) => {
    const cx = s * 14 + dx * 1.05, cy = 1, col = eyeCol(s), ox = P.lookX * 3, oy = P.lookY * 1.8;
    const shut = Math.max(P.blink, P.sleep);
    if (P.happy > .55 && shut < .85) { neon(curve(cx - 8, cy + 4, cx, cy - 6, cx + 8, cy + 4), col, 1.6); }
    else if (shut > .7) { neon(curve(cx - 8, cy + 1, cx, cy + 4, cx + 8, cy + 1), col, 1.3); }
    else {
      const open = clamp(P.open * (1 - shut), .15, 1.4), h = 6.5 * open * (F.eyeH || 1), w = 9 * (F.eyeW || 1);
      const e = new Path2D();
      if (F.sharp) {                                     // narrow, slanted, a cut at the inner corner
        e.moveTo(cx - s * w, cy + h * .4 + P.angry * 2); e.lineTo(cx + s * w * .2, cy - h + P.angry * 1.5); e.lineTo(cx + s * (w + 3), cy - h * .6);
        e.lineTo(cx + s * w * .5, cy + h * .7); e.closePath();
      } else e.ellipse(cx, cy, w, h, s * -.12, 0, TAU);
      g.save(); g.globalCompositeOperation = "lighter";
      g.fillStyle = rad(cx, cy, w * 2.2, [[0, `rgba(${col},.55)`], [1, `rgba(${col},0)`]]); g.beginPath(); g.ellipse(cx, cy, w * 2.2, h * 2.6 + 4, 0, 0, TAU); g.fill();
      g.fillStyle = `rgba(${col},.95)`; g.fill(e);
      g.restore();
      g.save(); g.clip(e);
      g.fillStyle = "rgba(255,255,255,.95)"; g.beginPath(); g.ellipse(cx + ox, cy + oy, w * .38, Math.max(1, h * .5), 0, 0, TAU); g.fill();   // the bright core = where they're looking
      if (F.pupil) { g.fillStyle = F.pupil; g.fillRect(cx + ox - .9, cy + oy - h, 1.8, h * 2); }
      g.restore();
    }
    const by = -9 - P.brow * 3 - (P.happy > .5 ? 1.5 : 0), inner = by + P.angry * 4, outer = by - P.angry * 1.5;
    neon(line([[cx - s * 7, inner], [cx + s * 7, outer]]), col, .7, .7);
  });
  // the mouth: a line of light; when they talk it opens into a little equaliser
  const mx = dx * 1.05, my = 26;
  if (P.mo < .06) {
    const sm = P.smile, sk = P.skew;
    const m = F.jagged ? line([[mx - 8, my - sm * 2 + sk * 2], [mx - 4, my + sm * 2], [mx, my + sm * 1], [mx + 4, my + sm * 2.5 - sk * 2], [mx + 9, my - sm * 3 - sk * 3]])
                       : curve(mx - 7 - sm * 1.5, my - sm * 1.5 + sk * 1.5, mx + sk * 2, my + sm * 5, mx + 7 + sm * 1.5, my - sm * 1.5 - sk * 2.5);
    neon(m, F.mouth, 1, .9);
  } else {
    const w = 8 + P.mw * 4 + P.smile * 2, h = 2 + P.mo * 7;
    const slot = new Path2D(); slot.roundRect(mx - w, my - h / 2 - P.smile, w * 2, h, h / 2);
    fs(slot, "rgba(0,0,0,.85)", null);
    const n = 7;
    for (let i = 0; i < n; i++) {
      const lv = clamp(P.mo * (.45 + .55 * Math.abs(Math.sin(t * 17 + i * 1.7))), 0, 1), bh = Math.max(1, (h - 2) * lv);
      g.fillStyle = `rgba(${F.mouth},.95)`; g.fillRect(mx - w + 2 + i * (w * 2 - 4) / n, my - bh / 2 - P.smile, (w * 2 - 4) / n - 1.2, bh);
    }
    neon(slot, F.mouth, .5, .6);
  }
  // LED blush when they're pleased
  const bl = P.blush + P.happy * .4;
  if (bl > .15) [-1, 1].forEach((s) => { for (let i = 0; i < 3; i++) { g.fillStyle = `rgba(${F.blush},${(bl - .1) * .8})`; g.fillRect(s * 19 + dx - 4 + i * 3, 17 - i * .3, 1.6, 4); } });
  // ear pods
  [-1, 1].forEach((s) => {
    const p = new Path2D(); p.ellipse(s * 32 + dx * .3, 4, 4.5, 9, 0, 0, TAU);
    fs(p, chrome(s * 28, -6, s * 36, 12, F.plate), C.line, 1.3);
    neon(curve(s * 32 + dx * .3, -3, s * 34 + dx * .3, 4, s * 32 + dx * .3, 11), F.neon, .7, .8 + Math.sin(t * 3 + s) * .2);
  });
}

// generic armoured limb: plate, a glowing joint, plate (the gap makes them read as built, not born)
function armLimb(C, a, s, t, P, hand) {
  const B = C.body;
  const upper = capsule(a.s[0], a.s[1], lerp(a.s[0], a.e[0], .9), lerp(a.s[1], a.e[1], .9), B.armW[0], B.armW[1]);
  fs(upper, chrome(a.s[0] - 9, a.s[1], a.s[0] + 9, a.s[1] + 30, B.plate2), C.line, 1.6);
  const fe = capsule(lerp(a.e[0], a.w[0], .1), lerp(a.e[1], a.w[1], .1), a.w[0], a.w[1], B.armW[2], B.armW[3]);
  fs(fe, chrome(a.e[0] - 8, a.e[1], a.e[0] + 8, a.e[1] + 30, B.plate), C.line, 1.6);
  const jp = new Path2D(); jp.arc(a.e[0], a.e[1], B.armW[1] * .85, 0, TAU); fs(jp, "#0a0a12", C.line, 1);
  neon((() => { const p = new Path2D(); p.arc(a.e[0], a.e[1], B.armW[1] * .55, 0, TAU); return p; })(), B.neon, .8);
  const ang = Math.atan2(a.w[1] - a.e[1], a.w[0] - a.e[0]);
  neon(line([[lerp(a.e[0], a.w[0], .3), lerp(a.e[1], a.w[1], .3)], [lerp(a.e[0], a.w[0], .85), lerp(a.e[1], a.w[1], .85)]]), B.neon, .7, .8);
  drawHand(C, a.w[0], a.w[1], ang, s, hand, 1);
  return ang;
}
// generic legs that taper to a point and hover over a ring of light
function hoverLeg(C, l, t, P) {
  const B = C.body;
  fs(capsule(l.hx, l.hy, lerp(l.hx, l.kx, .92), lerp(l.hy, l.ky, .92), B.legW[0], B.legW[1]), chrome(l.hx - 13, l.hy, l.hx + 13, l.hy + 40, B.plate2), C.line, 1.8);
  const shin = new Path2D(); shin.moveTo(l.kx - B.legW[1], l.ky); shin.quadraticCurveTo(l.kx - B.legW[1] * 1.1, lerp(l.ky, l.ay, .5), l.ax - 2, l.ay + 6);
  shin.lineTo(l.ax, l.ay + 16); shin.lineTo(l.ax + 2, l.ay + 6); shin.quadraticCurveTo(l.kx + B.legW[1] * 1.1, lerp(l.ky, l.ay, .5), l.kx + B.legW[1], l.ky); shin.closePath();
  fs(shin, chrome(l.kx - 12, l.ky, l.kx + 12, l.ky + 40, B.plate), C.line, 1.8);
  const kn = new Path2D(); kn.ellipse(l.kx, l.ky, B.legW[1] * .9, B.legW[1] * 1.1, 0, 0, TAU); fs(kn, chrome(l.kx - 9, l.ky - 9, l.kx + 9, l.ky + 9, B.plate2), C.line, 1.3);
  neon(line([[l.kx, l.ky + 14], [lerp(l.kx, l.ax, .75), lerp(l.ky, l.ay, .75)]]), B.neon, .8, .9);
}
function hoverRing(C, t, P) {
  const B = C.body, gy = 4, pulse = .6 + .4 * Math.sin(t * 3);
  g.save(); g.globalCompositeOperation = "lighter";
  g.fillStyle = rad(0, gy, 70, [[0, `rgba(${B.neon},${.25 * pulse})`], [1, `rgba(${B.neon},0)`]]); g.beginPath(); g.ellipse(0, gy, 70, 12, 0, 0, TAU); g.fill();
  g.restore();
  neon((() => { const p = new Path2D(); p.ellipse(0, gy, 40 + pulse * 6, 6, 0, 0, TAU); return p; })(), B.neon, .8, .7);
}
// a torso shell: chest plate, segmented waist, hip plate, neon seams
function torsoShell(C, t, P, w) {
  const B = C.body, top = -C.torsoLen, W = w || { sh: 34, ch: 32, wa: 22, hip: 30 };
  fs(capsule(0, top - 2, 0, top - 30, 7.5, 7), "#14141c", C.line, 1.6);           // neck: a dark sleeve with cables
  g.strokeStyle = B.cable; g.lineWidth = 2; [-1, 1].forEach((s) => { g.beginPath(); g.moveTo(s * 4, top - 28); g.quadraticCurveTo(s * 7, top - 14, s * 9, top); g.stroke(); });
  const chest = new Path2D();
  chest.moveTo(-W.sh * .45, top - 4); chest.quadraticCurveTo(-W.sh, top, -W.sh - 2, top + 10); chest.quadraticCurveTo(-W.ch - 2, top + 50, -W.wa - 4, top + 72);
  chest.lineTo(W.wa + 4, top + 72); chest.quadraticCurveTo(W.ch + 2, top + 50, W.sh + 2, top + 10); chest.quadraticCurveTo(W.sh, top, W.sh * .45, top - 4); chest.closePath();
  fs(chest, chrome(-W.sh, top, W.sh, top + 70, B.plate), C.line, 1.8);
  // the waist: stacked bands with dark gaps
  for (let i = 0; i < 4; i++) {
    const y = top + 76 + i * 13, ww = W.wa + (i > 2 ? 4 : 0);
    const band = new Path2D(); band.roundRect(-ww, y, ww * 2, 10, 3);
    fs(band, chrome(-ww, y, ww, y + 10, B.plate2), C.line, 1.3);
  }
  const hip = new Path2D(); hip.moveTo(-W.wa - 4, -18); hip.lineTo(W.wa + 4, -18); hip.quadraticCurveTo(W.hip + 4, -2, W.hip, 16); hip.quadraticCurveTo(0, 26, -W.hip, 16); hip.quadraticCurveTo(-W.hip - 4, -2, -W.wa - 4, -18); hip.closePath();
  fs(hip, chrome(-W.hip, -18, W.hip, 20, B.plate), C.line, 1.8);
  // seams in neon
  neon(curve(-W.sh + 6, top + 14, 0, top + 30, W.sh - 6, top + 14), B.neon, .8, .75);
  neon(line([[0, top + 34], [0, top + 70]]), B.neon, .8, .6 + .3 * Math.sin(t * 2.6));
  // collar plates
  [-1, 1].forEach((s) => { const c = new Path2D(); c.moveTo(s * 6, top - 2); c.lineTo(s * 12, top - 22); c.quadraticCurveTo(s * 20, top - 16, s * 22, top + 2); c.closePath(); fs(c, chrome(s * 6, top - 22, s * 22, top, B.plate2), C.line, 1.3); });
}
function pauldron(C, s, top, size) {
  const B = C.body, k = size || 1, p = new Path2D();
  p.moveTo(s * 18, top - 4); p.quadraticCurveTo(s * 44 * k, top - 12, s * 54 * k, top + 12); p.quadraticCurveTo(s * 46 * k, top + 24, s * 30, top + 18); p.closePath();
  fs(p, chrome(s * 18, top - 10, s * 54, top + 20, B.plate), C.line, 1.6);
  neon(curve(s * 24, top + 14, s * 42 * k, top + 18, s * 52 * k, top + 10), B.neon, .8, .8);
}

// ================================================================ JARVIS: light
const JA = {
  name: "jarvis", faceFn: cyberFace, line: "#0b1a24",
  shoulderW: 44, hipW: 15, arm: [70, 64], legLen: 224, torsoLen: 158, neckLen: 22, headUp: 38,
  glove: "#e8f2f6", claws: null, eyeRGB: "127,231,255",
  face: { plate: ["#ffffff", "#e3eef3", "#a8bfca", "#7f98a6"], seam: "rgba(30,60,80,.35)", visor: ["rgba(8,30,44,.95)", "rgba(4,16,26,.98)"], neon: "127,231,255", mouth: "127,231,255", blush: "255,214,140", eyeW: 1, eyeH: .85 },
  body: { plate: ["#ffffff", "#e6f0f4", "#a9c0cb", "#8aa3b0"], plate2: ["#7d8c97", "#36424c", "#161c22"], neon: "127,231,255", cable: "#3b6a80", armW: [10, 8.5, 8.5, 7], legW: [13, 10] },
};
JA.swords = (P) => P.fx > .3 || P.blades > .3;
JA.ground = (t, P) => hoverRing(JA, t, P);
JA.behind = function (t, P) {
  const B = JA.body, top = -JA.torsoLen;
  // a coat of long hard-light plates hanging from the back, edges in neon
  for (let i = -2; i <= 2; i++) {
    const sw = Math.sin(t * 1.2 + i) * 3 + P.sway * 14, x = i * 15, L = 170 - Math.abs(i) * 18;
    const p = new Path2D(); p.moveTo(x - 9, -60); p.lineTo(x + 9, -60); p.lineTo(x + 10 + i * 4 + sw, -60 + L); p.lineTo(x + i * 4 + sw, -60 + L + 12); p.lineTo(x - 10 + i * 4 + sw, -60 + L); p.closePath();
    fs(p, lin(0, -60, 0, -60 + L, [[0, "rgba(220,240,248,.95)"], [1, "rgba(127,231,255,.25)"]]), JA.line, 1.2);
    neon(line([[x + i * 4 + sw, -60 + L + 12], [x + 10 + i * 4 + sw, -60 + L]]), B.neon, .6, .7);
  }
  // the two swords of light, crossed on his back while he isn't holding them
  if (!JA.swords(P)) { blade(-50, top - 30, Math.PI * .28, 150, "light", t, .7); blade(50, top - 30, Math.PI * .72, 150, "light", t, .7); }
};
JA.hairBack = function (t, P) {
  // instead of hair: swept-back fins of chrome with light running along them, and a crest
  [-1, 1].forEach((s) => {
    for (let i = 2; i >= 0; i--) {
      const sw = Math.sin(t * 1.1 + i + s) * .8, rx = s * (22 + i * 5), ry = -40 + i * 12, tx = s * (54 + i * 8) + sw, ty = -58 + i * 18;
      fs(strand(rx, ry, tx, ty, 6 - i, s * 4), chrome(rx, ry - 10, tx, ty + 10, JA.face.plate), JA.line, 1.2);
      neon(curve(rx, ry, lerp(rx, tx, .5), lerp(ry, ty, .5) - 3, tx, ty), "127,231,255", .5, .7);
    }
  });
  const crest = strand(0, -44, 1, -62, 4, 1); fs(crest, chrome(-6, -62, 6, -44, ["#f3d38c", "#d6ad5a", "#8a6526"]), JA.line, 1.1);
};
JA.leg = (l, t, P) => hoverLeg(JA, l, t, P);
JA.torso = function (t, P) {
  const top = -JA.torsoLen;
  torsoShell(JA, t, P, { sh: 40, ch: 36, wa: 26, hip: 32 });
  // the core: a ring of light in the chest
  const pulse = .6 + .4 * Math.sin(t * 2.4);
  neon((() => { const p = new Path2D(); p.arc(0, top + 44, 8, 0, TAU); return p; })(), "127,231,255", 1.2, .7 + P.mo * .3);
  glow(0, top + 44, 20 + P.mo * 12, "127,231,255", .25 * pulse);
  g.fillStyle = "#ffffff"; star(0, top + 44, 4, 1.4, t * .5);
  [-1, 1].forEach((s) => pauldron(JA, s, top, 1));
};
JA.skirt = function (t, P) {                      // front plates hanging from the hips, like a split coat
  const B = JA.body;
  [-1, 1].forEach((s) => {
    const sw = Math.sin(t * 1.3 + s) * 2 + P.sway * 10, p = new Path2D();
    p.moveTo(s * 10, 10); p.lineTo(s * 32, 4); p.lineTo(s * (40 + sw * .3), 100); p.lineTo(s * (24 + sw * .3), 112); p.closePath();
    fs(p, chrome(s * 10, 0, s * 40, 110, B.plate), JA.line, 1.6);
    neon(line([[s * 14, 14], [s * (26 + sw * .3), 106]]), B.neon, .7, .8);
  });
};
JA.armDraw = function (a, s, t, P, hand) {
  const ang = armLimb(JA, a, s, t, P, JA.swords(P) ? "fist" : hand);
  if (JA.swords(P)) blade(a.w[0], a.w[1], ang + s * (P.blades > .3 ? (a.a > 1.5 ? .25 : -.75) : .6), 150, "light", t, 1);
};
JA.hairFront = function (t, P) {                   // a thin circlet across the brow
  neon(curve(-30, -22, 0, -34, 30, -22), "243,205,125", .8, .8);
};

// ================================================================ ULTRON: shadow
const UL = {
  name: "ultron", faceFn: cyberFace, line: "#000000",
  shoulderW: 36, hipW: 12, arm: [64, 58], legLen: 214, torsoLen: 148, neckLen: 22, headUp: 38,
  glove: "#0c0306", claws: "#ff3046", eyeRGB: "255,40,60",
  face: { plate: ["#5a5262", "#26212c", "#0d0a10", "#050307"], seam: "rgba(255,40,60,.35)", visor: ["rgba(20,0,6,.95)", "rgba(6,0,2,.98)"], neon: "255,40,60", mouth: "255,60,70", blush: "255,40,60", sharp: true, jagged: true, eyeH: .8, pupil: "rgba(60,0,10,.9)" },
  body: { plate: ["#6a6070", "#2a2430", "#0e0b12", "#060408"], plate2: ["#4a1018", "#22060c", "#0a0204"], neon: "255,40,60", cable: "#5a0a14", armW: [8.5, 7, 7, 5.5], legW: [12, 9] },
};
UL.swords = (P) => P.fx > .3 || P.blades > .3;
UL.ground = function (t, P) {                      // a pool of shadow instead of a ring of light
  g.save(); g.fillStyle = rad(0, 4, 90, [[0, "rgba(0,0,0,.65)"], [1, "rgba(0,0,0,0)"]]); g.beginPath(); g.ellipse(0, 4, 90, 14, 0, 0, TAU); g.fill(); g.restore();
  neon((() => { const p = new Path2D(); p.ellipse(0, 4, 46, 6, 0, 0, TAU); return p; })(), "255,40,60", .6, .5 + .3 * Math.sin(t * 4));
};
UL.behind = function (t, P) {
  const top = -UL.torsoLen;
  // a cape of smoke: ragged, always moving, edges dissolving
  const p = new Path2D(); p.moveTo(-30, top + 6); p.lineTo(30, top + 6);
  for (let i = 0; i <= 10; i++) { const x = 30 + i * 6 + Math.sin(t * 1.5 + i) * 6 + P.sway * 18; p.lineTo(x * (1 - i * .02), top + 6 + i * 34 + Math.sin(t * 2 + i) * 4); }
  for (let i = 10; i >= 0; i--) { const x = -30 - i * 6 + Math.sin(t * 1.4 + i * 1.3) * 6 + P.sway * 18; p.lineTo(x * (1 - i * .02), top + 6 + i * 34 + (i === 10 ? 0 : 0)); }
  p.closePath();
  g.fillStyle = lin(0, top, 0, top + 360, [[0, "rgba(10,2,6,.95)"], [.7, "rgba(20,2,8,.7)"], [1, "rgba(20,2,8,0)"]]); g.fill(p);
  for (let i = 0; i < 22; i++) { const q = (t * .25 + i * .121) % 1, x = Math.sin(i * 4.7) * 60 + Math.sin(t + i) * 10, y = top + 20 + q * 330, r = 10 + q * 18; g.fillStyle = rad(x, y, r, [[0, `rgba(20,0,6,${.4 * (1 - q)})`], [1, "rgba(20,0,6,0)"]]); g.beginPath(); g.arc(x, y, r, 0, TAU); g.fill(); }
  if (!UL.swords(P)) { blade(-46, top - 26, Math.PI * .3, 140, "shadow", t, .7); blade(46, top - 26, Math.PI * .7, 140, "shadow", t, .7); }
};
UL.hairBack = function (t, P) {
  // a crown of horns, and shadow rising off her head like smoke
  for (let i = 0; i < 5; i++) {
    const k = i / 4 - .5, rx = k * 40, ry = -38 + Math.abs(k) * 6, tx = k * 80, ty = -96 + Math.abs(k) * 40;
    fs(strand(rx, ry, tx, ty, 5.5, k * 18), chrome(rx - 6, ty, rx + 6, ry, UL.face.plate), "#000", 1.2);
    neon(curve(rx, ry, lerp(rx, tx, .5) + k * 10, lerp(ry, ty, .5), tx, ty), "255,40,60", .45, .8);
  }
  for (let i = 0; i < 12; i++) { const q = (t * .4 + i * .083) % 1, x = Math.sin(i * 3.3) * 30 + Math.sin(t * 2 + i) * 6, y = -40 - q * 90, r = 6 + q * 14; g.fillStyle = rad(x, y, r, [[0, `rgba(30,0,8,${.45 * (1 - q)})`], [1, "rgba(30,0,8,0)"]]); g.beginPath(); g.arc(x, y, r, 0, TAU); g.fill(); }
  // a hood of black chrome blades round the back of the head
  const hood = new Path2D(); hood.moveTo(-38, 10); hood.bezierCurveTo(-46, -60, 46, -60, 38, 10); hood.lineTo(30, 46); hood.lineTo(22, 30); hood.lineTo(0, 40); hood.lineTo(-22, 30); hood.lineTo(-30, 46); hood.closePath();
  fs(hood, chrome(-40, -50, 40, 40, UL.face.plate), "#000", 1.4);
};
UL.leg = (l, t, P) => hoverLeg(UL, l, t, P);
UL.torso = function (t, P) {
  const top = -UL.torsoLen;
  torsoShell(UL, t, P, { sh: 32, ch: 30, wa: 20, hip: 30 });
  // crimson cracks across the chest, flickering
  const fl = .6 + .4 * Math.abs(Math.sin(t * 7)) * (Math.sin(t * 1.3) > .7 ? 1 : .4);
  neon(line([[-18, top + 22], [-8, top + 34], [-12, top + 46], [0, top + 58]]), "255,40,60", .8, fl);
  neon(line([[14, top + 18], [6, top + 30], [12, top + 40]]), "255,40,60", .7, fl);
  // the core: a cracked red diamond
  const d = new Path2D(); d.moveTo(0, top + 30); d.lineTo(6, top + 42); d.lineTo(0, top + 54); d.lineTo(-6, top + 42); d.closePath();
  fs(d, "#300008", "#000", 1.2); neon(d, "255,40,60", .8, .7 + P.mo * .3);
  [-1, 1].forEach((s) => { pauldron(UL, s, top, .9); for (let i = 0; i < 3; i++) fs(strand(s * (40 + i * 4), top + 2 + i * 6, s * (58 + i * 6), top - 14 + i * 4, 3, 0), "#0e0b12", "#000", 1); });
};
UL.skirt = function (t, P) {                      // long ragged tassets of shadow-metal
  [-1, 1].forEach((s) => {
    for (let i = 0; i < 3; i++) {
      const sw = Math.sin(t * 1.3 + i + s) * 3 + P.sway * 12, x0 = s * (8 + i * 10), L = 120 - i * 18;
      const p = new Path2D(); p.moveTo(x0 - 7, 8); p.lineTo(x0 + 7, 8); p.lineTo(x0 + s * 6 + sw + 5, L); p.lineTo(x0 + s * 6 + sw, L + 14); p.lineTo(x0 + s * 6 + sw - 5, L); p.closePath();
      fs(p, chrome(x0 - 8, 0, x0 + 8, L, UL.body.plate), "#000", 1.3);
      if (i === 1) neon(line([[x0, 14], [x0 + s * 6 + sw, L]]), "255,40,60", .5, .6);
    }
  });
};
UL.armDraw = function (a, s, t, P, hand) {
  const ang = armLimb(UL, a, s, t, P, UL.swords(P) ? "fist" : hand);
  if (UL.swords(P)) blade(a.w[0], a.w[1], ang + s * (P.blades > .3 ? (a.a > 1.5 ? .25 : -.8) : .55), 140, "shadow", t, 1);
  for (let i = 0; i < 3; i++) { const q = (t * .5 + i * .33) % 1, x = a.e[0] + Math.sin(t + i) * 4, y = a.e[1] - q * 26, r = 4 + q * 7; g.fillStyle = rad(x, y, r, [[0, `rgba(30,0,8,${.4 * (1 - q)})`], [1, "rgba(30,0,8,0)"]]); g.beginPath(); g.arc(x, y, r, 0, TAU); g.fill(); }
};

// ================================================================ JUNO: the one made of both
const JU = {
  name: "juno", faceFn: cyberFace, line: "#1a0b2c",
  shoulderW: 36, hipW: 12, arm: [62, 56], legLen: 214, torsoLen: 148, neckLen: 20, headUp: 38,
  glove: "#2a1450", claws: "#ffd27a", eyes: ["127,231,255", "255,63,108"],
  face: { plate: ["#ffffff", "#ece4fb", "#b9a6dc", "#8c76b8"], seam: "rgba(90,40,160,.35)", visor: ["rgba(26,10,52,.95)", "rgba(12,4,28,.98)"], neon: "190,140,255", mouth: "255,140,230", blush: "255,92,214", eyeW: 1.05, eyeH: 1 },
  body: { plate: ["#ffffff", "#ece4fb", "#b39fe0", "#7c62b8"], plate2: ["#c7a4ff", "#7a4ce0", "#3a1a80"], neon: "190,140,255", cable: "#7a4ce0", armW: [8.5, 7, 7, 5.5], legW: [12, 9] },
};
JU.ground = (t, P) => hoverRing(JU, t, P);
JU.shards = function (t, P, front) {             // shards of light and shadow circling her waist
  const n = 8, R = 70 + P.fx * 30;
  for (let i = 0; i < n; i++) {
    const a = t * .8 + i * TAU / n, z = Math.sin(a);
    if ((z > 0) !== front) continue;
    const x = Math.cos(a) * R, y = -JU.legLen * .62 + Math.sin(a) * 14 - P.fx * 25 + Math.sin(t * 2 + i) * 4, s = 1 + z * .25;
    const light = i % 2 === 0;
    g.save(); g.translate(x, y); g.rotate(a * 1.5); g.scale(s, s);
    const d = new Path2D(); d.moveTo(0, -9); d.lineTo(4, 0); d.lineTo(0, 9); d.lineTo(-4, 0); d.closePath();
    fs(d, light ? "#ffffff" : "#120308", light ? "#7fe7ff" : "#ff3046", 1);
    glow(0, 0, 14, light ? "127,231,255" : "255,40,60", .45);
    g.restore();
  }
};
JU.behind = function (t, P) {
  const top = -JU.torsoLen;
  // wings made of thin translucent panels, opening and closing slowly
  [-1, 1].forEach((s) => {
    for (let i = 0; i < 4; i++) {
      const a = -Math.PI / 2 + s * (.45 + i * .26) + s * Math.sin(t * .9) * .05 * (1 + P.fx), L = 150 - i * 12;
      const rx = s * 14, ry = top + 20, tx = rx + Math.cos(a) * L, ty = ry + Math.sin(a) * L;
      fs(strand(rx, ry, tx, ty, 9, s * 12), lin(rx, ry, tx, ty, [[0, "rgba(122,76,224,.55)"], [1, "rgba(255,92,214,.12)"]]), "rgba(26,11,44,.5)", 1);
      neon(curve(rx, ry, lerp(rx, tx, .5) + s * 8, lerp(ry, ty, .5), tx, ty), i % 2 ? "190,140,255" : "255,140,230", .4, .7);
    }
  });
  JU.shards(t, P, false);
};
JU.hairBack = function (t, P) {
  // a crown of rings at two angles, turning against each other
  [[-.25, 46, 11, 1], [.3, 38, 9, -1]].forEach(([tilt, rx, ry, dir]) => {
    g.save(); g.translate(0, -62); g.rotate(tilt);
    neon((() => { const p = new Path2D(); p.ellipse(0, 0, rx, ry, 0, 0, TAU); return p; })(), dir > 0 ? "255,210,122" : "190,140,255", .7, .9);
    for (let i = 0; i < 6; i++) { const a = t * .6 * dir + i * TAU / 6; g.fillStyle = "#fff"; g.beginPath(); g.arc(Math.cos(a) * rx, Math.sin(a) * ry, 1.4, 0, TAU); g.fill(); }
    g.restore();
  });
  // fibre-optic hair: long strands of light falling from the back of her head to her knees
  for (let i = 0; i < 26; i++) {
    const k = i / 25 - .5, rx = k * 64, ry = -30 + Math.abs(k) * 20, L = 250 + Math.sin(i * 2.3) * 40;
    const sw = Math.sin(t * 1.2 + i * .5) * (6 + P.hairWind * 14) + P.sway * 30 - P.lean * 120;
    const tx = k * 120 + sw, ty = ry + L, p = new Path2D();
    p.moveTo(rx, ry); p.bezierCurveTo(rx * 1.4, ry + L * .3, tx - sw * .5, ty - L * .3, tx, ty);
    g.strokeStyle = lin(0, ry, 0, ty, [[0, "rgba(199,164,255,.95)"], [.6, "rgba(122,76,224,.85)"], [1, "rgba(255,92,214,.9)"]]); g.lineWidth = 3.4 - Math.abs(k) * 2; g.lineCap = "round"; g.stroke(p);
    glow(tx, ty, 6, "255,140,230", .5 + .3 * Math.sin(t * 3 + i));
  }
  // the shell at the back of the head the strands come out of
  const sh = new Path2D(); sh.moveTo(-36, 6); sh.bezierCurveTo(-44, -60, 44, -60, 36, 6); sh.quadraticCurveTo(0, 20, -36, 6); sh.closePath();
  fs(sh, chrome(-40, -50, 40, 10, JU.body.plate2), JU.line, 1.4);
};
JU.leg = (l, t, P) => hoverLeg(JU, l, t, P);
JU.torso = function (t, P) {
  const top = -JU.torsoLen;
  torsoShell(JU, t, P, { sh: 32, ch: 31, wa: 20, hip: 30 });
  const cy = top + 40, pulse = .6 + .4 * Math.sin(t * 3);
  glow(0, cy, 24 + P.mo * 12, "255,92,214", .35 + .2 * pulse);
  const d = new Path2D(); d.moveTo(0, cy - 9); d.lineTo(6, cy); d.lineTo(0, cy + 9); d.lineTo(-6, cy); d.closePath();
  fs(d, lin(0, cy - 9, 0, cy + 9, [[0, "#ffffff"], [.5, "#ff9ae8"], [1, "#7a4ce0"]]), JU.line, 1.2);
  neon((() => { const p = new Path2D(); p.arc(0, cy, 12, Math.PI * 1.1, Math.PI * 1.9); return p; })(), "127,231,255", .7, .8);
  neon((() => { const p = new Path2D(); p.arc(0, cy, 12, Math.PI * .1, Math.PI * .9); return p; })(), "255,40,60", .7, .8);
  [-1, 1].forEach((s) => pauldron(JU, s, top, .85));
};
JU.skirt = function (t, P) {                      // a skirt of light panels, cyan on one side, crimson on the other, violet between
  for (let i = -3; i <= 3; i++) {
    const sw = Math.sin(t * 1.4 + i) * 2.5 + P.sway * 10, x0 = i * 9, L = 60 + (3 - Math.abs(i)) * 8;
    const p = new Path2D(); p.moveTo(x0 - 6, 8); p.lineTo(x0 + 6, 8); p.lineTo(x0 + i * 4 + sw + 6, L); p.lineTo(x0 + i * 4 + sw, L + 8); p.lineTo(x0 + i * 4 + sw - 6, L); p.closePath();
    const col = i < -1 ? "127,231,255" : i > 1 ? "255,63,108" : "190,140,255";
    fs(p, lin(0, 8, 0, L, [[0, "rgba(236,228,251,.95)"], [1, `rgba(${col},.35)`]]), JU.line, 1.1);
    neon(line([[x0 + i * 4 + sw - 6, L], [x0 + i * 4 + sw, L + 8], [x0 + i * 4 + sw + 6, L]]), col, .5, .8);
  }
};
JU.armDraw = function (a, s, t, P, hand) { armLimb(JU, a, s, t, P, hand); };
JU.hairFront = function (t, P) {
  // two strands that fall in front, past the shoulders
  [-1, 1].forEach((s) => {
    const sw = Math.sin(t * 1.3 + s) * (2 + P.hairWind * 6) + P.sway * 10 - P.turn * 4, p = new Path2D();
    p.moveTo(s * 32, -10); p.bezierCurveTo(s * 40, 30, s * 36 + sw * .5, 80, s * 40 + sw, 120);
    g.strokeStyle = "rgba(199,164,255,.95)"; g.lineWidth = 3; g.lineCap = "round"; g.stroke(p);
    glow(s * 40 + sw, 120, 7, "255,140,230", .6);
  });
  neon(curve(-30, -22, 0, -36, 30, -22), "255,210,122", .7, .8);
  g.fillStyle = "#fff"; star(0, -33, 4, 1.4, t * .6); glow(0, -33, 10, "255,230,170", .4);
};
JU.front = function (t, P) { JU.shards(t, P, true); };
