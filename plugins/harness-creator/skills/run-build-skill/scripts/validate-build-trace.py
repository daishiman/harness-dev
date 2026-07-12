#!/usr/bin/env python3
# /// script
# name: validate-build-trace
# purpose: Validate run-build-skill reproducibility trace including 26/27/28 meta gates.
# inputs:
#   - argv: eval-log/skill-build-trace.json
# outputs:
#   - stdout: ok message
#   - stderr: validation errors
#   - exit: 0=OK / 1=validation failure / 2=usage or JSON error
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""Validate run-build-skill reproducibility trace / CapabilityManifest / Bundle.

Usage:
  # 既存(後方互換): build trace JSON を検証
  validate-build-trace.py eval-log/skill-build-trace.json

  # CapabilityManifest(任意 kind)を検証
  validate-build-trace.py --manifest path/to/SKILL.md
  validate-build-trace.py --manifest path/to/agent.md
  validate-build-trace.py --manifest path/to/plugin-composition.yaml

  # CapabilityBundle 内 capabilities[].ref の実在を一括検査
  validate-build-trace.py --bundle plugins/harness-creator/plugin-composition.yaml

  # 内蔵 self-test (3 件の代表 manifest をメモリ上で検査)
  validate-build-trace.py --self-test

CLI 出力契約 (新モード):
  stdout: JSON {"valid": bool, "kind": str|null, "findings": [str, ...]}
  exit:   0=PASS, 1=FAIL, 2=usage/parse error
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PurePosixPath

try:  # 任意依存: jsonschema があれば schema 検証を強化
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover - 環境依存
    _HAS_JSONSCHEMA = False

try:  # YAML は plugin-composition.yaml で必要。無ければ最小自前パーサで fallback
    import yaml  # type: ignore
    _HAS_YAML = True
except Exception:  # pragma: no cover
    _HAS_YAML = False


LAYER_YAML_PATH_PATTERNS = {
    "skill-local-v1": re.compile(
        r"^plugins/[a-z][a-z0-9-]*/skills/(ref|run|wrap|assign|delegate)-"
        r"[a-z0-9]+(-[a-z0-9]+)*/prompts/R[0-9]+(-[a-z0-9]+(-[a-z0-9]+)*)?\.(md|yaml)$"
    ),
    "agents-legacy": re.compile(
        r"^plugins/[a-z][a-z0-9-]*/agents/prompts/[a-z][a-z0-9-]*\.(md|yaml)$"
    ),
}
RESPONSIBILITY_ID_RE = re.compile(r"^R[0-9]+$")
PROMPT_REQUIRED_KINDS = {"run", "assign"}
PROMPT_OPTIONAL_KINDS = {"ref", "wrap"}
PROMPT_SKIP_KINDS = {"delegate"}


REQUIRED_BUILD_STEPS = {
    "problem-definition",
    "execution-layer",
    "classification",
    "naming",
    "frontmatter",
    "body",
    "support-files",
    "permissions-hooks",
    "validation",
    "operation-improvement",
}

REQUIRED_DOC_COVERAGE = {
    "02-skill-structure",
    "03-frontmatter",
    "04-invocation-permissions",
    "05-layering",
    "06-classification-naming",
    "07-progressive-disclosure",
    "08-skill-writing-guidelines",
    "09-evaluation-orchestration",
    "10-subagents-hooks-integration",
    "11-templates",
    "13-checklists",
    "14-dynamic-context-injection",
    "15-official-source-notes",
    "16-official-skills-reference",
    "26-meta-skill-dogfooding",
    "27-rubric-governance-runbook",
    "28-script-execution-model",
    "29-multi-project-rubric-composition",
    "30-paradigm-analogy-map",
    "31-output-routing-adapter-architecture",
    "32-creator-kit-implementation-ledger",
    "33-change-governance",
    "34-plugin-governance-roadmap",
    "35-meta-harness-feedback-loop",
}

REQUIRED_LAYERS = {"Skill", "Subagent", "Hook", "MCP", "CLI", "script"}
REQUIRED_GATES = {"lint", "evaluator", "elegant_review", "governance"}
REQUIRED_SCRIPT_CONTEXTS = {"A", "B", "C", "D", "E"}
REQUIRED_GOVERNANCE_ROLES = {"proposer", "reviewer", "approver", "tooling"}

# RTM (requirement_coverage): brief の非空フィールドのうち被覆宣言を要求しないもの。
# 識別・分類・build フラグ配管系は他ゲート (lint-skill-name / brief schema enum /
# variant_support クロスチェック / resolve-brief-to-category) が既に担保している。
NON_REQUIREMENT_BRIEF_FIELDS = {
    "skill_name", "prefix", "kind", "role_suffix", "hierarchy_level",
    "output_language", "parameter_language_exception",
    "source_url_or_path", "source_tier", "last_audited_date", "audit_trigger",
    "mass_production_profile", "paradigm_profile",
    "consult_build_knowledge", "with_subagent_hint", "with_hooks",
}
REQUIREMENT_DISPOSITIONS = {"mapped", "not_applicable"}
# brief フィールドパス: 例 key_constraints[2] / boundary / knowledge_loop.pattern
REQUIREMENT_ID_PATH_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\[[0-9]+\])*(\.[A-Za-z_][A-Za-z0-9_]*(\[[0-9]+\])*)*$"
)
_BRIEF_BASENAME_RE = re.compile(r"skill-brief[^/]*\.json$")


def _as_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def _items_by_key(value: object, key: str) -> dict[str, dict]:
    if not isinstance(value, list):
        return {}
    out = {}
    for item in value:
        if isinstance(item, dict) and item.get(key):
            out[str(item[key])] = item
    return out


def _status_ok(item: dict) -> bool:
    status = str(item.get("status", "")).upper()
    evidence = str(item.get("evidence", "")).strip()
    reason = str(item.get("reason", "")).strip()
    if status in {"PASS", "FAIL"}:
        return bool(evidence)
    if status == "N/A":
        return bool(reason or evidence)
    return False


def _completion_status_ok(item: dict) -> bool:
    status = str(item.get("status", "")).upper()
    return status in {"PASS", "N/A"} and _status_ok(item)


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


def _resolve_brief_kind(data: dict) -> str | None:
    variant = data.get("variant_support")
    if isinstance(variant, dict):
        prefix = str(variant.get("prefix", "")).strip().lower()
        if prefix:
            return prefix
    return None


