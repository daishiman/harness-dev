#!/usr/bin/env python3
# /// script
# name: validate-coverage-matrix
# version: 0.1.0
# purpose: システム構成カテゴリ×canonical platform id の収集マトリクスの全セルが『未収集/対象外/確定』のいずれかで埋まり、対象外に理由・確定に qa_ref が付与され、必須プラットフォーム行が全存在し、カテゴリ集約状態が真理値表と一致し、参照先 ID (qa_log/approval_log/categories/goals) が一意であることを検証する決定論ゲート (goal-spec C7 の直接実装)。
# inputs:
#   - argv: --matrix FILE [--require-complete] [--require-basis] [--require-foundation]
# outputs:
#   - stdout: OK summary
#   - stderr: violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: [coverage_foundation.py]
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
  "qa_log": [{"id": "qa-001", ...}],          # 確定 qa_ref の参照先 (存在検証 + id 一意性検証)
  "approval_log": [{"id": "appr-001", ...}],  # 一括承認 (対象外/確定を承認ログ参照で代替可・id 一意)
  "category_aggregate": {"<category_id>": "確定"|"収集中"|"未着手"|"対象外"}  # 任意 (あれば真理値表照合)
}

集約状態の真理値表 (goal-spec C1 の 4 値):
  全セル未収集              -> 未着手
  未収集混在 (一部のみ未収集) -> 収集中
  全セル対象外              -> 対象外
  それ以外で未収集 0        -> 確定

ID 一意性 (fail-closed・既定で有効): qa_log / approval_log / categories / goals の id は参照先を
識別する前提なので、集合へ正規化する前に出現順で走査して重複を検出する。集合内包で組み立てると
重複 id が黙って 1 件へ畳み込まれ、二重採番が「参照先は実在する」という緑のまま通り抜ける
(issues/sys-qa-log-id-uniqueness-gate-20260726.md)。

要件 C9 (上位概念 anchor・opt-in): --require-foundation を付けると validate_foundation() が
requirements_foundation の U1-U5 非空・各『確定』セルの serves_goals トレース (実在 goal へ ≥1)・
どのゴールにも資さない確定セル (drift 候補) を追加検証する。既定 (--matrix / --require-complete) は
従来どおりで validate() を一切変えないため後方互換 (foundation 検証は完全にオプトイン)。
検証本体は同ディレクトリの coverage_foundation.py (import-only support module) にある。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 回答本文が引用する承認 id の形 (approval_log の canonical id は appr-NNN)。
_APPROVAL_ID_RE = re.compile(r"appr-\d+")

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from coverage_foundation import validate_foundation

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
DESIGN_APPLICATION_CONTRACT_VERSION = "1.0"
CURRENT_STATE_SCHEMA_VERSION = "1.1"
LEGACY_STATE_SCHEMA_VERSION = "1.0"
DESIGN_APPLICATION_STATES = {"applied", "not_applicable"}
LEGACY_BACKFILL_PROVENANCE = {
    "mode": "legacy_backfill",
    "writer": "set-qa-design-applications",
}


def _validate_design_application_provenance(entry: dict) -> list[str]:
    """qa の参照有無に関わらず事後補完の由来を検証する。"""
    qa_id = entry.get("id", "<unknown>")
    if "design_application_provenance" not in entry:
        return []
    provenance = entry["design_application_provenance"]
    if provenance == LEGACY_BACKFILL_PROVENANCE:
        return []
    return [
        f"qa_log[{qa_id}].design_application_provenance: "
        "legacy_backfill/set-qa-design-applications の完全一致が必須"
    ]


QA_SOURCE_KINDS = {
    "user-dialogue",
    "written-requirements",
    "harness-remediation",
    "derived-consolidation",
}


def _validate_qa_source_shape(entry: dict) -> list[str]:
    """qa entry の出所メタデータが契約形状であることを検証する。

    契約は ``source`` を object と定め ``kind`` を必須とするが、本ゲートは長らく ``source``
    を一度も参照していなかった。そのため素の文字列 (採番変更の注記など) が混入しても全ゲートが
    緑のまま通り、実際に監査 reader が型を前提に走査して途中で落ちる事故が起きた。

    出所は「その回答が利用者の一次入力か否か」を決める唯一の手掛かりなので、形状が壊れている
    ことは中立性監査と foundation trace の前提が崩れていることを意味する。source を持たない
    entry (schema 1.1 移行前の legacy) は別の経路が扱うため、ここでは非 None のみを検査する。
    """
    qa_id = entry.get("id", "<unknown>")
    source = entry.get("source")
    if source is None:
        return []
    if not isinstance(source, dict):
        return [
            f"qa_log[{qa_id}].source: object 必須 ({type(source).__name__} が混入)。"
            " 注記は source_note へ退避し set-qa-source で契約形状へ修復する"
        ]
    kind = source.get("kind")
    if kind not in QA_SOURCE_KINDS:
        return [f"qa_log[{qa_id}].source.kind={kind!r} は {sorted(QA_SOURCE_KINDS)} のいずれか必須"]
    return []


