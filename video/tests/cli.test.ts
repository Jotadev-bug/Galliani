// Checks for the GallianiCli composition (spec 015 Part B, B-AC2..B-AC11). Run with `npm test`.
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {BRAND, TUI} from '../src/cli/palette.ts';

const read = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8');
const STYLES = read('../../galliani/tui/styles.py');
const CLI_DIR = fileURLToPath(new URL('../src/cli', import.meta.url));
const cliSources = () => readdirSync(CLI_DIR).map((name) => ({name, source: readFileSync(join(CLI_DIR, name), 'utf8')}));

// R26: hex, rgb(), rgba(), hsl(), hsla(), and the keywords white and black.
const COLOR_LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\bwhite\b|\bblack\b/;

function pythonDict(source: string, name: string): Record<string, string> {
  const body = source.match(new RegExp(`^${name} = \\{([\\s\\S]*?)\\n\\}`, 'm'));
  assert.ok(body, `${name} not found in styles.py`);
  return Object.fromEntries([...body[1].matchAll(/"([a-z]+)":\s*"(#[0-9a-fA-F]{6})"/g)].map((m) => [m[1], m[2]]));
}

test('B-AC5: TUI palette equals DARK_PALETTE in styles.py', () => {
  const dark = pythonDict(STYLES, 'DARK_PALETTE');
  assert.equal(Object.keys(dark).length, 10);
  assert.deepEqual(TUI, dark);
});

test('B-AC5: BRAND equals R25 and the showcase colors', () => {
  assert.deepEqual(BRAND, {
    bg: '#0A0A0B', surface: '#141416', raised: '#1C1C1F', text: '#EDEDEF', muted: '#8B8B92', accent: '#D97757',
  });
  const showcase = read('../src/Showcase.tsx');
  for (const key of ['bg', 'surface', 'raised', 'text', 'muted'] as const) {
    assert.match(showcase, new RegExp(`${key}: '${BRAND[key]}'`), `Showcase C.${key}`);
  }
  assert.match(read('../src/Mascot.tsx'), new RegExp(`const ORANGE = '${BRAND.accent}'`));
});

test('B-AC6: no color literal outside palette.ts, and palette.ts holds only R25 values', () => {
  for (const {name, source} of cliSources()) {
    if (name === 'palette.ts') continue;
    assert.doesNotMatch(source, COLOR_LITERAL, `${name} has a color literal`);
  }
  const allowed = new Set<string>([...Object.values(BRAND), ...Object.values(TUI)]);
  assert.equal(allowed.size, 16);
  const palette = readFileSync(join(CLI_DIR, 'palette.ts'), 'utf8');
  for (const [hex] of palette.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) assert.ok(allowed.has(hex), `${hex} is not an R25 value`);
  assert.doesNotMatch(palette, /\brgba?\(|\bhsla?\(|\bwhite\b|\bblack\b/);
});
