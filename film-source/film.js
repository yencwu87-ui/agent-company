import { clamp, lerp, seg, eio, eo } from "/core/lib.js";

const VO = await (await fetch("vo/dur.json")).json();
const LINES = await (await fetch("lines.json")).json();
const AT = { a1: 0.8, a2: 6.4, a3: 12.2, a4: 21.2, a5: 26.0, a6: 32.2, a7: 40.6, a8: 49.4, a9: 62.6, a10: 70.8 };
const DUR = 77.0;
// The real Guild demo keeps its own clock (src): each real-demo segment of this film plays a stretch of it.
const SEGS = [[0, 5.8, 0], [21.0, 31.4, 2.6], [39.8, 48.4, 4.0], [61.8, 70.6, 5.2]];   // [from, to, src − t]
const srcOf = (t) => { const s = SEGS.find(([a, b]) => t >= a && t < b); return s ? t + s[2] : null; };

// ---------------------------------------------------------------- the real pages
const appF = document.querySelector("#app iframe"), phoneF = document.querySelector("#phone iframe");
const fig0F = document.querySelector("#fig0 iframe"), fig1F = document.querySelector("#fig1 iframe"), fig2F = document.querySelector("#fig2 iframe");
const loaded = (f) => new Promise((r) => (f.contentDocument && f.contentDocument.readyState === "complete" && f.contentWindow.document.body ? r() : f.addEventListener("load", r, { once: true })));
await Promise.all([appF, phoneF, fig0F, fig1F, fig2F].map(loaded));
await document.fonts.ready;
const AW = appF.contentWindow, AD = appF.contentDocument, PW = phoneF.contentWindow, PD = phoneF.contentDocument;
await new Promise((r) => setTimeout(r, 400));
try { await AD.fonts.ready; await PD.fonts.ready; } catch (e) {}

// Scene builder injected into each Guild page: rebuild the whole state from the demo guild plus the film's steps.
const SCENE = `
window.__scene = function (d) {
  document.documentElement.dataset.theme = "dark";
  SOUND = false; toast = function () {}; levelUp = function () {};
  document.querySelectorAll("dialog").forEach((x) => { x.returnValue = "cancel"; if (x.open) x.close(); });
  demo();
  const H = (n) => Object.values(S.heroes).find((h) => h.name.startsWith(n));
  const tam = H("Tamsin"); tam.history = tam.history.map((x) => ({ ...x, o: "clean", d: 3 }));
  if (d.vera) { const id = "h" + (S.seq++); S.heroes[id] = { id, name: "Vera Quickblade", cls: "rogue", origin: "Gemini CLI", skin: 3, hair: 4, tunic: null, harness: HARNESS.map((p) => p.id), allow: [...ALLOW_DEFAULT.rogue], xp: 0, lv: 1, probation: 0, history: [], talents: [], lessons: [], record: { won: 0, back: 0, defects: 0 } }; }
  (d.place || []).forEach(([n, k]) => { const h = H(n); (S.slots[k] = S.slots[k] || []).push(h.id); });
  applyWorld(d.world || "realm");
  if (d.deployed) horn();
  if (d.accepted) { PQ = S.quests.find((q) => q.id === "q001"); $("#pv-pr").value = "https://github.com/acme/shop/pull/12"; $("#pv-tests").value = "rate-limit 24 passed"; $("#pv-verdict").value = "approve"; $("#pv-defects").value = "1"; $("#pv-op").value = "evidence/rate-limit.bundle"; const dp = $("#dp"); dp.returnValue = "accept"; dp.dispatchEvent(new Event("close")); dp.returnValue = "cancel"; }
  if (d.escaped) { EQ = "q001"; $("#e-what").value = "Bursts got through after a restart"; const de = $("#de"); de.returnValue = "ok"; de.dispatchEvent(new Event("close")); de.returnValue = "cancel"; }
  if (d.forge) { F = { step: d.forge.step, h: { name: d.forge.name || "", cls: d.forge.cls, origin: d.forge.origin, skin: 3, hair: 4, tunic: null, harness: HARNESS.slice(0, d.forge.fit || 0).map((p) => p.id), allow: [...ALLOW_DEFAULT[d.forge.cls]], xp: 0, lv: 1, probation: 0, history: [], talents: [], lessons: [], record: { won: 0, back: 0, defects: 0 } } }; renderForge(); }
  go(d.room);
  if (d.room === "train") { TH = H(d.train).id; renderTrain(); }
  if (d.prove) { PQ = S.quests.find((q) => q.id === "q001"); $("#pform").reset(); $("#p-title").textContent = "Prove quest 001: Add rate limiting to the API";
    $("#pv-pr").value = d.prove.pr; $("#pv-tests").value = d.prove.tests; $("#pv-verdict").value = d.prove.verdict; $("#pv-defects").value = d.prove.defects; $("#pv-op").value = d.prove.op; proveHint(); $("#dp").returnValue = "cancel"; $("#dp").showModal(); }
  document.body.classList.toggle("handheld", !!d.hand); if (d.hand) { const p = $("#pad"); p.style.display = ""; }
  if (!d.deployed) $("#files").classList.remove("open");
  const room = $("#room-" + d.room);
  document.documentElement.style.scrollBehavior = "auto";
  scrollTo(0, d.top ? 0 : Math.max(0, room.offsetTop - (d.room === "forge" ? 70 : 12)));
  $("#lvup").style.opacity = 0; $("#toast").classList.remove("on");
};`;
for (const w of [AW, PW]) { const s = w.document.createElement("script"); s.textContent = SCENE; w.document.body.appendChild(s); const st = w.document.createElement("style"); st.textContent = ".toast{transition:none!important}.slot{transition:none!important}.slot.nope{animation:none!important}.lvup.on{animation:none!important}html{scroll-behavior:auto!important}*{caret-color:transparent}"; w.document.head.appendChild(st); }

