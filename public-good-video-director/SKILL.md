---
name: public-good-video-director
description: Convert Chinese public-good project introductions, human stories, progress text, and authorized project images into a finished vertical Vox-style paper-collage video. Use when the user wants 公益图文一键成片、公益故事短视频、项目进展视频、Vox 风格公益视频, or a reusable director workflow with HyperFrames motion, pluggable image/speech providers, resumable tasks, and Alibaba Bailian fallback.
---

# Public Good Video Director

Act as the director layer: turn verified Chinese source material into a script-approved, audio-first, 9:16 finished video. Use HyperFrames as the primary smooth-motion renderer, Remotion as the compatibility fallback, the best media capabilities available to the current agent, and Alibaba Bailian only as provider fallback.

## Required inputs

- Public-good source text
- Project name
- Target duration, default 30 seconds
- Credentials only for the providers actually selected; `DASHSCOPE_API_KEY` is optional until Bailian fallback is needed

Treat every provider credential as a secret. Ask the user to set it locally; never echo, log, commit, or reproduce it. Use MiniMax voice names only as listening references. Never clone a system voice, a random GitHub recording, or a real speaker without explicit voice-use authorization.

## Provider routing gate

Read [provider-routing.md](references/provider-routing.md) before any paid image or speech call. Inspect the callable tools in the current agent instead of assuming capabilities from the host name.

Prefer, in order: the user’s explicit provider choice; a high-quality agent-native image or speech tool already available in Codex, WorkBuddy, or another host; a higher-quality connected specialist provider; Alibaba Bailian fallback. Do not call Bailian merely because the bundled fallback scripts exist. Record the actual decision in `workflow/provider-selection.json`.

When a host exposes its media model only through a command or custom API, use the provider adapter contract in [provider-adapter-contract.md](references/provider-adapter-contract.md). Keep credentials in that adapter's environment, never in this skill.

## Rendering gate

Read [rendering.md](references/rendering.md). Default to HyperFrames for layered parallax, continuous camera motion, local typography, and overlap transitions. Fall back to Remotion only when HyperFrames is unavailable or fails validation. Record the engine actually used in `workflow/render-selection.json`; never describe a Remotion fallback render as HyperFrames.

Before composing keyframes or placing overlays, read [visual-hierarchy.md](references/visual-hierarchy.md). Decorative tape, stickers, rings, arrows, and pins are disabled by default. Use them only when they are semantically necessary, visibly anchored, and outside protected subject regions.

## Workflow

Choose the task mode before starting the pipeline:

- **New video:** follow the source, script, voice, and preview gates below.
- **Audit or revise an existing video:** read [editorial-revisions.md](references/editorial-revisions.md). An audit is read-only; implement only the selected fixes. Reuse approved script, audio, source assets, cover and timings unless the requested change requires replacing them. Do not restart auditions or script generation for a visual-only revision.
- **Accept the current version:** if the user explicitly says the current MP4 is sufficient and declines a higher-quality export, deliver that exact checked file and record its acceptance. No mandatory re-render or repeated approval question.

Read [workflow.md](references/workflow.md), then follow every gate below.

For information-led hotspot/news roundups or multi-business progress summaries, also read [pacing.md](references/pacing.md) before writing the script. Build the pacing plan before script approval; do not apply those faster defaults to intimate human stories.

For recurring series, source-heavy roundups, or any job that would otherwise create date-specific setup, compile, capture, or TTS programs, read [declarative-workflow.md](references/declarative-workflow.md). Write one compact `workflow/scene-plan.yaml` and use the bundled scene pipeline, fixed layout registry, content-addressed material cache, and dirty-scene manifest. Do not write a new Python/JavaScript/HTML program for an episode unless the approved design cannot be represented by the registry; add a global layout only after it is reusable across at least two real projects.

