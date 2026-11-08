import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./skill/kit/iso-kit.mjs";
import { kitScript } from "./skill/scripts/inline-kit.mjs";

// The Forge drawn as a harness-fitting line. An agent figure rides a carriage out of the class bay (a rack of eight
// class keys and an origin selector) under six fitting stations. Each station's ram lowers one piece of the OpenProof
// harness onto the figure: helm, plate, gauntlets, belt, boots, amulet. A count dial on the gate post climbs with each
// piece, and the deploy gate's boom lifts only at six of six. Press M and one station skips its piece: the carriage
// stops at the gate, and the boom stays down.

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes("--light") ? "light" : "dark";
const FILM = process.argv.includes("--film");
const WIDTH = 660, HEIGHT = 440;

const PLATE = { x: -186, y: -70, w: 372, d: 140, r: 9 };
const PLATE_H = 12, FOOT_H = 5;
const RAIL = [-176, 176];
const BAY = -150, GATE = 132, OUT = 160;
const ST = [-108, -72, -36, 0, 36, 72];
const PIECES = ["helm", "plate", "gauntlets", "belt", "boots", "amulet"];
const CAR = { w: 30, d: 24 }, CAR_TOP = 6;
const BEAM_Z = 66, POST_Y = -24;
const RAM_REST = 16;   // how far above its fitted height a piece waits on the ram

const P = k.fitProjection(
  [...k.boxCorners(PLATE, -PLATE_H - FOOT_H, 0), [ST[0] - 12, POST_Y, BEAM_Z + 12], [ST[5] + 12, POST_Y, BEAM_Z + 12], [GATE, -20, 52], [BAY, -46, 30]],
  WIDTH, HEIGHT, { pad: 22, azimuth: 34 },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);
const slab = (plan, z, h, steps = 3, bevel = 0.5) => k.slabOf(plan, z, h, P, steps, bevel);
const cyl = (x, y, r, z, h, steps = 24, bevel = 0) => k.cylinder(x, y, r, z, h, P, steps, bevel);
const screws = (pts, z) => D(pts.map(([x, y]) => at([x, y, z])), { size: 0.45 });
const halo = (plan, z, h) => `<path class="iso-halo" d="${k.haloOf(plan, z, h, P)}"/>`;

