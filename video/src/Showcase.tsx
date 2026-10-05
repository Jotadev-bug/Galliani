// A single continuous shot: the chat bar appears, a prompt is typed, and the agent works it to done.
// Greyscale only, no cuts; every movement is a smooth ease between two frames.
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, random, staticFile, useCurrentFrame} from 'remotion';
import {HighFiveSpark, Mascot} from './Mascot.tsx';
import {Robot} from './Robot.tsx';
import {cameraAt} from './camera.ts';
import {
  CARD,
  HIGH_FIVE_AT,
  CHOSEN,
  COST,
  COST_ALL_OPUS,
  FPS,
  HEIGHT,
  MARK,
  MODELS,
  PROMPT,
  RESULT_DIFF,
  RESULT_FILE,
  RESULT_FOOTER,
  RESULT_LINES,
  ROUTE_REASON,
  SAVED,
  SCAN_ORDER,
  STEPS,
  T,
  USAGE,
  WIDTH,
  costAt,
  modelAt,
} from './timeline.ts';

const C = {
  bg: '#0A0A0B',
  surface: '#141416',
  raised: '#1C1C1F',
  border: '#2A2A2E',
  text: '#EDEDEF',
  soft: '#C9C9CE',
  muted: '#8B8B92',
  dim: '#4D4D53',
};
const SANS = '"Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif';
const MONO = '"Cascadia Mono", Consolas, "SF Mono", Menlo, monospace';

const COLUMN = {x: (WIDTH - 1100) / 2, width: 1100};
const BAR_HEIGHT = 100;
const BAR_CENTER_TOP = 500;
const BAR_DOCK_TOP = HEIGHT - 64 - BAR_HEIGHT;
const CARD_TOP = CARD.top;

const smoothEase = Easing.bezier(0.45, 0, 0.15, 1);

/** Smooth 0 -> 1 between two frames. */
function ease(frame: number, start: number, end: number): number {
  return interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: smoothEase,
  });
}

const mix = (a: number, b: number, t: number) => a + (b - a) * t;

/** Frame at which each prompt character appears: steady typing with a little human jitter. */
const CHAR_TIMES = Array.from(PROMPT, (_, i) => {
  const step = (T.typeEnd - T.typeStart) / PROMPT.length;
  return T.typeStart + i * step + (random(`k${i}`) - 0.5) * step * 0.8;
});

function typedText(frame: number): string {
  const count = CHAR_TIMES.filter((time) => time <= frame).length;
  return PROMPT.slice(0, count);
}

const LOGO = staticFile('galliani-mark.png');

const Logo: React.FC<{size: number}> = ({size}) => <Img src={LOGO} style={{width: size, height: size, display: 'block'}} />;

const SendIcon: React.FC<{color: string}> = ({color}) => (
  <svg width={30} height={30} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 19V5M5 12l7-7 7 7" />
  </svg>
);

const Spinner: React.FC<{frame: number; size: number}> = ({frame, size}) => (
  <svg width={size} height={size} viewBox="0 0 32 32">
    <circle cx={16} cy={16} r={12} fill="none" stroke={C.border} strokeWidth={3.5} />
    <circle
      cx={16}
      cy={16}
      r={12}
      fill="none"
      stroke={C.text}
      strokeWidth={3.5}
      strokeLinecap="round"
      strokeDasharray="20 100"
      transform={`rotate(${frame * 11} 16 16)`}
    />
  </svg>
);

