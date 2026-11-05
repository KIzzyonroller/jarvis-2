// Jarvis, Juno and Ultron, take 3. Pure SVG built from code, so every part can be moved and animated later.
"use strict";
const P = (pts) => "M" + pts.map((p) => p.join(" ")).join(" L") + " Z";
const PL = (pts) => "M" + pts.map((p) => p.join(" ")).join(" L");
const mx = (pts) => pts.map(([x, y]) => [-x, y]);
const el = (tag, a, inner = "") => `<${tag} ${Object.entries(a).map(([k, v]) => `${k}="${v}"`).join(" ")}>${inner}</${tag}>`;
const path = (d, a = {}) => el("path", Object.assign({ d }, a));
// draw a left-half shape and its mirror
const pair = (pts, a) => path(P(pts), a) + path(P(mx(pts)), a);
const O = (id) => `<g id="${id}">`, C = "</g>";
const pairD = (d, a) => path(d, a) + el("g", { transform: "scale(-1,1)" }, path(d, a));

function defs() {
  return `<defs>
  <filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="bigglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="smoke" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".018" numOctaves="3" seed="4"/><feDisplacementMap in="SourceGraphic" scale="40"/><feGaussianBlur stdDeviation="4"/></filter>
  <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="2" result="n"/><feColorMatrix in="n" type="saturate" values="0"/><feComposite in2="SourceGraphic" operator="in"/><feBlend in="SourceGraphic" mode="multiply"/></filter>
  <!-- Jarvis: pale carved stone -->
  <linearGradient id="jStone" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f7f2e6"/><stop offset=".55" stop-color="#d6ccb6"/><stop offset="1" stop-color="#8e846f"/></linearGradient>
  <linearGradient id="jStoneD" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#cfc5ae"/><stop offset="1" stop-color="#6f6655"/></linearGradient>
  <linearGradient id="jCloth" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b5a78"/><stop offset="1" stop-color="#16263a"/></linearGradient>
  <linearGradient id="jSash" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e9fbff"/><stop offset="1" stop-color="#7fd6ee"/></linearGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff0b8"/><stop offset=".5" stop-color="#e2b955"/><stop offset="1" stop-color="#8a6420"/></linearGradient>
  <linearGradient id="lightBlade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8ff3ff"/><stop offset=".5" stop-color="#ffffff"/><stop offset="1" stop-color="#8ff3ff"/></linearGradient>
  <!-- Ultron: black obsidian -->
  <linearGradient id="uStone" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a4352"/><stop offset=".45" stop-color="#1d1922"/><stop offset="1" stop-color="#08070b"/></linearGradient>
  <linearGradient id="uStoneD" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a2430"/><stop offset="1" stop-color="#050407"/></linearGradient>
  <linearGradient id="uCloth" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5a0d18"/><stop offset="1" stop-color="#1a0307"/></linearGradient>
  <linearGradient id="uSash" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff3550"/><stop offset="1" stop-color="#7a0716"/></linearGradient>
  <linearGradient id="shadowBlade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ff2a45"/><stop offset=".3" stop-color="#16121a"/><stop offset=".7" stop-color="#16121a"/><stop offset="1" stop-color="#ff2a45"/></linearGradient>
  <!-- Juno -->
  <linearGradient id="mane" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#7b2bff"/><stop offset=".5" stop-color="#c13dff"/><stop offset="1" stop-color="#ff5ae0"/></linearGradient>
  <linearGradient id="grid" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b44dff" stop-opacity="0"/><stop offset="1" stop-color="#b44dff" stop-opacity=".55"/></linearGradient>
  <radialGradient id="floorJ"><stop offset="0" stop-color="#8ff3ff" stop-opacity=".35"/><stop offset="1" stop-color="#8ff3ff" stop-opacity="0"/></radialGradient>
  <radialGradient id="uSmoke"><stop offset="0" stop-color="#3a0d1a" stop-opacity=".9"/><stop offset=".6" stop-color="#1a0a12" stop-opacity=".5"/><stop offset="1" stop-color="#1a0a12" stop-opacity="0"/></radialGradient>
  <radialGradient id="floorU"><stop offset="0" stop-color="#ff2a45" stop-opacity=".35"/><stop offset="1" stop-color="#ff2a45" stop-opacity="0"/></radialGradient>
  </defs>`;
}