function plate() {
  const out = [halo(PLATE, -PLATE_H - FOOT_H, PLATE_H)];
  const feet = k.corners(PLATE, 26).sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P));
  for (const [x, y] of feet) { out.push(S(cyl(x, y, 8, -PLATE_H - FOOT_H, 1.6, 28), { tone: "lo" })); out.push(S(cyl(x, y, 6, -PLATE_H - FOOT_H + 1.6, FOOT_H - 1.6, 28), { tone: "mid" })); }
  out.push(S(k.slabOf(PLATE, -PLATE_H, PLATE_H, P, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: "lo" }));
  const c = k.corners(PLATE, 11); out.push(L(c.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 16)).join(""), { tone: "lo" })); out.push(screws(c, 0));
  // station ruler along the front edge
  const strip = { x: ST[0] - 14, y: 22, w: ST[5] - ST[0] + 28, d: 6, r: 1 };
  out.push(S(slab(strip, 0, 0.6, 3, 0), { tone: "lo", crease: "none" }));
  const t = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 4, 9, strip.y + 0.6, 0.6, [1.8, 3.4], P);
  out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
  ST.forEach((x) => { const [sx, sy] = at([x, 25, 0.6]); out.push(`<g class="iso-dots" data-part="stmark" data-tone="lo"><circle cx="${sx}" cy="${sy}" r="1.9"/></g>`); });
  return out.join("");
}
function rails() {
  const out = [];
  for (const y of [-9, 6]) { out.push(S(slab({ x: RAIL[0], y, w: RAIL[1] - RAIL[0], d: 3.4, r: 1 }, 0, 3, 3, 0.4), { tone: "mid" })); out.push(screws([RAIL[0] + 6, -90, -18, 54, RAIL[1] - 6].map((x) => [x, y + 1.7]), 3)); }
  for (const x of [RAIL[0] - 4, RAIL[1]]) { out.push(S(slab({ x, y: -12, w: 4, d: 25, r: 1.2 }, 0, 7, 3, 0.5), { tone: "mid" })); }
  return out.join("");
}
function post(x, y, h, w = 5) {
  return S(slab({ x: x - w - 2, y: y - w - 2, w: 2 * w + 4, d: 2 * w + 4, r: 1.5 }, 0, 2.4, 3, 0.4), { tone: "lo" }) +
    S(slab({ x: x - w / 2, y: y - w / 2, w, d: w, r: 0.8 }, 2.4, h - 2.4, 2, 0.3), { tone: "mid" }) + screws([[x - w, y - w], [x + w, y + w]], 2.4);
}
// class bay: a rack of eight class keys (one raised, the class) and an origin selector dial
function bay() {
  const out = [], base = { x: BAY - 22, y: -56, w: 44, d: 22, r: 2.4 };
  out.push(halo(base, 0, 10), S(slab(base, 0, 10, 3, 0.6), { tone: "mid" }), screws(k.corners(base, 3), 10));
  for (let i = 0; i < 8; i++) { const x = BAY - 17.5 + i * 5, raised = i === 5; out.push(S(slab({ x: x - 1.6, y: -52, w: 3.2, d: 6, r: 0.5 }, 10, raised ? 9 : 4, 2, 0.2), raised ? { tone: "hi", lit: true } : { tone: "mid" })); }
  out.push(`<path class="iso-line" data-tone="faint" data-free="both" d="${k.lineOnTop([BAY - 19, -42], [BAY + 19, -42], 10, P)}"/>`);
  // origin selector
  const ox = BAY + 2, oy = -40;
  out.push(S(cyl(ox, oy, 7.4, 10, 2.4, 40, 0.4), { tone: "hi", crease: "lo" }));
  const t = k.radialTicks(ox, oy, 6.2, 8, 8, 12.4, [1.2, 1.2], P); out.push(L(t.major, { tone: "mid" }));
  const a = Math.PI * 0.35; out.push(`<path class="iso-line" data-tone="lit" data-free="start" d="${k.lineOnTop([ox, oy], [ox + Math.cos(a) * 5.4, oy + Math.sin(a) * 5.4], 12.6, P)}" style="stroke-width:1.2"/>`);
  out.push(L(k.ring(ox, oy, 1.2, 12.4, P, 14), { tone: "mid" }));
  return out.join("");
}
// stations: a post behind the rail and a cantilever beam over it; ram heads hang from the beam
function stationBack(x) { return post(x, POST_Y, BEAM_Z, 5); }
function stationBeam(x, i) {
  const out = [S(slab({ x: x - 5, y: POST_Y - 5, w: 10, d: 30, r: 1.4 }, BEAM_Z, 5, 3, 0.5), { tone: "mid" })];
  out.push(screws([[x, POST_Y], [x, 1]], BEAM_Z + 5));
  out.push(S(cyl(x, 0, 3.6, BEAM_Z + 5, 2.4, 20, 0.3), { tone: "mid" }), L(k.knurl(x, 0, 3.6, BEAM_Z + 5, BEAM_Z + 7.4, 16, P), { tone: "lo" }));
  const [sx, sy] = at([x + 3.5, POST_Y - 2, BEAM_Z + 5]); out.push(`<g class="iso-dots" data-part="stlamp" data-i="${i}" data-tone="lo"><circle cx="${sx}" cy="${sy}" r="1.6"/></g>`);
  return out.join("");
}
// the figure, built at the origin on the carriage; z0 is the carriage top; F scales the whole figure
const Z0 = CAR_TOP, F = 1.45;
const fc = (x, y, r, z, h, st, bv) => cyl(x * F, y * F, r * F, Z0 + z * F, h * F, st, bv);
function figureBody() {
  const out = [];
  for (const sx of [-2.6, 2.6]) out.push(S(fc(sx, 0, 2.1, 0, 12, 16, 0.3), { tone: "mid" }));
  out.push(S(fc(0, 0, 5.4, 12, 14, 24, 0.6), { tone: "mid" }));
  for (const sx of [-7.4, 7.4]) out.push(S(fc(sx, 0, 1.7, 14, 11, 14, 0.3), { tone: "mid" }));
  out.push(S(fc(0, 0, 1.6, 26, 1.6, 12), { tone: "mid" }));
  out.push(S(fc(0, 0, 4, 27.4, 7.6, 22, 1.2), { tone: "hi" }));
  out.push(D([at([-1.3 * F, 3.4 * F, Z0 + 31.6 * F]), at([1.3 * F, 3.4 * F, Z0 + 31.6 * F])], { size: 0.4 }));
  return out.join("");
}
// harness pieces, each drawn at its fitted height on the figure
const FIT_Z = { helm: Z0 + 31 * F, plate: Z0 + 15 * F, gauntlets: Z0 + 14 * F, belt: Z0 + 12 * F, boots: Z0, amulet: Z0 + 21 * F };
const TOP = { helm: 7.4, plate: 9.4, gauntlets: 4.2, belt: 2.6, boots: 4.4, amulet: 2.4 };
function piece(id) {
  if (id === "helm") return S(fc(0, 0, 4.7, 31, 4.8, 24, 1.0), { tone: "hi", lit: true }) + S(fc(0, -0.4, 1, 35.8, 2.6, 10), { tone: "hi" });
  if (id === "plate") return S(fc(0, 0, 6.3, 15, 9.4, 26, 0.6), { tone: "hi", lit: true }) + L(k.ring(0, 0, 6.3 * F, Z0 + 19.7 * F, P, 26), { tone: "lo" });
  if (id === "gauntlets") return [-7.4, 7.4].map((sx) => S(fc(sx, 0, 2.5, 14, 4.2, 14, 0.4), { tone: "hi", lit: true })).join("");
  if (id === "belt") return S(fc(0, 0, 6.6, 12, 2.6, 26, 0.3), { tone: "hi", lit: true }) + S(slab({ x: -1.6 * F, y: 5.8 * F, w: 3.2 * F, d: 1.4 * F, r: 0.3 }, Z0 + 12.2 * F, 2.2 * F, 2, 0.1), { tone: "hi" });
  if (id === "boots") return [-2.6, 2.6].map((sx) => S(fc(sx, 0.6, 2.9, 0, 4.4, 16, 0.5), { tone: "hi", lit: true })).join("");
  if (id === "amulet") return S(fc(0, 6.2, 1.6, 21, 2.4, 14, 0.3), { tone: "hi", lit: true });
  return "";
}
function carriage() {
  const plan = { x: -CAR.w / 2, y: -CAR.d / 2, w: CAR.w, d: CAR.d, r: 3 };
  return `<path class="iso-halo" d="${k.haloOf(k.insetPlan(plan, 3), 3, 0.1, P)}" style="filter:blur(4px)"/>` + S(slab(plan, 3, CAR_TOP - 3, 5, 0.6), { tone: "mid" }) + screws(k.corners(plan, 3), CAR_TOP) +
    S(cyl(0, 0, 11, CAR_TOP, 0.8, 32, 0.2), { tone: "lo" });
}
// the ram: a rod and a gripper; the waiting piece hangs under it (shown until fitted)
function ram(i) {
  const id = PIECES[i], gz = FIT_Z[id] + TOP[id] * F + 1;   // gripper sits just above the piece's top at its fitted height
  return S(cyl(0, 0, 1.3, gz + 3, BEAM_Z - gz + 4, 12), { tone: "mid", crease: "none" }) +
    S(slab({ x: -5, y: -3, w: 10, d: 6, r: 1 }, gz, 3, 2, 0.3), { tone: "mid" }) +
    `<g data-part="held" data-i="${i}">${piece(id)}</g>`;
}
// gate: post, boom pivot, count dial, lamp
function gatePost() {
  const out = [post(GATE, -22, 40, 6)];
  out.push(S(cyl(GATE, -22, 5.4, 40, 3, 28, 0.4), { tone: "mid" }));
  out.push(S(cyl(GATE + 9, -30, 9, 0, 2.4, 40, 0.4), { tone: "mid" }));
  const dz = 2.4, cx = GATE + 9, cy = -30;
  out.push(S(cyl(cx, cy, 7.6, dz, 2, 40, 0.4), { tone: "hi", crease: "lo" }));
  const t = k.radialTicks(cx, cy, 6.4, 6, 6, dz + 2, [1.4, 1.4], P, -Math.PI * 0.75, Math.PI * 1.5); out.push(L(t.major, { tone: "mid" }));
  out.push(`<g data-part="lamp">${S(cyl(GATE, -22, 3, 43, 3.4, 20, 0.4), { tone: "hi" })}</g>`);
  return out.join("");
}
const countNeedle = (frac) => { const cx = GATE + 9, cy = -30, a = -Math.PI * 0.75 + Math.PI * 1.5 * frac; return k.lineOnTop([cx - Math.cos(a) * 1.4, cy - Math.sin(a) * 1.4], [cx + Math.cos(a) * 5.6, cy + Math.sin(a) * 5.6], 4.6, P); };
const boomAt = (lift) => { const a = lift * Math.PI * 0.44, bx = GATE, by = -22, bz = 36; return k.segment([bx, by, bz], [bx, by + Math.cos(a) * 34, bz + Math.sin(a) * 34], P); };
function gateRest() { return S(slab({ x: GATE - 3, y: 14, w: 6, d: 6, r: 1 }, 0, 32, 2, 0.3), { tone: "mid" }) + S(slab({ x: GATE - 4, y: 13, w: 8, d: 8, r: 1.2 }, 32, 2, 2, 0.3), { tone: "mid" }); }

