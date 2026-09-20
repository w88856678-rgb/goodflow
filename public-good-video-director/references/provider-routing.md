# Capability-first provider routing

Use this before any image-generation or speech-synthesis call.

## Decision order

1. Honor an explicit user choice if the provider is callable and safe.
2. Inspect the current agent’s callable tools. Prefer a high-quality native image or speech capability already included in the host when it meets the task requirements.
3. Consider an installed specialist provider when it materially improves Chinese speech, style consistency, export quality, or controllability.
4. Use Alibaba Bailian as fallback when preferred capabilities are absent, fail, cannot export usable files, or fail QA.

Do not infer capability from the label “Codex,” “WorkBuddy,” or any model name alone. Inspect the actual tool inventory. Do not hardcode a current model alias into the workflow; record the exact provider/model returned or selected at runtime.

## Image qualification

A preferred image tool must:

- generate or edit portrait images suitable for 9:16 delivery;
- follow the full `image_prompt` and maintain the requested paper-collage style;
- avoid embedded Chinese text, logos, watermarks, and identifiable minor faces;
- return a usable file or artifact that can be imported locally;
- achieve reasonable cross-scene consistency.

If the agent exposes a strong native image-generation tool, use it before `generate_keyframes_bailian.py`. Generate one image per storyboard beat, save them with zero-padded names, then run:

```bash
python scripts/import_keyframes.py PROJECT GENERATED_IMAGE_DIRECTORY
```

Use `generate_keyframes_bailian.py` only as the Bailian fallback path.

## Speech qualification

A preferred speech tool must:

- produce natural Mandarin with controllable pacing and emotion;
- export audio files without destructive background music;
- support beat-level generation so each storyboard beat can be aligned independently;
- avoid odd interjections, announcer tone, excessive sweetness, or exaggerated sentiment;
- have clear usage rights for the intended delivery.

Generate files named `segment-01`, `segment-02`, and so on. WAV, MP3, M4A, AAC, FLAC, and OGG are accepted. Then run:

```bash
python scripts/assemble_external_tts.py PROJECT SEGMENTS_DIRECTORY \
  --provider PROVIDER_NAME --model MODEL_NAME
```

Use `tts_bailian.py` only as the Bailian fallback path or when the user explicitly selects a Bailian voice.

When the user prefers zero per-call speech cost, audition the two bundled local routes before a paid provider:

- Edge TTS: free and usually natural for Mandarin, requires internet, returns useful word boundaries, and needs no API key.
- Kokoro Chinese: free and fully local after model download, more reproducible and private, but heavier to install and more dependent on the selected Chinese voice/checkpoint.

Use `audition_local_tts.py` on the approved script. Do not automatically prefer “fully local” if the actual sample sounds less natural; record the winner and why.

## Record the decision

After inspecting capabilities, run:

```bash
python scripts/select_providers.py PROJECT \
  --image-provider PROVIDER --image-model MODEL \
  --image-reason "Why this is the best available image capability" \
  --tts-provider PROVIDER --tts-model MODEL \
  --tts-reason "Why this is the best available speech capability"
```

Use `agent-native` as the provider name when a host-integrated capability has no public provider label. Record exact callable model names only when the host exposes them.

## Fallback triggers

Fall back to Bailian only when one of these is true:

- preferred tool is unavailable or not callable;
- generation fails repeatedly;
- result cannot be saved or imported;
- image fails privacy, aspect, style, or consistency checks after a reasonable retry;
- speech fails Mandarin naturalness, export, or beat-alignment requirements;
- user explicitly requests Bailian.

Do not invoke two paid providers “just in case.” If quality is uncertain, audition one image and one speech beat first, compare, select, and continue with one provider.

## Command adapter route

When WorkBuddy, Codex, or another agent exposes a preferred model through its own executable or API wrapper, do not modify the director for that vendor. Follow [provider-adapter-contract.md](provider-adapter-contract.md) and run:

```bash
python scripts/run_provider_adapter.py PROJECT \
  --capability image --provider PROVIDER --model MODEL -- ADAPTER_COMMAND
```

The runner writes a request manifest, passes only paths and capability metadata through environment variables, imports validated outputs, records the actual provider/model, and checkpoints task status. Use the same route with `--capability tts`. The adapter must read its own credentials from its environment.
