#!/usr/bin/env python3
# /// script
# name: validate-coverage-matrix
# version: 0.1.0
# purpose: システム構成カテゴリ×canonical platform id の収集マトリクスの全セルが『未収集/対象外/確定』のいずれかで埋まり、対象外に理由・確定に qa_ref が付与され、必須プラットフォーム行が全存在し、カテゴリ集約状態が真理値表と一致することを検証する決定論ゲート (goal-spec C7 の直接実装)。
# inputs:
#   - argv: --matrix FILE [--require-complete]
# outputs:
#   - stdout: OK summary
#   - stderr: violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""カテゴリ×プラットフォーム収集マトリクス (spec-state.json) の網羅性を機械検証する。

matrix ファイル (spec-state.json) の期待形状:
{
  "categories": [{"id": "database", "label": "データベース"}, ...],
  "platforms": ["web","mobile","tablet","desktop-windows","desktop-linux","desktop-macos"],
  "matrix": {
    "<category_id>": {
      "<platform_id>": {"state": "確定", "qa_ref": "qa-001"},        # 確定は qa_ref 必須
      "<platform_id>": {"state": "対象外", "reason": "..."},          # 対象外は reason 必須
      "<platform_id>": {"state": "未収集"}                            # loop 中のみ許容
    }, ...
  },
  "qa_log": [{"id": "qa-001", ...}],          # 確定 qa_ref の参照先 (存在検証)
  "approval_log": [{"id": "appr-001", ...}],  # 一括承認 (対象外/確定を承認ログ参照で代替可)
  "category_aggregate": {"<category_id>": "確定"|"収集中"|"未着手"|"対象外"}  # 任意 (あれば真理値表照合)
}

集約状態の真理値表 (goal-spec C1 の 4 値):
  全セル未収集              -> 未着手
  未収集混在 (一部のみ未収集) -> 収集中
  全セル対象外              -> 対象外
  それ以外で未収集 0        -> 確定

要件 C9 (上位概念 anchor・opt-in): --require-foundation を付けると validate_foundation() が
requirements_foundation の U1-U5 非空・各『確定』セルの serves_goals トレース (実在 goal へ ≥1)・
どのゴールにも資さない確定セル (drift 候補) を追加検証する。既定 (--matrix / --require-complete) は
従来どおりで validate() を一切変えないため後方互換 (foundation 検証は完全にオプトイン)。
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

CELL_STATES = {"未収集", "対象外", "確定"}
CANONICAL_PLATFORMS = (
    "web",
    "mobile",
    "tablet",
    "desktop-windows",
    "desktop-linux",
    "desktop-macos",
)
# goal-spec C1 の例示カテゴリ (canonical id)。マトリクスはこれを最低含むか除外根拠を持つ。
GOAL_SPEC_CATEGORIES = (
    "database",
    "auth",
    "ui-ux",
    "security",
    "infrastructure",
    "backend",
    "frontend",
    "maintenance-ops",
)
DECISION_COST_CATEGORIES = {"free", "low-cost", "paid", "unknown"}
DECISION_COMPARISON_AXES = ("goal_fit", "tco", "security", "operations", "lock_in")
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _derive_aggregate(cells: list[str]) -> str:
    """セル状態集合から真理値表でカテゴリ集約状態を導出する。"""
    if all(c == "未収集" for c in cells):
        return "未着手"
    if all(c == "対象外" for c in cells):
        return "対象外"
    if any(c == "未収集" for c in cells):
        return "収集中"
    return "確定"


