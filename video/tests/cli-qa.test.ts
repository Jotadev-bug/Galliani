// Independent QA checks for GallianiCli (spec 015 Part B, V2c-QA, updated for V3a and Decision 0038). These re-derive the
// motion budget, holds, grid, seam, framing and contrast from the raw beat fields, the storyboard and the layout boxes
// instead of from the motion.ts helpers (MOTIONS, activeAt, longestHold, budgetViolations), so a bug shared by a helper
// and its own test in cli.test.ts still shows here. Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {join, relative} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {ACCENTS, FIELD_PERIODS, accentAt, backgroundField, sampleField} from '../src/cli/background.ts';
import {cursorAt, desktopShown, heroBoxes, heroIconAt, shellCommand, windowFocused} from '../src/cli/desktop.ts';
import {END_BLOCK, END_CTA, END_MARK, endCardShown, terminalRect, tuiShown} from '../src/cli/layout.ts';
import type {Rect} from '../src/cli/layout.ts';
import {costAt, ramp} from '../src/cli/motion.ts';
import {BRAND, TUI} from '../src/cli/palette.ts';
import {robotPose} from '../src/cli/pose.ts';
import type {RobotPose} from '../src/cli/pose.ts';
import {
  AT_DONE, AT_PROMPT, BEATS, BLINK_FRAMES, CAPTIONS, CARD_ENTER_FRAMES, CARD_ENTER_ROWS, CARET_BLINK_FRAMES, DESKTOP,
  DESKTOP_LABELS, DURATION, FILE_ROWS_ALL, FILE_ROWS_SIG, GRID, HEIGHT, HIGHLIGHT_FRAMES, POSES, ROBOT_BLINKS,
  ROBOT_BREATH, ROBOT_PLACE, SAFE, SLASH_ROWS, SPINNER_FPS, TERM, TERMINAL, VERB_SECONDS, WIDTH, charTimes, screenAt,
  typedText,
} from '../src/cli/timeline.ts';
import type {CliBeat, Pose, Typing} from '../src/cli/timeline.ts';

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

const beatOf = (frame: number) => BEATS.find((b) => frame >= b.start && frame < b.start + b.duration) as CliBeat;
const beatById = (id: string) => BEATS.find((b) => b.id === id) as CliBeat;

// ---------------------------------------------------------------- (1) determinism

