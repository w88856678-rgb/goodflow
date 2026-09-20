#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a project-local TTS pronunciation alias.")
    parser.add_argument("project")
    parser.add_argument("--written", required=True, help="Text kept in the approved script and captions")
    parser.add_argument("--spoken", required=True, help="Provider-facing pronunciation text")
    args = parser.parse_args()
    project_dir = Path(args.project).expanduser().resolve()
    path = project_dir / "workflow" / "tts-pronunciations.json"
    document = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"replacements": {}, "notes": {}}
    document.setdefault("replacements", {})[args.written] = args.spoken
    document.setdefault("notes", {})[args.written] = "Display text is unchanged; alias applies only to speech synthesis."
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    approval = project_dir / "workflow" / "preview-approved.json"
    if approval.exists():
        approval.unlink()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
