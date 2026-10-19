# 015 - Remotion Video

## Status

Draft for v0.1 marketing and product explanation (Part A, the explainer).

Amended 2026-10-20 (Decision 0036): Part B adds a second composition, `GallianiCli`, the CLI-update video. Part B is Accepted: the user said "start the CLI update video", and its storyboard and caption table (roadmap section "Video: Galliani in your terminal") are the user-approved starting point.

## Compositions and scope

The Remotion project in `video/` holds these compositions:

| Composition | What it is | Governed by |
|---|---|---|
| `GallianiShowcase` | The 28-second product showcase | Decision 0024 (sets Part A aside for this video) |
| `GallianiCli` | The 20-30 second CLI-update video | Part B of this spec (R19-R48) |
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

Added 2026-10-20 (Decision 0036). Roadmap items V0-V4.

## Goal

A 20-30 second motion-graphics video that shows the shipped terminal UI (`galliacli`, specs 017 and 018): a goal typed in the prompt box becomes a supervised plan, each step is routed, the user approves what matters, and the task ends verified and done. Modern, minimal, kinetic, and readable with the sound off.

## Non-goals

- Showing behavior that is not shipped. Streaming output and session resume are not built (Decision 0034 "Not in v1"); they never appear, not even as "coming soon".
- New colors, new image assets, external fonts, music, voice-over or generated speech.
- A vertical 9:16 cut. It is a later option and needs its own amendment of this spec.
- Changing the showcase (`GallianiShowcase`) or Part A.
- Publishing. The user publishes (roadmap V4).

## Requirements

### Format and structure

19. A second Remotion composition with id `GallianiCli` is registered in `video/src/Root.tsx` alongside `GallianiShowcase`. The showcase is unchanged.
20. Format: 16:9, 1920x1080, 30 fps.
21. Duration: 20-30 seconds; the target is 25 s (750 frames).
22. All timing, copy, terminal text and colors live in structured scene data (`video/src/cli/timeline.ts` and `video/src/cli/palette.ts`), in the style of `video/src/timeline.ts`. Components read scene data; they hold no copy, frame numbers or color values of their own.
23. The video is a sequence of beats (shots). Each beat lasts 1-3 seconds (30-90 frames). Beats are contiguous: the first starts at frame 0, each starts where the previous ends, and the last ends at the composition's last frame.
24. The beat order and content follow the storyboard table (R46). A change to the order, the beats or the caption text is a spec amendment approved by the user.

### Brand, color and type

25. The palette is exactly two groups, copied as values into `video/src/cli/palette.ts`:
    - `BRAND`, from the showcase and the mark: `bg #0A0A0B`, `surface #141416`, `raised #1C1C1F`, `text #EDEDEF`, `muted #8B8B92`, `accent #D97757`.
    - `TUI`, all ten keys of `DARK_PALETTE` in `galliani/tui/styles.py`, with the same keys and values (`bg`, `surface`, `border`, `fg`, `muted`, `accent`, `good`, `warn`, `bad`, `agent`). `styles.py` is the source of truth; a test fails when the copies drift.
26. No color literal (hex, `rgb()`, `rgba()`, `hsl()`, `hsla()`, or the keywords `white` and `black`) appears in any `GallianiCli` source file other than `palette.ts`. Transparency uses an opacity property, not a new color. `transparent` is allowed.
27. Inside the terminal frame, colors map to TUI tokens as `APP_CSS` in `galliani/tui/styles.py` assigns them: user lead `>` `accent` bold; plan entry text `fg` bold; route, retry and replan lines `muted`; verification lead `agent`; approval and question lines `warn`; result lead `good`; error `bad`; plan steps pending `muted`, running `accent`, waiting `warn`, verified `good`, failed `bad`; banner border `border`, banner tips `muted`; prompt box border `border`, focused `accent` (heavier); status line `muted`; completion popup background `surface`; approval card border `warn`; working line `accent`; terminal background `bg`.
28. Outside the terminal frame (the canvas, the hook, the end card, captions) only `BRAND` colors are used. `BRAND.accent` (orange) is used only by the mark and the hook caret; it never appears inside the terminal frame.
29. Fonts: Inter for headlines and captions (`"Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif`) and Cascadia Mono for terminal text (`"Cascadia Mono", Consolas, "SF Mono", Menlo, monospace`), the same stacks as the showcase. System fonts only: no font file, no `@font-face`, no font package.
30. Assets: only `video/public/galliani-mark.png`, `galliani-mark-g.png` and `galliani-mark-star.png`. No new file in `video/public/` and no new npm dependency.

