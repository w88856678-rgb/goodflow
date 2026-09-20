# Pacing for hotspot and multi-business roundups

Use this reference for `热点播报`, daily campaign recaps, and source-heavy progress summaries. It is not the default for intimate beneficiary or personal stories.

## Plan before script approval

Write `workflow/pacing-plan.json` before producing script variants. Record:

- `mode`: `roundup`;
- `target_duration_seconds` as a range;
- the selected voice and auditioned rates;
- `cover_hold_seconds`, normally 1.8–2.0 for a supplied static cover;
- `transition_seconds`, normally 0.25–0.35;
- `meaningful_change_interval_seconds`, normally 1.5–2.5;
- every source item with `tier`, `target_seconds`, and its supporting image IDs.

Use three editorial tiers:

- **Lead:** the strongest two or three stories; usually 8–12 seconds each and allowed a concrete detail.
- **Supporting:** necessary context; usually 5–8 seconds each.
- **Brief mention:** must remain covered but can share a compact sentence or grouped visual; usually 3–5 seconds each.

These are planning ranges, not fixed quotas. Never drop a business, name, date, number, or required fact merely to hit a duration. If the approved coverage cannot fit naturally, show the longer estimate before script approval.

## Compress without flattening

Aim to shorten repeated framing and duplicated conclusions before increasing speech rate. Combine low-priority activities only when the sentence and accompanying images remain unambiguous. Keep each named activity next to its exact action or result. Do not combine unrelated images beneath one caption.

For dense roundups, a useful structure is:

1. one short hook;
2. two or three lead stories;
3. grouped supporting and brief items with explicit names;
4. one restrained conclusion.

Vary sentence length. Use shorter action-led clauses for brief mentions and allow natural breathing space around emotionally important details.

Any wording change still goes through the script approval gate. Do not silently apply a compressed draft to an accepted video.

## Voice and silence

Reuse an already approved voice unless the user asks to audition another. For a news-style roundup, audition the same final excerpt around +10%, +12%, and +14% when selection is unclear. When +10% was judged slow, +12% is the next default—not an aggressive tempo jump.

Trim leading and trailing segment silence, and avoid stacking a synthesized punctuation pause with a large injected scene gap. Preserve natural phrase-final breathing and never solve a long script with more than 1.18× tempo compression.

## Visual rhythm

- Keep an approved cover completely static, normally for 1.8–2.0 seconds.
- Show the first meaningful source visual within roughly 0.2–0.6 seconds of its spoken subject.
- Create a meaningful change about every 1.5–2.5 seconds: reveal the corresponding image, replace a panel on a named cue, reflow a main/supporting pair, or emphasize a verified number.
- Do not count camera drift, arbitrary tape, confetti, rings, or unsupported stickers as meaningful changes.
- Keep transition overlaps around 0.25–0.35 seconds when that preserves continuity. Maintain at least one visual anchor through the overlap.
- Continue to use `contain` and proportional scaling when full source visibility is required. Faster pacing never authorizes cropping faces, titles, products, logos, or activity information.

## Pacing QA

Run:

```bash
python scripts/check_pacing.py /absolute/path/to/project
```

Review `qa/pacing-check.json` alongside the contact sheet and audio. The report is a diagnostic, not automatic permission to rewrite or re-render. Check:

- cover hold and total duration against the pacing plan;
- lead/supporting/brief scene allocation;
- long caption holds;
- long gaps between authored visual events;
- the actual selected voice rate;
- whether a warning is an intentional quiet beat or a real loss of momentum.

After a voice-rate or silence change, render a short final-script audio excerpt before synthesizing the whole narration. After a script change, regenerate word boundaries and rebuild every cue from the new audio.
