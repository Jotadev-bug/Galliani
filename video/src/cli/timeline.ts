// GallianiCli scene data (spec 015 Part B, R19-R82): every frame number, string and layout box.
// Components read this file and hold no copy, timing or color of their own (R22).
//
// Terminal strings are copied from galliani/tui/widgets.py and commands.py (R32). The banner lines, the
// transcript entries, route ids, costs and `@file` rows were captured from the real TUI Session (spec 015 R33)
// driven headless with every provider mocked: no key, no provider call, a demo folder named signup-app.

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const DURATION = 960; // 32 s (R21, R54)

export const CLI_RENDER = {
  compositionId: 'GallianiCli',
  fps: FPS,
  width: WIDTH,
  height: HEIGHT,
  durationInFrames: DURATION,
  output: 'out/galliani-cli.mp4',
  stillsDir: 'out/cli-stills',
  previewScale: 1,
  finalScale: 2,
  stillScale: 2,
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
  kept?: number; // leading characters already in the box, shown from `from`; the rest are typed (R52 at-file)
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
// `desk`: the desktop, with the window at its desktop rectangle; `shell`: the same window, typing after the shell
// prompt, over the still desktop; `terminal`: the TUI; `end`: the end card.
export type Shot =
  | {kind: 'desk'}
  | {kind: 'shell'; typing: Typing}
  | {kind: 'terminal'; keys: readonly Key[]}
  | {kind: 'end'};
// The emphasized motions a beat may carry (R38, R49: at most one per beat). `at` is a local frame.
export interface Timed {
  at: number;
  frames: number;
}
export interface Count extends Timed {
  from: number; // cost before, in USD
  to: number;
}
export interface CardEnter {
  at: number; // the approval card's own entry, CARD_ENTER_FRAMES long
}
export type Pose = 'lean' | 'point' | 'glance' | 'nod' | 'raise' | 'lower' | 'cheer' | 'wave';
export interface GestureCue {
  at: number;
  pose: Pose;
  target: TargetId;
}
export interface CliBeat {
  id: string;
  segment: Segment;
  start: number;
  duration: number;
  shot: Shot;
  cursor?: Timed;
  drag?: Timed;
  absorb?: Timed;
  expand?: Timed;
  count?: Count;
  card?: CardEnter;
  gesture?: GestureCue;
}
export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}
export interface CliCaption {
  segment: Segment;
  text: string;
  start: number;
  end: number;
  box: Box & {fontSize: number};
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
export const CURSOR_FRAMES = 30; // the cursor travels to the hero icon (R68)
export const DRAG_FRAMES = 40; // the icon rides one arc to the window (R70)
export const ABSORB = {frames: 8, scale: 0.12, fade: 4}; // the icon shrinks into the caret (R71)
export const EXPAND_FRAMES = 15; // the window grows into the TUI frame (R73)
export const COUNT_FRAMES = 15; // a cost counts up (R38, R56)
export const TYPE_SPEEDUP = 2.5; // the last character interval is this much shorter than the first (R52)

// ---------------------------------------------------------------- layout

export const FONTS = {
  sans: '"Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif',
  mono: '"Cascadia Mono", Consolas, "SF Mono", Menlo, monospace',
} as const;
export const MONO_ADVANCE = 0.586; // Cascadia Mono's advance width in em (1200 / 2048)

// The 90% title-safe area (R42, R63).
export const SAFE = {left: 96, right: WIDTH - 96, top: 54, bottom: HEIGHT - 54};

// The Act 3 terminal frame, left of centre so the robot fits at its lower right (R76). Rows are 30 px; the docked
// plan panel is 40 columns wide (widgets.DOCK_MIN_WIDTH), and transcript text wraps at `transcriptColumns`.
// `border` and `pad` size the content box (layout.ts); a focused window border is `focusBorder` wide (R71).
export const TERMINAL = {
  x: 104, y: 204, width: 1480, height: 780, radius: 14, titleBar: 40, border: 1.5, focusBorder: 3,
  pad: {top: 6, bottom: 4, side: 6}, fontSize: 21, row: 30, planColumns: 40, transcriptColumns: 74,
};

// The desktop (R66, R67): three generic icons and the hero icon in a column at the left, the window at the right.
// `tile` is the rounded square; the label sits below it.
export type Glyph = 'page' | 'folder' | 'grid';
export interface DesktopIcon {
  label: string;
  glyph?: Glyph;
  tile: Box;
  labelBox: Box;
}
const ICON = {x: 250, tile: 96, hero: 128, labelGap: 12, labelHeight: 32, labelWidth: 150};
const icon = (label: string, cy: number, size: number, glyph?: Glyph): DesktopIcon => ({
  label,
  glyph,
  tile: {x: ICON.x - size / 2, y: cy - size / 2, width: size, height: size},
  labelBox: {x: ICON.x - ICON.labelWidth / 2, y: cy + size / 2 + ICON.labelGap, width: ICON.labelWidth, height: ICON.labelHeight},
});
export const DESKTOP = {
  icons: [icon('Notes', 290, ICON.tile, 'page'), icon('Files', 660, ICON.tile, 'folder'), icon('Projects', 845, ICON.tile, 'grid')],
  hero: icon('Galliani', 475, ICON.hero),
  labelSize: 22,
  heroLabelSize: 24,
  tileRadius: 0.24, // of the tile size
  markSize: 84, // the mark inside the hero tile (R80: at most 320)
  hoverLift: 2, // px (R69)
  window: {x: 960, y: 300, width: 800, height: 460},
  // The cursor's tip enters from below the frame and grabs the hero tile `grab` px from its centre (R68).
  cursorEntry: {x: 820, y: 1140},
  grab: {x: 22, y: 26},
  cursorHeight: 34,
  // The drag arc ends with the tile over the shell line; its apex is `apex` px above the chord (R70).
  dragEnd: {x: 1290, y: 412},
  apex: 120,
};
// The strings drawn outside the terminal besides the captions and `galliacli` (R47, R67).
export const DESKTOP_LABELS = ['Galliani', 'Notes', 'Files', 'Projects'] as const;

// Where the shell caret sits in the desktop window with an empty command: the absorb target (R71).
export const SHELL_CARET = {
  x: DESKTOP.window.x + TERMINAL.border + TERMINAL.pad.side + (1 + TERM.shellPrompt.length + 0.5) * MONO_ADVANCE * TERMINAL.fontSize,
  y: DESKTOP.window.y + TERMINAL.border + TERMINAL.titleBar + TERMINAL.pad.top + TERMINAL.row / 2,
};

// The end card block: the mark, a gap, then the `galliacli` line, centered on the frame (R65).
export const END = {markSize: 240, gap: 36, wordSize: 64, wordLine: 80};

const TOP_CAPTION = {x: 96, y: 56, width: 1728, height: 112, fontSize: 64};

// ---------------------------------------------------------------- the robot (R74-R79)

// The hover-robot of video/src/Robot.tsx: each shape's static attributes, copied verbatim (B-AC24 checks them).
export const ROBOT_SHAPES = {
  thruster: {cx: 0, cy: 44, rx: 14, ry: 5},
  body: {x: -17, y: 14, width: 34, height: 24, rx: 10},
  chest: {cx: 0, cy: 26, r: 4},
  armLeft: {x: -27, y: 18, width: 9, height: 16, rx: 4.5},
  armRight: {x: 18, y: 18, width: 9, height: 16, rx: 4.5},
  antenna: {x1: 0, y1: -30, x2: 0, y2: -46},
  antennaTip: {cx: 0, cy: -49, r: 5},
  head: {x: -30, y: -32, width: 60, height: 46, rx: 16},
  face: {x: -23, y: -25, width: 46, height: 30, rx: 11},
  eyeLeft: {x: -13, width: 8, rx: 4},
  eyeRight: {x: 5, width: 8, rx: 4},
} as const;
// Robot.tsx's viewBox, arm pivots, eye row, rest arm angle and antenna stroke; the two fixed opacities replace its
// thruster flicker and antenna pulse (R75, R77).
export const ROBOT_FRAME = {
  viewBox: {x: -60, y: -70, width: 120, height: 130},
  pivotLeft: {x: -22, y: 18},
  pivotRight: {x: 22, y: 18},
  eyeRow: -10,
  eyeHeight: 10,
  restArm: 12, // degrees: the left arm rests at +12, the right at -12
  // The furthest an arm turns from hanging before the head, drawn above it as in Robot.tsx, covers any of it (R74).
  armReach: 124,
  antennaWidth: 3,
  thrusterOpacity: 0.2,
  antennaTipOpacity: 0.85,
};
export const ROBOT_HEIGHT = 200; // authored px (R74: 180-240)
export const ROBOT_SCALE = ROBOT_HEIGHT / ROBOT_FRAME.viewBox.height;
const robotBox = (x: number, y: number): Box => ({x, y, width: ROBOT_FRAME.viewBox.width * ROBOT_SCALE, height: ROBOT_HEIGHT});
// Act 3: in the margin at the terminal's lower right; the end card: beside the block (R76).
export const ROBOT_PLACE = {
  act3: robotBox(TERMINAL.x + TERMINAL.width + 24, 680), // high enough that `point` aims within armReach + 20°
  end: robotBox(1212, 440),
};
export const ROBOT_BREATH = {px: 2.5, period: 90}; // R77: at most 3 px, a 60-120 frame period
export const ROBOT_BLINKS: readonly number[] = [255, 410, 530, 640, 735, 840]; // 90+ frames apart, never in a gesture
export const BLINK_FRAMES = 6;

// The boxes the robot's gestures aim at, in canvas px (R78).
const rowY = (row: number) => TERMINAL.y + TERMINAL.titleBar + row * TERMINAL.row;
export const TARGETS = {
  prompt: {x: TERMINAL.x + 20, y: TERMINAL.y + TERMINAL.height - 150, width: TERMINAL.width - 40, height: 75},
  plan: {x: TERMINAL.x + TERMINAL.width - 520, y: rowY(0.5), width: 500, height: 6 * TERMINAL.row},
  // Step 2's route line in route-next (R78 glance): transcript row 16 below the content padding.
  route: {x: TERMINAL.x + 20, y: rowY(16) + TERMINAL.border + TERMINAL.pad.top, width: 960, height: TERMINAL.row},
  popup: {x: TERMINAL.x + 20, y: rowY(12), width: 900, height: 9 * TERMINAL.row},
  card: {x: TERMINAL.x + 20, y: TERMINAL.y + TERMINAL.height - 240, width: TERMINAL.width - 40, height: 170},
  cta: {x: 787, y: 362, width: 346, height: 356},
};
export type TargetId = keyof typeof TARGETS;

// Each pose: its legs in frames (out, hold, back; `wave` raises, swings and lowers) and its extent (R78). Angles are
// degrees, eye offsets robot units; negative turns toward the terminal, at the robot's left.
export const POSES = {
  lean: {legs: [8, 10, 8], headTilt: -8, lean: -6, eyeX: -5, eyeY: 3},
  point: {legs: [8, 14, 8]},
  glance: {legs: [6, 12, 6], headTilt: -6, eyeX: -6, eyeY: -3},
  nod: {legs: [8, 6, 8], headTilt: -8, eyeY: 2, headDip: 3}, // headDip: robot units down, the nod's downward cue
  raise: {legs: [9]},
  lower: {legs: [9]},
  cheer: {legs: [9, 6, 9], arm: 112}, // restArm + arm = armReach
  wave: {legs: [8, 10, 8], arm: 112, swing: 20},
} as const;

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

const SHELL_TYPING = typed(TERM.command, 6, 15);
const GOAL_TYPING = typed(GOAL, 3, 36);
// The `@` popup opens on the frame `@` is typed and holds its full list for AT_HOLD frames with nothing else moving
// (the caret blink aside), the one typing pause R52 allows; `sig` then types in fast and narrows it on the frame `g`
// is typed.
const AT_BEFORE = AT_PROMPT.slice(0, AT_PROMPT.indexOf('@') + 1);
const AT_TYPING_BEFORE = typed(AT_BEFORE, 0, 12);
const AT_SIGN = Math.ceil(charTimes(AT_TYPING_BEFORE)[AT_BEFORE.length - 1]);
const AT_HOLD = 24;
const AT_TAIL = AT_SIGN + AT_HOLD;
const AT_TYPING: Typing = {...typed(AT_PROMPT, AT_TAIL, 3), kept: AT_BEFORE.length};
const AT_SIG = Math.ceil(charTimes(AT_TYPING)[AT_PROMPT.length - 1]);
const AT_DONE_AT = AT_SIG + 6;
export const PRESS_Y = 15; // approval-answer: the local frame `y` is pressed

const BEATS_RAW: readonly Omit<CliBeat, 'start'>[] = [
  {id: 'desk-idle', segment: 'Hook', duration: 45, shot: {kind: 'desk'}},
  {id: 'desk-hover', segment: 'Hook', duration: 45, shot: {kind: 'desk'}, cursor: {at: 0, frames: CURSOR_FRAMES}},
  {id: 'desk-drag', segment: 'Hook', duration: 60, shot: {kind: 'desk'}, drag: {at: 0, frames: DRAG_FRAMES}},
  {id: 'desk-drop', segment: 'Hook', duration: 30, shot: {kind: 'desk'}, absorb: {at: 0, frames: ABSORB.frames}},
  {id: 'launch-type', segment: 'Launch', duration: 45, shot: {kind: 'shell', typing: SHELL_TYPING}},
  {
    id: 'launch-expand', segment: 'Launch', duration: 45, shot: {kind: 'terminal', keys: [{at: 0, screen: idle}]},
    expand: {at: 0, frames: EXPAND_FRAMES},
  },
  {
    id: 'goal-type', segment: 'Objective to plan', duration: 60,
    shot: {kind: 'terminal', keys: [{at: 0, screen: {...idle, prompt: idlePrompt(GOAL_TYPING)}}]},
    gesture: {at: 15, pose: 'lean', target: 'prompt'},
  },
  {
    id: 'plan-steps', segment: 'Objective to plan', duration: 60,
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
    gesture: {at: 15, pose: 'point', target: 'plan'},
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
    id: 'route-next', segment: 'Routing', duration: 60,
    shot: {kind: 'terminal', keys: [{at: 0, screen: {
      entries: coded, steps: ['verified', 'verified', 'running', 'pending'], fresh: 1,
      working: {group: 'running', elapsed: 7, cost: 0.0107, step: 3},
      status: {route: ROUTE_CODING, cost: 0.0107, label: 'Working'}, prompt: activePrompt,
    }}]},
    gesture: {at: 15, pose: 'glance', target: 'route'},
  },
  {
    id: 'slash-popup', segment: 'Commands', duration: 60,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: idle},
      {at: 15, screen: {...idle, prompt: idlePrompt(typed('/')), popup: {rows: SLASH_ROWS, selected: 0}}},
      {at: 30, screen: {...idle, prompt: idlePrompt(typed('/')), popup: {rows: SLASH_ROWS, selected: 1}}},
      {at: 40, screen: {...idle, prompt: idlePrompt(typed('/')), popup: {rows: SLASH_ROWS, selected: 2}}},
    ]},
    gesture: {at: 15, pose: 'nod', target: 'popup'},
  },
  {
    id: 'at-file', segment: 'Commands', duration: 75,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: {...idle, prompt: idlePrompt(AT_TYPING_BEFORE)}},
      {at: AT_SIGN, screen: {...idle, prompt: idlePrompt(AT_TYPING_BEFORE), popup: {rows: FILE_ROWS_ALL, selected: 0}}},
      {at: AT_TAIL, screen: {...idle, prompt: idlePrompt(AT_TYPING), popup: {rows: FILE_ROWS_ALL, selected: 0}}},
      {at: AT_SIG, screen: {...idle, prompt: idlePrompt(AT_TYPING), popup: {rows: FILE_ROWS_SIG, selected: 0}}},
      {at: AT_DONE_AT, screen: {...idle, prompt: idlePrompt(typed(AT_DONE))}},
    ]},
  },
  {
    id: 'approval-card', segment: 'Control', duration: 30,
    shot: {kind: 'terminal', keys: [{at: 0, screen: waitingScreen}]},
    card: {at: 0},
  },
  {
    id: 'approval-wait', segment: 'Control', duration: 30,
    shot: {kind: 'terminal', keys: [{at: 0, screen: waitingScreen}]},
    gesture: {at: 0, pose: 'raise', target: 'card'},
  },
  {
    id: 'approval-answer', segment: 'Control', duration: 60,
    shot: {kind: 'terminal', keys: [
      {at: 0, screen: waitingScreen},
      {at: PRESS_Y, screen: {...waitingScreen, approval: {pressed: true}}},
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
    gesture: {at: PRESS_Y, pose: 'lower', target: 'card'},
  },
  {
    id: 'verified-done', segment: 'Close', duration: 60,
    shot: {kind: 'terminal', keys: [{at: 0, screen: {
      entries: [...waiting, E.approved, E.writeOk, E.checked, E.routeText, E.checked, E.result, E.usage],
      steps: ['verified', 'verified', 'verified', 'verified'], fresh: 3, working: null,
      status: {route: ROUTE_TEXT, cost: 0.0108, label: 'Ready'}, prompt: idlePrompt(),
    }}]},
    gesture: {at: 15, pose: 'cheer', target: 'prompt'},
  },
  {id: 'end-card', segment: 'Close', duration: 75, shot: {kind: 'end'}, gesture: {at: 30, pose: 'wave', target: 'cta'}},
  {id: 'end-seam', segment: 'Close', duration: 30, shot: {kind: 'desk'}},
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
const caption = (segment: Segment, text: string, enterFrames: number = CAPTION_ENTER.frames): CliCaption => ({
  segment, text, ...segmentSpan(segment), box: TOP_CAPTION, enterFrames,
});

// Every caption sits in the top band, clear of the desktop, the drag arc, the terminal and the robot (R42). The hook
// caption cuts in on frame 0 (R55); the others rise in as one element (R38).
export const CAPTIONS: readonly CliCaption[] = [
  caption('Hook', 'Galliani now runs in your terminal.', 0),
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
  const kept = typing.kept ?? 0;
  if (kept > 0) return [...Array.from({length: kept}, () => typing.from), ...charTimes({...typing, text: typing.text.slice(kept), kept: 0})];
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
