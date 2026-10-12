"""Genuine functional tests for
plugins/harness-creator/skills/run-skill-update-notifier/scripts/notifier-check.py.

network/keychain/secret は無い (このスクリプトはローカル cache とファイル読みのみ)。
ただし CACHE_DIR/CACHE_PATH が ~/.cache/harness を指すため、全テストで
monkeypatch により tmp_path 配下へ差し替え、ユーザーの実 cache を一切汚さない。

検査対象:
- 純関数 _now_iso / _vprefix / _format_line / _is_fresh / _extract_latest_version /
  _installed_version / _load_cache / _save_cache
- 書式の正本 references/output-format.md の「例」の表と _format_line の出力の一致
- サブコマンド cmd_cache_status / cmd_refresh / cmd_notify (in-process)
- cmd_notify の --session-id による重複抑止 (同じ session・同じ plugin は 1 回)
- main() のディスパッチ・--mode 互換・graceful degradation (例外で exit 0)
- SKILL.md Key Rules に並べた標準ライブラリと scripts/ の実際の import の一致
- IN3 (AST 検査): scripts/ の書き込みは version-snapshot.json だけで、hook が起動するのは
  notifier-check.py だけ

全 fixture は tmp_path 配下。
"""
import ast
import importlib.util
import json
import sys
from collections import Counter
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


def test_vprefix_normalizes_uppercase_v():
    assert NC._vprefix("V1.2.3") == "v1.2.3"


# ===================== _format_line =====================

# 食い違いの向きごとの文言 (正本は references/output-format.md)
MANIFEST_BEHIND = "plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)"
CHANGELOG_BEHIND = "CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)"
NOT_COMPARABLE = "版を比べられない)"


def test_format_line_changelog_newer_says_manifest_behind():
    line = NC._format_line("1.0.0", "1.1.0")
    assert line == f"(plugin.json: v1.0.0 / CHANGELOG: v1.1.0 — {MANIFEST_BEHIND}"


def test_format_line_same_returns_empty():
    assert NC._format_line("1.0.0", "1.0.0") == ""


def test_format_line_same_with_whitespace_returns_empty():
    assert NC._format_line(" 1.0.0 ", "1.0.0") == ""


def test_format_line_missing_installed_empty():
    assert NC._format_line(None, "1.0.0") == ""


def test_format_line_missing_latest_empty():
    assert NC._format_line("1.0.0", None) == ""


@pytest.mark.parametrize("installed,latest", [
    # repo 実測の 3 件 (2026-10-10 21:34 測定)。いずれも plugin.json の version が
    # CHANGELOG 先頭より新しい = CHANGELOG の節の足し忘れ
    ("0.2.15", "0.2.0"),    # extract-system-blueprint
    ("1.4.45", "1.2.0"),    # harness-creator
    ("0.1.21", "0.1.2"),    # skill-intake
])
def test_format_line_manifest_newer_says_changelog_behind(installed, latest):
    assert NC._format_line(installed, latest) == (
        f"(plugin.json: v{installed} / CHANGELOG: v{latest} — {CHANGELOG_BEHIND}")


@pytest.mark.parametrize("older,newer", [
    # 文字列比較だと "0.10.0" < "0.9.0" が真になり向きが逆転する桁数差
    ("0.9.0", "0.10.0"),
    ("1.9.9", "1.10.0"),
    ("1.2.0-rc1", "1.2.0"),     # prerelease < release (semver 11)
    ("1.2.0-rc1", "1.2.0-rc2"),
    # 数値識別子はドットで区切られたときだけ数値として比較される。"rc2"/"rc10" は
    # 英数識別子なので semver では ASCII 順 ("rc10" < "rc2") が正しい。
    ("1.2.0-rc.2", "1.2.0-rc.10"),
])
def test_format_line_orders_by_semver_not_string(older, newer):
    assert NC._format_line(older, newer).endswith(MANIFEST_BEHIND)
    assert NC._format_line(newer, older).endswith(CHANGELOG_BEHIND)


def test_format_line_two_digit_minor_is_newer_than_one_digit():
    # 文字列比較 ("0.10.0" < "0.9.0" が真) に戻ると、この 2 本が入れ替わって落ちる
    assert NC._format_line("0.9.0", "0.10.0") == (
        f"(plugin.json: v0.9.0 / CHANGELOG: v0.10.0 — {MANIFEST_BEHIND}")
    assert NC._format_line("0.10.0", "0.9.0") == (
        f"(plugin.json: v0.10.0 / CHANGELOG: v0.9.0 — {CHANGELOG_BEHIND}")


