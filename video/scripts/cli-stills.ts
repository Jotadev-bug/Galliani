// `npm run stills:cli` (spec 015 R45): one PNG per GallianiCli beat, at the beat's middle frame, in out/cli-stills/.
// Bundles once, then renders each still from the bundle.
import {spawnSync} from 'node:child_process';
import {BEATS, CLI_RENDER} from '../src/cli/timeline.ts';

const bundle = 'out/cli-bundle';
const run = (args: string[]) => {
  const result = spawnSync('npx', ['remotion', ...args], {stdio: 'inherit', shell: process.platform === 'win32'});
  if (result.status !== 0) process.exit(result.status ?? 1);
};

run(['bundle', 'src/index.ts', `--out-dir=${bundle}`]);
for (const beat of BEATS) {
  const frame = beat.start + Math.floor(beat.duration / 2);
  run(['still', bundle, CLI_RENDER.compositionId, `${CLI_RENDER.stillsDir}/${beat.id}.png`, `--frame=${frame}`]);
}
