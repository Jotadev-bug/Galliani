import React from 'react';
import {Composition} from 'remotion';
import {Showcase} from './Showcase.tsx';
import {DURATION, FPS, HEIGHT, RENDER, WIDTH} from './timeline.ts';

export const RemotionRoot: React.FC = () => (
  <Composition
    id={RENDER.compositionId}
    component={Showcase}
    fps={FPS}
    width={WIDTH}
    height={HEIGHT}
    durationInFrames={DURATION}
  />
);
