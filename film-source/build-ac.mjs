import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./skill/kit/iso-kit.mjs";
import { kitScript } from "./skill/scripts/inline-kit.mjs";

// Agent Company as a dispatch line. One mission card rides a single rail through every station in order:
//   inbox rack → builder press (two strikes: failing tests, then the fix) → challenger probe → evaluator gauge →
//   owner's desk (only the owner's lever brings the merge stamp down) → done tray.
// One coordinator lamp on the gantry follows the card (exactly one coordinator). The watch tower lamp blinks when a
// mission lands in the tray. The readiness dial on the console climbs as each check is passed.

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes("--light") ? "light" : "dark";
const FILM = process.argv.includes("--film");
const WIDTH = 660, HEIGHT = 440;

const PLATE = { x: -176, y: -74, w: 352, d: 148, r: 9 };
const PLATE_H = 12, FOOT_H = 5;
const ST = { inbox: -132, build: -74, challenge: -22, evaluate: 30, owner: 84, done: 138 };
const RAIL = [-150, 154];
const CAR = 26, CAR_Z = 3, CAR_TOP = 7, CARD_H = 2.2, CARD_TOP = CAR_TOP + CARD_H;
const GANTRY = { y: -40, z: 78 };
const PRESS = { x: ST.build, beam: 58, rest: 30, ramLen: 18 };
const DIAL = { x: ST.evaluate, y: 0, r: 12, z: 44, h: 7 };
const DESK = { x: ST.owner - 18, y: 26, w: 36, d: 26, r: 2 };
const TOWER = [160, -58];
const CONSOLE = { x: -168, y: 34, w: 64, d: 32, r: 3 };
const TRAY = { x: ST.done - 16, y: -16, w: 32, d: 32, r: 2 };

const P = k.fitProjection(
  [...k.boxCorners(PLATE, -PLATE_H - FOOT_H, 0), [TOWER[0], TOWER[1], 104], [RAIL[0], GANTRY.y, GANTRY.z + 8], [RAIL[1], GANTRY.y, GANTRY.z + 8]],
  WIDTH, HEIGHT, { pad: 24, azimuth: 38 },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);
const slab = (plan, z, h, steps = 3, bevel = 0.5) => k.slabOf(plan, z, h, P, steps, bevel);
const cyl = (x, y, r, z, h, steps = 24, bevel = 0) => k.cylinder(x, y, r, z, h, P, steps, bevel);
const screws = (pts, z) => D(pts.map(([x, y]) => at([x, y, z])), { size: 0.45 });
const ruled = (plan, z, rows = 3) => {
  const out = [S(slab(plan, z, 0.7, 2, 0.2), { tone: "lo", crease: "none" })];
  for (let i = 0; i < rows; i++) { const y = plan.y + 2.4 + i * ((plan.d - 4.8) / Math.max(1, rows - 1)); out.push(`<path class="iso-line" data-tone="faint" data-free="both" d="${k.lineOnTop([plan.x + 2.4, y], [plan.x + plan.w * (i === rows - 1 ? 0.5 : 0.82), y], z + 0.7, P)}"/>`); }
  return out.join("");
};
const halo = (plan, z, h) => `<path class="iso-halo" d="${k.haloOf(plan, z, h, P)}"/>`;

