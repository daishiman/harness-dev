#!/usr/bin/env python3
# /// script
# name: check-native-surface-parity
# purpose: C02 read-only parity validator。native-surface-contract.md の canonical JSON block を正本とし、Claude/Codex surface 分類 (confirmed/unsupported/deferred)、dual manifest parity、repo marketplace parity、plugin hook trust 前提、artifact digest freshness/consistency を repo 実測と決定論突合する。いかなるファイルも書かない。
# inputs:
#   - argv: --repo-root PATH --plugin-slug SLUG --surface-contract PATH --plan-dir PATH [--json]
# outputs:
#   - stdout: 人間可読サマリ (既定) / JSON (--json)。surface 分類、manifest/marketplace parity、trust precondition、artifact digests、consistency、violations、verdict、exit_code。
#   - exit: 0=parity PASS / 1=drift・unsupported silent projection・stale evidence / 2=conflict / 3=invalid contract or layout
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""C02 native surface parity validator (read-only)。

`native-surface-contract.md` 内の唯一の fenced ```json block を canonical contract とし、
repo 実測 (dual plugin manifest / repo marketplace / forbidden codex surface / unsupported
kind の誤 projection) と artifact digest freshness を突合する。契約は正本であり、validator は
trust 状態や surface を一切変更しない (write-scope: none)。

exit code は重い順に評価する: 3 (invalid contract / invalid layout) > 2 (conflict) >
1 (drift / unsupported silent projection / stale evidence) > 0 (全 PASS)。複数該当時は最も
重い code を返す。

plugin-root script のため cross-plugin import は行わず、Python 標準ライブラリのみで自己完結する。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

# ── severity 定数 (= exit code の重み) ─────────────────────────────
SEV_INVALID = 3   # invalid contract / invalid layout
SEV_CONFLICT = 2  # 相互矛盾
SEV_DRIFT = 1     # drift / unsupported silent projection / stale evidence

# ── contract 構造規約 ─────────────────────────────────────────────
REQUIRED_CONTRACT_KEYS = (
    "schema_version",
    "checked_at",
    "codex_cli_version",
    "sources",
    "activation_semantics",
    "confirmed_kinds",
    "unsupported_kinds",
    "surfaces",
    "forbidden_codex_surfaces",
    "state_ownership",
    "failure_taxonomy",
    "digest_inputs",
)
SURFACE_REQUIRED_KEYS = (
    "key",
    "classification",
    "claude",
    "codex",
    "owner",
    "write_policy",
    "verification",
)
VALID_CLASSIFICATIONS = frozenset({"confirmed", "unsupported", "deferred"})
EXPECTED_ACTIVATION_SEMANTICS = {
    "claude_projection_selection": "repo_present_exact_project_identity_enabled",
    "codex_plugin_activation": "install_enable_then_user_hook_trust",
    "codex_trust_mutation": "forbidden_user_gated",
}
MARKETPLACE_INSTALLATION_VALUES = frozenset(
    {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
)
MARKETPLACE_AUTHENTICATION_VALUES = frozenset({"ON_INSTALL", "ON_USE"})
_PLUGIN_ROOT_REF_RE = re.compile(
    r"\$(?:\{(?:CLAUDE_)?PLUGIN_ROOT\}|(?:CLAUDE_)?PLUGIN_ROOT)(?P<path>/[^\s\"']+)"
)
_FORBIDDEN_TOML_MARKER_RE = re.compile(
    r"(?im)^\s*#.*(?:begin|end).*managed.*hooks?\b"
)
_FORBIDDEN_TOML_SCHEMA_RE = re.compile(
    r"(?im)^\s*\[\[?\s*hooks?(?:\.|\s*\]|\s*\]\])"
)

# consistency 検査に用いる digest input のファイル名。
HANDOFF_FILE = "handoff-run-plugin-dev-plan.json"
INVENTORY_FILE = "component-inventory.json"
TASK_GRAPH_FILE = "task-graph.json"
FINDINGS_FILE = "plan-findings.json"


# ─────────────────── contract parse & validate ───────────────────
def extract_json_blocks(text: str) -> list[str]:
    """markdown から fenced ```json block の本文だけを順に取り出す (json タグのみ数える)。"""
    blocks: list[str] = []
    buf: list[str] = []
    in_block = False
    for line in text.splitlines():
        s = line.strip()
        if not in_block:
            if s == "```json":
                in_block = True
                buf = []
            continue
        if s == "```":
            blocks.append("\n".join(buf))
            in_block = False
        else:
            buf.append(line)
    return blocks


def validate_contract_structure(data: dict) -> str | None:
    """canonical contract の必須キー・surfaces[] 構造を検査する。不正なら error 文を返す。"""
    missing = [k for k in REQUIRED_CONTRACT_KEYS if k not in data]
    if missing:
        return f"contract 必須キー欠落: {', '.join(missing)}"
    try:
        date.fromisoformat(data.get("checked_at"))
    except (TypeError, ValueError):
        return "checked_at は ISO date (YYYY-MM-DD) が必須"
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources or not all(
        isinstance(source, str) and source.startswith("https://") for source in sources
    ):
        return "sources は https URL の非空 list が必須"
    activation = data.get("activation_semantics")
    if activation != EXPECTED_ACTIVATION_SEMANTICS:
        return (
            "activation_semantics は Claude projection selection と Codex user trust gate を"
            "分離した canonical object が必須"
        )
    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        return "surfaces[] が list でない、または空"
    for i, s in enumerate(surfaces):
        if not isinstance(s, dict):
            return f"surfaces[{i}] が object でない"
        smiss = [k for k in SURFACE_REQUIRED_KEYS if k not in s]
        if smiss:
            return f"surfaces[{i}] のキー欠落: {', '.join(smiss)}"
        if s.get("classification") not in VALID_CLASSIFICATIONS:
            return f"surfaces[{i}] classification 不正: {s.get('classification')!r}"
        # plugin_hook は install/enable/trust 前提を必ず宣言する。
        if s.get("key") == "plugin_hook" and s.get("trust_required") is not True:
            return f"surfaces[{i}] (plugin_hook) は trust_required:true が必須"
    if not isinstance(data.get("forbidden_codex_surfaces"), list):
        return "forbidden_codex_surfaces が list でない"
    if not isinstance(data.get("state_ownership"), list) or not data.get("state_ownership"):
        return "state_ownership が list でない、または空"
    taxonomy = data.get("failure_taxonomy")
    if not isinstance(taxonomy, dict) or taxonomy.get("skipped_not_installed") != "generator-absent-only":
        return "failure_taxonomy.skipped_not_installed は generator-absent-only が必須"
    if not isinstance(data.get("digest_inputs"), list) or not data.get("digest_inputs"):
        return "digest_inputs が list でない、または空"
    return None


def parse_contract(text: str) -> tuple[dict | None, str | None]:
    """contract markdown を parse する。成功で (contract, None)、不正で (None, error)。"""
    blocks = extract_json_blocks(text)
    if len(blocks) == 0:
        return None, "canonical JSON block が見つからない (fenced ```json が 0 個)"
    if len(blocks) > 1:
        return None, f"canonical JSON block が複数 ({len(blocks)} 個・ちょうど1個必要)"
    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        return None, f"canonical JSON block が parse 不能: {exc}"
    if not isinstance(data, dict):
        return None, "canonical JSON block が object でない"
    err = validate_contract_structure(data)
    if err:
        return None, err
    return data, None


# ─────────────────── helpers ───────────────────
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_distinct_entity_refs(task_graph: object) -> int:
    """task-graph の nodes[] から非 null な distinct entity_ref の件数を数える。"""
    if not isinstance(task_graph, dict):
        return 0
    nodes = task_graph.get("nodes")
    if not isinstance(nodes, list):
        return 0
    refs: set = set()
    for n in nodes:
        if not isinstance(n, dict):
            continue
        er = n.get("entity_ref")
        if er is None:
            continue
        if isinstance(er, (dict, list)):
            refs.add(json.dumps(er, sort_keys=True, ensure_ascii=False))
        else:
            refs.add(er)
    return len(refs)


def _iter_strings(obj: object):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_strings(v)


def _load_manifest(path: Path) -> tuple[bool, dict | None, bool]:
    """(exists, data, json_ok) を返す。存在しなければ (False, None, True)。"""
    if not path.is_file():
        return (False, None, True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return (True, None, False)
    if not isinstance(data, dict):
        return (True, None, False)
    return (True, data, True)


def _marketplace_local_path(entry: object) -> str | None:
    """Official marketplace entry から local source path を取り出す。"""
    if not isinstance(entry, dict):
        return None
    source = entry.get("source")
    if isinstance(source, dict) and source.get("source") == "local":
        path = source.get("path")
        return path if isinstance(path, str) else None
    return None


def _path_within(root: Path, relative: str) -> Path | None:
    """./ 始まりの plugin-root 相対 path を安全に解決する。"""
    if not relative.startswith("./"):
        return None
    target = (root / relative[2:]).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target


def _plugin_root_command_paths(command: str, plugin_root: Path) -> tuple[list[Path], bool]:
    """command 内の plugin-root 参照を解決し、全参照が root 内かを返す。"""
    paths: list[Path] = []
    confined = True
    for match in _PLUGIN_ROOT_REF_RE.finditer(command):
        relative = "." + match.group("path")
        resolved = _path_within(plugin_root, relative)
        if resolved is None:
            confined = False
        else:
            paths.append(resolved)
    return paths, confined


def _v(severity: int, code: str, detail: str) -> dict:
    return {"severity": severity, "code": code, "detail": detail}


def _invalid_contract_report(detail: str) -> dict:
    """contract を信頼できないため他検査を打ち切り、最小 report を返す (exit 3)。"""
    return {
        "contract": None,
        "surfaces": [],
        "manifest_parity": {},
        "marketplace_parity": {},
        "hook_parity": {},
        "trust": {},
        "digests": {},
        "freshness": {},
        "consistency": {},
        "violations": [_v(SEV_INVALID, "invalid_contract", detail)],
        "verdict": "FAIL",
        "exit_code": SEV_INVALID,
    }


def _flatten_hooks(document: dict) -> list[tuple[str, str, str]]:
    hooks = document.get("hooks") if isinstance(document, dict) else None
    if not isinstance(hooks, dict):
        return []
    return [
        (
            event,
            group.get("matcher") or "",
            re.sub(r"\s+# harness-managed:[A-Za-z0-9._-]+:[A-Za-z0-9._-]+\s*$", "", handler.get("command") or ""),
        )
        for event, groups in hooks.items() if isinstance(groups, list)
        for group in groups if isinstance(group, dict)
        for handler in group.get("hooks", []) if isinstance(handler, dict)
    ]


def _validate_common_settings(repo_root: Path, slug: str, violations: list[dict]) -> dict:
    result = {"path": f"plugins/{slug}/native-surfaces.toml", "status": "invalid"}
    path = repo_root / "plugins" / slug / "native-surfaces.toml"
    if not path.is_file():
        violations.append(_v(SEV_INVALID, "native_surfaces_toml_missing", f"common SSOT 欠落: {path}"))
        return result
    try:
        common = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        violations.append(_v(SEV_INVALID, "native_surfaces_toml_invalid", str(exc)))
        return result
    hooks = common.get("hooks", [])
    activation = common.get("activation")
    discovery = common.get("discovery")
    if (
        common.get("schema_version") != 1
        or not isinstance(hooks, list)
        or not isinstance(activation, dict)
        or not isinstance(discovery, dict)
    ):
        violations.append(_v(SEV_INVALID, "native_surfaces_schema_invalid", "schema_version=1/[activation]/[discovery]/hooks[] 必須"))
        return result
    if activation.get("codex_discovery") != ".agents/plugins/marketplace.json":
        violations.append(_v(SEV_INVALID, "native_discovery_path_invalid", "Codex discovery path は .agents/plugins/marketplace.json 固定"))
    claude_marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    try:
        claude_marketplace = json.loads(claude_marketplace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        violations.append(_v(SEV_INVALID, "claude_marketplace_invalid", str(exc)))
    else:
        actual_marketplace = claude_marketplace.get("name") if isinstance(claude_marketplace, dict) else None
        if activation.get("claude_marketplace") != actual_marketplace:
            violations.append(_v(
                SEV_DRIFT,
                "claude_marketplace_semantic_drift",
                "native-surfaces.toml activation.claude_marketplace と root marketplace name が不一致",
            ))
    discovery_required = {
        "marketplace_name", "plugin_name", "source_path", "installation", "authentication",
        "category", "distributable", "scope", "activation_requires",
    }
    if not discovery_required.issubset(discovery) or discovery.get("plugin_name") != slug:
        violations.append(_v(SEV_INVALID, "native_discovery_schema_invalid", "common discovery entry の必須field/slugが不正"))
    ids = [hook.get("id") for hook in hooks if isinstance(hook, dict)]
    if len(ids) != len(set(ids)) or any(
        hook.get("delivery") not in {"plugin", "project"} for hook in hooks if isinstance(hook, dict)
    ):
        violations.append(_v(SEV_CONFLICT, "hook_delivery_owner_conflict", "hook id/delivery owner が一意でない"))

    config_path = repo_root / ".codex" / "config.toml"
    project_path = repo_root / ".codex" / "hooks.json"
    claude_path = repo_root / "plugins" / slug / ".claude-plugin" / "plugin.json"
    plugin_path = repo_root / "plugins" / slug / "hooks" / "hooks.json"
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        project = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        violations.append(_v(SEV_INVALID, "native_project_settings_invalid", str(exc)))
        return result
    discovery_path = repo_root / ".agents" / "plugins" / "marketplace.json"
    try:
        discovery_doc = json.loads(discovery_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        discovery_doc = {}
        violations.append(_v(SEV_DRIFT, "native_discovery_missing", ".agents marketplace は C01 --apply で再生成が必要"))
    except (OSError, json.JSONDecodeError) as exc:
        violations.append(_v(SEV_INVALID, "native_discovery_invalid", str(exc)))
        return result
    expected_entry = {
        "name": discovery.get("plugin_name"),
        "source": {"source": "local", "path": discovery.get("source_path")},
        "policy": {
            "installation": discovery.get("installation"),
            "authentication": discovery.get("authentication"),
        },
        "category": discovery.get("category"),
        "x_harness": {
            "distributable": discovery.get("distributable"),
            "scope": discovery.get("scope"),
            "activation_requires": discovery.get("activation_requires"),
        },
    }
    managed_entries = [
        entry for entry in discovery_doc.get("plugins", [])
        if isinstance(entry, dict) and entry.get("name") == slug
    ] if isinstance(discovery_doc, dict) and isinstance(discovery_doc.get("plugins"), list) else []
    if discovery_doc.get("name") != discovery.get("marketplace_name") or managed_entries != [expected_entry]:
        violations.append(_v(SEV_DRIFT, "native_discovery_semantic_drift", "common TOML と .agents marketplace managed entry が不一致"))
    try:
        claude = json.loads(claude_path.read_text(encoding="utf-8")) if claude_path.is_file() else {}
        plugin = json.loads(plugin_path.read_text(encoding="utf-8")) if plugin_path.is_file() else {}
    except (OSError, json.JSONDecodeError) as exc:
        violations.append(_v(SEV_INVALID, "native_plugin_settings_invalid", str(exc)))
        return result
    if config.get("features", {}).get("hooks") is not True:
        violations.append(_v(SEV_DRIFT, "codex_hooks_feature_disabled", ".codex/config.toml features.hooks=true 必須"))
    if isinstance(config.get("hooks"), dict):
        violations.append(_v(SEV_CONFLICT, "codex_same_layer_hook_duplicate", "hooks.json と inline [hooks] の併用禁止"))
    project_keys, claude_keys, plugin_keys = map(_flatten_hooks, (project, claude, plugin))
    for hook in hooks:
        if not isinstance(hook, dict):
            continue
        key = (hook.get("event"), hook.get("matcher") or "", hook.get("command"))
        delivery = hook.get("delivery")
        expected_project = 1 if delivery == "project" else 0
        expected_plugin = 1 if delivery == "plugin" else 0
        project_count = project_keys.count(key)
        plugin_count = plugin_keys.count(key)
        if project_count > expected_project or plugin_count > expected_plugin:
            violations.append(_v(SEV_CONFLICT, "hook_delivery_duplicate_or_missing", f"{hook.get('id')}: delivery={delivery}"))
        elif project_count < expected_project or plugin_count < expected_plugin:
            violations.append(_v(SEV_DRIFT, "hook_delivery_duplicate_or_missing", f"{hook.get('id')}: delivery={delivery}"))
        if "claude" in hook.get("products", []) and claude_keys.count(key) != 1:
            violations.append(_v(SEV_DRIFT, "claude_common_hook_drift", str(hook.get("id"))))
    result.update(status="confirmed", hooks=len(hooks), inline_hooks=False)
    return result


# ─────────────────── main evaluation ───────────────────
def evaluate(repo_root: Path, slug: str, contract_path: Path, plan_dir: Path) -> tuple[dict, int]:
    """contract を正本に repo 実測を read-only 突合し、(report, exit_code) を返す。"""
    # (0) contract parse — 不正なら他検査を行わず exit 3。
    if not contract_path.is_file():
        return _invalid_contract_report(f"surface-contract not found: {contract_path}"), SEV_INVALID
    contract, err = parse_contract(contract_path.read_text(encoding="utf-8"))
    if err is not None:
        return _invalid_contract_report(err), SEV_INVALID

    violations: list[dict] = []
    report: dict = {
        "contract": {
            "schema_version": contract.get("schema_version"),
            "checked_at": contract.get("checked_at"),
            "codex_cli_version": contract.get("codex_cli_version"),
            "activation_semantics": contract.get("activation_semantics"),
        },
        "surfaces": [],
        "manifest_parity": {},
        "marketplace_parity": {},
        "hook_parity": {},
        "settings_parity": {},
        "trust": {},
        "digests": {},
        "freshness": {},
        "consistency": {},
        "violations": [],
        "verdict": "",
        "exit_code": 0,
    }

    report["settings_parity"] = _validate_common_settings(repo_root, slug, violations)

    # (3) forbidden codex surface — 存在したら invalid layout (exit 3)。
    for entry in contract["forbidden_codex_surfaces"]:
        if not isinstance(entry, str):
            continue
        if entry == "guessed-toml-hook-merge":
            config_path = repo_root / ".codex" / "config.toml"
            if config_path.is_file():
                try:
                    config_text = config_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    violations.append(
                        _v(SEV_INVALID, "codex_toml_invalid_encoding", ".codex/config.toml が UTF-8 でない")
                    )
                else:
                    marker = _FORBIDDEN_TOML_MARKER_RE.search(config_text)
                    schema = _FORBIDDEN_TOML_SCHEMA_RE.search(config_text)
                    if marker or schema:
                        kind = "managed marker" if marker else "unconfirmed hooks table schema"
                        violations.append(
                            _v(
                                SEV_INVALID,
                                "forbidden_guessed_toml_hook_merge",
                                f".codex/config.toml に推測 hook merge {kind} を検出",
                            )
                        )
            continue
        # ".agents/agents" 等のファイルシステム経路を検査。その他の
        # sentinel は検出器が実装されるまで path として扱わない。
        if "/" not in entry and not entry.startswith("."):
            continue
        if (repo_root / entry).exists():
            violations.append(
                _v(SEV_INVALID, "forbidden_surface_present", f"forbidden codex surface が存在: {entry}")
            )

    # (2/6) surface parity + unsupported 誤 projection + plugin hook trust precondition。
    trust_info = {
        "claude_projection_selection": contract["activation_semantics"]["claude_projection_selection"],
        "codex_trust_required": False,
        "codex_runtime_evidence": "not_applicable",
        "codex_trust_mutation": contract["activation_semantics"]["codex_trust_mutation"],
    }
    for s in contract["surfaces"]:
        entry: dict = {
            "key": s["key"],
            "classification": s["classification"],
            "owner": s.get("owner"),
            "write_policy": s.get("write_policy"),
            "verification": s.get("verification"),
        }
        if "trust_required" in s:
            entry["trust_required"] = bool(s.get("trust_required"))

        if s["classification"] == "unsupported":
            # unsupported kind は必ず report へ明示 (silent PASS 禁止)。加えて Claude 面の
            # projection (.claude/x) が Codex 面 (.agents/x) へ写像されている痕跡を検出する。
            claude = s.get("claude")
            projected = None
            detected = False
            if isinstance(claude, str) and claude.startswith(".claude/"):
                projected = ".agents/" + claude[len(".claude/"):]
                if (repo_root / projected).exists():
                    detected = True
            entry["projection_path"] = projected
            entry["projection_detected"] = detected
            if detected:
                violations.append(
                    _v(
                        SEV_DRIFT,
                        "unsupported_projection",
                        f"unsupported kind {s['key']} が Codex 側へ誤 projection: {projected}",
                    )
                )

        if s["key"] == "plugin_hook" and s.get("trust_required") is True:
            trust_info["codex_trust_required"] = True
            trust_info["codex_runtime_evidence"] = "pending_user_gate"
        report["surfaces"].append(entry)
    report["trust"] = trust_info

    # (4) dual manifest parity。
    claude_m = repo_root / "plugins" / slug / ".claude-plugin" / "plugin.json"
    codex_m = repo_root / "plugins" / slug / ".codex-plugin" / "plugin.json"
    plugin_root = repo_root / "plugins" / slug
    c_exists, c_data, c_ok = _load_manifest(claude_m)
    x_exists, x_data, x_ok = _load_manifest(codex_m)
    mp: dict = {
        "claude_manifest": f"plugins/{slug}/.claude-plugin/plugin.json",
        "codex_manifest": f"plugins/{slug}/.codex-plugin/plugin.json",
        "claude_exists": c_exists,
        "codex_exists": x_exists,
        "claude_name": c_data.get("name") if isinstance(c_data, dict) else None,
        "codex_name": x_data.get("name") if isinstance(x_data, dict) else None,
    }
    if not c_exists or not x_exists:
        miss = []
        if not c_exists:
            miss.append(".claude-plugin/plugin.json")
        if not x_exists:
            miss.append(".codex-plugin/plugin.json")
        mp["status"] = "drift"
        violations.append(_v(SEV_DRIFT, "manifest_missing", f"dual manifest 欠落: {', '.join(miss)}"))
    elif not c_ok or not x_ok:
        mp["status"] = "invalid"
        violations.append(_v(SEV_INVALID, "manifest_invalid_json", "plugin manifest が invalid JSON/object"))
    else:
        cn = c_data.get("name")
        xn = x_data.get("name")
        mp["status"] = "confirmed"
        if cn != xn:
            mp["status"] = "conflict"
            violations.append(
                _v(SEV_CONFLICT, "manifest_name_conflict", f"manifest name 矛盾: claude={cn!r} codex={xn!r}")
            )
        elif cn != slug:
            mp["status"] = "drift"
            violations.append(
                _v(SEV_DRIFT, "manifest_folder_name_drift", f"manifest name={cn!r} が folder slug={slug!r} と不一致")
            )
        shared_required = ("name", "version", "description", "author")
        shared_missing = [
            field for field in shared_required
            if c_data.get(field) in (None, "", {}) or x_data.get(field) in (None, "", {})
        ]
        shared_drift = [
            field for field in shared_required
            if field not in shared_missing and c_data.get(field) != x_data.get(field)
        ]
        mp["shared_fields"] = list(shared_required)
        if shared_missing:
            mp["status"] = "invalid"
            mp["shared_field_missing"] = shared_missing
            violations.append(
                _v(
                    SEV_INVALID,
                    "manifest_metadata_missing",
                    f"dual manifest shared metadata 欠落: {', '.join(shared_missing)}",
                )
            )
        if shared_drift:
            if mp["status"] not in ("invalid", "conflict"):
                mp["status"] = "drift"
            mp["shared_field_drift"] = shared_drift
            violations.append(
                _v(
                    SEV_DRIFT,
                    "manifest_metadata_drift",
                    f"dual manifest metadata 不一致: {', '.join(shared_drift)}",
                )
            )

        # Codex native skill surface は plugin root の ./skills/ に固定。存在と
        # path confinement の両方を確認し、単な文字列一致で escape を見逃さない。
        skills_declared = x_data.get("skills")
        mp["codex_skills"] = skills_declared
        expected_skills = (plugin_root / "skills").resolve()
        skills_resolved = (
            _path_within(plugin_root, skills_declared)
            if isinstance(skills_declared, str) else None
        )
        if skills_resolved != expected_skills or not expected_skills.is_dir():
            mp["status"] = "invalid"
            violations.append(
                _v(
                    SEV_INVALID,
                    "manifest_skills_path_invalid",
                    f"Codex manifest skills は実在する ./skills/ 必須: {skills_declared!r}",
                )
            )
    report["manifest_parity"] = mp

    # (4b) plugin hook bundle parity。plan の native SSOT は plugin root/hooks/hooks.json。
    hook_path = repo_root / "plugins" / slug / "hooks" / "hooks.json"
    hp: dict = {
        "path": f"plugins/{slug}/hooks/hooks.json",
        "exists": hook_path.is_file(),
        "session_start": False,
        "entrypoint": "auto-sync-on-session-start.py",
        "status": "",
    }
    if not hook_path.is_file():
        hp["status"] = "drift"
        violations.append(_v(SEV_DRIFT, "plugin_hooks_missing", "plugin hooks/hooks.json 欠落"))
    else:
        try:
            hook_data = json.loads(hook_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            hp["status"] = "invalid"
            violations.append(_v(SEV_INVALID, "plugin_hooks_invalid_json", "hooks/hooks.json が invalid JSON"))
        else:
            hooks = hook_data.get("hooks") if isinstance(hook_data, dict) else None
            session_entries = hooks.get("SessionStart") if isinstance(hooks, dict) else None
            hp["session_start"] = isinstance(session_entries, list) and bool(session_entries)
            hook_schema_errors: list[str] = []
            commands: list[str] = []
            entrypoint_found = False
            paths_confined = True
            expected_entrypoint = (plugin_root / "hooks" / "auto-sync-on-session-start.py").resolve()
            if not isinstance(hook_data, dict) or not isinstance(hooks, dict):
                hook_schema_errors.append("root hooks object が必須")
            if not hp["session_start"]:
                hook_schema_errors.append("SessionStart の非空配列が必須")
            else:
                for i, group in enumerate(session_entries):
                    if not isinstance(group, dict):
                        hook_schema_errors.append(f"SessionStart[{i}] が object でない")
                        continue
                    matcher = group.get("matcher")
                    if matcher is not None and not isinstance(matcher, str):
                        hook_schema_errors.append(f"SessionStart[{i}].matcher が string でない")
                    nested = group.get("hooks")
                    if not isinstance(nested, list) or not nested:
                        hook_schema_errors.append(f"SessionStart[{i}].hooks が非空配列でない")
                        continue
                    for j, hook in enumerate(nested):
                        if not isinstance(hook, dict):
                            hook_schema_errors.append(f"SessionStart[{i}].hooks[{j}] が object でない")
                            continue
                        if hook.get("type") != "command":
                            hook_schema_errors.append(
                                f"SessionStart[{i}].hooks[{j}].type は command 必須"
                            )
                        command = hook.get("command")
                        if not isinstance(command, str) or not command.strip():
                            hook_schema_errors.append(
                                f"SessionStart[{i}].hooks[{j}].command が非空文字列でない"
                            )
                            continue
                        commands.append(command)
                        command_paths, confined = _plugin_root_command_paths(command, plugin_root)
                        if not confined or not command_paths:
                            paths_confined = False
                            hook_schema_errors.append(
                                f"SessionStart[{i}].hooks[{j}].command が plugin root 内 path でない"
                            )
                        if expected_entrypoint in command_paths:
                            entrypoint_found = True
                        timeout = hook.get("timeout")
                        if timeout is not None and (
                            isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0
                        ):
                            hook_schema_errors.append(
                                f"SessionStart[{i}].hooks[{j}].timeout は正数必須"
                            )
            hp["entrypoint_found"] = entrypoint_found
            hp["command_paths_confined"] = paths_confined
            hp["schema_errors"] = hook_schema_errors
            if hook_schema_errors:
                hp["status"] = "invalid"
                violations.append(
                    _v(
                        SEV_INVALID,
                        "plugin_hooks_schema_invalid",
                        "hooks/hooks.json schema/path 不正: " + "; ".join(hook_schema_errors),
                    )
                )
            elif not entrypoint_found:
                hp["status"] = "drift"
                violations.append(
                    _v(
                        SEV_DRIFT,
                        "plugin_hooks_wiring_drift",
                        "hooks/hooks.json に SessionStart auto-sync-on-session-start.py 配線がない",
                    )
                )
            else:
                hp["status"] = "confirmed"

    # Manifest hooks 指定は plugin root 内の official SSOT だけを許可。
    # 省略は product default `./hooks/hooks.json` として同じ実体を検査する。
    if isinstance(x_data, dict):
        declared = x_data.get("hooks", "./hooks/hooks.json")
        hp["manifest_declared"] = declared
        hp["manifest_resolution"] = "explicit" if "hooks" in x_data else "product_default"
        if isinstance(declared, str):
            resolved = _path_within(plugin_root, declared)
            if resolved is None or resolved != hook_path.resolve():
                hp["status"] = "invalid"
                violations.append(
                    _v(SEV_INVALID, "plugin_hooks_path_invalid", f"manifest hooks path が SSOT 外: {declared!r}")
                )
        else:
            hp["status"] = "invalid"
            violations.append(_v(SEV_INVALID, "plugin_hooks_manifest_invalid", "manifest hooks 型が不正"))
    report["hook_parity"] = hp

    # (5) repo marketplace parity。
    mk_path = repo_root / ".agents" / "plugins" / "marketplace.json"
    mk: dict = {"path": ".agents/plugins/marketplace.json", "exists": mk_path.is_file(), "referenced": False, "status": ""}
    if not mk_path.is_file():
        mk["status"] = "drift"
        violations.append(_v(SEV_DRIFT, "marketplace_missing", "repo marketplace.json 欠落"))
    else:
        try:
            mk_data = json.loads(mk_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            mk["status"] = "invalid"
            violations.append(_v(SEV_INVALID, "marketplace_invalid_json", "marketplace.json が invalid JSON"))
        else:
            expected = f"./plugins/{slug}"
            plugins = mk_data.get("plugins") if isinstance(mk_data, dict) else None
            matching = [
                entry for entry in plugins
                if isinstance(entry, dict) and entry.get("name") == slug
            ] if isinstance(plugins, list) else []
            paths = [_marketplace_local_path(entry) for entry in matching]
            referenced = expected in paths
            mk["expected_source_path"] = expected
            mk["matching_entries"] = len(matching)
            mk["source_paths"] = paths
            mk["referenced"] = referenced
            if not isinstance(plugins, list):
                mk["status"] = "invalid"
                violations.append(_v(SEV_INVALID, "marketplace_layout_invalid", "marketplace plugins[] が不正"))
            elif len(matching) > 1:
                mk["status"] = "conflict"
                violations.append(_v(SEV_CONFLICT, "marketplace_duplicate_plugin", f"marketplace に {slug} が複数定義"))
            elif not matching:
                mk["status"] = "drift"
                violations.append(
                    _v(SEV_DRIFT, "marketplace_unreferenced", f"marketplace が {slug} plugin root {expected} を参照していない")
                )
            else:
                named = matching[0]
                source = named.get("source")
                source_path = source.get("path") if isinstance(source, dict) else None
                source_kind = source.get("source") if isinstance(source, dict) else None
                resolved_source = (
                    _path_within(repo_root, source_path)
                    if isinstance(source_path, str) else None
                )
                expected_root = (repo_root / "plugins" / slug).resolve()
                policy = named.get("policy")
                installation = policy.get("installation") if isinstance(policy, dict) else None
                authentication = policy.get("authentication") if isinstance(policy, dict) else None
                category = named.get("category")
                mk.update(
                    source_kind=source_kind,
                    source_path=source_path,
                    installation=installation,
                    authentication=authentication,
                    category=category,
                )
                invalid_fields: list[str] = []
                if source_kind != "local" or not isinstance(source_path, str) or resolved_source is None:
                    invalid_fields.append("source={source:'local', path:'./plugins/<slug>'}")
                if installation not in MARKETPLACE_INSTALLATION_VALUES:
                    invalid_fields.append("policy.installation")
                if authentication not in MARKETPLACE_AUTHENTICATION_VALUES:
                    invalid_fields.append("policy.authentication")
                if not isinstance(category, str) or not category.strip():
                    invalid_fields.append("category")
                if invalid_fields:
                    mk["status"] = "invalid"
                    violations.append(
                        _v(
                            SEV_INVALID,
                            "marketplace_entry_invalid",
                            f"marketplace named entry が公式 local contract に不適合: {', '.join(invalid_fields)}",
                        )
                    )
                elif not referenced:
                    mk["status"] = "drift"
                    violations.append(
                        _v(
                            SEV_DRIFT,
                            "marketplace_unreferenced",
                            f"marketplace が {slug} plugin root {expected} を参照していない",
                        )
                    )
                else:
                    mk["status"] = "confirmed"
    report["marketplace_parity"] = mk

    # (7) artifact digest freshness + consistency。
    digests: dict = {}
    parsed: dict = {}
    for fname in contract["digest_inputs"]:
        if not isinstance(fname, str):
            continue
        fpath = plan_dir / fname
        if not fpath.is_file():
            digests[fname] = None
            violations.append(_v(SEV_INVALID, "digest_input_missing", f"digest input 欠落: {fname}"))
            continue
        digests[fname] = sha256_file(fpath)
        try:
            parsed[fname] = json.loads(fpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed[fname] = None
            violations.append(_v(SEV_INVALID, "digest_input_parse_error", f"digest input parse 不能: {fname}"))
    report["digests"] = digests

    # plan-findings が pin した digest と現物を比較する。単な hash 算出だけで
    # freshness PASS にしない (self hash となる plan-findings 自身は pin 対象外)。
    findings = parsed.get(FINDINGS_FILE)
    expected_digests = findings.get("artifact_digests") if isinstance(findings, dict) else None
    freshness: dict = {"pinned_by": FINDINGS_FILE, "artifacts": {}, "all_match": None}
    required_pins = [name for name in contract["digest_inputs"] if name != FINDINGS_FILE]
    if not isinstance(expected_digests, dict):
        freshness["all_match"] = False
        violations.append(_v(SEV_INVALID, "freshness_pins_missing", "plan-findings artifact_digests が不正/欠落"))
    else:
        all_match = True
        for fname in sorted(set(required_pins) | set(expected_digests)):
            expected_digest = expected_digests.get(fname)
            fpath = plan_dir / fname
            actual_digest = sha256_file(fpath) if fpath.is_file() else None
            valid_pin = isinstance(expected_digest, str) and len(expected_digest) == 64 and all(
                ch in "0123456789abcdef" for ch in expected_digest
            )
            match = valid_pin and actual_digest == expected_digest
            freshness["artifacts"][fname] = {
                "expected": expected_digest,
                "actual": actual_digest,
                "match": match,
            }
            if not valid_pin:
                all_match = False
                violations.append(_v(SEV_INVALID, "freshness_pin_invalid", f"digest pin 不正/欠落: {fname}"))
            elif not match:
                all_match = False
                violations.append(_v(SEV_DRIFT, "digest_mismatch", f"artifact digest stale: {fname}"))
        freshness["all_match"] = all_match
    report["freshness"] = freshness

    handoff = parsed.get(HANDOFF_FILE)
    inv = parsed.get(INVENTORY_FILE)
    tg = parsed.get(TASK_GRAPH_FILE)
    cons: dict = {"routes": None, "components": None, "entity_refs": None, "consistent": None}
    if isinstance(handoff, dict) and isinstance(inv, dict) and isinstance(tg, dict):
        routes = handoff.get("routes")
        comps = inv.get("components")
        r = len(routes) if isinstance(routes, list) else None
        c = len(comps) if isinstance(comps, list) else None
        e = count_distinct_entity_refs(tg)
        cons.update(routes=r, components=c, entity_refs=e)
        if r is not None and c is not None and r == c == e:
            cons["consistent"] = True
        else:
            cons["consistent"] = False
            violations.append(
                _v(SEV_DRIFT, "consistency_stale", f"artifact consistency 不一致: routes={r} components={c} entity_refs={e}")
            )
    report["consistency"] = cons

    # (8) exit code は最も重い severity。
    exit_code = max((v["severity"] for v in violations), default=0)
    report["violations"] = violations
    report["verdict"] = "PASS" if exit_code == 0 else "FAIL"
    report["exit_code"] = exit_code
    return report, exit_code


# ─────────────────── rendering / CLI ───────────────────
def render_human(report: dict, out) -> None:
    out.write(f"verdict: {report.get('verdict')} (exit {report.get('exit_code')})\n")
    contract = report.get("contract")
    if contract:
        out.write(
            f"contract: schema={contract.get('schema_version')} checked_at={contract.get('checked_at')} "
            f"codex_cli={contract.get('codex_cli_version')} "
            f"activation={contract.get('activation_semantics')}\n"
        )
    for s in report.get("surfaces", []):
        line = f"  surface {s.get('key')}: {s.get('classification')} owner={s.get('owner')} write_policy={s.get('write_policy')}"
        if s.get("classification") == "unsupported":
            line += f" projection_detected={s.get('projection_detected')}"
        if "trust_required" in s:
            line += f" trust_required={s.get('trust_required')}"
        out.write(line + "\n")
    mp = report.get("manifest_parity") or {}
    if mp:
        out.write(f"  manifest_parity: {mp.get('status')} (claude={mp.get('claude_exists')} codex={mp.get('codex_exists')} name={mp.get('claude_name')}/{mp.get('codex_name')})\n")
    mk = report.get("marketplace_parity") or {}
    if mk:
        out.write(f"  marketplace_parity: {mk.get('status')} (exists={mk.get('exists')} referenced={mk.get('referenced')})\n")
    tr = report.get("trust") or {}
    if tr:
        out.write(
            f"  trust: claude_selection={tr.get('claude_projection_selection')} "
            f"codex_required={tr.get('codex_trust_required')} "
            f"codex_runtime={tr.get('codex_runtime_evidence')}\n"
        )
    cons = report.get("consistency") or {}
    if cons:
        out.write(f"  consistency: consistent={cons.get('consistent')} routes={cons.get('routes')} components={cons.get('components')} entity_refs={cons.get('entity_refs')}\n")
    digests = report.get("digests") or {}
    for fname, dg in digests.items():
        out.write(f"  digest {fname}: {dg}\n")
    for v in report.get("violations", []):
        out.write(f"  VIOLATION[{v.get('severity')}] {v.get('code')}: {v.get('detail')}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="C02 native surface parity validator (read-only)。contract を正本に repo 実測を突合する。"
    )
    ap.add_argument("--repo-root", required=True, help="repo ルート")
    ap.add_argument("--plugin-slug", required=True, help="対象 plugin slug (例: harness-creator)")
    ap.add_argument("--surface-contract", required=True, help="native-surface-contract.md")
    ap.add_argument("--plan-dir", required=True, help="digest input を含む plan dir")
    ap.add_argument("--json", dest="as_json", action="store_true", help="機械可読 JSON 出力")
    args = ap.parse_args(argv)

    report, code = evaluate(
        Path(args.repo_root),
        args.plugin_slug,
        Path(args.surface_contract),
        Path(args.plan_dir),
    )
    if args.as_json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        render_human(report, sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
