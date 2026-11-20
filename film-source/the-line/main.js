// The Line: renderer, lights, cameras per shot, subtitles and title
import * as THREE from 'three';
import { clamp, seg, ss, eio, lerp } from '/core/lib.js';
import { DUR, T, VO, SKY, shotAt, B } from './story.js';
import { makePost } from './post.js';
import { buildWorld, SX, SZ, BELT_Z, GATE_X, EDGE_Z } from './world.js';

const W = innerWidth, H = innerHeight, K = H / 1080, QS = new URLSearchParams(location.search);
const SSAA = +(QS.get('ssaa') ?? 2);
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H);
renderer.toneMapping = THREE.NeutralToneMapping; renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.getElementById('stage').appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.OrthographicCamera(-10, 10, 5, -5, 1, 1600);
const post = makePost(renderer, scene, camera, W, H, { ssaa: SSAA, aoRadius: .7, aoScale: 1.5, aoThickness: 1 });
post.bloom.threshold = .95; post.bloom.radius = .55;
const world = buildWorld(scene);

const hemi = new THREE.HemisphereLight('#eef6fb', '#c6b89c', 1.1); scene.add(hemi);
const sun = new THREE.DirectionalLight('#fff6e8', 2.6); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -.0006; sun.shadow.normalBias = .02; sun.shadow.radius = 3;
Object.assign(sun.shadow.camera, { left: -20, right: 20, top: 12, bottom: -12, near: 1, far: 140 }); sun.shadow.camera.updateProjectionMatrix();
scene.add(sun, sun.target);

const C = h => new THREE.Color(h);
const SK = SKY.map(k => ({ t: k[0], zen: C(k[1]), hor: C(k[2]), sun: C(k[3]), sunI: k[4], hs: C(k[5]), hg: C(k[6]), hI: k[7], el: k[8], az: k[9], night: k[10] }));
function skyAt(t) {
  let i = 0; while (i < SK.length - 2 && t > SK[i + 1].t) i++;
  const a = SK[i], b = SK[i + 1], u = ss(seg(t, a.t, b.t)), o = {};
  for (const k of ['zen', 'hor', 'sun', 'hs', 'hg']) o[k] = a[k].clone().lerp(b[k], u);
  for (const k of ['sunI', 'hI', 'el', 'az', 'night']) o[k] = lerp(a[k], b[k], u);
  return o;
}

