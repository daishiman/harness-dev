#!/usr/bin/env python3
# /// script
# name: apply-spec-transition
# version: 0.2.3
# purpose: run-system-spec-elicit が所有する spec-state.json の単一 transition writer。カテゴリ×platform セルの 未収集/対象外/確定 遷移を規則付きで適用し、確定セルの直接巻き戻し (rollback) を Bash/script 経由でも拒否し、R4-reopen 経由のみ確定変更を許す。goal-seek chunk (per-invocation max_loops) の状態保存/resume も担う。
# inputs:
#   - argv: bootstrap|init|add-category|apply|chunk|aggregate|set-targets|set-foundation|set-decision|set-knowledge-candidate|set-qa-source|set-qa-design-applications|fix-qa-knowledge-ref サブコマンドと --state/--taxonomy/--op/--turns/--out/--max-loops/--require-all/--schema-version (confirm を含む apply/chunk は --required-info CATALOG が必須で、候補stateを検証)
# outputs:
#   - spec-state.json (stdout or --out。親ディレクトリが無ければ作り、同じディレクトリの一時ファイルから置き換える)
#   - exit: 0=OK / 1=TransitionError (state・turns・taxonomy の形の崩れを含む) or IO / 2=usage error (confirm を含む apply/chunk に --required-info が無い)・required-info catalog の形が不正
# contexts: [E, C]
# network: false
# write-scope: spec-state.json (単一 writer)
# dependencies: [scripts/validate-knowledge-graph.py, scripts/foundation_provenance.py, scripts/validate-design-knowledge-refs.py]
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
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
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
# set-foundation が受理する全キー: U1-U9 + 確定フラグ + ユーザー合意の承認参照 +
# U ごとの根拠束縛 (effective_source_refs)。未知キーは弾く。
FOUNDATION_KEYS = FOUNDATION_U_KEYS + ("confirmed", "approval_ref", "effective_source_refs")

# U1-U9 の根拠 (qa_log の一次入力 + approval_log) を検査する helper。coverage 検証
# (validate-coverage-matrix.py) と同じ実装を共有し、writer と validator で判定をずらさない。
_FOUNDATION_PROVENANCE_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "foundation_provenance.py"
)
_FOUNDATION_PROVENANCE_SPEC = importlib.util.spec_from_file_location(
    "system_spec_foundation_provenance", _FOUNDATION_PROVENANCE_PATH
)
if _FOUNDATION_PROVENANCE_SPEC is None or _FOUNDATION_PROVENANCE_SPEC.loader is None:
    raise ImportError(f"cannot load foundation provenance helper: {_FOUNDATION_PROVENANCE_PATH}")
_FOUNDATION_PROVENANCE = importlib.util.module_from_spec(_FOUNDATION_PROVENANCE_SPEC)
_FOUNDATION_PROVENANCE_SPEC.loader.exec_module(_FOUNDATION_PROVENANCE)
validate_foundation_source_indexes = _FOUNDATION_PROVENANCE.validate_foundation_source_indexes
FOUNDATION_SOURCE_INDEXES = _FOUNDATION_PROVENANCE.FOUNDATION_SOURCE_INDEXES

# state の版。既定は 1.0。1.1 は qa 単位の design_applications 契約
# (design_application_contract_version=1.0) を opt-in で有効にした state で、confirm の根拠 qa に
# 構造化した設計適用を必須にし、確定 foundation に effective_source_refs を必須にする。
LEGACY_STATE_SCHEMA_VERSION = "1.0"
CURRENT_STATE_SCHEMA_VERSION = "1.1"
STATE_SCHEMA_VERSIONS = (LEGACY_STATE_SCHEMA_VERSION, CURRENT_STATE_SCHEMA_VERSION)
DESIGN_APPLICATION_CONTRACT_VERSION = "1.0"
CATEGORY_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
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


class CatalogError(Exception):
    """--required-info に渡した catalog 自体が不正 (遷移の可否を判定できない) ときに送出する。"""


class UsageError(Exception):
    """引数の組合せが契約に反する (confirm を含むのに --required-info が無い等) ときに送出する。"""


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


def _refresh_hearing_progress(state: dict) -> None:
    """hearing_progress の complete / next_question を matrix から導き直す。

    run_chunk の最後だけで更新すると、apply や add-category で matrix が変わった後も
    古い complete=true が残り、未収集セルがあるのに完了扱いできてしまう。
    """
    progress = state.setdefault("hearing_progress", {})
    unresolved = count_unresolved(state)
    progress["complete"] = unresolved == 0
    progress["next_question"] = None if unresolved == 0 else next_unresolved_question(state)


# --------------------------------------------------------------------------- #
# 初期化 (R1-init)                                                             #
# --------------------------------------------------------------------------- #
def _require_schema_version(value) -> str:
    if value not in STATE_SCHEMA_VERSIONS:
        raise TransitionError(
            f"schema_version は {' / '.join(STATE_SCHEMA_VERSIONS)} のいずれか必須 (got {value!r})"
        )
    return value


def _existing_schema_version(existing: dict) -> str:
    """既存 state の schema_version と design application 契約 marker の組を確かめる。

    marker の欠落・不一致を init で黙って補うと、契約を満たさない qa entry を持つ state を
    schema 1.1 適合と偽装できる。組が崩れた state は修復せずに拒否する。
    """
    schema_version = existing.get("schema_version")
    contract_version = existing.get("design_application_contract_version")
    if schema_version == LEGACY_STATE_SCHEMA_VERSION:
        if contract_version is not None:
            raise TransitionError(
                "legacy schema 1.0 は design_application_contract_version 欠落時だけ明示 migration 可能"
            )
    elif schema_version == CURRENT_STATE_SCHEMA_VERSION:
        if contract_version != DESIGN_APPLICATION_CONTRACT_VERSION:
            raise TransitionError(
                "schema 1.1 は design_application_contract_version=1.0 必須。"
                "marker 欠落/不一致を init で修復してはならない"
            )
    else:
        raise TransitionError(
            "既存 state の schema_version は exact 1.0 legacy または exact 1.1 current 必須"
        )
    return schema_version


def _schema_envelope(schema_version: str) -> dict:
    """schema_version と、1.1 のときだけ付ける design application 契約 marker を返す。"""
    envelope = {"schema_version": _require_schema_version(schema_version)}
    if schema_version == CURRENT_STATE_SCHEMA_VERSION:
        envelope["design_application_contract_version"] = DESIGN_APPLICATION_CONTRACT_VERSION
    return envelope