function plate() {
  const out = [halo(PLATE, -PLATE_H - FOOT_H, PLATE_H)];
  const feet = k.corners(PLATE, 26).sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P));
  for (const [x, y] of feet) { out.push(S(cyl(x, y, 8, -PLATE_H - FOOT_H, 1.6, 28), { tone: "lo" })); out.push(S(cyl(x, y, 6, -PLATE_H - FOOT_H + 1.6, FOOT_H - 1.6, 28), { tone: "mid" })); }
  out.push(S(k.slabOf(PLATE, -PLATE_H, PLATE_H, P, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: "lo" }));
  const c = k.corners(PLATE, 11); out.push(L(c.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 16)).join(""), { tone: "lo" })); out.push(screws(c, 0));
  // ruler strip along the front edge of the rail: the stations' positions
  const strip = { x: RAIL[0], y: 16, w: RAIL[1] - RAIL[0], d: 6, r: 1 };
  out.push(S(slab(strip, 0, 0.6, 3, 0), { tone: "lo", crease: "none" }));
  const t = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 4, 5, strip.y + 0.6, 0.6, [1.8, 3.4], P);
  out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
  return out.join("");
}
function stationMarks() {
  return Object.values(ST).map((x, i) => { const [sx, sy] = at([x, 19, 0.6]); return `<g class="iso-dots" data-part="mark" data-tone="lo"><circle cx="${sx}" cy="${sy}" r="1.8"/></g>`; }).join("");
}
function post(x, y, h, w = 5) {
  return S(slab({ x: x - w - 2, y: y - w - 2, w: 2 * w + 4, d: 2 * w + 4, r: 1.5 }, 0, 2.4, 3, 0.4), { tone: "lo" }) +
    S(slab({ x: x - w / 2, y: y - w / 2, w, d: w, r: 0.8 }, 2.4, h - 2.4, 2, 0.3), { tone: "mid" }) + screws([[x - w, y - w], [x + w, y + w]], 2.4);
}
function gantryBack() {
  return post(RAIL[0] + 4, GANTRY.y, GANTRY.z) + post(RAIL[1] - 4, GANTRY.y, GANTRY.z);
}
function gantryBeam() {
  const out = [S(slab({ x: RAIL[0] - 2, y: GANTRY.y - 4, w: RAIL[1] - RAIL[0] + 4, d: 8, r: 1.2 }, GANTRY.z, 5, 3, 0.5), { tone: "mid" })];
  out.push(screws([[RAIL[0] + 4, GANTRY.y], [RAIL[1] - 4, GANTRY.y]], GANTRY.z + 5));
  const t = k.topTicks(RAIL[0] + 6, RAIL[1] - 6, 6, 5, GANTRY.y - 3.4, GANTRY.z + 5, [1.4, 2.6], P);
  out.push(L(t.minor, { tone: "faint" }), L(t.major, { tone: "lo" }));
  return out.join("");
}
// the coordinator: one trolley with a lamp, riding the gantry above the card
function coordinator() {
  const out = [S(slab({ x: -8, y: GANTRY.y - 6, w: 16, d: 12, r: 1.5 }, GANTRY.z - 7, 7, 3, 0.5), { tone: "mid" })];
  out.push(S(cyl(0, GANTRY.y, 2, GANTRY.z - 14, 7, 16), { tone: "mid", crease: "none" }));
  out.push(S(cyl(0, GANTRY.y, 4.6, GANTRY.z - 18, 4, 24, 0.3), { tone: "hi", lit: true }));
  out.push(S(cyl(0, GANTRY.y, 3, GANTRY.z - 19.6, 1.6, 20), { tone: "hi" }));
  out.push(D([at([-5, GANTRY.y + 6, GANTRY.z - 3]), at([5, GANTRY.y + 6, GANTRY.z - 3])], { size: 0.4 }));
  return out.join("");
}
function rails() {
  const out = [];
  for (const y of [-10, 8]) { out.push(S(slab({ x: RAIL[0], y, w: RAIL[1] - RAIL[0], d: 3.5, r: 1 }, 0, 3, 3, 0.4), { tone: "mid" })); out.push(screws([RAIL[0] + 6, -60, 0, 60, RAIL[1] - 6].map((x) => [x, y + 1.75]), 3)); }
  for (const x of [RAIL[0] - 5, RAIL[1]]) { out.push(S(slab({ x, y: -13, w: 5, d: 27, r: 1.2 }, 0, 7, 3, 0.5), { tone: "mid" })); out.push(screws([[x + 2.5, -9], [x + 2.5, 10]], 7)); }
  return out.join("");
}
function inbox() {
  const x = ST.inbox, out = [];
  const base = { x: x - 15, y: -40, w: 30, d: 22, r: 2 };
  out.push(halo(base, 0, 10), S(slab(base, 0, 10, 3, 0.6), { tone: "mid" }));
  for (let i = 0; i < 5; i++) out.push(S(slab({ x: x - 11 + i * 0.6, y: -37 + i * 0.4, w: 22, d: 16, r: 0.8 }, 10 + i * 2.4, 1.4, 2, 0.2), { tone: i === 4 ? "hi" : "mid", crease: "none" }));
  out.push(S(slab({ x: x - 15, y: -43, w: 30, d: 3, r: 0.6 }, 0, 26, 2, 0.3), { tone: "mid" }));   // back wall of the rack
  out.push(ruled({ x: x - 10, y: -42.6, w: 20, d: 2.2, r: 0.4 }, 26));
  return out.join("");
}
function pressBack() { return post(PRESS.x, -26, PRESS.beam, 6); }
function pressFront() {
  const x = PRESS.x, out = [post(x, 26, PRESS.beam, 6)];
  out.push(S(slab({ x: x - 7, y: -33, w: 14, d: 66, r: 2 }, PRESS.beam, 7, 3, 0.6), { tone: "mid" }));
  out.push(screws([[x - 3.6, -28], [x + 3.6, -28], [x - 3.6, 28], [x + 3.6, 28]], PRESS.beam + 7));
  out.push(S(cyl(x, 0, 7, PRESS.beam + 7, 3, 32, 0.5), { tone: "mid" })); out.push(L(k.knurl(x, 0, 7, PRESS.beam + 7, PRESS.beam + 10, 28, P), { tone: "lo" }));
  return out.join("");
}
function ram() {
  const x = PRESS.x;
  return S(cyl(x, 0, 2.2, PRESS.ramLen, 40, 20), { tone: "mid", crease: "none" }) + S(cyl(x, 0, 5.4, 0, PRESS.ramLen, 32, 0.4), { tone: "mid" }) +
    L([6, 12].map((z) => k.sideArc(x, 0, 5.4, z, P, 20)).join(""), { tone: "faint" }) + S(cyl(x, 0, 6.6, 0, 1.8, 32), { tone: "lo" });
}
function probeBase() {
  const x = ST.challenge, out = [];
  out.push(S(slab({ x: x - 8, y: -44, w: 16, d: 14, r: 2 }, 0, 9, 3, 0.6), { tone: "mid" }));
  out.push(S(cyl(x, -37, 2.6, 9, 12, 20), { tone: "mid", crease: "none" }));
  out.push(S(slab({ x: x - 5, y: -41, w: 10, d: 8, r: 1.2 }, 21, 5, 3, 0.4), { tone: "mid" }));
  out.push(S(cyl(x + 6, -37, 2.4, 22, 3.6, 18), { tone: "mid" })); out.push(L(k.knurl(x + 6, -37, 2.4, 22, 25.6, 14, P), { tone: "lo" }));
  return out.join("");
}
function probeArm() { // slides along +y toward the card; built at rest, moved with translateAlong
  const x = ST.challenge, out = [];
  out.push(S(slab({ x: x - 1.6, y: -33, w: 3.2, d: 20, r: 0.8 }, 22.4, 2.4, 2, 0.2), { tone: "mid" }));
  out.push(S(slab({ x: x - 1.2, y: -14, w: 2.4, d: 2.4, r: 0.6 }, 12, 12.8, 2, 0.2), { tone: "mid" }));
  out.push(S(cyl(x, -12.8, 1.4, 9.6, 2.6, 14), { tone: "hi" }));
  return out.join("");
}
function gaugeBack() {
  const x = DIAL.x, y = -36, out = [];
  out.push(S(slab({ x: x - 7, y: y - 7, w: 14, d: 14, r: 2 }, 0, 9, 4, 0.6), { tone: "mid" }));
  out.push(S(cyl(x, y, 2.6, 9, DIAL.z, 20), { tone: "mid", crease: "none" }));
  out.push(S(slab({ x: x - 2.2, y, w: 4.4, d: 36 - DIAL.r + 2, r: 1 }, DIAL.z + 3, 3.6, 2, 0.3), { tone: "mid" }));
  return out.join("");
}
function plunger() { return S(cyl(DIAL.x, 0, 1.2, 0, 36, 16), { tone: "hi", crease: "none" }) + S(cyl(DIAL.x, 0, 2.2, 0, 1.8, 16), { tone: "hi" }); }
function gauge() {
  const { x, y, r, z, h } = DIAL, top = z + h, out = [S(cyl(x, y, r, z, h, 56, 0.8), { tone: "hi", crease: "lo" })];
  out.push(L(k.knurl(x, y, r, top - 2.6, top, 56, P, 0.3), { tone: "lo" }), L(k.ring(x, y, r - 1.8, top, P, 56), { tone: "lo" }));
  const t = k.radialTicks(x, y, r - 2.4, 40, 5, top, [1.1, 2.2], P); out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
  out.push(L(k.ring(x, y, 1.3, top, P, 16), { tone: "mid" }));
  return out.join("");
}
const needleAt = (cx, cy, r, z, turn) => { const a = turn * Math.PI * 2; return k.lineOnTop([cx - Math.sin(a) * 2.4, cy + Math.cos(a) * 2.4], [cx + Math.sin(a) * (r - 3.2), cy - Math.cos(a) * (r - 3.2)], z + 0.2, P); };

