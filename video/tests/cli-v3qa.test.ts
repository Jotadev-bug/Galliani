// V3-QA independent checks for GallianiCli (spec 015 Part B, Decision 0038), added by qa-security on top of
// cli-qa.test.ts. Numbers are re-derived from the raw scene data and from Robot.tsx as text, sampled at every frame
// where cheap. The three V3-QA findings (the arm under the head, route-next, the at-file pause) are real tests since
// V3b, under the orchestrator's rulings (R46, R52, R78 and B-AC17 amended 2026-10-28). Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {accentAt, backgroundField, sampleField} from '../src/cli/background.ts';
import {DRAG_CHORD, cursorAt, dragPath, heroBoxes, heroIconAt} from '../src/cli/desktop.ts';
import {BANNER_ROWS, CONTENT, entryRows, sceneState, terminalRect, transcriptLayout} from '../src/cli/layout.ts';
import {movingAt} from '../src/cli/motion.ts';
import {BRAND} from '../src/cli/palette.ts';
import {robotPose} from '../src/cli/pose.ts';
import {
  AT_PROMPT, BEATS, POSES, CAPTIONS, DESKTOP, DURATION, FILE_ROWS_ALL, ROBOT_FRAME, ROBOT_PLACE, ROBOT_SCALE, ROBOT_SHAPES, ROUTE_CODING,
  ROUTE_TEXT, SAFE, SHELL_CARET, TARGETS, TERMINAL, captionAt, charTimes, screenAt, typedText,
} from '../src/cli/timeline.ts';
import type {Box, CliBeat} from '../src/cli/timeline.ts';

const read = (p: string) => readFileSync(fileURLToPath(new URL(p, import.meta.url)), 'utf8');
const beat = (id: string) => BEATS.find((b) => b.id === id) as CliBeat;
const inside = (b: Box, r: Box) => b.x >= r.x && b.y >= r.y && b.x + b.width <= r.x + r.width && b.y + b.height <= r.y + r.height;
const SAFE_BOX: Box = {x: SAFE.left, y: SAFE.top, width: SAFE.right - SAFE.left, height: SAFE.bottom - SAFE.top};

