#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import wave
from array import array
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def trim_edge_silence(frames: bytes, sample_rate: int) -> bytes:
    samples = array("h")
    samples.frombytes(frames)
    window = max(1, int(sample_rate * .01))
    active = []
    for start in range(0, len(samples), window):
        block = samples[start:start + window]
        if block and (sum(value * value for value in block) / len(block)) ** .5 >= 110:
            active.append(start)
    if not active:
        return frames
    pad = int(sample_rate * .10)
    return samples[max(0, active[0] - pad):min(len(samples), active[-1] + window + pad)].tobytes()


def combine(paths: list[Path], output: Path, pause: float = .16) -> list[tuple[float, float]]:
    ranges = []
    cursor = 0.0
    with wave.open(str(paths[0]), "rb") as first:
        channels, width, rate = first.getnchannels(), first.getsampwidth(), first.getframerate()
    silence = b"\0" * int(rate * pause) * width * channels
    with wave.open(str(output), "wb") as target:
        target.setnchannels(channels); target.setsampwidth(width); target.setframerate(rate)
        for index, path in enumerate(paths):
            with wave.open(str(path), "rb") as source:
                frames = trim_edge_silence(source.readframes(source.getnframes()), rate)
            duration = len(frames) / (rate * width * channels)
            start = cursor
            target.writeframes(frames)
            cursor += duration
            ranges.append((start, cursor))
            if index < len(paths) - 1:
                target.writeframes(silence); cursor += pause
    return ranges


def find_segment(source_dir: Path, index: int) -> Path:
    stem = f"segment-{index:02d}"
    for extension in AUDIO_EXTENSIONS:
        path = source_dir / f"{stem}{extension}"
        if path.exists():
            return path
    matches = sorted(source_dir.glob(f"{stem}.*"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Missing {stem} audio in {source_dir}")


def convert(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
        "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(target),
    ], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assemble beat-level audio from an agent-native or external TTS provider."
    )
    parser.add_argument("project")
    parser.add_argument("segments_dir")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", default="provider-default")
    parser.add_argument("--pause", type=float, default=0.16)
    args = parser.parse_args()

    project_dir = Path(args.project).expanduser().resolve()
    source_dir = Path(args.segments_dir).expanduser().resolve()
    project = read_json(project_dir / "project.json")
    storyboard = read_json(project_dir / "workflow" / "storyboard.json")
    audio_dir = project_dir / "assets" / "audio"
    normalized_dir = audio_dir / "provider-segments"
    paths: list[Path] = []
    for beat in storyboard["beats"]:
        index = int(beat["id"])
        source = find_segment(source_dir, index)
        target = normalized_dir / f"segment-{index:02d}.wav"
        convert(source, target)
        paths.append(target)

    natural = audio_dir / "narration-natural.wav"
    ranges = combine(paths, natural, pause=args.pause)
    natural_duration = ranges[-1][1]
    desired = float(project.get("duration", 30)) * 1.07
    tempo = min(1.18, max(1.0, natural_duration / desired))
    narration = audio_dir / "narration.wav"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(natural),
        "-af", f"atempo={tempo:.6f}", str(narration),
    ], check=True)
    ranges = [(start / tempo, end / tempo) for start, end in ranges]

    captions: list[dict[str, Any]] = []
    scenes: list[dict[str, Any]] = []
    for beat, (start, end) in zip(storyboard["beats"], ranges):
        scenes.append({
            "id": beat["id"], "from": round(start, 3), "to": round(end, 3),
            "text": beat["narration"],
        })
        texts = beat.get("captions") or [beat["narration"]]
        weights = [max(2, len(re.sub(r"\s", "", text))) for text in texts]
        total = sum(weights)
        cursor = start
        for caption_index, (text, weight) in enumerate(zip(texts, weights)):
            caption_end = end if caption_index == len(texts) - 1 else cursor + (end - start) * weight / total
            captions.append({"from": round(cursor, 3), "to": round(caption_end, 3), "text": text})
            cursor = caption_end
    write_json(audio_dir / "timestamps.json", {
        "alignment_method": "provider_segments_weighted_captions",
        "confidence": "beat_exact_caption_estimated",
        "captions": captions,
        "scenes": scenes,
    })

    ambient = SKILL_ROOT / "assets" / "runtime" / "assets" / "audio" / "ambient.m4a"
    if ambient.exists():
        shutil.copy2(ambient, audio_dir / "ambient.m4a")
    project["assets"]["narration"] = "assets/audio/narration.wav"
    project["assets"]["timestamps"] = "assets/audio/timestamps.json"
    project["assets"]["music"] = "assets/audio/ambient.m4a"
    project.setdefault("providers", {})["tts"] = args.provider
    project.setdefault("models", {})["tts"] = args.model
    write_json(project_dir / "project.json", project)

    selection_path = project_dir / "workflow" / "provider-selection.json"
    if selection_path.exists():
        selection = read_json(selection_path)
        selection.setdefault("tts", {})["assembled_from_segments"] = True
        selection["tts"]["provider"] = args.provider
        selection["tts"]["model"] = args.model
        write_json(selection_path, selection)
    print(json.dumps({
        "narration": str(narration), "provider": args.provider, "model": args.model,
        "segments": len(paths), "duration": round(ranges[-1][1], 3),
        "tempo": round(tempo, 3),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
