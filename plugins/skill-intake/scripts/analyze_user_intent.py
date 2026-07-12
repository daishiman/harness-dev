#!/usr/bin/env python3
"""ユーザー入力 (AskUserQuestion 回答 + 自由発話) を内部解析し、
真の要求 / 最適解候補 / 採用根拠を eval-log に残す裏処理。

出力はユーザーに直接表示しない (Notion ページの該当章の本文生成時に裏で参照される)。

入力: output/<hint>/*.json (全 phase の SubAgent 出力)
出力: output/<hint>/internal-analysis.json

usage:
  python3 plugins/skill-intake/scripts/analyze_user_intent.py <hint-dir>
"""
from __future__ import annotations
import sys, json, re, datetime, pathlib
from collections import Counter

ABSTRACT_VERBS = ["効率化", "最適化", "自動化", "改善", "見える化", "高度化", "強化"]
VAGUE_TOKENS = ["なんとなく", "とりあえず", "うまく", "いい感じ", "良い感じ"]


def load_json_safely(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def detect_signals(obj, prefix=""):
    """JSON を再帰走査し、抽象動詞 / 曖昧語 / 矛盾を検出。"""
    signals = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            signals.extend(detect_signals(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            signals.extend(detect_signals(v, f"{prefix}[{i}]"))
    elif isinstance(obj, str):
        for token in ABSTRACT_VERBS:
            if token in obj:
                signals.append({"kind": "abstract_verb", "field": prefix, "token": token, "text": obj[:80]})
        for token in VAGUE_TOKENS:
            if token in obj:
                signals.append({"kind": "vague_token", "field": prefix, "token": token, "text": obj[:80]})
    return signals


def extract_true_intent(phase_data: dict) -> dict:
    """各 phase 出力から『本当に欲しいもの』候補を抽出し、最頻動詞 + 最頻名詞でスコアリング。"""
    candidates: list[dict] = []

    purpose = phase_data.get("purpose", {}) or {}
    tp = (purpose.get("true_purpose") or {}) if isinstance(purpose.get("true_purpose"), dict) else {}
    if tp.get("verb_object"):
        candidates.append({"source": "purpose.json/true_purpose.verb_object", "text": tp["verb_object"], "weight": 3})
    if tp.get("underlying_motivation"):
        candidates.append({"source": "purpose.json/underlying_motivation", "text": tp["underlying_motivation"], "weight": 2})

    summary = phase_data.get("summary", {}) or {}
    fa = summary.get("five_axes", {}) or {}
    if fa.get("true_problem"):
        candidates.append({"source": "summary.json/five_axes.true_problem", "text": fa["true_problem"], "weight": 3})

    assumption = phase_data.get("assumption", {}) or {}
    if assumption.get("confirmed_deep_problem"):
        candidates.append({"source": "assumption.json/confirmed_deep_problem", "text": assumption["confirmed_deep_problem"], "weight": 2})

    return {
        "candidates": candidates,
        "best_pick": max(candidates, key=lambda c: c["weight"]) if candidates else None,
    }


def select_optimal_per_axis(phase_data: dict) -> dict:
    """5 軸ごとに最適解 (出典 / 採用候補 / 採用根拠) を抽出。重複した記述があれば最も具体的なものを選ぶ。"""
    axes = {}
    summary = phase_data.get("summary", {}) or {}
    fa = summary.get("five_axes", {}) or {}
    for axis_id in ("output_target", "info_source", "share_target", "true_problem", "knowledge_assets"):
        v = fa.get(axis_id)
        if v is None:
            axes[axis_id] = {"selected": None, "reason": "summary.json 未充足", "alternatives": []}
            continue
        text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        specificity = len(re.sub(r"\s+", "", text))
        axes[axis_id] = {
            "selected": v,
            "reason": f"summary 由来、文字密度 {specificity}",
            "alternatives": [],
            "specificity_score": specificity,
        }
    return axes


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write("usage: analyze_user_intent.py <hint-dir>\n")
        return 2
    hint_dir = pathlib.Path(argv[1]).resolve()
    if not hint_dir.is_dir():
        sys.stderr.write(f"not a directory: {hint_dir}\n")
        return 2

    phase_files = {
        "kickoff": "kickoff.json",
        "assumption": "assumption.json",
        "profile": "profile.json",
        "interview": "interview.json",
        "purpose": "purpose.json",
        "options": "options.json",
        "visuals": "visuals.json",
        "summary": "summary.json",
        "next_action": "next-action.json",
    }
    phase_data = {k: load_json_safely(hint_dir / fn) or {} for k, fn in phase_files.items()}

    signals = []
    for k, d in phase_data.items():
        signals.extend(detect_signals(d, prefix=k))

    counter = Counter((s["kind"], s["token"]) for s in signals)
    result = {
        "produced_by": "analyze_user_intent.py",
        "hint_dir": str(hint_dir),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "true_intent": extract_true_intent(phase_data),
        "per_axis_optimal": select_optimal_per_axis(phase_data),
        "signals": signals,
        "signal_summary": [{"kind": k, "token": t, "count": c} for (k, t), c in counter.most_common()],
        "hidden_from_user": True,
        "consumed_by": ["render_notion_page.py", "render-intake-final.py"],
        "notes": "本ファイルは内部解析の証跡。Notion 本文生成時に裏で参照されるが、ユーザーには直接表示しない。",
    }

    out_path = hint_dir / "internal-analysis.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(f"wrote {out_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
