// The CLI-update video (spec 015 Part B, Decisions 0036 and 0037). Hard cuts between beats; inside a beat only the
// motions in MOTIONS animate (R38, R49-R51), over a slow background field (R58-R62). Scene data lives in
// timeline.ts, motion in motion.ts, boxes in layout.ts and colors in palette.ts; this file holds none of them.
import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {BAND_STOPS, BLOB_STOPS, FIELD_COLORS, backgroundField, bandSpan, wavePath} from './background.ts';
import {
  BANNER_ROWS, END_CTA, HOOK_PROMPT, WINDOW, ctaShown, entranceOffset, entryRows, hookPromptShown, markAt, transcriptLayout, zoomAt,
} from './layout.ts';
import {CAPTION_ENTER, CARET_BLINK_FRAMES, DURATION, END, FONTS, HEIGHT, HIGHLIGHT_FRAMES, HOOK, SEAM_MARK, TERM, TERMINAL, WIDTH, beatAt, captionAt, planSummary, popupLines, screenAt, spinnerAt, statusText, stepLine, typedText, workingText} from './timeline.ts';
import type {CliBeat, CliCaption, Entry, EntryKind, Screen, StepState, Typing} from './timeline.ts';
import {costAt, motionIn, progress, ramp} from './motion.ts';
import {BRAND, TUI} from './palette.ts';

const MARK_G = staticFile('galliani-mark-g.png');
const MARK_STAR = staticFile('galliani-mark-star.png');
const blinkOn = (local: number) => Math.floor(local / CARET_BLINK_FRAMES) % 2 === 0;

// ---------------------------------------------------------------- the background field (R58-R61)

/** Soft blobs and wave bands in palette colors, drawn with SVG gradients only, outside the push. */
const BackgroundField: React.FC<{frame: number}> = ({frame}) => {
  const {blobs, waves} = backgroundField(frame);
  return (
    <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{position: 'absolute', inset: 0}}>
      <defs>
        {blobs.map((b, i) => (
          <radialGradient key={i} id={`field-blob-${i}`} gradientUnits="userSpaceOnUse" cx={b.cx} cy={b.cy} r={b.r}>
            {BLOB_STOPS.map(([offset, f]) => (
              <stop key={offset} offset={offset} stopColor={FIELD_COLORS[b.color]} stopOpacity={b.opacity * f} />
            ))}
          </radialGradient>
        ))}
        {waves.map((w, i) => {
          const {top, bottom} = bandSpan(w);
          return (
            <linearGradient key={i} id={`field-wave-${i}`} gradientUnits="userSpaceOnUse" x1={0} y1={top} x2={0} y2={bottom}>
              {BAND_STOPS.map(([offset, f]) => (
                <stop key={offset} offset={offset} stopColor={FIELD_COLORS[w.color]} stopOpacity={w.opacity * f} />
              ))}
            </linearGradient>
          );
        })}
      </defs>
      {blobs.map((_, i) => (
        <rect key={i} width={WIDTH} height={HEIGHT} fill={`url(#field-blob-${i})`} />
      ))}
      {waves.map((w, i) => (
        <path key={i} d={wavePath(w, HEIGHT)} fill={`url(#field-wave-${i})`} />
      ))}
    </svg>
  );
};

// ---------------------------------------------------------------- brand pieces (outside the terminal)

/** The mark: the G as drawn, with the star in orange (the only orange outside the hook caret and the field, R28). */
const Mark: React.FC<{size: number}> = ({size}) => {
  const fill: React.CSSProperties = {position: 'absolute', inset: 0, width: size, height: size};
  const star = `url(${MARK_STAR})`;
  return (
    <div style={{position: 'relative', width: size, height: size}}>
      <Img src={MARK_G} style={fill} />
      <div style={{...fill, background: BRAND.accent, maskImage: star, WebkitMaskImage: star, maskSize: '100% 100%', WebkitMaskSize: '100% 100%'}} />
    </div>
  );
};

