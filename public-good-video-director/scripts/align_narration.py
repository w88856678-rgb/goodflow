#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

PUNCTUATION = set("，。！？；：,.!?;:、—…（）()《》“”‘’ \n\t")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def unit_weight(char: str) -> float:
    if char in "。！？!?":
        return 3.2
    if char in "，；：,;:":
        return 1.9
    if char in PUNCTUATION:
        return .35
    if "\u4e00" <= char <= "\u9fff":
        return 1.0
    return .72


def estimated_words(text: str, duration: float, start: float = .08, tail: float = .16) -> list[dict[str, Any]]:
    usable = max(.5, duration - start - tail)
    weights = [unit_weight(char) for char in text]
    total = max(.001, sum(weights))
    words = []
    cursor = start
    for char, weight in zip(text, weights):
        end = cursor + usable * weight / total
        if char not in PUNCTUATION:
            words.append({"text": char, "from": round(cursor, 3), "to": round(end, 3), "confidence": None})
        cursor = end
    return words


def faster_whisper_words(audio: Path, model: str, language: str) -> list[dict[str, Any]]:
    from faster_whisper import WhisperModel  # type: ignore
    engine = WhisperModel(model, device="auto", compute_type="int8")
    segments, _ = engine.transcribe(str(audio), language=language, word_timestamps=True, vad_filter=True)
    result = []
    for segment in segments:
        for word in segment.words or []:
            value = str(word.word).strip()
            if value and word.start is not None and word.end is not None:
                result.append({
                    "text": value, "from": round(float(word.start), 3), "to": round(float(word.end), 3),
                    "confidence": round(float(word.probability), 4) if word.probability is not None else None,
                })
    return result


