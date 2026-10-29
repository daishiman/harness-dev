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


def _current_scenario_ids(plugin_dir: Path, skill: str) -> set[str] | None:
    """scenario 正本が定める、その skill の現行 scenario_id 集合を返す。

    正本を持たない plugin だけは None を返して突合しない。正本が存在するのに対象
    skill の scenario が 0 件なら空集合を返す。0 件を None と同一視すると、scenario を
    削除しても削除前の PASS 証拠を再利用でき、契約の失効操作が無効になるため。
    """
    path = plugin_dir.joinpath(*SCENARIO_FIXTURE_REL)
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


def _valid_reusable_evidence(
    verdict_module, schema: dict, eval_root: Path, plugin: str, skill: str,
    behavior_sha: str, scenario_ids: set[str] | None = None,
) -> tuple[Path | None, str]:
    trial_root = eval_root / plugin / skill / "live-trial"
    verdicts = sorted(trial_root.glob("*/verdict.json"), reverse=True)
    if not verdicts:
        return None, "missing-evidence"
    # verdicts は新しい順。返す理由は「最新の証跡がなぜ失格か」でなければならない。
    # 走査の最後 (= 最古の証跡) の理由を返すと、運用者は既に解決済みの古い理由を
    # 見せられ、現在の再走要因を取り違える。
    reasons: list[str] = []
    for path in verdicts:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reasons.append("invalid-verdict-json")
            continue
        if verdict_module.validate_schema(doc, schema):
            reasons.append("invalid-verdict-schema")
            continue
        if doc.get("target_skill") != f"{plugin}:{skill}":
            reasons.append("target-mismatch")
            continue
        if doc.get("overall", {}).get("verdict") != "PASS" or doc.get("tier") != "live":
            reasons.append("latest-evidence-not-pass")
            continue
        if doc.get("skill_dir_tree_sha") != behavior_sha:
            reasons.append("behavior-changed")
            continue
        scenario_id = doc.get("scenario_id")
        if not scenario_id:
            reasons.append("scenario-unbound")
            continue
        if scenario_ids is not None and scenario_id not in scenario_ids:
            # policy は「scenario 契約を変えたら scenario_id を bump して旧証跡を無効化
            # する」と宣言しているが、非空検査だけでは bump が失効操作にならず、契約を
            # 改訂しても旧契約下の PASS が current-pass のまま再利用され続ける。
            reasons.append("scenario-contract-superseded")
            continue
        expected_transcript_sha = doc.get("transcript_sha256")
        transcript = path.parent / "transcript.jsonl"
        if not expected_transcript_sha or not transcript.is_file():
            reasons.append("transcript-missing")
            continue
        if _sha256(transcript) != expected_transcript_sha:
            reasons.append("transcript-digest-mismatch")
            continue
        return path, "current-pass"
    return None, reasons[0] if reasons else "no-current-pass"


def build_plan(
    plugin_dir: Path, eval_root: Path, profile: str = "incremental",
    max_live_trials: int = DEFAULT_MAX_LIVE_TRIALS,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    selected_skills: list[str] | None = None,
) -> dict:
    plugin_dir = plugin_dir.resolve()
    eval_root = eval_root.resolve()
    if profile not in {"incremental", "exhaustive", "build-only"}:
        raise ValueError(f"unsupported profile: {profile}")
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
        behavior_sha = verdict_module.skill_dir_tree_sha(skill_dir)
        record = {
            "skill": skill,
            "acceptance_tier": tier,
            "behavior_sha256": behavior_sha,
            "action": tier,
            "reason": f"acceptance-tier-{tier}",
            "reused_evidence": None,
        }
        if tier != "live":
            records.append(record)
            continue
        evidence, reason = _valid_reusable_evidence(
            verdict_module, schema, eval_root, plugin_dir.name, skill, behavior_sha,
            _current_scenario_ids(plugin_dir, skill),
        )
        if profile == "build-only":
            record.update({
                "action": "defer",
                "reason": "not-run(profile=build-only)",
            })
        elif profile == "incremental" and evidence is not None:
            record.update({
                "action": "reuse",
                "reason": reason,
                "reused_evidence": str(evidence),
            })
        else:
            record.update({
                "action": "candidate",
                "reason": "exhaustive-profile" if profile == "exhaustive" else reason,
            })
            live_candidates.append(record)
        records.append(record)

    live_limit = len(live_candidates) if profile == "exhaustive" else max_live_trials
    scheduled = live_candidates[:live_limit]
    for record in scheduled:
        record["action"] = "run"
    for record in live_candidates[live_limit:]:
        record["action"] = "defer"
        record["reason"] = f"live-budget-exhausted:{max_live_trials}"

    scheduled_names = [record["skill"] for record in scheduled]
    concurrency = min(max_concurrency, len(scheduled_names)) if scheduled_names else 0
    batches = [
        scheduled_names[index:index + concurrency]
        for index in range(0, len(scheduled_names), concurrency)
    ] if concurrency else []
    counts = {
        action: sum(1 for record in records if record["action"] == action)
        for action in ("static", "fork", "reuse", "run", "defer")
    }
    return {
        "schema_version": 1,
        "plugin": plugin_dir.name,
        "profile": profile,
        "policy": {
            "max_live_trials": (
                None if profile == "exhaustive" else 0 if profile == "build-only"
                else max_live_trials
            ),
            "max_concurrency": max_concurrency,
            "effective_concurrency": concurrency,
            "evidence_reuse_requires": [
                "schema-valid PASS live verdict",
                "matching behavior closure digest",
                "stable scenario_id (bump when scenario contract changes)",
                "matching transcript digest",
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
        "--profile", choices=("incremental", "exhaustive", "build-only"),
        default="incremental",
    )
    parser.add_argument("--max-live-trials", type=int, default=DEFAULT_MAX_LIVE_TRIALS)
    parser.add_argument("--max-concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY)
    parser.add_argument("--skill", action="append", dest="skills")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(
            Path(args.plugin_dir), Path(args.eval_root), args.profile,
            args.max_live_trials, args.max_concurrency, args.skills,
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