// the owner's desk: a key lock and a lever; the stamp arm swings down only when the lever is pulled
function desk() {
  const out = [halo(DESK, 0, 16), S(slab(DESK, 0, 16, 3, 0.8), { tone: "mid" })];
  out.push(L(k.planOutline(k.insetPlan(DESK, 2.6), 16, P, 2), { tone: "faint" }));
  out.push(screws(k.corners(DESK, 2.2), 16));
  out.push(S(cyl(DESK.x + 9, DESK.y + 17, 3.6, 16, 2, 24, 0.3), { tone: "hi" }), L(k.ring(DESK.x + 9, DESK.y + 17, 2.2, 18, P, 20), { tone: "lo" }));
  out.push(S(slab({ x: DESK.x + 20, y: DESK.y + 9, w: 10, d: 6, r: 1 }, 16, 3, 2, 0.3), { tone: "lo" }));    // lever quadrant
  out.push(ruled({ x: DESK.x + 3, y: DESK.y + 3, w: 14, d: 6, r: 0.6 }, 16, 2));
  return out.join("");
}
const leverAt = (pull) => { const a = (-40 + 80 * pull) * Math.PI / 180, bx = DESK.x + 25, by = DESK.y + 12, bz = 19; return k.segment([bx, by, bz], [bx + Math.sin(a) * 2, by + Math.sin(a) * 6, bz + Math.cos(a) * 14], P); };
function stampPost() { return post(ST.owner, 22, 44, 5); }
function stampHead() { // hangs from the arm over the card; moved down with translateAlong
  const x = ST.owner, out = [];
  out.push(S(cyl(x, 0, 1.8, 6, 24, 16), { tone: "mid", crease: "none" }));
  out.push(S(slab({ x: x - 7, y: -6, w: 14, d: 12, r: 1.6 }, 0, 6, 3, 0.5), { tone: "mid" }));
  out.push(S(slab({ x: x - 6, y: -5, w: 12, d: 10, r: 1.2 }, -1.6, 1.6, 2, 0.2), { tone: "lo" }));
  return out.join("");
}
function stampArm() { return S(slab({ x: ST.owner - 2.4, y: -4, w: 4.8, d: 26, r: 1 }, 44, 4, 2, 0.3), { tone: "mid" }) + screws([[ST.owner, 20]], 48); }
function tray() {
  const out = [halo(TRAY, 0, 8), S(slab(TRAY, 0, 3, 3, 0.5), { tone: "mid" })];
  out.push(S(slab({ x: TRAY.x, y: TRAY.y, w: TRAY.w, d: 3, r: 0.6 }, 3, 8, 2, 0.3), { tone: "mid" }));
  out.push(S(slab({ x: TRAY.x, y: TRAY.y, w: 3, d: TRAY.d, r: 0.6 }, 3, 8, 2, 0.3), { tone: "mid" }));
  return out.join("");
}
function trayFront() {
  return S(slab({ x: TRAY.x + TRAY.w - 3, y: TRAY.y, w: 3, d: TRAY.d, r: 0.6 }, 3, 5, 2, 0.3), { tone: "mid" }) +
    S(slab({ x: TRAY.x, y: TRAY.y + TRAY.d - 3, w: TRAY.w, d: 3, r: 0.6 }, 3, 5, 2, 0.3), { tone: "mid" });
}
const DONE_MAX = 6;
function doneStack() { return Array.from({ length: DONE_MAX }, (_, i) => `<g data-part="donecard" data-i="${i}" style="display:none">${S(slab({ x: TRAY.x + 5 + (i % 2) * 0.6, y: TRAY.y + 6, w: 22, d: 20, r: 0.8 }, 3 + i * 1.6, 1.2, 2, 0.2), { tone: "mid", crease: "none" })}</g>`).join(""); }
function tower() {
  const [x, y] = TOWER, out = [post(x, y, 90, 5)];
  out.push(S(cyl(x, y, 6, 90, 3, 28, 0.4), { tone: "mid" }));
  out.push(`<g data-part="watch">${S(cyl(x, y, 4.4, 93, 6, 24, 0.3), { tone: "hi" })}</g>`);
  out.push(S(cyl(x, y, 5.4, 99, 2, 24, 0.3), { tone: "mid" }));
  return out.join("");
}
function consoleBox() {
  const out = [halo(CONSOLE, 0, 12), S(slab(CONSOLE, 0, 12, 3, 0.8), { tone: "mid" })];
  out.push(screws(k.corners(CONSOLE, 2.4), 12));
  const cx = CONSOLE.x + 20, cy = CONSOLE.y + 16;
  out.push(S(cyl(cx, cy, 12, 12, 2.4, 48, 0.5), { tone: "hi", crease: "lo" }), L(k.ring(cx, cy, 10.4, 14.4, P, 48), { tone: "lo" }));
  const t = k.radialTicks(cx, cy, 9.8, 20, 5, 14.4, [1.1, 2.2], P, -Math.PI * 0.75, Math.PI * 1.5); out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
  for (let i = 0; i < 8; i++) { const lx = CONSOLE.x + 40 + (i % 4) * 5.6, ly = CONSOLE.y + 9 + Math.floor(i / 4) * 10; out.push(L(k.ring(lx, ly, 2, 12, P, 14), { tone: "lo" })); const [sx, sy] = at([lx, ly, 12]); out.push(`<g class="iso-dots" data-part="role" data-tone="lo"><circle cx="${sx}" cy="${sy}" r="1.3"/></g>`); }
  return out.join("");
}
const dialNeedle = (frac) => { const cx = CONSOLE.x + 20, cy = CONSOLE.y + 16, a = -Math.PI * 0.75 + Math.PI * 1.5 * frac; return k.lineOnTop([cx - Math.cos(a) * 2, cy - Math.sin(a) * 2], [cx + Math.cos(a) * 8.6, cy + Math.sin(a) * 8.6], 14.6, P); };

