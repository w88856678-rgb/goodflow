#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer

from tts_bailian import get_or_create_voice, load_env, load_profiles, write_json


DEFAULT_TEXT = (
    "一顿热乎的午餐，看起来只是生活里的一件小事。"
    "可对孩子们来说，它意味着每天中午，都有人在惦记他们的成长。"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create same-script Bailian auditions for public-good voice profiles."
    )
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["warm-documentary", "gentle-senior", "soft-intimate", "sincere-adult"],
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env_file = Path(args.env_file).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    load_env(env_file)
    if not os.getenv("DASHSCOPE_API_KEY"):
        raise SystemExit(f"DASHSCOPE_API_KEY is not set in {env_file}")

    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
    dashscope.base_websocket_api_url = os.getenv(
        "DASHSCOPE_WEBSOCKET_URL",
        "wss://dashscope.aliyuncs.com/api-ws/v1/inference",
    )
    profiles = load_profiles()
    unknown = [name for name in args.profiles if name not in profiles]
    if unknown:
        raise SystemExit(f"Unknown profiles: {', '.join(unknown)}")

    manifest = {"text": args.text, "profiles": []}
    for index, profile_name in enumerate(args.profiles, 1):
        profile = profiles[profile_name]
        voice_id = get_or_create_voice(output_dir, profile_name, profile)
        path = output_dir / f"{index:02d}-{profile_name}.wav"
        if args.force or not path.exists():
            synthesizer = SpeechSynthesizer(
                model="cosyvoice-v3.5-plus",
                voice=voice_id,
                format=AudioFormat.WAV_24000HZ_MONO_16BIT,
                volume=int(profile["volume"]),
                speech_rate=float(profile["speech_rate"]),
                seed=20260807 + index,
                instruction=profile["instruction"],
                language_hints=["zh"],
            )
            audio = synthesizer.call(args.text)
            if not audio:
                raise RuntimeError(
                    f"TTS failed for {profile_name}: {synthesizer.get_response()}"
                )
            path.write_bytes(audio)
        manifest["profiles"].append(
            {
                "id": profile_name,
                "name": profile["name"],
                "description": profile["description"],
                "audio": path.name,
                "voice_id": voice_id,
            }
        )
        print(path)
    write_json(output_dir / "auditions.json", manifest)
    print(output_dir / "auditions.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
