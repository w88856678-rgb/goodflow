# Command provider adapter contract

Use this when the user wants to connect their own image or speech API without modifying the director or renderer.

The Skill launches the adapter as a child process. It does not read or store the adapter's credentials. The adapter receives these environment variables:

- `PG_PROVIDER_REQUEST`: absolute path to the JSON request;
- `PG_PROVIDER_OUTPUT_DIR`: directory where generated files must be written;
- `PG_PROJECT_DIR`: current video project;
- `PG_PROVIDER_CAPABILITY`: `image` or `tts`.

For image requests, write one file per request item using its `output_filename`, normally `scene-01.png`, `scene-02.png`, and so on. For speech requests, write `segment-01.wav`, `segment-02.wav`, and so on. The adapter may use a supported alternate extension; the importer accepts PNG/JPEG/WebP images and WAV/MP3/M4A/AAC/FLAC/OGG audio.

Example invocation:

```bash
python scripts/run_provider_adapter.py "$PROJECT" \
  --capability image \
  --provider my-image-api \
  --model my-best-model \
  -- python /absolute/path/to/my_image_adapter.py
```

The adapter reads its own key from an environment variable such as `MY_IMAGE_API_KEY`. Never add credentials to `project.json`, the request JSON, logs, or the packaged Skill.

The runner validates expected files, imports them into the project, updates `workflow/provider-selection.json`, and checkpoints `workflow/task-state.json`. A failed adapter remains resumable: fix the adapter or credentials and run the same command again with `--force` only when stale output must be replaced.