const svg = k.figureSvg({
  width: WIDTH, height: HEIGHT,
  label: "The Forge drawn as a harness-fitting line. A small agent figure rides a carriage out of a class bay, with a rack of eight class keys and an origin selector, under six fitting stations. Each station's ram lowers one piece of the OpenProof harness onto the figure: helm, plate, gauntlets, belt, boots and amulet. A count dial on the gate post climbs with each piece, and the deploy gate's boom lifts only when all six are on.",
  body: [
    plate(), bay(), ...ST.map((x) => stationBack(x)), gatePost(), rails(),
    `<g data-part="carriage" transform="${k.translateAlong(P, [BAY, 0, 0])}">${carriage()}<g data-part="figure">${figureBody()}${PIECES.map((id) => `<g data-part="fitted" data-i="${PIECES.indexOf(id)}" style="opacity:0">${piece(id)}</g>`).join("")}</g></g>`,
    ...ST.map((x, i) => `<g data-part="ram" data-i="${i}" transform="${k.translateAlong(P, [x, 0, RAM_REST])}">${ram(i)}</g>`),
    ...ST.map((x, i) => stationBeam(x, i)),
    `<path data-part="needle" class="iso-line" data-tone="lit" data-free="start" d="${countNeedle(0)}" style="stroke-width:1.2"/>`,
    `<path data-part="boom" class="iso-line" data-tone="hi" d="${boomAt(0)}" style="stroke-width:3;stroke-linecap:round"/>`,
    gateRest(),
  ],
});

