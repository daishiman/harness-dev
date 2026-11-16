#!/usr/bin/env python3
# /// script
# name: validate-run-model-budget
# purpose: 1 run_id で起動してよい AI context の予算 (convergence-policy.json の run_model_action_budget) が、9 ファイルに散らばるループ上限の宣言と、それらから計算した最悪ケースに一致するかを検査する。gate・launcher・planner は本ファイルを import し、run ごとの消費台帳を排他で予約する。
# inputs:
#   - argv: [--skills-root <plugins/harness-creator/skills>] [--policy <convergence-policy.json> (既定は --skills-root の下の正本)] [--print-expected] [--run-id <id> --state-dir <dir>]
# outputs:
#   - stdout: 一致なら ok、食い違いなら箇所の一覧。--print-expected は計算した components/total の JSON。--run-id は台帳の消費と残り
#   - exit: 0=一致 / 1=食い違い / 2=入力エラー (読めない・形が壊れている・台帳が壊れている)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [A, C]
# network: false
# write-scope: CLI は none。import 先が reserve() か reserve_verification() を呼んだときだけ <state_dir>/run-model-actions-<sha256(run_id)>.json (+ .lock)
# ///
"""Validate the single run-level model-action budget and reserve against its ledger.

予算の正本は ``run-elegant-review/references/convergence-policy.json`` の
``run_model_action_budget`` の 1 か所である。``bounds`` は各ループ上限の写しで、
本 script の CLI が collect_bound_sources の読む 9 ファイルの宣言と突き合わせる。
``components`` と ``total`` は ``compute_worst_case(bounds)`` の結果を書いたもので、
手で数字を合わせても計算と食い違えば落ちる。この式の検査は load_budget が毎回行うので、
gate・launcher・planner も水増しした policy では動かない (宣言との照合は CI の CLI が受け持つ)。

台帳は最初に予約したときの total を ``budget_total`` に記録し、以後は同じ total の呼び出ししか
受け付けない。gate・launcher・planner が別々の policy を読んでも、同じ run で予算が食い違わない。

起動を止めるのは script を必ず通る地点だけである。
- build-improvement-gate.py: 初回診断の claim (evaluator 1 context) と改善の認可 (executor max_rounds)
- build-review-launch.py: evaluator の配送 (claim の予約が無ければ、ここで予約する)
- plan-verification-obligations.py: 検証用 model action を reserve_verification で予約し、残りを budget_gate に出す

検証も台帳の component (verification) である。planner と gate が同じ plan から subject ごとの量を
「少なくとも n」で予約するので、planner の --state-dir が gate と違っても、gate の台帳に検証が入る。
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SKILLS_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_POLICY_PATH = DEFAULT_SKILLS_ROOT / "run-elegant-review" / "references" / "convergence-policy.json"
BUDGET_KEY = "run_model_action_budget"
BOUND_KEYS = (
    "gate_deny_cycles",
    "build_rerun_cycles",
    "initial_diagnosis_contexts",
    "improvement_rounds",
    "content_review_inner",
    "content_review_outer",
    "goal_seek_loops",
    "verification_actions",
)
LEDGER_COMPONENTS = {"initial_diagnosis", "bounded_improvement", "verification"}
LEDGER_SCHEMA_VERSION = 1
# at_least=True の予約で足りない分を足すとき、元の action_id にこれと要求数を付けた id で記録する。
TOPUP_MARKER = "#topup-"
# 検証用 model action は subject ごとに 1 つの action_id (と top-up) で「少なくとも n」を予約する。
VERIFICATION_ACTION_PREFIX = "verification:"


class BudgetError(ValueError):
    """The budget definition, its sources or the ledger cannot be trusted."""


class BudgetExhausted(BudgetError):
    """Reserving the requested model actions would exceed the run budget."""

    def __init__(self, message: str, *, total: int, consumed: int, requested: int) -> None:
        super().__init__(message)
        self.total = total
        self.consumed = consumed
        self.requested = requested


def _is_count(value: Any) -> bool:
    return type(value) is int and value >= 0


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BudgetError(f"cannot read {label} ({path}): {exc}") from exc


def _validated_bounds(bounds: Any) -> dict:
    if not isinstance(bounds, dict) or set(bounds) != set(BOUND_KEYS):
        raise BudgetError(f"{BUDGET_KEY}.bounds must have exactly {list(BOUND_KEYS)}")
    for key, value in bounds.items():
        if not _is_count(value):
            raise BudgetError(f"{BUDGET_KEY}.bounds.{key} must be a non-negative integer")
    return bounds


def load_budget(policy_path: Path = DEFAULT_POLICY_PATH, *, check_formula: bool = True) -> dict:
    """Return the validated ``run_model_action_budget`` object.

    check_formula=True (実行時の既定) は components/total が compute_worst_case(bounds) と
    一致しなければ BudgetError にする。CLI だけが False で読み、食い違いを MISMATCH (exit 1) として並べる。
    """
    doc = _read_json(Path(policy_path), "convergence policy")
    budget = doc.get(BUDGET_KEY) if isinstance(doc, dict) else None
    if not isinstance(budget, dict):
        raise BudgetError(f"{BUDGET_KEY} is missing from {policy_path}")
    bounds = _validated_bounds(budget.get("bounds"))
    components = budget.get("components")
    if not isinstance(components, dict) or not components or not all(
        isinstance(name, str) and _is_count(value) for name, value in components.items()
    ):
        raise BudgetError(f"{BUDGET_KEY}.components must map names to non-negative integers (compute_worst_case の結果を書く)")
    total = budget.get("total")
    if type(total) is not int or total < 1:
        raise BudgetError(f"{BUDGET_KEY}.total must be a positive integer (compute_worst_case の結果を書く)")
    if total != sum(components.values()):
        raise BudgetError(f"{BUDGET_KEY}.total must equal the sum of components")
    if check_formula:
        expected = compute_worst_case(bounds)
        if expected["components"] != components or expected["total"] != total:
            raise BudgetError(
                f"{BUDGET_KEY} の components/total が compute_worst_case(bounds) と違う "
                f"(定義 total={total} / 計算 total={expected['total']})。--print-expected の値を書く"
            )
    return budget


def compute_worst_case(bounds: Mapping[str, int]) -> dict:
    """Return ``{"components": {name: count}, "total": sum}`` for one run_id.

    bounds の意味 (どれも「その上限まで回ったとき」の値):
    - gate_deny_cycles: create の Gate が差し戻せる回数。差し戻すと build をやり直し、同じ run_id で数える
    - build_rerun_cycles: build の決定論ゲート未達で、build がやり直せる回数 (release の上限)
    - initial_diagnosis_contexts: 1 回の build で初回診断の evaluator を起動する数
    - improvement_rounds: 改善の深さのうち最も深いものの max_rounds (executor を起動する上限)
    - content_review_inner / content_review_outer: content-review の評価→改善→再評価の周回上限
    - goal_seek_loops: goal-seek の手順反復の上限
    - verification_actions: planner が 1 run で許す検証用 model action の累積上限

    1 model action = AI context を 1 つ起動すること。total は components の合計にする。
    """
    # 「最大 N 周」は初回とは別に N 回やり直せる、と多い側に読む (今通っている run を止めないため)。
    # Gate の差し戻しは build 全体をやり直すので、初回診断・改善・検証のすべてに掛かる。
    builds = 1 + bounds["gate_deny_cycles"]
    # 決定論ゲート未達のやり直しは、利用者に見せる前の build の中で回る。
    # 初回診断と改善は見せた後に 1 回ずつなので、ここで増えるのは検証だけ。
    attempts = builds * (1 + bounds["build_rerun_cycles"])
    # build の中の content-review は Step 12 の llm_batches として verification に入っている。
    # content-review の inner/outer 再評価周回と goal-seek (生成先の skill に入れる配線) は
    # gate も planner も通らず、足しても止める地点の無い余白になるので予算には入れない。
    # 上限が動いたことは bound_sources で捕まえる。
    components = {
        "initial_diagnosis": builds * bounds["initial_diagnosis_contexts"],
        "bounded_improvement": builds * bounds["improvement_rounds"],
        "verification": attempts * bounds["verification_actions"],
    }
    return {"components": components, "total": sum(components.values())}


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else ""


def _ints(path: Path, pattern: str, *, frontmatter: bool = False) -> list[int]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BudgetError(f"cannot read loop bound source ({path}): {exc}") from exc
    if frontmatter:
        text = _frontmatter(text)
    values = [int(match) for match in re.findall(pattern, text, flags=re.MULTILINE)]
    if not values:
        raise BudgetError(f"loop bound pattern not found in {path}: {pattern}")
    return values


def _pointer(doc: Any, path: tuple[str, ...], label: str) -> Any:
    node = doc
    for part in path:
        if not isinstance(node, dict) or part not in node:
            raise BudgetError(f"loop bound {label} is missing: /{'/'.join(path)}")
        node = node[part]
    return node


def default_policy_path(skills_root: Path) -> Path:
    return Path(skills_root) / "run-elegant-review" / "references" / "convergence-policy.json"


def collect_bound_sources(skills_root: Path = DEFAULT_SKILLS_ROOT, policy_path: Path | None = None) -> list[tuple[str, str, int]]:
    """Read every place that declares a loop bound; return (bound key, source, value).

    policy_path を省くと skills_root の下の正本を読む。CLI は予算を読んだのと同じ policy を渡す。
    """
    root = Path(skills_root)
    policy = _read_json(Path(policy_path) if policy_path is not None else default_policy_path(root), "convergence policy")
    flags = _read_json(root / "run-build-skill" / "schemas" / "build-flags.schema.json", "build flags schema")
    levels = _read_json(root / "run-build-skill" / "references" / "improvement-levels.json", "improvement levels")
    create_manifest = _read_json(root / "run-skill-create" / "workflow-manifest.json", "run-skill-create workflow manifest")
    feedback = ("properties", "feedback_contract", "properties")
    sources: list[tuple[str, str, int]] = [
        ("goal_seek_loops", "convergence-policy.json#/loop_bounds/goal_seek_inner/value",
         _pointer(policy, ("loop_bounds", "goal_seek_inner", "value"), "goal_seek_inner")),
        ("goal_seek_loops", "convergence-policy.json#/parameters/inner_max_loops",
         _pointer(policy, ("parameters", "inner_max_loops"), "inner_max_loops")),
        ("content_review_inner", "convergence-policy.json#/loop_bounds/content_review_inner_reeval/value",
         _pointer(policy, ("loop_bounds", "content_review_inner_reeval", "value"), "content_review_inner_reeval")),
        ("content_review_outer", "convergence-policy.json#/loop_bounds/content_review_outer_reeval/value",
         _pointer(policy, ("loop_bounds", "content_review_outer_reeval", "value"), "content_review_outer_reeval")),
        ("content_review_outer", "convergence-policy.json#/parameters/max_iterations",
         _pointer(policy, ("parameters", "max_iterations"), "max_iterations")),
        ("goal_seek_loops", "build-flags.schema.json#/properties/with_goal_seek/properties/max_loops/default",
         _pointer(flags, ("properties", "with_goal_seek", "properties", "max_loops", "default"), "with_goal_seek.max_loops")),
        ("content_review_inner", "build-flags.schema.json#/properties/feedback_contract/properties/inner_loop/properties/max_iterations/default",
         _pointer(flags, feedback + ("inner_loop", "properties", "max_iterations", "default"), "inner_loop.max_iterations")),
        ("content_review_outer", "build-flags.schema.json#/properties/feedback_contract/properties/outer_loop/properties/max_iterations/default",
         _pointer(flags, feedback + ("outer_loop", "properties", "max_iterations", "default"), "outer_loop.max_iterations")),
        ("gate_deny_cycles", "run-skill-create/workflow-manifest.json#/max_iterations",
         _pointer(create_manifest, ("max_iterations",), "workflow max_iterations")),
    ]
    rule = str(_pointer(policy, ("halt_conditions", "max_iterations_reached", "rule"), "max_iterations_reached.rule"))
    halt = re.fullmatch(r"iteration_count >= (\d+)", rule.strip())
    if halt is None:
        raise BudgetError(f"halt_conditions.max_iterations_reached.rule is not 'iteration_count >= N': {rule}")
    sources.append(("content_review_outer", "convergence-policy.json#/halt_conditions/max_iterations_reached/rule", int(halt.group(1))))
    level_map = _pointer(levels, ("levels",), "levels")
    if not isinstance(level_map, dict):
        raise BudgetError("improvement-levels.json levels must be an object")
    rounds = [level.get("max_rounds") for level in level_map.values() if isinstance(level, dict)]
    if not rounds or not all(_is_count(value) for value in rounds):
        raise BudgetError("improvement-levels.json levels[].max_rounds must be non-negative integers")
    sources.append(("improvement_rounds", "improvement-levels.json#/levels/*/max_rounds (最大値)", max(rounds)))
    regex_sources = (
        ("gate_deny_cycles", "run-skill-create/prompts/R2-gate-review.md (最大 N 周 / 否認 N 周)",
         root / "run-skill-create" / "prompts" / "R2-gate-review.md", r"(?:最大|否認)\s*(\d+)\s*周", False),
        ("build_rerun_cycles", "run-build-skill/SKILL.md (release で最大 N 周)",
         root / "run-build-skill" / "SKILL.md", r"release\s*で?\s*最大\s*(\d+)\s*周", False),
        ("content_review_outer", "run-build-skill/SKILL.md frontmatter feedback_contract.max_iterations",
         root / "run-build-skill" / "SKILL.md", r"^  max_iterations:\s*(\d+)\s*$", True),
        ("content_review_outer", "run-skill-create/SKILL.md frontmatter feedback_contract.max_iterations",
         root / "run-skill-create" / "SKILL.md", r"^  max_iterations:\s*(\d+)\s*$", True),
        ("initial_diagnosis_contexts", "run-build-skill/scripts/build-improvement-gate.py evaluator_context_limit",
         root / "run-build-skill" / "scripts" / "build-improvement-gate.py", r'"evaluator_context_limit":\s*(\d+)', False),
        ("verification_actions", "run-build-skill/scripts/plan-verification-obligations.py DEFAULT_INCREMENTAL_MODEL_ACTIONS",
         root / "run-build-skill" / "scripts" / "plan-verification-obligations.py", r"^DEFAULT_INCREMENTAL_MODEL_ACTIONS = (\d+)$", False),
    )
    for key, label, path, pattern, frontmatter in regex_sources:
        for value in _ints(path, pattern, frontmatter=frontmatter):
            sources.append((key, label, value))
    return sources


def budget_mismatches(budget: Mapping[str, Any], sources: list[tuple[str, str, int]]) -> list[str]:
    """Return every disagreement between the budget, its sources and the formula."""
    bounds = budget["bounds"]
    problems = []
    seen = {key for key, _, _ in sources}
    for key in BOUND_KEYS:
        if key not in seen:
            problems.append(f"bounds.{key}: 上限を宣言している箇所が 1 つも見つからない")
    for key, label, value in sources:
        if not _is_count(value):
            problems.append(f"bounds.{key}: {label} が非負の整数でない ({value!r})")
        elif value != bounds[key]:
            problems.append(f"bounds.{key}={bounds[key]} だが {label} は {value}")
    expected = compute_worst_case(bounds)
    if expected.get("components") != budget["components"]:
        problems.append(f"components が compute_worst_case と違う: 定義 {budget['components']} / 計算 {expected.get('components')}")
    if expected.get("total") != budget["total"]:
        problems.append(f"total が compute_worst_case と違う: 定義 {budget['total']} / 計算 {expected.get('total')}")
    return problems


def _require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise BudgetError(f"{label} must be a non-empty string without surrounding whitespace")
    return value


def ledger_path(state_dir: Path, run_id: str) -> Path:
    _require_id(run_id, "run_id")
    digest = hashlib.sha256(str(run_id).encode("utf-8")).hexdigest()
    return Path(state_dir) / f"run-model-actions-{digest}.json"


def read_ledger(state_dir: Path, run_id: str) -> dict:
    """Return the validated ledger, or an empty one when the run has not reserved yet."""
    path = ledger_path(state_dir, run_id)
    if path.is_symlink():
        raise BudgetError(f"run model-action ledger must not be a symlink: {path}")
    if not path.exists():
        return {"schema_version": LEDGER_SCHEMA_VERSION, "run_id": run_id, "entries": []}
    ledger = _read_json(path, "run model-action ledger")
    if not isinstance(ledger, dict) or ledger.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise BudgetError("run model-action ledger requires schema_version=1")
    if ledger.get("run_id") != run_id:
        raise BudgetError("run model-action ledger belongs to another run")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise BudgetError("run model-action ledger entries must be an array")
    action_ids = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"action_id", "component", "count", "recorded_at"}
            or not isinstance(entry["action_id"], str) or not entry["action_id"]
            or entry["component"] not in LEDGER_COMPONENTS
            or not _is_count(entry["count"])
            or not isinstance(entry["recorded_at"], str)
        ):
            raise BudgetError(f"run model-action ledger entry is malformed: {entry!r}")
        if entry["action_id"] in action_ids:
            raise BudgetError(f"run model-action ledger has a duplicate action_id: {entry['action_id']}")
        action_ids.add(entry["action_id"])
    bound_total = ledger.get("budget_total")
    if bound_total is not None:
        if type(bound_total) is not int or bound_total < 1:
            raise BudgetError("run model-action ledger budget_total must be a positive integer")
        if ledger_consumed(ledger) > bound_total:
            raise BudgetError(f"run model-action ledger is overdrawn: consumed {ledger_consumed(ledger)} > budget_total {bound_total}")
    return ledger


def check_ledger_total(ledger: Mapping[str, Any], total: int) -> None:
    """The ledger remembers the total it was opened with; refuse a caller reading another policy."""
    bound_total = ledger.get("budget_total")
    if bound_total is not None and bound_total != total:
        raise BudgetError(
            f"run model-action ledger was opened with total {bound_total}, but this caller uses {total} "
            "(gate・launcher・planner は同じ convergence-policy.json を読む)"
        )


def ledger_consumed(ledger: Mapping[str, Any]) -> int:
    return sum(entry["count"] for entry in ledger["entries"])


def budget_status(total: int, consumed: int) -> dict:
    return {"total": total, "consumed": consumed, "remaining": total - consumed}


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.with_suffix(path.suffix + ".lock"), flags, 0o600)
    except OSError as exc:
        raise BudgetError(f"cannot lock the run model-action ledger ({path}): {exc}") from exc
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_write_json(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _family(ledger: Mapping[str, Any], action_id: str, component: str, *, at_least: bool) -> tuple[list[dict], int]:
    """action_id の予約 (at_least なら過去の top-up も) と、その合計を返す。別の component なら拒む。"""
    family = [
        entry for entry in ledger["entries"]
        if entry["action_id"] == action_id or (at_least and entry["action_id"].startswith(action_id + TOPUP_MARKER))
    ]
    if any(entry["component"] != component for entry in family):
        raise BudgetError(f"action {action_id} was already reserved for another component")
    return family, sum(entry["count"] for entry in family)


def verification_action_id(subject: str) -> str:
    _require_id(subject, "subject")
    action_id = VERIFICATION_ACTION_PREFIX + subject
    if TOPUP_MARKER in action_id:
        raise BudgetError(f"subject must not contain {TOPUP_MARKER!r}: {subject}")
    return action_id


def reserve_verification(state_dir: Path, run_id: str, *, required: Mapping[str, int], total: int) -> dict:
    """検証用 model action を、subject ごとに「少なくとも required[subject]」で台帳に予約する。

    required は今の run で使った分と、これから使う分の subject ごとの合計。planner と gate は同じ
    plan から同じ値を出すので、2 回目は何も足さない (足りない subject の差分だけを top-up で足す)。
    全 subject の差分を 1 つの lock の中で足し、合計が total を超えるなら何も書かずに BudgetExhausted。
    並行する検証が lock の外で読んだ残りをそれぞれ使い、合わせて total を超えることはない。
    """
    if not isinstance(required, Mapping):
        raise BudgetError("required must map subject to a non-negative integer")
    wanted: list[tuple[str, int]] = []
    for subject in sorted(required):
        count = required[subject]
        if not _is_count(count):
            raise BudgetError(f"required[{subject!r}] must be a non-negative integer")
        wanted.append((verification_action_id(subject), count))
    if type(total) is not int or total < 1:
        raise BudgetError("total must be a positive integer")
    path = ledger_path(state_dir, run_id)
    with _locked(path):
        ledger = read_ledger(state_dir, run_id)
        check_ledger_total(ledger, total)
        consumed = ledger_consumed(ledger)
        recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        additions = []
        for action_id, count in wanted:
            family, held = _family(ledger, action_id, "verification", at_least=True)
            if held >= count:
                continue
            additions.append({
                "action_id": action_id if not family else f"{action_id}{TOPUP_MARKER}{count}",
                "component": "verification",
                "count": count - held,
                "recorded_at": recorded_at,
            })
        delta = sum(entry["count"] for entry in additions)
        if consumed + delta > total:
            raise BudgetExhausted(
                f"run {run_id} の AI 呼び出し予算が検証に足りない: 消費 {consumed} + 要求 {delta} > 上限 {total}",
                total=total, consumed=consumed, requested=delta,
            )
        if additions:
            ledger["budget_total"] = total
            ledger["entries"].extend(additions)
            try:
                _atomic_write_json(path, ledger)
            except OSError as exc:
                raise BudgetError(f"cannot write the run model-action ledger ({path}): {exc}") from exc
        return {"reserved": bool(additions), "added": delta, **budget_status(total, consumed + delta)}


def reserve(
    state_dir: Path,
    run_id: str,
    *,
    action_id: str,
    component: str,
    count: int,
    total: int,
    external_consumed: int = 0,
    at_least: bool = False,
) -> dict:
    """Reserve ``count`` model actions for ``action_id`` once; refuse when the run budget would overflow.

    同じ action_id の 2 回目は何も足さず、最初の予約をそのまま返す (再配送・再提出で二重に引かない)。
    at_least=False では count が違えば BudgetError。at_least=True は「少なくとも count」の意味で、
    同じ action_id (と過去の top-up) の合計が count 以上ならそのまま使い、足りなければ差分だけを
    ``<action_id>#topup-<count>`` で足す。多く予約した分は返さない (fail-closed)。
    external_consumed は台帳の外で数えた消費で、上限判定にだけ使う。検証は reserve_verification で
    台帳に入るので、渡すのは検証を台帳に予約しなかった古い claim を配送し直すときだけである。
    """
    _require_id(action_id, "action_id")
    if TOPUP_MARKER in action_id:
        raise BudgetError(f"action_id must not contain {TOPUP_MARKER!r}: {action_id}")
    if component not in LEDGER_COMPONENTS:
        raise BudgetError(f"unknown ledger component: {component}")
    if not _is_count(count) or not _is_count(external_consumed) or type(total) is not int or total < 1:
        raise BudgetError("count and external_consumed must be non-negative integers and total a positive integer")
    path = ledger_path(state_dir, run_id)
    with _locked(path):
        ledger = read_ledger(state_dir, run_id)
        check_ledger_total(ledger, total)
        family, held = _family(ledger, action_id, component, at_least=at_least)
        consumed = ledger_consumed(ledger) + external_consumed
        if family and (held == count or (at_least and held >= count)):
            return {"reserved": False, "action_id": action_id, "held": held, **budget_status(total, consumed)}
        if family and not at_least:
            raise BudgetError(f"action {action_id} was already reserved with a different component or count")
        record_id = action_id if not family else f"{action_id}{TOPUP_MARKER}{count}"
        delta = count - held
        if consumed + delta > total:
            raise BudgetExhausted(
                f"run {run_id} の AI 呼び出し予算が足りない: 消費 {consumed} + 要求 {delta} > 上限 {total}",
                total=total, consumed=consumed, requested=delta,
            )
        ledger["budget_total"] = total
        ledger["entries"].append({
            "action_id": record_id,
            "component": component,
            "count": delta,
            "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        try:
            _atomic_write_json(path, ledger)
        except OSError as exc:
            raise BudgetError(f"cannot write the run model-action ledger ({path}): {exc}") from exc
        return {"reserved": True, "action_id": action_id, "held": count, **budget_status(total, consumed + delta)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skills-root", default=str(DEFAULT_SKILLS_ROOT))
    parser.add_argument("--policy", help="既定は --skills-root の下の run-elegant-review/references/convergence-policy.json")
    parser.add_argument("--print-expected", action="store_true", help="bounds から計算した components/total を JSON で出す (policy へ書き写す値)")
    parser.add_argument("--run-id", help="--state-dir と一緒に渡すと、その run の台帳の消費と残りを出す")
    parser.add_argument("--state-dir")
    args = parser.parse_args(argv)
    skills_root = Path(args.skills_root)
    policy_path = Path(args.policy) if args.policy else default_policy_path(skills_root)
    try:
        if args.print_expected:
            doc = _read_json(policy_path, "convergence policy")
            bounds = _validated_bounds(_pointer(doc, (BUDGET_KEY, "bounds"), "bounds"))
            print(json.dumps(compute_worst_case(bounds), ensure_ascii=False, indent=2))
            return 0
        if args.run_id or args.state_dir:
            if not (args.run_id and args.state_dir):
                raise BudgetError("--run-id and --state-dir must be given together")
            budget = load_budget(policy_path)
            ledger = read_ledger(Path(args.state_dir), args.run_id)
            check_ledger_total(ledger, budget["total"])
            print(json.dumps(budget_status(budget["total"], ledger_consumed(ledger)), ensure_ascii=False))
            return 0
        budget = load_budget(policy_path, check_formula=False)
        sources = collect_bound_sources(skills_root, policy_path)
        problems = budget_mismatches(budget, sources)
    except BudgetError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if problems:
        for problem in problems:
            print(f"[MISMATCH] {problem}")
        print("Fix: ループ上限を変えたら、その値を run_model_action_budget.bounds に写し、--print-expected の結果を components/total に書く。")
        return 1
    print(f"ok: run_model_action_budget total={budget['total']} は {len(sources)} 個の上限宣言と一致する")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
