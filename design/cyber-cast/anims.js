// ============================================================================ animations
// Each one returns the pose a character is heading for right now; the scene eases the real pose towards it, so
// switching from one to another is always smooth. v = voice level (0..1) while talking.
"use strict";
const sn = Math.sin, cs = Math.cos;
const PERSONALITY = {
  juno: { smile: .45, open: 1.05, blush: .3 },
  jarvis: { smile: .22, open: .92, blush: .08, brow: -.1 },
  ultron: { smile: .32, skew: .7, open: .82, angry: .25, blush: .05 },
};

const ANIMS = {
  idle(t, c) {
    return { bob: sn(t * 1.7) * 1.6, tilt: sn(t * .5) * .03, aL: [.12 + sn(t * 1.7) * .015, -.1], aR: [.12 + sn(t * 1.7 + 1) * .015, -.1],
             lookX: Math.round(sn(t * .23) * 1.4) * .35, sway: sn(t * .8) * .1 };
  },
  talk(t, c, v) {
    const g8 = Math.floor(t / 3.5) % 3;              // a gesture every few seconds, different hands
    const syl = Math.max(0, sn(t * 12) * .6 + sn(t * 7.7) * .4);
    return { bob: sn(t * 1.7) * 1.6, nod: v * 1.6, tilt: sn(t * .9) * .05,
             mo: v * (.6 + syl * .4), mw: .35 + sn(t * 5) * .25, mr: Math.max(0, sn(t * 3.1)) * .4, brow: v * .25,
             aR: g8 === 0 ? [.55 + sn(t * 2) * .05, 1.25 + sn(t * 3) * .1] : [.14, -.08], handR: g8 === 0 ? "open" : "open",
             aL: g8 === 1 ? [.45, 1.0 + sn(t * 2.5) * .12] : [.14, -.08] };
  },
  listen(t, c) {
    return { tilt: .13, open: 1.18, brow: .45, lean: .025, lookX: .3, lookY: -.1, smile: .25, bob: sn(t * 1.7) * 1.2,
             aR: [.35, 2.1], handR: "open", aL: [.14, -.1] };
  },
  think(t, c) {
    return { tilt: -.06, lookX: .9, lookY: -.8, brow: .3, smile: .05, skew: -.4, mo: 0, bob: sn(t * 1.2),
             aL: [-.42, -2.25], handL: "point", aR: [-.55, -1.25], handR: "fist", star: 1 };
  },
  happy(t, c) {
    const hop = Math.max(0, sn(t * 6));
    return { happy: 1, smile: 1, mo: .45 + hop * .2, mw: .7, blush: .6, bob: -hop * 10, tilt: sn(t * 3) * .06,
             aL: [.7 + hop * .2, .3], aR: [.7 + hop * .2, .3], handL: "open", handR: "open", fL: hop * .2, fR: hop * .2 };
  },
  wave(t, c) {
    return { smile: .8, mo: .25, mw: .6, tilt: .08, lookX: -.2, bob: sn(t * 1.7) * 1.4, blush: .45,
             aR: [2.55, .35 + sn(t * 9) * .4], handR: "open", aL: [.12, -.1] };
  },
  walk(t, c) {
    const ph = t * 6.5, s = sn(ph);
    return { bob: -Math.abs(cs(ph)) * 4, turn: c.dir * .55, tilt: c.dir * .03, lean: c.dir * .02, sway: -c.dir * .25 + s * .05,
             fL: Math.max(0, s) * .7, fR: Math.max(0, -s) * .7, stepL: s * .4, stepR: -s * .4,
             aL: [.18 - s * .22, -.25], aR: [.18 + s * .22, -.25], lookX: c.dir * .7, hairWind: .5 };
  },
  dance(t, c) {
    const b = t * 4.2, beat = Math.abs(sn(b));
    return { bob: -beat * 9, lean: sn(b / 2) * .07, tilt: sn(b / 2) * .1, happy: Math.floor(t / 2) % 2 ? .9 : 0, smile: .9, mo: .2, mw: .6,
             aL: [1.3 + sn(b) * .7, .4 + sn(b + 1) * .5], aR: [1.3 - sn(b) * .7, .4 - sn(b + 1) * .5],
             fL: Math.max(0, sn(b / 2)) * .6, fR: Math.max(0, -sn(b / 2)) * .6, sway: sn(b / 2) * .4, hairWind: .6, blush: .5 };
  },
  nap(t, c) {
    const br = sn(t * 1.1);
    return { sleep: 1, tilt: .22 + br * .02, nod: 4 + br * 1.5, bob: 2 + br * 1.2, mo: .1 + Math.max(0, br) * .06, mr: 1, mw: .1,
             aL: [.06, -.05], aR: [.06, -.05], lean: .02, smile: .1, blush: .4 };
  },
  blades(t, c) {                                     // swords out (Juno: her shards spread into a ring)
    const br = Math.sin(t * 1.6);
    if (c.name === "juno") return { blades: 1, fx: 1, aL: [.62, .7], aR: [.62, .7], handL: "open", handR: "open", open: 1.15, smile: .5, bob: br * 2, hairWind: .4 };
    const hi = c.name === "jarvis" ? "aL" : "aR", lo = hi === "aL" ? "aR" : "aL";      // mirror images of each other
    return { blades: 1, [hi]: [2.15 + br * .03, .55], [lo]: [.42 - br * .03, -.15], lean: (hi === "aL" ? -1 : 1) * .03, bob: br * 1.5 - 2, tilt: (hi === "aL" ? 1 : -1) * .05, angry: c.name === "ultron" ? .7 : .1, brow: c.name === "jarvis" ? .1 : 0,
             smile: c.name === "ultron" ? .6 : .15, skew: c.name === "ultron" ? .9 : 0, open: c.name === "ultron" ? .85 : 1, lookY: .1 };
  },
  summon(t, c) {
    const p = (t % 3.2) / 3.2, up = smooth(clamp(p / .25, 0, 1)) * (1 - smooth(clamp((p - .8) / .2, 0, 1)));
    if (c.name === "jarvis") return { aL: [lerp(.12, 1.35, up), lerp(-.1, .55, up)], handL: "fist", lookX: -.6, lookY: -.5, brow: .2, smile: .3, fx: up, tilt: -.05 * up, open: 1.05 };
    if (c.name === "ultron") return { aR: [lerp(.14, 1.75, up), lerp(-.1, .15, up)], handR: up > .5 ? "claw" : "open", lookX: .8, lookY: -.4, angry: .5, smile: .5, skew: .9, fx: up, lean: .04 * up };
    return { aR: [lerp(.14, 2.0, up), lerp(-.1, .9 - up * .9, up)], handR: "open", lookX: .7, lookY: -.6, smile: .7, mo: .2 * up, fx: up, star: up, open: 1.15 };
  },
};
const ANIM_ORDER = ["idle", "talk", "listen", "think", "happy", "wave", "walk", "dance", "nap", "blades", "summon"];

function targetPose(c, anim, t, v) {
  const p = Object.assign({}, PERSONALITY[c.name] || {}, (ANIMS[anim] || ANIMS.idle)(t, c, v));
  return p;
}
