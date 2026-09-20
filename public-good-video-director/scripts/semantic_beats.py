#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


OPEN_QUOTES = {'“': '”', '‘': '’', '「': '」', '『': '』', '"': '"'}
STRONG_END = set('。！？!?；;')
SOFT_END = set('，,:：')
DEPENDENT_PREFIXES = (
    '而', '但', '却', '也', '并', '于是', '因此', '所以', '因为', '当', '在', '随着',
    '如果', '为了', '其中', '这时', '那一刻', '从此', '同时', '后来',
)


def visible_length(text: str) -> int:
    return len(re.sub(r'\s+', '', text))


def split_outside_quotes(text: str, delimiters: set[str]) -> list[str]:
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    for index, char in enumerate(text):
        if char in OPEN_QUOTES:
            close = OPEN_QUOTES[char]
            if char == '"' and stack and stack[-1] == '"':
                stack.pop()
            else:
                stack.append(close)
        elif stack and char == stack[-1]:
            stack.pop()
        if char in delimiters and not stack:
            parts.append(text[start:index + 1])
            start = index + 1
    if start < len(text):
        parts.append(text[start:])
    return [part for part in parts if part]


def split_long_unit(unit: str, max_chars: int) -> list[str]:
    if visible_length(unit) <= max_chars:
        return [unit]
    soft = split_outside_quotes(unit, SOFT_END)
    if len(soft) <= 1:
        return [unit]
    result: list[str] = []
    current = ''
    for piece in soft:
        if current and visible_length(current + piece) > max_chars:
            result.append(current)
            current = piece
        else:
            current += piece
    if current:
        result.append(current)
    return result


def merge_cost(left: str, right: str, target_chars: int) -> float:
    combined = visible_length(left + right)
    penalty = abs(combined - target_chars)
    right_clean = right.lstrip()
    if right_clean.startswith(DEPENDENT_PREFIXES):
        penalty -= 12
    if left.rstrip().endswith(tuple(STRONG_END)):
        penalty += 4
    return penalty


def split_semantic_beats(text: str, duration: float = 30.0) -> list[str]:
    if not text.strip():
        return []
    target_count = max(4, min(9, round(max(12.0, duration) / 4.4)))
    target_chars = max(14, round(visible_length(text) / target_count))
    max_chars = max(26, round(target_chars * 1.65))

    strong_units = split_outside_quotes(text, STRONG_END)
    beats = [piece for unit in strong_units for piece in split_long_unit(unit, max_chars)]

    index = 0
    while index < len(beats):
        current = beats[index]
        dependent = current.lstrip().startswith(DEPENDENT_PREFIXES)
        if len(beats) > 1 and (visible_length(current) < 8 or dependent):
            if index > 0:
                beats[index - 1:index + 1] = [beats[index - 1] + current]
                index = max(0, index - 1)
            else:
                beats[0:2] = [current + beats[1]]
            continue
        index += 1

    while len(beats) < target_count:
        candidates: list[tuple[int, list[str]]] = []
        for i, beat in enumerate(beats):
            pieces = split_outside_quotes(beat, SOFT_END)
            if len(pieces) >= 2 and min(visible_length(p) for p in pieces) >= 6:
                candidates.append((i, pieces))
        if not candidates:
            break
        i, pieces = max(candidates, key=lambda item: visible_length(beats[item[0]]))
        midpoint = len(pieces) // 2
        beats[i:i + 1] = [''.join(pieces[:midpoint]), ''.join(pieces[midpoint:])]

    while len(beats) > target_count:
        i = min(
            range(len(beats) - 1),
            key=lambda pos: merge_cost(beats[pos], beats[pos + 1], target_chars),
        )
        beats[i:i + 2] = [beats[i] + beats[i + 1]]

    beats = [beat for beat in beats if beat]
    source_compact = re.sub(r'\s+', '', text)
    output_compact = re.sub(r'\s+', '', ''.join(beats))
    if source_compact != output_compact:
        raise RuntimeError('Semantic beat splitting changed the approved narration')
    return beats


def main() -> int:
    parser = argparse.ArgumentParser(description='Split approved Chinese narration into semantic beats.')
    parser.add_argument('--text')
    parser.add_argument('--text-file')
    parser.add_argument('--project')
    parser.add_argument('--duration', type=float)
    parser.add_argument('--output')
    args = parser.parse_args()

    duration = args.duration or 30.0
    if args.project:
        project = Path(args.project).expanduser().resolve()
        approved = json.loads((project / 'workflow/approved-script.json').read_text(encoding='utf-8'))
        config = json.loads((project / 'project.json').read_text(encoding='utf-8'))
        text = approved['narration']
        duration = args.duration or float(config.get('duration', 30))
        output = Path(args.output).expanduser().resolve() if args.output else project / 'workflow/semantic-beats.json'
    elif args.text_file:
        text = Path(args.text_file).read_text(encoding='utf-8')
        output = Path(args.output).expanduser().resolve() if args.output else None
    elif args.text:
        text = args.text
        output = Path(args.output).expanduser().resolve() if args.output else None
    else:
        raise SystemExit('Provide --project, --text-file, or --text')

    result = {'duration': duration, 'beats': [
        {'id': index + 1, 'narration': beat, 'characters': visible_length(beat)}
        for index, beat in enumerate(split_semantic_beats(text, duration))
    ]}
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding='utf-8')
        print(output)
    else:
        print(encoded, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
