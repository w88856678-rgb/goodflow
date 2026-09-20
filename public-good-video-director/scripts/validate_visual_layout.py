#!/usr/bin/env python3
"""Validate captured visible video geometry. Standard library only; never edits video."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from typing import Any

GROUPS = ('opaqueCards', 'protected', 'overlays', 'captions', 'captionLines')

def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def overlap(a: dict, b: dict) -> float:
    return max(0, min(a['x']+a['width'], b['x']+b['width'])-max(a['x'], b['x'])) * max(0, min(a['y']+a['height'], b['y']+b['height'])-max(a['y'], b['y']))

def validate(doc: Any) -> dict:
    errors: list[dict] = []
    def fail(kind: str, **fields: Any) -> None:
        errors.append({'kind': kind, **fields})
    if not isinstance(doc, dict):
        return {'passed': False, 'samples': 0, 'errors': [{'kind': 'document_not_object'}]}
    count = doc.get('scenes')
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        fail('positive_scene_count_required')
    canvas = doc.get('canvas', {'width': 1080, 'height': 1920})
    if not isinstance(canvas, dict) or any(not number(canvas.get(k)) or canvas[k] <= 0 for k in ('width', 'height')):
        fail('invalid_canvas'); canvas = {'width': 1080, 'height': 1920}
    records = doc.get('records')
    if not isinstance(records, list) or not records:
        fail('nonempty_records_required'); records = []
    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            fail('invalid_record', index=index); continue
        sid = record.get('scene_id'); context = {'index': index, 'scene_id': sid, 'time': record.get('time')}
        if not isinstance(sid, int) or isinstance(sid, bool) or sid < 1 or (isinstance(count, int) and sid > count):
            fail('invalid_scene_id', **context)
        else:
            seen.add(sid)
        if not number(record.get('time')) or record['time'] < 0:
            fail('invalid_time', **context)
        valid = True
        for group in GROUPS:
            boxes = record.get(group)
            if not isinstance(boxes, list):
                fail('missing_geometry_group', group=group, **context); valid = False; continue
            for box in boxes:
                if not isinstance(box, dict) or any(not number(box.get(k)) for k in ('x', 'y', 'width', 'height')) or box['width'] < 0 or box['height'] < 0:
                    fail('invalid_box', group=group, **context); valid = False
        if not valid:
            continue
        text_boxes = record['overlays'] + record['captions']
        for group in ('opaqueCards', 'protected'):
            for image_index, image in enumerate(record[group]):
                for label in text_boxes:
                    if overlap(image, label) > 4:
                        fail('image_or_card_text_overlap', group=group, image_index=image_index, text=label.get('text', ''), **context)
        for caption in record['captions']:
            if caption['x'] < -1 or caption['y'] < -1 or caption['x']+caption['width'] > canvas['width']+1 or caption['y']+caption['height'] > canvas['height']+1:
                fail('caption_outside_canvas', text=caption.get('text', ''), **context)
            for label in record['overlays']:
                if overlap(caption, label) > 4:
                    fail('caption_overlay_overlap', text=label.get('text', ''), **context)
        for line in record['captionLines']:
            sw, cw = line.get('scrollWidth'), line.get('clientWidth')
            if not number(sw) or not number(cw) or cw <= 0 or sw < 0:
                fail('invalid_line_measurement', **context)
            elif sw > cw+1:
                fail('caption_line_overflow', text=line.get('text', ''), **context)
    if isinstance(count, int) and not isinstance(count, bool) and count > 0:
        for sid in range(1, count+1):
            if sid not in seen:
                fail('missing_scene', scene_id=sid)
    return {'passed': not errors, 'scope': 'captured_geometry_only', 'samples': len(records), 'scenes_seen': sorted(seen), 'errors': errors,
            'limits': 'Requires fresh correctly visibility-filtered captures. Does not validate source crops, exact transcript, audio timing, or aesthetic quality.'}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = validate(json.loads(args.capture.read_text(encoding='utf-8')))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        if args.output.resolve() == args.capture.resolve():
            parser.error('Output must not overwrite the capture input.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded, end='')
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
