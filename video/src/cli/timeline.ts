// GallianiCli scene data (spec 015 Part B, R19-R48): every frame number, string and layout box.
// Components read this file and hold no copy, timing or color of their own (R22).
//
// Terminal strings are copied from galliani/tui/widgets.py and commands.py (R32). The banner lines, the
// transcript entries, route ids, costs and `@file` rows were captured from the real TUI Session (spec 015 R33)
// driven headless with every provider mocked: no key, no provider call, a demo folder named signup-app.

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const DURATION = 720; // 24 s (R21, R54)

export const CLI_RENDER = {
  compositionId: 'GallianiCli',
  fps: FPS,
  width: WIDTH,
  height: HEIGHT,
  durationInFrames: DURATION,
  output: 'out/galliani-cli.mp4',
  stillsDir: 'out/cli-stills',
} as const;

// ---------------------------------------------------------------- copied TUI strings (R32, R33)

export const GOAL = 'Add email validation to signup.py and cover it with tests'; // R36, the showcase PROMPT
export const PLAN_STEPS = ['Read signup.py', 'Write the validation', 'Save signup.py and tests', 'Run the tests'];

export const TERM = {
  // Banner (widgets.py Banner); routing and settings lines as the session built them.
  bannerTitle: 'Galliani 0.2.0',
  bannerWorkspace: 'C:\\dev\\signup-app',
  bannerRouting: 'routing: auto · anthropic · openrouter',
  bannerSettings: 'edit mode: ask · budget: $0.50 · memory: on',
  tips: ['/help for commands · / to complete commands', 'Esc to stop a task · @ to mention a file'],
  idlePlaceholder: 'Type an objective, or / for commands',
  activePlaceholder: 'Esc to stop',
  promptLead: '>',
  leaders: {user: '>', plan: '●', route: '·', tool: '●', verification: '●', approval: '?', result: '●', usage: '·'},
  detailLead: '  └ ',
  detailIndent: '    ',
  stepGlyphs: {pending: '...', running: '>', waiting: '[?]', verified: '[ok]'},
  spinnerFrames: ['·', '•', '●', '•'],
  spinnerStatic: '●',
  verbs: {
    planning: ['Planning', 'Outlining', 'Mapping the steps', 'Sequencing'],
    running: ['Working', 'Gathering', 'Assembling', 'Working through it'],
    verifying: ['Verifying', 'Checking', 'Comparing', 'Confirming'],
    waiting: ['Waiting for you'],
  },
  planTitle: 'Plan',
  noPlan: 'No plan yet.',
  // Status line pieces (build_status_text): workspace name, budget, edit mode, memory.
  workspaceName: 'signup-app',
  budget: '$0.50',
  editMode: 'ask',
  memory: 'memory on',
  // Completion popup (CompletionPopup._redraw).
  popupCurrent: '› ',
  popupOther: '  ',
  popupMore: '  …',
  popupRows: 8,
  // Approval card (ApprovalCard).
  approvalTitle: 'Approval needed',
  approvalLabels: ['Action: ', 'Risk:   ', 'Scope:  '],
  approvalKeys: ['[y] approve   [n] deny', '   [a] approve and accept edits', '   [Esc] deny'],
  approvalValues: [
    "Allow 'write_file' (write) on 'signup.py' limited to scope 'signup.py'? Reason: Save signup.py and tests",
    'write action',
    'signup.py',
  ],
  // The shell line the TUI is launched from.
  shellPrompt: 'PS C:\\dev\\signup-app> ',
  command: 'galliacli',
} as const;

// commands.complete_command("/") for COMMANDS, in order: label and summary.
export const SLASH_ROWS: readonly PopupRow[] = [
  {label: '/help', summary: 'list commands and keys'},
  {label: '/clear', summary: 'clear the visible transcript (not history, not the task)'},
  {label: '/workspace', summary: 'show, or switch to an existing folder'},
  {label: '/edit-mode', summary: 'show or set the edit mode'},
  {label: '/budget', summary: 'show or set the per-task budget'},
  {label: '/memory', summary: 'list or forget memory records, or turn memory on/off'},
  {label: '/events', summary: 'show or hide verbose public events'},
  {label: '/theme', summary: 'switch the theme for this session'},
  {label: '/quit', summary: 'quit Galliani'},
];

