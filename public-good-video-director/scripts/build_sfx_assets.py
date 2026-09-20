#!/usr/bin/env python3
from __future__ import annotations

import math
import random
import wave
from pathlib import Path


RATE = 44100
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "runtime" / "assets" / "audio" / "sfx"


def save(name: str, samples: list[float]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    peak = max(1.0, max(abs(value) for value in samples))
    pcm = bytearray()
    for value in samples:
        normalized = max(-1.0, min(1.0, value / peak * 0.78))
        pcm.extend(int(normalized * 32767).to_bytes(2, "little", signed=True))
    with wave.open(str(OUTPUT / f"{name}.wav"), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(RATE)
        target.writeframes(bytes(pcm))


def envelope(t: float, duration: float, attack: float = 0.02) -> float:
    return min(1.0, t / attack) * max(0.0, 1.0 - t / duration) ** 2


def main() -> int:
    rng = random.Random(20260807)

    duration = 0.42
    paper = []
    smooth = 0.0
    for index in range(int(RATE * duration)):
        t = index / RATE
        smooth = smooth * 0.82 + rng.uniform(-1, 1) * 0.18
        flutter = 0.55 + 0.45 * math.sin(2 * math.pi * (16 + 9 * t) * t)
        paper.append(smooth * flutter * envelope(t, duration, 0.03))
    save("paper", paper)

    duration = 0.50
    whoosh = []
    smooth = 0.0
    for index in range(int(RATE * duration)):
        t = index / RATE
        smooth = smooth * 0.93 + rng.uniform(-1, 1) * 0.07
        sweep = math.sin(math.pi * t / duration) ** 1.6
        whoosh.append(smooth * sweep)
    save("whoosh", whoosh)

    duration = 0.18
    tap = []
    for index in range(int(RATE * duration)):
        t = index / RATE
        decay = math.exp(-30 * t)
        tap.append(
            decay * (
                math.sin(2 * math.pi * 620 * t)
                + 0.5 * math.sin(2 * math.pi * 1080 * t)
            )
        )
    save("tap", tap)

    duration = 0.82
    chime = []
    for index in range(int(RATE * duration)):
        t = index / RATE
        decay = math.exp(-4.8 * t)
        chime.append(
            decay * (
                math.sin(2 * math.pi * 660 * t)
                + 0.42 * math.sin(2 * math.pi * 990 * t)
                + 0.18 * math.sin(2 * math.pi * 1320 * t)
            )
        )
    save("chime", chime)

    for name in ("paper", "whoosh", "tap", "chime"):
        print(OUTPUT / f"{name}.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