def test_format_line_uppercase_v_is_same_version():
    # 大文字 V も表記差として扱う (semver として読めずに「比べられない」へ倒れない)
    assert NC._format_line("V1.0.0", "1.0.0") == ""
    assert NC._format_line("V1.0.0", "1.1.0") == (
        f"(plugin.json: v1.0.0 / CHANGELOG: v1.1.0 — {MANIFEST_BEHIND}")
    assert NC._format_line("V1.1.0", "1.0.0") == (
        f"(plugin.json: v1.1.0 / CHANGELOG: v1.0.0 — {CHANGELOG_BEHIND}")


@pytest.mark.parametrize("installed,latest,expected", [
    # semver として読めない値は向きを決めず、どちらが古いとも言わない。
    # 読めない値は書かれたまま出す (v を付けると版として読めたように見える)
    ("1.0", "1.0.0", "(plugin.json: 1.0 / CHANGELOG: v1.0.0 — 版を比べられない)"),
    ("dev", "1.2.0", "(plugin.json: dev / CHANGELOG: v1.2.0 — 版を比べられない)"),
    ("1.2.0", "1.2", "(plugin.json: v1.2.0 / CHANGELOG: 1.2 — 版を比べられない)"),
])
def test_format_line_unparseable_version_is_not_comparable(installed, latest, expected):
    assert NC._format_line(installed, latest) == expected


def test_format_line_v_prefix_only_notation_difference_is_silent():
    # 版として等しく表記だけが違う場合は通知しない
    assert NC._format_line("1.0.0", "v1.0.0") == ""


def test_format_line_preserves_v_prefix_no_double():
    line = NC._format_line("v1.0.0", "v2.0.0")
    assert "vv" not in line
    assert "plugin.json: v1.0.0" in line
    assert "CHANGELOG: v2.0.0" in line


