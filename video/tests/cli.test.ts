// Checks for the GallianiCli composition (spec 015 Part B, B-AC2..B-AC11, B-AC15..B-AC27). Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {join, relative} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {
  ACCENTS, BLOBS, FIELD_COLORS, FIELD_PERIODS, WAVES, accentAt, backgroundField, phaseAt, sampleField,
} from '../src/cli/background.ts';
import {DRAG_CHORD, cursorAt, desktopShown, dragPath, heroBoxes, heroHome, heroIconAt, shellCommand, windowFocused} from '../src/cli/desktop.ts';
import type {Point} from '../src/cli/desktop.ts';
import {
  BANNER_ROWS, CONTENT, END_BLOCK, END_CTA, END_MARK, WINDOW, bottomRows, endCardShown, entryRows, sceneState,
  terminalRect, transcriptLayout, transcriptOffset, tuiShown, visibleRows, wrap,
} from '../src/cli/layout.ts';
import type {Rect, SceneState} from '../src/cli/layout.ts';
import {
  EASINGS, EMPHASIZED, GESTURES, MAX_ANIMATING, MIN_HOLD, MOTIONS, activeAt, budgetViolations, changeFrames, costAt,
  deriveMotions, longestHold, movingAt, robotShownAt,
} from '../src/cli/motion.ts';
import type {CliMotion, MotionKind} from '../src/cli/motion.ts';
import {BRAND, ROBOT, TUI} from '../src/cli/palette.ts';
import {aimAngle, blinkAt, breathAt, robotPose, shoulderAt} from '../src/cli/pose.ts';
import type {RobotPose} from '../src/cli/pose.ts';
import {
  AT_DONE, AT_PROMPT, BEATS, BLINK_FRAMES, CAPTIONS, CAPTION_ENTER, CARD_ENTER_FRAMES, CARET_BLINK_FRAMES, CLI_RENDER,
  DESKTOP, DESKTOP_LABELS, DURATION, END, FILE_ROWS_ALL, FILE_ROWS_SIG, FPS, GOAL, GRID, HEIGHT, PLAN_STEPS, POSES,
  PRESS_Y, ROBOT_BLINKS, ROBOT_BREATH, ROBOT_FRAME, ROBOT_HEIGHT, ROBOT_PLACE, ROBOT_SHAPES, ROUTE_CODING, ROUTE_TEXT,
  SAFE, SHELL_CARET, SLASH_ROWS, TARGETS, TERM, TERMINAL, WIDTH, beatAt, captionAt, charTimes, planSummary, popupLines,
  screenAt, statusText, stepLine, typedCount, typedText, workingText,
} from '../src/cli/timeline.ts';
import type {CliBeat} from '../src/cli/timeline.ts';

const read = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8');
const STYLES = read('../../galliani/tui/styles.py');
const CLI_DIR = fileURLToPath(new URL('../src/cli', import.meta.url));
/** Every file under src/cli/, recursively (spec 015 Tests: the scans cover `src/cli/**`). */
const cliSources = () =>
  readdirSync(CLI_DIR, {recursive: true, withFileTypes: true})
    .filter((e) => e.isFile())
    .map((e) => ({name: relative(CLI_DIR, join(e.parentPath, e.name)), source: readFileSync(join(e.parentPath, e.name), 'utf8')}));

// R26: hex, rgb(), rgba(), hsl(), hsla(), and the keywords white and black.
const COLOR_LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\bwhite\b|\bblack\b/;

function pythonDict(source: string, name: string): Record<string, string> {
  const body = source.match(new RegExp(`^${name} = \\{([\\s\\S]*?)\\n\\}`, 'm'));
  assert.ok(body, `${name} not found in styles.py`);
  return Object.fromEntries([...body[1].matchAll(/"([a-z]+)":\s*"(#[0-9a-fA-F]{6})"/g)].map((m) => [m[1], m[2]]));
}
/** The GREY object of Robot.tsx, as a key-value map. */
function robotGrey(source: string): Record<string, string> {
  const body = source.match(/const GREY = \{([\s\S]*?)\};/);
  assert.ok(body, 'GREY not found in Robot.tsx');
  return Object.fromEntries([...body[1].matchAll(/(\w+):\s*'(#[0-9a-fA-F]{6})'/g)].map((m) => [m[1], m[2]]));
}
const ROBOT_TSX = read('../src/Robot.tsx');

test('B-AC5: TUI palette equals DARK_PALETTE in styles.py', () => {
  const dark = pythonDict(STYLES, 'DARK_PALETTE');
  assert.equal(Object.keys(dark).length, 10);
  assert.deepEqual(TUI, dark);
  assert.notDeepEqual({...TUI, good: '#5ec49b'}, dark, 'fixture: one changed value fails');
});

test('B-AC5: BRAND equals R25 and the showcase colors', () => {
  assert.deepEqual(BRAND, {
    bg: '#0A0A0B', surface: '#141416', raised: '#1C1C1F', text: '#EDEDEF', muted: '#8B8B92', accent: '#D97757',
  });
  const showcase = read('../src/Showcase.tsx');
  for (const key of ['bg', 'surface', 'raised', 'text', 'muted'] as const) {
    assert.match(showcase, new RegExp(`${key}: '${BRAND[key]}'`), `Showcase C.${key}`);
  }
  assert.match(read('../src/Mascot.tsx'), new RegExp(`const ORANGE = '${BRAND.accent}'`));
});

test('B-AC5: ROBOT equals GREY in Robot.tsx', () => {
  const grey = robotGrey(ROBOT_TSX);
  assert.equal(Object.keys(grey).length, 5);
  assert.deepEqual(ROBOT, grey);
  assert.deepEqual(ROBOT, {shell: '#D7D7DC', shellShade: '#A7A7AE', face: '#0E0E10', eye: '#F4F4F6', dark: '#5A5A61'});
  assert.notDeepEqual(robotGrey(ROBOT_TSX.replace("shell: '#D7D7DC'", "shell: '#D7D7DD'")), ROBOT, 'fixture: one changed value fails');
});

