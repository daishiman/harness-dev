"""ubm-write-path-guard.py (C04) の fail-closed 挙動テスト。

vault 配下の保護パス書込は許可/ブロックを正しく分岐し、vault 外・非対象ツールは
素通しすることを検証する。解釈不能 stdin / 対象 tool の file_path 欠落は
fail-closed(exit2) を検証し、manifest matcher ↔ hook GUARDED_TOOLS の契約一致も固定する。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOK = PLUGIN_ROOT / "hooks" / "ubm-write-path-guard.py"
MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"


def run(payload: dict, vault: str | None) -> int:
    env = {"PATH": "/usr/bin:/bin"}
    if vault is not None:
        env["UBM_VAULT_ROOT"] = vault
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), text=True, capture_output=True, env=env,
    ).returncode


def w(path: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path}}


def test_allow_goal_save(tmp_path: Path):
    vault = str(tmp_path)
    assert run(w(f"{vault}/05_Project/UBM/目標設定/UBM - 1-週報.md"), vault) == 0


def test_allow_daily_embed(tmp_path: Path):
    vault = str(tmp_path)
    assert run(w(f"{vault}/02_Configs/Templates/Daily.md"), vault) == 0


def test_block_other_vault_path(tmp_path: Path):
    vault = str(tmp_path)
    # vault 配下だが許可外 (移植元ソース) → fail-closed
    assert run(w(f"{vault}/05_Project/UBM/YouTube/2025-xx.md"), vault) == 2


def test_block_vault_config(tmp_path: Path):
    vault = str(tmp_path)
    assert run(w(f"{vault}/02_Configs/Daily/2026-07-05.md"), vault) == 2


def test_allow_outside_vault(tmp_path: Path):
    vault = str(tmp_path / "vault")
    # plugin 同梱 knowledge への書込は vault 外 → 素通し
    assert run(w(f"{tmp_path}/plugins/ubm-goal-setting/knowledge/principles.json"), vault) == 0


def test_allow_when_vault_unset(tmp_path: Path):
    # UBM_VAULT_ROOT 未設定 → 保護対象なしで全許可
    assert run(w(f"{tmp_path}/anything.md"), None) == 0


def test_ignore_non_write_tool(tmp_path: Path):
    vault = str(tmp_path)
    payload = {"tool_name": "Read", "tool_input": {"file_path": f"{vault}/05_Project/UBM/YouTube/x.md"}}
    assert run(payload, vault) == 0


def test_unparseable_input_blocked_fail_closed(tmp_path: Path):
    # 計画 C04 exit_semantics=fail-closed-exit2: 解釈不能 stdin は素通しでなく阻止
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json", text=True, capture_output=True,
        env={"PATH": "/usr/bin:/bin", "UBM_VAULT_ROOT": str(tmp_path)},
    )
    assert r.returncode == 2
    assert "fail-closed" in r.stderr


def test_missing_file_path_blocked_fail_closed(tmp_path: Path):
    # 対象 tool なのに file_path 欠落 → 検査不能を素通しせず阻止
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Write", "tool_input": {}}),
        text=True, capture_output=True,
        env={"PATH": "/usr/bin:/bin", "UBM_VAULT_ROOT": str(tmp_path)},
    )
    assert r.returncode == 2
    assert "fail-closed" in r.stderr


def test_edit_tool_also_guarded(tmp_path: Path):
    vault = str(tmp_path)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": f"{vault}/05_Project/UBM/合宿/rec.md"}}
    assert run(payload, vault) == 2


def test_multiedit_blocked_on_protected_path(tmp_path: Path):
    vault = str(tmp_path)
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": f"{vault}/05_Project/UBM/YouTube/2025-xx.md",
            "edits": [{"old_string": "a", "new_string": "b"}],
        },
    }
    assert run(payload, vault) == 2


def test_multiedit_allowed_on_goal_path(tmp_path: Path):
    vault = str(tmp_path)
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": f"{vault}/05_Project/UBM/目標設定/UBM - 1-週報.md",
            "edits": [{"old_string": "a", "new_string": "b"}],
        },
    }
    assert run(payload, vault) == 0


def test_manifest_matcher_matches_guarded_tools():
    """manifest matcher ↔ hook GUARDED_TOOLS の契約一致 (MultiEdit 脱落を捕捉)。

    mf-kessai test_plugin_contract.py の matcher 完全一致パターンを踏襲する。
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest["hooks"]["PreToolUse"]
    matchers = [e["matcher"] for e in entries if "ubm-write-path-guard.py" in e["hooks"][0]["command"]]
    assert len(matchers) == 1
    spec = importlib.util.spec_from_file_location("ubm_write_path_guard", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(matchers[0].split("|")) == mod.GUARDED_TOOLS
