// GallianiCli motion (spec 015 R38, R39, R49-R53, R56). Every foreground motion is a CliMotion derived from the
// scene data in timeline.ts; components animate nothing that is not in MOTIONS. Pure, so tests check the budget.
import {Easing, interpolate} from 'remotion';
import {
  BEATS, CAPTIONS, CAPTION_ENTER, CARD_ENTER_FRAMES, CARD_ENTER_ROWS, END, HIGHLIGHT_FRAMES, TERMINAL, charTimes,
  screenAt,
} from './timeline.ts';
import type {CliBeat, CliCaption, Screen, Typing} from './timeline.ts';

export type MotionKind = 'caption' | 'push' | 'entrance' | 'move' | 'count' | 'card';
export const EMPHASIZED: readonly MotionKind[] = ['push', 'entrance', 'move', 'count', 'card'];

export interface CliMotion {
  kind: MotionKind;
  beat: string; // beat id
  target: string; // the element that moves
  start: number; // absolute frame
  frames: number;
  slide?: number; // px
  zoom?: {from: number; to: number};
}

// R39: out-quart for every motion, never linear, never overshooting.
const OUT = Easing.out(Easing.poly(4));

/** 0 before `start`, 1 from `start + frames` on, eased in between. */
export function ramp(frame: number, start: number, frames: number): number {
  if (frames <= 0) return frame >= start ? 1 : 0;
  return interpolate(frame, [start, start + frames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: OUT});
}

export function deriveMotions(beats: readonly CliBeat[], captions: readonly CliCaption[]): CliMotion[] {
  const beatOf = (frame: number) => beats.find((b) => frame >= b.start && frame < b.start + b.duration) ?? beats[0];
  const out: CliMotion[] = [];
  for (const c of captions) {
    if (c.enterFrames > 0) {
      out.push({kind: 'caption', beat: beatOf(c.start).id, target: 'caption', start: c.start, frames: c.enterFrames, slide: CAPTION_ENTER.slide});
    }
  }
  for (const b of beats) {
    if (b.push) out.push({kind: 'push', beat: b.id, target: 'camera', start: b.start + b.push.at, frames: b.push.frames, zoom: {from: b.push.from, to: b.push.to}});
    if (b.entrance) out.push({kind: 'entrance', beat: b.id, target: 'window', start: b.start + b.entrance.at, frames: b.entrance.frames, slide: b.entrance.slide});
    if (b.move) out.push({kind: 'move', beat: b.id, target: 'mark', start: b.start + b.move.at, frames: b.move.frames});
    if (b.count) out.push({kind: 'count', beat: b.id, target: 'cost', start: b.start + b.count.at, frames: b.count.frames});
    if (b.card) out.push({kind: 'card', beat: b.id, target: 'card', start: b.start + b.card.at, frames: CARD_ENTER_FRAMES, slide: CARD_ENTER_ROWS * TERMINAL.row});
  }
  return out.sort((a, b) => a.start - b.start);
}

export const MOTIONS: readonly CliMotion[] = deriveMotions(BEATS, CAPTIONS);

/** The motion of `kind` in this beat, if any. */
export function motionIn(beat: CliBeat, kind: MotionKind, motions: readonly CliMotion[] = MOTIONS): CliMotion | undefined {
  return motions.find((m) => m.beat === beat.id && m.kind === kind);
}

/** Eased progress of a motion at an absolute frame; 1 when there is no motion. */
export function progress(motion: CliMotion | undefined, frame: number): number {
  return motion ? ramp(frame, motion.start, motion.frames) : 1;
}

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
  return count.from + (count.to - count.from) * ramp(local, count.at, count.frames);
}

// ---------------------------------------------------------------- budget (R49-R51)

/** The elements animating at an absolute frame: active motions plus a string being typed (R50). */
export function activeAt(frame: number, motions: readonly CliMotion[] = MOTIONS, beats: readonly CliBeat[] = BEATS): string[] {
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
  for (const m of motions) if (m.beat === beat.id) frames.add(m.start + m.frames - beat.start);
  if (beat.shot.kind === 'end') frames.add(END.ctaFrames);
  return new Set([...frames].flatMap((f) => (f >= 0 && f < beat.duration ? [f] : [])));
}

/** The longest run of frames in a beat in which nothing in the foreground moves or changes (R51). */
export function longestHold(beat: CliBeat, motions: readonly CliMotion[] = MOTIONS, beats: readonly CliBeat[] = BEATS): number {
  const changes = changeFrames(beat, motions);
  let run = 0;
  let best = 0;
  for (let local = 0; local < beat.duration; local++) {
    if (activeAt(beat.start + local, motions, beats).length > 0) run = 0;
    else run = changes.has(local) ? 1 : run + 1;
    best = Math.max(best, run);
  }
  return best;
}

export const MIN_HOLD = 8;

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
      if (active.length > 2) out.push(`frame ${f}: ${active.join(', ')} animate at once`);
    }
  }
  return out;
}
