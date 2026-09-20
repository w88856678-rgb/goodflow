# Declarative production and cache workflow

Use this path for source-heavy roundups, recurring series, and revisions that would otherwise create date-specific Python, JavaScript, or HTML. It borrows the useful architecture of Pixelle-Video, Editly, MoneyPrinterTurbo, and Revideo without replacing HyperFrames or importing those projects as runtime dependencies.

## Invariants

- The Agent writes `workflow/scene-plan.yaml`; it does not create a new setup/compiler/capture program for each episode.
- Source assets have content-derived IDs in `workflow/source-manifest.json`. Refer to those IDs instead of embedding changing absolute paths throughout prompts and code.
- A scene contains only media that depicts its narration. `grouped_briefs` may combine several activities only when every named activity has its own correctly labeled media item.
- All source media defaults to `contain`. `cover` is reserved for a generated background or a verified layered story image; it must not crop a person, title, product, logo, or activity information.
- Use the fixed layout registry in `assets/runtime/layouts/registry.json`. Add a reusable layout only after two real projects need it. Keep one-off design decisions inside the project plan.
- Dynamic scenes still need three meaningful events. Do not let the compiler invent decorative events merely to satisfy a count.
- Scene hashes are advisory until a preview passes. Never reuse an old rendered scene after narration, timing, layout, template, or referenced media changed.

## Commands

Create a content-addressed source index and cache:

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" index
```

Create a compact plan from the current project/storyboard:

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" init-plan
```

Edit only `workflow/scene-plan.yaml`, then compile it into the existing `project.json` keyframe contract:

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" compile
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" changes
```

The compiler rejects unknown layouts, missing assets, out-of-range reveal times, media-count violations, duplicate scene IDs, dynamic scenes with fewer than three semantic events, and narration that no longer equals the approved script. It invalidates stale timelines and preview approvals.

After compilation, continue with safe-zone analysis, audio alignment, timeline generation, HyperFrames preview, layout QA, and the normal approval gate. `changes` writes `workflow/incremental-render-plan.json`; unchanged scene assets and extracted frames remain cached, but the bundled renderer still performs a full video encode when that is necessary to preserve cross-scene transitions and audio continuity.

## Scene-plan shape

```yaml
version: 1
defaults:
  transition: paper_wipe
  fit: contain
scenes:
  - id: cover
    narration: ""
    layout: static_complete
    media:
      - asset: asset-0123456789ab
        role: cover
        at: 0
    cues: ["开场"]
    headline: ""
    events: []
  - id: activity-one
    narration: "茶百道的杯套扫一扫，就能为乡村儿童教育送出一份善意。"
    layout: hero_support
    media:
      - asset: asset-aabbccddeeff
        role: hero
        at: 0
      - asset: asset-112233445566
        role: support
        cue: "乡村儿童教育"
        at: 0.48
    cues: ["茶百道"]
    headline: "把日常选择变成守护"
    events:
      - {type: paper_label, at: 0.08, text: "茶百道"}
      - {type: fact_stack, at: 0.42, items: ["扫一扫", "送出善意"]}
      - {type: underline, at: 0.72, text: "乡村儿童教育"}
```

`narration` is used for integrity checking and scene hashes. The approved script remains the only spoken source of truth.