// ---------------------------------------------------------------- shared warrior parts
function greatsword(c, len, opts = {}) {
  // drawn pointing down, crossguard at y=0, tip at y=len
  const w = opts.w || 15, light = c.light;
  const blade = P([[-w, 0], [w, 0], [w * .8, len - 60], [0, len], [-w * .8, len - 60]]);
  let s = "";
  if (opts.aura) s += path(blade, { fill: c.glow, opacity: .55, filter: "url(#bigglow)" });
  s += path(blade, { fill: opts.bladeFill, stroke: c.line, "stroke-width": 2 });
  s += path(PL([[0, 10], [0, len - 40]]), { stroke: light, "stroke-width": 3, filter: "url(#glow)", fill: "none" }); // fuller of light
  // runes along the fuller
  for (let y = 40; y < len - 80; y += 46) s += path(P([[0, y - 7], [5, y], [0, y + 7], [-5, y]]), { fill: light, filter: "url(#glow)" });
  // crossguard
  const g = opts.guard === "jag"
    ? P([[-72, -6], [-40, -14], [-14, -10], [0, -22], [14, -10], [40, -14], [80, -2], [52, 4], [30, 12], [0, 8], [-30, 12], [-56, 2]])
    : P([[-78, -18], [-46, -8], [-14, -12], [0, -24], [14, -12], [46, -8], [78, -18], [70, 2], [40, 10], [0, 12], [-40, 10], [-70, 2]]);
  s += path(g, { fill: opts.metal, stroke: c.line, "stroke-width": 2 });
  s += el("circle", { cx: 0, cy: -4, r: 7, fill: light, filter: "url(#glow)" });
  // grip and pommel
  s += path(P([[-7, -22], [7, -22], [8, -78], [-8, -78]]), { fill: c.grip, stroke: c.line, "stroke-width": 2 });
  for (let y = -30; y > -76; y -= 9) s += path(PL([[-7, y], [7, y - 6]]), { stroke: c.line, "stroke-width": 1.5 });
  s += path(P([[0, -100], [12, -86], [0, -74], [-12, -86]]), { fill: opts.metal, stroke: c.line, "stroke-width": 2 });
  s += el("circle", { cx: 0, cy: -86, r: 4, fill: light, filter: "url(#glow)" });
  return s;
}

