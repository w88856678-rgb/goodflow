#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hyperframes_builder import build_hyperframes_project, commit_hyperframes_scene_state

ROOT = Path(__file__).resolve().parents[1]
REMOTION = ROOT / "remotion"
DEFAULT_SECRET_FILE = ROOT / ".env"

PALETTES = [
    "#2D6B55", "#D9543F", "#335D73", "#E3AF3E",
    "#C95B3B", "#4E6651", "#B54B3F", "#806642",
]
MOVES = ["pull_out", "push_in", "rise", "pan", "push_in", "parallax", "pull_out", "static"]
COMPONENT_SETS = [
    ["headline_strip", "timeline"],
    ["photo_slap", "steam"],
    ["route_line", "arrow"],
    ["stat_badges", "headline_strip"],
    ["clock", "steam", "ring_focus"],
    ["starburst", "confetti", "ring_focus"],
    ["photo_wall", "quote_card"],
    ["cta_card"],
]


def keyframe_path(item: Any) -> str:
    return item["path"] if isinstance(item, dict) else str(item)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_task_state(
    project_dir: Path,
    stage: str,
    status: str,
    *,
    output: str | None = None,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    path = project_dir / "workflow" / "task-state.json"
    if path.exists():
        state = read_json(path)
    else:
        now = utc_now()
        state = {
            "task_id": project_dir.name,
            "status": "created",
            "stage": "input",
            "created_at": now,
            "updated_at": now,
            "checkpoints": {},
            "last_error": None,
        }
    now = utc_now()
    state["status"] = status
    state["stage"] = stage
    state["updated_at"] = now
    checkpoint = {"status": status, "at": now}
    if output:
        checkpoint["output"] = output
    if details:
        checkpoint["details"] = details
    state.setdefault("checkpoints", {})[stage] = checkpoint
    state["last_error"] = error
    write_json(path, state)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def validate_project(doc: dict[str, Any], project_dir: Path) -> list[str]:
    errors: list[str] = []
    for key in ("project_name", "source_text", "duration", "aspect", "tone", "assets"):
        if key not in doc:
            errors.append(f"缺少字段：{key}")
    if len(str(doc.get("source_text", ""))) < 20:
        errors.append("source_text 至少需要20个字符")
    if doc.get("aspect") != "9:16":
        errors.append("第一阶段仅支持9:16")
    duration = doc.get("duration", 0)
    if not isinstance(duration, (int, float)) or not 10 <= duration <= 180:
        errors.append("duration 必须在10到180秒之间")
    assets = doc.get("assets", {})
    keyframes = assets.get("keyframes", []) if isinstance(assets, dict) else []
    if not keyframes:
        errors.append("assets.keyframes 至少需要一张图片")
    for item in keyframes:
        rel = keyframe_path(item)
        if not (project_dir / rel).exists():
            errors.append(f"找不到关键帧：{rel}")
        if isinstance(item, dict):
            for media in item.get("media", []):
                media_rel = media.get("path") if isinstance(media, dict) else None
                if media_rel and not (project_dir / media_rel).exists():
                    errors.append(f"找不到场景素材：{media_rel}")
            for layer_name, layer_rel in item.get("layers", {}).items():
                if not (project_dir / layer_rel).exists():
                    errors.append(f"找不到分层素材 {layer_name}：{layer_rel}")
    for key in ("narration", "music", "logo", "timestamps"):
        rel = assets.get(key) if isinstance(assets, dict) else None
        if rel and not (project_dir / rel).exists():
            errors.append(f"找不到素材 assets.{key}：{rel}")
    return errors


def sentence_split(text: str) -> list[str]:
    parts = [x.strip() for x in re.split(r"(?<=[。！？!?；;])\s*", text) if x.strip()]
    return parts or [text.strip()]


def extract_numbers(text: str) -> list[dict[str, str]]:
    pattern = r"(?:二[〇零]二[〇零]|20\d{2}|\d{1,4}(?::\d{2})?)"
    return [{"value": m.group(0), "context": text[max(0, m.start()-18):m.end()+18]}
            for m in re.finditer(pattern, text)]


def offline_facts(doc: dict[str, Any]) -> dict[str, Any]:
    text = doc["source_text"]
    sentences = sentence_split(text)
    names = re.findall(r"[\u4e00-\u9fff]{2,20}(?:小学|学校|项目|基金会|协会|中心)", text)
    years = re.findall(r"(?:19|20)\d{2}年?", text)
    times = re.findall(r"\d{1,2}[点时:：]\d{0,2}分?", text)
    return {
        "project_name": doc["project_name"],
        "organization": doc.get("organization", ""),
        "locations_or_entities": list(dict.fromkeys(names))[:12],
        "years": list(dict.fromkeys(years)),
        "times": list(dict.fromkeys(times)),
        "numbers": extract_numbers(text),
        "verified_statements": sentences,
        "uncertain_information": [],
        "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "mode": "offline_rules"
    }


def trim_script(text: str, duration: float) -> str:
    target_chars = int(duration * 7.2)
    if len(text) <= target_chars:
        return text
    sentences = sentence_split(text)
    out: list[str] = []
    for sentence in sentences:
        if len("".join(out)) + len(sentence) > target_chars and out:
            break
        out.append(sentence)
    return "".join(out)


def offline_scripts(doc: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    statements = facts["verified_statements"]
    duration = float(doc["duration"])
    if len(statements) >= 4:
        opening = statements[0]
        middle = "".join(statements[1:-1])
        ending = statements[-1]
    else:
        opening = statements[0]
        middle = "".join(statements[1:])
        ending = doc.get("call_to_action", "每一份改变，都值得被看见。")
    warm = trim_script(f"{opening}{middle}{ending}", duration)
    documentary = trim_script("".join(statements), duration)
    progress = trim_script(
        f"{doc['project_name']}正在发生新的变化。{''.join(statements)}"
        f"{doc.get('call_to_action', '让真实的进展被更多人看见。')}", duration
    )
    return {
        "variants": [
            {"id": "warm", "name": "温暖松弛", "narration": warm,
             "direction": "自然讲述、克制、不使用播音腔，不额外添加事实。"},
            {"id": "documentary", "name": "纪实克制", "narration": documentary,
             "direction": "先事实后感受，数字清晰，情绪不过度。"},
            {"id": "progress", "name": "进展有力", "narration": progress,
             "direction": "强调行动、变化与结果，结尾给出清晰行动方向。"}
        ],
        "fact_check": {
            "source_hash": facts["source_hash"],
            "unsupported_claims": [],
            "status": "pass_offline"
        },
        "mode": "offline_rules"
    }


def qwen_json(model: str, system: str, user: str) -> dict[str, Any]:
    load_env_file(DEFAULT_SECRET_FILE)
    key = os.getenv("DASHSCOPE_API_KEY", "")
    if not key:
        raise RuntimeError("未找到 DASHSCOPE_API_KEY，请使用 --offline 或配置百炼 Key")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.4
    }
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"百炼请求失败：HTTP {exc.code} {detail[:400]}") from exc
    content = result["choices"][0]["message"]["content"]
    return json.loads(content)


