#!/usr/bin/env python3
"""PKG-002〜008 / PKG-014 sub-check 実装。

正本仕様: doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md
findings schema: ../schemas/findings.schema.json

使い方:
  python3 validate-plugin-package.py --check pkg-002 --plugin harness-creator
  python3 validate-plugin-package.py --check all --plugin harness-creator

exit codes:
  0  全 PKG check pass または not_applicable
  1  1 件以上 fail
  2  schema 違反・入力エラー
"""

from __future__ import annotations
import argparse
import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

def _default_plugins_root() -> Path:
    env_plugin = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_plugin:
        return Path(env_plugin).expanduser().resolve().parent
    return Path(__file__).resolve().parents[5] / "plugins"


def _resolve_plugin_dir(plugin: str | None, plugin_dir: str | None, plugins_root: str | None) -> Path | None:
    if plugin_dir:
        return Path(plugin_dir).expanduser().resolve()
    env_plugin = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_plugin and (not plugin or Path(env_plugin).name == plugin):
        return Path(env_plugin).expanduser().resolve()
    if plugin:
        root = Path(plugins_root).expanduser().resolve() if plugins_root else _default_plugins_root()
        return root / plugin
    return None

PKG_IDS = [
    "PKG-002", "PKG-003", "PKG-004", "PKG-005", "PKG-006", "PKG-007", "PKG-008",
    "PKG-014",
]