// ---------------------------------------------------------------- the film's steps, as data
const typed = (s, t0, cps, t) => s.slice(0, clamp(Math.floor((t - t0) * cps), 0, s.length));
const NAME = "Vera Quickblade";
const PROOF = { pr: "https://github.com/acme/shop/pull/12", tests: "rate-limit 24 passed", op: "evidence/rate-limit.bundle" };
function sceneAt(t) {
  const d = { room: "map", world: "realm" };
  if (t < 7.0) { d.room = "map"; return d; }
  if (t < 19.6) {
    d.room = "forge";
    const step = t < 9.9 ? 0 : t < 11.8 ? 1 : t < 14.0 ? 2 : t < 18.5 ? 3 : 4;
    d.forge = { step, cls: t >= 9.0 ? "rogue" : "artificer", origin: t >= 10.95 ? "Gemini CLI" : "Claude Code", name: typed(NAME, 12.1, 12.5, t), fit: t < 15.0 ? 0 : clamp(Math.floor((t - 15.0) / 0.5) + 1, 0, 6) };
    return d;
  }
  if (t < 35.0 || (t >= 67.2)) {
    d.room = "map"; d.vera = true; d.place = [];
    if (t >= 22.8) d.place.push(["Ollo", "q002:scribe"]);
    if (t >= 28.2) d.place.push(["Vera", "q002:rogue"]);
    if (t >= 31.5) d.deployed = true;
    if (t >= 67.2) { d.world = t < 69.2 ? "neon" : t < 71.0 ? "sky" : "star"; d.deployed = false; }
    return d;
  }
  if (t < 43.2) { d.room = "map"; d.vera = true; d.place = [["Ollo", "q002:scribe"], ["Vera", "q002:rogue"]]; d.deployed = true; return d; }
  d.vera = true; d.place = [["Ollo", "q002:scribe"], ["Vera", "q002:rogue"]];
  if (t < 55.0) {
    d.room = "prove";
    if (t >= 44.4 && t < 49.9) d.prove = { pr: typed(PROOF.pr, 44.8, 30, t), tests: typed(PROOF.tests, 46.2, 26, t), verdict: t >= 47.4 ? "approve" : "", defects: "1", op: typed(PROOF.op, 47.9, 26, t) };
    if (t >= 49.9) d.accepted = true;
    return d;
  }
  d.room = "train"; d.train = "Brannoc"; d.accepted = true; if (t >= 56.6) d.escaped = true;
  return d;
}
let lastKey = "";
function applyApp(t) {
  const d = sceneAt(t), key = JSON.stringify(d);
  if (key !== lastKey) { lastKey = key; AW.__scene(d); }
  // transient UI the page would animate on its own: drawn per frame from the clock instead
  const nope = AD.querySelector('[data-slot="q002:paladin"]');
  if (nope) { const on = t >= 25.6 && t < 26.4; nope.classList.toggle("nope", on); nope.style.transform = on ? `translateX(${Math.sin((t - 25.6) * 55) * 5 * (1 - (t - 25.6) / 0.8)}px)` : ""; }
  const TO = [[25.6, 27.8, "Rogue can't take the Paladin slot"], [28.2, 29.6, "Vera Quickblade deployed"], [31.5, 33.8, "The horn sounds: quests deployed"], [19.6, 20.8, "Vera Quickblade joins the guild"], [56.6, 58.3, "Escaped defect: trust credits deducted"], [67.4, 69.0, "Neon City: same rules, new world"], [69.2, 70.9, "Sky Islands: same rules, new world"], [71.0, 72.6, "Star Fleet: same rules, new world"]];
  const msg = (TO.find(([a, b]) => t >= a && t < b) || [0, 0, ""])[2], toastEl = AD.querySelector("#toast");
  if (toastEl.textContent !== msg) toastEl.textContent = msg; toastEl.classList.toggle("on", !!msg); toastEl.style.opacity = msg ? 1 : 0; toastEl.style.transform = "translate(-50%,0)";
  const lv = AD.querySelector("#lvup"), lu = t >= 50.6 && t < 53.8 ? Math.min(1, (t - 50.6) / 0.35, (53.8 - t) / 0.5) : 0;
  lv.style.opacity = lu; lv.style.transform = `scale(${0.8 + 0.2 * eo(Math.min(1, (t - 50.6) / 0.4))})`;
  if (lu) { lv.querySelector("b").textContent = "LEVEL UP"; lv.querySelector("#lvup-t").textContent = "Nyx Shadowprobe reaches level 2 · a talent is ready to train"; }
}
let phoneKey = "";
function applyPhone(t) { const key = "p"; if (key !== phoneKey) { phoneKey = key; PW.__scene({ room: "map", world: "star", hand: true, top: true }); } }

