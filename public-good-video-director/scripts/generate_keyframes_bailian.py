#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def generate(prompt: str, model: str, seed: int) -> bytes:
    base = os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com").rstrip("/")
    endpoint = f"{base}/api/v1/services/aigc/multimodal-generation/generation"
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {
            "negative_prompt": (
                "3D, CGI, glossy render, photorealistic faces, identifiable child face, "
                "warped limbs, malformed fingers, embedded words, letters, numbers, logos, watermark"
            ),
            "prompt_extend": False,
            "watermark": False,
            "size": "1536*2688",
            "n": 1,
            "seed": seed,
        },
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result["output"]["choices"][0]["message"]["content"]
    image_url = next(item["image"] for item in content if item.get("image"))
    with urllib.request.urlopen(image_url, timeout=180) as image_response:
        return image_response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Vox keyframes with one Bailian API key.")
    parser.add_argument("studio")
    parser.add_argument("project")
    parser.add_argument("--model")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    studio = Path(args.studio).expanduser().resolve()
    project_dir = Path(args.project).expanduser().resolve()
    load_env(studio / ".env")
    load_env(project_dir / ".env")
    project = read_json(project_dir / "project.json")
    storyboard = read_json(project_dir / "workflow" / "storyboard.json")
    model = args.model or project.get("fallback_models", {}).get("image", "qwen-image-2.0")
    if not args.dry_run and not os.getenv("DASHSCOPE_API_KEY"):
        raise SystemExit("DASHSCOPE_API_KEY is not set")
    out_dir = project_dir / "assets" / "keyframes"
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_log = []
    for beat in storyboard["beats"]:
        path = out_dir / f"{int(beat['id']):02d}.png"
        prompt_log.append({"id": beat["id"], "path": str(path), "prompt": beat["image_prompt"]})
        if args.dry_run or (path.exists() and not args.force):
            continue
        path.write_bytes(generate(beat["image_prompt"], model, 20260807 + int(beat["id"])))
        print(path)
        time.sleep(0.5)
    (project_dir / "workflow" / "image-prompts.json").write_text(
        json.dumps(prompt_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(project_dir / "workflow" / "image-prompts.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
