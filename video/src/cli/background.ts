// The GallianiCli background field (spec 015 R58-R61, Decision 0037): the BRAND.bg base, three soft radial blobs
// and three sine-wave bands. A pure function of the frame, never of the beat. Every animated value is
// base + amp * cos(2π f / period) with a period of 8-12 s that divides DURATION, so the field turns at frame 0,
// moves at a constant phase rate, and equals itself at DURATION (the loop seam, R57).
import {BRAND, TUI} from './palette.ts';
import {DURATION, WIDTH} from './timeline.ts';

// R59: the only stop colors, as palette keys. Each gradient uses one key, so at most one accent hue.
export const FIELD_COLORS = {
  bg: BRAND.bg,
  surface: BRAND.surface,
  raised: BRAND.raised,
  border: TUI.border,
  muted: TUI.muted,
  accent: BRAND.accent,
  agent: TUI.agent,
} as const;
export type FieldColor = keyof typeof FIELD_COLORS;
export const ACCENTS: readonly FieldColor[] = ['accent', 'agent'];

export interface Osc {
  base: number;
  amp: number;
  period: number; // frames
}
// An accent blob's opacity: `peak * max(0, gate * cos)^2`. Orange (gate 1) shows near frame 0 and the end, with
// the mark; teal (gate -1) shows in between, so the two never show at once (R61).
export interface Gate {
  peak: number;
  period: number;
  gate: 1 | -1;
}
export interface BlobSpec {
  color: FieldColor;
  cx: Osc;
  cy: Osc;
  r: Osc;
  opacity: Osc | Gate;
}
export interface WaveSpec {
  color: FieldColor;
  opacity: number;
  y: Osc; // baseline
  amplitude: Osc;
  wavelength: number; // px
  phase: number; // radians at rest
  sway: {px: number; period: number}; // horizontal drift, distinct per layer (parallax)
  depth: number; // px the band fades over below its crest
}

export const BLOBS: readonly BlobSpec[] = [
  {color: 'border', cx: {base: 980, amp: 220, period: 360}, cy: {base: 520, amp: 70, period: 240}, r: {base: 1000, amp: 60, period: 360}, opacity: {base: 0.13, amp: 0.03, period: 240}},
  {color: 'accent', cx: {base: 1500, amp: 160, period: 240}, cy: {base: 230, amp: 90, period: 360}, r: {base: 820, amp: 50, period: 360}, opacity: {peak: 0.16, period: 360, gate: 1}},
  {color: 'agent', cx: {base: 380, amp: 160, period: 360}, cy: {base: 880, amp: 80, period: 240}, r: {base: 840, amp: 50, period: 240}, opacity: {peak: 0.15, period: 360, gate: -1}},
];

export const WAVES: readonly WaveSpec[] = [
  {color: 'muted', opacity: 0.05, y: {base: 250, amp: 20, period: 360}, amplitude: {base: 60, amp: 14, period: 240}, wavelength: 2000, phase: 4.0, sway: {px: 90, period: 360}, depth: 340},
  {color: 'muted', opacity: 0.07, y: {base: 790, amp: 24, period: 240}, amplitude: {base: 52, amp: 12, period: 360}, wavelength: 1600, phase: 0.4, sway: {px: 240, period: 360}, depth: 300},
  {color: 'border', opacity: 0.1, y: {base: 870, amp: 18, period: 360}, amplitude: {base: 40, amp: 10, period: 240}, wavelength: 1150, phase: 2.1, sway: {px: 150, period: 240}, depth: 240},
];

// Opacity along a blob's radius and down a band, as [offset, factor] gradient stops.
export const BLOB_STOPS: readonly (readonly [number, number])[] = [[0, 1], [0.35, 0.7], [0.7, 0.25], [1, 0]];
export const BAND_STOPS: readonly (readonly [number, number])[] = [[0, 1], [0.35, 0.55], [1, 0]];

export const FIELD_PERIODS: readonly number[] = [
  ...BLOBS.flatMap((b) => [b.cx.period, b.cy.period, b.r.period, b.opacity.period]),
  ...WAVES.flatMap((w) => [w.y.period, w.amplitude.period, w.sway.period]),
];

