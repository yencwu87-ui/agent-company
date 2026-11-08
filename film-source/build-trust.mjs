import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./skill/kit/iso-kit.mjs";
import { kitScript } from "./skill/scripts/inline-kit.mjs";

// Agent Company's trust credits drawn as a bench instrument.
//   A returned quest card rides in from the left under the proof press: three stamps (pull request, tests, verdict)
//   and the OpenProof seal. The card drops into a hopper and leaves a puck in the outcome rack, a ten-slot shift
//   register (the newest pushes the oldest off the end). Each outcome moves the credit sight-glass: incidents drain it,
//   sealed clean work refills it. Bands at 70, 40 and 15. Under 15 the containment cage drops over the agent.
//   The level ladder's marker climbs only when the gates are met, and drops a rung on containment.

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes("--light") ? "light" : "dark";
const FILM = process.argv.includes("--film");
const WIDTH = 660, HEIGHT = 440;

const PLATE = { x: -182, y: -78, w: 364, d: 156, r: 9 };
const PLATE_H = 12, FOOT_H = 5;
const RAIL_Y = 28, RAIL = [-178, -58];
const PRESS = { x0: -150, x1: -92, beam: 50, y: RAIL_Y, heads: [-136, -126, -116, -106], rest: 24 };
const CARD = { w: 30, d: 20 }, CAR_TOP = 6, CARD_TOP = CAR_TOP + 2;
const HOP = { x: -60, y: RAIL_Y };
const RACK = { x0: -44, step: 11.6, n: 10, y: RAIL_Y, z: 6 };
const BIN = { x: RACK.x0 + RACK.step * RACK.n + 4, y: RAIL_Y };
const GLASS = { x: 112, y: -34, r: 8, z0: 10, h: 80 };
const SCALE = { x: 124, y: -34 };
const PED = { x: 120, y: 34 };
const CAGE = { r: 15, h: 30, up: 34 };
const LADDER = { x: 32, y: -50, z0: 8, rung: 12 };
const DIAL = { x: -52, y: -46, r: 15, z: 30, h: 5 };

const P = k.fitProjection(
  [...k.boxCorners(PLATE, -PLATE_H - FOOT_H, 0), [GLASS.x, GLASS.y, GLASS.z0 + GLASS.h + 8], [PED.x, PED.y, CAGE.h + CAGE.up + 6], [LADDER.x, LADDER.y, LADDER.z0 + LADDER.rung * 6 + 6], [PRESS.x0, RAIL_Y, PRESS.beam + 10]],
  WIDTH, HEIGHT, { pad: 22, azimuth: 36 },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);
const slab = (plan, z, h, steps = 3, bevel = 0.5) => k.slabOf(plan, z, h, P, steps, bevel);
const cyl = (x, y, r, z, h, steps = 24, bevel = 0) => k.cylinder(x, y, r, z, h, P, steps, bevel);
const screws = (pts, z) => D(pts.map(([x, y]) => at([x, y, z])), { size: 0.45 });
const halo = (plan, z, h) => `<path class="iso-halo" d="${k.haloOf(plan, z, h, P)}"/>`;
const line = (a, b, tone = "lo", extra = "") => `<path class="iso-line" data-tone="${tone}" data-free="both" d="${k.segment(a, b, P)}"${extra}/>`;

