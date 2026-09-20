#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
import wave
from array import array
from pathlib import Path
from typing import Any

import dashscope
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer


SKILL_ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def voice_request(payload: dict[str, Any]) -> dict[str, Any]:
    base = os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com").rstrip("/")
    req = urllib.request.Request(
        f"{base}/api/v1/services/audio/tts/customization",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def load_profiles() -> dict[str, dict[str, Any]]:
    return read_json(SKILL_ROOT / "assets" / "voice-profiles.json")


def get_or_create_voice(
    audio_dir: Path, profile_name: str, profile: dict[str, Any]
) -> str:
    meta_path = audio_dir / f"voice-design-{profile_name}.json"
    if meta_path.exists():
        voice_id = read_json(meta_path).get("voice_id")
        if voice_id:
            return voice_id
    prefix = profile["prefix"]
    listed = voice_request({
        "model": "voice-enrollment",
        "input": {"action": "list_voice", "prefix": prefix, "page_size": 20, "page_index": 0},
    })
    for voice in listed.get("output", {}).get("voice_list", []):
        if voice.get("status") == "OK" and "cosyvoice-v3.5-plus" in voice.get("voice_id", ""):
            write_json(meta_path, {**voice, "profile": profile_name})
            return voice["voice_id"]
    created = voice_request({
        "model": "voice-enrollment",
        "input": {
            "action": "create_voice",
            "target_model": "cosyvoice-v3.5-plus",
            "voice_prompt": profile["voice_prompt"],
            "preview_text": profile["preview_text"],
            "prefix": prefix,
            "language_hints": ["zh"],
        },
        "parameters": {"sample_rate": 24000, "response_format": "wav"},
    })
    output = created["output"]
    preview = output.get("preview_audio", {}).get("data")
    if preview:
        (audio_dir / f"voice-preview-{profile_name}.wav").write_bytes(base64.b64decode(preview))
    write_json(meta_path, {
        "voice_id": output["voice_id"],
        "target_model": output.get("target_model", "cosyvoice-v3.5-plus"),
        "profile": profile_name,
        "name": profile["name"],
        "description": profile["description"],
        "voice_prompt": profile["voice_prompt"],
    })
    return output["voice_id"]


def trim_edge_silence(frames: bytes, sample_rate: int) -> bytes:
    samples = array("h")
    samples.frombytes(frames)
    window = max(1, int(sample_rate * 0.01))
    active = []
    for start in range(0, len(samples), window):
        block = samples[start:start + window]
        if block and (sum(value * value for value in block) / len(block)) ** 0.5 >= 110:
            active.append(start)
    if not active:
        return frames
    pad = int(sample_rate * 0.10)
    return samples[max(0, active[0] - pad):min(len(samples), active[-1] + window + pad)].tobytes()


def combine(paths: list[Path], output: Path, pause: float = 0.16) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    cursor = 0.0
    with wave.open(str(paths[0]), "rb") as first:
        channels, width, rate = first.getnchannels(), first.getsampwidth(), first.getframerate()
    silence = b"\0" * int(rate * pause) * width * channels
    with wave.open(str(output), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(rate)
        for index, path in enumerate(paths):
            with wave.open(str(path), "rb") as source:
                frames = source.readframes(source.getnframes())
            frames = trim_edge_silence(frames, rate)
            duration = len(frames) / (rate * width * channels)
            start = cursor
            target.writeframes(frames)
            cursor += duration
            ranges.append((start, cursor))
            if index < len(paths) - 1:
                target.writeframes(silence)
                cursor += pause
    return ranges


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate natural, beat-aligned Bailian narration.")
    parser.add_argument("studio")
    parser.add_argument("project")
    parser.add_argument("--profile", default="warm-documentary")
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    profiles = load_profiles()
    if args.list_profiles:
        for profile_id, profile in profiles.items():
            print(f"{profile_id}\t{profile['name']}\t{profile['description']}")
        return 0
    if args.profile not in profiles:
        raise SystemExit(
            f"Unknown voice profile: {args.profile}. Choose from: {', '.join(profiles)}"
        )
    profile = profiles[args.profile]
    studio = Path(args.studio).expanduser().resolve()
    project_dir = Path(args.project).expanduser().resolve()
    load_env(studio / ".env")
    load_env(project_dir / ".env")
    if not os.getenv("DASHSCOPE_API_KEY"):
        raise SystemExit("DASHSCOPE_API_KEY is not set")
    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
    dashscope.base_websocket_api_url = os.getenv(
        "DASHSCOPE_WEBSOCKET_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    )

    project = read_json(project_dir / "project.json")
    storyboard = read_json(project_dir / "workflow" / "storyboard.json")
    audio_dir = project_dir / "assets" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    voice_id = get_or_create_voice(audio_dir, args.profile, profile)
    cache_path = audio_dir / "segments-cache.json"
    cache = read_json(cache_path) if cache_path.exists() else {}
    paths: list[Path] = []
    for beat in storyboard["beats"]:
        index = int(beat["id"])
        text = beat["narration"]
        signature = hashlib.sha256(
            (
                text
                + beat.get("voice_direction", "")
                + voice_id
                + profile["instruction"]
            ).encode()
        ).hexdigest()
        path = audio_dir / f"segment-{index:02d}.wav"
        if args.force or not path.exists() or cache.get(str(index)) != signature:
            synthesizer = SpeechSynthesizer(
                model=project.get("fallback_models", {}).get("tts", "cosyvoice-v3.5-plus"),
                voice=voice_id,
                format=AudioFormat.WAV_24000HZ_MONO_16BIT,
                volume=int(profile["volume"]),
                speech_rate=float(profile["speech_rate"]),
                seed=20260807 + index,
                instruction=(
                    profile["instruction"]
                    + " "
                    + beat.get("voice_direction", "")
                ),
                language_hints=["zh"],
            )
            audio = synthesizer.call(text)
            if not audio:
                raise RuntimeError(f"TTS failed for beat {index}: {synthesizer.get_response()}")
            path.write_bytes(audio)
            cache[str(index)] = signature
        paths.append(path)
    write_json(cache_path, cache)

    natural = audio_dir / "narration-natural.wav"
    ranges = combine(paths, natural)
    natural_duration = ranges[-1][1]
    desired = float(project.get("duration", 30)) * 1.07
    tempo = min(1.18, max(1.0, natural_duration / desired))
    narration = audio_dir / "narration.wav"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(natural),
        "-af", f"atempo={tempo:.6f}", str(narration),
    ], check=True)
    ranges = [(start / tempo, end / tempo) for start, end in ranges]

    captions = []
    scenes = []
    for beat, (start, end) in zip(storyboard["beats"], ranges):
        scenes.append({"id": beat["id"], "from": round(start, 3), "to": round(end, 3), "text": beat["narration"]})
        texts = beat.get("captions") or [beat["narration"]]
        weights = [max(2, len(re.sub(r"\\s", "", text))) for text in texts]
        total = sum(weights)
        cursor = start
        for caption_index, (text, weight) in enumerate(zip(texts, weights)):
            caption_end = end if caption_index == len(texts) - 1 else cursor + (end - start) * weight / total
            captions.append({"from": round(cursor, 3), "to": round(caption_end, 3), "text": text})
            cursor = caption_end
    write_json(audio_dir / "timestamps.json", {
        "alignment_method": "bailian_segments_weighted_captions",
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
    write_json(project_dir / "project.json", project)
    print(json.dumps({
        "narration": str(narration),
        "natural_duration": round(natural_duration, 3),
        "final_duration": round(ranges[-1][1], 3),
        "tempo": round(tempo, 3),
        "voice_profile": args.profile,
        "voice_id": voice_id,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