function carriage() {
  const plan = { x: -CAR / 2, y: -CAR / 2 + 1, w: CAR, d: CAR - 2, r: 3 };
  const out = [`<path class="iso-halo" d="${k.haloOf(k.insetPlan(plan, 3), CAR_Z, 0.1, P)}" style="filter:blur(4px)"/>`];
  out.push(S(slab(plan, CAR_Z, CAR_TOP - CAR_Z, 5, 0.6), { tone: "mid" }));
  out.push(screws(k.corners(plan, 3), CAR_TOP));
  return out.join("");
}
function card() { // the mission card: the one lit part
  const c = { x: -10, y: -8, w: 20, d: 16, r: 1 };
  return S(slab(c, CAR_TOP, CARD_H, 2, 0.3), { tone: "hi", lit: true }) +
    `<path class="iso-line" data-tone="faint" data-free="both" d="${k.lineOnTop([c.x + 2.6, c.y + 4], [c.x + 15, c.y + 4], CARD_TOP, P)}"/>` +
    `<path class="iso-line" data-tone="faint" data-free="both" d="${k.lineOnTop([c.x + 2.6, c.y + 8], [c.x + 12, c.y + 8], CARD_TOP, P)}"/>` +
    `<g data-part="seal" style="opacity:0">${L(k.ring(4.6, 3.6, 3.2, CARD_TOP + 0.05, P, 24), { tone: "lit" })}${L(k.ring(4.6, 3.6, 1.6, CARD_TOP + 0.05, P, 16), { tone: "lit" })}</g>`;
}

