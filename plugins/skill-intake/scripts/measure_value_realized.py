#!/usr/bin/env python3
"""Compute the value-realized score (axes + visuals + open-question penalty)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

AXES = ['output_destination', 'info_source', 'share_target', 'true_problem', 'knowledge_assets']


def score(intake: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    axes = intake.get('5_axes') or intake.get('five_axes') or {}
    filled = 0
    for k in AXES:
        v = axes.get(k)
        if isinstance(v, str) and len(v.strip()) >= 4:
            filled += 1
    axis_score = filled / len(AXES)
    vis_count = 0
    if isinstance(manifest, dict):
        summ = manifest.get('summary')
        if isinstance(summ, dict) and isinstance(summ.get('total'), (int, float)):
            vis_count = int(summ['total'])
        elif isinstance(manifest.get('items'), list):
            vis_count = len(manifest['items'])
    vis_score = min(vis_count / 12, 1)
    open_q = len(intake['open_questions']) if isinstance(intake.get('open_questions'), list) else 0
    open_penalty = max(0.0, 1 - open_q * 0.05)
    total = round(0.55 * axis_score + 0.35 * vis_score + 0.10 * open_penalty, 3)
    return {
        'score': total,
        'components': {'axisScore': axis_score, 'visScore': vis_score, 'openPenalty': open_penalty},
        'axes_filled': filled,
        'visualization_count': vis_count,
    }


def load_previous_scores(history_file: str | None) -> list[float]:
    if not history_file:
        return []
    p = Path(history_file)
    if not p.exists():
        return []
    try:
        j = json.loads(p.read_text(encoding='utf-8'))
        if isinstance(j, dict):
            if isinstance(j.get('previous_scores'), list):
                return list(j['previous_scores'])[-5:]
            if isinstance(j.get('value_realized_score'), (int, float)):
                return [j['value_realized_score']]
        return []
    except Exception:
        return []


def is_declining(prev: list[Any], current: float) -> bool:
    if not isinstance(prev, list) or len(prev) < 2:
        return False
    a, b = prev[-2], prev[-1]
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and b < a and current < b


def main(argv: list[str]) -> int:
    intake_file = None
    manifest_file = None
    history_file = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--history':
            i += 1
            history_file = argv[i]
        elif a == '--manifest':
            i += 1
            manifest_file = argv[i]
        elif intake_file is None:
            intake_file = a
        elif manifest_file is None:
            manifest_file = a
        i += 1
    if not intake_file:
        sys.stderr.write('usage: measure_value_realized.py <intake.json> [manifest.json] [--history <self-update.json>]\n')
        return 2
    try:
        intake = json.loads(Path(intake_file).resolve().read_text(encoding='utf-8'))
        manifest = None
        if manifest_file and Path(manifest_file).exists():
            manifest = json.loads(Path(manifest_file).resolve().read_text(encoding='utf-8'))
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = score(intake, manifest)
    previous_scores = load_previous_scores(history_file)
    r['previous_scores'] = previous_scores
    r['declining'] = is_declining(previous_scores, r['score'])
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