function plate() {
  const out = [halo(PLATE, -PLATE_H - FOOT_H, PLATE_H)];
  const feet = k.corners(PLATE, 26).sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P));
  for (const [x, y] of feet) { out.push(S(cyl(x, y, 8, -PLATE_H - FOOT_H, 1.6, 28), { tone: "lo" })); out.push(S(cyl(x, y, 6, -PLATE_H - FOOT_H + 1.6, FOOT_H - 1.6, 28), { tone: "mid" })); }
  out.push(S(k.slabOf(PLATE, -PLATE_H, PLATE_H, P, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: "lo" }));
  const c = k.corners(PLATE, 11); out.push(L(c.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 16)).join(""), { tone: "lo" })); out.push(screws(c, 0));
  // engraved label plate, front left
  const lp = { x: -170, y: 56, w: 46, d: 12, r: 1.4 };
  out.push(S(slab(lp, 0, 0.8, 3, 0.2), { tone: "lo", crease: "none" }));
  out.push(screws([[lp.x + 3, lp.y + 6], [lp.x + lp.w - 3, lp.y + 6]], 0.8));
  out.push(`<path class="iso-line" data-tone="faint" data-free="both" d="${k.lineOnTop([lp.x + 7, lp.y + 4.2], [lp.x + 36, lp.y + 4.2], 0.8, P)}"/>`);
  out.push(`<path class="iso-line" data-tone="faint" data-free="both" d="${k.lineOnTop([lp.x + 7, lp.y + 7.8], [lp.x + 28, lp.y + 7.8], 0.8, P)}"/>`);
  return out.join("");
}
function post(x, y, h, w = 5) {
  return S(slab({ x: x - w - 2, y: y - w - 2, w: 2 * w + 4, d: 2 * w + 4, r: 1.5 }, 0, 2.4, 3, 0.4), { tone: "lo" }) +
    S(slab({ x: x - w / 2, y: y - w / 2, w, d: w, r: 0.8 }, 2.4, h - 2.4, 2, 0.3), { tone: "mid" }) + screws([[x - w, y - w], [x + w, y + w]], 2.4);
}
// level ladder at the back: two stiles, six rungs, a marker block that rides up and down
function ladder() {
  const { x, y, z0, rung } = LADDER, out = [];
  out.push(S(slab({ x: x - 16, y: y - 7, w: 32, d: 14, r: 2 }, 0, 4, 3, 0.5), { tone: "mid" }), screws(k.corners({ x: x - 16, y: y - 7, w: 32, d: 14 }, 2.4), 4));
  for (const sx of [x - 10, x + 10]) out.push(S(slab({ x: sx - 1.8, y: y - 1.8, w: 3.6, d: 3.6, r: 0.6 }, 4, z0 + rung * 6 + 2 - 4, 2, 0.2), { tone: "mid" }));
  for (let i = 1; i <= 6; i++) { const z = z0 + rung * i; out.push(S(slab({ x: x - 8.2, y: y - 1, w: 16.4, d: 2, r: 0.4 }, z - 0.8, 1.6, 2, 0.1), { tone: "lo" })); const [sx, sy] = at([x - 14, y, z]); out.push(`<g class="iso-dots" data-part="rungmark" data-tone="lo"><circle cx="${sx}" cy="${sy}" r="1.4"/></g>`); }
  out.push(S(cyl(x, y, 3.4, z0 + rung * 6 + 2, 3, 20, 0.3), { tone: "mid" }));
  return out.join("");
}
function marker() { // built at rung 0; moved with translateAlong
  const { x, y, z0 } = LADDER;
  return S(slab({ x: x - 9, y: y - 4, w: 18, d: 8, r: 1.2 }, z0 - 2, 4, 3, 0.4), { tone: "hi", lit: true }) + screws([[x - 6, y + 4], [x + 6, y + 4]], z0 + 2);
}
// credibility gauge: share of quests sealed by OpenProof, on a stand at the back
function dialStand() {
  const { x, y, z } = DIAL, out = [];
  const base = { x: x - 14, y: y - 10, w: 28, d: 20, r: 3 };
  out.push(halo(base, 0, 5), S(slab(base, 0, 5, 3, 0.6), { tone: "mid" }), screws(k.corners(base, 3), 5));
  out.push(S(cyl(x, y, 3, 5, z - 5, 20), { tone: "mid", crease: "none" }));
  out.push(S(cyl(x, y, 5, z - 3, 3, 24, 0.3), { tone: "mid" }));
  out.push(S(cyl(x + 9, y + 4, 2.4, 5, 3.4, 18), { tone: "mid" }), L(k.knurl(x + 9, y + 4, 2.4, 5, 8.4, 14, P), { tone: "lo" }));
  return out.join("");
}
function dial() {
  const { x, y, r, z, h } = DIAL, top = z + h, out = [S(cyl(x, y, r, z, h, 56, 0.8), { tone: "hi", crease: "lo" })];
  out.push(L(k.knurl(x, y, r, top - 2.4, top, 56, P, 0.3), { tone: "lo" }), L(k.ring(x, y, r - 2, top, P, 56), { tone: "lo" }));
  const t = k.radialTicks(x, y, r - 2.6, 20, 5, top, [1.2, 2.4], P, -Math.PI * 0.75, Math.PI * 1.5); out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
  // the 50% and 80% marks: the level-3 and level-5 credibility gates
  for (const f of [0.5, 0.8]) { const a = -Math.PI * 0.75 + Math.PI * 1.5 * f; out.push(`<path class="iso-line" data-tone="hi" data-free="both" d="${k.lineOnTop([x + Math.cos(a) * (r - 6), y + Math.sin(a) * (r - 6)], [x + Math.cos(a) * (r - 2.4), y + Math.sin(a) * (r - 2.4)], top, P)}" style="stroke-width:1.3"/>`); }
  out.push(L(k.ring(x, y, 1.4, top, P, 16), { tone: "mid" }));
  return out.join("");
}
const dialNeedle = (frac) => { const a = -Math.PI * 0.75 + Math.PI * 1.5 * frac; return k.lineOnTop([DIAL.x - Math.cos(a) * 2.4, DIAL.y - Math.sin(a) * 2.4], [DIAL.x + Math.cos(a) * (DIAL.r - 3.4), DIAL.y + Math.sin(a) * (DIAL.r - 3.4)], DIAL.z + DIAL.h + 0.2, P); };
// credit sight-glass: base, back half of the glass, the fluid column (lit), front rings and caps, scale plate with bands
function glassBack() {
  const { x, y, r, z0, h } = GLASS, out = [];
  out.push(halo({ x: x - 13, y: y - 13, w: 26, d: 26, r: 4 }, 0, 6), S(slab({ x: x - 13, y: y - 13, w: 26, d: 26, r: 4 }, 0, 6, 4, 0.6), { tone: "mid" }));
  out.push(screws(k.corners({ x: x - 13, y: y - 13, w: 26, d: 26 }, 3), 6));
  out.push(S(cyl(x, y, r + 2, 6, z0 - 6, 32, 0.4), { tone: "mid" }));
  out.push(L(k.sideArc(x, y, r, z0 + h * 0.5, P, 28), { tone: "faint" }));
  return out.join("");
}
function fluid() { return S(cyl(GLASS.x, GLASS.y, GLASS.r - 1.2, GLASS.z0, GLASS.h, 32), { tone: "hi", lit: true, crease: "none" }); }
function glassFront() {
  const { x, y, r, z0, h } = GLASS, out = [];
  out.push(L([z0, z0 + h].map((z) => k.ring(x, y, r, z, P, 32)).join(""), { tone: "mid" }));
  for (const [sx, sy] of [[-1, 0], [1, 0]]) { const a = at([x + sx * r * 0.7, y + sy, z0]), b = at([x + sx * r * 0.7, y + sy, z0 + h]); }
  out.push(`<path class="iso-line" data-tone="mid" data-free="both" d="${k.segment([x - r * 0.72, y + r * 0.69, z0], [x - r * 0.72, y + r * 0.69, z0 + h], P)}"/>`);
  out.push(`<path class="iso-line" data-tone="mid" data-free="both" d="${k.segment([x + r * 0.72, y - r * 0.69, z0], [x + r * 0.72, y - r * 0.69, z0 + h], P)}"/>`);
  out.push(S(cyl(x, y, r + 2, z0 + h, 4, 32, 0.5), { tone: "mid" }), L(k.knurl(x, y, r + 2, z0 + h, z0 + h + 4, 28, P), { tone: "lo" }));
  out.push(S(cyl(x, y, 2.4, z0 + h + 4, 3, 16), { tone: "mid" }));
  // scale plate: ticks every 10, bands at 70, 40, 15
  const sp = { x: SCALE.x - 1, y: SCALE.y - 6, w: 2.2, d: 12, r: 0.4 };
  out.push(S(slab(sp, 6, z0 + h - 6, 2, 0.2), { tone: "mid" }));
  const ticks = [], bands = [];
  for (let c = 0; c <= 100; c += 10) { const z = z0 + h * c / 100; ticks.push(k.segment([SCALE.x + 1.2, SCALE.y - 4, z], [SCALE.x + 1.2, SCALE.y + (c % 50 === 0 ? 4 : 1), z], P)); }
  for (const c of [70, 40, 15]) { const z = z0 + h * c / 100; bands.push(k.segment([SCALE.x + 1.2, SCALE.y - 6, z], [SCALE.x + 1.2, SCALE.y + 6, z], P)); }
  out.push(`<path class="iso-line" data-tone="lo" d="${ticks.join("")}"/>`, `<path class="iso-line" data-tone="hi" d="${bands.join("")}" style="stroke-width:1.4"/>`);
  return out.join("");
}
function float() { return S(cyl(GLASS.x, GLASS.y, GLASS.r - 0.8, 0, 2, 28, 0.3), { tone: "hi" }) + L(k.ring(GLASS.x, GLASS.y, GLASS.r + 3, 1, P, 28), { tone: "hi" }); }
// press: two posts behind the rail, beam above it, four stamp heads
function pressBack() { return post(PRESS.x0, RAIL_Y - 16, PRESS.beam, 6) + post(PRESS.x1, RAIL_Y - 16, PRESS.beam, 6); }
function pressBeam() {
  const out = [S(slab({ x: PRESS.x0 - 6, y: RAIL_Y - 20, w: PRESS.x1 - PRESS.x0 + 12, d: 28, r: 2 }, PRESS.beam, 6, 3, 0.6), { tone: "mid" })];
  out.push(screws([[PRESS.x0, RAIL_Y - 16], [PRESS.x1, RAIL_Y - 16]], PRESS.beam + 6));
  const t = k.topTicks(PRESS.x0 - 2, PRESS.x1 + 2, 3, 4, RAIL_Y + 4, PRESS.beam + 6, [1.4, 2.6], P);
  out.push(L(t.minor, { tone: "faint" }), L(t.major, { tone: "lo" }));
  return out.join("");
}
function head(i) { // built at z = 0 under the beam; moved with translateAlong
  const x = PRESS.heads[i], y = RAIL_Y, seal = i === 3, out = [];
  out.push(S(cyl(x, y, 1.4, 5, 30, 14), { tone: "mid", crease: "none" }));
  out.push(S(cyl(x, y, seal ? 4.4 : 3.6, 0, 5, 24, 0.3), seal ? { tone: "hi", lit: true } : { tone: "mid" }));
  out.push(S(cyl(x, y, seal ? 3.4 : 2.8, -1.2, 1.2, 20), { tone: "lo" }));
  return out.join("");
}
function railBed() {
  const out = [S(slab({ x: RAIL[0], y: RAIL_Y - 12, w: RAIL[1] - RAIL[0], d: 24, r: 2 }, 0, 2.4, 3, 0.4), { tone: "lo" })];
  for (const y of [RAIL_Y - 8, RAIL_Y + 6]) out.push(S(slab({ x: RAIL[0] + 2, y, w: RAIL[1] - RAIL[0] - 4, d: 2.4, r: 0.6 }, 2.4, 2, 2, 0.2), { tone: "mid" }));
  out.push(screws([RAIL[0] + 6, -130, -100, RAIL[1] - 6].map((x) => [x, RAIL_Y + 10]), 2.4));
  return out.join("");
}
function card() { // the returned quest card, the subject; seal ring appears when stamped
  const c = { x: -CARD.w / 2, y: RAIL_Y - CARD.d / 2, w: CARD.w, d: CARD.d, r: 1 }, out = [];
  out.push(S(slab({ x: c.x - 2, y: c.y - 2, w: c.w + 4, d: c.d + 4, r: 2 }, 2.4, CAR_TOP - 2.4, 3, 0.4), { tone: "mid" }));
  out.push(S(slab(c, CAR_TOP, 2, 2, 0.3), { tone: "hi" }));
  for (let i = 0; i < 4; i++) {
    const hx = PRESS.heads[i] - PRESS.x0 - (PRESS.x1 - PRESS.x0) / 2 + 0; // stamp marks line up with heads when the card is centred under the press
    out.push(`<g data-part="mark${i}" style="opacity:0">${L(k.ring(hx + (PRESS.x0 + PRESS.x1) / 2 - (PRESS.x0 + PRESS.x1) / 2, RAIL_Y, i === 3 ? 3.4 : 2.6, CARD_TOP + 0.05, P, 20), { tone: i === 3 ? "lit" : "mid" })}</g>`);
  }
  out.push(`<path class="iso-line" data-tone="faint" data-free="both" d="${k.lineOnTop([c.x + 3, c.y + 3.6], [c.x + 22, c.y + 3.6], CARD_TOP, P)}"/>`);
  return out.join("");
}
function hopper() {
  const { x, y } = HOP, out = [];
  out.push(S(slab({ x: x - 8, y: y - 12, w: 16, d: 24, r: 2 }, 0, 4, 3, 0.4), { tone: "mid" }));
  out.push(S(slab({ x: x - 7, y: y - 11, w: 14, d: 3, r: 0.6 }, 4, 10, 2, 0.2), { tone: "mid" }));
  return out.join("");
}
function hopperFront() { return S(slab({ x: HOP.x - 7, y: HOP.y + 8, w: 14, d: 3, r: 0.6 }, 4, 6, 2, 0.2), { tone: "mid" }); }
function rack() {
  const out = [], len = RACK.step * RACK.n + 6;
  const base = { x: RACK.x0 - 8, y: RACK.y - 9, w: len + 4, d: 18, r: 2 };
  out.push(halo(base, 0, 6), S(slab(base, 0, RACK.z, 3, 0.5), { tone: "mid" }));
  for (let i = 0; i < RACK.n; i++) { const x = RACK.x0 + i * RACK.step; out.push(L(k.ring(x, RACK.y, 5.2, RACK.z, P, 24), { tone: "lo" })); }
  const t = k.topTicks(RACK.x0 - 4, RACK.x0 + RACK.step * (RACK.n - 1) + 4, RACK.step, 5, RACK.y + 7, RACK.z, [1.2, 2], P);
  out.push(L(t.minor, { tone: "faint" }), L(t.major, { tone: "lo" }));
  // bin at the far end catches the oldest puck
  out.push(S(slab({ x: BIN.x - 6, y: BIN.y - 9, w: 12, d: 18, r: 1.6 }, 0, 3, 3, 0.3), { tone: "lo" }));
  return out.join("");
}
const PUCKS = 11;
function puck() { // drawn at the origin; tone set per frame by data-o
  return `<g class="pk-clean">${S(cyl(0, 0, 4.4, 0, 3.4, 24, 0.4), { tone: "hi" })}</g>` +
    `<g class="pk-back">${S(cyl(0, 0, 4.4, 0, 3.4, 24, 0.4), { tone: "mid" })}${L(k.ring(0, 0, 2.2, 3.4, P, 16), { tone: "lo" })}</g>` +
    `<g class="pk-escaped">${S(cyl(0, 0, 4.4, 0, 3.4, 24, 0.4), { tone: "lo" })}<path class="iso-line" data-tone="hi" d="${k.lineOnTop([-2.6, -2.6], [2.6, 2.6], 3.4, P)}${k.lineOnTop([-2.6, 2.6], [2.6, -2.6], 3.4, P)}"/></g>` +
    `<g class="pk-seal">${L(k.ring(0, 0, 3.2, 3.45, P, 20), { tone: "lit" })}</g>`;
}
// agent pedestal with a small figure, and the containment cage that drops over it
function pedestal() {
  const { x, y } = PED, out = [];
  out.push(halo({ x: x - 20, y: y - 20, w: 40, d: 40, r: 20 }, 0, 4));
  out.push(S(cyl(x, y, 19, 0, 3, 48, 0.5), { tone: "mid" }), L(k.ring(x, y, 16.4, 3, P, 48), { tone: "lo" }));
  const t = k.radialTicks(x, y, 17.6, 24, 6, 3, [0.9, 1.8], P); out.push(L(t.minor, { tone: "faint" }), L(t.major, { tone: "lo" }));
  out.push(S(cyl(x, y, 6, 3, 2, 24, 0.3), { tone: "mid" }));
  out.push(S(cyl(x, y, 3.4, 5, 10, 20, 0.4), { tone: "hi" }));     // body
  out.push(S(cyl(x, y, 4.4, 9.5, 2, 20, 0.3), { tone: "hi" }));     // harness belt
  out.push(S(cyl(x, y, 2.8, 15, 5.4, 20, 0.6), { tone: "hi" }));    // head
  out.push(D([at([x - 1.2, y + 2.6, 18]), at([x + 1.2, y + 2.6, 18])], { size: 0.35 }));
  return out.join("");
}
function cageBack() { // the far half: two back bars and the back of the rings; moved with the cage
  const { x, y } = PED, { r, h } = CAGE, out = [];
  for (const a of [Math.PI * 1.15, Math.PI * 1.5, Math.PI * 1.85]) out.push(line([x + Math.cos(a) * r, y + Math.sin(a) * r, 0], [x + Math.cos(a) * r, y + Math.sin(a) * r, h], "mid"));
  return out.join("");
}
function cageFront() {
  const { x, y } = PED, { r, h } = CAGE, out = [];
  out.push(L([0, h * 0.5, h].map((z) => k.ring(x, y, r, z, P, 40)).join(""), { tone: "mid" }));
  for (const a of [Math.PI * 0.15, Math.PI * 0.5, Math.PI * 0.85]) out.push(line([x + Math.cos(a) * r, y + Math.sin(a) * r, 0], [x + Math.cos(a) * r, y + Math.sin(a) * r, h], "hi"));
  out.push(S(cyl(x, y, r + 1.4, h, 2, 40, 0.4), { tone: "mid" }), S(cyl(x, y, 3, h + 2, 3, 16), { tone: "mid" }));
  out.push(S(cyl(x, y, 0.8, h + 5, 30, 10), { tone: "lo", crease: "none" }));   // the drop rod
  return out.join("");
}
function cageArm() { // fixed arm the cage hangs from
  const { x, y } = PED, top = CAGE.h + CAGE.up + 36;
  return post(x + 26, y - 18, top, 5) + S(slab({ x: x - 3, y: y - 21, w: 32, d: 6, r: 1 }, top, 4, 2, 0.3), { tone: "mid" }) + screws([[x, y - 18], [x + 26, y - 18]], top + 4);
}

