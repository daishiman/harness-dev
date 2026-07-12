#!/usr/bin/env python3
# /// script
# name: feedback_contract_ssot
# purpose: feedback_contract.criteria 制約の単一正本 (SSOT)。複数 lint/validator が共有する。
# inputs: []  (import 専用モジュール。CLI なし)
# outputs: []
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, D, E]
# network: false
# write-scope: none
# ///
"""feedback_contract.criteria の制約を一箇所に集約した SSOT モジュール。

従来 `id` の pattern / `verify_by` の enum / `loop_scope` / 必須キーは
  - build-flags.schema.json#/properties/feedback_contract
  - skill-build-trace.schema.json#/properties/feedback_contract
  - validate-build-trace.py の CRITERIA_ID_RE / CRITERIA_VERIFY_BY
の3者にミラーされ「値を変える際は3者同時更新」という drift 温床だった。
本モジュールを唯一の正本とし、validate-build-trace.py / lint-feedback-contract.py /
lint-content-review.py が import して共有する (Python による機械 SSOT)。

JSON schema 側は cross-file $ref をハンドロール validator が解決できないため、
本モジュールを正本とし schema の制約記述は「正本=feedback_contract_ssot.py」と注記する。
"""
from __future__ import annotations

import re

# --- criteria 単一正本 (この4定数が唯一の真実) ---
CRITERIA_ID_RE = re.compile(r"^(IN|OUT|C)[0-9]+$")
CRITERIA_VERIFY_BY = {"lint", "test", "script", "evaluator", "elegant-review", "live-trial", "human"}
LOOP_SCOPES = {"inner", "outer"}
REQUIRED_CRITERION_KEYS = ("id", "loop_scope", "text", "verify_by")

# --- kind 分類 (loop 実行系=criteria 必須 / ref・assign=N/A escape 可) ---
FEEDBACK_LOOP_KINDS = {"run", "wrap", "delegate"}
FEEDBACK_SKIP_KINDS = {"ref", "assign"}

# --- kind 抽出の単一実装 (lint 群が共有。末尾 # コメント / ハイフン kind を許容) ---
# 従来 lint-feedback-contract.py と lint-content-review.py が別正規表現を持ち、
# 片方だけ末尾コメントを許容する乖離 (kind: run  # ... を一方が None 誤判定) があった。
_KIND_RE = re.compile(r"^kind:\s*([a-z-]+)\s*(?:#.*)?$", re.M)


def read_kind(text: str) -> str | None:
    """SKILL.md frontmatter から kind 値を抽出 (末尾コメント・ハイフン許容)。"""
    m = _KIND_RE.search(text)
    return m.group(1) if m else None


# --- fail-closed フォールバック文面の単一正本 ---
# brief が per-skill criteria を持たない場合、render-frontmatter.py が下記既定を焼き込む。
# 全 loop-kind で skill 名/goal を差し替えただけの同語反復になり per-skill 性が空洞化する
# (Goodhart の罠)。内容妥当性は LLM 層 (content-review) が担保する二層分離が前提だが、
# 機械層でも「フォールバック既定がそのまま残存」は is_fallback_text で WARN 可視化する。
FALLBACK_INNER_SUFFIX = "の完了チェックリストと決定論 lint が全て exit0 で通過する"
FALLBACK_OUTER_SUFFIX = "がユーザー目的を満たし、run-elegant-review の4条件が全て PASS する"


def fallback_inner_text(skill_name: str) -> str:
    """brief 不在時の inner criteria 既定文 (render-frontmatter と同源)。"""
    return f"{skill_name} {FALLBACK_INNER_SUFFIX}"


def fallback_outer_text(goal: str) -> str:
    """brief 不在時の outer criteria 既定文 (render-frontmatter と同源)。"""
    return f"{goal} {FALLBACK_OUTER_SUFFIX}"


def is_fallback_text(text: object) -> bool:
    """criteria.text が brief 非導出のフォールバック既定 (同語反復) かを判定。"""
    t = str(text or "").strip()
    return t.endswith(FALLBACK_INNER_SUFFIX) or t.endswith(FALLBACK_OUTER_SUFFIX)


