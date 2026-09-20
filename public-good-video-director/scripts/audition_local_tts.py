#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the same audition with Edge TTS and Kokoro Chinese.")
    parser.add_argument("project")
    parser.add_argument("--edge-voice", default="zh-CN-XiaoxiaoNeural")
    parser.add_argument("--kokoro-voice", default="zf_xiaobei")
    args = parser.parse_args()
    script = Path(__file__).with_name("tts_local.py")
    results = []
    for provider, voice in (("edge", args.edge_voice), ("kokoro", args.kokoro_voice)):
        command = [sys.executable, str(script), args.project, "--provider", provider, "--voice", voice, "--audition"]
        run = subprocess.run(command, capture_output=True, text=True)
        results.append({
            "provider": provider, "voice": voice, "status": "completed" if run.returncode == 0 else "unavailable",
            "detail": (run.stdout or run.stderr).strip()[-800:],
        })
    project = Path(args.project).expanduser().resolve()
    output = project / "voice-auditions" / "local-auditions.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if any(item["status"] == "completed" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