// Session.complete for `@` and `@sig` in the demo folder.
export const FILE_ROWS_ALL: readonly PopupRow[] = [
  {label: '@README.md', summary: ''},
  {label: '@signup.py', summary: ''},
  {label: '@tests/test_signup.py', summary: ''},
];
export const FILE_ROWS_SIG: readonly PopupRow[] = [{label: '@signup.py', summary: ''}];
export const AT_PROMPT = 'Add a test for @sig';
export const AT_DONE = 'Add a test for @signup.py';

export const ROUTE_CODING = 'anthropic/claude-sonnet-5.5';
export const ROUTE_TEXT = 'google/gemini-3.1-flash-lite';

// Transcript entries as the session added them. The planning call's route line is left out (it names the
// planner's capability, which B-AC8 keeps off screen); the status line still shows its route.
const E = {
  user: {kind: 'user', text: GOAL},
  plan: {
    kind: 'plan',
    text: 'Plan v1: plan v1 with 4 step(s)',
    detail: [
      's1 (tool: read_file) Read signup.py',
      's2 (model: coding) Write the validation',
      's3 (tool: write_file) Save signup.py and tests',
      's4 (model: text) Run the tests',
    ],
  },
  readOk: {kind: 'tool', text: 'read_file succeeded'},
  checked: {kind: 'verification', text: 'The criterion is satisfied.'},
  routeCoding: {
    kind: 'route',
    text: `Selected ${ROUTE_CODING}: supports coding; high cost, medium latency (cheapest strategy).`,
  },
  writeBlocked: {kind: 'tool', text: 'write_file: write action requires user approval'},
  approval: {
    kind: 'approval',
    text: "Approval needed: Allow 'write_file' (write) on 'signup.py' limited to scope 'signup.py'? Reason: Save signup.py and tests",
    detail: ['risk: write action', 'scope: signup.py'],
  },
  approved: {kind: 'approval', text: 'You approved.'},
  writeOk: {kind: 'tool', text: 'write_file succeeded'},
  routeText: {
    kind: 'route',
    text: `Selected ${ROUTE_TEXT}: supports text; low cost, fast latency (cheapest strategy).`,
  },
  result: {
    kind: 'result',
    text: 'Status: done - objective completed and verified: all 4 step(s) passed verification',
    detail: ['Verification: pass - all 4 step(s) passed verification', 'overwritten: signup.py'],
    body: 'All 6 tests pass.',
  },
  usage: {kind: 'usage', text: 'Usage: 3 model call(s), 3943 input / 315 output tokens, est. $0.0108 (registry prices)'},
} as const satisfies Record<string, Entry>;

// ---------------------------------------------------------------- types (spec 015 Interfaces, Part B)

export type Segment = 'Hook' | 'Launch' | 'Objective to plan' | 'Routing' | 'Commands' | 'Control' | 'Close';
export type StepState = 'pending' | 'running' | 'waiting' | 'verified';
export type EntryKind = keyof typeof TERM.leaders;
export type VerbGroup = keyof typeof TERM.verbs;

