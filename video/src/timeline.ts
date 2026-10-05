// Everything the showcase shows and when. Frames at 30 fps; edit here to retime.

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export const PROMPT = 'Add email validation to signup.py and cover it with tests';

/** Key moments, in frames. */
export const T = {
  barIn: [0, 22],
  typeStart: 30,
  typeEnd: 116,
  send: 124,
  dock: [128, 166], // the bar glides to the bottom, the message moves up
  cardIn: [156, 180],
  stepsIn: 180, // plan rows appear one after another from here
  routeOpen: [254, 270], // the router weighs the models for the coding step
  routeScan: [272, 292], // a highlight hops across the candidates
  select: 294, // ...and lands on Sonnet 5.5
  mascotIn: [300, 314], // the Claude mascot pops out of the chosen model
  highFive: 326, // the robot and the mascot high-five
  mascotOut: [344, 356],
  routeClose: [352, 370],
  approvalOpen: [410, 426],
  approve: 452,
  approvalClose: [460, 478],
  collapse: [540, 568], // steps fold into a one-line summary
  statsIn: [566, 592], // model, cost, and savings
  fileIn: [584, 616], // the diff
  fadeOut: [740, 758], // the chat fades away
  logoDraw: [750, 772], // the G draws itself around its curve
  logoBar: [768, 778], // then its crossbar slides in
  robotIntoStar: [760, 776], // the robot zips to where the star will be
  robotVanish: [774, 782], // and shrinks into it
  starPop: [778, 792],
  wordmark: [788, 806],
  end: [830, 848],
} as const;

export const DURATION = T.end[1];

export interface Step {
  title: string;
  /** Public detail shown while and after the step runs. */
  meta: string;
  /** Shown instead of meta until a given frame (e.g. before routing or approval). */
  metaBefore?: {until: number; text: string};
  start: number;
  end: number;
}

export const STEPS: Step[] = [
  {title: 'Read signup.py', meta: 'read_file', start: 222, end: 250},
  {title: 'Write the validation', meta: 'Sonnet 5.5', metaBefore: {until: T.select, text: 'routing…'}, start: 250, end: 404},
  {
    title: 'Save signup.py and tests',
    meta: 'write_file · approved',
    metaBefore: {until: T.approve, text: 'write_file · needs approval'},
    start: 404,
    end: 490,
  },
  {title: 'Run the tests', meta: 'run_tests · 14 passed', metaBefore: {until: 526, text: 'run_tests'}, start: 490, end: 534},
];

/** Index of the step that writes files and needs approval, and of the step the router assigns. */
export const APPROVAL_STEP = 2;
export const ROUTED_STEP = 1;

/** Models the router weighs for the coding step. Prices are USD per million tokens (input / output). */
export const MODELS = [
  {name: 'Haiku 4.5', note: 'fast', price: [1, 5]},
  {name: 'Sonnet 5.5', note: 'best for code', price: [2, 10]},
  {name: 'Opus 5.5', note: 'most capable', price: [4, 20]},
] as const;
export const CHOSEN = 1; // Sonnet 5.5
export const ROUTE_REASON = 'Best for code at half the cost of Opus';
/** The order the scan highlight visits the candidates before settling. */
export const SCAN_ORDER = [0, 2, 1];

/** Illustrative token use per model call, priced with MODELS. */
export const USAGE = [
  {label: 'plan', model: 0, input: 6000, output: 1000, during: [T.stepsIn, STEPS[0].start]},
  {label: 'code', model: CHOSEN, input: 12000, output: 2400, during: [T.select + 6, STEPS[ROUTED_STEP].end]},
] as const;

const price = (model: number, input: number, output: number) =>
  (input * MODELS[model].price[0] + output * MODELS[model].price[1]) / 1_000_000;

export const COST = USAGE.reduce((sum, u) => sum + price(u.model, u.input, u.output), 0);
/** What the same calls would cost if every one ran on the most capable model. */
export const COST_ALL_OPUS = USAGE.reduce((sum, u) => sum + price(2, u.input, u.output), 0);
export const SAVED = COST_ALL_OPUS - COST;

/** Running cost shown in the header at a given frame. */
export function costAt(frame: number): number {
  return USAGE.reduce((sum, u) => {
    const [a, b] = u.during;
    const t = Math.min(1, Math.max(0, (frame - a) / (b - a)));
    return sum + price(u.model, u.input, u.output) * t;
  }, 0);
}

/** Model shown in the header at a given frame. */
export function modelAt(frame: number): string {
  return frame < T.select ? MODELS[0].name : MODELS[CHOSEN].name;
}

