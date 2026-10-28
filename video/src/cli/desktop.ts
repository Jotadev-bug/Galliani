// The GallianiCli desktop act (spec 015 R66-R72, Decision 0038): where the cursor and the hero icon are at each
// frame, and the window's focus and shell line. Pure, so B-AC22 is tested without rendering.
import {ABSORB, BEATS, DESKTOP, SHELL_CARET, beatAt, typedText} from './timeline.ts';
import type {Box, CliBeat} from './timeline.ts';
import {MOTIONS, motionIn, progress, ramp} from './motion.ts';
import type {CliMotion} from './motion.ts';

export interface Point {
  x: number;
  y: number;
}

const HERO = DESKTOP.hero.tile;
/** The hero tile's centre in its home slot; `lift` while hovered (R69). */
export const heroHome = (hovered = false): Point => ({x: HERO.x + HERO.width / 2, y: HERO.y + HERO.height / 2 - (hovered ? DESKTOP.hoverLift : 0)});

const DRAG_FROM = heroHome(true);
const DRAG_TO = DESKTOP.dragEnd;
// The control point sits 2 * apex above the chord's middle, so the arc's apex is `apex` px off the chord.
const CONTROL = (() => {
  const dx = DRAG_TO.x - DRAG_FROM.x;
  const dy = DRAG_TO.y - DRAG_FROM.y;
  const length = Math.hypot(dx, dy);
  const normal = {x: dy / length, y: -dx / length}; // the chord's normal that points up the frame
  return {x: (DRAG_FROM.x + DRAG_TO.x) / 2 + normal.x * 2 * DESKTOP.apex, y: (DRAG_FROM.y + DRAG_TO.y) / 2 + normal.y * 2 * DESKTOP.apex};
})();

/** The drag arc, one quadratic Bezier from the home slot to over the shell line, for t in 0-1 (R70). */
export function dragPath(t: number): Point {
  const u = 1 - t;
  return {
    x: u * u * DRAG_FROM.x + 2 * u * t * CONTROL.x + t * t * DRAG_TO.x,
    y: u * u * DRAG_FROM.y + 2 * u * t * CONTROL.y + t * t * DRAG_TO.y,
  };
}
export const DRAG_CHORD = {from: DRAG_FROM, to: DRAG_TO};

const beatById = (id: string, beats: readonly CliBeat[]) => beats.find((b) => b.id === id);
const inBeat = (frame: number, b: CliBeat | undefined) => !!b && frame >= b.start && frame < b.start + b.duration;

export interface HeroState {
  center: Point; // the tile's centre
  scale: number;
  rotation: number;
  opacity: number;
  hovered: boolean;
  home: boolean; // in its home slot
  label: boolean; // the label rides with the tile until the drop
}

/** The hero icon at an absolute frame, or null once it has gone into the caret (R69-R71). */
export function heroIconAt(frame: number, beats: readonly CliBeat[] = BEATS, motions: readonly CliMotion[] = MOTIONS): HeroState | null {
  const beat = beats.find((b) => frame >= b.start && frame < b.start + b.duration) ?? beats[beats.length - 1];
  const still = {scale: 1, rotation: 0, opacity: 1, label: true};
  if (beat.id === 'desk-idle' || beat.id === 'end-seam') return {...still, center: heroHome(), hovered: false, home: true};
  if (beat.id === 'desk-hover') {
    const cursor = motions.find((m) => m.beat === beat.id && m.kind === 'cursor');
    const hovered = !cursor || frame >= cursor.start + cursor.frames;
    return {...still, center: heroHome(hovered), hovered, home: true};
  }
  if (beat.id === 'desk-drag') {
    const drag = motions.find((m) => m.beat === beat.id && m.kind === 'drag');
    return {...still, center: dragPath(progress(drag, frame)), hovered: true, home: false};
  }
  if (beat.id === 'desk-drop') {
    const absorb = motions.find((m) => m.beat === beat.id && m.kind === 'absorb');
    if (absorb && frame >= absorb.start + absorb.frames) return null;
    const t = progress(absorb, frame);
    // The fade starts ABSORB.fade frames before the end and reaches 0 on the absorb's last frame (R71, B-AC22).
    const fade = absorb ? ramp(frame, absorb.start + absorb.frames - ABSORB.fade, ABSORB.fade - 1, 'outQuart') : 1;
    return {
      center: {x: DRAG_TO.x + (SHELL_CARET.x - DRAG_TO.x) * t, y: DRAG_TO.y + (SHELL_CARET.y - DRAG_TO.y) * t},
      scale: 1 - (1 - ABSORB.scale) * t, rotation: 0, opacity: 1 - fade, hovered: true, home: false, label: false,
    };
  }
  return null;
}

/** The hero tile's box (scaled about its centre) and its label box, at a frame. */
export function heroBoxes(hero: HeroState): {tile: Box; label: Box | null; all: Box} {
  const size = HERO.width * hero.scale;
  const tile = {x: hero.center.x - size / 2, y: hero.center.y - size / 2, width: size, height: size};
  const home = DESKTOP.hero.labelBox;
  const label = hero.label ? {...home, x: hero.center.x - home.width / 2, y: home.y + (hero.center.y - heroHome().y)} : null;
  const left = Math.min(tile.x, label?.x ?? tile.x);
  const right = Math.max(tile.x + tile.width, label ? label.x + label.width : 0);
  const bottom = label ? label.y + label.height : tile.y + tile.height;
  return {tile, label, all: {x: left, y: tile.y, width: right - left, height: bottom - tile.y}};
}

/** The cursor's tip at an absolute frame, or null when it is off screen (R68). */
export function cursorAt(frame: number, beats: readonly CliBeat[] = BEATS, motions: readonly CliMotion[] = MOTIONS): Point | null {
  const hover = beatById('desk-hover', beats);
  const drop = beatById('desk-drop', beats);
  const cursor = hover && motions.find((m) => m.beat === hover.id && m.kind === 'cursor');
  if (!cursor || !drop || frame < cursor.start || frame >= drop.start + drop.duration) return null;
  const grab = (c: Point) => ({x: c.x + DESKTOP.grab.x, y: c.y + DESKTOP.grab.y});
  if (inBeat(frame, hover)) {
    const t = progress(cursor, frame);
    const to = grab(heroHome());
    return {x: DESKTOP.cursorEntry.x + (to.x - DESKTOP.cursorEntry.x) * t, y: DESKTOP.cursorEntry.y + (to.y - DESKTOP.cursorEntry.y) * t};
  }
  if (inBeat(frame, drop)) return grab(DRAG_TO); // the cursor stays still after the release (R71)
  const hero = heroIconAt(frame, beats, motions);
  return hero ? grab(hero.center) : null;
}

/** The window border is focused from the drop until the `launch-expand` content cut (R71). */
export function windowFocused(frame: number): boolean {
  const beat = beatAt(frame);
  if (beat.id === 'desk-drop' || beat.id === 'launch-type') return true;
  if (beat.id !== 'launch-expand') return false;
  const expand = motionIn(beat, 'expand');
  return !!expand && frame < expand.start + expand.frames;
}

/** The command typed after the shell prompt (R72); empty on the desktop. */
export function shellCommand(frame: number): string {
  const beat = beatAt(frame);
  return beat.shot.kind === 'shell' ? typedText(beat.shot.typing, frame - beat.start) : '';
}

/** The desktop icons show from frame 0 through `launch-type`, and again in `end-seam` (R72, R73). */
export function desktopShown(frame: number): boolean {
  const kind = beatAt(frame).shot.kind;
  return kind === 'desk' || kind === 'shell';
}
