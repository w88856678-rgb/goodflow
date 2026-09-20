# Layered motion scene contract

Use this reference when inspecting or editing `workflow/storyboard.json`.

Each narration beat must map to one scene with:

- `scene`: a concrete visual that directly represents the spoken fact;
- `headline`: no more than nine Chinese characters, rendered locally;
- `image_prompt`: background and illustration only, with no generated text;
- `move`: continuous camera motion;
- `depth`: normally `layered`;
- `transition`: `paper_wipe`, `map_push`, `paper_roll`, or `ink_reveal`;
- `motion_events`: three to five timed internal events.

Example:

```json
{
  "id": 3,
  "narration": "过去，有的孩子从家里带饭。",
  "headline": "午饭各有去处",
  "move": "parallax",
  "depth": "layered",
  "transition": "paper_roll",
  "motion_events": [
    {"type": "paper_label", "at": 0.08, "text": "午饭各有去处", "sfx": "paper"},
    {"type": "fact_stack", "at": 0.36, "items": ["在校用餐", "回家吃饭", "从家带饭"], "sfx": "whoosh"},
    {"type": "underline", "at": 0.67, "text": "午饭有了新的安排", "sfx": "tap"}
  ]
}
```

`at` is a fraction of scene duration. Fractions near 0.08, 0.35 and 0.65 are planning placeholders, not final narration synchronization. With aligned audio, locate each cue inside its own beat, disambiguate repeated words, and compile `at = (cue_time - scene.start) / scene_duration`. Keep the original cue, absolute time and alignment method in a project-local event manifest. Missing matches require review or an explicitly labeled estimate, not a silent zero-time fallback.

Spread meaningful changes across the narration: subject first, then a relevant detail, then a number or consequence when spoken. A secondary photo can replace or reflow the first without changing the sentence or extending the approved audio. Keep a visual anchor during that exchange; do not fade the outgoing image completely before the incoming one begins. Do not populate every event at scene entry and call a small later drift a semantic event.

Static covers are exempt. Short transitions need not be crowded with decorations to reach a count. For source-photo scenes, see [editorial-revisions.md](editorial-revisions.md); pan only inside available source pixels, and keep faces, hands and text intact throughout reflow. Captions stay stable while source elements move. Custom templates must report the events they actually draw, not unused generic storyboard entries.

Available events:

- `paper_label`: local Chinese headline strip;
- `route_draw`: SVG route drawn over time;
- `pin_drop`: map or fact-location emphasis; use only with an explicit target coordinate;
- `focus_ring`: circular attention cue; use only with an explicit target box;
- `number_card`: locally rendered verified number;
- `underline`: hand-drawn emphasis under local text;
- `fact_stack`: staggered, source-grounded keyword cards for products, crafts, or participant groups;
- `cause_flow`: a three-step local-text sequence for verified cause-and-effect relationships;
- `arrow_in`: directional cue; use only when its start, direction, and target are explicit;
- `steam_rise`: subtle continuous food warmth;
- `quote_reveal`: short verified quote;
- `cta_reveal`: final call to action.

Use verified text only. Never ask the image model to render Chinese characters, arrows, labels, dates, or statistics.

Do not use a pointer event merely to satisfy the three-event minimum. Prefer `fact_stack`, `cause_flow`, `number_card`, or `underline` when no target geometry is available. Read [visual-hierarchy.md](visual-hierarchy.md) before placing any persistent overlay.

Run `analyze_safe_zones.py` before timeline generation. Persistent semantic overlays receive a `layout` rectangle selected from negative space; pointer events still require an explicit `target` and never inherit a generic safe box as a fake target.

Run `build_layers.py` before rendering. HyperFrames and Remotion both consume real background, transparent subject, and transparent foreground assets when present, moving them at different restrained rates. If layer extraction is unavailable, render one continuously moving keyframe rather than duplicating arbitrary regional crops and presenting them as real depth.