def edge_words(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    doc = read_json(path)
    return [
        {"text": str(item["text"]), "from": float(item["from"]), "to": float(item["to"]), "confidence": 1.0}
        for item in doc.get("words", []) if item.get("text") and float(item.get("to", 0)) > float(item.get("from", 0))
    ]


def approved_word_clock(text: str, observed: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not observed:
        return estimated_words(text, duration)
    approved_chars = [char for char in text if char not in PUNCTUATION]
    observed_chars: list[dict[str, Any]] = []
    for item in observed:
        chars = [char for char in str(item["text"]) if char not in PUNCTUATION]
        if not chars:
            continue
        start, end = float(item["from"]), float(item["to"])
        for index, char in enumerate(chars):
            observed_chars.append({
                "text": char,
                "from": start + (end - start) * index / len(chars),
                "to": start + (end - start) * (index + 1) / len(chars),
                "confidence": item.get("confidence"),
            })
    if not observed_chars:
        return estimated_words(text, duration)
    matcher = difflib.SequenceMatcher(
        None, "".join(approved_chars), "".join(item["text"] for item in observed_chars), autojunk=False,
    )
    mapped: dict[int, dict[str, Any]] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapped[block.a + offset] = observed_chars[block.b + offset]
    anchors = sorted(mapped)
    if not anchors:
        return estimated_words(text, duration)
    result = []
    for index, char in enumerate(approved_chars):
        if index in mapped:
            start, end = float(mapped[index]["from"]), float(mapped[index]["to"])
            confidence = mapped[index].get("confidence")
        else:
            left = max([anchor for anchor in anchors if anchor < index], default=None)
            right = min([anchor for anchor in anchors if anchor > index], default=None)
            left_time = float(mapped[left]["to"]) if left is not None else 0.05
            right_time = float(mapped[right]["from"]) if right is not None else duration - .12
            left_index = left if left is not None else -1
            right_index = right if right is not None else len(approved_chars)
            span = max(1, right_index - left_index)
            start = left_time + (right_time - left_time) * (index - left_index - 1) / span
            end = left_time + (right_time - left_time) * (index - left_index) / span
            confidence = None
        result.append({"text": char, "from": round(max(0.0, start), 3), "to": round(min(duration, max(start + .015, end)), 3), "confidence": confidence})
    for index in range(1, len(result)):
        result[index]["from"] = round(max(result[index]["from"], result[index - 1]["to"]), 3)
        result[index]["to"] = round(max(result[index]["from"] + .015, result[index]["to"]), 3)
    return result


def text_chunks(text: str, max_chars: int = 42) -> list[str]:
    """Create complete semantic subtitle cards without hard character cuts.

    Sentence endings and semicolons are valid card boundaries. A very long
    clause may split at a comma, but never inside a word, name, number, or
    arbitrary character position. The renderer scales long cards instead of
    flashing two incomplete fragments in sequence.
    """
    chunks = [item.strip() for item in re.findall(r".*?(?:[。！？；]|$)", text, re.S) if item.strip()]
    result: list[str] = []
    for chunk in chunks:
        pending = chunk
        while len(re.sub(r"\s", "", pending)) > max_chars * 2:
            candidates = [match.end() for match in re.finditer(r"[，：]", pending[: max_chars + 8])]
            if not candidates:
                break
            cut = candidates[-1]
            result.append(pending[:cut].strip())
            pending = pending[cut:].strip()
        if pending:
            result.append(pending)
    return result or [text]


def ranges_for_chunks(text: str, chunks: list[str], words: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    visible_positions = [index for index, char in enumerate(text) if char not in PUNCTUATION]
    time_by_position: dict[int, tuple[float, float]] = {}
    for position, word in zip(visible_positions, words):
        time_by_position[position] = (float(word["from"]), float(word["to"]))
    captions = []
    cursor = 0
    last_to = 0.0
    for chunk in chunks:
        found = text.find(chunk, cursor)
        if found < 0:
            found = cursor
        end_position = min(len(text), found + len(chunk))
        times = [time_by_position[index] for index in range(found, end_position) if index in time_by_position]
        if times:
            start, end = times[0][0], times[-1][1]
        else:
            start, end = last_to, min(duration, last_to + .7)
        captions.append({"from": round(max(last_to, start), 3), "to": round(max(start + .18, end), 3), "text": chunk})
        last_to = captions[-1]["to"]
        cursor = end_position
    if captions:
        captions[-1]["to"] = round(min(duration, max(captions[-1]["to"], duration - .12)), 3)
    return captions


def main() -> int:
    parser = argparse.ArgumentParser(description="Create local narration word/caption timestamps.")
    parser.add_argument("project")
    parser.add_argument("--engine", choices=["auto", "faster-whisper", "edge-boundaries", "estimated"], default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default="zh")
    args = parser.parse_args()
    project_dir = Path(args.project).expanduser().resolve()
    project = read_json(project_dir / "project.json")
    approved = read_json(project_dir / "workflow" / "approved-script.json")
    text = approved["narration"]
    narration = project_dir / project["assets"]["narration"]
    duration = audio_duration(narration)

    observed: list[dict[str, Any]] = []
    method = "estimated_weighted_text"
    requested = args.engine
    edge_path = project_dir / "assets" / "audio" / "edge-word-boundaries.json"
    if requested in {"auto", "edge-boundaries"}:
        observed = edge_words(edge_path)
        if observed:
            method = "edge_tts_word_boundaries"
    if not observed and requested in {"auto", "faster-whisper"}:
        try:
            observed = faster_whisper_words(narration, args.model, args.language)
            if observed:
                method = f"faster_whisper:{args.model}"
        except (ImportError, RuntimeError, OSError):
            if requested == "faster-whisper":
                raise
    words = approved_word_clock(text, observed, duration) if observed else estimated_words(text, duration)
    chunks = text_chunks(text)
    captions = ranges_for_chunks(text, chunks, words, duration)
    scenes = [
        {"id": index + 1, "from": item["from"], "to": item["to"], "text": item["text"]}
        for index, item in enumerate(captions)
    ]
    output = project_dir / "assets" / "audio" / "timestamps.json"
    write_json(output, {
        "alignment_method": method,
        "requested_engine": requested,
        "language": args.language,
        "duration": round(duration, 3),
        "confidence": "high" if method == "edge_tts_word_boundaries" else ("medium" if method.startswith("faster_whisper") else "estimated"),
        "observed_words": observed,
        "words": words,
        "captions": captions,
        "scenes": scenes,
    })
    project["assets"]["timestamps"] = str(output.relative_to(project_dir))
    write_json(project_dir / "project.json", project)
    print(output)
    print(f"alignment_method={method}, words={len(words)}, captions={len(captions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