const svg = k.figureSvg({
  width: WIDTH, height: HEIGHT,
  label: "Agent Company drawn as a dispatch line. A mission card rides one rail from an inbox rack through a builder press, a challenger probe and an evaluator dial gauge to the owner's desk, where only the owner's lever brings the merge stamp down, and on into the done tray. One coordinator lamp on an overhead gantry follows the card; a watch-tower lamp blinks when a mission lands; a readiness dial on the console climbs as each station passes.",
  body: [
    plate(), stationMarks(), gantryBack(), tower(), inbox(), probeBase(), gaugeBack(), pressBack(), rails(), tray(), doneStack(),
    `<g data-part="carriage" transform="${k.translateAlong(P, [ST.inbox, 0, 0])}">${carriage()}<g data-part="card">${card()}</g></g>`,
    `<g data-part="probe">${probeArm()}</g>`,
    `<g data-part="plunger" transform="${k.translateAlong(P, [0, 0, 16])}">${plunger()}</g>`,
    `<g data-part="ram" transform="${k.translateAlong(P, [0, 0, PRESS.rest])}">${ram()}</g>`,
    `<g data-part="stamp" transform="${k.translateAlong(P, [0, 0, 22])}">${stampHead()}</g>`,
    stampArm(), pressFront(), gauge(),
    `<path data-part="needle" class="iso-line" data-tone="lit" data-free="start" d="${needleAt(DIAL.x, DIAL.y, DIAL.r, DIAL.z + DIAL.h, 0)}" style="stroke-width:1.1"/>`,
    trayFront(), stampPost(), desk(),
    `<path data-part="lever" class="iso-line" data-tone="hi" d="${leverAt(0)}" style="stroke-width:2.2;stroke-linecap:round"/>`,
    gantryBeam(), `<g data-part="coord" transform="${k.translateAlong(P, [ST.inbox, 0, 0])}">${coordinator()}</g>`,
    consoleBox(), `<path data-part="dial" class="iso-line" data-tone="lit" data-free="start" d="${dialNeedle(0)}" style="stroke-width:1.2"/>`,
  ],
});

