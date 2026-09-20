#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from analyze_safe_zones import saliency_map


CANVAS = (1080, 1920)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def keyframe_path(item: Any) -> str:
    return item["path"] if isinstance(item, dict) else str(item)


def local_mask(image: Image.Image) -> Image.Image:
    score = saliency_map(image)
    height, width = score.shape
    yy, xx = np.mgrid[0:height, 0:width]
    center_weight = np.exp(-(((xx - width * .5) / (width * .58)) ** 2 + ((yy - height * .53) / (height * .67)) ** 2))
    combined = score * (.72 + .28 * center_weight)
    threshold = float(np.percentile(combined, 72))
    raw = np.clip((combined - threshold) / max(.08, 1 - threshold), 0, 1)
    raw = np.power(raw, .72)
    mask = Image.fromarray(np.uint8(raw * 255), mode="L").resize(CANVAS, Image.Resampling.BICUBIC)
    mask = mask.filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(34))
    return mask.point(lambda value: 0 if value < 22 else min(255, round(value * 1.32)))


def rembg_mask(image: Image.Image) -> Image.Image | None:
    try:
        from rembg import remove  # type: ignore
    except Exception:
        return None
    try:
        result = remove(image.convert("RGBA"))
        if isinstance(result, Image.Image):
            return result.getchannel("A").resize(CANVAS, Image.Resampling.LANCZOS)
    except Exception:
        return None
    return None


def split_layers(path: Path, output_dir: Path, prefer_rembg: bool) -> tuple[dict[str, str], str]:
    source = ImageOps.fit(Image.open(path).convert("RGB"), CANVAS, method=Image.Resampling.LANCZOS)
    mask = rembg_mask(source) if prefer_rembg else None
    provider = "rembg" if mask is not None else "local-saliency-matte-v1"
    if mask is None:
        mask = local_mask(source)

    mask_array = np.asarray(mask, dtype=np.float32) / 255.0
    y = np.linspace(0, 1, CANVAS[1], dtype=np.float32)[:, None]
    foreground_gate = np.clip((y - .68) / .22, 0, 1)
    foreground_alpha = np.uint8(mask_array * foreground_gate * 255)
    subject_alpha = np.uint8(mask_array * (1 - foreground_gate * .75) * 255)

    subject = source.convert("RGBA")
    subject.putalpha(Image.fromarray(subject_alpha, mode="L"))
    foreground = source.convert("RGBA")
    foreground.putalpha(Image.fromarray(foreground_alpha, mode="L"))

    blurred = source.filter(ImageFilter.GaussianBlur(22))
    background = Image.composite(blurred, source, mask)
    background = Image.blend(background, source, .28)

    output_dir.mkdir(parents=True, exist_ok=True)
    background_path = output_dir / "background.webp"
    subject_path = output_dir / "subject.png"
    foreground_path = output_dir / "foreground.png"
    mask_path = output_dir / "mask.png"
    background.save(background_path, "WEBP", quality=92, method=6)
    subject.save(subject_path, "PNG", optimize=True)
    foreground.save(foreground_path, "PNG", optimize=True)
    mask.save(mask_path, "PNG", optimize=True)
    return {
        "background": str(background_path),
        "subject": str(subject_path),
        "foreground": str(foreground_path),
        "mask": str(mask_path),
    }, provider


def main() -> int:
    parser = argparse.ArgumentParser(description="Build true background/subject/foreground layers locally.")
    parser.add_argument("project")
    parser.add_argument("--prefer-rembg", action="store_true", help="Use rembg when installed; otherwise use local saliency matte.")
    args = parser.parse_args()
    project_dir = Path(args.project).expanduser().resolve()
    project_path = project_dir / "project.json"
    project = read_json(project_path)
    keyframes = project["assets"]["keyframes"]
    updated = []
    manifest = {"canvas": {"width": CANVAS[0], "height": CANVAS[1]}, "scenes": []}
    for index, raw in enumerate(keyframes, 1):
        item = dict(raw) if isinstance(raw, dict) else {"path": str(raw), "cues": []}
        result, provider = split_layers(
            project_dir / keyframe_path(raw), project_dir / "assets" / "layers" / f"{index:02d}", args.prefer_rembg,
        )
        relative = {name: str(Path(path).relative_to(project_dir)) for name, path in result.items()}
        item["layers"] = {key: value for key, value in relative.items() if key != "mask"}
        item["layer_provider"] = provider
        item.setdefault("depth", "layered")
        updated.append(item)
        manifest["scenes"].append({"scene_id": index, "provider": provider, **relative})
    project["assets"]["keyframes"] = updated
    write_json(project_path, project)
    output = project_dir / "workflow" / "layer-manifest.json"
    write_json(output, manifest)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