// ---------------------------------------------------------------- measured anchors (cam coords), taken once per step
const APP = { x: 120, y: 100 };
function measure(t, sel, fx = 0.5, fy = 0.5) { lastKey = ""; applyApp(t); const el = AD.querySelector(sel); if (!el) { console.warn("no", sel, t); return { x: 960, y: 540, w: 0, h: 0 }; } const r = el.getBoundingClientRect(); return { x: APP.x + r.left + r.width * fx, y: APP.y + r.top + r.height * fy, w: r.width, h: r.height, l: APP.x + r.left, tp: APP.y + r.top }; }
const A = {};
A.rogue = measure(8.0, '[data-cls="rogue"]'); A.next0 = measure(9.5, "#f-next"); A.gem = measure(10.5, '[data-origin="Gemini CLI"]'); A.next1 = measure(11.4, "#f-next");
A.name = measure(12.0, "#h-name", 0.3); A.next2 = measure(13.6, "#f-next"); A.fitAll = measure(14.5, "#fit-all"); A.next3 = measure(18.0, "#f-next"); A.enter = measure(19.0, "#f-next");
A.forge = measure(16.0, "#fstep"); A.preview = measure(16.0, "#p-spr");
A.ollo = measure(21.0, '#tray .hero[data-hero]:last-of-type'); A.slotScribe = measure(21.0, '[data-slot="q002:scribe"]');
A.vera = measure(23.5, '#tray .hero:last-child'); A.slotPal = measure(23.5, '[data-slot="q002:paladin"]'); A.slotRogue = measure(23.5, '[data-slot="q002:rogue"]');
A.ring = measure(30.0, "#ring"); A.horn = measure(30.5, "#btn-horn"); A.files = measure(32.0, "#files", 0.5, 0.3); A.locs = measure(25.0, "#locs", 0.5, 0.42);
A.prove = measure(43.8, '#returned [data-prove]'); A.dlg = measure(46.0, "#dp"); A.accept = measure(49.0, "#pv-accept"); A.op = measure(48.0, "#pv-op");
A.chron = measure(50.5, "#chron", 0.5, 0.2); A.trust = measure(56.0, ".trust", 0.5, 0.45); A.trayTop = measure(30.0, "#tray", 0.5, 0.0);
// tray order: Ollo and Vera by name
A.ollo = measure(21.0, '#tray .hero:nth-child(9)'); A.vera = measure(23.5, '#tray .hero:nth-child(10)');
lastKey = ""; applyApp(0); applyPhone(0);

// ---------------------------------------------------------------- terminal
const TX = document.getElementById("tx");
const T1 = "$ python3 agent_company.py init my-project", O1 = "Agent Company 0.2.0: my-project/docs/ops\n  created: inbox/README.md, templates/…, outbox/STATUS.md, ROLES.md";
const T2 = "$ python3 agent_company.py guild my-project", O2 = "Agent Company Guild: http://127.0.0.1:8765/guild?token=…";
function termAt(t) {
  let out = `<span class="p">${typed(T1, 1.1, 28, t)}</span>`;
  if (t > 2.8) out += `\n<span class="dim">${O1}</span>\n`;
  if (t > 3.3) out += `<span class="p">${typed(T2, 3.5, 28, t)}</span>`;
  if (t > 5.3) out += `\n<span class="dim">${O2}</span>`;
  TX.innerHTML = out + (Math.floor(t * 2) % 2 === 0 ? '<span class="caret"></span>' : "");
}

