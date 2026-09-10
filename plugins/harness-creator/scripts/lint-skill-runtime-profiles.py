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
from collections.abc import Iterable
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

# goal_seek block 未宣言のまま残る既存 loop skill の ratchet。
# 数を数えず「何が残っているか」で固定する。数値 ratchet は「別の新規 legacy が
# baseline 以内なら素通りする」穴があり、負債の総量しか守れないため。
#
# 配布複製: plugin 追加のたび機械的に複製される skill。path 固定にすると新規 plugin の
# 追加が常にブロックされるので skill 名で一括許容する。複製元 template 側で goal_seek を
# 宣言すれば全複製が一度に解消するので、返済は 1 箇所で足りる。
LEGACY_LOOP_REPLICA_SKILLS = frozenset({"run-skill-feedback"})

# 配布複製以外で goal_seek 未宣言のまま残る既存 loop skill。宣言移行が済んだら path を削る。
# ここに無い legacy loop skill が現れたら新規負債として fail。
LEGACY_LOOP_BASELINE_PATHS = frozenset(
    {
        "plugins/skill-governance-adapters/skills/run-governance-adapters/SKILL.md",
        "plugins/system-dev-planner/skills/run-system-dev-plan/SKILL.md",
        # x-longpost-creator は本 lint 導入後に main へ入った既存 plugin。
        # allowed-tools に Agent/Task が無く goal-seek/task-graph 資産も参照しないため
        # 宣言値は inline/inline に決まるが、SKILL.md を触ると content-review の
        # skill_md_sha256 pin が無効化され無関係な verdict 8 件の再生成を誘発するので、
        # 宣言の追加は当該 plugin 側の変更に合わせて行う。
        "plugins/x-longpost-creator/skills/run-x-longpost-create/SKILL.md",
        "plugins/x-longpost-creator/skills/run-x-multipost-create/SKILL.md",
        "plugins/x-longpost-creator/skills/run-x-shortpost-optimize/SKILL.md",
        "plugins/x-longpost-creator/skills/run-x-visual-generate/SKILL.md",
    }
)

# has_goal_seek=False の loop skill に限り ratchet 扱いへ降格する finding。
LEGACY_FINDING_MARKERS = (
    "goal_seek block がない",
    "goal_seek.engine が未宣言",
    "goal_seek.fork が未宣言",
)

# fork=subagent と allowed-tools の不整合が導入前から存在する skill。
# 修正は SKILL.md 変更 = live-trial closure の再試行を伴うため、
# closure 更新と同時に解消するまで path 固定で ratchet 扱い。追加は不可。
FORK_TOOLS_MARKER = "allowed-tools に Agent/Task がない"
FORK_TOOLS_BASELINE = frozenset(
    {
        "plugins/system-spec-harness/skills/run-system-spec-compile/SKILL.md",
        "plugins/system-spec-harness/skills/run-system-spec-doc-fetch/SKILL.md",
    }
)