def _validate_prompt_generation_model(data: dict) -> list[str]:
    """Validate trace.prompt_generation_model against reproducibility-trace-schema.md.

    Enforces rules 1-6 from the schema: policy resolution, regex path match,
    id↔filename consistency, anchor_coverage emptiness, and required-policy
    lint PASS gating. Kind-based optionality follows agent-template.md table.
    """
    errs: list[str] = []
    model = data.get("prompt_generation_model")
    kind = _resolve_brief_kind(data)

    if not isinstance(model, dict):
        if kind in PROMPT_REQUIRED_KINDS:
            errs.append(
                f"prompt_generation_model is required when brief.kind={kind!r} "
                f"(run/assign). Schema: reproducibility-trace-schema.md"
            )
        return errs

    policy = model.get("policy_resolution")
    if not isinstance(policy, dict):
        errs.append("prompt_generation_model.policy_resolution missing")
        resolved = None
    else:
        resolved = str(policy.get("resolved_policy", "")).strip().lower()
        if resolved not in {"required", "optional", "skip"}:
            errs.append(
                f"policy_resolution.resolved_policy invalid: {resolved!r} "
                "(expected required/optional/skip)"
            )
        if not str(policy.get("resolved_via", "")).strip():
            errs.append("policy_resolution.resolved_via must explain derivation")
        if kind in PROMPT_REQUIRED_KINDS and resolved == "skip":
            errs.append(
                f"resolved_policy=skip contradicts brief.kind={kind!r} "
                "(run/assign は prompt 生成を skip できない。生成なしでも optional で宣言する)"
            )
        elif kind in PROMPT_REQUIRED_KINDS and resolved == "optional":
            # optional は「本 build が prompt を生成しない run/assign」(per_responsibility 空=
            # 上流/他skillが生成した共有 prompt を消費する等) では許容する。生成物があるのに
            # optional へ降格するのは prompt_provenance 必須化の迂回 (bypass) なので禁止する。
            # 実際の本文7層準拠は route C02 (lint-agent-prompt-content.py) の CI repo 全走査が
            # trace 非依存で独立強制するため、生成物ありの bypass はここと二層で塞がれる。
            _pr = model.get("per_responsibility")
            if isinstance(_pr, list) and _pr:
                errs.append(
                    f"resolved_policy=optional contradicts brief.kind={kind!r} with "
                    "non-empty per_responsibility (生成物があるのに optional 降格は "
                    "prompt_provenance の迂回。required + provenance にすること)"
                )
        if kind in PROMPT_SKIP_KINDS and resolved == "required":
            errs.append(
                f"resolved_policy=required contradicts brief.kind={kind!r} "
                "(delegate skips prompt-creator)"
            )

    per_resp = model.get("per_responsibility")
    if not isinstance(per_resp, list):
        errs.append("prompt_generation_model.per_responsibility must be array")
        per_resp = []

    if resolved == "required" and not per_resp:
        errs.append(
            "per_responsibility must not be empty when resolved_policy=required"
        )
    if resolved == "skip" and per_resp:
        errs.append(
            "per_responsibility must be empty when resolved_policy=skip "
            "(or escalate via policy_resolution.resolved_via)"
        )

    seen_ids: set[str] = set()
    for idx, item in enumerate(per_resp):
        if not isinstance(item, dict):
            errs.append(f"per_responsibility[{idx}] must be object")
            continue
        rid = str(item.get("id", "")).strip()
        if not RESPONSIBILITY_ID_RE.match(rid):
            errs.append(
                f"per_responsibility[{idx}].id={rid!r} must match ^R[0-9]+$"
            )
        if rid in seen_ids:
            errs.append(f"per_responsibility[{idx}].id={rid!r} duplicated")
        seen_ids.add(rid)

        convention = str(item.get("path_convention", "")).strip()
        pattern = LAYER_YAML_PATH_PATTERNS.get(convention)
        layer_path = str(item.get("layer_yaml_path", "")).strip()
        if pattern is None:
            errs.append(
                f"per_responsibility[{idx}].path_convention invalid: "
                f"{convention!r} (expected skill-local-v1 or agents-legacy)"
            )
        elif not pattern.match(layer_path):
            errs.append(
                f"per_responsibility[{idx}].layer_yaml_path={layer_path!r} "
                f"does not match {convention} regex"
            )
        elif convention == "skill-local-v1" and rid:
            stem = Path(layer_path).stem
            if stem != rid:
                errs.append(
                    f"per_responsibility[{idx}] filename {stem!r} != id {rid!r}"
                )

        if resolved == "required":
            lint_status = str(item.get("lint_status", "")).upper()
            if lint_status != "PASS":
                escalation = str(item.get("escalation", "")).strip().lower()
                if not escalation or escalation == "none":
                    errs.append(
                        f"per_responsibility[{idx}] lint_status={lint_status!r} "
                        "requires escalation != none when policy=required"
                    )

    anchor = model.get("anchor_coverage")
    if isinstance(anchor, dict):
        missing = anchor.get("missing_anchors")
        if isinstance(missing, list) and missing:
            errs.append(
                f"anchor_coverage.missing_anchors must be empty: {missing}"
            )
    elif resolved == "required":
        errs.append("anchor_coverage required when resolved_policy=required")

    cross_ref = model.get("cross_ref")
    if isinstance(cross_ref, dict):
        if cross_ref.get("join_key") != "responsibility.id":
            errs.append(
                "cross_ref.join_key must be 'responsibility.id' "
                "(reproducibility-trace-schema.md)"
            )
        if resolved == "required" and not cross_ref.get("prompt_creator_trace_path"):
            errs.append(
                "cross_ref.prompt_creator_trace_path required when policy=required"
            )

    return errs


# route C09: agent/prompt 生成が prompt-creator (7層契約) を経由し route C02 内容 lint を通過したことの証跡を強制する。
# subagent-hybrid-format.md=agent 契約 / seven-layer-format.md=prompt 契約 を source_contract_ref に許容する。
PROMPT_CONTRACT_REFS = ("subagent-hybrid-format.md", "seven-layer-format.md")


def _validate_prompt_provenance(data: dict) -> list[str]:
    """route C09 バイパス不能性: agents/prompts 生成が prompt-creator 経由 + route C02 lint 通過であることを検証。

    prompt_generation_model.policy_resolution.resolved_policy=required の build では
    prompt_provenance を必須化する。prompt_creator_invocation!=true / 契約参照欠落 /
    content_lint.status!=PASS / (policy=required 時の) ブロック欠落 はいずれも FAIL。
    """
    errs: list[str] = []
    model = data.get("prompt_generation_model")
    resolved = ""
    if isinstance(model, dict):
        policy = model.get("policy_resolution")
        if isinstance(policy, dict):
            resolved = str(policy.get("resolved_policy", "")).strip().lower()

    prov = data.get("prompt_provenance")
    if not isinstance(prov, dict):
        if resolved == "required":
            errs.append(
                "prompt_provenance is required when prompt_generation_model."
                "policy_resolution.resolved_policy=required "
                "(agent/prompt 生成は prompt-creator 経由 + C02 内容 lint 通過の証跡が必須)"
            )
        return errs

    # invocation は true 必須 (false=単独生成のバイパス試行 → 常に FAIL)
    invoked = prov.get("prompt_creator_invocation")
    if invoked is not True:
        errs.append(
            f"prompt_provenance.prompt_creator_invocation must be true (got {invoked!r}) "
            "— prompt-creator 非経由の単独生成は禁止 (bypass detected)"
        )

    ref = str(prov.get("source_contract_ref", "")).strip()
    if not ref:
        errs.append("prompt_provenance.source_contract_ref is empty (準拠した7層契約を明示すること)")
    elif not any(c in ref for c in PROMPT_CONTRACT_REFS):
        errs.append(
            f"prompt_provenance.source_contract_ref={ref!r} must reference a 7層契約 "
            f"({' / '.join(PROMPT_CONTRACT_REFS)})"
        )

    lint = prov.get("content_lint")
    if not isinstance(lint, dict):
        errs.append(
            "prompt_provenance.content_lint missing "
            "(C02 lint-agent-prompt-content --mode agent|prompt の結果を記録すること)"
        )
    else:
        mode = str(lint.get("mode", "")).strip().lower()
        if mode not in {"agent", "prompt"}:
            errs.append(f"prompt_provenance.content_lint.mode invalid: {mode!r} (agent|prompt)")
        status = str(lint.get("status", "")).strip().upper()
        if status != "PASS":
            errs.append(
                f"prompt_provenance.content_lint.status={status!r} must be PASS "
                "(C02 --mode agent|prompt が exit0 でなければ生成は未完了)"
            )

    return errs


