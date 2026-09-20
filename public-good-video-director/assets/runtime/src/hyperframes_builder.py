from __future__ import annotations

import json
import html as html_lib
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "hyperframes" / "index.template.html"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def keyframe_path(item: Any) -> str:
    return item["path"] if isinstance(item, dict) else str(item)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_if_changed(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        source_stat = source.stat()
        target_stat = target.stat()
        if source_stat.st_size == target_stat.st_size and source_stat.st_mtime_ns == target_stat.st_mtime_ns:
            return
        if source_stat.st_size == target_stat.st_size and file_hash(source) == file_hash(target):
            os.utime(target, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
            return
    shutil.copy2(source, target)


def scene_build_hash(project_dir: Path, raw: dict[str, Any], source_item: Any) -> str:
    digest = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    paths = [keyframe_path(source_item)]
    if isinstance(source_item, dict):
        paths.extend(media.get("path", "") for media in source_item.get("media", []) if isinstance(media, dict))
        paths.extend(source_item.get("layers", {}).values())
    for relative in dict.fromkeys(path for path in paths if path):
        source = project_dir / relative
        if source.exists():
            digest.update(file_hash(source).encode("ascii"))
    return digest.hexdigest()


def media_duration(path: Path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def build_hyperframes_project(project_dir: Path) -> Path:
    project = read_json(project_dir / "project.json")
    timeline = read_json(project_dir / "workflow" / "timeline.json")
    build_dir = project_dir / "build" / "hyperframes"
    assets = build_dir / "assets"
    (assets / "keyframes").mkdir(parents=True, exist_ok=True)
    (assets / "layers").mkdir(parents=True, exist_ok=True)
    (assets / "audio" / "sfx").mkdir(parents=True, exist_ok=True)
    (assets / "vendor").mkdir(parents=True, exist_ok=True)

    gsap = ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if not gsap.exists():
        raise RuntimeError("HyperFrames renderer requires installed gsap; run bootstrap --install")
    copy_if_changed(gsap, assets / "vendor" / "gsap.min.js")

    copied: dict[str, str] = {}
    for index, item in enumerate(project["assets"]["keyframes"], 1):
        relative = keyframe_path(item)
        source = project_dir / relative
        target = assets / "keyframes" / f"{index:02d}{source.suffix.lower()}"
        copy_if_changed(source, target)
        copied[relative] = f"assets/keyframes/{target.name}"

    def copy_audio(key: str, output_name: str) -> str | None:
        relative = project.get("assets", {}).get(key)
        if not relative:
            return None
        source = project_dir / relative
        if not source.exists():
            return None
        target = assets / "audio" / f"{output_name}{source.suffix.lower()}"
        copy_if_changed(source, target)
        return f"assets/audio/{target.name}"

    narration = copy_audio("narration", "narration")
    music = copy_audio("music", "music")
    scenes = []
    sfx = []
    sfx_root = ROOT / "assets" / "audio" / "sfx"
    copied_sfx: dict[str, str] = {}
    if any(isinstance(item, dict) and item.get("editorial") for item in project["assets"]["keyframes"]):
        source_root = project_dir / "assets" / "source"
        for source in source_root.rglob("*"):
            if source.is_file():
                copy_if_changed(source, assets / "source" / source.relative_to(source_root))
    previous_state_path = project_dir / ".cache" / "hyperframes-scene-state.json"
    previous_state = read_json(previous_state_path).get("scenes", {}) if previous_state_path.exists() else {}
    current_state: dict[str, str] = {}
    for scene_index, raw in enumerate(timeline["scenes"], 1):
        scene = dict(raw)
        scene["file"] = copied[scene["file"]]
        source_item = project["assets"]["keyframes"][scene_index - 1]
        scene_id = str(raw.get("id", scene_index))
        current_state[scene_id] = scene_build_hash(project_dir, raw, source_item)
        if isinstance(source_item, dict) and source_item.get("editorial"):
            scene["editorial"] = source_item["editorial"]
        copied_media = []
        if isinstance(source_item, dict):
            for media_index, media in enumerate(source_item.get("media", []), 1):
                if not isinstance(media, dict) or not media.get("path"):
                    continue
                source = project_dir / media["path"]
                target = assets / "media" / f"{scene_index:02d}" / f"{media_index:02d}{source.suffix.lower()}"
                copy_if_changed(source, target)
                copied_media.append({
                    **media,
                    "path": f"assets/media/{scene_index:02d}/{target.name}",
                })
        if copied_media:
            scene["media"] = copied_media
        layer_doc = source_item.get("layers", {}) if isinstance(source_item, dict) else {}
        copied_layers = {}
        for name, relative in layer_doc.items():
            source = project_dir / relative
            if not source.exists():
                continue
            target_dir = assets / "layers" / f"{scene_index:02d}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{name}{source.suffix.lower()}"
            copy_if_changed(source, target)
            copied_layers[name] = f"assets/layers/{scene_index:02d}/{target.name}"
        if copied_layers:
            scene["layers"] = copied_layers
        scenes.append(scene)
        scene_duration = float(scene["end"]) - float(scene["start"])
        for event in scene.get("motion_events", []):
            name = event.get("sfx")
            source = sfx_root / f"{name}.wav" if name else None
            if not source or not source.exists():
                continue
            if name not in copied_sfx:
                target = assets / "audio" / "sfx" / source.name
                copy_if_changed(source, target)
                copied_sfx[name] = f"assets/audio/sfx/{target.name}"
            sfx.append({
                "file": copied_sfx[name],
                "from": round(float(scene["start"]) + scene_duration * float(event.get("at", 0)), 3),
                "volume": 0.22 if name == "paper" else 0.16,
            })

    facts_path = project_dir / "workflow" / "facts.json"
    selection_path = project_dir / "workflow" / "provider-selection.json"
    data = {
        "projectName": project["project_name"],
        "organization": project.get("organization", ""),
        "duration": float(timeline["duration"]),
        "motionProfile": project.get("rendering", {}).get("motion_profile", "silky"),
        "scenes": scenes,
        "captions": timeline["captions"],
        "narration": narration,
        "music": music,
        "sfx": sfx,
        "cta": project.get("call_to_action", ""),
        "facts": read_json(facts_path) if facts_path.exists() else {},
        "providers": read_json(selection_path) if selection_path.exists() else {},
    }
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    audio_tags = []
    if narration:
        duration = min(data["duration"], media_duration(build_dir / narration))
        audio_tags.append(
            f'<audio id="narration" class="clip" data-start="0" data-duration="{duration:.3f}" '
            f'data-track-index="100" data-volume="0.92" src="{html_lib.escape(narration)}"></audio>'
        )
    if music:
        audio_tags.append(
            f'<audio id="music" class="clip" data-start="0" data-duration="{data["duration"]:.3f}" '
            f'data-track-index="101" data-volume="0.10" loop src="{html_lib.escape(music)}"></audio>'
        )
    for index, item in enumerate(sfx):
        source = build_dir / item["file"]
        duration = min(media_duration(source), max(0.05, data["duration"] - float(item["from"])))
        audio_tags.append(
            f'<audio id="sfx-{index + 1:03d}" class="clip" data-start="{float(item["from"]):.3f}" data-duration="{duration:.3f}" '
            f'data-track-index="{110 + index}" data-volume="{float(item["volume"]):.3f}" '
            f'src="{html_lib.escape(item["file"])}"></audio>'
        )
    custom_template = project.get("rendering", {}).get("template")
    template_path = project_dir / custom_template if custom_template else TEMPLATE
    html = template_path.read_text(encoding="utf-8")
    html = (
        html.replace("__PG_DURATION__", f"{data['duration']:.3f}")
        .replace("__PG_AUDIO_TAGS__", "\n".join(audio_tags))
        .replace("__PG_DATA__", encoded)
    )
    (build_dir / "index.html").write_text(html, encoding="utf-8")
    write_json(build_dir / "hyperframes.json", {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
        "media": {"autoProxy": True},
        "authoringSkill": "public-good-video-director",
    })
    dirty = [scene_id for scene_id, digest in current_state.items() if previous_state.get(scene_id) != digest]
    write_json(build_dir / "render-manifest.json", {
        "engine": "hyperframes",
        "project": project["project_name"],
        "duration": data["duration"],
        "scenes": len(scenes),
        "captions": len(timeline["captions"]),
        "motion_profile": data["motionProfile"],
        "dirty_scenes": dirty,
        "reusable_scenes": [scene_id for scene_id in current_state if scene_id not in dirty],
        "scene_hashes": current_state,
        "render_policy": "full_encode_with_cached_assets",
    })
    return build_dir


def commit_hyperframes_scene_state(project_dir: Path, build_dir: Path) -> None:
    manifest = read_json(build_dir / "render-manifest.json")
    write_json(project_dir / ".cache" / "hyperframes-scene-state.json", {
        "version": 1,
        "scenes": manifest.get("scene_hashes", {}),
        "last_successful_render": str(build_dir),
    })
