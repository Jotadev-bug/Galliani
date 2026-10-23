// The CLI-update video (spec 015 Part B, Decisions 0036-0038). A cursor drags the Galliani icon from a quiet desktop
// into a terminal window, `galliacli` is typed, and the window grows into the TUI while the showcase robot guides each
// beat. Hard cuts between beats; inside a beat only the motions in MOTIONS animate (R38, R49-R51), over a slow
// background field (R58-R62). Scene data lives in timeline.ts, motion in motion.ts, the desktop in desktop.ts, the robot
// in pose.ts, boxes in layout.ts and colors in palette.ts; this file holds none of them.
import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {BAND_STOPS, BLOB_STOPS, FIELD_COLORS, backgroundField, bandSpan, wavePath} from './background.ts';
import {cursorAt, desktopShown, heroBoxes, heroIconAt, shellCommand, windowFocused} from './desktop.ts';
import type {HeroState} from './desktop.ts';
import {BANNER_ROWS, END_CTA, END_MARK, WINDOW, endCardShown, entryRows, terminalRect, transcriptLayout, tuiShown} from './layout.ts';
import type {Rect} from './layout.ts';
import {
  CAPTION_ENTER, CARET_BLINK_FRAMES, DESKTOP, DURATION, END, FONTS, HEIGHT, HIGHLIGHT_FRAMES, TERM, TERMINAL, WIDTH,
  beatAt, captionAt, planSummary, popupLines, screenAt, spinnerAt, statusText, stepLine, typedText, workingText,
} from './timeline.ts';
import type {CliBeat, CliCaption, DesktopIcon, Entry, EntryKind, Glyph, Screen, StepState} from './timeline.ts';
import {costAt, motionIn, progress, ramp} from './motion.ts';
import {BRAND, TUI} from './palette.ts';
import {robotPose} from './pose.ts';
import {GuideRobot} from './robot.tsx';

const MARK_G = staticFile('galliani-mark-g.png');
const MARK_STAR = staticFile('galliani-mark-star.png');
const blinkOn = (frame: number) => Math.floor(frame / CARET_BLINK_FRAMES) % 2 === 0;

// ---------------------------------------------------------------- the background field (R58-R61)

/** Soft blobs and wave bands in palette colors, drawn with SVG gradients only. */
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

/** The mark: the G as drawn, with the star in orange (the only orange outside the field, R28). */
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

/** The `galliacli` end card: the mark and the call to action, centered as one block (R65). */
const EndCard: React.FC = () => (
  <>
    <div style={{position: 'absolute', left: END_MARK.x, top: END_MARK.y}}>
      <Mark size={END.markSize} />
    </div>
    <div style={{position: 'absolute', left: 0, width: WIDTH, top: END_CTA.y, height: END_CTA.height, lineHeight: `${END_CTA.height}px`, textAlign: 'center', fontFamily: FONTS.mono, fontSize: END.wordSize, color: BRAND.text, letterSpacing: '-0.01em'}}>
      {TERM.command}
    </div>
  </>
);

// ---------------------------------------------------------------- the desktop (R66-R71; BRAND only)

/** Abstract generic glyphs, strokes only: a page, a folder, a square grid (R67). */
const GLYPHS: Record<Glyph, React.ReactNode> = {
  page: (
    <>
      <path d="M7 3h7l5 5v13H7z" />
      <path d="M14 3v5h5M10 13h6M10 17h6" />
    </>
  ),
  folder: <path d="M3 6.5h6.2l2 2.2H21V19H3z" />,
  grid: (
    <>
      <rect x={4} y={4} width={7} height={7} rx={1.5} />
      <rect x={13} y={4} width={7} height={7} rx={1.5} />
      <rect x={4} y={13} width={7} height={7} rx={1.5} />
      <rect x={13} y={13} width={7} height={7} rx={1.5} />
    </>
  ),
};

const Label: React.FC<{box: Rect; size: number; color: string; highlight?: boolean; children: string}> = ({box, size, color, highlight, children}) => (
  <div style={{position: 'absolute', left: box.x, top: box.y, width: box.width, height: box.height, display: 'flex', justifyContent: 'center', alignItems: 'center'}}>
    <span style={{padding: '0 10px', borderRadius: 7, lineHeight: `${box.height}px`, background: highlight ? BRAND.raised : 'transparent', fontFamily: FONTS.sans, fontSize: size, fontWeight: 500, color, letterSpacing: '-0.01em'}}>
      {children}
    </span>
  </div>
);