# criteria 制約の正本は repo-root scripts/feedback_contract_ssot.py (単一 SSOT)。
# 従来 build-flags.schema / skill-build-trace.schema / 本ファイルに3者ミラーされていた
# id.pattern / verify_by.enum / loop_scope / kind 分類を一本化し drift を機械的に封じる。
#
# 解決順: (a) env CLAUDE_PLUGIN_ROOT/scripts → (b) 上方探索 (vendored plugin 内コピーを
# dev/install 双方で発見) → (c) 全滅時は最小 fallback。**絶対に raise しない**
# (build-time に plugin 単独 install されても import-time クラッシュさせない)。
# fallback 時は criteria 検証を skip し WARN を出す (build-time のみ・crash させない)。
import os as _os


def _load_feedback_contract_ssot():
    """feedback_contract_ssot を fail-soft に解決する (絶対に raise しない)。"""
    import importlib.util

    candidates: list[Path] = []
    plugin_root = _os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidates.append(Path(plugin_root) / "scripts" / "feedback_contract_ssot.py")
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidates.append(ancestor / "scripts" / "feedback_contract_ssot.py")
    for cand in candidates:
        try:
            if cand.is_file():
                spec = importlib.util.spec_from_file_location("feedback_contract_ssot", cand)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                return mod
        except Exception:
            continue
    return _fallback_feedback_contract_ssot()


def _fallback_feedback_contract_ssot():
    """SSOT 全滅時の最小 fallback。validate-build-trace が使う定数/述語のみ提供。

    criteria 検証 (validate_criteria) は SSOT 不在では正本ルールを保証できないため
    **検証を skip し WARN を1件返す** (build-time のみ・crash させない)。kind 分類定数は
    SSOT 実装と同値の保守的値。vendored コピーが常在するため通常ここには到達しない。
    """
    import re as _re
    import types

    fc = types.SimpleNamespace()
    fc.FEEDBACK_LOOP_KINDS = {"run", "wrap", "delegate"}
    fc.FEEDBACK_SKIP_KINDS = {"ref", "assign"}
    fc.CRITERIA_ID_RE = _re.compile(r"^(IN|OUT|C)[0-9]+$")
    fc.CRITERIA_VERIFY_BY = {"lint", "test", "script", "evaluator", "elegant-review", "live-trial", "human"}
    fc.validate_criteria = lambda criteria, **kw: [
        "WARN: feedback_contract_ssot.py 不在のため criteria 検証を skip しました "
        "(vendored copy が見つからない異常状態。plugins/harness-creator/scripts/ を確認)。"
    ]
    return fc


_FC = _load_feedback_contract_ssot()
FEEDBACK_LOOP_KINDS = _FC.FEEDBACK_LOOP_KINDS
FEEDBACK_SKIP_KINDS = _FC.FEEDBACK_SKIP_KINDS
CRITERIA_ID_RE = _FC.CRITERIA_ID_RE
CRITERIA_VERIFY_BY = _FC.CRITERIA_VERIFY_BY


def _resolve_trace_kind(data: dict) -> str | None:
    """trace の skill_kind(schema field)を優先し、無ければ variant_support.prefix。

    後方互換: 旧トレースは skill_kind を持たず variant_support.prefix のみ。
    """
    kind = str(data.get("skill_kind", "")).strip().lower()
    if kind:
        return kind
    return _resolve_brief_kind(data)


def _validate_feedback_contract(data: dict) -> list[str]:
    """feedback_contract.criteria を kind-aware に検査する。

    loop 実行系(run/wrap/delegate)では criteria を1件以上、各 criterion に
    id/loop_scope/text/verify_by を要求し、inner と outer を最低各1件課す。
    skip_reason での N/A escape は FEEDBACK_SKIP_KINDS(ref/assign)限定で、
    loop 実行系は skip_reason では免除されない(lint-feedback-contract.py と対称。
    trace 側だけ緩いと lint が封鎖した escape 穴が build-time に復活する)。
    required トップ配列には足さないため、kind 不明の旧トレースは検査しない
    (任意トレース破壊回避)。
    """
    errs: list[str] = []
    kind = _resolve_trace_kind(data)
    fc = data.get("feedback_contract")

    # kind 不明 or 非ループ系(ref/assign)は escape。
    if kind not in FEEDBACK_LOOP_KINDS:
        # ref/assign で feedback_contract がある場合のみ最低限の形式を確認。
        if isinstance(fc, dict) and fc.get("criteria") is not None:
            crit = fc.get("criteria")
            if not isinstance(crit, list):
                errs.append("feedback_contract.criteria must be array")
        return errs

    # ここから loop 実行系: criteria 必須(skip_reason では免除不可)。
    if not isinstance(fc, dict):
        errs.append(
            f"feedback_contract is required when skill_kind={kind!r} "
            "(loop 実行系 run/wrap/delegate)。criteria を brief.goal/Checklist から "
            f"導出してください (skip_reason escape は kind={sorted(FEEDBACK_SKIP_KINDS)} のみ)。"
        )
        return errs

    skip_reason = str(fc.get("skip_reason", "")).strip()
    criteria = fc.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        # skip_reason の N/A escape は SSOT の FEEDBACK_SKIP_KINDS(ref/assign)限定。
        # ここへ到達する kind は FEEDBACK_LOOP_KINDS のみのため、loop 実行系の
        # skip_reason は criteria 必須の免除にならない (lint-feedback-contract と対称)。
        if skip_reason and kind in FEEDBACK_SKIP_KINDS:
            return errs  # N/A escape: 明示根拠あり (ref/assign)
        errs.append(
            f"feedback_contract.criteria must list >=1 criterion when "
            f"skill_kind={kind!r} (skip_reason escape は "
            f"kind={sorted(FEEDBACK_SKIP_KINDS)} 限定。criteria を整備すること)"
        )
        return errs

    # criteria 本体の検査 (必須キー / id pattern / id 重複 / verify_by enum /
    # loop_scope / inner+outer 各1件) は SSOT (_FC.validate_criteria) に委譲し、
    # 旧来の独自再実装 (3者ミラーの drift 温床) を解消する。
    # kind 判定 / skip_reason escape / fc 必須は本 validator 固有なため上で処理済み。
    # ここに到達した時点で criteria は非空 list が保証される。
    errs.extend(
        _FC.validate_criteria(
            criteria,
            require_both_scopes=True,
            prefix="feedback_contract.criteria",
        )
    )
    return errs