// camera: orthographic isometric. Frustum height is the zoom.
const DEG = Math.PI / 180;
let CAM = {};
function cam(t) {
  const [t0, t1, name] = shotAt(t), u = seg(t, t0, t1), e = eio(u);
  let tg = [0, .6, 0], az = 45, el = 30, fh = 16, hzA = .5, hzB = 1.6, tiltB = .3;
  switch (name) {
    case 'loose': tg = [-1.5, .3, 1.2]; az = lerp(28, 44, u); el = 24; fh = lerp(15.5, 14.2, u); hzA = .25; hzB = .9; break;               // slow turntable, wide dusk sky
    case 'edge': { const z = lerp(3.4, EDGE_Z - .2, ss(seg(t, T.push + .3, T.fall2))); tg = [-3.0, .4, z]; az = 52; el = 27; fh = 6.2; tiltB = .26; break; }   // locked close on the shove
    case 'depot': tg = [SX.depot, 1.0, SZ + .4]; az = lerp(38, 42, u); el = 27; fh = 6.6; tiltB = .26; break;                                // tight on the first arrival
    case 'team': tg = [lerp(SX.team - 2.2, SX.team + 1.0, e), .7, SZ + .9]; az = 40; el = 30; fh = 7.6; tiltB = .28; break;                     // lateral truck along the row
    case 'forge': tg = [SX.forge + lerp(-.4, .5, u), .8, SZ + .4]; az = lerp(34, 46, u); el = lerp(25, 36, e); fh = lerp(7.4, 6.6, u); break;   // elevation rises as the pieces land
    case 'gate': tg = [GATE_X - .6, .7, BELT_Z - .3]; az = lerp(324, 316, u); el = 28; fh = lerp(5.6, 5.1, u); tiltB = .25; break;               // close on the refusal
    case 'office': tg = [lerp(SX.office - .6, SX.tower + .6, e), 1.2, SZ + .6]; az = 40; el = 30; fh = 8.4; break;                             // the truck continues
    case 'line': tg = [lerp(4, 0, e), lerp(1, .2, e), lerp(-1, .4, e)]; az = lerp(40, 46, u); el = lerp(30, 44, e); fh = lerp(9, 23.5, e); hzA = .6; hzB = 2; break;  // pure zoom out to the whole line
    default: tg = [SX.vault, lerp(1.9, 2.5, ss(seg(t, T.title - .6, T.title + .6))), SZ]; az = lerp(36, 41, seg(t, B(21), DUR)); el = 27; fh = lerp(5.6, 6.6, ss(seg(t, T.title - .6, T.title + .6))); tiltB = .3;   // vault, held
  }
  const D = Math.max(300, fh * 3), ce = Math.cos(el * DEG);
  camera.position.set(tg[0] + D * ce * Math.sin(az * DEG), tg[1] + D * Math.sin(el * DEG), tg[2] + D * ce * Math.cos(az * DEG));
  camera.up.set(0, 1, 0); camera.lookAt(tg[0], tg[1], tg[2]);
  const fw = fh * W / H; camera.left = -fw / 2; camera.right = fw / 2; camera.top = fh / 2; camera.bottom = -fh / 2; camera.near = 1; camera.far = D + fh * 5 + 800; camera.updateProjectionMatrix();
  const cot = 1 / Math.tan(el * DEG);
  post.comp.camDist.value = D; post.comp.hz0.value = hzA * fh * cot; post.comp.hz1.value = hzB * fh * cot;
  post.tilt.fy.value = .5; post.tilt.band.value = tiltB;
  CAM = { tg, az, el, fh, name };
}

// 2D layer: subtitles and title
const ov = document.getElementById('ov'); ov.width = W; ov.height = H; const g = ov.getContext('2d');
let DURS = {};
try { const r = await fetch('voices/dur.json'); if (r.ok) DURS = await r.json(); } catch (e) { }
const voDur = v => DURS[v.id] ?? v.text.length * .065;
const subSpan = v => { const i = VO.indexOf(v), nx = VO[i + 1]; let b = v.t + Math.max(1.8, voDur(v) + .6, v.text.length / 15 + 1.5); if (nx) b = Math.min(b, nx.t - .05); b = Math.min(b, T.title - .2); return [v.t - .05, b]; };
function hexIcon(x, y, s, top) {
  const P = a => [x + Math.cos(a) * s, y + Math.sin(a) * s * .58], pts = [0, 1, 2, 3, 4, 5].map(i => P(i * Math.PI / 3)), dy = s * .55;
  g.save();
  g.fillStyle = '#b9ad98'; g.beginPath(); g.moveTo(...pts[0]); g.lineTo(pts[0][0], pts[0][1] + dy); g.lineTo(pts[1][0], pts[1][1] + dy); g.lineTo(pts[2][0], pts[2][1] + dy); g.lineTo(pts[3][0], pts[3][1] + dy); g.lineTo(...pts[3]); g.closePath(); g.fill();
  g.fillStyle = '#9c917e'; g.beginPath(); g.moveTo(...pts[0]); g.lineTo(pts[0][0], pts[0][1] + dy); g.lineTo(pts[1][0], pts[1][1] + dy); g.lineTo(...pts[1]); g.closePath(); g.fill();
  g.fillStyle = top; g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(...p) : g.moveTo(...p)); g.closePath(); g.fill();
  g.restore();
}
const iconTop = t => t < B(4) ? '#ffa888' : t < B(17) ? '#ffc676' : t < B(21) ? '#f6cfc0' : '#a9d08e';
const SUBF = `600 ${Math.round(44 * K)}px Quicksand`;
function wrap(text, maxW) { g.font = SUBF; if (g.measureText(text).width <= maxW) return [text]; const w = text.split(' '); let best = null;
  for (let i = 1; i < w.length; i++) { const a = w.slice(0, i).join(' '), b = w.slice(i).join(' '), d = Math.abs(g.measureText(a).width - g.measureText(b).width); if (!best || d < best[0]) best = [d, a, b]; } return [best[1], best[2]]; }
