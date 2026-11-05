// Juno, drawn from her artwork (juno.png) and moved on the graphics card.
//
// The picture is laid over a fine mesh (about 90 x 120 points). Every point knows how much it belongs to her
// torso, head, each arm and leg, her hair, her grin and her crown (worked out once, from the joint positions
// below, in the picture's own pixels). Each frame only a handful of numbers change (angles, how open her grin
// is, how hard her hair is blowing...) and the graphics card bends the picture: one draw call, no redrawing of
// shapes, so it costs next to nothing. The hair speckles twinkle and the glitch is done in the same pass.
//
// The pixel-block effects around her are drawn on a second, plain canvas (a few dozen rectangles a frame).
"use strict";
const JunoGL = (() => {
  const IW = 896, IH = 1187, PAD = 90;                 // picture size; room around it to move into
  const J = {                                           // joints, in picture pixels
    hip: [390, 860], chest: [450, 690], neck: [548, 478], face: [560, 415], grinTop: 407, grin: [551, 432],
    crown: [565, 392], shR: [655, 400], handR: [850, 95], shL: [452, 560], handL: [170, 672],
    hipL: [330, 870], footL: [0, 1060], hipR: [365, 905], footR: [545, 1187],
  };
  const VS = `
attribute vec2 aPos; attribute vec4 aA; attribute vec4 aB; attribute float aC;
uniform vec4 uBones;   // torso, head, armR, armL (radians)
uniform vec4 uBones2;  // legL, legR, hair amount, grin open (1 = closed)
uniform vec4 uMisc;    // time, crown lift, breath, hair speed
uniform vec4 uRoot;    // x, y offset (px), scale, rotation
varying vec2 vUv;
vec2 rot(vec2 p, vec2 c, float a) { float s = sin(a), k = cos(a); p -= c; return c + vec2(p.x * k - p.y * s, p.x * s + p.y * k); }
void main() {
  vec2 q = aPos;
  float t = uMisc.x;
  q.y = mix(q.y, ${J.grinTop.toFixed(1)} + (q.y - ${J.grinTop.toFixed(1)}) * uBones2.w, aB.w);                 // grin opens downward
  q.y = mix(q.y, ${J.crown[1].toFixed(1)} + (q.y - ${J.crown[1].toFixed(1)}) * uMisc.y, aC);                  // crown lifts
  q = mix(q, rot(q, vec2(${J.neck}), uBones.y), aA.y);
  q = mix(q, rot(q, vec2(${J.shR}), uBones.z), aA.z);
  q = mix(q, rot(q, vec2(${J.shL}), uBones.w), aA.w);
  q = mix(q, rot(q, vec2(${J.hipL}), uBones2.x), aB.x);
  q = mix(q, rot(q, vec2(${J.hipR}), uBones2.y), aB.y);
  float d = length(aPos - vec2(${J.face}));
  float sp = uMisc.w;
  q += aB.z * uBones2.z * (0.4 + d / 500.0) * vec2(sin(t * 1.6 * sp + aPos.y * .011 + aPos.x * .004),
                                                     0.6 * cos(t * 1.25 * sp + aPos.x * .009 - aPos.y * .003)) * 9.0;
  q = mix(q, rot(q, vec2(${J.hip}), uBones.x), aA.x);
  q = mix(q, vec2(${J.chest}) + (q - vec2(${J.chest})) * (1.0 + uMisc.z), aA.x * 0.6);                     // breathing
  q = rot(q, vec2(${IW / 2}.0, ${IH}.0), uRoot.w);
  q = vec2(${IW / 2}.0, ${IH}.0) + (q - vec2(${IW / 2}.0, ${IH}.0)) * uRoot.z + uRoot.xy;
  vec2 c = (q + ${PAD}.0) / vec2(${IW + 2 * PAD}.0, ${IH + 2 * PAD}.0);
  gl_Position = vec4(c.x * 2.0 - 1.0, 1.0 - c.y * 2.0, 0.0, 1.0);
  vUv = aPos / vec2(${IW}.0, ${IH}.0);
}`;
  const FS = `
precision mediump float;
varying vec2 vUv;
uniform sampler2D uTex;
uniform vec4 uFx;      // time, glitch 0..1, glow 0..1, twinkle 0..1
float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  vec2 uv = vUv;
  float t = uFx.x, g = uFx.y;
  if (g > 0.01) {                                   // glitch: torn horizontal slices
    float band = floor(uv.y * 48.0), tick = floor(t * 14.0);
    if (h(vec2(band, tick)) < g * 0.35) uv.x += (h(vec2(tick, band)) - 0.5) * 0.06 * g;
  }
  vec4 c = texture2D(uTex, uv);
  if (g > 0.01) {                                   // and a colour split
    c.r = texture2D(uTex, uv + vec2(0.007 * g, 0.0)).r;
    c.b = texture2D(uTex, uv - vec2(0.007 * g, 0.0)).b;
  }
  float lum = dot(c.rgb, vec3(.33, .33, .34));
  if (lum > 0.55 && c.b > 0.55) {                   // the speckles in her hair twinkle
    vec2 cell = floor(uv * vec2(${IW}.0, ${IH}.0) / 7.0);
    float tw = pow(max(0.0, sin(t * (1.5 + h(cell) * 2.5) + h(cell + 3.1) * 6.28)), 10.0);
    c.rgb += uFx.w * tw * 0.55;
  }
  c.rgb += uFx.z * 0.16 * vec3(0.55, 0.3, 1.0) * c.a;  // she glows when she talks
  gl_FragColor = vec4(c.rgb * c.a, c.a);
}`;

  // ------------------------------------------------------------------ weights (computed once)
  const sm = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  function seg(p, a, b) {                               // distance to a bone, and how far along it (0 at the joint)
    const vx = b[0] - a[0], vy = b[1] - a[1], L = vx * vx + vy * vy;
    const t = Math.max(-1, Math.min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L));
    const cx = a[0] + vx * Math.max(0, t), cy = a[1] + vy * Math.max(0, t);
    return [Math.hypot(p[0] - cx, p[1] - cy), t];
  }
  const limb = (p, a, b, r0, r1, t0) => { const [d, t] = seg(p, a, b); return (1 - sm(r0, r1, d)) * sm(t0, t0 + .18, t); };
  function weights(x, y) {
    const p = [x, y];
    const armR = limb(p, J.shR, J.handR, 55, 105, 0), armL = limb(p, J.shL, J.handL, 50, 95, .02);
    const legL = limb(p, J.hipL, J.footL, 75, 125, .12), legR = limb(p, J.hipR, J.footR, 60, 110, .12);
    const fd = Math.hypot(x - J.face[0], y - J.face[1]);
    const head = 1 - sm(95, 150, fd);
    const core = 1 - sm(70, 130, seg(p, J.neck, J.hip)[0]);
    const torso = sm(900, 620, y) * Math.max(core, head, armR, armL, .35);
    const hair = Math.max(0, sm(110, 260, fd) * sm(880, 760, y) - Math.max(armR, armL, legL, legR, core)) + head * .0;
    const grin = (1 - sm(.9, 1.5, Math.hypot((x - J.grin[0]) / 34, (y - J.grin[1]) / 30))) * sm(395, 410, y);
    const crown = (1 - sm(.85, 1.4, Math.hypot((x - J.crown[0]) / 75, (y - (J.crown[1] - 22)) / 40))) * (1 - grin);
    return [torso, Math.max(head, hair * .25), armR, armL, legL, legR, hair, grin, crown];
  }

  // ------------------------------------------------------------------ poses
  const DEF = { torso: 0, head: 0, armR: 0, armL: 0, legL: 0, legR: 0, hair: .8, hairSp: 1, grin: 1, crown: 1, breath: 0,
                x: 0, y: 0, scale: 1, rot: 0, glitch: 0, glow: 0, twinkle: .8 };
  const s1 = Math.sin;
  const ANIM = {
    idle: (t) => ({ torso: s1(t * .9) * .015, head: s1(t * .7) * .03, armR: s1(t * 1.1) * .04, armL: s1(t * 1.3 + 1) * .035,
                    legL: s1(t * .8) * .02, legR: s1(t * .8 + 2) * .02, breath: s1(t * 1.7) * .008, y: s1(t * 1.2) * 6 }),
    listen: (t) => ({ head: .1 + s1(t * .9) * .02, torso: .02, armR: -.05 + s1(t) * .03, hair: 1.1, hairSp: 1.3, crown: 1.08, y: s1(t * 1.4) * 4, glow: .35 }),
    think: (t) => ({ head: -.08, torso: -.015, armL: .08, hair: .6, hairSp: .6, crown: .94, glitch: s1(t * 3) > .85 ? .45 : 0, y: s1(t) * 3, twinkle: 1.3 }),
    talk: (t, v) => ({ head: s1(t * 2.1) * .04 + v * .05, armR: s1(t * 1.7) * .06, armL: s1(t * 2.3) * .05, grin: 1 + v * .4, crown: 1 + v * .06,
                       hair: 1 + v * .6, hairSp: 1.2 + v, glow: .3 + v * .7, y: s1(t * 1.5) * 4 - v * 4, glitch: v > .85 ? .25 : 0 }),
    happy: (t) => ({ y: -Math.abs(s1(t * 4.6)) * 26, rot: s1(t * 2.3) * .03, armR: s1(t * 4.6) * .14, armL: s1(t * 4.6 + 1) * .12,
                     head: s1(t * 2.3) * .08, grin: 1.25, crown: 1.12, hair: 1.6, hairSp: 2.2, glow: .6, twinkle: 1.6, legL: s1(t * 4.6) * .05, legR: -s1(t * 4.6) * .05 }),
    summon: (t) => { const k = Math.min(1, t / .35) * (1 - Math.max(0, Math.min(1, (t - 2.6) / .8)));
                     return { armR: -.28 * k, armL: .12 * k, head: -.06 * k, hair: 1 + k * 1.4, hairSp: 1 + k * 1.5, glow: .5 + k * .5, glitch: t < .5 ? .8 : t < 1 ? .3 : 0, grin: 1.15, crown: 1.1, scale: 1 + .03 * k }; },
    battle: (t) => ({ torso: .06, y: 14 + s1(t * 2) * 3, head: -.04, armR: -.1 + s1(t * 1.6) * .02, armL: .14, legL: .05, legR: -.06,
                      hair: 1.5, hairSp: 1.6, glow: .45, glitch: s1(t * 3) > .7 ? .5 : 0, crown: .95 }),
  };

  // ------------------------------------------------------------------ the pixel-block effects
  const FXC = ["#20d27e", "#4b1fa3", "#2a0e63"];
  function makeFx() {
    const blocks = [];
    const SPOTS = [[700, 980], [820, 900], [120, 1090], [60, 760], [840, 560], [120, 300], [760, 1110], [560, 1000], [250, 1020]];
    return {
      blocks,
      spawn(burst) {
        const [ax, ay] = SPOTS[Math.floor(Math.random() * SPOTS.length)];
        const cs = 22 + Math.random() * 14, n = 4 + Math.floor(Math.random() * 6), dir = Math.random() < .5 ? -1 : 1;
        const cells = []; let cx = ax + (Math.random() - .5) * 120, cy = ay + (Math.random() - .5) * 80;
        for (let i = 0; i < n; i++) {                        // a little staircase, like her art
          cells.push([cx, cy, i % 3 === 2 ? 1 : 0]);
          if (Math.random() < .6) cx += cs * dir; else cy -= cs;
        }
        if (Math.random() < .5) cells.push([ax - 40, ay + cs * 2, 1, 6]);   // a long bar underneath
        blocks.push({ cells, cs, born: performance.now() / 1000, life: (burst ? .9 : 1.6) + Math.random() * 1.6, step: .045 + Math.random() * .04 });
        if (blocks.length > 40) blocks.shift();
      },
      draw(ctx, T, toPx, k) {
        for (let i = blocks.length - 1; i >= 0; i--) {
          const b = blocks[i], age = T - b.born, end = b.life;
          if (age > end + .5) { blocks.splice(i, 1); continue; }
          const shown = Math.min(b.cells.length, Math.floor(age / b.step) + 1);
          const dying = age > end, flick = dying ? (Math.random() < (age - end) * 2) : false;
          for (let c = 0; c < shown; c++) {
            if (dying && (flick || Math.random() < .3)) continue;
            const [x, y, kind, len] = b.cells[c], w = b.cs * (len || 1), hgt = b.cs * (len ? .7 : 1);
            const [px, py] = toPx(x, y);
            ctx.fillStyle = FXC[2]; ctx.fillRect(px + 6 * k, py + 6 * k, w * k, hgt * k);          // offset shadow
            ctx.fillStyle = FXC[kind]; ctx.fillRect(px, py, w * k, hgt * k);
          }
        }
      },
    };
  }

  // ------------------------------------------------------------------ setup
  function create(glCanvas, fxCanvas, imgUrl) {
    const gl = glCanvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: false });
    if (!gl) return null;
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    gl.useProgram(pr);
    // the mesh
    const NX = 90, NY = 120, verts = new Float32Array((NX + 1) * (NY + 1) * 11), idx = [];
    let o = 0;
    for (let j = 0; j <= NY; j++) for (let i = 0; i <= NX; i++) {
      const x = i / NX * IW, y = j / NY * IH, w = weights(x, y);
      verts.set([x, y, w[0], w[1], w[2], w[3], w[4], w[5], w[6], w[7], w[8]], o); o += 11;
    }
    for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
      const a = j * (NX + 1) + i, b = a + 1, c = a + NX + 1, d = c + 1; idx.push(a, b, c, b, d, c);
    }
    const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb); gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW);
    const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
    const big = idx.length > 65535 && gl.getExtension("OES_element_index_uint");
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, big ? new Uint32Array(idx) : new Uint16Array(idx), gl.STATIC_DRAW);
    const at = (n, size, off) => { const l = gl.getAttribLocation(pr, n); gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, size, gl.FLOAT, false, 44, off * 4); };
    at("aPos", 2, 0); at("aA", 4, 2); at("aB", 4, 6); at("aC", 1, 10);
    const U = {}; ["uBones", "uBones2", "uMisc", "uRoot", "uFx", "uTex"].forEach((n) => U[n] = gl.getUniformLocation(pr, n));
    const tex = gl.createTexture(); let ready = false;
    const img = new Image();
    img.onload = async () => {
      gl.bindTexture(gl.TEXTURE_2D, tex); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img); }
      catch (e) {                                 // a file:// page: get the picture from Python as a data: link
        if (img.src.startsWith("data:")) return;
        const get = () => window.pywebview && window.pywebview.api;
        const x = get() || await new Promise((r) => window.addEventListener("pywebviewready", () => r(get()), { once: true }));
        const d = x && x.picture ? await x.picture(imgUrl) : "";
        if (d) img.src = d;
        return;
      }
      for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
      ready = true;
    };
    img.src = imgUrl;
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    const fctx = fxCanvas.getContext("2d"), fx = makeFx();
    const cur = Object.assign({}, DEF);
    let anim = "idle", t0 = 0, spawnAcc = 0, extra = { glitch: 0, scale: 1 };

    function size(wCss, hCss) {
      const d = Math.min(2, devicePixelRatio || 1);
      for (const c of [glCanvas, fxCanvas]) { c.width = Math.round(wCss * d); c.height = Math.round(hCss * d); }
      gl.viewport(0, 0, glCanvas.width, glCanvas.height);
    }
    function play(a) { if (!ANIM[a]) a = "idle"; if (a !== anim) { anim = a; t0 = performance.now() / 1000; if (a === "summon") for (let i = 0; i < 10; i++) fx.spawn(true); } }
    function step(now, dt, level) {
      const T = now / 1000, ta = T - t0;
      const tgt = Object.assign({}, DEF, ANIM[anim](anim === "summon" ? ta : T, level || 0));
      const k = 1 - Math.exp(-dt * (anim === "talk" || anim === "happy" ? 12 : 6));
      for (const key in DEF) cur[key] += (tgt[key] - cur[key]) * (key === "glitch" ? 1 : k);
      extra.glitch = Math.max(0, extra.glitch - dt * 1.4);
      if (!ready) return;
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform4f(U.uBones, cur.torso, cur.head, cur.armR, cur.armL);
      gl.uniform4f(U.uBones2, cur.legL, cur.legR, cur.hair, cur.grin);
      gl.uniform4f(U.uMisc, T, cur.crown, cur.breath, cur.hairSp);
      gl.uniform4f(U.uRoot, cur.x, cur.y, cur.scale * extra.scale, cur.rot);
      gl.uniform4f(U.uFx, T, Math.min(1, cur.glitch + extra.glitch), cur.glow, cur.twinkle);
      gl.drawElements(gl.TRIANGLES, idx.length, big ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT, 0);
      // effects
      const rate = anim === "talk" ? 1.6 + level * 3 : anim === "happy" || anim === "battle" ? 2.5 : anim === "think" ? .9 : .5;
      spawnAcc += dt * rate; while (spawnAcc > 1) { fx.spawn(false); spawnAcc -= 1; }
      const sx = fxCanvas.width / (IW + 2 * PAD), sy = fxCanvas.height / (IH + 2 * PAD);
      fctx.setTransform(1, 0, 0, 1, 0, 0); fctx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);
      fx.draw(fctx, T, (x, y) => [(x + PAD + cur.x) * sx, (y + PAD + cur.y) * sy], sx);
    }
    return { play, step, size, glitch(v) { extra.glitch = Math.max(extra.glitch, v); }, setScale(v) { extra.scale = v; },
             aspect: (IW + 2 * PAD) / (IH + 2 * PAD), footFrac: (IH + PAD) / (IH + 2 * PAD), get ready() { return ready; } };
  }
  return { create };
})();
