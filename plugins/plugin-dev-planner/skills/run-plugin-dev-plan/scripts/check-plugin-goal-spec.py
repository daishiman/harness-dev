#!/usr/bin/env python3
# /// script
# name: check-plugin-goal-spec
# purpose: run-plugin-dev-plan R1 の plugin-goal-spec.json が汎用 goal-spec + plugin 固有アンカー契約を満たすか検証する。
# inputs:
#   - argv: <goal-spec.json>
# outputs:
#   - stdout: OK summary
#   - stderr: schema violations
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402  (PLAN_DIR 解決の SSOT=plan_output_dir を再現性アンカー照合に使う)


# per-phase 転換: 本数固定/カウント機構は 13 フェーズ固定で自然消滅したため required/allowed から削除。
# requested_count は「任意記録可 (gate 強制しない)」として ALLOWED に残す (goal-spec に希望本数を残せるが
# 出力本数を強制しない・凍結契約 §0)。
REQUIRED = {
    "purpose",
    "background",
    "goal",
    "checklist",
    "target_plugin_slug",
    "plan_dir",
}
ALLOWED = REQUIRED | {
    "artifact_class",
    "out_dir",
    "constraints",
    "handoff_targets",
    "max_loops",
    "open_questions",
    "requested_count",
    # E1/E3 provenance (任意): 改善/intake 由来の再生成 goal-spec が源泉を追跡できるようにする。
    # 欠落は後方互換で WARN 受理 (既存 goal-spec を壊さない)、present-but-malformed のみ fatal。
    "source_intake",
    "source_improvement",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
# provenance フィールド (source_intake/source_improvement) が持つべき sub-key。
_PROVENANCE_KEYS = ("source_intake", "source_improvement")


def _nonempty_str(data: dict, key: str, errors: list[str]) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key} が非空 string でない")
        return ""
    return value.strip()


def _provenance_field_errors(data: dict, key: str) -> list[str]:
    """provenance フィールドが *存在するとき* の schema 準拠を検査する (欠落/null は WARN 側で扱う)。

    存在時は object で {ref: 非空 string, schema_version: semver} を要求し、余分キーを禁止する。
    欠落 (キー無し) / null は fatal でない (後方互換: provenance_warnings が WARN として受理)。
    """
    if key not in data or data.get(key) is None:
        return []
    val = data.get(key)
    if not isinstance(val, dict):
        return [f"{key} は object または null であること (現値 {type(val).__name__})"]
    errors: list[str] = []
    extra = sorted(set(val.keys()) - {"ref", "schema_version"})
    if extra:
        errors.append(f"{key} additionalProperties not allowed: {extra}")
    ref = val.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        errors.append(f"{key}.ref が非空 string でない")
    sv = val.get("schema_version")
    if not isinstance(sv, str) or not SEMVER_RE.match(sv):
        errors.append(f"{key}.schema_version は semver (X.Y.Z) であること (現値 {sv!r})")
    return errors


def provenance_warnings(data: object) -> list[str]:
    """provenance フィールド欠落を WARN として列挙する (fatal でない・後方互換受理)。"""
    warnings: list[str] = []
    if not isinstance(data, dict):
        return warnings
    for key in _PROVENANCE_KEYS:
        if key not in data or data.get(key) is None:
            warnings.append(
                f"{key} 不在: intake/改善 由来でない既存 goal-spec として WARN 受理 (後方互換)"
            )
    return warnings


