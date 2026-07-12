#!/usr/bin/env python3
# /// script
# name: apply-spec-transition
# version: 0.1.0
# purpose: run-system-spec-elicit が所有する spec-state.json の単一 transition writer。カテゴリ×platform セルの 未収集/対象外/確定 遷移を規則付きで適用し、確定セルの直接巻き戻し (rollback) を Bash/script 経由でも拒否し、R4-reopen 経由のみ確定変更を許す。goal-seek chunk (per-invocation max_loops) の状態保存/resume も担う。
# inputs:
#   - argv: init|apply|chunk|aggregate サブコマンドと --state/--taxonomy/--op/--turns/--out/--max-loops
# outputs:
#   - spec-state.json (stdout or --out)
#   - exit: 0=OK / 1=TransitionError or IO / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: spec-state.json (単一 writer)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""spec-state.json の単一 transition writer (run-system-spec-elicit 所有)。

本モジュールは spec-state.json への **唯一の書込経路** である。確定 (確定) セルの
状態を変更できるのは action="reopen" (R4-reopen) だけであり、confirm / exclude が
確定セルを対象にすると TransitionError で拒否する。これにより Bash や別 script から
CLI を叩いても確定状態の直接巻き戻し (rollback) は起こせない (single-writer 防御)。

spec-state.json 形状は plugin 共有契約 (SKILL.md / validate-coverage-matrix.py と一致):
  categories / platforms / matrix / qa_log / approval_log / category_aggregate /
  targets / requirements_foundation / decisions / hearing_progress。集約状態は真理値表から導出する (直接指定不可)。

要件 C9 (上位概念 anchor): top-level ``requirements_foundation`` (本質的目的 U1 / 背景 U2 /
ゴール U3 / 目標 U4 / 成功基準 U5 / ステークホルダー U6 / スコープ U7 / 制約 U8 /
具体的やりたいこと U9) をカテゴリ×platform マトリクス収集の**手前**で確定する。書込は
``set-foundation`` op の一経路のみ。確定条件は (1) U1-U3 は値必須・U4-U9 は値または明示 N/A+理由、
かつ (2) ユーザー合意の機械証跡として ``approval_ref`` が ``approval_log`` に実在すること
(cell exclude の approval_ref と対称)。各確定セルは ``serves_goals: [<goal_id>, ...]``
(confirm 付随 or ``set-serves`` op) で上位概念へトレース (anchor) し、どのゴールにも資さない収集を
drift として検証側 (validate) が surface する。
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

CANONICAL_PLATFORMS = (
    "web",
    "mobile",
    "tablet",
    "desktop-windows",
    "desktop-linux",
    "desktop-macos",
)
PLATFORM_LABELS = {
    "web": "Web",
    "mobile": "モバイル",
    "tablet": "タブレット",
    "desktop-windows": "デスクトップ (Windows)",
    "desktop-linux": "デスクトップ (Linux)",
    "desktop-macos": "デスクトップ (macOS)",
}
CELL_STATES = {"未収集", "対象外", "確定"}
MAX_LOOPS_DEFAULT = 5

# 要件 C9: requirements_foundation (上位概念) の U1-U9 実体キー。
FOUNDATION_U_KEYS = (
    "essential_purpose",  # U1 本質的目的
    "background",         # U2 背景
    "goals",              # U3 ゴール
    "objectives",         # U4 目標
    "success_criteria",   # U5 成功基準
    "stakeholders",       # U6 ステークホルダー
    "scope",              # U7 スコープ (in/out)
    "constraints",        # U8 制約
    "concrete_intents",   # U9 具体的にやりたいこと
)
# U1-U3 (本質的目的/背景/ゴール) は N/A 不可 (値必須)。"目的が N/A のシステム" を弾く。
FOUNDATION_NA_FORBIDDEN = ("essential_purpose", "background", "goals")
# set-foundation が受理する全キー: U1-U9 + 確定フラグ + ユーザー合意の承認参照。未知キーは弾く。
FOUNDATION_KEYS = FOUNDATION_U_KEYS + ("confirmed", "approval_ref")
DECISION_STATUSES = {
    "needs_guidance",
    "recommended_pending_confirmation",
    "confirmed",
}
DECISION_OPTION_FIELDS = (
    "id",
    "label",
    "cost_model",
    "free_tier_limits",
    "goal_fit",
    "security_fit",
    "pros",
    "cons",
    "risks",
    "lock_in",
    "ops_burden",
    "evidence_refs",
)
DECISION_COST_CATEGORIES = {"free", "low-cost", "paid", "unknown"}
DECISION_COMPARISON_AXES = ("goal_fit", "tco", "security", "operations", "lock_in")
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class TransitionError(Exception):
    """禁止された遷移 (確定巻き戻し等) を検出したときに送出する。"""