def bootstrap_state(schema_version: str = LEGACY_STATE_SCHEMA_VERSION) -> dict:
    """R0 を matrix 初期化より先に実行できる最小 state envelope を返す。

    既定は schema 1.0。schema 1.1 (confirm の根拠 qa に design_applications を課す契約) は
    呼び出し側が明示したときだけ marker 付きで作る。
    """
    return {
        **_schema_envelope(schema_version),
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


def init_state(
    taxonomy: dict,
    existing_state: dict | None = None,
    schema_version: str | None = None,
) -> dict:
    """C04 taxonomy からカテゴリ×必須platform マトリクスを初期化する。

    必須 platform 行 (CANONICAL_PLATFORMS) の全存在を検証し、欠落があれば
    TransitionError を送出する (R1-init の必須行全存在検証)。taxonomy の形が崩れている
    (object でない・platforms/categories が id/label を持つ object の配列でない) ときも
    traceback ではなく TransitionError にする。

    existing_state は matrix 未着手の bootstrap state に限る。確定セルを含む state を
    init し直すと matrix が未収集へ戻り、R4-reopen を経ずに確定を巻き戻せてしまう。
    schema_version は既存 state の版を引き継ぎ、``schema_version="1.1"`` を明示したときだけ
    1.0 から 1.1 へ移す (1.1 から 1.0 へは戻さない)。
    """
    if not isinstance(taxonomy, dict):
        raise TransitionError(f"taxonomy は object 必須 (got {type(taxonomy).__name__})")
    for key, fields in (("platforms", ("id",)), ("categories", ("id", "label"))):
        items = taxonomy.get(key)
        if not isinstance(items, list) or not all(
            isinstance(item, dict) and all(f in item for f in fields) for item in items
        ):
            raise TransitionError(
                f"taxonomy.{key} は {'/'.join(fields)} を持つ object の配列必須"
            )
    tax_platforms = [p["id"] for p in taxonomy.get("platforms", [])]
    missing = [p for p in CANONICAL_PLATFORMS if p not in tax_platforms]
    if missing:
        raise TransitionError(f"taxonomy に必須 platform {missing} が欠落")
    cats = [{"id": c["id"], "label": c["label"]} for c in taxonomy["categories"]]
    if not cats:
        raise TransitionError("taxonomy.categories は非空配列必須")
    cat_ids = [c["id"] for c in cats]
    if len(set(cat_ids)) != len(cat_ids):
        raise TransitionError(f"taxonomy.categories の id が重複: {cat_ids}")
    matrix = {
        c["id"]: {pf: {"state": "未収集"} for pf in CANONICAL_PLATFORMS} for c in cats
    }
    if existing_state is None:
        prior: dict = {}
        prior_version = LEGACY_STATE_SCHEMA_VERSION
    else:
        if not isinstance(existing_state, dict):
            raise TransitionError("既存 state は object 必須")
        prior = existing_state
        if any(
            isinstance(cell, dict) and cell.get("state") == "確定"
            for row in (prior.get("matrix") or {}).values()
            if isinstance(row, dict)
            for cell in row.values()
        ):
            raise TransitionError(
                "init --state は matrix 未着手の bootstrap state 専用。"
                "確定セルを含む state の再初期化は R4-reopen を迂回するため拒否"
            )
        prior_version = _existing_schema_version(prior)
    target_version = prior_version if schema_version is None else _require_schema_version(schema_version)
    if prior_version == CURRENT_STATE_SCHEMA_VERSION and target_version != CURRENT_STATE_SCHEMA_VERSION:
        raise TransitionError(
            "schema 1.1 の state を 1.0 へ戻す init は拒否 (design application 契約は外せない)"
        )
    state: dict = {
        **_schema_envelope(target_version),
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
    _refresh_hearing_progress(state)
    return state


def add_category(state: dict, category: dict) -> None:
    """taxonomy に無いカテゴリ行を後から足す (既存行と確定セルには触れない)。

    対象 system 固有の関心事 (例: 開発フロー) が taxonomy に無いとき、init し直すと
    確定済みの行まで未収集へ戻る。新しい行を未収集で足すだけの経路を分ける。
    既存 id の変更は R4-reopen 経由に限る。
    """
    if not isinstance(category, dict):
        raise TransitionError("add-category: category は object 必須")
    category_id, label = category.get("id"), category.get("label")
    if not isinstance(category_id, str) or not category_id.strip():
        raise TransitionError("add-category: id が空")
    if not isinstance(label, str) or not label.strip():
        raise TransitionError("add-category: label が空")
    category_id, label = category_id.strip(), label.strip()
    if not CATEGORY_ID_RE.fullmatch(category_id):
        raise TransitionError(f"add-category: id は kebab-case 必須 ({category_id})")
    if category_id in state["matrix"] or any(
        item.get("id") == category_id for item in state["categories"]
    ):
        raise TransitionError(f"add-category: 既存カテゴリ ({category_id}) の変更は R4-reopen 経由")
    state["categories"].append({"id": category_id, "label": label})
    state["matrix"][category_id] = {pf: {"state": "未収集"} for pf in CANONICAL_PLATFORMS}
    recompute_aggregates(state)
    _refresh_hearing_progress(state)


# --------------------------------------------------------------------------- #
# セル遷移 (単一 writer 防御の中核)                                            #
# --------------------------------------------------------------------------- #
def _cell(state: dict, cat: str, pf: str) -> dict:
    if cat not in state["matrix"]:
        raise TransitionError(f"未知カテゴリ: {cat}")
    if pf not in state["matrix"][cat]:
        raise TransitionError(f"未知 platform: {pf} (カテゴリ {cat})")
    return state["matrix"][cat][pf]


def _require_known_ref(state: dict, ref, label: str, logs: tuple[str, ...]) -> None:
    """セルが指す根拠 id が、指定した log に実在することを書込前に確かめる。

    validate-coverage-matrix.py は確定 qa_ref を qa_log ∪ approval_log に、承認だけで外した
    対象外の approval_ref を approval_log に照合する。writer が宙に浮いた参照を受け入れると、
    検証で落ちる state を single writer 自身が公開してしまうので、同じ照合を先にかける。
    """
    if not isinstance(ref, str) or not ref.strip():
        raise TransitionError(f"{label} は非空文字列でない: {ref!r}")
    known = {
        entry.get("id")
        for log in logs
        for entry in state.get(log) or []
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    if ref not in known:
        raise TransitionError(
            f"{label}={ref!r} が {' / '.join(logs)} に存在しない (根拠のない参照は書き込めない)"
        )


def apply_cell_op(state: dict, op: dict) -> None:
    """1 セルの遷移を規則付きで適用する (state を破壊的に更新)。

    規則:
      - reopen: 現在が確定のときだけ許可し、reason 必須。未収集へ戻す。
      - set-serves: 確定セルにのみ許可。serves_goals (上位概念トレース) を付与する
        (state は 確定 のまま変えないため rollback 防御には抵触しない = additive anchor)。
      - set-approval: 確定セルにのみ許可。approval_log に実在する approval_ref を付与する。
      - confirm / exclude: 対象セルが確定なら TransitionError (rollback 拒否)。
        確定変更は必ず reopen を先に経由すること。
      - confirm は qa_ref 必須 (任意で serves_goals を同時付与可)、exclude は reason か approval_ref 必須。
        どちらも指した id は log に実在しなければならない (qa_ref は qa_log か approval_log、
        approval_ref は approval_log)。
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

    if action == "supersede-qa":
        # qa_log entry どうしの置き換え関係の記録専用 op。同じくログを対象にする。
        _supersede_qa(state, op)
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
        # reopen は確定を取り消す操作なので、qa_ref や approval_ref を次のセルへ引き継がない
        # (別の回答に対して得た承認を、再確定したセルが継承してしまう)。ただし何も残さずに
        # 落とすと「承認があったこと自体」が state から消え、reopen_log を読んでも再取得が
        # 要ると分からない。捨てる判断は変えず、捨てた事実だけを discarded に残す。
        discarded = {
            key: list(cell[key]) if isinstance(cell[key], list) else cell[key]
            for key in ("qa_ref", "qa_refs", "serves_goals", "serves_intents", "approval_ref")
            if key in cell
        }
        log_entry = {
            "category": cat,
            "platform": pf,
            "reason": reason,
            "from": "確定",
            "reopened_at": reopened_at,
        }
        if discarded:
            log_entry["discarded"] = discarded
        state.setdefault("reopen_log", []).append(log_entry)
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

    if action == "set-approval":
        # exclude は approval_ref を cell へ持てるのに confirm は持てない、という非対称が
        # 「回答本文は承認を主張しているが、確定セルから承認記録へ機械追跡できない」
        # 直接原因だった。confirm の確定条件には触れず、確定セル限定の後付け annotation
        # である set-serves / add-qa-ref と同型の action で対称化する (確定巻き戻し拒否は不変)。
        if cur != "確定":
            raise TransitionError(
                f"set-approval 不可: {cat}/{pf} は '{cur}' (確定セルのみ approval_ref を付与できる)"
            )
        approval_ref = op.get("approval_ref")
        if not isinstance(approval_ref, str) or not approval_ref.strip():
            raise TransitionError(f"set-approval には非空 approval_ref が必須: {cat}/{pf}")
        approval_ref = approval_ref.strip()
        if not _has_entry(state.get("approval_log") or [], approval_ref):
            raise TransitionError(
                f"set-approval: approval_log に存在しない approval_ref: {approval_ref} ({cat}/{pf})"
            )
        cell["approval_ref"] = approval_ref
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
        _require_known_ref(state, qa_ref, f"confirm {cat}/{pf} の qa_ref", ("qa_log", "approval_log"))
        retired = _qa_entry(state, qa_ref)
        if retired is not None and retired.get("superseded_by") is not None:
            # supersede-qa は「主たる接地根拠のままでは置き換えない」を課すが、置き換えた後に
            # 旧 entry を主根拠へ戻せると、その条件は reopen → confirm の 2 手で抜けられる。
            raise TransitionError(
                f"confirm 不可: {cat}/{pf} の qa_ref={qa_ref!r} は "
                f"{retired.get('superseded_by')!r} で置き換え済み "
                "(置き換え済みの問は主たる接地根拠にしない。置き換え先で確定すること)"
            )
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
            _require_known_ref(state, approval_ref, f"exclude {cat}/{pf} の approval_ref", ("approval_log",))
            newcell["approval_ref"] = approval_ref
        # 対象外にした根拠の質疑も記録できるようにする。従来は reason の散文だけが残り、
        # 「どの質疑でこの platform を外したのか」を機械で辿れなかった。除外は収集した
        # 結論の一種であって未検討ではない、という区別をデータに持たせる。
        qa_ref = op.get("qa_ref")
        if qa_ref:
            _require_known_ref(state, qa_ref, f"exclude {cat}/{pf} の qa_ref", ("qa_log", "approval_log"))
            newcell["qa_ref"] = qa_ref
        state["matrix"][cat][pf] = newcell
    else:
        raise TransitionError(f"未知 action: {action!r}")


def _normalize_also_categories(tid: str, cat, also) -> list[str]:
    """target の also_categories (主章に加えて出典を載せる章) を検査して返す。"""
    label = f"target {tid!r} の also_categories"
    if not cat:
        raise TransitionError(
            f"{label} は category (主たる章) を持つ target にだけ指定できる"
        )
    if not isinstance(also, list) or not also:
        raise TransitionError(f"{label} は非空の配列でなければならない: {also!r}")
    out: list[str] = []
    for c in also:
        if not isinstance(c, str) or not c.strip():
            raise TransitionError(f"{label} の要素は非空文字列: {c!r}")
        if c == cat:
            raise TransitionError(
                f"{label} に主たる章 category={cat!r} と同じ章は指定できない"
            )
        if c in out:
            raise TransitionError(f"{label} に {c!r} が重複している")
        out.append(c)
    return out


def set_targets(state: dict, targets: list) -> None:
    """取得対象一覧 targets[] を設定する (単一 writer の唯一の targets 書込経路)。

    consumer (validate-source-citation.py / compile-spec-doc.py) が期待する形状へ正規化する。
    各 target は ``{"target_id": str[, "category": str][, "also_categories": [str]]}`` または
    str (target_id) を受け付け、target_id 欠落/空・重複は TransitionError。category は任意
    (compile の章割当に使う)。apply-spec-transition.py 以外は spec-state を書き換えない
    不変則を保つため、targets も本経路経由でのみ設定する。

    also_categories は、1 つの技術が複数の章の判断を支えるときに、主たる章 (category) に
    加えて出典を載せる章を宣言する任意キー。category を 1 つしか持てないと、たとえば
    D1 の公式文書が database 章にしか出ず、同じ文書を根拠にした backend 章の判断
    (一括書込の上限など) を章から出典へ辿れなかった。主従を残すため category を主とし、
    also_categories は category を持つ target にだけ許す。要素は非空文字列で、重複と
    category との一致は拒否する (同じ章へ同じ出典を二度載せる宣言は誤記でしかない)。
    """
    if not isinstance(targets, list):
        raise TransitionError(f"targets は配列でない: {targets!r}")
    normalized: list[dict] = []
    seen: set[str] = set()
    for t in targets:
        also = None
        if isinstance(t, str):
            tid, cat = t, None
        elif isinstance(t, dict):
            tid, cat = t.get("target_id"), t.get("category")
            also = t.get("also_categories")
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
        if also is not None:
            entry["also_categories"] = _normalize_also_categories(tid, cat, also)
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


def _require_fresh_bindings_for_confirmed_value_changes(previous: dict, merged: dict) -> None:
    """確定済みの U の値を、古い根拠を付けたまま変えることを拒否する。

    値だけ差し替えて effective_source_refs を据え置くと、新しい値が旧い対話と承認に
    接地しているように見える。変えた U ごとに新しい qa_ref と approval_ref を求め、
    requirements_foundation.approval_ref もその新しい承認へ付け替えさせる。
    """
    if not previous.get("confirmed") or not merged.get("confirmed"):
        return
    changed = [
        (field, label)
        for field, label, _canonical_qa in FOUNDATION_SOURCE_INDEXES
        if previous.get(field) != merged.get(field)
    ]
    if not changed:
        return

    previous_refs = previous.get("effective_source_refs")
    merged_refs = merged.get("effective_source_refs")
    previous_refs = previous_refs if isinstance(previous_refs, dict) else {}
    merged_refs = merged_refs if isinstance(merged_refs, dict) else {}
    invalid_labels: list[str] = []
    changed_approval_refs: set[str] = set()
    for _field, label in changed:
        old_binding = previous_refs.get(label)
        new_binding = merged_refs.get(label)
        old_binding = old_binding if isinstance(old_binding, dict) else {}
        new_binding = new_binding if isinstance(new_binding, dict) else {}
        qa_changed = (
            isinstance(new_binding.get("qa_ref"), str)
            and new_binding.get("qa_ref") != old_binding.get("qa_ref")
        )
        approval_changed = (
            isinstance(new_binding.get("approval_ref"), str)
            and new_binding.get("approval_ref") != old_binding.get("approval_ref")
        )
        if not qa_changed or not approval_changed:
            invalid_labels.append(label)
        if approval_changed:
            changed_approval_refs.add(new_binding["approval_ref"])
    if invalid_labels:
        raise TransitionError(
            "確定済み foundation の値変更には対象U "
            + ", ".join(invalid_labels)
            + " の新しい qa_ref / approval_ref が必須"
        )

    current_approval = merged.get("approval_ref")
    if (
        current_approval == previous.get("approval_ref")
        or current_approval not in changed_approval_refs
    ):
        raise TransitionError(
            "確定済み foundation の値変更には、変更対象Uの新しい approval_ref を"
            " requirements_foundation.approval_ref に設定する必要がある"
        )


def set_foundation(state: dict, foundation: dict) -> None:
    """requirements_foundation (上位概念 U1-U9) を設定/確定する単一 writer 経路 (要件 C9)。

    - 既存 requirements_foundation へ渡された field をマージ (部分更新可・未知キーは拒否)。
    - goals は id 必須・重複禁止。concrete_intents.serves は実在 goal を指す (dangling 拒否)。
    - `confirmed: true` の確定条件 (上位概念のブレを機械で防ぐ):
        1. U1-U9 が値あり (U1-U3 は N/A 不可)、U4-U9 は明示 N/A+理由でも可。
        2. ユーザー合意の機械証跡として approval_ref が非空で approval_log に実在する
           (cell exclude の approval_ref と対称。承認なき確定を弾く)。
        3. U1-U9 の各値が利用者との対話 (qa_log の source) に接地している
           (foundation_provenance.validate_foundation_source_indexes)。
        4. 確定済みの値を変えるときは、変えた U に新しい qa_ref / approval_ref を付ける。
      approval_note を伴うときは approval_log へ idempotent 登録する (apply_turn と同じ機構)。
      検査が通るまで state には書かない (途中で拒否したとき approval_log だけ増える事故を防ぐ)。
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
    approvals = list(state.get("approval_log") or [])
    if approval_ref and approval_note is not None:
        if not _has_entry(approvals, approval_ref):
            approvals.append({"id": approval_ref, "note": approval_note})

    previous = dict(state.get("requirements_foundation") or empty_foundation())
    merged = dict(previous)
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
        _require_fresh_bindings_for_confirmed_value_changes(previous, merged)
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
        if not _has_entry(approvals, appr):
            raise TransitionError(
                f"確定条件不足: approval_ref={appr!r} が approval_log に不在 (承認証跡なし)"
            )
        candidate = dict(state)
        candidate["approval_log"] = approvals
        candidate["requirements_foundation"] = merged
        source_findings = validate_foundation_source_indexes(candidate)
        if source_findings:
            raise TransitionError("確定条件不足: " + "; ".join(source_findings))
    merged["confirmed"] = confirmed
    if approvals or "approval_log" in state:
        state["approval_log"] = approvals
    state["requirements_foundation"] = merged


def _require_nonempty(value, label: str) -> None:
    if isinstance(value, str):
        ok = bool(value.strip())
    elif isinstance(value, (list, dict)):
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
            "`python3 -c 'import datetime; "
            "print(datetime.datetime.now(datetime.timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\"))'` "
            "の実測値を使うこと"
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
    stray = sorted(k for k in QA_SUPERSESSION_KEYS if k in turn)
    if stray:
        # turn の未知キーは読み飛ばされるため、置き換えを書いたつもりで黙って失われる。
        raise TransitionError(
            f"qa_log {qa_id}: {stray} は turn では書けない "
            "(置き換えは supersede-qa op で、条件を検査したうえで記録する)"
        )
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
        if "source" in turn:
            # 後付けの set-qa-source が拒否する形 (例: path/section/sha256 を持たない
            # written-requirements) を主経路が逐語コピーで素通しすると、後付けより主経路が
            # 緩くなる。新規 entry の source も同じ正規化を通す。
            new_entry["source"] = normalize_qa_source(turn["source"], new_entry["answer"])
        if "design_applications" in turn:
            new_entry["design_applications"] = normalize_design_applications(
                turn["design_applications"]
            )
        if items:
            new_entry["required_info_items"] = sorted(set(items))
        if corrections:
            new_entry["corrections"] = list(corrections)
        state["qa_log"].append(new_entry)
        return
    for key, writer, normalize in (
        ("source", "set-qa-source", lambda raw: normalize_qa_source(raw, entry.get("answer"))),
        ("design_applications", "set-qa-design-applications", normalize_design_applications),
    ):
        # 既存 entry への source / design_applications は後付けの記録 (provenance) を伴う
        # 専用経路で扱う。turn 経由で黙って捨てる・黙って足すのどちらも記録の由来を偽るため、
        # 保存済みと同じ値の再適用だけを受け入れる。
        if key in turn and normalize(turn[key]) != entry.get(key):
            raise TransitionError(
                f"qa_log {qa_id}: 既存 entry の {key} は turn では書けない "
                f"(後付けは {writer} で、由来を記録したうえで行う)"
            )
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


def _as_utc(value: str) -> datetime:
    """RFC3339 文字列を tz 付き datetime にする (検証済みの値にだけ使う)。"""
    when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


QA_SUPERSESSION_KEYS = ("superseded_by", "superseded_at", "superseded_note")


def _qa_entry(state: dict, qa_id) -> dict | None:
    return next(
        (e for e in state.get("qa_log", []) or [] if isinstance(e, dict) and e.get("id") == qa_id),
        None,
    )


def _supersede_qa(state: dict, op: dict) -> None:
    """凍結済みの qa entry を、同じ論点を中立に問い直した新しい entry で置き換えたと記録する。

    背景。qa_log は append-only で question/answer を凍結している。これは記録を証跡に
    保つために正しいが、問の設計に欠陥 (推奨の印・片側だけの不利益など、
    ``neutral-question-criteria.md`` の N1-N4 違反) があった場合、その欠陥は永久に
    残る。C06 (hearing-auditor) は全 qa を誘導性評価の対象にするため、問い直して利用者の
    回答を取り直しても、旧 entry の検出は毎周同じ形で再発し、閉じる手段が無かった。

    本 op は旧 entry の本文に一切触れず、旧 entry へ ``superseded_by`` / ``superseded_at``
    / ``superseded_note`` を **1 度だけ** 追記する。本文も corrections も残るので、
    欠陥のあった問を記録から消すことにはならない。C06 は置き換え済みの entry を判定の
    対象から外し、報告に「閉じた検出」として残す。

    置き換えが有効になる条件は 3 つある:
      (a) 新しい qa が中立な問である — 判定は C06 (意味の判定で、writer には判定できない)
      (b) 旧 qa と同じ論点を扱う — 同じく C06 が判定する。writer は note を必須にして
          「何の論点をどう問い直したか」を C06 が照合できる形で残させる
      (c) 利用者の回答が記録されている — writer が決定論で検査する:
          新 entry の answer が非空・basis が user-decision・answered_at があり、
          旧 entry に answered_at があるならそれより後であること
    (a)(b) を満たさない置き換えは、C06 が無効と判定し旧 entry を対象へ戻す。writer が
    通したことは置き換えの正当性を意味しない。

    corrections を拡張せず別 op にした理由は 2 つ。corrections は ``{corrected_at, note}``
    以外のキーを拒否する契約とテストを持ち、そこへ機械が読む参照キーを混ぜると
    「未知キーは黙って失われる前に拒否する」という防御が崩れる。また、訂正は 1 つの
    entry の誤りの修正であり、置き換えは 2 つの entry の関係である — 意味が違うものを
    同じ場所に置くと、読む側 (C06・compile) が note の散文から区別するしかなくなる。

    書込の規則:
      - 旧 entry の superseded_by は write-once。同値の再適用は冪等、別値は拒否する。
      - 新 entry 自身が置き換え済みなら拒否する (置き換え済みへ向けない。これで循環も
        原理的に作れない — A→B の後に B→A を書こうとすると A は置き換え済みである)。
      - 旧 entry が確定セルの主たる接地根拠 (qa_ref) である間は拒否する。確定の根拠が
        旧版のままでは置き換えた意味が無い。先に R4-reopen → 新 qa で再確定すること。
        裏付け (qa_refs) からの参照は残してよい (compile が旧版の印付きで描く)。
    """
    label = "supersede-qa"
    old_id = op.get("qa_id")
    if not isinstance(old_id, str) or not old_id.strip():
        raise TransitionError(f"{label}: qa_id (置き換えられる旧 entry) が必須")
    new_id = op.get("superseded_by")
    if not isinstance(new_id, str) or not new_id.strip():
        raise TransitionError(
            f"{label} {old_id}: superseded_by (置き換える新 entry の qa_id) が必須"
        )
    if new_id == old_id:
        raise TransitionError(f"{label} {old_id}: superseded_by に自分自身は指定できない")
    old = _qa_entry(state, old_id)
    if old is None:
        raise TransitionError(f"{label}: qa_log に qa_id={old_id!r} が存在しない")
    new = _qa_entry(state, new_id)
    if new is None:
        raise TransitionError(
            f"{label} {old_id}: qa_log に superseded_by={new_id!r} が存在しない "
            "(置き換える問と回答を先に登録すること)"
        )
    note = op.get("note")
    if not isinstance(note, str) or not note.strip():
        raise TransitionError(
            f"{label} {old_id}: note は非空文字列必須 "
            "(旧 entry の問の欠陥と、同じ論点をどう問い直したかを書く。C06 が照合する)"
        )
    superseded_at = op.get("superseded_at")
    _require_past_rfc3339(superseded_at, f"{label} {old_id}.superseded_at")

    current = old.get("superseded_by")
    if current is not None:
        if (
            current == new_id
            and old.get("superseded_at") == superseded_at
            and old.get("superseded_note") == note.strip()
        ):
            return  # 同値の再適用 (冪等)
        raise TransitionError(
            f"{label} {old_id}: 既に superseded_by={current!r} が記録されている "
            "(置き換えの記録は書換不可。さらに置き換えるなら新しい entry を置き換えること)"
        )
    if new.get("superseded_by") is not None:
        raise TransitionError(
            f"{label} {old_id}: superseded_by={new_id!r} 自体が "
            f"{new.get('superseded_by')!r} で置き換え済み (置き換え済みの entry へは向けない)"
        )

    # (c) 利用者の回答が記録されていること。
    if not str(new.get("answer") or "").strip():
        raise TransitionError(
            f"{label} {old_id}: superseded_by={new_id!r} の answer が空 "
            "(利用者の回答が記録された entry でなければ置き換えにならない)"
        )
    if new.get("basis") != "user-decision":
        raise TransitionError(
            f"{label} {old_id}: superseded_by={new_id!r} の basis は "
            f"{new.get('basis')!r} (user-decision 必須。推定や観測事実は利用者の回答の"
            "取り直しにならない。未設定なら同じ qa_id の turn で basis を追記できる)"
        )
    new_at = new.get("answered_at")
    if not _is_rfc3339(new_at):
        raise TransitionError(
            f"{label} {old_id}: superseded_by={new_id!r} の answered_at が無い "
            "(問い直しが旧 entry より後であることを検査できない)"
        )
    old_at = old.get("answered_at")
    if _is_rfc3339(old_at) and _as_utc(new_at) <= _as_utc(old_at):
        raise TransitionError(
            f"{label} {old_id}: superseded_by={new_id!r} の answered_at ({new_at}) が "
            f"旧 entry の answered_at ({old_at}) より後でない (問い直しは後でなければならない)"
        )
    if _as_utc(superseded_at) < _as_utc(new_at):
        raise TransitionError(
            f"{label} {old_id}: superseded_at ({superseded_at}) が新 entry の "
            f"answered_at ({new_at}) より前 (回答を得る前に置き換えは記録できない)"
        )

    primary = sorted(
        f"{cat}/{pf}"
        for cat, row in (state.get("matrix") or {}).items()
        if isinstance(row, dict)
        for pf, cell in row.items()
        if isinstance(cell, dict)
        and cell.get("state") == "確定"
        and cell.get("qa_ref") == old_id
    )
    if primary:
        raise TransitionError(
            f"{label} {old_id}: 確定セル {primary} の主たる接地根拠 (qa_ref) のまま。"
            "先に R4-reopen し、新しい qa で再確定してから置き換えること"
        )
    # 上位概念 (U1-U9) の接地根拠も同じ扱いにする。foundation_provenance は置き換え済みの
    # qa への binding を拒否するため、付け替える前に置き換えると確定済み foundation が壊れる。
    source_refs = (state.get("requirements_foundation") or {}).get("effective_source_refs")
    if isinstance(source_refs, dict):
        bound = sorted(
            u_label
            for u_label, binding in source_refs.items()
            if isinstance(binding, dict) and binding.get("qa_ref") == old_id
        )
        if bound:
            raise TransitionError(
                f"{label} {old_id}: requirements_foundation.effective_source_refs {bound} の"
                "接地根拠 (qa_ref) のまま。先に set-foundation で新しい qa へ付け替えてから置き換えること"
            )

    old["superseded_by"] = new_id
    old["superseded_at"] = superseded_at
    old["superseded_note"] = note.strip()


# --------------------------------------------------------------------------- #
# qa entry の設計適用・出所の記録と後付け補修                                   #
# --------------------------------------------------------------------------- #
APPLICATION_STATES = {"applied", "not_applicable"}


def normalize_design_applications(raw: object) -> list[dict]:
    """qa entry の design_applications (どの設計知識をどう適用したか) を検査して整える。

    カテゴリ単位の state.design_applications (章の設計原則) とは別に、個々の回答が
    どの知識を根拠にどう解釈したかを qa entry へ残す。schema 1.1 では confirm の根拠 qa に必須。
    """
    if not isinstance(raw, list) or not raw:
        raise TransitionError("design_applications は非空配列必須")
    normalized: list[dict] = []
    for index, item in enumerate(raw):
        label = f"design_applications[{index}]"
        if not isinstance(item, dict):
            raise TransitionError(f"{label} は object 必須")
        for key in ("knowledge_ref", "principle", "rationale"):
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                raise TransitionError(f"{label}.{key} は非空文字列必須")
        applicability = item.get("applicability")
        if applicability not in APPLICATION_STATES:
            raise TransitionError(
                f"{label}.applicability={applicability!r} は applied|not_applicable 必須"
            )
        tradeoffs = item.get("tradeoffs")
        if (
            not isinstance(tradeoffs, list)
            or not tradeoffs
            or any(not isinstance(value, str) or not value.strip() for value in tradeoffs)
        ):
            raise TransitionError(f"{label}.tradeoffs は非空文字列の配列必須")
        normalized.append(
            {
                "knowledge_ref": item["knowledge_ref"].strip(),
                "principle": item["principle"].strip(),
                "applicability": applicability,
                "rationale": item["rationale"].strip(),
                "tradeoffs": [value.strip() for value in tradeoffs],
            }
        )
    return normalized


# 利用者の一次入力を出所とする kind。foundation trace と C06 中立性監査はここだけを根拠にできる。
PRIMARY_QA_SOURCE_KINDS = {"user-dialogue", "written-requirements"}
# 利用者の新規入力を伴わない kind。監査は「新しい主張が入ったか」を kind だけで判別できる。
#   harness-remediation : レビュー/監査の指摘を反映した是正 (新規主張はあるが利用者発ではない)
#   derived-consolidation: 既存 qa の統合・復旧 (新しい情報を増やさない、承認証跡が要る)
NON_PRIMARY_QA_SOURCE_KINDS = {"harness-remediation", "derived-consolidation"}
QA_SOURCE_KINDS = PRIMARY_QA_SOURCE_KINDS | NON_PRIMARY_QA_SOURCE_KINDS
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _find_qa(state: dict, qa_id: object, label: str) -> dict:
    if not isinstance(qa_id, str) or not qa_id.strip():
        raise TransitionError(f"{label}: qa_id は非空文字列必須")
    qa_id = qa_id.strip()
    entry = _qa_entry(state, qa_id)
    if entry is None:
        raise TransitionError(f"{label}: qa_log に存在しない qa_id: {qa_id}")
    return entry


def normalize_qa_source(raw: object, answer: object) -> dict:
    """qa entry の source を契約形状へ正規化する。

    対話は ``{"kind": "user-dialogue"}``、書面は path / section / sha256 を伴う。
    書面の sha256 は ``answer`` 原文 (UTF-8 bytes) と一致しなければならない。digest が
    合わない source を受け入れると「利用者原文を索引した」という主張が根拠を失う。

    利用者の新規入力を伴わない entry (レビュー指摘の反映・既存 qa の統合復旧) を
    ``user-dialogue`` と索引すると、C06 中立性監査と foundation trace が「利用者が答えた」
    という前提のまま偽の一次根拠を数えてしまう。この 2 経路は専用 kind で明示し、
    それぞれ何に由来するかを必須フィールドとして持たせる。
    """
    if not isinstance(raw, dict):
        raise TransitionError("qa source: source は object 必須")
    kind = raw.get("kind")
    if kind not in QA_SOURCE_KINDS:
        raise TransitionError(f"qa source: source.kind は {sorted(QA_SOURCE_KINDS)} のいずれか必須")
    if kind == "user-dialogue":
        if set(raw) - {"kind"}:
            raise TransitionError("qa source: user-dialogue source に余分な key を持たせない")
        return {"kind": kind}

    if kind == "harness-remediation":
        # どの指摘に由来するかを辿れなければ、是正は「AI が勝手に足した」と区別できない。
        trigger = raw.get("trigger")
        if set(raw) - {"kind", "trigger"}:
            raise TransitionError("qa source: harness-remediation source に余分な key を持たせない")
        if not isinstance(trigger, str) or not trigger.strip():
            raise TransitionError("qa source: harness-remediation source.trigger は非空文字列必須")
        return {"kind": kind, "trigger": trigger.strip()}

    if kind == "derived-consolidation":
        # 統合は新しい情報を増やさない操作なので、由来 qa と承認証跡の両方を要求する。
        derived_from, approval_ref = raw.get("derived_from"), raw.get("approval_ref")
        if set(raw) - {"kind", "derived_from", "approval_ref"}:
            raise TransitionError("qa source: derived-consolidation source に余分な key を持たせない")
        if not isinstance(derived_from, list) or not derived_from or not all(
            isinstance(item, str) and item.strip() for item in derived_from
        ):
            raise TransitionError(
                "qa source: derived-consolidation source.derived_from は非空の qa id 配列必須"
            )
        if not isinstance(approval_ref, str) or not approval_ref.strip():
            raise TransitionError(
                "qa source: derived-consolidation source.approval_ref は非空文字列必須"
            )
        return {
            "kind": kind,
            "derived_from": [item.strip() for item in derived_from],
            "approval_ref": approval_ref.strip(),
        }

    path, section, digest = raw.get("path"), raw.get("section"), raw.get("sha256")
    if not isinstance(path, str) or not path.strip() or path.startswith("/") or ".." in path.split("/"):
        raise TransitionError("qa source: written source.path は安全な相対パス必須")
    if not isinstance(section, str) or not section.strip():
        raise TransitionError("qa source: written source.section が空")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise TransitionError("qa source: written source.sha256 が不正")
    if not isinstance(answer, str) or hashlib.sha256(answer.encode("utf-8")).hexdigest() != digest:
        raise TransitionError("qa source: written source.sha256 が answer 原文と不一致")
    return {"kind": kind, "path": path, "section": section, "sha256": digest}


def set_qa_source(state: dict, qa_id: str, raw: object) -> None:
    """既存 qa の質問・回答を保ったまま、欠落していた出所メタデータだけを追記する。

    source を持たずに記録された qa は「対話で得たのか書面から索引したのか」を監査が
    判別できない。既登録の逐語を改変せずに出所だけを補える経路が無いと、reopen → 再確認
    という重い手順で回答そのものを作り直すことになり、かえって一次根拠を失う。

    ただし後付けであること自体は隠さない。``source_provenance`` に
    ``{"mode": "metadata_backfill", "writer": "set-qa-source"}`` を残し、対話時にその場で
    記録された source と区別できるようにする。既存 source の上書きは常に拒否する
    (同一 payload の再適用のみ冪等に受け入れる)。
    """
    entry = _find_qa(state, qa_id, "set-qa-source")
    normalized = normalize_qa_source(raw, entry.get("answer"))
    provenance = {"mode": "metadata_backfill", "writer": "set-qa-source"}
    repair = {"mode": "type_repair", "writer": "set-qa-source"}

    existing = entry.get("source")
    if existing is not None and not isinstance(existing, dict):
        # 契約は source を object と定めるが、素の文字列 (注記) が混入した state がある。
        # 型不正は「対話経路で記録済みの source」ではなく壊れた値なので保護対象に含めず、
        # 注記本文を source_note へ退避したうえで契約形状へ修復する。捨てると
        # 「なぜこの qa が存在するか」の唯一の手掛かりを失うため、必ず保存する。
        # 退避先は「読める注記」なので非空文字列に揃える (schema は minLength 1)。
        entry["source_note"] = (
            existing
            if isinstance(existing, str) and existing.strip()
            else f"(契約外の source を修復時に退避: {existing!r})"
        )
        entry["source"] = normalized
        entry["source_provenance"] = repair
        return

    if existing is not None:
        # 修復済み (type_repair) の再適用も、同一 payload なら冪等に受け入れる。
        if entry.get("source_provenance") not in (provenance, repair):
            raise TransitionError(
                "set-qa-source: 対話経路で記録済みの source は保護し、"
                f"後付けへの差し替えを拒否: {entry['id']}"
            )
        if existing != normalized:
            raise TransitionError(
                f"set-qa-source: 補完済み source と異なる値の再適用は拒否: {entry['id']}"
            )
        return

    entry["source"] = normalized
    entry["source_provenance"] = provenance


def set_qa_design_applications(state: dict, qa_id: str, raw: object) -> None:
    """既存 qa の問答本文を書き換えずに、design_applications だけを後付けする。

    対象は legacy_exempt=true と理由を持つ旧 qa に限る。後付けであることは
    design_application_provenance に残し、対話時に記録したものと区別できるようにする。
    """
    entry = _find_qa(state, qa_id, "set-qa-design-applications")
    qa_id = entry["id"]

    normalized = normalize_design_applications(raw)
    provenance = {
        "mode": "legacy_backfill",
        "writer": "set-qa-design-applications",
    }
    existing = entry.get("design_applications")
    existing_provenance = entry.get("design_application_provenance")
    if existing_provenance is not None:
        # schema が許す provenance はこの形だけだが、手書き JSON は schema / coverage の
        # ゲートより先にここへ届くため、writer 側でも明示的に検査する。
        if existing_provenance != provenance:
            raise TransitionError(
                f"set-qa-design-applications: 既存 provenance の上書きは拒否: {qa_id}"
            )
        if existing is None:
            raise TransitionError(
                "set-qa-design-applications: 完了済み provenance に対する "
                f"design_applications 欠落を検出: {qa_id}"
            )
        if normalize_design_applications(existing) != normalized:
            raise TransitionError(
                "set-qa-design-applications: 完了済み backfill と異なる "
                f"design_applications の再適用は拒否: {qa_id}"
            )
        # 完了済み backfill の同値再適用だけを冪等に受け入れる。
        entry.pop("legacy_exempt", None)
        entry.pop("legacy_exempt_reason", None)
        return

    if existing is not None:
        raise TransitionError(
            "set-qa-design-applications: provenance の無い既存 design_applications は"
            f"対話経路として保護し、legacy_backfill への変更を拒否: {qa_id}"
        )
    reason = entry.get("legacy_exempt_reason")
    if entry.get("legacy_exempt") is not True or not isinstance(reason, str) or not reason.strip():
        raise TransitionError(
            "set-qa-design-applications: legacy_exempt=true と非空の "
            f"legacy_exempt_reason を持つ旧 qa のみ補完可能: {qa_id}"
        )

    entry["design_applications"] = normalized
    entry["design_application_provenance"] = provenance
    # 検査済みの backfill が済んだので、一時的な legacy 免除は外す。
    entry.pop("legacy_exempt", None)
    entry.pop("legacy_exempt_reason", None)


# knowledge_ref の実在は validator と同じ解決規則 (repo root → 自 plugin root) で判定する。writer だけが
# repo root で判定すると、plugin を別の場所へ install した repo で、validator が有効と認める参照の付け替えを
# 許し、推奨形 (plugins/<plugin>/...) への訂正を拒む。
_KNOWLEDGE_REFS_PATH = Path(__file__).resolve().parents[3] / "scripts" / "validate-design-knowledge-refs.py"
_KNOWLEDGE_REFS_SPEC = importlib.util.spec_from_file_location(
    "system_spec_design_knowledge_refs", _KNOWLEDGE_REFS_PATH
)
if _KNOWLEDGE_REFS_SPEC is None or _KNOWLEDGE_REFS_SPEC.loader is None:
    raise ImportError(f"cannot load knowledge_ref resolver: {_KNOWLEDGE_REFS_PATH}")
_KNOWLEDGE_REFS = importlib.util.module_from_spec(_KNOWLEDGE_REFS_SPEC)
_KNOWLEDGE_REFS_SPEC.loader.exec_module(_KNOWLEDGE_REFS)


def _split_knowledge_ref(ref: str, label: str) -> tuple[str, str]:
    if not isinstance(ref, str) or not ref.strip():
        raise TransitionError(f"fix-qa-knowledge-ref: {label} は非空文字列必須")
    raw_path, _, anchor = ref.partition("#")
    raw_path = raw_path.strip()
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise TransitionError(
            f"fix-qa-knowledge-ref: {label} は repo root 配下の安全な相対パス必須: {raw_path!r}"
        )
    return raw_path, anchor.strip()


def fix_qa_knowledge_ref(
    state: dict, qa_id: str, old_ref: str, new_ref: str, repo_root: object
) -> None:
    """壊れた knowledge_ref だけを、解釈本文を一切変えずに実在する参照へ差し替える。

    ``set_qa_design_applications`` は design_applications 配列を丸ごと一単位として保護するため、
    対話経路 (provenance なし) の entry では綴り違いすら訂正できない。しかし参照先の実在しない
    引用は「この知識に基づいて判断した」という主張の根拠を持たず、放置すると
    ``validate-design-knowledge-refs.py`` が恒久的に赤になる。

    契約の保護意図は「対話で得た解釈内容を後から AI が書き換えないこと」なので、次の全条件を
    満たす場合に限って knowledge_ref だけの差し替えを許す。1 つでも欠ければ拒否する。

    - principle / applicability / rationale / tradeoffs は一切触らない (照合対象ですらない)。
    - 旧 ref の path が**実在しない** (実在する参照の付け替え=解釈の変更は許さない)。実在は
      ``validate-design-knowledge-refs.py`` と同じ解決規則 (repo root → 自 plugin root) で判定する。
      例外として、path は実在するが anchor の見出しが実在しない参照は、**同じ文書内**の見出しへの
      訂正に限って許す (どの文書で判断したかは変わらず、validator も赤にする壊れた引用なので)。
      別文書への付け替えは解釈の変更として拒否する。
    - 新 ref の path が実在し、anchor 指定があればその見出しも実在する。
    - 該当する application が 1 件以上ある。

    差し替えは ``knowledge_ref_corrections`` へ append-only で記録し、対話時の引用と
    後からの訂正を監査が区別できるようにする。同一の訂正の再適用は冪等に no-op とする。
    """
    entry = _find_qa(state, qa_id, "fix-qa-knowledge-ref")
    root = Path(repo_root)
    old_path, old_anchor = _split_knowledge_ref(old_ref, "old_ref")
    new_path, new_anchor = _split_knowledge_ref(new_ref, "new_ref")
    if old_ref == new_ref:
        raise TransitionError("fix-qa-knowledge-ref: old_ref と new_ref が同一")

    applications = entry.get("design_applications")
    if not isinstance(applications, list) or not applications:
        raise TransitionError(
            f"fix-qa-knowledge-ref: design_applications を持たない qa: {qa_id}"
        )

    if not any(item.get("knowledge_ref") == old_ref for item in applications):
        # 冪等な再適用: 訂正は既に入っていて、その記録も残っている。
        if any(item.get("knowledge_ref") == new_ref for item in applications) and any(
            record.get("old_ref") == old_ref and record.get("new_ref") == new_ref
            for record in entry.get("knowledge_ref_corrections", [])
        ):
            return
        raise TransitionError(
            f"fix-qa-knowledge-ref: old_ref に一致する design_application が無い: {qa_id}"
        )

    old_target = _KNOWLEDGE_REFS.resolve_knowledge_path(old_path, root)
    anchor_only_broken = (
        old_target is not None
        and bool(old_anchor)
        and old_anchor not in _KNOWLEDGE_REFS.headings(old_target.read_text(encoding="utf-8"))
    )
    if old_target is not None and not anchor_only_broken:
        raise TransitionError(
            "fix-qa-knowledge-ref: 実在する参照の付け替えは解釈の変更にあたるため拒否: "
            f"{old_path}"
        )
    target = _KNOWLEDGE_REFS.resolve_knowledge_path(new_path, root)
    if target is None:
        raise TransitionError(f"fix-qa-knowledge-ref: new_ref の参照先が実在しない: {new_path}")
    if new_anchor:
        if new_anchor not in _KNOWLEDGE_REFS.headings(target.read_text(encoding="utf-8")):
            raise TransitionError(
                f"fix-qa-knowledge-ref: new_ref の見出しが実在しない: {new_path}#{new_anchor}"
            )
    if anchor_only_broken and target.resolve() != old_target.resolve():
        raise TransitionError(
            "fix-qa-knowledge-ref: 見出しだけが壊れた参照の訂正は同じ文書内に限る "
            f"(別文書への付け替えは解釈の変更にあたるため拒否): {old_path} → {new_path}"
        )

    changed = 0
    for item in applications:
        if item.get("knowledge_ref") == old_ref:
            item["knowledge_ref"] = new_ref
            changed += 1
    entry.setdefault("knowledge_ref_corrections", []).append(
        {
            "old_ref": old_ref,
            "new_ref": new_ref,
            "applied_to": changed,
            "writer": "fix-qa-knowledge-ref",
            "reason": (
                "見出しが実在しない引用を、解釈本文と参照文書を変えずに同じ文書内の実在する見出しへ接地させる"
                if anchor_only_broken
                else "参照先が実在しない引用を、解釈本文を変えずに実在する参照へ接地させる"
            ),
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


def _require_confirm_design_applications(state: dict, turn: dict) -> None:
    """schema 1.1 の state では、confirm の根拠 qa が design_applications を持つことを課す。

    1.1 は「確定した要件がどの設計知識をどう適用したか」を qa entry に残す契約である。
    qa entry を書く前に検査し、契約を満たさない turn では qa_log にも何も残さない。
    1.0 の state (marker なし) には課さない。
    """
    if state.get("design_application_contract_version") != DESIGN_APPLICATION_CONTRACT_VERSION:
        return
    qa_id = turn.get("qa_id")
    confirmed_refs = {
        op.get("qa_ref") or qa_id
        for op in turn.get("ops", [])
        if isinstance(op, dict) and op.get("action") == "confirm"
    }
    for qa_ref in confirmed_refs:
        if not qa_ref:
            continue
        existing = _qa_entry(state, qa_ref)
        if existing is None:
            if qa_ref != qa_id:
                raise TransitionError(
                    f"schema 1.1 の confirm は qa_log entry を参照する必要がある: {qa_ref}"
                )
            normalize_design_applications(turn.get("design_applications"))
            continue
        normalize_design_applications(existing.get("design_applications"))


def apply_turn(state: dict, turn: dict) -> None:
    """1 ターン (質問→回答→反映) をまとめて適用する。

    turn.qa_id があれば qa_log へ、turn.approval_id があれば approval_log へ
    エントリを登録し、confirm op に qa_ref を、approval を伴う exclude / set-approval op に
    approval_ref を、supersede-qa op に superseded_by (= turn.qa_id) を補完してから
    各セル op を適用する。適用後に集約と hearing_progress を導き直す。
    """
    qa_id = turn.get("qa_id")
    _require_confirm_design_applications(state, turn)
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
        # confirm と同 turn で承認を得た場合、その turn の approval_id を確定セルへ紐づける。
        # turn 境界は state に永続化されないため、この場でしか対応を残せない。
        if op.get("action") == "set-approval" and not op.get("approval_ref") and appr_id:
            op["approval_ref"] = appr_id
        if (
            op.get("action") == "supersede-qa"
            and not op.get("superseded_by")
            and qa_id
            and op.get("qa_id") != qa_id
        ):
            # turn の qa (いま問い直した entry) が置き換える側。op.qa_id は旧 entry。
            op["superseded_by"] = qa_id
        apply_cell_op(state, op)

    recompute_aggregates(state)
    _refresh_hearing_progress(state)


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


def run_chunk(
    state: dict,
    turns: list[dict],
    max_loops: int = MAX_LOOPS_DEFAULT,
    require_all: bool = False,
) -> int:
    """1 invocation ぶん (最大 max_loops ターン) を適用し、状態を保存可能にする。

    max_loops 到達で未収集が残れば hearing_progress.complete=false・next_question
    非 null を保存して resumable にする。未収集 0 のときだけ complete=true。
    未収集セルは完了扱いしない。処理ターン数を返す。

    max_loops を超える turn は適用しない (per-invocation chunk limit)。complete は
    「未収集セルが 0」を意味するだけで turn を消化した証跡にはならないため、未消化が
    あれば必ず stderr へ出し、``require_all=True`` では TransitionError で止める。
    実際の max_loops は hearing_progress.max_loops に残し、再開時に上限を確かめられるようにする。
    """
    processed = 0
    state["hearing_progress"]["loop_count"] = 0
    for turn in turns:
        if processed >= max_loops:
            break
        apply_turn(state, turn)
        processed += 1
        state["hearing_progress"]["loop_count"] = processed

    recompute_aggregates(state)
    _refresh_hearing_progress(state)
    state["hearing_progress"]["max_loops"] = max_loops

    unprocessed = len(turns) - processed
    if unprocessed > 0:
        message = (
            f"chunk: 投入 {len(turns)} turn のうち {processed} turn を適用し、"
            f"{unprocessed} turn が未消化のまま残った (max_loops={max_loops})。"
            f"未消化分は次の chunk 呼出しへ切り出して再投入すること。"
        )
        if require_all:
            raise TransitionError(message)
        print(f"WARNING: {message}", file=sys.stderr)
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


# writer が存在を前提に state[...] で読む envelope のキー。
STATE_REQUIRED_KEYS = {
    "categories": list,
    "matrix": dict,
    "qa_log": list,
    "approval_log": list,
    "hearing_progress": dict,
}
# 古い state には無いことがある (writer が get/setdefault で補う) キー。あれば型を確かめる。
STATE_OPTIONAL_KEYS = {
    "platforms": list,
    "reopen_log": list,
    "category_aggregate": dict,
    "targets": list,
    "requirements_foundation": dict,
    "decisions": list,
    "knowledge_candidates": list,
    "design_applications": dict,
}


def load_state(path: str) -> dict:
    """spec-state を読み、writer が前提にする envelope の形を遷移の前に確かめる。

    JSON として読めても object でない state (``[]`` など) や envelope の型が崩れた state を
    遷移へ渡すと、KeyError や AttributeError の traceback で落ちる。形の崩れは遷移の可否を
    判定できない入力なので TransitionError (exit 1) にし、元の state は変えない。
    """
    state = load_json(path)
    if not isinstance(state, dict):
        raise TransitionError(f"spec-state は object 必須 (got {type(state).__name__}): {path}")
    broken = [
        f"{key} ({kind.__name__} 必須)"
        for key, kind in STATE_REQUIRED_KEYS.items()
        if not isinstance(state.get(key), kind)
    ] + [
        f"{key} ({kind.__name__} 必須)"
        for key, kind in STATE_OPTIONAL_KEYS.items()
        if key in state and not isinstance(state[key], kind)
    ]
    if broken:
        raise TransitionError(f"spec-state の envelope が不正: {', '.join(broken)}: {path}")
    return state


def _require_ops(ops, label: str) -> list:
    if not isinstance(ops, list) or not all(isinstance(op, dict) for op in ops):
        raise TransitionError(f"{label} は object の配列必須")
    return ops


def load_turns(path: str) -> list:
    """chunk の turns を読み、object の配列で各 ops も object の配列であることを確かめる。"""
    turns = load_json(path)
    _require_ops(turns, f"turns ({path})")
    for i, turn in enumerate(turns):
        _require_ops(turn.get("ops", []), f"turns[{i}].ops ({path})")
    return turns


def _require_catalog_for_confirm(ops: list, catalog_path: str | None) -> None:
    """confirm を含む apply / chunk は --required-info を必須にする (SKILL.md の収集ゲート)。

    回答を蓄積するだけの turn や reopen は引数なしで通す (spec-state-contract.md)。
    """
    if catalog_path is None and any(op.get("action") == "confirm" for op in ops):
        raise UsageError(
            "confirm を含む apply / chunk は --required-info <required-info-catalog.json> が必須"
            " (候補 state の必須情報の接地を確かめてから書く)"
        )


def load_json_arg(raw: str):
    """JSON文字列またはファイルpathを安全に読む (長いJSONをpath扱いしない)。"""
    stripped = raw.lstrip()
    if stripped.startswith(("{", "[")):
        return json.loads(raw)
    return json.loads(Path(raw).read_text(encoding="utf-8"))


def dump_state(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


def _emit(state: dict, out: str | None) -> None:
    """state を stdout か out へ書く。out は同じディレクトリの一時ファイルから置き換える。

    spec-state.json はこの writer だけが書く正本なので、書込の途中で落ちても (容量不足・
    中断) 前の版か新しい版のどちらかが残り、途中まで書いた JSON が残らないようにする。
    symlink はその先のファイルを置き換え、既存ファイルの permission を引き継ぐ。
    親ディレクトリが無ければ作る (bootstrap は対象 repo にまだ system-spec 配下が無い状態から始まる)。
    """
    text = dump_state(state)
    if not out:
        sys.stdout.write(text)
        return
    target = Path(os.path.realpath(out))
    try:
        mode = target.stat().st_mode & 0o7777
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _validate_candidate_required_info(state: dict, catalog_path: str | None) -> None:
    """候補 state の既存接地検証を通してからだけ _emit で公開する。

    CLI は入力をメモリへ load して遷移を適用するため、元ファイルの確定を
    先に変える必要はない。検証器を再実装せず、同じ postcondition を候補へ適用する。

    catalog 自体の不正 (object でない・validator が catalog 単体で findings を返す・型の
    崩れで validator が例外を出す) は、候補 state の接地不足 (TransitionError) と分けて
    CatalogError にする。前者は呼び出し側の設定の誤りで、遷移の可否を判定できていない。
    """
    if catalog_path is None:
        return  # confirm を含まない apply / chunk。confirm を含むときは main が先に拒否する。
    catalog = load_json(catalog_path)
    if not isinstance(catalog, dict):
        raise CatalogError(f"required-info catalog は object 必須: {catalog_path}")
    path = Path(__file__).resolve().parents[3] / "scripts" / "validate-knowledge-graph.py"
    spec = importlib.util.spec_from_file_location("required_info_candidate_validator", path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    try:
        catalog_findings, _ = validator.validate_required_info(catalog)
    except (TypeError, ValueError, AttributeError) as exc:
        raise CatalogError(
            f"required-info catalog の形が不正で検証できない ({type(exc).__name__}: {exc}): {catalog_path}"
        ) from exc
    if catalog_findings:
        raise CatalogError(
            f"required-info catalog が不正: {catalog_path}: " + "; ".join(catalog_findings)
        )
    findings, _ = validator.validate_required_info(catalog, state)
    if findings:
        raise TransitionError("required-info 候補state検証失敗: " + "; ".join(findings))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="spec-state.json 単一 transition writer (run-system-spec-elicit)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    schema_help = (
        "state の schema_version。1.1 は confirm の根拠 qa に design_applications を課す "
        "(既定は bootstrap が 1.0、init が既存 state の版を引き継ぐ。1.1 から 1.0 へは戻せない)"
    )
    p_boot = sub.add_parser("bootstrap", help="R0 用の空 state envelope を生成")
    p_boot.add_argument("--schema-version", choices=STATE_SCHEMA_VERSIONS, help=schema_help)
    p_boot.add_argument("--out")

    p_init = sub.add_parser("init", help="taxonomy からマトリクスを初期化")
    p_init.add_argument("--taxonomy", required=True)
    p_init.add_argument("--state", help="bootstrap済みstate (foundation/decisionsを保持)")
    p_init.add_argument("--schema-version", choices=STATE_SCHEMA_VERSIONS, help=schema_help)
    p_init.add_argument("--out")

    p_cat = sub.add_parser("add-category", help="taxonomy に無いカテゴリ行を 1 件足す")
    p_cat.add_argument("--state", required=True)
    p_cat.add_argument("--category", required=True, help="category JSON文字列またはファイル ({id, label})")
    p_cat.add_argument("--out")

    p_apply = sub.add_parser("apply", help="単一セル op を適用")
    p_apply.add_argument("--state", required=True)
    p_apply.add_argument("--op", required=True, help="JSON 文字列の cell op")
    p_apply.add_argument("--required-info", help="候補stateの必須情報接地をcommit前に検証するcatalog (confirm を含むときは必須)")
    p_apply.add_argument("--out")

    p_chunk = sub.add_parser("chunk", help="ターン列を 1 invocation ぶん適用")
    p_chunk.add_argument("--state", required=True)
    p_chunk.add_argument("--turns", required=True, help="ターン列 JSON ファイル")
    p_chunk.add_argument("--max-loops", type=int, default=MAX_LOOPS_DEFAULT)
    p_chunk.add_argument(
        "--require-all",
        action="store_true",
        help="投入 turn を全て消化できない場合に非 0 終了する (未消化の黙殺を防ぐ)",
    )
    p_chunk.add_argument("--required-info", help="候補stateの必須情報接地をcommit前に検証するcatalog (confirm を含むときは必須)")
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

    p_qa_source = sub.add_parser(
        "set-qa-source", help="既存 qa の質問・回答を保ったまま欠落した出所メタデータだけを追記"
    )
    p_qa_source.add_argument("--state", required=True)
    p_qa_source.add_argument("--qa-id", required=True)
    p_qa_source.add_argument(
        "--source",
        required=True,
        help='source JSON または JSON ファイル (例: {"kind":"user-dialogue"})',
    )
    p_qa_source.add_argument("--out")

    p_qa_design = sub.add_parser(
        "set-qa-design-applications", help="既存 qa の質問・回答を保ったまま設計適用を追記"
    )
    p_qa_design.add_argument("--state", required=True)
    p_qa_design.add_argument("--qa-id", required=True)
    p_qa_design.add_argument(
        "--applications", required=True, help="design_applications JSON配列または JSON ファイル"
    )
    p_qa_design.add_argument("--out")

    p_qa_ref = sub.add_parser(
        "fix-qa-knowledge-ref",
        help="解釈本文を変えず、実在しない knowledge_ref だけを実在する参照へ差し替え",
    )
    p_qa_ref.add_argument("--state", required=True)
    p_qa_ref.add_argument("--qa-id", required=True)
    p_qa_ref.add_argument("--old-ref", required=True, help="実在しない現行 knowledge_ref")
    p_qa_ref.add_argument("--new-ref", required=True, help="実在する差し替え先 knowledge_ref")
    p_qa_ref.add_argument("--repo-root", required=True, help="参照先の実在を確認する repo root")
    p_qa_ref.add_argument("--out")

    args = ap.parse_args(argv)

    try:
        if args.cmd == "bootstrap":
            _emit(bootstrap_state(args.schema_version or LEGACY_STATE_SCHEMA_VERSION), args.out)
        elif args.cmd == "init":
            existing = load_state(args.state) if args.state else None
            state = init_state(load_json(args.taxonomy), existing, args.schema_version)
            _emit(state, args.out)
        elif args.cmd == "add-category":
            state = load_state(args.state)
            add_category(state, load_json_arg(args.category))
            _emit(state, args.out or args.state)
        elif args.cmd == "apply":
            op = json.loads(args.op)
            if not isinstance(op, dict):
                raise TransitionError(f"--op は object 必須 (got {type(op).__name__})")
            _require_catalog_for_confirm([op], args.required_info)
            state = load_state(args.state)
            apply_turn(state, {"ops": [op]})
            _validate_candidate_required_info(state, args.required_info)
            _emit(state, args.out or args.state)
        elif args.cmd == "chunk":
            turns = load_turns(args.turns)
            applied = turns[: max(args.max_loops, 0)]
            _require_catalog_for_confirm(
                [op for turn in applied for op in turn.get("ops", [])], args.required_info
            )
            state = load_state(args.state)
            run_chunk(state, turns, max_loops=args.max_loops, require_all=args.require_all)
            _validate_candidate_required_info(state, args.required_info)
            _emit(state, args.out or args.state)
        elif args.cmd == "aggregate":
            state = load_state(args.state)
            recompute_aggregates(state)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-targets":
            state = load_state(args.state)
            raw = args.targets
            targets = load_json_arg(raw)
            if isinstance(targets, dict) and "targets" in targets:
                targets = targets["targets"]
            set_targets(state, targets)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-foundation":
            state = load_state(args.state)
            raw = args.foundation
            foundation = load_json_arg(raw)
            set_foundation(state, foundation)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-decision":
            state = load_state(args.state)
            raw = args.decision
            decision = load_json_arg(raw)
            set_decision(state, decision)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-knowledge-candidate":
            state = load_state(args.state)
            candidate = load_json_arg(args.candidate)
            set_knowledge_candidate(state, candidate)
            _emit(state, args.out or args.state)
        elif args.cmd == "set-qa-source":
            state = load_state(args.state)
            set_qa_source(state, args.qa_id, load_json_arg(args.source))
            _emit(state, args.out or args.state)
        elif args.cmd == "set-qa-design-applications":
            state = load_state(args.state)
            value = load_json_arg(args.applications)
            if isinstance(value, dict) and "design_applications" in value:
                value = value["design_applications"]
            set_qa_design_applications(state, args.qa_id, value)
            _emit(state, args.out or args.state)
        elif args.cmd == "fix-qa-knowledge-ref":
            state = load_state(args.state)
            fix_qa_knowledge_ref(state, args.qa_id, args.old_ref, args.new_ref, args.repo_root)
            _emit(state, args.out or args.state)
    except TransitionError as exc:
        print(f"TransitionError: {exc}", file=sys.stderr)
        return 1
    except CatalogError as exc:
        print(f"CatalogError: {exc}", file=sys.stderr)
        return 2
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        # UnicodeError: JSON の `\ud800` などは読めても UTF-8 へ書けない (書込前の版は残る)。
        print(f"IO/JSON error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
