"""Genuine functional tests for
plugins/harness-creator/skills/run-skill-update-notifier/scripts/notifier-check.py.

network/keychain/secret は無い (このスクリプトはローカル cache とファイル読みのみ)。
ただし CACHE_DIR/CACHE_PATH が ~/.cache/harness を指すため、全テストで
monkeypatch により tmp_path 配下へ差し替え、ユーザーの実 cache を一切汚さない。

検査対象:
- 純関数 _now_iso / _vprefix / _format_line / _is_fresh / _extract_latest_version /
  _installed_version / _load_cache / _save_cache
- サブコマンド cmd_cache_status / cmd_refresh / cmd_notify (in-process)
- main() のディスパッチ・--mode 互換・graceful degradation (例外で exit 0)

全 fixture は tmp_path 配下。
"""
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills"
          / "run-skill-update-notifier" / "scripts" / "notifier-check.py")

_SPEC = importlib.util.spec_from_file_location("notifier_check_s3", SCRIPT)
NC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(NC)


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """全テストで cache を tmp_path に隔離 (実 ~/.cache を絶対に触らない)。"""
    cache_dir = tmp_path / "cache" / "harness"
    monkeypatch.setattr(NC, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(NC, "CACHE_PATH", cache_dir / "version-snapshot.json")
    return cache_dir


# ===================== _now_iso =====================

def test_now_iso_is_parseable_utc():
    s = NC._now_iso()
    dt = datetime.fromisoformat(s)
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)


# ===================== _vprefix =====================

def test_vprefix_adds_prefix_once():
    assert NC._vprefix("1.2.3") == "v1.2.3"


def test_vprefix_does_not_double_prefix():
    assert NC._vprefix("v1.2.3") == "v1.2.3"


def test_vprefix_strips_whitespace():
    assert NC._vprefix("  1.0.0  ") == "v1.0.0"


# ===================== _format_line =====================

def test_format_line_diff_returns_notice():
    line = NC._format_line("1.0.0", "1.1.0")
    assert line == "(installed: v1.0.0 / latest: v1.1.0 — /skill-update で更新)"


def test_format_line_same_returns_empty():
    assert NC._format_line("1.0.0", "1.0.0") == ""


def test_format_line_same_with_whitespace_returns_empty():
    assert NC._format_line(" 1.0.0 ", "1.0.0") == ""


def test_format_line_missing_installed_empty():
    assert NC._format_line(None, "1.0.0") == ""


def test_format_line_missing_latest_empty():
    assert NC._format_line("1.0.0", None) == ""


def test_format_line_preserves_v_prefix_no_double():
    line = NC._format_line("v1.0.0", "v2.0.0")
    assert "vv" not in line
    assert "installed: v1.0.0" in line
    assert "latest: v2.0.0" in line


# ===================== _is_fresh =====================

def test_is_fresh_true_within_ttl():
    ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert NC._is_fresh({"last_refreshed_at": ts}) is True


def test_is_fresh_false_beyond_ttl():
    ts = (datetime.now(timezone.utc) - timedelta(hours=NC.TTL_HOURS + 1)).isoformat()
    assert NC._is_fresh({"last_refreshed_at": ts}) is False


def test_is_fresh_false_no_timestamp():
    assert NC._is_fresh({}) is False


def test_is_fresh_false_unparseable_timestamp():
    assert NC._is_fresh({"last_refreshed_at": "not-a-date"}) is False


# ===================== _load_cache / _save_cache =====================

def test_load_cache_absent_returns_empty():
    assert NC._load_cache() == {}


def test_save_then_load_roundtrip():
    NC._save_cache({"a": 1, "日本語": "値"})
    assert NC._load_cache() == {"a": 1, "日本語": "値"}


def test_load_cache_corrupt_json_returns_empty(_isolate_cache):
    _isolate_cache.mkdir(parents=True, exist_ok=True)
    (_isolate_cache / "version-snapshot.json").write_text("{not json", encoding="utf-8")
    assert NC._load_cache() == {}


def test_save_cache_handles_unwritable_dir(monkeypatch, capsys):
    # mkdir で例外を起こさせ graceful degradation (stderr に短文・例外伝播しない) を検査
    def boom(*a, **k):
        raise OSError("readonly")
    monkeypatch.setattr(NC.Path, "mkdir", boom)
    NC._save_cache({"x": 1})  # 例外が外に漏れない
    assert "cache save skipped" in capsys.readouterr().err