@dataclass(frozen=True)
class RuntimeProfile:
    path: str
    plugin: str
    skill: str
    kind: str
    applicable: bool
    engine: str | None
    fork: str | None
    has_goal_seek: bool
    findings: tuple[str, ...]

    @property
    def is_legacy_loop(self) -> bool:
        return self.applicable and not self.has_goal_seek

    def split_findings(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(enforced, legacy) に分ける。

        legacy は未宣言 loop skill の宣言系 finding と、
        FORK_TOOLS_BASELINE に path 固定された既存不整合だけ。
        """
        enforced: list[str] = []
        legacy: list[str] = []
        for finding in self.findings:
            if self.is_legacy_loop and any(
                marker in finding for marker in LEGACY_FINDING_MARKERS
            ):
                legacy.append(finding)
            elif (
                self.path in FORK_TOOLS_BASELINE
                and FORK_TOOLS_MARKER in finding
            ):
                legacy.append(finding)
            else:
                enforced.append(finding)
        return tuple(enforced), tuple(legacy)


def _unlisted_legacy_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """ratchet に登録されていない legacy loop skill の repo 相対 path を昇順で返す。

    `paths` は goal_seek 未宣言の loop skill (is_legacy_loop=True) の path だけが渡る。
    返り値が非空なら新規負債とみなして main が exit 1 にする。

    許容の根拠は 2 系統ある: 配布複製 (`LEGACY_LOOP_REPLICA_SKILLS`、skill 名で一括許容)
    と、複製以外の既知の残存 (`LEGACY_LOOP_BASELINE_PATHS`、path 固定)。path は
    `plugins/<plugin>/skills/<skill>/SKILL.md` 形式で、skill 名は末尾から 2 番目の要素。
    """
    unlisted: set[str] = set()
    for path in paths:
        if path in LEGACY_LOOP_BASELINE_PATHS:
            continue
        # path は常に "/" 区切りの repo 相対文字列なので split で十分。Path(...).parent.name は
        # Windows 由来の "\\" も分割してしまい、照合対象を広げる方向に緩むため使わない。
        segments = path.split("/")
        skill_name = segments[-2] if len(segments) >= 2 else ""
        if skill_name in LEGACY_LOOP_REPLICA_SKILLS:
            continue
        unlisted.add(path)
    return tuple(sorted(unlisted))


def _stale_legacy_paths(paths: Iterable[str], *, full_scope: bool) -> tuple[str, ...]:
    """返済済み・消滅済みなのに ratchet へ残ったままの登録 path を昇順で返す。

    `paths` は `_unlisted_legacy_paths` と同じく「今なお legacy な loop skill」の path。
    ここに現れない登録 path は、goal_seek を宣言し終えたか、リネーム/削除で実在しなくなったか
    のどちらか。放置すると同じ path が将来再登場した際に黙って再免除され、ratchet が
    締まる方向にしか効かなくなる (片方向 ratchet)。返済を検知した時点で削除を強制することで、
    免除リストが「現に残っている負債」と常に一致する。

    `full_scope=False` (--plugin/--skill による絞り込み実行) では常に空を返す。登録は repo 全体
    の定数なので、範囲外 plugin の登録が「今回集めた path に無い」ことは返済の証拠にならず、
    誤検出になる。しかもその誤検出に従って登録を削ると、次の全体実行で同じ path が今度は
    unlisted 判定になる — ratchet を壊す方向へ利用者を誘導してしまう。
    消滅済み path の検出は「集めた path との交差」では原理的にできない (消えた path は
    どのスコープにも現れない) ため、絞り込み時は検査ごと落とす方を選ぶ。
    """
    if not full_scope:
        return ()
    return tuple(sorted(LEGACY_LOOP_BASELINE_PATHS - set(paths)))


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
            relative, plugin, skill, "", False, None, None, False, (f"read error: {exc}",)
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
        bool(goal_seek),
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
    skill_entries: list[dict[str, object]] = []
    enforced_total = 0
    legacy_total = 0
    legacy_skills = 0
    for profile in profiles:
        enforced, legacy = profile.split_findings()
        entry = asdict(profile)
        entry["enforced_findings"] = list(enforced)
        entry["legacy_findings"] = list(legacy)
        # property は asdict に載らないが、ratchet 判定が report 経由で行われるため明示する。
        entry["is_legacy_loop"] = profile.is_legacy_loop
        skill_entries.append(entry)
        enforced_total += len(enforced)
        legacy_total += len(legacy)
        legacy_skills += profile.is_legacy_loop
    legacy_paths = tuple(entry["path"] for entry in skill_entries if entry["is_legacy_loop"])
    return {
        "schema_version": "1.1.0",
        "repo_root": str(repo_root),
        "summary": {
            "skills": len(profiles),
            "loop_skills": sum(profile.applicable for profile in profiles),
            "findings": sum(len(profile.findings) for profile in profiles),
            "enforced_findings": enforced_total,
            "legacy_findings": legacy_total,
            "legacy_loop_skills": legacy_skills,
            "legacy_loop_registered": len(LEGACY_LOOP_BASELINE_PATHS),
            "legacy_loop_unlisted": list(_unlisted_legacy_paths(legacy_paths)),
            # 返済済み/消滅済みの登録は削除を強制する。免除リストを両方向で実態へ縛るため。
            "legacy_loop_stale": list(
                _stale_legacy_paths(
                    legacy_paths, full_scope=plugin is None and skill is None
                )
            ),
            "by_profile": dict(sorted(by_profile.items())),
        },
        "skills": skill_entries,
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

    summary = report["summary"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "skill-runtime-profile: "
            f"skills={summary['skills']} loop={summary['loop_skills']} "
            f"enforced={summary['enforced_findings']} "
            # 分子/分母の意味が揃わない "27/6+replica" 表記はやめ、内訳を独立した数として出す。
            f"legacy={summary['legacy_loop_skills']} "
            f"registered={summary['legacy_loop_registered']} "
            f"unlisted={len(summary['legacy_loop_unlisted'])} "
            f"stale={len(summary['legacy_loop_stale'])} "
            f"profiles={summary['by_profile']}"
        )
        for profile in report["skills"]:
            for finding in profile["enforced_findings"]:
                sys.stderr.write(f"{profile['path']}: {finding}\n")
            for finding in profile["legacy_findings"]:
                sys.stderr.write(f"{profile['path']}: [legacy] {finding}\n")
    if summary["enforced_findings"]:
        return 1
    if summary["legacy_loop_unlisted"]:
        sys.stderr.write(
            "legacy loop skill ratchet 超過: goal_seek 未宣言の新規 loop skill が"
            f"{len(summary['legacy_loop_unlisted'])} 件ある。宣言するか、既存負債なら "
            "LEGACY_LOOP_BASELINE_PATHS へ根拠付きで登録すること: "
            f"{summary['legacy_loop_unlisted']}\n"
        )
        return 1
    if summary["legacy_loop_stale"]:
        sys.stderr.write(
            "legacy loop skill ratchet の免除が陳腐化: 登録済み path が既に legacy でない"
            f"({len(summary['legacy_loop_stale'])} 件)。返済済みなら "
            "LEGACY_LOOP_BASELINE_PATHS から削って ratchet を締めること: "
            f"{summary['legacy_loop_stale']}\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