def live_prepare(doc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    model = doc.get("models", {}).get("writer", "qwen-plus")
    facts = qwen_json(
        model,
        "你是公益内容事实编辑。只提取原文明确提供的信息，不推断、不补写。必须输出JSON。",
        "请把下面材料提取为JSON。字段必须包含 project_name、organization、"
        "locations_or_entities、years、times、numbers、verified_statements、"
        "uncertain_information。每条 verified_statements 必须能在原文中找到依据。\n\n"
        + doc["source_text"]
    )
    facts["source_hash"] = hashlib.sha256(doc["source_text"].encode("utf-8")).hexdigest()
    facts["mode"] = f"qwen:{model}"
    scripts = qwen_json(
        model,
        "你是中文公益短片导演。不得增加输入中不存在的事实。文案必须自然、口语化、"
        "有故事推进，避免播音腔和过度煽情。必须输出JSON。",
        "根据事实卡片生成三版旁白，目标时长"
        f"{doc['duration']}秒。输出字段 variants 数组，每项必须有 id、name、narration、"
        "direction；id依次为 warm、documentary、progress。另输出 fact_check，包含"
        "unsupported_claims和status。事实卡片如下：\n"
        + json.dumps(facts, ensure_ascii=False)
    )
    scripts["mode"] = f"qwen:{model}"
    return facts, scripts


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True
    )
    return float(result.stdout.strip())


def caption_chunks(text: str, max_chars: int = 42) -> list[str]:
    """Preserve complete sentences; max_chars is retained for caller compatibility.

    Visual wrapping is handled by caption.lines/layout, never by silently making
    a new timed card at a comma just because a sentence is long.
    """
    chunks = [item.strip() for item in re.findall(r".*?(?:[。！？；]|$)", text, re.S) if item.strip()]
    return chunks or [text]


