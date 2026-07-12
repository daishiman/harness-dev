#!/usr/bin/env python3
# /// script
# name: check-intake-consumption
# purpose: E1 情報漏れ検出ゲート。intake.json の主要項目 (executive_summary / purpose_excavator / next-action split_candidates) が goal-spec 生成時に反映されたかを signal 重複で検出し、未反映を WARN/FAIL する。
# inputs:
#   - argv: --intake <intake.json> --goal-spec <goal-spec.json> [--next-action <next-action.json>] [--strict]
# outputs:
#   - stdout: OK summary / 反映済み件数
#   - stderr: 未反映項目 (WARN/FAIL)
#   - exit: 0=全 fail-severity 反映済み / 1=fail-severity 未反映あり (--strict は warn も昇格) / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [specfm]
# requires-python: ">=3.10"
# ///
"""intake.json → goal-spec の情報漏れ検出ゲート (E1)。

skill-intake が produce した intake.json の主要セクションが、plugin-dev-planner の
goal-spec へ反映されたかを検査する。反映判定は specfm.purpose_signals による signal
(CJK bigram + ascii 語) の重複で決定論的に行う (形態素解析非依存・purpose-traceability
ゲートと同一機構)。intake の具体スキーマに硬結合せず、キー名部分一致で対象セクションを
再帰抽出するため、skill-intake の schema 微変更に対して頑健。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402  (purpose_signals を反映判定へ再利用)

# C11 hook が検証する pass marker のゲート名 (digest pin 契約)。
_MARKER_GATE = "intake-consumption"


def write_pass_marker(marker_dir: Path, gate_name: str, pinned_file: Path) -> Path:
    """<marker_dir>/.gate/<gate_name>.pass に pinned_file の sha256 を書く (digest pin)。

    marker は goal-spec の内容に pin される。goal-spec が後で変わると digest が食い違い、
    C11 hook が marker を stale として --mode update を block する (fail-open 穴の封鎖)。
    """
    digest = hashlib.sha256(pinned_file.read_bytes()).hexdigest()
    gate_dir = marker_dir / ".gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    marker = gate_dir / f"{gate_name}.pass"
    marker.write_text(digest + "\n", encoding="utf-8")
    return marker

# 反映を検査するセクションの (キー部分一致, severity)。fail=未反映で FAIL / warn=未反映で WARN。
_INTAKE_SECTIONS = (
    ("executive_summary", "fail"),
    ("purpose_excavator", "fail"),
)
_NEXT_ACTION_SECTIONS = (
    ("split_candidates", "warn"),
)


# purpose 本文でない「セッション envelope メタデータ」キー。skill-intake は各 section へ
# 生成時刻・pattern/depth/tier・handoff mode・使用技法などのメタを刻む。これらは intake の
# 実体(purpose/motivation/differentiation)でなく、goal-spec の purpose/goal へ反映される性質の
# ものでない (timestamp や enum は原理的に反映不能)。反映判定の分母から除外し誤 FAIL を防ぐ。
# 併せて `_`接頭辞キー (fidelity guard の `_fidelity` 等・私的名前空間) も除外する。
_META_KEYS = frozenset({
    "generated_at", "pattern", "workflow_pattern", "depth", "vocabulary_tier",
    "state", "handoff_mode", "value_realized_score", "techniques_used", "rounds",
    "agreement_loop_detected", "asset_id", "schema_version", "source_of_truth",
    "skill_name_hint",
})


def _collect_strings(node: object) -> list[str]:
    """任意ネスト構造から非空 string を再帰収集する (item 単位の反映判定素材)。

    dict 走査では `_`接頭辞キー (私的名前空間) と `_META_KEYS` (セッション envelope メタ) を
    除外し、purpose 実体だけを反映判定の対象にする (メタデータ/guard scaffolding での誤 FAIL 防止)。
    """
    out: list[str] = []
    if isinstance(node, str):
        if node.strip():
            out.append(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            if str(k).startswith("_") or str(k) in _META_KEYS:
                continue
            out.extend(_collect_strings(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_collect_strings(v))
    return out


def _find_sections(data: object, key_substr: str) -> list[object]:
    """キー名に key_substr を部分一致で含む値を再帰抽出する (schema 微変更に頑健)。"""
    found: list[object] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if key_substr in str(k):
                found.append(v)
            else:
                found.extend(_find_sections(v, key_substr))
    elif isinstance(data, list):
        for v in data:
            found.extend(_find_sections(v, key_substr))
    return found


def extract_items(intake: object, next_action: object | None) -> list[tuple[str, str, str]]:
    """反映検査対象 item を (source_label, text, severity) の list で返す。"""
    items: list[tuple[str, str, str]] = []
    for key_substr, severity in _INTAKE_SECTIONS:
        for idx, section in enumerate(_find_sections(intake, key_substr)):
            for j, text in enumerate(_collect_strings(section)):
                items.append((f"{key_substr}[{idx}.{j}]", text, severity))
    if next_action is not None:
        for key_substr, severity in _NEXT_ACTION_SECTIONS:
            for idx, section in enumerate(_find_sections(next_action, key_substr)):
                for j, text in enumerate(_collect_strings(section)):
                    items.append((f"{key_substr}[{idx}.{j}]", text, severity))
    return items


def goal_spec_signals(goal_spec: dict) -> set[str]:
    """goal-spec の purpose/background/goal/checklist から反映済み signal 集合を作る。"""
    vocab: set[str] = set()
    for key in ("purpose", "background", "goal"):
        vocab |= specfm.purpose_signals(goal_spec.get(key, ""))
    checklist = goal_spec.get("checklist")
    if isinstance(checklist, list):
        for item in checklist:
            if isinstance(item, dict):
                vocab |= specfm.purpose_signals(item.get("criterion", ""))
    return vocab


def find_unreflected(items, goal_signals: set[str]) -> list[tuple[str, str, str]]:
    """signal 重複が 1 つも無い item を未反映として返す (signal を持たない item は判定保留=反映扱い)。"""
    unreflected: list[tuple[str, str, str]] = []
    for label, text, severity in items:
        sig = specfm.purpose_signals(text)
        if sig and not (sig & goal_signals):
            unreflected.append((label, text, severity))
    return unreflected


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="intake.json の goal-spec への反映を検査する")
    ap.add_argument("--intake", required=True)
    ap.add_argument("--goal-spec", required=True)
    ap.add_argument("--next-action", default=None)
    ap.add_argument("--strict", action="store_true", help="warn-severity 未反映も FAIL に昇格する")
    ap.add_argument("--marker-dir", default=None,
                    help="PASS 時に <dir>/.gate/intake-consumption.pass (goal-spec digest pin) を書く (C11 hook 用)")
    args = ap.parse_args(argv)

    try:
        intake = json.loads(Path(args.intake).read_text(encoding="utf-8"))
        goal_spec = json.loads(Path(args.goal_spec).read_text(encoding="utf-8"))
        next_action = (
            json.loads(Path(args.next_action).read_text(encoding="utf-8"))
            if args.next_action else None
        )
    except FileNotFoundError as exc:
        sys.stderr.write(f"input not found: {exc}\n")
        return 2
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"JSON parse error: {exc}\n")
        return 2
    if not isinstance(goal_spec, dict):
        sys.stderr.write("goal-spec root が object でない\n")
        return 2

    items = extract_items(intake, next_action)
    goal_signals = goal_spec_signals(goal_spec)
    unreflected = find_unreflected(items, goal_signals)

    fail_hits = [u for u in unreflected if u[2] == "fail" or args.strict]
    for label, text, severity in unreflected:
        tag = "FAIL" if (severity == "fail" or args.strict) else "WARN"
        excerpt = text if len(text) <= 60 else text[:57] + "..."
        sys.stderr.write(f"{tag}: intake {label} が goal-spec へ未反映: {excerpt!r}\n")

    if fail_hits:
        return 1
    if args.marker_dir:
        write_pass_marker(Path(args.marker_dir), _MARKER_GATE, Path(args.goal_spec))
    sys.stdout.write(
        f"OK: intake {len(items)} 項目中 {len(items) - len(unreflected)} 反映済み "
        f"(WARN {len(unreflected)} 件)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
