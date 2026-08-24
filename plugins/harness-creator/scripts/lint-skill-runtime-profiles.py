#!/usr/bin/env python3
# /// script
# name: lint-skill-runtime-profiles
# purpose: plugins 配下の実 Skill が最小十分な runtime profile を明示し、必要資産と整合することを検査する。
# inputs:
#   - argv: [--repo-root PATH] [--plugin NAME] [--skill NAME] [--json]
# outputs:
#   - stdout: 対象数・profile 内訳または JSON report
#   - stderr: fail-closed finding
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""全 plugin の Skill runtime profile を同じ規則で検査する。

構築時の component DAG と、完成後 Skill 内の goal-seek runtime は別契約である。
本 lint が扱うのは後者だけ。loop kind は engine/fork を明示し、Task Graph は
実行時依存 DAG と同梱 engine 資産がある場合だけ、SubAgent/Agent Team は Agent
実行権限がある場合だけ受理する。Goal・Checklist・検証契約の内容評価は既存 lint
と content-review に委ねる。workflow manifest は依存先解決・非循環と
delegate Skill/Agent の実在を併せて検査する。

Exit 0 = 全対象整合、1 = finding、2 = usage error。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


LOOP_KINDS = {"run", "wrap", "delegate"}
ENGINE_VALUES = {"inline", "run-goal-seek", "task-graph"}
FORK_VALUES = {"inline", "subagent", "agent-team"}
TASK_GRAPH_ASSETS = (
    "extract-ready-set-from-checklist.py",
    "build-self-reflection-entry.py",
    "extract-capability-dependency-graph.py",
    "build-capability-graph-knowledge-entry.py",
)
GOAL_SEEK_ANCHOR = "validate-inline-goal-seek-anchor.py"


@dataclass(frozen=True)
class RuntimeProfile:
    path: str
    plugin: str
    skill: str
    kind: str
    applicable: bool
    engine: str | None
    fork: str | None
    findings: tuple[str, ...]


def _strip_scalar(value: str) -> str:
    """単純 YAML scalar から末尾コメントと引用符を除く。"""

    value = value.strip()
    if not value:
        return ""
    if value[0] in {'"', "'"}:
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
    return value.split("#", 1)[0].strip()


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else ""


def _top_scalar(frontmatter: str, key: str) -> str | None:
    match = re.search(
        rf"^{re.escape(key)}:\s*(.*?)\s*$", frontmatter, re.MULTILINE
    )
    return _strip_scalar(match.group(1)) if match else None


