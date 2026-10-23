// The only colors in the GallianiCli composition (spec 015 R25, R75, Decisions 0036 and 0038).
// BRAND is used outside the terminal frame, TUI only inside it, ROBOT only by robot.tsx. tests/cli.test.ts fails on drift.

// The showcase and the mark. `accent` (orange) is for the mark and the background field only (R28).
export const BRAND = {
  bg: '#0A0A0B',
  surface: '#141416',
  raised: '#1C1C1F',
  text: '#EDEDEF',
  muted: '#8B8B92',
  accent: '#D97757',
} as const;

// A copy of DARK_PALETTE in galliani/tui/styles.py, which is the source of truth.
export const TUI = {
  bg: '#121318',
  surface: '#1a1c23',
  border: '#444856',
  fg: '#e4e6ea',
  muted: '#9ba1ae',
  accent: '#c3c7d0',
  good: '#5ec49a',
  warn: '#e0b04f',
  bad: '#ec6f78',
  agent: '#4cc2bd',
} as const;

// A copy of GREY in video/src/Robot.tsx (the showcase robot), the one exception to the two groups (R75).
export const ROBOT = {
  shell: '#D7D7DC',
  shellShade: '#A7A7AE',
  face: '#0E0E10',
  eye: '#F4F4F6',
  dark: '#5A5A61',
} as const;

export type TuiColor = keyof typeof TUI;
export type BrandColor = keyof typeof BRAND;