const live = `
const P = ${JSON.stringify(P)}, ST = ${JSON.stringify(ST)}, BAY = ${BAY}, GATE = ${GATE}, OUT = ${OUT}, RAM_REST = ${RAM_REST};
const PIECES = ${JSON.stringify(PIECES)}, NAMES = ["Worktree helm","Deny-rule plate","No-merge gauntlets","Allowlist belt","Constructed-data boots","Evidence amulet"];
const countNeedle = ${countNeedle.toString().replaceAll("k.lineOnTop", "lineOnTop")};
const boomAt = ${boomAt.toString().replaceAll("k.segment", "segment")};
const stage = document.querySelector(".iso-stage"), svg = stage.querySelector("svg");
const $ = (s) => svg.querySelector(s), $$ = (s) => [...svg.querySelectorAll(s)];
const car = $('[data-part="carriage"]'), rams = $$('[data-part="ram"]'), fitted = $$('[data-part="fitted"]'), held = $$('[data-part="held"]');
const needle = $('[data-part="needle"]'), boom = $('[data-part="boom"]'), lamp = $('[data-part="lamp"]'), lamps = $$('[data-part="stlamp"]'), marks = $$('[data-part="stmark"]');
const readout = document.querySelector("[data-readout]");
const still = matchMedia("(prefers-reduced-motion: reduce)");
const ease = (t) => t<=0?0:t>=1?1:t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
// one pass: class bay 1.4 s, six stations of 1.7 s (move 0.6, fit 1.1), to the gate 0.8, gate 1.0, out 0.9, reset 1.0
const T_BAY = 1.4, T_ST = 1.7, T_MOVE = 0.6, T_GATEMOVE = 0.8, T_GATE = 1.0, T_OUT = 0.9, T_RESET = 1.0;
const T_STATIONS = T_BAY + 6 * T_ST, TOTAL = T_STATIONS + T_GATEMOVE + T_GATE + T_OUT + T_RESET;
let missing = -1;   // index of a skipped piece (press M): -1 when every station fits its piece
function want(t) {
  const w = { x: BAY, rams: [0,0,0,0,0,0], fit: [0,0,0,0,0,0], held: [1,1,1,1,1,1], lift: 0, count: 0, text: "", lamp: 0, active: -1 };
  if (t < T_BAY) { w.text = "class bay · Rogue · origin: Gemini CLI"; return w; }
  if (t < T_STATIONS) {
    const i = Math.floor((t - T_BAY) / T_ST), u = (t - T_BAY - i * T_ST);
    for (let j = 0; j < i; j++) if (j !== missing) { w.fit[j] = 1; w.held[j] = 0; }
    w.active = i;
    const from = i === 0 ? BAY : ST[i - 1];
    if (u < T_MOVE) { w.x = from + (ST[i] - from) * ease(u / T_MOVE); w.text = "to station " + (i + 1) + " · " + NAMES[i]; }
    else { w.x = ST[i]; const v = (u - T_MOVE) / (T_ST - T_MOVE);
      if (i === missing) { w.text = "station " + (i + 1) + " · " + NAMES[i] + " · skipped"; }
      else { w.rams[i] = v < 0.45 ? ease(v / 0.45) : v < 0.6 ? 1 : 1 - ease((v - 0.6) / 0.4); if (v >= 0.45) { w.fit[i] = 1; w.held[i] = 0; } w.text = "fitting " + NAMES[i]; } }
    w.count = w.fit.reduce((a, b) => a + b, 0); return w;
  }
  for (let j = 0; j < 6; j++) if (j !== missing) { w.fit[j] = 1; w.held[j] = 0; }
  w.count = w.fit.reduce((a, b) => a + b, 0);
  const ok = w.count === 6; let u = t - T_STATIONS;
  if (u < T_GATEMOVE) { w.x = ST[5] + (GATE - 22 - ST[5]) * ease(u / T_GATEMOVE); w.text = "to the deploy gate · " + w.count + "/6"; return w; }
  u -= T_GATEMOVE;
  if (u < T_GATE) { w.x = GATE - 22; w.lift = ok ? ease(u / T_GATE) : 0; w.lamp = ok ? 1 : (Math.floor(u * 6) % 2); w.text = ok ? "6/6 · gate opens" : w.count + "/6 · no harness, no deployment"; return w; }
  u -= T_GATE;
  if (u < T_OUT) { if (ok) { w.x = GATE - 22 + (OUT - GATE + 22) * ease(u / T_OUT); w.lift = 1; w.lamp = 1; w.text = "deployed"; } else { w.x = GATE - 22; w.lamp = Math.floor(u * 6) % 2; w.text = w.count + "/6 · held at the gate"; } return w; }
  u -= T_OUT;
  w.x = (ok ? OUT : GATE - 22); w.lift = ok ? 1 - ease(u / T_RESET) : 0; w.text = ok ? "next agent" : "refit in the Forge"; w.fitOut = 1 - ease(u / T_RESET); return w;
}
let clock = 0, frame = 0, last = 0, visible = false;
const cur = { x: BAY, rams: [0,0,0,0,0,0], lift: 0, count: 0 };
function draw(w) {
  car.setAttribute("transform", translateAlong(P, [cur.x, 0, 0]));
  car.style.opacity = w.fitOut === undefined ? 1 : w.fitOut;
  rams.forEach((el, i) => el.setAttribute("transform", translateAlong(P, [ST[i], 0, RAM_REST * (1 - cur.rams[i])])));
  fitted.forEach((el, i) => el.style.opacity = w.fit[i]);
  held.forEach((el, i) => el.style.opacity = i === missing ? 0 : w.held[i]);
  needle.setAttribute("d", countNeedle(cur.count / 6));
  boom.setAttribute("d", boomAt(cur.lift));
  const light = (el, on) => { el.dataset.tone = on ? "hi" : "lo"; el.firstChild.style.fill = on ? "var(--anatomy-lit)" : ""; el.firstChild.style.opacity = on ? "1" : ""; };
  lamps.forEach((el, i) => light(el, w.fit[i] === 1 || w.active === i));
  marks.forEach((el, i) => light(el, w.fit[i] === 1));
  lamp.firstChild && (lamp.style.opacity = w.lamp ? 1 : 0.35);
  if (readout.textContent !== w.text) readout.textContent = w.text;
}
function tick(now) {
  const dt = last ? Math.min((now - last) / 1000, 1/30) : 1/60; last = now;
  clock += dt; if (clock >= TOTAL) clock -= TOTAL;
  const w = want(clock), k2 = still.matches ? 1 : 1 - Math.exp(-dt / 0.05);
  cur.x += (w.x - cur.x) * k2; for (let i = 0; i < 6; i++) cur.rams[i] += (w.rams[i] - cur.rams[i]) * k2;
  cur.lift += (w.lift - cur.lift) * k2; cur.count += (w.count - cur.count) * (still.matches ? 1 : 1 - Math.exp(-dt / 0.15));
  draw(w);
  frame = visible ? requestAnimationFrame(tick) : 0;
}
const run = () => { if (!frame && visible) { last = 0; frame = requestAnimationFrame(tick); } };
${FILM ? "" : `new IntersectionObserver((e) => { visible = e[e.length-1].isIntersecting; if (visible) run(); }, { rootMargin: \"120px 0px\" }).observe(stage);`}
function toggle() { missing = missing < 0 ? 3 : -1; clock = 0; run(); }
stage.addEventListener("click", toggle);
stage.addEventListener("keydown", (e) => { if (e.key === "m" || e.key === "M" || e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
if (still.matches) clock = T_STATIONS + T_GATEMOVE + T_GATE * 0.9;
{ const w = want(clock); Object.assign(cur, { x: w.x, rams: w.rams.slice(), lift: w.lift, count: w.count }); draw(w); }
${FILM ? `window.figAt = (t, skip) => { missing = skip ? 3 : -1; clock = Math.max(0, Math.min(TOTAL - 0.01, t)); const w = want(clock); Object.assign(cur, { x: w.x, rams: w.rams.slice(), lift: w.lift, count: w.count }); draw(w); }; window.FIG_TOTAL = TOTAL; visible = false;` : ""}
`;

const body = k.plateHtml({
  fig: "Fig 1",
  title: "The Forge",
  hint: "Click or press M: skip a piece",
  readout: "class bay · Rogue · origin: Gemini CLI",
  keys: [
    { mark: "lit", label: "The harness pieces, the class key and the count needle: what makes an agent deployable" },
    { mark: "raised", label: "Class bay, six fitting stations, the deploy gate" },
  ],
  caption:
    "The Forge as a harness-fitting line. An agent leaves the class bay with its class (one job) and its origin (the tool it runs on) and rides under six stations. Each ram lowers one piece of the OpenProof harness: worktree helm, deny-rule plate, no-merge gauntlets, allowlist belt, constructed-data boots and evidence amulet. The count dial climbs with each piece. The deploy gate lifts only at six of six; skip a piece and the agent is held at the gate.",
  body: `<div class="iso-stage" tabindex="0" role="button" aria-label="The Forge harness-fitting line. Press M, Enter or Space, or click, to skip one piece and see the gate refuse">${svg}</div>`,
});
const name = FILM ? "forge-anatomy-film.html" : theme === "light" ? "forge-anatomy-light.html" : "forge-anatomy.html";
writeFileSync(join(HERE, name), k.pageHtml({ title: "Agent Company: the Forge", theme, body, script: kitScript() + live }));
console.log("wrote", name);
