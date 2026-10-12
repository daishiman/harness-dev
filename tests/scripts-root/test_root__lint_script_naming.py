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
- main: report モード JSON / text モード / VIOLATION 検出時 exit 1 / クリーン時 exit 0 /
    設定エラー exit 2 (存在しない path・走査 0 件・未知の option) / 明示した .py ファイル
- 照合キー: 絶対パス・別の cwd でも repo 相対の登録に当たる、repo 外の祖先 dir 名に引きずられない
- 登録の鮮度: PENDING_RENAME_PATHS の全 path が repo に実在する
- 動詞リスト: 28章 §4.1 (正本)・lint の docstring・CONVENTIONS.md の写しが ALLOWED_VERBS と一致し、
    §4.1.1 の寄せた別名 (apply/setup など) は VIOLATION のまま
- CLI: 実 repo (--report) が exit 0、明示の違反 fixture で exit 1

network: false, keychain: なし, 実ファイル書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import pathlib
import re
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


# ── 動詞リスト: 28章 §4.1 が正本。写しと寄せた別名を固定する ─────────────────
DOC_28 = ROOT / "doc" / "ClaudeCodeスキルの設計書" / "28-script-execution-model.md"
CONVENTIONS = ROOT / "installers" / "harness-creator-kit" / "CONVENTIONS.md"
STATE_VERBS = {"sync", "install", "record", "manage", "migrate"}  # 28章 §4.1.1


def _section(text: str, heading: str) -> str:
    """heading の行から次の同じ深さ以上の見出しの手前まで。"""
    start = text.index(heading + "\n")
    depth = heading.split(" ", 1)[0]
    rest = text[start + len(heading) + 1:]
    end = re.search(rf"^#{{1,{len(depth)}}} ", rest, re.M)
    return rest[:end.start()] if end else rest


def test_allowed_verbs_match_doc_28_section_4_1():
    # 動詞リストの変更は P1。lint と 28章の片方だけを変えるとここで止まる。
    text = DOC_28.read_text(encoding="utf-8")
    line = next(l for l in _section(text, "### 4.1 規約").splitlines() if l.startswith("- 動詞:"))
    assert set(re.findall(r"`([a-z]+)`", line)) == MOD.ALLOWED_VERBS
    # 状態を書き換える動詞は §3 の実行責務マトリクスにも行がある。
    matrix = _section(text, "## 3. 実行責務マトリクス")
    for verb in STATE_VERBS:
        assert f"\n| {verb} (" in matrix, verb


def test_allowed_verbs_copies_match():
    doc_line = next(l for l in MOD.__doc__.splitlines() if l.startswith("- 動詞リスト:"))
    assert set(doc_line.split(":", 1)[1].strip().split("/")) == MOD.ALLOWED_VERBS
    conventions = CONVENTIONS.read_text(encoding="utf-8")
    listed = re.search(r"動詞 \d+ 種（([^）]*)）", conventions).group(1)
    assert set(re.findall(r"[a-z]+", listed)) == MOD.ALLOWED_VERBS


def _folded_aliases() -> list[str]:
    """28章 §4.1.1 の表の「寄せた別名」の列。"""
    section = _section(DOC_28.read_text(encoding="utf-8"), "### 4.1.1 状態を書き換える動詞")
    rows = [l.split("|") for l in section.splitlines() if l.startswith("| `")]
    return sorted(a for row in rows for a in re.findall(r"`([a-z]+)`", row[4]))


def test_folded_aliases_are_documented():
    assert _folded_aliases() == sorted(["apply", "reconcile", "setup", "write", "log", "append", "backfill"])


@pytest.mark.parametrize("alias", _folded_aliases())
def test_classify_violation_folded_alias(alias):
    # 同じ意味の別名は動詞に足さない。寄せ先の動詞で名付ける。
    status, reason = _classify(f"scripts/{alias}-target.py")
    assert status == "VIOLATION"
    assert f"'{alias}'" in reason


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
    # 既知の登録パスを名指しで 1 件使う。next(iter(...)) だと台帳を恒久/改名待ちに
    # 分けた時点でどちらが引かれるか不定になるので、明示する。
    sample = "scripts/tenant-init.py"
    assert sample in MOD.PENDING_RENAME_PATHS
    status, reason = _classify(sample)
    assert status == "PENDING_RENAME"
    assert "legacy path" in reason


def test_classify_pending_rename_known_underscore_path():
    # underscore だが PENDING_RENAME_PATHS 登録済 → VIOLATION でなく PENDING。
    status, reason = _classify("scripts/link_master_plugins.py")
    assert status == "PENDING_RENAME"