### What is shown (real, shipped behavior only)

31. Only these shipped TUI surfaces appear: the welcome banner, the prompt box, the status line, the working line, plan steps, the `/` completion popup, `@file` completion, the inline approval card, the verification entry and the done result.
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

37. Beat boundaries are hard cuts. No dissolve or fade between beats.
38. Within a beat, motion is limited to: typing at a fixed rate, kinetic caption entry (snap, slide or scale in, at most 8 frames, slide at most 32 px, scale from at least 0.92), rows appearing one by one, glyph and color state changes, and short camera pushes (at most 15 frames, zoom at most 1.15x). Step-state changes are instant, as in the TUI (spec 018 R11).
39. Easing uses Remotion `interpolate` and `Easing`. Opacity ramps last at most 4 frames.

### Captions

40. Captions are burned in, in Inter, in `BRAND.text`, at least 56 px, one caption at a time, one line each.
41. Caption text is exactly the strings in the storyboard table (R46), character for character, including the final period. The `@` in `Slash commands. @ files.` may be set in Cascadia Mono.
42. Captions sit inside the 90% title-safe area (at least 96 px from the left and right edges, at least 54 px from the top and bottom) and never cover the terminal element the beat is about (checked on the stills, R45).
43. Each caption is on screen for the whole of its segment (2-5 s).

### Determinism, approval and storyboard

