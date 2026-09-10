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
from datetime import datetime, timezone
import json
import re
import sys
import unicodedata
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
        "design_applications": {},
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
        "design_applications": dict(prior.get("design_applications") or {}),
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

    if action == "set-design-application":
        # カテゴリ (章) 単位の op。platform を持たないのでセル解決の手前で処理する。
        _apply_design_application(state, cat, op)
        return

    if action == "set-doctrine-application":
        # 同じくカテゴリ単位。ただし (category, concern_id) の2軸で持つ。
        _apply_doctrine_application(state, cat, op)
        return

    if action == "add-reopen-correction":
        # reopen_log entry への追記専用 op。セルではなくログを対象にする。
        _add_reopen_correction(state, op)
        return

    if action == "correct-qa-timestamp":
        # qa_log entry の計測値時刻の訂正専用 op。同じくセルではなくログを対象にする。
        _correct_qa_timestamp(state, op)
        return

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
        # reopen は確定を巻き戻せる唯一の正規経路であり、いちばん時刻が要る操作である。
        # 時刻が無いと「差し替え後の主根拠がこの reopen より後に取り直された回答か」を
        # 検査できず、先に確定を壊してから既存の回答を主根拠に流用した場合と、正当に
        # 取り直した場合が同じ見た目になる。writer 自身が now() で埋めると書込時刻が
        # 実施時刻を騙るため、他の時刻と同じく呼び出し側の実測値を要求する。
        reopened_at = op.get("reopened_at")
        _require_past_rfc3339(reopened_at, f"reopen[{cat}/{pf}].reopened_at")
        state.setdefault("reopen_log", []).append(
            {
                "category": cat,
                "platform": pf,
                "reason": reason,
                "from": "確定",
                "reopened_at": reopened_at,
            }
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

    if action == "add-qa-ref":
        # 確定セルへ根拠参照 (qa_refs) を additive 追記する。
        # state=確定 を保つため rollback 防御に抵触せず、reopen->confirm と違って
        # required_info / required_info_checks を落とさない。serves_goals が「どの目的に
        # 資するか」を示すのに対し、qa_refs は「その主張がどの質疑に遡れるか」を示す。
        if cur != "確定":
            raise TransitionError(
                f"add-qa-ref 不可: {cat}/{pf} は '{cur}' (確定セルのみ qa_refs を追記できる)"
            )
        raw = op.get("qa_refs")
        if raw is None and op.get("qa_ref"):
            raw = [op["qa_ref"]]
        if not isinstance(raw, list) or not raw:
            raise TransitionError(f"add-qa-ref には非空 qa_refs (配列) が必須: {cat}/{pf}")
        known = {e.get("id") for e in state.get("qa_log") or []}
        refs = list(cell.get("qa_refs") or [])
        for ref in raw:
            if not isinstance(ref, str) or not ref.strip():
                raise TransitionError(f"qa_refs 要素は非空文字列でない: {ref!r}")
            if ref not in known:
                raise TransitionError(
                    f"add-qa-ref: qa_ref {ref!r} が qa_log に存在しない ({cat}/{pf})。"
                    "根拠のない参照は追記できない"
                )
            if ref not in refs:
                refs.append(ref)
        cell["qa_refs"] = refs
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
        # 対象外にした根拠の質疑も記録できるようにする。従来は reason の散文だけが残り、
        # 「どの質疑でこの platform を外したのか」を機械で辿れなかった。除外は収集した
        # 結論の一種であって未検討ではない、という区別をデータに持たせる。
        qa_ref = op.get("qa_ref")
        if qa_ref:
            newcell["qa_ref"] = qa_ref
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


FUTURE_TOLERANCE_SECONDS = 300


def _require_past_rfc3339(value, label: str) -> None:
    """RFC3339 かつ「未来でない」ことを課す。

    書式だけを見る検査は「書式の正しい嘘」を素通りさせる。実際、書込時刻より後の時刻を
    latest_checked_at / confirmed_at に書いても決定論ゲートは全て exit 0 になり、意味層の
    完成度 evaluator だけがそれを捉えた。まだ起きていない照合・採択を記録済みと主張する
    のは記録の捏造であり、決定論側で塞ぐ。時計ずれの許容は
    FUTURE_TOLERANCE_SECONDS 秒まで。
    """
    if not _is_rfc3339(value):
        raise TransitionError(f"{label} は RFC3339 必須 (受領値: {value!r})")
    when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    skew = (when - datetime.now(timezone.utc)).total_seconds()
    if skew > FUTURE_TOLERANCE_SECONDS:
        raise TransitionError(
            f"{label} が未来の時刻 ({value}, 現在より {int(skew)} 秒先)。"
            "まだ起きていない照合・採択を記録済みとして書けない。"
            "`date -u +%Y-%m-%dT%H:%M:%SZ` の実測値を使うこと"
        )


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
        _require_past_rfc3339(
            recommendation.get("latest_checked_at"),
            "decision: recommendation.latest_checked_at",
        )
        if recommendation["option_id"] not in option_ids:
            raise TransitionError("decision: recommendation.option_id が options に不在")

    user_decision = decision.get("user_decision")
    if status == "confirmed":
        if not isinstance(user_decision, dict):
            raise TransitionError("decision: confirmed には user_decision が必須")
        _require_nonempty(user_decision.get("option_id"), "user_decision.option_id")
        _require_nonempty(user_decision.get("confirmed_at"), "user_decision.confirmed_at")
        _require_past_rfc3339(
            user_decision.get("confirmed_at"), "decision: user_decision.confirmed_at"
        )
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


QA_PROVENANCE_KEYS = ("provenance", "basis", "answered_at")

# 回答の性質。確定の根拠として何が要るかがこれで変わる。
#   user-decision   : 利用者が代替案を見たうえで明示選択した。設計判断の正当な根拠。
#   observed-fact   : コード・設定・公式ドキュメントで検証できる観測事実。
#   agent-inference : アシスタントの推定。利用者確認も検証可能な出典も経ていない。
QA_BASIS_VALUES = ("user-decision", "observed-fact", "agent-inference")


def _incoming_required_info_items(qa_id: str, turn: dict) -> list[str]:
    """turn.required_info_items を検証して返す (未指定なら空)。

    required-info-catalog の item_id を qa_log entry へ**機械可読**に結び付けるための項目。
    従来この対応は qa_id の命名規約と確定セルの qa_ref 文字列からの目視推測でしか辿れず、
    「block 指定の必須情報が本当に確定へ接地しているか」を決定論で検査できなかった。
    """
    raw = turn.get("required_info_items")
    if raw is None:
        return []
    if not isinstance(raw, list) or any(
        not isinstance(i, str) or not i.strip() for i in raw
    ):
        raise TransitionError(
            f"qa_log {qa_id}: required_info_items は非空文字列の配列必須 "
            "(required-info-catalog の item_id を列挙する)"
        )
    return [i.strip() for i in raw]


QA_CORRECTION_KEYS = ("corrected_at", "note")


def _validate_correction(qa_id: str, index: int, item) -> None:
    """corrections[] の1件を検証する。不正なら TransitionError を投げる。

    問答本文 (question / answer) は改竄防止のため凍結されている。しかし本文の散文へ
    誤った値 (例: 実際には発生していない時刻) を書いてしまうと、凍結がそのまま
    「訂正できない誤り」になる。corrections は本文を書き換えずに『この記録は後に
    訂正された』という事実だけを append-only で残すための場所である。

    検査は3点。(1) corrected_at は他の時刻と同じく実測 RFC3339 で未来でないこと —
    まだ起きていない訂正を記録済みとして書けない。(2) note は空白のみでないこと —
    「何が誤りで何が正しいか」が読めない訂正記録は、訂正した体裁だけを整えて中身が無い。
    (3) 未知キーは拒否する — 呼び出し側は検証後に既知キーだけを取り出すため、typo を
    黙って捨てると「書いたつもりの訂正が消える」。
    """
    label = f"qa_log {qa_id}: corrections[{index}]"
    if not isinstance(item, dict):
        raise TransitionError(f"{label} は object 必須 (受領型: {type(item).__name__})")
    unknown = sorted(set(item) - set(QA_CORRECTION_KEYS))
    if unknown:
        raise TransitionError(
            f"{label}: 未知のキー {unknown} (既知: {list(QA_CORRECTION_KEYS)})。"
            "取り込まれずに黙って失われるため拒否する"
        )
    _require_past_rfc3339(item.get("corrected_at"), f"{label}.corrected_at")
    note = item.get("note")
    if not isinstance(note, str) or not note.strip():
        raise TransitionError(
            f"{label}: note は非空文字列必須 (何が誤りで何が正しいかを書く)"
        )


def _upsert_qa_entry(state: dict, qa_id: str, turn: dict) -> None:
    """qa_log entry を登録する。既存 entry へは provenance 項目だけを追記する。

    従来は `{id, question, answer}` の 3 キーしか保持せず、しかも既存 id を丸ごと
    読み飛ばしていたため、「その回答が誰のどの発話に由来するか」を後から一切付けられ
    なかった。出所不明の回答が確定セルの接地根拠になり得るのが問題の本体である。

    ただし question / answer の事後書換は許さない (記録の改竄防止)。既存 entry に対して
    許すのは、未設定の provenance 項目を**埋める**ことだけで、既に値がある項目の上書きや
    問答本文の変更は TransitionError で拒否する。追記は冪等 (同値の再適用は無変更)。
    """
    entry = next((e for e in state["qa_log"] if e.get("id") == qa_id), None)
    answered_at = turn.get("answered_at")
    if answered_at is not None:
        _require_past_rfc3339(answered_at, f"qa_log {qa_id}: answered_at")
    items = _incoming_required_info_items(qa_id, turn)
    corrections = turn.get("corrections")
    if corrections is not None:
        if not isinstance(corrections, list) or not corrections:
            raise TransitionError(
                f"qa_log {qa_id}: corrections は非空の配列必須"
            )
        for idx, item in enumerate(corrections):
            _validate_correction(qa_id, idx, item)
        corrections = [
            {k: item[k] for k in QA_CORRECTION_KEYS} for item in corrections
        ]
    basis = turn.get("basis")
    if basis is not None and basis not in QA_BASIS_VALUES:
        raise TransitionError(
            f"qa_log {qa_id}: basis={basis!r} が enum {list(QA_BASIS_VALUES)} 外"
        )
    if entry is None:
        new_entry = {
            "id": qa_id,
            "question": turn.get("question", ""),
            "answer": turn.get("answer", ""),
        }
        for key in QA_PROVENANCE_KEYS:
            if turn.get(key):
                new_entry[key] = turn[key]
        if items:
            new_entry["required_info_items"] = sorted(set(items))
        if corrections:
            new_entry["corrections"] = list(corrections)
        state["qa_log"].append(new_entry)
        return
    for key in ("question", "answer"):
        incoming = turn.get(key)
        if incoming and incoming != entry.get(key):
            raise TransitionError(
                f"qa_log {qa_id}: 既存 entry の {key} は書換不可 "
                "(記録の改竄防止。訂正が要るなら新しい qa_id を発行すること)"
            )
    for key in QA_PROVENANCE_KEYS:
        incoming = turn.get(key)
        if not incoming:
            continue
        current = entry.get(key)
        if current and current != incoming:
            raise TransitionError(
                f"qa_log {qa_id}: {key} は既に {current!r} が記録済みで上書きできない"
            )
        entry[key] = incoming
    if corrections:
        # append-only。既存の訂正記録は落とさず、同値の再適用でも増やさない (冪等)。
        existing = entry.setdefault("corrections", [])
        for item in corrections:
            if item not in existing:
                existing.append(item)
    if items:
        # 追記のみ (和集合)。既存の紐付けを turn 側の列挙漏れで落とさない。
        entry["required_info_items"] = sorted(
            set(entry.get("required_info_items", [])) | set(items)
        )


def _apply_design_application(state: dict, cat: str, op: dict) -> None:
    """章 (カテゴリ) 固有の「その設計知識をこの章でどう適用したか」を記録する。

    従来 compile の「適用された設計知識」節は resource-map の card 本文を逐語で流し込む
    だけで、章固有の記述を置く場所が schema に無かった。その結果、同じ card を引く章どうしが
    byte 単位で一致し、「適用した」と称しながら実体は「参照した」に過ぎない空洞になっていた
    (機械注入したものを自分で適用の証拠として数える自己循環)。card 本文は共有資産なので
    一致するのが当然であり、章固有性はここに書かれた記述だけが担える。
    """
    if not isinstance(cat, str) or not cat.strip():
        raise TransitionError("set-design-application には category が必須")
    known = {c.get("id") for c in state.get("categories", []) or []}
    if known and cat not in known:
        raise TransitionError(
            f"set-design-application: 未知のカテゴリ {cat!r} (既知: {sorted(known)})"
        )
    text = op.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TransitionError(
            f"set-design-application[{cat}]: text は非空文字列必須 "
            "(card の要約ではなく、この章の確定内容へどう効いたかを書く)"
        )
    basis = op.get("basis")
    if basis is not None and basis not in QA_BASIS_VALUES:
        raise TransitionError(
            f"set-design-application[{cat}]: basis={basis!r} が enum {list(QA_BASIS_VALUES)} 外"
        )
    recorded_at = op.get("recorded_at")
    _require_past_rfc3339(recorded_at, f"set-design-application[{cat}].recorded_at")
    record = {"text": text.strip(), "recorded_at": recorded_at}
    if basis:
        record["basis"] = basis
    state.setdefault("design_applications", {})[cat] = record


def _apply_doctrine_application(state: dict, cat: str, op: dict) -> None:
    """章 × 設計 concern 単位で「その上流指針を本章の確定内容へどう反映したか」を記録する。

    card レベル (design_applications) で塞いだのと同じ空洞が doctrine レベルにも残っていた。
    compile が doctrine registry を読んで authority を表へ描くようになった結果、
    Apple HIG / OWASP ASVS / Google SRE の名は章に現れるようになったが、現れる場所は
    registry の転記表の内側だけで、本文の確定セル要件へ効いた箇所は 1 件も無かった。
    表への出現を反映の証拠として数えるのは、機械注入したものを自分で証拠に数える自己循環で
    あり、rubric の Goodhart 防止条項が禁じているもの。章固有の反映はここにしか書けない。
    """
    if not isinstance(cat, str) or not cat.strip():
        raise TransitionError("set-doctrine-application には category が必須")
    known = {c.get("id") for c in state.get("categories", []) or []}
    if known and cat not in known:
        raise TransitionError(
            f"set-doctrine-application: 未知のカテゴリ {cat!r} (既知: {sorted(known)})"
        )
    concern_id = op.get("concern_id")
    if not isinstance(concern_id, str) or not concern_id.strip():
        raise TransitionError(
            f"set-doctrine-application[{cat}]: concern_id は非空文字列必須 "
            "(doctrine-anchor-registry の concern_id と一致させる)"
        )
    concern_id = concern_id.strip()
    text = op.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TransitionError(
            f"set-doctrine-application[{cat}/{concern_id}]: text は非空文字列必須 "
            "(authority の要約ではなく、本章の確定セルへどう効いたかを書く)"
        )
    text = text.strip()
    clash = _doctrine_reuse_conflict(state, cat, concern_id, text)
    if clash:
        raise TransitionError(
            f"set-doctrine-application[{cat}/{concern_id}]: 同じ concern を引く "
            f"{clash!r} 章と実質同一の反映記述である。章が違えば確定セルも違うため、"
            "反映の記述が一致するのは上流の要約を写しただけの疑いが強い "
            "(章固有の確定内容へ言及して書き直すこと)"
        )
    basis = op.get("basis")
    if basis is not None and basis not in QA_BASIS_VALUES:
        raise TransitionError(
            f"set-doctrine-application[{cat}/{concern_id}]: basis={basis!r} が "
            f"enum {list(QA_BASIS_VALUES)} 外"
        )
    recorded_at = op.get("recorded_at")
    _require_past_rfc3339(
        recorded_at, f"set-doctrine-application[{cat}/{concern_id}].recorded_at"
    )
    record = {"text": text, "recorded_at": recorded_at}
    if basis:
        record["basis"] = basis
    state.setdefault("doctrine_applications", {}).setdefault(cat, {})[concern_id] = record


def _add_reopen_correction(state: dict, op: dict) -> None:
    """既存 reopen_log entry へ、事後に判明した事実を追記する (既存キーは不可侵)。

    reopened_at を必須化する前に書かれた entry には時刻が無い。当初この欠落は
    「遡って埋めない」と決めていたが、その理由づけは 2 段階で誤っていた。
    最初は「実測できないから」としていて、これはトランスクリプトに残っている以上
    端的に偽だった。次に「既存 entry を書き換える op を writer に置かないため」と
    書き直したが、これは禁じるべき対象を取り違えていた — 守りたいのは既存フィールドの
    改変であって、新しいフィールドの追記ではない。qa_log は question/answer を凍結した
    まま corrections[] への追記だけを許しており、同じ設計をここへ当てはめれば、
    確定を壊した事実を後から消せる経路は作らずに欠測時刻を回復できる。
    append-only の下では「訂正 (既存事実の修正)」と「補記 (新しい事実の追加)」は別物で、
    トランスクリプトから復元した観測は後者である。

    entry には id が無いので index で指す。reopen_log は追記のみで並べ替えないため
    index は安定だが、取り違えると別の reopen に他人の時刻が付いてしまう。それは
    まさにこの記録が防ごうとしている種類の汚染なので、category/platform の照合を
    必須にして、番号だけの指定を受け付けない。
    """
    log = state.get("reopen_log") or []
    index = op.get("index")
    if not isinstance(index, int) or isinstance(index, bool):
        raise TransitionError("add-reopen-correction には整数 index が必須")
    if not 0 <= index < len(log):
        raise TransitionError(
            f"add-reopen-correction: index={index} が reopen_log の範囲外 (len={len(log)})"
        )
    entry = log[index]
    for key in ("category", "platform"):
        expected = op.get(f"match_{key}")
        if not expected:
            raise TransitionError(
                f"add-reopen-correction には match_{key} が必須 "
                "(index の取り違えで別の reopen へ追記するのを防ぐ)"
            )
        if entry.get(key) != expected:
            raise TransitionError(
                f"add-reopen-correction: index={index} の {key} は {entry.get(key)!r} で "
                f"match_{key}={expected!r} と一致しない (index の指定違い)"
            )
    note = op.get("note")
    if not isinstance(note, str) or not note.strip():
        raise TransitionError(
            f"add-reopen-correction[{index}]: note は非空文字列必須"
        )
    recovered_at = op.get("recovered_at")
    _require_past_rfc3339(recovered_at, f"add-reopen-correction[{index}].recovered_at")
    record: dict = {"recovered_at": recovered_at, "note": note.strip()}
    observed = op.get("observed_reopened_at")
    if observed is not None:
        # 復元した「reopen を実施した実測時刻」。既存キー reopened_at は書き換えず、
        # 補記側にだけ置く。どちらが原記録でどちらが後からの復元かを読み手が区別できる。
        _require_past_rfc3339(
            observed, f"add-reopen-correction[{index}].observed_reopened_at"
        )
        record["observed_reopened_at"] = observed
    corrections = entry.setdefault("corrections", [])
    if record not in corrections:  # 同値の再適用で増やさない (冪等)
        corrections.append(record)


QA_CORRECTABLE_TIMESTAMPS = ("answered_at",)


def _correct_qa_timestamp(state: dict, op: dict) -> None:
    """qa_log entry の計測値時刻を、旧値と根拠を残したうえで正しい実測値へ訂正する。

    背景。provenance 系キーは append-only (不在時のみ設定可) で凍結しており、これは
    question/answer と同じく「後から書き換えられるなら記録が証跡でなくなる」ためである。
    ところが answered_at は散文ではなく**計測値**なので、誤って書込時刻を入れてしまうと、
    正しい値を corrections[] の日本語文にしか置けなくなる。すると answered_at を読む
    機械は誤値を読み続け、訂正は散文の中にあって届かない。決定論ゲートは全て緑のまま
    誤った時刻が残る — 緑であることが内容の正しさを示さない典型形である。

    一方で無条件の上書きを許すと凍結の意味が消える。そこで訂正だけを別 op として切り出し、
    次を必須にする:
      - expected_current: 現在保持している値と一致すること。取り違えた entry や、既に
        別の訂正が入った entry を盲目的に塗り潰すことを防ぐ (fail-closed)。
      - value: 新しい実測値。過去の RFC3339 であること。
      - note / corrected_at: なぜ誤ったのか、いつ訂正したのか。
    そして値の差し替えと同時に corrections[] へ旧値・新値・根拠を追記する。フィールドは
    正しい値になり、誤っていた事実も残る。どちらか一方を捨てない。

    reopen_log の欠測時刻を observed_reopened_at という別キーへ補記したのとは扱いが違う。
    あちらは「原記録が存在しない」ケースで、後から測った値を原記録と同じ名前に置けば
    出所を偽ることになる。こちらは「原記録が存在するが誤っている」ケースなので、正しい
    値をその名前に置いたうえで、誤りの履歴を別に残すのが正しい。
    """
    qa_id = op.get("qa_id")
    if not isinstance(qa_id, str) or not qa_id.strip():
        raise TransitionError("correct-qa-timestamp には qa_id が必須")
    entry = next(
        (e for e in state.get("qa_log", []) or [] if isinstance(e, dict) and e.get("id") == qa_id),
        None,
    )
    if entry is None:
        raise TransitionError(f"correct-qa-timestamp: qa_log に {qa_id!r} が存在しない")
    key = op.get("key", "answered_at")
    if key not in QA_CORRECTABLE_TIMESTAMPS:
        raise TransitionError(
            f"correct-qa-timestamp: key={key!r} は訂正対象外 "
            f"(計測値時刻 {list(QA_CORRECTABLE_TIMESTAMPS)} のみ。"
            "question/answer/provenance/basis は本文であり、訂正でなく新しい qa_id を発行すること)"
        )
    value = op.get("value")
    _require_past_rfc3339(value, f"correct-qa-timestamp {qa_id}.{key}.value")
    note = op.get("note")
    if not isinstance(note, str) or not note.strip():
        raise TransitionError(f"correct-qa-timestamp {qa_id}: note は非空文字列必須")
    corrected_at = op.get("corrected_at")
    _require_past_rfc3339(corrected_at, f"correct-qa-timestamp {qa_id}.corrected_at")
    current = entry.get(key)
    corrections = entry.setdefault("corrections", [])
    # 冪等判定を「同じ record が既にあるか」で行ってはならない。適用後は現在値が新値に
    # なっているため previous_value が変わり、同じ op でも別 record になってしまう。
    # 見るべきは「このキーが既にこの値へ訂正済みか」だけである。
    already = any(
        isinstance(c, dict)
        and c.get("corrected_field") == key
        and c.get("corrected_value") == value
        and c.get("corrected_at") == corrected_at
        for c in corrections
    )
    if current == value and already:
        return  # 同値の再適用 (冪等)
    expected = op.get("expected_current")
    if expected != current:
        raise TransitionError(
            f"correct-qa-timestamp {qa_id}: {key} の現在値は {current!r} で "
            f"expected_current={expected!r} と一致しない "
            "(訂正対象を取り違えているか、既に別の訂正が入っている)"
        )
    entry[key] = value
    corrections.append(
        {
            "corrected_at": corrected_at,
            "note": note.strip(),
            "corrected_field": key,
            "previous_value": current,
            "corrected_value": value,
        }
    )


def _normalize_for_reuse(text: str) -> str:
    """転記の同一判定用に、意味を変えない表層差を落とす。

    落とすのは空白 (全角半角とも) と句読点・括弧・記号だけで、語は落とさない。
    ここで語まで削ると別内容が衝突しうるが、表層記号だけなら内容の異なる 2 記述が
    一致することはない。
    """
    return "".join(
        ch for ch in text if not ch.isspace() and unicodedata.category(ch)[0] != "P"
    )


def _doctrine_reuse_conflict(state: dict, cat: str, concern_id: str, text: str) -> str | None:
    """同じ concern を引く他章に、実質同一の適用記述が既にあれば、その章 id を返す。

    doctrine registry では 7 concern がいずれも 2 つ以上のカテゴリから参照される
    (presentation は ui-ux と frontend、data-access は database と backend、
    operations は infrastructure と maintenance-ops、など)。この構造ゆえ、
    「その章で本当に適用したのか、上流の要約を写しただけなのか」を機械で疑える —
    章が違えば確定セルも違うのだから、反映の記述が他章と一致するのは不自然である。

    None を返せば受理、章 id を返せば呼出し側が TransitionError にする。
    """
    existing = state.get("doctrine_applications") or {}
    for other_cat, per_concern in existing.items():
        if other_cat == cat or not isinstance(per_concern, dict):
            continue
        other = str((per_concern.get(concern_id) or {}).get("text") or "")
        if not other:
            continue
        # 正規化してから完全一致で判定する。素の完全一致だと句読点を1つ変えるだけで
        # 抜けられ、逆に言い換えの検出まで踏み込むと正当な記述を弾いてしまい、
        # 回避のためだけの無意味な言い換えを書き手に強いる (Goodhart を別の口から
        # 入れることになる)。正規化一致なら偽陽性が原理的に出ない — 内容の異なる
        # 2つの記述が正規化後に一致することはないので、writer が理不尽に止まらない。
        if _normalize_for_reuse(text) == _normalize_for_reuse(other):
            return other_cat
    return None


def apply_turn(state: dict, turn: dict) -> None:
    """1 ターン (質問→回答→反映) をまとめて適用する。

    turn.qa_id があれば qa_log へ、turn.approval_id があれば approval_log へ
    エントリを登録し、confirm op に qa_ref を、approval を伴う exclude op に
    approval_ref を補完してから各セル op を適用する。適用後に集約を再計算する。
    """
    qa_id = turn.get("qa_id")
    if qa_id:
        _upsert_qa_entry(state, qa_id, turn)
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
            op.get("action") == "add-qa-ref"
            and not op.get("qa_refs")
            and not op.get("qa_ref")
            and qa_id
        ):
            op["qa_refs"] = [qa_id]
        if (
            op.get("action") == "exclude"
            and not op.get("reason")
            and not op.get("approval_ref")
            and appr_id
        ):
            op["approval_ref"] = appr_id
        if op.get("action") == "exclude" and not op.get("qa_ref") and qa_id:
            op["qa_ref"] = qa_id
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
