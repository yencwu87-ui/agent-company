// The Line: a floating hex platform with six stations, six agents, a belt, a gate and one seal.
// Everything is a function of t. No state is carried between frames.
import * as THREE from 'three';
import { clamp, lerp, seg, ss, eio, hash, TAU } from '/core/lib.js';
import { T, N, MOTIF, B } from './story.js';

const R3 = Math.sqrt(3);
const flat = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, flatShading: true, roughness: .9, ...o });
const glow = (c, e = c) => new THREE.MeshStandardMaterial({ color: c, emissive: e, emissiveIntensity: 0, flatShading: true, roughness: .8 });
function mesh(geo, mat, x = 0, y = 0, z = 0, parent) { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent && parent.add(m); return m; }
const box = (w, h, d, mat, x, y, z, p) => mesh(new THREE.BoxGeometry(w, h, d), mat, x, y + h / 2, z, p);
function gable(w, h, d, mat, x, y, z, p) {            // prism roof along z
  const s = new THREE.Shape(); s.moveTo(-w / 2, 0); s.lineTo(w / 2, 0); s.lineTo(0, h); s.closePath();
  const g = new THREE.ExtrudeGeometry(s, { depth: d, bevelEnabled: false }); g.translate(0, 0, -d / 2);
  return mesh(g, mat, x, y, z, p);
}

// arrival curves (STYLE.md section 5). The event time is the landing.
function dropAt(g, t, t0, h = 2.6) {
  const s = t - t0;
  if (s < -.22) { g.visible = false; return; }
  g.visible = true;
  if (s < 0) { const u = (s + .22) / .22; g.position.y = g.userData.y0 + h * (1 - u * u); g.scale.set(1, 1, 1); return; }
  const sy = 1 - .16 * Math.exp(-12 * s) * Math.cos(26 * s), sx = 1 / Math.sqrt(sy);
  g.position.y = g.userData.y0 + Math.abs(Math.sin(15 * s)) * Math.exp(-9 * s) * .22; g.scale.set(sx, sy, sx);
}
const pop = (t, t0) => { const s = t - t0; return s < 0 ? 0 : 1 - Math.exp(-9 * s) * Math.cos(17 * s); };
function popAt(g, t, t0) { const k = pop(t, t0); g.visible = k > .001; g.scale.setScalar(Math.max(k, .001)); }

export const SX = { depot: -12.5, team: -7.5, forge: -2.5, office: 3.2, tower: 7.8, vault: 12.3 };
export const SZ = -2.3, BELT_Z = 1.7, GATE_X = .9, EDGE_Z = 5.25;
const ORDER = ['depot', 'team', 'forge', 'office', 'tower', 'vault'];
const PIECE_COL = ['#5b7fe0', '#9a7fe8', '#f0925c', '#4fb89a', '#ef7a62', '#f2c84e'];
const ROLE_COL = ['#f0925c', '#4fb89a', '#9a7fe8', '#5b7fe0', '#ef7a62', '#6a9a5a'];