const svg = k.figureSvg({
  width: WIDTH, height: HEIGHT,
  label: "Agent Company trust credits drawn as a bench instrument. A returned quest card rides under a proof press with three stamps and an OpenProof seal, drops into a hopper and leaves a puck in a ten-slot outcome rack. A tall sight-glass shows the agent's trust credits draining on incidents and refilling on sealed clean work, with bands at 70, 40 and 15. Under 15 a cage drops over the agent figure on its pedestal. A level ladder at the back shows the agent's level.",
  body: [
    plate(), dialStand(), dial(), `<path data-part="needle" class="iso-line" data-tone="lit" data-free="start" d="${dialNeedle(1)}" style="stroke-width:1.2"/>`, ladder(), `<g data-part="marker" transform="${k.translateAlong(P, [0, 0, LADDER.rung])}">${marker()}</g>`,
    glassBack(), `<g data-part="fluid" style="clip-path:url(#fluidclip)">${fluid()}</g>`, `<g data-part="float" transform="${k.translateAlong(P, [0, 0, GLASS.z0 + GLASS.h])}">${float()}</g>`, glassFront(),
    pressBack(), railBed(), hopper(), rack(),
    ...Array.from({ length: PUCKS }, (_, i) => `<g data-part="puck" data-i="${i}" style="display:none">${puck()}</g>`),
    `<g data-part="card" transform="${k.translateAlong(P, [RAIL[0] + 14, 0, 0])}">${card()}</g>`,
    hopperFront(),
    ...PRESS.heads.map((_, i) => `<g data-part="head" data-i="${i}" transform="${k.translateAlong(P, [0, 0, PRESS.rest])}">${head(i)}</g>`),
    pressBeam(), cageArm(), pedestal(),
    `<g data-part="cage" transform="${k.translateAlong(P, [0, 0, CAGE.up])}">${cageBack()}${cageFront()}</g>`,
  ],
});

