// Juno on the desktop from her standing and walking pictures (juno_stand.png, juno_walk.png).
//
// Each picture sits on a fine mesh. Every point of the mesh knows how much it belongs to each bone (torso, head,
// upper arm, forearm, thigh, shin) and to her hair, worked out once from the joint positions below, in the
// picture's own pixels. Bones hang off each other (forearm off upper arm off torso), so bending an elbow carries
// the hand with it. Each frame only the bone angles change and the graphics card bends the picture: one draw call.
// The far arm and far leg are drawn first, so the near ones pass in front of them when she walks.
"use strict";
const JunoRig = (() => {
  const sm = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  function seg(p, a, b) {
    const vx = b[0] - a[0], vy = b[1] - a[1], L = vx * vx + vy * vy;
    const t = ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L, c = Math.max(0, Math.min(1, t));
    return [Math.hypot(p[0] - a[0] - vx * c, p[1] - a[1] - vy * c), t];
  }

  // ------------------------------------------------------------------ the two pictures and their joints
  // bone: [name, parent index, pivot, end, inner radius, outer radius, back layer?, side test]
  const STAND = {
    src: "juno_stand.png", w: 507, h: 753, foot: [247, 750], face: [250, 195], faceR: [62, 96], hairTo: 430,
    bones: [
      ["torso", -1, [247, 480]],
      ["head", 0, [250, 242]],
      ["armL", 0, [192, 262], [180, 365], 13, 24],
      ["foreL", 2, [180, 365], [170, 494], 14, 26],
      ["armR", 0, [302, 262], [318, 365], 13, 24],
      ["foreR", 4, [318, 365], [328, 494], 14, 26],
      ["thighL", 0, [227, 505], [228, 605], 18, 28, 0, (x, y) => x < 248],
      ["shinL", 6, [228, 605], [232, 760], 16, 26, 0, (x, y) => x < 248],
      ["thighR", 0, [268, 505], [268, 605], 18, 28, 0, (x, y) => x >= 248],
      ["shinR", 8, [268, 605], [262, 760], 16, 26, 0, (x, y) => x >= 248],
    ],
  };
  const nearSide = (x, y) => x < 247 + (y - 450) * 0.15;
  const WALK = {
    src: "juno_walk.png", w: 498, h: 739, foot: [250, 728], face: [215, 195], faceR: [55, 88], hairTo: 720, facing: -1,
    bones: [
      ["torso", -1, [245, 440]],
      ["head", 0, [232, 252]],
      ["armN", 0, [196, 316], [128, 382], 14, 26],
      ["foreN", 2, [128, 382], [86, 432], 14, 28],
      ["armF", 0, [266, 300], [316, 368], 14, 26, 1],
      ["foreF", 4, [316, 368], [352, 462], 14, 28, 1],
      ["thighN", 0, [226, 452], [185, 578], 22, 34, 0, nearSide],
      ["shinN", 6, [185, 578], [58, 688], 32, 52, 0, nearSide, [[[124, 692], [44, 680], 26, 40], [[120, 696], [118, 736], 26, 40]]],
      ["thighF", 0, [262, 456], [308, 578], 22, 34, 1, (x, y) => !nearSide(x, y)],
      ["shinF", 8, [308, 578], [380, 726], 32, 52, 1, (x, y) => !nearSide(x, y), [[[360, 680], [398, 736], 26, 40]]],
    ],
  };
  // Two hero poses: pointing out to the side (when she opens something) and pointing up (when she's thinking).
  // They only bend at the head and the pointing arm, so they stay exactly like the art.
  const POINT = {
    src: "juno_point.png", w: 514, h: 770, foot: [262, 762], face: [240, 200], faceR: [52, 84], hairTo: 430,
    bones: [["torso", -1, [268, 420]], ["head", 0, [252, 250]], ["arm", 0, [205, 292], [22, 376], 20, 32]],
  };
  const UP = {
    src: "juno_up.png", w: 505, h: 776, foot: [278, 770], face: [272, 195], faceR: [50, 80], hairTo: 430,
    bones: [["torso", -1, [282, 420]], ["head", 0, [275, 242]], ["arm", 0, [228, 248], [108, 82], 20, 32]],
  };
  // Mid-leap, for her entrance. Her body is drawn smaller in this one, so her "feet" point is set where they'd be
  // at the standing picture's proportions; that keeps her the same size when the pictures swap.
  const DASH = {
    src: "juno_dash.png", w: 514, h: 722, foot: [240, 722], face: [185, 240], faceR: [48, 76], hairTo: 330, facing: -1,
    bones: [["torso", -1, [240, 430]], ["head", 0, [205, 282]]],
  };
  const NB = 10;

  // Which piece a spot belongs to: one of her limbs (a chain of bones hanging off the torso) or the body.
  // Pieces are cut apart for real (no shared mesh points), so a moving arm never smears into her side.
  function chains(S) {
    if (S._chains) return S._chains;
    const root = (i) => { while (S.bones[i][1] > 1) i = S.bones[i][1]; return i; };
    const c = {};
    for (let i = 2; i < S.bones.length; i++) (c[root(i)] = c[root(i)] || []).push(i);
    return (S._chains = c);
  }
  function pieceAt(S, x, y) {
    let best = -1, bestV = .5;
    for (let i = 2; i < S.bones.length; i++) {
      const [, , a, b, r0, r1, , side, extra] = S.bones[i];
      if (side && !side(x, y)) continue;
      const [d, t] = seg([x, y], a, b);
      let v = (1 - sm(r0, r1, d)) * sm(-0.1, 0.04, t);
      for (const [ea, eb, e0, e1] of extra || []) v = Math.max(v, 1 - sm(e0, e1, seg([x, y], ea, eb)[0]));   // her feet
      if (v > bestV) { bestV = v; best = i; }
    }
    if (best < 0) return -1;
    let r = best; while (S.bones[r][1] > 1) r = S.bones[r][1];
    return r;                                                 // the chain, named by its first bone
  }
  function weights(S, x, y, piece) {
    const p = [x, y], w = new Float32Array(NB + 1);
    let sum = 0;
    if (piece >= 0) {                                         // a limb: down the chain, pinned to the torso at the top
      for (const i of chains(S)[piece]) {
        const [, , a, b] = S.bones[i];
        const [, t] = seg(p, a, b);
        w[i] = sm(-0.1, 0.12, t);
      }
      // a later bone in the chain takes over from the one before it
      const list = chains(S)[piece];
      for (let k = list.length - 1; k > 0; k--) w[list[k - 1]] *= 1 - w[list[k]];
      for (const i of list) sum += w[i];
      w[0] = Math.max(0, 1 - sum);
      return { w, back: S.bones[piece][6] ? 1 : 0 };
    }
    const fd = Math.hypot(x - S.face[0], y - S.face[1]);
    const head = 1 - sm(S.faceR[0], S.faceR[1], fd);
    const body = seg(p, S.bones[1][2], S.bones[0][2])[0];
    const hair = sm(40, 90, body) * sm(S.hairTo, S.hairTo - 120, y) * (1 - head);
    w[1] = Math.min(1, head + hair * .55);
    w[0] = 1 - w[1];
    w[NB] = hair;
    return { w, back: 0 };
  }

  const VS = `
attribute vec2 aPos; attribute vec4 aW0; attribute vec4 aW1; attribute vec4 aW2;
uniform vec3 uM[${NB * 2}];
uniform vec4 uRoot;   // x, y (page px of her feet), scale, facing (1 or -1)
uniform vec4 uHair;   // time, amount, sway (px), speed
uniform vec2 uFoot;   // her feet in the picture
uniform vec2 uView;
varying vec2 vUv;
vec2 apply(int i, vec2 p) {
  vec3 h = vec3(p, 1.0);
  for (int k = 0; k < ${NB}; k++) if (k == i) return vec2(dot(uM[2 * k], h), dot(uM[2 * k + 1], h));
  return p;
}
void main() {
  float w[${NB}];
  w[0] = aW0.x; w[1] = aW0.y; w[2] = aW0.z; w[3] = aW0.w; w[4] = aW1.x; w[5] = aW1.y; w[6] = aW1.z; w[7] = aW1.w;
  w[8] = aW2.x; w[9] = aW2.y;
  vec2 q = vec2(0.0);
  for (int i = 0; i < ${NB}; i++) if (w[i] > 0.0001) q += w[i] * apply(i, aPos);
  float hair = aW2.z, t = uHair.x;
  q += hair * uHair.y * vec2(sin(t * 1.6 * uHair.w + aPos.y * .012 + aPos.x * .005) * 7.0 + uHair.z,
                             cos(t * 1.25 * uHair.w + aPos.x * .01) * 4.0);
  vec2 page = uRoot.xy + (q - uFoot) * vec2(uRoot.z * uRoot.w, uRoot.z);
  gl_Position = vec4(page.x / uView.x * 2.0 - 1.0, 1.0 - page.y / uView.y * 2.0, 0.0, 1.0);
  vUv = aPos;
}`;
  const FS = `
precision mediump float;
varying vec2 vUv;
uniform sampler2D uTex; uniform vec2 uSize;
uniform vec4 uFx;     // time, glitch, glow, alpha
float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  vec2 uv = vUv / uSize;
  float t = uFx.x, g = uFx.y;
  if (g > 0.01) { float band = floor(uv.y * 48.0), tick = floor(t * 14.0);
    if (h(vec2(band, tick)) < g * .35) uv.x += (h(vec2(tick, band)) - .5) * .06 * g; }
  vec4 c = texture2D(uTex, uv);
  if (g > 0.01) { c.r = texture2D(uTex, uv + vec2(.007 * g, 0.)).r; c.b = texture2D(uTex, uv - vec2(.007 * g, 0.)).b; }
  if (dot(c.rgb, vec3(.33)) > .6) {
    vec2 cell = floor(vUv / 4.0);
    c.rgb += .55 * pow(max(0., sin(t * (1.5 + h(cell) * 2.5) + h(cell + 3.1) * 6.28)), 9.);
  }
  c.rgb += uFx.z * .16 * vec3(.55, .3, 1.) * c.a;
  c *= uFx.w;
  gl_FragColor = vec4(c.rgb * c.a, c.a);
}`;

  // ------------------------------------------------------------------ poses: bone angles in degrees
  const s1 = Math.sin;
  function standPose(anim, t, v) {
    const b = new Float32Array(NB);
    const breath = s1(t * 1.7);
    b[0] = s1(t * .8) * 1.2;                          // weight shifting
    b[1] = s1(t * .7) * 2.5;
    b[2] = 3 + s1(t * 1.1) * 2; b[3] = -2 + s1(t * 1.3) * 3;
    b[4] = -3 - s1(t * 1.1 + 1) * 2; b[5] = 2 - s1(t * 1.2 + 1) * 3;
    b[6] = -s1(t * .8) * 1; b[8] = -s1(t * .8) * 1;
    let hair = .8, hs = 1, glow = 0, dy = breath * 1.5;
    if (anim === "listen") { b[1] = 6 + s1(t * .9) * 2; b[0] = 1.5; hair = 1.1; hs = 1.3; glow = .35; }
    if (anim === "think") { b[1] = -6 + s1(t) * 1; b[0] = -1; hair = .6; hs = .6; }
    if (anim === "talk") {
      b[1] = s1(t * 2.1) * 4 + v * 5; b[2] = 6 + s1(t * 1.7) * 6 + v * 8; b[3] = 10 + Math.abs(s1(t * 1.9)) * 18 + v * 12;
      b[4] = -6 - s1(t * 2.3) * 6; b[5] = -10 - Math.abs(s1(t * 2.6)) * 16; hair = 1 + v * .6; hs = 1.2 + v; glow = .3 + v * .7; dy -= v * 3;
    }
    if (anim === "happy") {
      dy = -Math.abs(s1(t * 4.6)) * 22; b[2] = 40 + s1(t * 4.6) * 20; b[4] = -40 - s1(t * 4.6) * 20; b[3] = 30; b[5] = -30;
      b[1] = s1(t * 2.3) * 6; hair = 1.6; hs = 2.2; glow = .6;
    }
    if (anim === "battle") { b[0] = -2; b[2] = 18; b[3] = 35; b[4] = -18; b[5] = -35; b[6] = 6; b[8] = -6; hair = 1.4; hs = 1.6; glow = .45; }
    return { b, hair, hs, glow, dy, sway: 0 };
  }
  function heroPose(t, v, which) {
    const b = new Float32Array(NB);
    b[0] = s1(t * .9) * .8;
    b[1] = s1(t * 1.3) * 2 + (v || 0) * 3;
    b[2] = which === "point" ? s1(t * 2.2) * 1.5 - Math.max(0, s1(t * 4)) * 2 : s1(t * 1.1) * 2;
    return { b, hair: 1.3, hs: 1.4, glow: .35 + (v || 0) * .5, dy: s1(t * 1.6) * 1.5, sway: 0 };
  }
  function walkPose(ph, t) {
    // ph: 0..2pi through one stride. The picture is the moment the near leg is forward.
    const b = new Float32Array(NB);
    const k = (1 - Math.cos(ph)) / 2;                // 0 at the picture, 1 halfway (legs swapped)
    const swingN = ph > Math.PI ? Math.sin(ph - Math.PI) : 0, swingF = ph < Math.PI ? Math.sin(ph) : 0;
    b[6] = -42 * k;  b[7] = -48 * swingN + 6 * k;    // near leg goes back; its knee folds as it comes forward
    b[8] = 42 * k;   b[9] = -48 * swingF - 6 * (1 - k);
    b[2] = -30 * k;  b[3] = -12 * k;                  // arms swing with the stride
    b[4] = 30 * k;   b[5] = 10 * k;
    b[0] = -1.5 + s1(ph * 2) * 1;
    b[1] = 2 + s1(ph * 2 + .6) * 2;
    return { b, hair: 1.2, hs: 1.6, glow: 0, dy: -Math.abs(s1(ph)) * 7, sway: 6 };
  }

  // ------------------------------------------------------------------ setup
  function create(canvas, onNeedPicture) {
    const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: true });
    if (!gl) return null;
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    gl.useProgram(pr);
    const U = {}; ["uM", "uRoot", "uHair", "uFoot", "uView", "uTex", "uSize", "uFx"].forEach((n) => U[n] = gl.getUniformLocation(pr, n));
    const A = {}; ["aPos", "aW0", "aW1", "aW2"].forEach((n) => { A[n] = gl.getAttribLocation(pr, n); gl.enableVertexAttribArray(A[n]); });
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    function mesh(S) {
      const NX = 72, NY = Math.round(72 * S.h / S.w), stride = 14;
      const verts = [], keys = new Map(), tris = [[], [], []];    // hair first, then the far limbs, then the rest
      const vert = (i, j, piece) => {
        const key = piece * 1e6 + j * 1000 + i;
        if (keys.has(key)) return keys.get(key);
        const x = i / NX * S.w, y = j / NY * S.h, { w } = weights(S, x, y, piece);
        verts.push(x, y, w[0], w[1], w[2], w[3], w[4], w[5], w[6], w[7], w[8], w[9], w[NB], 0);
        const n = verts.length / stride - 1; keys.set(key, n); return n;
      };
      for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
        const cx = (i + .5) / NX * S.w, cy = (j + .5) / NY * S.h;
        const piece = pieceAt(S, cx, cy);
        const a = vert(i, j, piece), b = vert(i + 1, j, piece), c = vert(i, j + 1, piece), d = vert(i + 1, j + 1, piece);
        const hr = piece < 0 ? weights(S, cx, cy, -1).w[NB] : 0;
        tris[piece >= 0 && S.bones[piece][6] ? 1 : hr > .5 ? 0 : 2].push(a, b, c, b, d, c);
      }
      const v = new Float32Array(verts);
      const idx = new Uint16Array([].concat(...tris));
      const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb); gl.bufferData(gl.ARRAY_BUFFER, v, gl.STATIC_DRAW);
      const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
      const tex = gl.createTexture();
      const m = { S, vb, ib, n: idx.length, tex, ready: false };
      const img = new Image();
      img.onload = async () => {
        gl.bindTexture(gl.TEXTURE_2D, tex);
        try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img); }
        catch (e) { if (!img.src.startsWith("data:") && onNeedPicture) { const d = await onNeedPicture(S.src); if (d) img.src = d; } return; }
        for (const [k, val] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, val);
        m.ready = true;
      };
      img.src = S.src;
      return m;
    }
    const meshes = { stand: mesh(STAND), walk: mesh(WALK), point: mesh(POINT), up: mesh(UP), dash: mesh(DASH) };

    // bone angles -> one 2D transform per bone, each riding on its parent
    const M = new Float32Array(NB * 6);
    function solve(S, deg) {
      const world = [];
      for (let i = 0; i < NB; i++) {
        const bone = S.bones[i];
        if (!bone) { world.push([1, 0, 0, 0, 1, 0]); continue; }
        const [, parent, pv] = bone, a = (deg[i] || 0) * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
        const loc = [c, -s, pv[0] - c * pv[0] + s * pv[1], s, c, pv[1] - s * pv[0] - c * pv[1]];     // turn about the joint
        const P = parent < 0 ? [1, 0, 0, 0, 1, 0] : world[parent];
        world.push([P[0] * loc[0] + P[1] * loc[3], P[0] * loc[1] + P[1] * loc[4], P[0] * loc[2] + P[1] * loc[5] + P[2],
                    P[3] * loc[0] + P[4] * loc[3], P[3] * loc[1] + P[4] * loc[4], P[3] * loc[2] + P[4] * loc[5] + P[5]]);
      }
      world.forEach((m, i) => M.set(m, i * 6));
      return M;
    }

    let W = 1, H = 1;
    function size(wCss, hCss) {
      const d = Math.min(2, devicePixelRatio || 1);
      canvas.width = Math.round(wCss * d); canvas.height = Math.round(hCss * d); W = wCss; H = hCss;
      gl.viewport(0, 0, canvas.width, canvas.height);
    }
    // draw her: which picture, the pose, where her feet go (page px within the canvas), how tall, which way
    function draw(which, pose, x, y, scale, facing, t, glitch, alpha) {
      const m = meshes[which];
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      if (!m.ready) return;
      gl.bindBuffer(gl.ARRAY_BUFFER, m.vb); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, m.ib);
      gl.vertexAttribPointer(A.aPos, 2, gl.FLOAT, false, 56, 0);
      gl.vertexAttribPointer(A.aW0, 4, gl.FLOAT, false, 56, 8);
      gl.vertexAttribPointer(A.aW1, 4, gl.FLOAT, false, 56, 24);
      gl.vertexAttribPointer(A.aW2, 4, gl.FLOAT, false, 56, 40);
      gl.bindTexture(gl.TEXTURE_2D, m.tex);
      const Mx = solve(m.S, pose.b), rows = new Float32Array(NB * 6);
      for (let i = 0; i < NB; i++) rows.set([Mx[i * 6], Mx[i * 6 + 1], Mx[i * 6 + 2], Mx[i * 6 + 3], Mx[i * 6 + 4], Mx[i * 6 + 5]], i * 6);
      gl.uniform3fv(U.uM, rows);
      const f = (m.S.facing || 1) * facing;
      gl.uniform4f(U.uRoot, x, y + pose.dy * scale, scale, f);
      gl.uniform4f(U.uHair, t, pose.hair, pose.sway, pose.hs);
      gl.uniform2f(U.uFoot, m.S.foot[0], m.S.foot[1]);
      gl.uniform2f(U.uView, W, H);
      gl.uniform2f(U.uSize, m.S.w, m.S.h);
      gl.uniform4f(U.uFx, t, glitch || 0, pose.glow || 0, alpha == null ? 1 : alpha);
      gl.drawElements(gl.TRIANGLES, m.n, gl.UNSIGNED_SHORT, 0);
    }
    return { size, draw, get ready() { return meshes.stand.ready && meshes.walk.ready; }, faceToFoot: (w) => meshes[w].S.foot[1] - meshes[w].S.face[1] };
  }
  return { create, standPose, walkPose, heroPose };
})();