44. The render is deterministic: `GallianiCli` sources use no `Math.random`, `Date.now`, `new Date`, `performance.now`, `fetch`, timers or network access; any pseudo-randomness uses Remotion `random(seed)`.
45. Before any final render, `npm run stills:cli` renders one PNG per beat (at the beat's middle frame) to `video/out/cli-stills/<beat-id>.png`, and the user reviews the stills and a Studio preview (roadmap V3). The final render `npm run render:cli` (to `video/out/galliani-cli.mp4`) runs only after the user approves.
46. Storyboard and exact captions (frames at 30 fps; total 750 frames = 25 s; frame ranges are start-inclusive, end-exclusive):

    | Beat id | Segment | Frames | Seconds | On screen | Caption (exact) |
    |---|---|---|---|---|---|
    | `hook-mark` | Hook | 0-45 | 0-1.5 | Black (`BRAND.bg`). The orange mark snaps in. | `Galliani now runs in your terminal.` |
    | `hook-prompt` | Hook | 45-90 | 1.5-3 | The mark moves aside; a blinking prompt `>` | (same caption) |
    | `launch-type` | Launch | 90-150 | 3-5 | `galliacli` typed on a Cascadia Mono shell line | `One command.` |
    | `launch-banner` | Launch | 150-210 | 5-7 | The terminal opens on the welcome banner, prompt box and status line | (same caption) |
    | `goal-type` | Objective to plan | 210-270 | 7-9 | The objective (R36) is typed into the focused prompt box | `Type a goal. Watch the plan.` |
    | `plan-steps` | Objective to plan | 270-330 | 9-11 | Plan entry; four step rows appear one by one as `...` pending, step 1 `>` running; working line `Planning…` | (same caption) |
    | `plan-check` | Objective to plan | 330-360 | 11-12 | Step 1 turns `[ok]` verified (`good`); step 2 running | (same caption) |
    | `route-first` | Routing | 360-420 | 12-14 | A route line `·` for step 2; the status line shows `route <id>`; cost ticks up | `The cheapest capable model, every step.` |
    | `route-next` | Routing | 420-480 | 14-16 | Step 2 `[ok]`; step 3 is routed to a different id; `step 3/4` | (same caption) |
    | `slash-popup` | Commands | 480-540 | 16-18 | Cut to an idle prompt: `/` opens the completion popup with the real command rows | `Slash commands. @ files.` |
    | `at-file` | Commands | 540-600 | 18-20 | `@sig` completes to a workspace file path from the popup | (same caption) |
    | `approval-card` | Control | 600-645 | 20-21.5 | The inline approval card for the write step (step 3 `[?]` waiting, `warn`) | `You approve what matters.` |
    | `approval-answer` | Control | 645-690 | 21.5-23 | `y` is pressed; the card closes; step 3 runs and turns `[ok]` | (same caption) |
    | `verified-done` | Close | 690-720 | 23-24 | Step 4 `[ok]`; verification entry `●` (`agent`); result `●` (`good`) `Status: done - ...` | `Local. No telemetry. Free.` |
    | `end-card` | Close | 720-750 | 24-25 | The mark and `galliacli` on `BRAND.bg` | (same caption) |

47. Copy rules (Part A Copy Rules also apply): only the seven captions above appear as copy outside the terminal; no "magic", no claim of unrestricted autonomy, no competitor names, no invented metrics; no chain-of-thought or model "thinking" text (the working-line verbs are fixed UI strings); no real API key, key prefix, token, username, home path or log on screen; the workspace path is a demo folder (for example `C:\dev\signup-app`).
48. The claim captions are checked before stills review (V3), and the check is recorded in the PR description with the source lines:
    - `No telemetry.`: `README.md` ("Galliani has no accounts and sends no telemetry") and `site/src/privacy.tsx` ("There is no telemetry, analytics, crash reporting or account").
    - `Free.`: `README.md` License section (AGPL-3.0 free software; no paid tier exists). Model requests are billed by the provider to the user's own key; see Open Question B1.
    - `Local.`: `README.md` ("The only network calls are the model requests you make with your own key"); see Open Question B1.
    - `The cheapest capable model, every step.`: `docs/routing.md` (`auto` mode instruction "pick the cheapest model that will answer it completely and correctly") and per-step routing (`route_selected` carries a `step_id`, `galliani/workers.py`). The banner in the video shows `routing: auto`.
    If any source no longer supports a claim, stop and ask the user; do not reword the caption.

## Interfaces and Data Contracts (Part B)

- `CliBeat`: `id`, `segment`, `start` (frame), `duration` (frames), `shot` (which terminal state or card is shown), `push?` (`{from, to, frames}`, zoom 1.0-1.15).
- `CliCaption`: `segment`, `text`, `start`, `end` (frames), `box` (`{x, y, width, height, fontSize}`), `enterFrames`.
- `CliPalette`: `BRAND` and `TUI` as in R25.
- `CliTerminal`: the copied terminal strings of R32-R33 (banner lines, placeholder, glyphs, popup rows, approval lines, status and working line pieces).
- `CLI_RENDER`: `{compositionId: 'GallianiCli', fps: 30, width: 1920, height: 1080, durationInFrames, output: 'out/galliani-cli.mp4', stillsDir: 'out/cli-stills'}`.
- npm scripts in `video/package.json`: `render:cli`, `stills:cli`. Existing scripts keep targeting the showcase. `video/out/` is already git-ignored.

## Security (Part B)

- No secret, key, key prefix, real username, real home path, raw log or provider response appears in scene data or on screen (R47).
- No hidden reasoning or chain-of-thought text is shown or implied; the working line uses the fixed `VERBS` strings.
- Provider and model ids appear only as route ids, under a banner that says `routing: auto`, so the video stays provider-neutral.
- No new asset or font; nothing is fetched at render time (R30, R44).

## Acceptance Criteria (Part B)

Automated criteria run with `npm test` in `video/` (Node test runner, like `tests/timeline.test.ts`), plus `npm run typecheck` and `npm run smoke`.

### B-AC1 Composition registered

Given `npm run smoke` runs, then both `GallianiShowcase` and `GallianiCli` are listed, and `GallianiCli` is 1920x1080 at 30 fps.

### B-AC2 Duration

Given the scene data, then the total frame count divided by 30 is between 20 and 30 seconds and equals the composition's `durationInFrames`.

### B-AC3 Timeline order and beat length

Given the beats, then their ids and order equal the R46 table, the first starts at 0, each starts where the previous ends, the last ends at the total, and every beat is 30-90 frames.

### B-AC4 Captions exact and timed

Given the captions, then there are exactly seven, their texts equal R46 character for character, each covers its whole segment, and together they cover the timeline without gaps or overlaps.

### B-AC5 Palette equals styles.py

Given the test reads `galliani/tui/styles.py`, then `TUI` in `palette.ts` has exactly the keys and values of `DARK_PALETTE`, and `BRAND` equals R25 (and matches the `C` values in `Showcase.tsx` and `ORANGE` in `Mascot.tsx`).

### B-AC6 No color literal outside the palette

Given every `GallianiCli` source file except `palette.ts`, then none contains a color literal as defined in R26; and every value in `palette.ts` is one of the 16 R25 values.

### B-AC7 Real terminal strings

Given the test reads `galliani/tui/widgets.py` and `galliani/tui/commands.py`, then the banner tips, placeholder, lead glyphs, step glyphs, spinner frames, working-line verbs, approval title and key line in scene data appear verbatim in those files, popup rows match `COMMANDS` labels and summaries, and every plan step line matches the `step_line` format.

### B-AC8 Shipped behavior only, nothing private

Given all scene data text, then it contains none of `stream`, `resume`, `--continue`, `thinking`, `chain-of-thought`, `reasoning` (case-insensitive); and nothing matching a key pattern (`sk-`, `Bearer `, `API_KEY`), a user home path (`C:\Users\`, `/home/`, `/Users/`) or an email address.

### B-AC9 Deterministic source

Given the `GallianiCli` sources, then none contains `Math.random`, `Date.now`, `new Date`, `performance.now`, `fetch(`, `setTimeout` or `setInterval`; `video/public/` holds only the three mark PNGs; and `package.json` dependencies are unchanged.

### B-AC10 Captions within safe margins

Given each caption's `box`, then it lies inside the 90% title-safe area (R42), the font size is at least 56 px, and the estimated width (characters x font size x 0.6) fits the box width on one line.

### B-AC11 Motion bounds

Given each beat's push and each caption's entry, then pushes last at most 15 frames with zoom at most 1.15x, caption entries last at most 8 frames, and no beat boundary carries a transition (hard cuts).

### B-AC12 Claims checked (manual, before V3)

Given the V2 pull request, then its description quotes the R48 sources for `Local.`, `No telemetry.`, `Free.` and `The cheapest capable model, every step.`, and states that each still holds on the branch.

### B-AC13 Stills for approval (manual, V3)

Given `npm run stills:cli` runs, then one PNG per beat exists in `video/out/cli-stills/`; a reviewer checks R27, R28, R31, R34 and R42 on them against a real `galliacli` screenshot; and the user approves the stills and a Studio preview.

### B-AC14 Final render after approval (V4)

Given the user's approval is recorded (this spec's Status or the PR), when `npm run render:cli` runs, then `video/out/galliani-cli.mp4` exists at 1920x1080, 30 fps, 20-30 s, or the specific environment limitation is reported. No final render happens before approval.

## Tests (Part B)

- `video/tests/cli.test.ts`: B-AC2 to B-AC11 (pure Node; reads `../galliani/tui/styles.py`, `widgets.py`, `commands.py` and the `src/cli/` sources as text).
- `npm run typecheck` and `npm run smoke` (B-AC1).
- The existing `tests/timeline.test.ts` keeps passing unchanged (the showcase is untouched).

## Implementation Tasks (Part B)

- [ ] V2.1 `video/src/cli/palette.ts` with the palette and color-literal tests (B-AC5, B-AC6), test first.
- [ ] V2.2 `video/src/cli/timeline.ts`: beats, captions, terminal strings, layout boxes (R22, R32, R33, R36, R46), with the B-AC2 to B-AC4 and B-AC7 to B-AC11 tests.
- [ ] V2.3 Capture the real banner lines, `@file` rows and route ids from a `galliacli` run in a demo folder (R33).
- [ ] V2.4 `video/src/cli/GallianiCli.tsx` and terminal components; register in `Root.tsx` (R19).
- [ ] V2.5 `render:cli` and `stills:cli` scripts and a `video/README.md` section.
- [ ] V2.6 Claims check in the PR (B-AC12).
- [ ] V3 Stills and preview to the user (B-AC13). Stop until the user approves.
- [ ] V4 Final render (B-AC14). The user publishes.

## Open Questions (Part B)

- B1. `Free.` and `Local.` are true of the software (AGPL, no accounts, runs on your machine), but model requests go to a cloud provider and are billed to the user's own key. Keep the closing caption as is, or change it? Recommendation: keep it (it is the user-approved copy and the README supports it) and say "bring your own key" in the post text, not in the video. A change is a spec amendment.
- B2. The roadmap outline said the cost counter "ticks down" and a "model chip" is picked. The shipped TUI shows cost rising against the budget, and the model as `route <id>` in the status line plus a `·` route line. R27, R32 and R35 follow the shipped UI. Confirm at V3.

## Dependencies (Part B)

- `017-interactive-cli` and `018-tui-polish` (implemented) for every surface shown.
- `003-model-router` and `docs/routing.md` for the routing caption.
- `016-public-launch` for the no-telemetry and privacy claims.
- Decision 0024 (showcase) and Decision 0025 (palette).