def validate(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["goal-spec root が object でない"]
    missing = sorted(REQUIRED - data.keys())
    if missing:
        errors.append(f"required keys missing: {missing}")
    extra = sorted(set(data.keys()) - ALLOWED)
    if extra:
        errors.append(f"additionalProperties not allowed: {extra}")

    for key in ("purpose", "background", "goal", "plan_dir"):
        _nonempty_str(data, key, errors)
    slug = _nonempty_str(data, "target_plugin_slug", errors)
    if slug and not SLUG_RE.match(slug):
        errors.append("target_plugin_slug は ASCII kebab-case であること")

    # 再現性アンカー: plan_dir は target_plugin_slug (+任意 out_dir) 由来の正本と一致すること。
    # SKILL「同一構想は常に同一 PLAN_DIR」を機械強制する (従来は散文のみで slug↔plan_dir の
    # drift が exit0 で素通りしていた)。解決 SSOT は specfm.plan_output_dir (単語置換でなく正本参照)。
    plan_dir = data.get("plan_dir")
    if slug and SLUG_RE.match(slug) and isinstance(plan_dir, str) and plan_dir.strip():
        out_dir = data.get("out_dir")
        od = out_dir.strip() if isinstance(out_dir, str) and out_dir.strip() else None
        try:
            expected = specfm.plan_output_dir(slug, od)
        except ValueError:
            expected = None
        if expected is not None and plan_dir.strip().rstrip("/") != expected:
            errors.append(
                f"plan_dir={plan_dir!r} が target_plugin_slug/out_dir 由来の正本 {expected!r} と不一致 "
                "(再現性アンカー違反: 同一構想は常に同一出力先であること)"
            )

    artifact_class = data.get("artifact_class")
    if artifact_class is not None and artifact_class not in {"skill-only", "plugin-plan", "existing-plugin-update"}:
        errors.append("artifact_class は skill-only|plugin-plan|existing-plugin-update のみ")

    # E1/E3 provenance: 存在時のみ schema 準拠を fatal 検査する (欠落は main が WARN 受理)。
    for key in _PROVENANCE_KEYS:
        errors.extend(_provenance_field_errors(data, key))

    # requested_count は任意記録 (希望本数のメモ)。null または正の int の型のみ検査し、出力本数の
    # 強制 (旧・本数 pin 機構) はしない (per-phase 転換で本数は 13 フェーズ固定)。
    requested = data.get("requested_count")
    if requested is not None and (not isinstance(requested, int) or isinstance(requested, bool) or requested < 1):
        errors.append("requested_count は null または正の int")

    max_loops = data.get("max_loops")
    if max_loops is not None and (not isinstance(max_loops, int) or isinstance(max_loops, bool) or max_loops < 1):
        errors.append("max_loops は正の int")

    for key in ("constraints", "handoff_targets", "open_questions"):
        value = data.get(key)
        if value is not None and (not isinstance(value, list) or any(not isinstance(x, str) for x in value)):
            errors.append(f"{key} は string list")

    checklist = data.get("checklist")
    if not isinstance(checklist, list) or not checklist:
        errors.append("checklist が非空 list でない")
    else:
        seen: set[str] = set()
        for idx, item in enumerate(checklist):
            prefix = f"checklist[{idx}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} が object でない")
                continue
            item_extra = sorted(set(item.keys()) - {"id", "criterion", "done", "verify_by"})
            if item_extra:
                errors.append(f"{prefix} additionalProperties not allowed: {item_extra}")
            cid = item.get("id")
            if not isinstance(cid, str) or not re.fullmatch(r"C[0-9]+", cid):
                errors.append(f"{prefix}.id は ^C[0-9]+$")
            elif cid in seen:
                errors.append(f"{prefix}.id={cid!r} が重複")
            else:
                seen.add(cid)
            if not isinstance(item.get("criterion"), str) or not item.get("criterion", "").strip():
                errors.append(f"{prefix}.criterion が非空 string でない")
            if not isinstance(item.get("done"), bool):
                errors.append(f"{prefix}.done が bool でない")
            verify_by = item.get("verify_by")
            if verify_by is not None and verify_by not in {"reasoning", "script", "lint", "test", "human"}:
                errors.append(f"{prefix}.verify_by が enum 外")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="plugin goal-spec を検証する")
    ap.add_argument("goal_spec", help="goal-spec.json")
    args = ap.parse_args(argv)
    path = Path(args.goal_spec)
    if not path.is_file():
        sys.stderr.write(f"goal-spec not found: {path}\n")
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"JSON parse error: {exc}\n")
        return 2
    errors = validate(data)
    # provenance 欠落は WARN (exit code に影響しない・後方互換受理)。
    for warn in provenance_warnings(data):
        sys.stderr.write("WARN: " + warn + "\n")
    if not errors:
        sys.stdout.write("OK: plugin goal-spec schema + plugin anchors validated\n")
        return 0
    for err in errors:
        sys.stderr.write(err + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