SKILL_FRONTMATTER_REQUIRED = {"name", "description", "kind"}
SKILL_FRONTMATTER_RECOMMENDED = {"responsibility_refs", "schema_refs", "manifest"}
PLUGIN_JSON_REQUIRED = {"name", "version", "description"}
PACKAGE_CONTRACT_REQUIRED = {"package_mode", "entry_points"}
SKILL_KINDS = {"run", "ref", "assign", "wrap", "delegate"}
LOOP_KINDS = {"run", "wrap", "delegate"}
KNOWN_COMBINATORS = {
    "with-run", "with-ref", "with-assign-generator", "with-assign-evaluator",
    "with-wrap", "with-delegate", "with-goal-seek", "with-feedback-contract",
    "with-evaluator", "with-hooks", "with-subagent", "with-knowledge",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    block = text[4:end]
    result: dict = {}
    current_key = None
    for line in block.splitlines():
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            result[key] = val
            current_key = key
        elif line.strip().startswith("- ") and current_key:
            if not isinstance(result[current_key], list):
                result[current_key] = []
            result[current_key].append(line.strip()[2:].strip())
    return result


def _unquote(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _as_list(value: object) -> list[str]:
    """Minimal YAML list normalizer (block list / inline flow list / scalar)."""
    if isinstance(value, list):
        raw = value
    else:
        text = _unquote(value)
        if text.startswith("[") and text.endswith("]"):
            raw = text[1:-1].split(",")
        else:
            raw = [text]
    return [item for item in (_unquote(v) for v in raw) if item and item != "[]"]


def _parse_completeness_exemptions(fm: dict) -> dict[str, str]:
    """Parse only reasoned ``<category>: <reason>`` exemptions.

    An empty category, an empty reason, or a decorative scalar does not exempt
    PKG-004. This matches lint-skill-completeness.py's fail-closed contract.
    """
    exemptions: dict[str, str] = {}
    for item in _as_list(fm.get("completeness_exempt")):
        match = re.match(r"^([a-z]+)\s*[:：]\s*(\S.*)$", item)
        if match:
            exemptions[match.group(1)] = match.group(2).strip()
    return exemptions


def _frontmatter_block(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    return None if end < 0 else text[4:end]


def _nested_mapping_block(frontmatter: str, key: str) -> str | None:
    """Return the indented YAML block below a top-level mapping key."""
    lines = frontmatter.splitlines()
    for idx, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:\s*(?:#.*)?$", line):
            nested: list[str] = []
            for candidate in lines[idx + 1:]:
                if candidate and not candidate[0].isspace():
                    break
                nested.append(candidate)
            return "\n".join(nested)
    return None


def _mapping_scalar(block: str | None, key: str) -> str:
    if block is None:
        return ""
    match = re.search(rf"^\s+{re.escape(key)}:\s*([^#\n]+)", block, re.MULTILINE)
    return _unquote(match.group(1)) if match else ""


def load_plugin_json(plugin_dir: Path) -> dict | None:
    pj = plugin_dir / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        return None
    try:
        return json.loads(pj.read_text())
    except json.JSONDecodeError:
        return None


def load_package_contract(plugin_dir: Path) -> dict | None:
    pc = plugin_dir / "references" / "package-contract.json"
    if not pc.exists():
        return None
    try:
        return json.loads(pc.read_text())
    except json.JSONDecodeError:
        return None


def get_package_mode(plugin_dir: Path) -> str:
    pc = load_package_contract(plugin_dir)
    if pc and "package_mode" in pc:
        return pc["package_mode"]
    pj = load_plugin_json(plugin_dir)
    if pj and "package_mode" in pj:
        return pj["package_mode"]
    return "skill-only"


def make_finding(pkg_id: str, idx: int, location: str, evidence: str,
                 severity: str = "P0", suggested_fix: str = "",
                 auto_fixable: bool = False) -> dict:
    num = pkg_id.split("-")[1]
    return {
        "id": f"F-PKG{num}-{idx:03d}",
        "pkg_id": pkg_id,
        "severity": severity,
        "location": location,
        "evidence": evidence,
        "suggested_fix": suggested_fix,
        "auto_fixable": auto_fixable,
    }


def check_pkg_002(plugin_dir: Path) -> list[dict]:
    findings: list[dict] = []
    pj = load_plugin_json(plugin_dir)
    if pj is None:
        findings.append(make_finding(
            "PKG-002", 1,
            f"{plugin_dir}/.claude-plugin/plugin.json",
            "plugin.json が存在しないか JSON 解析エラー",
            suggested_fix="plugin.json を新規作成し PLUGIN_JSON_REQUIRED キーを揃える"))
        return findings
    missing = PLUGIN_JSON_REQUIRED - pj.keys()
    for idx, key in enumerate(sorted(missing), 1):
        findings.append(make_finding(
            "PKG-002", idx,
            f"{plugin_dir}/.claude-plugin/plugin.json",
            f"必須キー欠落: {key}",
            suggested_fix=f"plugin.json に {key} を追加"))
    contract = load_package_contract(plugin_dir)
    start_idx = len(findings) + 1
    if contract is None:
        findings.append(make_finding(
            "PKG-002", start_idx,
            f"{plugin_dir}/references/package-contract.json",
            "package-contract.json が存在しないか JSON 解析エラー",
            suggested_fix="references/package-contract.json に package_mode と entry_points を追加"))
        return findings
    missing_contract = PACKAGE_CONTRACT_REQUIRED - contract.keys()
    for offset, key in enumerate(sorted(missing_contract), start_idx):
        findings.append(make_finding(
            "PKG-002", offset,
            f"{plugin_dir}/references/package-contract.json",
            f"package contract 必須キー欠落: {key}",
            suggested_fix=f"references/package-contract.json に {key} を追加"))
    scoped = contract.get("skill_dependencies")
    if scoped is not None:
        entry_points = contract.get("entry_points", {})
        declared_skills = set(
            entry_points.get("skills", []) if isinstance(entry_points, dict) else []
        )
        depends_on = contract.get("depends_on", [])
        allowed_dependencies = set(depends_on if isinstance(depends_on, list) else [])

        def scoped_finding(evidence: str) -> None:
            findings.append(make_finding(
                "PKG-002", len(findings) + 1,
                f"{plugin_dir}/references/package-contract.json#skill_dependencies",
                evidence,
                suggested_fix=(
                    "skill_dependencies を entry_points.skills のキーと "
                    "depends_on の部分集合だけで構成する"
                ),
            ))

        if not isinstance(scoped, dict):
            scoped_finding("skill_dependencies は object でなければならない")
        else:
            for skill, dependencies in scoped.items():
                if skill not in declared_skills:
                    scoped_finding(
                        f"skill_dependencies のキーが entry_points.skills 未宣言: {skill}"
                    )
                if not isinstance(dependencies, list) or not all(
                    isinstance(item, str) and item for item in dependencies
                ):
                    scoped_finding(
                        f"skill_dependencies.{skill} は plugin slug 配列でなければならない"
                    )
                    continue
                if len(dependencies) != len(set(dependencies)):
                    scoped_finding(f"skill_dependencies.{skill} に重複がある")
                undeclared = sorted(set(dependencies) - allowed_dependencies)
                if undeclared:
                    scoped_finding(
                        f"skill_dependencies.{skill} が depends_on 外を参照: {undeclared}"
                    )
    return findings


def check_pkg_003(plugin_dir: Path) -> list[dict]:
    findings: list[dict] = []
    target_name = plugin_dir.name
    plugins_root = plugin_dir.parent
    skill_names: dict[str, list[str]] = {}
    agent_names: dict[str, list[str]] = {}
    for plug in plugins_root.iterdir():
        if not plug.is_dir() or not (plug / ".claude-plugin").exists():
            continue
        # 名前空間の「所有」は実体 (非 symlink) のみ。symlink は他 plugin の単一スキルを
        # 共有配備したもの (例: run-skill-feedback を全 plugin へ配備) であり、同一スキルの
        # 参照に過ぎず真の名前衝突ではない。所有者カウントから除外する (PKG-003 偽陽性防止)。
        for sk in (plug / "skills").glob("*/SKILL.md") if (plug / "skills").exists() else []:
            if sk.parent.is_symlink():
                continue
            name = sk.parent.name
            skill_names.setdefault(name, []).append(plug.name)
        for ag in (plug / "agents").glob("*.md") if (plug / "agents").exists() else []:
            if ag.is_symlink():
                continue
            agent_names.setdefault(ag.stem, []).append(plug.name)
    idx = 1
    for name, owners in skill_names.items():
        if len(owners) > 1 and target_name in owners:
            findings.append(make_finding(
                "PKG-003", idx,
                f"plugins/{','.join(owners)}/skills/{name}",
                f"skill 名 {name} が複数 plugin で衝突: {owners}",
                suggested_fix="kebab-case 名を一意化、または domain prefix で名前空間分離"))
            idx += 1
    for name, owners in agent_names.items():
        if len(owners) > 1 and target_name in owners:
            findings.append(make_finding(
                "PKG-003", idx,
                f"plugins/{','.join(owners)}/agents/{name}.md",
                f"agent 名 {name} が複数 plugin で衝突: {owners}",
                suggested_fix="agent 名を一意化"))
            idx += 1
    return findings


def check_pkg_004(plugin_dir: Path) -> list[dict]:
    findings: list[dict] = []
    skills_dir = plugin_dir / "skills"
    if not skills_dir.exists():
        return findings
    idx = 1
    for sk_md in skills_dir.glob("*/SKILL.md"):
        # Symlinked compatibility skills are owned and validated by their
        # source plugin; they are not repackaged by the target plugin.
        if sk_md.parent.is_symlink():
            continue
        fm = parse_frontmatter(sk_md.read_text(encoding="utf-8"))
        if fm is None:
            findings.append(make_finding(
                "PKG-004", idx, str(sk_md),
                "frontmatter が解析できない（--- で囲まれていない）",
                suggested_fix="03章フォーマットで frontmatter を追加"))
            idx += 1
            continue
        for key in sorted(SKILL_FRONTMATTER_REQUIRED):
            if _unquote(fm.get(key)):
                continue
            findings.append(make_finding(
                "PKG-004", idx, str(sk_md),
                f"必須キー欠落: {key}（空値も欠落扱い）",
                suggested_fix=f"{key} を追加"))
            idx += 1
        exemptions = _parse_completeness_exemptions(fm)
        for key in sorted(SKILL_FRONTMATTER_RECOMMENDED):
            if key == "manifest" and exemptions.get("manifest"):
                continue
            values = _as_list(fm.get(key))
            if values:
                continue
            findings.append(make_finding(
                "PKG-004", idx, str(sk_md),
                f"推奨キー欠落または空値: {key}"
                + ("（理由付き completeness_exempt: manifest で代替可）" if key == "manifest" else ""),
                severity="P1",
                suggested_fix=(
                    "workflow-manifest.json の実体参照を追加、または理由付き manifest exemption を宣言"
                    if key == "manifest" else f"非空の {key} を追加"
                )))
            idx += 1
    return findings


def check_pkg_005(plugin_dir: Path) -> list[dict]:
    findings: list[dict] = []
    agents_dir = plugin_dir / "agents"
    skills_dir = plugin_dir / "skills"
    if not agents_dir.exists():
        return findings
    declared_agents: set[str] = set()
    for sk_md in skills_dir.glob("*/SKILL.md") if skills_dir.exists() else []:
        fm = parse_frontmatter(sk_md.read_text())
        if fm and "subagent_refs" in fm:
            refs = fm["subagent_refs"]
            if isinstance(refs, list):
                declared_agents.update(refs)
    actual_agents = {p.stem for p in agents_dir.glob("*.md")}
    idx = 1
    for missing in sorted(declared_agents - actual_agents):
        findings.append(make_finding(
            "PKG-005", idx,
            f"{plugin_dir}/agents/{missing}.md",
            f"SKILL.md で subagent_refs 宣言があるが agent ファイルが存在しない: {missing}",
            suggested_fix=f"agents/{missing}.md を作成、または SKILL.md の subagent_refs から削除"))
        idx += 1
    return findings


def check_pkg_006(plugin_dir: Path) -> list[dict]:
    findings: list[dict] = []
    hooks_dir = plugin_dir / "hooks"
    settings_dir = plugin_dir / "settings"
    if not hooks_dir.exists():
        return findings
    actual_hooks = {p for p in hooks_dir.glob("*") if p.is_file() and p.suffix in {".py", ".sh"}}
    registered: set[str] = set()

    def register_hook_name(value: str) -> None:
        """Extension の有無に関係なく hook entrypoint を同一視する。"""
        name = Path(value).name
        registered.add(name)
        registered.add(Path(name).stem)

    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        try:
            data = json.loads(plugin_json.read_text())
        except json.JSONDecodeError:
            data = {}
        hooks = data.get("hooks", {})
        if isinstance(hooks, dict):
            for event_hooks in hooks.values():
                for entry in event_hooks if isinstance(event_hooks, list) else []:
                    for h in entry.get("hooks", []) if isinstance(entry, dict) else []:
                        cmd = h.get("command") if isinstance(h, dict) else None
                        if cmd:
                            try:
                                tokens = shlex.split(cmd)
                            except ValueError:
                                tokens = cmd.split()
                            for token in tokens:
                                if "/hooks/" in token:
                                    register_hook_name(token)
        entry_points = data.get("entry_points", {})
        if isinstance(entry_points, dict):
            for hook_name in entry_points.get("hooks", []):
                if isinstance(hook_name, str):
                    register_hook_name(hook_name)

    # Harness-only entrypoint 台帳の正本は package-contract sidecar。
    # 公式 Claude plugin manifest に entry_points を混在させない。
    contract = load_package_contract(plugin_dir)
    if isinstance(contract, dict):
        entry_points = contract.get("entry_points", {})
        if isinstance(entry_points, dict):
            for hook_name in entry_points.get("hooks", []):
                if isinstance(hook_name, str):
                    register_hook_name(hook_name)
    if settings_dir.exists():
        for cfg in settings_dir.glob("*.json"):
            try:
                data = json.loads(cfg.read_text())
            except json.JSONDecodeError:
                continue
            hooks = data.get("hooks", {})
            if isinstance(hooks, dict):
                for event_hooks in hooks.values():
                    for h in event_hooks if isinstance(event_hooks, list) else []:
                        cmd = h.get("command") if isinstance(h, dict) else None
                        if cmd:
                            register_hook_name(cmd)
    idx = 1
    for hook in actual_hooks:
        if hook.name not in registered and hook.stem not in registered:
            findings.append(make_finding(
                "PKG-006", idx, str(hook),
                "hook ファイル実体は存在するが settings 断片の hooks 配列に未登録",
                suggested_fix=f"settings/*.json の hooks 配列に {hook.name} を追加"))
            idx += 1
    return findings


def check_pkg_007(plugin_dir: Path) -> list[dict]:
    findings: list[dict] = []
    scripts_dir = plugin_dir / "scripts"
    if not scripts_dir.exists():
        return findings
    idx = 1
    for sc in scripts_dir.glob("*"):
        if not sc.is_file():
            continue
        if sc.suffix not in {".py", ".sh"}:
            continue
        text_head = sc.read_text(errors="ignore")[:200] if sc.suffix in {".py", ".sh"} else ""
        if sc.suffix in {".py", ".sh"} and not text_head.startswith("#!"):
            findings.append(make_finding(
                "PKG-007", idx, str(sc),
                "shebang 欠落",
                suggested_fix="#!/usr/bin/env python3 または #!/usr/bin/env bash を先頭に追加"))
            idx += 1
        if text_head.startswith("#!") and not os.access(sc, os.X_OK):
            findings.append(make_finding(
                "PKG-007", idx, str(sc),
                "実行可能ビットなし (+x)",
                suggested_fix=f"chmod +x {sc}",
                auto_fixable=True))
            idx += 1
    return findings


def check_pkg_008(plugin_dir: Path) -> list[dict]:
    findings: list[dict] = []
    settings_dir = plugin_dir / "settings"
    if not settings_dir.exists():
        return findings
    idx = 1
    for cfg in settings_dir.glob("*.json"):
        try:
            data = json.loads(cfg.read_text())
        except json.JSONDecodeError as exc:
            findings.append(make_finding(
                "PKG-008", idx, str(cfg),
                f"JSON 解析エラー: {exc}",
                suggested_fix="JSON 構文を修正"))
            idx += 1
            continue
        if "$schema" not in data:
            findings.append(make_finding(
                "PKG-008", idx, str(cfg),
                "$schema フィールド欠落 (34a INV-2 違反)",
                severity="P1", suggested_fix="$schema を追加"))
            idx += 1
    return findings


def check_pkg_014(plugin_dir: Path) -> list[dict]:
    """Validate declared skill kind/combinators against runtime wiring.

    PKG-014 is intentionally not another presence check. It proves that each
    declared combinator has the configuration/body structure that implements
    its runtime behavior, and that kind-specific runtime claims do not drift.
    """
    findings: list[dict] = []
    skills_dir = plugin_dir / "skills"
    if not skills_dir.exists():
        return findings
    idx = 1

    def add(location: Path, evidence: str, suggested_fix: str) -> None:
        nonlocal idx
        findings.append(make_finding(
            "PKG-014", idx, str(location), evidence, severity="P1",
            suggested_fix=suggested_fix,
        ))
        idx += 1

    for sk_md in sorted(skills_dir.glob("*/SKILL.md")):
        if sk_md.parent.is_symlink():
            continue
        text = sk_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        frontmatter = _frontmatter_block(text)
        if fm is None or frontmatter is None:
            add(sk_md, "frontmatter を解析できず runtime contract を確定できない",
                "正規の SKILL.md frontmatter を追加")
            continue

        kind = _unquote(fm.get("kind"))
        if kind not in SKILL_KINDS:
            add(sk_md, f"未対応 kind または空値: {kind or '<empty>'}",
                f"kind を {sorted(SKILL_KINDS)} のいずれかに修正")
            continue
        combinators = set(_as_list(fm.get("combinators")))
        unknown = combinators - KNOWN_COMBINATORS
        for combinator in sorted(unknown):
            add(sk_md, f"未定義 combinator: {combinator}",
                "run-build-skill が定義する combinator 名へ修正")

        goal_block = _nested_mapping_block(frontmatter, "goal_seek")
        feedback_block = _nested_mapping_block(frontmatter, "feedback_contract")
        feedback_exempt = (
            feedback_block is not None
            and bool(_mapping_scalar(feedback_block, "skip_reason"))
        )
        if goal_block is not None and "with-goal-seek" not in combinators:
            add(sk_md, "goal_seek runtime 宣言があるが with-goal-seek combinator が未宣言",
                "combinators に with-goal-seek を追加")
        if (
            feedback_block is not None
            and not feedback_exempt
            and "with-feedback-contract" not in combinators
        ):
            add(sk_md, "feedback_contract runtime 宣言があるが with-feedback-contract combinator が未宣言",
                "combinators に with-feedback-contract を追加")

        if "with-goal-seek" in combinators:
            if kind not in LOOP_KINDS:
                add(sk_md, f"with-goal-seek は loop kind 専用だが kind={kind}",
                    f"kind を {sorted(LOOP_KINDS)} のいずれかにするか combinator を外す")
            if goal_block is None:
                add(sk_md, "with-goal-seek 宣言に対する goal_seek mapping がない",
                    "goal_seek.engine/max_loops/fork を追加")
            else:
                engine = _mapping_scalar(goal_block, "engine")
                fork = _mapping_scalar(goal_block, "fork")
                max_loops = _mapping_scalar(goal_block, "max_loops")
                if engine not in {"inline", "run-goal-seek", "task-graph"}:
                    add(sk_md, f"goal_seek.engine が未対応または空: {engine or '<empty>'}",
                        "engine を inline/run-goal-seek/task-graph のいずれかに修正")
                if fork not in {"inline", "subagent", "agent-team"}:
                    add(sk_md, f"goal_seek.fork が未対応または空: {fork or '<empty>'}",
                        "fork を inline/subagent/agent-team のいずれかに修正")
                if not max_loops.isdigit() or int(max_loops) < 1:
                    add(sk_md, f"goal_seek.max_loops が 1 以上の整数でない: {max_loops or '<empty>'}",
                        "max_loops を 1 以上の整数に修正")
            if not re.search(r"^##\s+ゴールシーク実行\s*$", text, re.MULTILINE):
                add(sk_md, "with-goal-seek 宣言に対する本文のゴールシーク実行配線がない",
                    "## ゴールシーク実行 に実行ループと停止条件を追加")

        if "with-feedback-contract" in combinators and not feedback_exempt:
            if feedback_block is None:
                add(sk_md, "with-feedback-contract 宣言に対する feedback_contract mapping がない",
                    "feedback_contract.max_iterations/criteria を追加")
            else:
                max_iterations = _mapping_scalar(feedback_block, "max_iterations")
                if not max_iterations.isdigit() or int(max_iterations) < 1:
                    add(sk_md, f"feedback_contract.max_iterations が 1 以上の整数でない: {max_iterations or '<empty>'}",
                        "max_iterations を 1 以上の整数に修正")
                for scope in ("inner", "outer"):
                    if not re.search(rf"^\s+loop_scope:\s*{scope}\s*(?:#.*)?$", feedback_block, re.MULTILINE):
                        add(sk_md, f"feedback_contract.criteria に loop_scope={scope} がない",
                            f"criteria に {scope} の受入基準を 1 件以上追加")

        if "with-knowledge" in combinators and not (sk_md.parent / "knowledge").is_dir():
            add(sk_md, "with-knowledge 宣言に対する knowledge/ 実体がない",
                "knowledge/ とその schema/index を同梱")
        if "with-hooks" in combinators and not (plugin_dir / "hooks").is_dir():
            add(sk_md, "with-hooks 宣言に対する plugin hooks/ 実体がない",
                "hooks/ 実体を追加するか combinator 宣言を外す")
    return findings


CHECK_FUNCTIONS = {
    "PKG-002": check_pkg_002,
    "PKG-003": check_pkg_003,
    "PKG-004": check_pkg_004,
    "PKG-005": check_pkg_005,
    "PKG-006": check_pkg_006,
    "PKG-007": check_pkg_007,
    "PKG-008": check_pkg_008,
    "PKG-014": check_pkg_014,
}

NA_FOR_SKILL_ONLY = {"PKG-003", "PKG-005", "PKG-006", "PKG-007", "PKG-008", "PKG-014"}


def run_checks(plugin_dir: Path, pkg_ids: list[str]) -> dict:
    package_mode = get_package_mode(plugin_dir)
    result_checks: dict[str, dict] = {}
    for pkg_id in pkg_ids:
        if package_mode == "skill-only" and pkg_id in NA_FOR_SKILL_ONLY:
            result_checks[pkg_id] = {
                "status": "not_applicable",
                "findings": [],
                "last_run_at": now_iso(),
                "skip_reason": f"package_mode=skill-only では {pkg_id} は適用対象外",
            }
            continue
        findings = CHECK_FUNCTIONS[pkg_id](plugin_dir)
        result_checks[pkg_id] = {
            "status": "fail" if findings else "pass",
            "findings": findings,
            "last_run_at": now_iso(),
        }
    counts = {"pass": 0, "fail": 0, "skip": 0, "not_applicable": 0}
    for v in result_checks.values():
        counts[v["status"]] += 1
    return {
        "run_id": f"pkg-validate-{plugin_dir.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')[:11].replace('-', '')[:8]}-001",
        "target_plugin": plugin_dir.name,
        "package_mode": package_mode,
        "pkg_checks": result_checks,
        "verdict": {"total": len(pkg_ids), **counts},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default="all",
                    help="pkg-002〜pkg-008 / pkg-014 のいずれか、または all")
    ap.add_argument("--plugin", help="plugin 名（互換: --plugins-root/<name> で解決）")
    ap.add_argument("--plugin-dir", help="検査対象 plugin ディレクトリ。marketplace 単独 install ではこちらを優先")
    ap.add_argument("--plugins-root", help="兄弟 plugin を含む root。未指定時は $CLAUDE_PLUGIN_ROOT の親または dev fallback")
    ap.add_argument("--output", default="-")
    args = ap.parse_args()

    plugin_dir = _resolve_plugin_dir(args.plugin, args.plugin_dir, args.plugins_root)
    if plugin_dir is None:
        print("error: --plugin-dir, --plugin, or CLAUDE_PLUGIN_ROOT is required", file=sys.stderr)
        return 2
    if not plugin_dir.exists():
        print(f"error: plugin not found: {plugin_dir}", file=sys.stderr)
        return 2

    if args.check == "all":
        pkg_ids = PKG_IDS
    else:
        pid = args.check.upper().replace("PKG-", "PKG-")
        if not pid.startswith("PKG-"):
            pid = "PKG-" + pid.split("-")[-1]
        if pid not in PKG_IDS:
            print(f"error: unsupported --check value: {args.check} (supported: {PKG_IDS})", file=sys.stderr)
            return 2
        pkg_ids = [pid]

    result = run_checks(plugin_dir, pkg_ids)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output)
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output)
    return 1 if result["verdict"]["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
