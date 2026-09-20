#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_static(item: dict[str, Any]) -> None:
    item["move"] = "static"
    item["cover_mode"] = "static_complete"
    item["headline"] = ""
    item["components"] = []
    item["motion_components"] = []
    for event in item.get("motion_events", []):
        event["suppressed"] = True
        event["suppressed_reason"] = "approved cover is shown complete and motionless"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show one designed cover as a complete motionless scene.")
    parser.add_argument("project")
    parser.add_argument("--scene", type=int, default=1)
    args = parser.parse_args()
    project_dir = Path(args.project).expanduser().resolve()
    index = args.scene - 1
    if index < 0:
        raise SystemExit("--scene must be at least 1")

    project_path = project_dir / "project.json"
    project = read_json(project_path)
    keyframes = project.get("assets", {}).get("keyframes", [])
    if index >= len(keyframes):
        raise SystemExit(f"scene {args.scene} does not exist")
    if not isinstance(keyframes[index], dict):
        keyframes[index] = {"path": str(keyframes[index])}
    make_static(keyframes[index])
    write_json(project_path, project)

    storyboard_path = project_dir / "workflow" / "storyboard.json"
    if storyboard_path.exists():
        storyboard = read_json(storyboard_path)
        if index < len(storyboard.get("beats", [])):
            make_static(storyboard["beats"][index])
            write_json(storyboard_path, storyboard)

    timeline_path = project_dir / "workflow" / "timeline.json"
    if timeline_path.exists():
        timeline = read_json(timeline_path)
        if index < len(timeline.get("scenes", [])):
            make_static(timeline["scenes"][index])
            write_json(timeline_path, timeline)

    approval = project_dir / "workflow" / "preview-approved.json"
    if approval.exists():
        approval.unlink()
    print(json.dumps({"project": str(project_dir), "scene": args.scene, "cover_mode": "static_complete"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
