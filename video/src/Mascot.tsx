// A small pixel-style Claude mascot (our own SVG drawing, in Claude's terracotta).
// It pops out of the chosen model chip, raises a hand for the robot's high five, and ducks back.
import React from 'react';
import {Easing, interpolate} from 'remotion';
import {HIGH_FIVE_ARM, MASCOT, T} from './timeline.ts';

const ORANGE = '#D97757';
const SHADE = '#B85F43';
const INK = '#141416';
const U = 9; // one "pixel" of the mascot, in scene px

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export const Mascot: React.FC<{frame: number}> = ({frame}) => {
  const pop = interpolate(frame, T.mascotIn, [0, 1], {...clamp, easing: Easing.out(Easing.back(2))});
  const duck = interpolate(frame, T.mascotOut, [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const shown = pop * (1 - duck);
  if (shown <= 0.001) return null;
  // The hand: rises before the high five and comes back down after.
  const armUp =
    interpolate(frame, [HIGH_FIVE_ARM[0], HIGH_FIVE_ARM[0] + 8], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)}) *
    (1 - interpolate(frame, [HIGH_FIVE_ARM[1], HIGH_FIVE_ARM[1] + 8], [0, 1], clamp));
  const bump = frame >= T.highFive && frame < T.highFive + 6 ? Math.sin(((frame - T.highFive) / 6) * Math.PI) * 3 : 0;
  const bob = Math.sin(frame / 6) * 2;
  const step = Math.floor(frame / 5) % 2; // little leg shuffle
  const blink = frame >= T.mascotIn[1] + 18 && frame < T.mascotIn[1] + 22;
  const lookRight = -1; // the robot comes in from its left

  const px = (x: number, y: number, w: number, h: number, fill: string, key?: string) => (
    <rect key={key} x={x * U} y={y * U} width={w * U} height={h * U} fill={fill} />
  );

  return (
    <svg
      width={20 * U}
      height={16 * U}
      viewBox={`${-10 * U} ${-11 * U} ${20 * U} ${16 * U}`}
      style={{
        position: 'absolute',
        left: MASCOT.x - 10 * U,
        top: MASCOT.y - 11 * U + (1 - shown) * 46 + bob + bump,
        overflow: 'visible',
        transform: `scale(${shown})`,
        transformOrigin: `${10 * U}px ${15 * U}px`,
        opacity: Math.min(1, shown * 1.4),
        filter: 'drop-shadow(0 8px 14px rgba(0,0,0,0.5))',
      }}
    >
      {/* legs */}
      {[-5, -3, 2, 4].map((x, i) => px(x, 2, 1, 2 + ((i + step) % 2) * 0.4, SHADE, `leg${i}`))}
      {/* body */}
      {px(-6, -5, 12, 7, ORANGE)}
      {px(-6, 1, 12, 1, SHADE)}
      {/* left arm: a nub that swings up for the high five */}
      <g transform={`rotate(${45 * armUp} ${-6 * U} ${-1 * U})`}>{px(-6 - 3.4 * armUp - 2 * (1 - armUp), -2, 2 + 1.4 * armUp, 2, ORANGE)}</g>
      {/* right nub */}
      {px(6, -2, 2, 2, ORANGE)}
      {/* eyes */}
      {blink ? (
        <>
          {px(-3 + lookRight * 0.4, -2.5, 1, 0.4, INK)}
          {px(2 + lookRight * 0.4, -2.5, 1, 0.4, INK)}
        </>
      ) : (
        <>
          {px(-3 + lookRight * 0.4, -3.5, 1, 2, INK)}
          {px(2 + lookRight * 0.4, -3.5, 1, 2, INK)}
        </>
      )}
    </svg>
  );
};

/** A small burst of sparks where the two hands meet. */
export const HighFiveSpark: React.FC<{frame: number; x: number; y: number}> = ({frame, x, y}) => {
  const t = (frame - T.highFive) / 14;
  if (t < 0 || t > 1) return null;
  const out = Easing.out(Easing.cubic)(t);
  return (
    <svg width={200} height={200} viewBox="-100 -100 200 200" style={{position: 'absolute', left: x - 100, top: y - 100, overflow: 'visible'}}>
      {Array.from({length: 8}, (_, i) => {
        const angle = (i / 8) * Math.PI * 2 + 0.3;
        const r1 = 10 + 30 * out;
        const r2 = r1 + 22 * (1 - t);
        return (
          <line
            key={i}
            x1={Math.cos(angle) * r1}
            y1={Math.sin(angle) * r1}
            x2={Math.cos(angle) * r2}
            y2={Math.sin(angle) * r2}
            stroke={i % 2 ? ORANGE : '#EDEDEF'}
            strokeWidth={5}
            strokeLinecap="round"
            opacity={1 - t}
          />
        );
      })}
      <circle r={14 * (1 - t)} fill="#FFFFFF" opacity={0.8 * (1 - t)} />
    </svg>
  );
};