def validate_criteria(
    criteria: object,
    *,
    require_both_scopes: bool = True,
    prefix: str = "feedback_contract.criteria",
) -> list[str]:
    """criteria 配列を検査し errors のリストを返す (kind 非依存の純検査)。

    - 各 criterion に id/loop_scope/text/verify_by を要求
    - id は ^(IN|OUT|C)[0-9]+$ / 重複禁止
    - verify_by は CRITERIA_VERIFY_BY のいずれか
    - loop_scope は inner|outer
    - require_both_scopes=True なら inner と outer を最低各1件
    """
    errs: list[str] = []
    if not isinstance(criteria, list) or not criteria:
        return [f"{prefix} must be a non-empty array"]
    seen_ids: set[str] = set()
    seen_scopes: set[str] = set()
    for idx, item in enumerate(criteria):
        if not isinstance(item, dict):
            errs.append(f"{prefix}[{idx}] must be object")
            continue
        for key in REQUIRED_CRITERION_KEYS:
            v = item.get(key)
            if not (isinstance(v, str) and v.strip()):
                errs.append(f"{prefix}[{idx}].{key} is empty")
        cid = str(item.get("id", "")).strip()
        if cid and not CRITERIA_ID_RE.match(cid):
            errs.append(f"{prefix}[{idx}].id={cid!r} must match ^(IN|OUT|C)[0-9]+$")
        if cid and cid in seen_ids:
            errs.append(f"{prefix}[{idx}].id={cid!r} duplicated")
        seen_ids.add(cid)
        vb = str(item.get("verify_by", "")).strip()
        if vb and vb not in CRITERIA_VERIFY_BY:
            errs.append(
                f"{prefix}[{idx}].verify_by={vb!r} not in {sorted(CRITERIA_VERIFY_BY)}"
            )
        scope = str(item.get("loop_scope", "")).strip().lower()
        if scope and scope not in LOOP_SCOPES:
            errs.append(f"{prefix}[{idx}].loop_scope={scope!r} must be inner or outer")
        elif scope:
            seen_scopes.add(scope)
    if require_both_scopes:
        for required_scope in ("inner", "outer"):
            if required_scope not in seen_scopes:
                errs.append(
                    f"{prefix} must include >=1 {required_scope} loop_scope criterion"
                )
    return errs


# ─────────────────────────────────────────────────────────────────────────
# dogfooding 境界の SSOT (ADR)
# ─────────────────────────────────────────────────────────────────────────
# harness-creator 自身 (skill を量産する生成器メタプラグイン) に対する除外/非除外
# ルールは **機構ごとに非対称** である。従来は制御リテラル "harness-creator" が
#   - scripts/lint-feedback-protocol.py                         (feedback 配備/周知から除外)
#   - plugins/.../run-elegant-review/scripts/check-review-trigger.py (Stop block 除外)
#   - plugins/.../run-build-skill/scripts/render-combinators.py      (symlink 配備除外)
#   - scripts/lint-content-review.py (EXEMPT_PLUGINS=set() で「非除外」を空集合で暗黙表現)
# の4 consumer に独立散在し、非対称ルールの SSOT が存在しなかった (findings SS-01/08/10)。
# 本ブロックを唯一の正本とし、各 consumer は下記述語を import 共有する。除外プラグインを
# 足す / 意味を変える際は **ここだけ** を編集すれば全 consumer に伝播する。
#
# 非対称ルールの要約 (なぜ除外/非除外か):
#   | 機構                          | harness-creator | 理由                                            |
#   |-------------------------------|---------------|-------------------------------------------------|
#   | Stop hook decision:block      | 除外 (True)   | 自己編集セッションの自己ブロック=評価不能(無限ループ)を回避 |
#   | feedback-loop 配備/周知 (symlink/R6/R7) | 除外 (True) | 生成器自身=run-skill-feedback の正本。自分への symlink は循環 |
#   | content-review verdict (CI/pre-push)    | 非除外 (False) | dogfooding 対象。自己改善の品質も CI で機械強制する |
#   | iter-improve 被験体コピー (INV7)        | 交差時 True   | エンジン閉包 skill を被験体にすると編集エンジン=被験体の自己言及。隔離コピー強制 |
SELF_DOGFOODING_PLUGIN = "harness-creator"

# 収束ポリシー / 評価経路を構成するエンジン閉包 (INVARIANT 7)。iter-improve が
# この閉包の skill 自体を被験体にすると、編集エンジンと被験体が同一実体になり
# 評価が自己言及で壊れる。閉包の列挙はこの frozenset のみ (consumer への
# ハードコード散在禁止 = 上記 ADR と同じ規律)。閉包を広げる時はここだけを編集する。
ENGINE_SKILLS = frozenset(
    {"run-elegant-review", "run-skill-iter-improve", "run-skill-live-trial"}
)


def is_stop_block_exempt(plugin: str) -> bool:
    """Stop hook の decision:block 対象から除外するか。

    harness-creator は True。harness-creator 自身を編集中のセッションを Stop で
    block すると、評価→改善のループが自己ブロックされて回らなくなる
    (無限ループ)。そのため Stop hook の安全弁としてのみ除外する。CI/pre-push の
    強制層では除外しない (is_content_review_exempt 参照) ため dogfooding は維持される。
    """
    return plugin == SELF_DOGFOODING_PLUGIN


def is_feedback_deploy_exempt(plugin: str) -> bool:
    """run-skill-feedback の配備/周知 (symlink 配置・R6/R7 lint) から除外するか。

    harness-creator は True。harness-creator は run-skill-feedback の SSOT 正本を保持する
    生成器自身であり、自分自身へ symlink を貼ると循環参照になる。周知 (R6) も生成器
    には不要。render-combinators.apply_feedback_loop の symlink 配備除外も
    「量産先へ配備する対象から生成器自身を外す」という同一概念なのでこの述語を共有する。
    """
    return plugin == SELF_DOGFOODING_PLUGIN


