// Independent QA checks for GallianiCli (spec 015 Part B, V2c-QA). These re-derive the motion budget, holds,
// framing and contrast from the raw scene data instead of from motion.ts/layout.ts helpers where possible, so a
// bug shared by a helper and its own test still shows here. Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {join, relative} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {ACCENTS, FIELD_PERIODS, accentAt, backgroundField, sampleField} from '../src/cli/background.ts';
import {END_CTA, HOOK_PROMPT, ctaShown, hookPromptShown, markAt, terminalRect} from '../src/cli/layout.ts';
import {costAt, ramp} from '../src/cli/motion.ts';
import {BRAND, TUI} from '../src/cli/palette.ts';
import {
  BEATS, CAPTIONS, CARD_ENTER_FRAMES, CARD_ENTER_ROWS, DURATION, END, FILE_ROWS_ALL, FILE_ROWS_SIG, GRID, HEIGHT,
  HIGHLIGHT_FRAMES, SAFE, SEAM_MARK, SLASH_ROWS, SPINNER_FPS, TERM, TERMINAL, VERB_SECONDS, WIDTH, AT_DONE, AT_PROMPT,
  charTimes, screenAt, typedText,
} from '../src/cli/timeline.ts';
import type {CliBeat} from '../src/cli/timeline.ts';

const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));
const read = (p: string) => readFileSync(here(p), 'utf8');
const CLI_DIR = here('../src/cli');

/** Every file under src/cli/, recursively, so a new subfolder cannot slip past the scans. */
function cliFiles(): {name: string; source: string}[] {
  return readdirSync(CLI_DIR, {recursive: true, withFileTypes: true})
    .filter((e) => e.isFile())
    .map((e) => {
      const path = join(e.parentPath, e.name);
      return {name: relative(CLI_DIR, path), source: readFileSync(path, 'utf8')};
    });
}

// ---------------------------------------------------------------- (1) determinism

