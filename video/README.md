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
