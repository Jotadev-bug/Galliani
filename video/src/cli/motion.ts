// GallianiCli motion (spec 015 R38, R39, R49-R53, R56, R78). Every foreground motion is a CliMotion derived from the
// scene data in timeline.ts; components animate nothing that is not in MOTIONS. Pure, so tests check the budget.
import {Easing, interpolate} from 'remotion';
import {
  BEATS, CAPTIONS, CAPTION_ENTER, CARD_ENTER_FRAMES, CARD_ENTER_ROWS, HIGHLIGHT_FRAMES, POSES, TERMINAL, charTimes,
  screenAt,
} from './timeline.ts';
import type {CliBeat, CliCaption, Pose, Screen, TargetId, Typing} from './timeline.ts';

export type MotionKind = 'caption' | 'cursor' | 'drag' | 'absorb' | 'expand' | 'count' | 'card' | 'gesture';
export const EMPHASIZED: readonly MotionKind[] = ['cursor', 'drag', 'absorb', 'expand', 'count', 'card', 'gesture'];

// R39: the only easings. `inOutCubic` is for `cursor` and `drag` only (a hand-held drag starts from rest).
export const EASINGS = {
  outExpo: Easing.out(Easing.exp),
  outQuart: Easing.out(Easing.poly(4)),
  inOutCubic: Easing.inOut(Easing.poly(3)),
} as const;
export type EasingName = keyof typeof EASINGS;
const EASING_OF: Record<MotionKind, EasingName> = {
  caption: 'outQuart', cursor: 'inOutCubic', drag: 'inOutCubic', absorb: 'outExpo', expand: 'outExpo',
  count: 'outQuart', card: 'outQuart', gesture: 'outQuart',
};

export interface CliMotion {
  kind: MotionKind;
  beat: string; // beat id
  target: string; // the element that moves
  start: number; // absolute frame
  frames: number;
  easing: EasingName;
  slide?: number; // px
  pose?: Pose; // gesture only
  aim?: TargetId; // gesture only: the element box it turns toward
  legs?: readonly number[]; // gesture only: frames per leg
}

/** 0 before `start`, exactly 1 from `start + frames` on (Easing.exp alone stops just short), eased in between. */
export function ramp(frame: number, start: number, frames: number, easing: EasingName = 'outQuart'): number {
  if (frames <= 0 || frame >= start + frames) return frame >= start ? 1 : 0;
  return interpolate(frame, [start, start + frames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: EASINGS[easing]});
}

export function deriveMotions(beats: readonly CliBeat[], captions: readonly CliCaption[]): CliMotion[] {
  const beatOf = (frame: number) => beats.find((b) => frame >= b.start && frame < b.start + b.duration) ?? beats[0];
  const out: CliMotion[] = [];
  const add = (kind: MotionKind, b: CliBeat, target: string, at: number, frames: number, extra: Partial<CliMotion> = {}) =>
    out.push({kind, beat: b.id, target, start: b.start + at, frames, easing: EASING_OF[kind], ...extra});
  for (const c of captions) {
    if (c.enterFrames > 0) add('caption', beatOf(c.start), 'caption', c.start - beatOf(c.start).start, c.enterFrames, {slide: CAPTION_ENTER.slide});
  }
  for (const b of beats) {
    // The cursor and the dragged icon count as one element (R50).
    if (b.cursor) add('cursor', b, 'cursor', b.cursor.at, b.cursor.frames);
    if (b.drag) add('drag', b, 'cursor', b.drag.at, b.drag.frames);
    if (b.absorb) add('absorb', b, 'icon', b.absorb.at, b.absorb.frames);
    if (b.expand) add('expand', b, 'window', b.expand.at, b.expand.frames);
    if (b.count) add('count', b, 'cost', b.count.at, b.count.frames);
    if (b.card) add('card', b, 'card', b.card.at, CARD_ENTER_FRAMES, {slide: CARD_ENTER_ROWS * TERMINAL.row});
    if (b.gesture) {
      const legs = POSES[b.gesture.pose].legs;
      add('gesture', b, 'robot', b.gesture.at, legs.reduce((s, f) => s + f, 0), {pose: b.gesture.pose, aim: b.gesture.target, legs});
    }
  }
  return out.sort((a, b) => a.start - b.start);
}

export const MOTIONS: readonly CliMotion[] = deriveMotions(BEATS, CAPTIONS);
export const GESTURES: readonly CliMotion[] = MOTIONS.flatMap((m) => (m.kind === 'gesture' ? [m] : []));

/** The motion of `kind` in this beat, if any. */
export function motionIn(beat: CliBeat, kind: MotionKind, motions: readonly CliMotion[] = MOTIONS): CliMotion | undefined {
  return motions.find((m) => m.beat === beat.id && m.kind === kind);
}

/** Eased progress of a motion at an absolute frame, with its own easing; 1 when there is no motion. */
export function progress(motion: CliMotion | undefined, frame: number): number {
  return motion ? ramp(frame, motion.start, motion.frames, motion.easing) : 1;
}

/** The frame a motion ends: its last moving frame plus one. */
export const endOf = (m: CliMotion) => m.start + m.frames;

// ---------------------------------------------------------------- what is on screen at a local frame