// ---------------------------------------------------------------- JARVIS
function jarvis() {
  const c = { line: "#3d372c", light: "#8ff3ff", glow: "#8ff3ff", grip: "#2d4560" };
  const st = { fill: "url(#jStone)", stroke: c.line, "stroke-width": 2.2, "stroke-linejoin": "round" };
  const etch = { fill: "none", stroke: c.light, "stroke-width": 1.6, filter: "url(#glow)", "stroke-linecap": "round" };
  const goldS = { fill: "url(#gold)", stroke: "#5c4210", "stroke-width": 1.6 };
  let s = "";
  s += el("ellipse", { cx: 0, cy: 2, rx: 210, ry: 26, fill: "url(#floorJ)" });
  s += O("j-halo");
  // light rays behind (halo crown)
  for (let i = 0; i < 13; i++) {
    const a = -Math.PI / 2 + (i - 6) * .2, r0 = 58, r1 = i % 2 ? 108 : 150, cx = 0, cy = -588;
    const p = (r, d) => [cx + Math.cos(a + d) * r, cy + Math.sin(a + d) * r];
    s += path(P([p(r0, -.05), p(r1, 0), p(r0, .05)]), { fill: i % 2 ? "url(#gold)" : "#dffbff", opacity: i % 2 ? .9 : .85, filter: "url(#glow)" });
  }
  s += el("circle", { cx: 0, cy: -588, r: 62, fill: "none", stroke: "url(#gold)", "stroke-width": 3 });
  s += el("circle", { cx: 0, cy: -588, r: 70, fill: "none", stroke: "#8ff3ff", "stroke-width": 1, "stroke-dasharray": "2 7", filter: "url(#glow)" });
  s += C;
  s += O("j-cloak");
  // cloak
  s += path("M -84 -508 C -150 -470 -168 -300 -196 -40 C -150 -22 -120 -38 -86 -24 C -40 -36 -10 -20 30 -30 C 80 -20 120 -36 196 -40 C 168 -300 150 -470 84 -508 Z", { fill: "url(#jCloth)", stroke: "#0d1724", "stroke-width": 2.2 });
  for (const x of [-140, -100, 100, 140]) s += path(`M ${x * .6} -470 Q ${x * .9} -250 ${x} -45`, { fill: "none", stroke: "#0b1420", "stroke-width": 2, opacity: .6 });
  s += path("M -196 -40 C -150 -22 -120 -38 -86 -24 C -40 -36 -10 -20 30 -30 C 80 -20 120 -36 196 -40", { fill: "none", stroke: "url(#gold)", "stroke-width": 4 });
  // cloak: woven sun sigils and a band of gold diamonds along the hem
  for (const [x, y, k] of [[-150, -200, 1], [-128, -360, .8], [150, -210, 1], [128, -370, .8], [-170, -90, .7], [170, -100, .7]]) {
    let g = el("circle", { r: 9, fill: "none", stroke: "url(#gold)", "stroke-width": 1.6 }) + el("circle", { r: 3, fill: "#eaffff", filter: "url(#glow)" });
    for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4; g += path(PL([[Math.cos(a) * 12, Math.sin(a) * 12], [Math.cos(a) * (i % 2 ? 16 : 21), Math.sin(a) * (i % 2 ? 16 : 21)]]), { stroke: "url(#gold)", "stroke-width": 1.4 }); }
    s += el("g", { transform: `translate(${x},${y}) scale(${k})`, opacity: .85 }, g);
  }
  for (let x = -186; x <= 186; x += 17) { const y = -44 + Math.sin(x * .08) * 5; s += path(P([[x, y - 7], [x + 5, y], [x, y + 5], [x - 5, y]]), { fill: "url(#gold)", opacity: .9 }); }
  s += C;
  // legs
  const thigh = [[-74, -312], [-20, -312], [-22, -178], [-64, -176]], shin = [[-64, -160], [-24, -160], [-28, -34], [-58, -34]], boot = [[-64, -36], [-24, -36], [-12, -2], [-80, -2]];
  s += pair(thigh, st) + pair(shin, st) + pair(boot, { ...st, fill: "url(#jStoneD)" });
  s += pair([[-44, -190], [-24, -168], [-44, -140], [-64, -168]], goldS);         // knee
  s += pairD("M -44 -150 L -44 -50 M -54 -120 L -34 -120 M -52 -80 L -36 -80", etch);
  s += pairD("M -30 -32 L -60 -32", { stroke: "url(#gold)", "stroke-width": 3 });
  s += O("j-tabard");
  // long tabard
  s += path(P([[-50, -360], [50, -360], [44, -70], [0, -26], [-44, -70]]), { fill: "url(#jCloth)", stroke: "#0d1724", "stroke-width": 2 });
  s += path(P([[-40, -350], [40, -350], [35, -78], [0, -40], [-35, -78]]), { fill: "none", stroke: "url(#gold)", "stroke-width": 2 });
  for (let y = -320, i = 0; y < -90; y += 36, i++) s += i % 2 ? path(P([[0, y - 12], [10, y], [0, y + 12], [-10, y]]), { fill: "none", ...etch }) : path(PL([[-12, y + 6], [0, y - 6], [12, y + 6]]), etch);
  s += C;
  s += O("j-sword");
  // the sword he stands guard with, point down in front
  s += el("g", { transform: "translate(0,-318)" }, greatsword(c, 300, { bladeFill: "url(#lightBlade)", metal: "url(#gold)", aura: true, w: 17 }));
  s += C;
  // waist and belt
  s += path(P([[-62, -384], [62, -384], [56, -350], [-56, -350]]), goldS);
  s += path(P([[0, -394], [14, -367], [0, -340], [-14, -367]]), { fill: "#eaffff", stroke: "#5c4210", "stroke-width": 1.5, filter: "url(#glow)" });
  // sash, wrapped and blowing to one side
  s += path("M -64 -376 C -20 -396 30 -388 66 -370 L 62 -354 C 30 -368 -20 -374 -60 -358 Z", { fill: "url(#jSash)", stroke: "#3b7f95", "stroke-width": 1.5, opacity: .95 });
  s += O("j-sash");
  s += path("M 58 -366 C 110 -360 150 -320 200 -300 C 240 -286 260 -250 300 -246 C 262 -230 230 -262 190 -270 C 150 -278 120 -320 64 -350 Z", { fill: "url(#jSash)", stroke: "#3b7f95", "stroke-width": 1.5, opacity: .9 });
  s += path("M 60 -356 C 96 -330 120 -280 132 -232 C 140 -200 168 -176 186 -150 C 152 -160 128 -190 118 -226 C 108 -270 84 -318 58 -344 Z", { fill: "url(#jSash)", stroke: "#3b7f95", "stroke-width": 1.5, opacity: .8 });
  s += C;
  s += O("j-chest");
  // breastplate
  const chest = [[0, -512], [-72, -512], [-92, -476], [-84, -426], [-60, -386], [0, -378]];
  s += pair(chest, st);
  s += pairD("M -6 -500 C -40 -500 -66 -486 -76 -458 C -64 -440 -36 -432 -6 -436", { fill: "none", stroke: c.line, "stroke-width": 1.8 });
  s += pairD("M -16 -490 C -40 -488 -56 -478 -64 -460", etch);
  s += pairD("M -10 -420 L -52 -410 M -12 -404 L -48 -396", { stroke: c.line, "stroke-width": 1.5, opacity: .7 });
  s += path(P([[0, -486], [16, -460], [0, -432], [-16, -460]]), { fill: "#eaffff", filter: "url(#bigglow)" });
  s += el("circle", { cx: 0, cy: -460, r: 24, fill: "none", stroke: "url(#gold)", "stroke-width": 3 });
  // arms: upper arms, then forearms reaching in to rest both hands on the pommel
  s += pair([[-86, -500], [-112, -492], [-118, -414], [-94, -410]], st);
  s += pair([[-116, -418], [-94, -410], [-26, -330], [-34, -310], [-48, -312]], st);
  s += pair([[-120, -430], [-92, -424], [-88, -404], [-118, -400]], goldS);       // elbow cop
  s += pairD("M -104 -480 L -106 -432 M -90 -392 L -48 -334", etch);
  s += pair([[-38, -346], [-8, -350], [-6, -320], [-30, -310], [-44, -320]], { ...st, fill: "url(#jStoneD)" }); // gauntlets on the grip
  s += pairD("M -34 -340 L -12 -342 M -34 -330 L -12 -332", { stroke: c.line, "stroke-width": 1.4 });
  s += pairD("M -38 -332 L -34 -320 M -28 -334 L -24 -318 M -18 -336 L -15 -320", { stroke: c.line, "stroke-width": 1.2 });   // knuckles
  s += pairD("M -66 -164 L -22 -164", { stroke: "url(#gold)", "stroke-width": 4 }) + pairD("M -68 -306 L -20 -306", { stroke: "url(#gold)", "stroke-width": 4 });
  s += pairD("M -44 -110 a 7 7 0 1 0 0.1 0", { fill: "none", stroke: "#8ff3ff", "stroke-width": 1.2, filter: "url(#glow)" });
  // pauldrons: three stacked lames each side, sweeping out like folded wings
  for (let i = 2; i >= 0; i--) {
    const dy = i * 20, dx = i * 10;
    const d = `M -66 ${-522 + dy} C -110 ${-552 + dy} -158 ${-540 + dy - dx} ${-176 - dx} ${-500 + dy} C ${-160 - dx} ${-494 + dy} -140 ${-500 + dy} -122 ${-488 + dy} C -104 ${-506 + dy} -84 ${-506 + dy} -66 ${-494 + dy} Z`;
    s += pairD(d, st);
    s += pairD(`M -76 ${-516 + dy} C -112 ${-538 + dy} -146 ${-530 + dy - dx} ${-164 - dx} ${-504 + dy}`, i === 0 ? { fill: "none", stroke: "url(#gold)", "stroke-width": 3 } : etch);
  }
  s += C;
  s += O("j-head");
  // hood draped behind the head
  s += path("M -50 -600 C -64 -560 -70 -530 -86 -506 C -40 -496 40 -496 86 -506 C 70 -530 64 -560 50 -600 C 30 -642 -30 -642 -50 -600 Z", { fill: "url(#jCloth)", stroke: "#0d1724", "stroke-width": 2 });
  s += C;
  // gold gorget at the base of the neck
  s += path("M -40 -512 C -24 -528 24 -528 40 -512 L 34 -500 C 20 -512 -20 -512 -34 -500 Z", { fill: "url(#gold)", stroke: "#5c4210", "stroke-width": 1.5 });
  s += path("M -30 -510 C -14 -520 14 -520 30 -510", { fill: "none", stroke: "#8ff3ff", "stroke-width": 1.2, filter: "url(#glow)" });
  s += O("j-head2");
  // neck and face: a calm carved mask
  s += path(P([[-14, -540], [14, -540], [16, -506], [-16, -506]]), st);
  s += path("M 0 -628 C 24 -628 36 -610 35 -584 C 34 -556 22 -534 0 -528 C -22 -534 -34 -556 -35 -584 C -36 -610 -24 -628 0 -628 Z", st);
  s += path("M 0 -628 C 24 -628 36 -610 35 -584 C 34 -556 22 -534 0 -528 C 10 -548 14 -570 12 -600 C 10 -616 6 -624 0 -628 Z", { fill: "#8e846f", opacity: .35 });  // shade one side of the face
  s += path("M -30 -594 C -16 -600 -6 -598 0 -590 C 6 -598 16 -600 30 -594", { fill: "none", stroke: c.line, "stroke-width": 2 }); // brow
  s += path("M 0 -590 L -4 -560 L 4 -558", { fill: "none", stroke: c.line, "stroke-width": 1.6 });                                    // nose
  s += O("j-eyes");
  s += pairD("M -26 -580 Q -17 -587 -7 -580 Q -17 -575 -26 -580 Z", { fill: c.light, filter: "url(#glow)" });                        // eyes
  s += C;
  s += path("M -9 -545 Q 0 -541 9 -545", { fill: "none", stroke: c.line, "stroke-width": 1.8 });                                     // mouth
  s += pairD("M -28 -568 L -18 -552", { stroke: c.line, "stroke-width": 1.2, opacity: .6 });                                          // cheek plane
  s += path("M -34 -606 C -14 -616 14 -616 34 -606", { fill: "none", stroke: "url(#gold)", "stroke-width": 4 });                       // circlet
  s += path(P([[0, -620], [7, -609], [0, -598], [-7, -609]]), { fill: "#eaffff", filter: "url(#glow)" });
  s += path("M 0 -598 L 0 -592", { stroke: c.light, "stroke-width": 1.4, filter: "url(#glow)" });
  s += C;
  s += O("j-fx") + C;
  return s;
}