test('QA-1: src/cli/** is deterministic and self-contained', () => {
  const files = cliFiles();
  assert.ok(files.length >= 9, 'all GallianiCli sources are scanned, the desktop, pose and robot modules included');
  for (const required of ['desktop.ts', 'pose.ts', 'robot.tsx', 'background.ts']) assert.ok(files.some((f) => f.name === required), required);
  for (const {name, source} of files) {
    assert.doesNotMatch(source, /Math\.random|\bDate\b|performance\.now|\bfetch\b|XMLHttpRequest|WebSocket|setTimeout|setInterval|requestAnimationFrame|delayRender/, `${name}: non-deterministic API`);
    assert.doesNotMatch(source, /https?:\/\/|@import|@font-face|\.woff|\.ttf|\.otf/, `${name}: external asset or font`);
    assert.doesNotMatch(source, /filter|blur|drop-shadow|mix-?blend|backdrop|box-?shadow|text-?shadow|<canvas/i, `${name}: filter, blur, blend or shadow`);
    // Only relative imports and the two runtime packages; nothing from the showcase (R74).
    for (const [, from] of source.matchAll(/^import[^'"]*['"]([^'"]+)['"]/gm)) {
      assert.ok(from.startsWith('./') || from === 'react' || from === 'remotion', `${name} imports ${from}`);
    }
    for (const [, file] of source.matchAll(/staticFile\(['"]([^'"]+)['"]\)/g)) {
      assert.ok(['galliani-mark-g.png', 'galliani-mark-star.png', 'galliani-mark.png'].includes(file), `${name} loads ${file}`);
    }
  }
  // The scan itself sees what it must reject.
  assert.match('const t = new Date();', /\bDate\b/);
  assert.match("style={{filter: 'drop-shadow(0 0 4px)'}}", /filter|drop-shadow/);
  assert.match("import {Robot} from '../Robot.tsx'", /^import[^'"]*['"](\.\.\/[^'"]+)['"]/m);
});

test('QA-1: backgroundField, sampleField, the desktop and the robot are pure functions of the frame', () => {
  const last = DURATION - 1;
  const order = [last, 0, 480, 1, 479, 240, 120, 600, 0, last, 100, 160, 250, 870, 100];
  const first = new Map<number, string>();
  for (const f of order) {
    const snap = JSON.stringify([backgroundField(f), sampleField(f, 333, 777), accentAt(f, 1500, 230), heroIconAt(f), cursorAt(f), robotPose(f), terminalRect(f)]);
    if (first.has(f)) assert.equal(snap, first.get(f), `frame ${f} differs on a second call`);
    else first.set(f, snap);
  }
  // Periodic: the field at f and f + DURATION match, for every frame.
  for (let f = 0; f < DURATION; f += 7) assert.deepEqual(backgroundField(f + DURATION), backgroundField(f));
  // Every period divides DURATION, so the seam is exact without the `% DURATION` fold.
  for (const p of FIELD_PERIODS) assert.equal(DURATION % p, 0, `period ${p}`);
});

// ---------------------------------------------------------------- (2) palette and copied strings

const CLI = read('../src/cli/GallianiCli.tsx');
const SECTIONS = CLI.split(/\n(?=const |export const )/);
const sectionOf = (name: string) => SECTIONS.find((s) => new RegExp(`^(?:export )?const ${name}\\b`).test(s));

test('QA-2: palette groups stay in their places: BRAND outside, TUI inside, ROBOT only in the robot (R27, R28, R75)', () => {
  // BRAND.accent (orange) is drawn only by the mark; the field reaches it through FIELD_COLORS in background.ts.
  const users = SECTIONS.filter((s) => s.includes('BRAND.accent')).map((s) => s.match(/^(?:export )?const (\w+)/)?.[1]);
  assert.deepEqual(users.sort(), ['Mark']);
  for (const {name, source} of cliFiles()) {
    if (name === 'GallianiCli.tsx' || name === 'palette.ts' || name === 'background.ts') continue;
    assert.doesNotMatch(source, /BRAND\.accent/, `${name} uses the orange`);
  }
  // Inside the terminal only TUI colors appear.
  const inside = ['TerminalFrame', 'ShellLine', 'EntryView', 'Banner', 'Transcript', 'PlanPanel', 'Popup', 'ApprovalCard', 'PromptBox', 'TuiScreen', 'Bordered', 'Cursor', 'ENTRY_COLORS', 'STEP_COLORS'];
  for (const name of inside) {
    const s = sectionOf(name);
    assert.ok(s, `${name} exists`);
    assert.doesNotMatch(s, /BRAND\.|ROBOT\./, `${name} uses a non-TUI color inside the terminal`);
  }
  // Outside the terminal (desktop, cursor, captions, end card) only BRAND colors appear.
  const outside = ['Mark', 'Caption', 'EndCard', 'Label', 'GenericIcon', 'HeroIcon', 'CursorArrow', 'DesktopIcons', 'BackgroundField'];
  for (const name of outside) {
    const s = sectionOf(name);
    assert.ok(s, `${name} exists`);
    assert.doesNotMatch(s, /TUI\.|ROBOT\./, `${name} uses a TUI or ROBOT color outside the terminal`);
  }
  // ROBOT is referenced only by robot.tsx, and robot.tsx references no other group.
  for (const {name, source} of cliFiles()) {
    if (name === 'palette.ts') continue;
    if (name === 'robot.tsx') {
      assert.match(source, /\bROBOT\./);
      assert.doesNotMatch(source, /\bBRAND\b|\bTUI\b/, 'robot.tsx uses another palette group');
    } else {
      assert.doesNotMatch(source, /\bROBOT\./, `${name} uses the ROBOT group`);
    }
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
  assert.ok(labels.size >= 4);
  for (const label of labels) assert.ok(WIDGETS.includes(`"${label}"`), `status label ${label}`);
  // Fixture: a drifted glyph is caught.
  assert.notEqual('[v]', steps.verified);
});

// ---------------------------------------------------------------- (3) motion budget, re-derived from raw beats

// R46, typed out again here: each beat's single emphasized motion and its robot gesture.
const STORYBOARD: readonly [string, Emphasis | null, Pose | null][] = [
  ['desk-idle', null, null], ['desk-hover', 'cursor', null], ['desk-drag', 'drag', null], ['desk-drop', 'absorb', null],
  ['launch-type', null, null], ['launch-expand', 'expand', null], ['goal-type', 'gesture', 'lean'],
  ['plan-steps', 'gesture', 'point'], ['plan-check', null, null], ['route-first', 'count', null],
  ['route-next', 'gesture', 'glance'], ['slash-popup', 'gesture', 'nod'], ['at-file', null, null],
  ['approval-card', 'card', null], ['approval-wait', 'gesture', 'raise'], ['approval-answer', 'gesture', 'lower'],
  ['verified-done', 'gesture', 'cheer'], ['end-card', 'gesture', 'wave'], ['end-seam', null, null],
];

type Emphasis = (typeof EMPHASIS_FIELDS)[number];
const EMPHASIS_FIELDS = ['cursor', 'drag', 'absorb', 'expand', 'count', 'card', 'gesture'] as const;
// R50: the cursor and the dragged icon are one element; a gesture is the robot.
const ELEMENT_OF: Record<Emphasis, string> = {cursor: 'cursor', drag: 'cursor', absorb: 'icon', expand: 'window', count: 'cost', card: 'card', gesture: 'robot'};
const LIMITS: Record<Emphasis, [number, number]> = {cursor: [20, 30], drag: [30, 45], absorb: [6, 10], expand: [10, 15], count: [1, 15], card: [1, 15], gesture: [1, 30]};

/** A beat's emphasized motions as [kind, local start, frames], from the raw fields only. */
function emphasesOf(b: CliBeat): [Emphasis, number, number][] {
  const out: [Emphasis, number, number][] = [];
  for (const k of EMPHASIS_FIELDS) {
    const m = b[k];
    if (!m) continue;
    let frames: number;
    if (k === 'card') frames = CARD_ENTER_FRAMES;
    else if (k === 'gesture') frames = (POSES[b.gesture!.pose].legs as readonly number[]).reduce((s, f) => s + f, 0);
    else frames = (m as {frames: number}).frames;
    out.push([k, m.at, frames]);
  }
  return out;
}

// R76: the robot shows from the launch-expand content cut to the end of end-card.
const EXPAND_BEAT = beatById('launch-expand');
const ROBOT_FROM = EXPAND_BEAT.start + EXPAND_BEAT.expand!.at + EXPAND_BEAT.expand!.frames;
const END_BEAT = beatById('end-card');
const ROBOT_TO = END_BEAT.start + END_BEAT.duration;

function typingOf(beat: CliBeat, local: number): Typing | null {
  if (beat.shot.kind === 'shell') return beat.shot.typing;
  if (beat.shot.kind !== 'terminal') return null;
  return screenAt(beat.shot.keys, local).key.screen.prompt?.typing ?? null;
}

/** Elements animating at an absolute frame, from the beat fields, caption data and typing schedules only. */
function animating(frame: number): string[] {
  const beat = beatOf(frame);
  const local = frame - beat.start;
  const out = new Set<string>();
  for (const c of CAPTIONS) if (frame >= c.start && frame < c.start + c.enterFrames) out.add('caption');
  for (const [k, at, frames] of emphasesOf(beat)) if (local >= at && local < at + frames) out.add(ELEMENT_OF[k]);
  if (frame >= ROBOT_FROM && frame < ROBOT_TO) out.add('robot');
  const typing = typingOf(beat, local);
  if (typing && typing.frames > 0) {
    const times = charTimes(typing);
    if (local >= Math.floor(times[0]) && local <= Math.ceil(times[times.length - 1])) out.add('typing');
  }
  return [...out];
}

const r2 = (v: number) => Math.round(v * 100) / 100 + 0; // + 0 folds -0 into 0
const rect = (b: Rect | null) => b && [r2(b.x), r2(b.y), r2(b.width), r2(b.height)];

/** Everything a viewer can see change in the foreground, except the field, spinner, caret and robot idle (R51). */
function foreground(frame: number): string {
  const beat = beatOf(frame);
  const local = frame - beat.start;
  const caption = CAPTIONS.find((c) => frame >= c.start && frame < c.end);
  const parts: unknown[] = [beat.id, caption?.text, caption ? r2(ramp(frame - caption.start, 0, caption.enterFrames)) : null];
  const hero = heroIconAt(frame);
  parts.push(hero && [r2(hero.center.x), r2(hero.center.y), r2(hero.scale), r2(hero.rotation), r2(hero.opacity), hero.hovered, hero.label]);
  const cursor = cursorAt(frame);
  parts.push(cursor && [r2(cursor.x), r2(cursor.y)]);
  parts.push(rect(terminalRect(frame)), windowFocused(frame), desktopShown(frame), tuiShown(frame), endCardShown(frame), shellCommand(frame));
  const pose = robotPose(frame);
  // Breathing and blinks are the robot's idle; everything else in its pose is foreground motion.
  parts.push(pose && [rect(pose.box), r2(pose.headTilt), r2(pose.lean), r2(pose.eyeX), r2(pose.eyeY), r2(pose.armLeft), r2(pose.armRight)]);
  const typing = typingOf(beat, local);
  if (typing) parts.push(typedText(typing, local));
  if (beat.shot.kind === 'terminal') {
    const {key, since} = screenAt(beat.shot.keys, local);
    parts.push(beat.shot.keys.indexOf(key), costAt(beat, local, key.screen).toFixed(4));
    parts.push(key.screen.fresh !== undefined && since < HIGHLIGHT_FRAMES);
    if (beat.card) parts.push(r2(ramp(local, beat.card.at, CARD_ENTER_FRAMES)));
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

test('QA-3: one emphasized motion per beat as in R46, in its bounds, at most three animating elements per frame (R49, R50)', () => {
  assert.deepEqual(BEATS.map((b) => b.id), STORYBOARD.map(([id]) => id));
  for (const [id, kind, pose] of STORYBOARD) {
    const b = beatById(id);
    const emphasized = emphasesOf(b);
    assert.ok(emphasized.length <= 1, `${id}: ${emphasized.map(([k]) => k).join(', ')}`);
    assert.equal(emphasized[0]?.[0] ?? null, kind, `${id}: emphasized motion`);
    assert.equal(b.gesture?.pose ?? null, pose, `${id}: robot gesture`);
    for (const [k, at, frames] of emphasized) {
      const [lo, hi] = LIMITS[k];
      assert.ok(frames >= lo && frames <= hi, `${id}: ${k} lasts ${frames}`);
      assert.ok(at >= 0 && at + frames <= b.duration, `${id}: ${k} crosses the cut`);
    }
  }
  let peak = 0;
  for (let f = 0; f < DURATION; f++) {
    const a = animating(f);
    peak = Math.max(peak, a.length);
    assert.ok(a.length <= 3, `frame ${f}: ${a.join(', ')}`);
  }
  assert.ok(peak >= 2, 'the robot and a gesture or typing overlap somewhere, so the count is exercised');
  // Fixture: a count added to a gesture beat makes two emphasized motions.
  const doubled = {...beatById('route-next'), count: {at: 30, frames: 15, from: 0.0107, to: 0.0108}};
  assert.equal(emphasesOf(doubled).length, 2);
});

test('QA-3: every beat holds still for 8+ frames, the video ends on an 8+ frame hold (R51, R57)', () => {
  for (const b of BEATS) assert.ok(longestStill(b) >= 8, `${b.id}: longest still run ${longestStill(b)}`);
  const tail = Array.from({length: 8}, (_, i) => foreground(DURATION - 8 + i));
  assert.equal(new Set(tail).size, 1, 'the last 8 frames change');
  // Fixture: a shell beat that types a character every frame or so has no hold.
  const index = BEATS.findIndex((b) => b.id === 'launch-type');
  const saved = BEATS[index];
  const busy: CliBeat = {...saved, shot: {kind: 'shell', typing: {text: 'x'.repeat(40), from: 0, frames: saved.duration - 1}}};
  (BEATS as CliBeat[])[index] = busy;
  try {
    assert.ok(longestStill(busy) < 8);
  } finally {
    (BEATS as CliBeat[])[index] = saved;
  }
});

test('QA-3: grid, pace, beat length, act spans, caption length, no dead start (R23, R53-R55)', () => {
  assert.ok(DURATION >= 840 && DURATION <= 1020 && DURATION % 30 === 0, `${DURATION}`);
  let cursor = 0;
  for (const b of BEATS) {
    assert.equal(b.start, cursor);
    assert.equal(b.start % GRID, 0, `${b.id} start`);
    assert.ok(b.duration >= 30 && b.duration <= 105, `${b.id} ${b.duration}`);
    for (const [k, at] of emphasesOf(b)) assert.equal((b.start + at) % GRID, 0, `${b.id} ${k} start`);
    cursor += b.duration;
  }
  assert.equal(cursor, DURATION);
  const span = (pred: (b: CliBeat) => boolean) => BEATS.filter(pred).reduce((s, b) => s + b.duration, 0);
  const hook = span((b) => b.segment === 'Hook');
  const launch = span((b) => b.segment === 'Launch');
  const close = span((b) => b.id === 'end-card' || b.id === 'end-seam');
  assert.ok(hook >= 150 && hook <= 180, `Hook ${hook}`);
  assert.ok(launch >= 60 && launch <= 105, `Launch ${launch}`);
  assert.ok(close >= 75 && close <= 120, `end card and seam ${close}`);
  for (const c of CAPTIONS) {
    assert.equal(c.start % GRID, 0, `${c.text} start`);
    assert.ok(c.end - c.start >= 60 && c.end - c.start <= 180, `${c.text}`);
    assert.ok(c.enterFrames <= 6, `${c.text} enters in ${c.enterFrames}`);
  }
  // Frame 0: the hero icon, the three icons and the window, and a hook caption that is already whole.
  assert.ok(heroIconAt(0)?.home && desktopShown(0) && terminalRect(0));
  const hookCaption = CAPTIONS[0];
  assert.ok(hookCaption.start === 0 && ramp(0, 0, hookCaption.enterFrames) === 1, 'the hook caption cuts in on frame 0');
});

test('QA-3: no banned motion kinds, easings or CSS scales in the components', () => {
  assert.doesNotMatch(CLI, /\binterpolate\(|\bspring\(|Easing\./, 'GallianiCli.tsx animates outside motion.ts');
  // Every transform is the caption rise, the card rise or the whole-row transcript scroll; no scale anywhere (R73).
  const transforms = [...CLI.matchAll(/transform: (?:\w+ \? )?('[^']*'|`[^`]*`|[^,}]+)/g)].map(([, t]) => t);
  assert.ok(transforms.length >= 3);
  for (const t of transforms) {
    assert.match(t, /^`translateY\(\$\{(rise|\(1 - rise\) \* CAPTION_ENTER\.slide|-offset)\}px\)`$/, t);
  }
  for (const {name, source} of cliFiles()) {
    assert.doesNotMatch(source, /\bscale\(/, `${name}: a CSS or SVG scale`);
    // Code only: copy such as the route id `gemini-3.1-flash-lite` is not a motion.
    const code = source.replace(/'[^'\n]*'/g, "''").replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');
    assert.doesNotMatch(code, /pulse|punch|bump|flash|glow|stagger|shake|wobble|wiggle|Easing\.(linear|back|elastic|bounce|bezier|in\()/i, name);
  }
  // The robot moves only by rotations and the eye translate that pose.ts computes.
  const robot = read('../src/cli/robot.tsx');
  for (const [, t] of robot.matchAll(/transform[=:]\s*\{?(`[^`]*`|[^,}]+)/g)) assert.match(t, /rotate\(|translate\(\$\{pose\.eyeX\}/, t);
  assert.doesNotMatch(robot, /Math\.sin|Math\.cos/, 'the robot runs no free motion of its own');
  const motion = read('../src/cli/motion.ts');
  assert.equal([...motion.matchAll(/\binterpolate\(/g)].length, 1, 'one interpolate, inside ramp()');
  assert.match(motion, /easing: EASINGS\[easing\]/);
  const easings = motion.match(/export const EASINGS = \{([\s\S]*?)\} as const/);
  assert.ok(easings, 'EASINGS table');
  const entries = [...easings[1].matchAll(/(\w+): (Easing\.[^,\n]+),/g)].map(([, k, v]) => `${k}=${v}`);
  assert.deepEqual(entries, ['outExpo=Easing.out(Easing.exp)', 'outQuart=Easing.out(Easing.poly(4))', 'inOutCubic=Easing.inOut(Easing.poly(3))']);
  const inOut = cliFiles().flatMap(({source}) => [...source.matchAll(/Easing\.inOut/g)]);
  assert.equal(inOut.length, 1, 'Easing.inOut only in EASINGS');
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
const within = (b: Rect, x: number, y: number) => x >= b.x && x <= b.x + b.width && y >= b.y && y <= b.y + b.height;

/** The mark's boxes on screen at a frame: the hero tile and the end-card mark. */
const markBoxes = (f: number): Rect[] => {
  const hero = heroIconAt(f);
  return [...(hero ? [heroBoxes(hero).tile] : []), ...(endCardShown(f) ? [END_MARK] : [])];
};

function worstOver(f: number, box: Rect, color: string, step = 12): number {
  let worst = Infinity;
  const c = rgb(color);
  for (let x = box.x; x <= box.x + box.width; x += step * 2) {
    for (let y = box.y; y <= box.y + box.height; y += step) worst = Math.min(worst, ratio(c, sampleField(f, x, y)));
  }
  return worst;
}

test('QA-4: captions, the call to action and the hero label keep 7:1, the generic labels 4.5:1, at every other frame', () => {
  let text = Infinity;
  let muted = Infinity;
  for (let f = 0; f < DURATION; f += 2) {
    const caption = CAPTIONS.find((c) => f >= c.start && f < c.end);
    const hero = heroIconAt(f);
    const label = hero ? heroBoxes(hero).label : null;
    for (const box of [caption?.box, endCardShown(f) ? END_CTA : null, label]) if (box) text = Math.min(text, worstOver(f, box, BRAND.text));
    if (desktopShown(f)) for (const icon of DESKTOP.icons) muted = Math.min(muted, worstOver(f, icon.labelBox, BRAND.muted, 8));
  }
  assert.ok(text >= 7, `worst text contrast ${text.toFixed(2)}`);
  assert.ok(muted >= 4.5, `worst generic label contrast ${muted.toFixed(2)}`);
});

test('QA-4: the field stays within 1.5:1 of BRAND.bg and saturation 0.35, every 5th frame', () => {
  const bg = rgb(BRAND.bg);
  let maxRatio = 0;
  let maxSat = 0;
  for (let f = 0; f < DURATION; f += 5) {
    const marks = markBoxes(f);
    for (let x = 20; x < WIDTH; x += 40) {
      for (let y = 20; y < HEIGHT; y += 40) {
        const s = sampleField(f, x, y);
        maxRatio = Math.max(maxRatio, ratio(s, bg));
        if (!marks.some((m) => within(m, x, y))) maxSat = Math.max(maxSat, sat(s));
      }
    }
  }
  assert.ok(maxRatio <= 1.5, `field contrast ${maxRatio.toFixed(3)}`);
  assert.ok(maxSat <= 0.35, `field saturation ${maxSat.toFixed(3)}`);
});

test('QA-4: one accent hue at a time, and no teal while the mark shows (hero icon or end card), at every frame', () => {
  const points: [number, number][] = [];
  for (let x = 80; x < WIDTH; x += 160) for (let y = 60; y < HEIGHT; y += 160) points.push([x, y]);
  let markFrames = 0;
  for (let f = 0; f < DURATION; f++) {
    const blobs = backgroundField(f).blobs;
    const visible = new Set(blobs.filter((b) => ACCENTS.includes(b.color) && b.opacity > 0.02).map((b) => b.color));
    assert.ok(visible.size <= 1, `frame ${f}: ${[...visible]}`);
    if (markBoxes(f).length > 0) {
      markFrames++;
      for (const [x, y] of points) assert.ok(accentAt(f, x, y).agent <= 0.02, `frame ${f}: teal at ${x},${y} while the mark shows`);
    }
  }
  assert.ok(markFrames >= 180 + 75, 'the mark shows through the desktop act and the end card');
});

test('QA-4: terminal text colors on the opaque TUI.bg window (AA 4.5:1 floor)', () => {
  const bg = rgb(TUI.bg);
  const surface = rgb(TUI.surface);
  const on = (c: string, b: number[]) => ratio(rgb(c), b);
  for (const c of ['fg', 'muted', 'accent', 'good', 'warn', 'agent'] as const) assert.ok(on(TUI[c], bg) >= 4.5, `${c} ${on(TUI[c], bg).toFixed(2)}`);
  // Popup rows on TUI.surface; unselected summaries are fg at 0.6 opacity (GallianiCli.tsx Popup).
  assert.ok(on(TUI.fg, surface) >= 7);
  assert.match(sectionOf('Popup') ?? '', /opacity: line\.current \? 1 : 0\.6/);
  assert.ok(ratio(blend(rgb(TUI.fg), surface, 0.6), surface) >= 4.5);
  // The title bar label is muted on surface.
  assert.ok(on(TUI.muted, surface) >= 4.5);
  // The hero label highlight (BRAND.raised) keeps BRAND.text readable.
  assert.ok(on(BRAND.text, rgb(BRAND.raised)) >= 7);
});

// ---------------------------------------------------------------- (5) privacy and claims

test('QA-5: no secret, real user, home path, brand or banned word in anything on screen', () => {
  const strings: string[] = [];
  const walk = (v: unknown): void => {
    if (typeof v === 'string') strings.push(v);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  // Beat ids and gesture targets are names, not copy: walk what the shots draw.
  walk({SHOTS: BEATS.map((b) => b.shot), CAPTIONS, TERM, SLASH_ROWS, FILE_ROWS_ALL, FILE_ROWS_SIG, AT_PROMPT, AT_DONE, DESKTOP, DESKTOP_LABELS});
  assert.ok(strings.length > 50);
  const banned = /stream|resume|--continue|thinking|chain-of-thought|reasoning|sk-|Bearer |API_KEY|api[_-]?key|token=|password|secret|C:\\Users\\|\/home\/|\/Users\/|jesus|soyagenteia|[\w.+-]+@[\w-]+\.[a-z]{2,}/i;
  for (const s of strings) assert.doesNotMatch(s, banned, s);
  for (const {name, source} of cliFiles()) assert.doesNotMatch(source, /jesus|soyagenteia|C:\\\\Users/i, name);
  // The only workspace on screen is the demo folder.
  for (const s of strings) for (const [path] of s.matchAll(/[A-Z]:\\[^\s>'"]*/g)) assert.match(path, /^C:\\dev\\signup-app/, path);
  // The desktop labels are the generic list (R67), with no OS, app or vendor name.
  assert.deepEqual([...DESKTOP_LABELS].sort(), ['Files', 'Galliani', 'Notes', 'Projects']);
  assert.deepEqual([DESKTOP.hero.label, ...DESKTOP.icons.map((i) => i.label)].sort(), [...DESKTOP_LABELS].sort());
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

// ---------------------------------------------------------------- (6) framing, the robot and the seam, re-derived

const ACT3: Rect = {x: TERMINAL.x, y: TERMINAL.y, width: TERMINAL.width, height: TERMINAL.height};
const insideSafe = (b: Rect) => b.x >= SAFE.left && b.x + b.width <= SAFE.right && b.y >= SAFE.top && b.y + b.height <= SAFE.bottom;
const overlaps = (a: Rect, b: Rect) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
const grow = (b: Rect, by: number): Rect => ({x: b.x - by, y: b.y - by, width: b.width + 2 * by, height: b.height + 2 * by});
/** The robot's box as drawn, moved by its breath. */
const robotBox = (pose: RobotPose): Rect => ({...pose.box, y: pose.box.y + pose.breath});

test('QA-6: the window is the desktop rectangle, an interpolated expand, the Act 3 frame, or gone, inside the safe area', () => {
  assert.ok(insideSafe(DESKTOP.window) && insideSafe(ACT3));
  assert.ok(DESKTOP.window.width < ACT3.width && DESKTOP.window.height < ACT3.height);
  assert.match(sectionOf('TerminalFrame') ?? '', /left: rect\.x, top: rect\.y, width: rect\.width, height: rect\.height/, 'the window is sized from its rectangle');
  for (let f = 0; f < DURATION; f++) {
    const beat = beatOf(f);
    const local = f - beat.start;
    const r = terminalRect(f);
    if (beat.shot.kind === 'end') {
      assert.equal(r, null, `frame ${f}`);
      continue;
    }
    assert.ok(r, `frame ${f}: no window`);
    if (beat.shot.kind !== 'terminal') {
      assert.deepEqual(r, DESKTOP.window, `frame ${f}: the desktop window moved`);
    } else if (beat.expand && local < beat.expand.at + beat.expand.frames) {
      // A convex mix of the two rectangles, the same t on every edge: interpolated, never overshooting.
      const t = (r.width - DESKTOP.window.width) / (ACT3.width - DESKTOP.window.width);
      assert.ok(t >= 0 && t <= 1, `frame ${f}: expand t ${t}`);
      const at = (a: number, b: number) => a + (b - a) * t;
      assert.ok(Math.abs(r.x - at(DESKTOP.window.x, ACT3.x)) < 1e-6 && Math.abs(r.y - at(DESKTOP.window.y, ACT3.y)) < 1e-6 && Math.abs(r.height - at(DESKTOP.window.height, ACT3.height)) < 1e-6, `frame ${f}: the edges disagree`);
    } else {
      assert.deepEqual(r, ACT3, `frame ${f}: the Act 3 frame moved`);
    }
    assert.ok(insideSafe(r), `frame ${f}: ${rect(r)}`);
  }
});

test('QA-6: captions never cover the desktop, the drag, the window, the robot or the end card (R42, R76)', () => {
  for (let f = 0; f < DURATION; f++) {
    const caption = CAPTIONS.find((c) => f >= c.start && f < c.end);
    assert.ok(caption, `frame ${f}: no caption`);
    const box = caption.box;
    assert.ok(insideSafe(box), `${caption.text} leaves the safe area`);
    const r = terminalRect(f);
    if (r) assert.ok(!overlaps(box, r), `frame ${f}: the caption covers the window`);
    if (desktopShown(f)) for (const icon of DESKTOP.icons) assert.ok(!overlaps(box, icon.tile) && !overlaps(box, icon.labelBox), `frame ${f}: the caption covers ${icon.label}`);
    const hero = heroIconAt(f);
    if (hero) assert.ok(!overlaps(box, heroBoxes(hero).all), `frame ${f}: the caption covers the hero icon`);
    const cursor = cursorAt(f);
    if (cursor) assert.ok(!within(box, cursor.x, cursor.y), `frame ${f}: the cursor runs under the caption`);
    const pose = robotPose(f);
    if (pose) assert.ok(!overlaps(box, robotBox(pose)), `frame ${f}: the caption covers the robot`);
    if (endCardShown(f)) assert.ok(!overlaps(box, END_BLOCK), `frame ${f}: the caption covers the end card`);
  }
});

test('QA-6: the robot shows from the content cut to the end card, beside the terminal, still between cuts (R76, R77)', () => {
  const starts = new Set(BEATS.map((b) => b.start));
  for (let f = 0; f < DURATION; f++) {
    const pose = robotPose(f);
    assert.equal(pose !== null, f >= ROBOT_FROM && f < ROBOT_TO, `frame ${f}: robot shown`);
    if (!pose) continue;
    const box = robotBox(pose);
    assert.ok(insideSafe(box), `frame ${f}: the robot leaves the safe area`);
    assert.ok(Math.abs(pose.breath) <= 3, `frame ${f}: breath ${pose.breath}`);
    const r = terminalRect(f);
    if (r) assert.ok(!overlaps(grow(box, 16), r), `frame ${f}: the robot is within 16 px of the terminal`);
    if (endCardShown(f)) assert.ok(!overlaps(box, END_BLOCK), `frame ${f}: the robot is in the end-card block`);
    const before = robotPose(f - 1);
    if (before && !starts.has(f)) assert.deepEqual(pose.box, before.box, `frame ${f}: the robot travels inside a beat`);
  }
  assert.deepEqual(robotPose(ROBOT_FROM)?.box, ROBOT_PLACE.act3);
  assert.deepEqual(robotPose(END_BEAT.start)?.box, ROBOT_PLACE.end);
  // Blinks: 90+ frames apart, while the robot shows, never during a gesture.
  const gestures = BEATS.flatMap((b) => emphasesOf(b).filter(([k]) => k === 'gesture').map(([, at, frames]) => [b.start + at, b.start + at + frames] as const));
  assert.equal(gestures.length, 8);
  for (let i = 0; i < ROBOT_BLINKS.length; i++) {
    const blink = ROBOT_BLINKS[i];
    if (i > 0) assert.ok(blink - ROBOT_BLINKS[i - 1] >= 90, `blink ${blink}`);
    assert.ok(blink >= ROBOT_FROM && blink + BLINK_FRAMES <= ROBOT_TO, `blink ${blink} off screen`);
    for (const [from, to] of gestures) assert.ok(blink + BLINK_FRAMES <= from || blink >= to, `blink ${blink} inside a gesture`);
  }
  assert.ok(ROBOT_BREATH.period >= 60 && ROBOT_BREATH.period <= 120);
  // Idle: outside gestures and the raised-arm hold, the pose is the rest pose.
  const raise = beatById('approval-wait');
  const lower = beatById('approval-answer');
  const held = [raise.start + raise.gesture!.at, lower.start + lower.gesture!.at];
  const rest = robotPose(ROBOT_FROM) as RobotPose;
  const parts = (p: RobotPose) => [p.headTilt, p.lean, p.eyeX, p.eyeY, p.armLeft, p.armRight].map(r2);
  for (let f = ROBOT_FROM; f < ROBOT_TO; f++) {
    if (gestures.some(([from, to]) => f >= from && f < to) || (f >= held[0] && f < held[1])) continue;
    assert.deepEqual(parts(robotPose(f) as RobotPose), parts(rest), `frame ${f}: the robot moves while idle`);
  }
});

/** The R57 seam state at a frame, as data: icons, hero, window, shell line, caret phase and what is absent. */
function seam(f: number) {
  const hero = heroIconAt(f);
  return {
    icons: desktopShown(f),
    hero: hero && {x: r2(hero.center.x), y: r2(hero.center.y), scale: hero.scale, opacity: hero.opacity, hovered: hero.hovered, home: hero.home},
    window: rect(terminalRect(f)),
    focused: windowFocused(f),
    command: shellCommand(f),
    caret: Math.floor(f / CARET_BLINK_FRAMES) % 2,
    cursor: cursorAt(f) !== null,
    robot: robotPose(f) !== null,
    tui: tuiShown(f),
    cta: endCardShown(f),
  };
}

test('QA-6: the last frame is the seam state of frame 0, and the end card is centered (R57, R65)', () => {
  const first = seam(0);
  assert.deepEqual(seam(DURATION - 1), {...first, caret: Math.floor((DURATION - 1) / CARET_BLINK_FRAMES) % 2});
  assert.equal(Math.floor(DURATION / CARET_BLINK_FRAMES) % 2, first.caret, 'the caret phase is continuous across the loop');
  assert.ok(first.icons && first.hero?.home && !first.hero.hovered && first.hero.scale === 1 && first.hero.opacity === 1);
  assert.ok(!first.focused && first.command === '' && !first.cursor && !first.robot && !first.tui && !first.cta);
  assert.deepEqual(backgroundField(DURATION), backgroundField(0));
  // Fixture: a hero icon left in the window breaks the seam.
  const leftInWindow = {...first, hero: {...first.hero!, x: DESKTOP.dragEnd.x, y: DESKTOP.dragEnd.y, home: false}};
  assert.notDeepEqual(leftInWindow, first);
  // The end card block is centered on the frame.
  assert.ok(Math.abs(END_BLOCK.x + END_BLOCK.width / 2 - WIDTH / 2) <= 4);
  assert.ok(Math.abs(END_BLOCK.y + END_BLOCK.height / 2 - HEIGHT / 2) <= 4, `vertical center ${END_BLOCK.y + END_BLOCK.height / 2}`);
  assert.equal(END_MARK.y, END_BLOCK.y);
  assert.ok(Math.abs(END_CTA.x + END_CTA.width / 2 - WIDTH / 2) <= 4);
  assert.match(CLI, /left: 0, width: WIDTH, top: END_CTA\.y,[^\n]*textAlign: 'center'/, 'the CTA line is drawn centered at END_CTA.y');
});