# ── classify: PERMANENT_EXCEPTION 個別パス ──────────────────────────────────
def test_classify_permanent_exception_explicit_path():
    # 素の import 対象は恒久例外。改名待ちの列に混ぜない。
    sample = "scripts/feedback_contract_ssot.py"
    assert sample in MOD.PERMANENT_EXCEPTION_PATHS
    status, reason = _classify(sample)
    assert status == "PERMANENT_EXCEPTION"
    # 理由は 1 件ずつ固有の文字列であること (グループ共通の定型文で埋めない)。
    assert reason == MOD.PERMANENT_EXCEPTION_PATHS[sample]
    assert "import" in reason


def test_permanent_and_pending_are_disjoint():
    # 同じ path が両方に載ると「残り何件か」が二重計上で読めなくなる。
    assert not (set(MOD.PERMANENT_EXCEPTION_PATHS) & set(MOD.PENDING_RENAME_PATHS))


def test_permanent_exception_reasons_are_individual():
    reasons = list(MOD.PERMANENT_EXCEPTION_PATHS.values())
    assert all(r.strip() for r in reasons)
    # 全件が同一文言ではない (個別の理由が読めること)。
    assert len(set(reasons)) > 1


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
    # 台帳は repo ルート相対なので、tmp を全域走査するときは空にしておく
    # (さもないと全登録が「実体不在」として stale になる)。
    _make_clean_tree(tmp_path)
    monkeypatch.setattr(MOD, "PERMANENT_EXCEPTION_PATHS", {})
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATHS", set())
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "summary:" in out
    assert "stale=0" in out


# ── 台帳の逆向きラチェット (stale 検出) ─────────────────────────────────────
def test_stale_absent_registration_returns_1(tmp_path, monkeypatch, capsys):
    # 実体の無い path を登録すると全域走査で rc=1 になる (消滅した登録が残らない)。
    _make_clean_tree(tmp_path)
    monkeypatch.setattr(MOD, "PERMANENT_EXCEPTION_PATHS", {})
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATHS", {"scripts/emit-vanished.py"})
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py"])
    assert rc == 1, "実体不在の登録を見逃している"
    captured = capsys.readouterr()
    assert "scripts/emit-vanished.py" in captured.err
    assert "stale=1" in captured.out


def test_stale_absent_not_flagged_in_narrow_scope(tmp_path, monkeypatch, capsys):
    # path を明示した narrow 走査では不在検出を切る。範囲外の登録が「今回集めた
    # path に無い」ことは消滅の証拠にならず誤検出になるため。
    _make_clean_tree(tmp_path)
    monkeypatch.setattr(MOD, "PERMANENT_EXCEPTION_PATHS", {})
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATHS", {"plugins/other/scripts/emit-x.py"})
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "scripts"])
    assert rc == 0
    assert "stale=0" in capsys.readouterr().out


def test_stale_repaid_registration_returns_1(tmp_path, monkeypatch, capsys):
    # 既に規約を満たす path を登録したままにすると rc=1 になる (返済済みの検出)。
    s = _make_clean_tree(tmp_path)
    (s / "lint-already-fine.py").write_text("x", encoding="utf-8")
    monkeypatch.setattr(MOD, "PERMANENT_EXCEPTION_PATHS", {})
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATHS", {"scripts/lint-already-fine.py"})
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "scripts"])
    assert rc == 1, "既に規約を満たしている登録を見逃している"
    captured = capsys.readouterr()
    assert "scripts/lint-already-fine.py" in captured.err
    assert "stale=1" in captured.out


def test_stale_repaid_detected_for_permanent_registration(tmp_path, monkeypatch, capsys):
    # 恒久例外側も同じ歯止めに掛ける (恒久の棚は検査の抜け道にしない)。
    s = _make_clean_tree(tmp_path)
    (s / "lint-already-fine.py").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        MOD, "PERMANENT_EXCEPTION_PATHS",
        {"scripts/lint-already-fine.py": "import something"},
    )
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATHS", set())
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "scripts"])
    assert rc == 1, "恒久例外側の返済済み登録を見逃している"
    assert "stale=1" in capsys.readouterr().out


def test_stale_report_mode_lists_both_kinds(tmp_path, monkeypatch, capsys):
    s = _make_clean_tree(tmp_path)
    (s / "lint-already-fine.py").write_text("x", encoding="utf-8")
    monkeypatch.setattr(MOD, "PERMANENT_EXCEPTION_PATHS", {})
    monkeypatch.setattr(
        MOD, "PENDING_RENAME_PATHS",
        {"scripts/lint-already-fine.py", "scripts/emit-vanished.py"},
    )
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "--report"])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ledger_stale_repaid"] == ["scripts/lint-already-fine.py"]
    assert data["ledger_stale_absent"] == ["scripts/emit-vanished.py"]
    assert data["ledger_stale_unreferenced"] == []
    assert data["summary"]["ledger_stale"] == 2