export function buildWorld(scene) {
  const W = new THREE.Group(); scene.add(W);
  const EVS = [];
  const ev = (t, type, o = {}) => EVS.push({ t, type, ...o });

  // ---- platform: pointy-top hex columns, thin cap over a sunk darker column ----
  const cells = [];
  for (let r = -3; r <= 3; r++) for (let q = -14; q <= 14; q++) { const x = R3 * (q + r / 2), z = 1.5 * r; if (Math.abs(x) <= 16.6) cells.push([x, z, r]); }
  const capG = new THREE.CylinderGeometry(.985, .985, .16, 6), colG = new THREE.CylinderGeometry(.985, .985, 1.5, 6);
  const caps = new THREE.InstancedMesh(capG, flat('#ffffff'), cells.length), cols = new THREE.InstancedMesh(colG, flat('#ffffff'), cells.length);
  const M4 = new THREE.Matrix4(), col = new THREE.Color();
  cells.forEach(([x, z, r], i) => {
    const j = (hash(i * 3.1 + 7) - .5) * .07, grass = Math.abs(r) === 3 && hash(i + 91) > .45, road = Math.abs(z - BELT_Z) < .9;
    M4.makeTranslation(x, -.08, z); caps.setMatrixAt(i, M4);
    M4.makeTranslation(x, -.93, z); cols.setMatrixAt(i, M4);
    col.set(grass ? '#a9d08e' : road ? '#dcd6cb' : '#ece6da').offsetHSL(0, 0, j); caps.setColorAt(i, col);
    col.set(grass ? '#b79a72' : '#c9bca8').offsetHSL(0, 0, j); cols.setColorAt(i, col);
  });
  caps.receiveShadow = true; cols.receiveShadow = true; cols.castShadow = true; W.add(caps, cols);

  // ---- belt (present from the start, idle until the line runs) ----
  const belt = new THREE.Group(); W.add(belt);
  box(31, .2, .9, flat('#9aa0aa'), 0, 0, BELT_Z, belt);
  const rollG = new THREE.CylinderGeometry(.09, .09, .92, 6); rollG.rotateX(Math.PI / 2);
  const rollers = []; for (let i = 0; i < 52; i++) rollers.push(mesh(rollG, flat('#6f7682'), -15.3 + i * .6, .22, BELT_Z, belt));

  // ---- lamps: six dark posts mark the six stations from the first frame ----
  const lampOn = { depot: T.depotLamp, team: T.teamLamp, forge: T.forgeLamp, office: T.officeLamp, tower: T.windows[2], vault: T.seal + .15 };
  const lamps = {};
  ORDER.forEach((k, i) => {
    const g = new THREE.Group(); g.position.set(SX[k], 0, .15); W.add(g);
    mesh(new THREE.CylinderGeometry(.05, .07, 1.1, 5), flat('#8f949c'), 0, .55, 0, g);
    const m = glow('#d9d2c4', '#ffc676'); mesh(new THREE.IcosahedronGeometry(.17, 0), m, 0, 1.2, 0, g);
    lamps[k] = m; ev(lampOn[k], 'lamp', { note: [N.A4, N.B4, N.D5, N.E5, N.Fs5, N.A5][i], what: k });
  });

  // ---- stations ----
  const S = {};
  const station = (k, build) => { const g = new THREE.Group(); g.position.set(SX[k], 0, SZ); g.userData.y0 = 0; W.add(g); build(g); S[k] = g; return g; };
  const win = (g, x, y, z, w = .26, h = .3, ry = 0) => { const m = glow('#3d4660', '#ffc676'); const q = mesh(new THREE.BoxGeometry(w, h, .04), m, x, y, z, g); q.rotation.y = ry; q.castShadow = false; return m; };

  const depotWin = [];
  station('depot', g => {
    box(3.0, 1.4, 2.1, flat('#a9cbe8'), 0, 0, 0, g); gable(3.3, .8, 2.3, flat('#4f7fb8'), 0, 1.4, 0, g).rotation.y = Math.PI / 2;
    box(.7, .9, .05, flat('#3d5f96'), 0, 0, 1.06, g);
    for (const x of [-1, 1]) depotWin.push(win(g, x, .85, 1.07));
  });
  ev(T.depot, 'drop', { note: N.D4, what: 'depot', size: 3 });

  const houses = [], houseWin = [];
  [['#f5c2b0', '#d9644a'], ['#b5dccb', '#3f8f86'], ['#e9c9e6', '#6a5a8e']].forEach(([wall, roof], i) => {
    const g = new THREE.Group(); g.position.set(SX.team - 1.6 + i * 1.6, 0, SZ); g.userData.y0 = 0; W.add(g);
    box(1.0, .72, 1.0, flat(wall), 0, 0, 0, g); gable(1.2, .52, 1.16, flat(roof), 0, .72, 0, g);
    box(.26, .44, .04, flat(roof), -.2, 0, .51, g); houseWin.push(win(g, .22, .42, .51, .22, .22));
    houses.push(g); ev(T.houses[i], 'drop', { note: [N.Fs4, N.A4, N.B4][i], what: 'house', size: 1 });
  });

  const pieces = [];
  station('forge', g => {
    box(4.6, .3, 1.7, flat('#fbf3e6'), 0, 0, 0, g);
    for (let i = 0; i < 6; i++) box(.44, .34, .44, flat('#e3dccd'), -1.8 + i * .72, .3, 0, g);
  });
  ev(T.forge, 'drop', { note: N.D4, what: 'forge', size: 3 });
  for (let i = 0; i < 6; i++) {
    const m = glow(PIECE_COL[i]); const p = mesh(new THREE.IcosahedronGeometry(.22, 0), m, SX.forge - 1.8 + i * .72, .86, SZ, W); p.userData.y0 = .86;
    pieces.push([p, m]); ev(T.pieces[i], 'piece', { note: MOTIF[i], i });
  }

  // gate across the belt, just past the Forge
  const gate = new THREE.Group(); gate.position.set(GATE_X, 0, BELT_Z); W.add(gate);
  for (const z of [-.62, .62]) box(.14, 1.5, .14, flat('#8f949c'), 0, 0, z, gate);
  const barM = glow('#e0553b', '#ff5a3c'); const bar = box(.1, .5, 1.1, barM, 0, .32, 0, gate);
  ev(T.buzz, 'buzz'); ev(T.gateUp, 'gate', { note: N.D5 });

  const orders = [];
  station('office', g => {
    box(2.3, 1.3, 1.8, flat('#f7df8f'), 0, 0, 0, g); gable(2.6, .7, 2.0, flat('#6a5a8e'), 0, 1.3, 0, g).rotation.y = Math.PI / 2;
    box(1.5, .82, .06, flat('#cbb86a'), 0, .3, .92, g);
    for (let i = 0; i < 4; i++) { const o = mesh(new THREE.BoxGeometry(.26, .34, .05), glow('#ffffff', '#ffe9b8'), -.51 + i * .34, .72, .97, g); orders.push(o); }
  });
  ev(T.office, 'drop', { note: N.E4, what: 'office', size: 2 });
  T.orders.forEach((t, i) => ev(t, 'order', { note: [N.A4, N.B4, N.D5, N.E5][i], i }));

  const floors = [], floorWin = [];
  for (let i = 0; i < 3; i++) {
    const g = new THREE.Group(); g.position.set(SX.tower, i * .82, SZ); g.userData.y0 = i * .82; W.add(g);
    box(1.5, .8, 1.5, flat(i % 2 ? '#a3d2c0' : '#b5dccb'), 0, 0, 0, g);
    if (i === 2) box(1.7, .12, 1.7, flat('#3f8f86'), 0, .8, 0, g);
    const ws = []; for (const x of [-.42, 0, .42]) ws.push(win(g, x, .42, .76, .22, .3)); for (const z of [-.42, 0, .42]) ws.push(win(g, .76, .42, z, .22, .3, Math.PI / 2));
    floors.push(g); floorWin.push(ws); ev(T.tower[i], 'drop', { note: [N.D4, N.Fs4, N.A4][i], what: 'floor', size: 2 });
    ev(T.windows[i], 'window', { note: [N.D5, N.E5, N.Fs5][i], i });
  }

  let sealM, seal;
  station('vault', g => {
    box(2.3, 1.35, 1.9, flat('#fbf3e6'), 0, 0, 0, g); box(2.5, .16, 2.1, flat('#3f8f86'), 0, 1.35, 0, g);
    box(.9, .95, .06, flat('#4a5266'), 0, 0, .97, g);
    const d = mesh(new THREE.CylinderGeometry(.24, .24, .06, 8), flat('#7fd0b8'), 0, .5, 1.01, g); d.rotation.x = Math.PI / 2;
  });
  ev(T.vault, 'drop', { note: N.B4 - 12, what: 'vault', size: 3 });
  sealM = glow('#f2c84e', '#ffd670'); seal = mesh(new THREE.CylinderGeometry(.55, .62, .34, 6), sealM, SX.vault, 1.51 + .17, SZ, W); seal.userData.y0 = 1.68;
  mesh(new THREE.CylinderGeometry(.3, .3, .06, 6), flat('#fff3c4'), 0, .2, 0, seal).castShadow = false;
  ev(T.seal, 'seal', { note: N.D5 });

  // ---- trees: pop in at dawn ----
  const trees = T.trees.map((t, i) => {
    const g = new THREE.Group(); g.position.set([-14.6, -5.2, 0.4, 5.6, 10.2, 15][i], 0, -4.4 + (i % 2) * .25); W.add(g);
    mesh(new THREE.CylinderGeometry(.07, .09, .4, 5), flat('#9b7b5b'), 0, .2, 0, g);
    if (i % 2) mesh(new THREE.ConeGeometry(.42, 1.0, 6), flat('#3f8a5a'), 0, .9, 0, g); else mesh(new THREE.IcosahedronGeometry(.42, 0), flat('#7fc36a'), 0, .78, 0, g);
    ev(t, 'pop', { note: [N.A5, N.Fs5, N.E5, N.A5, N.B4 + 12, N.D6][i] }); return g;
  });

  // ---- agents ----
  const home = [[SX.team - 1.6, SZ + .95], [SX.team, SZ + .95], [SX.team + 1.6, SZ + .95], [SX.forge - 2.7, SZ + .7], [SX.office + 1.6, SZ + 1.0], [SX.tower + 1.3, SZ + 1.0]];
  const arrive = [T.houses[0] + .7, T.houses[1] + .7, T.houses[2] + .7, T.forge + 1.2, T.office + 1.0, T.tower[2] + .8];
  const agents = ROLE_COL.map((c, i) => {
    const g = new THREE.Group(); W.add(g);
    mesh(new THREE.CylinderGeometry(.15, .2, .46, 6), flat(c), 0, .23, 0, g); mesh(new THREE.IcosahedronGeometry(.16, 0), flat('#f3d2b3'), 0, .62, 0, g);
    g.scale.setScalar(1.5); g.userData.s = 1.5; return g;
  });
  const wander = (i, t) => {
    const cx = [-3.5, 4, -9, 8, 0, 11][i], cz = [3.2, 3.4, 3.0, 3.6, -3.6, 3.1][i], a = 2.2 + hash(i) * 1.6, w = .45 + hash(i + 5) * .35;
    return [cx + a * Math.sin(w * t + i * 1.7), cz + .9 * Math.sin(w * 1.63 * t + i * 2.3)];
  };
  const PUSH0 = [-3.0, 2.9], PUSH1 = [-3.0, EDGE_Z - .55];
  function agentPos(i, t) {
    let [x, z] = wander(i, t);
    if (i === 0) {     // agent 0 shoves crate B to the edge during 'edge', then walks home
      const a = eio(seg(t, T.push - 1.2, T.push + .2)), u = ss(seg(t, T.push + .3, T.fall2));
      const px = PUSH0[0], pz = Math.min(lerp(PUSH0[1], EDGE_Z, u) - .5, EDGE_Z - .75);
      x = lerp(x, px, a); z = lerp(z, pz, a);
    }
    const h = eio(seg(t, arrive[i] - 2.2, arrive[i]));
    return [lerp(x, home[i][0], h), lerp(z, home[i][1], h), h];
  }

  // ---- crates ----
  const crateG = new THREE.BoxGeometry(.6, .6, .6), crateM = () => flat('#d9b27c');
  const crA = mesh(crateG, crateM(), 0, 0, 0, W), crB = mesh(crateG, crateM(), 0, 0, 0, W), crG = mesh(crateG, crateM(), 0, 0, 0, W);
  const runners = [0, 1, 2, 3, 4].map(() => mesh(crateG, crateM(), 0, 0, 0, W));
  function fallOff(m, t, tFall, x, z0, z1, tSlide) {
    const u = ss(seg(t, tSlide, tFall)), s = t - tFall;
    m.visible = s < 1.6;
    if (s <= 0) { m.position.set(x, .25, lerp(z0, z1, u)); m.rotation.set(0, 0, 0); return; }
    m.position.set(x, .25 - 6 * s * s, z1 + 1.2 * s); m.rotation.set(s * 4.2, 0, s * 1.3);
  }
  ev(T.fall1, 'fall'); ev(T.fall2, 'fall');
  ev(T.crateAtGate, 'tap'); ev(T.cratePass, 'tap');
  ev(T.run, 'run'); T.replay.forEach((t, i) => ev(t, 'replay', { note: MOTIF[i], i }));

  function update(t, o) {
    const night = o.night;
    // rollers and running crates
    const run = ss(seg(t, T.run, T.run + 1.2)), travel = t < T.run ? 0 : (t - T.run) * 2.4 * 1;
    rollers.forEach((r, i) => { r.rotation.z = -travel * 6 - (t > T.gateUp ? 0 : 0); });
    runners.forEach((m, k) => {
      const x = -15.2 + ((travel + k * 6.1) % 30.4);
      m.position.set(x, .47, BELT_Z); const a = pop(t, T.run + .15 + k * .25) * clamp((15.2 - Math.abs(x)) / .6); m.visible = a > .01; m.scale.setScalar(Math.max(a, .01));
    });
    // lamps
    ORDER.forEach((k, i) => {
      const s = t - lampOn[k]; let e = s < 0 ? 0 : (1 - Math.exp(-s * 9)) * (1 + .5 * Math.exp(-s * 5));
      const rp = t - T.replay[i]; if (rp > 0) e += 1.3 * Math.exp(-rp * 5);
      lamps[k].emissiveIntensity = e * lerp(.9, 2.6, night);
    });
    // stations
    dropAt(S.depot, t, T.depot); depotWin.forEach(m => m.emissiveIntensity = ss(seg(t, T.depotLamp, T.depotLamp + .3)) * lerp(.3, 2.2, night));
    houses.forEach((g, i) => { dropAt(g, t, T.houses[i]); houseWin[i].emissiveIntensity = ss(seg(t, arrive[i], arrive[i] + .3)) * lerp(.3, 2.4, night); });
    dropAt(S.forge, t, T.forge);
    pieces.forEach(([p, m], i) => { dropAt(p, t, T.pieces[i], 2.0); p.rotation.y = t * .7 + i; const s = t - T.pieces[i]; m.emissiveIntensity = s < 0 ? 0 : lerp(.25, 1.1, night) * (1 + 1.5 * Math.exp(-s * 6)); });
    // gate: red and down until the sixth piece is in and the Forge lamp is on
    const up = eio(seg(t, T.gateUp, T.gateUp + .45)), bz = t - T.buzz;
    bar.position.y = .57 + up * 1.0 + (bz > 0 && bz < .5 ? Math.sin(bz * 60) * .02 * (1 - bz / .5) : 0);
    barM.color.set(up > .5 ? '#3fb98c' : '#e0553b'); barM.emissive.set(up > .5 ? '#4fe0a8' : '#ff5a3c');
    barM.emissiveIntensity = lerp(.5, 1.8, night) * (1 + (bz > 0 && bz < .6 ? 2.2 * Math.abs(Math.sin(bz * 22)) * (1 - bz / .6) : 0));
    dropAt(S.office, t, T.office); orders.forEach((m, i) => { const k = pop(t, T.orders[i]); m.visible = k > .01 && S.office.visible; m.scale.setScalar(Math.max(k, .01)); m.material.emissiveIntensity = lerp(.05, .55, night); });
    floors.forEach((g, i) => { dropAt(g, t, T.tower[i]); floorWin[i].forEach(m => m.emissiveIntensity = ss(seg(t, T.windows[i], T.windows[i] + .25)) * lerp(.3, 2.4, night)); });
    dropAt(S.vault, t, T.vault);
    // the seal: one heavy piece
    { const s = t - T.seal; seal.visible = s > -.3;
      if (s < 0) { const u = (s + .3) / .3; seal.position.y = seal.userData.y0 + 3.2 * (1 - u * u); seal.scale.set(1, 1, 1); }
      else { const sy = 1 - .3 * Math.exp(-9 * s) * Math.cos(20 * s), sx = 1 / Math.sqrt(sy); seal.position.y = seal.userData.y0 - (1 - sy) * .17; seal.scale.set(sx, sy, sx); }
      sealM.emissiveIntensity = s < 0 ? 0 : .35 + 1.6 * Math.exp(-s * 2.2); seal.rotation.y = .5; }
    trees.forEach((g, i) => popAt(g, t, T.trees[i]));
    // agents
    agents.forEach((g, i) => {
      const [x, z, h] = agentPos(i, t), [x2, z2] = agentPos(i, t + .05);
      const moving = Math.hypot(x2 - x, z2 - z) / .05;
      g.position.set(x, Math.abs(Math.sin(t * 9 + i * 2)) * .07 * clamp(moving / 1.2), z);
      if (moving > .05) g.rotation.y = Math.atan2(x2 - x, z2 - z);
      const sq = 1 + Math.sin(t * 9 + i * 2) * .04 * clamp(moving / 1.2); g.scale.set(1.5 / Math.sqrt(sq), 1.5 * sq, 1.5 / Math.sqrt(sq));
    });
    // crates
    fallOff(crA, t, T.fall1, -6.2, 3.3, EDGE_Z, T.fall1 - 1.5);
    fallOff(crB, t, T.fall2, PUSH0[0], PUSH0[1], EDGE_Z, T.push + .3);
    { // the crate that tries to jump the queue
      const a = pop(t, T.crateAtGate - 2.3); let x = lerp(-3.6, GATE_X - .85, eio(seg(t, T.crateAtGate - 2.1, T.crateAtGate)));
      const bz2 = t - T.buzz; if (bz2 > 0 && bz2 < .5) x -= Math.sin(bz2 / .5 * Math.PI) * .22;
      if (t > T.gateUp + .5) x += (t - T.gateUp - .5) * 2.4;
      const out = clamp((15 - x) / .6); crG.position.set(x, .47, BELT_Z); crG.visible = a * out > .01; crG.scale.setScalar(Math.max(a * out, .01)); crG.rotation.set(0, 0, 0);
    }
  }
  return { update, EVS, group: W, agentPos, PUSH0, PUSH1 };
}