const hex = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const lum = (rgb: readonly number[]) => {
  const [r, g, b] = rgb.map((v) => (v / 255 <= 0.03928 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: readonly number[], b: readonly number[]) => {
  const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (hi + 0.05) / (lo + 0.05);
};
const minContrast = (color: string, frame: number, box: Box, step = 12) => {
  let worst = Infinity;
  for (let x = box.x; x <= box.x + box.width; x += step) {
    for (let y = box.y; y <= box.y + box.height; y += step) worst = Math.min(worst, contrast(hex(color), sampleField(frame, x, y)));
  }
  return worst;
};

// ---------------------------------------------------------------- drag and absorb (R70, R71, B-AC22)

test('V3-QA: the drag arc apex is at most 160 px off the chord, measured by sampling the path', () => {
  const {from, to} = DRAG_CHORD;
  const length = Math.hypot(to.x - from.x, to.y - from.y);
  let apex = 0;
  for (let i = 0; i <= 2000; i++) {
    const p = dragPath(i / 2000);
    apex = Math.max(apex, Math.abs((to.y - from.y) * p.x - (to.x - from.x) * p.y + to.x * from.y - to.y * from.x) / length);
  }
  assert.ok(apex > 0 && apex <= 160, `apex ${apex.toFixed(1)} px`);
  assert.deepEqual(dragPath(0), from);
  assert.deepEqual(dragPath(1), to);
});

test('V3-QA: every drag frame keeps the icon and its label in the safe area, unscaled, and it lands in the window content', () => {
  const drag = beat('desk-drag');
  const drop = beat('desk-drop');
  const w = DESKTOP.window;
  const content: Box = {x: w.x, y: w.y + TERMINAL.border + TERMINAL.titleBar, width: w.width, height: w.height - TERMINAL.border - TERMINAL.titleBar};
  let still = 0;
  let last: {x: number; y: number} | null = null;
  for (let f = drag.start; f < drop.start; f++) {
    const hero = heroIconAt(f);
    assert.ok(hero, `frame ${f}: no hero icon`);
    assert.equal(hero.scale, 1, `frame ${f}: scaled`);
    assert.equal(hero.rotation, 0, `frame ${f}: rotated`);
    assert.equal(hero.home, false, `frame ${f}: home slot not empty`);
    assert.ok(inside(heroBoxes(hero).all, SAFE_BOX), `frame ${f}: icon outside the safe area`);
    if (last && last.x === hero.center.x && last.y === hero.center.y) still++;
    else still = 0;
    last = hero.center;
  }
  assert.ok(last && last.x > content.x && last.x < content.x + content.width && last.y > content.y && last.y < content.y + content.height, 'drag ends outside the window content');
  assert.ok(still + 1 >= 8, `icon holds ${still + 1} frames before the drop`);
});

test('V3-QA: the absorb ends at the caret, at most 0.15 scale and opacity 0, and the icon is gone afterwards', () => {
  const drop = beat('desk-drop');
  let lastFrame = drop.start;
  while (heroIconAt(lastFrame + 1)) lastFrame++;
  const absorbFrames = lastFrame - drop.start + 1;
  assert.ok(absorbFrames >= 6 && absorbFrames <= 10, `absorb lasts ${absorbFrames} frames`);
  const end = heroIconAt(lastFrame);
  assert.ok(end);
  assert.ok(end.scale <= 0.15, `scale ${end.scale}`);
  assert.equal(end.opacity, 0);
  assert.ok(Math.hypot(end.center.x - SHELL_CARET.x, end.center.y - SHELL_CARET.y) <= 4, 'center not on the caret');
  // Opacity ramps over at most 4 frames.
  let fading = 0;
  for (let f = drop.start; f <= lastFrame; f++) if ((heroIconAt(f)?.opacity ?? 1) < 1) fading++;
  assert.ok(fading <= 4, `opacity ramps over ${fading} frames`);
  for (let f = lastFrame + 1; f < beat('end-seam').start; f++) assert.equal(heroIconAt(f), null, `frame ${f}: icon back`);
  // The cursor stays still from the release to the cut.
  const at = cursorAt(drop.start);
  for (let f = drop.start; f < drop.start + drop.duration; f++) assert.deepEqual(cursorAt(f), at, `frame ${f}: cursor moved`);
  assert.equal(cursorAt(drop.start + drop.duration), null);
});

// ---------------------------------------------------------------- expand and seam (R57, R73, B-AC18, B-AC23)

test('V3-QA: the expand moves each window edge monotonically from the desktop rectangle to the Act 3 frame', () => {
  const b = beat('launch-expand');
  const edges = (r: Box) => [r.x, r.y, r.x + r.width, r.y + r.height];
  const start = edges(DESKTOP.window);
  const end = edges({x: TERMINAL.x, y: TERMINAL.y, width: TERMINAL.width, height: TERMINAL.height});
  let previous = start;
  let moving = 0;
  for (let f = b.start; f < b.start + b.duration; f++) {
    const rect = terminalRect(f);
    assert.ok(rect && inside(rect, SAFE_BOX), `frame ${f}: outside the safe area`);
    const now = edges(rect);
    now.forEach((v, i) => assert.ok(Math.sign(end[i] - start[i]) * (v - previous[i]) >= -1e-9, `frame ${f}: edge ${i} went back`));
    if (now.some((v, i) => v !== previous[i])) moving++;
    previous = now;
  }
  assert.deepEqual(previous, end);
  assert.ok(moving >= 10 && moving <= 15, `expand changes the rectangle on ${moving} frames`);
});

test('V3-QA: the last 8 frames hold the seam state of frame 0, and the field and caret blink are continuous', () => {
  const first = JSON.stringify(sceneState(0));
  for (let f = DURATION - 8; f < DURATION; f++) assert.equal(JSON.stringify(sceneState(f)), first, `frame ${f}`);
  assert.deepEqual(backgroundField(DURATION), backgroundField(0));
  assert.equal(DURATION % 30, 0, 'the 15-frame caret blink needs a multiple of 30');
  // Frame 0 is not empty: icons, hero, window and the hook caption.
  const s = sceneState(0);
  assert.ok(s.icons?.length === 3 && s.hero?.home && s.window && captionAt(0)?.start === 0);
});

// ---------------------------------------------------------------- contrast and field (R61, B-AC20)

test('V3-QA: captions keep 7:1 and the generic labels 4.5:1 over the field at every frame', () => {
  for (let f = 0; f < DURATION; f++) {
    const c = captionAt(f);
    assert.ok(c, `frame ${f}: no caption`);
    assert.ok(minContrast(BRAND.text, f, c.box, 24) >= 7, `frame ${f}: caption under 7:1`);
    const hero = heroIconAt(f);
    const label = hero && heroBoxes(hero).label;
    if (label) assert.ok(minContrast(BRAND.text, f, label, 8) >= 7, `frame ${f}: hero label under 7:1`);
    if (sceneState(f).icons) for (const icon of DESKTOP.icons) assert.ok(minContrast(BRAND.muted, f, icon.labelBox, 8) >= 4.5, `frame ${f}: ${icon.label} under 4.5:1`);
  }
});

test('V3-QA: the field stays within 1.5:1 of BRAND.bg and accent cover stays at most 40%, every 3rd frame on 48 x 27', () => {
  for (let f = 0; f <= DURATION; f += 3) {
    const rect = terminalRect(f % DURATION);
    let outside = 0;
    let covered = 0;
    for (let i = 0; i < 48; i++) {
      for (let j = 0; j < 27; j++) {
        const x = (i + 0.5) * 40;
        const y = (j + 0.5) * 40;
        assert.ok(contrast(hex(BRAND.bg), sampleField(f, x, y)) <= 1.5, `frame ${f} (${x}, ${y})`);
        if (rect && x >= rect.x && x <= rect.x + rect.width && y >= rect.y && y <= rect.y + rect.height) continue;
        outside++;
        const a = accentAt(f, x, y);
        if (a.accent > 0.05 || a.agent > 0.05) covered++;
      }
    }
    assert.ok(covered / outside <= 0.4, `frame ${f}: accent covers ${(100 * covered / outside).toFixed(1)}%`);
  }
});

// ---------------------------------------------------------------- the robot (R74-R79, B-AC24, B-AC25)

test('V3-QA: robot.tsx draws every ROBOT_SHAPES entry once, and each equals the Robot.tsx literals by tag and fill role', () => {
  const showcase = read('../src/Robot.tsx');
  const robot = read('../src/cli/robot.tsx');
  // Robot.tsx shapes as literal attribute maps, keyed by tag, in drawing order.
  const literal = [...showcase.matchAll(/<(ellipse|rect|circle|line)\s([^>]*?)\/>/g)].map((m) => ({
    tag: m[1],
    attrs: Object.fromEntries([...m[2].matchAll(/\b(x|y|width|height|rx|ry|cx|cy|r|x1|y1|x2|y2)=\{(-?[\d.]+)\}/g)].map((a) => [a[1], Number(a[2])])),
  }));
  const drawn = [...robot.matchAll(/<(ellipse|rect|circle|line) \{\.\.\.S\.(\w+)\}/g)].map((m) => ({tag: m[1], name: m[2] as keyof typeof ROBOT_SHAPES}));
  assert.deepEqual(drawn.map((d) => d.name).sort(), Object.keys(ROBOT_SHAPES).sort(), 'every shape drawn exactly once');
  assert.deepEqual(drawn.map((d) => d.tag), literal.map((l) => l.tag), 'same tags in the same order');
  drawn.forEach((d, i) => assert.deepEqual(ROBOT_SHAPES[d.name], literal[i].attrs, `${d.name} drifted`));
  const code = robot.replace(/\/\/.*$/gm, ''); // the header comment names what was left out
  assert.doesNotMatch(code, /filter|drop-shadow|wiggle|Math\.(sin|cos|random)|Date|scale\(/);
});

test('V3-QA: the robot shows from the content cut to the end of end-card, outside the terminal and captions, moving only at cuts', () => {
  const cut = beat('launch-expand').start + 15;
  const endCard = beat('end-card');
  let box: Box | null = null;
  for (let f = 0; f < DURATION; f++) {
    const pose = robotPose(f);
    const shown = f >= cut && f < endCard.start + endCard.duration;
    assert.equal(!!pose, shown, `frame ${f}`);
    if (!pose) continue;
    assert.ok(inside(pose.box, SAFE_BOX), `frame ${f}: outside the safe area`);
    assert.ok(Math.abs(pose.breath) <= 3, `frame ${f}: breath`);
    const rect = terminalRect(f);
    if (rect) assert.ok(pose.box.x >= rect.x + rect.width + 16 || pose.box.y >= rect.y + rect.height + 16, `frame ${f}: within 16 px of the terminal`);
    for (const c of CAPTIONS) if (f >= c.start && f < c.end) assert.ok(pose.box.y >= c.box.y + c.box.height || pose.box.x >= c.box.x + c.box.width, `frame ${f}: under a caption`);
    if (box && JSON.stringify(box) !== JSON.stringify(pose.box)) assert.ok(BEATS.some((b) => b.start === f), `frame ${f}: moved mid-beat`);
    box = pose.box;
    assert.ok(Math.abs(pose.headTilt) <= 10 && Math.abs(pose.lean) <= 8 && Math.abs(pose.eyeX) <= 6 && Math.abs(pose.eyeY) <= 4, `frame ${f}: pose out of bounds`);
  }
  assert.deepEqual(Object.keys(ROBOT_PLACE).sort(), ['act3', 'end']);
});

/** The arm's free end in robot units, for a rotation about its shoulder pivot. */
function armTip(side: 'left' | 'right', degrees: number): {x: number; y: number} {
  const shape = side === 'left' ? ROBOT_SHAPES.armLeft : ROBOT_SHAPES.armRight;
  const pivot = side === 'left' ? ROBOT_FRAME.pivotLeft : ROBOT_FRAME.pivotRight;
  const end = {x: shape.x + shape.width / 2 - pivot.x, y: shape.y + shape.height - pivot.y};
  const t = (degrees * Math.PI) / 180;
  return {x: pivot.x + end.x * Math.cos(t) - end.y * Math.sin(t), y: pivot.y + end.x * Math.sin(t) + end.y * Math.cos(t)};
}
const underHead = (p: {x: number; y: number}) => {
  const h = ROBOT_SHAPES.head;
  return p.x > h.x && p.x < h.x + h.width && p.y > h.y && p.y < h.y + h.height;
};

/** True when a point in robot units lies inside a rounded rectangle. */
function inRounded(b: {x: number; y: number; width: number; height: number; rx: number}, p: {x: number; y: number}): boolean {
  if (p.x < b.x || p.x > b.x + b.width || p.y < b.y || p.y > b.y + b.height) return false;
  const cx = Math.min(Math.max(p.x, b.x + b.rx), b.x + b.width - b.rx);
  const cy = Math.min(Math.max(p.y, b.y + b.rx), b.y + b.height - b.rx);
  return Math.hypot(p.x - cx, p.y - cy) <= b.rx;
}
const turn = (p: {x: number; y: number}, about: {x: number; y: number}, degrees: number) => {
  const t = (degrees * Math.PI) / 180;
  const dx = p.x - about.x;
  const dy = p.y - about.y;
  return {x: about.x + dx * Math.cos(t) - dy * Math.sin(t), y: about.y + dx * Math.sin(t) + dy * Math.cos(t)};
};
/** Points of an arm (a 0.5-unit grid over its rounded shape) that the head, drawn above it, covers in a pose. */
function armUnderHead(side: 'left' | 'right', pose: {armLeft: number; armRight: number; headTilt: number; headDip: number}): number {
  const shape = side === 'left' ? ROBOT_SHAPES.armLeft : ROBOT_SHAPES.armRight;
  const pivot = side === 'left' ? ROBOT_FRAME.pivotLeft : ROBOT_FRAME.pivotRight;
  const angle = side === 'left' ? pose.armLeft : pose.armRight;
  let covered = 0;
  for (let x = shape.x; x <= shape.x + shape.width; x += 0.5) {
    for (let y = shape.y; y <= shape.y + shape.height; y += 0.5) {
      if (!inRounded(shape, {x, y})) continue;
      // Into the head group's frame: undo its dip, then its tilt about the origin (robot.tsx).
      const p = turn(turn({x, y}, pivot, angle), {x: 0, y: 0}, -pose.headTilt);
      if (inRounded(ROBOT_SHAPES.head, {x: p.x, y: p.y - pose.headDip})) covered++;
    }
  }
  return covered;
}

test('V3-QA: the raised arm of `point` and `cheer` ends clear of the head, which is drawn above it (R74)', () => {
  for (const id of ['plan-steps', 'verified-done']) {
    const b = beat(id);
    const f = (b.gesture?.at ?? 0) + b.start + 12; // inside the hold leg
    const pose = robotPose(f);
    assert.ok(pose);
    assert.ok(pose.armLeft > 90, `${id} frame ${f}: the arm is not raised (${pose.armLeft.toFixed(0)} deg)`);
    assert.ok(!underHead(armTip('left', pose.armLeft)), `${id} frame ${f}: the left arm tip (${pose.armLeft.toFixed(0)} deg) is under the head`);
  }
  // No part of either arm is covered by the head at any frame, in any pose (R74: Robot.tsx's layer order).
  for (let f = 0; f < DURATION; f++) {
    const pose = robotPose(f);
    if (!pose) continue;
    for (const side of ['left', 'right'] as const) assert.equal(armUnderHead(side, pose), 0, `frame ${f}: the ${side} arm is under the head`);
  }
  // The layer order is Robot.tsx's: both arms before the head group.
  const robot = read('../src/cli/robot.tsx');
  assert.ok(robot.indexOf('S.armRight') < robot.indexOf('S.head}'), 'the arms are drawn before the head');
  // Failure path: the pre-V3b 152 deg cheer puts the arm under the head.
  assert.ok(armUnderHead('left', {armLeft: 152, armRight: -12, headTilt: 0, headDip: 0}) > 0, 'fixture: a 152 deg arm is covered');
  assert.ok(TARGETS.plan && ROBOT_SCALE > 0);
});

test('V3-QA: the nod has a downward cue: the head dips and comes back, within the pose bounds (R78)', () => {
  const nod = beat('slash-popup');
  const at = nod.start + (nod.gesture?.at ?? 0);
  const [out, hold, back] = POSES.nod.legs;
  const held = robotPose(at + out);
  assert.ok(held && held.headDip > 0 && held.headDip <= 4, `head dip ${held?.headDip}`);
  assert.ok(held.headTilt < 0 && held.eyeY >= 0, 'the head tilts and the eyes look down, not up');
  // The beat's still (its middle frame) shows the nod down.
  assert.ok((robotPose(nod.start + Math.floor(nod.duration / 2))?.headDip ?? 0) > 1, 'the slash-popup still misses the nod');
  const end = at + out + hold + back;
  assert.equal(robotPose(end)?.headDip, 0, 'the head comes back');
  for (let f = 0; f < DURATION; f++) {
    const p = robotPose(f);
    if (p && (f < at || f >= end)) assert.equal(p.headDip, 0, `frame ${f}: the head dips outside the nod`);
  }
});

// ---------------------------------------------------------------- storyboard content (R46, R52)

/** The canvas y of each route line in a beat's last screen, with its id. */
function routeLines(x: CliBeat): {id: string; y: number}[] {
  if (x.shot.kind !== 'terminal') return [];
  const screen = screenAt(x.shot.keys, x.duration - 1).key.screen;
  const layout = transcriptLayout(screen);
  const out: {id: string; y: number}[] = [];
  let row = BANNER_ROWS;
  for (const e of screen.entries) {
    if (e.kind === 'route') out.push({id: e.text.split(' ')[1].replace(/:$/, ''), y: TERMINAL.y + CONTENT.top + (row - layout.offsetRows) * TERMINAL.row});
    row += entryRows(e).length;
  }
  return out;
}

test("V3-QA: route-next adds no route id; the glance targets step 2's route line; verified-done shows step 4's (R46, R78)", () => {
  const next = beat('route-next');
  // Before step 4 the only route id is step 2's.
  for (const b of BEATS.slice(0, BEATS.indexOf(beat('verified-done')))) {
    for (const r of routeLines(b)) assert.equal(r.id, ROUTE_CODING, `${b.id}: a second route id before step 4`);
    if (b.shot.kind === 'terminal') for (const k of b.shot.keys) assert.ok(k.screen.status.route === null || k.screen.status.route === ROUTE_CODING, `${b.id}: status route`);
  }
  assert.deepEqual(routeLines(next).map((r) => r.id), [ROUTE_CODING], "route-next shows step 2's route line only");
  assert.equal(routeLines(next).length, routeLines(beat('route-first')).length, 'route-next adds a route line');
  if (next.shot.kind === 'terminal') {
    const s = screenAt(next.shot.keys, 0).key.screen;
    assert.deepEqual(s.steps?.slice(0, 3), ['verified', 'verified', 'running'], 'step 2 done, step 3 next');
  }
  // The glance target is step 2's route line on screen in route-next.
  assert.equal(next.gesture?.pose, 'glance');
  const line = routeLines(next)[0];
  const target = TARGETS[next.gesture?.target as keyof typeof TARGETS];
  const mid = target.y + target.height / 2;
  assert.ok(mid >= line.y && mid <= line.y + TERMINAL.row, `glance aims at y ${mid}, the route line is ${line.y}-${line.y + TERMINAL.row}`);
  // verified-done: step 4's route line with the captured id, the only other id.
  const done = routeLines(beat('verified-done'));
  assert.deepEqual(done.map((r) => r.id), [ROUTE_CODING, ROUTE_TEXT]);
  assert.equal(ROUTE_TEXT, 'google/gemini-3.1-flash-lite');
  const all = new Set(BEATS.flatMap((b) => routeLines(b).map((r) => r.id)));
  assert.deepEqual([...all].sort(), [ROUTE_CODING, ROUTE_TEXT].sort(), 'no third route id');
});

/** The local frame each character of a beat's prompt first shows, read from the rendered screens. */
function shownTimes(b: CliBeat): number[] {
  if (b.shot.kind !== 'terminal') return [];
  const times: number[] = [];
  let shown = 0;
  for (let l = 0; l < b.duration; l++) {
    const prompt = screenAt(b.shot.keys, l).key.screen.prompt;
    if (!prompt) continue;
    const n = typedText(prompt.typing, l).length;
    if (prompt.typing.frames === 0 && n > shown) break; // a completion or a cut sets the text at once: not typing
    for (let i = shown; i < n; i++) times.push(l);
    shown = Math.max(shown, n);
  }
  return times;
}

/** Typing pauses: an interval that grows by more than one frame of rounding over the one before it (R52). */
function typingPauses(times: readonly number[]): {after: number; frames: number}[] {
  const gaps = times.slice(1).map((t, i) => t - times[i]);
  return gaps.flatMap((g, i) => (i > 0 && g > gaps[i - 1] + 1 ? [{after: i, frames: g}] : []));
}

/** The B-AC17 pause rule: only `at-file` may pause, once, for at most 30 frames. */
function pauseViolations(id: string, times: readonly number[]): string[] {
  const pauses = typingPauses(times);
  const out: string[] = [];
  if (pauses.length && id !== 'at-file') out.push(`${id}: typing pauses`);
  if (pauses.length > 1) out.push(`${id}: ${pauses.length} pauses`);
  for (const p of pauses) if (p.frames > 30) out.push(`${id}: a ${p.frames}-frame pause`);
  return out;
}

test('B-AC17 (amended): typing pauses only once in at-file, at most 30 frames, while the full popup holds and nothing else moves', () => {
  for (const b of BEATS) {
    if (b.shot.kind === 'shell') assert.deepEqual(typingPauses(charTimes(b.shot.typing).map(Math.ceil)), [], `${b.id} pauses`);
    if (b.shot.kind === 'terminal') assert.deepEqual(pauseViolations(b.id, shownTimes(b)), [], b.id);
  }
  const b = beat('at-file');
  const times = shownTimes(b);
  assert.equal(times.length, AT_PROMPT.length, 'every typed character of `@sig` is seen');
  const pauses = typingPauses(times);
  assert.equal(pauses.length, 1, 'at-file pauses once');
  const [{after, frames}] = pauses;
  assert.equal(AT_PROMPT[after], '@', 'the pause follows the `@`');
  assert.ok(frames <= 30, `${frames}-frame pause`);
  // During the pause the full popup shows and nothing in the foreground moves (the robot idles).
  if (b.shot.kind !== 'terminal') return;
  const keys = b.shot.keys;
  for (let l = times[after] + 1; l < times[after + 1]; l++) {
    assert.deepEqual(screenAt(keys, l).key.screen.popup?.rows, FILE_ROWS_ALL, `local ${l}: the popup is not fully shown`);
    assert.deepEqual(movingAt(b.start + l), [], `local ${l}: something moves in the pause`);
  }
  assert.equal(b.gesture, undefined, 'no gesture in at-file');
  // Either side of the pause: intervals never grow, and the last third is at least 1.5x faster (continuous schedules).
  for (const k of keys) {
    const t = k.screen.prompt?.typing;
    if (!t || t.frames === 0) continue;
    const typed = charTimes(t).slice(t.kept ?? 0);
    const gaps = typed.slice(1).map((v, i) => v - typed[i]);
    for (let i = 1; i < gaps.length; i++) assert.ok(gaps[i] <= gaps[i - 1] + 1e-9, `${t.text}: interval grows`);
    const third = Math.max(1, Math.floor(gaps.length / 3));
    const mean = (xs: number[]) => xs.reduce((s, x) => s + x, 0) / xs.length;
    assert.ok(mean(gaps.slice(0, third)) >= 1.5 * mean(gaps.slice(-third)) - 1e-9, `${t.text}: last third not 1.5x faster`);
  }
  // Failure paths: a pause in another beat, a second pause in at-file, and a pause over 30 frames.
  const paused = [0, 3, 5, 6, 26, 27, 28];
  assert.ok(pauseViolations('goal-type', paused).some((v) => v.endsWith('typing pauses')), 'fixture: a pause in goal-type passes');
  assert.ok(pauseViolations('at-file', [0, 3, 5, 6, 26, 27, 47, 48]).some((v) => v.endsWith('2 pauses')), 'fixture: a second pause passes');
  assert.ok(pauseViolations('at-file', [0, 3, 5, 6, 38, 39, 40]).some((v) => v.endsWith('32-frame pause')), 'fixture: a 32-frame pause passes');
  assert.deepEqual(pauseViolations('at-file', paused), [], 'fixture: one 20-frame pause in at-file is allowed');
});

// ---------------------------------------------------------------- the cursor (R37, R69)

test('V3-QA: the cursor is continuous across the desk-hover/desk-drag cut and rides the lifted tile from arrival', () => {
  const hover = beat('desk-hover');
  const drag = beat('desk-drag');
  const before = cursorAt(drag.start - 1);
  const after = cursorAt(drag.start);
  assert.ok(before && after);
  const jump = Math.hypot(after.x - before.x, after.y - before.y);
  assert.ok(jump < 1e-9, `the cursor jumps ${jump.toFixed(2)} px at the cut`);
  // From the hover lift on, the cursor keeps the grab offset to the tile's centre.
  for (let f = hover.start; f < drag.start + drag.duration; f++) {
    const hero = heroIconAt(f);
    const c = cursorAt(f);
    if (!hero?.hovered || !c) continue;
    assert.ok(Math.abs(c.x - hero.center.x - DESKTOP.grab.x) < 1e-9 && Math.abs(c.y - hero.center.y - DESKTOP.grab.y) < 1e-9, `frame ${f}: the cursor slips off the grab point`);
  }
  // Outside the cursor and drag motions the cursor does not move.
  for (let f = hover.start + 1; f < beat('desk-drop').start; f++) {
    const a = cursorAt(f - 1);
    const c = cursorAt(f);
    if (!a || !c || movingAt(f).length > 0 || movingAt(f - 1).length > 0) continue;
    const step = Math.hypot(c.x - a.x, c.y - a.y);
    assert.ok(step < 1e-9, `frame ${f}: the cursor moves ${step.toFixed(2)} px with no motion`);
  }
});

test('V3-QA: each gesture beat\'s still (its middle frame) shows the gesture, except `lower`, which shows the arm down', () => {
  for (const b of BEATS) {
    if (!b.gesture) continue;
    const p = robotPose(b.start + Math.floor(b.duration / 2));
    assert.ok(p, `${b.id}: no robot on the still`);
    const off = Math.max(Math.abs(p.headTilt), Math.abs(p.lean), Math.abs(p.armLeft - ROBOT_FRAME.restArm), Math.abs(p.armRight + ROBOT_FRAME.restArm));
    if (b.gesture.pose === 'lower') assert.equal(p.armLeft, ROBOT_FRAME.restArm, `${b.id}: the arm is not down`);
    else assert.ok(off >= 4, `${b.id}: the still shows the robot at rest (${b.gesture.pose} off by ${off.toFixed(1)})`);
  }
});
