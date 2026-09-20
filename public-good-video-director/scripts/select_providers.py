#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record capability-first image and speech provider selection."
    )
    parser.add_argument("project")
    parser.add_argument("--image-provider", required=True)
    parser.add_argument("--image-model", default="provider-default")
    parser.add_argument("--image-reason", required=True)
    parser.add_argument("--tts-provider", required=True)
    parser.add_argument("--tts-model", default="provider-default")
    parser.add_argument("--tts-reason", required=True)
    parser.add_argument("--fallback", default="bailian")
    args = parser.parse_args()

    project_dir = Path(args.project).expanduser().resolve()
    project_path = project_dir / "project.json"
    project = read_json(project_path)
    selection = {
        "strategy": "best-available",
        "image": {
            "provider": args.image_provider,
            "model": args.image_model,
            "reason": args.image_reason,
            "fallback": project.get("fallback_models", {}).get("image", "qwen-image-2.0"),
        },
        "tts": {
            "provider": args.tts_provider,
            "model": args.tts_model,
            "reason": args.tts_reason,
            "fallback": project.get("fallback_models", {}).get("tts", "cosyvoice-v3.5-plus"),
        },
        "fallback_provider": args.fallback,
        "rule": "Use the selected higher-quality available capability; invoke fallback only if it is unavailable, fails, or fails QA.",
    }
    write_json(project_dir / "workflow" / "provider-selection.json", selection)
    project["providers"] = {
        "strategy": "best-available",
        "image": args.image_provider,
        "tts": args.tts_provider,
        "fallback": args.fallback,
    }
    project.setdefault("models", {})["image"] = args.image_model
    project.setdefault("models", {})["tts"] = args.tts_model
    write_json(project_path, project)
    print(project_dir / "workflow" / "provider-selection.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