export interface Entry {
  kind: EntryKind;
  text: string;
  detail?: readonly string[];
  body?: string;
}
export interface PopupRow {
  label: string;
  summary: string;
}
export interface Typing {
  text: string;
  from: number; // local frame the first character appears
  frames: number; // frames from the first character to the last; 0 shows the whole string at once
}
export interface Screen {
  entries: readonly Entry[];
  steps: readonly StepState[] | null; // null: no plan yet
  shownSteps?: number; // plan rows shown so far (rows appear one by one)
  fresh?: number; // index of the step that just turned [ok] (bold for HIGHLIGHT_FRAMES, spec 018 R11)
  working: {group: VerbGroup; elapsed: number; cost: number; step?: number} | null;
  status: {route: string | null; cost: number; label: string};
  prompt: {typing: Typing; placeholder: string} | null; // null while the approval card replaces the box
  popup?: {rows: readonly PopupRow[]; selected: number};
  approval?: {pressed: boolean};
}
export interface Key {
  at: number; // local frame within the beat
  screen: Screen;
}
export type Shot =
  | {kind: 'mark'}
  | {kind: 'hook-prompt'}
  | {kind: 'shell'; typing: Typing}
  | {kind: 'terminal'; keys: readonly Key[]}
  | {kind: 'end'};
// The emphasized motions a beat may carry (R38, R49: at most one per beat). `at` is a local frame.
export interface Push {
  at: number;
  frames: number;
  from: number;
  to: number;
  origin: {x: number; y: number}; // canvas pixels the push zooms toward
}
export interface Entrance {
  at: number;
  frames: number;
  slide: number; // px the incoming shot rises into place
}
export interface Move {
  at: number;
  frames: number; // the mark moves from the seam spot to beside the hook prompt
}
export interface Count {
  at: number;
  frames: number;
  from: number; // cost before, in USD
  to: number;
}
export interface CardEnter {
  at: number; // the approval card's own entry, CARD_ENTER_FRAMES long
}
export interface CliBeat {
  id: string;
  segment: Segment;
  start: number;
  duration: number;
  shot: Shot;
  push?: Push;
  entrance?: Entrance;
  move?: Move;
  count?: Count;
  card?: CardEnter;
}
export interface CliCaption {
  segment: Segment;
  text: string;
  start: number;
  end: number;
  box: {x: number; y: number; width: number; height: number; fontSize: number};
  enterFrames: number;
}

// ---------------------------------------------------------------- timing constants

export const SPINNER_FPS = 4; // widgets.SPINNER_FPS
export const VERB_SECONDS = 3; // widgets.VERB_SECONDS
export const HIGHLIGHT_FRAMES = 12; // widgets.HIGHLIGHT_SECONDS (0.4 s)
export const CARD_ENTER_FRAMES = 5; // widgets.CARD_ENTER_SECONDS (0.18 s)
export const CARD_ENTER_ROWS = 2; // widgets.CARD_ENTER_ROWS
export const CARET_BLINK_FRAMES = 15; // Textual's 0.5 s cursor blink
export const GRID = 15; // beats and motions start on the 0.5 s grid (R53)
export const CAPTION_ENTER = {frames: 6, slide: 24, fade: 4}; // one element; px; opacity ramp (R38, R39)
export const ENTRANCE = {frames: 8, slide: 24}; // a new shot rises into place, no fade (R38, R62)
export const MOVE_FRAMES = 15; // the mark moves aside (R38)
export const COUNT_FRAMES = 15; // a cost counts up (R38, R56)
export const PUSH_FRAMES = 15;
export const TYPE_SPEEDUP = 2.5; // the last character interval is this much shorter than the first (R52)

// ---------------------------------------------------------------- layout

export const FONTS = {
  sans: '"Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif',
  mono: '"Cascadia Mono", Consolas, "SF Mono", Menlo, monospace',
} as const;

// The 90% title-safe area (R42, R63).
export const SAFE = {left: 96, right: WIDTH - 96, top: 54, bottom: HEIGHT - 54};

