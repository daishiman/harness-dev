"""live-trial の scenario 観測契約を検証する support module。

観測の自己申告だけではなく、run directory 内の実在ファイルへ証拠参照を束縛する。
entry point ではなく ``live-trial-verdict.py`` から読み込まれる。
"""
from __future__ import annotations

import json
import re
from pathlib import Path


_FLAG_PATTERN = re.compile(r"(?<![\w-])--[A-Za-z0-9][A-Za-z0-9-]*")


def load_scenario(scenario_file: Path, scenario_id: str) -> dict:
    """scenarios[] を持つ契約ファイルから scenario_id を一意解決する。"""
    try:
        doc = json.loads(scenario_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"scenario file read/parse error: {scenario_file}: {exc}") from exc
    scenarios = doc.get("scenarios") if isinstance(doc, dict) else None
    if not isinstance(scenarios, list):
        raise ValueError(f"scenario file has no scenarios[]: {scenario_file}")
    matched = [
        item
        for item in scenarios
        if isinstance(item, dict) and item.get("scenario_id") == scenario_id
    ]
    if len(matched) != 1:
        raise ValueError(
            f"scenario_id {scenario_id!r} must resolve to exactly one scenario in "
            f"{scenario_file} (matched {len(matched)})"
        )
    required = matched[0].get("required_observations")
    if not isinstance(required, list) or not required or not all(
        isinstance(item, str) and item.strip() for item in required
    ):
        raise ValueError(
            f"scenario {scenario_id!r} must declare non-empty required_observations strings"
        )
    # Every canonical scenario must be bounded.  Import lazily so this support
    # module remains directly executable in isolation.
    import importlib.util

    budget_path = Path(__file__).resolve().parent / "validate-live-trial-resource-budget.py"
    spec = importlib.util.spec_from_file_location("live_trial_resource_budget", budget_path)
    assert spec and spec.loader
    budget_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(budget_module)
    budget_module.resource_budget(matched[0])
    return matched[0]


def repo_relative_scenario_file(scenario_file: str) -> str:
    """受領書へ記録する scenario_file を、それを所有する repo からの相対へ畳む。

    verdict.json は clone 先で追試されるため、著者の作業機の絶対パスを残すと
    その持ち主の環境でしか解決できない参照になる。evidence_ref は
    ``validate_evidence_claims`` が相対性と閉じ込めを強制しているのに、
    scenario_file だけは受け取った文字列をそのまま記録していた。実際 C04/C19 の
    再実走で作業機の絶対パスが記録され、下流の受領書検査
    (``tests/test_skill_criteria_evidence.py``) が repo 相対を要求して落ちた。

    基準を workdir ではなく scenario file 自身が属する repo に取る。workdir は
    fixture 検証では tmp 配下に置かれ repo を持たないことがあるのに対し、実運用の
    scenario 正本は必ず repo 内にあるためこちらのほうが安定する。どの repo にも
    属さない scenario (tmp fixture など) は畳む基準が無いので受け取った形のまま返す。
    """
    resolved = Path(scenario_file).resolve()
    for candidate in resolved.parents:
        if (candidate / ".git").exists():  # worktree では .git はファイル
            return resolved.relative_to(candidate).as_posix()
    return scenario_file


def parse_observation_claims(raw: list[str], total: int) -> dict[int, str]:
    """``--observation N=<evidence ref>`` を index→evidence へ解く。"""
    claims: dict[int, str] = {}
    for entry in raw:
        index_text, sep, evidence = entry.partition("=")
        if not sep or not evidence.strip():
            raise ValueError(f"--observation は N=<evidence ref> 形式: {entry!r}")
        try:
            index = int(index_text.strip())
        except ValueError as exc:
            raise ValueError(f"--observation の index が整数でない: {entry!r}") from exc
        if not 1 <= index <= total:
            raise ValueError(
                f"--observation の index {index} が required_observations の範囲外 "
                f"(1..{total})"
            )
        if index in claims:
            raise ValueError(f"--observation の index {index} が重複している")
        claims[index] = evidence.strip()
    return claims


def validate_evidence_claims(workdir: Path, claims: dict[int, str]) -> dict[int, str]:
    """Evidence refs must resolve to files contained by the run directory.

    ``path#json-pointer`` の fragment は任意だが、path は相対パスかつ実在する通常
    ファイルでなければならない。これにより ignored fixture や削除済み一時領域への
    dangling ref（参照先が存在しないリンク）を PASS 根拠にできない。
    """
    root = workdir.resolve()
    validated: dict[int, str] = {}
    for index, ref in claims.items():
        path_text, _separator, _fragment = ref.partition("#")
        relative = Path(path_text)
        if not path_text or relative.is_absolute():
            raise ValueError(
                f"--observation {index} の evidence ref は workdir 相対パスが必須: {ref!r}"
            )
        try:
            resolved = (root / relative).resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                f"--observation {index} の evidence file が存在しない: {ref!r}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"--observation {index} の evidence ref が workdir 外へ逸脱: {ref!r}"
            ) from exc
        if not resolved.is_file():
            raise ValueError(
                f"--observation {index} の evidence ref は通常ファイルでない: {ref!r}"
            )
        validated[index] = ref
    return validated


def observation_coverage(
    required: list[str], claims: dict[int, str]
) -> tuple[list[dict], list[dict]]:
    """required_observations を回収済み / 未回収へ機械的に二分する。"""
    observed: list[dict] = []
    unobserved: list[dict] = []
    for index, observation in enumerate(required, start=1):
        evidence = claims.get(index)
        if evidence:
            observed.append(
                {"index": index, "observation": observation, "evidence_ref": evidence}
            )
        else:
            unobserved.append({"index": index, "observation": observation})
    return observed, unobserved


