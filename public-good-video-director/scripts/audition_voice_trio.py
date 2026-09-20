#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import importlib.util
from pathlib import Path

from tts_local import audition_text, edge_generate, speech_text_for, write_json


CANDIDATES = [
    {"id": "A", "voice": "zh-CN-XiaoyiNeural", "direction": "清亮亲和女声，适合温暖热点和项目进展"},
    {"id": "B", "voice": "zh-CN-YunxiNeural", "direction": "年轻自然男声，适合轻松讲故事"},
    {"id": "C", "voice": "zh-CN-YunyangNeural", "direction": "稳健播报男声，适合信息密度较高的新闻轮播"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate three same-script Edge TTS voice candidates.")
    parser.add_argument("project")
    parser.add_argument("--rate", default="+6%")
    parser.add_argument("--pitch", default="+1Hz")
    args = parser.parse_args()
    if importlib.util.find_spec("edge_tts") is None:
        raise SystemExit("edge_tts is unavailable; bootstrap the studio with --local-speech")

    project_dir = Path(args.project).expanduser().resolve()
    written = audition_text(project_dir)
    spoken = speech_text_for(project_dir, written)
    output_dir = project_dir / "voice-auditions" / "edge-trio"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_candidates = []
    for item in CANDIDATES:
        output = output_dir / f"voice-{item['id']}-{item['voice'].removeprefix('zh-CN-').removesuffix('Neural').lower()}.mp3"
        asyncio.run(edge_generate(spoken, output, item["voice"], args.rate, args.pitch))
        manifest_candidates.append({**item, "file": str(output)})
    manifest = {
        "provider": "edge",
        "written_sample": written,
        "spoken_sample": spoken,
        "settings": {"rate": args.rate, "pitch": args.pitch},
        "candidates": manifest_candidates,
        "selection_required": True,
    }
    output = output_dir / "manifest.json"
    write_json(output, manifest)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
