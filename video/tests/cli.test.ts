// Checks for the GallianiCli composition (spec 015 Part B, B-AC2..B-AC11, B-AC15..B-AC21). Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {
  ACCENTS, BLOBS, FIELD_COLORS, FIELD_PERIODS, WAVES, accentAt, backgroundField, phaseAt, sampleField,
} from '../src/cli/background.ts';
import {
  BANNER_ROWS, CONTENT, END_BLOCK, END_CTA, END_MARK_Y, HOOK_PROMPT, WINDOW, bottomRows, ctaShown, entryRows,
  hookPromptShown, markAt, terminalRect, transcriptLayout, transcriptOffset, visibleRows, wrap,
} from '../src/cli/layout.ts';
import type {Rect} from '../src/cli/layout.ts';
import {MIN_HOLD, MOTIONS, activeAt, budgetViolations, changeFrames, costAt, deriveMotions, longestHold} from '../src/cli/motion.ts';
import type {CliMotion, MotionKind} from '../src/cli/motion.ts';
import {BRAND, TUI} from '../src/cli/palette.ts';
import {
  AT_DONE, AT_PROMPT, BEATS, CAPTIONS, CAPTION_ENTER, CARD_ENTER_FRAMES, CLI_RENDER, DURATION, FILE_ROWS_ALL,
  FILE_ROWS_SIG, FPS, GOAL, GRID, HEIGHT, PLAN_STEPS, ROUTE_CODING, ROUTE_TEXT, SAFE, SEAM_MARK, SLASH_ROWS, TERM,
  TERMINAL, WIDTH, beatAt, captionAt, charTimes, planSummary, popupLines, screenAt, statusText, stepLine, typedCount,
  typedText, workingText,
} from '../src/cli/timeline.ts';
import type {CliBeat} from '../src/cli/timeline.ts';

const read = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8');
const STYLES = read('../../galliani/tui/styles.py');
const CLI_DIR = fileURLToPath(new URL('../src/cli', import.meta.url));
const cliSources = () => readdirSync(CLI_DIR).map((name) => ({name, source: readFileSync(join(CLI_DIR, name), 'utf8')}));

// R26: hex, rgb(), rgba(), hsl(), hsla(), and the keywords white and black.
const COLOR_LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\bwhite\b|\bblack\b/;

function pythonDict(source: string, name: string): Record<string, string> {
  const body = source.match(new RegExp(`^${name} = \\{([\\s\\S]*?)\\n\\}`, 'm'));
  assert.ok(body, `${name} not found in styles.py`);
  return Object.fromEntries([...body[1].matchAll(/"([a-z]+)":\s*"(#[0-9a-fA-F]{6})"/g)].map((m) => [m[1], m[2]]));
}