def validate(data: dict, require_complete: bool = False) -> list[str]:
    findings: list[str] = []

    categories = data.get("categories")
    matrix = data.get("matrix")
    if not isinstance(categories, list) or not categories:
        findings.append("categories: 非空配列でない")
        return findings
    if not isinstance(matrix, dict) or not matrix:
        findings.append("matrix: 非空オブジェクトでない")
        return findings

    cat_ids = []
    for c in categories:
        if not isinstance(c, dict) or not c.get("id"):
            findings.append(f"categories: id 欠落エントリ ({c!r})")
            continue
        cat_ids.append(c["id"])

    # カテゴリ軸床: goal-spec 例示カテゴリを最低含むか除外根拠 (excluded_categories) を持つ
    excluded = set(data.get("excluded_categories", {}) or {})
    missing_cat = [
        g for g in GOAL_SPEC_CATEGORIES if g not in cat_ids and g not in excluded
    ]
    if missing_cat:
        findings.append(
            f"カテゴリ軸床: goal-spec 例示カテゴリ {missing_cat} が未定義かつ除外根拠 (excluded_categories) 無し"
        )

    qa_ids = {e.get("id") for e in data.get("qa_log", []) if isinstance(e, dict)}
    approval_ids = {e.get("id") for e in data.get("approval_log", []) if isinstance(e, dict)}
    ref_ids = qa_ids | approval_ids

    unresolved = 0
    for cat_id in cat_ids:
        row = matrix.get(cat_id)
        if not isinstance(row, dict):
            findings.append(f"matrix[{cat_id}]: 行が存在しない/オブジェクトでない")
            continue

        # 必須プラットフォーム行の全存在
        missing_pf = [p for p in CANONICAL_PLATFORMS if p not in row]
        if missing_pf:
            findings.append(f"matrix[{cat_id}]: 必須 platform {missing_pf} が欠落")

        cells: list[str] = []
        for pf in CANONICAL_PLATFORMS:
            cell = row.get(pf)
            if cell is None:
                continue
            if not isinstance(cell, dict):
                findings.append(f"matrix[{cat_id}][{pf}]: セルがオブジェクトでない")
                continue
            state = cell.get("state")
            if state not in CELL_STATES:
                findings.append(
                    f"matrix[{cat_id}][{pf}]: state={state!r} が {sorted(CELL_STATES)} 外"
                )
                continue
            cells.append(state)
            if state == "未収集":
                unresolved += 1
            elif state == "対象外":
                if not (cell.get("reason") or cell.get("approval_ref") in approval_ids):
                    findings.append(
                        f"matrix[{cat_id}][{pf}]: 対象外だが reason も approval_ref も無い"
                    )
            elif state == "確定":
                qa_ref = cell.get("qa_ref")
                if not qa_ref:
                    findings.append(f"matrix[{cat_id}][{pf}]: 確定だが qa_ref が空")
                elif qa_ref not in ref_ids:
                    findings.append(
                        f"matrix[{cat_id}][{pf}]: 確定 qa_ref={qa_ref!r} が qa_log/approval_log に不在"
                    )

        # 集約状態の真理値表照合 (宣言があれば)
        declared = (data.get("category_aggregate") or {}).get(cat_id)
        if declared is not None and cells:
            derived = _derive_aggregate(cells)
            if declared != derived:
                findings.append(
                    f"matrix[{cat_id}]: category_aggregate={declared!r} が真理値表導出 {derived!r} と不一致"
                )

    if require_complete and unresolved:
        findings.append(f"未収集セルが {unresolved} 件残存 (最終時は未収集 0 が必須)")

    return findings


# 上位概念 (requirements_foundation) の検証対象キー (U1-U9)。
_FOUNDATION_REQUIRED = (
    ("essential_purpose", "U1 本質的目的"),
    ("background", "U2 背景"),
    ("goals", "U3 ゴール"),
    ("objectives", "U4 目標"),
    ("success_criteria", "U5 成功基準"),
    ("stakeholders", "U6 ステークホルダー"),
    ("scope", "U7 スコープ"),
    ("constraints", "U8 制約"),
    ("concrete_intents", "U9 具体的にやりたいこと"),
)


# U1-U3 (本質的目的/背景/ゴール) は N/A 不可 (値必須)。writer 側 FOUNDATION_NA_FORBIDDEN と同一契約。
_FOUNDATION_NA_FORBIDDEN = ("essential_purpose", "background", "goals")


