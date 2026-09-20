#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from semantic_beats import split_semantic_beats


EDGE_DEFAULT = "zh-CN-XiaoxiaoNeural"
KOKORO_DEFAULT = "zf_xiaobei"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def availability() -> dict[str, Any]:
    return {
        "edge": {"available": importlib.util.find_spec("edge_tts") is not None, "cost": "free", "network": True},
        "kokoro": {
            "available": importlib.util.find_spec("kokoro") is not None and importlib.util.find_spec("soundfile") is not None,
            "cost": "free", "network_after_model_download": False,
        },
    }


def beats_for(project_dir: Path) -> list[dict[str, Any]]:
    storyboard = project_dir / "workflow" / "storyboard.json"
    if storyboard.exists():
        return read_json(storyboard)["beats"]
    approved = read_json(project_dir / "workflow" / "approved-script.json")
    project = read_json(project_dir / "project.json")
    return [
        {"id": index + 1, "narration": value}
        for index, value in enumerate(split_semantic_beats(approved["narration"], float(project.get("duration", 30))))
    ]


def speech_text_for(project_dir: Path, text: str) -> str:
    """Apply project-local pronunciation aliases without changing approved copy."""
    path = project_dir / "workflow" / "tts-pronunciations.json"
    if not path.exists():
        return text
    document = read_json(path)
    replacements = document.get("replacements", {})
    if not isinstance(replacements, dict):
        return text
    spoken = text
    for written, pronunciation in replacements.items():
        if written and isinstance(pronunciation, str):
            spoken = spoken.replace(str(written), pronunciation)
    return spoken


async def edge_generate(text: str, output: Path, voice: str, rate: str, pitch: str) -> list[dict[str, Any]]:
    import edge_tts  # type: ignore
    output.parent.mkdir(parents=True, exist_ok=True)
    boundaries = []
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    with output.open("wb") as stream:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                stream.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = float(chunk["offset"]) / 10_000_000
                duration = float(chunk["duration"]) / 10_000_000
                boundaries.append({"text": chunk["text"], "from": start, "to": start + duration})
    return boundaries


def kokoro_generate(text: str, output: Path, voice: str, speed: float) -> None:
    import numpy as np
    import soundfile as sf  # type: ignore
    from kokoro import KPipeline  # type: ignore
    pipeline = KPipeline(lang_code="z")
    chunks = [np.asarray(audio, dtype=np.float32) for _, _, audio in pipeline(text, voice=voice, speed=speed)]
    if not chunks:
        raise RuntimeError("Kokoro returned no audio")
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output), np.concatenate(chunks), 24000, subtype="PCM_16")


def audition_text(project_dir: Path) -> str:
    text = read_json(project_dir / "workflow" / "approved-script.json")["narration"]
    compact = re.sub(r"\s+", "", text)
    aliases_path = project_dir / "workflow" / "tts-pronunciations.json"
    if aliases_path.exists():
        replacements = read_json(aliases_path).get("replacements", {})
        for written in replacements if isinstance(replacements, dict) else []:
            position = compact.find(str(written))
            if position >= 0:
                start = max([compact.rfind(mark, 0, position) for mark in "。！？；"], default=-1) + 1
                endings = [compact.find(mark, position) for mark in "。！？；"]
                endings = [value for value in endings if value >= 0]
                end = min(endings) + 1 if endings else min(len(compact), start + 90)
                return compact[start:end]
    cut = min(len(compact), 72)
    punctuation = max([compact.rfind(mark, 28, cut) for mark in "。！？；"], default=-1)
    return compact[:punctuation + 1 if punctuation >= 28 else cut]


def assemble(project_dir: Path, segment_dir: Path, provider: str, model: str, pause: float) -> None:
    subprocess.run([
        sys.executable, str(Path(__file__).with_name("assemble_external_tts.py")), str(project_dir), str(segment_dir),
        "--provider", provider, "--model", model, "--pause", str(pause),
    ], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Free local/Edge Chinese TTS with beat-level generation.")
    parser.add_argument("project", nargs="?")
    parser.add_argument("--provider", choices=["edge", "kokoro"])
    parser.add_argument("--voice")
    parser.add_argument("--rate", default="-3%", help="Edge rate, for example minus three percent or plus eight percent.")
    parser.add_argument("--pitch", default="-2Hz", help="Edge pitch such as -2Hz.")
    parser.add_argument("--speed", type=float, default=.96, help="Kokoro speech speed.")
    parser.add_argument("--pause", type=float, default=.16)
    parser.add_argument("--audition", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    status = availability()
    if args.check:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    if not args.project or not args.provider:
        parser.error("project and --provider are required unless --check is used")
    if not status[args.provider]["available"]:
        raise SystemExit(f"{args.provider} is unavailable; install the matching optional requirements file")

    project_dir = Path(args.project).expanduser().resolve()
    voice = args.voice or (EDGE_DEFAULT if args.provider == "edge" else KOKORO_DEFAULT)
    if args.audition:
        texts = [{"id": 1, "narration": audition_text(project_dir)}]
        output_dir = project_dir / "voice-auditions" / args.provider
    else:
        texts = beats_for(project_dir)
        output_dir = project_dir / "assets" / "audio" / f"{args.provider}-segments"

    boundary_segments = []
    for item in texts:
        index = int(item["id"])
        text = speech_text_for(project_dir, item["narration"])
        if args.provider == "edge":
            output = output_dir / f"segment-{index:02d}.mp3"
            words = asyncio.run(edge_generate(text, output, voice, args.rate, args.pitch))
            boundary_segments.append({"id": index, "words": words})
        else:
            output = output_dir / f"segment-{index:02d}.wav"
            kokoro_generate(text, output, voice, args.speed)
    manifest = {
        "provider": args.provider, "voice": voice, "audition": args.audition,
        "segments": len(texts), "output_dir": str(output_dir), "settings": {
            "rate": args.rate, "pitch": args.pitch, "speed": args.speed, "pause": args.pause,
        },
        "pronunciation_aliases": str(project_dir / "workflow" / "tts-pronunciations.json")
        if (project_dir / "workflow" / "tts-pronunciations.json").exists() else None,
    }
    write_json(output_dir / "manifest.json", manifest)
    if not args.audition:
        assemble(project_dir, output_dir, args.provider, voice, args.pause)
        if boundary_segments:
            narration = project_dir / "assets" / "audio" / "narration.wav"
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(narration),
            ], check=True, capture_output=True, text=True)
            final_duration = float(probe.stdout.strip())
            flat = []
            cursor = 0.0
            for segment in boundary_segments:
                words = segment["words"]
                segment_end = max([float(word["to"]) for word in words] or [0.1])
                for word in words:
                    flat.append({"text": word["text"], "from": cursor + float(word["from"]), "to": cursor + float(word["to"])})
                cursor += segment_end + args.pause
            scale = final_duration / max(.1, cursor - args.pause)
            for word in flat:
                word["from"] = round(word["from"] * scale, 3); word["to"] = round(word["to"] * scale, 3)
            write_json(project_dir / "assets" / "audio" / "edge-word-boundaries.json", {
                "provider": "edge", "voice": voice, "words": flat, "duration": round(final_duration, 3),
            })
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