// ---------------------------------------------------------------- ULTRON
function crack(pts) { return path(PL(pts), { fill: "none", stroke: "#ff2a45", "stroke-width": 1.8, filter: "url(#glow)", "stroke-linejoin": "miter" }); }
function ultron() {
  const c = { line: "#000", light: "#ff2a45", glow: "#ff2a45", grip: "#2a0a10" };
  const st = { fill: "url(#uStone)", stroke: "#000", "stroke-width": 2.2, "stroke-linejoin": "miter" };
  let s = "";
  s += el("ellipse", { cx: 0, cy: 2, rx: 230, ry: 28, fill: "url(#floorU)" });
  s += O("u-rift");
  s += C;
  s += O("u-smoke");
  // smoke rising off him
  s += el("ellipse", { cx: 0, cy: -300, rx: 230, ry: 330, fill: "url(#uSmoke)", opacity: .9 });
  s += C;
  s += O("u-hisword");
  // the raised sword, held over his left shoulder, blade back behind his head
  s += el("g", { transform: "translate(126,-430) rotate(158)" }, greatsword(c, 430, { bladeFill: "url(#shadowBlade)", metal: "url(#uStone)", guard: "jag", aura: true, w: 16 }));
  s += C;
  s += O("u-cloak");
  // tattered cloak
  s += path("M -88 -506 C -160 -460 -186 -300 -214 -60 L -190 -20 L -176 -64 L -150 -10 L -132 -58 L -104 -6 L -84 -50 L -56 -16 L -36 -60 L -6 -14 L 20 -54 L 48 -10 L 70 -58 L 102 -14 L 120 -64 L 150 -18 L 168 -70 L 202 -34 C 180 -300 150 -460 88 -506 Z", { fill: "url(#uCloth)", stroke: "#000", "stroke-width": 2.2 });
  s += path("M -150 -300 L -132 -280 L -146 -262 Z M 120 -200 L 140 -184 L 126 -168 Z", { fill: "#0b0a0e" });  // holes torn through
  // runes burned into the cloak, faint, and more tears
  const runes = ["M0 -8 L0 8 M-5 -3 L5 3", "M-5 -8 L5 0 L-5 8", "M-5 8 L0 -8 L5 8 M-3 2 L3 2", "M-4 -8 L4 -8 L-4 8 L4 8", "M0 -8 L-5 0 L0 8 L5 0 Z", "M-5 -8 L-5 8 M-5 0 L5 -8 M-5 0 L5 8"];
  [[-160, -380], [-150, -230], [-176, -120], [150, -380], [160, -260], [176, -140], [-120, -150], [118, -130]].forEach(([x, y], i) =>
    s += el("g", { transform: `translate(${x},${y}) rotate(${(i * 37) % 30 - 15})` }, path(runes[i % runes.length], { fill: "none", stroke: "#ff2a45", "stroke-width": 1.6, opacity: .55, filter: "url(#glow)" })));
  s += path("M -180 -150 L -166 -132 L -184 -118 Z M 166 -330 L 180 -316 L 164 -304 Z M -60 -60 L -48 -48 L -62 -38 Z", { fill: "#0b0a0e" });
  s += C;
  // legs, angular, spiked knees
  const thigh = [[-78, -312], [-20, -312], [-26, -180], [-70, -176]], shin = [[-70, -160], [-26, -160], [-30, -30], [-62, -30]], boot = [[-68, -32], [-26, -32], [-8, 0], [-60, -6], [-88, 0]];
  s += pair(thigh, st) + pair(shin, st) + pair(boot, st);
  s += pair([[-48, -200], [-26, -170], [-30, -150], [-48, -136], [-82, -178]], st);  // knee spike
  s += crack([[-60, -150], [-48, -120], [-56, -96], [-40, -60]]) + crack([[56, -300], [44, -250], [52, -214]]);
  // ragged sash and tabard
  s += path(P([[-50, -360], [50, -360], [46, -150], [36, -120], [40, -80], [20, -96], [0, -40], [-16, -100], [-38, -70], [-34, -130], [-46, -160]]), { fill: "url(#uCloth)", stroke: "#000", "stroke-width": 2 });
  s += crack([[0, -340], [-8, -300], [6, -260], [-4, -220], [8, -170], [0, -120]]);
  s += path("M -14 -240 L -6 -226 L -14 -212 M 8 -196 L 16 -184 L 8 -172 M -10 -150 L 0 -140 L 10 -150", { fill: "none", stroke: "#ff2a45", "stroke-width": 1.4, opacity: .7, filter: "url(#glow)" });
  s += O("u-losword");
  // the lowered sword in his right hand, trailing down to the ground
  s += el("g", { transform: "translate(-150,-300) rotate(24)" }, greatsword(c, 330, { bladeFill: "url(#shadowBlade)", metal: "url(#uStone)", guard: "jag", aura: true, w: 16 }));
  s += C;
  // belt
  s += path(P([[-62, -386], [62, -386], [58, -350], [-58, -350]]), st);
  s += path("M -18 -386 L 0 -352 L 18 -386", { fill: "none", stroke: "#ff2a45", "stroke-width": 2.5, filter: "url(#glow)" });
  s += path("M -64 -378 C -20 -392 30 -384 66 -372 L 62 -356 C 30 -366 -20 -372 -60 -360 Z", { fill: "url(#uSash)", stroke: "#000", "stroke-width": 1.5 });
  s += O("u-sash");
  s += path("M -60 -362 C -110 -350 -130 -300 -170 -280 L -150 -262 L -196 -246 L -176 -226 L -214 -214 C -170 -236 -140 -290 -58 -350 Z", { fill: "url(#uSash)", stroke: "#000", "stroke-width": 1.5 });
  s += C;
  s += O("u-chest");
  // breastplate, faceted
  const chest = [[0, -514], [-76, -514], [-96, -470], [-82, -420], [-60, -384], [0, -376]];
  s += pair(chest, st);
  s += pairD("M 0 -504 L -60 -488 L -82 -456 L -40 -436 L 0 -446", { fill: "none", stroke: "#3a3340", "stroke-width": 1.6 });
  s += crack([[0, -500], [-14, -476], [-6, -456], [-30, -440], [-24, -414], [-50, -396]]) + crack([[0, -476], [20, -462], [16, -436], [44, -420]]);
  s += O("u-core");
  s += path(P([[0, -486], [18, -456], [0, -426], [-18, -456]]), { fill: "#ff2a45", filter: "url(#bigglow)" });
  s += path(P([[0, -476], [9, -456], [0, -436], [-9, -456]]), { fill: "#ffd0d6" });
  s += C;
  s += C;
  s += O("u-rarm");
  // right arm (viewer's left) hanging down to the low sword
  s += path(P([[-90, -500], [-120, -490], [-140, -410], [-112, -404]]), st);
  s += path(P([[-138, -414], [-112, -404], [-142, -314], [-166, -322]]), st);
  s += path(P([[-170, -330], [-138, -318], [-136, -290], [-160, -282], [-178, -298]]), st);   // fist
  s += path(P([[-142, -430], [-110, -426], [-104, -400], [-132, -390], [-152, -412]]), st);   // spiked elbow
  s += crack([[-118, -476], [-126, -440], [-120, -420]]);
  s += C;
  s += O("u-larm");
  // left arm raised: hand up by the shoulder gripping the high sword
  s += path(P([[90, -500], [120, -490], [148, -440], [124, -426]]), st);
  s += path(P([[148, -446], [124, -428], [118, -470], [132, -486]]), st);
  s += path(P([[110, -470], [140, -478], [148, -450], [124, -436], [104, -448]]), st);
  s += C;
  // pauldrons: jagged, lopsided, the left one bigger
  s += path("M -64 -522 L -110 -560 L -104 -536 L -150 -566 L -138 -530 L -190 -548 L -164 -508 L -200 -500 L -150 -486 L -120 -498 L -90 -490 L -66 -494 Z", st);
  s += path("M 64 -522 L 100 -580 L 106 -546 L 150 -600 L 148 -548 L 206 -574 L 178 -516 L 222 -508 L 160 -482 L 124 -496 L 92 -488 L 66 -494 Z", st);
  s += crack([[-150, -540], [-130, -520], [-150, -500]]) + crack([[150, -584], [140, -540], [170, -520], [160, -496]]);
  s += O("u-claws");
  // claws on the low hand, rivets on the pauldrons, spikes on the belt
  for (const [dx, dy] of [[-4, 0], [6, 4], [14, 6]]) s += path(P([[-160 + dx, -284 + dy], [-166 + dx * 1.4, -262 + dy], [-152 + dx, -280 + dy]]), { fill: "#2a2430", stroke: "#000", "stroke-width": 1 });
  s += C;
  for (const [x, y] of [[-96, -506], [-126, -500], [-156, -496], [100, -508], [134, -500], [170, -494]]) s += el("circle", { cx: x, cy: y, r: 3, fill: "#5a525f", stroke: "#000", "stroke-width": 1 });
  for (const x of [-48, -24, 24, 48]) s += path(P([[x - 6, -386], [x, -402], [x + 6, -386]]), { fill: "url(#uStone)", stroke: "#000", "stroke-width": 1.2 });
  s += pairD("M -8 -420 L -40 -404 M -10 -404 L -46 -390", { stroke: "#3a3340", "stroke-width": 1.6 });
  s += O("u-head");
  // head: horned crest, snarling mask
  s += path(P([[-14, -542], [14, -542], [16, -508], [-16, -508]]), st);
  const horns = [[-34, -610, -76, -690], [-24, -620, -46, -716], [-8, -628, -10, -730], [10, -628, 22, -722], [26, -620, 58, -704], [36, -606, 92, -662]];
  for (const [x0, y0, x1, y1] of horns) s += path(P([[x0 - 9, y0 + 6], [x1, y1], [x0 + 9, y0 - 4]]), st) + path(PL([[x0, y0], [x1 * .9 + x0 * .1, y1 * .9 + y0 * .1]]), { stroke: "#ff2a45", "stroke-width": 1.2, opacity: .7, filter: "url(#glow)" });
  s += path("M 0 -630 L 30 -620 L 38 -588 L 32 -556 L 14 -532 L 0 -528 L -14 -532 L -32 -556 L -38 -588 L -30 -620 Z", st);
  s += path("M 0 -630 L 30 -620 L 38 -588 L 32 -556 L 14 -532 L 0 -528 L 6 -560 L 4 -600 Z", { fill: "#000", opacity: .35 });
  s += O("u-eyes");
  s += pairD("M -32 -594 L -6 -580 L -8 -574 L -30 -582 Z", { fill: "#ff2a45", filter: "url(#glow)" });      // eyes: slanted slits
  s += pairD("M -34 -600 L -4 -584", { stroke: "#000", "stroke-width": 3 });                                   // brow
  for (let x = -12; x <= 12; x += 6) s += path(PL([[x, -556], [x, -540]]), { stroke: "#ff2a45", "stroke-width": 2.4, filter: "url(#glow)" }); // grill
  s += C;
  s += crack([[22, -624], [14, -604], [22, -590]]);
  s += C;
  s += O("u-embers");
  for (let i = 0; i < 26; i++) { const x = Math.sin(i * 12.9898) * 190, y = -60 - ((i * 97) % 640), r = 1.2 + (i % 4) * .6; s += el("circle", { cx: x.toFixed(1), cy: y, r, fill: i % 3 ? "#ff2a45" : "#ff8a3a", opacity: .4 + (i % 5) * .1 }); }
  s += C;
  return s;
}