def _output_format_examples():
    """references/output-format.md の「例」の表を (installed, latest, 出力) の列で返す。"""
    text = (SCRIPT.parents[1] / "references" / "output-format.md").read_text(encoding="utf-8")
    section = text.split("\n## 例\n", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("installed", "---"):
            continue
        installed, latest = (None if c == "null" else c for c in (x.strip("`") for x in cells[:2]))
        expected = "" if cells[2] == "(空)" else cells[2].split("`")[1]
        rows.append((installed, latest, expected))
    return rows


def test_output_format_examples_match_format_line():
    """書式の正本 (output-format.md) の例と実装が食い違わない。"""
    rows = _output_format_examples()
    assert len(rows) == 14
    for installed, latest, expected in rows:
        assert NC._format_line(installed, latest) == expected, (installed, latest)


def test_no_update_guidance_left_in_skill():
    """順方向は作者の上げ忘れなので、利用者に更新を促す文言と旧 status 名を残さない。

    offline はネットワークに出ないので到達しない status として外した。
    """
    skill_dir = SCRIPT.parents[1]
    for path in sorted(skill_dir.rglob("*")):
        if path.suffix in (".md", ".py", ".json", ".yaml") and "__pycache__" not in path.parts:
            text = path.read_text(encoding="utf-8")
            for stale in ("/skill-update", "update-available", "up-to-date", "offline", "表示先は"):
                assert stale not in text, f"{path.relative_to(skill_dir)}: {stale}"


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


def _spy_replace(monkeypatch):
    """Path.replace の呼び出し元 (一時ファイル) の名前を記録する。"""
    used = []
    real = NC.Path.replace

    def spy(self, target):
        used.append(self.name)
        return real(self, target)
    monkeypatch.setattr(NC.Path, "replace", spy)
    return used


def test_save_cache_temp_name_differs_per_call(monkeypatch, _isolate_cache):
    """同時に動いた 2 つが同じ一時ファイルを書き合わないよう、名前は呼び出しごとに変わる。"""
    _isolate_cache.mkdir(parents=True)
    # 固定名だった頃の一時ファイル (別プロセスが書き途中のもの) には触れない
    (_isolate_cache / "version-snapshot.tmp").write_text("other", encoding="utf-8")
    used = _spy_replace(monkeypatch)
    NC._save_cache({"a": 1})
    NC._save_cache({"a": 2})
    assert len(used) == 2 and used[0] != used[1]
    assert "version-snapshot.tmp" not in used
    assert all(n.startswith("version-snapshot.") and n.endswith(".tmp") for n in used)
    assert NC._load_cache() == {"a": 2}
    assert sorted(p.name for p in _isolate_cache.iterdir()) == [
        "version-snapshot.json", "version-snapshot.tmp"]
    assert (_isolate_cache / "version-snapshot.tmp").read_text(encoding="utf-8") == "other"


def _fail_replace(monkeypatch):
    def boom(self, target):
        raise OSError("replace failed")
    monkeypatch.setattr(NC.Path, "replace", boom)


@pytest.mark.parametrize("data,breaker", [
    ({"x": object()}, None),            # 書き込みの途中で失敗 (JSON にできない値)
    ({"x": 1}, _fail_replace),          # 置き換えで失敗
])
def test_save_cache_failure_leaves_no_temp_file(monkeypatch, capsys, _isolate_cache, data, breaker):
    NC._save_cache({"keep": True})
    if breaker:
        breaker(monkeypatch)
    NC._save_cache(data)  # 例外が外に漏れない
    assert "cache save skipped" in capsys.readouterr().err
    assert sorted(p.name for p in _isolate_cache.iterdir()) == ["version-snapshot.json"]
    assert NC._load_cache() == {"keep": True}  # 前の記録は壊れない


def test_save_cache_keeps_temp_file_it_did_not_create(monkeypatch, capsys, _isolate_cache):
    """名前が衝突したら書かずに諦め、相手の一時ファイルは消さない。"""
    monkeypatch.setattr(NC.os, "urandom", lambda n: b"\x00" * n)
    used = _spy_replace(monkeypatch)
    NC._save_cache({"a": 1})
    other = _isolate_cache / used[0]
    other.write_text("other", encoding="utf-8")
    NC._save_cache({"a": 2})
    assert "cache save skipped" in capsys.readouterr().err
    assert other.read_text(encoding="utf-8") == "other"
    assert NC._load_cache() == {"a": 1}


def test_cmd_notify_prints_and_exits_zero_when_cache_replace_fails(monkeypatch, capsys, _isolate_cache):
    """cache は読めるが置き換えられない: 通知は出し、記録だけを飛ばし、一時ファイルを残さない。"""
    _seed_cache("alpha", "1.0.0", "1.2.0")
    _fail_replace(monkeypatch)
    assert NC.main(["notify", "--plugin", "alpha", "--session-id", "s1"]) == 0
    captured = capsys.readouterr()
    assert "CHANGELOG: v1.2.0" in captured.out
    assert "cache save skipped" in captured.err
    assert sorted(p.name for p in _isolate_cache.iterdir()) == ["version-snapshot.json"]
    assert "notified" not in NC._load_cache()


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

def _plugin_with_version(tmp_path, version, name="p"):
    pj = tmp_path / ".claude-plugin" / "plugin.json"
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
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


def test_cmd_refresh_keeps_notified_records(tmp_path):
    # refresh で通知済みの記録が消えると、TTL を跨いだ session で同じ通知が再び出る
    NC._save_cache({"last_refreshed_at": "x", "plugins": {},
                    "notified": {"alpha": {"session_id": "s1", "last_notified_at": "t"}}})
    plugins = tmp_path / "plugins"
    (plugins / "alpha").mkdir(parents=True)
    assert NC.cmd_refresh(_Args(plugins_root=str(plugins))) == 0
    assert NC._load_cache()["notified"] == {
        "alpha": {"session_id": "s1", "last_notified_at": "t"}}


def test_cmd_refresh_includes_single_plugin_root(tmp_path):
    collection = tmp_path / "empty-collection"
    collection.mkdir()
    direct = _plugin_with_version(tmp_path / "marketplace" / "harness-creator", "1.2.3",
                                  name="harness-creator")
    (direct / "CHANGELOG.md").write_text("## [1.3.0]\n", encoding="utf-8")
    assert NC.cmd_refresh(_Args(
        plugins_root=str(collection), plugin_root=str(direct)
    )) == 0
    assert NC._load_cache()["plugins"]["harness-creator"] == {
        "installed": "1.2.3", "latest": "1.3.0"
    }


# ===================== cmd_refresh: install 先の版ディレクトリ =====================

def _install_cache(tmp_path, versions, *, changelog_head="1.2.0"):
    """install 先 ~/.claude/plugins/cache/<marketplace>/<name>/<version>/ の形を作り、
    hook-cache-refresh.py が --plugins-root に渡す親 (<name>/) を返す。"""
    parent = tmp_path / "plugins-cache" / "harness-local" / "harness-creator"
    for version in versions:
        d = _plugin_with_version(parent / version, version, name="harness-creator")
        (d / "CHANGELOG.md").write_text(
            f"## [Unreleased]\n\n## [{changelog_head}]\n", encoding="utf-8")
    return parent


def test_refresh_keys_install_cache_by_manifest_name(tmp_path, capsys):
    # key がディレクトリ名だと版名 (1.4.30 など) になり、notify --plugin harness-creator が
    # 常に無出力になる
    parent = _install_cache(tmp_path, ["1.4.30", "1.4.42", "1.4.43"])
    assert NC.main(["refresh", "--plugins-root", str(parent),
                    "--plugin-root", str(parent / "1.4.43")]) == 0
    assert set(NC._load_cache()["plugins"]) == {"harness-creator"}
    assert NC.main(["notify", "--plugin", "harness-creator"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"(plugin.json: v1.4.43 / CHANGELOG: v1.2.0 — {CHANGELOG_BEHIND}"]


def test_refresh_prefers_plugin_root_over_newer_version_dir(tmp_path):
    parent = _install_cache(tmp_path, ["1.4.42", "1.4.43"])
    assert NC.cmd_refresh(_Args(plugins_root=str(parent),
                                plugin_root=str(parent / "1.4.42"))) == 0
    assert NC._load_cache()["plugins"]["harness-creator"]["installed"] == "1.4.42"


def test_refresh_without_plugin_root_takes_largest_semver(tmp_path):
    # パスの辞書順なら最後は "zz-dev" と "1.4.9"。semver として読めて最大の 1.4.43 を採る
    parent = _install_cache(tmp_path, ["1.4.9", "1.4.30", "1.4.43"])
    _plugin_with_version(parent / "zz-dev", "dev", name="harness-creator")
    assert NC.cmd_refresh(_Args(plugins_root=str(parent))) == 0
    assert NC._load_cache()["plugins"]["harness-creator"] == {
        "installed": "1.4.43", "latest": "1.2.0"}


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
    assert "plugin.json: v1.0.0 / CHANGELOG: v1.2.0" in out


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


def test_cmd_notify_same_session_notifies_once(capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")
    assert NC.cmd_notify(_Args(plugin="alpha", session_id="s1")) == 0
    assert "CHANGELOG: v1.2.0" in capsys.readouterr().out
    record = NC._load_cache()["notified"]["alpha"]
    assert record["session_id"] == "s1"
    datetime.fromisoformat(record["last_notified_at"])  # 時刻として読める
    assert NC.cmd_notify(_Args(plugin="alpha", session_id="s1")) == 0
    assert capsys.readouterr().out == ""


def test_cmd_notify_new_session_notifies_again(capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")
    NC.cmd_notify(_Args(plugin="alpha", session_id="s1"))
    capsys.readouterr()
    assert NC.cmd_notify(_Args(plugin="alpha", session_id="s2")) == 0
    assert "CHANGELOG: v1.2.0" in capsys.readouterr().out
    assert NC._load_cache()["notified"]["alpha"]["session_id"] == "s2"


def test_cmd_notify_dedup_is_per_plugin(capsys):
    NC._save_cache({
        "last_refreshed_at": NC._now_iso(),
        "plugins": {"alpha": {"installed": "1.0.0", "latest": "1.2.0"},
                    "beta": {"installed": "2.0.0", "latest": "2.1.0"}},
    })
    NC.cmd_notify(_Args(plugin="alpha", session_id="s1"))
    capsys.readouterr()
    assert NC.cmd_notify(_Args(plugin="beta", session_id="s1")) == 0
    assert "CHANGELOG: v2.1.0" in capsys.readouterr().out


def test_cmd_notify_without_session_id_notifies_every_time(capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")
    for _ in range(2):
        assert NC.cmd_notify(_Args(plugin="alpha")) == 0
        assert "CHANGELOG: v1.2.0" in capsys.readouterr().out
    assert "notified" not in NC._load_cache()


def test_cmd_notify_silent_line_is_not_recorded(capsys):
    # 通知を出していない (版が同じ) ときは通知済みにしない
    _seed_cache("alpha", "1.0.0", "1.0.0")
    assert NC.cmd_notify(_Args(plugin="alpha", session_id="s1")) == 0
    assert capsys.readouterr().out == ""
    assert "notified" not in NC._load_cache()


def test_cmd_notify_prints_even_if_record_cannot_be_saved(monkeypatch, capsys):
    _seed_cache("alpha", "1.0.0", "1.2.0")

    def boom(*a, **k):
        raise OSError("readonly")
    monkeypatch.setattr(NC.Path, "mkdir", boom)
    assert NC.cmd_notify(_Args(plugin="alpha", session_id="s1")) == 0
    captured = capsys.readouterr()
    assert "CHANGELOG: v1.2.0" in captured.out
    assert "cache save skipped" in captured.err


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
    assert "CHANGELOG: v2.0.0" in capsys.readouterr().out


def test_main_notify_session_id_option(capsys):
    _seed_cache("alpha", "1.0.0", "2.0.0")
    assert NC.main(["notify", "--plugin", "alpha", "--session-id=s1"]) == 0
    assert "CHANGELOG: v2.0.0" in capsys.readouterr().out
    assert NC.main(["notify", "--plugin", "alpha", "--session-id", "s1"]) == 0
    assert capsys.readouterr().out == ""


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


# ===================== SKILL.md の標準ライブラリ一覧 =====================

def test_skill_md_stdlib_list_matches_script_imports():
    """Key Rules「Python stdlib のみ」に並べた名前と scripts/ の import が一致する。"""
    import re

    skill_dir = SCRIPT.parents[1]
    imported: set[str] = set()
    for script in sorted((skill_dir / "scripts").glob("*.py")):
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
    imported.discard("__future__")
    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)

    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if "**Python stdlib のみ**" in l)
    listed = set(re.findall(r"`([a-z_][a-z0-9_.]*)`", line.split("(", 1)[1].split(")", 1)[0]))
    assert listed == imported


# ===================== IN3: 書き込み先は version-snapshot.json だけ =====================
# 使う module の集合は上の stdlib 一覧の検査で固定されている。ここではその中で書き込みと
# 別プロセスの起動ができる os・shutil・subprocess を、別名・from-import を解いて追う。

_WRITE_METHODS = {"write_text", "write_bytes", "touch", "mkdir", "unlink", "rmdir",
                  "symlink_to", "hardlink_to", "chmod"}
# Path.replace(dst) / Path.rename(dst) は引数 1 つ。str.replace(old, new) は 2 つなので外れる
_MOVE_METHODS = {"replace", "rename"}
# os の書き込み関数。値は書き込み先になる位置引数の数と、同じ引数の keyword 名
_OS_WRITE_FUNCS = {
    **dict.fromkeys(("replace", "rename", "renames", "symlink", "link"),
                    (2, {"src", "dst", "old", "new"})),
    **dict.fromkeys(("remove", "removedirs", "unlink", "makedirs", "mkdir", "rmdir", "chmod",
                     "chown", "truncate", "utime", "mkfifo", "mknod", "open"),
                    (1, {"path", "name"})),
}
# os.open はこの flag のどれかが付くと書き込み (O_RDONLY などだけなら読み取り)
_OS_OPEN_WRITE_FLAGS = {"O_WRONLY", "O_RDWR", "O_CREAT", "O_APPEND", "O_TRUNC"}
_WATCHED_MODULES = ("os", "shutil", "subprocess")
# 別プロセスを起動する os の関数 (subprocess は全関数を起動とみなす)
_OS_LAUNCH_FUNCS = {"system", "popen"}
_OS_LAUNCH_PREFIXES = ("exec", "spawn", "posix_spawn")
# notifier-check.py の起動に付けてよい keyword (何を・どこで・どの環境で起動するかを変えないもの)
_LAUNCH_KEYWORDS = {"capture_output", "text", "timeout", "check", "input", "encoding", "errors"}
# 書き込みと起動の呼び出しの固定 (検査が空振りしていないことの確認も兼ねる)
_EXPECTED_SIDE_EFFECTS = {
    "notifier-check.py": ["mkdir", "open", "replace", "unlink"],
    "hook-cache-refresh.py": ["subprocess.run", "subprocess.run"],
    "hook-notify-skill-end.py": ["subprocess.run"],
}


def _module_names(tree):
    """監視する module の別名と、from-import で取り込んだ名前を解く。

    返り値は ({名前: module}, {名前: (module, 関数名)})。`import os as o` は o → os、
    `from os import replace as r` は r → (os, replace)。
    """
    modules = {m: m for m in _WATCHED_MODULES}
    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _WATCHED_MODULES:
                    modules[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in _WATCHED_MODULES:
            for alias in node.names:
                funcs[alias.asname or alias.name] = (node.module, alias.name)
    return modules, funcs


def _resolve(func, modules, funcs):
    """呼び出し先が監視する module の関数なら (module, 関数名)、そうでなければ None。"""
    if isinstance(func, ast.Name):
        return funcs.get(func.id)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        module = modules.get(func.value.id)
        return (module, func.attr) if module else None
    return None


def _targets(call, count, names):
    """書き込み先の式。位置引数の先頭 count 個と、同じ引数を keyword で渡したもの。

    読めない呼び出し (`**kw` だけで渡すなど) は、呼び出しそのものを返して違反にする。
    """
    found = call.args[:count] + [k.value for k in call.keywords
                                 if k.arg is None or k.arg in names]
    return found or [call]


def _os_open_writes(call, modules):
    """os.open の flags に書き込みの flag が付く (または静的に読めない) なら真。"""
    flags = call.args[1] if len(call.args) > 1 else next(
        (k.value for k in call.keywords if k.arg == "flags"), None)
    if flags is None:
        return True
    for node in ast.walk(flags):
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Name):
            if node.id in modules:
                continue  # `os.O_RDONLY` の `os`
            name = node.id
        elif isinstance(node, (ast.BinOp, ast.operator, ast.expr_context)):
            continue
        else:
            return True  # 数値・呼び出しなど、値を静的に読めない flag
        if name in _OS_OPEN_WRITE_FLAGS or not name.startswith("O_"):
            return True  # 書き込みの flag か、flag を入れた変数
    return False


def _open_mode(call, pos):
    if len(call.args) > pos:
        return call.args[pos]
    return next((k.value for k in call.keywords if k.arg == "mode"), None)


def _is_write_mode(mode):
    if mode is None:
        return False  # 既定は "r"
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return bool(set(mode.value) & set("wax+"))
    return True  # 実行時に決まる mode は書き込みとみなす


def _write_calls(tree):
    """書き込み呼び出しごとに (行, 呼び出し名, 書き込み先の式の列) を返す。"""
    modules, funcs = _module_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        resolved = _resolve(node.func, modules, funcs)
        if resolved:
            module, name = resolved
            if module == "shutil":
                yield node.lineno, f"shutil.{name}", _targets(
                    node, 2, {"src", "dst", "path", "base_name", "filename", "extract_dir"})
            elif module == "os" and name in _OS_WRITE_FUNCS and (
                    name != "open" or _os_open_writes(node, modules)):
                yield node.lineno, f"os.{name}", _targets(node, *_OS_WRITE_FUNCS[name])
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "open":
            if _is_write_mode(_open_mode(node, 1)):
                yield node.lineno, "open", _targets(node, 1, {"file"})
        elif isinstance(func, ast.Attribute):
            owner, attr = func.value, func.attr
            if attr in _WRITE_METHODS:
                yield node.lineno, attr, [owner]
            elif attr in _MOVE_METHODS and (
                    len(node.args) == 1 or any(k.arg == "target" for k in node.keywords)):
                yield node.lineno, attr, [owner, *_targets(node, 1, {"target"})]
            elif attr == "open" and _is_write_mode(_open_mode(node, 0)):
                yield node.lineno, attr, [owner]


def _launches(tree):
    """別プロセスを起動する呼び出しごとに (行, 呼び出し名, Call) を返す。"""
    modules, funcs = _module_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        resolved = _resolve(node.func, modules, funcs)
        if resolved and (resolved[0] == "subprocess" or resolved[0] == "os" and (
                resolved[1] in _OS_LAUNCH_FUNCS or resolved[1].startswith(_OS_LAUNCH_PREFIXES))):
            yield node.lineno, ".".join(resolved), node


def _module_consts(tree):
    """module 直下の `名前 = 式` を {名前: 式の文字列} で返す。"""
    return {node.targets[0].id: ast.unparse(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)}


def _notifier_pinned(tree):
    """NOTIFIER が同じディレクトリの notifier-check.py を指し、どこでも束ね直されていない。"""
    consts = _module_consts(tree)
    bindings = Counter(
        [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
        + [n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)])
    return (consts.get("HERE") == "Path(__file__).resolve().parent"
            and consts.get("NOTIFIER") == "HERE / 'notifier-check.py'"
            and bindings["HERE"] == 1 and bindings["NOTIFIER"] == 1)


def _launches_notifier(name, call, pinned):
    """`subprocess.run(["python3", str(NOTIFIER), ...], ...)` の形で notifier-check.py だけを起動する。"""
    if not (pinned and name == "subprocess.run" and len(call.args) == 1):
        return False
    if any(k.arg not in _LAUNCH_KEYWORDS for k in call.keywords):
        return False  # shell・executable・env・cwd・`**kw` は起動するものや環境を変えうる
    argv = call.args[0]
    return (isinstance(argv, ast.List) and len(argv.elts) >= 2
            and ast.unparse(argv.elts[0]) == "'python3'"
            and ast.unparse(argv.elts[1]) == "str(NOTIFIER)")


def _writes_outside_cache(source):
    """cache 以外へ書きうる呼び出しを `行: 呼び出し名(書き込み先)` の列で返す。

    cache のファイルとみなすのは CACHE_PATH と、CACHE_PATH.with_suffix(...) を束ねた
    変数 (atomic rename の一時ファイル) だけ。CACHE_DIR は mkdir の対象としてだけ許す。
    別プロセスは何を書くかを追えないので、notifier-check.py の起動のほかは違反にする。
    呼び出し先を静的に解けない使い方 (`from os import *`、`getattr(os, ...)` のように
    module を値として渡す、`__import__`・importlib) も違反にする。
    """
    tree = ast.parse(source)
    files = {"CACHE_PATH"}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func) == "CACHE_PATH.with_suffix"):
            files.add(node.targets[0].id)
    bad = []
    for lineno, name, targets in _write_calls(tree):
        for target in targets:
            if not (isinstance(target, ast.Name) and (
                    target.id in files or (name == "mkdir" and target.id == "CACHE_DIR"))):
                bad.append(f"{lineno}: {name}({ast.unparse(target)})")
    pinned = _notifier_pinned(tree)
    for lineno, name, call in _launches(tree):
        if not _launches_notifier(name, call, pinned):
            bad.append(f"{lineno}: {name}({', '.join(ast.unparse(a) for a in call.args)})")
    modules, _ = _module_names(tree)
    owners = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _WATCHED_MODULES and any(
                alias.name == "*" for alias in node.names):
            bad.append(f"{node.lineno}: from {node.module} import *")
        elif isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                (alias.name if isinstance(node, ast.Import) else node.module or "")
                .split(".")[0] == "importlib" for alias in node.names):
            bad.append(f"{node.lineno}: import importlib")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and (
                node.id == "__import__" or node.id in modules and id(node) not in owners):
            bad.append(f"{node.lineno}: {node.id}")
    return bad