# --------------------------------------------------------------------------- #
# 集約状態 (真理値表)                                                          #
# --------------------------------------------------------------------------- #
def derive_aggregate(cells: list[str]) -> str:
    """セル状態集合からカテゴリ集約状態を真理値表で導出する。

    全セル未収集 -> 未着手 / 全セル対象外 -> 対象外 /
    未収集混在 -> 収集中 / それ以外で未収集0 -> 確定。
    validate-coverage-matrix.py の _derive_aggregate と同一定義 (SSOT 整合)。
    """
    if not cells:
        return "未着手"
    if all(c == "未収集" for c in cells):
        return "未着手"
    if all(c == "対象外" for c in cells):
        return "対象外"
    if any(c == "未収集" for c in cells):
        return "収集中"
    return "確定"


def _row_states(state: dict, cat_id: str) -> list[str]:
    row = state["matrix"][cat_id]
    return [row[pf]["state"] for pf in CANONICAL_PLATFORMS if pf in row]


def recompute_aggregates(state: dict) -> None:
    """category_aggregate を真理値表から再計算して state を更新する。"""
    agg = {}
    for cat in state["categories"]:
        agg[cat["id"]] = derive_aggregate(_row_states(state, cat["id"]))
    state["category_aggregate"] = agg


def count_unresolved(state: dict) -> int:
    """未収集セルの総数を返す。"""
    total = 0
    for row in state["matrix"].values():
        for cell in row.values():
            if cell.get("state") == "未収集":
                total += 1
    return total


# --------------------------------------------------------------------------- #
# 初期化 (R1-init)                                                             #
# --------------------------------------------------------------------------- #
def bootstrap_state() -> dict:
    """R0 を matrix 初期化より先に実行できる最小 state envelope を返す。"""
    return {
        "schema_version": "1.0",
        "categories": [],
        "platforms": [],
        "matrix": {},
        "qa_log": [],
        "approval_log": [],
        "reopen_log": [],
        "category_aggregate": {},
        "targets": [],
        "requirements_foundation": empty_foundation(),
        "decisions": [],
        "knowledge_candidates": [],
        "hearing_progress": {"loop_count": 0, "next_question": None, "complete": False},
    }


def init_state(taxonomy: dict, existing_state: dict | None = None) -> dict:
    """C04 taxonomy からカテゴリ×必須platform マトリクスを初期化する。

    必須 platform 行 (CANONICAL_PLATFORMS) の全存在を検証し、欠落があれば
    TransitionError を送出する (R1-init の必須行全存在検証)。
    """
    tax_platforms = [p["id"] for p in taxonomy.get("platforms", [])]
    missing = [p for p in CANONICAL_PLATFORMS if p not in tax_platforms]
    if missing:
        raise TransitionError(f"taxonomy に必須 platform {missing} が欠落")
    cats = [{"id": c["id"], "label": c["label"]} for c in taxonomy["categories"]]
    matrix = {
        c["id"]: {pf: {"state": "未収集"} for pf in CANONICAL_PLATFORMS} for c in cats
    }
    prior = existing_state if isinstance(existing_state, dict) else {}
    state: dict = {
        "schema_version": prior.get("schema_version", "1.0"),
        "categories": cats,
        "platforms": list(CANONICAL_PLATFORMS),
        "matrix": matrix,
        "qa_log": list(prior.get("qa_log") or []),
        "approval_log": list(prior.get("approval_log") or []),
        "reopen_log": list(prior.get("reopen_log") or []),
        "category_aggregate": {},
        "targets": list(prior.get("targets") or []),
        "requirements_foundation": dict(
            prior.get("requirements_foundation") or empty_foundation()
        ),
        "decisions": list(prior.get("decisions") or []),
        "knowledge_candidates": list(prior.get("knowledge_candidates") or []),
        "hearing_progress": {"loop_count": 0, "next_question": None, "complete": False},
    }
    recompute_aggregates(state)
    state["hearing_progress"]["next_question"] = next_unresolved_question(state)
    return state


# --------------------------------------------------------------------------- #
# セル遷移 (単一 writer 防御の中核)                                            #
# --------------------------------------------------------------------------- #
def _cell(state: dict, cat: str, pf: str) -> dict:
    if cat not in state["matrix"]:
        raise TransitionError(f"未知カテゴリ: {cat}")
    if pf not in state["matrix"][cat]:
        raise TransitionError(f"未知 platform: {pf} (カテゴリ {cat})")
    return state["matrix"][cat][pf]