def make_captions(text: str, duration: float,
                  timestamp_doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if timestamp_doc:
        source = timestamp_doc.get("captions", timestamp_doc.get("segments", []))
        captions = [
            {"from": round(float(c["from"]), 3), "to": round(float(c["to"]), 3),
             "text": str(c["text"]).strip()}
            for c in source
            if c.get("text") and float(c["to"]) > float(c["from"])
        ]
        if captions:
            originals = [c for c in source if c.get("text") and float(c["to"]) > float(c["from"])]
            for caption, original in zip(captions, originals):
                if "lines" not in original:
                    continue
                lines = original["lines"]
                if not isinstance(lines, list) or not lines or any(not isinstance(line, str) or not line or "\n" in line for line in lines) or "".join(lines) != caption["text"]:
                    raise ValueError("Caption lines must preserve the exact approved text and punctuation.")
                caption["lines"] = lines
            return captions
    chunks = caption_chunks(text)
    weights = [max(2, len(re.sub(r"\s", "", c))) for c in chunks]
    lead, tail = min(0.35, duration * 0.02), min(0.45, duration * 0.025)
    usable = max(1.0, duration - lead - tail)
    total_weight = sum(weights)
    captions: list[dict[str, Any]] = []
    cursor = lead
    for i, (chunk, weight) in enumerate(zip(chunks, weights)):
        seg = usable * weight / total_weight
        end = duration - tail if i == len(chunks) - 1 else cursor + seg
        captions.append({"from": round(cursor, 3), "to": round(end, 3), "text": chunk})
        cursor = end
    return captions


def normalize_cue_text(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", str(value)).casefold()


def cue_start_from_words(cues: list[Any], words: list[dict[str, Any]], minimum_start: float) -> float | None:
    stream: list[str] = []
    times: list[float] = []
    for word in words:
        token = normalize_cue_text(word.get("word", word.get("text", word.get("token", ""))))
        if not token:
            continue
        start = float(word.get("from", word.get("start", 0.0)))
        stream.extend(token)
        times.extend([start] * len(token))
    joined = "".join(stream)
    for cue in cues:
        needle = normalize_cue_text(cue)
        if not needle:
            continue
        position = joined.find(needle)
        while position >= 0:
            if position < len(times) and times[position] >= minimum_start:
                return times[position]
            position = joined.find(needle, position + 1)
    return None


def cue_start(item: Any, captions: list[dict[str, Any]], index: int, count: int,
              words: list[dict[str, Any]] | None = None, minimum_start: float = 0.0) -> float:
    if isinstance(item, dict):
        cues = item.get("cues", [])
        word_start = cue_start_from_words(cues, words or [], minimum_start)
        if word_start is not None:
            return word_start
        for caption in captions:
            if float(caption["from"]) < minimum_start:
                continue
            normalized = normalize_cue_text(caption["text"])
            if any(normalize_cue_text(cue) in normalized for cue in cues):
                return float(caption["from"])
    caption_index = min(len(captions) - 1, round(index * len(captions) / count))
    return max(minimum_start, float(captions[caption_index]["from"]))


def make_timeline(text: str, duration: float, keyframes: list[Any],
                  timestamp_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    captions = make_captions(text, duration, timestamp_doc)
    scene_count = len(keyframes)
    words = timestamp_doc.get("words", []) if timestamp_doc else []
    cue_starts: list[float] = []
    for i, item in enumerate(keyframes):
        minimum_start = cue_starts[-1] + 0.5 if cue_starts else 0.0
        cue_starts.append(cue_start(item, captions, i, scene_count, words, minimum_start))
    cue_starts[0] = 0.0
    for i in range(1, len(cue_starts)):
        cue_starts[i] = max(cue_starts[i], cue_starts[i - 1] + 0.5)
    scenes = []
    for i in range(scene_count):
        item = keyframes[i]
        cue = cue_starts[i]
        next_cue = cue_starts[i + 1] if i < scene_count - 1 else duration
        start = max(0, cue - (0.18 if i else 0))
        end = min(duration, next_cue + (0.24 if i < scene_count - 1 else 0))
        scenes.append({
            "id": i + 1,
            "file": keyframe_path(item),
            "start": round(start, 3),
            "end": round(end, 3),
            "cue_start": round(cue, 3),
            "move": item.get("move", MOVES[i % len(MOVES)]) if isinstance(item, dict) else MOVES[i % len(MOVES)],
            "accent": item.get("accent", PALETTES[i % len(PALETTES)]) if isinstance(item, dict) else PALETTES[i % len(PALETTES)],
            "motion_components": item.get("components", COMPONENT_SETS[i % len(COMPONENT_SETS)])
            if isinstance(item, dict) else COMPONENT_SETS[i % len(COMPONENT_SETS)],
            "motion_events": item.get("motion_events", []) if isinstance(item, dict) else [],
            "transition": item.get("transition", "paper_wipe") if isinstance(item, dict) else "paper_wipe",
            "depth": item.get("depth", "layered") if isinstance(item, dict) else "layered",
            "headline": item.get("headline", "") if isinstance(item, dict) else "",
            "matched_cues": item.get("cues", []) if isinstance(item, dict) else [],
            "layout_id": item.get("layout_id", "") if isinstance(item, dict) else "",
            "fit": item.get("fit", "cover") if isinstance(item, dict) else "cover",
            "cover_mode": item.get("cover_mode", "") if isinstance(item, dict) else "",
            "media": item.get("media", []) if isinstance(item, dict) else [],
        })
    return {
        "duration": round(duration, 3),
        "alignment": timestamp_doc.get("alignment_method", "provided_timestamps+semantic_cues") if timestamp_doc else "estimated_timestamps+ordered_cues",
        "captions": captions,
        "scenes": scenes
    }


def apply_safe_layout(timeline: dict[str, Any], safe_doc: dict[str, Any] | None) -> None:
    if not safe_doc:
        return
    by_id = {int(item['scene_id']): item for item in safe_doc.get('scenes', [])}
    wide_types = {'underline', 'fact_stack', 'cause_flow', 'quote_reveal', 'cta_reveal'}
    for scene in timeline.get('scenes', []):
        analysis = by_id.get(int(scene.get('id', 0)))
        if not analysis:
            continue
        candidates = sorted(analysis.get('safe_boxes', []), key=lambda box: float(box.get('score', 1)))
        used: list[dict[str, Any]] = []
        for event in scene.get('motion_events', []):
            if event.get('layout') or event.get('type') == 'paper_label':
                continue
            compatible = [
                box for box in candidates
                if box not in used and (
                    event.get('type') not in wide_types or int(box.get('width', 0)) >= 800
                )
            ]
            if not compatible:
                compatible = [box for box in candidates if box not in used]
            if not compatible:
                continue
            box = compatible[0]
            used.append(box)
            if box.get('safety') == 'least_risk_fallback':
                event['suppressed'] = True
                event['suppression_reason'] = 'no_verified_negative_space'
                continue
            event['layout'] = {
                'x': int(box['x']), 'y': int(box['y']),
                'width': int(box['width']), 'height': int(box['height']),
                'source': f"visual-safe-zones:{box.get('safety', 'unknown')}",
            }
        scene['protected_boxes'] = analysis.get('protected_boxes', [])
        scene['safe_boxes'] = analysis.get('safe_boxes', [])


def material_hash(project_dir: Path) -> str:
    h = hashlib.sha256()
    for rel in (
        "project.json", "workflow/approved-script.json", "workflow/timeline.json",
        "workflow/scene-plan.compiled.json", "workflow/source-manifest.json",
    ):
        path = project_dir / rel
        if path.exists():
            h.update(path.read_bytes())
    doc = read_json(project_dir / "project.json")
    # Layout-only edits to a project-local template must invalidate approval too.
    template = doc.get("rendering", {}).get("template")
    if template:
        template_path = project_dir / template
        if template_path.is_file():
            h.update(template_path.read_bytes())
        else:
            h.update(b"missing-render-template")
    for item in doc.get("assets", {}).get("keyframes", []):
        path = project_dir / keyframe_path(item)
        if path.exists():
            h.update(str(path.stat().st_mtime_ns).encode())
        if isinstance(item, dict):
            for media in item.get("media", []):
                media_rel = media.get("path") if isinstance(media, dict) else None
                media_path = project_dir / media_rel if media_rel else None
                if media_path and media_path.exists():
                    h.update(str(media_path.stat().st_mtime_ns).encode())
            for rel in item.get("layers", {}).values():
                layer = project_dir / rel
                if layer.exists():
                    h.update(str(layer.stat().st_mtime_ns).encode())
    for key in ("narration", "music"):
        rel = doc.get("assets", {}).get(key)
        path = project_dir / rel if rel else None
        if path and path.exists():
            h.update(str(path.stat().st_mtime_ns).encode())
    return h.hexdigest()


def build_props(project_dir: Path) -> Path:
    doc = read_json(project_dir / "project.json")
    errors = validate_project(doc, project_dir)
    if errors:
        raise RuntimeError("\n".join(errors))
    approved = read_json(project_dir / "workflow" / "approved-script.json")
    timeline = read_json(project_dir / "workflow" / "timeline.json")
    public_project = REMOTION / "public" / "project"
    if public_project.exists():
        shutil.rmtree(public_project)
    (public_project / "keyframes").mkdir(parents=True, exist_ok=True)
    (public_project / "layers").mkdir(parents=True, exist_ok=True)
    (public_project / "audio").mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for i, item in enumerate(doc["assets"]["keyframes"], 1):
        rel = keyframe_path(item)
        src = project_dir / rel
        dst = public_project / "keyframes" / f"{i:02d}{src.suffix.lower()}"
        shutil.copy2(src, dst)
        copied[rel] = f"project/keyframes/{dst.name}"
    narration_rel = doc["assets"].get("narration")
    music_rel = doc["assets"].get("music")
    narration_out = None
    music_out = None
    if narration_rel:
        src = project_dir / narration_rel
        dst = public_project / "audio" / f"narration{src.suffix.lower()}"
        shutil.copy2(src, dst)
        narration_out = f"project/audio/{dst.name}"
    if music_rel:
        src = project_dir / music_rel
        dst = public_project / "audio" / f"music{src.suffix.lower()}"
        shutil.copy2(src, dst)
        music_out = f"project/audio/{dst.name}"
    scenes = timeline["scenes"]
    for index, scene in enumerate(scenes):
        scene["file"] = copied[scene["file"]]
        source_item = doc["assets"]["keyframes"][index]
        layer_doc = source_item.get("layers", {}) if isinstance(source_item, dict) else {}
        copied_layers = {}
        for name, rel in layer_doc.items():
            source = project_dir / rel
            if not source.exists():
                continue
            target_dir = public_project / "layers" / f"{index + 1:02d}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{name}{source.suffix.lower()}"
            shutil.copy2(source, target)
            copied_layers[name] = f"project/layers/{index + 1:02d}/{target.name}"
        if copied_layers:
            scene["layers"] = copied_layers
    sfx = []
    sfx_root = ROOT / "assets" / "audio" / "sfx"
    sfx_public = public_project / "audio" / "sfx"
    sfx_public.mkdir(parents=True, exist_ok=True)
    copied_sfx: dict[str, str] = {}
    for scene in scenes:
        scene_duration = float(scene["end"]) - float(scene["start"])
        for event in scene.get("motion_events", []):
            name = event.get("sfx")
            source = sfx_root / f"{name}.wav" if name else None
            if not source or not source.exists():
                continue
            if name not in copied_sfx:
                target = sfx_public / source.name
                shutil.copy2(source, target)
                copied_sfx[name] = f"project/audio/sfx/{source.name}"
            sfx.append({
                "file": copied_sfx[name],
                "from": round(float(scene["start"]) + scene_duration * float(event.get("at", 0)), 3),
                "volume": 0.24 if name == "paper" else 0.18,
            })
    props = {
        "projectName": doc["project_name"],
        "organization": doc.get("organization", ""),
        "duration": timeline["duration"],
        "fps": 30,
        "scenes": scenes,
        "captions": timeline["captions"],
        "narration": narration_out,
        "music": music_out,
        "sfx": sfx,
        "script": approved["narration"],
        "cta": doc.get("call_to_action", ""),
        "facts": read_json(project_dir / "workflow" / "facts.json"),
        "materialHash": material_hash(project_dir)
    }
    out = project_dir / "build" / "remotion-props.json"
    write_json(out, props)
    return out


def pnpm_path() -> str:
    found = shutil.which("pnpm")
    if found:
        return found
    fallback = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError("未找到 pnpm，请安装 Node.js LTS 与 pnpm")


def node_env() -> dict[str, str]:
    env = os.environ.copy()
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"
    if bundled.exists():
        env["PATH"] = f"{bundled}:{env.get('PATH', '')}"
    return env


def ensure_node_modules() -> None:
    required = [
        ROOT / "node_modules" / ".bin" / "remotion",
        ROOT / "node_modules" / ".bin" / "hyperframes",
        ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js",
    ]
    if all(path.exists() for path in required):
        return
    subprocess.run([pnpm_path(), "install"], cwd=ROOT, env=node_env(), check=True)


def frame_average_luma(video: Path, frame_number: int) -> int | None:
    result = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(video),
        "-vf", f"select=eq(n\\,{frame_number}),scale=1:1:flags=area,format=gray",
        "-frames:v", "1", "-f", "rawvideo", "pipe:1",
    ], check=False, capture_output=True)
    return result.stdout[0] if result.returncode == 0 and result.stdout else None


def first_frame_initializer_glitch(video: Path) -> tuple[bool, int | None, int | None]:
    first = frame_average_luma(video, 0)
    second = frame_average_luma(video, 1)
    glitch = first is not None and second is not None and first <= 32 and second >= first + 18
    return glitch, first, second


def finalize_rendered_video(project_dir: Path, raw: Path, out: Path, preview: bool) -> None:
    repair, first_luma, second_luma = first_frame_initializer_glitch(raw)
    command = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw)]
    if repair:
        command.extend([
            "-filter:v", "trim=start_frame=1,setpts=PTS-STARTPTS,tpad=start_duration=0.033333:start_mode=clone",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23" if preview else "18",
            "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p",
        ])
    else:
        command.extend(["-c:v", "copy"])
    command.extend([
        "-af", "loudnorm=I=-16:LRA=5:TP=-1.5", "-ar", "48000",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
    ])
    subprocess.run(command, check=True)
    write_json(project_dir / "workflow" / "output-validation.json", {
        "mode": "preview" if preview else "final",
        "first_frame_policy": "repair_initializer_black_frame",
        "first_frame_repaired": repair,
        "raw_first_frame_luma": first_luma,
        "raw_second_frame_luma": second_luma,
        "audio_sample_rate": 48000,
        "faststart": True,
        "output": str(out.resolve()),
        "updated_at": utc_now(),
    })