def test_scripts_write_only_to_version_snapshot_cache():
    """IN3: scripts/ の書き込みは ~/.cache/harness/version-snapshot.json だけ。"""
    scripts = {path.name: path for path in (SCRIPT.parents[1] / "scripts").glob("*.py")}
    assert set(scripts) == set(_EXPECTED_SIDE_EFFECTS)
    for name, path in sorted(scripts.items()):
        source = path.read_text(encoding="utf-8")
        assert _writes_outside_cache(source) == [], name
        tree = ast.parse(source)
        found = [n for _, n, _ in _write_calls(tree)] + [n for _, n, _ in _launches(tree)]
        assert sorted(found) == _EXPECTED_SIDE_EFFECTS[name], name
    consts = _module_consts(ast.parse(SCRIPT.read_text(encoding="utf-8")))
    assert consts["CACHE_DIR"] == "Path.home() / '.cache' / 'harness'"
    assert consts["CACHE_PATH"] == "CACHE_DIR / 'version-snapshot.json'"


@pytest.mark.parametrize("name", ["hook-cache-refresh.py", "hook-notify-skill-end.py"])
def test_hook_scripts_launch_only_notifier_check(name):
    """hook が起動するのは同じディレクトリの notifier-check.py だけ (argv は python3 と NOTIFIER)。"""
    tree = ast.parse((SCRIPT.parent / name).read_text(encoding="utf-8"))
    assert _notifier_pinned(tree)
    launches = list(_launches(tree))
    assert launches
    for _, launch, call in launches:
        assert _launches_notifier(launch, call, pinned=True), ast.unparse(call)