def _validate_design_applications(entry: dict) -> list[str]:
    """確定 qa の章固有設計解釈を fail-closed に検証する。"""
    qa_id = entry.get("id", "<unknown>")
    applications = entry.get("design_applications")
    if not isinstance(applications, list) or not applications:
        return [f"qa_log[{qa_id}]: design_applications は非空配列必須"]
    findings: list[str] = []
    for index, application in enumerate(applications):
        label = f"qa_log[{qa_id}].design_applications[{index}]"
        if not isinstance(application, dict):
            findings.append(f"{label}: object でない")
            continue
        for key in ("knowledge_ref", "principle", "rationale"):
            value = application.get(key)
            if not isinstance(value, str) or not value.strip():
                findings.append(f"{label}.{key}: 非空文字列でない")
        applicability = application.get("applicability")
        if applicability not in DESIGN_APPLICATION_STATES:
            findings.append(
                f"{label}.applicability={applicability!r}: applied|not_applicable でない"
            )
        tradeoffs = application.get("tradeoffs")
        if (
            not isinstance(tradeoffs, list)
            or not tradeoffs
            or any(not isinstance(value, str) or not value.strip() for value in tradeoffs)
        ):
            findings.append(f"{label}.tradeoffs: 非空文字列の配列でない")
    return findings


def _collect_unique_ids(entries, label: str) -> tuple[set[str], list[str]]:
    """id 付きエントリ列から一意な ID 集合を作り、id の欠落と重複を finding として返す。

    集合内包 ({e.get("id") for e in ...}) で組み立てると重複 id が黙って 1 件へ畳み込まれ、
    「参照先が一意か」という前提が検査される前に消える (= 二重採番の無検出)。
    正規化より先に検査するため、出現順に走査して重複を明示的に検出する。

    Returns:
        (一意な id の集合, findings)。findings が非空なら呼び出し側が違反として扱う。
    """
    findings: list[str] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}
    if not isinstance(entries, list):
        if entries is not None:
            findings.append(f"{label}: 配列でない")
        return seen, findings

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            findings.append(f"{label}[{i}]: エントリがオブジェクトでない")
            continue
        eid = entry.get("id")
        if not eid:
            findings.append(f"{label}[{i}]: id 欠落")
            continue
        if not isinstance(eid, str):
            findings.append(f"{label}[{i}]: id が文字列でない ({eid!r})")
            continue
        if eid in seen:
            counts[eid] = counts.get(eid, 1) + 1
        else:
            seen.add(eid)

    for eid in sorted(counts):
        findings.append(
            f"{label}: id={eid!r} が {counts[eid]} 件重複"
            " (ID が一意でなければ参照先を識別できない)"
        )
    return seen, findings


def _derive_aggregate(cells: list[str]) -> str:
    """セル状態集合から真理値表でカテゴリ集約状態を導出する。"""
    if all(c == "未収集" for c in cells):
        return "未着手"
    if all(c == "対象外" for c in cells):
        return "対象外"
    if any(c == "未収集" for c in cells):
        return "収集中"
    return "確定"


