// GallianiCli layout (spec 015 R57, R62-R65, R73): where the terminal, its transcript rows and the end card sit at
// each frame, and the seam state. Pure, so the framing is tested without rendering; the components draw these boxes.
import {TUI} from './palette.ts';
import {DESKTOP, END, HEIGHT, TERM, TERMINAL, WIDTH, beatAt, popupLines, screenAt} from './timeline.ts';
import type {Box, Entry, Screen} from './timeline.ts';
import {motionIn, progress} from './motion.ts';
import {cursorAt, desktopShown, heroIconAt, shellCommand, windowFocused} from './desktop.ts';
import {robotPose} from './pose.ts';

export type Rect = Box;

const ROW = TERMINAL.row;

// R62: the window is an opaque TUI.bg fill at full opacity, so the field never shows through it.
export const WINDOW = {background: TUI.bg, opacity: 1} as const;

// ---------------------------------------------------------------- the terminal window

const lerpRect = (a: Rect, b: Rect, t: number): Rect => ({
  x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, width: a.width + (b.width - a.width) * t, height: a.height + (b.height - a.height) * t,
});
const ACT3: Rect = {x: TERMINAL.x, y: TERMINAL.y, width: TERMINAL.width, height: TERMINAL.height};

/** The window at an absolute frame: its desktop rectangle, the `expand` toward the Act 3 frame, the Act 3 frame, or
 * null on the end card. The rectangle is interpolated, never CSS-scaled (R73). */
export function terminalRect(frame: number): Rect | null {
  const beat = beatAt(frame);
  if (beat.shot.kind === 'end') return null;
  if (beat.shot.kind !== 'terminal') return {...DESKTOP.window};
  const expand = motionIn(beat, 'expand');
  return expand ? lerpRect(DESKTOP.window, ACT3, progress(expand, frame)) : ACT3;
}

/** The TUI content (banner, transcript, prompt, status) shows once the window has finished growing (R73). */
export function tuiShown(frame: number): boolean {
  const beat = beatAt(frame);
  if (beat.shot.kind !== 'terminal') return false;
  const expand = motionIn(beat, 'expand');
  return !expand || frame >= expand.start + expand.frames;
}

/** The content box inside the window border, title bar and padding, relative to the window. */
export const CONTENT = {
  top: TERMINAL.border + TERMINAL.titleBar + TERMINAL.pad.top,
  height: TERMINAL.height - 2 * TERMINAL.border - TERMINAL.titleBar - TERMINAL.pad.top - TERMINAL.pad.bottom,
};

// ---------------------------------------------------------------- transcript rows (R64)

// The banner block: top border row, seven content rows (title, workspace, routing, settings, blank, two tips),
// bottom border row and one and a half rows of margin, which round to ten rows with the top margin.
export const BANNER_ROWS = 10;

export interface Row {
  part: 'blank' | 'main' | 'detail' | 'body';
  lead: string; // the lead column: a glyph, a detail lead or spaces
  text: string;
}

/** Word wrap at `width` columns, folding a word longer than a row, as Rich wraps transcript text. */
export function wrap(text: string, width: number): string[] {
  const rows: string[] = [];
  let line = '';
  for (const word of text.split(' ')) {
    const next = line ? `${line} ${word}` : word;
    if (next.length <= width) {
      line = next;
      continue;
    }
    if (line) rows.push(line);
    line = word;
    while (line.length > width) {
      rows.push(line.slice(0, width));
      line = line.slice(width);
    }
  }
  rows.push(line);
  return rows;
}

/** One entry as whole terminal rows: the lead glyph column is 2 wide, detail leads are 4 wide. */
export function entryRows(entry: Entry): Row[] {
  const cols = TERMINAL.transcriptColumns;
  const rows: Row[] = entry.kind === 'user' ? [{part: 'blank', lead: '', text: ''}] : [];
  wrap(entry.text, cols - 2).forEach((text, i) => rows.push({part: 'main', lead: i === 0 ? TERM.leaders[entry.kind] : '', text}));
  entry.detail?.forEach((line, d) => {
    wrap(line, cols - 4).forEach((text, i) => rows.push({part: 'detail', lead: d === 0 && i === 0 ? TERM.detailLead : TERM.detailIndent, text}));
  });
  if (entry.body) wrap(entry.body, cols - 2).forEach((text) => rows.push({part: 'body', lead: '', text}));
  return rows;
}

