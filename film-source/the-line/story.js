// The Line: one timeline for picture, score, foley and subtitles. 96 bpm, 4/4, 26 bars.
export const BPM = 96, BEAT = 60 / BPM, BAR = BEAT * 4;
export const B = (bar, beat = 1) => ((bar - 1) * 4 + (beat - 1)) * BEAT;
export const DUR = B(27);                       // 65 s

export const T = {
  fall1: B(2, 3), push: B(3, 1), fall2: B(4, 3), hush1: [B(4, 3), B(5)],
  depot: B(5), depotLamp: B(5, 3),
  houses: [B(6), B(6, 3), B(7)], teamLamp: B(7, 3),
  forge: B(8), pieces: [B(8, 3), B(9), B(9, 3), B(10), B(10, 3), B(12)],          // the sixth lands after the refusal
  crateAtGate: B(11), buzz: B(11, 2), hush2: [B(11, 3), B(12)], forgeLamp: B(12, 2), gateUp: B(12, 3), cratePass: B(13),
  office: B(14), orders: [B(14, 3), B(14, 4), B(15), B(15, 2)], officeLamp: B(15, 2),
  tower: [B(15, 3), B(15, 4), B(16)], windows: [B(16, 2), B(16, 3), B(16, 4)], vault: B(16, 3),
  run: B(17), replay: [B(17, 3), B(18), B(18, 3), B(19), B(19, 3), B(20)], trees: [B(18, 2), B(18, 4), B(19, 2), B(19, 4), B(20, 2), B(20, 4)],
  seal: B(21), title: B(23), end: DUR,
};

// narration: American female (Kokoro af_heart). Times are where each line starts.
export const VO = [
  { id: 'v1', t: 0.6, text: 'Putting an AI agent to work still feels like trial and error.' },
  { id: 'v2', t: 5.4, text: 'Work goes missing, and nobody can show what was done.' },
  { id: 'v3', t: B(5) + .5, text: 'Agent Company gives the work a line, with six stations.' },
  { id: 'v4', t: B(6) + 1.7, text: 'First a project. Then a team, with one job each.' },
  { id: 'v5', t: B(8) + 1.0, text: 'Then the harness: six limits, fitted with one click.' },
  { id: 'v6', t: B(11) + .3, text: 'Nothing skips ahead. A station opens only when the one before it is done.' },
  { id: 'v7', t: B(14) + .4, text: 'Written orders go in, and one coordinator starts the line.' },
  { id: 'v8', t: B(17) + 1.2, text: 'The screen shows only what is really in your repo.' },
  { id: 'v9', t: B(21) + .9, text: 'Then the proof is sealed. Merging stays with you.' },
];

// shots: [t0, t1, name]. Hard cuts on bar lines.
export const SHOTS = [
  [0, B(3), 'loose'], [B(3), B(5), 'edge'], [B(5), B(6), 'depot'], [B(6), B(8), 'team'], [B(8), B(11), 'forge'],
  [B(11), B(14), 'gate'], [B(14), B(17), 'office'], [B(17), B(21), 'line'], [B(21), DUR + 1, 'vault'],
];
export const shotAt = t => SHOTS.find(s => t >= s[0] && t < s[1]) || SHOTS[SHOTS.length - 1];

// light is the clock: dusk -> night (lamps are the only bright things) -> dawn -> day
// [t, zenith, horizon, sun colour, sun intensity, hemi sky, hemi ground, hemi intensity, sun elevation, sun azimuth, night 0..1]
export const SKY = [
  [0,      '#6f6fa8', '#ffb394', '#ff9a68', 1.9, '#c9b6d6', '#b08a78', .85, 10, 250, .25],
  [B(4, 3),'#5a5c98', '#e79a8e', '#f0906c', 1.5, '#b3a4cc', '#9a7c78', .8,  7,  252, .4],
  [B(6, 3),'#171c44', '#4c467c', '#aab2ee', .95, '#7078b0', '#4a4870', .8,  38, 300, 1],
  [B(16),  '#171c44', '#4c467c', '#aab2ee', .95, '#7078b0', '#4a4870', .8,  38, 300, 1],
  [B(19),  '#8fa9cc', '#f6cfc0', '#ffd2a8', 1.8, '#d6dcec', '#b9a892', .9,  14, 80,  .25],
  [B(21),  '#8ccbe8', '#eef6f1', '#fff4e2', 2.6, '#eef6fb', '#c6b89c', 1.1, 34, 60,  0],
  [DUR,    '#88c8e8', '#eaf5f2', '#fff6e8', 2.7, '#eef6fb', '#c6b89c', 1.1, 40, 50,  0],
];

// D major pentatonic, as MIDI
export const N = { D3: 50, A3: 57, D4: 62, E4: 64, Fs4: 66, A4: 69, B4: 71, D5: 74, E5: 76, Fs5: 78, A5: 81, D6: 86 };
export const MOTIF = [N.D4, N.E4, N.Fs4, N.A4, N.B4, N.D5];