/** The phase of a component at a frame: a constant step of 2π / period per frame. */
export const phaseAt = (period: number, frame: number) => (2 * Math.PI * (frame % DURATION)) / period;
const osc = (o: Osc, frame: number) => o.base + o.amp * Math.cos(phaseAt(o.period, frame));
const opacityAt = (o: Osc | Gate, frame: number) =>
  'gate' in o ? o.peak * Math.max(0, o.gate * Math.cos(phaseAt(o.period, frame))) ** 2 : osc(o, frame);

export interface Blob {
  color: FieldColor;
  cx: number;
  cy: number;
  r: number;
  opacity: number;
}
export interface Wave {
  color: FieldColor;
  opacity: number;
  amplitude: number;
  wavelength: number;
  phase: number;
  y: number;
  parallax: number; // sway in px; distinct per layer
  depth: number;
}

/** The field at a frame: blobs then waves, painted in that order over BRAND.bg. */
export function backgroundField(frame: number): {blobs: Blob[]; waves: Wave[]} {
  return {
    blobs: BLOBS.map((b) => ({color: b.color, cx: osc(b.cx, frame), cy: osc(b.cy, frame), r: osc(b.r, frame), opacity: opacityAt(b.opacity, frame)})),
    waves: WAVES.map((w) => ({
      color: w.color,
      opacity: w.opacity,
      amplitude: osc(w.amplitude, frame),
      wavelength: w.wavelength,
      phase: w.phase + (2 * Math.PI * w.sway.px * Math.cos(phaseAt(w.sway.period, frame))) / w.wavelength,
      y: osc(w.y, frame),
      parallax: w.sway.px,
      depth: w.depth,
    })),
  };
}

/** The crest of a band at x. */
export const crestY = (w: Wave, x: number) => w.y + w.amplitude * Math.sin((2 * Math.PI * x) / w.wavelength + w.phase);
/** A band's gradient runs from above its highest crest to `depth` below its lowest. */
export const bandSpan = (w: Wave) => ({top: w.y - w.amplitude, bottom: w.y + w.amplitude + w.depth});

/** The band outline as an SVG path: the crest sampled every `step` px, closed along the bottom of the frame. */
export function wavePath(w: Wave, height: number, step = 24): string {
  const points: string[] = [];
  for (let x = -step; x <= WIDTH + step; x += step) points.push(`${x} ${crestY(w, x).toFixed(1)}`);
  return `M ${points.join(' L ')} L ${WIDTH + step} ${height} L ${-step} ${height} Z`;
}

function stopFactor(stops: readonly (readonly [number, number])[], t: number): number {
  if (t <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) {
    const [o1, f1] = stops[i];
    const [o0, f0] = stops[i - 1];
    if (t <= o1) return f0 + ((f1 - f0) * (t - o0)) / (o1 - o0);
  }
  return stops[stops.length - 1][1];
}

/** Each layer's color and effective alpha at a point, bottom to top, as the SVG paints them. */
function layersAt(frame: number, x: number, y: number): {color: FieldColor; alpha: number}[] {
  const {blobs, waves} = backgroundField(frame);
  const layers = blobs.map((b) => ({color: b.color, alpha: b.opacity * stopFactor(BLOB_STOPS, Math.hypot(x - b.cx, y - b.cy) / b.r)}));
  for (const w of waves) {
    const {top, bottom} = bandSpan(w);
    layers.push({color: w.color, alpha: y >= crestY(w, x) ? w.opacity * stopFactor(BAND_STOPS, (y - top) / (bottom - top)) : 0});
  }
  return layers;
}

const rgbOf = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

/** The field composited over BRAND.bg at a point, as 0-255 RGB. */
export function sampleField(frame: number, x: number, y: number): [number, number, number] {
  let rgb = rgbOf(FIELD_COLORS.bg);
  for (const {color, alpha} of layersAt(frame, x, y)) {
    const c = rgbOf(FIELD_COLORS[color]);
    rgb = rgb.map((v, i) => v * (1 - alpha) + c[i] * alpha);
  }
  return rgb as [number, number, number];
}

/** How much of each accent hue reaches a point after the layers above it. */
export function accentAt(frame: number, x: number, y: number): Record<'accent' | 'agent', number> {
  const layers = layersAt(frame, x, y);
  const out = {accent: 0, agent: 0};
  layers.forEach((layer, i) => {
    if (layer.color !== 'accent' && layer.color !== 'agent') return;
    out[layer.color] += layers.slice(i + 1).reduce((a, above) => a * (1 - above.alpha), layer.alpha);
  });
  return out;
}
