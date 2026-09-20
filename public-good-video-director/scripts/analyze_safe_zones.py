#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


CANVAS_W, CANVAS_H = 1080, 1920


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def keyframe_path(item: Any) -> str:
    return item['path'] if isinstance(item, dict) else str(item)


def scale_box(box: tuple[float, float, float, float], sx: float, sy: float) -> dict[str, int]:
    x, y, w, h = box
    return {
        'x': round(x * sx), 'y': round(y * sy),
        'width': round(w * sx), 'height': round(h * sy),
    }


def overlap_ratio(a: dict[str, int], b: dict[str, int]) -> float:
    x1, y1 = max(a['x'], b['x']), max(a['y'], b['y'])
    x2 = min(a['x'] + a['width'], b['x'] + b['width'])
    y2 = min(a['y'] + a['height'], b['y'] + b['height'])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    area = (x2 - x1) * (y2 - y1)
    return area / max(1, a['width'] * a['height'])


def ocr_boxes(path: Path, sx: float, sy: float) -> list[dict[str, int]]:
    if not shutil.which('tesseract'):
        return []
    try:
        result = subprocess.run(
            ['tesseract', str(path), 'stdout', '-l', 'chi_sim+eng', 'tsv'],
            check=True, capture_output=True, text=True, timeout=90,
        )
    except Exception:
        return []
    boxes: list[dict[str, int]] = []
    lines = result.stdout.splitlines()
    if not lines:
        return boxes
    header = lines[0].split('\t')
    columns = {name: index for index, name in enumerate(header)}
    for line in lines[1:]:
        row = line.split('\t')
        try:
            confidence = float(row[columns['conf']])
            text = row[columns['text']].strip()
            if confidence < 45 or not text:
                continue
            box = (
                float(row[columns['left']]), float(row[columns['top']]),
                float(row[columns['width']]), float(row[columns['height']]),
            )
            boxes.append(scale_box(box, sx, sy))
        except (KeyError, ValueError, IndexError):
            continue
    return boxes


def face_boxes(image: Image.Image, sx: float, sy: float) -> list[dict[str, int]]:
    try:
        import cv2  # type: ignore
    except Exception:
        return []
    cascade_path = Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'
    cascade = cv2.CascadeClassifier(str(cascade_path))
    gray = np.asarray(image.convert('L'))
    found = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(34, 34))
    return [scale_box(tuple(map(float, box)), sx, sy) for box in found]


