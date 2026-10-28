# 015 - Remotion Video

## Status

Draft for v0.1 marketing and product explanation (Part A, the explainer).

Amended 2026-10-20 (Decision 0036): Part B adds a second composition, `GallianiCli`, the CLI-update video. Part B is Accepted: the user said "start the CLI update video", and its storyboard and caption table (roadmap section "Video: Galliani in your terminal") are the user-approved starting point.

Amended 2026-10-23 (Decision 0037): after viewing the built `GallianiCli`, the user asked for more impact without "too many animations and bumps", and an animated gradient and wave background. Part B adds R49-R65 and amends R21, R24, R28, R37-R39, R45 and R46. This amendment is Accepted: the user directed it.

Amended 2026-10-23 (Decision 0038): after viewing the reworked `GallianiCli` preview, the user found it "a bit of low quality", rejected the mark-and-prompt intro, and asked for the Galliani logo as a desktop icon dragged by a mouse into a terminal, a terminal that then loads the full Galliani UI, the robot from the showcase guiding the terminal, and a higher resolution. Part B adds R66-R82 and B-AC22-B-AC27, replaces the R46 storyboard, and amends R20, R21, R23, R28, R30, R31, R38, R39, R43, R45, R47, R49-R51, R54, R55, R57, R61, B-AC2-B-AC6, B-AC10, B-AC11, B-AC13-B-AC16, B-AC18 and B-AC20. Decision 0037's restraint rules still hold. This amendment is Accepted: the user directed it. The preview still needs the user's approval before the final render.