// ---------------------------------------------------------------- JUNO (flat, sharp, neon), in movable pieces
function juno() {
  const ink = "#0d0a14", v = "#c13dff", cy = "#46f0ff", pink = "#ff5ae0", deep = "#3a1cff", rim = "#a24dff", red = "#ff2a45";
  const line = (d, c = cy, w = 1.4) => path(d, { fill: "none", stroke: c, "stroke-width": w, "stroke-linecap": "round", "stroke-linejoin": "round", filter: "url(#glow)" });
  // a set of black shapes drawn as one glowing outline, then filled, so pieces of one limb show no seams
  const piece = (shapes) => { const d = shapes.map(P).join(" "); return path(d, { fill: rim, stroke: rim, "stroke-width": 7, "stroke-linejoin": "miter", filter: "url(#glow)", opacity: .9 }) + path(d, { fill: ink }); };
  let s = "";
  // mane, behind everything; turns with her head
  s += O("n-mane");
  const mane = "M -6 -560 L -40 -620 L -150 -640 L -60 -660 L -190 -760 L -50 -700 L -60 -820 L 10 -712 L 60 -860 L 70 -720 L 170 -800 L 110 -690 L 260 -720 L 140 -650 L 300 -600 L 150 -610 L 250 -500 L 120 -560 L 160 -420 L 80 -530 L 40 -470 L 30 -548 Z";
  s += el("g", { id: "n-maneshadow" }, path(mane, { fill: deep, transform: "translate(14,12)", opacity: .9 }));
  s += path(mane, { fill: "url(#mane)", stroke: "#ff9cf0", "stroke-width": 1.2 });
  const facets = [
    [[-60, -660], [-190, -760], [-50, -700], [-30, -650]], [[-60, -820], [10, -712], [0, -680], [-40, -690]],
    [[60, -860], [70, -720], [40, -700], [20, -720]], [[170, -800], [110, -690], [90, -700]],
    [[260, -720], [140, -650], [120, -664]], [[300, -600], [150, -610], [140, -626]], [[250, -500], [120, -560], [130, -580]],
    [[160, -420], [80, -530], [100, -540]], [[-150, -640], [-40, -620], [-30, -636]],
  ];
  facets.forEach((f, i) => s += path(P(f), { fill: i % 2 ? "#ffb8f4" : "#5a22ff", opacity: i % 2 ? .45 : .55 }));
  s += path("M 20 -600 L 120 -700 M 30 -580 L 200 -620 M 10 -620 L 30 -760 M 40 -560 L 180 -520 M -10 -600 L -110 -700", { stroke: "#ffe6fd", "stroke-width": 1.6, opacity: .75 });
  s += C;
  // legs
  s += O("n-legL") + piece([[[-4, -300], [-48, -300], [-56, -210], [-44, -140], [-30, -40], [-36, 0], [-20, -42], [-18, -150], [-10, -230]]]);
  s += line("M -28 -290 L -38 -160 L -28 -70") + line("M -20 -300 L -24 -200", "#3d2a66", 2);
  s += path(P([[-40, -190], [-30, -170], [-38, -150], [-48, -170]]), { fill: v }) + path(P([[-30, -60], [-20, -42], [-36, 0], [-44, -40]]), { fill: cy, filter: "url(#glow)" }) + C;
  s += O("n-legR") + piece([[[4, -300], [48, -300], [66, -196], [90, -62], [110, -10], [72, -56], [34, -160], [14, -236]]]);
  s += line("M 26 -290 L 46 -170 L 76 -70") + line("M 22 -300 L 34 -210", "#3d2a66", 2);
  s += path(P([[46, -192], [56, -172], [46, -152], [38, -172]]), { fill: v }) + path(P([[86, -60], [110, -10], [72, -56]]), { fill: cy, filter: "url(#glow)" }) + C;
  // core: hips, waist, chest, neck
  s += O("n-core") + piece([[[-42, -336], [42, -336], [52, -298], [0, -258], [-52, -298]], [[-26, -424], [26, -424], [17, -372], [42, -334], [-42, -334], [-17, -372]],
    [[-52, -492], [52, -492], [44, -456], [28, -422], [-28, -422], [-44, -456]], [[-10, -500], [10, -500], [8, -520], [-8, -520]]]);
  s += path(P([[-42, -336], [42, -336], [0, -300]]), { fill: v }) + path(P([[-24, -332], [24, -332], [0, -312]]), { fill: pink });
  s += line("M -16 -410 L -8 -350 M 16 -410 L 8 -350", "#3d2a66", 2);
  s += path(P([[-34, -480], [0, -440], [34, -480], [0, -462]]), { fill: v });
  s += el("g", { id: "n-heart" }, path(P([[0, -458], [10, -442], [0, -426]]), { fill: red, filter: "url(#glow)" }) + path(P([[0, -458], [-10, -442], [0, -426]]), { fill: cy, filter: "url(#glow)" }));
  s += line("M -40 -470 L -26 -436 M 40 -470 L 26 -436", pink, 1.2) + C;
  // arm thrown up (viewer's left), pivots at the shoulder
  s += O("n-armU") + piece([[[-38, -484], [-62, -500], [-114, -598], [-94, -614]], [[-112, -598], [-94, -614], [-148, -722], [-164, -714]],
    ...[[-200, -760], [-186, -782], [-160, -790], [-140, -776]].map(([x, y]) => [[-160, -716], [x, y], [-148, -722]])]);
  s += line("M -52 -506 L -100 -598 M -106 -612 L -150 -708") + path(P([[-104, -598], [-92, -612], [-98, -620], [-112, -606]]), { fill: pink });
  s += path(P([[-150, -720], [-168, -742], [-156, -748]]), { fill: pink }) + C;
  // arm sweeping down (viewer's right), ending in a blade
  s += O("n-armD") + piece([[[38, -484], [62, -494], [124, -412], [106, -398]], [[122, -412], [106, -398], [178, -328], [192, -342]]]);
  s += line("M 52 -492 L 112 -414 L 180 -342") + path(P([[112, -420], [124, -408], [118, -398], [106, -410]]), { fill: pink });
  s += path(P([[180, -330], [190, -340], [236, -270], [196, -322]]), { fill: cy, filter: "url(#glow)" }) + C;
  // shoulder points, over the joints
  s += path(P([[-46, -490], [-84, -516], [-60, -476]]), { fill: v }) + path(P([[46, -490], [84, -516], [60, -476]]), { fill: v });
  s += path(P([[-54, -494], [-74, -508], [-62, -484]]), { fill: pink }) + path(P([[54, -494], [74, -508], [62, -484]]), { fill: pink });
  // head
  s += O("n-head") + piece([[[0, -604], [30, -584], [26, -540], [0, -514], [-26, -540], [-30, -584]]]);
  s += path(P([[-30, -584], [30, -584], [27, -560], [-27, -560]]), { fill: "#1d1430" });
  s += O("n-eyes");
  s += path(P([[-24, -582], [-4, -574], [-22, -563], [-14, -573]]), { fill: cy, filter: "url(#glow)" });
  s += path(P([[24, -582], [4, -574], [22, -563], [14, -573]]), { fill: red, filter: "url(#glow)" });
  s += path(P([[-14, -575], [-10, -573], [-14, -571]]), { fill: "#fff" }) + path(P([[14, -575], [10, -573], [14, -571]]), { fill: "#fff" }) + C;
  s += O("n-grin");
  s += path("M -20 -548 Q 0 -526 22 -550 L 17 -546 L 13 -540 L 9 -544 L 5 -536 L 1 -541 L -3 -535 L -7 -540 L -11 -536 L -15 -543 Z", { fill: "#fff" });
  s += path("M -18 -546 Q 0 -530 20 -548", { fill: "none", stroke: pink, "stroke-width": 1, opacity: .8 }) + C;
  s += path(P([[0, -604], [7, -622], [0, -642], [-7, -622]]), { fill: pink, filter: "url(#glow)" });
  s += path(P([[-30, -584], [-40, -600], [-26, -592]]), { fill: v }) + path(P([[30, -584], [40, -600], [26, -592]]), { fill: v }) + C;
  // shards orbiting her (moved every frame)
  s += O("n-shards");
  for (const [f, k] of [[cy, 1], [pink, 1.2], [v, .9], [cy, 1], [pink, .8], [v, .7], [cy, .8], [pink, 1]])
    s += el("g", {}, el("g", { transform: `scale(${k})` }, path(P([[0, -16], [6, 0], [0, 16], [-6, 0]]), { fill: f }) + path(P([[0, -16], [6, 0], [0, 0]]), { fill: "#fff", opacity: .35 })));
  s += C;
  return s;
}