def saliency_map(image: Image.Image) -> np.ndarray:
    preview = ImageOps.fit(image.convert('RGB'), (270, 480), method=Image.Resampling.LANCZOS)
    gray = np.asarray(preview.convert('L'), dtype=np.float32) / 255.0
    edges = np.asarray(preview.convert('L').filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255.0
    color = np.asarray(preview, dtype=np.float32) / 255.0
    saturation = color.max(axis=2) - color.min(axis=2)
    local = np.abs(gray - np.asarray(preview.convert('L').filter(ImageFilter.GaussianBlur(9)), dtype=np.float32) / 255.0)
    score = edges * 0.5 + saturation * 0.25 + local * 0.25
    low, high = np.percentile(score, [5, 95])
    return np.clip((score - low) / max(1e-6, high - low), 0, 1)


def subject_box(score: np.ndarray) -> dict[str, int]:
    threshold = np.percentile(score, 82)
    ys, xs = np.where(score >= threshold)
    if not len(xs):
        return {'x': 180, 'y': 360, 'width': 720, 'height': 960}
    x1, x2 = np.percentile(xs, [8, 92])
    y1, y2 = np.percentile(ys, [8, 92])
    scale_x, scale_y = CANVAS_W / score.shape[1], CANVAS_H / score.shape[0]
    pad_x, pad_y = 36, 54
    return {
        'x': max(0, round(x1 * scale_x) - pad_x),
        'y': max(0, round(y1 * scale_y) - pad_y),
        'width': min(CANVAS_W, round((x2 - x1) * scale_x) + pad_x * 2),
        'height': min(CANVAS_H, round((y2 - y1) * scale_y) + pad_y * 2),
    }


def salient_regions(score: np.ndarray) -> list[dict[str, int]]:
    threshold = float(np.percentile(score, 88))
    binary = Image.fromarray(np.uint8(score >= threshold) * 255, mode='L').filter(ImageFilter.MaxFilter(9))
    active = np.asarray(binary) > 0
    height, width = active.shape
    seen = np.zeros_like(active, dtype=bool)
    regions: list[tuple[int, int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if not active[y, x] or seen[y, x]:
                continue
            queue = deque([(x, y)])
            seen[y, x] = True
            x1 = x2 = x; y1 = y2 = y; count = 0
            while queue:
                cx, cy = queue.popleft(); count += 1
                x1, x2 = min(x1, cx), max(x2, cx); y1, y2 = min(y1, cy), max(y2, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < width and 0 <= ny < height and active[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; queue.append((nx, ny))
            box_area = (x2 - x1 + 1) * (y2 - y1 + 1)
            if count >= width * height * .0025 and box_area < width * height * .72:
                regions.append((count, x1, y1, x2, y2))
    sx, sy = CANVAS_W / width, CANVAS_H / height
    result = []
    for _, x1, y1, x2, y2 in sorted(regions, reverse=True)[:8]:
        pad_x, pad_y = 20, 28
        result.append({
            'x': max(0, round(x1 * sx) - pad_x), 'y': max(0, round(y1 * sy) - pad_y),
            'width': min(CANVAS_W, round((x2 - x1 + 1) * sx) + pad_x * 2),
            'height': min(CANVAS_H, round((y2 - y1 + 1) * sy) + pad_y * 2),
        })
    return result


def candidate_boxes() -> list[dict[str, int]]:
    return [
        {'x': 500, 'y': 120, 'width': 516, 'height': 190},
        {'x': 64, 'y': 120, 'width': 430, 'height': 190},
        {'x': 64, 'y': 260, 'width': 952, 'height': 250},
        {'x': 64, 'y': 540, 'width': 952, 'height': 300},
        {'x': 64, 'y': 875, 'width': 952, 'height': 310},
        {'x': 64, 'y': 1210, 'width': 952, 'height': 260},
        {'x': 64, 'y': 1490, 'width': 952, 'height': 210},
        {'x': 64, 'y': 650, 'width': 460, 'height': 360},
        {'x': 556, 'y': 650, 'width': 460, 'height': 360},
        {'x': 64, 'y': 1050, 'width': 460, 'height': 360},
        {'x': 556, 'y': 1050, 'width': 460, 'height': 360},
    ]


def mean_saliency(score: np.ndarray, box: dict[str, int]) -> float:
    sx, sy = score.shape[1] / CANVAS_W, score.shape[0] / CANVAS_H
    x1, y1 = round(box['x'] * sx), round(box['y'] * sy)
    x2 = round((box['x'] + box['width']) * sx)
    y2 = round((box['y'] + box['height']) * sy)
    region = score[max(0, y1):max(y1 + 1, y2), max(0, x1):max(x1 + 1, x2)]
    return float(region.mean()) if region.size else 1.0


def analyze(path: Path) -> tuple[dict[str, Any], Image.Image]:
    image = Image.open(path).convert('RGB')
    score = saliency_map(image)
    sx, sy = CANVAS_W / image.width, CANVAS_H / image.height
    faces = face_boxes(image, sx, sy)
    text = ocr_boxes(path, sx, sy)
    subject = subject_box(score)
    regions = salient_regions(score)
    protected = [
        {'kind': 'face', **box} for box in faces
    ] + [
        {'kind': 'source_text', **box} for box in text
    ] + [{'kind': 'salient_region', **box} for box in regions]
    if not regions:
        protected.append({'kind': 'salient_subject', **subject})

    ranked: list[dict[str, Any]] = []
    for box in candidate_boxes():
        saliency = mean_saliency(score, box)
        overlap = max([overlap_ratio(box, item) for item in protected] or [0.0])
        subtitle_penalty = 0.45 if box['y'] + box['height'] > 1710 else 0.0
        score_value = saliency + overlap * 1.8 + subtitle_penalty
        ranked.append({**box, 'score': round(score_value, 4)})
    ranked.sort(key=lambda item: item['score'])

    clean = [item for item in ranked if max([overlap_ratio(item, region) for region in protected] or [0.0]) < .12]
    pool = clean or ranked
    safety = 'negative_space' if clean else 'least_risk_fallback'
    accepted: list[dict[str, Any]] = []
    for item in pool:
        if all(overlap_ratio(item, other) < 0.35 for other in accepted):
            accepted.append({**item, 'safety': safety})
        if len(accepted) >= 4:
            break

    debug = ImageOps.fit(image, (CANVAS_W, CANVAS_H), method=Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(debug, 'RGBA')
    for item in protected:
        draw.rectangle(
            (item['x'], item['y'], item['x'] + item['width'], item['y'] + item['height']),
            outline=(220, 68, 54, 230), width=7,
        )
    for index, item in enumerate(accepted, 1):
        draw.rectangle(
            (item['x'], item['y'], item['x'] + item['width'], item['y'] + item['height']),
            outline=(51, 140, 88, 230), width=7,
        )
        draw.text((item['x'] + 10, item['y'] + 8), f'SAFE {index}', fill=(51, 140, 88, 255))
    return {
        'image': str(path), 'subject_box': subject, 'protected_boxes': protected,
        'safe_boxes': accepted, 'provider': 'local-saliency-v1',
        'optional_detectors': {'opencv_faces': bool(faces), 'tesseract_ocr': bool(text)},
    }, debug


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect protected subjects and rank overlay-safe zones.')
    parser.add_argument('project')
    args = parser.parse_args()
    project_dir = Path(args.project).expanduser().resolve()
    project = read_json(project_dir / 'project.json')
    output_dir = project_dir / 'qa' / 'safe-zones'
    output_dir.mkdir(parents=True, exist_ok=True)
    scenes = []
    for index, item in enumerate(project['assets']['keyframes'], 1):
        path = project_dir / keyframe_path(item)
        result, debug = analyze(path)
        result['scene_id'] = index
        scenes.append(result)
        debug.save(output_dir / f'{index:02d}.jpg', quality=88)
    document = {'canvas': {'width': CANVAS_W, 'height': CANVAS_H}, 'scenes': scenes}
    output = project_dir / 'workflow' / 'visual-safe-zones.json'
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
