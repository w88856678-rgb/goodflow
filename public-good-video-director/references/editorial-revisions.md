# Source-image editing and incremental visual revisions

Read for existing-video audits, selected visual fixes, and source-heavy multi-business updates. This is not a requirement to redesign every short story or to use today's voice/layout forever.

## Scope and preservation

1. Identify the exact current MP4 and its project; do not assume the newest file is the accepted one. Inspect the selected revision and source images.
2. For an audit, capture fresh frames and list scene/time, visible problem and proposed fix. Do not edit until requested.
3. For selected fixes, save the old template/configuration and current MP4 outside the active build. Record hashes of approved script, audio and timing inputs. Only change the selected scope. Other suggestions remain suggestions.
4. Prefer layout, crop and sequencing changes over regenerating authorized source media. Reuse voice, rate, pronunciation aliases and timings. Do not invent scenes, change facts or drop businesses to improve a layout.
5. Keep project-specific source names, business counts, voice auditions, dates and line breaks in the project. Never copy a one-off campaign into the global default template.

## Choose a composition from the source

| Source / purpose | Useful treatment | Avoid |
|---|---|---|
| Game character or product | Remove empty source margins; enlarge proportionally with complete subject | Stretching, clipped hands/feet, giant white mat |
| Landscape banner + result | Wide source image and separate number/explanation region | Landscape art squeezed into a tall card |
| Person | Large portrait window with clear face, hands and relevant object | Decorative tags over subject |
| Two related moments | One main/one supporting image, or sequential replacement on a spoken cue | Shrinking both to unreadable thumbnails |
| Long activity poster/map | Readable source windows, with a pan inside real pixels | Treating tiny full-poster text as readable |
| Low-resolution original | Modestly sized supporting image anchored to the main fact | Hard upscaling and claiming “HD” |
| Certificate / proof | Whole meaningful document region or deliberate readable detail | Unexplained narrow crop that removes its meaning |

Keep shared type, margins and palette. Choose only layouts the material needs, not a mandatory quota. Reserve the actual full-caption height and headline band before positioning media. Pair a number with its qualifier as one protected block. When content is too dense, simplify duplicate on-screen labels or show them sequentially; changes to approved narration or business coverage need user agreement.

## Narration-driven events

Within a beat, distinguish an establishing image from a later emphasis. Locate each cue in that beat's word-boundary transcript, including speech-only aliases; repeated phrases must not match another scene. Record cue, absolute seconds, alignment source, target element and action in `workflow/visual-events.json`. Convert seconds to the renderer's actual timing convention (see `motion.md`). Do not guess evenly spaced times when word boundaries exist.

A useful progression is subject → action/detail → result/meaning, but the narration determines the order. Reveal a secondary image when its subject is mentioned; show a number on the spoken figure; keep a visual anchor during a crossfade/reflow. An approved static cover stays still. Do not add arbitrary rings, tape, shake or useless labels to satisfy an event count. Inspect the actual rendered events; generic `motion_events` entries ignored by a custom template are not evidence of movement.

## Whole-sentence captions with readable line breaks

Temporal segmentation and visual wrapping are separate decisions. Keep a whole approved sentence/card on screen for its existing time; add line breaks without changing any letters or punctuation. Where appropriate, use a project-local `lines` field in `workflow/timeline.json` captions (or aligned input captions):

```json
{"from": 0.0, "to": 4.0, "text": "戴上小红花头像框，一块做好事。", "lines": ["戴上小红花头像框，", "一块做好事。"]}
```

`lines.join("")` must equal `text` exactly. The bundled HyperFrames and Remotion renderers support it; custom templates must support it explicitly too. A visual line break is not a new caption timestamp. Preserve multi-character nouns, names, number-unit pairs and complete date ranges on the same line. Keep project-specific phrase lists local rather than growing a universal dictionary of campaign names.

Measure with the actual font after it loads. Check each line's `scrollWidth <= clientWidth`, caption bounds, and overlap with source panels. If a full sentence needs several lines, reserve a taller caption region and reduce competing content; do not repeatedly shrink the font or automatically cut at a character count. If the sentence cannot fit legibly, propose a script/clause revision for approval. Missing manual lines may use normal wrapping, but that is not a successful semantic wrapping review.

## Actual-layout QA contract

Use the host's permitted rendering/capture tools. This helper does not install a browser or invent permission to automate one. Capture early, middle and late states for every scene, plus cue/transition states; for moving/reflowing layouts, add a roughly 100–200 ms geometry sweep. Then inspect fresh decoded MP4 samples, including frames 0–3.

Export a project-local JSON file with `scenes` (positive count) and `records`. Each record includes:

- `scene_id`, `time` in seconds, and optional `phase`;
- `opaqueCards`: whole visible opaque media-card rectangles, including white border/mat;
- `protected`: visible protected source-image/subject rectangles;
- `overlays`: visible headline, number+qualifier, tag and other text rectangles;
- `captions`: visible full subtitle-card rectangles;
- `captionLines`: visible line rectangles with `scrollWidth` and `clientWidth`.

Rectangles use `{x, y, width, height}` in canvas pixels, with optional `text`. Supply `canvas: {width, height}` at the document root when not 1080 × 1920. Compute post-transform visible bounds, including ancestor opacity/display and clipping; exclude hidden outgoing nodes. Empty arrays are valid in a scene without that element, but missing fields or missing scenes are not a pass. For intentional overlapping photo transitions, only exempt photo-to-photo overlap, not either card against text. Capture provenance and video/template hashes alongside the records so stale snapshots cannot be mistaken for current ones.

```bash
python "$SKILL_DIR/scripts/validate_visual_layout.py" \
  "$PROJECT/qa/layout-capture.json" --output "$PROJECT/qa/visual-layout-check.json"
```

The checker validates geometry and measured line widths, not facts, audio sync, source crop semantics, exact transcript identity or aesthetic quality. Compare flattened caption text against the approved caption transcript separately. Inspect full source-card bounds as well as inner image bounds: a white border can hide text while the inner-image collision test passes. A custom template requires its own fresh records; never reuse generic saliency/event boxes as certification.

After changing the checker or bundled subtitle code, run `python "$SKILL_DIR/scripts/test_video_regressions.py"`. Also render a long-sentence sample with the actual font; unit tests cannot establish on-screen readability.

Review freeze-detector hits in decoded samples: static covers can be intentional, sparse text reveals can produce threshold alerts, and actual long unintended holds must be repaired. Keep specific evidence for any dismissed alert. Do not claim social-platform overlay safety without an actual target-platform preview.

## Finish at the requested quality

Deliver the checked revision for confirmation. When the user accepts it and says no higher-quality version is needed, retain that exact file and record acceptance per `rendering.md`. Do not render again just to create a `final.mp4` filename. Updating this Skill later must not silently re-render or change the accepted video.