// ---------------------------------------------------------------- camera
const C = (x, y, z) => ({ x, y, z });
const TC = C(700, 520, 1.3);
const CK = [
  [0, TC], [6.4, TC], [7.4, C(960, 540, 1.0)],
  [8.4, C(A.forge.x + 140, A.forge.y - 40, 1.18)], [13.6, C(A.forge.x + 140, A.forge.y - 40, 1.18)],
  [14.6, C((A.forge.x + A.preview.x) / 2, A.forge.y, 1.12)], [19.2, C((A.forge.x + A.preview.x) / 2, A.forge.y, 1.12)],
  [20.2, C(960, 540, 1.0)], [21.0, C(A.slotPal.x + 60, (A.vera.y + A.slotPal.y) / 2, 1.12)], [29.0, C(A.slotPal.x + 60, (A.vera.y + A.slotPal.y) / 2, 1.12)],
  [30.0, C(A.ring.x - 120, A.ring.y + 200, 1.25)], [34.6, C(A.ring.x - 120, A.ring.y + 220, 1.25)],
  [35.4, C(960, 540, 1.0)], [42.6, C(980, 520, 1.06)], [43.6, C(960, 540, 1.0)],
  [44.6, C(A.dlg.x, A.dlg.y, 1.32)], [49.4, C(A.dlg.x, A.dlg.y, 1.32)], [50.4, C(960, 540, 1.0)], [54.6, C(960, 540, 1.0)],
  [55.6, C(A.trust.x, A.trust.y, 1.4)], [58.2, C(A.trust.x, A.trust.y, 1.4)], [58.9, C(960, 540, 1.0)], [66.8, C(990, 520, 1.06)],
  [67.4, C(960, 540, 1.0)], [72.2, C(960, 540, 1.0)], [73.0, C(1150, 560, 1.06)], [76.4, C(1150, 560, 1.06)], [77.2, C(960, 540, 1.0)], [DUR, C(960, 540, 1.0)],
];
function camAt(t) {
  let i = 0; while (i < CK.length - 2 && t > CK[i + 1][0]) i++;
  const [t0, a] = CK[i], [t1, b] = CK[i + 1], u = eio(seg(t, t0, t1));
  return { x: lerp(a.x, b.x, u) + Math.sin(t * 0.31) * 2.5, y: lerp(a.y, b.y, u), z: lerp(a.z, b.z, u), speed: Math.hypot(b.x - a.x, b.y - a.y) / Math.max(0.3, t1 - t0) * (u > 0.12 && u < 0.88 ? 1 : 0) };
}

// ---------------------------------------------------------------- cursor: clicks and drags
const CLICKS = [[9.0, A.rogue], [9.8, A.next0], [10.9, A.gem], [11.7, A.next1], [12.0, A.name], [13.9, A.next2], [14.9, A.fitAll], [18.4, A.next3], [19.4, A.enter], [31.4, A.horn], [44.3, A.prove], [47.3, { x: A.dlg.x, y: A.dlg.y + 40 }], [47.8, A.op], [49.8, A.accept]];
const DRAGS = [[21.4, 22.8, "Ollo", A.ollo, A.slotScribe], [24.2, 25.6, "Vera", A.vera, A.slotPal, true], [26.8, 28.2, "Vera", A.vera, A.slotRogue]];
function cursorAt(t) {
  const d = DRAGS.find((x) => t >= x[0] - 0.6 && t < x[1] + 0.3);
  if (d) {
    const [t0, t1, who, from, to, refused] = d;
    if (t < t0) { const prev = [...CLICKS, ...DRAGS.map((x) => [x[1], x[4]])].filter((c) => c[0] < t0).sort((a, b) => b[0] - a[0])[0]; const p = prev ? prev[1] : { x: 1500, y: 900 }; const u = eio(seg(t, t0 - 0.6, t0 - 0.05)); return { x: lerp(p.x, from.x, u), y: lerp(p.y, from.y, u), s: 1 }; }
    if (t < t1) { const u = eio(seg(t, t0, t1)); return { x: lerp(from.x, to.x, u), y: lerp(from.y, to.y, u) - Math.sin(u * Math.PI) * 40, s: 0.92, ghost: who }; }
    if (refused) { const u = eio(seg(t, t1 + 0.05, t1 + 0.3)); return { x: lerp(to.x, from.x, u * 0.25), y: to.y, s: 1, ghost: t < t1 + 0.15 ? who : null }; }
    return { x: to.x, y: to.y, s: 1 };
  }
  const i = CLICKS.findIndex((c) => t < c[0] + 0.35);
  if (i < 0) return null;
  const [tc, p] = CLICKS[i];
  const prevs = [...CLICKS.slice(0, i), ...DRAGS.map((x) => [x[1], x[4]])].filter((c) => c[0] < tc - 0.01).sort((a, b) => b[0] - a[0]);
  const q = prevs[0] ? prevs[0][1] : { x: p.x + 220, y: p.y + 160 };
  const t0 = Math.max(prevs[0] ? prevs[0][0] + 0.3 : tc - 1.0, tc - 1.0);
  const u = eio(seg(t, t0, tc - 0.08));
  return { x: lerp(q.x, p.x, u), y: lerp(q.y, p.y, u), s: t >= tc && t < tc + 0.16 ? 0.8 : 1 };
}
const CURSOR_ON = (t) => (t > 8.0 && t < 19.8) || (t > 20.6 && t < 32.4) || (t > 43.6 && t < 50.2);

