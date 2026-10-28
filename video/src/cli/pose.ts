// The GallianiCli robot's pose at each frame (spec 015 R76-R79, Decision 0038). Between gestures it only breathes
// and blinks; each gesture is one CliMotion with at most two legs (three for `wave`). Pure, so B-AC24 and B-AC25 test
// it without rendering; robot.tsx draws exactly this pose.
import {
  BLINK_FRAMES, POSES, ROBOT_BLINKS, ROBOT_BREATH, ROBOT_FRAME, ROBOT_PLACE, ROBOT_SCALE, TARGETS, beatAt,
} from './timeline.ts';
import type {Box, TargetId} from './timeline.ts';
import {GESTURES, ramp, robotShownAt} from './motion.ts';
import type {CliMotion} from './motion.ts';

export interface RobotPose {
  box: Box; // the robot's box at rest; `breath` moves it vertically
  breath: number; // px
  headTilt: number; // degrees
  headDip: number; // robot units down, the nod's cue
  lean: number; // degrees, the whole robot
  eyeX: number; // robot units
  eyeY: number;
  armLeft: number; // degrees about the shoulder pivot
  armRight: number;
  blink: number; // eye height factor, 1 open
}

const REST = {headTilt: 0, headDip: 0, lean: 0, eyeX: 0, eyeY: 0, armLeft: ROBOT_FRAME.restArm, armRight: -ROBOT_FRAME.restArm};
type Parts = typeof REST;

/** The only free-running motion: a sine of the frame, at most ROBOT_BREATH.px (R77). */
export const breathAt = (frame: number) => ROBOT_BREATH.px * Math.sin((2 * Math.PI * frame) / ROBOT_BREATH.period);

/** Robot.tsx's blink shape: the eyes close and open over BLINK_FRAMES. */
export function blinkAt(frame: number): number {
  for (const start of ROBOT_BLINKS) {
    const t = frame - start;
    if (t >= 0 && t < BLINK_FRAMES) return Math.abs(t - BLINK_FRAMES / 2) / (BLINK_FRAMES / 2) + 0.08;
  }
  return 1;
}

export const placeAt = (frame: number): Box => (beatAt(frame).shot.kind === 'end' ? ROBOT_PLACE.end : ROBOT_PLACE.act3);

/** A shoulder's pivot in canvas px, for a robot standing in `box` with no lean. */
export function shoulderAt(box: Box, side: 'left' | 'right'): {x: number; y: number} {
  const pivot = side === 'left' ? ROBOT_FRAME.pivotLeft : ROBOT_FRAME.pivotRight;
  return {x: box.x + (pivot.x - ROBOT_FRAME.viewBox.x) * ROBOT_SCALE, y: box.y + (pivot.y - ROBOT_FRAME.viewBox.y) * ROBOT_SCALE};
}

/** The arm rotation that aims the hanging arm (pointing down at 0°) from the shoulder at a box's centre. */
export function aimAngle(box: Box, target: Box, side: 'left' | 'right' = 'left'): number {
  const s = shoulderAt(box, side);
  const dx = target.x + target.width / 2 - s.x;
  const dy = target.y + target.height / 2 - s.y;
  return (Math.atan2(-dx, dy) * 180) / Math.PI; // SVG rotate(θ) turns (0, 1) into (-sin θ, cos θ)
}

/** An arm angle limited to armReach, so the head never covers the arm (R74). */
const reach = (degrees: number) => Math.max(-ROBOT_FRAME.armReach, Math.min(ROBOT_FRAME.armReach, degrees));

/** Each leg's eased progress at a frame: [out, back] or [raise, swing, lower]. */
function legProgress(m: CliMotion, frame: number): number[] {
  const legs = m.legs ?? [m.frames];
  let at = m.start;
  const marks = legs.map((frames) => {
    const begin = at;
    at += frames;
    return {begin, frames};
  });
  // The two-leg and three-leg poses move on their first and last legs and hold on the middle one, except `wave`.
  if (m.pose === 'wave') return marks.map((leg) => ramp(frame, leg.begin, leg.frames, m.easing));
  if (marks.length === 1) return [ramp(frame, marks[0].begin, marks[0].frames, m.easing)];
  const out = marks[0];
  const back = marks[marks.length - 1];
  return [ramp(frame, out.begin, out.frames, m.easing), ramp(frame, back.begin, back.frames, m.easing)];
}

/** The pose a gesture adds at a frame, given the parts it starts from. */
function gesturePose(m: CliMotion, frame: number, from: Parts, box: Box): Parts {
  const p = legProgress(m, frame);
  const there = (p[0] ?? 0) - (p[1] ?? 0); // 0 at rest, 1 held, back to 0
  const pose = m.pose ?? 'lean';
  const target = TARGETS[m.aim as TargetId];
  switch (pose) {
    case 'lean':
    case 'glance':
    case 'nod': {
      const shape = POSES[pose] as {headTilt: number; headDip?: number; lean?: number; eyeX?: number; eyeY?: number};
      return {
        ...from, headTilt: shape.headTilt * there, headDip: (shape.headDip ?? 0) * there, lean: (shape.lean ?? 0) * there,
        eyeX: (shape.eyeX ?? 0) * there, eyeY: (shape.eyeY ?? 0) * there,
      };
    }
    case 'point': {
      const aim = reach(aimAngle(box, target));
      return {...from, armLeft: from.armLeft + (aim - from.armLeft) * there};
    }
    case 'raise': {
      const aim = reach(aimAngle(box, target));
      return {...from, armLeft: from.armLeft + (aim - from.armLeft) * p[0]};
    }
    case 'lower':
      return {...from, armLeft: from.armLeft + (REST.armLeft - from.armLeft) * p[0]};
    case 'cheer':
      return {...from, armLeft: REST.armLeft + POSES.cheer.arm * there, armRight: REST.armRight - POSES.cheer.arm * there};
    case 'wave': {
      const [up, swing, down] = p;
      return {...from, armRight: REST.armRight - POSES.wave.arm * (up - down) + POSES.wave.swing * swing * (1 - down)};
    }
  }
}

/** The robot at an absolute frame, or null when it is off screen (R76-R78). */
export function robotPose(frame: number, gestures: readonly CliMotion[] = GESTURES): RobotPose | null {
  if (!robotShownAt(frame)) return null;
  const box = placeAt(frame);
  let parts: Parts = {...REST};
  // Gestures apply in order, so a `raise` holds its arm until the `lower` brings it down (R78).
  for (const m of gestures) {
    if (frame < m.start) break;
    parts = gesturePose(m, Math.min(frame, m.start + m.frames), parts, placeAt(m.start));
  }
  return {box, breath: breathAt(frame), blink: blinkAt(frame), ...parts};
}