def _is_explicit_na(value) -> bool:
    return (
        isinstance(value, dict)
        and value.get("status") == "not_applicable"
        and bool(str(value.get("reason") or "").strip())
    )


def _foundation_value_present(key: str, value) -> bool:
    if key not in _FOUNDATION_NA_FORBIDDEN and _is_explicit_na(value):
        return True
    if key in ("essential_purpose", "background"):
        return isinstance(value, str) and bool(value.strip())
    if key == "scope":
        return (
            isinstance(value, dict)
            and isinstance(value.get("in"), list)
            and isinstance(value.get("out"), list)
            and bool(value.get("in") or value.get("out"))
        )
    return isinstance(value, list) and bool(value)


def _is_nonempty_string_list(value) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _is_https_url(value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None


def _is_rfc3339(value) -> bool:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_cost_model(value, prefix: str) -> tuple[list[str], str | None]:
    findings: list[str] = []
    if not isinstance(value, dict):
        return [f"{prefix}: cost_model は object 必須"], None
    category = value.get("category")
    if category not in DECISION_COST_CATEGORIES:
        findings.append(f"{prefix}: cost_model.category={category!r} が許容値外")
        category = None
    amount = value.get("amount")
    if category == "unknown":
        if amount is not None and (
            isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0
        ):
            findings.append(f"{prefix}: cost_model.amount は非負数または null 必須")
    elif category is not None and (
        isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0
    ):
        findings.append(f"{prefix}: cost_model.amount は非負数必須")
    if category == "free" and amount != 0:
        findings.append(f"{prefix}: category=free の amount は 0 必須")
    if category in {"low-cost", "paid"} and amount == 0:
        findings.append(f"{prefix}: category={category} の amount は正数必須")
    for field in ("currency", "billing_period", "tco"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            findings.append(f"{prefix}: cost_model.{field} が空")
    return findings, category


def validate_decisions(data: dict, goal_ids: set[str]) -> list[str]:
    """decisions[] の比較・推奨・ユーザー確認・goal trace 契約を検証する。"""
    findings: list[str] = []
    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        return ["decisions: 配列が存在しない"]
    seen: set[str] = set()
    statuses = {"needs_guidance", "recommended_pending_confirmation", "confirmed"}
    option_fields = (
        "id", "label", "free_tier_limits", "goal_fit", "security_fit", "pros", "cons",
        "risks", "lock_in", "ops_burden", "evidence_refs",
    )
    for decision in decisions:
        if not isinstance(decision, dict):
            findings.append(f"decision: object でない ({decision!r})")
            continue
        did = decision.get("id")
        prefix = f"decision[{did or '?'}]"
        if not isinstance(did, str) or not did.strip():
            findings.append(f"{prefix}: id が空")
        elif did in seen:
            findings.append(f"{prefix}: id が重複")
        else:
            seen.add(did)
        if not str(decision.get("question") or "").strip():
            findings.append(f"{prefix}: question が空")
        status = decision.get("status")
        if status not in statuses:
            findings.append(f"{prefix}: status={status!r} が許容値外")
        serves = decision.get("serves_goals")
        if not isinstance(serves, list) or not serves:
            findings.append(f"{prefix}: serves_goals が空")
        else:
            dangling = [gid for gid in serves if gid not in goal_ids]
            if dangling:
                findings.append(f"{prefix}: serves_goals {dangling} が dangling")

        options = decision.get("options")
        option_ids: list[str] = []
        cost_categories: set[str] = set()
        if not isinstance(options, list) or not 2 <= len(options) <= 3:
            findings.append(f"{prefix}: options は2-3件必須")
            options = []
        for option in options:
            if not isinstance(option, dict):
                findings.append(f"{prefix}: option が object でない")
                continue
            for field in option_fields:
                value = option.get(field)
                if value is None or value == "" or value == []:
                    findings.append(f"{prefix}: option.{field} が空")
            cost_findings, cost_category = _validate_cost_model(
                option.get("cost_model"), f"{prefix}: option"
            )
            findings.extend(cost_findings)
            if cost_category:
                cost_categories.add(cost_category)
            for field in ("pros", "cons", "risks"):
                if not _is_nonempty_string_list(option.get(field)):
                    findings.append(f"{prefix}: option.{field} は非空文字列の配列必須")
            evidence_refs = option.get("evidence_refs")
            if not _is_nonempty_string_list(evidence_refs):
                findings.append(f"{prefix}: option.evidence_refs は非空文字列の配列必須")
            elif any(not _is_https_url(ref) for ref in evidence_refs):
                findings.append(f"{prefix}: option.evidence_refs は公式 https URL 必須")
            oid = option.get("id")
            if oid in option_ids:
                findings.append(f"{prefix}: option id {oid!r} が重複")
            elif oid:
                option_ids.append(oid)
        if options and not cost_categories.intersection({"free", "low-cost"}):
            findings.append(f"{prefix}: options には free または low-cost 候補が最低1件必須")

        recommendation = decision.get("recommendation")
        if status != "needs_guidance":
            if not isinstance(recommendation, dict):
                findings.append(f"{prefix}: recommendation が必須")
            else:
                for field in ("option_id", "rationale", "caveats", "confidence", "latest_checked_at"):
                    value = recommendation.get(field)
                    if value is None or value == "" or value == []:
                        findings.append(f"{prefix}: recommendation.{field} が空")
                if not _is_nonempty_string_list(recommendation.get("caveats")):
                    findings.append(f"{prefix}: recommendation.caveats は非空文字列の配列必須")
                comparison_basis = recommendation.get("comparison_basis")
                if not isinstance(comparison_basis, dict):
                    findings.append(f"{prefix}: recommendation.comparison_basis は object 必須")
                else:
                    for axis in DECISION_COMPARISON_AXES:
                        value = comparison_basis.get(axis)
                        if not isinstance(value, str) or not value.strip():
                            findings.append(
                                f"{prefix}: recommendation.comparison_basis.{axis} が空"
                            )
                if not _is_rfc3339(recommendation.get("latest_checked_at")):
                    findings.append(f"{prefix}: recommendation.latest_checked_at は RFC3339 必須")
                if recommendation.get("option_id") not in option_ids:
                    findings.append(f"{prefix}: recommendation.option_id が options に不在")

        user_decision = decision.get("user_decision")
        if status == "confirmed":
            if not isinstance(user_decision, dict):
                findings.append(f"{prefix}: confirmed には user_decision が必須")
            else:
                if user_decision.get("option_id") not in option_ids:
                    findings.append(f"{prefix}: user_decision.option_id が options に不在")
                if not str(user_decision.get("confirmed_at") or "").strip():
                    findings.append(f"{prefix}: user_decision.confirmed_at が空")
                elif not _is_rfc3339(user_decision.get("confirmed_at")):
                    findings.append(f"{prefix}: user_decision.confirmed_at は RFC3339 必須")
        elif user_decision:
            findings.append(f"{prefix}: ユーザー確認前に user_decision を記録している")
    return findings


def validate_foundation(data: dict) -> list[str]:
    """上位概念 (requirements_foundation) と serves_goals トレースを検証する (要件 C9・anti-drift)。

    検証内容 (opt-in; --require-foundation 時のみ):
      (a) requirements_foundation の U1-U9 が値あり (U1-U3 は N/A 不可)、または明示 N/A+理由で
          確定され、confirmed=true はユーザー合意の approval_ref (approval_log 実在) を伴う。
      (b) 各『確定』セルが serves_goals で 1 つ以上の実在する goal id へトレースされる。
      (c) どのゴールにも資さない確定セル (serves_goals 無し = drift 候補) を surface。
    上位概念がブレると仕様が整ってもブレるため、収集を上位概念へ機械的に結び付ける。
    """
    findings: list[str] = []
    rf = data.get("requirements_foundation")
    if not isinstance(rf, dict):
        findings.append(
            "requirements_foundation: オブジェクトが存在しない (上位概念 U1-U9 が未抽出)"
        )
        return findings

    # (a) U1-U9 が値あり、または明示 N/A+理由
    goal_ids: list[str] = []
    for key, label in _FOUNDATION_REQUIRED:
        val = rf.get(key)
        if not _foundation_value_present(key, val):
            findings.append(
                f"requirements_foundation: {label}({key}) が空 (値または明示 N/A+理由が必須)"
            )
    if not rf.get("confirmed"):
        findings.append("requirements_foundation: confirmed=true でない")
    else:
        # confirmed はユーザー合意の approval_log 参照が必須 (writer の approval_ref と同一契約)
        approval_ids = {
            e.get("id") for e in data.get("approval_log", []) if isinstance(e, dict)
        }
        approval_ref = rf.get("approval_ref")
        if not (isinstance(approval_ref, str) and approval_ref.strip()):
            findings.append(
                "requirements_foundation: confirmed だが approval_ref (ユーザー合意) が空"
            )
        elif approval_ref not in approval_ids:
            findings.append(
                f"requirements_foundation: approval_ref={approval_ref!r} が approval_log に不在"
            )
    goals = rf.get("goals") or []
    if _is_explicit_na(goals):
        goals = []
    for g in goals:
        if isinstance(g, dict) and g.get("id"):
            goal_ids.append(g["id"])
            if not str(g.get("text") or "").strip():
                findings.append(f"requirements_foundation: goal {g['id']!r} の text が空")
        else:
            findings.append(f"requirements_foundation: goal に id 欠落 ({g!r})")

    # (b)(c) 各確定セルの serves_goals トレース (実在 goal へ ≥1 / drift 候補の surface)
    goal_id_set = set(goal_ids)
    matrix = data.get("matrix")
    if isinstance(matrix, dict):
        for cat_id, row in matrix.items():
            if not isinstance(row, dict):
                continue
            for pf, cell in row.items():
                if not isinstance(cell, dict) or cell.get("state") != "確定":
                    continue
                serves = cell.get("serves_goals")
                if not isinstance(serves, list) or not serves:
                    findings.append(
                        f"drift 候補: 確定セル {cat_id}.{pf} が serves_goals を持たず"
                        " どのゴールにも資さない (上位概念へ未トレース)"
                    )
                    continue
                dangling = [s for s in serves if s not in goal_id_set]
                if dangling:
                    findings.append(
                        f"matrix[{cat_id}][{pf}]: serves_goals {dangling} が実在 goal を指さない (dangling)"
                    )
    findings += validate_decisions(data, goal_id_set)
    return findings


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="収集マトリクス網羅性の決定論検証 (goal-spec C7)")
    ap.add_argument("--matrix", required=True, help="spec-state.json のパス")
    ap.add_argument(
        "--require-complete",
        action="store_true",
        help="最終時: 未収集セル 0 を必須にする (OUT1/C7 受入)",
    )
    ap.add_argument(
        "--require-foundation",
        action="store_true",
        help="上位概念 (requirements_foundation U1-U9 値ありまたは明示N/A)・decisions・goalトレースを検証 (C9・opt-in)",
    )
    args = ap.parse_args(argv)

    path = Path(args.matrix)
    if not path.is_file():
        print(f"matrix ファイルが存在しない: {args.matrix}", file=sys.stderr)
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"matrix ファイルの JSON parse 失敗: {exc}", file=sys.stderr)
        return 2

    findings = validate(data, require_complete=args.require_complete)
    if args.require_foundation:
        findings += validate_foundation(data)
    if findings:
        for f in findings:
            print(f"VIOLATION: {f}", file=sys.stderr)
        print(f"FAIL: {len(findings)} 件の網羅性違反", file=sys.stderr)
        return 1
    mode = "final(未収集0)" if args.require_complete else "loop"
    if args.require_foundation:
        mode += "+foundation(上位概念トレース)"
    print(f"OK: 収集マトリクス網羅性 ({mode}) を満たす")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
