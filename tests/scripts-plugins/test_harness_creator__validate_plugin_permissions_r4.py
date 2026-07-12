"""validate-plugin-permissions.py (PKG-013a〜d) を genuine に網羅する。

このスクリプトは plugins/<name>/.claude-plugin/plugin.json の permissions ブロックを読み、
ワイルドカード全許可 (Bash(*) / *) ・plugin root 外の絶対パス書込 ・network allowlist 全許可
・MCP scope ワイルドカード を検出する。network/keychain/secret には一切触れない純ローカル lint。

テスト方針:
  - 純関数 (load_permissions / check_013a〜d / now_iso) は実ファイルを importlib で
    ロードして実入力で検証する。
  - REPO_ROOT はモジュール定数 (parents[5]) なので main 経路では monkeypatch.setattr で
    tmp_path に差し替え、tmp に plugin.json fixture を置いて repo を汚さず駆動する。
  - main は argparse なので monkeypatch.setattr(sys, "argv", ...) で引数を与え、
    stdout を capsys で捕捉して JSON 構造・exit code を assert する。
  - 合格 fixture (違反なし -> pass/0) と各違反 fixture (013a/b/c/d 個別 -> fail/1) を網羅。

tests/scripts(2,3) と衝突しない _r4 名で in-process ロードする。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-plugin-package-check"
    / "scripts"
    / "validate-plugin-permissions.py"
)

_SPEC = importlib.util.spec_from_file_location("validate_plugin_permissions_r4", SCRIPT)
VPP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VPP)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _write_plugin_json(plugin_dir: Path, data: dict) -> Path:
    cp = plugin_dir / ".claude-plugin"
    cp.mkdir(parents=True, exist_ok=True)
    pj = cp / "plugin.json"
    pj.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return pj


def _run_main(monkeypatch, capsys, repo_root: Path, plugin: str, check: str | None = None):
    # REPO_ROOT module 定数は廃止。main() は --plugin-dir 明示時はそれを、未指定なら
    # _resolve_repo_root() ($CLAUDE_PROJECT_DIR→parents[5]→cwd) から plugins/<plugin> を解決する。
    # fixture は tmp_path/plugins/<plugin>/.claude-plugin/plugin.json を書くので、その plugin dir を
    # --plugin-dir で直接渡し、実 repo を汚さず完全 isolation で駆動する (dir 不在なら not_applicable)。
    plugin_dir = repo_root / "plugins" / plugin
    argv = ["prog", "--plugin", plugin, "--plugin-dir", str(plugin_dir)]
    if check is not None:
        argv += ["--check", check]
    monkeypatch.setattr(sys, "argv", argv)
    rc = VPP.main()
    out = capsys.readouterr().out
    return rc, json.loads(out)


# --------------------------------------------------------------------------
# now_iso
# --------------------------------------------------------------------------

def test_now_iso_format():
    s = VPP.now_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s)


# --------------------------------------------------------------------------
# load_permissions
# --------------------------------------------------------------------------

def test_load_permissions_missing_file_returns_none(tmp_path):
    assert VPP.load_permissions(tmp_path / "no-such-plugin") is None


def test_load_permissions_invalid_json_returns_none(tmp_path):
    cp = tmp_path / ".claude-plugin"
    cp.mkdir()
    (cp / "plugin.json").write_text("{not: valid", encoding="utf-8")
    assert VPP.load_permissions(tmp_path) is None


def test_load_permissions_non_dict_top_returns_none(tmp_path):
    _write_plugin_json(tmp_path, {})  # placeholder to make dir
    (tmp_path / ".claude-plugin" / "plugin.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert VPP.load_permissions(tmp_path) is None


def test_load_permissions_no_permissions_key_returns_empty(tmp_path):
    _write_plugin_json(tmp_path, {"name": "demo"})
    assert VPP.load_permissions(tmp_path) == {}


def test_load_permissions_extracts_block(tmp_path):
    _write_plugin_json(tmp_path, {"permissions": {"tools": ["Bash(git status)"]}})
    assert VPP.load_permissions(tmp_path) == {"tools": ["Bash(git status)"]}


# --------------------------------------------------------------------------
# check_013a: tool permission wildcard
# --------------------------------------------------------------------------

def test_013a_clean_no_findings():
    perms = {"tools": ["Bash(python3 *)", "Bash(git diff *)"]}
    assert VPP.check_013a(perms, "p") == []


def test_013a_flags_bash_star():
    findings = VPP.check_013a({"tools": ["Bash(*)"]}, "p")
    assert len(findings) == 1
    f = findings[0]
    assert f["pkg_id"] == "PKG-013a"
    assert f["severity"] == "P0"
    assert "Bash(*)" in f["evidence"]
    assert "permissions.tools[0]" in f["location"]


def test_013a_flags_global_star_and_indexes():
    findings = VPP.check_013a({"tools": ["Bash(git log)", "*"]}, "p")
    assert len(findings) == 1
    assert findings[0]["id"] == "F-PKG013a-002"
    assert "tools[1]" in findings[0]["location"]


def test_013a_perms_not_dict_no_crash():
    assert VPP.check_013a([], "p") == []


def test_013a_ignores_non_string_entries():
    assert VPP.check_013a({"tools": [{"x": 1}, None]}, "p") == []


# --------------------------------------------------------------------------
# check_013b: filesystem write outside plugin root
# --------------------------------------------------------------------------

def test_013b_clean_relative_paths():
    perms = {"filesystem": {"write": ["plugins/demo/out", "plugins/demo/eval-log"]}}
    assert VPP.check_013b(perms, "demo") == []


def test_013b_flags_absolute_outside_root():
    findings = VPP.check_013b({"filesystem": {"write": ["/etc/passwd"]}}, "demo")
    assert len(findings) == 1
    assert findings[0]["pkg_id"] == "PKG-013b"
    assert "/etc/passwd" in findings[0]["evidence"]


def test_013b_absolute_inside_plugin_root_allowed():
    # plugins/<plugin>/ で始まる絶対パスは許容 (startswith チェックの分岐)。
    perms = {"filesystem": {"write": ["plugins/demo/sub"]}}
    assert VPP.check_013b(perms, "demo") == []


def test_013b_fs_not_dict_no_crash():
    assert VPP.check_013b({"filesystem": "nope"}, "demo") == []


# --------------------------------------------------------------------------
# check_013c: network allowlist wildcard
# --------------------------------------------------------------------------

def test_013c_clean_specific_hosts():
    perms = {"network": {"allowlist": ["api.notion.com", "gbiz-info.go.jp"]}}
    assert VPP.check_013c(perms, "p") == []


def test_013c_flags_star():
    findings = VPP.check_013c({"network": {"allowlist": ["*"]}}, "p")
    assert len(findings) == 1
    assert findings[0]["pkg_id"] == "PKG-013c"


def test_013c_flags_cidr_all():
    findings = VPP.check_013c({"network": {"allowlist": ["api.x.com", "0.0.0.0/0"]}}, "p")
    assert len(findings) == 1
    assert "0.0.0.0/0" in findings[0]["evidence"]
    assert "allowlist[1]" in findings[0]["location"]


def test_013c_net_not_dict_no_crash():
    assert VPP.check_013c({"network": []}, "p") == []


# --------------------------------------------------------------------------
# check_013d: MCP scope wildcard
# --------------------------------------------------------------------------

def test_013d_clean_specific_scopes():
    perms = {"mcp": {"notion": ["read", "write"]}}
    assert VPP.check_013d(perms, "p") == []


def test_013d_flags_wildcard_scope():
    findings = VPP.check_013d({"mcp": {"drive": ["*"]}}, "p")
    assert len(findings) == 1
    assert findings[0]["pkg_id"] == "PKG-013d"
    assert "drive" in findings[0]["evidence"]


def test_013d_scopes_not_list_ignored():
    assert VPP.check_013d({"mcp": {"svc": "read"}}, "p") == []


def test_013d_mcp_not_dict_no_crash():
    assert VPP.check_013d({"mcp": []}, "p") == []


# --------------------------------------------------------------------------
# CHECKS registry
# --------------------------------------------------------------------------

def test_checks_registry_complete():
    assert set(VPP.CHECKS) == {"013a", "013b", "013c", "013d"}


# --------------------------------------------------------------------------
# main: end-to-end via REPO_ROOT monkeypatch
# --------------------------------------------------------------------------

def test_main_not_applicable_when_plugin_json_absent(monkeypatch, capsys, tmp_path):
    rc, out = _run_main(monkeypatch, capsys, tmp_path, "ghost")
    assert rc == 0
    assert out["status"] == "not_applicable"
    assert "permissions" in out["skip_reason"]
    assert out["pkg_id"] == "PKG-013"


def test_main_pass_when_permissions_clean(monkeypatch, capsys, tmp_path):
    pdir = tmp_path / "plugins" / "clean"
    _write_plugin_json(
        pdir,
        {
            "permissions": {
                "tools": ["Bash(python3 *)"],
                "filesystem": {"write": ["plugins/clean/out"]},
                "network": {"allowlist": ["api.notion.com"]},
                "mcp": {"notion": ["read"]},
            }
        },
    )
    rc, out = _run_main(monkeypatch, capsys, tmp_path, "clean")
    assert rc == 0
    assert out["status"] == "pass"
    assert set(out["sub_checks"]) == {"PKG-013a", "PKG-013b", "PKG-013c", "PKG-013d"}
    for sc in out["sub_checks"].values():
        assert sc["status"] == "pass"
        assert sc["findings"] == []


def test_main_fail_aggregates_all_violations(monkeypatch, capsys, tmp_path):
    pdir = tmp_path / "plugins" / "bad"
    _write_plugin_json(
        pdir,
        {
            "permissions": {
                "tools": ["Bash(*)"],
                "filesystem": {"write": ["/var/lib/x"]},
                "network": {"allowlist": ["*"]},
                "mcp": {"drive": ["*"]},
            }
        },
    )
    rc, out = _run_main(monkeypatch, capsys, tmp_path, "bad")
    assert rc == 1
    assert out["status"] == "fail"
    for sid in ("PKG-013a", "PKG-013b", "PKG-013c", "PKG-013d"):
        assert out["sub_checks"][sid]["status"] == "fail"
        assert out["sub_checks"][sid]["findings"]


def test_main_check_subset_and_unknown_sid_skipped(monkeypatch, capsys, tmp_path):
    pdir = tmp_path / "plugins" / "subset"
    _write_plugin_json(
        pdir,
        {"permissions": {"filesystem": {"write": ["/abs"]}, "tools": ["Bash(*)"]}},
    )
    # bogus は CHECKS に無いので skip され、013b のみ実行される。
    rc, out = _run_main(monkeypatch, capsys, tmp_path, "subset", check="013b,bogus")
    assert rc == 1
    assert set(out["sub_checks"]) == {"PKG-013b"}
    assert out["sub_checks"]["PKG-013b"]["status"] == "fail"


def test_main_empty_permissions_block_passes(monkeypatch, capsys, tmp_path):
    # permissions: {} は None でないので not_applicable には入らず、違反ゼロで pass。
    pdir = tmp_path / "plugins" / "emptyperms"
    _write_plugin_json(pdir, {"permissions": {}})
    rc, out = _run_main(monkeypatch, capsys, tmp_path, "emptyperms")
    assert rc == 0
    assert out["status"] == "pass"


# --------------------------------------------------------------------------
# main: subprocess smoke (sys.executable で実 CLI 起動・実通信なし)
# --------------------------------------------------------------------------

def test_main_subprocess_not_applicable(tmp_path):
    import subprocess

    env_root = tmp_path  # plugins/<name> が無いので not_applicable
    # REPO_ROOT は parents[5] 固定なので subprocess では実 repo を見る。実 repo に存在しない
    # plugin 名を渡し、permissions 未定義の安全経路 (not_applicable/0) を実行する。
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--plugin", "__nonexistent_plugin_r4__"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "not_applicable"
