# Galliani showcase video

A 28-second Remotion video (Decision 0024) filmed as one continuous shot. The chat bar appears and a coding prompt is typed and sent. Galliani then plans on Haiku 4.5 and routes the coding step to Sonnet 5.5. The Claude mascot pops out of the chosen model and high-fives the robot. The agent saves the files (with approval), runs the tests, and finishes with the model, cost and savings, and the diff. The current model and running cost stay in the card header the whole time. A tiny robot wanders the chat throughout: it trails the caret, hops on Send, watches each step, eyes the approval, cheers at done, and reads the result. At the end the logo builds itself: the G draws around its curve, and the robot zips into place and becomes the star. It uses a dark background, greyscale UI and smooth movement, with no cuts. The camera snaps in while typing and while the tasks load, eases between the moments that matter, and holds still for the logo reveal.

Output: `out/galliani-showcase.mp4` (1920x1080, 30 fps).

## Commands

```bash
npm install
npm test           # timeline order, robot and camera paths, prompt fit, deterministic source
npm run typecheck
npm run smoke      # loads the composition in Remotion
npm run render     # MP4
npm run poster     # still frame
npm run studio     # live preview
```

The first Remotion command downloads Chrome Headless Shell.

## Editing

- `src/timeline.ts`: the prompt, plan steps, result text, and every key frame.
- `src/timeline.ts` also holds the robot's path (`ROBOT_KEYS`), hops, cheer, and blinks.
- `src/Showcase.tsx`: the scene (greeting, chat bar, message, agent card, file card, logo end card).
- `src/Robot.tsx`: the robot, drawn in SVG.
- `src/Mascot.tsx`: a pixel-style Claude mascot (our own SVG drawing in Claude's terracotta) and the high-five spark.
- The model prices (USD per million tokens) and token counts are in `MODELS` and `USAGE` in `src/timeline.ts`. Cost and savings are computed from them: $0.059 spent and $0.081 saved (58%) against running every call on Opus 5.5. The token counts are illustrative.
- `src/camera.ts`: the camera path, a smooth curve through `CAMERA_KEYS` (focus point and zoom per moment) that never overshoots.
- `public/galliani-mark*.png`: the G-and-star mark cut out of the new logo (transparent). `galliani-mark.png` is the whole mark, and `-g` and `-star` are the separate pieces for the end-card animation.

The only assets are the logo pieces. Everything else is system fonts and inline SVG.

# Galliani in your terminal (`GallianiCli`)

Working title: "Drop Galliani into your terminal." A 32-second video of the shipped terminal UI, `galliacli` (spec 015 Part B, Decisions 0036-0038). It has 19 beats joined by hard cuts, on a 15-frame rhythm grid. A mouse drags the Galliani icon from a quiet desktop into a terminal window, `galliacli` is typed, and the window grows into the full TUI. There a goal is typed, the plan steps turn `[ok]`, each step is routed while the cost rises against the budget, `/` and `@file` complete, the inline approval card is answered, and the task ends verified and done. The showcase robot stands beside the terminal and guides each beat with one small gesture. The end card shows the mark and `galliacli`, then the video cuts back to the opening desktop, so it loops cleanly. A slow background field of soft gradient blobs and wave bands sits behind everything. The video has seven burned-in captions and no sound.

Output: `out/galliani-cli.mp4`, 3840x2160 (authored at 1920x1080, rendered at scale 2), 30 fps, 960 frames.

## Scenes

| Act | Beats | What happens |
|---|---|---|
| Hook (0-6 s) | `desk-idle`, `desk-hover`, `desk-drag`, `desk-drop` | The desktop with three generic icons and the hero icon; the cursor enters, hovers, drags the icon along one arc into the window, and the icon is absorbed into the caret |
| Launch (6-9 s) | `launch-type`, `launch-expand` | `galliacli` is typed after the shell prompt; the desktop clears and the window grows into the TUI frame; the banner, prompt, status line and robot cut in |
| Objective to plan (9-14 s) | `goal-type`, `plan-steps`, `plan-check` | The goal is typed; four plan steps appear; step 1 turns `[ok]` |
| Routing (14-18 s) | `route-first`, `route-next` | Route lines and the status-line route; the cost counts up once |
| Commands (18-22.5 s) | `slash-popup`, `at-file` | The `/` popup, then `@sig` completing to `@signup.py` |
| Control (22.5-26.5 s) | `approval-card`, `approval-wait`, `approval-answer` | The approval card enters, the robot raises a hand, `y` is pressed |
| Close (26.5-32 s) | `verified-done`, `end-card`, `end-seam` | Verified and done; the end card with the robot's wave; the cut back to the desktop |

## Commands

```bash
npm test             # also runs tests/cli.test.ts and tests/cli-qa.test.ts: palette, copied strings, captions, motion budget, desktop, drag, robot, loop seam, field, framing, render scripts, privacy
npm run stills:cli   # scale 2 (3840x2160) PNGs in out/cli-stills/: one per beat (its middle frame), frame-first, frame-last and launch-type-later-field
npm run preview:cli  # scale 1 (1920x1080) review MP4, out/galliani-cli-preview.mp4
npm run render:cli   # final 4K MP4: scale 2, H.264, CRF 16, yuv420p, PNG frames; only after the stills and preview are approved (spec 015 R45)
```

In Studio (`npm run studio`), pick `GallianiCli`. Remotion's output is already faststart (`moov` before `mdat`), so no extra ffmpeg step is needed.

Measured on the development machine (Windows 11, 2026-10-28):

| Script | Time | Size |
|---|---|---|
| `stills:cli` (22 stills at scale 2, one bundle) | 1 min 47 s | 1.8-4.0 MB per still |
| `preview:cli` (960 frames at scale 1) | 1 min 20 s | 3.5 MB |
| `render:cli` (timing run: `--frames=0-59` at scale 2, same flags) | 26 s for 60 frames, bundling included | 1.1 MB for 60 frames |
| `render:cli` (full 960 frames, extrapolated from the timing run) | about 7 min | about 18 MB |

The full 4K render has not been run; it waits for the user's approval (spec 015 V4). The extrapolation scales the 60-frame run by 16, so it overstates the time (the bundle is built once) and is a rough guide to the size (the TUI beats hold more detail than the desktop act).

## Motion budget

Every foreground motion is a `CliMotion` derived from the beats (`src/cli/motion.ts`): `caption`, `cursor`, `drag`, `absorb`, `expand`, `count`, `card` and `gesture`. Each beat has at most one emphasized motion (the R46 Motion column), at most three elements animate at any frame (the robot counts as one whenever it is on screen), and every beat holds still for 8 frames or more. Every beat and motion starts on the 15-frame grid. Easings come only from `EASINGS` (`outExpo`, `outQuart`, and `inOutCubic` for the cursor and the drag); there is no spring, overshoot or linear ramp. Typing speeds up over each string and finishes inside its beat.

## Editing

- `src/cli/timeline.ts`: every beat, frame, caption, layout box, typing schedule and terminal string, plus the desktop (`DESKTOP`), the robot's shapes, places, blinks and poses (`ROBOT_SHAPES`, `ROBOT_PLACE`, `ROBOT_BLINKS`, `POSES`) and gesture targets. Components hold none of their own.
- `src/cli/motion.ts`: `EASINGS`, `MOTIONS` and the motion-budget check (`budgetViolations`).
- `src/cli/desktop.ts`: the desktop act as pure functions of the frame: the cursor (`cursorAt`), the hero icon on its home slot, the drag arc and the absorb (`heroIconAt`, `dragPath`), the window focus and the typed shell line.
- `src/cli/pose.ts`: the robot's pose at each frame (`robotPose`): idle breathing and blinks, and the eight gestures (`lean`, `point`, `glance`, `nod`, `raise`, `lower`, `cheer`, `wave`).
- `src/cli/robot.tsx`: draws that pose. The shapes are copied from the showcase `src/Robot.tsx` (a test fails on drift), and it does not import the showcase.
- `src/cli/layout.ts`: the window rectangle at each frame (the desktop window, the `expand`, the Act 3 frame), the whole-row transcript scroll, the end-card block and the seam state (`sceneState`).
- `src/cli/background.ts`: the background field, a pure function of the frame built from cosines with 240- and 320-frame periods that divide the duration. It uses only palette colors at low opacity and SVG gradients.
- `src/cli/palette.ts`: the only colors. `BRAND` (showcase and mark) is for outside the terminal, `TUI` is for inside it, and `ROBOT` is for the robot only. `TUI` is a copy of `DARK_PALETTE` in `galliani/tui/styles.py` and `ROBOT` a copy of `GREY` in `src/Robot.tsx`; the tests fail if the copies drift.
- `src/cli/GallianiCli.tsx`: the desktop, the cursor, the terminal, the end card and the captions.
- Terminal strings are copied from `galliani/tui/widgets.py` and `commands.py`, and the tests check them against those files. The banner routing line, the transcript entries, the route ids, the costs and the `@file` rows come from the real TUI session, run headless in a demo folder with every provider mocked. If the TUI's wording changes, capture it again and update `TERM` and the entries in `timeline.ts`.
- The captions are fixed copy (spec 015 R46). Changing one is a spec amendment.
