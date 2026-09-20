#!/usr/bin/env python3
"""Declarative scene planning, source indexing, and incremental change detection."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from PIL import Image


SKILL_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / "assets" / "runtime" / "layouts" / "registry.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
POINTER_EVENTS = {"focus_ring", "arrow_in", "pin_drop"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def media_dimensions(path: Path) -> tuple[int | None, int | None, float | None]:
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        try:
            with Image.open(path) as image:
                return image.width, image.height, None
        except Exception:
            return None, None, None
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=width,height:format=duration",
             "-select_streams", "v:0", "-of", "json", str(path)],
            check=True, capture_output=True, text=True,
        )
        payload = json.loads(result.stdout)
        stream = (payload.get("streams") or [{}])[0]
        duration = float(payload.get("format", {}).get("duration", 0)) or None
        return stream.get("width"), stream.get("height"), duration
    except Exception:
        return None, None, None


def relative_to_project(project_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_dir.resolve()))
    except ValueError as exc:
        raise ValueError(f"素材必须位于项目目录内：{path}") from exc


def index_sources(project_dir: Path) -> dict[str, Any]:
    project = read_json(project_dir / "project.json")
    declared = {
        str(item.get("path")): item for item in project.get("source_media", [])
        if isinstance(item, dict) and item.get("path")
    }
    source_root = project_dir / "assets" / "source"
    paths = sorted(
        path for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    ) if source_root.exists() else []
    cache_root = project_dir / ".cache" / "materials"
    cache_root.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for path in paths:
        relative = relative_to_project(project_dir, path)
        digest = sha256_file(path)
        width, height, duration = media_dimensions(path)
        asset_id = f"asset-{digest[:12]}"
        meta = declared.get(relative, {})
        cache_path = cache_root / f"{digest}{path.suffix.lower()}"
        if not cache_path.exists():
            try:
                os.link(path, cache_path)
            except OSError:
                shutil.copy2(path, cache_path)
        duplicate_of = seen.get(digest)
        if duplicate_of is None:
            seen[digest] = asset_id
        assets.append({
            "id": asset_id,
            "path": relative,
            "media_type": "image" if path.suffix.lower() in IMAGE_EXTENSIONS else "video",
            "sha256": digest,
            "bytes": path.stat().st_size,
            "width": width,
            "height": height,
            "duration": round(duration, 3) if duration else None,
            "aspect": round(width / height, 4) if width and height else None,
            "caption": meta.get("caption", ""),
            "rights": meta.get("rights", "unverified"),
            "duplicate_of": duplicate_of,
            "cache_path": relative_to_project(project_dir, cache_path),
        })
    manifest = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project.get("project_name", project_dir.name),
        "assets": assets,
        "unique_content": len(seen),
        "duplicates": sum(1 for item in assets if item["duplicate_of"]),
    }
    write_json(project_dir / "workflow" / "source-manifest.json", manifest)
    return manifest


def load_plan(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return read_json(path)
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("scene plan 顶层必须是对象")
    return value


def manifest_lookup(project_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    manifest_path = project_dir / "workflow" / "source-manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else index_sources(project_dir)
    by_id = {item["id"]: item for item in manifest.get("assets", [])}
    by_path = {item["path"]: item for item in manifest.get("assets", [])}
    return by_id, by_path


def resolve_media(raw: Any, by_id: dict[str, dict[str, Any]], by_path: dict[str, dict[str, Any]],
                  project_dir: Path) -> dict[str, Any]:
    item = {"asset": raw} if isinstance(raw, str) else dict(raw)
    reference = item.get("asset") or item.get("path")
    if not reference:
        raise ValueError("每个 media 项必须包含 asset 或 path")
    record = by_id.get(str(reference)) or by_path.get(str(reference))
    if record:
        path = record["path"]
        asset_id = record["id"]
    else:
        path_obj = (project_dir / str(reference)).resolve()
        if not path_obj.exists():
            raise ValueError(f"找不到素材：{reference}")
        path = relative_to_project(project_dir, path_obj)
        asset_id = f"asset-{sha256_file(path_obj)[:12]}"
    at = float(item.get("at", 0))
    if not 0 <= at <= 1:
        raise ValueError(f"素材 {reference} 的 at 必须在 0 到 1 之间")
    return {
        "asset": asset_id,
        "path": path,
        "role": str(item.get("role", "support")),
        "cue": str(item.get("cue", "")),
        "at": at,
        "fit": str(item.get("fit", "contain")),
    }


def validate_event(event: dict[str, Any], scene_id: str) -> None:
    if not event.get("type"):
        raise ValueError(f"场景 {scene_id} 的事件缺少 type")
    at = float(event.get("at", -1))
    if not 0 <= at <= 1:
        raise ValueError(f"场景 {scene_id} 的事件 at 必须在 0 到 1 之间")
    if event["type"] in POINTER_EVENTS and not event.get("target"):
        raise ValueError(f"场景 {scene_id} 的 {event['type']} 必须绑定 target")


def compile_plan(project_dir: Path, plan_path: Path) -> dict[str, Any]:
    project = read_json(project_dir / "project.json")
    plan = load_plan(plan_path)
    registry = read_json(REGISTRY_PATH)["layouts"]
    by_id, by_path = manifest_lookup(project_dir)
    defaults = plan.get("defaults", {}) if isinstance(plan.get("defaults", {}), dict) else {}
    scenes = plan.get("scenes")
    if plan.get("version") != 1 or not isinstance(scenes, list) or not scenes:
        raise ValueError("scene plan 必须是 version: 1 且至少包含一个场景")
    seen_ids: set[str] = set()
    keyframes: list[dict[str, Any]] = []
    compiled_scenes: list[dict[str, Any]] = []
    narration_parts: list[str] = []
    for index, raw_scene in enumerate(scenes, 1):
        scene = dict(raw_scene)
        scene_id = str(scene.get("id") or f"scene-{index:02d}")
        if scene_id in seen_ids:
            raise ValueError(f"重复场景 ID：{scene_id}")
        seen_ids.add(scene_id)
        layout_id = str(scene.get("layout", defaults.get("layout", "single_portrait")))
        if layout_id not in registry:
            raise ValueError(f"未知布局 {layout_id}；可用值：{', '.join(registry)}")
        layout = registry[layout_id]
        media = [resolve_media(item, by_id, by_path, project_dir) for item in scene.get("media", [])]
        if not layout["min_media"] <= len(media) <= layout["max_media"]:
            raise ValueError(
                f"场景 {scene_id} 的 {layout_id} 需要 {layout['min_media']}–{layout['max_media']} 张素材，"
                f"当前为 {len(media)} 张"
            )
        events = [dict(event) for event in scene.get("events", [])]
        for event in events:
            validate_event(event, scene_id)
        move = str(scene.get("move", layout["move"]))
        if move != "static" and len([event for event in events if not event.get("suppressed")]) < 3:
            raise ValueError(f"动态场景 {scene_id} 至少需要三个有语义的 events")
        narration = str(scene.get("narration", ""))
        if narration:
            narration_parts.append(narration)
        cues = [str(value) for value in scene.get("cues", []) if str(value).strip()]
        if not cues:
            cue = next((item["cue"] for item in media if item.get("cue")), "")
            cues = [cue or narration[:12] or scene_id]
        fit = str(scene.get("fit", defaults.get("fit", layout["fit"])))
        if fit not in {"contain", "cover"}:
            raise ValueError(f"场景 {scene_id} 的 fit 只能是 contain 或 cover")
        if fit == "cover" and layout_id != "layered_story":
            raise ValueError(f"场景 {scene_id} 只有 layered_story 可使用 cover，源素材默认必须完整显示")
        item = {
            "path": media[0]["path"],
            "cues": cues,
            "move": move,
            "transition": str(scene.get("transition", defaults.get("transition", "paper_wipe"))),
            "depth": str(scene.get("depth", layout["depth"])),
            "headline": str(scene.get("headline", "")),
            "accent": str(scene.get("accent", defaults.get("accent", "#2D6B55"))),
            "components": [str(value) for value in scene.get("components", [])],
            "motion_events": events,
            "layout_id": layout_id,
            "fit": fit,
            "media": media,
        }
        if layout_id == "static_complete":
            item["cover_mode"] = "static_complete"
        keyframes.append(item)
        compiled_scenes.append({"id": scene_id, "narration": narration, **item})
    approved_path = project_dir / "workflow" / "approved-script.json"
    if not approved_path.exists():
        raise ValueError("缺少 approved-script.json；请先完成脚本确认")
    approved = read_json(approved_path).get("narration", "")
    if normalized_text("".join(narration_parts)) != normalized_text(str(approved)):
        raise ValueError("scene plan 中所有 narration 拼接后与已确认旁白不一致")
    compiled = {
        "version": 1,
        "source": str(plan_path.resolve()),
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "layouts": sorted({scene["layout_id"] for scene in compiled_scenes}),
        "scenes": compiled_scenes,
    }
    project.setdefault("assets", {})["keyframes"] = keyframes
    project.setdefault("rendering", {})["scene_plan"] = "workflow/scene-plan.compiled.json"
    write_json(project_dir / "project.json", project)
    write_json(project_dir / "workflow" / "scene-plan.compiled.json", compiled)
    for stale in ("timeline.json", "preview-approved.json"):
        (project_dir / "workflow" / stale).unlink(missing_ok=True)
    return compiled


def scene_hash(project_dir: Path, scene: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(scene, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for media in scene.get("media", []):
        path = project_dir / media["path"]
        digest.update(sha256_file(path).encode("ascii"))
    approved_path = project_dir / "workflow" / "approved-script.json"
    if approved_path.exists():
        digest.update(approved_path.read_bytes())
    return digest.hexdigest()


def calculate_changes(project_dir: Path, commit: bool = False) -> dict[str, Any]:
    compiled_path = project_dir / "workflow" / "scene-plan.compiled.json"
    if not compiled_path.exists():
        raise ValueError("请先运行 compile")
    compiled = read_json(compiled_path)
    current = {scene["id"]: scene_hash(project_dir, scene) for scene in compiled["scenes"]}
    state_path = project_dir / ".cache" / "scene-state.json"
    previous = read_json(state_path).get("scenes", {}) if state_path.exists() else {}
    dirty = [scene_id for scene_id, digest in current.items() if previous.get(scene_id) != digest]
    removed = sorted(set(previous) - set(current))
    plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dirty_scenes": dirty,
        "reusable_scenes": [scene_id for scene_id in current if scene_id not in dirty],
        "removed_scenes": removed,
        "render_policy": "full_encode_with_cached_assets",
        "reason": "Preserve cross-scene transitions and audio continuity; reuse unchanged materials and frame extraction cache.",
        "scene_hashes": current,
    }
    write_json(project_dir / "workflow" / "incremental-render-plan.json", plan)
    if commit:
        write_json(state_path, {"version": 1, "updated_at": plan["generated_at"], "scenes": current})
    return plan


def initial_plan(project_dir: Path) -> Path:
    project = read_json(project_dir / "project.json")
    manifest = index_sources(project_dir)
    assets_by_path = {item["path"]: item["id"] for item in manifest["assets"]}
    storyboard_path = project_dir / "workflow" / "storyboard.json"
    storyboard = read_json(storyboard_path) if storyboard_path.exists() else {}
    beats = storyboard.get("beats", [])
    scenes = []
    for index, item in enumerate(project.get("assets", {}).get("keyframes", []), 1):
        source = item if isinstance(item, dict) else {"path": str(item)}
        path = source.get("path", "")
        beat = beats[index - 1] if index <= len(beats) else {}
        media = source.get("media") or [{"asset": assets_by_path.get(path, path), "role": "hero", "at": 0}]
        scenes.append({
            "id": f"scene-{index:02d}",
            "narration": beat.get("narration", ""),
            "layout": source.get("layout_id", "static_complete" if source.get("move") == "static" else "single_portrait"),
            "media": media,
            "cues": source.get("cues", []),
            "headline": source.get("headline", ""),
            "move": source.get("move", "push_in"),
            "transition": source.get("transition", "paper_wipe"),
            "fit": source.get("fit", "contain"),
            "events": source.get("motion_events", []),
        })
    path = project_dir / "workflow" / "scene-plan.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "defaults": {"transition": "paper_wipe", "fit": "contain"}, "scenes": scenes}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Declarative public-good video scene pipeline")
    parser.add_argument("project")
    parser.add_argument("command", choices=["index", "init-plan", "compile", "changes", "commit-cache"])
    parser.add_argument("--plan", help="YAML or JSON scene plan; defaults to workflow/scene-plan.yaml")
    args = parser.parse_args()
    project_dir = Path(args.project).expanduser().resolve()
    try:
        if args.command == "index":
            result = index_sources(project_dir)
            print(f"已索引 {len(result['assets'])} 个素材，{result['duplicates']} 个重复项")
        elif args.command == "init-plan":
            print(initial_plan(project_dir))
        elif args.command == "compile":
            path = Path(args.plan).expanduser().resolve() if args.plan else project_dir / "workflow" / "scene-plan.yaml"
            result = compile_plan(project_dir, path)
            calculate_changes(project_dir)
            print(f"已编译 {len(result['scenes'])} 个场景：{project_dir / 'workflow' / 'scene-plan.compiled.json'}")
        else:
            result = calculate_changes(project_dir, commit=args.command == "commit-cache")
            print(json.dumps({key: result[key] for key in ("dirty_scenes", "reusable_scenes", "removed_scenes", "render_policy")}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"错误：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
