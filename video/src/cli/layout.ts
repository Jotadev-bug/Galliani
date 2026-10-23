// GallianiCli layout (spec 015 R57, R62-R65): where the terminal, its transcript rows, the mark and the end card sit
// at each frame. Pure, so the framing is tested without rendering; the components draw exactly these boxes.
import {TUI} from './palette.ts';
import {
  END, HEIGHT, HOOK, SEAM_MARK, TERM, TERMINAL, WIDTH, beatAt, popupLines, screenAt,
} from './timeline.ts';
import type {Entry, Screen} from './timeline.ts';
import {motionIn, progress} from './motion.ts';

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

const ROW = TERMINAL.row;

// R62: the window is an opaque TUI.bg fill at full opacity, so the field never shows through it.
export const WINDOW = {background: TUI.bg, opacity: 1} as const;

// ---------------------------------------------------------------- the terminal window

/** The terminal window at an absolute frame, after the entrance slide and the push zoom; null when none shows. */
export function terminalRect(frame: number): Rect | null {
  const beat = beatAt(frame);
  if (beat.shot.kind !== 'shell' && beat.shot.kind !== 'terminal') return null;
  const rect = {x: TERMINAL.x, y: TERMINAL.y + entranceOffset(frame), width: TERMINAL.width, height: TERMINAL.height};
  const z = zoomAt(frame);
  const origin = beat.push?.origin ?? {x: 0, y: 0};
  return {
    x: origin.x + (rect.x - origin.x) * z,
    y: origin.y + (rect.y - origin.y) * z,
    width: rect.width * z,
    height: rect.height * z,
  };
}

/** How far below its place the window still is during its entrance (R38). */
export function entranceOffset(frame: number): number {
  const entrance = motionIn(beatAt(frame), 'entrance');
  return entrance ? (entrance.slide ?? 0) * (1 - progress(entrance, frame)) : 0;
}

export function zoomAt(frame: number): number {
  const beat = beatAt(frame);
  const push = motionIn(beat, 'push');
  return push?.zoom ? push.zoom.from + (push.zoom.to - push.zoom.from) * progress(push, frame) : 1;
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

// ---------------------------------------------------------------- the mark and the end card (R57, R65)

const blockHeight = END.markSize + END.gap + END.wordLine;
const blockTop = HEIGHT / 2 - blockHeight / 2;
const ctaWidth = TERM.command.length * END.wordSize * 0.6;

/** The end card block (mark, gap, `galliacli` line) and its call-to-action line. */
export const END_BLOCK: Rect = {x: WIDTH / 2 - Math.max(END.markSize, ctaWidth) / 2, y: blockTop, width: Math.max(END.markSize, ctaWidth), height: blockHeight};
export const END_CTA: Rect = {x: WIDTH / 2 - ctaWidth / 2, y: blockTop + END.markSize + END.gap, width: ctaWidth, height: END.wordLine};
export const END_MARK_Y = blockTop + END.markSize / 2;

/** The hook prompt `>` line, beside the moved mark. */
export const HOOK_PROMPT: Rect = {x: HOOK.promptX, y: SEAM_MARK.y - HOOK.promptSize / 2, width: HOOK.promptSize * 1.2, height: HOOK.promptSize};

export interface MarkState {
  x: number; // center
  y: number;
  size: number;
  opacity: number;
}

/** The mark at an absolute frame: in the seam spot, moving aside in `hook-prompt`, or not shown. */
export function markAt(frame: number): MarkState | null {
  const beat = beatAt(frame);
  const seam = {x: SEAM_MARK.x, y: SEAM_MARK.y, size: SEAM_MARK.size, opacity: 1};
  if (beat.shot.kind === 'mark' || beat.shot.kind === 'end') return seam;
  if (beat.shot.kind !== 'hook-prompt') return null;
  const t = progress(motionIn(beat, 'move'), frame);
  return {...seam, x: seam.x + (HOOK.asideX - seam.x) * t, size: seam.size + (HOOK.asideSize - seam.size) * t};
}

/** The hook prompt appears once the mark has moved aside. */
export function hookPromptShown(frame: number): boolean {
  const beat = beatAt(frame);
  const move = motionIn(beat, 'move');
  return beat.shot.kind === 'hook-prompt' && (!move || frame >= move.start + move.frames);
}

/** The `galliacli` call to action shows for END.ctaFrames, then the card holds in the seam state. */
export function ctaShown(frame: number): boolean {
  const beat = beatAt(frame);
  return beat.shot.kind === 'end' && frame - beat.start < END.ctaFrames;
}
