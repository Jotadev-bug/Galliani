import React from 'react';
import {Composition} from 'remotion';
import {Showcase} from './Showcase.tsx';
import {DURATION, FPS, HEIGHT, RENDER, WIDTH} from './timeline.ts';
import {GallianiCli} from './cli/GallianiCli.tsx';
import {CLI_RENDER} from './cli/timeline.ts';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id={RENDER.compositionId}
      component={Showcase}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      durationInFrames={DURATION}
    />
    <Composition
      id={CLI_RENDER.compositionId}
      component={GallianiCli}
      fps={CLI_RENDER.fps}
      width={CLI_RENDER.width}
      height={CLI_RENDER.height}
      durationInFrames={CLI_RENDER.durationInFrames}
    />
  </>
);
