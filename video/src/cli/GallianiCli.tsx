// The CLI-update video (spec 015 Part B, Decision 0036). Hard cuts between beats; inside a beat only typing,
// caption entry, rows appearing, glyph and color changes and short pushes (R37-R39). Scene data lives in
// timeline.ts and colors in palette.ts; this file holds neither.
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {BRAND, TUI} from './palette.ts';
import {
  CARD_ENTER_FRAMES,
  CARD_ENTER_ROWS,
  CARET_BLINK_FRAMES,
  CAPTION_SLIDE,
  END,
  FONTS,
  HIGHLIGHT_FRAMES,
  HOOK,
  MARK_SNAP,
  TERM,
  TERMINAL,
  WIDTH,
  WORD_FRAMES,
  beatAt,
  captionAt,
  planSummary,
  popupLines,
  screenAt,
  spinnerAt,
  statusText,
  stepLine,
  typedText,
  workingText,
} from './timeline.ts';
import type {CliBeat, CliCaption, Entry, EntryKind, Screen, StepState, Typing} from './timeline.ts';

const MARK_G = staticFile('galliani-mark-g.png');
const MARK_STAR = staticFile('galliani-mark-star.png');
const OUT = Easing.out(Easing.cubic);
const ramp = (frame: number, start: number, frames: number) =>
  interpolate(frame, [start, start + frames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: OUT});
const blinkOn = (local: number) => Math.floor(local / CARET_BLINK_FRAMES) % 2 === 0;

// ---------------------------------------------------------------- brand pieces (outside the terminal)

/** The mark: the G as drawn, with the star in orange (the only orange outside the hook caret, R28). */
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

const MarkShot: React.FC<{local: number}> = ({local}) => {
  const snap = ramp(local, 0, MARK_SNAP.frames);
  return (
    <Centered x={WIDTH / 2} y={HOOK.markY} style={{opacity: ramp(local, 0, 4), transform: `translate(-50%, -50%) scale(${MARK_SNAP.fromScale + (1 - MARK_SNAP.fromScale) * snap})`}}>
      <Mark size={HOOK.markSize} />
    </Centered>
  );
};

