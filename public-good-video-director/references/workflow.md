# Portable workflow

Assume:

```bash
SKILL_DIR="/absolute/path/to/your-agent-skills/public-good-video-director"
STUDIO="/absolute/path/to/public-good-video-studio"
SOURCE="/absolute/path/to/source.txt"
PROJECT_NAME="项目名称"
```

## 1. Bootstrap once

```bash
python "$SKILL_DIR/scripts/bootstrap.py" "$STUDIO" --install
```

For free Edge speech plus local word alignment, add `--local-speech`. For fully local Kokoro Chinese, also add `--kokoro`; this downloads a substantially larger model stack:

```bash
python "$SKILL_DIR/scripts/bootstrap.py" "$STUDIO" --install --local-speech --kokoro
```

Do not configure a provider key yet unless the routing gate selects that provider. If Alibaba Bailian is selected as fallback, store its key locally:

```bash
umask 077
read -s "DASHSCOPE_API_KEY?请输入阿里云百炼 API Key: "
printf 'DASHSCOPE_API_KEY=%s\n' "$DASHSCOPE_API_KEY" > "$STUDIO/.env"
unset DASHSCOPE_API_KEY
chmod 600 "$STUDIO/.env"
```

Never place the key in the project JSON, narration, chat response, screenshots, logs, Git history, or packaged skill.

## 2. Create and prepare

```bash
python "$SKILL_DIR/scripts/new_project.py" "$STUDIO" \
  --name "$PROJECT_NAME" \
  --content-file "$SOURCE" \
  --duration 30 \
  --tone "温暖松弛" \
  --renderer hyperframes \
  --media-dir "/absolute/path/to/authorized-project-media"
```

Omit `--media-dir` when the user supplied text only. Imported files are copied into `assets/source`; retain captions and rights notes in `project.json.source_media` before using identifiable or third-party material.

The command prints the absolute project path. Save it as `PROJECT`.

```bash
"$STUDIO/pg-video" prepare "$PROJECT" --live
```

Inspect:

- `workflow/facts.json`
- `workflow/scripts.json`

Compare every name, number, place, date, event, and quotation against `project.json.source_text`. Remove unsupported claims.

## 3. Script approval gate

Show the user all three complete variants or the strongest recommended variant. Do not generate paid images or speech until the narration is approved.

If the user edits a variant, update that variant’s `narration` in `workflow/scripts.json`, then approve it:

```bash
"$STUDIO/pg-video" approve-script "$PROJECT" --variant warm
```

Available variants: `warm`, `documentary`, `progress`.

## 4. Exact beat mapping

```bash
python "$SKILL_DIR/scripts/semantic_beats.py" --project "$PROJECT"
python "$SKILL_DIR/scripts/storyboard.py" "$STUDIO" "$PROJECT"
```

Inspect `workflow/storyboard.json`. Each beat must have:

- exact narration text;
- a visual showing that sentence’s subject/action;
- a short natural voice direction;
- phone-readable caption chunks;
- a distinct motion and transition;
- at least three timed `motion_events`.

Revise mismatched scenes before generating assets.
Read `references/motion.md` when changing event types or timing.

For a recurring series or source-heavy roundup, replace episode-specific setup/compiler scripts with the declarative path after script approval:

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" index
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" init-plan
# Edit workflow/scene-plan.yaml only.
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" compile
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" changes
```

Read `references/declarative-workflow.md` before editing the plan. The existing approved narration remains authoritative; the compiler refuses narration drift and unsafe default cropping.

## 5. Select image and speech providers

Inspect the media tools actually callable in the current Agent. Image and speech are independent decisions: the best image tool and the best speech tool do not need to come from the same provider. Apply `references/provider-routing.md`, then record the decision:

```bash
python "$SKILL_DIR/scripts/select_providers.py" "$PROJECT" \
  --image-provider "agent-native" \
  --image-model "actual callable image model" \
  --image-reason "best available visual quality" \
  --tts-provider "agent-native" \
  --tts-model "actual callable speech model" \
  --tts-reason "best available Mandarin prosody"
```

Use the real provider and model names. Do not label a tool `GPT Image 2`, MiniMax, or Bailian merely because the host might support it.

For a host model or custom API exposed through a command, use the generic adapter instead of hardcoding a provider into the director:

```bash
python "$SKILL_DIR/scripts/run_provider_adapter.py" "$PROJECT" \
  --capability image --provider PROVIDER --model MODEL -- \
  /absolute/path/to/image-adapter
```

Run the same command with `--capability tts` for speech. Read `references/provider-adapter-contract.md` for environment variables and output naming.

### Image route A: Agent-native or connected image tool

Generate one vertical image per storyboard beat with the selected tool. Save them in a directory using zero-padded scene order such as `scene-01.png`, `scene-02.png`, and then import them:

```bash
python "$SKILL_DIR/scripts/import_keyframes.py" \
  "$PROJECT" "/absolute/path/to/generated-scenes"
```

### Image route B: Bailian fallback

Dry-run the image prompts first:

```bash
python "$SKILL_DIR/scripts/generate_keyframes_bailian.py" \
  "$STUDIO" "$PROJECT" --dry-run
```

After inspection:

```bash
python "$SKILL_DIR/scripts/generate_keyframes_bailian.py" \
  "$STUDIO" "$PROJECT"
