#!/usr/bin/env python3
"""Compute the value-realized score (axes + visuals + open-question penalty)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CANONICAL_AXES = ('output_to', 'input_from', 'share_target', 'real_problem', 'knowledge_asset')
LEGACY_AXIS_KEYS = {
    'output_to': ('output_to', 'output_destination'),
    'input_from': ('input_from', 'info_source'),
    'share_target': ('share_target',),
    'real_problem': ('real_problem', 'true_problem'),
    'knowledge_asset': ('knowledge_asset', 'knowledge_assets'),
}
# Public compatibility alias used by existing callers and tests.
AXES = [aliases[-1] for aliases in LEGACY_AXIS_KEYS.values()]


def extract_axes(intake: dict[str, Any]) -> dict[str, Any]:
    """Return one answer per canonical axis from v2 or legacy intake shapes."""
    answers: dict[str, Any] = {}
    sections = intake.get('sections')
    if isinstance(sections, dict):
        summary = sections.get('6_five_axes_summary')
        if isinstance(summary, dict) and isinstance(summary.get('axes'), list):
            for axis in summary['axes']:
                if not isinstance(axis, dict):
                    continue
                axis_id = axis.get('axis_id')
                if axis_id in CANONICAL_AXES:
                    answers[axis_id] = axis.get('answer')

    legacy = intake.get('5_axes') or intake.get('five_axes')
    if isinstance(legacy, dict):
        for canonical, aliases in LEGACY_AXIS_KEYS.items():
            if canonical in answers:
                continue
            for alias in aliases:
                if alias in legacy:
                    answers[canonical] = legacy[alias]
                    break
    return answers


def count_open_questions(intake: dict[str, Any]) -> int:
    questions = intake.get('open_questions')
    if isinstance(questions, list):
        return len(questions)
    sections = intake.get('sections')
    if isinstance(sections, dict):
        open_section = sections.get('8_open_questions')
        if isinstance(open_section, dict) and isinstance(open_section.get('questions'), list):
            return len(open_section['questions'])
    return 0


def score(intake: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    axes = extract_axes(intake)
    filled = sum(
        1
        for key in CANONICAL_AXES
        if isinstance(axes.get(key), str) and len(axes[key].strip()) >= 4
    )
    axis_score = filled / len(CANONICAL_AXES)
    vis_count = 0
    if isinstance(manifest, dict):
        summ = manifest.get('summary')
        if isinstance(summ, dict) and isinstance(summ.get('total'), (int, float)):
            vis_count = int(summ['total'])
        elif isinstance(manifest.get('items'), list):
            vis_count = len(manifest['items'])
    vis_score = min(vis_count / 12, 1)
    open_q = count_open_questions(intake)
    open_penalty = max(0.0, 1 - open_q * 0.05)
    total = round(0.55 * axis_score + 0.35 * vis_score + 0.10 * open_penalty, 3)
    return {
        'score': total,
        'value_realized_score': total,
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