def _make_permanent_tree(tmp_path, monkeypatch):
    """恒久例外 scripts/shared_mod.py を 1 件だけ登録した全域走査用ツリー (cwd=tmp)。"""
    s = _make_clean_tree(tmp_path)
    # 自分自身の中の import 行は参照に数えない。
    (s / "shared_mod.py").write_text("import shared_mod\n", encoding="utf-8")
    monkeypatch.setattr(
        MOD, "PERMANENT_EXCEPTION_PATHS",
        {"scripts/shared_mod.py": "import shared_mod — §4.3"},
    )
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATHS", set())
    monkeypatch.chdir(tmp_path)
    return s


def test_stale_unreferenced_permanent_returns_1(tmp_path, monkeypatch, capsys):
    # 恒久例外の登録条件は「素の import で参照されていること」。参照が 0 件なら rc=1。
    _make_permanent_tree(tmp_path, monkeypatch)
    rc = MOD.main(["lint-script-naming.py"])
    assert rc == 1, "import 参照の無い恒久例外を見逃している"
    captured = capsys.readouterr()
    assert "scripts/shared_mod.py" in captured.err
    assert "素の import 参照が 0 件" in captured.err
    assert "stale=1" in captured.out


@pytest.mark.parametrize("line", [
    "import shared_mod\n",
    "    from shared_mod import X\n",
    "import shared_mod as sm\n",
])
def test_stale_unreferenced_cleared_by_import(tmp_path, monkeypatch, capsys, line):
    # 別ファイル (scripts/ の外、_lib の中でも) から素の import があれば stale にしない。
    _make_permanent_tree(tmp_path, monkeypatch)
    user = tmp_path / "plugins" / "p" / "_lib" / "use.py"
    user.parent.mkdir(parents=True)
    user.write_text(f"def f():\n{line}", encoding="utf-8")
    rc = MOD.main(["lint-script-naming.py"])
    assert rc == 0, capsys.readouterr().err
    assert "stale=0" in capsys.readouterr().out


@pytest.mark.parametrize("line", [
    "# import shared_mod\n",
    "x = 'import shared_mod'\n",
    "import shared_mod_extra\n",
])
def test_stale_unreferenced_ignores_non_import_mentions(tmp_path, monkeypatch, capsys, line):
    # コメント・文字列・接頭辞が同じ別 module は参照に数えない。
    _make_permanent_tree(tmp_path, monkeypatch)
    (tmp_path / "scripts" / "lint-user.py").write_text(line, encoding="utf-8")
    assert MOD.main(["lint-script-naming.py"]) == 1
    assert "stale=1" in capsys.readouterr().out


def test_stale_unreferenced_ignores_hidden_dirs(tmp_path, monkeypatch, capsys):
    # .git や .venv の中の import は repo の参照ではない。
    _make_permanent_tree(tmp_path, monkeypatch)
    hidden = tmp_path / ".venv" / "use.py"
    hidden.parent.mkdir()
    hidden.write_text("import shared_mod\n", encoding="utf-8")
    assert MOD.main(["lint-script-naming.py"]) == 1


def test_stale_unreferenced_not_flagged_in_narrow_scope(tmp_path, monkeypatch, capsys):
    # path を明示した narrow 走査では参照検出を切る (参照は repo 全域から数えるため)。
    _make_permanent_tree(tmp_path, monkeypatch)
    rc = MOD.main(["lint-script-naming.py", "scripts"])
    assert rc == 0
    assert "stale=0" in capsys.readouterr().out


def test_stale_unreferenced_listed_in_report(tmp_path, monkeypatch, capsys):
    _make_permanent_tree(tmp_path, monkeypatch)
    rc = MOD.main(["lint-script-naming.py", "--report"])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ledger_stale_unreferenced"] == ["scripts/shared_mod.py"]
    assert data["ledger_stale_repaid"] == []
    assert data["ledger_stale_absent"] == []
    assert data["summary"]["ledger_stale"] == 1