function junoFloor() {
  let s = "";
  for (let i = -10; i <= 10; i++) s += path(PL([[i * 30, 0], [i * 140, 220]]), { stroke: "url(#grid)", "stroke-width": 1.4 });
  for (let k = 0; k < 7; k++) { const y = Math.pow(k / 6, 1.8) * 220; s += path(PL([[-1400, y], [1400, y]]), { stroke: "#b44dff", "stroke-opacity": .18 + k * .06, "stroke-width": 1.2 }); }
  return s;
}

function render(svgEl) {
  const W = 1560, H = 960, G = 880;
  svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svgEl.innerHTML = defs()
    + el("rect", { width: W, height: H, fill: "#0f0c16" })
    + el("g", { transform: `translate(780,${G})` }, junoFloor())
    + el("rect", { y: G, width: W, height: H - G, fill: "#0b0910", opacity: .6 })
    + el("g", { transform: `translate(270,${G}) scale(1.08)` }, el("g", { id: "jarvis" }, jarvis()))
    + el("g", { transform: `translate(1290,${G}) scale(1.08)` }, el("g", { id: "ultron" }, ultron()))
    + el("g", { transform: `translate(760,${G}) scale(1.0)` }, el("g", { id: "juno" }, juno()));
}
if (document.getElementById("cast")) render(document.getElementById("cast"));
