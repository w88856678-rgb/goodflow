#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from semantic_beats import split_semantic_beats


MOVES = ["pull_out", "pan", "push_in", "rise", "parallax", "push_in", "pull_out", "static"]
TRANSITIONS = ["paper_wipe", "map_push", "paper_roll", "ink_reveal"]
COMPONENTS = [
    ["timeline"],
    ["steam"],
    [],
    [],
    ["steam"],
    [],
    [],
    [],
]
STYLE = (
    "Mixed-media hand-cut PAPER COLLAGE, warm Chinese editorial newsprint style; "
    "torn and scissor-cut paper edges, clean paper-mounted frames, halftone dots, newspaper scraps, "
    "risograph ink texture, real paper drop shadows, flat 2D printed illustrated cut-outs, "
    "aged cream + mustard + brick red + forest green + charcoal palette, tactile print grain. "
    "Vertical 9:16, strong layered depth, readable at phone size, safe space for local captions. "
    "No masking tape, stickers, floating color blocks, circles, arrows, or pins over image content. "
    "No embedded text, letters, numbers, logos or watermark. No identifiable minor faces; "
    "show children from behind or use hands and symbolic details. NOT 3D, NOT CGI."
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def split_narration(text: str, duration: float = 30.0) -> list[str]:
    return split_semantic_beats(text, duration)


def caption_chunks(text: str, limit: int = 42) -> list[str]:
    """Keep captions as complete sentences or semantic clauses.

    Never slice copy at a fixed character index. Long cards are handled by
    responsive renderer typography; only exceptionally long clauses may break
    at a visible comma or colon.
    """
    chunks = [item.strip() for item in re.findall(r".*?(?:[。！？；]|$)", text, re.S) if item.strip()]
    result: list[str] = []
    for chunk in chunks:
        pending = chunk
        while len(re.sub(r"\s", "", pending)) > limit * 2:
            candidates = [match.end() for match in re.finditer(r"[，：]", pending[: limit + 8])]
            if not candidates:
                break
            cut = candidates[-1]
            result.append(pending[:cut].strip())
            pending = pending[cut:].strip()
        if pending:
            result.append(pending)
    return result or [text]


def fact_items(text: str, limit: int = 4) -> list[str]:
    cleaned = text.strip().strip("，。！？；：,.!?;:")
    pieces = [
        item.strip()
        for item in re.split(r"[、，；：,.!?;:]+", cleaned)
        if item.strip()
    ]
    if len(pieces) < 2:
        pieces = caption_chunks(cleaned, limit=9)
    result: list[str] = []
    for piece in pieces:
        value = piece[:12]
        if value and value not in result:
            result.append(value)
        if len(result) >= limit:
            break
    return result or [cleaned[:12]]


def qwen_visuals(project: dict[str, Any], facts: dict[str, Any], beats: list[str]) -> list[dict[str, Any]]:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY is not set")
    endpoint = os.getenv(
        "DASHSCOPE_CHAT_ENDPOINT",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    )
    fixed = [{"id": i + 1, "narration": text} for i, text in enumerate(beats)]
    payload = {
        "model": project.get("models", {}).get("writer", "qwen-plus"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是中文公益短片分镜导演。只使用事实卡片已有信息，不补写事实。"
                    "为每个固定旁白片段设计一个能够直接看懂的画面和三个连续发生的镜头内动作；"
                    "相邻画面必须推进故事，不得重复同一构图。未成年人不得露出可识别正脸。"
                    "所有中文文字都由后期排版，不写入图片。只输出 JSON。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "输出 {\"visuals\":[...]}。每项必须包含 id、scene、headline、"
                    "event_types、voice_direction。"
                    "id 必须与固定片段一致；scene 用中文描述主体、动作、环境、镜别和构图，"
                    "不要在画面中生成文字。headline 是不超过九个字的后期标题。"
                    "event_types 从 paper_label、fact_stack、cause_flow、number_card、"
                    "underline、steam_rise、quote_reveal 中选择三个，按出现顺序排列。"
                    "平行的产品、手艺或参与者用 fact_stack；明确的三段因果关系用 cause_flow；"
                    "没有明确目标坐标时不得使用圆圈、箭头、定位针或装饰胶带。"
                    "voice_direction 用一句话描述自然口语的情绪。"
                    f"\n项目：{project['project_name']}\n语气：{project.get('tone', '温暖松弛')}"
                    f"\n事实：{json.dumps(facts, ensure_ascii=False)}"
                    f"\n固定片段：{json.dumps(fixed, ensure_ascii=False)}"
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.35,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    visuals = json.loads(content)["visuals"]
    by_id = {int(item["id"]): item for item in visuals}
    if any(index not in by_id for index in range(1, len(beats) + 1)):
        raise RuntimeError("Qwen storyboard response omitted beat IDs")
    return [by_id[index] for index in range(1, len(beats) + 1)]


def event_plan(
    index: int,
    text: str,
    cue: str,
    visual: dict[str, Any],
    facts: dict[str, Any],
    is_last: bool,
) -> list[dict[str, Any]]:
    if is_last:
        return [
            {"type": "paper_label", "at": 0.08, "duration": 0.34, "text": cue, "sfx": "paper"},
            {"type": "underline", "at": 0.38, "duration": 0.32, "text": cue, "sfx": "whoosh"},
            {"type": "cta_reveal", "at": 0.68, "duration": 0.28, "sfx": "chime"},
        ]
    spoken_number = re.search(
        r"(?:\d{1,4}(?:到|至|[-–—])\d{1,4}(?:小时|分钟|天|人|名|份|元)?|"
        r"\d{1,4}(?::\d{2})?(?:小时|分钟|天|人|名|份|元)?|"
        r"[一二三四五六七八九十零〇两]{1,8}点"
        r"[一二三四五六七八九十零〇两]{0,8}分?|"
        r"[一二三四五六七八九十零〇两]{4}年)",
        text,
    )
    number = spoken_number.group(0) if spoken_number else ""
    requested = [
        value for value in visual.get("event_types", [])
        if value in {
            "paper_label", "fact_stack", "cause_flow", "number_card",
            "underline", "steam_rise", "quote_reveal",
        }
    ]
    default_types = ["paper_label", "number_card" if number else "fact_stack", "underline"]
    types = requested[:3] if len(requested) >= 3 else default_types
    if "paper_label" not in types:
        types[0] = "paper_label"
    items = fact_items(text)
    events = []
    for position, event_type in enumerate(types):
        if event_type == "number_card" and not number:
            event_type = "fact_stack"
        if event_type == "cause_flow" and len(items) < 3:
            event_type = "fact_stack"
        event: dict[str, Any] = {
            "type": event_type,
            "at": [0.08, 0.36, 0.67][position],
            "duration": [0.28, 0.34, 0.27][position],
            "sfx": ["paper", "whoosh", "tap"][position],
        }
        if event_type in {"paper_label", "underline", "quote_reveal"}:
            event["text"] = cue if event_type != "quote_reveal" else text.strip("。！？")
        if event_type == "number_card":
            event["value"] = number
        if event_type == "fact_stack":
            event["items"] = items
        if event_type == "cause_flow":
            event["items"] = items[:3]
        events.append(event)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fact-grounded, audio-first Vox storyboard.")
    parser.add_argument("studio")
    parser.add_argument("project")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    studio = Path(args.studio).expanduser().resolve()
    project_dir = Path(args.project).expanduser().resolve()
    load_env(studio / ".env")
    load_env(project_dir / ".env")
    project = read_json(project_dir / "project.json")
    approved = read_json(project_dir / "workflow" / "approved-script.json")
    facts = read_json(project_dir / "workflow" / "facts.json")
    narration_beats = split_narration(
        approved["narration"], float(project.get("duration", 30))
    )
    write_json(project_dir / "workflow" / "semantic-beats.json", {
        "duration": float(project.get("duration", 30)),
        "beats": [
            {"id": index + 1, "narration": beat}
            for index, beat in enumerate(narration_beats)
        ],
    })
    if args.offline:
        visuals = [
            {
                "id": i + 1,
                "scene": f"用一个具体动作表现这句旁白：{text}",
                "headline": caption_chunks(text)[0][:9],
                "event_types": [],
                "voice_direction": "自然、温暖、克制地讲述。",
            }
            for i, text in enumerate(narration_beats)
        ]
    else:
        visuals = qwen_visuals(project, facts, narration_beats)

    beats = []
    keyframes = []
    for index, (text, visual) in enumerate(zip(narration_beats, visuals), 1):
        cue = caption_chunks(text)[0]
        components = COMPONENTS[min(index - 1, len(COMPONENTS) - 1)]
        if index == len(narration_beats):
            components = []
        events = event_plan(
            index, text, cue, visual, facts, index == len(narration_beats)
        )
        beats.append({
            "id": index,
            "narration": text,
            "captions": caption_chunks(text),
            "scene": visual["scene"],
            "voice_direction": visual.get("voice_direction", "自然、温暖、克制地讲述。"),
            "image_prompt": f"{STYLE} Scene: {visual['scene']}",
            "move": MOVES[min(index - 1, len(MOVES) - 1)],
            "transition": TRANSITIONS[(index - 1) % len(TRANSITIONS)],
            "depth": "layered",
            "headline": visual.get("headline", cue[:9]),
            "components": components,
            "motion_events": events,
            "cue": cue,
        })
        keyframes.append({
            "path": f"assets/keyframes/{index:02d}.png",
            "cues": [cue],
            "move": beats[-1]["move"],
            "transition": beats[-1]["transition"],
            "depth": beats[-1]["depth"],
            "headline": beats[-1]["headline"],
            "components": components,
            "motion_events": events,
        })
    storyboard = {
        "project": project["project_name"],
        "aspect": "9:16",
        "theme": "warm-chinese-newsprint",
        "beats": beats,
    }
    write_json(project_dir / "workflow" / "storyboard.json", storyboard)
    project["assets"]["keyframes"] = keyframes
    write_json(project_dir / "project.json", project)
    print(project_dir / "workflow" / "storyboard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