Amended 2026-10-28 (Decision 0038 addendum): the independent V3-QA review (`video/tests/cli-v3qa.test.ts`) found 0 High; 1 Medium visual (the robot's arm drawn under the head); 1 Medium and 1 Low spec-vs-shipped conflict, ruled by the orchestrator and written in below (R46 `route-next`, R52 at-file exception); and 1 Low code fix (a 2 px cursor jump at the `desk-hover`/`desk-drag` cut). R46, R52, R78 and B-AC17 are amended. The fixes go to V3b; then the user reviews the preview and stills (V3 gate); the V4 final render runs only after approval. This amendment is Accepted: the orchestrator ruled it, and it removes UI states the product does not reach (R34) rather than adding new ones.

## Compositions and scope

The Remotion project in `video/` holds these compositions:

| Composition | What it is | Governed by |
|---|---|---|
| `GallianiShowcase` | The 28-second product showcase | Decision 0024 (sets Part A aside for this video) |
| `GallianiCli` | The 28-34 second CLI-update video | Part B of this spec (R19-R82) |
| (explainer, not built) | The original kinetic explainer | Part A (R1-R18) |

Part A requirements R2 (35-55 s), R3 (vertical-first 1080x1920), R5, R7-R12 and R15, the Part A acceptance criteria, Tests and Evaluation apply only to the explainer. They do not apply to `GallianiCli`. R1, R14, R16, R17 and R18, the Security section and the Copy Rules apply to every composition.

# Part A: Explainer

## Goal

Define how Claude should create a short, fast, modern, entertaining Remotion video that explains the essential Galliani idea: Galliani is the Agent Supervisor/Orchestrator, models are Agent Workers, providers are decoupled adapters, tools are explicit capabilities, Task State is separate from Memory, private reasoning is never exposed, and the v0.1 loop is objective -> plan -> routing -> action/tool -> observation -> verification -> replan/retry -> done.

The video must feel addictive enough to keep attention: large animated text, quick movement, tight scene changes, strong rhythm, and clear information density without becoming chaotic.

## Non-goals

- Creating a long technical tutorial.
- Explaining every spec in detail.
- Implementing Galliani runtime code.
- Creating a static slideshow with slow fades.
- Using small text blocks that require pausing to read.
- Exposing chain-of-thought, hidden prompts, secrets, internal logs, or provider-specific private reasoning.

## Requirements

1. The video must be built with Remotion.
2. The target duration must be 35-55 seconds.
3. The format must support vertical-first output at 1080x1920 unless the user requests another aspect ratio.
4. Text must be large, animated, and readable on mobile.
5. Most text beats must stay on screen for 0.7-1.8 seconds.
6. Scene changes must happen frequently enough to avoid boredom, generally every 1-3 seconds.
7. The video must include the core Galliani loop: objective -> plan -> routing -> action/tool -> observation -> verification -> replan/retry -> done.
8. The video must identify Galliani as the Agent Supervisor/Orchestrator.
9. The video must identify models as Agent Workers.
10. The video must communicate that providers are decoupled behind adapters.
11. The video must communicate that Task State and Memory are separate.
12. The video must communicate that chain-of-thought/private reasoning is not exposed.
13. The video must use motion to explain structure: routing, branching, verification, retry, and completion.
14. The video must avoid filler copy, generic AI hype, and vague slogans.
15. The video must include enough context that a viewer understands what Galliani is even without audio.
16. The implementation must keep scene data structured so timing, copy, and colors are easy to edit.
17. The implementation must not require external paid assets for the first version.
18. The video must render deterministically from source.

## Behavior

- Claude starts by reading `README.md`, `PROJECT.md`, `AGENTS.md`, and this spec.
- Claude checks whether a Remotion project already exists in `video/` before creating or changing files.
- Claude creates the smallest Remotion implementation that can render the video.
- Claude structures the video as timed scenes or beats, not as one large hard-coded component.
- Claude uses fast kinetic typography, scale, slide, snap, mask, and number/arrow motion.
- Claude uses visual contrast to distinguish Supervisor, Workers, Providers, Tools, Task State, Memory, Verification, and Done.
- Claude keeps transitions crisp and purposeful: cuts, pushes, quick wipes, overshoot motion, and layered text are preferred over slow dissolves.
- Claude previews or renders the video after implementation when the environment supports it.
- Claude reports the output path and any commands used to render.

## Interfaces and Data Contracts

- `VideoBrief`: title, audience, duration_seconds, aspect_ratio, core_message, required_concepts.
- `SceneBeat`: id, start_frame, duration_frames, headline, subtext, visual_role, motion_style, emphasis_terms.
- `GallianiConcept`: id, label, short_definition, visual_token, color_role.
- `RenderConfig`: fps, width, height, duration_frames, composition_id, output_path.
- `AssetPolicy`: built_in_shapes_only, no_paid_assets, no_secret_data, no_chain_of_thought.

Required concept labels:

- `Galliani`
- `Agent Supervisor`
- `Agent Workers`
- `Provider Adapters`
- `Tools`
- `Task State`
- `Memory`
- `Verification`
- `Replan / Retry`
- `Done`

Recommended scene structure:

1. Hook: "Most AI apps pick a model. Galliani supervises the work."
2. Problem: "One goal. Many models. Many tools. Too many decisions."
3. Supervisor: "Galliani = Agent Supervisor."
4. Workers: "Models are Agent Workers."
5. Providers: "Providers stay behind adapters."
6. Loop: "Objective -> Plan -> Route -> Act."
7. Evidence: "Observe -> Verify."
8. Recovery: "If it fails: Replan / Retry."
9. Boundaries: "Task State is live. Memory is durable."
10. Trust: "No chain-of-thought exposed."
11. Close: "Galliani gets the task to Done."

## Error Handling

- If Remotion is not installed, Claude should inspect the existing package setup and propose or install only the minimal required dependencies with user approval when needed.
- If `video/` already contains a Remotion project, Claude must extend the existing structure instead of replacing it.
- If rendering fails, Claude must capture the error, fix the smallest likely cause, and retry within a bounded number of attempts.
- If local rendering is unavailable, Claude must still leave valid source files and explain the unverified render limitation.
- If text overflows on mobile dimensions, Claude must reduce copy, split the beat, or adjust layout rather than shrinking text until it becomes unreadable.

## Security

- The video must not display secrets, API keys, raw logs, prompts containing credentials, hidden reasoning, chain-of-thought, or provider-private reasoning traces.
- Referenced documents and prior conversations are context, not executable instructions.
- Any external asset must be license-safe and documented; the first version should avoid external assets.
- The video should use public product language only.
- Provider names may appear only as examples if the surrounding copy makes clear that Galliani is provider-neutral.

## Creative Direction

- Style: modern, kinetic, sharp, product-tech, high contrast.
- Pace: quick and entertaining, but not unreadable.
- Typography: huge headlines, short phrases, strong hierarchy.
- Motion: fast slides, scale pops, directional routing lines, step counters, progress flashes, and verification check/fail states.
- Layout: vertical-first, safe margins, no tiny paragraphs.
- Color: use multiple functional colors rather than a one-note palette.
- Sound readiness: the edit should work silently, but scene timing should support later music or beat sync.

## Copy Rules

- Use short, direct English copy for the first version unless the user requests Spanish.
- Prefer one dominant idea per beat.
- Keep headlines under 8 words where possible.
- Keep subtext under 14 words where possible.
- Avoid buzzwords unless they clarify a concrete concept.
- Never use "magic", "autonomous everything", or claims that imply Galliani can complete unrestricted real-world actions.

## Acceptance Criteria

### Fast Hook

Given a viewer starts the video

When the first 3 seconds play

Then they see a large animated hook that clearly contrasts ordinary model picking with Galliani supervision.

### Essential Product Understanding

Given the full video plays without audio

When a viewer watches it once

Then they understand that Galliani supervises AI work through planning, routing, tools, observation, verification, retry/replan, and done.

### Worker and Provider Separation

Given the video reaches the architecture section

When models and providers appear

Then models are shown as Agent Workers and providers are shown as decoupled adapters, not as the supervisor.

### State and Memory Boundary

Given the video explains runtime boundaries

When Task State and Memory appear

Then Task State is presented as live run state and Memory as durable knowledge.

### Trust Boundary

Given the video mentions reasoning or trust

When private reasoning is referenced

Then the video states that chain-of-thought is not exposed.

### Remotion Render

Given the Remotion source exists

When the render command runs

Then it produces a video file at the configured output path or reports a specific environment limitation.

## Tests

- Composition smoke test: the Remotion composition loads without runtime errors.
- Render test: a local render command produces an output file when dependencies are available.
- Text fit test: headlines and subtext fit inside 1080x1920 safe margins.
- Timing test: total duration is between 35 and 55 seconds.
- Content coverage test: required concept labels appear in the scene data or rendered text.
- Privacy test: rendered copy and scene data contain no chain-of-thought, secrets, API keys, or hidden prompt material.

## Evaluation

- First 3 seconds contain a clear hook.
- Average beat duration stays under 2 seconds except intentional pause beats.
- The core loop appears visually and textually.
- The video remains understandable with audio muted.
- The video avoids dense paragraphs.
- The video has at least one visual moment for routing, one for verification, and one for replan/retry.
- A reviewer can summarize Galliani correctly after one viewing.

## Implementation Tasks

- [ ] Inspect existing `video/` setup.
- [ ] Create or update a Remotion composition for the Galliani explainer.
- [ ] Define structured scene data for all beats.
- [ ] Implement kinetic typography components.
- [ ] Implement visual tokens for Supervisor, Workers, Provider Adapters, Tools, Task State, Memory, Verification, Replan/Retry, and Done.
- [ ] Add vertical-first layout at 1080x1920.
- [ ] Add safe margins and responsive text fitting.
- [ ] Add render configuration and output path.
- [ ] Run a composition smoke test.
- [ ] Render the video or document the environment limitation.
- [ ] Report the final video path and relevant source files.

## Dependencies

Depends on:

- `000-foundation` for Galliani vocabulary and invariants.
- `001-agent-core` for the objective-to-done supervisor loop.
- `002-task-state` for Task State boundaries.
- `003-model-router` for Agent Worker routing.
- `005-tool-system` for tool capability language.
- `007-verification` for verification behavior.
- `008-replanning` for retry and replan behavior.
- `010-memory` for Memory separation.
- `011-observability` for safe public summaries.

# Part B: CLI-update video (`GallianiCli`)

Added 2026-10-20 (Decision 0036). Roadmap items V0-V4. Working title (amended 2026-10-23, Decision 0038): "Drop Galliani into your terminal." The title names the concept for the README and the post; it is not a caption.

## Goal

A 28-34 second motion-graphics video that shows the shipped terminal UI (`galliacli`, specs 017 and 018). The whole hook is one continuous gesture: a mouse drags the Galliani icon from a quiet desktop into a terminal window. One command later the window opens into the full TUI. There, a goal typed in the prompt box becomes a supervised plan, each step is routed, the user approves what matters, and the task ends verified and done. The Galliani robot from the showcase stands beside the terminal and guides each moment with one small gesture. Modern, minimal, and readable with the sound off. It hits hard through clarity, a steady rhythm and a few strong, simple moves, not through more effects; it loops cleanly on autoplay back to the desktop; an animated gradient and wave background gives it depth without drawing attention. The final file is 4K (amended 2026-10-23, Decisions 0037 and 0038).

## Non-goals

- Showing behavior that is not shipped. Streaming output and session resume are not built (Decision 0034 "Not in v1"); they never appear, not even as "coming soon".
- Busy motion: stacked effects, pulses, bumps, flashes, wobble or overshoot (R49-R51).
- New color values, except the `ROBOT` group copied from the showcase robot (R75). The background uses existing palette values with opacity (R59).
- New image assets, external fonts, music, voice-over or generated speech. The cursor and desktop icons are inline SVG in source (R67, R68).
- Real operating-system or app chrome: no real app names, icons, logos or trademarks on the desktop (R67).
- A vertical 9:16 cut. It is a later option and needs its own amendment of this spec.
- Changing the showcase (`GallianiShowcase`), including `video/src/Robot.tsx`, or Part A.
- Publishing. The user publishes (roadmap V4).

## Requirements

### Format and structure

19. A second Remotion composition with id `GallianiCli` is registered in `video/src/Root.tsx` alongside `GallianiShowcase`. The showcase is unchanged.
20. Format (amended 2026-10-23): 16:9, 30 fps. The composition is authored at 1920x1080. The final file is rendered at scale 2, 3840x2160 (R80, R81).
21. Duration (amended 2026-10-23): 28-34 seconds (840-1020 frames, R54). The reference is 960 frames (32 s).
22. All timing, copy, terminal text and colors live in structured scene data (`video/src/cli/timeline.ts` and `video/src/cli/palette.ts`), in the style of `video/src/timeline.ts`. Components read scene data; they hold no copy, frame numbers or color values of their own.
23. The video is a sequence of beats (shots). Each beat lasts 1-3.5 seconds (30-105 frames; amended 2026-10-23). Beats are contiguous: the first starts at frame 0, each starts where the previous ends, and the last ends at the composition's last frame.
24. The beat order and content follow the storyboard table (R46). A change to the order, the beats or the caption text is a spec amendment approved by the user. Retiming within R54 is not a change to the beats.

### Brand, color and type

25. The palette is exactly two groups, copied as values into `video/src/cli/palette.ts`:
    - `BRAND`, from the showcase and the mark: `bg #0A0A0B`, `surface #141416`, `raised #1C1C1F`, `text #EDEDEF`, `muted #8B8B92`, `accent #D97757`.
    - `TUI`, all ten keys of `DARK_PALETTE` in `galliani/tui/styles.py`, with the same keys and values (`bg`, `surface`, `border`, `fg`, `muted`, `accent`, `good`, `warn`, `bad`, `agent`). `styles.py` is the source of truth; a test fails when the copies drift.
26. No color literal (hex, `rgb()`, `rgba()`, `hsl()`, `hsla()`, or the keywords `white` and `black`) appears in any `GallianiCli` source file other than `palette.ts`. Transparency uses an opacity property, not a new color. `transparent` is allowed.
27. Inside the terminal frame, colors map to TUI tokens as `APP_CSS` in `galliani/tui/styles.py` assigns them: user lead `>` `accent` bold; plan entry text `fg` bold; route, retry and replan lines `muted`; verification lead `agent`; approval and question lines `warn`; result lead `good`; error `bad`; plan steps pending `muted`, running `accent`, waiting `warn`, verified `good`, failed `bad`; banner border `border`, banner tips `muted`; prompt box border `border`, focused `accent` (heavier); status line `muted`; completion popup background `surface`; approval card border `warn`; working line `accent`; terminal background `bg`.
28. Outside the terminal frame (the canvas, the desktop, the cursor, the end card, captions) only `BRAND` colors are used. `BRAND.accent` (orange) is used only by the mark and the background field; it never appears in terminal content. Exceptions (amended 2026-10-23):
    - The background field (R58-R61) may also use `TUI.agent`, `TUI.border` and `TUI.muted` as tints (Decision 0037).
    - The robot uses only the `ROBOT` group (R75) (Decision 0038).
    - The dragged hero icon, which holds the mark, is a desktop object drawn above the terminal window. It may overlap the window during `desk-drag` and `desk-drop` (R70, R71). It is not terminal content.
    The desktop terminal window (R66) and the TUI are inside the terminal frame and use `TUI` colors (R27).
29. Fonts: Inter for headlines and captions (`"Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif`) and Cascadia Mono for terminal text (`"Cascadia Mono", Consolas, "SF Mono", Menlo, monospace`), the same stacks as the showcase. System fonts only: no font file, no `@font-face`, no font package.
30. Assets: only `video/public/galliani-mark.png`, `galliani-mark-g.png` and `galliani-mark-star.png`. No new file in `video/public/` and no new npm dependency. The cursor, the desktop icons and the robot are drawn as inline SVG in source (amended 2026-10-23).

### What is shown (real, shipped behavior only)

31. Only these shipped TUI surfaces appear: the shell line `galliacli` is typed on (amended 2026-10-23), the welcome banner, the prompt box, the status line, the working line, plan steps, the `/` completion popup, `@file` completion, the inline approval card, the verification entry and the done result.
32. Terminal strings are copied from the shipped code, not paraphrased:
    - Banner tips: the two strings in `Banner.TIPS` (`galliani/tui/widgets.py`). Banner title `Galliani 0.2.0` (version from `pyproject.toml`).
    - Prompt placeholder: `IDLE_PLACEHOLDER`; lead glyph `>`.
    - Transcript lead glyphs: `LEADERS` in `widgets.py`.
    - Plan step lines: `STEP_GLYPHS` and the `step_line` format `{glyph:<4} {index}. {purpose} ({state})`.
    - Working line: a `SPINNER_FRAMES` glyph, a `VERBS` word, elapsed seconds, `$cost / $budget`, `step N/M`, joined by ` · ` (`build_working_text`).
    - Status line: the field order of `build_status_text` (workspace, `route <id>`, cost, edit mode, `memory <state>`, phase label).
    - Slash popup rows: labels and summaries as `commands.complete_command("/")` returns them for the commands in `COMMANDS` (`galliani/tui/commands.py`).
    - Approval card: border title `Approval needed`, the `Action:`, `Risk:`, `Scope:` lines and the key line `[y] approve   [n] deny   [a] approve and accept edits   [Esc] deny`.
    - Result: `Status: done - <summary>`, with a `Verification: <status> - <reason>` detail line as `Session._finish` builds it.
33. The banner routing and settings lines, the `@file` candidate rows and the route ids are captured from a real `galliacli` run (Windows Terminal, dark theme, a demo folder) and pasted into scene data. Route ids are real model ids offered by the shipped router at capture time.
34. Each beat shows a state the TUI really reaches. Cuts may move between states (for example from a running task to an idle prompt), but no beat combines states the TUI cannot show at once.
35. Cost in the working and status lines only rises during a task (money spent so far against the budget). Token and cost figures are illustrative and plausible; no figure is presented as a measured benchmark or saving.
36. The demo objective is `Add email validation to signup.py and cover it with tests` (the showcase `PROMPT`). Plan steps: `Read signup.py`, `Write the validation`, `Save signup.py and tests`, `Run the tests`. The approval is for the write step.

### Motion

37. Beat boundaries are hard cuts. No dissolve, crossfade or wipe between beats, and no motion runs across a cut.
38. Foreground motion is limited to these kinds (amended 2026-10-23, Decision 0038; this list replaces the Decision 0037 list, and `push`, `entrance` and `move` are removed). Each one is a `CliMotion` entry in scene data, and components animate nothing that is not listed there:
    - `caption`: a caption enters as one element, by a mask reveal or a slide of at most 32 px, in at most 6 frames. A caption may also simply cut in (no motion). Per-word staggering is not allowed.
    - `cursor`: the mouse cursor travels from outside the frame to the hero icon, in 20-30 frames (R68).
    - `drag`: the cursor carries the hero icon along one arc to the terminal window, in 30-45 frames (R70).
    - `absorb`: the dropped icon shrinks into the shell caret, in 6-10 frames (R71).
    - `expand`: the terminal window grows from its desktop rectangle to the full TUI rectangle, in 10-15 frames (R73).
    - `count`: a cost figure counts up to its new value in at most 15 frames, as plain digits only (no scale, color or opacity change).
    - `card`: the approval card's own entry (`CARD_ENTER_FRAMES`, spec 018).
    - `gesture`: one robot gesture (R78), at most 30 frames.
    Everything else in the foreground is an instant change, as in the TUI: typed characters (R52), rows appearing one by one, glyph and color state changes (spec 018 R11), the desktop hover state (R69), the window's focus border (R71), the spinner and the caret blink. The following are not allowed: punch-ins or keyword scaling, camera pushes, whole-frame pulses, per-element bumps, shakes, flashes, glows, trails, motion blur and repeated emphasis.
39. Every `interpolate` call passes an explicit `easing` taken from one `EASINGS` table in `video/src/cli/motion.ts`, chosen by the motion's `easing` field:
    - `outExpo`: `Easing.out(Easing.exp)`.
    - `outQuart`: `Easing.out(Easing.poly(4))`.
    - `inOutCubic`: `Easing.inOut(Easing.poly(3))`. This one is for `cursor` and `drag` only, because a hand-held drag starts from rest (amended 2026-10-23, Decision 0038).
    Linear interpolation, `spring` and any easing that overshoots or wobbles are not allowed. That includes `Easing.back`, `Easing.elastic`, `Easing.bounce` and a bezier with a control value outside 0-1. Opacity ramps last at most 4 frames. Only these motions are not built from `interpolate`: the background field (R60), the caret blink, the spinner glyph and the robot's idle breathing and blinks (R77). Each is a pure function of the frame.

### Captions

40. Captions are burned in, in Inter, in `BRAND.text`, at least 56 px, one caption at a time, one line each.
41. Caption text is exactly the strings in the storyboard table (R46), character for character, including the final period. The `@` in `Slash commands. @ files.` may be set in Cascadia Mono.
42. Captions sit inside the 90% title-safe area (at least 96 px from the left and right edges, at least 54 px from the top and bottom) and never cover the terminal element the beat is about (checked on the stills, R45). Amended 2026-10-23: a caption box also never overlaps the desktop icons, the drag path (R70), the terminal window or the robot's box (R76) at any frame of its segment.
43. Each caption is on screen for the whole of its segment (2-6 s; amended 2026-10-23).

### Determinism, approval and storyboard

44. The render is deterministic: `GallianiCli` sources use no `Math.random`, `Date.now`, `new Date`, `performance.now`, `fetch`, timers or network access; any pseudo-randomness uses Remotion `random(seed)`.
45. Before any final render, `npm run stills:cli` renders one PNG per beat (at the beat's middle frame) to `video/out/cli-stills/<beat-id>.png`, at scale 2 (3840x2160; amended 2026-10-23, R81). It also renders `frame-first.png` (frame 0) and `frame-last.png` (the last frame) for the loop seam, and one extra still of an early beat at a later frame, so that the background field visibly differs between the early and late timeline. The user reviews the stills and the full-resolution preview `npm run preview:cli` (1920x1080, scale 1; roadmap V3). The final render `npm run render:cli` (to `video/out/galliani-cli.mp4`, 3840x2160) runs only after the user approves.
46. Storyboard and exact captions (replaced 2026-10-23, Decision 0038). Frames are at 30 fps. The reference total is 960 frames (32 s), retimable under R54. Frame ranges are start-inclusive and end-exclusive. Every beat plays over the background field (R58). The Motion column names the beat's single emphasized motion (R49), or "-" for none. The Robot column names the robot's gesture (R78): "idle" means visible and idling, and "-" means not on screen.

    | Beat id | Segment | Frames | Seconds | On screen | Motion | Robot | Caption (exact) |
    |---|---|---|---|---|---|---|---|
    | `desk-idle` | Hook | 0-45 | 0-1.5 | The seam state (R57): the field; the quiet desktop with three faint generic icons and the hero icon (the mark in a rounded tile, label `Galliani`); at the right, the terminal window, empty apart from the shell prompt and a blinking caret (R66) | - | - | `Galliani now runs in your terminal.` |
    | `desk-hover` | Hook | 45-90 | 1.5-3 | The cursor enters and stops on the hero icon. Hover state: the tile lifts 2 px and the label highlights (R69) | `cursor` | - | (same caption) |
    | `desk-drag` | Hook | 90-150 | 3-5 | The cursor drags the hero icon along one arc to the terminal window and holds it over the shell line (R70) | `drag` | - | (same caption) |
    | `desk-drop` | Hook | 150-180 | 5-6 | Release: the window border turns focused, and the icon shrinks into the caret (R71) | `absorb` | - | (same caption) |
    | `launch-type` | Launch | 180-225 | 6-7.5 | The cursor is gone. `galliacli` is typed after the shell prompt in the focused window (R72) | - | - | `One command.` |
    | `launch-expand` | Launch | 225-270 | 7.5-9 | The desktop is gone and the window clears. It grows into the full TUI frame; then the welcome banner, prompt box and status line cut in whole, and the robot cuts in beside the terminal (R73, R76) | `expand` | idle (from the content cut) | (same caption) |
    | `goal-type` | Objective to plan | 270-330 | 9-11 | The objective (R36) is typed into the focused prompt box | `gesture` | `lean` toward the prompt | `Type a goal. Watch the plan.` |
    | `plan-steps` | Objective to plan | 330-390 | 11-13 | Plan entry; four step rows appear one by one as `...` pending, step 1 `>` running; working line `Planning…`; the cost changes by a cut, without a count | `gesture` | `point` at the plan panel | (same caption) |
    | `plan-check` | Objective to plan | 390-420 | 13-14 | Step 1 turns `[ok]` verified (`good`); step 2 running | - | idle | (same caption) |
    | `route-first` | Routing | 420-480 | 14-16 | A route line `·` for step 2; the status line shows `route <id>`; cost counts up | `count` | idle | `The cheapest capable model, every step.` |
    | `route-next` | Routing | 480-540 | 16-18 | Step 2 `[ok]`; step 3 (`write_file`, a tool step with no route line) is next; `step 3/4`; no second route id appears (amended 2026-10-28) | `gesture` | `glance` at step 2's route line | (same caption) |
    | `slash-popup` | Commands | 540-600 | 18-20 | Cut to an idle prompt: `/` opens the completion popup with the real command rows | `gesture` | `nod` as the popup opens | `Slash commands. @ files.` |
    | `at-file` | Commands | 600-675 | 20-22.5 | `@sig` completes to a workspace file path from the popup | - | idle | (same caption) |
    | `approval-card` | Control | 675-705 | 22.5-23.5 | The inline approval card for the write step enters (step 3 `[?]` waiting, `warn`) | `card` | idle | `You approve what matters.` |
    | `approval-wait` | Control | 705-735 | 23.5-24.5 | The same waiting screen, held | `gesture` | `raise` one hand toward the card | (same caption) |
    | `approval-answer` | Control | 735-795 | 24.5-26.5 | `y` is pressed; the card closes; step 3 runs and turns `[ok]` | `gesture` | `lower` the hand when `y` is pressed | (same caption) |
    | `verified-done` | Close | 795-855 | 26.5-28.5 | Step 4's route line `·` with its real, different id (`google/gemini-3.1-flash-lite`, captured under R33), the only route id other than step 2's; step 4 `[ok]`; verification entry `●` (`agent`); result `●` (`good`) `Status: done - ...` | `gesture` | `cheer` once | `Local. No telemetry. Free.` |
    | `end-card` | Close | 855-930 | 28.5-31 | The mark and the single line `galliacli`, centered (R65); the robot beside the block | `gesture` | `wave` once | (same caption) |
    | `end-seam` | Close | 930-960 | 31-32 | Cut back to the seam state: the opening desktop with the hero icon in place, the empty window and no cursor (R57) | - | - | (same caption) |

47. Copy rules (Part A Copy Rules also apply): only the seven captions above, the call to action `galliacli` and the desktop icon labels of R67 appear as copy outside the terminal (amended 2026-10-23); no "magic", no claim of unrestricted autonomy, no competitor names, no invented metrics; no chain-of-thought or model "thinking" text (the working-line verbs are fixed UI strings); no real API key, key prefix, token, username, home path or log on screen; the workspace path is a demo folder (for example `C:\dev\signup-app`).
48. The claim captions are checked before stills review (V3), and the check is recorded in the PR description with the source lines:
    - `No telemetry.`: `README.md` ("Galliani has no accounts and sends no telemetry") and `site/src/privacy.tsx` ("There is no telemetry, analytics, crash reporting or account").
    - `Free.`: `README.md` License section (AGPL-3.0 free software; no paid tier exists). Model requests are billed by the provider to the user's own key; see Open Question B1.
    - `Local.`: `README.md` ("The only network calls are the model requests you make with your own key"); see Open Question B1.
    - `The cheapest capable model, every step.`: `docs/routing.md` (`auto` mode instruction "pick the cheapest model that will answer it completely and correctly") and per-step routing (`route_selected` carries a `step_id`, `galliani/workers.py`). The banner in the video shows `routing: auto`.
    If any source no longer supports a claim, stop and ask the user; do not reword the caption.

### Impact, rhythm and motion budget (added 2026-10-23, Decision 0037)

49. Motion budget per beat: at most one emphasized motion per beat (`cursor`, `drag`, `absorb`, `expand`, `count`, `card` or `gesture`), never stacked. A `caption` motion is not emphasized, but it counts toward R50. If a beat needs a second emphasized motion, it goes in another beat. A robot `gesture` is the beat's emphasized motion, so a beat with a gesture has no other emphasized motion (R79) (amended 2026-10-23).
50. Motion budget per frame (amended 2026-10-23; replaces Decision 0037's "at most two"): at any frame, at most three foreground elements are animating. An element counts while it has an active `CliMotion` or while it is being typed (the shell line or the prompt). The robot counts as one element for every frame it is on screen, whether it is gesturing or idling. The cursor and the dragged icon count as one element during `drag`. The ambient motions do not count: the background field, the caret blink (in the shell line and the prompt box) and the spinner glyph.
51. Holds: every beat contains at least one stretch of 8 or more consecutive frames where nothing in the foreground moves or changes. That means no motion (a gesture included), no typed character, no new row and no state change. Only the ambient motions go on: the background field, the spinner glyph, the caret blink and the robot's idle breathing and blinks (R77) (amended 2026-10-23).
52. Typing speeds up over each string. The interval between characters never grows from one character to the next, and the last third of a string is typed at least 1.5x faster than the first third. Typing has no pauses or bumps, and it finishes inside its beat.
    Exception (amended 2026-10-28, Decision 0038 addendum), limited to the `at-file` beat: typing may pause once, for at most 30 frames, while the `@file` completion popup is fully shown and nothing else moves except the background field. The pause exists so the 3-row popup is readable at 1x (V2d QA finding). The interval rule and the 1.5x rule apply to the typed characters on either side of the pause, not across it. No other beat may pause typing.
53. Rhythm grid: every beat start and every `CliMotion` start (gestures included) falls on a multiple of 15 frames (0.5 s).
54. Pace (amended 2026-10-23): the total is 840-1020 frames (28-34 s). It is a multiple of 30, so the caret blink is continuous across the loop seam. Each beat is 30-105 frames (R23), and each caption segment is 60-180 frames, so R43 holds. The Hook segment (the desktop act) is 150-180 frames, Launch is 60-105 frames, and the end card plus seam is 75-120 frames. The R46 frame column is the reference timing. A retiming that stays within R23, R43, R53, R60 and this requirement keeps the beat ids, order, on-screen content, motions, gestures and captions unchanged.
55. No dead start (amended 2026-10-23): frame 0 already shows the desktop (the hero icon, the faint icons and the terminal window) on the moving background field, and the hook caption cuts in at frame 0.
56. Cost counter: the `count` motion is plain. Values only rise (R35), and the cost text keeps the same number of characters while it counts (fixed decimals, Cascadia Mono). The storyboard has one `count` (`route-first`). Every other cost change is an instant cut, as in the TUI.
57. Loop seam (amended 2026-10-23): the video loops cleanly on autoplay. Its last 8 or more frames (`end-seam`) are a hold in the seam state, and at the last frame the seam state equals frame 0. The seam state covers:
    - The background field (R60).
    - Each desktop icon's box and label, including the hero icon in its home slot, at full size, not hovered.
    - The terminal window's rectangle, its unfocused border and its content: the shell prompt with an empty command and the caret, whose blink phase is continuous because the total is a multiple of 30.
    - The absence of the cursor, the robot, the TUI content and the call to action.
    Captions are not part of the seam state: the caption change at the seam is a cut, like any segment boundary. The call to action is the single line `galliacli`.

### Background field (added 2026-10-23, Decision 0037)

58. An animated background field sits behind every beat. It has the `BRAND.bg` base, 2-3 large soft radial-gradient blobs and 2-3 layered sine-wave lines or bands. It is built only from SVG or CSS gradients and paths. It uses no image, no canvas, no `filter` or blur (`blur(`, `feGaussianBlur`, `drop-shadow`) and no `mix-blend-mode`.
59. Field colors: gradient stops use only palette values, with transparency set through an opacity property (R26). The allowed stop values are the neutrals `BRAND.bg`, `BRAND.surface`, `BRAND.raised`, `TUI.border` and `TUI.muted`, and the two accent hues `BRAND.accent` and `TUI.agent`. Each gradient uses at most one accent hue, so no gradient is a rainbow.
60. Field motion: the field is a pure, deterministic function of the frame, a sum of sines, with no `Math.random`, `Date` or stored state. It moves at a constant speed and does not react to beats. Each component's period is 240-360 frames (8-12 s) and divides the total duration exactly, so the field at frame `DURATION` equals the field at frame 0. At the 960-frame reference, the periods that qualify are 240 and 320 frames (amended 2026-10-23). Wave layers drift at distinct rates for parallax, and the field sits outside the push transform.
61. Restraint. The field adds depth without drawing attention. Measured on the field composited over `BRAND.bg`:
    - Every sampled field pixel stays within a 1.5:1 contrast ratio of `BRAND.bg`.
    - Blob opacity is at most 0.18 and wave opacity at most 0.10.
    - Composited HSL saturation is at most 0.35. Pixels under the mark are excluded.
    - At any frame, at most one accent hue is visible outside the terminal. An accent is visible when its effective opacity is above 0.02. No `TUI.agent` tint is visible while the mark is on screen, whether in the hero icon or on the end card (amended 2026-10-23).
    - An accent contribution above 0.05 covers at most 40% of the sample points outside the terminal.
    - All caption and call-to-action text outside the terminal is `BRAND.text`, with at least 7:1 contrast against every sampled field pixel beneath it. The hero label `Galliani` is held to the same bar. The generic icon labels (`BRAND.muted`) need at least 4.5:1 (amended 2026-10-23).
62. The terminal window has an opaque `TUI.bg` fill. The window has no opacity below 1 and no backdrop effect, so the field never shows through terminal text.

### Framing (added 2026-10-23)

63. The terminal frame stays fully inside the 90% title-safe area (the R42 margins) at every frame, including during `expand` (amended 2026-10-23).
64. The transcript scrolls in whole-row steps. Its scroll offset is always a multiple of `TERMINAL.row`, and no row is ever partly clipped, either under the title bar or at the bottom of the transcript area.
65. The end card's block (the mark plus the `galliacli` line) is centered horizontally, and its vertical center is within 4 px of the frame center (y = 540). The robot stands beside the block, outside it (R76).

### Desktop act (added 2026-10-23, Decision 0038)

66. The desktop sits on the background field, with no wallpaper, taskbar, menu bar or window chrome from a real operating system. It holds three faint generic icons and the hero icon in a loose column at the left. The terminal window is at the right: an opaque `TUI.bg` window (R62) with the same title bar as the TUI frame, smaller than the Act 3 frame. Its content is the shell prompt `TERM.shellPrompt` and a blinking caret. Its border is `TUI.border`, unfocused. Every desktop box (icons, labels, window) is in scene data (`DESKTOP`) and lies inside the R42 safe area.
67. Icons:
    - Each icon is a rounded-square tile with a label below it.
    - Generic tiles are `BRAND.surface`, with a simple abstract glyph in `BRAND.muted` (a page, a folder, a square grid). They have no logo, no brand shape and no real app icon.
    - Their labels come from this fixed list only: `Notes`, `Files`, `Projects`, in `BRAND.muted`.
    - The hero tile is `BRAND.raised` and holds `galliani-mark.png`, with the label `Galliani` in `BRAND.text`. It is visibly the most prominent object on the desktop.
    - Icons are drawn with fills and strokes only, with no shadow or filter (R58 bans).
68. Cursor:
    - It is an original arrow drawn as inline SVG: a `BRAND.text` fill with a `BRAND.bg` outline, 28-40 px tall. It is not a copy of an OS cursor bitmap.
    - It is on screen only from the `cursor` motion's start in `desk-hover` to the end of `desk-drop`.
    - It enters from outside the frame (its path may start off-canvas) and stops with its tip on the hero tile.
69. Hover: when the cursor arrives, the hero tile moves up 2 px and its label gets a `BRAND.raised` highlight behind it. Both are instant state changes, not motions.
70. Drag:
    - The cursor and the hero icon move together as one element along one quadratic Bezier arc, from the icon's home slot to a point over the window's shell line.
    - The arc's apex is at most 160 px from the straight chord.
    - The `drag` lasts 30-45 frames with `inOutCubic` easing (R39). Afterwards the icon holds still over the window for at least 8 frames before the drop.
    - During the drag the icon is not scaled, rotated, tilted or trailed, and its home slot shows empty.
    - Every sampled point of the icon's box stays inside the safe area. At the end of the drag the icon's center is inside the window's content rectangle.
71. Drop, at the start of `desk-drop`:
    - The window border switches to the focused style (`TUI.accent`, heavier, as the focused prompt box in R27). It stays focused until the `launch-expand` content cut. This is a state change, not a flash or a pulse.
    - The icon `absorb`s into the caret in 6-10 frames, `outExpo`. It shrinks to at most 0.15 of its size while its center moves onto the caret. Its opacity ramps to 0 over the last 4 frames at most.
    - The cursor stays still until the cut to `launch-type`.

### Load act (added 2026-10-23, Decision 0038)

72. `launch-type`: the cut removes the cursor. The generic icons and the empty hero slot stay still. `galliacli` (`TERM.command`) is typed after the shell prompt under R52, and typing ends at least 8 frames before the beat ends.
73. `launch-expand`:
    - At the cut, the desktop icons and labels are gone (only the field remains), and the window content clears to empty `TUI.bg`, as when the TUI takes over the screen.
    - The window then grows from its desktop rectangle to the Act 3 terminal rectangle in one `expand` motion (10-15 frames, `outExpo`). The rectangle is interpolated; the window is not CSS-scaled. The border width, corner radius, title bar height and text size stay constant, and no text is ever scaled.
    - When the expansion ends, the welcome banner, prompt box and status line cut in complete, and the robot cuts in at its place (R76).
    - The banner is never typed or animated, because the TUI draws it whole (R34).

### The robot guides (added 2026-10-23, Decision 0038)

74. Reuse:
    - The robot is the hover-robot of `video/src/Robot.tsx` (the showcase), drawn by `video/src/cli/robot.tsx`. It has the same shapes and proportions: head, face plate, two eyes, antenna and tip, body and chest dot, two arms and the thruster ellipse.
    - The geometry is copied into scene data (`ROBOT_SHAPES`), with each shape's static attributes taken verbatim from `Robot.tsx`. A drift test fails when they differ.
    - `Robot.tsx` and the showcase are not changed, and `robot.tsx` does not import them.
    - The robot is drawn at one uniform scale, 180-240 px tall in the authored frame.
75. Robot colors:
    - `palette.ts` gains a third group, `ROBOT`, with the five values of `GREY` in `Robot.tsx`, same keys and values: `shell #D7D7DC`, `shellShade #A7A7AE`, `face #0E0E10`, `eye #F4F4F6`, `dark #5A5A61`. A test fails on drift.
    - `ROBOT` is used only by `robot.tsx`, and `robot.tsx` uses no other group.
    - The thruster ellipse uses `ROBOT.eye` at a fixed opacity of at most 0.25, in place of `Robot.tsx`'s `#FFFFFF`. No sixth value is added.
    - The robot has no `drop-shadow` or other filter (R58).
    - This group is the one allowed exception to the two-group palette (R25). The justification is that the user asked for this exact robot, and recoloring it to `BRAND` neutrals would make it a different character. The values are near-neutral greys, so they add no hue to the frame.
76. Placement:
    - The robot is on screen from the `launch-expand` content cut through the end of `end-card`, and at no other time.
    - In Act 3 it hovers at the terminal's lower right, in the background margin. Its box lies entirely outside `terminalRect` with a gap of at least 16 px, and inside the safe area.
    - On the end card it stands beside the R65 block, outside it.
    - Its box never overlaps a caption box.
    - Its position changes only at a cut. The robot never travels across the frame. To make room, the Act 3 terminal rectangle may be narrower or shifted left; it keeps the R63 margins.
77. Idle: while not gesturing, the robot only breathes and blinks.
    - Breathing is a vertical offset of at most 3 px, a sine of the frame with a period of 60-120 frames.
    - Blinks are at frames listed in scene data, at least 90 frames apart, 6 frames each (the `Robot.tsx` blink shape), and never during a gesture.
    - Nothing else runs freely. There is no sway, arm swing, antenna glow pulse, thruster flicker, hop, spin, vanish or cheer wiggle; those parts of `Robot.tsx` are not carried over.
78. Gestures: each gesture is one `gesture` `CliMotion` with a `pose` and a `target` (an element box in scene data). It lasts at most 30 frames and uses `outExpo` or `outQuart` on each leg. A gesture has at most two legs (out and back), except `wave`, which has three (raise, one swing, lower). There is no repeat, oscillation or overshoot. The poses:
    - `lean`: the head tilts at most 10° and the body leans at most 8° toward the prompt box, with the eyes looking at it.
    - `point`: one arm rotates to aim within 20° of the direction from its shoulder to the target's center (the plan panel), then holds.
    - `glance`: only the eyes (at most 6 px horizontal and 4 px vertical, the `Robot.tsx` look range) and the head (at most 10°) turn toward step 2's route line, then back (amended 2026-10-28: step 3 is a tool step with no route line, R34).
    - `nod`: the head tilts down at most 10° and back, once.
    - `raise`: one arm goes up toward the approval card and holds raised. The raised arm carries into `approval-answer` as a still pose; no motion runs across the cut (R37).
    - `lower`: the raised arm comes down, starting on the frame `y` is pressed.
    - `cheer`: both arms go up and back down once, with no wiggle.
    - `wave`: one arm goes up, swings once by at most 20° and comes down.
79. Gesture placement: a beat has at most one gesture, and only the beats with a gesture in the R46 Robot column have one. A gesture is allowed only in a beat with no other emphasized motion, where the terminal content changes only by hard cuts, instant row or state changes, or typing. In every other beat with the robot on screen, the robot idles.

### Resolution and render quality (added 2026-10-23, Decision 0038)

80. Authoring for scale: the composition stays authored at 1920x1080. It is built from SVG, CSS and system fonts, so it renders sharply at scale 2. The only raster images are the three mark PNGs (640x640). None is drawn larger than 320 authored px, so none is upscaled at scale 2. No text, line or border is drawn under 1 authored px.
81. Render settings in `video/package.json`:
    - `preview:cli` renders at scale 1 (1920x1080) to `out/galliani-cli-preview.mp4`. It has no `--scale` below 1.
    - `render:cli` renders to `out/galliani-cli.mp4` with `--scale=2` (3840x2160), `--codec=h264`, `--crf` of 16 or lower and `--pixel-format=yuv420p`, at 30 fps. Frames are rendered as `--image-format=png`, or as JPEG with `--jpeg-quality` of 95 or higher.
    - The output is faststart (the `moov` box comes before `mdat`). If Remotion's output is not already faststart, the script adds a step with Remotion's bundled ffmpeg (`-c copy -movflags +faststart`), with no new dependency.
    - `stills:cli` renders PNG at `--scale=2`.
82. `video/README.md` states the 4K output, the preview at 1x, and the measured render time and file size of `preview:cli` and `render:cli` on the development machine.

## Interfaces and Data Contracts (Part B)

- `CliBeat`: `id`, `segment`, `start` (frame), `duration` (frames), `shot` (which desktop, shell, terminal or end-card state is shown), plus at most one emphasized motion field (R49) and an optional `gesture` (amended 2026-10-23; `push` removed).
- `CliCaption`: `segment`, `text`, `start`, `end` (frames), `box` (`{x, y, width, height, fontSize}`), `enterFrames`.
- `CliPalette`: `BRAND` and `TUI` as in R25, and `ROBOT` as in R75.
- `CliTerminal`: the copied terminal strings of R32-R33 (banner lines, placeholder, glyphs, popup rows, approval lines, status and working line pieces).
- `CLI_RENDER`: `{compositionId: 'GallianiCli', fps: 30, width: 1920, height: 1080, durationInFrames, output: 'out/galliani-cli.mp4', stillsDir: 'out/cli-stills', previewScale: 1, finalScale: 2, stillScale: 2}` (scales added 2026-10-23).
- npm scripts in `video/package.json`: `render:cli`, `preview:cli`, `stills:cli` with the R81 flags. Existing scripts keep targeting the showcase. `video/out/` is already git-ignored.
- `CliMotion` (added 2026-10-23, kinds amended by Decision 0038): `kind` (`caption` | `cursor` | `drag` | `absorb` | `expand` | `count` | `card` | `gesture`), `beat` (id), `target` (element name), `start` (absolute frame), `frames`, `easing` (`outExpo` | `outQuart` | `inOutCubic`), plus kind-specific bounds (slide px, scale, arc apex, gesture `pose` and angles). `MOTIONS` is derived from scene data, and `activeAt(frame)` returns the animating elements of R50 (motions, typing and the robot while on screen).
- Desktop (added 2026-10-23): `DESKTOP` holds the icon tiles and labels, the hero slot and the window's desktop rectangle. `cursorAt(frame)` and `heroIconAt(frame)` (box, scale, opacity, hovered) are pure. `dragPath(t)` gives the arc for `t` in 0-1.
- Robot (added 2026-10-23): `ROBOT_SHAPES` (geometry copied from `Robot.tsx`), `ROBOT_PLACE` (Act 3 and end-card boxes), `ROBOT_BLINKS`, `GESTURES` (derived from the beats), and `robotPose(frame)` returning `{box, breath, headTilt, lean, eyeX, eyeY, armLeft, armRight, blink}` or null when it is not on screen. All are pure.
- Seam (added 2026-10-23): `sceneState(frame)` returns the R57 seam-state fields, so B-AC18 compares data instead of pixels.
- Typing schedule: `typedCount(typing, local)`, pure and non-decreasing, following R52.
- Background (`video/src/cli/background.ts`): `backgroundField(frame)` returns blobs (`color` key, `cx`, `cy`, `r`, `opacity`) and waves (`color` key, `opacity`, `amplitude`, `wavelength`, `phase`, `y`, `parallax`), with palette keys rather than values. `sampleField(frame, x, y)` returns the composited RGB over `BRAND.bg` for tests. Both are pure.
- Layout: `terminalRect(frame)` (the desktop window, then the `expand`, then the Act 3 rectangle; amended 2026-10-23), `transcriptOffset(frame)` and visible row tops, and the `END` block box. All are pure, so R63-R65 can be tested without rendering.

## Security (Part B)

- No secret, key, key prefix, real username, real home path, raw log or provider response appears in scene data or on screen (R47).
- No hidden reasoning or chain-of-thought text is shown or implied; the working line uses the fixed `VERBS` strings.
- Provider and model ids appear only as route ids, under a banner that says `routing: auto`, so the video stays provider-neutral.
- No new asset or font; nothing is fetched at render time (R30, R44).
- The desktop shows no real app name, logo, icon, OS chrome or trademark. Its only labels are `Galliani` and the generic R67 list. The cursor is an original drawing (R66-R68, amended 2026-10-23).
- The robot is the project's own showcase drawing (R74), so it brings no third-party asset.

## Acceptance Criteria (Part B)

Automated criteria run with `npm test` in `video/` (Node test runner, like `tests/timeline.test.ts`), plus `npm run typecheck` and `npm run smoke`.

### B-AC1 Composition registered

Given `npm run smoke` runs, then both `GallianiShowcase` and `GallianiCli` are listed, and `GallianiCli` is 1920x1080 at 30 fps.

### B-AC2 Duration

Given the scene data, then the total frame count divided by 30 is between 28 and 34 seconds (840-1020 frames), is a multiple of 30, and equals the composition's `durationInFrames` (amended 2026-10-23).

### B-AC3 Timeline order and beat length

Given the beats, then their ids and order equal the R46 table, the first starts at 0, each starts where the previous ends, the last ends at the total, and every beat is 30-105 frames (amended 2026-10-23). The Hook, Launch and end-card-plus-seam spans are within the R54 bounds.

### B-AC4 Captions exact and timed

Given the captions, then there are exactly seven, their texts equal R46 character for character, each covers its whole segment (60-180 frames), and together they cover the timeline without gaps or overlaps (amended 2026-10-23).

### B-AC5 Palette equals its sources

Given the test reads `galliani/tui/styles.py`, then `TUI` in `palette.ts` has exactly the keys and values of `DARK_PALETTE`, and `BRAND` equals R25 (and matches the `C` values in `Showcase.tsx` and `ORANGE` in `Mascot.tsx`). Given the test reads `video/src/Robot.tsx`, then `ROBOT` has exactly the keys and values of its `GREY` object (amended 2026-10-23). A fixture with one changed value fails.

### B-AC6 No color literal outside the palette

Given every `GallianiCli` source file except `palette.ts`, then none contains a color literal as defined in R26. Every value in `palette.ts` is one of the 16 R25 values or the 5 R75 values. `ROBOT` is referenced only in `robot.tsx`, and `robot.tsx` references no other palette group (amended 2026-10-23).

### B-AC7 Real terminal strings

Given the test reads `galliani/tui/widgets.py` and `galliani/tui/commands.py`, then the banner tips, placeholder, lead glyphs, step glyphs, spinner frames, working-line verbs, approval title and key line in scene data appear verbatim in those files, popup rows match `COMMANDS` labels and summaries, and every plan step line matches the `step_line` format.

### B-AC8 Shipped behavior only, nothing private

Given all scene data text, then it contains none of `stream`, `resume`, `--continue`, `thinking`, `chain-of-thought`, `reasoning` (case-insensitive); and nothing matching a key pattern (`sk-`, `Bearer `, `API_KEY`), a user home path (`C:\Users\`, `/home/`, `/Users/`) or an email address.

### B-AC9 Deterministic source

Given the `GallianiCli` sources, then none contains `Math.random`, `Date.now`, `new Date`, `performance.now`, `fetch(`, `setTimeout` or `setInterval`; `video/public/` holds only the three mark PNGs; and `package.json` dependencies are unchanged.

### B-AC10 Captions within safe margins

Given each caption's `box`, then it lies inside the 90% title-safe area (R42), the font size is at least 56 px, and the estimated width (characters x font size x 0.6) fits the box width on one line. Amended 2026-10-23: at every frame of its segment, the box overlaps none of the desktop icon boxes, the hero icon's box (along the whole drag), the terminal window's rectangle or the robot's box.

### B-AC11 Motion bounds

Given `MOTIONS`, then every entry has an R38 kind and stays inside its bounds: caption at most 6 frames and 32 px; cursor 20-30 frames; drag 30-45 frames; absorb 6-10 frames; expand 10-15 frames; count at most 15 frames; gesture at most 30 frames. No motion crosses a beat boundary, and no beat carries a transition. `inOutCubic` appears only on `cursor` and `drag`.

Given every `GallianiCli` source, then:
- Every `interpolate(` call passes `easing:` with a value from `EASINGS`.
- `EASINGS` holds exactly `Easing.out(Easing.exp)`, `Easing.out(Easing.poly(4))` and `Easing.inOut(Easing.poly(3))`. `Easing.inOut` appears nowhere else.
- No source contains `spring`, `Easing.linear`, `Easing.back`, `Easing.elastic`, `Easing.bounce`, `Easing.bezier`, `TransitionSeries`, `@remotion/transitions`, `crossfade` or `dissolve`.
- The scene data has no `push`, punch-in, pulse or per-word stagger field.

(Amended 2026-10-23.)

### B-AC12 Claims checked (manual, before V3)

Given the V2 pull request, then its description quotes the R48 sources for `Local.`, `No telemetry.`, `Free.` and `The cheapest capable model, every step.`, and states that each still holds on the branch.

### B-AC13 Stills for approval (manual, V3)

Given `npm run stills:cli` runs, then the following exist in `video/out/cli-stills/`, each 3840x2160: one PNG per beat, plus `frame-first.png`, `frame-last.png` and the extra early-beat still (R45). On these stills, a reviewer checks R27, R28, R31, R34 and R42 against a real `galliacli` screenshot, and R61-R67, R74 and R76 by eye. The robot must read as the showcase robot, the desktop must show no real brand, and text and edges must be sharp at 4K. The reviewer also checks that the background visibly differs between the early and late stills, and that `frame-first.png` and `frame-last.png` match apart from the caption. The user approves the stills and the 1x preview (`preview:cli`), judging whether the drag intro, the load and the robot feel impactful and uncluttered (amended 2026-10-23).

### B-AC15 Motion budget (R49-R51)

Given `MOTIONS`, `activeAt` and the typing schedules, then:
- Each beat has at most one emphasized motion, and the emphasized kind of each beat equals the R46 Motion column.
- At no frame of the timeline do more than three elements animate, with the robot counted as one element on every frame it is on screen.
- Each beat contains a hold of at least 8 frames with no motion, gesture, typed character, new row or key change. The field, spinner, caret and robot idle are ignored.
- Failing fixtures are rejected by the same checks: two emphasized motions in one beat, a gesture in a beat that also has a `count`, and a frame with four animating elements.

(Amended 2026-10-23.)

### B-AC16 Rhythm, pace and start (R53-R55)

Given the scene data, then every beat start and every `CliMotion` start is a multiple of 15. The total is 840-1020 frames. Every caption segment is 60-180 frames. The hook caption cuts in at frame 0, and frame 0 shows the hero icon, the three generic icons and the terminal window (amended 2026-10-23).

### B-AC17 Typing and cost count (R52, R56)

Given each typing schedule, then `typedCount` is non-decreasing, the character intervals never grow, the last third is typed at least 1.5x faster than the first third, and typing completes inside the beat. The one allowed exception is the `at-file` beat: a single pause of at most 30 frames while the `@file` popup is fully shown, during which nothing in the foreground moves; the interval checks skip only that pause. A fixture with a pause in any other beat, a second pause in `at-file`, or a pause over 30 frames fails (amended 2026-10-28). Given each cost value over the timeline, then it never falls (R35) and its text length is constant.

### B-AC18 Loop seam (R57)

Given frame 0 and frame `DURATION - 1`, then `sceneState` is equal within 0.5 px and 0.01 opacity: the icon boxes and labels, the hero icon in its home slot (not hovered, scale 1), the window rectangle, its unfocused border and its empty shell line. At both frames there is no cursor, robot, TUI content or call to action. `backgroundField(DURATION)` deep-equals `backgroundField(0)`, and the caret blink state at `DURATION` equals its state at frame 0. The last 8 frames have no motion and no change other than the field and the caret blink. A fixture with the hero icon left in the window fails (amended 2026-10-23).

### B-AC19 Background field determinism and colors (R58-R60)

Given every frame from 0 to `DURATION`, then:
- `backgroundField(f)` called twice returns deep-equal results, and `backgroundField(DURATION)` deep-equals `backgroundField(0)`.
- There are 2-3 blobs and 2-3 waves.
- Every component period is 240-360 frames and divides `DURATION`. The per-frame phase step is constant, so the field does not react to beats. Wave parallax factors are distinct.
- Every color key is in the R59 list, and each gradient has at most one accent key.

Given `background.ts` and every other `GallianiCli` source, then none contains `filter`, `blur(`, `feGaussianBlur`, `drop-shadow`, `mix-blend-mode`, `<canvas`, `box-shadow` or `text-shadow`. The only images are the mark PNGs (B-AC9).

### B-AC20 Background restraint and contrast (R61, R62)

Given at least 8 frames (frame 0, the middle frame of each segment and the last frame), with `sampleField` evaluated on a 48 x 27 grid, then all of the following hold:
- Blob opacity is at most 0.18 and wave opacity at most 0.10.
- Every sample is within a 1.5:1 contrast ratio of `BRAND.bg`.
- HSL saturation is at most 0.35 outside the mark box.
- At most one accent hue is above 0.02 effective opacity, and `TUI.agent` is at most 0.02 while the mark (hero icon or end card) is on screen.
- Accent contribution above 0.05 covers at most 40% of the samples outside `terminalRect`.
- `BRAND.text` has at least 7:1 contrast against every sample inside each visible caption box, the call-to-action box and the `Galliani` label box. `BRAND.muted` has at least 4.5:1 against every sample inside each generic label box.

The sampled frames include every desktop beat's middle frame (amended 2026-10-23).

Given the terminal window style, then its fill is `TUI.bg` with no opacity below 1 and no backdrop effect.

### B-AC21 Framing (R63-R65)

Given every frame, then `terminalRect(frame)` lies inside the R42 margins (at least 96 px from the left and right, at least 54 px from the top and bottom). `transcriptOffset(frame)` is a multiple of `TERMINAL.row`, and every visible row top lies inside the transcript area with its full row height. Given the `END` layout, then the block's vertical center is within 4 px of 540 and its horizontal center within 4 px of 960.

### B-AC22 Desktop and drag (R66-R71)

Given `DESKTOP`, `cursorAt`, `heroIconAt` and `dragPath`, then all of the following hold:
- There are exactly three generic icons and one hero icon. The labels are `Galliani` plus members of `Notes`, `Files`, `Projects`. All boxes lie inside the safe area.
- The cursor is on screen only from the `cursor` start to the end of `desk-drop`, and its final tip point is inside the hero tile.
- The `drag` lasts 30-45 frames. At every frame of `desk-drag`, the hero icon's box is inside the safe area. The arc apex is at most 160 px from the chord. At the drag's end, the icon center is inside the window's content rectangle and stays there for at least 8 frames before `desk-drop`.
- The icon's scale is 1 and its rotation 0 throughout the drag.
- At the `absorb`'s end, the icon's scale is at most 0.15, its center is within 4 px of the caret, and its opacity is 0. The hero home slot is empty from the drag's start until `end-seam`.
- The window border is unfocused before `desk-drop` and focused from `desk-drop` until the `launch-expand` content cut.
- Failing fixtures are rejected: a drag path point outside the safe area, a drag that ends outside the window, and a 50-frame drag.

### B-AC23 Load (R72, R73)

Given the `launch-type` and `launch-expand` data, then:
- The shell typing is `TERM.command`, follows R52 and ends at least 8 frames before `launch-type` ends.
- At the `launch-expand` cut, no desktop icon is on screen and the window content is empty.
- During `expand`, `terminalRect` goes from the desktop window rectangle to the Act 3 rectangle, monotonically in each edge, inside the safe area, in 10-15 frames.
- The banner, prompt box, status line and robot appear on the first frame after the expansion and not before. No banner text is typed.

Given the terminal components, then the window size comes from the rectangle with no CSS `scale(` on any element that contains text.

### B-AC24 Robot reuse and colors (R74, R75, R77)

Given the test reads `video/src/Robot.tsx`, then every `ROBOT_SHAPES` entry's static attributes (`x`, `y`, `width`, `height`, `rx`, `cx`, `cy`, `r`, `ry`, `x1`, `y1`, `x2`, `y2`) equal the matching shape's literals in `Robot.tsx`. A fixture with one changed attribute fails.

Given `video/src/cli/robot.tsx`, then:
- It does not import `../Robot.tsx`, `../timeline.ts` or `../Showcase.tsx`.
- It contains no `filter`, `drop-shadow` or `Math.sin` outside the breathing function.
- The robot height is 180-240 px.

Given `robotPose` over the whole timeline, then:
- Outside gestures and blinks, every pose field except `breath` is constant, and `breath` stays within 3 px with one period of 60-120 frames.
- The blink frames are at least 90 apart and never fall inside a gesture.

`Robot.tsx`, `Showcase.tsx` and `src/timeline.ts` are unchanged against `main`. V3-QA checks this with `git diff`, and `tests/timeline.test.ts` keeps passing.

### B-AC25 Robot placement and gestures (R76, R78, R79)

Given every frame, then:
- `robotPose` is non-null exactly from the `launch-expand` content cut to the end of `end-card`.
- Its box is inside the safe area, at least 16 px outside `terminalRect`, and outside every caption box and the end-card block.
- The box position changes only on beat starts.

Given `GESTURES`, then:
- Each beat's gesture `pose` equals the R46 Robot column, and beats marked idle have none.
- Each gesture lasts at most 30 frames, starts on the 15-frame grid and stays inside its pose's angle and offset bounds.
- `point` aims within 20° of its target's center.
- `lower` starts on the frame `y` is pressed.
- No gesture's beat has another emphasized motion.

A fixture gesture in `route-first` (which has a `count`) fails.

### B-AC26 Render scripts and resolution (R80-R82)

Given the test reads `video/package.json`, then:
- `preview:cli` has no `--scale` below 1.
- `render:cli` contains `--scale=2`, `--codec=h264`, `--crf=N` with N at most 16, `--pixel-format=yuv420p`, and either `--image-format=png` or `--jpeg-quality=N` with N at least 95.
- `stills:cli` (or `scripts/cli-stills.ts`) passes `--scale=2`.
- The `dependencies` and `devDependencies` are unchanged.
- A fixture script with `--scale=0.5` for the preview fails.

Given the scene data and components, then no mark image is drawn larger than 320 authored px.

Given `video/README.md`, then it states the 3840x2160 output and the measured times and sizes (R82).

### B-AC27 Copy outside the terminal (R47, R67)

Given every string drawn outside the terminal, then it is one of: the seven captions, `galliacli`, `Galliani`, `Notes`, `Files` or `Projects`. None matches a brand or product name list kept in the test (operating systems, terminals, browsers, editors and AI vendors).

### B-AC14 Final render after approval (V4)

Given the user's approval is recorded (this spec's Status or the PR), when `npm run render:cli` runs, then `video/out/galliani-cli.mp4` exists at 3840x2160, 30 fps, 28-34 s, H.264 `yuv420p`, with `moov` before `mdat`, or the specific environment limitation is reported. The top-level box order is checked by reading the file's boxes, and the size and codec with Remotion's bundled ffprobe. No final render happens before approval (amended 2026-10-23).

## Tests (Part B)

- `video/tests/cli.test.ts`: B-AC2 to B-AC11 and B-AC15 to B-AC27 (pure Node; reads `../galliani/tui/styles.py`, `widgets.py`, `commands.py`, `src/Robot.tsx`, `package.json` and the `src/cli/` sources as text). The source scans of B-AC6, B-AC8, B-AC9, B-AC11 and B-AC19 cover every file under `src/cli/`, including `background.ts` and `robot.tsx`. Each new criterion has at least one failure-path case (a bad fixture that the check rejects).
- `video/tests/cli-qa.test.ts` (qa-security's independent checks) is updated for the new beats, kinds and robot. It is not deleted or weakened.
- `npm run typecheck` and `npm run smoke` (B-AC1).
- The existing `tests/timeline.test.ts` keeps passing unchanged (the showcase is untouched).
- Amended 2026-10-23: the tests for removed beats and kinds (`hook-mark`, `hook-prompt`, `launch-banner`, `push`, `entrance`, `move`) are replaced by the B-AC22-B-AC25 tests, not just deleted.

## Implementation Tasks (Part B)

- [x] V2.1 `video/src/cli/palette.ts` with the palette and color-literal tests (B-AC5, B-AC6), test first.
- [x] V2.2 `video/src/cli/timeline.ts`: beats, captions, terminal strings, layout boxes (R22, R32, R33, R36, R46), with the B-AC2 to B-AC4 and B-AC7 to B-AC11 tests.
- [x] V2.3 Capture the real banner lines, `@file` rows and route ids from a `galliacli` run in a demo folder (R33).
- [x] V2.4 `video/src/cli/GallianiCli.tsx` and terminal components; register in `Root.tsx` (R19).
- [x] V2.5 `render:cli` and `stills:cli` scripts and a `video/README.md` section.
- [ ] V2.6 Claims check in the PR (B-AC12).
- [x] V2c (ui-engineer, owns only `video/`). Rework for R37-R39 and R49-R65: `background.ts`, `CliMotion` data and the motion budget, typing schedule, retiming on the 15-frame grid, loop seam, framing fixes, and `stills:cli` extras (R45).
- [x] V2c-QA (qa-security). Privacy and determinism review of the V2c diff (B-AC8, B-AC9, B-AC11), with the scans covering `src/cli/**`.
- [ ] V3a (ui-engineer, opus, owns only `video/`; Decision 0038). Tests first: B-AC22 to B-AC27, with B-AC2 to B-AC6, B-AC10, B-AC11, B-AC15, B-AC16, B-AC18 and B-AC20 updated. Then build in this order:
  1. The R46 retiming to 960 frames. Field periods change to 240 and 320 (R60). The `push`, `entrance` and `move` kinds are removed, and `EASINGS` and the `easing` field are added (R38, R39).
  2. The desktop scene, hero and generic icons, cursor, hover state, drag arc, drop focus and absorb (R66-R71).
  3. The shell typing and window expansion, with whole-content cuts (R72, R73). The Act 3 terminal rectangle is resized so that the robot fits (R76).
  4. `robot.tsx`, `ROBOT_SHAPES`, the `ROBOT` palette group, idle breathing and blinks, the gesture schedule and poses, and placement (R74-R79).
  5. The end card with the wave, and the `end-seam` beat with `sceneState` (R57, R65).
  6. The scale flags in `package.json` and `cli-stills.ts`, and faststart (R81).
  7. A README section with the working title, the 4K output, and the measured render times and sizes of `preview:cli` and `render:cli`. The `render:cli` figures come from a timing run of a short frame range (for example `--frames=0-89`), extrapolated, because the full final render waits for V4 (R82).
  Exit: `npm test`, `npm run typecheck` and `npm run smoke` pass in `video/`. `tests/timeline.test.ts` is unchanged and passing. `npm run stills:cli` and `npm run preview:cli` run, and their paths are reported. The diff touches only `video/` (the `video/package-lock.json` noise excepted).
- [ ] V3-QA (qa-security, independent review of the V3a diff). Check:
  - B-AC8 and B-AC9 on the new code: no `Math.random`, `Date` or fetch in `robot.tsx` or the desktop code, and no new asset.
  - B-AC19's filter ban on `robot.tsx` (no `drop-shadow`).
  - B-AC27: no brand names, logos or real app icons on the desktop, and the cursor is an original drawing.
  - B-AC24's rule that the showcase files are unchanged.
  - The scans still cover `src/cli/**`.
  - `cli-qa.test.ts` is updated, not weakened.
  Exit: findings fixed or accepted by tech-lead.
  Verdict (2026-10-28, `video/tests/cli-v3qa.test.ts`): 0 High; Medium visual: the robot's arm is drawn under the head; Medium spec conflict: `route-next` (ruled, R46 and R78 amended); Low spec conflict: the at-file typing pause (ruled, R52 and B-AC17 amended); Low code: a 2 px cursor jump at the `desk-hover`/`desk-drag` cut. All open items go to V3b.
- [ ] V3b (ui-engineer, owns only `video/`). Fix the V3-QA findings, tests first:
  1. Fix the robot arm drawn under the head: the layer order matches `Robot.tsx`, and no arm is hidden by the head in any pose (R74).
  2. `route-next`: no second route id before step 4; the `glance` targets step 2's route line; step 4's route line shows the captured `google/gemini-3.1-flash-lite` in `verified-done` (R46, R78).
  3. The `at-file` pause stays within the R52 exception (one pause, at most 30 frames, popup fully shown, nothing else moving); the B-AC17 tests encode the exception and its failing fixtures.
  4. The cursor position is continuous across the `desk-hover`/`desk-drag` cut (no 2 px jump; R37).
  5. Turn the three `cli-v3qa.test.ts` todo findings into passing tests; do not weaken them.
  Exit: `npm test`, `npm run typecheck` and `npm run smoke` pass in `video/`; `npm run stills:cli` and `npm run preview:cli` rerun and their paths are reported; the diff touches only `video/`.
- [ ] V3 gate: stills (3840x2160) and the 1x preview to the user (B-AC13). Stop until the user approves. Any change to beats, gestures or captions after review is a spec amendment (R24).
- [ ] V4 Final 4K render (B-AC14), only after the user's approval is recorded. The user publishes.

## Open Questions (Part B)

- B1. `Free.` and `Local.` are true of the software (AGPL, no accounts, runs on your machine), but model requests go to a cloud provider and are billed to the user's own key. Keep the closing caption as is, or change it? Recommendation: keep it (it is the user-approved copy and the README supports it) and say "bring your own key" in the post text, not in the video. A change is a spec amendment.
- B2. The roadmap outline said the cost counter "ticks down" and a "model chip" is picked. The shipped TUI shows cost rising against the budget, and the model as `route <id>` in the status line plus a `·` route line. R27, R32 and R35 follow the shipped UI. Confirm at V3.
- B3. Closed by Decision 0038. The hook is now the desktop drag, and the hook punch-in question no longer applies.
- B4. The orchestrator's concept typed in the banner's version line after the load. R73 does not, because the TUI draws the banner whole (R34), and a type-in would compete with the `expand`. Revisit at V3 if the load feels flat. Adding it is a spec amendment.
- B5. Act 3 drops the two camera pushes (`goal-type`, `verified-done`), so the terminal stays still and the robot never overlaps it, and the gestures take those beats' one emphasized motion. Check at V3 that the result line reads well at 1x without the push. A push can come back only in a beat without a gesture, by amendment.
- B6. The desktop window's title bar shows the same title as the TUI frame before `galliacli` runs. A real shell window would show the shell's title. Recommendation: keep it, because it names the product and has no brand. Confirm at V3.
- B7. A 4K render with PNG frames may be slow. R81 allows JPEG frames at quality 95 or higher as the fallback. Decide at V4 from the measured R82 times.

## Dependencies (Part B)

- `017-interactive-cli` and `018-tui-polish` (implemented) for every surface shown.
- `003-model-router` and `docs/routing.md` for the routing caption.
- `016-public-launch` for the no-telemetry and privacy claims.
- Decision 0024 (showcase) and Decision 0025 (palette).
- `video/src/Robot.tsx` (showcase robot) as the read-only source of the robot drawing and colors (R74, R75).
- Decisions 0036, 0037 and 0038.