const live = `
const P = ${JSON.stringify(P)}, ST = ${JSON.stringify(ST)}, DIAL = ${JSON.stringify(DIAL)}, DESK = ${JSON.stringify(DESK)}, CONSOLE = ${JSON.stringify(CONSOLE)}, TRAY = ${JSON.stringify(TRAY)};
const PRESS = ${JSON.stringify(PRESS)}, CARD_TOP = ${CARD_TOP}, DONE_MAX = ${DONE_MAX};
const needleAt = ${needleAt.toString().replaceAll("k.lineOnTop", "lineOnTop")};
const leverAt = ${leverAt.toString().replaceAll("k.segment", "segment")};
const dialNeedle = ${dialNeedle.toString().replaceAll("k.lineOnTop", "lineOnTop")};
const stage = document.querySelector(".iso-stage"), svg = stage.querySelector("svg");
const $ = (s) => svg.querySelector(s), $$ = (s) => [...svg.querySelectorAll(s)];
const car = $('[data-part="carriage"]'), cardEl = $('[data-part="card"]'), seal = $('[data-part="seal"]'), coord = $('[data-part="coord"]');
const ramEl = $('[data-part="ram"]'), probe = $('[data-part="probe"]'), plungerEl = $('[data-part="plunger"]'), needle = $('[data-part="needle"]');
const stamp = $('[data-part="stamp"]'), lever = $('[data-part="lever"]'), dial = $('[data-part="dial"]'), watch = $('[data-part="watch"]');
const marks = $$('[data-part="mark"]'), roles = $$('[data-part="role"]'), done = $$('[data-part="donecard"]');
const readout = document.querySelector("[data-readout]");
const still = matchMedia("(prefers-reduced-motion: reduce)");
// one mission, 13 s: [phase, seconds]
const PH = [["inbox",1.0],["toBuild",0.9],["build",1.8],["toChallenge",0.8],["challenge",1.2],["toEval",0.8],["eval",1.3],["toOwner",0.8],["owner",1.8],["toDone",0.8],["land",1.0],["back",1.0]];
const TOTAL = PH.reduce((s,p)=>s+p[1],0);
const ease = (t) => t<=0?0:t>=1?1:t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
const order = PH.map(p=>p[0]);
function phaseAt(t){let a=0;for(const [n,d] of PH){if(t<a+d)return [n,(t-a)/d];a+=d}return ["back",1]}
let clock = 0, missions = 0, ownerAway = false, held = 0, frame = 0, last = 0, visible = false;
const W = { x: ST.inbox, ram: PRESS.rest, probe: 0, tip: 16, stamp: 22, lever: 0, seal: 0, ready: 0, lift: 0, cardOn: 1 };
const cur = { ...W };
function want(t){
  const [n,u] = phaseAt(t), w = { x: ST.inbox, ram: PRESS.rest, probe: 0, tip: 16, stamp: 22, lever: 0, seal: 0, ready: 0, lift: 0, cardOn: 1, text: "", marks: 0 };
  const i = order.indexOf(n), past = (p) => i > order.indexOf(p);
  const mv = (a,b) => a + (b - a) * ease(u);
  w.marks = past("build") ? (past("challenge") ? (past("eval") ? (past("owner") ? (past("land") ? 6 : 5) : 4) : 3) : 2) : (n === "inbox" ? 0 : 1);
  w.ready = [0, 0.18, 0.36, 0.56, 0.76, 1, 1][w.marks];
  if (n === "inbox") { w.lift = Math.sin(u * Math.PI) * 0; w.text = "inbox · mission 00" + (missions % 9 + 1) + " picked up"; }
  if (n === "toBuild") { w.x = mv(ST.inbox, ST.build); w.text = "coordinator dispatches · one branch, one builder"; }
  if (n === "build") { w.x = ST.build; const s = (a,b) => u > a && u < b ? Math.sin((u - a) / (b - a) * Math.PI) : 0; w.ram = PRESS.rest - (PRESS.rest - CARD_TOP) * Math.max(s(0.1,0.4), s(0.55,0.85)); w.text = u < 0.5 ? "builder · failing tests first" : "builder · then the fix"; }
  if (n === "toChallenge") { w.x = mv(ST.build, ST.challenge); w.text = "pull request opened"; }
  if (n === "challenge") { w.x = ST.challenge; w.probe = Math.sin(Math.min(1, u * 1.4) * Math.PI) * 3; w.text = "challenger · tries to break it"; }
  if (n === "toEval") { w.x = mv(ST.challenge, ST.evaluate); w.text = "to the independent evaluator"; }
  if (n === "eval") { w.x = ST.evaluate; w.tip = CARD_TOP; w.text = "evaluator · different vendor, clean checkout"; }
  if (n === "toOwner") { w.x = mv(ST.evaluate, ST.owner); w.text = "waiting for the owner"; }
  if (n === "owner") { w.x = ST.owner; w.lever = Math.min(1, u * 3); const s = u > 0.35 && u < 0.75 ? Math.sin((u - 0.35) / 0.4 * Math.PI) : 0; w.stamp = 22 - (22 - CARD_TOP) * s; w.seal = u > 0.55 ? 1 : 0; w.text = u < 0.35 ? "owner's lever · only a person merges" : "merged · stamped"; }
  if (n === "toDone") { w.x = mv(ST.owner, ST.done); w.seal = 1; w.text = "to done"; }
  if (n === "land") { w.x = ST.done; w.seal = 1; w.cardOn = u < 0.4 ? 1 : 0; w.text = "done · watch reports to the owner"; }
  if (n === "back") { w.x = mv(ST.done, ST.inbox); w.cardOn = 0; w.text = "next mission"; }
  return w;
}
function draw(w){
  car.setAttribute("transform", translateAlong(P, [cur.x, 0, 0]));
  coord.setAttribute("transform", translateAlong(P, [cur.x, 0, 0]));
  cardEl.style.opacity = w.cardOn; seal.style.opacity = w.seal;
  ramEl.setAttribute("transform", translateAlong(P, [0, 0, cur.ram]));
  probe.setAttribute("transform", translateAlong(P, [0, cur.probe, 0]));
  const under = Math.abs(cur.x - DIAL.x) < 8 && w.cardOn ? CARD_TOP : 16, tip = Math.max(cur.tip, under);
  plungerEl.setAttribute("transform", translateAlong(P, [0, 0, tip]));
  needle.setAttribute("d", needleAt(DIAL.x, DIAL.y, DIAL.r, DIAL.z + DIAL.h, (tip - 16) / 9));
  stamp.setAttribute("transform", translateAlong(P, [0, 0, cur.stamp]));
  lever.setAttribute("d", leverAt(cur.lever));
  dial.setAttribute("d", dialNeedle(cur.ready));
  const light = (el, on) => { el.dataset.tone = on ? "hi" : "lo"; el.firstChild.style.fill = on ? "var(--anatomy-lit)" : ""; el.firstChild.style.opacity = on ? "1" : ""; };
  marks.forEach((el, i) => light(el, i < w.marks));
  roles.forEach((el, i) => light(el, true));
  done.forEach((el, i) => { el.style.display = i < Math.min(DONE_MAX, held) ? "" : "none"; });
  watch.style.opacity = w.blink ? 0.35 : 1;
  const text = ownerAway && order.indexOf(phaseAt(clock)[0]) >= order.indexOf("owner") && phaseAt(clock)[0] === "owner" ? "owner away · nothing merges" : w.text;
  if (readout.textContent !== text) readout.textContent = text;
}
function tick(now){
  const dt = last ? Math.min((now - last) / 1000, 1/30) : 1/60; last = now;
  const before = phaseAt(clock)[0];
  const [n, u] = phaseAt(clock);
  if (!(ownerAway && n === "owner" && u > 0.2)) clock += dt;           // the line waits at the desk while the owner is away
  if (clock >= TOTAL) { clock -= TOTAL; missions++; }
  const after = phaseAt(clock)[0];
  if (before === "land" && after === "back") held = Math.min(DONE_MAX, held + 1) % (DONE_MAX + 1);
  const w = want(clock);
  if (ownerAway && n === "owner") { w.lever = 0; w.stamp = 22; w.seal = 0; }
  w.blink = after === "land" && Math.floor(clock * 6) % 2 === 0;
  const k2 = still.matches ? 1 : 1 - Math.exp(-dt / 0.06);
  for (const f of ["x","ram","probe","tip","stamp","lever","ready"]) cur[f] += (w[f] - cur[f]) * k2;
  draw(w);
  frame = visible ? requestAnimationFrame(tick) : 0;
}
const run = () => { if (!frame && visible) { last = 0; frame = requestAnimationFrame(tick); } };
${FILM ? "" : `new IntersectionObserver((e) => { visible = e[e.length-1].isIntersecting; if (visible) run(); }, { rootMargin: \"120px 0px\" }).observe(stage);`}
function toggle(){ ownerAway = !ownerAway; run(); }
stage.addEventListener("click", toggle);
stage.addEventListener("keydown", (e) => { if (e.key === "o" || e.key === "O" || e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
if (still.matches) { clock = 7.9; }
draw(want(clock));
${FILM ? `window.figAt = (t, away, heldN) => { ownerAway = !!away; held = heldN || 0; clock = t % TOTAL; const [n,u] = phaseAt(clock); const w = want(clock); if (ownerAway && n === "owner") { w.lever = 0; w.stamp = 22; w.seal = 0; } w.blink = n === "land" && Math.floor(clock * 6) % 2 === 0; Object.assign(cur, w); draw(w); }; window.FIG_TOTAL = TOTAL; visible = false;` : ""}
`;

const body = k.plateHtml({
  fig: "Fig 2",
  title: "Agent Company",
  hint: "Click or press O: owner steps away",
  readout: "inbox · mission 001 picked up",
  keys: [
    { mark: "lit", label: "The mission card, the coordinator's lamp and the dials: what moves as the work is done" },
    { mark: "raised", label: "Stations: inbox, builder, challenger, evaluator, owner's desk, done tray" },
  ],
  caption:
    "Agent Company as a dispatch line. A mission leaves the inbox and rides one rail. The builder's press strikes twice, failing tests first and then the fix. The challenger's probe tries to break the work, and the evaluator's gauge reads it from a clean checkout. Only the owner's lever brings the merge stamp down; step away and the card waits at the desk. One coordinator lamp follows the work, the watch tower blinks when a mission lands, and the readiness dial climbs with each station passed.",
  body: `<div class="iso-stage" tabindex="0" role="button" aria-label="Agent Company dispatch line. Press O, Enter or Space, or click, to make the owner step away or come back">${svg}</div>`,
});
const name = FILM ? "agent-company-anatomy-film.html" : theme === "light" ? "agent-company-anatomy-light.html" : "agent-company-anatomy.html";
writeFileSync(join(HERE, name), k.pageHtml({ title: "Agent Company: anatomy", theme, body, script: kitScript() + live }));
console.log("wrote", name);
