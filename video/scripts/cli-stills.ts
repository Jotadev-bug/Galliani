// `npm run stills:cli` (spec 015 R45): one PNG per GallianiCli beat, at the beat's middle frame, in out/cli-stills/,
// plus frame-first.png and frame-last.png for the loop seam, and an early beat over a later background field.
// Bundles once, then renders each still from the bundle.
import {spawnSync} from 'node:child_process';
import {mkdirSync, writeFileSync} from 'node:fs';
import {BEATS, CLI_RENDER, DURATION} from '../src/cli/timeline.ts';

const bundle = 'out/cli-bundle';
const run = (args: string[]) => {
  const result = spawnSync('npx', ['remotion', ...args], {stdio: 'inherit', shell: process.platform === 'win32'});
  if (result.status !== 0) process.exit(result.status ?? 1);
};
const still = (name: string, frame: number, extra: string[] = []) =>
  run(['still', bundle, CLI_RENDER.compositionId, `${CLI_RENDER.stillsDir}/${name}.png`, `--frame=${frame}`, ...extra]);

run(['bundle', 'src/index.ts', `--out-dir=${bundle}`]);
for (const beat of BEATS) still(beat.id, beat.start + Math.floor(beat.duration / 2));
still('frame-first', 0);
still('frame-last', DURATION - 1);

// The early beat `launch-banner` with the field half a loop later, so the field's drift shows side by side.
const early = BEATS.find((b) => b.id === 'launch-banner') ?? BEATS[0];
mkdirSync(CLI_RENDER.stillsDir, {recursive: true});
const props = `${CLI_RENDER.stillsDir}/field-shift.json`;
writeFileSync(props, JSON.stringify({fieldShift: DURATION / 4}));
still(`${early.id}-later-field`, early.start + Math.floor(early.duration / 2), [`--props=${props}`]);
