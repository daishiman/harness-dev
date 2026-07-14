"""check-native-surface-parity.py (C02) の機能テスト。

native-surface-contract.md の canonical JSON block を正本に、Claude/Codex surface 分類・
dual manifest parity・repo marketplace parity・plugin hook trust 前提・artifact digest
freshness/consistency を read-only 突合する validator の受入/負例/exit code を固定する。

すべて tempdir 上に合成 repo/contract を組み立てて検査するため real repo 状態に依存しない
(validator は write-scope: none のため安全)。conftest.py には触れず、本ファイル内で module を
file-path import する。
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

# ── module を file-path import (ハイフン名のため importlib) ──
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_native_surface_parity", _SCRIPTS_DIR / "check-native-surface-parity.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nsp = _load()


# ─────────────────── fixtures / builders ───────────────────
def _contract() -> dict:
    """構造的に妥当な canonical contract。テストごとに deepcopy して改変する。"""
    return {
        "schema_version": "1.0",
        "checked_at": "2026-07-12",
        "codex_cli_version": "0.144.0",
        "sources": ["https://developers.openai.com/codex/plugins/build"],
        "activation_semantics": {
            "claude_projection_selection": "repo_present_exact_project_identity_enabled",
            "codex_plugin_activation": "install_enable_then_user_hook_trust",
            "codex_trust_mutation": "forbidden_user_gated",
        },
        "confirmed_kinds": ["skill", "hook"],
        "unsupported_kinds": ["agent", "command"],
        "surfaces": [
            {
                "key": "repo_skill",
                "classification": "confirmed",
                "claude": ".claude/skills",
                "codex": ".agents/skills",
                "owner": "repo-generator",
                "write_policy": "fingerprint-diff-only",
                "verification": "skill 集合が一致",
            },
            {
                "key": "plugin_hook",
                "classification": "confirmed",
                "claude": ".claude-plugin/plugin.json",
                "codex": ".codex-plugin/plugin.json",
                "owner": "plugin-source",
                "write_policy": "build-or-update-only",
                "trust_required": True,
                "verification": "trust 済みのみ発火",
            },
            {
                "key": "plugin_discovery",
                "classification": "confirmed",
                "claude": "claude-plugin-manifest",
                "codex": ".agents/plugins/marketplace.json",
                "owner": "repo",
                "write_policy": "explicit-entry-only",
                "verification": "marketplace が codex-plugin を指す",
            },
            {
                "key": "agent",
                "classification": "unsupported",
                "claude": ".claude/agents",
                "codex": None,
                "owner": "none",
                "write_policy": "none",
                "verification": "silent projection 禁止",
            },
            {
                "key": "command",
                "classification": "unsupported",
                "claude": ".claude/commands",
                "codex": None,
                "owner": "none",
                "write_policy": "none",
                "verification": "silent projection 禁止",
            },
        ],
        "forbidden_codex_surfaces": [
            ".agents/agents",
            ".agents/commands",
            ".agents/hooks",
            "guessed-toml-hook-merge",
        ],
        "state_ownership": [
            {"state": ".claude-managed-projection", "owner": "repo-generator", "auto_write": "fingerprint-diff-only"}
        ],
        "failure_taxonomy": {
            "skipped_not_installed": "generator-absent-only",
            "not_collapsible_to_success": ["drift", "conflict", "parse", "race", "timeout"],
        },
        "digest_inputs": [
            "goal-spec.json",
            "component-inventory.json",
            "handoff-run-plugin-dev-plan.json",
            "task-graph.json",
            "plan-findings.json",
        ],
    }


def _md(contract: dict | None, *, extra_json_blocks: int = 0, extra_bash: bool = False, raw: str | None = None) -> str:
    if raw is not None:
        return raw
    parts = ["# Native Surface Contract\n", "prose text here\n"]
    if extra_bash:
        parts.append("```bash\necho hi\n```\n")
    if contract is not None:
        parts.append("```json\n" + json.dumps(contract, ensure_ascii=False, indent=2) + "\n```\n")
    for _ in range(extra_json_blocks):
        parts.append("```json\n{}\n```\n")
    return "\n".join(parts)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _build_plan_dir(plan_dir: Path, n_routes: int = 3, n_comps: int = 3, n_refs: int = 3) -> None:
    _write_json(plan_dir / "goal-spec.json", {"goal": "x"})
    _write_json(plan_dir / "handoff-run-plugin-dev-plan.json", {"routes": [{"id": f"C{i}"} for i in range(n_routes)]})
    _write_json(plan_dir / "component-inventory.json", {"components": [{"id": f"C{i}"} for i in range(n_comps)]})
    # entity_ref に None を混ぜて non-null distinct のみ数えられるか確かめる。
    nodes = [{"entity_ref": f"E{i}"} for i in range(n_refs)] + [{"entity_ref": None}]
    _write_json(plan_dir / "task-graph.json", {"nodes": nodes})
    pinned = {
        fname: nsp.sha256_file(plan_dir / fname)
        for fname in (
            "goal-spec.json",
            "component-inventory.json",
            "handoff-run-plugin-dev-plan.json",
            "task-graph.json",
        )
    }
    _write_json(plan_dir / "plan-findings.json", {"findings": [], "artifact_digests": pinned})


def _build_repo(
    tmp_path: Path,
    *,
    slug: str = "myplugin",
    claude_name: str | None = None,
    codex_name: str | None = None,
    claude_manifest: bool = True,
    codex_manifest: bool = True,
    marketplace: bool = True,
    marketplace_ref: bool = True,
    hooks: bool = True,
    contract: dict | None = "__default__",  # type: ignore[assignment]
    md_kwargs: dict | None = None,
    n_routes: int = 3,
    n_comps: int = 3,
    n_refs: int = 3,
):
    """合成 repo を組み立て (root, slug, contract_path, plan_dir) を返す。"""
    root = tmp_path / "repo"
    plugin = root / "plugins" / slug
    _write_json(root / ".claude-plugin" / "marketplace.json", {"name": "skills", "plugins": []})
    shared = {
        "name": slug,
        "version": "1.2.3",
        "description": "fixture plugin",
        "author": {"name": "fixture"},
    }
    (plugin / "skills").mkdir(parents=True, exist_ok=True)
    if claude_manifest:
        _write_json(
            plugin / ".claude-plugin" / "plugin.json",
            {**shared, "name": claude_name or slug, "hooks": {
                "SessionStart": [{"matcher": "", "hooks": [{
                    "type": "command",
                    "command": "python3 ${PLUGIN_ROOT}/hooks/auto-sync-on-session-start.py",
                }]}]
            }},
        )
    if codex_manifest:
        _write_json(
            plugin / ".codex-plugin" / "plugin.json",
            {
                **shared,
                "name": codex_name or slug,
                "skills": "./skills/",
                "hooks": "./hooks/hooks.json",
            },
        )
    if hooks:
        _write_json(
            plugin / "hooks" / "hooks.json",
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 ${PLUGIN_ROOT}/hooks/auto-sync-on-session-start.py",
                                }
                            ]
                        }
                    ]
                }
            },
        )
    if marketplace:
        ref = f"./plugins/{slug}" if marketplace_ref else "./plugins/other"
        _write_json(
            root / ".agents" / "plugins" / "marketplace.json",
            {
                "name": "fixture-marketplace",
                "plugins": [
                    {
                        "name": slug,
                        "source": {"source": "local", "path": ref},
                        "policy": {
                            "installation": "AVAILABLE",
                            "authentication": "ON_INSTALL",
                        },
                        "category": "Internal-Tooling",
                        "x_harness": {
                            "distributable": False,
                            "scope": "repo-internal",
                            "activation_requires": ["user-install", "user-enable", "user-hook-trust"],
                        },
                    }
                ]
            },
        )
    (root / ".codex").mkdir(parents=True, exist_ok=True)
    _write_json(root / ".codex" / "hooks.json", {"hooks": {}})
    (root / ".codex" / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")
    (plugin / "native-surfaces.toml").write_text(
        f'''schema_version = 1
[activation]
claude_marketplace = "skills"
codex_discovery = ".agents/plugins/marketplace.json"
[codex]
hooks_file = ".codex/hooks.json"
config_file = ".codex/config.toml"
features_hooks = true
[discovery]
marketplace_name = "fixture-marketplace"
plugin_name = "{slug}"
source_path = "./plugins/{slug}"
installation = "AVAILABLE"
authentication = "ON_INSTALL"
category = "Internal-Tooling"
distributable = false
scope = "repo-internal"
activation_requires = ["user-install", "user-enable", "user-hook-trust"]
[[hooks]]
id = "sync"
owner = "myplugin"
event = "SessionStart"
matcher = ""
command = "python3 ${{PLUGIN_ROOT}}/hooks/auto-sync-on-session-start.py"
delivery = "plugin"
products = ["claude", "codex"]
''',
        encoding="utf-8",
    )
    plan_dir = root / "plan"
    _build_plan_dir(plan_dir, n_routes, n_comps, n_refs)
    c = _contract() if contract == "__default__" else contract
    contract_path = root / "contract.md"
    contract_path.write_text(_md(c, **(md_kwargs or {})), encoding="utf-8")
    return root, slug, contract_path, plan_dir


def _eval(repo):
    root, slug, cp, pd = repo
    return nsp.evaluate(root, slug, cp, pd)


def _codes(report) -> set[str]:
    return {v["code"] for v in report["violations"]}


def test_common_native_surface_toml_missing_fails_closed(tmp_path):
    repo = _build_repo(tmp_path)
    (repo[0] / "plugins" / repo[1] / "native-surfaces.toml").unlink()
    report, code = _eval(repo)
    assert code == 3 and "native_surfaces_toml_missing" in _codes(report)


def test_codex_inline_and_json_hooks_same_layer_conflict(tmp_path):
    repo = _build_repo(tmp_path)
    (repo[0] / ".codex" / "config.toml").write_text(
        "[features]\nhooks=true\n[hooks]\n", encoding="utf-8"
    )
    report, code = _eval(repo)
    assert code >= 2 and "codex_same_layer_hook_duplicate" in _codes(report)


def test_plugin_delivery_duplicated_in_project_layer_conflicts(tmp_path):
    repo = _build_repo(tmp_path)
    _write_json(repo[0] / ".codex" / "hooks.json", {"hooks": {"SessionStart": [{
        "matcher": "", "hooks": [{"type": "command", "command":
        "python3 ${PLUGIN_ROOT}/hooks/auto-sync-on-session-start.py"}]
    }]}})
    report, code = _eval(repo)
    assert code == 2 and "hook_delivery_duplicate_or_missing" in _codes(report)


def test_forbidden_agents_native_guess_still_fails_closed(tmp_path):
    repo = _build_repo(tmp_path)
    (repo[0] / ".agents" / "hooks").mkdir(parents=True)
    report, code = _eval(repo)
    assert code == 3 and "forbidden_surface_present" in _codes(report)


# ═══════════════════ extract_json_blocks ═══════════════════
def test_extract_zero_blocks():
    assert nsp.extract_json_blocks("# heading\nno fence here\n") == []


def test_extract_single_block():
    blocks = nsp.extract_json_blocks("pre\n```json\n{\"a\": 1}\n```\npost\n")
    assert len(blocks) == 1
    assert json.loads(blocks[0]) == {"a": 1}


def test_extract_two_blocks():
    assert len(nsp.extract_json_blocks("```json\n{}\n```\n```json\n{}\n```\n")) == 2


def test_extract_three_blocks():
    text = "```json\n1\n```\ntxt\n```json\n2\n```\ntxt\n```json\n3\n```\n"
    assert len(nsp.extract_json_blocks(text)) == 3


def test_extract_ignores_non_json_fences():
    text = "```bash\necho hi\n```\n```json\n{\"k\": 2}\n```\n"
    blocks = nsp.extract_json_blocks(text)
    assert len(blocks) == 1
    assert json.loads(blocks[0]) == {"k": 2}


def test_extract_empty_json_fence_counts():
    assert nsp.extract_json_blocks("```json\n```\n") == [""]


def test_extract_indented_fence_markers():
    # strip() 後に ```json / ``` を判定するため軽微なインデントは許容。
    text = "   ```json\n{\"x\": 1}\n   ```\n"
    assert len(nsp.extract_json_blocks(text)) == 1


# ═══════════════════ parse_contract ═══════════════════
def test_parse_valid_contract_ok():
    data, err = nsp.parse_contract(_md(_contract()))
    assert err is None
    assert data["schema_version"] == "1.0"


def test_parse_zero_blocks_error():
    data, err = nsp.parse_contract(_md(None))
    assert data is None
    assert "0 個" in err


def test_parse_two_blocks_error():
    data, err = nsp.parse_contract(_md(_contract(), extra_json_blocks=1))
    assert data is None
    assert "複数" in err


def test_parse_broken_json_error():
    data, err = nsp.parse_contract("```json\n{ broken,,, }\n```\n")
    assert data is None
    assert "parse 不能" in err


def test_parse_non_object_error():
    data, err = nsp.parse_contract("```json\n[1, 2, 3]\n```\n")
    assert data is None
    assert "object でない" in err


@pytest.mark.parametrize("key", list(nsp.REQUIRED_CONTRACT_KEYS))
def test_parse_missing_required_key_error(key):
    c = _contract()
    del c[key]
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "必須キー欠落" in err
    assert key in err


@pytest.mark.parametrize("key", list(nsp.SURFACE_REQUIRED_KEYS))
def test_parse_surface_missing_key_error(key):
    c = _contract()
    del c["surfaces"][0][key]
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "キー欠落" in err


def test_parse_surfaces_not_list_error():
    c = _contract()
    c["surfaces"] = {"nope": 1}
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "surfaces" in err


def test_parse_surfaces_empty_error():
    c = _contract()
    c["surfaces"] = []
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "surfaces" in err


def test_parse_surface_non_dict_error():
    c = _contract()
    c["surfaces"][0] = "not-a-dict"
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "object でない" in err


def test_parse_invalid_classification_error():
    c = _contract()
    c["surfaces"][0]["classification"] = "bogus"
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "classification" in err


def test_parse_deferred_classification_ok():
    c = _contract()
    c["surfaces"][0]["classification"] = "deferred"
    data, err = nsp.parse_contract(_md(c))
    assert err is None
    assert data is not None


def test_parse_plugin_hook_missing_trust_error():
    c = _contract()
    del c["surfaces"][1]["trust_required"]  # index 1 = plugin_hook
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "trust_required" in err


def test_parse_plugin_hook_trust_false_error():
    c = _contract()
    c["surfaces"][1]["trust_required"] = False
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "trust_required" in err


def test_parse_forbidden_not_list_error():
    c = _contract()
    c["forbidden_codex_surfaces"] = "nope"
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "forbidden_codex_surfaces" in err


def test_parse_digest_inputs_not_list_error():
    c = _contract()
    c["digest_inputs"] = {}
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "digest_inputs" in err


def test_parse_digest_inputs_empty_error():
    c = _contract()
    c["digest_inputs"] = []
    data, err = nsp.parse_contract(_md(c))
    assert data is None
    assert "digest_inputs" in err


# ═══════════════════ helpers ═══════════════════
def test_sha256_file_deterministic(tmp_path):
    p = tmp_path / "a.json"
    p.write_text("hello", encoding="utf-8")
    assert nsp.sha256_file(p) == nsp.sha256_file(p)


def test_sha256_file_differs_by_content(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.write_text("x", encoding="utf-8")
    b.write_text("y", encoding="utf-8")
    assert nsp.sha256_file(a) != nsp.sha256_file(b)


def test_count_entity_refs_empty():
    assert nsp.count_distinct_entity_refs({"nodes": []}) == 0


def test_count_entity_refs_skips_null():
    tg = {"nodes": [{"entity_ref": "A"}, {"entity_ref": None}, {"entity_ref": "B"}]}
    assert nsp.count_distinct_entity_refs(tg) == 2


def test_count_entity_refs_distinct():
    tg = {"nodes": [{"entity_ref": "A"}, {"entity_ref": "A"}, {"entity_ref": "B"}]}
    assert nsp.count_distinct_entity_refs(tg) == 2


def test_count_entity_refs_dict_values():
    tg = {"nodes": [{"entity_ref": {"id": 1}}, {"entity_ref": {"id": 1}}, {"entity_ref": {"id": 2}}]}
    assert nsp.count_distinct_entity_refs(tg) == 2


def test_count_entity_refs_non_dict_input():
    assert nsp.count_distinct_entity_refs("nope") == 0
    assert nsp.count_distinct_entity_refs({"nodes": "x"}) == 0


def test_iter_strings_finds_nested():
    strings = set(nsp._iter_strings({"a": ["x", {"b": "y"}], "c": 3}))
    assert "x" in strings and "y" in strings


# ═══════════════════ evaluate: PASS ═══════════════════
def test_evaluate_clean_pass(tmp_path):
    report, code = _eval(_build_repo(tmp_path))
    assert code == 0
    assert report["verdict"] == "PASS"
    assert report["violations"] == []


def test_pass_manifest_confirmed(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert report["manifest_parity"]["status"] == "confirmed"


def test_pass_marketplace_confirmed(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert report["marketplace_parity"]["status"] == "confirmed"
    assert report["marketplace_parity"]["referenced"] is True


def test_pass_consistency_true(tmp_path):
    report, _ = _eval(_build_repo(tmp_path, n_routes=4, n_comps=4, n_refs=4))
    assert report["consistency"]["consistent"] is True
    assert report["consistency"]["routes"] == 4


def test_pass_digests_present_for_all_inputs(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    for fname in _contract()["digest_inputs"]:
        assert report["digests"][fname] and len(report["digests"][fname]) == 64


def test_pass_unsupported_surfaces_listed_explicitly(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    unsup = [s for s in report["surfaces"] if s["classification"] == "unsupported"]
    assert {s["key"] for s in unsup} == {"agent", "command"}
    assert all(s["projection_detected"] is False for s in unsup)


# ═══════════════════ trust precondition ═══════════════════
def test_trust_precondition_reported(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert report["trust"] == {
        "claude_projection_selection": "repo_present_exact_project_identity_enabled",
        "codex_trust_required": True,
        "codex_runtime_evidence": "pending_user_gate",
        "codex_trust_mutation": "forbidden_user_gated",
    }


def test_trust_surface_entry_flag(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    ph = next(s for s in report["surfaces"] if s["key"] == "plugin_hook")
    assert ph["trust_required"] is True


def test_trust_never_causes_failure(tmp_path):
    # plugin hook trust は precondition の明示のみで失敗要因にしない。
    report, code = _eval(_build_repo(tmp_path))
    assert code == 0
    assert "trust" not in _codes(report)


# ═══════════════════ forbidden surface (exit 3) ═══════════════════
@pytest.mark.parametrize("path", [".agents/agents", ".agents/commands", ".agents/hooks"])
def test_forbidden_surface_present_exit3(tmp_path, path):
    repo = _build_repo(tmp_path)
    root = repo[0]
    (root / path).mkdir(parents=True)
    report, code = _eval(repo)
    assert code == 3
    assert "forbidden_surface_present" in _codes(report)


def test_forbidden_sentinel_does_not_flag_supported_features_toggle(tmp_path):
    repo = _build_repo(tmp_path)
    (repo[0] / ".codex").mkdir(parents=True, exist_ok=True)
    (repo[0] / ".codex" / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")
    # 公式 feature toggle は推測 hook schema/managed marker ではない。
    report, code = _eval(repo)
    assert code == 0
    assert "forbidden_surface_present" not in _codes(report)


@pytest.mark.parametrize(
    "toml",
    [
        "# BEGIN HARNESS MANAGED HOOKS\n[features]\nhooks = true\n",
        "[hooks]\nSessionStart = ['python3 guessed.py']\n",
        "[[hooks.SessionStart]]\ncommand = 'python3 guessed.py'\n",
    ],
)
def test_forbidden_guessed_toml_marker_or_schema_exit3(tmp_path, toml):
    repo = _build_repo(tmp_path)
    (repo[0] / ".codex").mkdir(parents=True, exist_ok=True)
    (repo[0] / ".codex" / "config.toml").write_text(toml, encoding="utf-8")
    report, code = _eval(repo)
    assert code == 3
    assert "forbidden_guessed_toml_hook_merge" in _codes(report)


def test_forbidden_hooks_dir_absent_ok(tmp_path):
    report, code = _eval(_build_repo(tmp_path))
    assert "forbidden_surface_present" not in _codes(report)
    assert code == 0


# ═══════════════════ dual manifest parity ═══════════════════
def test_manifest_codex_missing_drift(tmp_path):
    report, code = _eval(_build_repo(tmp_path, codex_manifest=False))
    assert code == 1
    assert "manifest_missing" in _codes(report)
    assert report["manifest_parity"]["status"] == "drift"


def test_manifest_claude_missing_drift(tmp_path):
    report, code = _eval(_build_repo(tmp_path, claude_manifest=False))
    assert code == 1
    assert "manifest_missing" in _codes(report)


def test_manifest_both_missing_drift(tmp_path):
    report, code = _eval(_build_repo(tmp_path, claude_manifest=False, codex_manifest=False))
    assert code == 1
    assert "manifest_missing" in _codes(report)


def test_manifest_codex_invalid_json_is_invalid_layout(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    (root / "plugins" / slug / ".codex-plugin" / "plugin.json").write_text("{ broken", encoding="utf-8")
    report, code = _eval(repo)
    assert code == 3
    assert "manifest_invalid_json" in _codes(report)


def test_manifest_name_conflict_exit2(tmp_path):
    report, code = _eval(_build_repo(tmp_path, claude_name="myplugin", codex_name="other-name"))
    assert code == 2
    assert "manifest_name_conflict" in _codes(report)
    assert report["manifest_parity"]["status"] == "conflict"


def test_manifest_folder_name_drift_exit1(tmp_path):
    # 両 manifest は一致するが folder slug と食い違う → drift。
    report, code = _eval(_build_repo(tmp_path, claude_name="renamed", codex_name="renamed"))
    assert code == 1
    assert "manifest_folder_name_drift" in _codes(report)


def test_manifest_names_reported(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert report["manifest_parity"]["claude_name"] == "myplugin"
    assert report["manifest_parity"]["codex_name"] == "myplugin"


def test_manifest_shared_version_required(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    path = root / "plugins" / slug / ".codex-plugin" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["version"]
    _write_json(path, data)
    report, code = _eval(repo)
    assert code == 3
    assert "manifest_metadata_missing" in _codes(report)


def test_manifest_shared_author_drift(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    path = root / "plugins" / slug / ".codex-plugin" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["author"] = {"name": "different"}
    _write_json(path, data)
    report, code = _eval(repo)
    assert code == 1
    assert "manifest_metadata_drift" in _codes(report)


@pytest.mark.parametrize("skills", [None, "../outside", "./other-skills/"])
def test_manifest_skills_path_required_and_confined(tmp_path, skills):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    path = root / "plugins" / slug / ".codex-plugin" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if skills is None:
        del data["skills"]
    else:
        data["skills"] = skills
    _write_json(path, data)
    report, code = _eval(repo)
    assert code == 3
    assert "manifest_skills_path_invalid" in _codes(report)


# ═══════════════════ marketplace parity ═══════════════════
def test_marketplace_missing_drift(tmp_path):
    report, code = _eval(_build_repo(tmp_path, marketplace=False))
    assert code == 1
    assert "marketplace_missing" in _codes(report)


def test_marketplace_invalid_json_is_invalid_layout(tmp_path):
    repo = _build_repo(tmp_path)
    root = repo[0]
    (root / ".agents" / "plugins" / "marketplace.json").write_text("{ broken", encoding="utf-8")
    report, code = _eval(repo)
    assert code == 3
    assert "marketplace_invalid_json" in _codes(report)


def test_marketplace_unreferenced_drift(tmp_path):
    report, code = _eval(_build_repo(tmp_path, marketplace_ref=False))
    assert code == 1
    assert "marketplace_unreferenced" in _codes(report)
    assert report["marketplace_parity"]["referenced"] is False


def test_marketplace_referenced_ok(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert "marketplace_unreferenced" not in _codes(report)


def test_marketplace_requires_named_plugin_root_entry(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    _write_json(
        root / ".agents" / "plugins" / "marketplace.json",
        {"note": f"./plugins/{slug}", "plugins": [{"name": "other", "source": f"./plugins/{slug}"}]},
    )
    report, code = _eval(repo)
    assert code == 1
    assert "marketplace_unreferenced" in _codes(report)


def test_marketplace_plain_string_source_rejected(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    _write_json(
        root / ".agents" / "plugins" / "marketplace.json",
        {"plugins": [{"name": slug, "source": f"./plugins/{slug}"}]},
    )
    report, code = _eval(repo)
    assert code == 3
    assert "marketplace_entry_invalid" in _codes(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("installation", "SOMETIMES"),
        ("authentication", "NEVER"),
    ],
)
def test_marketplace_policy_enum_rejected(tmp_path, field, value):
    repo = _build_repo(tmp_path)
    path = repo[0] / ".agents" / "plugins" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["plugins"][0]["policy"][field] = value
    _write_json(path, data)
    report, code = _eval(repo)
    assert code == 3
    assert "marketplace_entry_invalid" in _codes(report)


def test_marketplace_category_required(tmp_path):
    repo = _build_repo(tmp_path)
    path = repo[0] / ".agents" / "plugins" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["plugins"][0]["category"] = ""
    _write_json(path, data)
    report, code = _eval(repo)
    assert code == 3
    assert "marketplace_entry_invalid" in _codes(report)


def test_marketplace_source_path_escape_is_invalid(tmp_path):
    repo = _build_repo(tmp_path)
    path = repo[0] / ".agents" / "plugins" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["plugins"][0]["source"]["path"] = "./../../outside"
    _write_json(path, data)
    report, code = _eval(repo)
    assert code == 3
    assert "marketplace_entry_invalid" in _codes(report)


def test_plugin_hooks_missing_is_drift(tmp_path):
    report, code = _eval(_build_repo(tmp_path, hooks=False))
    assert code == 1
    assert report["hook_parity"]["status"] == "drift"
    assert "plugin_hooks_missing" in _codes(report)


def test_plugin_hooks_sessionstart_entrypoint_required(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    _write_json(root / "plugins" / slug / "hooks" / "hooks.json", {"hooks": {"SessionStart": []}})
    report, code = _eval(repo)
    assert code == 3
    assert "plugin_hooks_schema_invalid" in _codes(report)


def test_plugin_hooks_schema_rejects_non_command(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    _write_json(
        root / "plugins" / slug / "hooks" / "hooks.json",
        {"hooks": {"SessionStart": [{"hooks": [{"type": "prompt", "command": "x"}]}]}},
    )
    report, code = _eval(repo)
    assert code == 3
    assert "plugin_hooks_schema_invalid" in _codes(report)


def test_plugin_hooks_sessionstart_command_path_escape_is_invalid(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    _write_json(
        root / "plugins" / slug / "hooks" / "hooks.json",
        {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ${PLUGIN_ROOT}/../outside.py",
                            }
                        ]
                    }
                ]
            }
        },
    )
    report, code = _eval(repo)
    assert code == 3
    assert "plugin_hooks_schema_invalid" in _codes(report)


def test_manifest_hook_path_escape_is_invalid(tmp_path):
    repo = _build_repo(tmp_path)
    root, slug = repo[0], repo[1]
    _write_json(
        root / "plugins" / slug / ".codex-plugin" / "plugin.json",
        {"name": slug, "hooks": "./../outside.json"},
    )
    report, code = _eval(repo)
    assert code == 3
    assert "plugin_hooks_path_invalid" in _codes(report)


# ═══════════════════ unsupported silent / misprojection ═══════════════════
def _contract_no_forbidden() -> dict:
    """unsupported projection を単独 (exit1) で観測するため forbidden 一致を外した契約。"""
    c = _contract()
    c["forbidden_codex_surfaces"] = ["guessed-toml-hook-merge"]
    return c


def test_unsupported_agent_misprojection_exit1(tmp_path):
    repo = _build_repo(tmp_path, contract=_contract_no_forbidden())
    (repo[0] / ".agents" / "agents").mkdir(parents=True)
    report, code = _eval(repo)
    assert code == 1
    assert "unsupported_projection" in _codes(report)


def test_unsupported_command_misprojection_exit1(tmp_path):
    repo = _build_repo(tmp_path, contract=_contract_no_forbidden())
    (repo[0] / ".agents" / "commands").mkdir(parents=True)
    report, code = _eval(repo)
    assert code == 1
    assert "unsupported_projection" in _codes(report)


def test_unsupported_no_projection_no_violation(tmp_path):
    report, code = _eval(_build_repo(tmp_path, contract=_contract_no_forbidden()))
    assert code == 0
    assert "unsupported_projection" not in _codes(report)


def test_unsupported_projection_flag_in_surface(tmp_path):
    repo = _build_repo(tmp_path, contract=_contract_no_forbidden())
    (repo[0] / ".agents" / "agents").mkdir(parents=True)
    report, _ = _eval(repo)
    agent = next(s for s in report["surfaces"] if s["key"] == "agent")
    assert agent["projection_detected"] is True
    assert agent["projection_path"] == ".agents/agents"


# ═══════════════════ digest freshness (exit 3) ═══════════════════
@pytest.mark.parametrize("fname", _contract()["digest_inputs"])
def test_digest_input_missing_exit3(tmp_path, fname):
    repo = _build_repo(tmp_path)
    (repo[3] / fname).unlink()
    report, code = _eval(repo)
    assert code == 3
    assert "digest_input_missing" in _codes(report)


@pytest.mark.parametrize("fname", _contract()["digest_inputs"])
def test_digest_input_parse_error_exit3(tmp_path, fname):
    repo = _build_repo(tmp_path)
    (repo[3] / fname).write_text("{ not json", encoding="utf-8")
    report, code = _eval(repo)
    assert code == 3
    assert "digest_input_parse_error" in _codes(report)


def test_digest_missing_null_in_report(tmp_path):
    repo = _build_repo(tmp_path)
    (repo[3] / "goal-spec.json").unlink()
    report, _ = _eval(repo)
    assert report["digests"]["goal-spec.json"] is None


def test_digest_pin_mismatch_is_stale(tmp_path):
    repo = _build_repo(tmp_path)
    _write_json(repo[3] / "goal-spec.json", {"goal": "changed after review"})
    report, code = _eval(repo)
    assert code == 1
    assert report["freshness"]["all_match"] is False
    assert "digest_mismatch" in _codes(report)


def test_missing_artifact_digest_pins_is_invalid(tmp_path):
    repo = _build_repo(tmp_path)
    _write_json(repo[3] / "plan-findings.json", {"findings": []})
    report, code = _eval(repo)
    assert code == 3
    assert "freshness_pins_missing" in _codes(report)


# ═══════════════════ consistency (exit 1) ═══════════════════
def test_consistency_routes_ne_components_stale(tmp_path):
    report, code = _eval(_build_repo(tmp_path, n_routes=4, n_comps=3, n_refs=3))
    assert code == 1
    assert "consistency_stale" in _codes(report)
    assert report["consistency"]["consistent"] is False


def test_consistency_components_ne_refs_stale(tmp_path):
    report, code = _eval(_build_repo(tmp_path, n_routes=3, n_comps=3, n_refs=5))
    assert code == 1
    assert "consistency_stale" in _codes(report)


def test_consistency_routes_ne_refs_stale(tmp_path):
    report, code = _eval(_build_repo(tmp_path, n_routes=2, n_comps=2, n_refs=6))
    assert code == 1
    assert "consistency_stale" in _codes(report)


def test_consistency_all_equal_ok(tmp_path):
    report, code = _eval(_build_repo(tmp_path, n_routes=7, n_comps=7, n_refs=7))
    assert "consistency_stale" not in _codes(report)
    assert code == 0


def test_consistency_counts_reported(tmp_path):
    report, _ = _eval(_build_repo(tmp_path, n_routes=3, n_comps=3, n_refs=3))
    c = report["consistency"]
    assert c["routes"] == 3 and c["components"] == 3 and c["entity_refs"] == 3


# ═══════════════════ invalid contract via evaluate (exit 3) ═══════════════════
def test_evaluate_missing_contract_file_exit3(tmp_path):
    root, slug, _cp, pd = _build_repo(tmp_path)
    report, code = nsp.evaluate(root, slug, root / "nope.md", pd)
    assert code == 3
    assert "invalid_contract" in _codes(report)


def test_evaluate_zero_block_contract_exit3(tmp_path):
    repo = _build_repo(tmp_path, contract=None)
    report, code = _eval(repo)
    assert code == 3
    assert "invalid_contract" in _codes(report)


def test_evaluate_two_block_contract_exit3(tmp_path):
    repo = _build_repo(tmp_path, md_kwargs={"extra_json_blocks": 1})
    report, code = _eval(repo)
    assert code == 3
    assert report["verdict"] == "FAIL"


def test_evaluate_broken_contract_exit3(tmp_path):
    repo = _build_repo(tmp_path, md_kwargs={"raw": "```json\n{ broken,,, \n```\n"})
    report, code = _eval(repo)
    assert code == 3


def test_evaluate_missing_key_contract_exit3(tmp_path):
    c = _contract()
    del c["digest_inputs"]
    report, code = _eval(_build_repo(tmp_path, contract=c))
    assert code == 3


def test_invalid_contract_skips_other_sections(tmp_path):
    # contract 不正時は他検査を打ち切り、violation は invalid_contract のみ。
    repo = _build_repo(tmp_path, contract=None)
    report, _ = _eval(repo)
    assert _codes(report) == {"invalid_contract"}


# ═══════════════════ exit priority ═══════════════════
def test_priority_forbidden_over_drift(tmp_path):
    # forbidden(3) と manifest drift(1) 同時 → 最重 3。
    repo = _build_repo(tmp_path, codex_manifest=False)
    (repo[0] / ".agents" / "hooks").mkdir(parents=True)
    report, code = _eval(repo)
    assert code == 3
    assert {"forbidden_surface_present", "manifest_missing"} <= _codes(report)


def test_priority_conflict_over_drift(tmp_path):
    # name conflict(2) と marketplace drift(1) 同時 → 最重 2。
    repo = _build_repo(tmp_path, claude_name="myplugin", codex_name="x", marketplace=False)
    report, code = _eval(repo)
    assert code == 2
    assert {"manifest_name_conflict", "marketplace_missing"} <= _codes(report)


def test_priority_invalid_over_conflict(tmp_path):
    # digest missing(3) と name conflict(2) 同時 → 最重 3。
    repo = _build_repo(tmp_path, claude_name="myplugin", codex_name="x")
    (repo[3] / "task-graph.json").unlink()
    report, code = _eval(repo)
    assert code == 3


def test_priority_multiple_drifts_stay_one(tmp_path):
    repo = _build_repo(tmp_path, codex_manifest=False, marketplace=False)
    report, code = _eval(repo)
    assert code == 1
    assert len([v for v in report["violations"] if v["severity"] == 1]) >= 2


def test_priority_invalid_over_all(tmp_path):
    # forbidden(3)+conflict(2)+drift(1) が同時でも最重は 3。
    repo = _build_repo(tmp_path, claude_name="myplugin", codex_name="x", marketplace=False)
    (repo[0] / ".agents" / "agents").mkdir(parents=True)
    report, code = _eval(repo)
    assert code == 3


# ═══════════════════ main / CLI ═══════════════════
def _argv(repo, as_json=False):
    root, slug, cp, pd = repo
    argv = ["--repo-root", str(root), "--plugin-slug", slug, "--surface-contract", str(cp), "--plan-dir", str(pd)]
    if as_json:
        argv.append("--json")
    return argv


def test_main_pass_returns_zero(tmp_path, capsys):
    assert nsp.main(_argv(_build_repo(tmp_path))) == 0
    out = capsys.readouterr().out
    assert "verdict: PASS" in out


def test_main_json_pass(tmp_path, capsys):
    code = nsp.main(_argv(_build_repo(tmp_path), as_json=True))
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "PASS"
    assert payload["exit_code"] == 0


def test_main_json_has_all_required_keys(tmp_path, capsys):
    nsp.main(_argv(_build_repo(tmp_path), as_json=True))
    payload = json.loads(capsys.readouterr().out)
    for key in ("surfaces", "manifest_parity", "marketplace_parity", "trust", "digests", "consistency", "violations", "verdict", "exit_code"):
        assert key in payload


def test_main_drift_returns_one(tmp_path):
    assert nsp.main(_argv(_build_repo(tmp_path, codex_manifest=False))) == 1


def test_main_conflict_returns_two(tmp_path):
    assert nsp.main(_argv(_build_repo(tmp_path, claude_name="myplugin", codex_name="x"))) == 2


def test_main_invalid_contract_returns_three(tmp_path):
    assert nsp.main(_argv(_build_repo(tmp_path, contract=None))) == 3


def test_main_forbidden_returns_three(tmp_path):
    repo = _build_repo(tmp_path)
    (repo[0] / ".agents" / "agents").mkdir(parents=True)
    assert nsp.main(_argv(repo)) == 3


def test_main_missing_contract_returns_three(tmp_path):
    root, slug, _cp, pd = _build_repo(tmp_path)
    argv = ["--repo-root", str(root), "--plugin-slug", slug, "--surface-contract", str(root / "no.md"), "--plan-dir", str(pd)]
    assert nsp.main(argv) == 3


def test_main_human_output_contains_sections(tmp_path, capsys):
    nsp.main(_argv(_build_repo(tmp_path, codex_manifest=False)))
    out = capsys.readouterr().out
    assert "manifest_parity" in out
    assert "VIOLATION" in out


def test_main_json_digests_present(tmp_path, capsys):
    nsp.main(_argv(_build_repo(tmp_path), as_json=True))
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["digests"]) == 5


def test_main_stale_returns_one(tmp_path):
    assert nsp.main(_argv(_build_repo(tmp_path, n_routes=4, n_comps=3, n_refs=3))) == 1


# ═══════════════════ verdict / structure invariants ═══════════════════
def test_report_keys_present_on_evaluate(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    for key in ("contract", "surfaces", "manifest_parity", "marketplace_parity", "trust", "digests", "consistency", "violations", "verdict", "exit_code"):
        assert key in report


def test_verdict_pass_iff_exit_zero(tmp_path):
    report, code = _eval(_build_repo(tmp_path))
    assert (report["verdict"] == "PASS") == (code == 0)


def test_verdict_fail_on_drift(tmp_path):
    report, _ = _eval(_build_repo(tmp_path, marketplace=False))
    assert report["verdict"] == "FAIL"


def test_exit_code_matches_report_field(tmp_path):
    report, code = _eval(_build_repo(tmp_path, codex_manifest=False))
    assert report["exit_code"] == code


def test_all_surfaces_reported(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert len(report["surfaces"]) == len(_contract()["surfaces"])


def test_confirmed_surface_carries_owner_write_policy(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    skill = next(s for s in report["surfaces"] if s["key"] == "repo_skill")
    assert skill["owner"] == "repo-generator"
    assert skill["write_policy"] == "fingerprint-diff-only"


def test_contract_metadata_reported(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert report["contract"]["codex_cli_version"] == "0.144.0"
    assert report["contract"]["activation_semantics"] == _contract()["activation_semantics"]


def test_deferred_surface_not_flagged_as_unsupported(tmp_path):
    c = _contract()
    c["surfaces"][3]["classification"] = "deferred"  # agent → deferred
    report, code = _eval(_build_repo(tmp_path, contract=c))
    # deferred は unsupported projection 検査の対象外。
    assert "unsupported_projection" not in _codes(report)
    assert code == 0


def test_marketplace_path_reported(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    assert report["marketplace_parity"]["path"] == ".agents/plugins/marketplace.json"


def test_manifest_paths_reported(tmp_path):
    report, _ = _eval(_build_repo(tmp_path, slug="foo"))
    assert report["manifest_parity"]["claude_manifest"] == "plugins/foo/.claude-plugin/plugin.json"
    assert report["manifest_parity"]["codex_manifest"] == "plugins/foo/.codex-plugin/plugin.json"


def test_slug_variation_pass(tmp_path):
    report, code = _eval(_build_repo(tmp_path, slug="harness-creator"))
    assert code == 0


def test_digests_are_hex_sha256(tmp_path):
    report, _ = _eval(_build_repo(tmp_path))
    for dg in report["digests"].values():
        assert dg is not None
        int(dg, 16)  # 16 進として解釈可能
        assert len(dg) == 64