const live = `
const P = ${JSON.stringify(P)}, RAIL = ${JSON.stringify(RAIL)}, PRESS = ${JSON.stringify(PRESS)}, HOP = ${JSON.stringify(HOP)}, RACK = ${JSON.stringify(RACK)}, BIN = ${JSON.stringify(BIN)};
const DIAL = ${JSON.stringify(DIAL)}, dialNeedle = ${dialNeedle.toString().replaceAll("k.lineOnTop", "lineOnTop")};
const GLASS = ${JSON.stringify(GLASS)}, CAGE = ${JSON.stringify(CAGE)}, LADDER = ${JSON.stringify(LADDER)}, CARD_TOP = ${CARD_TOP};
const stage = document.querySelector(".iso-stage"), svg = stage.querySelector("svg");
const $ = (s) => svg.querySelector(s), $$ = (s) => [...svg.querySelectorAll(s)];
const cardEl = $('[data-part="card"]'), heads = $$('[data-part="head"]'), pucks = $$('[data-part="puck"]'), fluidEl = $('[data-part="fluid"]'), floatEl = $('[data-part="float"]');
const cage = $('[data-part="cage"]'), markerEl = $('[data-part="marker"]'), marks = [0,1,2,3].map(i => $('[data-part="mark'+i+'"]')), rungs = $$('[data-part="rungmark"]');
const readout = document.querySelector("[data-readout]"), needleEl = $('[data-part="needle"]');
const fst = document.createElement("style"); fst.textContent = '[data-part="fluid"] path{fill:color-mix(in srgb,var(--anatomy-lit) 34%,transparent)}'; document.head.appendChild(fst);
const still = matchMedia("(prefers-reduced-motion: reduce)");
// fluid clip: a rectangle in screen space whose top follows the credit level
const ns = "http://www.w3.org/2000/svg", defs = document.createElementNS(ns, "defs"), cp = document.createElementNS(ns, "clipPath"), cr = document.createElementNS(ns, "path");
cp.id = "fluidclip"; cp.setAttribute("clipPathUnits", "userSpaceOnUse"); cp.appendChild(cr); defs.appendChild(cp); svg.prepend(defs);
// the rules, as in the game: start 100; sealed clean +8, self-reported +3; send-back -10, escaped -25; x1.5 at levels 3-4
// bands 70 / 40 / 15; under 15 contained (cage drops, one level lost); restored at 30 on probation
const SCRIPT = ["S","S","S","C","B","E","S","E","E","R","S","S"];
const STEP = 2.2, TOTAL = SCRIPT.length * STEP + 1.4;
const stake = (lv) => lv >= 5 ? 2 : lv >= 3 ? 1.5 : 1;
function replay(n, extra) {
  let c = 100, lv = 1, clean = 0, sealed = 0, total = 0, contained = false, prob = 0, ring = [];
  const seq = SCRIPT.slice(0, n); if (extra) seq.splice(Math.min(seq.length, extra.at), 0, ...extra.list.filter(x => x.at < n).map(x => "E"));
  for (const o of seq) {
    if (o === "R") { contained = false; c = 30; prob = 2; continue; }
    total++;
    if (o === "S" || o === "C") { c = Math.min(100, c + (o === "S" ? 8 : 3)); clean++; if (o === "S") { sealed++; if (prob) prob--; } }
    if (o === "B") c = Math.max(0, c - Math.round(10 * stake(lv)));
    if (o === "E") c = Math.max(0, c - Math.round(25 * stake(lv)));
    ring.unshift(o); ring = ring.slice(0, 10);
    if (c < 15 && !contained) { contained = true; lv = Math.max(1, lv - 1); }
    const cred = total ? sealed / total : 0, ok = !contained && c >= 40 && !prob;
    if (ok && lv < 2 && clean >= 1) lv = 2;
    if (ok && lv < 3 && clean >= 3 && cred >= 0.5) lv = 3;
  }
  const status = contained ? "contained" : c >= 70 && !prob ? "trusted" : c >= 40 && !prob ? "watch" : "probation";
  return { c, lv, ring, status, cred: total ? sealed / total : 1 };
}
const ease = (t) => t<=0?0:t>=1?1:t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
let clock = 0, frame = 0, last = 0, visible = false, injected = [];
const cur = { cred: 1, card: RAIL[0] + 14, heads: [PRESS.rest,PRESS.rest,PRESS.rest,PRESS.rest], c: 100, cage: CAGE.up, lv: 1, shift: 0 };
const WORDS = { S: "sealed ◆ +8", C: "self-reported +3", B: "sent back", E: "escaped defect", R: "restored · 30 · probation" };
function want(t) {
  const i = Math.min(SCRIPT.length - 1, Math.floor(t / STEP)), u = (t - i * STEP) / STEP, o = SCRIPT[i];
  const done = t >= SCRIPT.length * STEP;
  const before = replay(i), after = replay(i + 1);
  const w = { cred: before.cred, card: RAIL[0] + 14, heads: [PRESS.rest,PRESS.rest,PRESS.rest,PRESS.rest], marks: [0,0,0,0], cardOn: 1, shift: 0, ring: before.ring, c: before.c, lv: before.lv, status: before.status, text: "" };
  const mid = (PRESS.x0 + PRESS.x1) / 2, sealOK = o === "S";
  if (done) { w.cred = after.cred; w.cardOn = 0; w.ring = after.ring; w.c = after.c; w.lv = after.lv; w.status = after.status; w.text = "window rolls on · starting again"; return w; }
  if (o === "R") { w.cardOn = 0; const v = ease(Math.min(1, u * 2)); w.c = before.c + (after.c - before.c) * v; w.lv = after.lv; w.status = u > 0.5 ? after.status : before.status; w.text = WORDS.R; return w; }
  if (u < 0.22) { w.card = RAIL[0] + 14 + (mid - RAIL[0] - 14) * ease(u / 0.22); w.text = "quest " + String(i + 1).padStart(3, "0") + " returns"; }
  else if (u < 0.62) { w.card = mid; const v = (u - 0.22) / 0.4; for (let h = 0; h < 4; h++) { const a = h * 0.22, s = v > a && v < a + 0.28 ? Math.sin((v - a) / 0.28 * Math.PI) : 0; if (h === 3 && !sealOK) continue; if (o === "B" || o === "E") { if (h > 0) continue; } w.heads[h] = PRESS.rest - (PRESS.rest - CARD_TOP) * s; w.marks[h] = v > a + 0.14 ? 1 : 0; }
    w.text = o === "S" ? "PR · tests · verdict · ◆ seal" : o === "C" ? "PR · tests · verdict · no seal" : o === "B" ? "verdict: changes needed" : "defect escaped"; }
  else if (u < 0.78) { w.card = mid + (HOP.x - mid) * ease((u - 0.62) / 0.16); for (let h = 0; h < 4; h++) w.marks[h] = (h === 3 ? sealOK : (o === "S" || o === "C" || h === 0)) ? 1 : 0; w.text = WORDS[o]; }
  else { w.cred = after.cred; w.cardOn = 0; w.shift = ease((u - 0.78) / 0.22); w.ring = after.ring; w.c = before.c + (after.c - before.c) * w.shift; w.lv = after.lv; w.status = after.status;
    w.text = (o === "B" || o === "E" ? WORDS[o] + " " + (after.c - before.c) : WORDS[o]) + " → " + Math.round(after.c) + " · " + after.status; }
  return w;
}
function draw(w) {
  cardEl.setAttribute("transform", translateAlong(P, [cur.card, 0, 0])); cardEl.style.opacity = w.cardOn;
  heads.forEach((el, i) => el.setAttribute("transform", translateAlong(P, [0, 0, cur.heads[i]])));
  marks.forEach((el, i) => el.style.opacity = w.marks[i]);
  // pucks: index 0 is the newest; during a shift the new one drops in at the left and the oldest slides into the bin
  pucks.forEach((el, i) => {
    const o = w.ring[i]; if (!o || i >= 10) { el.style.display = "none"; return; }
    const slot = RACK.x0 + i * RACK.step - (1 - w.shift) * RACK.step * (w.shift > 0 ? 1 : 0) * (i === 0 ? 0 : 1);
    let x = slot, z = RACK.z; if (i === 0 && w.shift > 0) { x = RACK.x0 - (1 - w.shift) * (RACK.x0 - HOP.x); z = RACK.z + Math.sin(w.shift * Math.PI) * 6; }
    el.style.display = ""; el.setAttribute("transform", translateAlong(P, [x, RACK.y, z]));
    el.querySelector(".pk-clean").style.display = o === "S" || o === "C" ? "" : "none";
    el.querySelector(".pk-back").style.display = o === "B" ? "" : "none";
    el.querySelector(".pk-escaped").style.display = o === "E" ? "" : "none";
    el.querySelector(".pk-seal").style.display = o === "S" ? "" : "none";
  });
  const z = GLASS.z0 + GLASS.h * Math.max(0, Math.min(100, cur.c)) / 100;
  floatEl.setAttribute("transform", translateAlong(P, [0, 0, z]));
  const [, top] = iso([GLASS.x, GLASS.y, z], P), [, bot] = iso([GLASS.x, GLASS.y, GLASS.z0 - 6], P), [lx] = iso([GLASS.x - 20, GLASS.y, 0], P), [rx] = iso([GLASS.x + 20, GLASS.y, 0], P);
  const [cx] = iso([GLASS.x, GLASS.y, 0], P);
  cr.setAttribute("d", "M" + (cx - 40) + " " + top + "H" + (cx + 40) + "V" + (bot + 20) + "H" + (cx - 40) + "Z");
  cage.setAttribute("transform", translateAlong(P, [0, 0, cur.cage]));
  needleEl.setAttribute("d", dialNeedle(cur.cred));
  markerEl.setAttribute("transform", translateAlong(P, [0, 0, LADDER.rung * (cur.lv - 1)]));
  rungs.forEach((el, i) => { const on = i < Math.round(cur.lv); el.dataset.tone = on ? "hi" : "lo"; el.firstChild.style.fill = on ? "var(--anatomy-lit)" : ""; });
  const text = w.text + " · L" + Math.round(w.lv);
  if (readout.textContent !== text) readout.textContent = text;
}
function tick(now) {
  const dt = last ? Math.min((now - last) / 1000, 1/30) : 1/60; last = now;
  clock += dt; if (clock >= TOTAL) clock -= TOTAL;
  const w = want(clock), k2 = still.matches ? 1 : 1 - Math.exp(-dt / 0.06);
  cur.card += (w.card - cur.card) * k2; for (let i = 0; i < 4; i++) cur.heads[i] += (w.heads[i] - cur.heads[i]) * k2;
  cur.cred += (w.cred - cur.cred) * (still.matches ? 1 : 1 - Math.exp(-dt / 0.2)); cur.c += (w.c - cur.c) * (still.matches ? 1 : 1 - Math.exp(-dt / 0.18)); cur.lv += (w.lv - cur.lv) * (still.matches ? 1 : 1 - Math.exp(-dt / 0.25));
  const cageWant = w.status === "contained" ? 0 : CAGE.up; cur.cage += (cageWant - cur.cage) * (still.matches ? 1 : 1 - Math.exp(-dt / (cageWant === 0 ? 0.08 : 0.3)));
  draw(w);
  frame = visible ? requestAnimationFrame(tick) : 0;
}
const run = () => { if (!frame && visible) { last = 0; frame = requestAnimationFrame(tick); } };
${FILM ? "" : `new IntersectionObserver((e) => { visible = e[e.length-1].isIntersecting; if (visible) run(); }, { rootMargin: \"120px 0px\" }).observe(stage);`}
function jump() { clock = 7 * STEP + 0.01; run(); }   // jump to the next escaped defect
stage.addEventListener("click", jump);
stage.addEventListener("keydown", (e) => { if (e.key === "e" || e.key === "E" || e.key === "Enter" || e.key === " ") { e.preventDefault(); jump(); } });
if (still.matches) clock = 8 * STEP + 2;
{ const w = want(clock); Object.assign(cur, { cred: w.cred, card: w.card, heads: w.heads.slice(), c: w.c, lv: w.lv, cage: w.status === "contained" ? 0 : CAGE.up }); draw(w); }
${FILM ? `window.figAt = (t) => { clock = Math.max(0, Math.min(TOTAL - 0.01, t)); const w = want(clock); Object.assign(cur, { cred: w.cred, card: w.card, heads: w.heads.slice(), c: w.c, lv: w.lv, cage: w.status === "contained" ? 0 : CAGE.up }); draw(w); }; window.FIG_TOTAL = TOTAL; window.FIG_STEP = STEP; visible = false;` : ""}
`;

const body = k.plateHtml({
  fig: "Fig 3",
  title: "Trust credits",
  hint: "Click: escaped defect",
  readout: "quest 001 returns · level 1",
  keys: [
    { mark: "lit", label: "The OpenProof seal, the credit column, the credibility needle and the level marker: what proof moves" },
    { mark: "raised", label: "Proof press, outcome rack, sight-glass, credibility gauge, containment cage, level ladder" },
  ],
  caption:
    "Trust credits as a bench instrument. Each returned quest passes under the proof press: pull request, tests and verdict, and the OpenProof seal when there is checkable evidence. It leaves a puck in a ten-slot rack, the newest pushing the oldest off the end. Sealed clean work refills the credit column; a send-back or an escaped defect drains it, by more at higher levels. Below 15 credits the cage drops over the agent and it loses a level; after review it is restored at 30 credits, on probation. The credibility gauge reads the share of quests sealed by OpenProof, marked at the 50% and 80% gates; the level marker climbs only when there are enough clean quests and enough sealed proof.",
  body: `<div class="iso-stage" tabindex="0" role="button" aria-label="Trust credits instrument. Click, or press E, Enter or Space, to jump to an escaped defect">${svg}</div>`,
});
const name = FILM ? "trust-credits-anatomy-film.html" : theme === "light" ? "trust-credits-anatomy-light.html" : "trust-credits-anatomy.html";
writeFileSync(join(HERE, name), k.pageHtml({ title: "Agent Company: trust credits", theme, body, script: kitScript() + live }));
console.log("wrote", name);