test('QA-1: src/cli/** is deterministic and self-contained', () => {
  const files = cliFiles();
  assert.ok(files.length >= 6, 'all GallianiCli sources are scanned');
  for (const {name, source} of files) {
    assert.doesNotMatch(source, /Math\.random|\bDate\b|performance\.now|\bfetch\b|XMLHttpRequest|WebSocket|setTimeout|setInterval|requestAnimationFrame|delayRender/, `${name}: non-deterministic API`);
    assert.doesNotMatch(source, /https?:\/\/|@import|@font-face|\.woff|\.ttf|\.otf/, `${name}: external asset or font`);
    assert.doesNotMatch(source, /filter|blur|drop-shadow|mix-?blend|backdrop|box-?shadow|text-?shadow|<canvas/i, `${name}: filter, blur, blend or shadow`);
    // Only relative imports and the two runtime packages.
    for (const [, from] of source.matchAll(/^import[^'"]*['"]([^'"]+)['"]/gm)) {
      assert.ok(from.startsWith('./') || from === 'react' || from === 'remotion', `${name} imports ${from}`);
    }
    for (const [, file] of source.matchAll(/staticFile\(['"]([^'"]+)['"]\)/g)) {
      assert.ok(['galliani-mark-g.png', 'galliani-mark-star.png', 'galliani-mark.png'].includes(file), `${name} loads ${file}`);
    }
  }
  // The scan itself sees what it must reject.
  assert.match('const t = new Date();', /\bDate\b/);
  assert.match("style={{filter: 'blur(2px)'}}", /filter|blur/);
});

test('QA-1: backgroundField and sampleField are pure functions of the frame', () => {
  const order = [719, 0, 360, 1, 359, 240, 120, 600, 0, 719];
  const first = new Map<number, string>();
  for (const f of order) {
    const snap = JSON.stringify([backgroundField(f), sampleField(f, 333, 777), accentAt(f, 1500, 230)]);
    if (first.has(f)) assert.equal(snap, first.get(f), `frame ${f} differs on a second call`);
    else first.set(f, snap);
  }
  // Periodic: the field at f and f + DURATION match, for every frame.
  for (let f = 0; f < DURATION; f += 7) assert.deepEqual(backgroundField(f + DURATION), backgroundField(f));
  // Every period divides DURATION, so the seam is exact without the `% DURATION` fold.
  for (const p of FIELD_PERIODS) assert.equal(DURATION % p, 0, `period ${p}`);
});

// ---------------------------------------------------------------- (2) palette and copied strings

test('QA-2: BRAND.accent appears only in the mark and the hook caret, never inside the terminal (R28)', () => {
  const cli = read('../src/cli/GallianiCli.tsx');
  const sections = cli.split(/\n(?=const |export const )/);
  const users = sections.filter((s) => s.includes('BRAND.accent')).map((s) => s.match(/^(?:export )?const (\w+)/)?.[1]);
  assert.deepEqual(users.sort(), ['HookPrompt', 'Mark']);
  // Inside the terminal components only TUI colors appear.
  for (const s of sections.filter((x) => /^const (TerminalFrame|ShellShot|EntryView|Banner|Transcript|PlanPanel|Popup|ApprovalCard|PromptBox|TuiScreen|Bordered|Cursor|ENTRY_COLORS|STEP_COLORS)\b/.test(x))) {
    assert.doesNotMatch(s, /BRAND\./, `${s.match(/^const (\w+)/)?.[1]} uses a BRAND color inside the terminal`);
  }
});

const WIDGETS = read('../../galliani/tui/widgets.py');
const pyDict = (name: string) => {
  const m = WIDGETS.match(new RegExp(`^${name} = \\{([\\s\\S]*?)\\}`, 'm'));
  assert.ok(m, `${name} in widgets.py`);
  return Object.fromEntries([...m[1].matchAll(/"([a-z_]+)": "([^"]*)"/g)].map((x) => [x[1], x[2]]));
};
const pyNumber = (name: string) => {
  const m = WIDGETS.match(new RegExp(`^${name} = ([0-9.]+)`, 'm'));
  assert.ok(m, `${name} in widgets.py`);
  return Number(m[1]);
};

test('QA-2: glyphs and timings equal widgets.py (fails on drift)', () => {
  const leaders = pyDict('LEADERS');
  for (const [kind, glyph] of Object.entries(TERM.leaders)) assert.equal(glyph, leaders[kind], `LEADERS.${kind}`);
  const steps = pyDict('STEP_GLYPHS');
  for (const [state, glyph] of Object.entries(TERM.stepGlyphs)) assert.equal(glyph, steps[state], `STEP_GLYPHS.${state}`);
  assert.equal(SPINNER_FPS, pyNumber('SPINNER_FPS'));
  assert.equal(VERB_SECONDS, pyNumber('VERB_SECONDS'));
  assert.equal(HIGHLIGHT_FRAMES, Math.round(pyNumber('HIGHLIGHT_SECONDS') * 30));
  assert.equal(CARD_ENTER_FRAMES, Math.round(pyNumber('CARD_ENTER_SECONDS') * 30));
  assert.equal(CARD_ENTER_ROWS, pyNumber('CARD_ENTER_ROWS'));
  assert.ok(WIDGETS.includes(`lead = "${TERM.detailLead}" if index == 0 else "${TERM.detailIndent}"`), 'detail leads');
  // Status labels shown are real TUI labels.
  const labels = new Set(BEATS.flatMap((b) => (b.shot.kind === 'terminal' ? b.shot.keys.map((k) => k.screen.status.label) : [])));
  for (const label of labels) assert.ok(WIDGETS.includes(`"${label}"`), `status label ${label}`);
  // Fixture: a drifted glyph is caught.
  assert.notEqual('[v]', steps.verified);
});

// ---------------------------------------------------------------- (3) motion budget, re-derived from raw beats

type Element = 'caption' | 'camera' | 'window' | 'mark' | 'cost' | 'card' | 'typing';
const EMPHASIS_FIELDS = ['push', 'entrance', 'move', 'count', 'card'] as const;

function typingOf(beat: CliBeat, local: number) {
  if (beat.shot.kind === 'shell') return beat.shot.typing;
  if (beat.shot.kind !== 'terminal') return null;
  return screenAt(beat.shot.keys, local).key.screen.prompt?.typing ?? null;
}

/** Elements animating at an absolute frame, from the beat fields and caption data only. */
function animating(frame: number): Element[] {
  const beat = BEATS.find((b) => frame >= b.start && frame < b.start + b.duration) as CliBeat;
  const local = frame - beat.start;
  const out: Element[] = [];
  const within = (at: number, frames: number) => local >= at && local < at + frames;
  for (const c of CAPTIONS) if (frame >= c.start && frame < c.start + c.enterFrames) out.push('caption');
  if (beat.push && within(beat.push.at, beat.push.frames)) out.push('camera');
  if (beat.entrance && within(beat.entrance.at, beat.entrance.frames)) out.push('window');
  if (beat.move && within(beat.move.at, beat.move.frames)) out.push('mark');
  if (beat.count && within(beat.count.at, beat.count.frames)) out.push('cost');
  if (beat.card && within(beat.card.at, CARD_ENTER_FRAMES)) out.push('card');
  const typing = typingOf(beat, local);
  if (typing && typing.frames > 0) {
    const times = charTimes(typing);
    if (local >= Math.floor(times[0]) && local <= Math.ceil(times[times.length - 1])) out.push('typing');
  }
  return out;
}

/** Everything a viewer can see change in the foreground, except the field, spinner and caret. */
function foreground(frame: number): string {
  const beat = BEATS.find((b) => frame >= b.start && frame < b.start + b.duration) as CliBeat;
  const local = frame - beat.start;
  const r = (v: number) => Math.round(v * 100) / 100;
  const caption = CAPTIONS.find((c) => frame >= c.start && frame < c.end);
  const parts: unknown[] = [beat.id, caption?.text, caption ? r(ramp(frame - caption.start, 0, caption.enterFrames)) : null];
  const mark = markAt(frame);
  parts.push(mark && [r(mark.x), r(mark.y), r(mark.size), r(mark.opacity)], hookPromptShown(frame), ctaShown(frame));
  const rect = terminalRect(frame);
  parts.push(rect && [r(rect.x), r(rect.y), r(rect.width), r(rect.height)]);
  const typing = typingOf(beat, local);
  if (typing) parts.push(typedText(typing, local));
  if (beat.shot.kind === 'terminal') {
    const {key, since} = screenAt(beat.shot.keys, local);
    parts.push(beat.shot.keys.indexOf(key), costAt(beat, local, key.screen).toFixed(4));
    parts.push(key.screen.fresh !== undefined && since < HIGHLIGHT_FRAMES);
    if (beat.card) parts.push(r(ramp(local, beat.card.at, CARD_ENTER_FRAMES)));
  }
  return JSON.stringify(parts);
}

function longestStill(beat: CliBeat): number {
  let best = 1;
  let run = 1;
  for (let f = beat.start + 1; f < beat.start + beat.duration; f++) {
    run = foreground(f) === foreground(f - 1) ? run + 1 : 1;
    best = Math.max(best, run);
  }
  return best;
}

test('QA-3: at most one emphasized motion per beat, at most two animating elements per frame (R49, R50)', () => {
  for (const b of BEATS) {
    const emphasized = EMPHASIS_FIELDS.filter((k) => b[k] !== undefined);
    assert.ok(emphasized.length <= 1, `${b.id}: ${emphasized.join(', ')}`);
  }
  let peak = 0;
  for (let f = 0; f < DURATION; f++) {
    const a = animating(f);
    peak = Math.max(peak, a.length);
    assert.ok(a.length <= 2, `frame ${f}: ${a.join(', ')}`);
  }
  assert.ok(peak >= 1);
});

test('QA-3: every beat holds still for 8+ frames, the video ends on an 8+ frame hold (R51, R57)', () => {
  for (const b of BEATS) assert.ok(longestStill(b) >= 8, `${b.id}: longest still run ${longestStill(b)}`);
  const tail = Array.from({length: 8}, (_, i) => foreground(DURATION - 8 + i));
  assert.equal(new Set(tail).size, 1, 'the last 8 frames change');
  // Fixture: a beat whose screen changes every 4 frames has no hold.
  const busy = {...BEATS[3], shot: {kind: 'shell' as const, typing: {text: 'x'.repeat(40), from: 0, frames: 44}}};
  const saved = (BEATS as CliBeat[])[3];
  (BEATS as CliBeat[])[3] = busy;
  try {
    assert.ok(longestStill(busy) < 8);
  } finally {
    (BEATS as CliBeat[])[3] = saved;
  }
});

test('QA-3: grid, pace, beat length, caption length, no dead start (R23, R53-R55)', () => {
  assert.ok(DURATION >= 660 && DURATION <= 750, `${DURATION}`);
  let cursor = 0;
  for (const b of BEATS) {
    assert.equal(b.start, cursor);
    assert.equal(b.start % GRID, 0, `${b.id} start`);
    assert.ok(b.duration >= 30 && b.duration <= 90, `${b.id} ${b.duration}`);
    for (const k of EMPHASIS_FIELDS) {
      const m = b[k];
      if (m) assert.equal((b.start + m.at) % GRID, 0, `${b.id} ${k} start`);
    }
    cursor += b.duration;
  }
  assert.equal(cursor, DURATION);
  for (const c of CAPTIONS) {
    assert.equal(c.start % GRID, 0, `${c.text} start`);
    assert.ok(c.end - c.start >= 60 && c.end - c.start <= 150, `${c.text}`);
  }
  // Frame 0: the mark and a fully readable hook caption.
  assert.ok(markAt(0));
  const hook = CAPTIONS[0];
  assert.ok(hook.start === 0 && ramp(12, 0, hook.enterFrames) === 1);
});

test('QA-3: no banned motion kinds or easings in the component', () => {
  const cli = read('../src/cli/GallianiCli.tsx');
  assert.doesNotMatch(cli, /\binterpolate\(|\bspring\(|Easing\./, 'GallianiCli.tsx animates outside motion.ts');
  // Every transform is the push zoom, the entrance/card rise or the caption rise.
  for (const [t] of cli.matchAll(/transform: (?:\w+ \? )?('[^']*'|`[^`]*`|[^,}]+)/g)) {
    assert.match(t, /scale\(\$\{zoom\}\)|translateY\(\$\{(dy|rise|\(1 - rise\) \* CAPTION_ENTER\.slide)\}px\)|translate\(-50%, -50%\)|translateY\(-50%\)|translateY\(\$\{-offset\}px\)/, t);
  }
  for (const {name, source} of cliFiles()) {
    // Code only: copy such as the route id `gemini-3.1-flash-lite` is not a motion.
    const code = source.replace(/'[^'\n]*'/g, "''").replace(/\/\/.*$/gm, '');
    assert.doesNotMatch(code, /pulse|punch|bump|flash|glow|stagger|shake|wobble|Easing\.(linear|back|elastic|bounce|bezier|in\()/i, name);
  }
  const motion = read('../src/cli/motion.ts');
  assert.equal([...motion.matchAll(/\binterpolate\(/g)].length, 1, 'one interpolate, inside ramp()');
  assert.match(motion, /const OUT = Easing\.out\(Easing\.poly\(4\)\)/);
});

// ---------------------------------------------------------------- (4) contrast and restraint

const lum = ([r, g, b]: readonly number[]) => {
  const lin = (v: number) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};
const ratio = (a: readonly number[], b: readonly number[]) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const sat = (rgb: readonly number[]) => {
  const [max, min] = [Math.max(...rgb) / 255, Math.min(...rgb) / 255];
  const l = (max + min) / 2;
  return max === min ? 0 : (max - min) / (l > 0.5 ? 2 - max - min : max + min);
};
const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const blend = (fg: number[], bg: number[], a: number) => fg.map((v, i) => v * a + bg[i] * (1 - a));

test('QA-4: caption, call-to-action and hook prompt text keep 7:1 over the field at every other frame', () => {
  const text = rgb(BRAND.text);
  let worst = Infinity;
  for (let f = 0; f < DURATION; f += 2) {
    const caption = CAPTIONS.find((c) => f >= c.start && f < c.end);
    const boxes = [caption?.box, ctaShown(f) ? END_CTA : null, hookPromptShown(f) ? HOOK_PROMPT : null];
    for (const box of boxes) {
      if (!box) continue;
      for (let x = box.x; x <= box.x + box.width; x += 24) {
        for (let y = box.y; y <= box.y + box.height; y += 12) worst = Math.min(worst, ratio(text, sampleField(f, x, y)));
      }
    }
  }
  assert.ok(worst >= 7, `worst text contrast ${worst.toFixed(2)}`);
});

test('QA-4: the field stays within 1.5:1 of BRAND.bg and saturation 0.35, every 5th frame', () => {
  const bg = rgb(BRAND.bg);
  let maxRatio = 0;
  let maxSat = 0;
  for (let f = 0; f < DURATION; f += 5) {
    const m = markAt(f);
    for (let x = 20; x < WIDTH; x += 40) {
      for (let y = 20; y < HEIGHT; y += 40) {
        const s = sampleField(f, x, y);
        maxRatio = Math.max(maxRatio, ratio(s, bg));
        const underMark = m && Math.abs(x - m.x) <= m.size / 2 && Math.abs(y - m.y) <= m.size / 2;
        if (!underMark) maxSat = Math.max(maxSat, sat(s));
      }
    }
  }
  assert.ok(maxRatio <= 1.5, `field contrast ${maxRatio.toFixed(3)}`);
  assert.ok(maxSat <= 0.35, `field saturation ${maxSat.toFixed(3)}`);
});

test('QA-4: one accent hue at a time, and no teal while the mark or caret shows, at every frame', () => {
  const points = [[1500, 230], [380, 880], [960, 540], [200, 200], [1700, 900]];
  for (let f = 0; f < DURATION; f++) {
    const blobs = backgroundField(f).blobs;
    const visible = new Set(blobs.filter((b) => ACCENTS.includes(b.color) && b.opacity > 0.02).map((b) => b.color));
    assert.ok(visible.size <= 1, `frame ${f}: ${[...visible]}`);
    if (markAt(f) || hookPromptShown(f)) {
      for (const [x, y] of points) assert.ok(accentAt(f, x, y).agent <= 0.02, `frame ${f}: teal under the mark`);
    }
  }
});

test('QA-4: terminal text colors on the opaque TUI.bg window (AA 4.5:1 floor; 7:1 reported)', () => {
  const bg = rgb(TUI.bg);
  const surface = rgb(TUI.surface);
  const on = (c: string, b: number[]) => ratio(rgb(c), b);
  for (const c of ['fg', 'muted', 'accent', 'good', 'warn', 'agent'] as const) assert.ok(on(TUI[c], bg) >= 4.5, `${c} ${on(TUI[c], bg).toFixed(2)}`);
  // Popup rows on TUI.surface; unselected summaries are fg at 0.6 opacity (GallianiCli.tsx Popup).
  assert.ok(on(TUI.fg, surface) >= 7);
  assert.ok(ratio(blend(rgb(TUI.fg), surface, 0.6), surface) >= 4.5);
  // The title bar label is muted on surface.
  assert.ok(on(TUI.muted, surface) >= 4.5);
});

// ---------------------------------------------------------------- (5) privacy and claims

test('QA-5: no secret, real user, home path or banned word in anything on screen', () => {
  const strings: string[] = [];
  const walk = (v: unknown): void => {
    if (typeof v === 'string') strings.push(v);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  walk({BEATS, CAPTIONS, TERM, SLASH_ROWS, FILE_ROWS_ALL, FILE_ROWS_SIG, AT_PROMPT, AT_DONE});
  assert.ok(strings.length > 50);
  const banned = /stream|resume|--continue|thinking|chain-of-thought|reasoning|sk-|Bearer |API_KEY|api[_-]?key|token=|password|secret|C:\\Users\\|\/home\/|\/Users\/|jesus|soyagenteia|[\w.+-]+@[\w-]+\.[a-z]{2,}/i;
  for (const s of strings) assert.doesNotMatch(s, banned, s);
  for (const {name, source} of cliFiles()) assert.doesNotMatch(source, /jesus|soyagenteia|C:\\\\Users/i, name);
  // The only workspace on screen is the demo folder.
  for (const s of strings) for (const [path] of s.matchAll(/[A-Z]:\\[^\s>'"]*/g)) assert.match(path, /^C:\\dev\\signup-app/, path);
});

test('QA-5: the on-screen claims still have their R48 sources', () => {
  const readme = read('../../README.md');
  assert.ok(readme.includes('Galliani has no accounts and sends no telemetry.'), 'No telemetry. (README)');
  assert.ok(readme.includes('The only network calls are the model requests you make with your own key.'), 'Local. (README)');
  assert.ok(readme.includes('Galliani is free software') && readme.includes('GNU Affero General Public License'), 'Free. (README License)');
  assert.ok(read('../../site/src/privacy.tsx').includes('There is no telemetry, analytics, crash reporting or account'), 'No telemetry. (privacy page)');
  assert.ok(read('../../docs/routing.md').includes('pick the cheapest model that will answer it completely and correctly'), 'routing caption');
  assert.ok(TERM.bannerRouting.startsWith('routing: auto'));
});

// ---------------------------------------------------------------- (6) framing, re-derived

test('QA-6: the terminal stays in the title-safe area at every frame, computed from TERMINAL and the beat data', () => {
  const cli = read('../src/cli/GallianiCli.tsx');
  assert.match(cli, /transform: `scale\(\$\{zoom\}\)`, transformOrigin: `\$\{origin\.x\}px \$\{origin\.y\}px`/);
  for (let f = 0; f < DURATION; f++) {
    const beat = BEATS.find((b) => f >= b.start && f < b.start + b.duration) as CliBeat;
    if (beat.shot.kind !== 'shell' && beat.shot.kind !== 'terminal') continue;
    const local = f - beat.start;
    const dy = beat.entrance ? beat.entrance.slide * (1 - ramp(local, beat.entrance.at, beat.entrance.frames)) : 0;
    // Worst case: the push at its full zoom for the whole beat.
    const z = beat.push ? Math.max(beat.push.from, beat.push.to) : 1;
    const o = beat.push?.origin ?? {x: 0, y: 0};
    const x0 = o.x + (TERMINAL.x - o.x) * z;
    const y0 = o.y + (TERMINAL.y + dy - o.y) * z;
    const x1 = o.x + (TERMINAL.x + TERMINAL.width - o.x) * z;
    const y1 = o.y + (TERMINAL.y + dy + TERMINAL.height - o.y) * z;
    assert.ok(x0 >= SAFE.left && x1 <= SAFE.right && y0 >= SAFE.top && y1 <= SAFE.bottom, `frame ${f}: ${[x0, y0, x1, y1].map(Math.round)}`);
    const caption = CAPTIONS.find((c) => f >= c.start && f < c.end);
    if (caption) assert.ok(y0 >= caption.box.y + caption.box.height, `frame ${f}: the caption covers the terminal`);
  }
});

test('QA-6: the end card block is centered and its mark sits in the seam spot (R57, R65)', () => {
  const top = SEAM_MARK.y - END.markSize / 2;
  const bottom = top + END.markSize + END.gap + END.wordLine;
  assert.ok(Math.abs((top + bottom) / 2 - HEIGHT / 2) <= 4, `vertical center ${(top + bottom) / 2}`);
  assert.equal(SEAM_MARK.x, WIDTH / 2);
  assert.equal(END_CTA.y, top + END.markSize + END.gap);
  assert.ok(Math.abs(END_CTA.x + END_CTA.width / 2 - WIDTH / 2) <= 4);
  const cli = read('../src/cli/GallianiCli.tsx');
  assert.match(cli, /left: 0, width: WIDTH, top: END_CTA\.y,[^\n]*textAlign: 'center'/, 'the CTA line is drawn centered at END_CTA.y');
});
