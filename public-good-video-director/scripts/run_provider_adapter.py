#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_request(project_dir: Path, capability: str, provider: str, model: str, output: Path) -> dict[str, Any]:
    project = read_json(project_dir / "project.json")
    storyboard = read_json(project_dir / "workflow" / "storyboard.json")
    items = []
    for beat in storyboard["beats"]:
        index = int(beat["id"])
        if capability == "image":
            items.append({
                "id": index,
                "output_filename": f"scene-{index:02d}.png",
                "prompt": beat["image_prompt"],
                "aspect_ratio": "9:16",
                "width": 1080,
                "height": 1920,
                "reference_media": project.get("source_media", []),
            })
        else:
            items.append({
                "id": index,
                "output_filename": f"segment-{index:02d}.wav",
                "text": beat["narration"],
                "direction": beat.get("voice_direction", "自然、温暖、克制地讲述。"),
                "language": "zh-CN",
                "sample_rate": 24000,
            })
    return {
        "schema_version": 1,
        "capability": capability,
        "provider": provider,
        "model": model,
        "project_dir": str(project_dir),
        "output_dir": str(output),
        "items": items,
        "rules": {
            "secrets": "Read credentials from your own environment only; never write them to output.",
            "minors": "Do not generate identifiable minor faces.",
            "image_text": "Do not render Chinese text inside generated images.",
        },
    }


def update_selection(project_dir: Path, capability: str, provider: str, model: str) -> None:
    selection_path = project_dir / "workflow" / "provider-selection.json"
    selection = read_json(selection_path) if selection_path.exists() else {
        "strategy": "best-available", "fallback_provider": "bailian"
    }
    selection[capability if capability == "image" else "tts"] = {
        "provider": provider,
        "model": model,
        "reason": "Executed through the project command-adapter contract.",
        "adapter": "command",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(selection_path, selection)
    project_path = project_dir / "project.json"
    project = read_json(project_path)
    key = capability if capability == "image" else "tts"
    project.setdefault("providers", {})[key] = provider
    project.setdefault("models", {})[key] = model
    write_json(project_path, project)


def update_task(project_dir: Path, capability: str, status: str, error: str | None = None) -> None:
    path = project_dir / "workflow" / "task-state.json"
    state = read_json(path) if path.exists() else {"task_id": project_dir.name, "checkpoints": {}}
    now = datetime.now(timezone.utc).isoformat()
    stage = f"provider-{capability}"
    state.update({"status": status, "stage": stage, "updated_at": now, "last_error": error})
    state.setdefault("checkpoints", {})[stage] = {"status": status, "at": now}
    write_json(path, state)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a user-supplied image or TTS API adapter without embedding provider secrets in the skill."
    )
    parser.add_argument("project")
    parser.add_argument("--capability", choices=["image", "tts"], required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    raw = sys.argv[1:]
    if raw in (["-h"], ["--help"]):
        parser.parse_args(raw)
    if "--" not in raw:
        parser.error("separate the adapter command with --")
    separator = raw.index("--")
    args = parser.parse_args(raw[:separator])
    command = raw[separator + 1:]
    if not command:
        raise SystemExit("Provide an adapter command after --")
    project_dir = Path(args.project).expanduser().resolve()
    output = Path(args.output_dir).expanduser().resolve() if args.output_dir else (
        project_dir / "work" / "provider-output" / args.capability
    )
    if output.exists() and args.force:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    request = build_request(project_dir, args.capability, args.provider, args.model, output)
    request_path = project_dir / "workflow" / "provider-requests" / f"{args.capability}.json"
    write_json(request_path, request)
    env = os.environ.copy()
    env.update({
        "PG_PROVIDER_REQUEST": str(request_path),
        "PG_PROVIDER_OUTPUT_DIR": str(output),
        "PG_PROJECT_DIR": str(project_dir),
        "PG_PROVIDER_CAPABILITY": args.capability,
    })
    update_task(project_dir, args.capability, "running")
    try:
        subprocess.run(command, cwd=project_dir, env=env, check=True)
        if args.capability == "image":
            subprocess.run([
                sys.executable, str(SKILL_ROOT / "scripts" / "import_keyframes.py"),
                str(project_dir), str(output),
            ], check=True)
        else:
            subprocess.run([
                sys.executable, str(SKILL_ROOT / "scripts" / "assemble_external_tts.py"),
                str(project_dir), str(output), "--provider", args.provider, "--model", args.model,
            ], check=True)
        update_selection(project_dir, args.capability, args.provider, args.model)
        update_task(project_dir, args.capability, "completed")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        update_task(project_dir, args.capability, "failed", str(exc)[:1000])
        raise
    print(json.dumps({
        "capability": args.capability, "provider": args.provider, "model": args.model,
        "request": str(request_path), "output": str(output), "status": "completed",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