// ---------------------------------------------------------------- mascot (Warden)
const MINT = "#3EE6A8", DARKV = "#0d1f19", PX = 6;
const BODY = ["......##......", "......##......", "....######....", "...########...", "..##########..", "..##########..", "..#........#..", "..##########..", "..##########..", "..##########..", "...########...", "....##..##....", "....##..##....", "...###..###..."];
const termR = document.getElementById("term").getBoundingClientRect();
const SPOT = {
  caret: { x: termR.left + 820, y: termR.top + 470 }, termBar: { x: termR.left + 640, y: termR.top },
  appBar: { x: 1500, y: 60 }, fig1: { x: 1440, y: 90 }, fig2: { x: 1440, y: 90 }, phone: { x: 1640, y: 110 }, end: { x: 1330, y: 340 },
};
const MS = [
  [0, 1.6, null, null, "hidden"], [1.6, 2.2, SPOT.caret, SPOT.caret, "emerge"], [2.2, 5.0, SPOT.caret, SPOT.caret, "hold"], [5.0, 6.0, SPOT.caret, SPOT.fig1, "jump"],
  [6.0, 20.4, SPOT.fig1, SPOT.fig1, "hold"], [20.4, 21.4, SPOT.fig1, SPOT.appBar, "jump"], [21.4, 30.8, SPOT.appBar, SPOT.appBar, "hold"], [30.8, 31.8, SPOT.appBar, SPOT.fig1, "jump"],
  [31.8, 39.2, SPOT.fig1, SPOT.fig1, "hold"], [39.2, 40.2, SPOT.fig1, SPOT.appBar, "jump"], [40.2, 47.6, SPOT.appBar, SPOT.appBar, "hold"], [47.6, 48.6, SPOT.appBar, SPOT.fig2, "jump"],
  [48.6, 61.2, SPOT.fig2, SPOT.fig2, "hold"], [61.2, 62.2, SPOT.fig2, SPOT.appBar, "jump"], [62.2, 66.6, SPOT.appBar, SPOT.appBar, "hold"], [66.6, 67.6, SPOT.appBar, SPOT.phone, "jump"],
  [67.6, 70.2, SPOT.phone, SPOT.phone, "hold"], [70.2, 71.2, SPOT.phone, SPOT.end, "jump"], [71.2, DUR, SPOT.end, SPOT.end, "hold"],
];
function mascotAt(t) {
  const m = MS.find((s) => t >= s[0] && t < s[1]) || MS[MS.length - 1];
  const [t0, t1, a, b, kind] = m; if (kind === "hidden") return null;
  const u = seg(t, t0, t1); let x = a.x, y = a.y, sq = 1, pose = "stand", eyes = "n", prop = null;
  if (kind === "emerge") { y = a.y + 26 * (1 - eo(u)); sq = 0.8 + 0.2 * eo(u); }
  if (kind === "jump") {
    if (u < 0.18) sq = 1 - 0.25 * (u / 0.18);
    else if (u < 0.86) { const v = (u - 0.18) / 0.68; x = lerp(a.x, b.x, v); y = lerp(a.y, b.y, v) - Math.sin(v * Math.PI) * (70 + Math.abs(b.x - a.x) * 0.1); sq = 1.16; pose = "air"; }
    else { x = b.x; y = b.y; sq = 1 - 0.22 * Math.sin(((u - 0.86) / 0.14) * Math.PI); }
  }
  if (kind === "hold") {
    sq = 1 + 0.03 * Math.sin(t * Math.PI * 1.6);
    if ([4.2, 9.8, 16.4, 25.0, 35.0, 43.3, 52.0, 64.4, 73.4].some((b2) => t > b2 && t < b2 + 0.12)) eyes = "shut";
    if (t > 23.0 && t < 24.6) { eyes = "wide"; prop = "!"; }
    if ((t > 18.6 && t < 20.2) || (t > 26.6 && t < 30.0) || (t > 46.6 && t < 48.2)) { pose = "cheer"; eyes = "happy"; }
    if (t > 55.0 && t < 58.4) { eyes = "wide"; prop = "!"; }
    if (t > 75.0) { eyes = "shut"; sq = 0.9; }
  }
  return { x, y, sq, pose, eyes, prop };
}
const mctx = document.getElementById("mascot").getContext("2d");
function drawMascot(m) {
  mctx.clearRect(0, 0, 1920, 1080); if (!m) return;
  const px = PX, w = 14 * px, h = 14 * px * m.sq, ph = px * m.sq;
  const ox = Math.round((m.x - w / 2) / 3) * 3, oy = Math.round((m.y - h) / 3) * 3;
  mctx.fillStyle = "rgba(0,0,0,0.3)"; mctx.fillRect(ox + px * 2, Math.round(m.y) - 2, px * 10, 3);
  BODY.forEach((row, j) => { if (m.pose === "air" && j >= 11) return; [...row].forEach((c, i) => { if (c === "#") { mctx.fillStyle = j === 0 ? "#bfffe8" : MINT; mctx.fillRect(ox + i * px, oy + j * ph, px, Math.ceil(ph)); } }); });
  if (m.pose === "air") { mctx.fillStyle = MINT; mctx.fillRect(ox + 4 * px, oy + 11 * ph, px * 2, ph); mctx.fillRect(ox + 8 * px, oy + 11 * ph, px * 2, ph); }
  mctx.fillStyle = DARKV; mctx.fillRect(ox + 3 * px, oy + 6 * ph, px * 8, ph);
  mctx.fillStyle = "#e8fff6";
  if (m.eyes === "shut") { mctx.fillRect(ox + 4 * px, oy + 6.4 * ph, px * 2, ph * 0.3); mctx.fillRect(ox + 8 * px, oy + 6.4 * ph, px * 2, ph * 0.3); }
  else if (m.eyes === "happy") { [[4, 6], [5, 5.6], [8, 5.6], [9, 6]].forEach(([i, j]) => mctx.fillRect(ox + i * px, oy + j * ph, px, ph * 0.5)); }
  else if (m.eyes === "wide") { [[4, 6], [5, 6], [8, 6], [9, 6]].forEach(([i, j]) => mctx.fillRect(ox + i * px, oy + j * ph, px, ph)); }
  else { [[5, 6], [8, 6]].forEach(([i, j]) => mctx.fillRect(ox + i * px, oy + j * ph, px, ph)); }
  if (m.pose === "cheer") { mctx.fillStyle = MINT; mctx.fillRect(ox, oy + 2 * ph, px, ph * 4); mctx.fillRect(ox + 13 * px, oy + 2 * ph, px, ph * 4); }
  if (m.prop === "!") { mctx.fillStyle = "#ffd166"; mctx.fillRect(ox + 6 * px, oy - 6 * px, px * 2, px * 3); mctx.fillRect(ox + 6 * px, oy - 2 * px, px * 2, px); }
}