/** The string being typed in this beat at `local` (the shell line or the prompt), or null. */
export function typingAt(beat: CliBeat, local: number): {target: 'shell' | 'prompt'; typing: Typing} | null {
  if (beat.shot.kind === 'shell') return {target: 'shell', typing: beat.shot.typing};
  if (beat.shot.kind !== 'terminal') return null;
  const prompt = screenAt(beat.shot.keys, local).key.screen.prompt;
  return prompt ? {target: 'prompt', typing: prompt.typing} : null;
}

/** The cost the status and working lines show: the screen's value, or the count toward it (R56). */
export function costAt(beat: CliBeat, local: number, screen: Screen): number {
  const count = beat.count;
  if (!count || local < count.at) return screen.status.cost;
  return count.from + (count.to - count.from) * ramp(local, count.at, count.frames, EASING_OF.count);
}

// ---------------------------------------------------------------- budget (R49-R51)

/** The robot is on screen from the `launch-expand` content cut to the end of `end-card` (R76). */
export function robotShownAt(frame: number, beats: readonly CliBeat[] = BEATS, motions: readonly CliMotion[] = MOTIONS): boolean {
  const expand = beats.find((b) => b.id === 'launch-expand');
  const end = beats.find((b) => b.id === 'end-card');
  const cut = expand ? (motions.find((m) => m.beat === expand.id && m.kind === 'expand') ?? {start: expand.start, frames: 0}) : null;
  return !!cut && !!end && frame >= cut.start + cut.frames && frame < end.start + end.duration;
}

/** The elements that move at an absolute frame: active motions (gestures included) and a string being typed. */
export function movingAt(frame: number, motions: readonly CliMotion[] = MOTIONS, beats: readonly CliBeat[] = BEATS): string[] {
  const active = new Set<string>();
  for (const m of motions) if (frame >= m.start && frame < m.start + m.frames) active.add(m.target);
  const beat = beats.find((b) => frame >= b.start && frame < b.start + b.duration);
  if (beat) {
    const local = frame - beat.start;
    const typing = typingAt(beat, local);
    if (typing && typing.typing.frames > 0 && local >= typing.typing.from && local <= typing.typing.from + typing.typing.frames) {
      active.add(typing.target);
    }
  }
  return [...active];
}

/** The elements animating at an absolute frame for R50: the moving ones, plus the robot whenever it is on screen. */
export function activeAt(frame: number, motions: readonly CliMotion[] = MOTIONS, beats: readonly CliBeat[] = BEATS): string[] {
  const active = new Set(movingAt(frame, motions, beats));
  if (robotShownAt(frame, beats, motions)) active.add('robot');
  return [...active];
}

/** Local frames where the foreground changes without a motion: cuts, keys, typed characters, highlight ends. */
export function changeFrames(beat: CliBeat, motions: readonly CliMotion[] = MOTIONS): Set<number> {
  const frames = new Set<number>([0]);
  if (beat.shot.kind === 'terminal') {
    for (const k of beat.shot.keys) {
      frames.add(k.at);
      if (k.screen.fresh !== undefined) frames.add(k.at + HIGHLIGHT_FRAMES);
    }
  }
  for (let local = 0; local < beat.duration; local++) {
    const typing = typingAt(beat, local);
    if (typing) for (const t of charTimes(typing.typing)) frames.add(Math.ceil(t));
  }
  // A motion's end is a change too: the hover state, the drop's end, the content cut after the expand.
  for (const m of motions) if (m.beat === beat.id) frames.add(m.start + m.frames - beat.start);
  return new Set([...frames].flatMap((f) => (f >= 0 && f < beat.duration ? [f] : [])));
}

/** The longest run of frames in a beat in which nothing in the foreground moves or changes (R51). */
export function longestHold(beat: CliBeat, motions: readonly CliMotion[] = MOTIONS, beats: readonly CliBeat[] = BEATS): number {
  const changes = changeFrames(beat, motions);
  let run = 0;
  let best = 0;
  for (let local = 0; local < beat.duration; local++) {
    if (movingAt(beat.start + local, motions, beats).length > 0) run = 0;
    else run = changes.has(local) ? 1 : run + 1;
    best = Math.max(best, run);
  }
  return best;
}

export const MIN_HOLD = 8;
export const MAX_ANIMATING = 3;

/** Every R49-R51 breach in a timeline; empty when the budget holds. */
export function budgetViolations(beats: readonly CliBeat[] = BEATS, motions: readonly CliMotion[] = MOTIONS): string[] {
  const out: string[] = [];
  for (const b of beats) {
    const emphasized = motions.flatMap((m) => (m.beat === b.id && EMPHASIZED.includes(m.kind) ? [m] : []));
    if (emphasized.length > 1) out.push(`${b.id}: ${emphasized.length} emphasized motions (${emphasized.map((m) => m.kind).join(', ')})`);
    const hold = longestHold(b, motions, beats);
    if (hold < MIN_HOLD) out.push(`${b.id}: longest hold ${hold} frames`);
    for (let f = b.start; f < b.start + b.duration; f++) {
      const active = activeAt(f, motions, beats);
      if (active.length > MAX_ANIMATING) out.push(`frame ${f}: ${active.join(', ')} animate at once`);
    }
  }
  return out;
}