const GenericIcon: React.FC<{icon: DesktopIcon}> = ({icon}) => {
  const {tile} = icon;
  return (
    <>
      <div style={{position: 'absolute', left: tile.x, top: tile.y, width: tile.width, height: tile.height, borderRadius: tile.width * DESKTOP.tileRadius, background: BRAND.surface, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <svg width={tile.width * 0.44} height={tile.width * 0.44} viewBox="0 0 24 24" fill="none" stroke={BRAND.muted} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round">
          {icon.glyph ? GLYPHS[icon.glyph] : null}
        </svg>
      </div>
      <Label box={icon.labelBox} size={DESKTOP.labelSize} color={BRAND.muted}>{icon.label}</Label>
    </>
  );
};

/** The hero icon: the mark in a raised tile, at its home slot, on the drag arc, or shrinking into the caret. Its
 * size comes from the box, so nothing is CSS-scaled (R70, R71). */
const HeroIcon: React.FC<{hero: HeroState}> = ({hero}) => {
  const {tile, label} = heroBoxes(hero);
  const radius = tile.width * DESKTOP.tileRadius;
  return (
    <div style={{position: 'absolute', inset: 0, opacity: hero.opacity}}>
      <div style={{position: 'absolute', left: tile.x, top: tile.y, width: tile.width, height: tile.height, borderRadius: radius, background: BRAND.raised, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <Mark size={DESKTOP.markSize * hero.scale} />
      </div>
      {label ? <Label box={label} size={DESKTOP.heroLabelSize} color={BRAND.text} highlight={hero.hovered}>{DESKTOP.hero.label}</Label> : null}
    </div>
  );
};

/** An original arrow cursor: a BRAND.text fill with a BRAND.bg outline, its tip at (x, y) (R68). */
const CURSOR_TIP = {x: 1.5, y: 1.5};
const CursorArrow: React.FC<{x: number; y: number}> = ({x, y}) => {
  const k = DESKTOP.cursorHeight / 30;
  return (
    <svg width={20 * k} height={30 * k} viewBox="0 0 20 30" style={{position: 'absolute', left: x - CURSOR_TIP.x * k, top: y - CURSOR_TIP.y * k, overflow: 'visible'}}>
      <path d="M1.5 1.5 L1.5 23.6 L7 18.6 L10.8 27.4 L14.6 25.8 L10.9 17.2 L18.4 17.2 Z" fill={BRAND.text} stroke={BRAND.bg} strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  );
};

/** The generic icons, then the hero icon and the cursor above the window (R28). */
const DesktopIcons: React.FC = () => (
  <>
    {DESKTOP.icons.map((icon) => (
      <GenericIcon key={icon.label} icon={icon} />
    ))}
  </>
);

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

const Cursor: React.FC<{frame: number; char?: string}> = ({frame, char}) => (
  <span style={{background: blinkOn(frame) ? TUI.fg : 'transparent', color: blinkOn(frame) ? TUI.bg : TUI.muted}}>{char ?? ' '}</span>
);

/** The window at `rect`: an opaque TUI.bg fill at full opacity (R62). Its size comes from the rectangle, never from a
 * CSS scale, and the border, radius, title bar and text size stay constant (R73). The focused border is drawn as an
 * overlay, so focusing never shifts the content (R71). */
const TerminalFrame: React.FC<{rect: Rect; focused: boolean; children?: React.ReactNode}> = ({rect, focused, children}) => (
  <div style={{position: 'absolute', left: rect.x, top: rect.y, width: rect.width, height: rect.height, boxSizing: 'border-box', borderRadius: TERMINAL.radius, background: WINDOW.background, opacity: WINDOW.opacity, overflow: 'hidden', display: 'flex', flexDirection: 'column', fontFamily: FONTS.mono, fontSize: TERMINAL.fontSize, color: TUI.fg, padding: TERMINAL.border}}>
    <div style={{height: TERMINAL.titleBar, boxSizing: 'border-box', flex: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', background: TUI.surface, borderBottom: `${TERMINAL.border}px solid ${TUI.border}`}}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{width: 12, height: 12, borderRadius: 6, background: TUI.border}} />
      ))}
      <span style={{flex: 1, textAlign: 'center', color: TUI.muted, fontSize: TERMINAL.fontSize * 0.8, marginRight: 52}}>{TERM.command}</span>
    </div>
    <div style={{flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: `${TERMINAL.pad.top}px ${TERMINAL.pad.side}px ${TERMINAL.pad.bottom}px`}}>{children}</div>
    <div style={{position: 'absolute', inset: 0, borderRadius: TERMINAL.radius, border: focused ? `${TERMINAL.focusBorder}px solid ${TUI.accent}` : `${TERMINAL.border}px solid ${TUI.border}`}} />
  </div>
);

/** The shell line: the prompt, the typed command and the caret, blinking on the absolute frame so the seam holds. */
const ShellLine: React.FC<{frame: number}> = ({frame}) => (
  <div style={{...LINE, padding: '0 1ch'}}>
    <span style={{color: TUI.muted}}>{TERM.shellPrompt}</span>
    <span>{shellCommand(frame)}</span>
    <Cursor frame={frame} />
  </div>
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
            <Cursor frame={local} />
          </span>
        ) : (
          <span style={{color: TUI.muted}}>
            <Cursor frame={local} char={prompt.placeholder[0]} />
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
    <>
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
    </>
  );
};

// ---------------------------------------------------------------- composition

/** `fieldShift` (default 0) only offsets the field for the review still of an early beat over a later field (R45). */
export const GallianiCli: React.FC<{fieldShift?: number}> = ({fieldShift = 0}) => {
  const frame = useCurrentFrame();
  const beat = beatAt(frame);
  const local = frame - beat.start;
  const caption = captionAt(frame);
  const rect = terminalRect(frame);
  const hero = heroIconAt(frame);
  const cursor = cursorAt(frame);
  const robot = robotPose(frame);
  return (
    <AbsoluteFill style={{background: BRAND.bg, overflow: 'hidden'}}>
      <BackgroundField frame={(frame + fieldShift) % DURATION} />
      {desktopShown(frame) ? <DesktopIcons /> : null}
      {rect ? (
        <TerminalFrame rect={rect} focused={windowFocused(frame)}>
          {beat.shot.kind === 'terminal' ? (tuiShown(frame) ? <TuiScreen beat={beat} local={local} frame={frame} /> : null) : <ShellLine frame={frame} />}
        </TerminalFrame>
      ) : null}
      {endCardShown(frame) ? <EndCard /> : null}
      {hero ? <HeroIcon hero={hero} /> : null}
      {cursor ? <CursorArrow x={cursor.x} y={cursor.y} /> : null}
      {robot ? <GuideRobot pose={robot} /> : null}
      {caption ? <Caption caption={caption} frame={frame} /> : null}
    </AbsoluteFill>
  );
};