// The terminal window. Rows are 30 px; the docked plan panel is 40 columns wide (widgets.DOCK_MIN_WIDTH), and
// transcript text wraps at `transcriptColumns`. `border` and `pad` size the content box (layout.ts).
export const TERMINAL = {
  x: 180, y: 204, width: 1560, height: 780, radius: 14, titleBar: 40, border: 1.5, pad: {top: 6, bottom: 4, side: 6},
  fontSize: 21, row: 30, planColumns: 40, transcriptColumns: 80,
};
// The seam spot (R57): where the mark sits on frame 0, in the end card and on the last frame.
export const SEAM_MARK = {x: WIDTH / 2, y: 482, size: 240};
export const HOOK = {asideSize: 150, asideX: 818, promptX: 953, promptSize: 150};
// The end card block: the mark, a gap, then the `galliacli` line, centered on the frame (R65). The call to action
// shows for `ctaFrames`, then the card holds in the seam state (R57).
export const END = {markSize: SEAM_MARK.size, gap: 36, wordSize: 64, wordLine: 80, ctaFrames: 30};

const TOP_CAPTION = {x: 96, y: 56, width: 1728, height: 112, fontSize: 64};
const HOOK_CAPTION = {x: 96, y: 650, width: 1728, height: 110, fontSize: 76};

// Push origins. Each keeps the zoomed terminal inside the safe area and below the caption band (B-AC21).
const AT = {
  prompt: {x: 560, y: 600},
  result: {x: 640, y: 560},
};

// ---------------------------------------------------------------- beats (R46)

const idleStatus = {route: null, cost: 0, label: 'Ready'};
const typed = (text: string, from = 0, frames = 0): Typing => ({text, from, frames});
const idlePrompt = (typing: Typing = typed('')) => ({typing, placeholder: TERM.idlePlaceholder});
const activePrompt = {typing: typed(''), placeholder: TERM.activePlaceholder};

const idle: Screen = {entries: [], steps: null, working: null, status: idleStatus, prompt: idlePrompt()};
const ran = [E.user, E.plan, E.readOk, E.checked];
const coded = [...ran, E.routeCoding, E.checked];
const waiting = [...coded, E.writeBlocked, E.approval];
const waitingScreen: Screen = {
  entries: waiting,
  steps: ['verified', 'verified', 'waiting', 'pending'],
  working: {group: 'waiting', elapsed: 8, cost: 0.0107, step: 3},
  status: {route: ROUTE_CODING, cost: 0.0107, label: 'Needs your approval'},
  prompt: null,
  approval: {pressed: false},
};

const planning = (shownSteps: number): Screen => ({
  entries: [E.user, E.plan],
  steps: ['pending', 'pending', 'pending', 'pending'],
  shownSteps,
  working: {group: 'planning', elapsed: 1, cost: 0.0103},
  status: {route: ROUTE_CODING, cost: 0.0103, label: 'Planning'},
  prompt: activePrompt,
});

const SHELL_TYPING = typed(TERM.command, 12, 12);
const GOAL_TYPING = typed(GOAL, 3, 36);
const AT_TYPING = typed(AT_PROMPT, 0, 18);
// The `@` popup opens on the frame `@` is typed, and narrows to `@sig` on the frame `g` is typed.
const AT_SIGN = Math.ceil(charTimes(AT_TYPING)[AT_PROMPT.indexOf('@')]);
const AT_SIG = Math.ceil(charTimes(AT_TYPING)[AT_PROMPT.length - 1]);

