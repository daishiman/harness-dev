#!/usr/bin/env python3
"""Fail closed when any executable plugin entrypoint can run heavy work before handoff choice."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml


# 成果物の渡し方の契約 (artifact-delivery-v1) の正本はこのファイルの定数と
# references/artifact-delivery-policy.json の 2 か所だけで、両者の食い違いは _lint_policy が止める。
# SKILL.md は `artifact_delivery: artifact-delivery-v1` の 1 行、workflow-manifest.json は
# artifact_delivery_contract に contract と phase_activation だけを書き、state machine を写さない。
# 写しは正本と完全一致しか許されず、持ち主ごとの情報が無かった (harness-vvd)。
# 解決済みの契約は `--print-contract` で見られる。
CONTRACT_ID = "artifact-delivery-v1"
POLICY_REL = Path("references/artifact-delivery-policy.json")
# 現物を見せた直後に聞くのは「このまま試すか、診断を受けるか」の 2 択だけ (harness-znj)。
# どの深さで直すかは、診断の結果を見た後に改善段で 1 回だけ聞く。先に深さを聞いても
# 診断の中身は変わらず、同じ問いを 2 回することになっていた。
DIAGNOSTIC_CHOICES = ["accept-as-is", "diagnose"]
ACCEPT_CHOICE, DIAGNOSE_CHOICE = DIAGNOSTIC_CHOICES
# workflow-manifest.json の phase_activation が、どちらの状態機械に従うかを決める。
EVALUATOR_ACTIVATION = "all-legacy-phases-after-semantic_evaluator_started"
# Gate を持つ orchestrator (gate_order 宣言あり) だけが使える phase の起動宣言。
# phase は gate_order の順に人間承認 Gate を通って進み、診断の選択は委譲先 build の
# receipt を転記する。orchestrator 自身は evaluator を起動しないので、状態機械にも
# evaluator の state を持たない。
GATED_ORCHESTRATOR_ACTIVATION = "gate-ordered-phases-with-delegated-choice"
PRE_CHOICE_STATES = ["artifact_created", "minimal_guard_passed", "artifact_presented", "user_choice_recorded"]
PRE_CHOICE_TRANSITIONS = [
    {"from": "artifact_created", "event": "minimum_guard_pass", "to": "minimal_guard_passed"},
    {"from": "minimal_guard_passed", "event": "present_actual_artifact", "to": "artifact_presented"},
    {"from": "artifact_presented", "event": "record_user_choice", "to": "user_choice_recorded"},
]
PRE_CHOICE_FORBIDDEN = [
    "semantic-evaluator",
    "task-fork",
    "subagent",
    "multi-worker",
    "revise-loop",
]


def _delivery_contract(post_choice_states: list[str], choice_transitions: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "contract": CONTRACT_ID,
        "state_machine": {
            "initial": PRE_CHOICE_STATES[0],
            "states": [*PRE_CHOICE_STATES, *post_choice_states, "handoff_complete"],
            "transitions": [*PRE_CHOICE_TRANSITIONS, *choice_transitions],
            "pre_choice_forbidden": PRE_CHOICE_FORBIDDEN,
            "accept_contexts": {"evaluator": 0, "improver": 0},
        },
        "release": "explicit-only",
        "exhaustive": "explicit-only",
    }


CANONICAL_CONTRACT = _delivery_contract(
    ["semantic_evaluator_started"],
    [
        {"from": "user_choice_recorded", "event": ACCEPT_CHOICE, "to": "handoff_complete"},
        {"from": "user_choice_recorded", "event": DIAGNOSE_CHOICE, "to": "semantic_evaluator_started"},
        {"from": "semantic_evaluator_started", "event": "improvement_complete", "to": "handoff_complete"},
    ],
)
# accept-as-is でも orchestrator は残りの Gate と P0 lint を通してから引き継ぐ。
# diagnose なら診断は委譲先の build が行い、その receipt が揃ってから Gate へ進む。
GATED_CONTRACT = _delivery_contract(
    ["diagnosis_delegated", "gate_review_started"],
    [
        {"from": "user_choice_recorded", "event": ACCEPT_CHOICE, "to": "gate_review_started"},
        {"from": "user_choice_recorded", "event": DIAGNOSE_CHOICE, "to": "diagnosis_delegated"},
        {"from": "diagnosis_delegated", "event": "delegated_diagnosis_complete", "to": "gate_review_started"},
        {"from": "gate_review_started", "event": "gates_approved", "to": "handoff_complete"},
    ],
)
CONTRACTS = {EVALUATOR_ACTIVATION: CANONICAL_CONTRACT, GATED_ORCHESTRATOR_ACTIVATION: GATED_CONTRACT}
# 繰り返し (goal_seek の重い制御・feedback の差し戻しループ) が動いてよい最初の state。
LOOP_ACTIVATION_STATES = {
    EVALUATOR_ACTIVATION: "semantic_evaluator_started",
    GATED_ORCHESTRATOR_ACTIVATION: "gate_review_started",
}
# 移行前に SKILL.md frontmatter へ写されていた契約の形 (harness-vvd 時点)。rewrite_copied_contract は
# この形と完全一致する写しだけを 1 行へ置き換える。replay artifact-delivery-v1 がレビュー時の
# SKILL.md に当て直して結果を比べるので、CANONICAL_CONTRACT が後で変わってもここは変えない。
COPIED_CONTRACT_V1 = {
    "contract": "artifact-delivery-v1",
    "state_machine": {
        "initial": "artifact_created",
        "states": [
            "artifact_created",
            "minimal_guard_passed",
            "artifact_presented",
            "user_choice_recorded",
            "semantic_evaluator_started",
            "handoff_complete",
        ],
        "transitions": [
            {"from": "artifact_created", "event": "minimum_guard_pass", "to": "minimal_guard_passed"},
            {"from": "minimal_guard_passed", "event": "present_actual_artifact", "to": "artifact_presented"},
            {"from": "artifact_presented", "event": "record_user_choice", "to": "user_choice_recorded"},
            {"from": "user_choice_recorded", "event": "accept-as-is", "to": "handoff_complete"},
            {"from": "user_choice_recorded", "event": "light|standard|detailed", "to": "semantic_evaluator_started"},
            {"from": "semantic_evaluator_started", "event": "improvement_complete", "to": "handoff_complete"},
        ],
        "pre_choice_forbidden": ["semantic-evaluator", "task-fork", "subagent", "multi-worker", "revise-loop"],
        "accept_contexts": {"evaluator": 0, "improver": 0},
    },
    "release": "explicit-only",
    "exhaustive": "explicit-only",
}
DIAGNOSTIC_CHOICE_ALIASES = [
    (ACCEPT_CHOICE, "現状で試す"),
    (DIAGNOSE_CHOICE, "診断する"),
]
# 2 択にする前の 4 択 (accept-as-is / light / standard / detailed) を初回に聞く書き方。
# 深さの語が 2 つ以上と、初回の選択か evaluator の起動を指す語が同じ行に並んだら旧い書き方とみなす。
LEGACY_DEPTH_WORDS = (
    re.compile(r"\blight\b|軽微", re.IGNORECASE),
    re.compile(r"\bstandard\b|標準", re.IGNORECASE),
    re.compile(r"\bdetailed\b|詳細", re.IGNORECASE),
)
LEGACY_INITIAL_CHOICE_MARKERS = ("accept-as-is", "現状で試す", "semantic_evaluator_started")
INITIAL_CHOICE_FORBIDDEN = ("release", "exhaustive", "リリース", "完全監査")
INITIAL_CHOICE_PROMPT_MARKERS = ("ask", "choose", "select", "choice", "聞く", "選ぶ", "選択")
SEPARATE_EVENT_MARKERS = (
    "do not mix",
    "must not include",
    "separate event",
    "別の明示event",
    "別の明示 event",
    "別イベント",
    "混ぜず",
    "含めない",
)
NORMAL_ENTRYPOINT_KINDS = {"run", "wrap", "delegate"}
WORKFLOW_CONTRACT_KEYS = {"contract", "phase_activation"}
PRE_CHOICE_HEADING = "## Pre-choice usable artifact execution"
POST_CHOICE_HEADING = "## Post-choice selected improvement execution"
PRE_CHOICE_HEADING_JA = "## 選ぶ前の実成果物の作成"
POST_CHOICE_HEADING_JA = "## 選んだ深さでの改善の実行"
# 本文は (pre, post) の組を1つだけ使う。組の中で言語を混ぜてはいけない。
CHOICE_HEADING_PAIRS = {
    "en": (PRE_CHOICE_HEADING, POST_CHOICE_HEADING),
    "ja": (PRE_CHOICE_HEADING_JA, POST_CHOICE_HEADING_JA),
}
LEGACY_BOUNDARY_HEADING = "## Artifact delivery boundary (hard gate)"


class Entrypoint(NamedTuple):
    plugin: str
    path: Path


class Classification(NamedTuple):
    mode: str
    reason: str


class LintError(ValueError):
    """A skill cannot be classified or parsed safely."""


def _frontmatter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LintError(f"cannot read UTF-8 skill: {exc}") from exc
    if not text.startswith("---"):
        raise LintError("frontmatter is required")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise LintError("frontmatter closing delimiter is required")
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise LintError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise LintError("frontmatter must be an object")
    return frontmatter, parts[2]


def read_kind(path: Path) -> str:
    frontmatter, _ = _frontmatter_and_body(path)
    return str(frontmatter.get("kind", "")).strip()


def read_artifact_delivery(path: Path) -> Any:
    """SKILL.md が宣言する契約 id を返す (宣言が無ければ None)。中身は CANONICAL_CONTRACT にある。"""
    frontmatter, _ = _frontmatter_and_body(path)
    return frontmatter.get("artifact_delivery")


def rewrite_copied_contract(text: str) -> str | None:
    """SKILL.md frontmatter にある契約の写しを `artifact_delivery: <CONTRACT_ID>` の 1 行に置き換える。

    写しが移行前の形 (COPIED_CONTRACT_V1) と完全一致するときだけ置き換え、置換後の frontmatter を
    読み直して artifact_delivery 以外のキーと順序、本文が 1 文字も変わらないことを確かめる。
    写しが無い・移行済みなら None、正本と違う写しや確かめに失敗したら LintError。

    決定的な変換なので、content-review の結び直し
    (sync-content-review-sha.py --replay artifact-delivery-v1) がレビュー時の SKILL.md に
    当て直し、結果が現在の SKILL.md と bytes で一致するかを確かめる (harness-vvd / harness-g67)。
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise LintError("frontmatter closing delimiter is required")
    starts = [i for i in range(1, end) if lines[i].startswith("artifact_delivery:")]
    if not starts:
        return None
    if len(starts) != 1:
        raise LintError(f"artifact_delivery appears {len(starts)} times in frontmatter")
    try:
        before = yaml.safe_load("".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise LintError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(before, dict):
        raise LintError("frontmatter must be an object")
    if before.get("artifact_delivery") == CONTRACT_ID:
        return None
    if before.get("artifact_delivery") != COPIED_CONTRACT_V1:
        raise LintError("artifact_delivery is not an exact copy of the pre-migration contract")
    start = starts[0]
    last = start
    for index in range(start + 1, end):
        if lines[index].startswith((" ", "\t")):
            last = index
        elif lines[index].strip():
            break
    newline = "\r\n" if lines[start].endswith("\r\n") else "\n"
    new_lines = [*lines[:start], f"artifact_delivery: {CONTRACT_ID}{newline}", *lines[last + 1:]]
    new_end = end - (last - start)
    after = yaml.safe_load("".join(new_lines[1:new_end]))
    expected = {**before, "artifact_delivery": CONTRACT_ID}
    if after != expected or list(after) != list(expected):
        raise LintError("rewriting artifact_delivery changed other frontmatter keys")
    if "".join(new_lines[new_end:]) != "".join(lines[end:]):
        raise LintError("rewriting artifact_delivery changed the body")
    return "".join(new_lines)


# 初回の選択肢を 4 択から 2 択へ書き換える表 (harness-znj)。上から順に、左の語句を右へ置き換える。
# 長い語句を先に置くので、短い語句が長い語句の一部を先に食うことはない。replay
# diagnostic-choice-2way がレビュー時の SKILL.md に当て直すので、移行後もこの表は変えない。
DIAGNOSTIC_CHOICE_REWRITES = (
    (
        "現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）",
        "現状で試すか診断するかを記録する（記録する値は順に `accept-as-is`・`diagnose`）",
    ),
    ("軽微・標準・詳細のどれかが記録されて", "「診断する」が記録されて"),
    ("accept-as-is|light|standard|detailed", "accept-as-is|diagnose"),
    ("light / standard / detailed", "diagnose"),
    ("light/standard/detailed", "diagnose"),
)


def _rewrite_choice_phrases(text: str) -> str:
    for old, new in DIAGNOSTIC_CHOICE_REWRITES:
        text = text.replace(old, new)
    return text


def _rewrite_choice_strings(value: Any) -> Any:
    if isinstance(value, str):
        return _rewrite_choice_phrases(value)
    if isinstance(value, list):
        return [_rewrite_choice_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_choice_strings(item) for key, item in value.items()}
    return value


def rewrite_diagnostic_choices(text: str) -> str | None:
    """SKILL.md の初回の選択肢を 4 択の書き方から accept-as-is / diagnose の 2 択へ書き換える。

    DIAGNOSTIC_CHOICE_REWRITES の語句だけを置き換え、frontmatter は読み直して、文字列の値に
    同じ表を当てた結果と一致すること (キーと順序を含む) を確かめる。置き換えた後に 4 択の
    書き方 (legacy_diagnostic_choice_lines) が本文に残るなら、表で直せない書き方なので LintError。
    変わる語句が無ければ None。

    決定的な変換なので、content-review の結び直し
    (sync-content-review-sha.py --replay diagnostic-choice-2way) がレビュー時の SKILL.md に当て直し、
    結果が現在の SKILL.md と bytes で一致するかを確かめる。
    """
    rewritten = _rewrite_choice_phrases(text)
    if rewritten == text:
        return None
    lines = text.splitlines(keepends=True)
    new_lines = rewritten.splitlines(keepends=True)
    if len(new_lines) != len(lines):
        raise LintError("rewriting the diagnostic choices changed the line count")
    body_start = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            raise LintError("frontmatter closing delimiter is required")
        try:
            before = yaml.safe_load("".join(lines[1:end]))
            after = yaml.safe_load("".join(new_lines[1:end]))
        except yaml.YAMLError as exc:
            raise LintError(f"invalid YAML frontmatter: {exc}") from exc
        expected = _rewrite_choice_strings(before)
        if after != expected or (isinstance(after, dict) and list(after) != list(expected)):
            raise LintError("rewriting the diagnostic choices changed frontmatter beyond the phrase table")
        body_start = end + 1
    leftover = legacy_diagnostic_choice_lines("".join(new_lines[body_start:]))
    if leftover:
        raise LintError(
            f"legacy 4-choice prose the phrase table cannot rewrite remains at body line {leftover[0]}"
        )
    return rewritten


def discover_entrypoints(root: Path) -> list[Entrypoint]:
    """Use plugin manifests as the mother set, then enumerate every on-disk skill."""
    plugins_root = root / "plugins"
    manifests = sorted(
        path
        for path in plugins_root.glob("*/.claude-plugin/plugin.json")
        if path.is_file()
    )
    entrypoints: list[Entrypoint] = []
    for manifest in manifests:
        plugin_dir = manifest.parents[1]
        for skill in sorted(plugin_dir.glob("skills/*/SKILL.md")):
            if skill.is_file():
                entrypoints.append(Entrypoint(plugin=plugin_dir.name, path=skill))
    return entrypoints


def classify_entrypoint(entrypoint: Entrypoint) -> Classification:
    frontmatter, _ = _frontmatter_and_body(entrypoint.path)
    kind = str(frontmatter.get("kind", "")).strip()
    effect = str(frontmatter.get("effect", "")).strip()
    if kind in NORMAL_ENTRYPOINT_KINDS:
        return Classification("enforced", f"kind={kind}: executable artifact entrypoint")
    if kind == "ref" and effect == "none":
        return Classification("exempt", "kind=ref,effect=none: non-executable reference")
    if kind == "assign" and frontmatter.get("user-invocable") is False:
        return Classification("exempt", "kind=assign,user-invocable=false: post-choice internal evaluator")
    raise LintError(
        f"unclassified entrypoint kind/effect/role: kind={kind!r}, effect={effect!r}, "
        f"user-invocable={frontmatter.get('user-invocable')!r}"
    )


def _lint_contract(value: Any) -> list[str]:
    if value is None or value == "" or value == {}:
        return [f"artifact_delivery contract is required: write `artifact_delivery: {CONTRACT_ID}`"]
    if isinstance(value, dict):
        return [
            f"artifact_delivery must be the contract id only (`artifact_delivery: {CONTRACT_ID}`); "
            "do not copy the state machine, it lives in scripts/lint-entrypoint-artifact-first.py"
        ]
    if value != CONTRACT_ID:
        return [f"artifact_delivery contract must reference {CONTRACT_ID}: got {value!r}"]
    return []


def _lint_policy(root: Path) -> list[str]:
    """契約の正本 2 か所 (この lint と policy) の食い違いを止める。"""
    try:
        policy = json.loads((root / POLICY_REL).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"{POLICY_REL.as_posix()}: cannot read the artifact-delivery policy: {exc}"]
    if not isinstance(policy, dict):
        return [f"{POLICY_REL.as_posix()}: policy must be an object"]
    errors: list[str] = []
    if policy.get("policy_id") != CONTRACT_ID:
        errors.append(f"{POLICY_REL.as_posix()}: policy_id must be {CONTRACT_ID}: got {policy.get('policy_id')!r}")
    user_choice = policy.get("user_choice")
    levels = user_choice.get("improvement_levels") if isinstance(user_choice, dict) else None
    if levels != DIAGNOSTIC_CHOICES:
        errors.append(
            f"{POLICY_REL.as_posix()}: user_choice.improvement_levels {levels!r} drifted from "
            f"DIAGNOSTIC_CHOICES {DIAGNOSTIC_CHOICES!r}"
        )
    return errors


def phase_activation_of(skill_dir: Path) -> str:
    """skill が従う状態機械の名前。manifest が無いか読めないときは evaluator 型として扱う。

    manifest の誤りそのものは _lint_workflow_manifest が報告する。ここで甘く読むのは、
    誤った manifest を理由に frontmatter 側の検査を緩めないため (evaluator 型の方が厳しい)。
    """
    try:
        document = json.loads((skill_dir / "workflow-manifest.json").read_text(encoding="utf-8"))
        activation = document["artifact_delivery_contract"]["phase_activation"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return EVALUATOR_ACTIVATION
    return activation if activation in CONTRACTS else EVALUATOR_ACTIVATION


def _lint_frontmatter_control_flow(frontmatter: dict[str, Any], activation: str = EVALUATOR_ACTIVATION) -> list[str]:
    errors: list[str] = []
    loop_state = LOOP_ACTIVATION_STATES[activation]
    goal_seek = frontmatter.get("goal_seek")
    if isinstance(goal_seek, dict):
        fork = str(goal_seek.get("fork", "inline")).strip().casefold()
        max_loops = goal_seek.get("max_loops", 1)
        is_heavy = fork not in {"", "inline"} or (
            isinstance(max_loops, int) and not isinstance(max_loops, bool) and max_loops > 1
        )
        if is_heavy and goal_seek.get("activation_state") != loop_state:
            errors.append(f"goal_seek heavy control must activate post-choice at {loop_state}")
    feedback = frontmatter.get("feedback_contract")
    if isinstance(feedback, dict):
        iterations = feedback.get("max_iterations", 0)
        if (
            isinstance(iterations, int)
            and not isinstance(iterations, bool)
            and iterations > 0
            and feedback.get("activation_state") != loop_state
        ):
            errors.append(f"feedback revise loop must activate post-choice at {loop_state}")
    return errors


def legacy_diagnostic_choice_lines(body: str) -> list[int]:
    """2 択にする前の 4 択を初回に聞く書き方が残る行 (1 始まり)。"""
    hits = []
    for index, line in enumerate(body.splitlines(), start=1):
        depth_words = sum(bool(word.search(line)) for word in LEGACY_DEPTH_WORDS)
        if depth_words >= 2 and any(marker in line.casefold() for marker in LEGACY_INITIAL_CHOICE_MARKERS):
            hits.append(index)
    return hits


def _lint_body_control_flow(body: str) -> list[str]:
    lines = body.splitlines()
    errors: list[str] = []
    if LEGACY_BOUNDARY_HEADING in body:
        errors.append(f"legacy prose artifact boundary is forbidden; reference `artifact_delivery: {CONTRACT_ID}` instead")
    positions = {
        language: (
            [index for index, line in enumerate(lines) if line.strip() == pre_heading],
            [index for index, line in enumerate(lines) if line.strip() == post_heading],
        )
        for language, (pre_heading, post_heading) in CHOICE_HEADING_PAIRS.items()
    }
    languages = [language for language, (pre, post) in positions.items() if pre or post]
    pre_start, post_start = 0, len(lines)
    if len(languages) > 1:
        errors.append(
            f"mixed {'/'.join(languages)} pre-choice/post-choice headings are forbidden; use one language pair"
        )
    else:
        pre_positions, post_positions = positions[languages[0]] if languages else ([], [])
        if len(pre_positions) != 1 or len(post_positions) != 1 or pre_positions[0] >= post_positions[0]:
            canonical_pairs = ", or ".join(
                f"'{pre_heading}' then '{post_heading}'" for pre_heading, post_heading in CHOICE_HEADING_PAIRS.values()
            )
            errors.append(
                "body requires one ordered pre-choice usable-artifact section and post-choice selected-improvement section: "
                + canonical_pairs
            )
        else:
            pre_start, post_start = pre_positions[0] + 1, post_positions[0]

    if languages and len(languages) == 1:
        other_root = "## Runtime root contract" if languages[0] == "ja" else "## 実行時のルートの決め方"
        if any(line.strip() == other_root for line in lines):
            errors.append("runtime root contract language mismatch with pre/post-choice headings")

    for index, line in enumerate(lines):
        normalized = line.casefold()
        option_count = sum(
            any(alias.casefold() in normalized for alias in aliases)
            for aliases in DIAGNOSTIC_CHOICE_ALIASES
        )
        mixes_stage_promotion = (
            option_count >= len(DIAGNOSTIC_CHOICES)
            and any(marker in normalized for marker in INITIAL_CHOICE_PROMPT_MARKERS)
            and any(marker in normalized for marker in INITIAL_CHOICE_FORBIDDEN)
            and not any(marker in normalized for marker in SEPARATE_EVENT_MARKERS)
        )
        if mixes_stage_promotion:
            errors.append(
                "initial diagnostic choices must exclude release/exhaustive "
                f"at body line {index + 1}"
            )
            break
    legacy = legacy_diagnostic_choice_lines(body)
    if legacy:
        errors.append(
            "the first question is accept-as-is or diagnose only; ask the depth after the diagnosis "
            f"(legacy 4-choice prose at body line {legacy[0]})"
        )

    imperative_heavy = re.compile(
        r"(?ix)(?:\b(?:run|start|launch|invoke|dispatch|ask|use|execute)\b[^\n]{0,120}"
        r"(?:quality[_ -]?oracle|semantic[_ -]?evaluator|evaluator|\btask\b|subagent|"
        r"multi[_ -]?(?:agent|worker)|\bworkers?\b)|"
        r"\b(?:revise|improve|iterate|loop)\b|"
        r"(?:task|subagent|evaluator|worker|agent).{0,80}(?:\u8d77\u52d5|\u59d4\u8b72|\u5b9f\u884c)|"
        r"(?:\u4fee\u6b63|\u6539\u5584|\u53cd\u5fa9|\u5468\u56de|\u518d\u8a55\u4fa1)(?:\u3059\u308b|\u3057|\u3092))"
    )
    for index in range(pre_start, post_start):
        line = lines[index]
        lowered = line.casefold()
        prohibited = any(
            marker in lowered
            for marker in ("must not", "do not", "forbidden", "reject", "without", "\u7981\u6b62", "\u3057\u306a\u3044", "\u62d2\u5426", "\u4e0d\u8981")
        )
        if not prohibited and imperative_heavy.search(line):
            errors.append(f"pre-choice imperative heavy operation at body line {index + 1}")
            break

    contradiction = re.compile(
        r"(?ix)(?:only\s+then\s+(?:create|show|present|write|emit|publish)|"
        r"(?:run|start|ask|revise|iterate)[^\n]{0,160}\b(?:before|prior to)\b[^\n]{0,80}"
        r"(?:create|show|present|artifact)|"
        r"(?:\u8a55\u4fa1|\u4fee\u6b63|\u53cd\u5fa9|\u5468\u56de|\u59d4\u8b72).{0,100}(?:\u305d\u306e\u5f8c|\u5f8c\u3067|\u304b\u3089)(?:\u751f\u6210|\u4f5c\u6210|\u63d0\u793a))"
    )
    for index, line in enumerate(lines):
        if contradiction.search(line):
            errors.append(f"heavy-before-create/present contradiction at body line {index + 1}")
            break
    publication_gate = re.compile(
        r"(?ix)(?:(?:do\s+not|don't|must\s+not|not)\s+[^\n]{0,80}"
        r"(?:publish|present|show)[^\n]{0,80}(?:until|unless)[^\n]{0,80}"
        r"(?:evaluator|review|pass)|"
        r"(?:evaluator|review)[^\n]{0,80}(?:pass|complete|\u4e00\u81f4)[^\n]{0,80}"
        r"(?:\u307e\u3067|until)[^\n]{0,40}(?:publish|present|show|\u516c\u958b|\u63d0\u793a)(?:\u3057\u306a\u3044|\u7981\u6b62)?)"
    )
    for index, line in enumerate(lines):
        if publication_gate.search(line):
            errors.append(f"evaluator-before-first-publication contradiction at body line {index + 1}")
            break
    return errors


def _lint_workflow_manifest(path: Path) -> list[str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"cannot read workflow-manifest.json: {exc}"]
    if not isinstance(document, dict):
        return ["workflow-manifest.json must be an object"]
    contract = document.get("artifact_delivery_contract")
    if not isinstance(contract, dict):
        return ["workflow-manifest.json requires artifact_delivery_contract"]
    errors: list[str] = []
    if set(contract) != WORKFLOW_CONTRACT_KEYS:
        errors.append(
            "workflow artifact_delivery_contract must hold exactly contract and phase_activation; "
            "do not copy the state machine, it lives in scripts/lint-entrypoint-artifact-first.py"
        )
    if contract.get("contract") != CONTRACT_ID:
        errors.append(f"workflow must reference {CONTRACT_ID}")
    phases = document.get("phases")
    phase_ids = [phase.get("id") for phase in phases] if isinstance(phases, list) and all(isinstance(phase, dict) for phase in phases) else []
    if len(phase_ids) != len(set(phase_ids)) or any(not isinstance(phase_id, str) or not phase_id for phase_id in phase_ids):
        errors.append("workflow phases require unique non-empty ids")
    if isinstance(phases, list):
        for phase in phases:
            if isinstance(phase, dict) and "choices" in phase:
                if phase.get("choices") != DIAGNOSTIC_CHOICES:
                    errors.append(
                        "workflow diagnostic choices must be canonical: " + "|".join(DIAGNOSTIC_CHOICES)
                    )
    activation = contract.get("phase_activation")
    gate_order = document.get("gate_order")
    gated_orchestrator = isinstance(gate_order, list) and bool(gate_order)
    if activation == GATED_ORCHESTRATOR_ACTIVATION and not gated_orchestrator:
        errors.append("workflow gate-ordered activation requires a non-empty gate_order")
    elif activation not in CONTRACTS:
        errors.append("workflow legacy phases require exact post-choice activation")
    return errors


def lint_guarded_external_entrypoint(skill_md: Path) -> list[str]:
    """Prove a model-callable external workflow retains its execution guard.

    Fail closed on parsing/import/contract errors; metadata alone is not evidence.
    """
    try:
        fm, body = _frontmatter_and_body(skill_md)
        errors = []
        if fm.get("effect") != "external-mutation":
            errors.append("guarded workflow requires effect: external-mutation")
        if fm.get("runtime_root_policy") != "host-skill-path":
            errors.append("guarded workflow requires runtime_root_policy: host-skill-path")
        errors.extend(_lint_contract(fm.get("artifact_delivery")))
        errors.extend(_lint_frontmatter_control_flow(fm, phase_activation_of(skill_md.parent)))
        errors.extend(_lint_body_control_flow(body))
        import importlib.util
        spec = importlib.util.spec_from_file_location("artifact_delivery_guard_validation", Path(__file__).with_name("build-artifact-delivery.py"))
        if spec is None or spec.loader is None:
            raise LintError("artifact delivery guard validator unavailable")
        delivery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(delivery)
        delivery._external_guard_contract(skill_md, fm, {"effect_guards": {"external-mutation": delivery.EXPECTED_EXTERNAL_GUARD_POLICY}})
        return errors
    except Exception as exc:
        return [f"guarded external workflow validation failed: {exc}"]


def lint_entrypoint(entrypoint: Entrypoint) -> list[str]:
    try:
        classification = classify_entrypoint(entrypoint)
        if classification.mode == "exempt":
            return []
        frontmatter, body = _frontmatter_and_body(entrypoint.path)
        errors = _lint_contract(frontmatter.get("artifact_delivery"))
        errors.extend(_lint_frontmatter_control_flow(frontmatter, phase_activation_of(entrypoint.path.parent)))
        errors.extend(_lint_body_control_flow(body))
        if entrypoint.plugin == "ubm-goal-setting" and entrypoint.path.parent.name.startswith("run-ubm-"):
            headings = [line.strip() for line in body.splitlines() if re.match(r"^#{1,2} ", line)]
            expected = [f"# {frontmatter.get('name')}", "## 目的と出力契約", "## 実行時のルートの決め方", PRE_CHOICE_HEADING_JA, POST_CHOICE_HEADING_JA, "## 全体の流れ"]
            if headings[:6] != expected:
                errors.append("ubm opening heading order must be H1 → purpose → runtime root → pre-choice → post-choice → workflow")
        workflow = entrypoint.path.parent / "workflow-manifest.json"
        if workflow.exists():
            errors.extend(_lint_workflow_manifest(workflow))
        return errors
    except LintError as exc:
        return [str(exc)]


def lint_repository(root: Path) -> list[str]:
    entrypoints = discover_entrypoints(root)
    if not entrypoints:
        return ["no plugin entrypoints discovered from plugins/*/.claude-plugin/plugin.json"]
    errors = _lint_policy(root)
    for entrypoint in entrypoints:
        relative = entrypoint.path.relative_to(root).as_posix()
        errors.extend(f"{relative}: {message}" for message in lint_entrypoint(entrypoint))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--print-contract",
        action="store_true",
        help=f"print the resolved {CONTRACT_ID} contract that SKILL.md and workflow-manifest.json refer to",
    )
    parser.add_argument(
        "--phase-activation",
        choices=sorted(CONTRACTS),
        default=EVALUATOR_ACTIVATION,
        help="with --print-contract: the workflow-manifest phase_activation whose state machine to print",
    )
    args = parser.parse_args(argv)
    if args.print_contract:
        print(json.dumps(CONTRACTS[args.phase_activation], ensure_ascii=False, indent=2))
        return 0
    root = Path(args.repo_root).resolve()
    errors = lint_repository(root)
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    discovered = discover_entrypoints(root)
    enforced = sum(classify_entrypoint(item).mode == "enforced" for item in discovered)
    exempt = len(discovered) - enforced
    print(f"OK: artifact-first entrypoints valid ({len(discovered)} inventory, {enforced} enforced, {exempt} mechanically exempt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
