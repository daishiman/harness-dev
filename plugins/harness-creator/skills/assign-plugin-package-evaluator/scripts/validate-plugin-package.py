#!/usr/bin/env python3
"""PKG-002〜008 sub-check 実装。

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

PKG_IDS = ["PKG-002", "PKG-003", "PKG-004", "PKG-005", "PKG-006", "PKG-007", "PKG-008"]

SKILL_FRONTMATTER_REQUIRED = {"name", "description", "kind"}
SKILL_FRONTMATTER_RECOMMENDED = {"responsibility_refs", "schema_refs", "manifest"}
PLUGIN_JSON_REQUIRED = {"name", "version", "description"}
PACKAGE_CONTRACT_REQUIRED = {"package_mode", "entry_points"}


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
        fm = parse_frontmatter(sk_md.read_text())
        if fm is None:
            findings.append(make_finding(
                "PKG-004", idx, str(sk_md),
                "frontmatter が解析できない（--- で囲まれていない）",
                suggested_fix="03章フォーマットで frontmatter を追加"))
            idx += 1
            continue
        missing = SKILL_FRONTMATTER_REQUIRED - fm.keys()
        for key in sorted(missing):
            findings.append(make_finding(
                "PKG-004", idx, str(sk_md),
                f"必須キー欠落: {key}",
                suggested_fix=f"{key} を追加"))
            idx += 1
        missing_rec = SKILL_FRONTMATTER_RECOMMENDED - fm.keys()
        for key in sorted(missing_rec):
            findings.append(make_finding(
                "PKG-004", idx, str(sk_md),
                f"推奨キー欠落: {key}（plugin package mode で必須化進行中）",
                severity="P1", suggested_fix=f"{key} を追加"))
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
                                    registered.add(Path(token).name)
        entry_points = data.get("entry_points", {})
        if isinstance(entry_points, dict):
            for hook_name in entry_points.get("hooks", []):
                if isinstance(hook_name, str):
                    registered.add(Path(hook_name).name)
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
                            registered.add(Path(cmd).name)
    idx = 1
    for hook in actual_hooks:
        if hook.name not in registered:
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


CHECK_FUNCTIONS = {
    "PKG-002": check_pkg_002,
    "PKG-003": check_pkg_003,
    "PKG-004": check_pkg_004,
    "PKG-005": check_pkg_005,
    "PKG-006": check_pkg_006,
    "PKG-007": check_pkg_007,
    "PKG-008": check_pkg_008,
}

NA_FOR_SKILL_ONLY = {"PKG-003", "PKG-005", "PKG-006", "PKG-007", "PKG-008"}


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
                    help="pkg-002〜pkg-008 のいずれか、または all")
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