function spaced(text, x, track) { const ws = [...text].map(ch => g.measureText(ch).width), tot = ws.reduce((a, b) => a + b, 0) + track * (text.length - 1); let cx = x - tot / 2; const pos = []; [...text].forEach((ch, i) => { pos.push(cx); cx += ws[i] + track; }); return pos; }
const TITLE = 'AGENT COMPANY WORLD', SUBLINE = 'python3 agent_company.py launch', FINE = 'An illustration. The real recorded run is in docs/WORLD-GUIDE.md';
function title(t) {
  const t0 = T.title, y = 250 * K;
  { const a = ss(seg(t, t0 - .2, t0 + .8)); let gr = g.createLinearGradient(0, 0, 0, 420 * K); gr.addColorStop(0, `rgba(24,44,86,${.55 * a})`); gr.addColorStop(1, 'rgba(24,44,86,0)'); g.fillStyle = gr; g.fillRect(0, 0, W, 420 * K);
    gr = g.createLinearGradient(0, H - 170 * K, 0, H); gr.addColorStop(0, 'rgba(24,44,86,0)'); gr.addColorStop(1, `rgba(24,44,86,${.6 * a})`); g.fillStyle = gr; g.fillRect(0, H - 170 * K, W, 170 * K); }
  g.save(); g.font = `600 ${Math.round(78 * K)}px "Josefin Sans"`; g.textBaseline = 'alphabetic'; g.textAlign = 'left';
  const pos = spaced(TITLE, W / 2, 16 * K);
  g.save(); g.beginPath(); g.rect(0, 0, W, y + 14 * K); g.clip();
  [...TITLE].forEach((ch, i) => { const s = t - (t0 + i * .055); if (s < 0) return;
    const off = s < .28 ? 110 * K * Math.pow(1 - s / .28, 2) : -Math.sin((s - .28) * 14) * Math.exp(-(s - .28) * 8) * 10 * K;
    g.shadowColor = 'rgba(20,40,70,.4)'; g.shadowBlur = 18 * K; g.shadowOffsetY = 4 * K; g.fillStyle = '#ffffff'; g.fillText(ch, pos[i], y + off); });
  g.restore();
  const wl = ss(seg(t, t0, t0 + .8)); g.strokeStyle = 'rgba(255,255,255,.75)'; g.lineWidth = 2 * K; g.beginPath(); g.moveTo(W / 2 - 360 * K * wl, y + 22 * K); g.lineTo(W / 2 + 360 * K * wl, y + 22 * K); g.stroke();
  g.textAlign = 'center'; g.shadowColor = 'rgba(20,40,70,.45)'; g.shadowBlur = 12 * K; g.shadowOffsetY = 2 * K;
  g.globalAlpha = ss(seg(t, t0 + 1.3, t0 + 1.9)); g.font = `600 ${Math.round(36 * K)}px Quicksand`; g.fillStyle = '#fffdf8'; g.fillText(SUBLINE, W / 2, y + 78 * K);
  g.globalAlpha = ss(seg(t, t0 + .9, t0 + 1.4)); g.font = `500 ${Math.round(31 * K)}px Quicksand`; g.fillStyle = 'rgba(255,255,255,.96)'; g.fillText(FINE, W / 2, H - 70 * K);
  g.restore();
}
function hud(t) {
  g.clearRect(0, 0, W, H);
  if (QS.get('nohud')) return;
  if (t >= T.title || QS.get('poster')) title(QS.get('poster') ? T.title + 5 : t);
  if (QS.get('poster')) return;
  const v = VO.find(v => { const [a, b] = subSpan(v); return t >= a && t < b; });
  if (v) {
    const [a, b] = subSpan(v), al = ss(seg(t, a, a + .18)) * (1 - ss(seg(t, b - .2, b))), lines = wrap(v.text, W * .8);
    { const day = 1 - skyAt(t).night; if (day > .01) { const gr = g.createLinearGradient(0, H - 300 * K, 0, H); gr.addColorStop(0, 'rgba(22,34,70,0)'); gr.addColorStop(.55, `rgba(22,34,70,${.5 * day * al})`); gr.addColorStop(1, `rgba(22,34,70,${.62 * day * al})`); g.fillStyle = gr; g.fillRect(0, H - 300 * K, W, 300 * K); } }
    g.save(); g.globalAlpha = al; g.font = SUBF; g.textBaseline = 'middle'; g.textAlign = 'left';
    lines.forEach((ln, i) => { const tw = g.measureText(ln).width, pad = i === 0 ? 58 * K : 0, x0 = W / 2 - (tw + pad) / 2, y = H - (118 + (lines.length - 1 - i) * 58) * K;
      if (i === 0) { g.shadowColor = 'transparent'; hexIcon(x0 + 18 * K, y - 6 * K, 17 * K, iconTop(t)); }
      g.shadowColor = 'rgba(15,25,45,.85)'; g.shadowBlur = 14 * K; g.shadowOffsetY = 2 * K; g.fillStyle = '#fffdf8'; g.fillText(ln, x0 + pad, y + 2 * K); g.shadowBlur = 5 * K; g.fillText(ln, x0 + pad, y + 2 * K); });
    g.restore();
  }
}

