#!/usr/bin/env python3
"""Plan bounded live trials from behavior digests and existing evidence.

This script never launches an LLM session.  It turns the documented
``acceptance tier x behavior change x budget`` policy into a deterministic
plan that an orchestrator can execute without rediscovering the rules in
prompt context.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

DEFAULT_MAX_LIVE_TRIALS = 2
DEFAULT_MAX_CONCURRENCY = 2
ACCEPTANCE_TIERS = {"static", "fork", "live"}
LIVE_SIGNAL_TOOLS = {"Skill", "Agent", "AskUserQuestion"}
LOOP_KINDS = {"run", "wrap", "delegate"}
# plugin が live-trial の scenario 正本を置く慣例パス。
SCENARIO_FIXTURE_REL = ("tests", "fixtures", "live-trial-positive-scenarios.json")
CODEX_SCENARIO_FIXTURE_REL = ("tests", "fixtures", "live-trial-codex-scenarios.json")


def _load_sibling(name: str):
    path = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sibling: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index])
    return ""


def _scalar(block: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*([^#\n]+)", block, re.MULTILINE)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def _flow_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [item.strip().strip("'\"") for item in value.split(",") if item.strip()]


def derive_acceptance_tier(skill_dir: Path) -> str:
    """Mirror validate-build-plan.py's static acceptance-tier signals."""
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    block = _frontmatter(text)
    declared = _scalar(block, "acceptance_tier")
    if declared:
        if declared not in ACCEPTANCE_TIERS:
            raise ValueError(f"unknown acceptance_tier in {skill_dir}: {declared}")
        return declared
    kind = _scalar(block, "kind")
    tools = set(_flow_list(_scalar(block, "allowed-tools")))
    has_hooks = any(skill_dir.glob("scripts/hook-*.py"))
    if has_hooks or tools & LIVE_SIGNAL_TOOLS:
        return "live"
    if kind in LOOP_KINDS:
        return "fork"
    return "static"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry_skills(plugin_dir: Path) -> list[str]:
    contract_path = plugin_dir / "references" / "package-contract.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"package contract read/parse error: {contract_path}: {exc}") from exc
    if not isinstance(contract, dict) or contract.get("plugin_name") != plugin_dir.name:
        raise ValueError(f"package contract plugin_name mismatch: {contract_path}")
    entry_points = contract.get("entry_points")
    skills = entry_points.get("skills") if isinstance(entry_points, dict) else None
    if not isinstance(skills, list) or not all(isinstance(item, str) and item for item in skills):
        raise ValueError(f"package contract entry_points.skills must be strings: {contract_path}")
    if len(skills) != len(set(skills)):
        raise ValueError(f"package contract entry_points.skills contains duplicates: {contract_path}")
    return skills


def _current_scenario_ids(plugin_dir: Path, skill: str, runtime: str = "claude") -> set[str] | None:
    """scenario 正本が定める、その skill の現行 scenario_id 集合を返す。

    正本を持たない plugin だけは None を返して突合しない。正本が存在するのに対象
    skill の scenario が 0 件なら空集合を返す。0 件を None と同一視すると、scenario を
    削除しても削除前の PASS 証拠を再利用でき、契約の失効操作が無効になるため。
    """
    relative = CODEX_SCENARIO_FIXTURE_REL if runtime == "codex" else SCENARIO_FIXTURE_REL
    path = plugin_dir.joinpath(*relative)
    if not path.is_file():
        return None
    try:
        suite = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # 正本が読めないなら再利用可否を判断できない。黙って全再利用に倒すと
        # 「正本を壊せば旧証跡が永久に通る」経路になるので fail-closed。
        raise ValueError(f"scenario fixture is unreadable: {path}") from exc
    scenarios = suite.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError(f"scenario fixture has no scenarios list: {path}")
    ids = {
        item["scenario_id"]
        for item in scenarios
        if isinstance(item, dict)
        and item.get("skill") == skill
        and isinstance(item.get("scenario_id"), str)
        and item["scenario_id"]
    }
    return ids


def _evidence_selection():
    """lint と同じ criteria receipt 選択。受領証跡と再利用証跡を分裂させない。"""
    path = (
        Path(__file__).resolve().parents[5]
        / "plugins" / "dev-graph" / "lib" / "live_trial_evidence_selection.py"
    )
    return _load_sibling_path(path)


def _load_sibling_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load evidence selection: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _closure_sha(verdict_module, skill_dir: Path, runtime: str) -> str:
    """指定 runtime の挙動閉包。Claude は既存の引数なし digest のまま。"""
    if runtime == "codex":
        return verdict_module.skill_dir_tree_sha(skill_dir, runtime="codex")
    return verdict_module.skill_dir_tree_sha(skill_dir)