def _nested_scalars(frontmatter: str, key: str) -> dict[str, str]:
    """2-space indent の frontmatter mapping を読む（goal_seek 用）。"""

    lines = frontmatter.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.match(rf"^{re.escape(key)}:\s*(?:#.*)?$", line)),
        None,
    )
    if start is None:
        return {}
    values: dict[str, str] = {}
    for line in lines[start + 1 :]:
        if line and not line.startswith((" ", "\t")):
            break
        match = re.match(r"^  ([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if match:
            values[match.group(1)] = _strip_scalar(match.group(2))
    return values


def _has_agent_tool(frontmatter: str) -> bool:
    """Codex の Agent と Claude Code の Task のどちらも受理する。"""

    return bool(
        re.search(r"^\s*-\s*(?:Agent|Task)\s*(?:#.*)?$", frontmatter, re.MULTILINE)
        or re.search(
            r"^allowed-tools:\s*.*\b(?:Agent|Task)\b", frontmatter, re.MULTILINE
        )
    )


def _undeclared_delegation_lines(text: str, frontmatter: str) -> list[str]:
    """Agent/Task 権限が無いのに委譲を必須化する本文を検出する。"""

    if _has_agent_tool(frontmatter):
        return []
    findings: list[str] = []
    for line in text.splitlines():
        if not re.search(r"`(?:Agent|Task)`", line):
            continue
        if not re.search(r"fork|分離\s*context|SubAgent|委譲", line, re.IGNORECASE):
            continue
        if re.search(r"禁止|使わない|不要|しない", line):
            continue
        findings.append(line.strip())
    return findings


def _skill_identity(path: Path, plugins_root: Path) -> tuple[str, str]:
    relative = path.relative_to(plugins_root)
    return relative.parts[0], relative.parts[2]


def _manifest_findings(
    path: Path, frontmatter: str, repo_root: Path, plugin: str
) -> list[str]:
    """workflow manifest の局所依存 DAG と委譲先を検査する。"""

    manifest_ref = _top_scalar(frontmatter, "manifest")
    if not manifest_ref:
        return []
    manifest_path = path.parent / manifest_ref
    if not manifest_path.is_file():
        return [f"manifest が解決できない: {manifest_ref}"]
    # `manifest` はデータ定義 YAML を指す既存 Skill もある。ここでは
    # workflow-manifest JSON の依存 DAG だけを検査し、他形式は各ドメイン lint に委ねる。
    if manifest_path.suffix.lower() != ".json":
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest が読めない: {manifest_ref}: {exc}"]
    phases = payload.get("phases")
    if not isinstance(phases, list):
        return [f"manifest.phases が array でない: {manifest_ref}"]

    findings: list[str] = []
    ids = [phase.get("id") for phase in phases if isinstance(phase, dict)]
    if len(ids) != len(phases) or any(
        not isinstance(item, str) or not item for item in ids
    ):
        return ["manifest phase の id が未宣言または無効"]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        findings.append(f"manifest phase id が重複: {duplicates}")
    id_set = set(ids)
    graph: dict[str, list[str]] = {}
    for phase in phases:
        phase_id = phase["id"]
        depends_on = phase.get("dependsOn", []) or []
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        if not isinstance(depends_on, list) or not all(
            isinstance(dep, str) and dep for dep in depends_on
        ):
            findings.append(f"manifest phase {phase_id} dependsOn が無効")
            continue
        graph[phase_id] = depends_on
        dangling = sorted(set(depends_on) - id_set)
        if dangling:
            findings.append(
                f"manifest phase {phase_id} の dependsOn が dangling: {dangling}"
            )

        delegate_skill = phase.get("delegateSkill")
        if isinstance(delegate_skill, str) and delegate_skill:
            matches = list(
                (repo_root / "plugins").glob(f"*/skills/{delegate_skill}/SKILL.md")
            )
            if not matches:
                findings.append(
                    f"manifest phase {phase_id} の delegateSkill が不在: "
                    f"{delegate_skill}"
                )
        if phase.get("delegateType") == "agent":
            delegate_name = phase.get("delegateName")
            agent_path = (
                repo_root / "plugins" / plugin / "agents" / f"{delegate_name}.md"
            )
            if not isinstance(delegate_name, str) or not agent_path.is_file():
                findings.append(
                    f"manifest phase {phase_id} の delegate agent が不在: "
                    f"{delegate_name!r}"
                )

    state: dict[str, int] = {}

    def visit(node: str, trail: list[str]) -> list[str] | None:
        if state.get(node) == 1:
            return trail + [node]
        if state.get(node) == 2:
            return None
        state[node] = 1
        for dependency in graph.get(node, []):
            if dependency not in graph:
                continue
            cycle = visit(dependency, trail + [node])
            if cycle:
                return cycle
        state[node] = 2
        return None

    for phase_id in graph:
        cycle = visit(phase_id, [])
        if cycle:
            findings.append(f"manifest dependsOn が循環: {' -> '.join(cycle)}")
            break
    return findings


def inspect_skill(path: Path, plugins_root: Path) -> RuntimeProfile:
    plugin, skill = _skill_identity(path, plugins_root)
    relative = path.relative_to(plugins_root.parent).as_posix()
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return RuntimeProfile(
            relative, plugin, skill, "", False, None, None, (f"read error: {exc}",)
        )

    fm = _frontmatter(text)
    kind = (_top_scalar(fm, "prefix") or _top_scalar(fm, "kind") or "").strip()
    applicable = kind in LOOP_KINDS
    goal_seek = _nested_scalars(fm, "goal_seek")
    engine = goal_seek.get("engine")
    fork = goal_seek.get("fork")

    findings.extend(_manifest_findings(path, fm, plugins_root.parent, plugin))

    if applicable:
        if not goal_seek:
            findings.append(
                "loop kind に goal_seek block がない（engine/fork を最小十分に明示する）"
            )
        if engine not in ENGINE_VALUES:
            findings.append(
                f"goal_seek.engine が未宣言または無効: {engine!r} "
                f"(allowed={sorted(ENGINE_VALUES)})"
            )
        if fork not in FORK_VALUES:
            findings.append(
                f"goal_seek.fork が未宣言または無効: {fork!r} "
                f"(allowed={sorted(FORK_VALUES)})"
            )
        if fork in {"subagent", "agent-team"} and not _has_agent_tool(fm):
            findings.append(
                f"fork={fork} だが allowed-tools に Agent/Task がない"
                "（宣言だけで実行不能）"
            )
        undeclared = _undeclared_delegation_lines(text, fm)
        if undeclared:
            findings.append(
                "allowed-tools に Agent/Task がないが本文が分離委譲を必須化: "
                + " | ".join(undeclared[:3])
            )
        if GOAL_SEEK_ANCHOR in text:
            anchor_script = plugins_root / plugin / "scripts" / GOAL_SEEK_ANCHOR
            canonical_anchor = (
                plugins_root
                / "harness-creator"
                / "skills"
                / "run-build-skill"
                / "templates"
                / "goal-seek-runtime"
                / "scripts"
                / GOAL_SEEK_ANCHOR
            )
            if not anchor_script.is_file():
                findings.append(
                    f"{GOAL_SEEK_ANCHOR} を呼ぶが plugin scripts/ に不在"
                )
            elif not canonical_anchor.is_file() or anchor_script.read_bytes() != canonical_anchor.read_bytes():
                findings.append(
                    f"{GOAL_SEEK_ANCHOR} が Harness Creator 正本と不一致"
                )
        if fork == "agent-team":
            missing_team_wiring = [
                token
                for token in ("fan-out", "fan-in")
                if token not in text
            ]
            if not any(
                token in text
                for token in ("ownership", "所有", "write scope", "single writer")
            ):
                missing_team_wiring.append("ownership")
            if missing_team_wiring:
                findings.append(
                    f"fork=agent-team だが並列所有権配線が不足: "
                    f"{missing_team_wiring}"
                )

        scripts_dir = path.parent / "scripts"
        present_assets = {
            name for name in TASK_GRAPH_ASSETS if (scripts_dir / name).is_file()
        }
        if engine == "task-graph":
            missing = sorted(set(TASK_GRAPH_ASSETS) - present_assets)
            if missing:
                findings.append(
                    f"engine=task-graph だが engine asset が不足: {missing}"
                )
            canonical_dir = (
                plugins_root
                / "harness-creator"
                / "skills"
                / "run-build-skill"
                / "templates"
                / "task-graph-engine"
                / "scripts"
            )
            drifted = sorted(
                name
                for name in present_assets
                if not (canonical_dir / name).is_file()
                or (scripts_dir / name).read_bytes()
                != (canonical_dir / name).read_bytes()
            )
            if drifted:
                findings.append(
                    f"task-graph engine asset が正本と不一致: {drifted}"
                )
            if goal_seek.get("engine_profile") != "checklist-graph":
                findings.append(
                    "engine=task-graph だが engine_profile=checklist-graph でない"
                )
            if goal_seek.get("full_task_spec_graph") != "false":
                findings.append(
                    "engine=task-graph だが full_task_spec_graph=false でない"
                )
            required_wiring = (
                "depends_on",
                "extract-ready-set-from-checklist.py",
                "build-self-reflection-entry.py",
                "ready_set",
                "selected_item",
            )
            missing_wiring = [token for token in required_wiring if token not in text]
            if missing_wiring:
                findings.append(
                    f"engine=task-graph だが runtime wiring が不足: {missing_wiring}"
                )
        elif present_assets:
            findings.append(
                f"engine={engine or '<missing>'} だが task-graph asset が残存: "
                f"{sorted(present_assets)}"
            )
    elif goal_seek:
        findings.append("non-loop kind に goal_seek block がある（runtime profile 非適用）")

    return RuntimeProfile(
        relative,
        plugin,
        skill,
        kind,
        applicable,
        engine,
        fork,
        tuple(findings),
    )


def collect_skills(
    repo_root: Path, *, plugin: str | None = None, skill: str | None = None
) -> list[Path]:
    """plugins/<plugin>/skills/<skill>/SKILL.md の正本だけを列挙する。"""

    plugins_root = repo_root / "plugins"
    if plugin and skill:
        candidate = plugins_root / plugin / "skills" / skill / "SKILL.md"
        return [candidate] if candidate.is_file() else []
    plugin_dirs = [plugins_root / plugin] if plugin else sorted(plugins_root.iterdir())
    targets: list[Path] = []
    for plugin_dir in plugin_dirs:
        skills_dir = plugin_dir / "skills"
        if not skills_dir.is_dir():
            continue
        targets.extend(
            sorted(
                candidate / "SKILL.md"
                for candidate in skills_dir.iterdir()
                if candidate.is_dir() and (candidate / "SKILL.md").is_file()
            )
        )
    return targets


def build_report(
    repo_root: Path, *, plugin: str | None = None, skill: str | None = None
) -> dict[str, object]:
    plugins_root = repo_root / "plugins"
    profiles = [
        inspect_skill(path, plugins_root)
        for path in collect_skills(repo_root, plugin=plugin, skill=skill)
    ]
    by_profile: dict[str, int] = {}
    for profile in profiles:
        key = (
            f"{profile.engine}/{profile.fork}"
            if profile.applicable
            else "not-applicable"
        )
        by_profile[key] = by_profile.get(key, 0) + 1
    return {
        "schema_version": "1.0.0",
        "repo_root": str(repo_root),
        "summary": {
            "skills": len(profiles),
            "loop_skills": sum(profile.applicable for profile in profiles),
            "findings": sum(len(profile.findings) for profile in profiles),
            "by_profile": dict(sorted(by_profile.items())),
        },
        "skills": [asdict(profile) for profile in profiles],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plugin")
    parser.add_argument("--skill")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.skill and not args.plugin:
        parser.error("--skill requires --plugin")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    if not (repo_root / "plugins").is_dir():
        sys.stderr.write(f"plugins directory not found: {repo_root / 'plugins'}\n")
        return 2
    report = build_report(repo_root, plugin=args.plugin, skill=args.skill)
    if not report["skills"]:
        sys.stderr.write("no canonical SKILL.md target found\n")
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            "skill-runtime-profile: "
            f"skills={summary['skills']} loop={summary['loop_skills']} "
            f"findings={summary['findings']} profiles={summary['by_profile']}"
        )
        for profile in report["skills"]:
            for finding in profile["findings"]:
                sys.stderr.write(f"{profile['path']}: {finding}\n")
    return 1 if report["summary"]["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