const Centered: React.FC<{x: number; y: number; children: React.ReactNode; style?: React.CSSProperties}> = ({x, y, children, style}) => (
  <div style={{position: 'absolute', left: x, top: y, transform: 'translate(-50%, -50%)', ...style}}>{children}</div>
);

/** The mark where layout.ts puts it: the seam spot, or moving aside in `hook-prompt` (R57). */
const MarkAt: React.FC<{frame: number}> = ({frame}) => {
  const mark = markAt(frame);
  return mark ? (
    <Centered x={mark.x} y={mark.y} style={{opacity: mark.opacity}}>
      <Mark size={mark.size} />
    </Centered>
  ) : null;
};

const HookPrompt: React.FC<{frame: number; local: number}> = ({frame, local}) => (
  <>
    <MarkAt frame={frame} />
    {hookPromptShown(frame) ? (
      <div style={{position: 'absolute', left: HOOK_PROMPT.x, top: SEAM_MARK.y, transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', fontFamily: FONTS.mono, fontSize: HOOK.promptSize, lineHeight: 1, color: BRAND.text}}>
        <span style={{fontWeight: 700}}>{TERM.promptLead}</span>
        <span style={{width: '0.55em', height: '1em', marginLeft: '0.35em', background: BRAND.accent, opacity: blinkOn(local) ? 1 : 0}} />
      </div>
    ) : null}
  </>
);

/** The mark and `galliacli`, centered as one block (R65); the line cuts out before the seam hold (R57). */
const EndCard: React.FC<{frame: number}> = ({frame}) => (
  <>
    <MarkAt frame={frame} />
    {ctaShown(frame) ? (
      <div style={{position: 'absolute', left: 0, width: WIDTH, top: END_CTA.y, height: END_CTA.height, lineHeight: `${END_CTA.height}px`, textAlign: 'center', fontFamily: FONTS.mono, fontSize: END.wordSize, color: BRAND.text, letterSpacing: '-0.01em'}}>
        {TERM.command}
      </div>
    ) : null}
  </>
);

/** One caption, one element: it cuts in, or rises CAPTION_ENTER.slide px while fading in (R38-R41). */
const Caption: React.FC<{caption: CliCaption; frame: number}> = ({caption, frame}) => {
  const local = frame - caption.start;
  const rise = ramp(local, 0, caption.enterFrames);
  const fade = caption.enterFrames > 0 ? ramp(local, 0, CAPTION_ENTER.fade) : 1;
  const {x, y, width, height, fontSize} = caption.box;
  const [before, after] = caption.text.split(' @ ');
  return (
    <div style={{position: 'absolute', left: x, top: y, width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FONTS.sans, fontSize, fontWeight: 600, letterSpacing: '-0.025em', color: BRAND.text, whiteSpace: 'pre', opacity: fade, transform: `translateY(${(1 - rise) * CAPTION_ENTER.slide}px)`}}>
      {after === undefined ? caption.text : (
        <>
          {`${before} `}
          <span style={{fontFamily: FONTS.mono}}>@</span>
          {` ${after}`}
        </>
      )}
    </div>
  );
};

// ---------------------------------------------------------------- the terminal (TUI palette only, R27)

const ROW = TERMINAL.row;
const LINE: React.CSSProperties = {height: ROW, lineHeight: `${ROW}px`, whiteSpace: 'pre', overflow: 'hidden', textOverflow: 'ellipsis'};

/** A Textual `round` border: one cell on each side, the line drawn through the middle of that cell. */
const Bordered: React.FC<{color: string; heavy?: boolean; title?: string; titleColor?: string; style?: React.CSSProperties; children: React.ReactNode}> = ({color, heavy, title, titleColor, style, children}) => {
  const width = heavy ? 3 : 1.5;
  return (
    <div style={{position: 'relative', margin: `${ROW / 2}px 0.5ch`, padding: `${ROW / 2 - width}px calc(1.5ch - ${width}px)`, border: `${width}px solid ${color}`, borderRadius: 8, ...style}}>
      {title ? (
        <div style={{position: 'absolute', top: -ROW / 2 - width / 2, left: '1ch', padding: '0 0.5ch', background: TUI.bg, color: titleColor ?? color, ...LINE}}>{title}</div>
      ) : null}
      {children}
    </div>
  );
};

const Cursor: React.FC<{local: number; char?: string}> = ({local, char}) => (
  <span style={{background: blinkOn(local) ? TUI.fg : 'transparent', color: blinkOn(local) ? TUI.bg : TUI.muted}}>{char ?? ' '}</span>
);

/** The window: an opaque TUI.bg fill at full opacity (R62), risen `dy` px during its entrance. */
const TerminalFrame: React.FC<{dy: number; children: React.ReactNode}> = ({dy, children}) => (
  <div style={{position: 'absolute', left: TERMINAL.x, top: TERMINAL.y, width: TERMINAL.width, height: TERMINAL.height, boxSizing: 'border-box', transform: dy ? `translateY(${dy}px)` : undefined, borderRadius: TERMINAL.radius, border: `${TERMINAL.border}px solid ${TUI.border}`, background: WINDOW.background, opacity: WINDOW.opacity, overflow: 'hidden', display: 'flex', flexDirection: 'column', fontFamily: FONTS.mono, fontSize: TERMINAL.fontSize, color: TUI.fg}}>
    <div style={{height: TERMINAL.titleBar, boxSizing: 'border-box', flex: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', background: TUI.surface, borderBottom: `${TERMINAL.border}px solid ${TUI.border}`}}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{width: 12, height: 12, borderRadius: 6, background: TUI.border}} />
      ))}
      <span style={{flex: 1, textAlign: 'center', color: TUI.muted, fontSize: TERMINAL.fontSize * 0.8, marginRight: 52}}>{TERM.command}</span>
    </div>
    <div style={{flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: `${TERMINAL.pad.top}px ${TERMINAL.pad.side}px ${TERMINAL.pad.bottom}px`}}>{children}</div>
  </div>
);

const ShellShot: React.FC<{typing: Typing; local: number; dy: number}> = ({typing, local, dy}) => (
  <TerminalFrame dy={dy}>
    <div style={{...LINE, padding: '0 1ch'}}>
      <span style={{color: TUI.muted}}>{TERM.shellPrompt}</span>
      <span>{typedText(typing, local)}</span>
      <Cursor local={local} />
    </div>
  </TerminalFrame>
);

const ENTRY_COLORS: Record<EntryKind, {glyph: string; text: string; glyphBold?: boolean; bold?: boolean}> = {
  user: {glyph: TUI.accent, text: TUI.fg, glyphBold: true},
  plan: {glyph: TUI.fg, text: TUI.fg, bold: true},
  route: {glyph: TUI.muted, text: TUI.muted},
  tool: {glyph: TUI.fg, text: TUI.fg},
  verification: {glyph: TUI.agent, text: TUI.fg},
  approval: {glyph: TUI.warn, text: TUI.warn},
  result: {glyph: TUI.good, text: TUI.fg, bold: true},
  usage: {glyph: TUI.muted, text: TUI.muted},
};

/** An entry as the whole rows layout.ts wraps it into, so every row is exactly ROW tall (R64). */
const EntryView: React.FC<{entry: Entry}> = ({entry}) => {
  const color = ENTRY_COLORS[entry.kind];
  return (
    <>
      {entryRows(entry).map((row, i) => {
        if (row.part === 'detail') {
          return (
            <div key={i} style={{...LINE, display: 'flex', color: TUI.muted}}>
              <span style={{width: '4ch', flex: 'none'}}>{row.lead}</span>
              <span>{row.text}</span>
            </div>
          );
        }
        if (row.part === 'body') return <div key={i} style={{...LINE, paddingLeft: '2ch', color: TUI.fg}}>{row.text}</div>;
        return (
          <div key={i} style={{...LINE, display: 'flex'}}>
            <span style={{width: '2ch', flex: 'none', color: color.glyph, fontWeight: color.glyphBold ? 700 : 400}}>{row.lead}</span>
            <span style={{color: color.text, fontWeight: color.bold ? 700 : 400}}>{row.text}</span>
          </div>
        );
      })}
    </>
  );
};

const Banner: React.FC = () => (
  <div style={{height: BANNER_ROWS * ROW, display: 'flow-root'}}>
    <Bordered color={TUI.border} style={{marginBottom: 0}}>
      <div style={{...LINE, fontWeight: 700}}>{TERM.bannerTitle}</div>
      <div style={{...LINE, color: TUI.muted}}>{TERM.bannerWorkspace}</div>
      <div style={LINE}>{TERM.bannerRouting}</div>
      <div style={{...LINE, color: TUI.muted}}>{TERM.bannerSettings}</div>
      {TERM.tips.map((tip, i) => (
        <div key={tip} style={{...LINE, color: TUI.muted, marginTop: i === 0 ? ROW : 0}}>{tip}</div>
      ))}
    </Bordered>
  </div>
);

/** The transcript scrolled by whole rows so the newest row is the last one in view (R64). */
const Transcript: React.FC<{entries: readonly Entry[]; offset: number}> = ({entries, offset}) => (
  <div style={{flex: 1, minWidth: 0, overflow: 'hidden', padding: '0 1ch'}}>
    <div style={{transform: `translateY(${-offset}px)`}}>
      <Banner />
      {entries.map((entry, i) => (
        <EntryView key={i} entry={entry} />
      ))}
    </div>
  </div>
);

const STEP_COLORS: Record<StepState, string> = {pending: TUI.muted, running: TUI.accent, waiting: TUI.warn, verified: TUI.good};

const PlanPanel: React.FC<{screen: Screen; frame: number; since: number}> = ({screen, frame, since}) => {
  const steps = screen.steps;
  const shown = steps ? steps.slice(0, screen.shownSteps ?? steps.length) : [];
  return (
    <Bordered color={TUI.border} title={TERM.planTitle} titleColor={TUI.muted} style={{width: `${TERMINAL.planColumns - 1}ch`, flex: 'none', boxSizing: 'border-box'}}>
      <div style={{...LINE, fontWeight: steps ? 700 : 400}}>{steps ? planSummary(steps) : TERM.noPlan}</div>
      {shown.map((state, i) => (
        <div key={i} style={{...LINE, color: STEP_COLORS[state], fontWeight: screen.fresh === i && since < HIGHLIGHT_FRAMES ? 700 : 400}}>
          {stepLine(i + 1, state, spinnerAt(frame))}
        </div>
      ))}
    </Bordered>
  );
};

const Popup: React.FC<{popup: NonNullable<Screen['popup']>}> = ({popup}) => (
  <div style={{background: TUI.surface, padding: '0 1ch', margin: '0 0.5ch'}}>
    {popupLines(popup.rows, popup.selected).map((line, i) => {
      const split = line.text.length > 2 ? line.text.slice(0, 2).length + line.text.slice(2).search(/ {2}\S|$/) : line.text.length;
      return (
        <div key={i} style={{...LINE, color: TUI.fg, fontWeight: line.current ? 700 : 400}}>
          <span>{line.text.slice(0, split)}</span>
          <span style={{opacity: line.current ? 1 : 0.6}}>{line.text.slice(split)}</span>
        </div>
      );
    })}
  </div>
);

/** The approval card; it rises `slide` px over its own entry (spec 018 CARD_ENTER_FRAMES), else sits still. */
const ApprovalCard: React.FC<{pressed: boolean; rise: number}> = ({pressed, rise}) => {
  const [first, ...rest] = TERM.approvalKeys;
  const key = first.slice(0, 3);
  return (
    <div style={{transform: rise ? `translateY(${rise}px)` : undefined}}>
      <Bordered color={TUI.warn} heavy title={TERM.approvalTitle} style={{marginBottom: 0}}>
        {TERM.approvalLabels.map((label, i) => (
          <div key={label} style={LINE}>
            <span style={{fontWeight: 700}}>{label}</span>
            {TERM.approvalValues[i]}
          </div>
        ))}
        <div style={LINE}>
          <span style={pressed ? {background: TUI.fg, color: TUI.bg} : undefined}>{key}</span>
          {first.slice(3)}
          {rest.join('')}
        </div>
      </Bordered>
    </div>
  );
};

const PromptBox: React.FC<{prompt: NonNullable<Screen['prompt']>; local: number}> = ({prompt, local}) => {
  const text = typedText(prompt.typing, local);
  return (
    <Bordered color={TUI.accent} heavy style={{marginBottom: 0, marginTop: ROW / 2}}>
      <div style={{...LINE, display: 'flex'}}>
        <span style={{width: '2ch', flex: 'none', color: TUI.accent, fontWeight: 700}}>{TERM.promptLead}</span>
        {text ? (
          <span>
            {text}
            <Cursor local={local} />
          </span>
        ) : (
          <span style={{color: TUI.muted}}>
            <Cursor local={local} char={prompt.placeholder[0]} />
            {prompt.placeholder.slice(1)}
          </span>
        )}
      </div>
    </Bordered>
  );
};

const TuiScreen: React.FC<{beat: CliBeat; local: number; frame: number}> = ({beat, local, frame}) => {
  if (beat.shot.kind !== 'terminal') return null;
  const {key, since} = screenAt(beat.shot.keys, local);
  const screen = key.screen;
  const spinner = spinnerAt(frame);
  const {areaRows, offsetRows} = transcriptLayout(screen);
  const cost = costAt(beat, local, screen);
  const card = motionIn(beat, 'card');
  const rise = card ? (card.slide ?? 0) * (1 - progress(card, frame)) : 0;
  return (
    <TerminalFrame dy={entranceOffset(frame)}>
      <div style={{height: areaRows * ROW, flex: 'none', display: 'flex'}}>
        <Transcript entries={screen.entries} offset={offsetRows * ROW} />
        <PlanPanel screen={screen} frame={frame} since={since} />
      </div>
      <div style={{flex: 1}} />
      <div style={{flex: 'none'}}>
        <div style={{...LINE, padding: '0 1ch', color: TUI.accent}}>{screen.working ? workingText({...screen.working, cost}, spinner) : ''}</div>
        {screen.popup ? <Popup popup={screen.popup} /> : null}
        {screen.approval ? <ApprovalCard pressed={screen.approval.pressed} rise={rise} /> : null}
        {screen.prompt ? <PromptBox prompt={screen.prompt} local={local} /> : null}
        <div style={{...LINE, marginTop: ROW / 2, padding: '0 2ch', color: TUI.muted}}>{statusText({...screen.status, cost})}</div>
      </div>
    </TerminalFrame>
  );
};

// ---------------------------------------------------------------- composition

const Shot: React.FC<{beat: CliBeat; local: number; frame: number}> = ({beat, local, frame}) => {
  switch (beat.shot.kind) {
    case 'mark':
      return <MarkAt frame={frame} />;
    case 'hook-prompt':
      return <HookPrompt frame={frame} local={local} />;
    case 'shell':
      return <ShellShot typing={beat.shot.typing} local={local} dy={entranceOffset(frame)} />;
    case 'terminal':
      return <TuiScreen beat={beat} local={local} frame={frame} />;
    case 'end':
      return <EndCard frame={frame} />;
  }
};

/** `fieldShift` (default 0) only offsets the field for the review still of an early beat over a later field (R45). */
export const GallianiCli: React.FC<{fieldShift?: number}> = ({fieldShift = 0}) => {
  const frame = useCurrentFrame();
  const beat = beatAt(frame);
  const local = frame - beat.start;
  const caption = captionAt(frame);
  const zoom = zoomAt(frame);
  const origin = beat.push?.origin;
  return (
    <AbsoluteFill style={{background: BRAND.bg, overflow: 'hidden'}}>
      <BackgroundField frame={(frame + fieldShift) % DURATION} />
      <AbsoluteFill style={origin && zoom !== 1 ? {transform: `scale(${zoom})`, transformOrigin: `${origin.x}px ${origin.y}px`} : undefined}>
        <Shot beat={beat} local={local} frame={frame} />
      </AbsoluteFill>
      {caption ? <Caption caption={caption} frame={frame} /> : null}
    </AbsoluteFill>
  );
};