const Check: React.FC<{size: number; t?: number}> = ({size, t = 1}) => (
  <svg width={size} height={size} viewBox="0 0 32 32">
    <circle cx={16} cy={16} r={14} fill={C.text} opacity={t} />
    <path
      d="M10 16.5l4 4 8-8.5"
      fill="none"
      stroke={C.bg}
      strokeWidth={3.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={20}
      strokeDashoffset={20 * (1 - t)}
    />
  </svg>
);

const Pending: React.FC<{size: number}> = ({size}) => (
  <svg width={size} height={size} viewBox="0 0 32 32">
    <circle cx={16} cy={16} r={12} fill="none" stroke={C.dim} strokeWidth={3} />
  </svg>
);

const ChatBar: React.FC<{frame: number}> = ({frame}) => {
  const appear = ease(frame, T.barIn[0], T.barIn[1]);
  const dock = ease(frame, T.dock[0], T.dock[1]);
  const top = mix(BAR_CENTER_TOP + 30 * (1 - appear), BAR_DOCK_TOP, dock);
  const sent = frame >= T.send;
  const text = sent ? '' : typedText(frame);
  const typing = frame >= T.typeStart && frame < T.typeEnd + 4;
  const caretOn = !sent && (typing || Math.floor(frame / 15) % 2 === 0);
  const press = 1 - 0.08 * (ease(frame, T.send - 4, T.send) - ease(frame, T.send, T.send + 6));
  const filled = text.length > 0;
  const textOpacity = 1 - ease(frame, T.send, T.send + 6);

  return (
    <div
      style={{
        position: 'absolute',
        left: COLUMN.x,
        top,
        width: COLUMN.width,
        height: BAR_HEIGHT,
        borderRadius: 28,
        background: C.surface,
        border: `2px solid ${C.border}`,
        opacity: appear,
        display: 'flex',
        alignItems: 'center',
        padding: '0 22px 0 36px',
        boxSizing: 'border-box',
        boxShadow: '0 30px 80px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{flex: 1, fontSize: 31, fontFamily: SANS, color: C.text, whiteSpace: 'nowrap', overflow: 'hidden'}}>
        {text ? (
          <span style={{opacity: textOpacity}}>{text}</span>
        ) : (
          <span style={{color: C.dim}}>Ask Galliani to do something…</span>
        )}
        <span
          style={{
            display: 'inline-block',
            width: 3,
            height: 36,
            marginLeft: 3,
            verticalAlign: 'middle',
            background: C.text,
            opacity: caretOn ? 1 : 0,
          }}
        />
      </div>
      <div
        style={{
          width: 60,
          height: 60,
          borderRadius: 30,
          background: filled ? C.text : C.raised,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transform: `scale(${press})`,
        }}
      >
        <SendIcon color={filled ? C.bg : C.dim} />
      </div>
    </div>
  );
};

const Greeting: React.FC<{frame: number}> = ({frame}) => {
  const appear = ease(frame, 6, 30);
  const leave = ease(frame, T.dock[0], T.dock[0] + 18);
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        width: WIDTH,
        top: 240,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 22,
        opacity: appear * (1 - leave),
        transform: `translateY(${mix(20, 0, appear) - 40 * leave}px)`,
        fontFamily: SANS,
      }}
    >
      <Logo size={76} />
      <div style={{fontSize: 50, fontWeight: 600, color: C.text, letterSpacing: '-0.02em'}}>What should Galliani do?</div>
    </div>
  );
};

const UserMessage: React.FC<{frame: number}> = ({frame}) => {
  const t = ease(frame, T.dock[0] + 6, T.dock[1]);
  return (
    <div
      style={{
        position: 'absolute',
        right: COLUMN.x,
        top: 120 + 40 * (1 - t),
        maxWidth: 820,
        padding: '22px 30px',
        borderRadius: 24,
        background: C.raised,
        color: C.text,
        fontFamily: SANS,
        fontSize: 30,
        lineHeight: 1.35,
        opacity: t,
      }}
    >
      {PROMPT}
    </div>
  );
};

const ROW = 62;

const StepRow: React.FC<{frame: number; index: number}> = ({frame, index}) => {
  const step = STEPS[index];
  const appearAt = T.stepsIn + index * 7;
  const appear = ease(frame, appearAt, appearAt + 14);
  const active = frame >= step.start && frame < step.end;
  const done = frame >= step.end;
  const metaIn = ease(frame, step.start, step.start + 10);
  return (
    <div
      style={{
        height: ROW,
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        opacity: appear,
        transform: `translateX(${mix(-16, 0, appear)}px)`,
      }}
    >
      <div style={{width: 32, height: 32}}>
        {done ? <Check size={32} t={ease(frame, step.end, step.end + 8)} /> : active ? <Spinner frame={frame} size={32} /> : <Pending size={32} />}
      </div>
      <div style={{flex: 1, fontSize: 29, color: done || active ? C.text : C.muted, fontWeight: active ? 600 : 400}}>
        {step.title}
      </div>
      <div style={{fontFamily: MONO, fontSize: 22, color: C.muted, opacity: metaIn}}>
        {step.metaBefore && frame < step.metaBefore.until ? step.metaBefore.text : step.meta}
      </div>
    </div>
  );
};

