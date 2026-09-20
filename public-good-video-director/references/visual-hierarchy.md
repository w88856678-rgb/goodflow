# Visual hierarchy and occlusion gate

Read this before generating keyframes, placing local overlays, or approving a preview.

## Protected regions

Treat these as protected unless the source itself contains the text or mark:

- faces and identifying human features;
- hands performing the action described by the narration;
- the main product, meal, object, or documentary detail;
- logos, project names, verified numbers, and readable source-document text;
- the visual path between two objects when that relationship is the point of the scene.

Use negative space first. If no safe area exists, reduce the overlay, move it to a paper margin, shorten the text, or change the crop. Do not solve crowding by covering the subject.

The automatic local analyzer labels a candidate `least_risk_fallback` when it cannot verify true negative space. Persistent nonessential overlays assigned only to such a candidate must be suppressed and recorded in QA, not rendered over the subject.

## Decoration policy

- Masking tape, stickers, color blocks, circles, arrows, and pins are off by default.
- Tape is acceptable only when it visibly attaches a paper edge, remains outside protected regions, and improves the collage structure. Otherwise omit it.
- A marker must bind to a named target and an explicit target box or coordinate. Never use a fixed template position as a substitute for semantic placement.
- Prefer paper labels, fact stacks, cause flows, number cards, and underlines because their information value is visible without pretending to point at an object.
- Keep decorative color subordinate to the source image. A brand accent may appear in safe margins, progress indicators, or text emphasis without becoming a floating block over content.

## Placement order

1. Lock the primary subject crop.
2. Reserve a headline band and subtitle safe area.
3. Map remaining negative space.
4. Place only the semantic overlays required by the narration beat.
5. Remove any decoration whose absence does not reduce comprehension.

## Source-aware layout

Choose the card around the useful image region, not a fixed tall box around every source. Use a landscape frame for a banner, a larger portrait window for a person, a coherent number-and-label block for data, and sequential or one-main/one-support views for related images. Use only as many layout families as the story needs; retain common typography, margins and color.

Inspect source images before cropping. Remove empty margins without stretching the image, truncating a person or turning a certificate into a meaningless strip. A tall poster can move through readable windows of the original; do not substitute a tiny full-poster thumbnail for readable content. Low-resolution material may remain a supporting image rather than being forcibly enlarged. Never invent pixels or imply that cropping improved source resolution.

Reserve headline and full-caption regions first. Position number plus explanation as a single protected group. An opaque photo border can obscure that explanation even when its inner image does not overlap it; validate both rectangles. Move, resize or sequence the whole card rather than covering the conflict with another paper strip.

## Preview rejection checks

Inspect at least the early, middle, and late state of every scene at full resolution. Reject and revise the preview when:

- an overlay crosses a face, hand, product feature, logo, or readable source text;
- a circle, arrow, pin, or tape has no unambiguous target;
- several persistent overlays accumulate into a poster-like layout;
- an overlay remains after its narration cue and competes with the next idea;
- the 10-frame contact sheet looks acceptable but a between-frame animation temporarily covers the subject.

Also check cue times and transition midpoints; for overlapping/reflowing layouts, sample at roughly 100–200 ms intervals in addition to early/middle/late screenshots. Use live transformed bounds with ancestor opacity and clipping accounted for. Treat intentionally sequenced photo-to-photo transitions separately from text occlusion; do not globally exempt collisions. Fresh encoded MP4 frames are the final evidence, not just HTML screenshots. See [editorial-revisions.md](editorial-revisions.md) for the portable geometry checker.