const BEATS_RAW: readonly Omit<CliBeat, 'start'>[] = [
  {id: 'hook-mark', segment: 'Hook', duration: 45, shot: {kind: 'mark'}},
  {id: 'hook-prompt', segment: 'Hook', duration: 45, shot: {kind: 'hook-prompt'}, move: {at: 0, frames: MOVE_FRAMES}},
  {
    id: 'launch-type', segment: 'Launch', duration: 45, shot: {kind: 'shell', typing: SHELL_TYPING},
    entrance: {at: 0, ...ENTRANCE},
  },
  {id: 'launch-banner', segment: 'Launch', duration: 45, shot: {kind: 'terminal', keys: [{at: 0, screen: idle}]}},
  {
    id: 'goal-type', segment: 'Objective to plan', duration: 60,
    shot: {kind: 'terminal', keys: [{at: 0, screen: {...idle, prompt: idlePrompt(GOAL_TYPING)}}]},
    push: {at: 15, frames: PUSH_FRAMES, from: 1, to: 1.05, origin: AT.prompt},
  },
  {
    id: 'plan-steps', segment: 'Objective to plan', duration: 45,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: {
        entries: [E.user], steps: null, working: {group: 'planning', elapsed: 0, cost: 0},
        status: {route: ROUTE_CODING, cost: 0, label: 'Planning'}, prompt: activePrompt,
      }},
      {at: 15, screen: planning(1)},
      {at: 18, screen: planning(2)},
      {at: 21, screen: planning(3)},
      {at: 24, screen: planning(4)},
      {at: 33, screen: {
        entries: [E.user, E.plan], steps: ['running', 'pending', 'pending', 'pending'],
        working: {group: 'running', elapsed: 3, cost: 0.0103, step: 1},
        status: {route: ROUTE_CODING, cost: 0.0103, label: 'Working'}, prompt: activePrompt,
      }},
    ]},
    count: {at: 15, frames: COUNT_FRAMES, from: 0, to: 0.0103},
  },
  {
    id: 'plan-check', segment: 'Objective to plan', duration: 30,
    shot: {kind: 'terminal', keys: [{at: 0, screen: {
      entries: ran, steps: ['verified', 'running', 'pending', 'pending'], fresh: 0,
      working: {group: 'running', elapsed: 4, cost: 0.0103, step: 2},
      status: {route: ROUTE_CODING, cost: 0.0103, label: 'Working'}, prompt: activePrompt,
    }}]},
  },
  {
    id: 'route-first', segment: 'Routing', duration: 60,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: {
        entries: [...ran, E.routeCoding], steps: ['verified', 'running', 'pending', 'pending'],
        working: {group: 'running', elapsed: 5, cost: 0.0103, step: 2},
        status: {route: ROUTE_CODING, cost: 0.0103, label: 'Working'}, prompt: activePrompt,
      }},
      {at: 30, screen: {
        entries: [...ran, E.routeCoding], steps: ['verified', 'running', 'pending', 'pending'],
        working: {group: 'verifying', elapsed: 6, cost: 0.0107, step: 2},
        status: {route: ROUTE_CODING, cost: 0.0107, label: 'Checking the result'}, prompt: activePrompt,
      }},
    ]},
    count: {at: 30, frames: COUNT_FRAMES, from: 0.0103, to: 0.0107},
  },
  {
    id: 'route-next', segment: 'Routing', duration: 45,
    shot: {kind: 'terminal', keys: [{at: 0, screen: {
      entries: coded, steps: ['verified', 'verified', 'running', 'pending'], fresh: 1,
      working: {group: 'running', elapsed: 7, cost: 0.0107, step: 3},
      status: {route: ROUTE_CODING, cost: 0.0107, label: 'Working'}, prompt: activePrompt,
    }}]},
  },
  {
    id: 'slash-popup', segment: 'Commands', duration: 60,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: idle},
      {at: 15, screen: {...idle, prompt: idlePrompt(typed('/')), popup: {rows: SLASH_ROWS, selected: 0}}},
      {at: 30, screen: {...idle, prompt: idlePrompt(typed('/')), popup: {rows: SLASH_ROWS, selected: 1}}},
      {at: 40, screen: {...idle, prompt: idlePrompt(typed('/')), popup: {rows: SLASH_ROWS, selected: 2}}},
    ]},
  },
  {
    id: 'at-file', segment: 'Commands', duration: 60,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: {...idle, prompt: idlePrompt(AT_TYPING)}},
      {at: AT_SIGN, screen: {...idle, prompt: idlePrompt(AT_TYPING), popup: {rows: FILE_ROWS_ALL, selected: 0}}},
      {at: AT_SIG, screen: {...idle, prompt: idlePrompt(AT_TYPING), popup: {rows: FILE_ROWS_SIG, selected: 0}}},
      {at: 30, screen: {...idle, prompt: idlePrompt(typed(AT_DONE))}},
    ]},
  },
  {
    id: 'approval-card', segment: 'Control', duration: 45,
    shot: {kind: 'terminal', keys: [{at: 0, screen: waitingScreen}]},
    card: {at: 0},
  },
  {
    id: 'approval-answer', segment: 'Control', duration: 45,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: waitingScreen},
      {at: 15, screen: {...waitingScreen, approval: {pressed: true}}},
      {at: 20, screen: {
        entries: [...waiting, E.approved], steps: ['verified', 'verified', 'running', 'pending'],
        working: {group: 'running', elapsed: 9, cost: 0.0107, step: 3},
        status: {route: ROUTE_CODING, cost: 0.0107, label: 'Working'}, prompt: activePrompt,
      }},
      {at: 30, screen: {
        entries: [...waiting, E.approved, E.writeOk, E.checked], steps: ['verified', 'verified', 'verified', 'running'],
        fresh: 2, working: {group: 'running', elapsed: 10, cost: 0.0107, step: 4},
        status: {route: ROUTE_CODING, cost: 0.0107, label: 'Working'}, prompt: activePrompt,
      }},
    ]},
  },
  {
    id: 'verified-done', segment: 'Close', duration: 45,
    shot: {kind: 'terminal', keys: [{at: 0, screen: {
      entries: [...waiting, E.approved, E.writeOk, E.checked, E.routeText, E.checked, E.result, E.usage],
      steps: ['verified', 'verified', 'verified', 'verified'], fresh: 3, working: null,
      status: {route: ROUTE_TEXT, cost: 0.0108, label: 'Ready'}, prompt: idlePrompt(),
    }}]},
    push: {at: 0, frames: PUSH_FRAMES, from: 1, to: 1.05, origin: AT.result},
  },
  {id: 'end-card', segment: 'Close', duration: 45, shot: {kind: 'end'}},
];

