# 015 - Remotion Video

## Status

Draft for v0.1 marketing and product explanation.

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