def validate(data: dict, require_complete: bool = False, require_basis: bool = False) -> list[str]:
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
        # 重複 category id は同一 matrix 行を二重評価し、片方の定義を静かに握り潰す
        if c["id"] in cat_ids:
            findings.append(f"categories: id={c['id']!r} が重複 (matrix 行が二重に評価される)")
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

    # 参照先 ID の一意性検査 (集合化で重複を潰す前に検査する)
    qa_ids, qa_findings = _collect_unique_ids(data.get("qa_log"), "qa_log")
    approval_ids, approval_findings = _collect_unique_ids(data.get("approval_log"), "approval_log")
    findings.extend(qa_findings)
    findings.extend(approval_findings)
    # 両ログは ref_ids へ統合されるため、ログを跨いだ id 衝突も参照先を一意に定められなくする
    collision = sorted(qa_ids & approval_ids)
    if collision:
        findings.append(
            f"qa_log/approval_log: id {collision} が両ログに重複 (qa_ref の参照先が一意に定まらない)"
        )
    ref_ids = qa_ids | approval_ids
    # 承認主張の突合用に qa_log entry の本文 (question + answer) を id 索引する。
    qa_entry_text: dict[str, str] = {}
    qa_entries: dict[str, dict] = {}
    for entry in data.get("qa_log") or []:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            qa_entries[entry["id"]] = entry
            qa_entry_text[entry["id"]] = " ".join(
                str(entry.get(key, "")) for key in ("question", "answer")
            )
            findings.extend(_validate_design_application_provenance(entry))
            findings.extend(_validate_qa_source_shape(entry))

    # supersede-qa の後継は qa_log 内の別 entry でなければならない (後継がさらに置き換えられる連鎖は正当)
    for qa_id, entry in qa_entries.items():
        superseded_by = entry.get("superseded_by")
        if superseded_by is None:
            continue
        if superseded_by == qa_id or superseded_by not in qa_entries:
            findings.append(
                f"qa_log[{qa_id}].superseded_by={superseded_by!r}: "
                "qa_log の別の entry を指す必要がある"
            )

    unresolved = 0
    reasons_by_category: dict[str, set[str]] = {}
    confirmed_qa_refs: set[str] = set()
    confirmed_non_qa_refs: set[str] = set()
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
        cat_reasons: set[str] = set()
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
                reason = cell.get("reason")
                if isinstance(reason, str) and reason.strip():
                    cat_reasons.add(reason.strip())
            elif state == "確定":
                qa_ref = cell.get("qa_ref")
                if not qa_ref:
                    findings.append(f"matrix[{cat_id}][{pf}]: 確定だが qa_ref が空")
                elif qa_ref not in ref_ids:
                    findings.append(
                        f"matrix[{cat_id}][{pf}]: 確定 qa_ref={qa_ref!r} が qa_log/approval_log に不在"
                    )
                elif qa_ref in qa_entries:
                    confirmed_qa_refs.add(qa_ref)
                    if qa_entries[qa_ref].get("superseded_by") is not None:
                        findings.append(
                            f"matrix[{cat_id}][{pf}]: 置き換え済み (retired) qa_ref={qa_ref!r} を"
                            " active consumer が参照している"
                        )
                else:
                    confirmed_non_qa_refs.add(qa_ref)
                approval_ref = cell.get("approval_ref")
                if approval_ref is not None and approval_ref not in approval_ids:
                    findings.append(
                        f"matrix[{cat_id}][{pf}]: 確定 approval_ref={approval_ref!r} が approval_log に不在"
                    )
                # 承認主張 × 承認記録の突合 (F-0025)。回答本文が承認 id を引用しているのに
                # セルに approval_ref が無いと、確定セルから承認記録へ機械追跡できない。
                # 誤検出を避けるため「承認」という語ではなく appr-NNN の明示引用だけを見る。
                if approval_ref is None and qa_ref in qa_entry_text:
                    cited = _APPROVAL_ID_RE.findall(qa_entry_text[qa_ref])
                    known = sorted({c for c in cited if c in approval_ids})
                    if known:
                        findings.append(
                            f"matrix[{cat_id}][{pf}]: 確定の根拠 {qa_ref} が承認 {known} を引用しているが "
                            f"セルに approval_ref が無い (set-approval op で付与すること)"
                        )

        reasons_by_category[cat_id] = cat_reasons

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

    if require_complete:
        schema_version = data.get("schema_version")
        marker_present = "design_application_contract_version" in data
        if not marker_present and schema_version != LEGACY_STATE_SCHEMA_VERSION:
            findings.append(
                "design_application_contract_version が欠落: schema 1.1 以降は "
                f"{DESIGN_APPLICATION_CONTRACT_VERSION!r} 必須"
            )
        if marker_present:
            version = data.get("design_application_contract_version")
        else:
            version = None
        if marker_present and version != DESIGN_APPLICATION_CONTRACT_VERSION:
            findings.append(
                "design_application_contract_version="
                f"{version!r} は {DESIGN_APPLICATION_CONTRACT_VERSION!r} 必須"
            )
        elif marker_present:
            for qa_ref in sorted(confirmed_non_qa_refs):
                findings.append(
                    f"確定 qa_ref={qa_ref!r}: schema 1.1 では design_applications を持つ "
                    "qa_log entry の参照が必須"
                )
            for qa_ref in sorted(confirmed_qa_refs):
                findings.extend(_validate_design_applications(qa_entries[qa_ref]))

    findings.extend(_boilerplate_reason_findings(reasons_by_category))
    findings.extend(_inference_only_findings(data, matrix, cat_ids, require_basis))
    return findings