# ===================== _extract_latest_version =====================

def test_extract_version_simple(tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Changelog\n\n## [1.4.2] - 2026-06-01\n- fix\n", encoding="utf-8")
    assert NC._extract_latest_version(p) == "1.4.2"


def test_extract_version_with_v_prefix(tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("## v2.0.0\n", encoding="utf-8")
    assert NC._extract_latest_version(p) == "2.0.0"


def test_extract_version_takes_first_match(tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("## [3.1.0]\n## [2.0.0]\n", encoding="utf-8")
    assert NC._extract_latest_version(p) == "3.1.0"


def test_extract_version_prerelease_suffix(tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("## [1.2.3-rc1]\n", encoding="utf-8")
    assert NC._extract_latest_version(p) == "1.2.3-rc1"


def test_extract_version_none_when_no_heading(tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("plain text, no version heading\n", encoding="utf-8")
    assert NC._extract_latest_version(p) is None


def test_extract_version_missing_file_returns_none(tmp_path):
    assert NC._extract_latest_version(tmp_path / "nope.md") is None


# ===================== _installed_version =====================

def _plugin_with_version(tmp_path, version):
    pj = tmp_path / ".claude-plugin" / "plugin.json"
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text(json.dumps({"name": "p", "version": version}), encoding="utf-8")
    return tmp_path


def test_installed_version_reads_plugin_json(tmp_path):
    d = _plugin_with_version(tmp_path, "9.9.9")
    assert NC._installed_version(d) == "9.9.9"


def test_installed_version_no_manifest_returns_none(tmp_path):
    assert NC._installed_version(tmp_path) is None


def test_installed_version_corrupt_manifest_returns_none(tmp_path):
    pj = tmp_path / ".claude-plugin" / "plugin.json"
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text("{broken", encoding="utf-8")
    assert NC._installed_version(tmp_path) is None


def test_installed_version_missing_version_key_returns_none(tmp_path):
    pj = tmp_path / ".claude-plugin" / "plugin.json"
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text(json.dumps({"name": "p"}), encoding="utf-8")
    assert NC._installed_version(tmp_path) is None


# ===================== cmd_cache_status =====================

def test_cmd_cache_status_absent(capsys):
    assert NC.cmd_cache_status(None) == 0
    assert capsys.readouterr().out.strip() == "absent"


def test_cmd_cache_status_fresh(capsys):
    ts = datetime.now(timezone.utc).isoformat()
    NC._save_cache({"last_refreshed_at": ts, "plugins": {}})
    assert NC.cmd_cache_status(None) == 0
    assert capsys.readouterr().out.strip() == "fresh"


def test_cmd_cache_status_stale(capsys):
    ts = (datetime.now(timezone.utc) - timedelta(hours=NC.TTL_HOURS + 5)).isoformat()
    NC._save_cache({"last_refreshed_at": ts, "plugins": {}})
    assert NC.cmd_cache_status(None) == 0
    assert capsys.readouterr().out.strip() == "stale"


# ===================== cmd_refresh =====================

class _Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_cmd_refresh_builds_snapshot(tmp_path):
    plugins = tmp_path / "plugins"
    # plugin A: changelog + plugin.json
    a = plugins / "alpha"
    (a / ".claude-plugin").mkdir(parents=True)
    (a / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "1.0.0"}), encoding="utf-8")
    (a / "CHANGELOG.md").write_text("## [1.1.0]\n", encoding="utf-8")
    # plugin B: no changelog, no manifest
    b = plugins / "beta"
    b.mkdir(parents=True)

    assert NC.cmd_refresh(_Args(plugins_root=str(plugins))) == 0
    cache = NC._load_cache()
    assert "last_refreshed_at" in cache
    assert cache["plugins"]["alpha"] == {"installed": "1.0.0", "latest": "1.1.0"}
    assert cache["plugins"]["beta"] == {"installed": None, "latest": None}


def test_cmd_refresh_empty_root(tmp_path):
    plugins = tmp_path / "empty-plugins"
    plugins.mkdir()
    assert NC.cmd_refresh(_Args(plugins_root=str(plugins))) == 0
    assert NC._load_cache()["plugins"] == {}


def test_cmd_refresh_includes_single_plugin_root(tmp_path):
    collection = tmp_path / "empty-collection"
    collection.mkdir()
    direct = _plugin_with_version(tmp_path / "marketplace" / "harness-creator", "1.2.3")
    (direct / "CHANGELOG.md").write_text("## [1.3.0]\n", encoding="utf-8")
    assert NC.cmd_refresh(_Args(
        plugins_root=str(collection), plugin_root=str(direct)
    )) == 0
    assert NC._load_cache()["plugins"]["harness-creator"] == {
        "installed": "1.2.3", "latest": "1.3.0"
    }


# ===================== cmd_notify =====================

def _seed_cache(plugin, installed, latest):
    NC._save_cache({
        "last_refreshed_at": NC._now_iso(),
        "plugins": {plugin: {"installed": installed, "latest": latest}},
    })


def test_cmd_notify_prints_when_outdated(capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")
    assert NC.cmd_notify(_Args(plugin="alpha")) == 0
    out = capsys.readouterr().out
    assert "installed: v1.0.0 / latest: v1.2.0" in out


def test_cmd_notify_silent_when_up_to_date(capsys):
    _seed_cache("alpha", "1.0.0", "1.0.0")
    assert NC.cmd_notify(_Args(plugin="alpha")) == 0
    assert capsys.readouterr().out == ""


def test_cmd_notify_suppressed_by_env(monkeypatch, capsys):
    monkeypatch.setenv(NC.SUPPRESS_ENV, "OFF")
    _seed_cache("alpha", "1.0.0", "9.9.9")
    assert NC.cmd_notify(_Args(plugin="alpha")) == 0
    assert capsys.readouterr().out == ""


def test_cmd_notify_no_cache(capsys):
    assert NC.cmd_notify(_Args(plugin="alpha")) == 0
    assert capsys.readouterr().out == ""


def test_cmd_notify_unknown_plugin(capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")
    assert NC.cmd_notify(_Args(plugin="ghost")) == 0
    assert capsys.readouterr().out == ""


def test_cmd_notify_format_not_implemented_noop(monkeypatch, capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")

    def raise_ni(*a, **k):
        raise NotImplementedError
    monkeypatch.setattr(NC, "_format_line", raise_ni)
    assert NC.cmd_notify(_Args(plugin="alpha")) == 0
    assert capsys.readouterr().out == ""


def test_cmd_notify_format_generic_exception_noop(monkeypatch, capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")

    def boom(*a, **k):
        raise ValueError("bad")
    monkeypatch.setattr(NC, "_format_line", boom)
    assert NC.cmd_notify(_Args(plugin="alpha")) == 0
    assert "format skipped" in capsys.readouterr().err


# ===================== main() in-process =====================

def test_main_cache_status(capsys):
    assert NC.main(["cache-status"]) == 0
    assert capsys.readouterr().out.strip() == "absent"


def test_main_mode_compat_prefix(capsys):
    # --mode cache-status の互換形式
    assert NC.main(["--mode", "cache-status"]) == 0
    assert capsys.readouterr().out.strip() == "absent"


def test_main_refresh(tmp_path):
    plugins = tmp_path / "plugins"
    (plugins / "alpha").mkdir(parents=True)
    assert NC.main(["refresh", "--plugins-root", str(plugins)]) == 0
    assert "alpha" in NC._load_cache()["plugins"]


def test_main_notify_outdated(capsys):
    _seed_cache("alpha", "1.0.0", "2.0.0")
    assert NC.main(["notify", "--plugin", "alpha"]) == 0
    assert "latest: v2.0.0" in capsys.readouterr().out


def test_main_dispatch_exception_is_noop(monkeypatch, capsys):
    # dispatch 内例外を握りつぶし exit 0 (graceful degradation)
    def boom(_args):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(NC, "cmd_cache_status", boom)
    assert NC.main(["cache-status"]) == 0
    assert "no-op: kaboom" in capsys.readouterr().err


def test_main_requires_subcommand_exits_nonzero():
    # subparser required=True なので引数なしは SystemExit(2)
    with pytest.raises(SystemExit) as ei:
        NC.main([])
    assert ei.value.code == 2


def test_main_via_argv_default(monkeypatch, capsys):
    # argv=None 経路 (sys.argv 参照) を踏む
    monkeypatch.setattr(sys, "argv", ["notifier-check.py", "cache-status"])
    assert NC.main() == 0
    assert capsys.readouterr().out.strip() == "absent"