1. Bootstrap the bundled runtime into a working directory.
2. Create a project, import any authorized source media, inspect available media capabilities, record provider selection, and extract only source-grounded facts. For a source-heavy project, index media once into `workflow/source-manifest.json` and reference its content-derived asset IDs thereafter.
3. Generate three script variants. For a roundup, preserve complete business coverage while assigning lead, supporting, and brief-mention tiers; compress repeated framing rather than giving every item equal weight.
4. Show the complete narration to the user and stop for approval unless the user explicitly waived review.
5. Split the approved narration with `semantic_beats.py`; compile every exact semantic beat into one keyframe, one TTS segment, one scene, complete-sentence or approved-clause captions, and three to five timed visual events. Never lose, paraphrase, or reorder approved narration during splitting.
6. Prefer authorized original media when it already illustrates the fact; compose it locally without regenerating it. Generate missing collage visuals only with the selected image capability. Render Chinese headlines and labels locally. Run `analyze_safe_zones.py` before layout; use `build_layers.py` for genuine layered scenes. For source-image cards and multi-business updates, read [editorial-revisions.md](references/editorial-revisions.md) before choosing crops and layouts. Compile declarative plans before alignment so the timeline consumes the final ordered scene set.
7. Synthesize narration by beat with the selected best-available speech capability. When paid speech is unnecessary, read [local-media-pipeline.md](references/local-media-pipeline.md). If the best voice is unclear, generate three same-script candidates and stop for selection. Keep display copy unchanged; put brand names, letters, polyphones, and foreign names in project-local `workflow/tts-pronunciations.json`. Edge is the free network route, Kokoro is the fully local route, and Bailian remains fallback.
8. Run `align_narration.py`, preferring provider word boundaries, then local Faster-Whisper, and clearly labeled weighted estimation only as the fallback. Captions must be complete sentences or semantic clauses and may never be cut at a fixed character count. Rebuild the audio-derived timeline, render a low-resolution HyperFrames preview, and inspect the contact sheet. When the user supplies a designed cover and asks it to stay still, use the static-complete cover mode instead of parallax. For a roundup, run `scripts/check_pacing.py` before preview approval and review every pacing warning. Use Remotion only as the recorded fallback.
9. Get preview approval, then either render the requested final MP4 and run QA, or retain the exact accepted current MP4 when the user declines another export. Record the actual delivery choice and file; see [rendering.md](references/rendering.md).

Do not render a final video from an unapproved script or changed, unapproved preview.

## Voice direction

When Bailian is selected, default to `warm-documentary`. For project updates, consider `gentle-senior`; for a close personal detail, use `soft-intimate`; for action/data-led progress, use `sincere-adult`. With native or connected speech tools, map these names to the same perceptual direction—warmth, restraint, pace, breath, and sentence endings—without pretending the provider exposes those exact profiles.

Before spending Bailian API credits, play the four bundled same-script samples when they are relevant and ask the user to choose a profile. Read `assets/voice-auditions/manifest.json` for the mapping. Treat the audio as listening references only; never submit it as cloning or training audio. When a different speech provider is selected, audition its own candidates using the final script instead.

List profiles:

```bash
python scripts/tts_bailian.py . . --list-profiles
```

Generate a same-script audition before choosing a long-term project voice:

```bash
python scripts/audition_voices_bailian.py \
  --env-file /absolute/path/to/.env \
  --output-dir /absolute/path/to/voice-auditions
```

The profiles are original Bailian Voice Design prompts derived from general perceptual traits such as warmth, cadence, breath, and sentence endings. They do not copy a third-party speaker’s timbre. Read [voice.md](references/voice.md) before adding or cloning a voice.

## Quality rules