def render_remotion(project_dir: Path, preview: bool) -> Path:
    props = build_props(project_dir)
    ensure_node_modules()
    if preview:
        out = project_dir / "preview" / "preview.mp4"
    else:
        approval = project_dir / "workflow" / "preview-approved.json"
        if not approval.exists():
            raise RuntimeError("低清预览尚未确认，请先运行 approve-preview")
        stamp = read_json(approval)
        if stamp.get("material_hash") != material_hash(project_dir):
            raise RuntimeError("文案或素材在预览确认后发生变化，请重新生成并确认预览")
        out = project_dir / "dist" / "final.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_name(f"{out.stem}-raw{out.suffix}")
    cmd = [
        pnpm_path(), "exec", "remotion", "render",
        "remotion/src/index.jsx", "PublicGoodFilm", str(raw),
        f"--props={props}", "--codec=h264", "--audio-codec=aac",
        "--public-dir=remotion/public",
        "--crf=21" if not preview else "--crf=28",
        "--scale=1" if not preview else "--scale=0.5",
        "--overwrite"
    ]
    subprocess.run(cmd, cwd=ROOT, env=node_env(), check=True)
    finalize_rendered_video(project_dir, raw, out, preview)
    raw.unlink(missing_ok=True)
    return out


def approved_output_path(project_dir: Path, preview: bool) -> Path:
    if preview:
        return project_dir / "preview" / "preview.mp4"
    approval = project_dir / "workflow" / "preview-approved.json"
    if not approval.exists():
        raise RuntimeError("低清预览尚未确认，请先运行 approve-preview")
    stamp = read_json(approval)
    if stamp.get("material_hash") != material_hash(project_dir):
        raise RuntimeError("文案或素材在预览确认后发生变化，请重新生成并确认预览")
    return project_dir / "dist" / "final.mp4"