test('B-AC5: TUI palette equals DARK_PALETTE in styles.py', () => {
  const dark = pythonDict(STYLES, 'DARK_PALETTE');
  assert.equal(Object.keys(dark).length, 10);
  assert.deepEqual(TUI, dark);
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

test('B-AC6: no color literal outside palette.ts, and palette.ts holds only R25 values', () => {
  for (const {name, source} of cliSources()) {
    if (name === 'palette.ts') continue;
    assert.doesNotMatch(source, COLOR_LITERAL, `${name} has a color literal`);
  }
  const allowed = new Set<string>([...Object.values(BRAND), ...Object.values(TUI)]);
  assert.equal(allowed.size, 16);
  const palette = readFileSync(join(CLI_DIR, 'palette.ts'), 'utf8');
  for (const [hex] of palette.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) assert.ok(allowed.has(hex), `${hex} is not an R25 value`);
  assert.doesNotMatch(palette, /\brgba?\(|\bhsla?\(|\bwhite\b|\bblack\b/);
});

// ---------------------------------------------------------------- timeline (V2.2)

const WIDGETS = read('../../galliani/tui/widgets.py');
const COMMANDS_PY = read('../../galliani/tui/commands.py');
const BEAT_IDS = [
  'hook-mark', 'hook-prompt', 'launch-type', 'launch-banner', 'goal-type', 'plan-steps', 'plan-check',
  'route-first', 'route-next', 'slash-popup', 'at-file', 'approval-card', 'approval-answer', 'verified-done', 'end-card',
];
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

test('B-AC2: 20-30 s, and the beats add up to the composition', () => {
  const seconds = DURATION / FPS;
  assert.ok(seconds >= 20 && seconds <= 30, `${seconds}s`);
  assert.equal(BEATS.reduce((sum, b) => sum + b.duration, 0), DURATION);
  const {compositionId, fps, width, height, durationInFrames} = CLI_RENDER;
  assert.deepEqual({compositionId, fps, width, height, durationInFrames},
    {compositionId: 'GallianiCli', fps: 30, width: 1920, height: 1080, durationInFrames: DURATION});
  assert.match(read('../src/Root.tsx'), /id=\{CLI_RENDER\.compositionId\}[\s\S]*durationInFrames=\{CLI_RENDER\.durationInFrames\}/);
});

test('B-AC3: beat order, contiguity and length', () => {
  assert.deepEqual(BEATS.map((b) => b.id), BEAT_IDS);
  BEATS.forEach((b, i) => {
    assert.equal(b.start, i === 0 ? 0 : BEATS[i - 1].start + BEATS[i - 1].duration, `${b.id} start`);
    assert.ok(b.duration >= 30 && b.duration <= 90, `${b.id} lasts ${b.duration}`);
  });
  const last = BEATS[BEATS.length - 1];
  assert.equal(last.start + last.duration, DURATION);
});

test('B-AC4: seven exact captions, each over its whole segment, no gaps or overlaps', () => {
  assert.deepEqual(CAPTIONS.map((c) => c.text), CAPTION_TEXTS);
  let cursor = 0;
  for (const c of CAPTIONS) {
    const beats = BEATS.filter((b) => b.segment === c.segment);
    assert.equal(c.start, beats[0].start, `${c.text} start`);
    assert.equal(c.end, beats[beats.length - 1].start + beats[beats.length - 1].duration, `${c.text} end`);
    assert.equal(c.start, cursor, `gap or overlap before ${c.text}`);
    const seconds = (c.end - c.start) / FPS;
    assert.ok(seconds >= 2 && seconds <= 5, `${c.text} on screen ${seconds}s (R43)`);
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
  const data = JSON.stringify({BEATS, CAPTIONS, TERM, SLASH_ROWS, FILE_ROWS_ALL, FILE_ROWS_SIG, AT_PROMPT, AT_DONE});
  for (const text of [data, ...cliSources().map((s) => s.source)]) {
    assert.doesNotMatch(text, /stream|resume|--continue|thinking|chain-of-thought|reasoning/i);
    assert.doesNotMatch(text, /sk-|Bearer |API_KEY/);
    assert.ok(!text.includes('C:\\Users\\') && !text.includes('C:\\\\Users\\\\'), 'a Windows home path');
    assert.doesNotMatch(text, /\/home\/|\/Users\//);
    assert.doesNotMatch(text, /[\w.+-]+@[\w-]+\.[a-z]{2,}/i);
  }
});

test('B-AC9: deterministic source, only the mark assets, dependencies unchanged', () => {
  for (const {name, source} of cliSources()) {
    assert.doesNotMatch(source, /Math\.random|Date\.now|new Date|performance\.now|fetch\(|setTimeout|setInterval/, name);
  }
  const publicDir = fileURLToPath(new URL('../public', import.meta.url));
  assert.deepEqual(readdirSync(publicDir).sort(), ['galliani-mark-g.png', 'galliani-mark-star.png', 'galliani-mark.png']);
  const pkg = JSON.parse(read('../package.json'));
  assert.deepEqual(pkg.dependencies, {'@remotion/cli': '4.0.533', react: '19.2.0', 'react-dom': '19.2.0', remotion: '4.0.533'});
  assert.deepEqual(pkg.devDependencies, {'@types/node': '26.6.4', '@types/react': '19.2.2', typescript: '5.9.3'});
});

test('B-AC10: captions sit in the title-safe area on one line', () => {
  for (const c of CAPTIONS) {
    const {x, y, width, height, fontSize} = c.box;
    assert.ok(x >= 96 && x + width <= WIDTH - 96 && y >= 54 && y + height <= HEIGHT - 54, `${c.text} leaves the safe area`);
    assert.ok(fontSize >= 56, `${c.text} font ${fontSize}`);
    assert.ok(c.text.length * fontSize * 0.6 <= width, `${c.text} does not fit on one line`);
    assert.ok(fontSize * 1.2 <= height, `${c.text} box too short`);
  }
  // Captions over the terminal stay above its frame (R42).
  for (const c of CAPTIONS.filter((c) => BEATS.some((b) => b.segment === c.segment && b.shot.kind === 'terminal'))) {
    assert.ok(c.box.y + c.box.height <= TERMINAL.y, `${c.text} overlaps the terminal`);
  }
});

// ---------------------------------------------------------------- motion (R37-R39, R49-R57)

const beatById = (id: string) => BEATS.find((b) => b.id === id) as CliBeat;
const BANNED_MOTION = /TransitionSeries|@remotion\/transitions|crossfade|dissolve|spring|Easing\.(linear|back|elastic|bounce|bezier)/i;

test('B-AC11: motion bounds, hard cuts and easing', () => {
  const bounds: Record<MotionKind, (m: CliMotion) => boolean> = {
    caption: (m) => m.frames <= 6 && (m.slide ?? 0) <= 32,
    push: (m) => m.frames <= 15 && !!m.zoom && [m.zoom.from, m.zoom.to].every((z) => z >= 1 && z <= 1.15),
    entrance: (m) => m.frames >= 6 && m.frames <= 10 && (m.slide ?? 0) <= 32,
    move: (m) => m.frames <= 15,
    count: (m) => m.frames <= 15,
    card: (m) => m.frames === CARD_ENTER_FRAMES,
  };
  assert.ok(MOTIONS.length > 0);
  for (const m of MOTIONS) {
    assert.ok(m.kind in bounds && bounds[m.kind](m), `${m.beat} ${m.kind} is out of bounds`);
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
  for (const {source, name} of cliSources()) {
    assert.doesNotMatch(source, BANNED_MOTION, `${name} uses a banned motion`);
    for (const m of source.matchAll(/\binterpolate\(/g)) {
      assert.match(source.slice(m.index, m.index + 240), /easing:/, `${name}: interpolate without an explicit easing`);
    }
    for (const m of source.matchAll(/Easing\.out\(/g)) {
      assert.match(source.slice(m.index), /^Easing\.out\(Easing\.(exp|poly\(4\))\)/, `${name}: easing other than out-exp or out-quart`);
    }
  }
  // No punch-in, pulse or per-word stagger field anywhere in the scene data (field names, not copy).
  const fields = new Set<string>();
  const walk = (v: unknown): void => {
    if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) (fields.add(k), walk(x));
  };
  walk({BEATS, CAPTIONS, MOTIONS, CAPTION_ENTER});
  const BANNED_FIELD = /punch|pulse|stagger|bump|flash|glow|shake|wobble|word/i;
  assert.deepEqual([...fields].filter((k) => BANNED_FIELD.test(k)), []);
  assert.ok(BANNED_FIELD.test('wordStagger'), 'fixture: a per-word stagger field is rejected');
  assert.match('Easing.out(Easing.back(2))', /Easing\.out\(Easing\.back/, 'fixture: the scan sees an overshooting easing');
});

test('B-AC15: one emphasized motion per beat, at most two animating, a hold in every beat', () => {
  assert.deepEqual(budgetViolations(), []);
  for (const b of BEATS) assert.ok(longestHold(b) >= MIN_HOLD, `${b.id} hold`);
  for (let f = 0; f < DURATION; f++) assert.ok(activeAt(f).length <= 2, `frame ${f}: ${activeAt(f)}`);
  // Failure path: a second emphasized motion in a beat, and a beat with no hold.
  const twice = BEATS.map((b) => (b.id === 'plan-steps' ? {...b, push: {at: 0, frames: 15, from: 1, to: 1.05, origin: {x: 960, y: 540}}} : b));
  assert.ok(budgetViolations(twice, deriveMotions(twice, CAPTIONS)).some((v) => v.startsWith('plan-steps: 2 emphasized')));
  const busy = BEATS.map((b) => (b.id === 'route-next' && b.shot.kind === 'terminal'
    ? {...b, shot: {kind: 'terminal' as const, keys: Array.from({length: 12}, (_, i) => ({at: i * 4, screen: b.shot.kind === 'terminal' ? b.shot.keys[0].screen : idleScreen()}))}}
    : b));
  assert.ok(budgetViolations(busy, deriveMotions(busy, CAPTIONS)).some((v) => v.startsWith('route-next: longest hold')));
  const crowded = [...MOTIONS, {kind: 'caption' as const, beat: 'goal-type', target: 'extra', start: 195, frames: 6}];
  assert.ok(budgetViolations(BEATS, crowded).some((v) => v.includes('animate at once')));
});
function idleScreen() {
  const b = beatById('launch-banner');
  return b.shot.kind === 'terminal' ? b.shot.keys[0].screen : (undefined as never);
}

const offGrid = (beats: readonly CliBeat[], motions: readonly CliMotion[]) => [
  ...beats.flatMap((b) => (b.start % GRID ? [b.id] : [])),
  ...motions.flatMap((m) => (m.start % GRID ? [`${m.beat} ${m.kind}`] : [])),
];

test('B-AC16: the 15-frame grid, the pace and a start with no dead frames', () => {
  assert.equal(GRID, 15);
  assert.deepEqual(offGrid(BEATS, MOTIONS), []);
  assert.ok(DURATION >= 660 && DURATION <= 750, `${DURATION} frames`);
  for (const c of CAPTIONS) assert.ok(c.end - c.start >= 60 && c.end - c.start <= 150, `${c.text} lasts ${c.end - c.start}`);
  const hook = CAPTIONS[0];
  assert.equal(hook.start, 0);
  assert.ok(hook.enterFrames === 0 || hook.enterFrames <= 12, 'the hook caption is readable by frame 12');
  assert.ok(markAt(0), 'the mark is on screen at frame 0');
  // Failure path: a motion off the grid.
  assert.deepEqual(offGrid(BEATS, [{kind: 'push', beat: 'goal-type', target: 'camera', start: 187, frames: 15}]), ['goal-type push']);
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
  for (const {beat, typing} of typed) assert.ok(intervalsOk(charTimes(typing)), `${beat.id} typing does not speed up`);
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
  for (const b of BEATS) {
    if (!b.count || b.shot.kind !== 'terminal') continue;
    const at = screenAt(b.shot.keys, b.count.at).key.screen.status.cost;
    const before = screenAt(b.shot.keys, b.count.at - 1).key.screen.status.cost;
    assert.equal(b.count.to, at, `${b.id} counts to the screen's cost`);
    assert.equal(b.count.from, before, `${b.id} counts from the cost before`);
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

test('B-AC18: the last frame matches frame 0 and the video ends on a hold', () => {
  const last = DURATION - 1;
  assert.ok(fieldClose(backgroundField(0), backgroundField(last)), 'the field jumps at the seam');
  const [a, b] = [markAt(0), markAt(last)];
  assert.ok(a && b);
  assert.ok(Math.abs(a.x - b.x) <= 0.5 && Math.abs(a.y - b.y) <= 0.5 && Math.abs(a.size - b.size) <= 0.5 && Math.abs(a.opacity - b.opacity) <= 0.01);
  for (const f of [0, last]) {
    assert.equal(terminalRect(f), null, `a terminal or shell line shows at ${f}`);
    assert.equal(ctaShown(f), false, `the call to action shows at ${f}`);
    assert.equal(hookPromptShown(f), false);
  }
  const end = BEATS[BEATS.length - 1];
  const changes = changeFrames(end);
  for (let local = end.duration - 7; local < end.duration; local++) {
    assert.ok(!changes.has(local) && activeAt(end.start + local).length === 0, `frame ${end.start + local} changes`);
  }
  assert.equal(fieldClose(backgroundField(0), backgroundField(90)), false, 'fixture: a moved field is rejected');
});

const ALLOWED_FIELD = ['bg', 'surface', 'raised', 'border', 'muted', 'accent', 'agent'];
const BANNED_EFFECT = /filter|blur\(|feGaussianBlur|drop-shadow|mix-?blend|<canvas|box-?shadow|text-?shadow|backdrop/i;

test('B-AC19: the field is deterministic, periodic and built from palette keys', () => {
  for (let f = 0; f <= DURATION; f++) assert.deepEqual(backgroundField(f), backgroundField(f), `frame ${f}`);
  assert.deepEqual(backgroundField(DURATION), backgroundField(0));
  const {blobs, waves} = backgroundField(0);
  assert.ok(blobs.length >= 2 && blobs.length <= 3 && waves.length >= 2 && waves.length <= 3);
  for (const p of FIELD_PERIODS) assert.ok(p >= 240 && p <= 360 && DURATION % p === 0, `period ${p}`);
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
  assert.match('style={{filter: "blur(4px)"}}', BANNED_EFFECT, 'fixture: the scan sees a blur');
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
const markBox = (f: number): Rect | null => {
  const m = markAt(f);
  return m ? {x: m.x - m.size / 2, y: m.y - m.size / 2, width: m.size, height: m.size} : null;
};
const SAMPLE_FRAMES = [...new Set([
  0, DURATION - 1, ...CAPTIONS.map((c) => Math.floor((c.start + c.end) / 2)), ...Array.from({length: DURATION / 15}, (_, i) => i * 15 + 7),
])];

test('B-AC20: the field stays quiet: contrast, saturation, one accent, readable text', () => {
  const bg = hexRgb(BRAND.bg);
  const text = hexRgb(BRAND.text);
  assert.ok(SAMPLE_FRAMES.length >= 8);
  for (const f of SAMPLE_FRAMES) {
    const {blobs, waves} = backgroundField(f);
    for (const b of blobs) assert.ok(b.opacity <= 0.18, `blob opacity ${b.opacity}`);
    for (const w of waves) assert.ok(w.opacity <= 0.1, `wave opacity ${w.opacity}`);
    const visible = blobs.flatMap((b) => (ACCENTS.includes(b.color) && b.opacity > 0.02 ? [b.color] : []));
    assert.ok(new Set(visible).size <= 1, `frame ${f}: two accent hues`);
    if (markAt(f) || hookPromptShown(f)) {
      assert.ok(blobs.every((b) => b.color !== 'agent' || b.opacity <= 0.02), `frame ${f}: teal with the mark`);
    }
    const term = terminalRect(f);
    const caption = captionAt(f);
    const boxes = [caption?.box, ctaShown(f) ? END_CTA : null, hookPromptShown(f) ? HOOK_PROMPT : null];
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
      for (const box of boxes) if (inside(box, x, y)) assert.ok(contrast(text, rgb) >= 7, `frame ${f}: text contrast`);
    }
    assert.ok(tinted <= 0.4 * outside, `frame ${f}: accent covers ${tinted}/${outside}`);
  }
  // Failure path: a full-strength accent fails the contrast bound.
  assert.ok(contrast(hexRgb(BRAND.accent), bg) > 1.5);
  // R62: an opaque TUI.bg window with no backdrop effect.
  assert.deepEqual(WINDOW, {background: TUI.bg, opacity: 1});
  const cli = readFileSync(join(CLI_DIR, 'GallianiCli.tsx'), 'utf8');
  const frame = cli.slice(cli.indexOf('const TerminalFrame'), cli.indexOf('const ShellShot'));
  assert.match(frame, /background: WINDOW\.background/);
  assert.match(frame, /opacity: WINDOW\.opacity/);
});

const insideSafe = (r: Rect) => r.x >= SAFE.left && r.x + r.width <= SAFE.right && r.y >= SAFE.top && r.y + r.height <= SAFE.bottom;

test('B-AC21: framing: the terminal in the safe area, whole-row scroll, a centered end card', () => {
  for (let f = 0; f < DURATION; f++) {
    const r = terminalRect(f);
    if (r) {
      assert.ok(insideSafe(r), `frame ${f}: terminal ${JSON.stringify(r)} leaves the safe area`);
      const caption = captionAt(f);
      if (caption) assert.ok(r.y >= caption.box.y + caption.box.height, `frame ${f}: the terminal runs into the caption`);
    }
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
  assert.equal(END_MARK_Y, SEAM_MARK.y, 'the end card mark sits in the seam spot');
  // Failure path: the old approval framing (zoom 1.1 toward y 420) ran off the bottom.
  const z = 1.1;
  const old = {x: 960 + (TERMINAL.x - 960) * z, y: 420 + (TERMINAL.y - 420) * z, width: TERMINAL.width * z, height: TERMINAL.height * z};
  assert.equal(insideSafe(old), false);
  assert.deepEqual(wrap('aaaa bbbb cccc', 9), ['aaaa bbbb', 'cccc']);
});