def _recorded_runtime(path: Path) -> str | None:
    """証跡の runtime。未記録は Claude。読めない、または未知の値は None。"""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    environment = document.get("environment")
    if not isinstance(environment, dict):
        return "claude"
    if "runtime" not in environment or environment.get("runtime") in {None, ""}:
        return "claude"
    runtime = environment.get("runtime")
    if runtime in {"claude", "codex"}:
        return runtime
    return None


def _reuse_block(
    path: Path, verdict_module, schema: dict, plugin: str, skill: str,
    behavior_sha: str, scenario_ids: set[str] | None, runtime: str,
    skill_dir: Path | None,
) -> str | None:
    """再利用できるとき None。できないときはその証跡の理由。"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "invalid-verdict-json"
    if verdict_module.validate_schema(doc, schema):
        return "invalid-verdict-schema"
    if doc.get("target_skill") != f"{plugin}:{skill}":
        return "target-mismatch"
    if doc.get("environment", {}).get("runtime", "claude") != runtime:
        return "runtime-mismatch"
    if doc.get("overall", {}).get("verdict") != "PASS" or doc.get("tier") != "live":
        return "latest-evidence-not-pass"
    if doc.get("skill_dir_tree_sha") != behavior_sha:
        return "behavior-changed"
    scenario_id = doc.get("scenario_id")
    if not scenario_id:
        return "scenario-unbound"
    if scenario_ids is not None and scenario_id not in scenario_ids:
        # policy は「scenario 契約を変えたら scenario_id を bump して旧証跡を無効化
        # する」と宣言しているが、非空検査だけでは bump が失効操作にならず、契約を
        # 改訂しても旧契約下の PASS が current-pass のまま再利用され続ける。
        return "scenario-contract-superseded"
    expected_transcript_sha = doc.get("transcript_sha256")
    transcript = path.parent / "transcript.jsonl"
    if not expected_transcript_sha or not transcript.is_file():
        return "transcript-missing"
    if _sha256(transcript) != expected_transcript_sha:
        return "transcript-digest-mismatch"
    if runtime == "codex":
        source = skill_dir or Path(__file__).resolve().parents[4] / plugin / "skills" / skill
        if verdict_module.validate_runtime_evidence(doc, transcript, source):
            return "invalid-runtime-evidence"
    return None


def _behavior_drift(
    verdict_module, repo: Path, skill_dir: Path | None, verdict_path: Path, runtime: str,
) -> list[str]:
    """受領 commit から見た挙動差分。git 不能なら空。sha は書き換えない。"""
    if skill_dir is None:
        return []
    commit = verdict_module.verdict_baseline_commit(repo, verdict_path)
    if not commit:
        return []
    labels = verdict_module.closure_drift_labels(
        repo, skill_dir, commit, runtime=runtime,
    )
    return labels or []


def _valid_reusable_evidence(
    verdict_module, schema: dict, eval_root: Path, plugin: str, skill: str,
    behavior_sha: str, scenario_ids: set[str] | None = None,
    runtime: str = "claude", skill_dir: Path | None = None,
) -> tuple[Path | None, str, list[str] | None, str | None]:
    """再利用する verdict、できない理由、behavior-changed の差分、受領 runtime。

    criteria receipt がある skill は、その PASS だけを受理証跡にする。閉包と
    drift は証跡自身の runtime で見る。計画の runtime とは比べない。辞書順で
    新しい BLOCKED は、receipt の current PASS を隠さない。壊れた receipt は
    別の PASS へ読み替えない。receipt が無い skill だけ、計画 runtime で新しい
    順に走査する。そのときの受領 runtime は None。
    """
    repo = eval_root.resolve().parent
    selected, error = _evidence_selection().verdict_selection_from_criteria_receipt(
        repo, plugin, skill,
    )
    if error:
        return None, error, None, None
    if selected is not None:
        recorded = _recorded_runtime(selected)
        judge_runtime = recorded if recorded in {"claude", "codex"} else runtime
        judge_sha = behavior_sha
        judge_scenarios = scenario_ids
        if recorded in {"claude", "codex"} and skill_dir is not None:
            judge_sha = _closure_sha(verdict_module, skill_dir, judge_runtime)
            judge_scenarios = _current_scenario_ids(skill_dir.parents[1], skill, judge_runtime)
        block = _reuse_block(
            selected, verdict_module, schema, plugin, skill, judge_sha,
            judge_scenarios, judge_runtime, skill_dir,
        )
        evidence_runtime = recorded if recorded in {"claude", "codex"} else None
        if block is None:
            return selected, "current-pass", None, evidence_runtime
        drift = (
            _behavior_drift(verdict_module, repo, skill_dir, selected, judge_runtime)
            if block == "behavior-changed" else None
        )
        return None, block, drift, evidence_runtime

    trial_root = eval_root / plugin / skill / "live-trial"
    verdicts = sorted(trial_root.glob("*/verdict.json"), reverse=True)
    if not verdicts:
        return None, "missing-evidence", None, None
    # verdicts は新しい順。返す理由は「最新の証跡がなぜ失格か」でなければならない。
    # 走査の最後 (= 最古の証跡) の理由を返すと、運用者は既に解決済みの古い理由を
    # 見せられ、現在の再走要因を取り違える。
    reasons: list[str] = []
    behavior_path: Path | None = None
    for path in verdicts:
        block = _reuse_block(
            path, verdict_module, schema, plugin, skill, behavior_sha,
            scenario_ids, runtime, skill_dir,
        )
        if block is None:
            return path, "current-pass", None, None
        if block == "behavior-changed" and behavior_path is None:
            behavior_path = path
        reasons.append(block)
    reason = reasons[0] if reasons else "no-current-pass"
    drift = None
    if reason == "behavior-changed" and behavior_path is not None:
        drift = _behavior_drift(verdict_module, repo, skill_dir, behavior_path, runtime)
    return None, reason, drift, None


def _bind_acceptance_runtime(record: dict, verdict_module, skill_dir: Path, acceptance_runtime: str) -> None:
    """refresh の実走・再利用は受領 runtime の閉包に合わせる。"""
    record["runtime"] = acceptance_runtime
    record["behavior_sha256"] = _closure_sha(verdict_module, skill_dir, acceptance_runtime)


def _live_batches(scheduled: list[dict], max_concurrency: int) -> list[list[str]]:
    """同じ runtime だけを同時実行する。runtime ごとに concurrency で切る。"""
    grouped: dict[str, list[str]] = {}
    for record in scheduled:
        grouped.setdefault(str(record.get("runtime") or "claude"), []).append(record["skill"])
    batches: list[list[str]] = []
    for names in grouped.values():
        batches.extend(
            names[index:index + max_concurrency]
            for index in range(0, len(names), max_concurrency)
        )
    return batches


def build_plan(
    plugin_dir: Path, eval_root: Path, profile: str = "incremental",
    max_live_trials: int = DEFAULT_MAX_LIVE_TRIALS,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    selected_skills: list[str] | None = None,
    runtime: str = "claude",
) -> dict:
    plugin_dir = plugin_dir.resolve()
    eval_root = eval_root.resolve()
    if profile not in {"incremental", "exhaustive", "build-only", "refresh"}:
        raise ValueError(f"unsupported profile: {profile}")
    if runtime not in {"claude", "codex"}:
        raise ValueError(f"unsupported runtime: {runtime}")
    if max_live_trials < 0:
        raise ValueError("max_live_trials must be >= 0")
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be >= 1")

    verdict_module = _load_sibling("live-trial-verdict")
    schema_path = Path(verdict_module._schema_path())
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    all_skills = _entry_skills(plugin_dir)
    if selected_skills:
        unknown = sorted(set(selected_skills) - set(all_skills))
        if unknown:
            raise ValueError(f"skills are not declared entry points: {unknown}")
        selected = set(selected_skills)
        all_skills = [skill for skill in all_skills if skill in selected]

    records: list[dict] = []
    live_candidates: list[dict] = []
    for skill in all_skills:
        skill_dir = plugin_dir / "skills" / skill
        if not (skill_dir / "SKILL.md").is_file():
            raise ValueError(f"declared skill is missing: {skill_dir / 'SKILL.md'}")
        tier = derive_acceptance_tier(skill_dir)
        behavior_sha = (verdict_module.skill_dir_tree_sha(skill_dir, runtime=runtime)
                        if runtime == "codex" else verdict_module.skill_dir_tree_sha(skill_dir))
        record = {
            "skill": skill,
            "runtime": runtime,
            "acceptance_tier": tier,
            "behavior_sha256": behavior_sha,
            "action": tier,
            "reason": f"acceptance-tier-{tier}",
            "reused_evidence": None,
        }
        if tier != "live":
            records.append(record)
            continue
        evidence, reason, drift, acceptance_runtime = _valid_reusable_evidence(
            verdict_module, schema, eval_root, plugin_dir.name, skill, behavior_sha,
            _current_scenario_ids(plugin_dir, skill, runtime), runtime, skill_dir,
        )
        cross_runtime = acceptance_runtime is not None and acceptance_runtime != runtime
        if profile == "build-only":
            record.update({
                "action": "defer",
                "reason": "not-run(profile=build-only)",
            })
        elif reason.startswith("criteria-receipt-"):
            # 壊れた受領書を別 run の実走で埋めない。修復対象として queue に残す。
            record.update({
                "action": "defer",
                "reason": reason,
                "evidence_reason": reason,
            })
        elif profile == "refresh" and acceptance_runtime in {"claude", "codex"}:
            # 受領 runtime で current なら再利用し、stale ならその runtime で実走する。
            # 計画の --runtime は receipt が無い skill だけに使う。
            _bind_acceptance_runtime(record, verdict_module, skill_dir, acceptance_runtime)
            if evidence is not None:
                record.update({
                    "action": "reuse",
                    "reason": reason,
                    "reused_evidence": str(evidence),
                })
            else:
                record.update({"action": "candidate", "reason": reason})
                if drift is not None:
                    record["behavior_drift"] = drift
                live_candidates.append(record)
        elif profile in {"incremental", "refresh"} and evidence is not None and not cross_runtime:
            record.update({
                "action": "reuse",
                "reason": reason,
                "reused_evidence": str(evidence),
            })
        elif profile == "exhaustive":
            # current PASS も含めて再実走する。受領閉包が stale なら、runtime が
            # 違っても behavior-changed を残して予算順の先頭に置く。
            keep_behavior = reason == "behavior-changed"
            record.update({
                "action": "candidate",
                "reason": reason if keep_behavior else "exhaustive-profile",
            })
            if cross_runtime:
                record["acceptance_runtime"] = acceptance_runtime
            if drift is not None:
                record["behavior_drift"] = drift
            live_candidates.append(record)
        elif cross_runtime and reason == "current-pass":
            record.update({
                "action": "candidate",
                "reason": "runtime-mismatch",
                "acceptance_runtime": acceptance_runtime,
            })
            live_candidates.append(record)
        else:
            record.update({"action": "candidate", "reason": reason})
            if cross_runtime:
                record["acceptance_runtime"] = acceptance_runtime
            if drift is not None:
                record["behavior_drift"] = drift
            live_candidates.append(record)
        records.append(record)

    # 予算は、CI が拒否している挙動差分から使う。欠測だけの skill が先に枠を
    # 埋めると、改善すべき skill が理由ごと予算超過へ潰れる。
    live_candidates.sort(key=lambda record: record.get("reason") != "behavior-changed")
    unbounded = profile in {"exhaustive", "refresh"}
    live_limit = len(live_candidates) if unbounded else max_live_trials
    scheduled = live_candidates[:live_limit]
    for record in scheduled:
        record["action"] = "run"
    for record in live_candidates[live_limit:]:
        record["evidence_reason"] = record["reason"]
        record["action"] = "defer"
        record["reason"] = f"live-budget-exhausted:{max_live_trials}"

    scheduled_names = [record["skill"] for record in scheduled]
    concurrency = min(max_concurrency, len(scheduled_names)) if scheduled_names else 0
    batches = _live_batches(scheduled, max_concurrency) if scheduled else []
    counts = {
        action: sum(1 for record in records if record["action"] == action)
        for action in ("static", "fork", "reuse", "run", "defer")
    }
    return {
        "schema_version": 1,
        "plugin": plugin_dir.name,
        "runtime": runtime,
        "profile": profile,
        "policy": {
            "max_live_trials": (
                None if profile in {"exhaustive", "refresh"} else 0 if profile == "build-only"
                else max_live_trials
            ),
            "max_concurrency": max_concurrency,
            "effective_concurrency": concurrency,
            "evidence_reuse_requires": [
                "schema-valid PASS live verdict",
                "criteria receipt PASS when a live-trial ref exists; otherwise newest reusable PASS",
                "receipt verdict runtime for that closure; plan runtime only when no receipt exists",
                "matching behavior closure digest",
                "stable scenario_id (bump when scenario contract changes)",
                "matching transcript digest",
                "matching runtime and native activation evidence",
            ],
        },
        "counts": counts,
        "live_batches": batches,
        "skills": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plugin-dir", required=True)
    parser.add_argument("--eval-root", default="eval-log")
    parser.add_argument(
        "--profile", choices=("incremental", "exhaustive", "build-only", "refresh"),
        default="incremental",
    )
    parser.add_argument("--max-live-trials", type=int, default=DEFAULT_MAX_LIVE_TRIALS)
    parser.add_argument("--max-concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY)
    parser.add_argument("--skill", action="append", dest="skills")
    parser.add_argument("--runtime", choices=("claude", "codex"), default="claude")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(
            Path(args.plugin_dir), Path(args.eval_root), args.profile,
            args.max_live_trials, args.max_concurrency, args.skills, args.runtime,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
