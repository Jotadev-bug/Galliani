// Sanity checks for the showcase timeline and source. Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {
  APPROVAL_STEP,
  CAMERA_KEYS,
  CHOSEN,
  COST,
  COST_ALL_OPUS,
  DURATION,
  FPS,
  MODELS,
  PROMPT,
  RESULT_LINES,
  ROBOT_KEYS,
  ROUTED_STEP,
  SAVED,
  STEPS,
  T,
  costAt,
  modelAt,
} from '../src/timeline.ts';
import {cameraAt} from '../src/camera.ts';

test('the showcase is short: 15-30 seconds', () => {
  const seconds = DURATION / FPS;
  assert.ok(seconds >= 15 && seconds <= 30, `${seconds}s`);
});

test('moments happen in order: type, send, dock, work, result, fade', () => {
  assert.ok(T.barIn[1] <= T.typeStart && T.typeStart < T.typeEnd && T.typeEnd < T.send);
  assert.ok(T.send <= T.dock[0] && T.dock[0] < T.cardIn[1] && T.cardIn[1] <= T.stepsIn);
  assert.ok(T.stepsIn + STEPS.length * 7 + 14 <= STEPS[0].start, 'all plan rows show before work starts');
  STEPS.forEach((step, i) => {
    assert.ok(step.start < step.end, step.title);
    if (i > 0) assert.equal(step.start, STEPS[i - 1].end, `${step.title} follows the previous step`);
  });
  const write = STEPS[APPROVAL_STEP];
  assert.ok(T.approvalOpen[0] >= write.start && T.approvalClose[1] <= write.end, 'approval happens during the write');
  const routed = STEPS[ROUTED_STEP];
  assert.ok(T.routeOpen[0] >= routed.start && T.routeClose[1] <= routed.end, 'routing happens during the coding step');
  assert.ok(T.routeOpen[1] <= T.routeScan[0] && T.routeScan[1] <= T.select && T.select < T.mascotIn[0]);
  assert.ok(T.mascotIn[1] < T.highFive && T.highFive < T.mascotOut[0] && T.mascotOut[1] <= T.routeClose[1], 'high five while the router is open');
  assert.ok(T.routeClose[1] <= T.approvalOpen[0], 'router and approval never overlap');
  assert.ok(T.approve > T.approvalOpen[1] && T.approve < T.approvalClose[0]);
  assert.ok(STEPS[STEPS.length - 1].end <= T.collapse[0] && T.collapse[1] <= T.statsIn[1] && T.statsIn[0] <= T.fileIn[0]);
  assert.ok(T.fileIn[0] + 14 + RESULT_LINES.length * 5 + 12 + 60 <= T.fadeOut[0], 'result holds on screen before the fade');
  assert.ok(T.fadeOut[0] < T.logoDraw[0] && T.logoDraw[1] <= T.logoBar[1]);
  assert.ok(T.robotIntoStar[1] <= T.robotVanish[1] && T.robotVanish[0] <= T.starPop[0], 'the star appears as the robot vanishes into it');
  assert.ok(T.starPop[1] <= T.wordmark[1] && T.wordmark[1] < T.end[0]);
  assert.equal(DURATION, T.end[1]);
});

test('cost and savings follow the model prices', () => {
  assert.equal(MODELS[CHOSEN].name, 'Sonnet 5.5');
  // USD per million tokens (input / output), as published for these models.
  assert.deepEqual(MODELS.map((m) => [m.name, ...m.price]), [
    ['Haiku 4.5', 1, 5],
    ['Sonnet 5.5', 2, 10],
    ['Opus 5.5', 4, 20],
  ]);
  assert.ok(Math.abs(COST - 0.059) < 1e-9, `cost ${COST}`);
  assert.ok(Math.abs(COST_ALL_OPUS - 0.14) < 1e-9, `all-Opus cost ${COST_ALL_OPUS}`);
  assert.ok(Math.abs(SAVED - (COST_ALL_OPUS - COST)) < 1e-12 && SAVED > 0);
  // The header's running cost starts at zero, never goes down, and ends at the total.
  let last = 0;
  for (let f = 0; f <= DURATION; f++) {
    const cost = costAt(f);
    assert.ok(cost >= last - 1e-12, `cost drops at ${f}`);
    last = cost;
  }
  assert.equal(costAt(0), 0);
  assert.ok(Math.abs(costAt(DURATION) - COST) < 1e-12);
  assert.equal(modelAt(T.select - 1), MODELS[0].name);
  assert.equal(modelAt(T.select), 'Sonnet 5.5');
});

test('the prompt fits in the chat bar on one line', () => {
  // About 0.52em per character at 31px in a 1100px bar with padding and the send button.
  assert.ok(PROMPT.length * 31 * 0.52 <= 1100 - 36 - 22 - 60 - 20, `${PROMPT.length} chars`);
});

test('the robot path is ordered and stays on screen', () => {
  ROBOT_KEYS.forEach((key, i) => {
    if (i > 0) assert.ok(key.f > ROBOT_KEYS[i - 1].f, `key ${i} is out of order`);
    if (key.f >= 34) assert.ok(key.x > 60 && key.x < 1860 && key.y > 60 && key.y < 1020, `key ${i} is off screen`);
  });
  assert.equal(ROBOT_KEYS[ROBOT_KEYS.length - 1].f, DURATION);
});

test('the camera moves smoothly and never shows past the scene edge', () => {
  CAMERA_KEYS.forEach((key, i) => {
    if (i > 0) assert.ok(key.f > CAMERA_KEYS[i - 1].f, `camera key ${i} is out of order`);
  });
  assert.equal(CAMERA_KEYS[CAMERA_KEYS.length - 1].f, DURATION);
  let previous = cameraAt(0);
  for (let f = 0; f <= DURATION; f++) {
    const cam = cameraAt(f);
    assert.ok(cam.scale >= 1 && cam.scale <= 1.5, `zoom ${cam.scale} at ${f}`);
    // Horizontally the scene always fills the frame.
    const halfWidth = 960 / cam.scale;
    assert.ok(cam.x - halfWidth >= -1 && cam.x + halfWidth <= 1921, `frame ${f} shows past the side`);
    // Impact zooms are fast but never a cut: under 10% zoom and 60px of pan per frame.
    assert.ok(Math.abs(cam.scale - previous.scale) < 0.1, `zoom jumps at ${f}`);
    assert.ok(Math.hypot(cam.x - previous.x, cam.y - previous.y) < 60, `pan jumps at ${f}`);
    if (f >= T.logoDraw[0]) assert.deepEqual(cam, {scale: 1, x: 960, y: 540}, `logo reveal is zoomed at ${f}`);
    previous = cam;
  }
});

test('source is deterministic, self-contained, and has no secrets', () => {
  const dir = fileURLToPath(new URL('../src', import.meta.url));
  for (const name of readdirSync(dir)) {
    const source = readFileSync(join(dir, name), 'utf8');
    assert.doesNotMatch(source, /https?:\/\//, `${name} references a URL`);
    assert.doesNotMatch(source, /<Audio|<Video/, `${name} loads media`);
    for (const [, file] of source.matchAll(/staticFile\('([^']+)'\)/g)) {
      assert.match(file, /^galliani-mark(-g|-star)?\.png$/, `${name} loads an unexpected asset`);
    }
    assert.doesNotMatch(source, /Math\.random|Date\.now|new Date\(/, `${name} is not deterministic`);
    assert.doesNotMatch(source, /sk-[A-Za-z0-9]{8,}|process\.env|api[_-]?key\s*[:=]/i, `${name} touches secrets`);
  }
});