const Approval: React.FC<{frame: number}> = ({frame}) => {
  const pressed = ease(frame, T.approve - 3, T.approve + 3);
  const scale = 1 - 0.05 * (ease(frame, T.approve - 3, T.approve) - ease(frame, T.approve, T.approve + 6));
  return (
    <div
      style={{
        marginTop: 14,
        height: 84,
        borderRadius: 18,
        border: `2px solid ${C.border}`,
        background: C.raised,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px 0 26px',
        gap: 14,
        boxSizing: 'border-box',
      }}
    >
      <div style={{flex: 1, fontSize: 27, color: C.text}}>
        Allow writing <span style={{fontFamily: MONO, color: C.soft}}>signup.py</span> and its tests?
      </div>
      <div style={{padding: '12px 26px', borderRadius: 12, border: `2px solid ${C.border}`, color: C.muted, fontSize: 24}}>
        Deny
      </div>
      <div
        style={{
          padding: '12px 26px',
          borderRadius: 12,
          background: pressed > 0.5 ? C.soft : C.text,
          color: C.bg,
          fontSize: 24,
          fontWeight: 600,
          transform: `scale(${scale})`,
        }}
      >
        Approve
      </div>
    </div>
  );
};

const STATUS = (frame: number) => (frame < STEPS[0].start ? 'Planning…' : frame < STEPS[STEPS.length - 1].end ? 'Working…' : 'Done');

const AgentCard: React.FC<{frame: number}> = ({frame}) => {
  const appear = ease(frame, T.cardIn[0], T.cardIn[1]);
  const rowsVisible = STEPS.reduce((sum, _, i) => sum + ease(frame, T.stepsIn + i * 7, T.stepsIn + i * 7 + 14), 0);
  const collapse = ease(frame, T.collapse[0], T.collapse[1]);
  const approval = ease(frame, T.approvalOpen[0], T.approvalOpen[1]) * (1 - ease(frame, T.approvalClose[0], T.approvalClose[1]));
  const route = ease(frame, T.routeOpen[0], T.routeOpen[1]) * (1 - ease(frame, T.routeClose[0], T.routeClose[1]));
  const statsIn = ease(frame, T.statsIn[0], T.statsIn[1]);
  const fileIn = ease(frame, T.fileIn[0], T.fileIn[1]);
  const endFrame = STEPS[STEPS.length - 1].end;
  const elapsed = (Math.min(frame, endFrame) - T.cardIn[0]) / FPS;
  const status = STATUS(frame);

  return (
    <div
      style={{
        position: 'absolute',
        left: COLUMN.x,
        top: CARD_TOP + 24 * (1 - appear),
        width: COLUMN.width,
        opacity: appear,
        borderRadius: 26,
        border: `2px solid ${C.border}`,
        background: C.surface,
        padding: '26px 36px',
        boxSizing: 'border-box',
        fontFamily: SANS,
      }}
    >
      <div style={{display: 'flex', alignItems: 'center', gap: 16, height: 48}}>
        <Logo size={34} />
        <div style={{fontSize: 29, fontWeight: 600, color: C.text}}>Galliani</div>
        <div style={{fontSize: 26, color: C.muted}}>{status}</div>
        <div style={{flex: 1}} />
        <ModelChip frame={frame} />
        <div style={{fontFamily: MONO, fontSize: 22, color: C.soft, width: 92, textAlign: 'right'}}>{`$${costAt(frame).toFixed(3)}`}</div>
        <div style={{fontFamily: MONO, fontSize: 22, color: C.muted, width: 70, textAlign: 'right'}}>{`${Math.max(0, elapsed).toFixed(1)}s`}</div>
      </div>
      <div style={{height: 14}} />
      <div style={{height: rowsVisible * ROW * (1 - collapse), overflow: 'hidden', opacity: 1 - collapse}}>
        {STEPS.map((_, i) => (
          <StepRow key={i} frame={frame} index={i} />
        ))}
      </div>
      <div style={{height: route * 172, overflow: 'hidden', opacity: route}}>
        <Router frame={frame} />
      </div>
      <div style={{height: approval * 98, overflow: 'hidden', opacity: approval}}>
        <Approval frame={frame} />
      </div>
      <div
        style={{
          height: 52 * collapse,
          overflow: 'hidden',
          opacity: collapse,
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          fontSize: 27,
          color: C.soft,
        }}
      >
        <Check size={30} />
        {`${STEPS.length} steps · verified · 2 files changed`}
      </div>
      <div style={{height: statsIn * 128, overflow: 'hidden', opacity: statsIn}}>
        <Stats frame={frame} />
      </div>
      <div style={{height: fileIn * 290, overflow: 'hidden', opacity: fileIn}}>
        <DiffCard frame={frame} />
      </div>
    </div>
  );
};