_NOTIFIER_PRELUDE = 'HERE = Path(__file__).resolve().parent\nNOTIFIER = HERE / "notifier-check.py"\n'


@pytest.mark.parametrize("source", [
    'Path("plugin.json").write_text("{}")',
    'open(p, "w")',
    'open(p, mode="a")',
    'open(file=p, mode="w")',
    'p.open("w")',
    'os.replace(tmp, target)',
    'os.replace(src=tmp, dst=target)',
    'shutil.copy(a, b)',
    'CACHE_PATH.parent.write_text("")',
    'CACHE_DIR.write_text("")',
    'tmp.replace(other)',
    'tmp.replace(target=other)',
    # os.open は flags で読み書きが決まる
    'os.open(p, os.O_WRONLY | os.O_CREAT)',
    'os.open(p, os.O_RDWR)',
    'os.open(p, flags=os.O_APPEND)',
    'os.open(p, flags)',
    'os.open(p, 0o1101)',
    # 別名 import・from-import
    'from os import replace\nreplace(a, b)',
    'from os import open as o, O_CREAT\no(p, O_CREAT)',
    'from shutil import copy\ncopy(a, b)',
    'import shutil as sh\nsh.rmtree(d)',
    'import os as o\no.remove(p)',
    # 呼び出し先を静的に解けない使い方
    'from os import *\nreplace(a, b)',
    'getattr(os, "replace")(a, b)',
    '__import__("shutil").copy(a, b)',
    'import importlib\nimportlib.import_module("shutil").copy(a, b)',
    # 別プロセスの起動
    'subprocess.run(["cp", a, b])',
    'subprocess.run(cmd)',
    'from subprocess import run\nrun(["sh", "-c", "touch x"])',
    'import subprocess as sp\nsp.check_call(["touch", p])',
    'os.system("touch x")',
    'os.execv("/bin/sh", ["sh"])',
    'os.posix_spawn("/bin/sh", ["sh"], {})',
    _NOTIFIER_PRELUDE + 'subprocess.Popen(["python3", str(NOTIFIER)])',
    _NOTIFIER_PRELUDE + 'subprocess.run(["python3", str(NOTIFIER)], shell=True)',
    _NOTIFIER_PRELUDE + 'subprocess.run(["python3", str(NOTIFIER)], executable="/bin/sh")',
    _NOTIFIER_PRELUDE + 'subprocess.run(["python3", str(NOTIFIER)], env=env)',
    _NOTIFIER_PRELUDE + 'subprocess.run(["python3", str(NOTIFIER)], **kw)',
    _NOTIFIER_PRELUDE + 'subprocess.run(["sh", str(NOTIFIER)])',
    _NOTIFIER_PRELUDE + 'subprocess.run(["python3", str(OTHER)])',
    _NOTIFIER_PRELUDE + 'subprocess.run(argv)',
    _NOTIFIER_PRELUDE + 'NOTIFIER = Path("/tmp/x.py")\nsubprocess.run(["python3", str(NOTIFIER)])',
    _NOTIFIER_PRELUDE + 'def f(NOTIFIER):\n    subprocess.run(["python3", str(NOTIFIER)])',
    'HERE = Path(__file__).resolve().parent\nNOTIFIER = HERE / "other.py"\n'
    'subprocess.run(["python3", str(NOTIFIER)])',
])
def test_write_lint_flags_writes_outside_cache(source):
    assert _writes_outside_cache(source)


@pytest.mark.parametrize("source", [
    'open(p)',
    'open(p, "r")',
    '"a-b".replace("-", "_")',
    'p.read_text(errors="replace")',
    'tmp = CACHE_PATH.with_suffix(".tmp")\ntmp.write_text("")\ntmp.replace(CACHE_PATH)',
    'CACHE_DIR.mkdir(parents=True)',
    'os.environ.get("X")',
    'os.open(p, os.O_RDONLY)',
    'os.open(p, flags=os.O_RDONLY | os.O_CLOEXEC)',
    'os.open(CACHE_PATH, os.O_WRONLY | os.O_CREAT)',
    'from os import getenv\ngetenv("HOME")',
    'import os as o\no.environ.get("X")',
    _NOTIFIER_PRELUDE + 'subprocess.run(["python3", str(NOTIFIER), "notify", *args],\n'
    '               capture_output=True, text=True, timeout=5)',
])
def test_write_lint_allows_reads_and_cache_writes(source):
    assert _writes_outside_cache(source) == []