def is_content_review_exempt(plugin: str) -> bool:
    """content-review verdict (CI/pre-push) の必須化から除外するか。

    常に False。harness-creator (生成器メタプラグイン) 自身も自己改善 (dogfooding) の
    品質を保証する対象であり、SKILL.md 変更時は
    eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json を必須とする。
    上の2述語と異なり **生成器自身も除外しない** のが非対称性の要点。現状この機構で
    除外されるプラグインは存在しないため常に False を返す (空集合 EXEMPT_PLUGINS の置換)。
    """
    return False


def requires_subject_copy(plugin_name: str, target_skill: str) -> bool:
    """iter-improve が被験体を隔離コピーしてから編集すべきか (INVARIANT 7)。

    harness-creator 自身のエンジン閉包 (ENGINE_SKILLS = 収束ポリシー/評価経路を構成する
    skill) を被験体にする交差時のみ True。編集エンジンと被験体の同一実体化 (自己言及で
    評価が壊れる) を防ぐ。通常 skill は直接編集を維持する (コピー強制は閉包交差時のみ)。
    """
    return plugin_name == SELF_DOGFOODING_PLUGIN and target_skill in ENGINE_SKILLS


def criteria_ids(criteria: object) -> set[str]:
    """criteria 配列から id 集合を抽出 (空白/非 dict は無視)。"""
    out: set[str] = set()
    if not isinstance(criteria, list):
        return out
    for item in criteria:
        if isinstance(item, dict):
            cid = str(item.get("id", "")).strip()
            if cid:
                out.add(cid)
    return out


def is_loop_kind(kind: object) -> bool:
    """loop 実行系 (run/wrap/delegate) なら True。criteria 必須判定に使う。"""
    return str(kind or "").strip().lower() in FEEDBACK_LOOP_KINDS


def extract_frontmatter_feedback_contract(skill_md_text: str) -> dict | None:
    """SKILL.md テキストの YAML frontmatter から feedback_contract dict を抽出。

    yaml が import 可能ならそれを使う。無ければ feedback_contract ブロックを
    最小インデントパーサで読む (criteria の id/loop_scope/text/verify_by のみ抽出)。
    見つからなければ None。
    """
    if not skill_md_text.startswith("---"):
        return None
    parts = skill_md_text.split("\n---", 1)
    if len(parts) < 2:
        return None
    fm_text = parts[0].lstrip("-").lstrip("\n")
    try:  # 任意依存
        import yaml  # type: ignore

        data = yaml.safe_load(fm_text) or {}
        if isinstance(data, dict):
            fc = data.get("feedback_contract")
            return fc if isinstance(fc, dict) else None
    except Exception:
        pass
    return _parse_feedback_contract_block(fm_text)


def _parse_feedback_contract_block(fm_text: str) -> dict | None:
    """yaml 非搭載環境向けの最小パーサ。

    frontmatter から `feedback_contract:` ブロックを取り出し、その配下の
    `criteria:` 配列要素 (- id: .. / loop_scope: .. / text: .. / verify_by: ..) を
    抽出する。max_iterations / skip_reason のスカラも拾う。
    """
    lines = fm_text.splitlines()
    n = len(lines)
    i = 0
    fc_indent = None
    block: list[str] = []
    while i < n:
        line = lines[i]
        if fc_indent is None:
            # `feedback_contract:` 行末に YAML インラインコメント (# ...) が付くケースを許容。
            # 実 SKILL.md は `feedback_contract: # per-skill 評価基準...` の形を取るため
            # `\s*$` 固定だと yaml 非搭載環境でブロックを取りこぼし全 criteria が None になる。
            if re.match(r"^feedback_contract:\s*(#.*)?$", line):
                fc_indent = len(line) - len(line.lstrip())
                i += 1
                continue
            i += 1
            continue
        # ブロック内: より浅いインデントの非空行で終了
        if line.strip() and (len(line) - len(line.lstrip())) <= fc_indent:
            break
        block.append(line)
        i += 1
    if fc_indent is None:
        return None
    fc: dict = {}
    criteria: list[dict] = []
    cur: dict | None = None
    for line in block:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^(max_iterations|skip_reason):\s*(.+)$", stripped)
        if m and "- " not in line.split(":", 1)[0]:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            fc[key] = int(val) if key == "max_iterations" and val.isdigit() else val
            continue
        if stripped.startswith("- "):
            cur = {}
            criteria.append(cur)
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if cur is not None and ":" in stripped:
            key, val = stripped.split(":", 1)
            cur[key.strip()] = val.strip().strip('"').strip("'")
    if criteria:
        fc["criteria"] = criteria
    return fc or None
