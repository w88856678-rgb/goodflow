#!/usr/bin/env python3
"""Create a lightweight pacing diagnostic for a public-good video project."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def event_time(event, start: float, end: float):
    if "time" in event:
        return number(event["time"], start)
    at = number(event.get("at"), 0.0)
    if 0.0 <= at <= 1.0 and end > start:
        return start + at * (end - start)
    return at


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir")
    parser.add_argument("--output")
    args = parser.parse_args()

    project = Path(args.project_dir).expanduser().resolve()
    timeline = load_json(project / "workflow" / "timeline.json", {})
    plan = load_json(project / "workflow" / "pacing-plan.json", {})
    provider = load_json(project / "workflow" / "provider-selection.json", {})
    scenes = timeline.get("scenes", [])
    captions = timeline.get("captions", [])

    duration = number(timeline.get("duration"))
    if not duration and scenes:
        duration = max(number(scene.get("end")) for scene in scenes)

    script = "".join(str(caption.get("text", "")) for caption in captions)
    chars = len(re.sub(r"\s|[，。！？；：、“”‘’（）《》…—,.!?;:'\"()<>]", "", script))
    chars_per_minute = round(chars / duration * 60, 1) if duration else 0.0

    plan_items = {str(item.get("scene_id")): item for item in plan.get("items", [])}
    scene_reports = []
    warnings = []
    for index, scene in enumerate(scenes, 1):
        start = number(scene.get("start"))
        end = number(scene.get("end"), start)
        scene_id = scene.get("id", index)
        times = [start, end]
        times.extend(event_time(event, start, end) for event in scene.get("motion_events", []))
        unique = sorted({round(max(start, min(end, t)), 3) for t in times})
        gaps = [round(b - a, 3) for a, b in zip(unique, unique[1:])]
        max_gap = max(gaps, default=0.0)
        item = plan_items.get(str(scene_id), {})
        report = {
            "scene_id": scene_id,
            "business": scene.get("editorial", {}).get("business", ""),
            "duration_seconds": round(end - start, 3),
            "tier": item.get("tier"),
            "authored_event_count": len(unique) - 2,
            "maximum_authored_event_gap_seconds": max_gap,
        }
        scene_reports.append(report)
        if max_gap > number(plan.get("meaningful_change_interval_seconds", [1.5, 2.5])[-1], 2.5) + 0.3:
            warnings.append({"type": "long_visual_event_gap", **report})

    cover_hold = scene_reports[0]["duration_seconds"] if scene_reports else 0.0
    cover_range = plan.get("cover_hold_seconds", [1.8, 2.0])
    if isinstance(cover_range, (int, float)):
        cover_range = [number(cover_range), number(cover_range)]
    if cover_hold and cover_hold > number(cover_range[-1], 2.0) + 0.15:
        warnings.append({"type": "long_cover_hold", "seconds": cover_hold, "recommended": cover_range})

    target = plan.get("target_duration_seconds")
    if isinstance(target, (int, float)):
        target = [number(target), number(target)]
    if target and duration > number(target[-1]) + 0.5:
        warnings.append({"type": "duration_above_plan", "seconds": duration, "target": target})

    caption_holds = []
    for caption in captions:
        hold = number(caption.get("to")) - number(caption.get("from"))
        if hold > 7.0:
            caption_holds.append({"text": caption.get("text", ""), "seconds": round(hold, 3)})
    if caption_holds:
        warnings.append({"type": "long_caption_holds", "items": caption_holds})

    selected_tts = provider.get("tts", provider.get("providers", {}).get("tts", {}))
    report = {
        "mode": plan.get("mode", "unplanned"),
        "duration_seconds": round(duration, 3),
        "script_characters": chars,
        "characters_per_minute": chars_per_minute,
        "cover_hold_seconds": cover_hold,
        "selected_tts": selected_tts,
        "scenes": scene_reports,
        "warnings": warnings,
        "status": "review_required" if warnings else "pass",
        "note": "Warnings require editorial review; they do not authorize automatic rewriting or cropping.",
    }

    output = Path(args.output).expanduser().resolve() if args.output else project / "qa" / "pacing-check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