/** Rows below the transcript: working line, popup, approval card, prompt box and status line (in rows). */
export function bottomRows(screen: Screen): number {
  const popup = screen.popup ? popupLines(screen.popup.rows, screen.popup.selected).length : 0;
  return 1 + popup + (screen.approval ? 5.5 : 0) + (screen.prompt ? 2.5 : 0) + 1.5;
}

export interface TranscriptLayout {
  rows: Row[]; // entry rows after the banner block
  totalRows: number; // banner plus entry rows
  areaRows: number; // whole rows the transcript area shows
  offsetRows: number; // rows scrolled off the top
}

export function transcriptLayout(screen: Screen): TranscriptLayout {
  const rows = screen.entries.flatMap(entryRows);
  const totalRows = BANNER_ROWS + rows.length;
  const areaRows = Math.floor((CONTENT.height - bottomRows(screen) * ROW) / ROW);
  return {rows, totalRows, areaRows, offsetRows: Math.max(0, totalRows - areaRows)};
}

function screenOf(frame: number): Screen | null {
  const beat = beatAt(frame);
  return beat.shot.kind === 'terminal' ? screenAt(beat.shot.keys, frame - beat.start).key.screen : null;
}

/** The transcript scroll offset in px: always whole rows, so newest rows stay in view (R64). */
export function transcriptOffset(frame: number): number {
  const screen = screenOf(frame);
  return screen ? transcriptLayout(screen).offsetRows * ROW : 0;
}

/** Tops of the visible transcript rows, relative to the transcript area, and that area's height. */
export function visibleRows(frame: number): {tops: number[]; areaHeight: number} | null {
  const screen = screenOf(frame);
  if (!screen) return null;
  const {totalRows, areaRows, offsetRows} = transcriptLayout(screen);
  const tops: number[] = [];
  for (let i = offsetRows; i < totalRows; i++) tops.push((i - offsetRows) * ROW);
  return {tops, areaHeight: areaRows * ROW};
}

// ---------------------------------------------------------------- the end card (R65)

const blockHeight = END.markSize + END.gap + END.wordLine;
const blockTop = HEIGHT / 2 - blockHeight / 2;
const ctaWidth = TERM.command.length * END.wordSize * 0.6;

/** The end card block (mark, gap, `galliacli` line) and its call-to-action line. */
export const END_BLOCK: Rect = {x: WIDTH / 2 - Math.max(END.markSize, ctaWidth) / 2, y: blockTop, width: Math.max(END.markSize, ctaWidth), height: blockHeight};
export const END_CTA: Rect = {x: WIDTH / 2 - ctaWidth / 2, y: blockTop + END.markSize + END.gap, width: ctaWidth, height: END.wordLine};
export const END_MARK: Rect = {x: WIDTH / 2 - END.markSize / 2, y: blockTop, width: END.markSize, height: END.markSize};

/** The end card (the mark and `galliacli`) shows for the whole `end-card` beat. */
export const endCardShown = (frame: number) => beatAt(frame).shot.kind === 'end';

// ---------------------------------------------------------------- the seam state (R57)

export interface SceneState {
  icons: {label: string; tile: Rect}[] | null;
  hero: {center: {x: number; y: number}; scale: number; opacity: number; hovered: boolean; home: boolean} | null;
  window: {rect: Rect; focused: boolean; command: string} | null;
  cursor: boolean;
  robot: boolean;
  tui: boolean;
  cta: boolean;
}

/** What B-AC18 compares at frame 0 and the last frame, as data rather than pixels. */
export function sceneState(frame: number): SceneState {
  const hero = heroIconAt(frame);
  const rect = terminalRect(frame);
  return {
    icons: desktopShown(frame) ? DESKTOP.icons.map((i) => ({label: i.label, tile: i.tile})) : null,
    hero: hero && {center: hero.center, scale: hero.scale, opacity: hero.opacity, hovered: hero.hovered, home: hero.home},
    window: rect && {rect, focused: windowFocused(frame), command: tuiShown(frame) ? '(tui)' : shellCommand(frame)},
    cursor: cursorAt(frame) !== null,
    robot: robotPose(frame) !== null,
    tui: tuiShown(frame),
    cta: endCardShown(frame),
  };
}