# =============================================================
# requirement_coverage (RTM: 要求トレーサビリティ) 検証
# =============================================================

def _find_brief_ref(data: dict) -> str | None:
    """trace が参照する brief のパス文字列を返す (brief_path 優先、無ければ source_docs)。"""
    bp = str(data.get("brief_path", "") or "").strip()
    if bp:
        return bp
    docs = data.get("source_docs")
    if isinstance(docs, list):
        for doc in docs:
            if isinstance(doc, str) and _BRIEF_BASENAME_RE.search(doc.replace("\\", "/")):
                return doc
    return None


def _load_brief(brief_ref: str, trace_path: Path) -> dict | None:
    """brief_ref を cwd 相対 → trace 隣接の順で解決し JSON dict を返す (失敗時 None)。"""
    for cand in (Path(brief_ref), trace_path.parent / brief_ref):
        try:
            if cand.is_file():
                loaded = json.loads(cand.read_text(encoding="utf-8"))
                return loaded if isinstance(loaded, dict) else None
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _resolve_brief_field(brief: dict, path: str) -> bool:
    """requirement_id のフィールドパスが brief 上に実在するかを判定する。"""
    cur: object = brief
    for seg in path.split("."):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)((?:\[[0-9]+\])*)$", seg)
        if m is None or not isinstance(cur, dict) or m.group(1) not in cur:
            return False
        cur = cur[m.group(1)]
        for idx in re.findall(r"\[([0-9]+)\]", m.group(2)):
            if not isinstance(cur, list) or int(idx) >= len(cur):
                return False
            cur = cur[int(idx)]
    return True


def _requirement_bearing(value: object) -> bool:
    """brief フィールドが被覆すべき要求を含むか (空文字/空配列/False/None は対象外)。"""
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _validate_requirement_coverage(data: dict, trace_path: Path) -> list[str]:
    """requirement_coverage (RTM) を brief と突合して機械検査する。

    doc_coverage(参照知識の被覆)と対になる「ユーザー要望の被覆」検査。
    - requirement_coverage あり: 構造検査 + brief の非空要求フィールドの被覆完全性を
      exit 1 検査 (requirement_id の brief 上の実在も検査)
    - requirement_coverage なし: 旧 trace / brief 非経由 build は skip。ただし trace が
      brief を参照している場合は WARN (段階導入。exit code は変えない)
    - 被覆の意味的正しさ (mapped_to が本当に要求を満たすか) は content-review = LLM 層
      の責務で、ここでは検査しない (二層分離)。最小粒度は brief フィールド単位に固定し
      文分解の水増し検査はしない。
    """
    errs: list[str] = []
    rc = data.get("requirement_coverage")
    brief_ref = _find_brief_ref(data)

    if rc is None:
        if brief_ref:
            print(
                f"WARN: trace は brief ({brief_ref}) を参照していますが requirement_coverage "
                "がありません。brief の要求→生成物の写像証跡 (RTM) を記録してください "
                "(段階導入につき FAIL にはしません)。",
                file=sys.stderr,
            )
        return errs

    if not isinstance(rc, list):
        errs.append("requirement_coverage must be array")
        return errs

    # 構造検査 (brief 非解決時も常に実施)
    seen_ids: set[str] = set()
    valid_ids: list[tuple[int, str]] = []
    for idx, item in enumerate(rc):
        if not isinstance(item, dict):
            errs.append(f"requirement_coverage[{idx}] must be object")
            continue
        rid = str(item.get("requirement_id", "")).strip()
        if not REQUIREMENT_ID_PATH_RE.match(rid):
            errs.append(
                f"requirement_coverage[{idx}].requirement_id={rid!r} must be a brief "
                "field path (例: key_constraints[2] / boundary / knowledge_loop.pattern)"
            )
        else:
            if rid in seen_ids:
                errs.append(
                    f"requirement_coverage[{idx}].requirement_id={rid!r} duplicated"
                )
            seen_ids.add(rid)
            valid_ids.append((idx, rid))
        disposition = str(item.get("disposition", "")).strip()
        if disposition not in REQUIREMENT_DISPOSITIONS:
            errs.append(
                f"requirement_coverage[{idx}].disposition={disposition!r} must be "
                f"one of {sorted(REQUIREMENT_DISPOSITIONS)}"
            )
        if disposition == "mapped" and not _non_empty_string(item.get("mapped_to")):
            errs.append(
                f"requirement_coverage[{idx}].mapped_to is required when "
                "disposition=mapped (反映先: feedback_contract.criteria の id / "
                "SKILL.md 節 / 生成物パス等)"
            )
        if disposition == "not_applicable" and not _non_empty_string(item.get("reason")):
            errs.append(
                f"requirement_coverage[{idx}].reason is required when "
                "disposition=not_applicable"
            )

    brief = _load_brief(brief_ref, trace_path) if brief_ref else None
    if brief is None:
        print(
            "WARN: requirement_coverage はありますが brief を解決できないため "
            f"(brief_ref={brief_ref!r}) requirement_id 実在と被覆完全性の検査を "
            "skip しました (構造検査のみ実施)。",
            file=sys.stderr,
        )
        return errs

    # requirement_id の brief 上の実在検査 + 被覆フィールド集合の構築
    covered_fields: set[str] = set()
    for idx, rid in valid_ids:
        if not _resolve_brief_field(brief, rid):
            errs.append(
                f"requirement_coverage[{idx}].requirement_id={rid!r} not found in "
                f"brief ({brief_ref})"
            )
        else:
            covered_fields.add(rid.split(".", 1)[0].split("[", 1)[0])

    # 被覆完全性: brief の非空要求フィールド全てが mapped or not_applicable+reason で
    # 被覆されていること (doc_coverage の required 差分検査と同型)
    required_fields = {
        k for k, v in brief.items()
        if k not in NON_REQUIREMENT_BRIEF_FIELDS and _requirement_bearing(v)
    }
    missing = sorted(required_fields - covered_fields)
    if missing:
        errs.append(
            "requirement_coverage does not cover all brief requirement fields: "
            f"missing={missing} (各フィールドを disposition=mapped か "
            "not_applicable+reason で被覆すること)"
        )
    return errs


# =============================================================
# CapabilityManifest 検証 (kind 別 dispatch)
# =============================================================

# 共通核 (commonCore.required)
_COMMON_CORE_REQUIRED = ("name", "description", "kind", "version", "owner")
_VALID_KINDS = {
    "skill", "agent", "hook", "command",
    "plugin-composition", "prompt", "workflow",
}

_HOOK_EVENT_ENUM = {
    "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop",
    "SessionEnd", "SubagentStop", "PreCompact", "Notification",
}

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _emit_result(valid: bool, kind: object, findings: list[str]) -> int:
    """新モード共通の JSON 出力。exit_code は valid に対応。"""
    out = {"valid": bool(valid), "kind": kind, "findings": findings}
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return 0 if valid else 1