// ---------------------------------------------------------------- captions and chapters
const CAPS = [];
for (const l of LINES) {
  const parts = l.text.match(/[^.?:]+[.?:]/g) || [l.text]; const merged = [];
  for (const p of parts) { if (merged.length && merged[merged.length - 1].length < 34) merged[merged.length - 1] += p; else merged.push(p); }
  const tot = merged.reduce((s, p) => s + p.length, 0); let at = AT[l.id];
  merged.forEach((p, i) => { const dd = (p.length / tot) * VO[l.id]; CAPS.push({ t0: at, t1: at + dd + (i === merged.length - 1 ? 0.7 : 0.25), text: p.trim() }); at += dd; });
}
for (let i = 0; i < CAPS.length - 1; i++) CAPS[i].t1 = Math.min(CAPS[i].t1, CAPS[i + 1].t0);
window.CAPS = CAPS;
const CHAPTERS = [[5.8, 21.0, "Fig 1 · The Forge"], [21.0, 31.4, "Live · Deploy"], [31.4, 39.8, "Fig 2 · The dispatch line"], [39.8, 48.4, "Live · Prove"], [48.4, 61.8, "Fig 3 · Trust credits"], [61.8, 70.4, "Live · Worlds"]];

// ---------------------------------------------------------------- render
const cam = document.getElementById("cam"), ghost = document.getElementById("ghost"), gcv = ghost.querySelector("canvas"), cursorEl = document.getElementById("cursor"), vig = document.getElementById("vig").getContext("2d");
const term = document.getElementById("term"), app = document.getElementById("app"), fig0 = document.getElementById("fig0"), fig1 = document.getElementById("fig1"), fig2 = document.getElementById("fig2"), phone = document.getElementById("phone");
const endEl = document.getElementById("endcard"), captionEl = document.getElementById("caption"), chapterEl = document.getElementById("chapter"), appsub = document.getElementById("appsub");
const show = (el, v, dy = 50) => { el.style.opacity = v; el.style.transform = `translateY(${(1 - v) * dy}px)`; el.style.visibility = v > 0.01 ? "visible" : "hidden"; };
const fade = (t, a, b, c, d) => (t < a ? 0 : t < b ? eo(seg(t, a, b)) : t < c ? 1 : t < d ? 1 - eio(seg(t, c, d)) : 0);
// figure windows: a slow push-in on each figure
const FIGS = [[5.6, 21.2, 0], [31.2, 40.0, 1], [48.2, 62.0, 2]];
const figCam = (t, a, b) => { const u = seg(t, a, b); return { x: 960 + 16 * u, y: 560 - 10 * u, z: 1.12 + 0.1 * u, speed: 0 }; };
function camNow(t) {
  const src = srcOf(t), f = FIGS.find(([a, b]) => t >= a - 0.3 && t < b + 0.3);
  let c = src != null ? camAt(src) : f ? figCam(t, f[0], f[1]) : { x: 960, y: 540, z: 1, speed: 0 };
  // blend across each cut so the camera never jumps
  for (const [a] of SEGS.slice(1)) if (t >= a - 0.6 && t < a + 0.6) { const prev = figCam(a - 0.3, 0, 1), next = camAt(a + 0.6 + SEGS.find((s) => s[0] === a)[2]); const u = eio(seg(t, a - 0.6, a + 0.6)); c = { x: lerp(prev.x, next.x, u), y: lerp(prev.y, next.y, u), z: lerp(prev.z, next.z, u), speed: 0 }; }
  for (const [a] of FIGS) if (t >= a - 0.6 && t < a + 0.4 && a > 1) { const s0 = SEGS.find(([x, y]) => a > x && a <= y + 0.5); if (s0) { const prev = camAt(Math.min(s0[1], a - 0.6) + s0[2]); const u = eio(seg(t, a - 0.6, a + 0.4)); c = { x: lerp(prev.x, 960, u), y: lerp(prev.y, 560, u), z: lerp(prev.z, 1.12, u), speed: 0 }; } }
  if (t >= 70.4) c = { x: 960, y: 540, z: 1, speed: 0 };
  return c;
}
let ghostWho = "";
window.render = (t) => {
  const src = srcOf(t);
  const appSrc = src != null ? src : t < 39.8 ? 34.0 : t < 61.8 ? 52.4 : 75.0;
  applyApp(appSrc); applyPhone(t);
  const c = camNow(t);
  cam.style.transform = `translate(${960 - c.x * c.z}px,${540 - c.y * c.z}px) scale(${c.z})`;
  document.getElementById("blurwrap").style.filter = "none";
  show(term, t < 5.4 ? 1 : 1 - eio(seg(t, 5.4, 6.0)), 60); termAt(Math.min(t + 0.4, 6.2));
  show(app, Math.max(fade(t, 20.8, 21.4, 31.0, 31.6), fade(t, 39.4, 40.0, 48.0, 48.6), fade(t, 61.4, 62.0, 70.2, 70.8)), 0);
  show(fig0, fade(t, 5.5, 6.2, 20.8, 21.4)); show(fig1, fade(t, 31.0, 31.7, 39.6, 40.2)); show(fig2, fade(t, 48.0, 48.7, 61.6, 62.2));
  show(phone, fade(t, 66.4, 67.2, 70.2, 70.8), 120);
  if (fig0F.contentWindow.figAt) fig0F.contentWindow.figAt(clamp((t - 6.0) * 0.98, 0, 14.3), false);
  if (fig1F.contentWindow.figAt) fig1F.contentWindow.figAt(clamp((t - 31.6) * 1.5, 0, 12.9), false, t > 38 ? 3 : 2);
  const f3 = t < 55.6 ? 6.0 + Math.max(0, t - 48.6) * 1.93 : t < 58.4 ? 19.6 : 19.6 + (t - 58.4) * 1.5;
  if (fig2F.contentWindow.figAt) fig2F.contentWindow.figAt(Math.min(f3, 24.6));
  appsub.textContent = appSrc >= 67.2 ? ["· Neon City", "· Sky Islands", "· Star Fleet"][appSrc < 69.2 ? 0 : appSrc < 71.0 ? 1 : 2] + " · 127.0.0.1 · my-project" : "· Guild · 127.0.0.1 · my-project";
  const cu = src != null ? cursorAt(src) : null, on = cu && CURSOR_ON(src) && ((t > 21.2 && t < 29.6) || (t > 40.0 && t < 46.2));
  cursorEl.style.display = on ? "block" : "none";
  if (on) cursorEl.style.transform = `translate(${cu.x}px,${cu.y}px) scale(${(cu.s || 1) / c.z * 1.25})`;
  if (on && cu.ghost) {
    if (ghostWho !== cu.ghost) { ghostWho = cu.ghost; const h = Object.values(AW.eval("S.heroes")).find((x) => x.name.startsWith(cu.ghost)); if (h) { AW.drawHero(gcv, h); ghost.querySelector(".n").textContent = h.name; } }
    ghost.style.display = "flex"; ghost.style.left = cu.x + 30 + "px"; ghost.style.top = cu.y + 26 + "px";
  } else ghost.style.display = "none";
  drawMascot(mascotAt(t));
  vig.clearRect(0, 0, 1920, 1080);
  const vs = src != null && src > 29.6 && src < 31.2 ? Math.min(1, (src - 29.6) / 0.4, (31.2 - src) / 0.4) : 0;
  if (vs > 0) { const p = { x: 960 + (A.ring.x - c.x) * c.z, y: 540 + (A.ring.y - c.y) * c.z }; const g = vig.createRadialGradient(p.x, p.y, 110, p.x, p.y, 700); g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(1, `rgba(0,0,0,${0.55 * vs})`); vig.fillStyle = g; vig.fillRect(0, 0, 1920, 1080); }
  const eIn = t < 70.6 ? 0 : eo(seg(t, 70.6, 71.4)); endEl.style.opacity = eIn; endEl.style.transform = `translate(-50%,-50%) scale(${0.96 + 0.04 * eIn})`;
  const ch = CHAPTERS.find(([a, b]) => t >= a && t < b); chapterEl.style.opacity = ch ? Math.min(1, (t - ch[0]) / 0.4, (ch[1] - t) / 0.4) : 0; if (ch && chapterEl.textContent !== ch[2]) chapterEl.textContent = ch[2];
  const cap = CAPS.find((x) => t >= x.t0 && t < x.t1); captionEl.style.opacity = cap ? 1 : 0; if (captionEl.textContent !== (cap ? cap.text : "")) captionEl.textContent = cap ? cap.text : "";
};