function render(t) {
  const sk = skyAt(t); cam(t);
  const night = sk.night;
  hemi.color.copy(sk.hs); hemi.groundColor.copy(sk.hg); hemi.intensity = sk.hI;
  const se = sk.el * DEG, sa = sk.az * DEG; sun.color.copy(sk.sun); sun.intensity = sk.sunI;
  sun.target.position.set(0, 0, 0); sun.position.set(Math.cos(se) * Math.sin(sa) * 60, Math.sin(se) * 60, Math.cos(se) * Math.cos(sa) * 60);
  post.comp.zen.value.copy(sk.zen); post.comp.hor.value.copy(sk.hor);
  post.comp.stars.value = ss(seg(night, .5, 1)); post.comp.starOff.value = CAM.az / 60; post.comp.time.value = t;
  const gd = post.grade; gd.sat.value = lerp(1.04, 1.1, night); gd.contrast.value = lerp(.06, .12, night);
  gd.lift.value.setRGB(lerp(.018, .014, night), lerp(.016, .018, night), lerp(.024, .05, night)); gd.vig.value = lerp(.16, .3, night);
  post.bloom.strength = lerp(.22, .5, night);
  world.update(t, { night });
  post.composer.render(); hud(t);
}

function events() {
  const ev = world.EVS.slice();
  VO.forEach(v => ev.push({ t: v.t, type: 'vo', id: v.id, text: v.text }));
  ev.push({ t: T.title, type: 'title' });
  return ev.sort((a, b) => a.t - b.t);
}
window.TEXTS = t => {
  const out = [], v = VO.find(v => { const [a, b] = subSpan(v); return t >= a && t < b; });
  if (v) out.push({ id: v.id, text: v.text, x0: W * .1, y0: H - 200 * K, x1: W * .9, y1: H - 80 * K });
  if (t >= T.title) { out.push({ id: 'title', text: TITLE, x0: W * .2, y0: 180 * K, x1: W * .8, y1: 260 * K });
    if (t >= T.title + 1.3) out.push({ id: 'sub', text: SUBLINE, x0: W * .3, y0: 300 * K, x1: W * .7, y1: 340 * K });
    if (t >= T.title + .9) out.push({ id: 'fine', text: FINE, x0: W * .1, y0: H - 100 * K, x1: W * .9, y1: H - 50 * K }); }
  return out;
};
window.render = render; window.DUR = DUR; window.EV = events();
for (const f of ['600 78px "Josefin Sans"', '600 44px Quicksand', '500 30px Quicksand']) await document.fonts.load(f);
render(parseFloat(QS.get('t') ?? '10'));
window.READY = true;