def _load_frontmatter(text: str) -> tuple[dict | None, str]:
    """SKILL.md / agent.md 等の YAML frontmatter を抽出して dict を返す。

    返り値: (frontmatter_dict_or_None, error_message)
    """
    if not text.startswith("---"):
        return None, "frontmatter delimiter '---' not found at top"
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return None, "closing '---' for frontmatter not found"
    fm_text = parts[0].lstrip("-").lstrip("\n")
    if _HAS_YAML:
        try:
            data = yaml.safe_load(fm_text) or {}
        except Exception as exc:  # pragma: no cover
            return None, f"YAML parse error: {exc}"
        if not isinstance(data, dict):
            return None, "frontmatter must be a mapping"
        return _normalize_dates(data), ""
    # YAML 無し: 最小 key:value パーサ (フラット & スカラのみ)
    data = {}
    for line in fm_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line or line.startswith(" "):
            continue
        k, v = line.split(":", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data, ""


def _normalize_dates(obj):
    """YAML から date/datetime として読み込まれた値を ISO 文字列へ正規化。

    jsonschema は format=date を string 上で評価するため、Python の date を
    そのまま渡すと "is not of type 'string'" になる。再帰的に正規化する。
    """
    import datetime as _dt
    if isinstance(obj, dict):
        return {k: _normalize_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_dates(v) for v in obj]
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj


def _load_manifest(path: Path) -> tuple[dict | None, str]:
    """manifest を path 拡張子に応じて読み込む。

    - .md  : frontmatter を抽出
    - .yaml/.yml/.json : 本体をパース
    """
    if not path.exists():
        return None, f"file not found: {path}"
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return _load_frontmatter(text)
    if suffix in {".yaml", ".yml"}:
        if _HAS_YAML:
            try:
                data = yaml.safe_load(text) or {}
            except Exception as exc:
                return None, f"YAML parse error: {exc}"
        else:
            # fallback: frontmatter parser を流用 (フラット限定)
            data, err = _load_frontmatter("---\n" + text + "\n---\n")
            if err:
                return None, f"yaml fallback parse error: {err}"
        if not isinstance(data, dict):
            return None, "manifest root must be a mapping"
        return _normalize_dates(data), ""
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return None, f"json parse error: {exc}"
        if not isinstance(data, dict):
            return None, "manifest root must be a mapping"
        return data, ""
    return None, f"unsupported manifest extension: {suffix}"


def _check_common_core(data: dict) -> list[str]:
    findings: list[str] = []
    for key in _COMMON_CORE_REQUIRED:
        if not data.get(key):
            findings.append(f"commonCore.{key} is empty/missing")
    name = data.get("name")
    if isinstance(name, str) and not _NAME_RE.match(name):
        findings.append(f"name={name!r} must match ^[a-z][a-z0-9-]*$")
    desc = data.get("description")
    if isinstance(desc, str):
        L = len(desc)
        if L < 10 or L > 400:
            findings.append(f"description length {L} out of [10,400]")
    version = data.get("version")
    if isinstance(version, str) and not _SEMVER_RE.match(version):
        findings.append(f"version={version!r} must be SemVer X.Y.Z")
    kind = data.get("kind")
    if isinstance(kind, str) and kind not in _VALID_KINDS:
        findings.append(f"kind={kind!r} not in {sorted(_VALID_KINDS)}")
    return findings


def _check_kind_skill(data: dict) -> list[str]:
    f: list[str] = []
    triggers = data.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        f.append("skill.triggers must be non-empty array")
    return f


def _check_kind_agent(data: dict) -> list[str]:
    f: list[str] = []
    tools = data.get("tools")
    if not isinstance(tools, list) or not tools:
        f.append("agent.tools must be non-empty array")
    if not data.get("isolation"):
        f.append("agent.isolation missing (fork|worktree|inherit)")
    elif data.get("isolation") not in {"fork", "worktree", "inherit"}:
        f.append(f"agent.isolation invalid: {data.get('isolation')!r}")
    model = data.get("model")
    if model and model not in {"sonnet", "opus", "haiku", "inherit"}:
        f.append(f"agent.model invalid: {model!r}")
    if not data.get("phase"):
        f.append("agent.phase missing")
    return f


def _check_kind_hook(data: dict) -> list[str]:
    f: list[str] = []
    event = data.get("event")
    if not event:
        f.append("hook.event missing")
    elif event not in _HOOK_EVENT_ENUM:
        f.append(f"hook.event={event!r} not in {sorted(_HOOK_EVENT_ENUM)}")
    if not data.get("command"):
        f.append("hook.command missing")
    timeout = data.get("timeout_ms")
    if timeout is not None:
        if not isinstance(timeout, int) or not (100 <= timeout <= 60000):
            f.append(f"hook.timeout_ms={timeout!r} out of [100,60000]")
    return f


def _check_kind_command(data: dict, manifest_path: Path | None) -> list[str]:
    f: list[str] = []
    if not data.get("argument-hint"):
        f.append("command.argument-hint missing")
    allowed = data.get("allowed-tools")
    if not isinstance(allowed, list) or not allowed:
        f.append("command.allowed-tools must be non-empty array")
    entry = data.get("entrypoint")
    if entry and manifest_path is not None:
        # entrypoint が Skill 参照を指す場合、リポジトリ上に SKILL.md が存在するか確認
        # 解決ルール: manifest と同一プラグイン root を起点に skills/<entry>/SKILL.md を試す
        plugin_root = _resolve_plugin_root(manifest_path)
        if plugin_root is not None:
            candidate = plugin_root / "skills" / entry / "SKILL.md"
            if not candidate.exists():
                # 絶対/相対パス直書きの可能性も許容
                alt = (manifest_path.parent / entry).resolve()
                if not alt.exists():
                    f.append(
                        f"command.entrypoint={entry!r}: SKILL.md not found "
                        f"(tried {candidate})"
                    )
    return f


def _check_kind_prompt(data: dict) -> list[str]:
    f: list[str] = []
    layers = data.get("layers")
    if not isinstance(layers, list) or len(layers) != 7:
        f.append(f"prompt.layers must have exactly 7 items (got {len(layers) if isinstance(layers, list) else 'N/A'})")
        return f
    seen_idx: set[int] = set()
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            f.append(f"prompt.layers[{i}] must be object")
            continue
        idx = layer.get("index")
        if not isinstance(idx, int) or not (1 <= idx <= 7):
            f.append(f"prompt.layers[{i}].index invalid: {idx!r}")
        elif idx in seen_idx:
            f.append(f"prompt.layers[{i}].index duplicated: {idx}")
        else:
            seen_idx.add(idx)
        if not layer.get("title"):
            f.append(f"prompt.layers[{i}].title missing")
    return f


def _check_kind_workflow(data: dict) -> list[str]:
    f: list[str] = []
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases:
        f.append("workflow.phases must be non-empty array")
        return f
    for i, p in enumerate(phases):
        if not isinstance(p, dict):
            f.append(f"workflow.phases[{i}] must be object")
            continue
        if not p.get("id"):
            f.append(f"workflow.phases[{i}].id missing")
        agents = p.get("agents")
        if not isinstance(agents, list) or not agents:
            f.append(f"workflow.phases[{i}].agents must be non-empty array")
    return f


def _plugin_relative_ref_findings(ref: str, field: str, plugin_name: str | None) -> list[str]:
    f: list[str] = []
    if ref.startswith("hook:"):
        return f
    if ref.startswith("/") or ref.startswith("\\") or re.match(r"^[A-Za-z]:[\\/]", ref):
        f.append(f"{field} must be plugin-relative, not absolute: {ref}")
        return f
    parts = PurePosixPath(ref.replace("\\", "/")).parts
    if ".." in parts:
        f.append(f"{field} must not escape plugin root with '..': {ref}")
    if len(parts) >= 2 and parts[0] == "plugins" and (
        plugin_name is None or parts[1] == plugin_name
    ):
        f.append(f"{field} must be relative to plugin root, not start with plugins/<name>/: {ref}")
    return f


def _check_kind_plugin_composition(data: dict, manifest_path: Path | None) -> list[str]:
    f: list[str] = []
    caps = data.get("capabilities")
    if not isinstance(caps, list) or not caps:
        f.append("plugin-composition.capabilities must be non-empty array")
        caps = []
    cap_kinds = {"skill", "agent", "hook", "command", "prompt", "workflow"}
    plugin_name = manifest_path.parent.name if manifest_path is not None else data.get("name")
    cap_refs: set[str] = set()
    for i, c in enumerate(caps):
        if not isinstance(c, dict):
            f.append(f"capabilities[{i}] must be object")
            continue
        if c.get("kind") not in cap_kinds:
            f.append(f"capabilities[{i}].kind invalid: {c.get('kind')!r}")
        ref = c.get("ref")
        if not ref:
            f.append(f"capabilities[{i}].ref missing")
        elif isinstance(ref, str):
            cap_refs.add(ref)
            f.extend(_plugin_relative_ref_findings(ref, f"capabilities[{i}].ref", plugin_name))
    deps = data.get("dependencies", [])
    if deps and not isinstance(deps, list):
        f.append("plugin-composition.dependencies must be array")
        deps = []
    # DAG 循環検出
    if isinstance(deps, list) and deps:
        graph: dict[str, list[str]] = {}
        dep_types = {"calls", "reads", "extends", "evaluates", "emits", "writes", "delegates", "deploys"}
        for i, d in enumerate(deps):
            if isinstance(d, dict) and d.get("from") and d.get("to"):
                dep_type = d.get("type")
                if dep_type is not None and dep_type not in dep_types:
                    f.append(f"dependencies[{i}].type invalid: {dep_type!r}")
                if cap_refs:
                    for key in ("from", "to"):
                        endpoint = d[key]
                        if endpoint not in cap_refs:
                            f.append(
                                f"dependencies[{i}].{key} references undeclared capability: {endpoint}"
                            )
                graph.setdefault(d["from"], []).append(d["to"])
        if _has_cycle(graph):
            f.append("plugin-composition.dependencies contains cycle")
    return f


def _has_cycle(graph: dict[str, list[str]]) -> bool:
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    for node in list(graph.keys()):
        if color.get(node, WHITE) != WHITE:
            continue
        stack = [(node, iter(graph.get(node, [])))]
        color[node] = GRAY
        while stack:
            n, it = stack[-1]
            try:
                nxt = next(it)
            except StopIteration:
                color[n] = BLACK
                stack.pop()
                continue
            c = color.get(nxt, WHITE)
            if c == GRAY:
                return True
            if c == WHITE:
                color[nxt] = GRAY
                stack.append((nxt, iter(graph.get(nxt, []))))
    return False


def _resolve_plugin_root(manifest_path: Path) -> Path | None:
    """manifest_path から最寄りの plugins/<name>/ を遡って返す。"""
    p = manifest_path.resolve()
    for ancestor in [p] + list(p.parents):
        if ancestor.parent.name == "plugins":
            return ancestor
    return None


_KIND_DISPATCH = {
    "skill": lambda d, _p: _check_kind_skill(d),
    "agent": lambda d, _p: _check_kind_agent(d),
    "hook": lambda d, _p: _check_kind_hook(d),
    "command": lambda d, p: _check_kind_command(d, p),
    "plugin-composition": lambda d, p: _check_kind_plugin_composition(d, p),
    "prompt": lambda d, _p: _check_kind_prompt(d),
    "workflow": lambda d, _p: _check_kind_workflow(d),
}


def _load_schema() -> dict | None:
    schema_path = (
        Path(__file__).resolve().parent.parent / "references" / "capability-manifest.schema.json"
    )
    if not schema_path.exists():
        return None
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover
        return None


def validate_manifest(data: dict, manifest_path: Path | None = None) -> tuple[bool, str | None, list[str]]:
    """CapabilityManifest を共通核 + kind 固有で検証する純関数。"""
    findings: list[str] = []
    findings.extend(_check_common_core(data))
    kind = data.get("kind") if isinstance(data.get("kind"), str) else None
    if kind in _KIND_DISPATCH:
        findings.extend(_KIND_DISPATCH[kind](data, manifest_path))
    elif kind is not None:
        findings.append(f"unknown kind dispatch: {kind!r}")

    # jsonschema があれば追加で形式検証 (manual check の補強)
    if _HAS_JSONSCHEMA:
        schema = _load_schema()
        if schema is not None:
            try:
                jsonschema.validate(data, schema)
            except jsonschema.ValidationError as exc:
                findings.append(f"jsonschema: {exc.message} at {list(exc.path)}")
    return (not findings), kind, findings


def _handle_manifest_mode(path: Path) -> int:
    data, err = _load_manifest(path)
    if data is None:
        return _emit_result(False, None, [err])
    valid, kind, findings = validate_manifest(data, manifest_path=path)
    return _emit_result(valid, kind, findings)


def _handle_bundle_mode(path: Path) -> int:
    data, err = _load_manifest(path)
    if data is None:
        return _emit_result(False, None, [err])
    findings: list[str] = []
    # bundle 自体も plugin-composition として検証
    valid_m, kind, m_findings = validate_manifest(data, manifest_path=path)
    findings.extend(m_findings)
    # ref の実在チェック (hook:* 仮想参照はスキップ)
    caps = data.get("capabilities") or []
    plugin_root = path.parent
    for i, c in enumerate(caps):
        if not isinstance(c, dict):
            continue
        ref = c.get("ref")
        if not isinstance(ref, str) or not ref:
            continue
        if ref.startswith("hook:"):
            # plugin.json hook 配線は別ファイルで管理。manifest では存在保留。
            continue
        ref_path = plugin_root / ref
        # skill/agent は SKILL.md / *.md を持つディレクトリ。command は *.md ファイル想定。
        # ディレクトリ or ファイルどちらかが存在すれば OK。
        if ref_path.exists():
            continue
        # commands/<name> は .md 拡張子を補って再試行
        if (plugin_root / (ref + ".md")).exists():
            continue
        findings.append(f"capabilities[{i}].ref not found: {ref}")
    return _emit_result(not findings, kind, findings)


def _self_test() -> int:
    """内蔵 3 件の代表 manifest を検査し全 PASS で 0。"""
    samples: list[tuple[str, dict, bool]] = [
        (
            "skill-ok",
            {
                "name": "run-sample",
                "description": "サンプル発動条件の宣言。テスト用 manifest。",
                "kind": "skill",
                "version": "1.0.0",
                "owner": "team-test",
                "triggers": ["sample"],
                "contract": {"intent": "x", "interface": {}, "invariant": ["i1"]},
            },
            True,
        ),
        (
            "agent-missing-isolation",
            {
                "name": "agent-sample",
                "description": "isolation を欠落させた失敗ケース。",
                "kind": "agent",
                "version": "0.1.0",
                "owner": "team-test",
                "tools": ["Read"],
                "phase": "phase-1",
            },
            False,
        ),
        (
            "plugin-composition-with-cycle",
            {
                "name": "bundle-sample",
                "description": "DAG 循環を持つ plugin-composition 失敗ケース。",
                "kind": "plugin-composition",
                "version": "0.0.1",
                "owner": "team-test",
                "capabilities": [
                    {"kind": "skill", "ref": "skills/a"},
                    {"kind": "skill", "ref": "skills/b"},
                ],
                "dependencies": [
                    {"from": "a", "to": "b"},
                    {"from": "b", "to": "a"},
                ],
            },
            False,
        ),
    ]
    all_ok = True
    results = []
    for label, data, expect_valid in samples:
        valid, kind, findings = validate_manifest(data)
        ok = (valid == expect_valid)
        all_ok &= ok
        results.append({
            "label": label, "expect_valid": expect_valid,
            "got_valid": valid, "kind": kind,
            "findings": findings, "pass": ok,
        })
    print(json.dumps({"self_test_pass": all_ok, "results": results}, ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


# =============================================================
# main: 引数ディスパッチ (後方互換 + 新モード)
# =============================================================

def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(
            "usage: validate-build-trace.py <trace.json>\n"
            "       validate-build-trace.py --manifest <path>\n"
            "       validate-build-trace.py --bundle <plugin-composition.yaml>\n"
            "       validate-build-trace.py --self-test",
            file=sys.stderr,
        )
        return 2

    # 新モード
    if argv[0] == "--self-test":
        return _self_test()
    if argv[0] == "--manifest":
        if len(argv) != 2:
            print("usage: --manifest <path>", file=sys.stderr)
            return 2
        return _handle_manifest_mode(Path(argv[1]))
    if argv[0] == "--bundle":
        if len(argv) != 2:
            print("usage: --bundle <plugin-composition.yaml>", file=sys.stderr)
            return 2
        return _handle_bundle_mode(Path(argv[1]))

    # 既存モード (後方互換): 単一の trace JSON path
    if len(argv) != 1:
        print("usage: validate-build-trace.py eval-log/skill-build-trace.json", file=sys.stderr)
        return 2

    path = Path(argv[0])
    # A-3 強制化: ファイル未存在 or 空は FAIL (exit 1) として扱う
    # run-build-skill Step 3.5 開始前に必ずトレースを記録することを強制する。
    if not path.exists():
        print(f"FAIL: skill-build-trace.json not found: {path}", file=sys.stderr)
        print("run-build-skill Step 3.5 を開始する前に skill-build-trace.json を作成してください。", file=sys.stderr)
        return 1
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        print(f"FAIL: skill-build-trace.json is empty: {path}", file=sys.stderr)
        print("空ファイルは無効です。run-build-skill Step 3.5 の記録内容を投入してください。", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid json: {exc}", file=sys.stderr)
        return 2

    errs: list[str] = []

    source_docs = _as_set(data.get("source_docs"))
    if not source_docs:
        errs.append("source_docs must list the docs actually read")
    context_map = data.get("context_map_decision")
    if not isinstance(context_map, dict):
        errs.append("missing context_map_decision")
    else:
        for key in ("map", "task_category", "selected_docs"):
            if not context_map.get(key):
                errs.append(f"context_map_decision.{key} is empty")
        selected_docs = _as_set(context_map.get("selected_docs"))
        if selected_docs and source_docs and not source_docs.issubset(selected_docs):
            errs.append("source_docs must be a subset of context_map_decision.selected_docs")

    design = data.get("design_model")
    if not isinstance(design, dict):
        errs.append("missing design_model")
    else:
        for key in ("intent", "contract", "boundary", "execution", "feedback"):
            if not design.get(key):
                errs.append(f"design_model.{key} is empty")

    build_steps = _items_by_key(data.get("build_flow_coverage"), "step")
    missing_steps = REQUIRED_BUILD_STEPS - set(build_steps)
    if missing_steps:
        errs.append(f"missing build_flow_coverage steps: {sorted(missing_steps)}")
    for step, item in build_steps.items():
        if step in REQUIRED_BUILD_STEPS and not _completion_status_ok(item):
            errs.append(f"invalid build_flow_coverage item: {step}")

    doc_coverage = _items_by_key(data.get("doc_coverage"), "doc")
    missing_coverage = REQUIRED_DOC_COVERAGE - set(doc_coverage)
    if missing_coverage:
        errs.append(f"missing doc_coverage items: {sorted(missing_coverage)}")
    for doc, item in doc_coverage.items():
        if doc in REQUIRED_DOC_COVERAGE and not _completion_status_ok(item):
            errs.append(f"invalid doc_coverage item: {doc}")

    layer_items = _items_by_key(data.get("layer_decisions"), "layer")
    missing_layers = REQUIRED_LAYERS - set(layer_items)
    if missing_layers:
        errs.append(f"missing layer_decisions: {sorted(missing_layers)}")
    for layer, item in layer_items.items():
        if layer not in REQUIRED_LAYERS:
            continue
        decision = str(item.get("decision", "")).lower()
        if decision not in {"use", "skip"}:
            errs.append(f"layer_decisions.{layer} invalid decision")
        for key in ("reason", "placement_evidence", "fallback"):
            if not str(item.get(key, "")).strip():
                errs.append(f"layer_decisions.{layer} missing {key}")
        for key in ("dependency_direction_ok", "macos_stdlib_ok"):
            if not isinstance(item.get(key), bool):
                errs.append(f"layer_decisions.{layer}.{key} must be boolean")
        if item.get("deterministic") not in {True, False}:
            errs.append(f"layer_decisions.{layer}.deterministic must be boolean")

    variant = data.get("variant_support")
    if not isinstance(variant, dict):
        errs.append("missing variant_support")
    else:
        for key in ("prefix", "role_suffix", "subagent", "hook"):
            if not variant.get(key):
                errs.append(f"variant_support.{key} is empty")
        # 強化 (M3): variant_support.prefix が現行 kind 列挙と整合するか検証
        # （`atomic` などの旧仕様値が trace に紛れ込まないようガード）
        valid_prefixes = {"ref", "run", "wrap", "assign", "delegate"}
        prefix_val = str(variant.get("prefix", "")).strip().lower()
        if prefix_val and prefix_val not in valid_prefixes:
            errs.append(
                f"variant_support.prefix={prefix_val!r} not in {sorted(valid_prefixes)} "
                "(atomic は旧仕様。19章 factory 障害 #6 参照)"
            )
        # variant_support.prefix と生成スキル frontmatter の kind が一致するかクロスチェック
        skill_path = data.get("skill_path") or data.get("target_skill_path")
        if skill_path:
            from pathlib import Path as _P
            skill_md = _P(skill_path) / "SKILL.md"
            if skill_md.exists():
                text = skill_md.read_text(encoding="utf-8")
                # frontmatter 内の kind 行を最小パースで抽出
                for line in text.splitlines():
                    s = line.strip()
                    if s.startswith("kind:"):
                        kind_val = s.split(":", 1)[1].strip().split("#", 1)[0].strip()
                        if prefix_val and kind_val and prefix_val != kind_val:
                            errs.append(
                                f"variant_support.prefix={prefix_val!r} != frontmatter.kind={kind_val!r} in {skill_md}"
                            )
                        break

    # 強化 (M3): context_map_decision.category が resource-map.yaml に列挙された
    # category のいずれかに一致するか検証
    context_decision = data.get("context_map_decision")
    if isinstance(context_decision, dict):
        cats = context_decision.get("category")
        if cats:
            # resource-map.yaml を探索（trace 隣接か run-build-skill 直下）
            from pathlib import Path as _P
            candidate_maps = [
                _P("plugins/harness-creator/skills/run-build-skill/references/resource-map.yaml"),
                _P(".claude/skills/run-build-skill/references/resource-map.yaml"),
            ]
            known_cats: set[str] = set()
            for cm in candidate_maps:
                if cm.exists():
                    try:
                        for ln in cm.read_text(encoding="utf-8").splitlines():
                            stripped = ln.strip()
                            if stripped.startswith("- category:"):
                                known_cats.add(stripped.split(":", 1)[1].strip().strip('"'))
                    except OSError:
                        pass
                    break
            if known_cats:
                cat_list = cats if isinstance(cats, list) else [cats]
                for c in cat_list:
                    if c not in known_cats:
                        errs.append(
                            f"context_map_decision.category={c!r} not in resource-map.yaml "
                            f"({sorted(known_cats)})"
                        )

    patterns = data.get("pattern_decisions")
    if not isinstance(patterns, list) or not patterns:
        errs.append("missing pattern_decisions")
    else:
        for idx, item in enumerate(patterns):
            if not isinstance(item, dict):
                errs.append(f"pattern_decisions[{idx}] must be object")
                continue
            decision = str(item.get("decision", "")).lower()
            if decision not in {"use", "skip"}:
                errs.append(f"pattern_decisions[{idx}].decision invalid")
            for key in ("pattern_ref", "reason", "reuse_target"):
                if not str(item.get(key, "")).strip():
                    errs.append(f"pattern_decisions[{idx}].{key} is empty")

    gates = data.get("reproducibility_gates")
    if not isinstance(gates, dict):
        errs.append("missing reproducibility_gates")
    else:
        missing_gates = REQUIRED_GATES - set(gates)
        if missing_gates:
            errs.append(f"missing reproducibility_gates: {sorted(missing_gates)}")
        for gate in REQUIRED_GATES & set(gates):
            status = str(gates.get(gate, "")).upper()
            if status not in {"PASS", "N/A"}:
                errs.append(f"invalid gate status: {gate}={gates.get(gate)}")

    script_model = data.get("script_execution_model")
    if not isinstance(script_model, dict):
        errs.append("missing script_execution_model")
    else:
        contexts = _as_set(script_model.get("contexts"))
        if missing_contexts := REQUIRED_SCRIPT_CONTEXTS - contexts:
            errs.append(f"script_execution_model.contexts missing: {sorted(missing_contexts)}")
        for key in ("responsibility_matrix", "priority_order", "permission_boundary"):
            if not _non_empty_string(script_model.get(key)):
                errs.append(f"script_execution_model.{key} is empty")
        scripts = script_model.get("scripts")
        if not isinstance(scripts, list) or not scripts:
            errs.append("script_execution_model.scripts must list generated/used scripts")
        else:
            for idx, item in enumerate(scripts):
                if not isinstance(item, dict):
                    errs.append(f"script_execution_model.scripts[{idx}] must be object")
                    continue
                for key in ("path", "type", "allowed_contexts", "frontmatter_status"):
                    if not item.get(key):
                        errs.append(f"script_execution_model.scripts[{idx}].{key} is empty")
                allowed = _as_set(item.get("allowed_contexts"))
                unknown = allowed - REQUIRED_SCRIPT_CONTEXTS
                if unknown:
                    errs.append(f"script_execution_model.scripts[{idx}].allowed_contexts unknown: {sorted(unknown)}")

    governance = data.get("governance_model")
    if not isinstance(governance, dict):
        errs.append("missing governance_model")
    else:
        for key in ("rubric_version", "rubric_hash", "proposal_required", "impact_assessment"):
            if not str(governance.get(key, "")).strip():
                errs.append(f"governance_model.{key} is empty")
        roles = governance.get("roles")
        if not isinstance(roles, dict):
            errs.append("governance_model.roles is missing")
        else:
            missing_roles = REQUIRED_GOVERNANCE_ROLES - set(roles)
            if missing_roles:
                errs.append(f"governance_model.roles missing: {sorted(missing_roles)}")
        if "newly_failing_count" in governance and not isinstance(governance.get("newly_failing_count"), int):
            errs.append("governance_model.newly_failing_count must be integer when present")

    dogfooding = data.get("dogfooding_model")
    if not isinstance(dogfooding, dict):
        errs.append("missing dogfooding_model")
    else:
        for key in ("artifact_type", "adapter", "forked_evaluator", "eval_log_path"):
            if not _non_empty_string(dogfooding.get(key)):
                errs.append(f"dogfooding_model.{key} is empty")
        if not _non_empty_list(dogfooding.get("recursive_checks")):
            errs.append("dogfooding_model.recursive_checks must list rubric checks")

    optional_models = {
        "rubric_composition_model": ("ordered_refs", "merge_strategy", "conflict_policy", "composition_hash_evidence"),
        "paradigm_analogy_model": ("primary_analogy", "matched_skill_concept", "limits", "placement_decision"),
        "output_routing_model": ("task_kind", "payload_schema_version", "route_ref", "adapter_registry_ref", "fallback", "secret_boundary"),
    }
    for model_name, keys in optional_models.items():
        model = data.get(model_name)
        if not isinstance(model, dict):
            errs.append(f"missing {model_name}")
            continue
        status = str(model.get("status", "")).upper()
        if status == "N/A":
            if not str(model.get("reason", "")).strip():
                errs.append(f"{model_name}.reason is required when N/A")
            continue
        if status != "PASS":
            errs.append(f"{model_name}.status must be PASS or N/A")
        for key in keys:
            if not model.get(key):
                errs.append(f"{model_name}.{key} is empty")

    errs.extend(_validate_prompt_generation_model(data))

    errs.extend(_validate_prompt_provenance(data))

    errs.extend(_validate_feedback_contract(data))

    variable_contract = data.get("variable_contract")
    if not isinstance(variable_contract, list) or not variable_contract:
        errs.append("variable_contract must list template variables or N/A rationale item")
    else:
        for idx, item in enumerate(variable_contract):
            if not isinstance(item, dict):
                errs.append(f"variable_contract[{idx}] must be object")
                continue
            for key in ("name", "meaning", "default", "required", "not_applicable_when", "source_trace"):
                if key not in item or item.get(key) in ("", None):
                    errs.append(f"variable_contract[{idx}].{key} is empty")

    errs.extend(_validate_requirement_coverage(data, path))

    if errs:
        for err in errs:
            print(err, file=sys.stderr)
        return 1

    print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
