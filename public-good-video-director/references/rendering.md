# HyperFrames rendering contract

Use HyperFrames as the primary renderer and Remotion as the compatibility fallback. HyperFrames requires Node.js 22 or newer, pnpm, ffmpeg/ffprobe, and a Chromium-compatible browser installed through its dependency chain.

The bundled invocation uses HyperFrames parallel workers, fast/page-side capture when supported by the installed version, and a project-local extracted-frame cache. `build/hyperframes/render-manifest.json` records dirty and reusable scene hashes. Dirty-scene detection reduces repeated asset preparation; it does not authorize a lossy splice across transitions or a changed audio timeline.

## Engine routing

`project.json.rendering` controls the default:

```json
{
  "engine": "hyperframes",
  "fallback": "remotion",
  "motion_profile": "silky"
}
```

Use `--engine auto` to follow the project and permit its recorded fallback. Use an explicit engine during diagnosis or comparison:

```bash
pg-video preview PROJECT --engine hyperframes
pg-video preview PROJECT --engine remotion
pg-video render PROJECT --engine auto
```

After every preview or final render, inspect `workflow/render-selection.json`. It is the source of truth for requested engine, actual engine, whether fallback occurred, and any primary-engine error. Never infer the engine from visual style alone.

## HyperFrames build

The runtime compiles `workflow/timeline.json` and project assets into `build/hyperframes/index.html`. It uses local GSAP, local HTML/SVG text, static audio elements, and deterministic time-based animation. The page contains:

- layered background, middle, and foreground motion;
- continuous camera drift and controlled parallax;
- paper wipes and overlapping scene transitions;
- timed labels, numbers, routes, arrows, focus rings, quotes, and CTA events;
- narration, music, and restrained event SFX aligned to the audio-derived timeline.

The layer builder writes independent background, transparent subject, and transparent foreground assets under `assets/layers`, and both renderers consume them. When layer extraction is unavailable, use a single continuously moving keyframe; do not duplicate arbitrary regional crops and call them depth layers.

## Smoothness rules

- Keep at least one continuous low-amplitude motion active; avoid full-frame stop-and-cut behavior.
- Use two or more depth speeds, but keep the subject readable and captions stable.
- Transition near semantic beat boundaries derived from the narration, not at arbitrary equal intervals.
- Render Chinese labels and facts locally; never depend on image-model typography.
- Use overlap transitions briefly enough that the current narration still has one dominant visual.
- Treat motion events as semantic emphasis, not decoration.

## Publication guard

After either renderer finishes, normalize the mix near -16 LUFS, encode AAC at 48 kHz, and enable MP4 `faststart`. Compare decoded frames 0 and 1: when frame 0 is an isolated dark initialization frame and frame 1 is the intended cover, replace frame 0 with a clone of frame 1 without moving the audio timeline. Record the result in `workflow/output-validation.json`, and require exact frame 0–3 samples in QA because duration-based black detection can miss a single bad frame.

## Static-complete cover exception

A designed title cover is not an ordinary scene when the user asks it to remain fixed. Mark the cover scene with `move: "static"` / `cover_mode: "static_complete"`, or run `scripts/set_static_cover.py PROJECT --scene 1` after the cover is imported. HyperFrames then:

- uses the original full-frame keyframe instead of separated depth layers;
- preserves its aspect ratio with no zoom, pan, parallax, wash, grain, headline animation, or opening wipe;
- delays the global brand/progress overlay until the next scene;
- keeps ordinary motion rules for later scenes.

Intentional static holds are acceptable inside a marked static scene. Treat other freeze-detector hits as review findings: inspect decoded frames and event timing to distinguish a real stall from sparse text animation below the detector's global difference threshold. Repair true unintended freezes; document specific verified false positives with timestamps and image evidence rather than disabling the detector or claiming all hits are harmless.

Long semantic subtitle cards use responsive typography classes. Do not shorten or split approved copy merely to keep one fixed font size.

## Accepting the existing MP4

User acceptance and render quality are different states. If the user says “就用这版 / 不用高清版”, do not run `render` again, change bitrate, synthesize speech, or re-open the choice. Keep the exact accepted MP4 at its current path (a requested copy must be byte-identical). Record `workflow/delivery.json` with `status: accepted_existing`, the project-relative `video`, its `sha256`, actual width/height/duration, `rerendered: false`, confirmation wording/time, and references to the checks for that file. Preserve preview approval and engine records instead of relabeling a draft render as a high-quality render. Acceptance is not permission to publish externally.

If known technical failures remain, disclose them without silently transcoding a version the user told you to keep. If the user requests later changes, preserve the accepted file and create a new review revision. Source, audio, timeline, template and layout changes require a fresh preview; old geometry and screenshots cannot approve a new render.

## Fallback

Fall back to Remotion only when HyperFrames is unavailable, fails to build, or fails preview validation. A fallback is successful only if it passes the same audio, subtitle, black-frame, aspect, duration, loudness, and contact-sheet QA. Record and report the actual engine and the reason for fallback.