- Preserve names, dates, places, numbers, and quotes exactly; do not invent facts.
- Write natural spoken Chinese with a clear hook, change, concrete human detail, and restrained ending.
- Avoid propaganda phrasing, announcer tone, exaggerated tragedy, and unsupported emotional claims.
- Keep captions legible and semantically complete. Change cards only at spoken punctuation or an approved clause boundary; never split a name, word, number, or sentence merely to meet a character limit. Scale long cards responsively instead of flashing fragments.
- Distinguish timed caption changes from visual line breaks. Preserve words, date ranges and number-unit pairs across lines; reserve space for long sentences before placing images. Use exact `lines` metadata and inspect rendered widths instead of repeatedly shrinking the font.
- Preserve the approved script and on-screen spelling when fixing pronunciation. Apply speech-only aliases through `workflow/tts-pronunciations.json`, then regenerate word boundaries and the timeline.
- Match every visual to its exact narration beat. Do not reuse generic school or meal visuals when the sentence describes a different fact.
- Resolve scene cues against provider word boundaries before subtitle-card boundaries. A cue containing letters such as `QQ` must switch on the matched spoken word, not at the beginning of a longer subtitle card.
- Give each scene 3–5 semantic internal events such as a paper label, fact stack, cause flow, number card, underline, or CTA reveal. A camera move alone is not a finished scene.
- Distribute these events over the spoken beat. Resolve image, number and label cues from the selected voice's word boundaries; showing everything in the first half-second followed by tiny drift is not meaningful sequencing.
- Protect faces, hands, products, logos, and readable source text from decorative overlays. Move or simplify the overlay when the available negative space is insufficient.
- Generate `workflow/visual-safe-zones.json` and attach a safe `layout` to persistent overlays. Treat automatic detection as a placement proposal that must still pass the contact-sheet review.
- Check the entire opaque photo card, not only its inner image: white borders can hide text too. Custom templates require fresh rendered geometry and screenshots; stale generic event boxes or counts cannot certify them. Use `scripts/validate_visual_layout.py` with the capture contract in [editorial-revisions.md](references/editorial-revisions.md).
- Do not add masking tape or arbitrary color blocks by default. If tape is deliberately used, it must visibly attach a paper edge and must not cover meaningful image content.
- Use rings, arrows, and pins only with an explicit target box or coordinate. If the renderer cannot bind the marker to that target, replace it with local text emphasis.
- Keep `depth: layered` unless a deliberately flat information card is required. Generate real background/subject/foreground files under `assets/layers`; never duplicate and crop the same image to simulate depth when the layer builder is available.
- Protect minors: use backs, hands, objects, silhouettes, or authorized non-identifying material.
- Prefer continuous camera motion, parallax, paper layers, masked reveals, and overlap transitions over slide-to-slide cuts.
- Exception: an approved title cover marked `static_complete` must use the untouched source image at 100% frame size with no parallax, depth layers, wash, grain, headline animation, or opening wipe. A resulting freeze-detection event is intentional only inside that marked scene.
- If narration exceeds target duration, shorten the copy before applying more than 1.18× tempo compression.
- For information-led roundups, start with the previously approved voice and audition the final-script excerpt near +10%, +12%, and +14% when needed. If +10% was perceived as slow, prefer about +12% plus silence cleanup; do not exceed +14% without the user's listening approval. For intimate stories, start near the provider default. Never choose speed without listening to the same final-script excerpt.
- Treat perceived pace as an editorial and visual property, not only a TTS rate. In a roundup, remove repeated framing, give lead items more time than brief mentions, place the first meaningful visual near the spoken subject, and create a useful visual change about every 1.5–2.5 seconds without adding arbitrary decoration.
- In a roundup with an approved static cover, normally hold the complete cover for about 1.8–2.0 seconds. Keep it perfectly still and preserve frames 0–3; change the duration only when the user or platform requires something else.
- Keep roundup scene overlaps concise, commonly about 0.25–0.35 seconds, while switching each source image on its exact spoken cue. Avoid an empty lead-in longer than roughly 0.6 seconds before the scene's first meaningful visual.
- Mix narration, music, and event SFX to approximately -16 LUFS with restrained dynamics; do not maximize loudness.
- Publish AAC audio at 48 kHz and write MP4 metadata with `faststart` for social-platform compatibility.
- Verify portrait orientation, audio presence, subtitle timing, the exact first four decoded frames, and the 10-frame contact sheet before delivery. A one-frame initializer black screen is a failure even when ordinary duration-based black-frame detection misses it; repair it by cloning the first valid cover frame without shifting audio. Also inspect early, middle, and late frames of every scene for subject occlusion.
- Report the actual image and speech providers/models. Never claim Bailian, GPT Image, MiniMax, or another provider was used unless `workflow/provider-selection.json` records it.

## Outputs

Deliver:

- `dist/final.mp4`, or the exact user-accepted current MP4 with `workflow/delivery.json` when no new export is wanted
- `qa/qa-report.json`
- `qa/contact-sheet.jpg`
- `workflow/approved-script.json`
- `workflow/storyboard.json`
- `workflow/source-manifest.json` and `workflow/scene-plan.compiled.json` for declarative/source-heavy projects
- `workflow/incremental-render-plan.json` for declarative revisions
- `workflow/semantic-beats.json`
- `workflow/visual-safe-zones.json`
- `workflow/layer-manifest.json`
- `workflow/timeline.json`
- `assets/audio/timestamps.json`
- `workflow/provider-selection.json`
- `workflow/tts-pronunciations.json` when speech aliases are needed
- `workflow/render-selection.json`
- `workflow/pacing-plan.json` and `qa/pacing-check.json` for hotspot/news roundups
- `workflow/output-validation.json`
- `workflow/task-state.json`
- `build/hyperframes/index.html` when HyperFrames is selected

Report the selected script variant, actual image provider/model, actual speech provider/model, voice profile where applicable, duration, QA result, and any facts that still require confirmation.