test('B-AC6: no color literal outside palette.ts; palette.ts holds only R25 and R75 values; ROBOT only in robot.tsx', () => {
  for (const {name, source} of cliSources()) {
    if (name === 'palette.ts') continue;
    assert.doesNotMatch(source, COLOR_LITERAL, `${name} has a color literal`);
  }
  const allowed = new Set<string>([...Object.values(BRAND), ...Object.values(TUI), ...Object.values(ROBOT)]);
  assert.equal(allowed.size, 21);
  const palette = readFileSync(join(CLI_DIR, 'palette.ts'), 'utf8');
  for (const [hex] of palette.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) assert.ok(allowed.has(hex), `${hex} is not an R25 or R75 value`);
  assert.doesNotMatch(palette, /\brgba?\(|\bhsla?\(|\bwhite\b|\bblack\b/);
  for (const {name, source} of cliSources()) {
    if (name === 'palette.ts') continue;
    if (name === 'robot.tsx') {
      assert.match(source, /\bROBOT\./);
      assert.doesNotMatch(source, /\b(BRAND|TUI|FIELD_COLORS)\b/, 'robot.tsx uses another palette group');
    } else {
      assert.doesNotMatch(source, /\bROBOT\b/, `${name} uses the ROBOT group`);
    }
  }
});

// ---------------------------------------------------------------- timeline

const WIDGETS = read('../../galliani/tui/widgets.py');
const COMMANDS_PY = read('../../galliani/tui/commands.py');
// R46: beat id, emphasized motion (null for "-"), robot (null off screen, 'idle', or the gesture pose).
const STORYBOARD: readonly [string, MotionKind | null, string | null][] = [
  ['desk-idle', null, null], ['desk-hover', 'cursor', null], ['desk-drag', 'drag', null], ['desk-drop', 'absorb', null],
  ['launch-type', null, null], ['launch-expand', 'expand', 'idle'], ['goal-type', 'gesture', 'lean'],
  ['plan-steps', 'gesture', 'point'], ['plan-check', null, 'idle'], ['route-first', 'count', 'idle'],
  ['route-next', 'gesture', 'glance'], ['slash-popup', 'gesture', 'nod'], ['at-file', null, 'idle'],
  ['approval-card', 'card', 'idle'], ['approval-wait', 'gesture', 'raise'], ['approval-answer', 'gesture', 'lower'],
  ['verified-done', 'gesture', 'cheer'], ['end-card', 'gesture', 'wave'], ['end-seam', null, null],
];
const BEAT_IDS = STORYBOARD.map(([id]) => id);
const CAPTION_TEXTS = [
  'Galliani now runs in your terminal.', 'One command.', 'Type a goal. Watch the plan.',
  'The cheapest capable model, every step.', 'Slash commands. @ files.', 'You approve what matters.',
  'Local. No telemetry. Free.',
];
const terminalKeys = () =>
  BEATS.flatMap((b) => (b.shot.kind === 'terminal' ? b.shot.keys.map((key) => ({beat: b, key})) : []));
const pyTuple = (source: string, name: string) => {
  const m = source.match(new RegExp(`^${name} = \\(([^)]*)\\)`, 'm'));
  assert.ok(m, `${name} not found`);
  return [...m[1].matchAll(/"([^"]*)"/g)].map((x) => x[1]);
};
const beatById = (id: string) => BEATS.find((b) => b.id === id) as CliBeat;
const spanOf = (ids: string[]) => ids.reduce((s, id) => s + beatById(id).duration, 0);

test('B-AC2: 28-34 s, a multiple of 30, and the beats add up to the composition', () => {
  const seconds = DURATION / FPS;
  assert.ok(seconds >= 28 && seconds <= 34, `${seconds}s`);
  assert.equal(DURATION % 30, 0);
  assert.equal(BEATS.reduce((sum, b) => sum + b.duration, 0), DURATION);
  const {compositionId, fps, width, height, durationInFrames, previewScale, finalScale, stillScale} = CLI_RENDER;
  assert.deepEqual({compositionId, fps, width, height, durationInFrames, previewScale, finalScale, stillScale},
    {compositionId: 'GallianiCli', fps: 30, width: 1920, height: 1080, durationInFrames: DURATION, previewScale: 1, finalScale: 2, stillScale: 2});
  assert.match(read('../src/Root.tsx'), /id=\{CLI_RENDER\.compositionId\}[\s\S]*durationInFrames=\{CLI_RENDER\.durationInFrames\}/);
});

test('B-AC3: beat order, contiguity, length and act spans', () => {
  assert.deepEqual(BEATS.map((b) => b.id), BEAT_IDS);
  BEATS.forEach((b, i) => {
    assert.equal(b.start, i === 0 ? 0 : BEATS[i - 1].start + BEATS[i - 1].duration, `${b.id} start`);
    assert.ok(b.duration >= 30 && b.duration <= 105, `${b.id} lasts ${b.duration}`);
  });
  const last = BEATS[BEATS.length - 1];
  assert.equal(last.start + last.duration, DURATION);
  const hook = spanOf(BEATS.filter((b) => b.segment === 'Hook').map((b) => b.id));
  const launch = spanOf(BEATS.filter((b) => b.segment === 'Launch').map((b) => b.id));
  const close = spanOf(['end-card', 'end-seam']);
  assert.ok(hook >= 150 && hook <= 180, `Hook ${hook}`);
  assert.ok(launch >= 60 && launch <= 105, `Launch ${launch}`);
  assert.ok(close >= 75 && close <= 120, `end card and seam ${close}`);
});

test('B-AC4: seven exact captions, each over its whole segment, no gaps or overlaps', () => {
  assert.deepEqual(CAPTIONS.map((c) => c.text), CAPTION_TEXTS);
  let cursor = 0;
  for (const c of CAPTIONS) {
    const beats = BEATS.filter((b) => b.segment === c.segment);
    assert.equal(c.start, beats[0].start, `${c.text} start`);
    assert.equal(c.end, beats[beats.length - 1].start + beats[beats.length - 1].duration, `${c.text} end`);
    assert.equal(c.start, cursor, `gap or overlap before ${c.text}`);
    assert.ok(c.end - c.start >= 60 && c.end - c.start <= 180, `${c.text} on screen ${c.end - c.start} frames (R43, R54)`);
    cursor = c.end;
  }
  assert.equal(cursor, DURATION);
});

test('B-AC7: terminal strings are copied verbatim from widgets.py and commands.py', () => {
  for (const s of [...TERM.tips, TERM.approvalTitle, ...TERM.approvalLabels, ...TERM.approvalKeys, TERM.planTitle,
    TERM.noPlan, TERM.popupCurrent.trim(), TERM.popupMore.trim()]) {
    assert.ok(WIDGETS.includes(s), `"${s}" is not in widgets.py`);
  }
  assert.ok(WIDGETS.includes(`IDLE_PLACEHOLDER = "${TERM.idlePlaceholder}"`));
  assert.ok(WIDGETS.includes(`ACTIVE_PLACEHOLDER = "${TERM.activePlaceholder}"`));
  assert.equal(TERM.approvalKeys.join(''), '[y] approve   [n] deny   [a] approve and accept edits   [Esc] deny');
  assert.ok(WIDGETS.includes(`POPUP_ROWS = ${TERM.popupRows}`));
  assert.deepEqual(pyTuple(WIDGETS, 'SPINNER_FRAMES'), [...TERM.spinnerFrames]);
  assert.ok(WIDGETS.includes(`SPINNER_STATIC = "${TERM.spinnerStatic}"`));
  for (const [kind, glyph] of Object.entries(TERM.leaders)) assert.ok(WIDGETS.includes(`"${kind}": "${glyph}"`), `LEADERS ${kind}`);
  for (const [state, glyph] of Object.entries(TERM.stepGlyphs)) {
    assert.ok(WIDGETS.includes(`"${state}": "${glyph}"`), `STEP_GLYPHS ${state}`);
  }
  for (const [group, verbs] of Object.entries(TERM.verbs)) {
    const tuple = `(${verbs.map((v) => `"${v}"`).join(', ')}${verbs.length === 1 ? ',' : ''})`;
    assert.ok(WIDGETS.includes(`"${group}": ${tuple}`), `VERBS ${group}`);
  }
  assert.ok(WIDGETS.includes('f"Galliani {info.version}"'));
  const version = TERM.bannerTitle.split(' ')[1];
  assert.ok(read('../../pyproject.toml').includes(`version = "${version}"`), 'banner version');
  assert.ok(TERM.bannerRouting.startsWith('routing: auto · '));
  // Popup rows: COMMANDS labels and summaries, in order.
  const commands = [...COMMANDS_PY.matchAll(/CommandSpec\("([a-z-]+)", "[^"]*", "([^"]*)"/g)]
    .map((m) => ({label: `/${m[1]}`, summary: m[2]}));
  assert.deepEqual(SLASH_ROWS, commands);
  // Route ids are real registry model ids.
  const models = read('../../config/models.yaml');
  for (const id of [ROUTE_CODING, ROUTE_TEXT]) assert.match(models, new RegExp(`- id: ${id.replace(/[./]/g, '\\$&')}\\r?\\n`), id);
  // Plan step lines follow step_line's format with a STEP_GLYPHS glyph or, while running, a spinner frame.
  const glyphs = new Set<string>([...Object.values(TERM.stepGlyphs), ...TERM.spinnerFrames]);
  for (const {key} of terminalKeys()) {
    key.screen.steps?.forEach((state, i) => {
      for (const spinner of [undefined, ...TERM.spinnerFrames]) {
        const line = stepLine(i + 1, state, spinner);
        const m = line.match(/^(\S+) *(\d)\. (.+) \((pending|running|waiting|verified)\)$/);
        assert.ok(m && glyphs.has(m[1]) && line.indexOf(` ${i + 1}. `) === 4, line);
        assert.equal(m[3], PLAN_STEPS[i]);
      }
    });
  }
  assert.deepEqual(PLAN_STEPS, ['Read signup.py', 'Write the validation', 'Save signup.py and tests', 'Run the tests']);
  assert.equal(GOAL, 'Add email validation to signup.py and cover it with tests');
  assert.equal(stepLine(1, 'pending'), '...  1. Read signup.py (pending)');
  assert.equal(stepLine(3, 'waiting'), '[?]  3. Save signup.py and tests (waiting)');
  assert.equal(planSummary(['verified', 'running', 'pending', 'pending']), 'Plan v1 - step 2/4 - running');
  assert.equal(planSummary(['verified', 'verified', 'verified', 'verified']), 'Plan v1 - step 4/4 - done');
  assert.equal(workingText({group: 'waiting', elapsed: 8, cost: 0.0107, step: 3}, '·'),
    '● Waiting for you… · 8s · $0.0107 / $0.50 · step 3/4');
  assert.equal(statusText({route: ROUTE_CODING, cost: 0.0107, label: 'Working'}),
    'signup-app · route anthropic/claude-sonnet-5.5 · $0.0107 / $0.50 · ask · memory on · Working');
  assert.equal(popupLines(SLASH_ROWS, 0)[0].text, '› /help       list commands and keys');
  assert.equal(popupLines(SLASH_ROWS, 0).length, TERM.popupRows + 1, 'eight rows and the more marker');
});

test('R35: cost only rises during the task', () => {
  let last = 0;
  for (const {beat, key} of terminalKeys()) {
    if (key.screen.working === null && key.screen.status.cost === 0) continue; // an idle prompt between tasks
    assert.ok(key.screen.status.cost >= last, `cost drops in ${beat.id}`);
    if (key.screen.working) assert.equal(key.screen.working.cost, key.screen.status.cost, `${beat.id} lines agree`);
    last = key.screen.status.cost;
  }
});

test('B-AC8: shipped behavior only, nothing private', () => {
  const data = JSON.stringify({BEATS, CAPTIONS, TERM, SLASH_ROWS, FILE_ROWS_ALL, FILE_ROWS_SIG, AT_PROMPT, AT_DONE, DESKTOP, DESKTOP_LABELS});
  for (const text of [data, ...cliSources().map((s) => s.source)]) {
    assert.doesNotMatch(text, /stream|resume|--continue|thinking|chain-of-thought|reasoning/i);
    assert.doesNotMatch(text, /sk-|Bearer |API_KEY/); // a key prefix starts a token (`desk-idle` is a beat id)
    assert.ok(!text.includes('C:\\Users\\') && !text.includes('C:\\\\Users\\\\'), 'a Windows home path');
    assert.doesNotMatch(text, /\/home\/|\/Users\//);
    assert.doesNotMatch(text, /[\w.+-]+@[\w-]+\.[a-z]{2,}/i);
  }
});

test('B-AC9: deterministic source, only the mark assets, dependencies unchanged', () => {
  assert.ok(cliSources().some((s) => s.name === 'robot.tsx') && cliSources().some((s) => s.name === 'desktop.ts'));
  for (const {name, source} of cliSources()) {
    assert.doesNotMatch(source, /Math\.random|Date\.now|new Date|performance\.now|fetch\(|setTimeout|setInterval/, name);
  }
  const publicDir = fileURLToPath(new URL('../public', import.meta.url));
  assert.deepEqual(readdirSync(publicDir).sort(), ['galliani-mark-g.png', 'galliani-mark-star.png', 'galliani-mark.png']);
  const pkg = JSON.parse(read('../package.json'));
  assert.deepEqual(pkg.dependencies, {'@remotion/cli': '4.0.533', react: '19.2.0', 'react-dom': '19.2.0', remotion: '4.0.533'});
  assert.deepEqual(pkg.devDependencies, {'@types/node': '26.6.4', '@types/react': '19.2.2', typescript: '5.9.3'});
});

const overlaps = (a: Rect, b: Rect) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
const robotBoxAt = (pose: RobotPose): Rect => ({...pose.box, y: pose.box.y + pose.breath});

test('B-AC10: captions sit in the title-safe area on one line, clear of the desktop, window and robot', () => {
  for (const c of CAPTIONS) {
    const {x, y, width, height, fontSize} = c.box;
    assert.ok(x >= 96 && x + width <= WIDTH - 96 && y >= 54 && y + height <= HEIGHT - 54, `${c.text} leaves the safe area`);
    assert.ok(fontSize >= 56, `${c.text} font ${fontSize}`);
    assert.ok(c.text.length * fontSize * 0.6 <= width, `${c.text} does not fit on one line`);
    assert.ok(fontSize * 1.2 <= height, `${c.text} box too short`);
  }
  for (let f = 0; f < DURATION; f++) {
    const c = captionAt(f);
    assert.ok(c, `frame ${f} has no caption`);
    const boxes: [string, Rect | null][] = [['terminal', terminalRect(f)]];
    if (desktopShown(f)) for (const i of DESKTOP.icons) boxes.push([i.label, i.tile], [`${i.label} label`, i.labelBox]);
    const hero = heroIconAt(f);
    if (hero) boxes.push(['hero', heroBoxes(hero).all]);
    const robot = robotPose(f);
    if (robot) boxes.push(['robot', robotBoxAt(robot)]);
    if (endCardShown(f)) boxes.push(['end block', END_BLOCK]);
    for (const [name, box] of boxes) if (box) assert.ok(!overlaps(c.box, box), `frame ${f}: the caption covers the ${name}`);
  }
  // The whole drag arc stays clear of the caption band too.
  for (let t = 0; t <= 1; t += 0.02) {
    const all = heroBoxes({center: dragPath(t), scale: 1, rotation: 0, opacity: 1, hovered: true, home: false, label: true}).all;
    for (const c of CAPTIONS) assert.ok(!overlaps(c.box, all), `the drag arc at t=${t} runs into a caption`);
  }
  assert.ok(overlaps({x: 0, y: 0, width: 10, height: 10}, {x: 5, y: 5, width: 10, height: 10}), 'fixture: overlap is seen');
});

// ---------------------------------------------------------------- motion (R37-R39, R49-R57)

const BANNED_MOTION = /TransitionSeries|@remotion\/transitions|crossfade|dissolve|spring|Easing\.(linear|back|elastic|bounce|bezier)/i;

test('B-AC11: motion bounds, hard cuts and easing', () => {
  const bounds: Record<MotionKind, (m: CliMotion) => boolean> = {
    caption: (m) => m.frames <= 6 && (m.slide ?? 0) <= 32,
    cursor: (m) => m.frames >= 20 && m.frames <= 30,
    drag: (m) => m.frames >= 30 && m.frames <= 45,
    absorb: (m) => m.frames >= 6 && m.frames <= 10,
    expand: (m) => m.frames >= 10 && m.frames <= 15,
    count: (m) => m.frames <= 15,
    card: (m) => m.frames === CARD_ENTER_FRAMES,
    gesture: (m) => m.frames <= 30,
  };
  assert.ok(MOTIONS.length > 0);
  for (const m of MOTIONS) {
    assert.ok(m.kind in bounds && bounds[m.kind](m), `${m.beat} ${m.kind} is out of bounds`);
    assert.ok(m.easing in EASINGS, `${m.beat} ${m.kind} easing ${m.easing}`);
    assert.equal(m.easing === 'inOutCubic', m.kind === 'cursor' || m.kind === 'drag', `${m.beat} ${m.kind}: inOutCubic is for cursor and drag only`);
    if (m.kind === 'absorb' || m.kind === 'expand') assert.equal(m.easing, 'outExpo', `${m.kind} uses outExpo`);
    if (m.kind === 'gesture') assert.ok(m.easing === 'outExpo' || m.easing === 'outQuart');
    const b = beatById(m.beat);
    assert.ok(m.start >= b.start && m.start + m.frames <= b.start + b.duration, `${m.beat} ${m.kind} crosses a cut`);
  }
  for (const b of BEATS) {
    assert.ok(!('transition' in b), `${b.id} has a transition`);
    if (b.shot.kind === 'terminal') {
      const keys = b.shot.keys;
      keys.forEach((k, i) => {
        assert.ok(Number.isInteger(k.at) && k.at >= 0 && k.at < b.duration, `${b.id} key ${i}`);
        if (i > 0) assert.ok(k.at > keys[i - 1].at, `${b.id} keys out of order`);
      });
    }
  }
  assert.ok(CAPTION_ENTER.frames <= 6 && CAPTION_ENTER.slide <= 32 && CAPTION_ENTER.fade <= 4);
  const motion = readFileSync(join(CLI_DIR, 'motion.ts'), 'utf8');
  const table = motion.slice(motion.indexOf('export const EASINGS'), motion.indexOf('} as const;', motion.indexOf('export const EASINGS')));
  assert.deepEqual([...table.matchAll(/(\w+): (Easing\.[^\n]+),/g)].map((m) => [m[1], m[2]]),
    [['outExpo', 'Easing.out(Easing.exp)'], ['outQuart', 'Easing.out(Easing.poly(4))'], ['inOutCubic', 'Easing.inOut(Easing.poly(3))']]);
  for (const {source, name} of cliSources()) {
    assert.doesNotMatch(source, BANNED_MOTION, `${name} uses a banned motion`);
    for (const m of source.matchAll(/\binterpolate\(/g)) {
      assert.match(source.slice(m.index, m.index + 240), /easing: EASINGS\[/, `${name}: interpolate without an EASINGS easing`);
    }
    const outside = name === 'motion.ts' ? source.replace(table, '') : source;
    assert.doesNotMatch(outside, /Easing\.(out|inOut|in)\(/, `${name}: an easing outside the EASINGS table`);
  }
  // No push, punch-in, pulse or per-word stagger field anywhere in the scene data (field names, not copy).
  const fields = new Set<string>();
  const walk = (v: unknown): void => {
    if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) (fields.add(k), walk(x));
  };
  walk({BEATS, CAPTIONS, MOTIONS, CAPTION_ENTER, DESKTOP, POSES});
  const BANNED_FIELD = /^push$|entrance|^move$|zoom|punch|pulse|stagger|bump|flash|glow|shake|wobble|word|sway|wiggle/i;
  assert.deepEqual([...fields].filter((k) => BANNED_FIELD.test(k)), []);
  assert.ok(BANNED_FIELD.test('push') && BANNED_FIELD.test('wordStagger'), 'fixture: a push or per-word stagger field is rejected');
  assert.match('Easing.out(Easing.back(2))', BANNED_MOTION, 'fixture: the scan sees an overshooting easing');
});

const emphasizedOf = (b: CliBeat, motions: readonly CliMotion[] = MOTIONS) =>
  motions.filter((m) => m.beat === b.id && EMPHASIZED.includes(m.kind)).map((m) => m.kind);

test('B-AC15: one emphasized motion per beat as in R46, at most three animating, a hold in every beat', () => {
  assert.deepEqual(budgetViolations(), []);
  for (const [id, kind] of STORYBOARD) assert.deepEqual(emphasizedOf(beatById(id)), kind ? [kind] : [], `${id} motion`);
  for (const b of BEATS) assert.ok(longestHold(b) >= MIN_HOLD, `${b.id} hold`);
  assert.equal(MAX_ANIMATING, 3);
  let peak = 0;
  for (let f = 0; f < DURATION; f++) {
    const active = activeAt(f);
    assert.ok(active.length <= 3, `frame ${f}: ${active}`);
    assert.equal(active.includes('robot'), robotPose(f) !== null, `frame ${f}: the robot counts while on screen`);
    peak = Math.max(peak, active.length);
  }
  assert.equal(peak, 3, 'the budget is used, not exceeded');
  // Failure paths: two emphasized motions in a beat, a gesture beside a count, four animating, a beat with no hold.
  const twice = BEATS.map((b) => (b.id === 'desk-drag' ? {...b, absorb: {at: 45, frames: 8}} : b));
  assert.ok(budgetViolations(twice, deriveMotions(twice, CAPTIONS)).some((v) => v.startsWith('desk-drag: 2 emphasized')));
  const counted = BEATS.map((b) => (b.id === 'route-first' ? {...b, gesture: {at: 0, pose: 'nod' as const, target: 'route' as const}} : b));
  assert.ok(budgetViolations(counted, deriveMotions(counted, CAPTIONS)).some((v) => v.startsWith('route-first: 2 emphasized')));
  const crowded = [...MOTIONS, {kind: 'caption' as const, beat: 'goal-type', target: 'extra', start: 272, frames: 6, easing: 'outQuart' as const}];
  assert.ok(budgetViolations(BEATS, crowded).some((v) => v.includes('animate at once')));
  const busy = BEATS.map((b) => (b.id === 'route-next' && b.shot.kind === 'terminal'
    ? {...b, shot: {kind: 'terminal' as const, keys: Array.from({length: 15}, (_, i) => ({at: i * 4, screen: b.shot.kind === 'terminal' ? b.shot.keys[0].screen : (undefined as never)}))}}
    : b));
  assert.ok(budgetViolations(busy, deriveMotions(busy, CAPTIONS)).some((v) => v.startsWith('route-next: longest hold')));
});

const offGrid = (beats: readonly CliBeat[], motions: readonly CliMotion[]) => [
  ...beats.flatMap((b) => (b.start % GRID ? [b.id] : [])),
  ...motions.flatMap((m) => (m.start % GRID ? [`${m.beat} ${m.kind}`] : [])),
];

test('B-AC16: the 15-frame grid, the pace and a start with no dead frames', () => {
  assert.equal(GRID, 15);
  assert.deepEqual(offGrid(BEATS, MOTIONS), []);
  assert.ok(DURATION >= 840 && DURATION <= 1020, `${DURATION} frames`);
  for (const c of CAPTIONS) assert.ok(c.end - c.start >= 60 && c.end - c.start <= 180, `${c.text} lasts ${c.end - c.start}`);
  const hook = CAPTIONS[0];
  assert.equal(hook.start, 0);
  assert.equal(hook.enterFrames, 0, 'the hook caption cuts in at frame 0');
  const first = sceneState(0);
  assert.equal(first.icons?.length, 3, 'the three generic icons show at frame 0');
  assert.ok(first.hero?.home, 'the hero icon shows at frame 0');
  assert.ok(first.window, 'the terminal window shows at frame 0');
  // Failure path: a motion off the grid.
  assert.deepEqual(offGrid(BEATS, [{kind: 'gesture', beat: 'goal-type', target: 'robot', start: 287, frames: 20, easing: 'outQuart'}]), ['goal-type gesture']);
});

const intervalsOk = (times: readonly number[]) => {
  const gaps = times.slice(1).map((t, i) => t - times[i]);
  if (gaps.some((g, i) => i > 0 && g > gaps[i - 1] + 1e-9)) return false;
  const third = Math.max(1, Math.floor(gaps.length / 3));
  const mean = (xs: number[]) => xs.reduce((s, x) => s + x, 0) / xs.length;
  return mean(gaps.slice(0, third)) >= 1.5 * mean(gaps.slice(-third));
};
const typings = () => BEATS.flatMap((b) => {
  if (b.shot.kind === 'shell') return [{beat: b, typing: b.shot.typing}];
  if (b.shot.kind !== 'terminal') return [];
  return b.shot.keys.flatMap((k) => (k.screen.prompt ? [{beat: b, typing: k.screen.prompt.typing}] : []));
});

test('B-AC17: typing speeds up and finishes in its beat; cost only rises at a fixed width', () => {
  const typed = typings().filter(({typing}) => typing.frames > 0);
  assert.ok(typed.length >= 3, 'the shell line, the goal and the @ prompt are typed');
  for (const {beat, typing} of typings()) {
    let last = 0;
    for (let local = -2; local <= beat.duration; local++) {
      const n = typedCount(typing, local);
      assert.ok(n >= last, `${beat.id}: typedCount falls at ${local}`);
      last = n;
    }
    assert.ok(typing.from + typing.frames <= beat.duration - 1, `${beat.id} typing runs past the beat`);
    assert.equal(typedText(typing, beat.duration - 1), typing.text, `${beat.id} typing is cut off`);
  }
  for (const {beat, typing} of typed) assert.ok(intervalsOk(charTimes(typing).slice(typing.kept ?? 0)), `${beat.id} typing does not speed up`);
  assert.equal(intervalsOk([0, 1, 3, 6]), false, 'fixture: growing intervals are rejected');
  assert.equal(intervalsOk([0, 3, 6, 9, 12]), false, 'fixture: an even pace is rejected');
  // Cost (R35, R56): the shown value never falls during a task and keeps its width.
  let shown = 0;
  for (let f = 0; f < DURATION; f++) {
    const b = beatAt(f);
    if (b.shot.kind !== 'terminal') continue;
    const screen = screenAt(b.shot.keys, f - b.start).key.screen;
    if (screen.working === null && screen.status.cost === 0) continue; // an idle prompt between tasks
    const cost = costAt(b, f - b.start, screen);
    assert.ok(cost >= shown - 1e-12, `cost falls at frame ${f}`);
    assert.equal(statusText({...screen.status, cost}).length, statusText(screen.status).length, `cost width changes at ${f}`);
    shown = cost;
  }
  const counts = BEATS.filter((b) => b.count);
  assert.deepEqual(counts.map((b) => b.id), ['route-first'], 'one count, in route-first (R56)');
  for (const b of counts) {
    if (!b.count || b.shot.kind !== 'terminal') continue;
    assert.equal(b.count.to, screenAt(b.shot.keys, b.count.at).key.screen.status.cost, `${b.id} counts to the screen's cost`);
    assert.equal(b.count.from, screenAt(b.shot.keys, b.count.at - 1).key.screen.status.cost, `${b.id} counts from the cost before`);
  }
});

const fieldClose = (a: ReturnType<typeof backgroundField>, b: ReturnType<typeof backgroundField>) =>
  a.blobs.every((x, i) => {
    const y = b.blobs[i];
    return x.color === y.color && Math.abs(x.cx - y.cx) <= 0.5 && Math.abs(x.cy - y.cy) <= 0.5 && Math.abs(x.r - y.r) <= 0.5 && Math.abs(x.opacity - y.opacity) <= 0.01;
  }) && a.waves.every((x, i) => {
    const y = b.waves[i];
    const px = (Math.abs(x.phase - y.phase) * x.wavelength) / (2 * Math.PI);
    return x.color === y.color && px <= 0.5 && Math.abs(x.y - y.y) <= 0.5 && Math.abs(x.amplitude - y.amplitude) <= 0.5 && Math.abs(x.opacity - y.opacity) <= 0.01;
  });
/** B-AC18's comparison: boxes within 0.5 px, opacity and scale within 0.01, flags and strings equal. */
function sceneClose(a: SceneState, b: SceneState): boolean {
  const near = (x: unknown, y: unknown): boolean => {
    if (typeof x === 'number' && typeof y === 'number') return Math.abs(x - y) <= 0.01 || Math.abs(x - y) <= 0.5 && Math.abs(x) > 1;
    if (x && y && typeof x === 'object' && typeof y === 'object') {
      const keys = new Set([...Object.keys(x), ...Object.keys(y)]);
      return [...keys].every((k) => near((x as Record<string, unknown>)[k], (y as Record<string, unknown>)[k]));
    }
    return x === y;
  };
  return near(a, b);
}

test('B-AC18: the last frame matches frame 0 and the video ends on a hold', () => {
  const last = DURATION - 1;
  assert.ok(fieldClose(backgroundField(0), backgroundField(last)), 'the field jumps at the seam');
  assert.deepEqual(backgroundField(DURATION), backgroundField(0));
  const [a, b] = [sceneState(0), sceneState(last)];
  assert.ok(sceneClose(a, b), `the seam state differs:\n${JSON.stringify(a)}\n${JSON.stringify(b)}`);
  for (const s of [a, b]) {
    assert.ok(s.hero && s.hero.home && !s.hero.hovered && s.hero.scale === 1 && s.hero.opacity === 1, 'the hero icon is home, at rest');
    assert.ok(s.window && !s.window.focused && s.window.command === '', 'the window is unfocused with an empty shell line');
    assert.deepEqual([s.cursor, s.robot, s.tui, s.cta], [false, false, false, false]);
  }
  assert.equal(DURATION % (2 * CARET_BLINK_FRAMES), 0, 'the caret blink is continuous across the seam');
  const end = BEATS[BEATS.length - 1];
  assert.equal(end.id, 'end-seam');
  const changes = changeFrames(end);
  for (let local = end.duration - 8; local < end.duration; local++) {
    assert.ok(!changes.has(local) && activeAt(end.start + local).length === 0, `frame ${end.start + local} changes`);
    assert.ok(sceneClose(sceneState(end.start + local), a), `frame ${end.start + local} leaves the seam state`);
  }
  assert.equal(fieldClose(backgroundField(0), backgroundField(90)), false, 'fixture: a moved field is rejected');
  const stuck = {...b, hero: b.hero && {...b.hero, center: DESKTOP.dragEnd, home: false}};
  assert.equal(sceneClose(a, stuck), false, 'fixture: the hero icon left in the window is rejected');
});

const ALLOWED_FIELD = ['bg', 'surface', 'raised', 'border', 'muted', 'accent', 'agent'];
const BANNED_EFFECT = /filter|blur\(|feGaussianBlur|drop-shadow|mix-?blend|<canvas|box-?shadow|text-?shadow|backdrop/i;

test('B-AC19: the field is deterministic, periodic and built from palette keys', () => {
  for (let f = 0; f <= DURATION; f++) assert.deepEqual(backgroundField(f), backgroundField(f), `frame ${f}`);
  assert.deepEqual(backgroundField(DURATION), backgroundField(0));
  const {blobs, waves} = backgroundField(0);
  assert.ok(blobs.length >= 2 && blobs.length <= 3 && waves.length >= 2 && waves.length <= 3);
  for (const p of FIELD_PERIODS) assert.ok(p >= 240 && p <= 360 && DURATION % p === 0, `period ${p}`);
  assert.deepEqual([...new Set(FIELD_PERIODS)].sort(), [240, 320], 'the 960-frame periods (R60)');
  for (const p of new Set(FIELD_PERIODS)) {
    const step = phaseAt(p, 1) - phaseAt(p, 0);
    for (let f = 1; f < DURATION; f++) assert.ok(Math.abs(phaseAt(p, f + 1) - phaseAt(p, f) - step) < 1e-9 || f + 1 === DURATION, `phase step ${p}`);
  }
  assert.equal(new Set(waves.map((w) => w.parallax)).size, waves.length, 'wave parallax factors are distinct');
  assert.deepEqual(Object.keys(FIELD_COLORS), ALLOWED_FIELD);
  assert.deepEqual(FIELD_COLORS, {bg: BRAND.bg, surface: BRAND.surface, raised: BRAND.raised, border: TUI.border, muted: TUI.muted, accent: BRAND.accent, agent: TUI.agent});
  for (const layer of [...BLOBS, ...WAVES]) assert.ok(ALLOWED_FIELD.includes(layer.color), layer.color);
  // Each gradient has one stop color, so at most one accent key.
  assert.deepEqual([...ACCENTS], ['accent', 'agent']);
  // The field never reads the beats.
  const bg = readFileSync(join(CLI_DIR, 'background.ts'), 'utf8');
  assert.doesNotMatch(bg, /BEATS|beatAt|CAPTIONS|captionAt|MOTIONS/);
  for (const {name, source} of cliSources()) assert.doesNotMatch(source, BANNED_EFFECT, `${name} uses a filter, blend, canvas or shadow`);
  assert.match('style={{filter: "drop-shadow(0 10px 18px)"}}', BANNED_EFFECT, 'fixture: the scan sees a drop-shadow');
});

// WCAG relative luminance and contrast; HSL saturation.
const luminance = ([r, g, b]: readonly number[]) => {
  const lin = (v: number) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};
const contrast = (a: readonly number[], b: readonly number[]) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const saturation = (rgb: readonly number[]) => {
  const [max, min] = [Math.max(...rgb) / 255, Math.min(...rgb) / 255];
  const l = (max + min) / 2;
  return max === min ? 0 : (max - min) / (l > 0.5 ? 2 - max - min : max + min);
};
const hexRgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const inside = (r: Rect | null | undefined, x: number, y: number) => !!r && x >= r.x && x <= r.x + r.width && y >= r.y && y <= r.y + r.height;
const GRID_POINTS = Array.from({length: 48 * 27}, (_, i) => ({x: ((i % 48) + 0.5) * 40, y: (Math.floor(i / 48) + 0.5) * 40}));
/** The mark's box at a frame: the hero tile or the end card mark. */
const markBox = (f: number): Rect | null => {
  const hero = heroIconAt(f);
  if (hero) return heroBoxes(hero).tile;
  return endCardShown(f) ? END_MARK : null;
};
const boxPoints = (b: Rect) => {
  const out: {x: number; y: number}[] = [];
  for (let x = b.x; x <= b.x + b.width; x += 12) for (let y = b.y; y <= b.y + b.height; y += 8) out.push({x, y});
  return out;
};
const SAMPLE_FRAMES = [...new Set([
  0, DURATION - 1, ...CAPTIONS.map((c) => Math.floor((c.start + c.end) / 2)), ...BEATS.map((b) => b.start + Math.floor(b.duration / 2)),
  ...Array.from({length: DURATION / 15}, (_, i) => i * 15 + 7),
])];

test('B-AC20: the field stays quiet: contrast, saturation, one accent, readable text', () => {
  const bg = hexRgb(BRAND.bg);
  const text = hexRgb(BRAND.text);
  const muted = hexRgb(BRAND.muted);
  assert.ok(SAMPLE_FRAMES.length >= 8);
  for (const b of BEATS.filter((b) => b.shot.kind === 'desk')) assert.ok(SAMPLE_FRAMES.includes(b.start + Math.floor(b.duration / 2)), `${b.id} middle`);
  for (const f of SAMPLE_FRAMES) {
    const {blobs, waves} = backgroundField(f);
    for (const b of blobs) assert.ok(b.opacity <= 0.18, `blob opacity ${b.opacity}`);
    for (const w of waves) assert.ok(w.opacity <= 0.1, `wave opacity ${w.opacity}`);
    const visible = blobs.flatMap((b) => (ACCENTS.includes(b.color) && b.opacity > 0.02 ? [b.color] : []));
    assert.ok(new Set(visible).size <= 1, `frame ${f}: two accent hues`);
    if (markBox(f)) assert.ok(blobs.every((b) => b.color !== 'agent' || b.opacity <= 0.02), `frame ${f}: teal with the mark`);
    const term = terminalRect(f);
    const caption = captionAt(f);
    const hero = heroIconAt(f);
    const strong = [caption?.box, endCardShown(f) ? END_CTA : null, hero ? heroBoxes(hero).label : null];
    const weak = desktopShown(f) ? DESKTOP.icons.map((i) => i.labelBox) : [];
    let outside = 0;
    let tinted = 0;
    for (const {x, y} of GRID_POINTS) {
      const rgb = sampleField(f, x, y);
      assert.ok(contrast(rgb, bg) <= 1.5, `frame ${f} (${x}, ${y}): contrast ${contrast(rgb, bg).toFixed(2)}`);
      if (!inside(markBox(f), x, y)) assert.ok(saturation(rgb) <= 0.35, `frame ${f} (${x}, ${y}): saturation ${saturation(rgb).toFixed(2)}`);
      if (!inside(term, x, y)) {
        outside++;
        const a = accentAt(f, x, y);
        if (a.accent + a.agent > 0.05) tinted++;
      }
    }
    for (const box of strong) if (box) for (const {x, y} of boxPoints(box)) assert.ok(contrast(text, sampleField(f, x, y)) >= 7, `frame ${f}: text contrast`);
    for (const box of weak) for (const {x, y} of boxPoints(box)) {
      assert.ok(contrast(muted, sampleField(f, x, y)) >= 4.5, `frame ${f}: label contrast ${contrast(muted, sampleField(f, x, y)).toFixed(2)}`);
    }
    assert.ok(tinted <= 0.4 * outside, `frame ${f}: accent covers ${tinted}/${outside}`);
  }
  // Failure path: a full-strength accent fails the contrast bound, and muted on a lighter field fails 4.5:1.
  assert.ok(contrast(hexRgb(BRAND.accent), bg) > 1.5);
  assert.ok(contrast(muted, hexRgb(BRAND.raised)) < 4.5 || contrast(muted, [60, 60, 66]) < 4.5);
  // R62: an opaque TUI.bg window with no backdrop effect.
  assert.deepEqual(WINDOW, {background: TUI.bg, opacity: 1});
  const cli = readFileSync(join(CLI_DIR, 'GallianiCli.tsx'), 'utf8');
  const frame = cli.slice(cli.indexOf('const TerminalFrame'), cli.indexOf('const ShellLine'));
  assert.match(frame, /background: WINDOW\.background/);
  assert.match(frame, /opacity: WINDOW\.opacity/);
  assert.doesNotMatch(frame, /backdrop|opacity: 0/);
});

const insideSafe = (r: Rect) => r.x >= SAFE.left && r.x + r.width <= SAFE.right && r.y >= SAFE.top && r.y + r.height <= SAFE.bottom;

test('B-AC21: framing: the terminal in the safe area, whole-row scroll, a centered end card', () => {
  for (let f = 0; f < DURATION; f++) {
    const r = terminalRect(f);
    if (r) assert.ok(insideSafe(r), `frame ${f}: terminal ${JSON.stringify(r)} leaves the safe area`);
    assert.equal(transcriptOffset(f) % TERMINAL.row, 0, `frame ${f}: offset ${transcriptOffset(f)}`);
    const rows = visibleRows(f);
    if (!rows) continue;
    assert.equal(rows.areaHeight % TERMINAL.row, 0);
    for (const top of rows.tops) assert.ok(top >= 0 && top + TERMINAL.row <= rows.areaHeight, `frame ${f}: row at ${top} is clipped`);
    const b = beatAt(f);
    if (b.shot.kind === 'terminal') {
      const screen = screenAt(b.shot.keys, f - b.start).key.screen;
      assert.ok(rows.areaHeight + bottomRows(screen) * TERMINAL.row <= CONTENT.height, `frame ${f}: the bottom rows do not fit`);
      assert.ok(transcriptLayout(screen).areaRows >= BANNER_ROWS, `frame ${f}: the banner does not fit`);
    }
  }
  for (const row of BEATS.flatMap((b) => (b.shot.kind === 'terminal' ? b.shot.keys : [])).flatMap((k) => k.screen.entries.flatMap(entryRows))) {
    assert.ok(row.lead.length + row.text.length <= TERMINAL.transcriptColumns, `row too wide: ${row.text}`);
  }
  assert.ok(Math.abs(END_BLOCK.y + END_BLOCK.height / 2 - HEIGHT / 2) <= 4, 'end block vertical center');
  assert.ok(Math.abs(END_BLOCK.x + END_BLOCK.width / 2 - WIDTH / 2) <= 4, 'end block horizontal center');
  assert.equal(END_MARK.y, END_BLOCK.y, 'the mark tops the block');
  // Failure path: a frame a few px past the right margin is rejected.
  assert.equal(insideSafe({x: 300, y: 204, width: 1530, height: 780}), false);
  assert.deepEqual(wrap('aaaa bbbb cccc', 9), ['aaaa bbbb', 'cccc']);
});

// ---------------------------------------------------------------- the desktop act (R66-R73)

const drag = MOTIONS.find((m) => m.kind === 'drag') as CliMotion;
const absorb = MOTIONS.find((m) => m.kind === 'absorb') as CliMotion;
const cursorMotion = MOTIONS.find((m) => m.kind === 'cursor') as CliMotion;
const expand = MOTIONS.find((m) => m.kind === 'expand') as CliMotion;
const W = DESKTOP.window;
const CONTENT_RECT: Rect = {x: W.x + TERMINAL.border, y: W.y + TERMINAL.border + TERMINAL.titleBar, width: W.width - 2 * TERMINAL.border, height: W.height - 2 * TERMINAL.border - TERMINAL.titleBar};
/** Distance from a point to the line through a chord. */
const chordDistance = (p: Point, a: Point, b: Point) => Math.abs((b.x - a.x) * (a.y - p.y) - (a.x - p.x) * (b.y - a.y)) / Math.hypot(b.x - a.x, b.y - a.y);
/** B-AC22's drag checks for any path, so the failing fixtures run through the same code. */
function dragViolations(frames: number, path: (t: number) => Point, window: Rect = CONTENT_RECT): string[] {
  const out: string[] = [];
  if (frames < 30 || frames > 45) out.push(`drag lasts ${frames}`);
  const a = path(0);
  const b = path(1);
  let apex = 0;
  for (let i = 0; i <= 100; i++) {
    const p = path(i / 100);
    apex = Math.max(apex, chordDistance(p, a, b));
    const box = heroBoxes({center: p, scale: 1, rotation: 0, opacity: 1, hovered: true, home: false, label: true}).all;
    if (!insideSafe(box)) out.push(`t=${i / 100}: the icon leaves the safe area`);
  }
  if (apex > 160) out.push(`apex ${apex.toFixed(1)} px`);
  if (!inside(window, b.x, b.y)) out.push('the drag ends outside the window');
  return out;
}

test('B-AC22: the desktop, the cursor and the drag', () => {
  assert.equal(DESKTOP.icons.length, 3);
  assert.deepEqual(DESKTOP.icons.map((i) => i.label).sort(), ['Files', 'Notes', 'Projects']);
  assert.equal(DESKTOP.hero.label, 'Galliani');
  for (const i of [...DESKTOP.icons, DESKTOP.hero]) for (const box of [i.tile, i.labelBox]) assert.ok(insideSafe(box), `${i.label} leaves the safe area`);
  assert.ok(insideSafe(W), 'the window leaves the safe area');
  assert.ok(W.width < TERMINAL.width && W.height < TERMINAL.height, 'the desktop window is smaller than the Act 3 frame');
  assert.ok(DESKTOP.hero.tile.width > DESKTOP.icons[0].tile.width, 'the hero tile is the most prominent');
  assert.ok(DESKTOP.cursorHeight >= 28 && DESKTOP.cursorHeight <= 40);
  // The cursor: on screen only from its motion's start to the end of desk-drop, its final tip on the hero tile.
  const drop = beatById('desk-drop');
  for (let f = 0; f < DURATION; f++) {
    const on = f >= cursorMotion.start && f < drop.start + drop.duration;
    assert.equal(cursorAt(f) !== null, on, `frame ${f}: cursor`);
  }
  assert.ok(DESKTOP.cursorEntry.y > HEIGHT || DESKTOP.cursorEntry.x < 0 || DESKTOP.cursorEntry.x > WIDTH, 'the cursor enters from outside the frame');
  const tip = cursorAt(cursorMotion.start + cursorMotion.frames) as Point;
  assert.ok(inside(heroBoxes(heroIconAt(cursorMotion.start + cursorMotion.frames) as never).tile, tip.x, tip.y), 'the tip rests on the hero tile');
  // Hover: an instant 2 px lift and a label highlight when the cursor arrives.
  const arrive = cursorMotion.start + cursorMotion.frames;
  assert.equal(heroIconAt(arrive - 1)?.hovered, false);
  assert.equal(heroIconAt(arrive)?.hovered, true);
  assert.equal((heroIconAt(arrive - 1) as never as {center: Point}).center.y - (heroIconAt(arrive) as never as {center: Point}).center.y, DESKTOP.hoverLift);
  // The drag: one arc, in the safe area, ending inside the window and holding there before the drop.
  assert.deepEqual(dragViolations(drag.frames, dragPath), []);
  assert.equal(drag.easing, 'inOutCubic');
  for (let f = drag.start; f < drop.start; f++) {
    const hero = heroIconAt(f);
    assert.ok(hero && hero.scale === 1 && hero.rotation === 0 && !hero.home, `frame ${f}: the icon is scaled, turned or home`);
    assert.ok(insideSafe(heroBoxes(hero).all), `frame ${f}: the icon leaves the safe area`);
    const c = cursorAt(f) as Point;
    assert.ok(Math.abs(c.x - hero.center.x - DESKTOP.grab.x) < 1e-9 && Math.abs(c.y - hero.center.y - DESKTOP.grab.y) < 1e-9, `frame ${f}: the cursor lets go`);
  }
  const end = drag.start + drag.frames;
  assert.ok(drop.start - end >= 8, `the icon holds ${drop.start - end} frames before the drop`);
  for (let f = end; f < drop.start; f++) {
    const c = (heroIconAt(f) as never as {center: Point}).center;
    assert.ok(inside(CONTENT_RECT, c.x, c.y) && Math.hypot(c.x - DESKTOP.dragEnd.x, c.y - DESKTOP.dragEnd.y) < 1e-6, `frame ${f}: the icon moves after the drag`);
  }
  // The absorb: into the caret, small and gone.
  assert.equal(absorb.start, drop.start);
  assert.equal(absorb.easing, 'outExpo');
  const last = heroIconAt(absorb.start + absorb.frames - 1) as never as {center: Point; scale: number; opacity: number};
  const atEnd = {center: last.center, scale: last.scale, opacity: last.opacity};
  assert.ok(atEnd.scale <= 0.15, `scale ${atEnd.scale}`);
  assert.ok(Math.hypot(atEnd.center.x - SHELL_CARET.x, atEnd.center.y - SHELL_CARET.y) <= 4, 'the icon ends on the caret');
  assert.equal(atEnd.opacity, 0);
  assert.equal(heroIconAt(absorb.start + absorb.frames), null);
  for (let f = absorb.start; f < absorb.start + absorb.frames - 4; f++) assert.equal(heroIconAt(f)?.opacity, 1, `frame ${f}: the fade starts early`);
  const seam = beatById('end-seam');
  for (let f = drag.start; f < seam.start; f++) assert.ok(!heroIconAt(f)?.home, `frame ${f}: the home slot shows the icon`);
  for (let f = 0; f < drag.start; f++) assert.ok(heroIconAt(f)?.home, `frame ${f}: the icon left early`);
  // Focus: unfocused before desk-drop, focused from desk-drop to the launch-expand content cut.
  const cut = expand.start + expand.frames;
  for (let f = 0; f < DURATION; f++) assert.equal(windowFocused(f), f >= drop.start && f < cut, `frame ${f}: focus`);
  // Failure paths.
  assert.ok(dragViolations(drag.frames, (t) => ({...dragPath(t), y: dragPath(t).y - 600 * Math.sin(Math.PI * t)})).some((v) => v.includes('safe area')), 'fixture: off the safe area');
  assert.ok(dragViolations(drag.frames, (t) => ({x: dragPath(t).x * (1 - 0.6 * t), y: dragPath(t).y})).some((v) => v.includes('outside the window')), 'fixture: ends outside the window');
  assert.ok(dragViolations(50, dragPath).some((v) => v.includes('drag lasts 50')), 'fixture: a 50-frame drag');
  assert.ok(chordDistance(dragPath(0.5), DRAG_CHORD.from, DRAG_CHORD.to) <= 160);
  assert.ok(heroHome().x === DESKTOP.hero.tile.x + DESKTOP.hero.tile.width / 2);
});

test('B-AC23: the load: typed command, a cleared window that grows, then the TUI cuts in', () => {
  const type = beatById('launch-type');
  assert.ok(type.shot.kind === 'shell');
  if (type.shot.kind !== 'shell') return;
  assert.equal(type.shot.typing.text, TERM.command);
  assert.ok(type.shot.typing.from + type.shot.typing.frames <= type.duration - 8, 'typing ends 8 frames before the beat ends');
  assert.equal(shellCommand(type.start + type.duration - 1), TERM.command);
  for (let f = type.start; f < type.start + type.duration; f++) {
    assert.equal(cursorAt(f), null, `frame ${f}: the cursor`);
    assert.ok(desktopShown(f), `frame ${f}: the desktop is gone early`);
  }
  const beat = beatById('launch-expand');
  assert.equal(expand.beat, beat.id);
  assert.equal(expand.start, beat.start);
  assert.ok(expand.frames >= 10 && expand.frames <= 15);
  assert.ok(!desktopShown(beat.start), 'the icons are gone at the cut');
  assert.equal(tuiShown(beat.start), false, 'the window content is empty at the cut');
  assert.deepEqual(terminalRect(beat.start), W, 'the expand starts from the desktop rectangle');
  let prev = terminalRect(beat.start) as Rect;
  for (let f = beat.start; f <= expand.start + expand.frames; f++) {
    const r = terminalRect(f) as Rect;
    assert.ok(insideSafe(r), `frame ${f}: the growing window leaves the safe area`);
    assert.ok(r.x <= prev.x && r.y <= prev.y && r.x + r.width <= prev.x + prev.width + 1e-9 && r.y + r.height >= prev.y + prev.height - 1e-9, `frame ${f}: an edge turns back`);
    prev = r;
  }
  assert.deepEqual(terminalRect(expand.start + expand.frames), {x: TERMINAL.x, y: TERMINAL.y, width: TERMINAL.width, height: TERMINAL.height});
  const cut = expand.start + expand.frames;
  for (let f = beat.start; f < cut; f++) assert.ok(!tuiShown(f) && robotPose(f) === null, `frame ${f}: content or robot before the expansion ends`);
  assert.ok(tuiShown(cut) && robotPose(cut) !== null, 'the banner, prompt, status line and robot cut in on the first frame after');
  // The banner is never typed: no Typing carries banner text.
  const typedTexts = typings().map(({typing}) => typing.text);
  for (const s of [TERM.bannerTitle, TERM.bannerRouting, TERM.bannerSettings, ...TERM.tips]) assert.ok(!typedTexts.includes(s), s);
  // No CSS scale anywhere in the components: sizes come from rectangles.
  for (const {name, source} of cliSources()) if (name.endsWith('.tsx')) assert.doesNotMatch(source, /scale\(/, `${name} uses a CSS scale`);
});

// ---------------------------------------------------------------- the robot (R74-R79)

const SHAPE_ORDER = ['thruster', 'body', 'chest', 'armLeft', 'armRight', 'antenna', 'antennaTip', 'head', 'face', 'eyeLeft', 'eyeRight'] as const;
const STATIC_ATTRS = ['x', 'y', 'width', 'height', 'rx', 'cx', 'cy', 'r', 'ry', 'x1', 'y1', 'x2', 'y2'];
/** The numeric literal attributes of each shape in Robot.tsx, in drawing order. */
function showcaseShapes(source: string): Record<string, number>[] {
  return [...source.matchAll(/<(ellipse|rect|circle|line)\s([^>]*?)\/>/g)].map((m) =>
    Object.fromEntries([...m[2].matchAll(/(\w+)=\{(-?[\d.]+)\}/g)].filter((a) => STATIC_ATTRS.includes(a[1])).map((a) => [a[1], Number(a[2])])));
}
const shapesMatch = (shapes: readonly Record<string, number>[]) =>
  shapes.length === SHAPE_ORDER.length && SHAPE_ORDER.every((name, i) => JSON.stringify(ROBOT_SHAPES[name]) === JSON.stringify(shapes[i]));

test('B-AC24: the robot is the showcase robot, copied, not imported', () => {
  assert.ok(shapesMatch(showcaseShapes(ROBOT_TSX)), 'ROBOT_SHAPES drifted from Robot.tsx');
  assert.equal(shapesMatch(showcaseShapes(ROBOT_TSX.replace('width={46} height={30}', 'width={48} height={30}'))), false, 'fixture: one changed attribute fails');
  const v = ROBOT_FRAME.viewBox;
  assert.ok(ROBOT_TSX.includes(`viewBox="${v.x} ${v.y} ${v.width} ${v.height}"`), 'viewBox');
  assert.ok(ROBOT_TSX.includes(`${ROBOT_FRAME.pivotLeft.x} ${ROBOT_FRAME.pivotLeft.y})`) && ROBOT_TSX.includes(`${ROBOT_FRAME.pivotRight.x} ${ROBOT_FRAME.pivotRight.y})`), 'arm pivots');
  assert.ok(ROBOT_TSX.includes(`rotate(\${${ROBOT_FRAME.restArm} +`) && ROBOT_TSX.includes(`rotate(\${-${ROBOT_FRAME.restArm} -`), 'rest arm angles');
  assert.ok(ROBOT_TSX.includes(`eyeDY - ${-ROBOT_FRAME.eyeRow}`) && ROBOT_TSX.includes(`height={${ROBOT_FRAME.eyeHeight} * blink}`), 'eye row and height');
  assert.ok(ROBOT_TSX.includes(`strokeWidth={${ROBOT_FRAME.antennaWidth}}`), 'antenna stroke');
  const robot = readFileSync(join(CLI_DIR, 'robot.tsx'), 'utf8');
  assert.doesNotMatch(robot, /from ['"]\.\.\/(Robot|timeline|Showcase)/, 'robot.tsx imports the showcase');
  for (const {name, source} of cliSources()) assert.doesNotMatch(source, /from ['"]\.\.\/(Robot|timeline|Showcase)(\.tsx?)?['"]/, `${name} imports the showcase`);
  assert.doesNotMatch(robot, /filter|drop-shadow|Math\.sin/);
  assert.ok(ROBOT_FRAME.thrusterOpacity <= 0.25);
  assert.match(robot, /<ellipse \{\.\.\.S\.thruster\} fill=\{ROBOT\.eye\} opacity=\{ROBOT_FRAME\.thrusterOpacity\}/);
  // Only breathAt in pose.ts uses a sine.
  const pose = readFileSync(join(CLI_DIR, 'pose.ts'), 'utf8');
  assert.equal([...pose.matchAll(/Math\.sin/g)].length, 1);
  assert.match(pose, /export const breathAt = \(frame: number\) => ROBOT_BREATH\.px \* Math\.sin/);
  assert.ok(ROBOT_HEIGHT >= 180 && ROBOT_HEIGHT <= 240);
  for (const box of Object.values(ROBOT_PLACE)) assert.ok(Math.abs(box.height - ROBOT_HEIGHT) < 1e-9 && Math.abs(box.width / box.height - v.width / v.height) < 1e-9, 'one uniform scale');
  // Breath: at most 3 px, one 60-120 frame period.
  assert.ok(ROBOT_BREATH.px <= 3 && ROBOT_BREATH.period >= 60 && ROBOT_BREATH.period <= 120);
  for (let f = 0; f < DURATION; f++) {
    assert.ok(Math.abs(breathAt(f)) <= 3);
    assert.ok(Math.abs(breathAt(f + ROBOT_BREATH.period) - breathAt(f)) < 1e-9);
  }
  // Blinks: 90+ frames apart, never in a gesture, BLINK_FRAMES long.
  ROBOT_BLINKS.forEach((b, i) => {
    if (i > 0) assert.ok(b - ROBOT_BLINKS[i - 1] >= 90, `blink at ${b}`);
    for (const g of GESTURES) assert.ok(b + BLINK_FRAMES <= g.start || b >= g.start + g.frames, `blink at ${b} falls in a gesture`);
    assert.ok(robotShownAt(b) && robotShownAt(b + BLINK_FRAMES - 1), `blink at ${b} is off screen`);
  });
  assert.equal(BLINK_FRAMES, 6);
  // Outside gestures and blinks, every pose field but breath is constant over each idle stretch.
  const inGesture = (f: number) => GESTURES.some((g) => f >= g.start && f < g.start + g.frames);
  const still = (p: RobotPose) => JSON.stringify({...p, breath: 0, box: 0});
  let prev: string | null = null;
  for (let f = 0; f < DURATION; f++) {
    const p = robotPose(f);
    if (!p || inGesture(f) || p.blink !== 1) {
      prev = null;
      continue;
    }
    if (prev !== null && beatAt(f).start !== f) assert.equal(still(p), prev, `frame ${f}: the robot moves while idle`);
    prev = still(p);
  }
});

test('B-AC25: robot placement and the one-gesture-per-beat schedule', () => {
  const cut = expand.start + expand.frames;
  const endCard = beatById('end-card');
  for (let f = 0; f < DURATION; f++) {
    const p = robotPose(f);
    assert.equal(p !== null, f >= cut && f < endCard.start + endCard.duration, `frame ${f}: robot on screen`);
    if (!p) continue;
    const box = robotBoxAt(p);
    assert.ok(insideSafe(box), `frame ${f}: the robot leaves the safe area`);
    const term = terminalRect(f);
    if (term) {
      const gap = {x: term.x - 16, y: term.y - 16, width: term.width + 32, height: term.height + 32};
      assert.ok(!overlaps(box, gap), `frame ${f}: the robot is within 16 px of the terminal`);
    }
    const c = captionAt(f);
    if (c) assert.ok(!overlaps(box, c.box), `frame ${f}: the robot covers the caption`);
    if (endCardShown(f)) assert.ok(!overlaps(box, END_BLOCK), `frame ${f}: the robot covers the end block`);
    const before = robotPose(f - 1);
    if (before && beatAt(f).start !== f) assert.deepEqual(before.box, p.box, `frame ${f}: the robot travels`);
  }
  // Gestures equal the R46 Robot column, one per beat at most.
  for (const [id, , robot] of STORYBOARD) {
    const g = GESTURES.filter((m) => m.beat === id);
    if (robot === null || robot === 'idle') assert.deepEqual(g, [], `${id} has a gesture`);
    else assert.deepEqual(g.map((m) => m.pose), [robot], `${id} gesture`);
  }
  assert.equal(GESTURES.length, 8);
  const sign = (x: number) => Math.abs(x);
  for (const g of GESTURES) {
    assert.ok(g.frames <= 30 && g.start % GRID === 0, `${g.beat}: ${g.frames} frames at ${g.start}`);
    assert.ok(g.easing === 'outQuart' || g.easing === 'outExpo');
    assert.ok((g.legs ?? []).length <= (g.pose === 'wave' ? 3 : 3) && (g.legs ?? []).length >= 1, `${g.beat} legs`);
    assert.deepEqual(emphasizedOf(beatById(g.beat)), ['gesture'], `${g.beat}: a gesture beside another emphasized motion`);
    for (let f = g.start; f < g.start + g.frames; f++) {
      const p = robotPose(f) as RobotPose;
      assert.ok(sign(p.headTilt) <= 10 && sign(p.lean) <= 8 && sign(p.eyeX) <= 6 && sign(p.eyeY) <= 4, `${g.beat} frame ${f}: past the pose bounds`);
      if (g.pose === 'glance') assert.ok(p.lean === 0 && p.armLeft === ROBOT_FRAME.restArm, 'glance turns only the eyes and head');
      if (g.pose === 'nod') assert.ok(p.lean === 0 && p.eyeX === 0, 'nod moves only the head');
    }
  }
  // Moving legs: two (out and back) for each pose, three for wave; raise and lower are one leg each.
  for (const [pose, shape] of Object.entries(POSES)) {
    const moving = pose === 'wave' ? 3 : shape.legs.length === 1 ? 1 : 2;
    assert.ok(moving <= (pose === 'wave' ? 3 : 2), pose);
  }
  assert.ok(POSES.wave.swing <= 20);
  // point aims within 20° of the plan panel from its shoulder, at the hold.
  const point = GESTURES.find((g) => g.pose === 'point') as CliMotion;
  const held = robotPose(point.start + (point.legs as number[])[0]) as RobotPose;
  const s = shoulderAt(held.box, 'left');
  const t = TARGETS.plan;
  const want = (Math.atan2(-(t.x + t.width / 2 - s.x), t.y + t.height / 2 - s.y) * 180) / Math.PI;
  assert.ok(Math.abs(held.armLeft - want) <= 20, `point aims ${held.armLeft.toFixed(1)}°, wants ${want.toFixed(1)}°`);
  assert.ok(Math.abs(aimAngle(held.box, t) - want) < 1e-9);
  // raise holds into approval-answer as a still pose; lower starts on the frame `y` is pressed.
  const raise = GESTURES.find((g) => g.pose === 'raise') as CliMotion;
  const lower = GESTURES.find((g) => g.pose === 'lower') as CliMotion;
  const answer = beatById('approval-answer');
  assert.equal(lower.start, answer.start + PRESS_Y);
  if (answer.shot.kind === 'terminal') assert.ok(screenAt(answer.shot.keys, PRESS_Y).key.screen.approval?.pressed, '`y` is pressed at the lower');
  const up = (robotPose(raise.start + raise.frames) as RobotPose).armLeft;
  for (let f = raise.start + raise.frames; f <= lower.start; f++) assert.equal((robotPose(f) as RobotPose).armLeft, up, `frame ${f}: the raised arm moves`);
  assert.equal((robotPose(lower.start + lower.frames) as RobotPose).armLeft, ROBOT_FRAME.restArm);
  // cheer: both arms up and back once; wave: one arm up, a 20° swing, down.
  const cheer = GESTURES.find((g) => g.pose === 'cheer') as CliMotion;
  assert.equal((robotPose(cheer.start + cheer.frames) as RobotPose).armLeft, ROBOT_FRAME.restArm);
  const wave = GESTURES.find((g) => g.pose === 'wave') as CliMotion;
  assert.equal((robotPose(wave.start + wave.frames) as RobotPose).armRight, -ROBOT_FRAME.restArm);
  // Failure path: a gesture in route-first, which has a count.
  const fixture = BEATS.map((b) => (b.id === 'route-first' ? {...b, gesture: {at: 15, pose: 'glance' as const, target: 'route' as const}} : b));
  assert.ok(budgetViolations(fixture, deriveMotions(fixture, CAPTIONS)).some((v) => v.startsWith('route-first: 2 emphasized')));
  assert.ok(movingAt(point.start).includes('robot'), 'a gesture is a motion');
});

// ---------------------------------------------------------------- render settings and copy (R47, R67, R80-R82)

const PKG = JSON.parse(read('../package.json'));
/** B-AC26 on a scripts object, so the failing fixture runs through the same checks. */
function scriptViolations(scripts: Record<string, string>, stillsScript: string): string[] {
  const out: string[] = [];
  const preview = scripts['preview:cli'] ?? '';
  for (const [, s] of preview.matchAll(/--scale=([\d.]+)/g)) if (Number(s) < 1) out.push(`preview scale ${s}`);
  if (!/out\/galliani-cli-preview\.mp4/.test(preview)) out.push('preview output');
  const render = scripts['render:cli'] ?? '';
  for (const flag of ['--scale=2', '--codec=h264', '--pixel-format=yuv420p', 'out/galliani-cli.mp4']) if (!render.includes(flag)) out.push(`render lacks ${flag}`);
  const crf = render.match(/--crf=(\d+)/);
  if (!crf || Number(crf[1]) > 16) out.push('render crf');
  const jpeg = render.match(/--jpeg-quality=(\d+)/);
  if (!render.includes('--image-format=png') && !(jpeg && Number(jpeg[1]) >= 95)) out.push('render frame format');
  if (!(scripts['stills:cli'] ?? '').includes('--scale=2') && !stillsScript.includes('--scale=2') && !/--scale=\$\{CLI_RENDER\.stillScale\}/.test(stillsScript)) out.push('stills scale');
  return out;
}

test('B-AC26: render scripts, resolution and image sizes', () => {
  const stills = read('../scripts/cli-stills.ts');
  assert.deepEqual(scriptViolations(PKG.scripts, stills), []);
  assert.equal(CLI_RENDER.stillScale, 2);
  assert.ok(scriptViolations({...PKG.scripts, 'preview:cli': PKG.scripts['preview:cli'] + ' --scale=0.5'}, stills).some((v) => v.startsWith('preview scale')), 'fixture: a half-scale preview fails');
  assert.deepEqual(PKG.dependencies, {'@remotion/cli': '4.0.533', react: '19.2.0', 'react-dom': '19.2.0', remotion: '4.0.533'});
  assert.deepEqual(PKG.devDependencies, {'@types/node': '26.6.4', '@types/react': '19.2.2', typescript: '5.9.3'});
  assert.equal(PKG.scripts.render, 'remotion render src/index.ts GallianiShowcase out/galliani-showcase.mp4', 'the showcase script is unchanged');
  // No mark drawn above 320 authored px (the PNGs are 640 px, so nothing is upscaled at scale 2).
  for (const size of [END.markSize, DESKTOP.markSize]) assert.ok(size <= 320, `mark ${size}`);
  const cli = readFileSync(join(CLI_DIR, 'GallianiCli.tsx'), 'utf8');
  assert.deepEqual([...cli.matchAll(/<Mark size=\{([^}]+)\}/g)].map((m) => m[1]).sort(), ['DESKTOP.markSize * hero.scale', 'END.markSize']);
  // No border, line or text under 1 authored px.
  for (const w of [TERMINAL.border, TERMINAL.focusBorder]) assert.ok(w >= 1);
  const readme = read('../README.md');
  assert.match(readme, /3840x2160/);
  assert.match(readme, /preview:cli[\s\S]*\d+(\.\d+)? ?(s|min)[\s\S]*\d+(\.\d+)? ?MB/, 'measured preview time and size');
  assert.match(readme, /render:cli[\s\S]*\d+(\.\d+)? ?(s|min)[\s\S]*\d+(\.\d+)? ?MB/, 'measured render time and size');
});

const BRAND_NAMES = /windows|macos|mac os|ubuntu|linux|apple|microsoft|finder|explorer|powershell|iterm|windows terminal|chrome|safari|firefox|edge|vs ?code|visual studio|jetbrains|intellij|sublime|vim|emacs|zed|claude|anthropic|openai|chatgpt|gemini|copilot|cursor ai/i;

test('B-AC27: copy outside the terminal is the captions, galliacli and the desktop labels', () => {
  const allowed = new Set([...CAPTION_TEXTS, TERM.command, 'Galliani', 'Notes', 'Files', 'Projects']);
  const outside = [...CAPTIONS.map((c) => c.text), TERM.command, DESKTOP.hero.label, ...DESKTOP.icons.map((i) => i.label), ...DESKTOP_LABELS];
  for (const s of outside) {
    assert.ok(allowed.has(s), `"${s}" is not allowed outside the terminal`);
    assert.doesNotMatch(s, BRAND_NAMES, s);
  }
  assert.match('Finder', BRAND_NAMES, 'fixture: a real app name is rejected');
  // The components outside the terminal print only data: no string literal children in them.
  const cli = readFileSync(join(CLI_DIR, 'GallianiCli.tsx'), 'utf8');
  for (const name of ['Caption', 'EndCard', 'Label', 'GenericIcon', 'HeroIcon', 'CursorArrow', 'DesktopIcons']) {
    const start = cli.indexOf(`const ${name}`);
    assert.ok(start >= 0, name);
    const body = cli.slice(start, cli.indexOf('\n};', start));
    assert.doesNotMatch(body, />[ \t]*[A-Za-z][^<{]*</, `${name} draws literal text`);
  }
});