def apply_cell_op(state: dict, op: dict) -> None:
    """1 セルの遷移を規則付きで適用する (state を破壊的に更新)。

    規則:
      - reopen: 現在が確定のときだけ許可し、reason 必須。未収集へ戻す。
      - set-serves: 確定セルにのみ許可。serves_goals (上位概念トレース) を付与する
        (state は 確定 のまま変えないため rollback 防御には抵触しない = additive anchor)。
      - confirm / exclude: 対象セルが確定なら TransitionError (rollback 拒否)。
        確定変更は必ず reopen を先に経由すること。
      - confirm は qa_ref 必須 (任意で serves_goals を同時付与可)、exclude は reason か approval_ref 必須。
    """
    action = op.get("action")
    cat, pf = op.get("category"), op.get("platform")
    cell = _cell(state, cat, pf)
    cur = cell.get("state")

    if action == "reopen":
        if cur != "確定":
            raise TransitionError(
                f"reopen 不可: {cat}/{pf} は '{cur}' (確定セルのみ reopen できる)"
            )
        reason = op.get("reason")
        if not reason:
            raise TransitionError(f"reopen には reason が必須: {cat}/{pf}")
        state.setdefault("reopen_log", []).append(
            {"category": cat, "platform": pf, "reason": reason, "from": "確定"}
        )
        state["matrix"][cat][pf] = {
            "state": "未収集",
            "reopened_from": "確定",
            "reopen_reason": reason,
        }
        return

    if action == "set-serves":
        # 確定セルへ上位概念トレース (serves_goals) を additive 付与する (要件 C9 anchor)。
        # state=確定 を保つため rollback 防御には抵触しない。未確定セルへの付与は不可。
        if cur != "確定":
            raise TransitionError(
                f"set-serves 不可: {cat}/{pf} は '{cur}' (確定セルのみ serves_goals を付与できる)"
            )
        serves = _normalize_serves(op.get("serves_goals"))
        if not serves:
            raise TransitionError(f"set-serves には非空 serves_goals が必須: {cat}/{pf}")
        cell["serves_goals"] = serves
        return

    # confirm / exclude は確定セルへの直接変更を拒否する (single-writer rollback 防御)
    if cur == "確定":
        raise TransitionError(
            f"確定セルの直接変更は拒否: {cat}/{pf}。変更は R4-reopen を経由すること"
        )

    if action == "confirm":
        qa_ref = op.get("qa_ref")
        if not qa_ref:
            raise TransitionError(f"confirm には qa_ref が必須: {cat}/{pf}")
        newcell: dict = {"state": "確定", "qa_ref": qa_ref}
        serves = _normalize_serves(op.get("serves_goals"))
        if serves:
            newcell["serves_goals"] = serves
        state["matrix"][cat][pf] = newcell
    elif action == "exclude":
        reason = op.get("reason")
        approval_ref = op.get("approval_ref")
        if not (reason or approval_ref):
            raise TransitionError(
                f"exclude には reason か approval_ref が必須: {cat}/{pf}"
            )
        newcell: dict = {"state": "対象外"}
        if reason:
            newcell["reason"] = reason
        if approval_ref:
            newcell["approval_ref"] = approval_ref
        state["matrix"][cat][pf] = newcell
    else:
        raise TransitionError(f"未知 action: {action!r}")


def set_targets(state: dict, targets: list) -> None:
    """取得対象一覧 targets[] を設定する (単一 writer の唯一の targets 書込経路)。

    consumer (validate-source-citation.py / compile-spec-doc.py) が期待する形状へ正規化する。
    各 target は ``{"target_id": str[, "category": str]}`` または str (target_id) を受け付け、
    target_id 欠落/空・重複は TransitionError。category は任意 (compile の章割当に使う)。
    apply-spec-transition.py 以外は spec-state を書き換えない不変則を保つため、targets も
    本経路経由でのみ設定する。
    """
    if not isinstance(targets, list):
        raise TransitionError(f"targets は配列でない: {targets!r}")
    normalized: list[dict] = []
    seen: set[str] = set()
    for t in targets:
        if isinstance(t, str):
            tid, cat = t, None
        elif isinstance(t, dict):
            tid, cat = t.get("target_id"), t.get("category")
        else:
            raise TransitionError(f"target は str か object でない: {t!r}")
        if not tid:
            raise TransitionError(f"target に target_id が必須: {t!r}")
        if tid in seen:
            raise TransitionError(f"target_id が重複: {tid!r}")
        seen.add(tid)
        entry: dict = {"target_id": tid}
        if cat:
            entry["category"] = cat
        normalized.append(entry)
    state["targets"] = normalized


# --------------------------------------------------------------------------- #
# requirements_foundation (上位概念・要件 C9) の単一 writer 経路                #
# --------------------------------------------------------------------------- #
def empty_foundation() -> dict:
    """空の requirements_foundation を返す (init_state が埋める初期値)。

    U1-U9 を空・confirmed=False で初期化する。上位概念が未抽出であることを表し、
    validate 側 (--require-foundation) はこの空状態を「上位概念未確定」として弾く。
    """
    return {
        "essential_purpose": "",
        "background": "",
        "goals": [],
        "objectives": [],
        "success_criteria": [],
        "stakeholders": [],
        "scope": {"in": [], "out": []},
        "constraints": [],
        "concrete_intents": [],
        "confirmed": False,
    }


