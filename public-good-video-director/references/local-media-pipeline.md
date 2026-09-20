# Local media pipeline

Use this path when the user wants zero per-call speech cost and local visual analysis.

## Install profiles

- Base: Pillow, NumPy, rendering runtime.
- `--local-speech`: Edge TTS plus Faster-Whisper alignment. Edge needs internet; Faster-Whisper downloads its selected model on first use.
- `--kokoro`: Kokoro Chinese, Misaki Chinese G2P, and SoundFile. This is a larger install and downloads model assets before fully offline use.

## Required order

1. Approve the narration.
2. Run semantic splitting and generate/import the keyframes.
3. Analyze safe zones.
4. Build real layers.
5. Audition Edge and Kokoro on the same approved sentence. When the voice direction is still unclear, generate the Edge A/B/C trio and wait for selection.
6. Add project-local pronunciation aliases for any awkward letters, brands, names, numbers, or polyphones; do not edit approved display copy to force pronunciation.
7. Generate every semantic beat with the chosen voice and selected pace.
8. Align narration and rebuild the timeline. Subtitle cards must end at natural punctuation or an approved clause boundary, never at an arbitrary character count.
9. Mark an approved designed cover as `static_complete` when the user wants a still first page.
10. Render preview, inspect every scene, approve, then render final.

Useful commands:

```bash
python scripts/audition_voice_trio.py PROJECT --rate=+6% --pitch=+1Hz
python scripts/set_pronunciation.py PROJECT --written QQ --spoken "Q Q "
python scripts/set_static_cover.py PROJECT --scene 1
```

Do not describe weighted timing estimation as word alignment. `assets/audio/timestamps.json.alignment_method` is the source of truth.