```

Only use this route after configuring `DASHSCOPE_API_KEY` and recording Bailian as the selected fallback.

### Speech route A: Agent-native or connected speech tool

Synthesize each storyboard beat independently with the selected speech tool. Name the files `segment-01.wav`, `segment-02.wav`, and so on; supported inputs include WAV, MP3, M4A, AAC, FLAC, and OGG. Assemble and normalize them:

```bash
python "$SKILL_DIR/scripts/assemble_external_tts.py" \
  "$PROJECT" "/absolute/path/to/generated-segments" \
  --provider "agent-native" \
  --model "actual callable speech model"
```

### Speech route B: Free Edge TTS or fully local Kokoro

Check what is installed, then generate the same short audition with both available engines:

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/tts_local.py" --check
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/audition_local_tts.py" "$PROJECT"
```

After listening, generate the full narration with one engine:

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/tts_local.py" "$PROJECT" \
  --provider edge --voice zh-CN-XiaoxiaoNeural

# Or fully local after its model is installed/downloaded:
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/tts_local.py" "$PROJECT" \
  --provider kokoro --voice zf_xiaobei
```

Edge needs network but no API key. Kokoro needs no API and can run offline after its model files are present. Keep the chosen engine/model in the provider record.

### Speech route C: Bailian fallback

List voice profiles:

```bash
python "$SKILL_DIR/scripts/tts_bailian.py" . . --list-profiles
```

For a new brand voice, generate same-script auditions first:

```bash
python "$SKILL_DIR/scripts/audition_voices_bailian.py" \
  --env-file "$STUDIO/.env" \
  --output-dir "$STUDIO/voice-auditions"
```

Generate narration:

```bash
python "$SKILL_DIR/scripts/tts_bailian.py" \
  "$STUDIO" "$PROJECT" --profile warm-documentary
```

The script synthesizes each semantic beat independently, trims only edge silence, inserts controlled pauses, and writes beat timestamps. If the delivery is wrong, regenerate only the affected segment with `--force` after refining `voice_direction`; do not TTS the full 30-second paragraph as one block.

## 6. Visual analysis, layers, alignment, timeline, preview, and final

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/analyze_safe_zones.py" "$PROJECT"
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/build_layers.py" "$PROJECT" --prefer-rembg
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/align_narration.py" "$PROJECT" --engine auto
"$STUDIO/pg-video" timeline "$PROJECT"
"$STUDIO/pg-video" preview "$PROJECT" --engine hyperframes
"$STUDIO/pg-video" qa "$PROJECT"
```

Inspect `preview/preview.mp4`, `qa/contact-sheet.jpg`, and `qa/qa-report.json`. Check:

- spoken sentence and image describe the same fact;
- scene changes happen on provider word boundaries for the actual spoken cue, including cues that contain letters or brand names;
- subtitles follow the spoken words;
- `assets/audio/timestamps.json.alignment_method` truthfully states Edge boundaries, Faster-Whisper, or estimated fallback;
- no long freeze, black frame, or identifiable child face;
- the exact decoded frames 0–3 begin with the intended cover rather than a renderer initialization frame;
- voice has natural phrasing and no odd interjection;
- no image contains generated Chinese text.
- every scene contains visible internal change rather than only a whole-frame zoom;
- early, middle, and late frames of every scene keep faces, hands, products, logos, and readable source text unobstructed;
- safe-zone debug frames agree with the real subject, and every persistent overlay carrying `layout` stays within its selected region;
- background, subject, and foreground move at visibly different but restrained rates without cutout halos;
- decorative tape and color blocks are absent unless they visibly attach an edge and stay outside protected content;
- rings, arrows, and pins have an explicit target; otherwise replace them with text emphasis;
- final integrated loudness is approximately -16 LUFS.
- publication audio is AAC 48 kHz and the MP4 uses `faststart`.

After a successful checked preview, persist the scene cache for the next revision:

```bash
"$STUDIO/.venv/bin/python" "$SKILL_DIR/scripts/scene_pipeline.py" "$PROJECT" commit-cache
```

HyperFrames uses a persistent extracted-frame cache and unchanged material files. Keep full encoding when needed for cross-scene transitions and audio continuity; do not splice an old scene merely because its source image is unchanged.

After approval, when a higher-quality final export is requested:

```bash
"$STUDIO/pg-video" approve-preview "$PROJECT"
"$STUDIO/pg-video" render "$PROJECT" --engine auto
"$STUDIO/pg-video" qa "$PROJECT" --video "$PROJECT/dist/final.mp4"
```

`auto` follows `project.json.rendering.engine`, normally HyperFrames, and uses the configured fallback only after the primary engine fails. Inspect `workflow/render-selection.json` and `workflow/task-state.json` before reporting the result. Resume a failed stage by fixing its provider, credential, or asset issue and rerunning that stage; completed checkpoints remain inspectable with:

```bash
"$STUDIO/pg-video" status "$PROJECT" --json
```

The approval stamp is invalidated if source, script, timeline, images, narration, or music change.
Project-local render-template changes also invalidate approval. When bringing these helpers into an existing studio, update only the relevant runtime files after comparing local customizations; do not use `bootstrap --force` on a studio containing user projects. Existing accepted MP4s remain unchanged.

For an explicitly accepted current version with no further export, skip the `render` command. Retain the verified MP4 and record `workflow/delivery.json` as described in `references/rendering.md`. Do not imply that a new high-quality render happened. For visual-only fixes, use the incremental path in `references/editorial-revisions.md` and leave approved narration/timings unchanged unless necessary.

## 7. Delivery

Return the final MP4 or the exact accepted existing MP4, plus the relevant QA report. Also retain the approved script, storyboard, provider selection, renderer selection, and task state so the production is auditable, resumable, and repeatable. A user who explicitly accepts the current export is finished; do not require another resolution choice.
