// The showcase hover-robot as the GallianiCli guide (spec 015 R74-R78, Decision 0038). The shapes are copied from
// video/src/Robot.tsx into ROBOT_SHAPES (a test checks for drift) and drawn here in the ROBOT palette only. It does not
// import the showcase: no shadow, no sway, no cheer wiggle, no pulse. pose.ts says where every part is.
import React from 'react';
import {ROBOT_FRAME, ROBOT_SHAPES as S} from './timeline.ts';
import {ROBOT} from './palette.ts';
import type {RobotPose} from './pose.ts';

const V = ROBOT_FRAME.viewBox;

export const GuideRobot: React.FC<{pose: RobotPose}> = ({pose}) => {
  const {box} = pose;
  const origin = {x: (-V.x / V.width) * box.width, y: (-V.y / V.height) * box.height};
  const eyeH = ROBOT_FRAME.eyeHeight * pose.blink; // Robot.tsx: height 10 * blink, y -5 * blink
  return (
    <svg
      width={box.width}
      height={box.height}
      viewBox={`${V.x} ${V.y} ${V.width} ${V.height}`}
      style={{
        position: 'absolute',
        left: box.x,
        top: box.y + pose.breath,
        overflow: 'visible',
        transform: pose.lean ? `rotate(${pose.lean}deg)` : undefined,
        transformOrigin: `${origin.x}px ${origin.y}px`,
      }}
    >
      <ellipse {...S.thruster} fill={ROBOT.eye} opacity={ROBOT_FRAME.thrusterOpacity} />
      <rect {...S.body} fill={ROBOT.shellShade} />
      <circle {...S.chest} fill={ROBOT.dark} />
      <rect {...S.armLeft} fill={ROBOT.shellShade} transform={`rotate(${pose.armLeft} ${ROBOT_FRAME.pivotLeft.x} ${ROBOT_FRAME.pivotLeft.y})`} />
      <rect {...S.armRight} fill={ROBOT.shellShade} transform={`rotate(${pose.armRight} ${ROBOT_FRAME.pivotRight.x} ${ROBOT_FRAME.pivotRight.y})`} />
      <g transform={`rotate(${pose.headTilt} 0 0)`}>
        <line {...S.antenna} stroke={ROBOT.shellShade} strokeWidth={ROBOT_FRAME.antennaWidth} strokeLinecap="round" />
        <circle {...S.antennaTip} fill={ROBOT.eye} opacity={ROBOT_FRAME.antennaTipOpacity} />
        <rect {...S.head} fill={ROBOT.shell} />
        <rect {...S.face} fill={ROBOT.face} />
        <g transform={`translate(${pose.eyeX} ${pose.eyeY + ROBOT_FRAME.eyeRow})`}>
          <rect {...S.eyeLeft} y={-eyeH / 2} height={eyeH} fill={ROBOT.eye} />
          <rect {...S.eyeRight} y={-eyeH / 2} height={eyeH} fill={ROBOT.eye} />
        </g>
      </g>
    </svg>
  );
};
