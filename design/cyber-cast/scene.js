// ============================================================================ the preview scene
"use strict";
const cv = document.getElementById("c"), ctx = cv.getContext("2d");
useCtx(ctx);
let W = 0, H = 0, DPR = 1;
function size() { DPR = Math.min(devicePixelRatio || 1, 2); W = innerWidth; H = innerHeight; cv.width = W * DPR; cv.height = H * DPR; }
addEventListener("resize", size); size();

const CAST = [typeof JA !== "undefined" && JA, typeof JU !== "undefined" && JU, typeof UL !== "undefined" && UL].filter(Boolean);
const STATE = CAST.map((c, i) => ({ c, pose: newPose(), anim: "idle", blinkAt: 1 + i, x: 0, dir: i % 2 ? -1 : 1 }));
let view = new URLSearchParams(location.search).get("view") || "lineup", anim = new URLSearchParams(location.search).get("anim") || "idle";
let T0 = performance.now() / 1000, startupT = null;

// ---- controls
const bar = document.getElementById("bar");
function button(label, pressed, onclick) { const b = document.createElement("button"); b.textContent = label; b.setAttribute("aria-pressed", String(pressed)); b.onclick = onclick; bar.appendChild(b); return b; }
const animBtns = ANIM_ORDER.map((a) => button(a[0].toUpperCase() + a.slice(1), a === anim, () => { anim = a; animBtns.forEach((b, i) => b.setAttribute("aria-pressed", String(ANIM_ORDER[i] === a))); }));
bar.appendChild(Object.assign(document.createElement("span"), { className: "sep" }));
const viewBtns = [["lineup", "Line-up"], ["close", "Faces"], ["startup", "Juno's startup"]].map(([v, l]) => button(l, v === view, () => {
  view = v; viewBtns.forEach((b, i) => b.setAttribute("aria-pressed", String(["lineup", "close", "startup"][i] === v))); if (v === "startup") startupT = performance.now() / 1000;
}));

function voice(t) { const phrase = (t % 4.4) < 3.3, syl = Math.max(0, sn(t * 13) * .6 + sn(t * 7.3) * .4); return phrase ? .2 + .8 * syl : 0; }

function updatePoses(t, dt) {
  STATE.forEach((s, i) => {
    const target = targetPose(Object.assign({ dir: s.dir }, s.c), anim, t + i * 1.3, anim === "talk" ? voice(t + i) : 0);
    // blinking (not while napping or in the ^^ face)
    if (t > s.blinkAt) { s.blinkAt = t + 2 + Math.random() * 3.5; s.blinkStart = t; }
    const bt = s.blinkStart ? (t - s.blinkStart) / .16 : 2;
    target.blink = bt < 1 ? Math.sin(bt * Math.PI) : 0;
    blendPose(s.pose, target, 1 - Math.exp(-dt * 10));
    s.pose.blink = target.blink;                       // blinks are instant, not eased
  });
}

function backdrop(t) {
  const gr = ctx.createLinearGradient(0, 0, 0, H);
  gr.addColorStop(0, "#151127"); gr.addColorStop(1, "#0b0914"); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "rgba(255,255,255,.04)"; ctx.fillRect(0, H - 44, W, 44);
  ctx.fillStyle = "rgba(255,255,255,.08)"; ctx.fillRect(0, H - 44, W, 1);
}

function drawAt(s, x, y, sc, t) {
  ctx.save(); ctx.translate(x, y); ctx.scale(sc, sc);
  drawCharacter(s.c, s.pose, t);
  ctx.restore();
}

let last = performance.now() / 1000;
function frame(now) {
  const t = now / 1000, dt = Math.min(.05, t - last); last = t;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  backdrop(t);
  updatePoses(t, dt);
  if (view === "lineup") {
    const sc = Math.min((H - 120) / 560, W / (CAST.length * 300));
    STATE.forEach((s, i) => drawAt(s, W / 2 + (i - (CAST.length - 1) / 2) * 300 * sc, H - 44, sc, t + i * 1.3));
  } else if (view === "close") {
    const sc = Math.min((H - 80) / 230, W / (CAST.length * 160));
    STATE.forEach((s, i) => {
      const cx = W / 2 + (i - (CAST.length - 1) / 2) * 150 * sc;
      ctx.save(); ctx.beginPath(); ctx.rect(cx - 75 * sc, 60, 150 * sc, H - 60); ctx.clip();
      drawAt(s, cx, H + 330 * sc, sc, t + i * 1.3);
      ctx.restore();
    });
  } else if (typeof drawStartup === "function") {
    drawStartup(t - startupT, t, dt);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