export const RESULT_FILE = 'signup.py';
export const RESULT_DIFF = '+18 −2';
export const RESULT_LINES = [
  'def is_valid_email(value: str) -> bool:',
  '    return EMAIL_RE.fullmatch(value) is not None',
  'if not is_valid_email(form.email):',
  '    raise ValidationError("Enter a valid email")',
];
export const RESULT_FOOTER = 'tests/test_signup.py  +31  ·  14 passed';

export const RENDER = {
  compositionId: 'GallianiShowcase',
  outputPath: 'out/galliani-showcase.mp4',
};

/** Where the robot is going: its center, in scene pixels, and where its eyes look (-1..1). */
export interface RobotKey {
  f: number;
  x: number;
  y: number;
  look?: [number, number];
  /** Move into this key at constant speed instead of easing (used to trail the caret). */
  linear?: boolean;
  /** Frames the move into this key takes; the robot then idles until the key's frame. */
  travel?: number;
}

/** Default move time: quick darts, then idle. */
export const ROBOT_TRAVEL = 13;

const CARET_X0 = 446; // first character in the chat bar
const CHAR_PX = 15.2; // average character width at 31px

/** The robot trails the caret while the prompt is typed. */
const followCaret: RobotKey[] = [56, 70, 84, 98, 110].map((f) => ({
  f,
  x: CARET_X0 + ((f - T.typeStart) / (T.typeEnd - T.typeStart)) * PROMPT.length * CHAR_PX,
  y: 466,
  look: [0.3, 1] as [number, number],
  linear: true,
}));

/** The end-card mark: a square box, and where the G and star sit inside it (fractions of the box). */
export const MARK = {size: 260, top: 300, gCenter: [0.55, 0.5], star: [0.775, 0.258]} as const;
const STAR = {
  x: WIDTH / 2 + (MARK.star[0] - 0.5) * MARK.size,
  y: MARK.top + MARK.star[1] * MARK.size,
};

/** Agent card geometry, shared with the scene so the robot and mascot land on the right spots. */
export const CARD = {
  top: 300,
  rowsTop: 388, // after padding, header, and gap
  row: 62,
  routerTop: 650, // the router panel opens below the four rows
  chipTop: 720, // top edge of the model chips
  chipCenters: [628, 960, 1292], // x center of each model chip
};

const ROW_Y = (i: number) => CARD.rowsTop + 31 + i * CARD.row; // center of plan row i
const BESIDE_CARD = 356;

/** Where the Claude mascot stands: on top of the chosen chip. */
export const MASCOT = {x: CARD.chipCenters[CHOSEN], y: CARD.chipTop - 34};
/** Where the two raised hands meet (the robot comes in from the mascot's left). */
export const HIGH_FIVE_AT = {x: MASCOT.x - 84, y: MASCOT.y - 30};

export const ROBOT_KEYS: RobotKey[] = [
  {f: 0, x: -140, y: 380, look: [1, 0]},
  {f: 34, x: 330, y: 540, look: [1, 0.2], travel: 26}, // arrives beside the empty bar
  {f: 48, x: 446, y: 466, look: [0.2, 1]}, // hops on top of it
  ...followCaret,
  {f: 119, x: 1458, y: 462, look: [0, 1]}, // over the send button
  {f: 130, x: 1458, y: 462, look: [0, 1]},
  {f: 154, x: 1180, y: 360, look: [-0.6, -0.6]}, // follows the message up
  {f: 188, x: 1440, y: 264, look: [-0.5, 1]}, // perches on the agent card
  {f: 210, x: 1440, y: 264, look: [-0.8, 0.8]},
  {f: 226, x: BESIDE_CARD, y: ROW_Y(0), look: [1, 0]}, // watches each step
  {f: 250, x: BESIDE_CARD, y: ROW_Y(0), look: [1, 0.1]},
  {f: 262, x: BESIDE_CARD, y: ROW_Y(1), look: [1, 0]},
  {f: 280, x: BESIDE_CARD, y: CARD.chipTop, look: [1, 0.2]}, // watches the router
  {f: 300, x: BESIDE_CARD, y: CARD.chipTop, look: [1, 0]},
  {f: 314, x: MASCOT.x - 165, y: MASCOT.y - 14, look: [1, 0], travel: 12}, // meets the mascot
  {f: 318, x: MASCOT.x - 165, y: MASCOT.y - 14, look: [1, -0.2]},
  {f: 326, x: MASCOT.x - 128, y: MASCOT.y - 16, look: [1, -0.3], travel: 8}, // high five
  {f: 340, x: MASCOT.x - 165, y: MASCOT.y - 14, look: [1, 0]},
  {f: 352, x: MASCOT.x - 165, y: MASCOT.y - 14, look: [0.6, 0.6]},
  {f: 366, x: BESIDE_CARD, y: ROW_Y(1), look: [1, 0]},
  {f: 404, x: BESIDE_CARD, y: ROW_Y(1), look: [1, 0.1]},
  {f: 416, x: BESIDE_CARD, y: ROW_Y(2), look: [1, 0]},
  {f: 432, x: 1580, y: 692, look: [-1, 0]}, // eyes the approval
  {f: 458, x: 1580, y: 692, look: [-1, 0.2]},
  {f: 472, x: BESIDE_CARD, y: ROW_Y(2), look: [1, 0]},
  {f: 490, x: BESIDE_CARD, y: ROW_Y(2), look: [1, 0]},
  {f: 502, x: BESIDE_CARD, y: ROW_Y(3), look: [1, 0]},
  {f: 534, x: BESIDE_CARD, y: ROW_Y(3), look: [1, 0]},
  {f: 558, x: BESIDE_CARD, y: CARD.rowsTop + 26, look: [1, -0.2]}, // done: cheers beside the summary
  {f: 590, x: BESIDE_CARD, y: CARD.rowsTop + 26, look: [0.6, -0.4]},
  {f: 614, x: 900, y: 276, look: [1, 0.3]}, // arcs over the card
  {f: 644, x: 1584, y: 640, look: [-1, 0.2]}, // reads the result
  {f: 706, x: 1584, y: 690, look: [-1, 0.4]},
  {f: 760, x: 1584, y: 690, look: [-1, -0.4]},
  {f: 776, x: STAR.x, y: STAR.y, look: [0, 0], travel: 16}, // becomes the logo's star
  {f: 848, x: STAR.x, y: STAR.y, look: [0, 0]},
];

