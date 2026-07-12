"""lint-forbidden-deps.py の禁止依存検出ロジックを実入力で網羅検証する。

このスクリプトは manifest.json の requirements.forbidden_dependencies を読み、
kit/scripts/.claude 配下の *.py / *.sh を grep して禁止ライブラリ混入を検出する。
network 不要なので深くテストできる。

検証対象:
  - build_patterns: import / from / pip install / brew install / コマンド呼び出し
    の各正規表現分岐 (PASS=マッチ, 偽陽性回避=非マッチ)
  - scan: 拡張子フィルタ / 自分自身除外 / 読めないファイルskip / 行番号・行本文抽出
  - main: 4 経路 (manifest 欠落 SKIP=0 / forbidden 空=0 / 検出なし OK=0 /
    検出あり FAIL=1) を module 定数 monkeypatch で駆動

module 定数 (KIT_DIR/MANIFEST/SCAN_ROOTS/SELF) は __file__ から算出されるため、
tmp_path 上に最小ツリーを作り定数を差し替えて実 plugin を汚さずに駆動する。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-forbidden-deps.py"
)


def _load_module():
    """毎テスト独立した module インスタンスを返す (定数 monkeypatch の汚染回避)。"""
    spec = importlib.util.spec_from_file_location("lint_forbidden_deps_t", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load_module()


# --- build_patterns: 5 つの検出形式それぞれの分岐 ---


def test_build_patterns_returns_one_pattern_per_name(mod):
    pats = mod.build_patterns(["requests", "numpy"])
    assert set(pats.keys()) == {"requests", "numpy"}
    # 値は compiled regex
    assert all(hasattr(p, "search") for p in pats.values())


def test_build_patterns_matches_import_form(mod):
    pat = mod.build_patterns(["requests"])["requests"]
    assert pat.search("import requests")
    assert pat.search("    import requests  # indented")


def test_build_patterns_matches_from_import_form(mod):
    pat = mod.build_patterns(["requests"])["requests"]
    assert pat.search("from requests import get")


def test_build_patterns_matches_pip_install_form(mod):
    pat = mod.build_patterns(["requests"])["requests"]
    assert pat.search("pip install requests")
    # \S* で prefix 付きパッケージ名にもヒット
    assert pat.search("pip install requests==2.0")


def test_build_patterns_matches_brew_install_form(mod):
    pat = mod.build_patterns(["numpy"])["numpy"]
    assert pat.search("brew install numpy-extra")


def test_build_patterns_matches_command_invocation_with_flag(mod):
    pat = mod.build_patterns(["requests"])["requests"]
    # `<name> --flag` / `<name> -x` のコマンド呼び出し形式
    assert pat.search("requests --help")
    assert pat.search("requests -v")


def test_build_patterns_avoids_false_positive_substring(mod):
    pat = mod.build_patterns(["requests"])["requests"]
    # 部分文字列 (変数名) はマッチしない (\b / \W 境界)
    assert not pat.search("my_requests_var = 1")
    # フラグの無いただの単語末尾もマッチしない
    assert not pat.search("see the requests docs")


def test_build_patterns_escapes_regex_metachars(mod):
    # 依存名にドット等が含まれても re.escape で文字通り扱う
    pat = mod.build_patterns(["a.b"])["a.b"]
    assert pat.search("import a.b")
    # "axb" は a.b の正規表現解釈ではマッチしない (escape されている証拠)
    assert not pat.search("import axb")


# --- scan: ファイル走査・フィルタ・行抽出 ---


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_scan_detects_py_and_sh_only(mod, tmp_path):
    pats = mod.build_patterns(["requests"])
    _write(tmp_path / "a.py", "import requests\n")
    _write(tmp_path / "b.sh", "pip install requests\n")
    _write(tmp_path / "c.txt", "import requests\n")  # 対象外拡張子
    _write(tmp_path / "d.md", "import requests\n")  # 対象外拡張子
    findings = mod.scan([tmp_path], pats)
    found_paths = {f[0].name for f in findings}
    assert found_paths == {"a.py", "b.sh"}


def test_scan_first_line_reports_line_1_with_full_text(mod, tmp_path):
    # ファイル先頭行 (前置改行なし) は ^ アンカーがマッチし行番号・本文が正確
    pats = mod.build_patterns(["requests"])
    _write(tmp_path / "x.py", "import requests\nprint('ok')\n")
    findings = mod.scan([tmp_path], pats)
    assert len(findings) == 1
    _path, line_no, name, line = findings[0]
    assert line_no == 1
    assert name == "requests"
    assert line == "import requests"  # strip 済み本文


def test_scan_line_attribution_quirk_when_preceded_by_newline(mod, tmp_path):
    # 既知の仕様: (?:^|\W) が直前の改行を取り込むため、行頭 import が前置改行を
    # 持つ場合 m.start() は前行末を指し line_no が 1 つ手前・本文は空になる。
    # 偽の合格でなく実挙動をピン留めする (回帰検出用)。
    pats = mod.build_patterns(["requests"])
    _write(tmp_path / "x.py", "# header\n\nimport requests\nprint('ok')\n")
    findings = mod.scan([tmp_path], pats)
    assert len(findings) == 1
    _path, line_no, name, line = findings[0]
    assert name == "requests"
    assert line_no == 2  # 実際の import 行 (3) ではなく直前行を指す
    assert line == ""  # 前行は空行


def test_scan_excludes_self(mod, tmp_path):
    pats = mod.build_patterns(["requests"])
    self_file = _write(tmp_path / "me.py", "import requests\n")
    mod.SELF = self_file.resolve()
    # SELF と一致するファイルは findings に含まれない
    assert mod.scan([tmp_path], pats) == []


def test_scan_skips_nonexistent_root(mod, tmp_path):
    pats = mod.build_patterns(["requests"])
    missing = tmp_path / "does_not_exist"
    # root が存在しなくても例外を出さず空を返す
    assert mod.scan([missing], pats) == []


def test_scan_skips_undecodable_file(mod, tmp_path):
    pats = mod.build_patterns(["requests"])
    # UTF-8 として復号不能なバイト列の .py は read_text で例外 -> skip
    bad = tmp_path / "binary.py"
    bad.write_bytes(b"\xff\xfe\x00\x01import requests\n")
    good = _write(tmp_path / "good.py", "import requests\n")
    findings = mod.scan([tmp_path], pats)
    # 復号不能ファイルは無視され、良ファイルのみ検出
    names = {f[0].name for f in findings}
    assert names == {"good.py"}


def test_scan_empty_when_no_match(mod, tmp_path):
    pats = mod.build_patterns(["numpy"])
    _write(tmp_path / "clean.py", "import os\nimport sys\n")
    assert mod.scan([tmp_path], pats) == []


def test_scan_multiple_findings_in_one_file(mod, tmp_path):
    pats = mod.build_patterns(["requests"])
    _write(tmp_path / "multi.py", "import requests\nfrom requests import get\n")
    findings = mod.scan([tmp_path], pats)
    assert len(findings) == 2


# --- main: 4 経路 (定数 monkeypatch で駆動) ---


def _setup_kit(mod, tmp_path: Path, forbidden, src_files: dict) -> Path:
    """manifest + scan 対象を tmp に作り module 定数を差し替える。manifest path を返す。"""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"requirements": {"forbidden_dependencies": forbidden}})
    )
    scan_root = tmp_path / "scan"
    for rel, body in src_files.items():
        _write(scan_root / rel, body)
    mod.MANIFEST = manifest
    mod.SCAN_ROOTS = [scan_root]
    mod.SELF = SCRIPT.resolve()  # tmp 内では一致しない
    return manifest


def test_main_skip_when_manifest_missing(mod, tmp_path, capsys):
    mod.MANIFEST = tmp_path / "nope.json"
    rc = mod.main()
    assert rc == 0
    err = capsys.readouterr().err
    assert "SKIP" in err
    assert "not found" in err


def test_main_ok_when_forbidden_empty(mod, tmp_path, capsys):
    _setup_kit(mod, tmp_path, forbidden=[], src_files={"a.py": "import requests\n"})
    rc = mod.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "empty" in out


def test_main_ok_when_no_findings(mod, tmp_path, capsys):
    _setup_kit(
        mod,
        tmp_path,
        forbidden=["requests"],
        src_files={"clean.py": "import os\n"},
    )
    rc = mod.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK: no forbidden dependency usage detected" in out
    assert "requests" in out  # チェックしたパターン名を表示


def test_main_fail_when_forbidden_used(mod, tmp_path, capsys):
    _setup_kit(
        mod,
        tmp_path,
        forbidden=["requests"],
        src_files={"bad.py": "import requests\nprint('x')\n"},
    )
    rc = mod.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL: 1 forbidden dependency usage(s) detected" in out
    assert "bad.py" in out
    assert "[requests]" in out


def test_main_fail_lists_every_finding(mod, tmp_path, capsys):
    _setup_kit(
        mod,
        tmp_path,
        forbidden=["requests", "numpy"],
        src_files={
            "a.py": "import requests\n",
            "b.sh": "brew install numpy-extra\n",
        },
    )
    rc = mod.main()
    assert rc == 1
    out = capsys.readouterr().out
    # 2 件検出 = 各違反が行として出る
    assert "FAIL: 2 forbidden dependency usage(s) detected" in out
    assert "[requests]" in out
    assert "[numpy]" in out


# --- end-to-end subprocess: 実 plugin (manifest なし) は SKIP=0 で通る ---


def test_subprocess_skip_path_exits_zero():
    """実 plugin には manifest.json が無いので SKIP (exit 0) になることを確認。"""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "SKIP" in proc.stderr
