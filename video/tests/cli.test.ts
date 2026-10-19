// Checks for the GallianiCli composition (spec 015 Part B, B-AC2..B-AC11). Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {BRAND, TUI} from '../src/cli/palette.ts';
import {
  AT_DONE, AT_PROMPT, BEATS, CAPTIONS, CAPTION_SLIDE, CLI_RENDER, DURATION, FILE_ROWS_ALL, FILE_ROWS_SIG, FPS, GOAL,
  HEIGHT, MARK_SNAP, PLAN_STEPS, ROUTE_CODING, ROUTE_TEXT, SLASH_ROWS, TERM, TERMINAL, WIDTH, WORD_FRAMES, planSummary,
  popupLines, statusText, stepLine, typedText, workingText,
} from '../src/cli/timeline.ts';
import type {CliBeat, Typing} from '../src/cli/timeline.ts';

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

test('B-AC11: motion bounds and hard cuts', () => {
  for (const b of BEATS) {
    if (b.push) {
      const {at, frames, from, to} = b.push;
      assert.ok(frames > 0 && frames <= 15, `${b.id} push lasts ${frames}`);
      assert.ok(from >= 1 && to >= 1 && from <= 1.15 && to <= 1.15, `${b.id} zoom`);
      assert.ok(at >= 0 && at + frames <= b.duration, `${b.id} push leaves the beat`);
      // R42: zoomed in, the terminal's top edge stays below the caption band.
      const caption = CAPTIONS.find((c) => c.segment === b.segment);
      const top = b.push.origin.y + (TERMINAL.y - b.push.origin.y) * Math.max(from, to);
      if (caption && caption.box.y < TERMINAL.y) assert.ok(top >= caption.box.y + caption.box.height, `${b.id} push runs into the caption`);
    }
    if (b.shot.kind === 'terminal') {
      const {keys} = b.shot;
      keys.forEach((k, i) => {
        assert.ok(k.at >= 0 && k.at < b.duration, `${b.id} key ${i}`);
        if (i > 0) assert.ok(k.at > keys[i - 1].at, `${b.id} keys out of order`);
      });
    }
    assert.ok(!('transition' in b), `${b.id} has a transition`);
  }
  for (const c of CAPTIONS) assert.ok(c.enterFrames <= 8, `${c.text} enters in ${c.enterFrames}`);
  assert.ok(WORD_FRAMES <= 4 && CAPTION_SLIDE <= 32 && MARK_SNAP.frames <= 8 && MARK_SNAP.fromScale >= 0.92);
  for (const {source, name} of cliSources()) {
    assert.doesNotMatch(source, /TransitionSeries|@remotion\/transitions|crossfade|dissolve/i, `${name} uses a transition`);
  }
});

test('typing finishes inside its beat', () => {
  const check = (beat: CliBeat, typing: Typing) =>
    assert.equal(typedText(typing, beat.duration - 1), typing.text, `${beat.id} typing is cut off`);
  for (const b of BEATS) {
    if (b.shot.kind === 'shell') check(b, b.shot.typing);
    if (b.shot.kind === 'terminal') for (const k of b.shot.keys) if (k.screen.prompt) check(b, k.screen.prompt.typing);
  }
});