/** The model currently working, as a pill in the card header. It pulses when the router switches it. */
const ModelChip: React.FC<{frame: number}> = ({frame}) => {
  const pulse = ease(frame, T.select, T.select + 4) * (1 - ease(frame, T.select + 4, T.select + 14));
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '6px 16px',
        borderRadius: 999,
        border: `2px solid ${pulse > 0.05 ? C.text : C.border}`,
        fontSize: 21,
        color: C.text,
        transform: `scale(${1 + 0.08 * pulse})`,
      }}
    >
      <div style={{width: 9, height: 9, borderRadius: 5, background: C.soft}} />
      {modelAt(frame)}
    </div>
  );
};

/** The router weighs the candidate models for the coding step and settles on one. */
const Router: React.FC<{frame: number}> = ({frame}) => {
  const [a, b] = T.routeScan;
  const hop = (b - a) / SCAN_ORDER.length;
  const scanning = frame >= a && frame < T.select;
  const scanIndex = SCAN_ORDER[Math.min(SCAN_ORDER.length - 1, Math.floor((frame - a) / hop))];
  const chosen = frame >= T.select;
  const reason = ease(frame, T.select + 2, T.select + 12);
  return (
    <div
      style={{
        marginTop: 14,
        height: 158,
        borderRadius: 18,
        border: `2px solid ${C.border}`,
        background: C.raised,
        padding: '18px 24px',
        boxSizing: 'border-box',
      }}
    >
      <div style={{display: 'flex', alignItems: 'center', gap: 14, height: 36}}>
        <div style={{fontSize: 24, fontWeight: 600, color: C.text}}>Routing</div>
        <div style={{fontSize: 20, color: C.muted, border: `2px solid ${C.border}`, borderRadius: 999, padding: '2px 12px'}}>coding task</div>
        <div style={{flex: 1}} />
        <div style={{fontSize: 21, color: C.soft, opacity: reason, transform: `translateX(${mix(12, 0, reason)}px)`}}>{ROUTE_REASON}</div>
      </div>
      <div style={{display: 'flex', gap: 16, marginTop: 16}}>
        {MODELS.map((model, i) => {
          const picked = chosen && i === CHOSEN;
          const lit = scanning && i === scanIndex;
          const fill = picked ? ease(frame, T.select, T.select + 6) : 0;
          const pop = picked ? ease(frame, T.select, T.select + 4) - ease(frame, T.select + 4, T.select + 12) : 0;
          return (
            <div
              key={model.name}
              style={{
                flex: 1,
                height: 70,
                borderRadius: 14,
                border: `2px solid ${lit || picked ? C.text : C.border}`,
                background: fill > 0.5 ? C.text : C.surface,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                padding: '0 18px',
                boxSizing: 'border-box',
                opacity: chosen && !picked ? 0.45 : 1,
                transform: `scale(${1 + 0.04 * pop})`,
              }}
            >
              <div style={{fontSize: 25, fontWeight: 600, color: fill > 0.5 ? C.bg : C.text}}>{model.name}</div>
              <div style={{fontSize: 19, color: fill > 0.5 ? C.raised : C.muted}}>
                {`${model.note} · $${model.price[0]} / $${model.price[1]}`}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const money = (value: number) => `$${value.toFixed(3)}`;

/** Model, cost, and savings: the numbers Galliani puts front and center when a task finishes. */
const Stats: React.FC<{frame: number}> = ({frame}) => {
  const count = ease(frame, T.statsIn[0] + 4, T.statsIn[1] + 14);
  const percent = Math.round((SAVED / COST_ALL_OPUS) * 100);
  const tiles = [
    {label: 'Model', value: MODELS[CHOSEN].name, sub: `planned on ${MODELS[USAGE[0].model].name}`},
    {label: 'Cost', value: money(COST * count), sub: `${USAGE.length} model calls`},
    {label: 'Saved', value: money(SAVED * count), sub: `${percent}% vs. Opus 5.5 only`},
  ];
  return (
    <div style={{display: 'flex', gap: 16, marginTop: 16}}>
      {tiles.map((tile, i) => {
        const t = ease(frame, T.statsIn[0] + i * 5, T.statsIn[0] + i * 5 + 14);
        return (
          <div
            key={tile.label}
            style={{
              flex: 1,
              height: 112,
              borderRadius: 16,
              border: `2px solid ${C.border}`,
              background: C.raised,
              padding: '14px 22px',
              boxSizing: 'border-box',
              opacity: t,
              transform: `translateY(${mix(14, 0, t)}px)`,
            }}
          >
            <div style={{fontSize: 19, color: C.muted}}>{tile.label}</div>
            <div style={{fontSize: 34, fontWeight: 600, color: C.text, lineHeight: '44px'}}>{tile.value}</div>
            <div style={{fontSize: 18, color: C.muted}}>{tile.sub}</div>
          </div>
        );
      })}
    </div>
  );
};

const DiffCard: React.FC<{frame: number}> = ({frame}) => (
  <div style={{marginTop: 20, borderRadius: 18, border: `2px solid ${C.border}`, background: C.bg, padding: '18px 26px'}}>
    <div style={{display: 'flex', alignItems: 'center', gap: 14, height: 40, marginBottom: 8}}>
      <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke={C.muted} strokeWidth={2} strokeLinejoin="round">
        <path d="M14 3H6v18h12V7z M14 3v4h4" />
      </svg>
      <div style={{fontFamily: MONO, fontSize: 25, color: C.text}}>{RESULT_FILE}</div>
      <div style={{flex: 1}} />
      <div style={{fontFamily: MONO, fontSize: 22, color: C.soft}}>{RESULT_DIFF}</div>
    </div>
    {RESULT_LINES.map((line, i) => {
      const at = T.fileIn[0] + 14 + i * 5;
      const t = ease(frame, at, at + 12);
      return (
        <div
          key={line}
          style={{
            display: 'flex',
            gap: 18,
            fontFamily: MONO,
            fontSize: 22,
            lineHeight: '36px',
            color: C.soft,
            whiteSpace: 'pre',
            opacity: t,
            transform: `translateX(${mix(-10, 0, t)}px)`,
          }}
        >
          <span style={{color: C.dim}}>+</span>
          {line}
        </div>
      );
    })}
    <div style={{marginTop: 8, fontFamily: MONO, fontSize: 20, color: C.muted, opacity: ease(frame, T.fileIn[1], T.fileIn[1] + 12)}}>
      {RESULT_FOOTER}
    </div>
  </div>
);

const MARK_G = staticFile('galliani-mark-g.png');
const MARK_STAR = staticFile('galliani-mark-star.png');

/** Region of the G's crossbar left of the curve, as % of the mark box: top, right, bottom, left. */
const BAR = {top: 44, right: 19, bottom: 37.5, left: 40.5};
const ARC_START = 16; // degrees clockwise from 12 o'clock: the G's top tip
const ARC_SWEEP = 330; // counterclockwise, around to the crossbar

/** The logo builds itself: the G draws around its curve, the crossbar slides in, the star pops. */
const EndCard: React.FC<{frame: number}> = ({frame}) => {
  const draw = ease(frame, T.logoDraw[0], T.logoDraw[1]) * ARC_SWEEP;
  const bar = ease(frame, T.logoBar[0], T.logoBar[1]);
  const star = interpolate(frame, T.starPop, [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(2.2)),
  });
  const flash = ease(frame, T.starPop[0], T.starPop[0] + 4) * (1 - ease(frame, T.starPop[0] + 4, T.starPop[1] + 6));
  const twinkle = frame > T.starPop[1] ? 1 + 0.06 * Math.sin((frame - T.starPop[1]) / 5) : 1;
  const word = ease(frame, T.wordmark[0], T.wordmark[1]);
  const out = 1 - ease(frame, T.end[0], T.end[1]);
  const [gx, gy] = MARK.gCenter;
  const [sx, sy] = MARK.star;
  // Reveal counterclockwise from the top tip: a conic sector that ends at the tip and grows backwards.
  const arcMask = `conic-gradient(from ${ARC_START - draw}deg at ${gx * 100}% ${gy * 100}%, #000 0deg, #000 ${draw}deg, transparent ${draw + 3}deg)`;
  // The crossbar is cut out of the arc layer (it sits near the center, where angles mean little)...
  const notch = `polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${BAR.left}% ${BAR.top}%, ${100 - BAR.right}% ${BAR.top}%, ${100 - BAR.right}% ${100 - BAR.bottom}%, ${BAR.left}% ${100 - BAR.bottom}%, ${BAR.left}% ${BAR.top}%)`;
  // ...and slides in from the curve toward the center.
  const barLeft = mix(100 - BAR.right, BAR.left, bar);
  // Overlap the arc layer by a little so no seam shows where the two clips meet.
  const barClip = `inset(${BAR.top}% ${BAR.right - 1.5}% ${BAR.bottom}% ${barLeft}%)`;
  const built = frame >= Math.max(T.logoDraw[1], T.logoBar[1]);
  const box: React.CSSProperties = {position: 'absolute', inset: 0, width: '100%', height: '100%'};

  return (
    <div style={{position: 'absolute', inset: 0, opacity: out, fontFamily: SANS}}>
      <div style={{position: 'absolute', left: (WIDTH - MARK.size) / 2, top: MARK.top, width: MARK.size, height: MARK.size}}>
        {built ? (
          <Img src={MARK_G} style={box} />
        ) : (
          <>
            <Img src={MARK_G} style={{...box, maskImage: arcMask, WebkitMaskImage: arcMask, clipPath: notch}} />
            <Img src={MARK_G} style={{...box, clipPath: barClip, opacity: bar > 0 ? 1 : 0}} />
          </>
        )}
        <div
          style={{
            position: 'absolute',
            left: `${sx * 100}%`,
            top: `${sy * 100}%`,
            width: 140,
            height: 140,
            marginLeft: -70,
            marginTop: -70,
            borderRadius: 70,
            background: 'radial-gradient(circle, rgba(255,255,255,0.55) 0%, transparent 65%)',
            opacity: flash,
            transform: `scale(${mix(0.4, 1.4, flash)})`,
          }}
        />
        <Img
          src={MARK_STAR}
          style={{
            ...box,
            transformOrigin: `${sx * 100}% ${sy * 100}%`,
            transform: `scale(${Math.max(0, star) * twinkle}) rotate(${mix(-90, 0, Math.min(1, star))}deg)`,
          }}
        />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          width: WIDTH,
          top: MARK.top + MARK.size + 34,
          textAlign: 'center',
          fontSize: 60,
          fontWeight: 600,
          color: C.text,
          letterSpacing: '-0.02em',
          opacity: word,
          transform: `translateY(${mix(16, 0, word)}px)`,
        }}
      >
        Galliani
      </div>
    </div>
  );
};

export const Showcase: React.FC = () => {
  const frame = useCurrentFrame();
  // The camera eases between focus points (see CAMERA_KEYS) instead of cutting.
  const cam = cameraAt(frame);
  const fade = 1 - ease(frame, T.fadeOut[0], T.fadeOut[1]);
  const end = 1 - ease(frame, T.end[0], T.end[1]);
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <AbsoluteFill
        style={{
          background: 'radial-gradient(ellipse at 50% 40%, rgba(255,255,255,0.045) 0%, transparent 60%)',
        }}
      />
      <AbsoluteFill
        style={{
          transformOrigin: '0 0',
          transform: `translate(${WIDTH / 2}px, ${HEIGHT / 2}px) scale(${cam.scale}) translate(${-cam.x}px, ${-cam.y}px)`,
        }}
      >
        <AbsoluteFill style={{opacity: fade}}>
          <Greeting frame={frame} />
          {frame >= T.dock[0] ? <UserMessage frame={frame} /> : null}
          {frame >= T.cardIn[0] ? <AgentCard frame={frame} /> : null}
          <ChatBar frame={frame} />
          <Mascot frame={frame} />
          <HighFiveSpark frame={frame} x={HIGH_FIVE_AT.x} y={HIGH_FIVE_AT.y} />
        </AbsoluteFill>
        {frame >= T.logoDraw[0] ? <EndCard frame={frame} /> : null}
        <div style={{opacity: end}}>
          <Robot frame={frame} />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