/** Little hops (frame where the hop starts). */
export const ROBOT_HOPS = [44, T.send - 2, T.highFive - 4, T.approve - 2, 560, 574];
/** A happy wiggle with arms up when the task is done. */
export const ROBOT_CHEER: [number, number] = [558, 588];
/** The robot's right arm (and the mascot's left) goes up for the high five (start, end). */
export const HIGH_FIVE_ARM: [number, number] = [T.highFive - 12, T.highFive + 8];
/** Blinks (frame where the blink starts). */
export const ROBOT_BLINKS = [64, 140, 205, 290, 370, 440, 520, 620, 700];

/** Camera: at frame f, scene point (x, y) sits at the center of the screen, magnified by `scale`. */
export interface CameraKey {
  f: number;
  scale: number;
  x: number;
  y: number;
}

// Impact zooms are two keys a few frames apart (a fast snap); the smooth curve then lets them settle.
export const CAMERA_KEYS: CameraKey[] = [
  {f: 0, scale: 1, x: 960, y: 540},
  {f: 30, scale: 1, x: 960, y: 540},
  {f: 38, scale: 1.42, x: 690, y: 548}, // impact: typing starts
  {f: 116, scale: 1.46, x: 1240, y: 548}, // follows the caret
  {f: 124, scale: 1.5, x: 1250, y: 550}, // push on send
  {f: 136, scale: 1, x: 960, y: 540}, // snap back out as the chat docks
  {f: 180, scale: 1, x: 960, y: 540},
  {f: 188, scale: 1.34, x: 900, y: 470}, // impact: the plan loads
  {f: 222, scale: 1.34, x: 900, y: 470},
  {f: 227, scale: 1.41, x: 900, y: 470}, // a push as the first step starts
  {f: 250, scale: 1.36, x: 900, y: 480},
  {f: 272, scale: 1.32, x: 960, y: 640}, // down to the router
  {f: 292, scale: 1.32, x: 960, y: 650},
  {f: 298, scale: 1.48, x: 950, y: 690}, // impact: Sonnet 5.5 chosen, the mascot appears
  {f: 340, scale: 1.5, x: 940, y: 680}, // slow push through the high five
  {f: 358, scale: 1.34, x: 940, y: 560},
  {f: 404, scale: 1.34, x: 930, y: 540},
  {f: 409, scale: 1.41, x: 930, y: 545}, // push as the save starts
  {f: 430, scale: 1.38, x: 1100, y: 640}, // lean into the approval
  {f: 458, scale: 1.38, x: 1100, y: 640},
  {f: 476, scale: 1.36, x: 920, y: 560},
  {f: 490, scale: 1.36, x: 910, y: 560},
  {f: 495, scale: 1.43, x: 900, y: 580}, // push as the tests run
  {f: 534, scale: 1.37, x: 900, y: 580},
  {f: 560, scale: 1.12, x: 960, y: 520}, // done: pull out
  {f: 604, scale: 1.16, x: 980, y: 600}, // in on cost and the diff
  {f: 704, scale: 1.2, x: 1000, y: 640},
  {f: 748, scale: 1, x: 960, y: 540}, // fully out before the logo
  {f: 848, scale: 1, x: 960, y: 540}, // the logo reveal itself is not zoomed
];