def args_divergence(task_args_template: str, actual_args: str) -> dict:
    """task_args_template と実 args の option flag 集合の差分を測る。"""
    template_flags = sorted(set(_FLAG_PATTERN.findall(task_args_template or "")))
    actual_flags = sorted(set(_FLAG_PATTERN.findall(actual_args or "")))
    missing = [flag for flag in template_flags if flag not in actual_flags]
    extra = [flag for flag in actual_flags if flag not in template_flags]
    return {
        "task_args_template": task_args_template or "",
        "template_flags": template_flags,
        "actual_flags": actual_flags,
        "missing_flags": missing,
        "extra_flags": extra,
        "matches": not missing and not extra,
    }


def validate_task_contract(scenario: dict, task_path: Path) -> dict:
    """scenario が要求する task.md の手順を実ファイルへ束縛する。

    実走 agent が不可能な手順を別経路へ読み替えて完走しても、観測値だけを見れば
    PASS にできてしまう。scenario が ``task_contract`` を宣言した場合は、必須断片と
    禁止断片を task.md の実バイトに照合し、手順契約そのものの drift を拒否する。
    """
    raw = scenario.get("task_contract")
    if raw is None:
        return {
            "declared": False,
            "task_file": task_path.name,
            "task_file_exists": task_path.is_file(),
            "required_fragments": [],
            "forbidden_fragments": [],
            "missing_required_fragments": [],
            "present_forbidden_fragments": [],
            "matches": True,
        }
    if not isinstance(raw, dict):
        raise ValueError("scenario task_contract must be an object")

    def fragments(key: str) -> list[str]:
        values = raw.get(key)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            raise ValueError(
                f"scenario task_contract.{key} must be a string array"
            )
        if len(set(values)) != len(values):
            raise ValueError(f"scenario task_contract.{key} contains duplicates")
        return values

    required = fragments("required_fragments")
    forbidden = fragments("forbidden_fragments")
    exists = task_path.is_file()
    text = task_path.read_text(encoding="utf-8") if exists else ""
    missing = [fragment for fragment in required if fragment not in text]
    present = [fragment for fragment in forbidden if fragment in text]
    return {
        "declared": True,
        "task_file": task_path.name,
        "task_file_exists": exists,
        "required_fragments": required,
        "forbidden_fragments": forbidden,
        "missing_required_fragments": missing,
        "present_forbidden_fragments": present,
        "matches": exists and not missing and not present,
    }


def validate_invocation_contract(scenario: dict, invoked_skills: list[str]) -> dict:
    """Reject expensive or invalid nested Skill calls declared by the scenario."""
    raw = scenario.get("forbidden_invoked_skills", [])
    if not isinstance(raw, list) or not all(
        isinstance(value, str) and value.strip() for value in raw
    ):
        raise ValueError("scenario forbidden_invoked_skills must be a string array")
    if len(set(raw)) != len(raw):
        raise ValueError("scenario forbidden_invoked_skills contains duplicates")
    present = sorted(set(raw) & set(invoked_skills))
    return {
        "forbidden_invoked_skills": raw,
        "present_forbidden_invoked_skills": present,
        "matches": not present,
    }


def scenario_contract_blockers(contract: dict) -> list[str]:
    """scenario 契約の破れを goal blocker 文字列へ落とす。"""
    blockers: list[str] = []
    unobserved = contract["unobserved"]
    if unobserved:
        items = " / ".join(
            f"[{item['index']}] {item['observation']}" for item in unobserved
        )
        blockers.append(
            f"scenario {contract['scenario_id']} の required_observations 未回収 "
            f"{len(unobserved)}/{len(contract['required_observations'])} 件: {items}"
        )
    divergence = contract["args_divergence"]
    if not divergence["matches"]:
        detail = []
        if divergence["missing_flags"]:
            detail.append(f"template のみ {divergence['missing_flags']}")
        if divergence["extra_flags"]:
            detail.append(f"実 args のみ {divergence['extra_flags']}")
        blockers.append(
            f"scenario {contract['scenario_id']} の task_args_template と実 args が乖離: "
            + " / ".join(detail)
            + f" (template={divergence['task_args_template']!r})"
        )
    task = contract.get("task_contract")
    if isinstance(task, dict) and not task.get("matches", False):
        detail = []
        if not task.get("task_file_exists"):
            detail.append(f"{task.get('task_file', 'task.md')} が存在しない")
        if task.get("missing_required_fragments"):
            detail.append(f"必須断片なし {task['missing_required_fragments']}")
        if task.get("present_forbidden_fragments"):
            detail.append(f"禁止断片あり {task['present_forbidden_fragments']}")
        blockers.append(
            f"scenario {contract['scenario_id']} の task.md 手順契約が不一致: "
            + " / ".join(detail)
        )
    resource = contract.get("resource_usage")
    if isinstance(resource, dict) and resource.get("violations"):
        blockers.append(
            f"scenario {contract['scenario_id']} の resource budget 違反: "
            + " / ".join(resource["violations"])
        )
    invocations = contract.get("invocation_contract")
    if isinstance(invocations, dict) and not invocations.get("matches", False):
        blockers.append(
            f"scenario {contract['scenario_id']} の禁止 Skill が実行された: "
            + ", ".join(invocations["present_forbidden_invoked_skills"])
        )
    return blockers