def _normalize_serves(raw) -> list[str]:
    """serves_goals (goal id 列) を検証しつつ順序保持で重複除去する。

    None は空扱い (未指定)。非配列・非文字列/空要素は TransitionError。
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TransitionError(f"serves_goals は配列でない: {raw!r}")
    out: list[str] = []
    for gid in raw:
        if not isinstance(gid, str) or not gid.strip():
            raise TransitionError(f"serves_goals 要素は非空文字列でない: {gid!r}")
        if gid not in out:
            out.append(gid)
    return out


def _foundation_goal_ids(goals) -> list[str]:
    """goals[] を検証して goal id 列を返す (id 必須・重複禁止)。"""
    if not isinstance(goals, list):
        raise TransitionError("requirements_foundation.goals は配列でない")
    ids: list[str] = []
    for g in goals:
        if not isinstance(g, dict) or not g.get("id"):
            raise TransitionError(f"goal に id が必須: {g!r}")
        gid = g["id"]
        if gid in ids:
            raise TransitionError(f"goal id が重複: {gid!r}")
        ids.append(gid)
    return ids


def _is_explicit_na(value) -> bool:
    """明示 N/A marker (`status=not_applicable` + 非空 reason) を判定する。"""
    return (
        isinstance(value, dict)
        and value.get("status") == "not_applicable"
        and bool(str(value.get("reason") or "").strip())
    )


def _foundation_missing_fields(foundation: dict) -> list[str]:
    """U1-U9 の値なし・明示 N/A なしを列挙する。U1-U3 は N/A 不可 (値必須)。"""
    missing: list[str] = []
    for key in FOUNDATION_U_KEYS:
        value = foundation.get(key)
        if key not in FOUNDATION_NA_FORBIDDEN and _is_explicit_na(value):
            continue
        if key in ("essential_purpose", "background"):
            present = isinstance(value, str) and bool(value.strip())
        elif key == "scope":
            present = (
                isinstance(value, dict)
                and isinstance(value.get("in"), list)
                and isinstance(value.get("out"), list)
                and bool(value.get("in") or value.get("out"))
            )
        else:
            present = isinstance(value, list) and bool(value)
        if not present:
            missing.append(key)
    return missing


def set_foundation(state: dict, foundation: dict) -> None:
    """requirements_foundation (上位概念 U1-U9) を設定/確定する単一 writer 経路 (要件 C9)。

    - 既存 requirements_foundation へ渡された field をマージ (部分更新可・未知キーは拒否)。
    - goals は id 必須・重複禁止。concrete_intents.serves は実在 goal を指す (dangling 拒否)。
    - `confirmed: true` の確定条件 (上位概念のブレを機械で防ぐ):
        1. U1-U9 が値あり (U1-U3 は N/A 不可)、U4-U9 は明示 N/A+理由でも可。
        2. ユーザー合意の機械証跡として approval_ref が非空で approval_log に実在する
           (cell exclude の approval_ref と対称。承認なき確定を弾く)。
      approval_note を伴うときは approval_log へ idempotent 登録する (apply_turn と同じ機構)。
      approval_note はログ登録専用で requirements_foundation へは保存しない (本文は approval_log)。

    apply-spec-transition.py 以外は spec-state を書き換えない不変則を保つため、
    requirements_foundation も本経路経由でのみ設定する。
    """
    if not isinstance(foundation, dict):
        raise TransitionError(f"requirements_foundation は object でない: {foundation!r}")
    foundation = dict(foundation)
    # ユーザー合意の承認を approval_log へ idempotent 登録 (apply_turn の approval_id と同じ機構)。
    approval_note = foundation.pop("approval_note", None)
    approval_ref = foundation.get("approval_ref")
    if approval_ref and approval_note is not None:
        appr_log = state.setdefault("approval_log", [])
        if not _has_entry(appr_log, approval_ref):
            appr_log.append({"id": approval_ref, "note": approval_note})

    merged = dict(state.get("requirements_foundation") or empty_foundation())
    for k, v in foundation.items():
        if k not in FOUNDATION_KEYS:
            raise TransitionError(f"requirements_foundation の未知キー: {k!r}")
        merged[k] = v

    # scope 正規化 (in/out 配列を必ず持たせる)
    scope = merged.get("scope")
    if scope is None:
        scope = {"in": [], "out": []}
    if not isinstance(scope, dict):
        raise TransitionError("requirements_foundation.scope は object でない")
    if not _is_explicit_na(scope):
        scope.setdefault("in", [])
        scope.setdefault("out", [])
    merged["scope"] = scope

    # goals 構造検証 + concrete_intents.serves の dangling 拒否 (トレース健全性)
    goals = merged.get("goals", [])
    goal_ids = [] if _is_explicit_na(goals) else _foundation_goal_ids(goals)
    intents = merged.get("concrete_intents", []) or []
    if _is_explicit_na(intents):
        intents = []
    elif not isinstance(intents, list):
        raise TransitionError("requirements_foundation.concrete_intents は配列でない")
    for intent in intents:
        if not isinstance(intent, dict):
            raise TransitionError(f"concrete_intent は object でない: {intent!r}")
        for gid in intent.get("serves", []) or []:
            if gid not in goal_ids:
                raise TransitionError(
                    f"concrete_intent {intent.get('id')!r} の serves={gid!r} が実在 goal を指さない"
                )

    # 確定条件: U1-U9 (U1-U3 は値必須) かつ ユーザー合意の approval_log 参照 (上位概念ブレ防止の要)
    confirmed = bool(merged.get("confirmed"))
    if confirmed:
        missing = _foundation_missing_fields(merged)
        if missing:
            raise TransitionError(
                "確定条件不足: U1-U3 は値必須・U4-U9 は値または明示 N/A+理由が必須: "
                + ", ".join(missing)
            )
        appr = merged.get("approval_ref")
        if not (isinstance(appr, str) and appr.strip()):
            raise TransitionError(
                "確定条件不足: confirmed には approval_ref (ユーザー合意の approval_log 参照) が必須"
            )
        if not _has_entry(state.get("approval_log") or [], appr):
            raise TransitionError(
                f"確定条件不足: approval_ref={appr!r} が approval_log に不在 (承認証跡なし)"
            )
    merged["confirmed"] = confirmed
    state["requirements_foundation"] = merged


def _require_nonempty(value, label: str) -> None:
    if isinstance(value, str):
        ok = bool(value.strip())
    elif isinstance(value, list):
        ok = bool(value)
    else:
        ok = value is not None
    if not ok:
        raise TransitionError(f"decision: {label} が空")


def _require_nonempty_string_list(value, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise TransitionError(f"decision: {label} は非空配列必須")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise TransitionError(f"decision: {label} は非空文字列の配列必須")


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


def _validate_cost_model(value, label: str) -> str:
    """費用分類・金額・周期・TCO を検証し、費用分類を返す。"""
    if not isinstance(value, dict):
        raise TransitionError(f"decision: {label} は object 必須")
    category = value.get("category")
    if category not in DECISION_COST_CATEGORIES:
        raise TransitionError(
            f"decision: {label}.category={category!r} が許容値外 "
            f"({sorted(DECISION_COST_CATEGORIES)})"
        )
    amount = value.get("amount")
    if category == "unknown":
        if amount is not None and (
            isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0
        ):
            raise TransitionError(f"decision: {label}.amount は非負数または null 必須")
    elif isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        raise TransitionError(f"decision: {label}.amount は非負数必須")
    if category == "free" and amount != 0:
        raise TransitionError(f"decision: {label}.category=free の amount は 0 必須")
    if category in {"low-cost", "paid"} and amount == 0:
        raise TransitionError(f"decision: {label}.category={category} の amount は正数必須")
    for field in ("currency", "billing_period", "tco"):
        _require_nonempty(value.get(field), f"{label}.{field}")
    return category


def set_decision(state: dict, decision: dict) -> None:
    """意思決定支援 record を id 単位で upsert する単一 writer 経路。"""
    if not isinstance(decision, dict):
        raise TransitionError("decision は object でない")
    did = decision.get("id")
    _require_nonempty(did, "id")
    _require_nonempty(decision.get("question"), "question")
    status = decision.get("status")
    if status not in DECISION_STATUSES:
        raise TransitionError(f"decision: status={status!r} が許容値外")

    goal_ids = set(_foundation_goal_ids(
        (state.get("requirements_foundation") or {}).get("goals", [])
    ))
    serves = _normalize_serves(decision.get("serves_goals"))
    if not serves:
        raise TransitionError("decision: serves_goals は非空必須")
    dangling = [gid for gid in serves if gid not in goal_ids]
    if dangling:
        raise TransitionError(f"decision: serves_goals {dangling} が実在 goal を指さない")

    options = decision.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 3:
        raise TransitionError("decision: options は2-3件必須")
    option_ids: list[str] = []
    cost_categories: set[str] = set()
    for option in options:
        if not isinstance(option, dict):
            raise TransitionError("decision option は object 必須")
        for field in DECISION_OPTION_FIELDS:
            if field != "cost_model":
                _require_nonempty(option.get(field), f"option.{field}")
        cost_categories.add(_validate_cost_model(option.get("cost_model"), "option.cost_model"))
        for field in ("pros", "cons", "risks"):
            _require_nonempty_string_list(option.get(field), f"option.{field}")
        evidence_refs = option.get("evidence_refs")
        _require_nonempty_string_list(evidence_refs, "option.evidence_refs")
        if any(not _is_https_url(ref) for ref in evidence_refs):
            raise TransitionError("decision: option.evidence_refs は公式 https URL 必須")
        if option["id"] in option_ids:
            raise TransitionError(f"decision: option id 重複 {option['id']!r}")
        option_ids.append(option["id"])
    if not cost_categories.intersection({"free", "low-cost"}):
        raise TransitionError("decision: options には free または low-cost 候補が最低1件必須")

    recommendation = decision.get("recommendation")
    if status != "needs_guidance":
        if not isinstance(recommendation, dict):
            raise TransitionError("decision: recommendation が必須")
        for field in (
            "option_id", "rationale", "caveats", "confidence", "latest_checked_at"
        ):
            _require_nonempty(recommendation.get(field), f"recommendation.{field}")
        _require_nonempty_string_list(recommendation.get("caveats"), "recommendation.caveats")
        comparison_basis = recommendation.get("comparison_basis")
        if not isinstance(comparison_basis, dict):
            raise TransitionError("decision: recommendation.comparison_basis は object 必須")
        for axis in DECISION_COMPARISON_AXES:
            _require_nonempty(
                comparison_basis.get(axis), f"recommendation.comparison_basis.{axis}"
            )
        if not _is_rfc3339(recommendation.get("latest_checked_at")):
            raise TransitionError("decision: recommendation.latest_checked_at は RFC3339 必須")
        if recommendation["option_id"] not in option_ids:
            raise TransitionError("decision: recommendation.option_id が options に不在")

    user_decision = decision.get("user_decision")
    if status == "confirmed":
        if not isinstance(user_decision, dict):
            raise TransitionError("decision: confirmed には user_decision が必須")
        _require_nonempty(user_decision.get("option_id"), "user_decision.option_id")
        _require_nonempty(user_decision.get("confirmed_at"), "user_decision.confirmed_at")
        if not _is_rfc3339(user_decision.get("confirmed_at")):
            raise TransitionError("decision: user_decision.confirmed_at は RFC3339 必須")
        if user_decision["option_id"] not in option_ids:
            raise TransitionError("decision: user_decision.option_id が options に不在")
    elif user_decision:
        raise TransitionError("decision: AI推奨だけで confirmed にせずユーザー確認を待つこと")

    normalized = dict(decision)
    normalized["serves_goals"] = serves
    records = list(state.get("decisions") or [])
    for i, current in enumerate(records):
        if isinstance(current, dict) and current.get("id") == did:
            records[i] = normalized
            break
    else:
        records.append(normalized)
    state["decisions"] = records


def _has_entry(log: list[dict], entry_id: str) -> bool:
    return any(e.get("id") == entry_id for e in log)


def apply_turn(state: dict, turn: dict) -> None:
    """1 ターン (質問→回答→反映) をまとめて適用する。

    turn.qa_id があれば qa_log へ、turn.approval_id があれば approval_log へ
    エントリを登録し、confirm op に qa_ref を、approval を伴う exclude op に
    approval_ref を補完してから各セル op を適用する。適用後に集約を再計算する。
    """
    qa_id = turn.get("qa_id")
    if qa_id and not _has_entry(state["qa_log"], qa_id):
        state["qa_log"].append(
            {
                "id": qa_id,
                "question": turn.get("question", ""),
                "answer": turn.get("answer", ""),
            }
        )
    appr_id = turn.get("approval_id")
    if appr_id and not _has_entry(state["approval_log"], appr_id):
        state["approval_log"].append(
            {"id": appr_id, "note": turn.get("approval_note", "")}
        )

    for op in turn.get("ops", []):
        op = dict(op)
        if op.get("action") == "confirm" and not op.get("qa_ref") and qa_id:
            op["qa_ref"] = qa_id
        if (
            op.get("action") == "exclude"
            and not op.get("reason")
            and not op.get("approval_ref")
            and appr_id
        ):
            op["approval_ref"] = appr_id
        apply_cell_op(state, op)

    recompute_aggregates(state)


def next_unresolved_question(state: dict) -> str | None:
    """最初の未収集セル (カテゴリ順→platform 正順) の質問文を導出する。"""
    label_by_id = {c["id"]: c["label"] for c in state["categories"]}
    for cat in state["categories"]:
        row = state["matrix"][cat["id"]]
        for pf in CANONICAL_PLATFORMS:
            cell = row.get(pf)
            if cell and cell.get("state") == "未収集":
                clabel = label_by_id.get(cat["id"], cat["id"])
                plabel = PLATFORM_LABELS.get(pf, pf)
                return (
                    f"{clabel}（{cat['id']}）× {plabel}（{pf}）は対象ですか? "
                    "対象なら要件を、非対象なら理由を教えてください。"
                )
    return None


def run_chunk(state: dict, turns: list[dict], max_loops: int = MAX_LOOPS_DEFAULT) -> int:
    """1 invocation ぶん (最大 max_loops ターン) を適用し、状態を保存可能にする。

    max_loops 到達で未収集が残れば hearing_progress.complete=false・next_question
    非 null を保存して resumable にする。未収集 0 のときだけ complete=true。
    未収集セルは完了扱いしない。処理ターン数を返す。
    """
    processed = 0
    state["hearing_progress"]["loop_count"] = 0
    for turn in turns:
        if processed >= max_loops:
            break
        apply_turn(state, turn)
        processed += 1
        state["hearing_progress"]["loop_count"] = processed

    unresolved = count_unresolved(state)
    if unresolved == 0:
        state["hearing_progress"]["complete"] = True
        state["hearing_progress"]["next_question"] = None
    else:
        state["hearing_progress"]["complete"] = False
        state["hearing_progress"]["next_question"] = next_unresolved_question(state)
    recompute_aggregates(state)
    return processed


# --------------------------------------------------------------------------- #
# KNOWLEDGE_CANDIDATES_EXTENSION_C                                             #
# seed 外 knowledge candidate の単一 writer / lifecycle                       #
# --------------------------------------------------------------------------- #
KNOWLEDGE_CANDIDATE_STATUSES = (
    "discovered",
    "qualified",
    "deepened",
    "promoted",
)
KNOWLEDGE_CARD_REQUIRED_FIELDS = (
    "purpose",
    "background",
    "problems",
    "core_concepts",
    "applies_when",
    "does_not_apply_when",
    "tradeoffs",
    "failure_modes",
    "goal_contribution",
    "primary_sources",
    "freshness",
)
_KNOWLEDGE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _require_candidate_value(value, label: str) -> None:
    if isinstance(value, str):
        valid = bool(value.strip())
    elif isinstance(value, (list, dict)):
        valid = bool(value)
    else:
        valid = value is not None
    if not valid:
        raise TransitionError(f"knowledge candidate: {label} が空")


def _validate_candidate_sources(source_refs: object) -> None:
    """qualified 以降の根拠を、公式/一次 HTTPS + 確認時刻に限定する。"""
    if not isinstance(source_refs, list) or not source_refs:
        raise TransitionError("knowledge candidate: qualified 以降は source_refs が非空必須")
    for index, source in enumerate(source_refs):
        if not isinstance(source, dict):
            raise TransitionError(f"knowledge candidate: source_refs[{index}] は object 必須")
        url = source.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise TransitionError(
                f"knowledge candidate: source_refs[{index}].url は HTTPS 必須"
            )
        if source.get("official_or_primary") is not True:
            raise TransitionError(
                f"knowledge candidate: source_refs[{index}] は official_or_primary=true 必須"
            )
        _require_candidate_value(source.get("checked_at"), f"source_refs[{index}].checked_at")


def _validate_deep_knowledge_card(card: object) -> None:
    """C04 deep-card の意味フィールドを candidate の deepened 以降でも強制する。"""
    if not isinstance(card, dict):
        raise TransitionError("knowledge candidate: deepened 以降は card object 必須")
    for field in KNOWLEDGE_CARD_REQUIRED_FIELDS:
        _require_candidate_value(card.get(field), f"card.{field}")
    primary_sources = card.get("primary_sources")
    if not isinstance(primary_sources, list):
        raise TransitionError("knowledge candidate: card.primary_sources は配列必須")
    for index, source in enumerate(primary_sources):
        if not isinstance(source, dict):
            raise TransitionError(
                f"knowledge candidate: card.primary_sources[{index}] は object 必須"
            )
        locator = source.get("locator")
        if not isinstance(locator, str) or not locator.startswith("https://"):
            raise TransitionError(
                f"knowledge candidate: card.primary_sources[{index}].locator は HTTPS 必須"
            )


def set_knowledge_candidate(state: dict, candidate: dict) -> None:
    """seed 外 candidate を stable id で upsertし、前進方向の状態遷移だけを許可する。"""
    if not isinstance(candidate, dict):
        raise TransitionError("knowledge candidate は object 必須")
    candidate_id = candidate.get("id")
    if not isinstance(candidate_id, str) or not _KNOWLEDGE_ID_RE.fullmatch(candidate_id):
        raise TransitionError("knowledge candidate: id は kebab-case の stable id 必須")
    for field in ("topic", "status", "problem", "serves_goals"):
        _require_candidate_value(candidate.get(field), field)
    status = candidate.get("status")
    if status not in KNOWLEDGE_CANDIDATE_STATUSES:
        raise TransitionError(f"knowledge candidate: status={status!r} が許容値外")
    if not isinstance(candidate.get("source_refs"), list):
        raise TransitionError("knowledge candidate: source_refs は配列必須")

    serves = _normalize_serves(candidate.get("serves_goals"))
    goal_ids = set(
        _foundation_goal_ids((state.get("requirements_foundation") or {}).get("goals", []))
    )
    dangling = [goal_id for goal_id in serves if goal_id not in goal_ids]
    if dangling:
        raise TransitionError(
            f"knowledge candidate: serves_goals {dangling} が実在 goal を指さない"
        )

    status_index = KNOWLEDGE_CANDIDATE_STATUSES.index(status)
    if status_index >= KNOWLEDGE_CANDIDATE_STATUSES.index("qualified"):
        _validate_candidate_sources(candidate.get("source_refs"))
    if status_index >= KNOWLEDGE_CANDIDATE_STATUSES.index("deepened"):
        _validate_deep_knowledge_card(candidate.get("card"))
    if status == "promoted":
        _require_candidate_value(candidate.get("curation_ref"), "curation_ref")

    records = list(state.get("knowledge_candidates") or [])
    existing_index: int | None = None
    for index, current in enumerate(records):
        if isinstance(current, dict) and current.get("id") == candidate_id:
            existing_index = index
            if current.get("topic") != candidate.get("topic"):
                raise TransitionError("knowledge candidate: stable topic は変更できない")
            current_status = current.get("status")
            if current_status not in KNOWLEDGE_CANDIDATE_STATUSES:
                raise TransitionError("knowledge candidate: 既存 status が不正")
            current_index = KNOWLEDGE_CANDIDATE_STATUSES.index(current_status)
            if status_index not in (current_index, current_index + 1):
                raise TransitionError(
                    "knowledge candidate: lifecycle は同一status更新または1段階前進のみ"
                )
            break
    if existing_index is None and status != "discovered":
        raise TransitionError("knowledge candidate: 新規 candidate は discovered から開始する")

    normalized = dict(candidate)
    normalized["serves_goals"] = serves
    if existing_index is None:
        records.append(normalized)
    else:
        records[existing_index] = normalized
    state["knowledge_candidates"] = records


# --------------------------------------------------------------------------- #
# IO / CLI                                                                     #
# --------------------------------------------------------------------------- #
def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_json_arg(raw: str):
    """JSON文字列またはファイルpathを安全に読む (長いJSONをpath扱いしない)。"""
    stripped = raw.lstrip()
    if stripped.startswith(("{", "[")):
        return json.loads(raw)
    return json.loads(Path(raw).read_text(encoding="utf-8"))


def dump_state(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


def _emit(state: dict, out: str | None) -> None:
    text = dump_state(state)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="spec-state.json 単一 transition writer (run-system-spec-elicit)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_boot = sub.add_parser("bootstrap", help="R0 用の空 state envelope を生成")
    p_boot.add_argument("--out")

    p_init = sub.add_parser("init", help="taxonomy からマトリクスを初期化")
    p_init.add_argument("--taxonomy", required=True)
    p_init.add_argument("--state", help="bootstrap済みstate (foundation/decisionsを保持)")
    p_init.add_argument("--out")

    p_apply = sub.add_parser("apply", help="単一セル op を適用")
    p_apply.add_argument("--state", required=True)
    p_apply.add_argument("--op", required=True, help="JSON 文字列の cell op")
    p_apply.add_argument("--out")

    p_chunk = sub.add_parser("chunk", help="ターン列を 1 invocation ぶん適用")
    p_chunk.add_argument("--state", required=True)
    p_chunk.add_argument("--turns", required=True, help="ターン列 JSON ファイル")
    p_chunk.add_argument("--max-loops", type=int, default=MAX_LOOPS_DEFAULT)
    p_chunk.add_argument("--out")

    p_agg = sub.add_parser("aggregate", help="集約状態を再計算")
    p_agg.add_argument("--state", required=True)
    p_agg.add_argument("--out")

    p_tgt = sub.add_parser("set-targets", help="取得対象一覧 targets[] を設定")
    p_tgt.add_argument("--state", required=True)
    p_tgt.add_argument(
        "--targets",
        required=True,
        help="targets の JSON 配列文字列、または JSON ファイルパス ([...] か {\"targets\": [...]})",
    )
    p_tgt.add_argument("--out")

    p_found = sub.add_parser(
        "set-foundation", help="requirements_foundation (上位概念 U1-U9) を設定/確定"
    )
    p_found.add_argument("--state", required=True)
    p_found.add_argument(
        "--foundation",
        required=True,
        help="requirements_foundation の JSON 文字列、または JSON ファイルパス",
    )
    p_found.add_argument("--out")

    p_decision = sub.add_parser("set-decision", help="意思決定支援 record を upsert")
    p_decision.add_argument("--state", required=True)
    p_decision.add_argument("--decision", required=True, help="decision JSON文字列またはファイル")
    p_decision.add_argument("--out")

    # KNOWLEDGE_CANDIDATES_EXTENSION_C: decision CLI と独立した単一 writer 入口。
    p_candidate = sub.add_parser(
        "set-knowledge-candidate", help="seed 外 knowledge candidate を lifecycle 付きで upsert"
    )
    p_candidate.add_argument("--state", required=True)
    p_candidate.add_argument(
        "--candidate", required=True, help="knowledge candidate JSON文字列またはファイル"
    )
    p_candidate.add_argument("--out")

    args = ap.parse_args(argv)

    try:
        if args.cmd == "bootstrap":
            _emit(bootstrap_state(), args.out)
        elif args.cmd == "init":
            existing = load_json(args.state) if args.state else None
            state = init_state(load_json(args.taxonomy), existing)
            _emit(state, args.out)
        elif args.cmd == "apply":
            state = load_json(args.state)
            apply_turn(state, {"ops": [json.loads(args.op)]})
            _emit(state, args.out or args.state)
        elif args.cmd == "chunk":
            state = load_json(args.state)
            turns = load_json(args.turns)
            run_chunk(state, turns, max_loops=args.max_loops)
            _emit(state, args.out or args.state)
        elif args.cmd == "aggregate":
            state = load_json(args.state)
            recompute_aggregates(state)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-targets":
            state = load_json(args.state)
            raw = args.targets
            targets = load_json_arg(raw)
            if isinstance(targets, dict) and "targets" in targets:
                targets = targets["targets"]
            set_targets(state, targets)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-foundation":
            state = load_json(args.state)
            raw = args.foundation
            foundation = load_json_arg(raw)
            set_foundation(state, foundation)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-decision":
            state = load_json(args.state)
            raw = args.decision
            decision = load_json_arg(raw)
            set_decision(state, decision)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-knowledge-candidate":
            state = load_json(args.state)
            candidate = load_json_arg(args.candidate)
            set_knowledge_candidate(state, candidate)
            _emit(state, args.out or args.state)
    except TransitionError as exc:
        print(f"TransitionError: {exc}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"IO/JSON error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
