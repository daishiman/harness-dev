"""scripts/lint-script-naming.py の genuine で網羅的な機能テスト (network 不要)。

28章 §4.1-§4.6 の script 命名規約を機械強制する lint。純関数 (classify /
find_scripts) と main(argv) の全分岐を in-process で網羅し (--cov=scripts 計上)、
subprocess で実 CLI の exit code / 出力も確認する。

カバー分岐:
- classify:
    OK (許可動詞 <verb>-<target>.py)
    VIOLATION banned name (check/run/main/utils/helper.py)
    VIOLATION underscore (§4.3)
    VIOLATION 形式不一致 (パターン非マッチ・アンダースコアなし)
    VIOLATION 動詞が許可外
    EXCEPTION adapters/ ディレクトリ (§4.6)
    EXCEPTION sink_*.py / *_helper.py / audit_*.py (§4.4)
    PENDING_RENAME 個別パス (PENDING_RENAME_PATHS)
    PENDING_RENAME hook-*.py prefix (PENDING_RENAME_PATTERNS)
- find_scripts: 非存在 root skip / SKIP_PARTS 除外 / scripts/ 配下 / scripts ルート直下
- main: report モード JSON / text モード / VIOLATION 検出時 exit 1 / クリーン時 exit 0
- CLI: 実 repo (--report) が exit 0、明示の違反 fixture で exit 1

network: false, keychain: なし, 実ファイル書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import pathlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-script-naming.py"

SPEC = importlib.util.spec_from_file_location("lint_script_naming_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _classify(posix: str):
    """posix 文字列を Path にして classify。PENDING_RENAME_PATHS は posix 完全一致。"""
    return MOD.classify(pathlib.Path(posix))


# ── classify: OK ────────────────────────────────────────────────────────────
def test_classify_ok_allowed_verb():
    status, reason = _classify("scripts/lint-foo-bar.py")
    assert status == "OK"
    assert reason is None


def test_classify_ok_each_allowed_verb():
    for verb in MOD.ALLOWED_VERBS:
        status, _ = _classify(f"scripts/{verb}-target.py")
        assert status == "OK", verb


# ── classify: VIOLATION banned name ─────────────────────────────────────────
@pytest.mark.parametrize("banned", sorted(MOD.BANNED_NAMES))
def test_classify_violation_banned_name(banned):
    status, reason = _classify(f"scripts/{banned}")
    assert status == "VIOLATION"
    assert "banned name" in reason


# ── classify: VIOLATION underscore ──────────────────────────────────────────
def test_classify_violation_underscore():
    # 例外節・PENDING に該当しない underscore 名。
    status, reason = _classify("scripts/some_random_module.py")
    assert status == "VIOLATION"
    assert "underscore" in reason


# ── classify: VIOLATION 形式不一致 (アンダースコアなし、動詞-構造でない) ──────
def test_classify_violation_no_match_no_underscore():
    status, reason = _classify("scripts/Foo.py")  # 大文字始まり -> パターン非マッチ
    assert status == "VIOLATION"
    assert "does not match" in reason


def test_classify_violation_single_token_no_hyphen():
    status, reason = _classify("scripts/foobar.py")  # ハイフンなし
    assert status == "VIOLATION"
    assert "does not match" in reason


# ── classify: VIOLATION 動詞が許可外 ────────────────────────────────────────
def test_classify_violation_disallowed_verb():
    status, reason = _classify("scripts/emit-thing.py")  # emit は許可外
    assert status == "VIOLATION"
    assert "not in allowed list" in reason
    assert "emit" in reason


# ── classify: EXCEPTION adapters/ (§4.6) ────────────────────────────────────
def test_classify_exception_adapters_dir():
    status, reason = _classify("plugins/x/adapters/weird_name.py")
    assert status == "EXCEPTION"
    assert "§4.6" in reason


# ── classify: EXCEPTION §4.4 各パターン ─────────────────────────────────────
def test_classify_exception_sink_pattern():
    status, reason = _classify("scripts/sink_notion.py")
    assert status == "EXCEPTION"
    assert "Sink" in reason


def test_classify_exception_helper_pattern():
    status, reason = _classify("scripts/secret_helper.py")
    assert status == "EXCEPTION"
    assert "helper" in reason.lower()


def test_classify_exception_audit_pattern():
    status, reason = _classify("scripts/audit_trail_log.py")
    assert status == "EXCEPTION"
    assert "audit" in reason.lower()


# ── classify: PENDING_RENAME 個別パス ───────────────────────────────────────
def test_classify_pending_rename_explicit_path():
    # PENDING_RENAME_PATHS に存在する既知のパスを 1 件使う。
    sample = next(iter(MOD.PENDING_RENAME_PATHS))
    status, reason = _classify(sample)
    assert status == "PENDING_RENAME"
    assert "legacy path" in reason


def test_classify_pending_rename_known_underscore_path():
    # underscore だが PENDING_RENAME_PATHS 登録済 → VIOLATION でなく PENDING。
    status, reason = _classify("scripts/feedback_contract_ssot.py")
    assert status == "PENDING_RENAME"


# ── classify: PENDING_RENAME hook-*.py prefix ───────────────────────────────
def test_classify_pending_rename_hook_prefix():
    # hook-*.py は PENDING_RENAME_PATTERNS でマッチ (個別パス未登録でも)。
    status, reason = _classify("scripts/hook-guard-newthing.py")
    assert status == "PENDING_RENAME"
    assert "hook-* prefix" in reason


# ── find_scripts ────────────────────────────────────────────────────────────
def test_find_scripts_missing_root_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = list(MOD.find_scripts(["does-not-exist"]))
    assert out == []


def test_find_scripts_scripts_root_direct(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "lint-a.py").write_text("x", encoding="utf-8")
    out = [p.name for p in MOD.find_scripts(["scripts"])]
    assert "lint-a.py" in out


def test_find_scripts_under_plugins_scripts_subdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "plugins" / "p" / "scripts"
    d.mkdir(parents=True)
    (d / "validate-x.py").write_text("x", encoding="utf-8")
    out = [p.as_posix() for p in MOD.find_scripts(["plugins"])]
    assert any(o.endswith("plugins/p/scripts/validate-x.py") for o in out)


def test_find_scripts_skips_pycache_and_node_modules(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = tmp_path / "scripts"
    (s / "__pycache__").mkdir(parents=True)
    (s / "__pycache__" / "lint-cached.py").write_text("x", encoding="utf-8")
    (s / "node_modules").mkdir()
    (s / "node_modules" / "lint-dep.py").write_text("x", encoding="utf-8")
    (s / "lint-real.py").write_text("x", encoding="utf-8")
    names = [p.name for p in MOD.find_scripts(["scripts"])]
    assert "lint-real.py" in names
    assert "lint-cached.py" not in names
    assert "lint-dep.py" not in names


def test_find_scripts_nested_under_scripts_root(tmp_path, monkeypatch):
    # root 名が "scripts" で、ファイルが scripts/<subdir>/x.py のように
    # parent が "scripts" で終わらず "/scripts/" も含まない場合の
    # `elif rp.name == "scripts"` フォールバック分岐をカバーする。
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "scripts" / "phase2"
    d.mkdir(parents=True)
    (d / "lint-nested.py").write_text("x", encoding="utf-8")
    names = [p.name for p in MOD.find_scripts(["scripts"])]
    assert "lint-nested.py" in names


def test_find_scripts_non_scripts_py_under_plugins_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # plugins/p/lib/util.py は "/scripts/" を含まず parent も scripts でない → 除外
    d = tmp_path / "plugins" / "p" / "lib"
    d.mkdir(parents=True)
    (d / "validate-thing.py").write_text("x", encoding="utf-8")
    out = list(MOD.find_scripts(["plugins"]))
    assert out == []


# ── main: text モード / report モード / exit code ───────────────────────────
def _make_clean_tree(tmp_path):
    """OK のみの最小 scripts ツリー (cwd=tmp 前提)。"""
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "lint-good.py").write_text("x", encoding="utf-8")
    return s


def test_main_clean_returns_0_text(tmp_path, monkeypatch, capsys):
    _make_clean_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "scripts"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "VIOLATION=0" in out
    assert "OK=1" in out


def test_main_violation_returns_1_text(tmp_path, monkeypatch, capsys):
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "emit-bad.py").write_text("x", encoding="utf-8")  # 許可外動詞
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "scripts"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "VIOLATION" in captured.err
    assert "emit-bad.py" in captured.err


def test_main_report_mode_json(tmp_path, monkeypatch, capsys):
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "lint-good.py").write_text("x", encoding="utf-8")
    (s / "emit-bad.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "--report", "scripts"])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["OK"] == 1
    assert data["summary"]["VIOLATION"] == 1
    assert data["violations"][0]["path"].endswith("emit-bad.py")


def test_main_pending_reported_in_text(tmp_path, monkeypatch, capsys):
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "hook-thing.py").write_text("x", encoding="utf-8")  # PENDING via hook- prefix
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "scripts"])
    assert rc == 0  # PENDING は exit 1 にしない
    err = capsys.readouterr().err
    assert "PENDING" in err
    assert "hook-thing.py" in err


def test_main_defaults_to_scan_roots_when_no_path(tmp_path, monkeypatch, capsys):
    # path 引数なし → SCAN_ROOTS。tmp に scripts のみ用意。
    _make_clean_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py"])
    assert rc == 0
    assert "summary:" in capsys.readouterr().out


# ── CLI subprocess: 実 repo 健全性 + 明示違反 fixture ───────────────────────
def test_cli_real_repo_report_exit_zero():
    res = subprocess.run([sys.executable, str(SCRIPT), "--report"],
                         text=True, capture_output=True)
    # 実 repo は PENDING を許容しつつ VIOLATION=0 のはず (CI 前提)。
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    data = json.loads(res.stdout)
    assert data["summary"]["VIOLATION"] == 0


def test_cli_violation_fixture_exit_one(tmp_path):
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "run.py").write_text("x", encoding="utf-8")  # banned name
    res = subprocess.run([sys.executable, str(SCRIPT), str(s)],
                         text=True, capture_output=True)
    assert res.returncode == 1
    assert "run.py" in res.stderr