const HookPrompt: React.FC<{local: number}> = ({local}) => (
  <>
    <Centered x={HOOK.asideX} y={HOOK.markY}>
      <Mark size={HOOK.asideSize} />
    </Centered>
    <div style={{position: 'absolute', left: HOOK.promptX, top: HOOK.markY, transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', fontFamily: FONTS.mono, fontSize: HOOK.promptSize, lineHeight: 1, color: BRAND.text}}>
      <span style={{fontWeight: 700}}>{TERM.promptLead}</span>
      <span style={{width: '0.55em', height: '1em', marginLeft: '0.35em', background: BRAND.accent, opacity: blinkOn(local) ? 1 : 0}} />
    </div>
  </>
);

const EndCard: React.FC = () => (
  <>
    <Centered x={WIDTH / 2} y={END.markY}>
      <Mark size={END.markSize} />
    </Centered>
    <Centered x={WIDTH / 2} y={END.wordY} style={{fontFamily: FONTS.mono, fontSize: END.wordSize, color: BRAND.text, letterSpacing: '-0.01em'}}>
      {TERM.command}
    </Centered>
  </>
);

/** One caption: words snap up and in, staggered across `enterFrames` (R38-R41). */
const Caption: React.FC<{caption: CliCaption; frame: number}> = ({caption, frame}) => {
  const local = frame - caption.start;
  const words = caption.text.split(' ');
  const stagger = words.length > 1 ? (caption.enterFrames - WORD_FRAMES) / (words.length - 1) : 0;
  const {x, y, width, height, fontSize} = caption.box;
  return (
    <div style={{position: 'absolute', left: x, top: y, width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.26em', fontFamily: FONTS.sans, fontSize, fontWeight: 600, letterSpacing: '-0.025em', color: BRAND.text, whiteSpace: 'nowrap'}}>
      {words.map((word, i) => {
        const t = ramp(local, i * stagger, WORD_FRAMES);
        return (
          <span key={i} style={{display: 'inline-block', opacity: t, transform: `translateY(${(1 - t) * CAPTION_SLIDE}px)`, fontFamily: word === '@' ? FONTS.mono : undefined}}>
            {word}
          </span>
        );
      })}
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

const TerminalFrame: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{position: 'absolute', left: TERMINAL.x, top: TERMINAL.y, width: TERMINAL.width, height: TERMINAL.height, borderRadius: TERMINAL.radius, border: `1.5px solid ${TUI.border}`, background: TUI.bg, overflow: 'hidden', display: 'flex', flexDirection: 'column', fontFamily: FONTS.mono, fontSize: TERMINAL.fontSize, color: TUI.fg}}>
    <div style={{height: TERMINAL.titleBar, flex: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', background: TUI.surface, borderBottom: `1.5px solid ${TUI.border}`}}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{width: 12, height: 12, borderRadius: 6, background: TUI.border}} />
      ))}
      <span style={{flex: 1, textAlign: 'center', color: TUI.muted, fontSize: TERMINAL.fontSize * 0.8, marginRight: 52}}>{TERM.command}</span>
    </div>
    <div style={{flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: '6px 6px 4px'}}>{children}</div>
  </div>
);

const ShellShot: React.FC<{typing: Typing; local: number}> = ({typing, local}) => (
  <TerminalFrame>
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

const EntryView: React.FC<{entry: Entry}> = ({entry}) => {
  const color = ENTRY_COLORS[entry.kind];
  return (
    <div style={{marginTop: entry.kind === 'user' ? ROW : 0}}>
      <div style={{display: 'flex', lineHeight: `${ROW}px`}}>
        <span style={{width: '2ch', flex: 'none', color: color.glyph, fontWeight: color.glyphBold ? 700 : 400}}>{TERM.leaders[entry.kind]}</span>
        <span style={{flex: 1, color: color.text, fontWeight: color.bold ? 700 : 400}}>{entry.text}</span>
      </div>
      {entry.detail?.map((line, i) => (
        <div key={i} style={{display: 'flex', lineHeight: `${ROW}px`, color: TUI.muted}}>
          <span style={{width: '4ch', flex: 'none', whiteSpace: 'pre'}}>{i === 0 ? TERM.detailLead : TERM.detailIndent}</span>
          <span style={{flex: 1}}>{line}</span>
        </div>
      ))}
      {entry.body ? <div style={{lineHeight: `${ROW}px`, paddingLeft: '2ch', color: TUI.fg}}>{entry.body}</div> : null}
    </div>
  );
};

const Banner: React.FC = () => (
  <Bordered color={TUI.border} style={{marginBottom: ROW * 1.5}}>
    <div style={{...LINE, fontWeight: 700}}>{TERM.bannerTitle}</div>
    <div style={{...LINE, color: TUI.muted}}>{TERM.bannerWorkspace}</div>
    <div style={LINE}>{TERM.bannerRouting}</div>
    <div style={{...LINE, color: TUI.muted}}>{TERM.bannerSettings}</div>
    {TERM.tips.map((tip, i) => (
      <div key={tip} style={{...LINE, color: TUI.muted, marginTop: i === 0 ? ROW : 0}}>{tip}</div>
    ))}
  </Bordered>
);

/** Newest entries stay at the bottom once the transcript is longer than the view, as when it scrolls to the end. */
const Transcript: React.FC<{entries: readonly Entry[]}> = ({entries}) => (
  <div style={{flex: 1, minWidth: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column-reverse', padding: '0 1ch'}}>
    <div style={{flex: '1 0 auto'}}>
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

const ApprovalCard: React.FC<{pressed: boolean; local: number}> = ({pressed, local}) => {
  const enter = ramp(local, 0, CARD_ENTER_FRAMES);
  const [first, ...rest] = TERM.approvalKeys;
  const key = first.slice(0, 3);
  return (
    <div style={{transform: `translateY(${(1 - enter) * CARD_ENTER_ROWS * ROW}px)`}}>
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
  return (
    <TerminalFrame>
      <div style={{flex: 1, minHeight: 0, display: 'flex'}}>
        <Transcript entries={screen.entries} />
        <PlanPanel screen={screen} frame={frame} since={since} />
      </div>
      <div style={{flex: 'none'}}>
        <div style={{...LINE, padding: '0 1ch', color: TUI.accent}}>{screen.working ? workingText(screen.working, spinner) : ''}</div>
        {screen.popup ? <Popup popup={screen.popup} /> : null}
        {screen.approval ? <ApprovalCard pressed={screen.approval.pressed} local={local} /> : null}
        {screen.prompt ? <PromptBox prompt={screen.prompt} local={local} /> : null}
        <div style={{...LINE, marginTop: ROW / 2, padding: '0 2ch', color: TUI.muted}}>{statusText(screen.status)}</div>
      </div>
    </TerminalFrame>
  );
};

// ---------------------------------------------------------------- composition

const Shot: React.FC<{beat: CliBeat; local: number; frame: number}> = ({beat, local, frame}) => {
  switch (beat.shot.kind) {
    case 'mark':
      return <MarkShot local={local} />;
    case 'hook-prompt':
      return <HookPrompt local={local} />;
    case 'shell':
      return <ShellShot typing={beat.shot.typing} local={local} />;
    case 'terminal':
      return <TuiScreen beat={beat} local={local} frame={frame} />;
    case 'end':
      return <EndCard />;
  }
};

export const GallianiCli: React.FC = () => {
  const frame = useCurrentFrame();
  const beat = beatAt(frame);
  const local = frame - beat.start;
  const caption = captionAt(frame);
  const push = beat.push;
  const zoom = push ? push.from + (push.to - push.from) * ramp(local, push.at, push.frames) : 1;
  return (
    <AbsoluteFill style={{background: BRAND.bg, overflow: 'hidden'}}>
      <AbsoluteFill style={push ? {transform: `scale(${zoom})`, transformOrigin: `${push.origin.x}px ${push.origin.y}px`} : undefined}>
        <Shot beat={beat} local={local} frame={frame} />
      </AbsoluteFill>
      {caption ? <Caption caption={caption} frame={frame} /> : null}
    </AbsoluteFill>
  );
};
