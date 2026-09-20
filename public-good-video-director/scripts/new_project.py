#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return value or "public-good-story"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a public-good video project from source text.")
    parser.add_argument("studio")
    parser.add_argument("--name", required=True)
    parser.add_argument("--content-file", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--organization", default="")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--tone", default="温暖松弛")
    parser.add_argument("--cta", default="让真实的改变被更多人看见")
    parser.add_argument("--media-dir", help="Optional directory of authorized project images/videos.")
    parser.add_argument("--renderer", choices=["hyperframes", "remotion", "auto"], default="hyperframes")
    args = parser.parse_args()

    studio = Path(args.studio).expanduser().resolve()
    content = Path(args.content_file).read_text(encoding="utf-8").strip()
    if len(content) < 20:
        raise SystemExit("公益内容不得少于 20 个字符。")
    project = studio / "projects" / slugify(args.slug or args.name)
    for directory in ("assets/keyframes", "assets/source", "assets/audio", "workflow", "preview", "dist", "qa"):
        (project / directory).mkdir(parents=True, exist_ok=True)
    source_media = []
    if args.media_dir:
        media_dir = Path(args.media_dir).expanduser().resolve()
        if not media_dir.is_dir():
            raise SystemExit(f"素材目录不存在：{media_dir}")
        image_ext = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
        video_ext = {".mp4", ".mov", ".m4v", ".webm"}
        candidates = sorted(path for path in media_dir.iterdir() if path.is_file())
        accepted = [path for path in candidates if path.suffix.lower() in image_ext | video_ext]
        for index, source in enumerate(accepted, 1):
            media_type = "image" if source.suffix.lower() in image_ext else "video"
            target = project / "assets" / "source" / f"{index:02d}-{source.name}"
            shutil.copy2(source, target)
            source_media.append({
                "path": str(target.relative_to(project)),
                "type": media_type,
                "caption": "",
                "rights": "unverified",
            })
    doc = {
        "project_name": args.name,
        "organization": args.organization,
        "source_text": content,
        "duration": args.duration,
        "aspect": "9:16",
        "tone": args.tone,
        "call_to_action": args.cta,
        "rendering": {
            "engine": args.renderer,
            "fallback": "remotion" if args.renderer != "remotion" else "none",
            "motion_profile": "silky",
        },
        "source_media": source_media,
        "models": {
            "writer": "qwen-plus",
            "image": "auto",
            "tts": "auto",
        },
        "fallback_models": {
            "image": "qwen-image-2.0",
            "tts": "cosyvoice-v3.5-plus",
        },
        "providers": {
            "strategy": "best-available",
            "image": "auto",
            "tts": "auto",
            "fallback": "bailian",
        },
        "assets": {
            "keyframes": [{
                "path": "assets/keyframes/01-placeholder.png",
                "cues": ["待生成"],
                "move": "push_in",
                "components": ["headline_strip", "timeline"],
            }],
            "narration": "assets/audio/narration.wav",
            "timestamps": "assets/audio/timestamps.json",
            "music": "assets/audio/ambient.m4a",
            "logo": "",
        },
        "privacy": {
            "minor_faces_allowed": False,
            "materials_authorized": False,
        },
    }
    (project / "project.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    now = datetime.now(timezone.utc).isoformat()
    task_state = {
        "task_id": slugify(args.slug or args.name),
        "status": "created",
        "stage": "input",
        "created_at": now,
        "updated_at": now,
        "source_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "checkpoints": {"input": {"status": "completed", "at": now}},
        "last_error": None,
    }
    (project / "workflow" / "task-state.json").write_text(
        json.dumps(task_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
