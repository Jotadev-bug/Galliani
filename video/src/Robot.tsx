// A tiny greyscale hover-robot that wanders the chat, curious about whatever is happening.
// Its path, hops, spin, and blinks come from timeline.ts; everything is a pure function of the frame.
import React from 'react';
import {Easing, interpolate} from 'remotion';
import {HIGH_FIVE_ARM, ROBOT_BLINKS, ROBOT_CHEER, ROBOT_HOPS, ROBOT_KEYS, ROBOT_TRAVEL, T, type RobotKey} from './timeline.ts';

const smooth = Easing.bezier(0.45, 0, 0.2, 1);

interface Pose {
  x: number;
  y: number;
  lookX: number;
  lookY: number;
}

function poseAt(frame: number): Pose {
  const keys = ROBOT_KEYS;
  let next = keys.findIndex((key) => key.f > frame);
  if (next === -1) next = keys.length - 1;
  const b: RobotKey = keys[next];
  const a: RobotKey = keys[Math.max(0, next - 1)];
  // Linear keys spread over the whole gap; others dart over a short travel time, then idle.
  const span = b.linear ? b.f - a.f : Math.min(b.f - a.f, b.travel ?? ROBOT_TRAVEL);
  const raw = span <= 0 ? 1 : Math.min(1, Math.max(0, (frame - a.f) / span));
  const t = b.linear ? raw : smooth(raw);
  const mix = (p: number, q: number) => p + (q - p) * t;
  const la = a.look ?? [0, 0];
  const lb = b.look ?? la;
  return {x: mix(a.x, b.x), y: mix(a.y, b.y), lookX: mix(la[0], lb[0]), lookY: mix(la[1], lb[1])};
}

/** A soft hop: up and back down over 12 frames. */
function hopOffset(frame: number): number {
  return ROBOT_HOPS.reduce((sum, start) => {
    const t = (frame - start) / 12;
    return t > 0 && t < 1 ? sum - 22 * Math.sin(Math.PI * t) : sum;
  }, 0);
}

function blinkScale(frame: number): number {
  for (const start of ROBOT_BLINKS) {
    const t = frame - start;
    if (t >= 0 && t < 6) return Math.abs(t - 3) / 3 + 0.08;
  }
  return 1;
}

const SCALE = 1.15;

const GREY = {
  shell: '#D7D7DC',
  shellShade: '#A7A7AE',
  face: '#0E0E10',
  eye: '#F4F4F6',
  dark: '#5A5A61',
};

export const Robot: React.FC<{frame: number}> = ({frame}) => {
  const pose = poseAt(frame);
  const before = poseAt(frame - 2);
  const after = poseAt(frame + 2);
  const vx = (after.x - before.x) / 4;
  // Lean into the direction of travel, plus a gentle idle sway.
  const lean = Math.max(-16, Math.min(16, vx * 1.2)) + Math.sin(frame / 17) * 3;
  const bob = Math.sin(frame / 7) * 4;
  const cheerT = interpolate(frame, ROBOT_CHEER, [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const cheer = Math.sin(Math.PI * cheerT); // 0 -> 1 -> 0 envelope
  const wiggle = Math.sin(cheerT * Math.PI * 6) * 10 * cheer;
  const armLift = 150 * cheer;
  // Right arm up for the high five.
  const fiveUp =
    interpolate(frame, [HIGH_FIVE_ARM[0], HIGH_FIVE_ARM[0] + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: smooth}) *
    (1 - interpolate(frame, [HIGH_FIVE_ARM[1], HIGH_FIVE_ARM[1] + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const vanish = interpolate(frame, T.robotVanish, [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: smooth});
  if (vanish <= 0) return null;
  const blink = blinkScale(frame);
  const eyeDX = pose.lookX * 6;
  const eyeDY = pose.lookY * 4;
  const glow = 0.55 + 0.45 * Math.sin(frame / 6);
  const thrust = 0.35 + 0.2 * Math.sin(frame / 3);
  const headTilt = pose.lookX * 6;

  return (
    <svg
      width={120 * SCALE}
      height={130 * SCALE}
      viewBox="-60 -70 120 130"
      style={{
        position: 'absolute',
        left: pose.x - 60 * SCALE,
        top: pose.y + bob + hopOffset(frame) - 64 * SCALE,
        overflow: 'visible',
        transform: `rotate(${lean + wiggle + (1 - vanish) * 120}deg) scale(${vanish})`,
        transformOrigin: `${60 * SCALE}px ${70 * SCALE}px`,
        filter: 'drop-shadow(0 10px 18px rgba(0,0,0,0.55))',
      }}
    >
      {/* thruster glow */}
      <ellipse cx={0} cy={44} rx={14} ry={5} fill="#FFFFFF" opacity={thrust * 0.5} />
      {/* body */}
      <rect x={-17} y={14} width={34} height={24} rx={10} fill={GREY.shellShade} />
      <circle cx={0} cy={26} r={4} fill={GREY.dark} />
      {/* arms */}
      <rect x={-27} y={18} width={9} height={16} rx={4.5} fill={GREY.shellShade} transform={`rotate(${12 + Math.sin(frame / 5) * 10 + armLift} -22 18)`} />
      <rect x={18} y={18} width={9} height={16} rx={4.5} fill={GREY.shellShade} transform={`rotate(${-12 - Math.sin(frame / 5) * 10 * (1 - fiveUp) - armLift - 140 * fiveUp} 22 18)`} />
      <g transform={`rotate(${headTilt} 0 0)`}>
        {/* antenna */}
        <line x1={0} y1={-30} x2={0} y2={-46} stroke={GREY.shellShade} strokeWidth={3} strokeLinecap="round" />
        <circle cx={0} cy={-49} r={5} fill={GREY.eye} opacity={glow} />
        {/* head */}
        <rect x={-30} y={-32} width={60} height={46} rx={16} fill={GREY.shell} />
        <rect x={-23} y={-25} width={46} height={30} rx={11} fill={GREY.face} />
        {/* eyes */}
        <g transform={`translate(${eyeDX} ${eyeDY - 10})`}>
          <rect x={-13} y={-5 * blink} width={8} height={10 * blink} rx={4} fill={GREY.eye} />
          <rect x={5} y={-5 * blink} width={8} height={10 * blink} rx={4} fill={GREY.eye} />
        </g>
      </g>
    </svg>
  );
};