def render_hyperframes(project_dir: Path, preview: bool) -> Path:
    ensure_node_modules()
    out = approved_output_path(project_dir, preview)
    out.parent.mkdir(parents=True, exist_ok=True)
    build_dir = build_hyperframes_project(project_dir)
    raw = out.with_name(f"{out.stem}-hyperframes-raw{out.suffix}")
    cmd = [
        shutil.which("node") or "node", str(ROOT / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"),
        "render", str(build_dir),
        "--output", str(raw), "--format", "mp4", "--fps", "30",
        "--resolution", "portrait", "--quality", "draft" if preview else "high",
        "--crf", "28" if preview else "21", "--skill", "public-good-video-director",
        "--workers", "auto",
        "--frames-cache-dir", str(project_dir / ".cache" / "hyperframes-frames"),
        "--best-effort",
    ]
    subprocess.run(cmd, cwd=ROOT, env=node_env(), check=True)
    finalize_rendered_video(project_dir, raw, out, preview)
    commit_hyperframes_scene_state(project_dir, build_dir)
    raw.unlink(missing_ok=True)
    return out


def record_render_selection(
    project_dir: Path,
    requested: str,
    actual: str,
    preview: bool,
    output: Path,
    attempts: list[dict[str, Any]],
) -> None:
    write_json(project_dir / "workflow" / "render-selection.json", {
        "requested": requested,
        "actual": actual,
        "fallback_used": actual != requested and requested not in {"auto", actual},
        "mode": "preview" if preview else "final",
        "output": str(output.resolve()),
        "attempts": attempts,
        "updated_at": utc_now(),
    })


def render(project_dir: Path, preview: bool, engine_override: str = "auto") -> Path:
    project = read_json(project_dir / "project.json")
    rendering = project.get("rendering", {})
    requested = engine_override if engine_override != "auto" else rendering.get("engine", "hyperframes")
    if requested == "auto":
        requested = "hyperframes"
    fallback = rendering.get("fallback", "remotion")
    candidates = [requested]
    if fallback not in {"none", requested}:
        candidates.append(fallback)
    attempts: list[dict[str, Any]] = []
    last_error: Exception | None = None
    for engine in candidates:
        try:
            output = render_hyperframes(project_dir, preview) if engine == "hyperframes" else render_remotion(project_dir, preview)
            attempts.append({"engine": engine, "status": "completed"})
            record_render_selection(project_dir, requested, engine, preview, output, attempts)
            return output
        except (RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as exc:
            last_error = exc
            attempts.append({"engine": engine, "status": "failed", "error": str(exc)[:600]})
    raise RuntimeError(f"所有渲染后端均失败：{last_error}")


def run_capture(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=False, capture_output=True, text=True).stderr


def qa(project_dir: Path, video: Path | None = None) -> Path:
    if video is None:
        final = project_dir / "dist" / "final.mp4"
        preview = project_dir / "preview" / "preview.mp4"
        candidates = [path for path in (preview, final) if path.exists()]
        video = max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else preview
    if not video.exists():
        raise RuntimeError("找不到视频，请先执行 preview 或 render")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
        check=True, capture_output=True, text=True
    )
    metadata = json.loads(probe.stdout)
    black = run_capture(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                         "blackdetect=d=0.2:pix_th=0.10", "-an", "-f", "null", "-"])
    freeze = run_capture(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                          "freezedetect=n=-50dB:d=2", "-an", "-f", "null", "-"])
    loudness = run_capture(["ffmpeg", "-hide_banner", "-i", str(video), "-af",
                            "ebur128=peak=true", "-vn", "-f", "null", "-"])
    integrated = None
    matches = re.findall(r"I:\s*(-?\d+(?:\.\d+)?) LUFS", loudness)
    if matches:
        integrated = float(matches[-1])
    black_events = re.findall(r"black_start:([0-9.]+).*?black_end:([0-9.]+)", black)
    freeze_events = re.findall(r"freeze_start: ([0-9.]+).*?freeze_end: ([0-9.]+)", freeze, re.S)
    freeze_ranges = [(float(start), float(end)) for start, end in freeze_events]
    video_stream = next((s for s in metadata["streams"] if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in metadata["streams"] if s.get("codec_type") == "audio"), {})
    first_frame_black, first_luma, second_luma = first_frame_initializer_glitch(video)
    audio_sample_rate = int(audio_stream.get("sample_rate", 0) or 0)
    checks = {
        "has_video": bool(video_stream),
        "has_audio": bool(audio_stream),
        "portrait": video_stream.get("height", 0) > video_stream.get("width", 0),
        "black_frames": len(black_events) + int(first_frame_black and not black_events),
        "first_frame_visible": not first_frame_black,
        "first_frame_luma": first_luma,
        "second_frame_luma": second_luma,
        "audio_sample_rate": audio_sample_rate,
        "publish_audio_rate_ok": audio_sample_rate == 48000,
        "long_freezes": len(freeze_events),
        "integrated_lufs": integrated,
        "loudness_ok": integrated is not None and -18.5 <= integrated <= -13.5,
        "ocr": "not_run_mvp",
        "asr_roundtrip": "not_run_mvp"
    }
    timeline_path = project_dir / "workflow" / "timeline.json"
    if timeline_path.exists():
        timeline = read_json(timeline_path)
        dynamic_scenes = [scene for scene in timeline.get("scenes", []) if scene.get("move") != "static"]
        event_counts = [
            sum(1 for event in scene.get("motion_events", []) if not event.get("suppressed"))
            for scene in dynamic_scenes
        ]
        static_ranges = [
            (float(scene.get("start", 0)), float(scene.get("end", 0)))
            for scene in timeline.get("scenes", []) if scene.get("move") == "static"
        ]
        intentional_freezes = [
            (start, end) for start, end in freeze_ranges
            if any(start >= scene_start - .25 and end <= scene_end + .5 for scene_start, scene_end in static_ranges)
        ]
        unexpected_freezes = [item for item in freeze_ranges if item not in intentional_freezes]
        pointer_types = {"focus_ring", "arrow_in", "pin_drop"}
        untargeted = [
            {"scene": scene.get("id"), "type": event.get("type")}
            for scene in timeline.get("scenes", [])
            for event in scene.get("motion_events", [])
            if not event.get("suppressed") and event.get("type") in pointer_types and not event.get("target")
        ]
        checks["motion_events"] = sum(event_counts)
        checks["minimum_events_per_scene"] = min(event_counts) if event_counts else 0
        checks["motion_density_ok"] = bool(event_counts) and min(event_counts) >= 3
        checks["static_scenes"] = len(static_ranges)
        checks["intentional_static_freezes"] = len(intentional_freezes)
        checks["unexpected_long_freezes"] = len(unexpected_freezes)
        checks["untargeted_pointer_events"] = untargeted
        checks["targeted_markers_ok"] = not untargeted
        checks["occlusion_review"] = "manual_required_at_early_middle_late_scene_frames"
        checks["safe_layout_events"] = sum(
            1 for scene in timeline.get("scenes", []) for event in scene.get("motion_events", []) if event.get("layout")
        )
        checks["suppressed_unsafe_overlays"] = [
            {"scene": scene.get("id"), "type": event.get("type"),
             "reason": event.get("suppression_reason") or event.get("suppressed_reason")}
            for scene in timeline.get("scenes", []) for event in scene.get("motion_events", []) if event.get("suppressed")
        ]
        def layout_overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
            x1, y1 = max(float(a["x"]), float(b["x"])), max(float(a["y"]), float(b["y"]))
            x2 = min(float(a["x"]) + float(a["width"]), float(b["x"]) + float(b["width"]))
            y2 = min(float(a["y"]) + float(a["height"]), float(b["y"]) + float(b["height"]))
            if x2 <= x1 or y2 <= y1:
                return 0.0
            return (x2 - x1) * (y2 - y1) / max(1.0, float(a["width"]) * float(a["height"]))
        layout_occlusions = []
        for scene in timeline.get("scenes", []):
            for event in scene.get("motion_events", []):
                layout = event.get("layout")
                if not layout:
                    continue
                overlap = max([layout_overlap(layout, protected) for protected in scene.get("protected_boxes", [])] or [0.0])
                if overlap >= .12:
                    layout_occlusions.append({"scene": scene.get("id"), "type": event.get("type"), "overlap": round(overlap, 3)})
        checks["layout_occlusions"] = layout_occlusions
        checks["automatic_occlusion_ok"] = not layout_occlusions
    else:
        checks["motion_events"] = 0
        checks["minimum_events_per_scene"] = 0
        checks["motion_density_ok"] = False
        checks["untargeted_pointer_events"] = []
        checks["targeted_markers_ok"] = False
        checks["occlusion_review"] = "manual_required_at_early_middle_late_scene_frames"
        checks["safe_layout_events"] = 0
        checks["suppressed_unsafe_overlays"] = []
        checks["layout_occlusions"] = []
        checks["automatic_occlusion_ok"] = False
        checks["static_scenes"] = 0
        checks["intentional_static_freezes"] = 0
        checks["unexpected_long_freezes"] = len(freeze_ranges)
    timestamp_path = project_dir / "assets" / "audio" / "timestamps.json"
    if timestamp_path.exists():
        alignment = read_json(timestamp_path)
        checks["alignment_method"] = alignment.get("alignment_method", "unknown")
        checks["word_alignment"] = alignment.get("confidence", "unknown")
    else:
        checks["alignment_method"] = "missing"
        checks["word_alignment"] = "missing"
    checks["status"] = "pass" if (
        checks["has_video"] and checks["has_audio"] and checks["portrait"]
        and checks["black_frames"] == 0 and checks["loudness_ok"]
        and checks["first_frame_visible"] and checks["publish_audio_rate_ok"]
        and checks["motion_density_ok"] and checks["targeted_markers_ok"]
        and checks["automatic_occlusion_ok"] and checks["unexpected_long_freezes"] == 0
    ) else "review"
    report = {
        "video": str(video.resolve()),
        "format": metadata["format"],
        "video_stream": video_stream,
        "audio_stream": audio_stream,
        "checks": checks
    }
    qa_dir = project_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    first_frame_samples = []
    for frame_number in range(4):
        sample = qa_dir / f"first-frame-{frame_number:02d}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
            "-vf", f"select=eq(n\\,{frame_number}),scale=360:-1",
            "-frames:v", "1", "-update", "1", str(sample),
        ], check=True)
        first_frame_samples.append(str(sample.resolve()))
    checks["first_frame_samples"] = first_frame_samples
    report_path = qa_dir / "qa-report.json"
    write_json(report_path, report)
    duration = float(metadata["format"]["duration"])
    frames = []
    for i, t in enumerate([duration * (x + 0.5) / 10 for x in range(10)]):
        frame = qa_dir / f"frame-{i+1:02d}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i",
                        str(video), "-frames:v", "1", "-vf", "scale=360:-1", str(frame)],
                       check=True)
        frames.append(frame)
    try:
        from PIL import Image, ImageOps, ImageDraw
        images = [Image.open(p).convert("RGB") for p in frames]
        cell_w, cell_h = images[0].size
        sheet = Image.new("RGB", (cell_w * 5, cell_h * 2), "#eee3cc")
        draw = ImageDraw.Draw(sheet)
        for i, image in enumerate(images):
            x, y = (i % 5) * cell_w, (i // 5) * cell_h
            sheet.paste(ImageOps.fit(image, (cell_w, cell_h)), (x, y))
            draw.rectangle((x, y, x + 54, y + 24), fill="#18211d")
            draw.text((x + 6, y + 4), f"{i+1:02d}", fill="white")
        sheet.save(qa_dir / "contact-sheet.jpg", quality=88)
    except Exception:
        pass
    return report_path


def cmd_init(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    if project_dir.exists() and any(project_dir.iterdir()):
        raise RuntimeError("目标目录不是空目录")
    (project_dir / "assets" / "keyframes").mkdir(parents=True, exist_ok=True)
    (project_dir / "assets" / "audio").mkdir(parents=True, exist_ok=True)
    template = {
        "project_name": "请填写项目名称",
        "organization": "",
        "source_text": "请粘贴不少于二十字的公益项目介绍、故事或进展。",
        "duration": 30,
        "aspect": "9:16",
        "tone": "温暖松弛",
        "call_to_action": "关注项目的持续进展",
        "rendering": {"engine": "hyperframes", "fallback": "remotion", "motion_profile": "silky"},
        "source_media": [],
        "models": {"writer": "qwen-plus", "image": "auto", "tts": "auto"},
        "fallback_models": {"image": "qwen-image-2.0", "tts": "cosyvoice-v3.5-plus"},
        "providers": {
            "strategy": "best-available", "image": "auto", "tts": "auto",
            "fallback": "bailian"
        },
        "assets": {
            "keyframes": [
                {
                    "path": "assets/keyframes/01.png",
                    "cues": ["请填写这张画面对应的旁白关键词"],
                    "move": "push_in",
                    "components": ["headline_strip", "timeline"]
                }
            ],
            "narration": "assets/audio/narration.wav",
            "timestamps": "",
            "music": ""
        },
        "privacy": {"minor_faces_allowed": False, "materials_authorized": False}
    }
    write_json(project_dir / "project.json", template)
    print(f"已创建：{project_dir}")


def cmd_prepare(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    doc = read_json(project_dir / "project.json")
    errors = validate_project(doc, project_dir)
    asset_errors = [e for e in errors if not e.startswith("找不到")]
    if asset_errors:
        raise RuntimeError("\n".join(asset_errors))
    if args.live:
        facts, scripts = live_prepare(doc)
    else:
        facts = offline_facts(doc)
        scripts = offline_scripts(doc, facts)
    write_json(project_dir / "workflow" / "facts.json", facts)
    write_json(project_dir / "workflow" / "scripts.json", scripts)
    for stale in ("approved-script.json", "timeline.json", "preview-approved.json"):
        (project_dir / "workflow" / stale).unlink(missing_ok=True)
    print("事实卡片和三版文案已生成。请检查 workflow/scripts.json 后运行 approve-script。")


def cmd_approve_script(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    scripts = read_json(project_dir / "workflow" / "scripts.json")
    variant = next((v for v in scripts["variants"] if v["id"] == args.variant), None)
    if variant is None:
        raise RuntimeError("找不到该文案版本")
    approved = dict(variant)
    approved["source_hash"] = read_json(project_dir / "workflow" / "facts.json")["source_hash"]
    approved["approved"] = True
    write_json(project_dir / "workflow" / "approved-script.json", approved)
    (project_dir / "workflow" / "preview-approved.json").unlink(missing_ok=True)
    print(f"已确认文案：{variant['name']}")


def cmd_timeline(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    doc = read_json(project_dir / "project.json")
    approved = read_json(project_dir / "workflow" / "approved-script.json")
    audio_rel = doc.get("assets", {}).get("narration")
    duration = ffprobe_duration(project_dir / audio_rel) if audio_rel else float(doc["duration"])
    timestamps_rel = doc.get("assets", {}).get("timestamps")
    timestamp_doc = read_json(project_dir / timestamps_rel) if timestamps_rel else None
    timeline = make_timeline(
        approved["narration"], duration, doc["assets"]["keyframes"], timestamp_doc
    )
    safe_path = project_dir / "workflow" / "visual-safe-zones.json"
    apply_safe_layout(timeline, read_json(safe_path) if safe_path.exists() else None)
    write_json(project_dir / "workflow" / "timeline.json", timeline)
    (project_dir / "workflow" / "preview-approved.json").unlink(missing_ok=True)
    print(f"时间轴已生成：{duration:.2f}秒，{len(timeline['scenes'])}个场景，"
          f"{len(timeline['captions'])}条字幕，模式={timeline['alignment']}")


def cmd_approve_preview(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    preview = project_dir / "preview" / "preview.mp4"
    if not preview.exists():
        raise RuntimeError("请先生成低清预览")
    stamp = {"approved": True, "material_hash": material_hash(project_dir),
             "preview": str(preview.resolve())}
    write_json(project_dir / "workflow" / "preview-approved.json", stamp)
    print("低清预览已确认，可以渲染高清版。")


def cmd_status(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    checks = [
        ("项目输入", project_dir / "project.json"),
        ("事实卡片", project_dir / "workflow" / "facts.json"),
        ("三版文案", project_dir / "workflow" / "scripts.json"),
        ("文案确认", project_dir / "workflow" / "approved-script.json"),
        ("音画时间轴", project_dir / "workflow" / "timeline.json"),
        ("低清预览", project_dir / "preview" / "preview.mp4"),
        ("预览确认", project_dir / "workflow" / "preview-approved.json"),
        ("高清成片", project_dir / "dist" / "final.mp4"),
        ("质检报告", project_dir / "qa" / "qa-report.json"),
        ("任务状态", project_dir / "workflow" / "task-state.json"),
        ("渲染选择", project_dir / "workflow" / "render-selection.json"),
        ("HyperFrames工程", project_dir / "build" / "hyperframes" / "index.html"),
    ]
    if args.json:
        state_path = project_dir / "workflow" / "task-state.json"
        state = read_json(state_path) if state_path.exists() else {"status": "unknown"}
        state["artifacts"] = {
            label: {"path": str(path.relative_to(project_dir)), "exists": path.exists()}
            for label, path in checks
        }
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return
    for label, path in checks:
        print(f"{'✓' if path.exists() else '·'} {label:<10} {path.relative_to(project_dir)}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pg-video", description="公益 Vox 短片生成器")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init"); init.add_argument("project_dir"); init.set_defaults(func=cmd_init)
    prepare = sub.add_parser("prepare"); prepare.add_argument("project_dir")
    mode = prepare.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true"); mode.add_argument("--offline", action="store_true")
    prepare.set_defaults(func=cmd_prepare)
    approve = sub.add_parser("approve-script"); approve.add_argument("project_dir")
    approve.add_argument("--variant", choices=["warm", "documentary", "progress"], required=True)
    approve.set_defaults(func=cmd_approve_script)
    timeline = sub.add_parser("timeline"); timeline.add_argument("project_dir"); timeline.set_defaults(func=cmd_timeline)
    preview = sub.add_parser("preview"); preview.add_argument("project_dir")
    preview.add_argument("--engine", choices=["auto", "hyperframes", "remotion"], default="auto")
    preview.set_defaults(func=lambda a: print(f"低清预览：{render(Path(a.project_dir).resolve(), True, a.engine)}"))
    approve_preview = sub.add_parser("approve-preview"); approve_preview.add_argument("project_dir")
    approve_preview.set_defaults(func=cmd_approve_preview)
    full = sub.add_parser("render"); full.add_argument("project_dir")
    full.add_argument("--engine", choices=["auto", "hyperframes", "remotion"], default="auto")
    full.set_defaults(func=lambda a: print(f"高清成片：{render(Path(a.project_dir).resolve(), False, a.engine)}"))
    quality = sub.add_parser("qa"); quality.add_argument("project_dir"); quality.add_argument("--video")
    quality.set_defaults(func=lambda a: print(f"质检报告：{qa(Path(a.project_dir).resolve(), Path(a.video).resolve() if a.video else None)}"))
    status = sub.add_parser("status"); status.add_argument("project_dir")
    status.add_argument("--json", action="store_true"); status.set_defaults(func=cmd_status)
    return p


def main() -> int:
    args = parser().parse_args()
    stage_map = {
        "prepare": "script", "approve-script": "script-approval", "timeline": "timeline",
        "preview": "preview", "approve-preview": "preview-approval", "render": "render",
        "qa": "qa",
    }
    project_dir = None
    if hasattr(args, "project_dir"):
        project_dir = Path(args.project_dir).resolve()
    stage = stage_map.get(args.command)
    try:
        if project_dir and stage:
            update_task_state(project_dir, stage, "running")
        args.func(args)
        if project_dir and stage:
            details = None
            selection = project_dir / "workflow" / "render-selection.json"
            if args.command in {"preview", "render"} and selection.exists():
                details = read_json(selection)
            update_task_state(project_dir, stage, "completed", details=details)
        return 0
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        if project_dir and stage:
            update_task_state(project_dir, stage, "failed", error=str(exc)[:1000])
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