export const BEATS: readonly CliBeat[] = BEATS_RAW.reduce<CliBeat[]>((out, beat) => {
  const previous = out[out.length - 1];
  out.push({...beat, start: previous ? previous.start + previous.duration : 0});
  return out;
}, []);

// ---------------------------------------------------------------- captions (R40-R43, R46: exact text)

export const segmentSpan = (segment: Segment) => {
  const beats = BEATS.flatMap((b) => (b.segment === segment ? [b] : []));
  return {start: beats[0].start, end: beats[beats.length - 1].start + beats[beats.length - 1].duration};
};
const caption = (segment: Segment, text: string, box = TOP_CAPTION, enterFrames: number = CAPTION_ENTER.frames): CliCaption => ({
  segment, text, ...segmentSpan(segment), box, enterFrames,
});

// The hook caption cuts in on frame 0 (R55); the others rise in as one element (R38).
export const CAPTIONS: readonly CliCaption[] = [
  caption('Hook', 'Galliani now runs in your terminal.', HOOK_CAPTION, 0),
  caption('Launch', 'One command.'),
  caption('Objective to plan', 'Type a goal. Watch the plan.'),
  caption('Routing', 'The cheapest capable model, every step.'),
  caption('Commands', 'Slash commands. @ files.'),
  caption('Control', 'You approve what matters.'),
  caption('Close', 'Local. No telemetry. Free.'),
];

// ---------------------------------------------------------------- lookups and the TUI's own formats

export function beatAt(frame: number): CliBeat {
  return BEATS.find((b) => frame >= b.start && frame < b.start + b.duration) ?? BEATS[BEATS.length - 1];
}

export function captionAt(frame: number): CliCaption | undefined {
  return CAPTIONS.find((c) => frame >= c.start && frame < c.end);
}

export function screenAt(keys: readonly Key[], local: number): {key: Key; since: number} {
  let key = keys[0];
  for (const k of keys) if (k.at <= local) key = k;
  return {key, since: local - key.at};
}