// ---------------------------------------------------------------- events for the mixer (on this film's clock)
const EV = [];
for (const [id, t] of Object.entries(AT)) EV.push({ t, type: "vo", id });
const inv = (src, segi) => src - SEGS[segi][2];
for (const [t0, s, cps] of [[1.1, T1, 28], [3.5, T2, 28]]) for (let t = t0 - 0.4; t < t0 - 0.4 + s.length / cps && t < 5.6; t += 1 / 12) EV.push({ t, type: "key" });
EV.push({ t: 1.4, type: "chip", note: 76 }, { t: 2.4, type: "enter" }, { t: 4.9, type: "enter" }, { t: 5.5, type: "whoosh" });
// Fig 1: six fits, the gate, out
const fg = (x) => 6.0 + x / 0.98;
for (let i = 0; i < 6; i++) EV.push({ t: fg(1.4 + i * 1.7 + 0.6 + 0.5 * 1.1 * 0.45 + 0.2), type: "fit", i });
EV.push({ t: fg(1.4 + 10.2 + 0.8 + 0.1), type: "green" }, { t: fg(1.4 + 10.2 + 0.8 + 1.0 + 0.1), type: "place" }, { t: 20.8, type: "whoosh" });
// live deploy (src 23.6–34.0)
for (const d of DRAGS) if (d[0] > 23.6 && d[1] < 34) EV.push({ t: inv(d[0] - 0.05, 1), type: "click" }, { t: inv(d[1], 1), type: d[5] ? "buzz" : "place" });
EV.push({ t: inv(29.9, 1), type: "green" }, { t: inv(31.4, 1), type: "click" }, { t: inv(31.5, 1), type: "horn" }, { t: 31.0, type: "whoosh" });
// Fig 2
const f1 = (x) => 31.6 + x / 1.5;
EV.push({ t: f1(1.0 + 0.9 + 1.8 * 0.25), type: "press" }, { t: f1(1.0 + 0.9 + 1.8 * 0.7), type: "press" }, { t: f1(5.3 + 0.3), type: "probe" }, { t: f1(9.23), type: "stamp" }, { t: 39.5, type: "whoosh" });
// live prove (src 43.8–52.4)
for (const [t0, str, cps] of [[44.8, PROOF.pr, 30], [46.2, PROOF.tests, 26], [47.9, PROOF.op, 26]]) for (let t = t0; t < t0 + str.length / cps; t += 1 / 12) EV.push({ t: inv(t, 2), type: "key" });
EV.push({ t: inv(44.3, 2), type: "click" }, { t: inv(49.8, 2), type: "click" }, { t: inv(49.9, 2), type: "coin" }, { t: inv(50.6, 2), type: "level" }, { t: 48.0, type: "whoosh" });
// Fig 3: each quest outcome, the cage
const f3t = (x) => (x <= 19.6 ? 48.6 + (x - 6.0) / 1.93 : 58.4 + (x - 19.6) / 1.5);
for (let i = 3; i < 11; i++) { const x = i * 2.2 + 0.6; const o = ["S","S","S","C","B","E","S","E","E","R","S","S"][i]; if (x > 6 && x < 24.6) EV.push({ t: f3t(x), type: o === "B" || o === "E" ? "buzz" : o === "R" ? "chime" : "stamp" }); }
EV.push({ t: f3t(19.3), type: "cage" }, { t: 61.6, type: "whoosh" });
// live worlds (src 67.0–75.8)
EV.push({ t: inv(67.4, 3), type: "world" }, { t: inv(69.2, 3), type: "world" }, { t: inv(71.0, 3), type: "world" }, { t: 66.4, type: "whoosh" }, { t: 70.6, type: "chime" });
for (const m of MS) if (m[4] === "jump") EV.push({ t: m[0] + 0.12, type: "jump" }, { t: m[1] - 0.08, type: "land" });
window.EV = EV.filter((e) => e.t >= 0 && e.t < DUR).sort((a, b) => a.t - b.t);
window.DUR = DUR;
window.TEXTS = () => [];
window.READY = true;
