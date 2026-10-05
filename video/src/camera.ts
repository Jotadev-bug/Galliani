// Camera path: a monotone cubic through CAMERA_KEYS, so motion never stops hard at a key
// and never overshoots past one. Pure; shared by the scene and the tests.
import {CAMERA_KEYS, type CameraKey} from './timeline.ts';

type Field = 'scale' | 'x' | 'y';
const FIELDS: Field[] = ['scale', 'x', 'y'];

/** Fritsch-Carlson tangents: zero at turning points and at the ends. */
function tangents(keys: CameraKey[], field: Field): number[] {
  const n = keys.length;
  const slope = (i: number) => (keys[i + 1][field] - keys[i][field]) / (keys[i + 1].f - keys[i].f);
  return keys.map((_, i) => {
    if (i === 0 || i === n - 1) return 0;
    const a = slope(i - 1);
    const b = slope(i);
    if (a * b <= 0) return 0;
    const wa = 2 * (keys[i + 1].f - keys[i].f) + (keys[i].f - keys[i - 1].f);
    const wb = (keys[i + 1].f - keys[i].f) + 2 * (keys[i].f - keys[i - 1].f);
    return (wa + wb) / (wa / a + wb / b);
  });
}

const TANGENTS = Object.fromEntries(FIELDS.map((field) => [field, tangents(CAMERA_KEYS, field)])) as Record<Field, number[]>;

export function cameraAt(frame: number): {scale: number; x: number; y: number} {
  const keys = CAMERA_KEYS;
  const pose = ({scale, x, y}: CameraKey) => ({scale, x, y});
  if (frame <= keys[0].f) return pose(keys[0]);
  if (frame >= keys[keys.length - 1].f) return pose(keys[keys.length - 1]);
  const i = keys.findIndex((key, k) => frame >= key.f && frame < keys[k + 1].f);
  const a = keys[i];
  const b = keys[i + 1];
  // A hold stays exactly still (no floating-point drift).
  if (a.scale === b.scale && a.x === b.x && a.y === b.y) return pose(a);
  const h = b.f - a.f;
  const t = (frame - a.f) / h;
  const t2 = t * t;
  const t3 = t2 * t;
  const value = (field: Field) =>
    (2 * t3 - 3 * t2 + 1) * a[field] +
    (t3 - 2 * t2 + t) * h * TANGENTS[field][i] +
    (-2 * t3 + 3 * t2) * b[field] +
    (t3 - t2) * h * TANGENTS[field][i + 1];
  return {scale: value('scale'), x: value('x'), y: value('y')};
}