# ── 台帳を空にしたときの床 (登録を増やして緑にする道を塞ぐ) ─────────────────
def test_empty_ledger_on_real_repo_has_violations(monkeypatch, capsys):
    # 台帳が空なら実 repo は必ず VIOLATION を出す。つまり現在の VIOLATION=0 は
    # 「違反が無い」ではなく「台帳が吸っている」状態であり、台帳を空にして緑に
    # なる (= 検査が何も当てていない) 経路が無いことをここで固定する。
    monkeypatch.setattr(MOD, "PERMANENT_EXCEPTION_PATHS", {})
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATHS", set())
    monkeypatch.setattr(MOD, "PENDING_RENAME_PATTERNS", [])
    monkeypatch.chdir(ROOT)
    rc = MOD.main(["lint-script-naming.py", "--report"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert data["summary"]["VIOLATION"] > 0, "台帳を空にしても違反が 0 件: 検査が当たっていない"
    assert data["summary"]["PERMANENT_EXCEPTION"] == 0
    assert data["summary"]["PENDING_RENAME"] == 0


# ── CLI subprocess: 実 repo 健全性 + 明示違反 fixture ───────────────────────
def test_cli_real_repo_report_exit_zero():
    # 台帳は repo ルート相対なので cwd を固定する (別 cwd だと全登録が stale になる)。
    res = subprocess.run([sys.executable, str(SCRIPT), "--report"],
                         cwd=str(ROOT), text=True, capture_output=True)
    # 実 repo は PENDING を許容しつつ VIOLATION=0 / stale=0 のはず (CI 前提)。
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    data = json.loads(res.stdout)
    assert data["summary"]["VIOLATION"] == 0
    assert data["summary"]["ledger_stale"] == 0


def test_cli_violation_fixture_exit_one(tmp_path):
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "run.py").write_text("x", encoding="utf-8")  # banned name
    res = subprocess.run([sys.executable, str(SCRIPT), str(s)],
                         text=True, capture_output=True)
    assert res.returncode == 1
    assert "run.py" in res.stderr


# ── 照合キー: 絶対パス・別の cwd ────────────────────────────────────────────
def test_classify_absolute_repo_path_matches_relative_registration():
    # 登録は repo 相対。絶対パスで渡しても同じ登録に当たり、VIOLATION に化けない。
    # 恒久例外と改名待ちの2つの台帳のどちらも同じ照合キーで引く。
    status, _ = _classify(str(ROOT / "scripts" / "feedback_contract_ssot.py"))
    assert status == "PERMANENT_EXCEPTION"
    status, _ = _classify(str(ROOT / "scripts" / "gate-phase0.py"))
    assert status == "PENDING_RENAME"


def test_main_absolute_repo_roots_from_other_cwd_have_no_violation(tmp_path, monkeypatch, capsys):
    # CI と同じ repo を、別の cwd から絶対パスで走査しても結果は変わらない。
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", str(ROOT / "scripts"), str(ROOT / "plugins")])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert "VIOLATION=0" in captured.out


def test_find_scripts_ignores_scripts_named_ancestor_outside_repo(tmp_path, monkeypatch):
    # repo の外の祖先 dir が scripts という名前でも、その下の lib/ は scripts 扱いしない。
    project = tmp_path / "scripts" / "proj"
    lib = project / "lib"
    lib.mkdir(parents=True)
    (lib / "validate-thing.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(project)
    assert list(MOD.find_scripts([str(lib)])) == []


# ── main: 設定エラー (exit 2) と明示ファイル ────────────────────────────────
def test_main_missing_path_is_config_error(tmp_path, monkeypatch, capsys):
    _make_clean_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "scripts", "nosuchdir"])
    assert rc == 2
    assert "path not found: nosuchdir" in capsys.readouterr().err


def test_main_zero_scanned_from_wrong_cwd_is_config_error(tmp_path, monkeypatch, capsys):
    # path を省略して scripts/ も plugins/ も無い cwd で起動すると、検査が空振りする。
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py"])
    assert rc == 2
    assert "no scripts scanned" in capsys.readouterr().err


def test_main_dir_without_scripts_is_config_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "docs"])
    assert rc == 2
    assert "no scripts scanned" in capsys.readouterr().err


def test_main_unknown_option_is_config_error(tmp_path, monkeypatch, capsys):
    _make_clean_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["lint-script-naming.py", "--repot", "scripts"])
    assert rc == 2
    assert "unknown option(s): --repot" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_main_help_prints_usage_and_returns_0(tmp_path, monkeypatch, capsys, flag):
    # --help は設定エラーではない。走査も台帳の照合もせずに usage を出して 0。
    monkeypatch.chdir(tmp_path)  # scripts/ が無い cwd でも 2 にならない
    assert MOD.main(["lint-script-naming.py", flag]) == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out
    assert "--report" in captured.out
    assert captured.err == ""


def test_cli_help_exit_zero():
    res = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                         text=True, capture_output=True)
    assert res.returncode == 0, res.stderr
    assert "usage:" in res.stdout


def test_main_explicit_file_is_checked(tmp_path, monkeypatch, capsys):
    # 置き場所が scripts/ でなくても、明示したファイルは照合する (0 件で素通りしない)。
    bad = tmp_path / "emit-bad.py"
    bad.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert MOD.main(["lint-script-naming.py", str(bad)]) == 1
    assert "emit-bad.py" in capsys.readouterr().err


# ── 登録の鮮度 ──────────────────────────────────────────────────────────────
def test_every_pending_rename_path_exists_in_repo():
    # repo から消えた path を登録に残すと、後で同じ path に置いた別物を黙って通す。
    missing = sorted(p for p in MOD.PENDING_RENAME_PATHS if not (ROOT / p).exists())
    assert missing == []