// The local frame each character appears (R52). The n-1 intervals shrink linearly, so typing speeds up: the last
// interval is TYPE_SPEEDUP times shorter than the first, they never grow, and the last character lands on
// `from + frames`. Frames 0 shows the whole string at `from`.
export function charTimes(typing: Typing): number[] {
  const n = typing.text.length;
  if (n === 0) return [];
  const gaps = n - 1;
  if (typing.frames <= 0 || gaps === 0) return Array.from({length: n}, () => typing.from);
  const first = (2 * typing.frames) / (gaps * (1 + 1 / TYPE_SPEEDUP));
  const times = [typing.from];
  for (let i = 0; i < gaps; i++) {
    const shrink = gaps === 1 ? 0 : (1 - 1 / TYPE_SPEEDUP) * (i / (gaps - 1));
    times.push(times[i] + first * (1 - shrink));
  }
  return times;
}

// How many characters show at a local frame; pure and non-decreasing.
export function typedCount(typing: Typing, local: number): number {
  return charTimes(typing).reduce((count, t) => (t <= local + 1e-9 ? count + 1 : count), 0);
}

export function typedText(typing: Typing, local: number): string {
  return typing.text.slice(0, typedCount(typing, local));
}

// widgets.spinner_frame at 4 frames per second of video.
export function spinnerAt(frame: number): string {
  return TERM.spinnerFrames[Math.floor((frame * SPINNER_FPS) / FPS) % TERM.spinnerFrames.length];
}

const money = (usd: number) => `$${usd.toFixed(4)}`;

// widgets.step_line: `{glyph:<4} {index}. {purpose} ({state})`; a running row shows the spinner frame.
export function stepLine(index: number, state: StepState, spinner?: string): string {
  const glyph = spinner && state === 'running' ? spinner : TERM.stepGlyphs[state];
  return `${glyph.padEnd(4)} ${index}. ${PLAN_STEPS[index - 1]} (${state})`;
}

// widgets.active_step and plan_summary_text.
export function planSummary(steps: readonly StepState[]): string {
  let number = steps.length;
  let word: string = steps[steps.length - 1];
  const found = (['running', 'waiting', 'pending'] as const).find((w) => steps.includes(w));
  if (found) {
    number = steps.indexOf(found) + 1;
    word = found;
  } else if (steps.every((s) => s === 'verified')) {
    word = 'done';
  }
  return `Plan v1 - step ${number}/${steps.length} - ${word}`;
}

// widgets.build_working_text with motion on.
export function workingText(working: NonNullable<Screen['working']>, spinner: string): string {
  const verbs = TERM.verbs[working.group];
  const verb = verbs[Math.floor(working.elapsed / VERB_SECONDS) % verbs.length];
  const glyph = working.group === 'waiting' ? TERM.spinnerStatic : spinner;
  const parts = [`${glyph} ${verb}…`, `${working.elapsed}s`, `${money(working.cost)} / ${TERM.budget}`];
  if (working.step) parts.push(`step ${working.step}/${PLAN_STEPS.length}`);
  return parts.join(' · ');
}

// widgets.build_status_text at full width.
export function statusText(status: Screen['status']): string {
  const parts: string[] = [TERM.workspaceName];
  if (status.route) parts.push(`route ${status.route}`);
  parts.push(`${money(status.cost)} / ${TERM.budget}`, TERM.editMode, TERM.memory, status.label);
  return parts.join(' · ');
}

// CompletionPopup._redraw: the label column is the longest label (at most 28) plus two.
export function popupLines(rows: readonly PopupRow[], selected: number): {text: string; current: boolean}[] {
  const window = rows.slice(0, TERM.popupRows);
  const column = Math.min(28, Math.max(...window.map((r) => r.label.length))) + 2;
  const lines = window.map((row, i) => ({
    text: (i === selected ? TERM.popupCurrent : TERM.popupOther) + row.label.padEnd(column) + row.summary,
    current: i === selected,
  }));
  if (rows.length > TERM.popupRows) lines.push({text: TERM.popupMore, current: false});
  return lines;
}