# 回答の性質 (qa_log entry の basis)。詳細は spec-state-contract.md。
_INFERENCE = "agent-inference"


def _inference_only_findings(
    data: dict, matrix: dict, cat_ids: list[str], require_basis: bool
) -> list[str]:
    """確定セルが『アシスタントの推定』だけを根拠にしていないかを検査する。

    設計判断を利用者に確認せずアシスタントが決め、それが `確定` として仕様に載ると、
    利用者が選んだ結論と区別がつかなくなる。しかも矛盾しないので、どの決定論ゲートにも
    引っ掛からない。qa entry の `basis` を導入したことで、この区別が機械可読になった。

    `basis` を宣言している参照だけを見て判定するため、未宣言の既存 state を壊さない。
    「宣言しなければ検査されない」という抜け道は `--require-basis` が塞ぐ (確定セルの
    根拠に basis 宣言そのものを要求する)。既存 state へ一斉に backfill を強いないよう、
    既定では課さず、収集を閉じる側が明示的に有効化する。
    """
    findings: list[str] = []
    basis_by_qa = {
        e["id"]: e.get("basis")
        for e in data.get("qa_log", []) or []
        if isinstance(e, dict) and e.get("id")
    }
    for cat_id in cat_ids:
        row = matrix.get(cat_id)
        if not isinstance(row, dict):
            continue
        for pf, cell in row.items():
            if not isinstance(cell, dict) or cell.get("state") != "確定":
                continue
            refs = [cell["qa_ref"]] if cell.get("qa_ref") else []
            refs += [r for r in (cell.get("qa_refs") or []) if isinstance(r, str)]
            declared = [basis_by_qa[r] for r in refs if basis_by_qa.get(r)]
            if not declared:
                if require_basis and refs:
                    findings.append(
                        f"matrix[{cat_id}][{pf}]: 確定の根拠 {refs} が basis を宣言していない "
                        "(利用者決定・観測事実・推定の区別が付かない)"
                    )
                continue
            if all(b == _INFERENCE for b in declared):
                findings.append(
                    f"matrix[{cat_id}][{pf}]: 確定の根拠が {_INFERENCE} のみ "
                    f"({refs})。利用者確認 (user-decision) か検証可能な出典 "
                    "(observed-fact) を根拠に加えること"
                )
    return findings


def _boilerplate_reason_findings(reasons_by_category: dict[str, set[str]]) -> list[str]:
    """同一の対象外 reason が複数カテゴリに跨っていないかを検査する。

    カテゴリを跨いで byte 同一の理由文が使われている状態は、「そのカテゴリで何を諦めたか」を
    セルが一度も述べていないことと区別がつかない。除外の**共通根拠** (例: 対象 platform は
    web のみ) は approval_log の 1 箇所に置き、セルの `reason` には当該カテゴリ固有の帰結
    (そのカテゴリで本来収集したはずの事項と、その関心事をどこで代替して扱うか) を書く。
    共通根拠の複製で 40 セルを一律に埋めると、検討済みと未検討が同じ見た目になる。
    """
    findings: list[str] = []
    owners: dict[str, list[str]] = {}
    for cat_id, reasons in reasons_by_category.items():
        for reason in reasons:
            owners.setdefault(reason, []).append(cat_id)
    for reason, cats in owners.items():
        if len(cats) > 1:
            findings.append(
                f"対象外 reason がカテゴリ {sorted(cats)} で byte 同一 "
                f"(共通根拠は approval_log へ、reason にはカテゴリ固有の帰結を書くこと): "
                f"{reason[:60]!r}..."
            )
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
        "--require-basis",
        action="store_true",
        help="確定セルの根拠 qa_ref に basis 宣言 (user-decision/observed-fact/agent-inference) を必須にする (opt-in)",
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

    findings = validate(data, require_complete=args.require_complete, require_basis=args.require_basis)
    if args.require_foundation:
        findings += validate_foundation(data)
    if findings:
        for f in findings:
            print(f"VIOLATION: {f}", file=sys.stderr)
        print(f"FAIL: {len(findings)} 件の網羅性違反", file=sys.stderr)
        return 1
    mode = "final(未収集0)" if args.require_complete else "loop"
    if args.require_basis:
        mode += "+basis(根拠の性質宣言)"
    if args.require_foundation:
        mode += "+foundation(上位概念トレース)"
    print(f"OK: 収集マトリクス網羅性 ({mode}) を満たす")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
