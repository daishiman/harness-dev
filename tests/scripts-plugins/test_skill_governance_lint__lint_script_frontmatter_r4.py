"""lint-script-frontmatter.py の PEP 723 frontmatter 検証を独立に網羅する (scripts4 系列)。

対象 script:
  plugins/skill-governance-lint/scripts/lint-script-frontmatter.py

extract_frontmatter (純パーサ) と main (ディレクトリ走査 + 違反/pending/exemption 分岐) の
全経路をゼロから被覆する。純ローカル meta-lint (network=false, write-scope=none) のため stub 不要。
全 fixture は tmp_path に書き出し repo を一切汚染しない。main は in-process(monkeypatch argv)と
subprocess(__main__ ガード + exit code 契約)双方で確認する。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-script-frontmatter.py"

# REQUIRED_KEYS 全部を備えた最小合格 frontmatter を素片化したテンプレ
GOOD_FM = (
    "#!/usr/bin/env python3\n"
    "# /// script\n"
    "# name: sample\n"
    "# purpose: do a thing\n"
    "# inputs:\n"
    "#   - argv: x\n"
    "# outputs:\n"
    "#   - stdout: y\n"
    "# contexts: [E]\n"
    "# network: false\n"
    "# write-scope: none\n"
    "# dependencies: []\n"
    "# ///\n"
    '"""body."""\n'
)


def _load():
    spec = importlib.util.spec_from_file_location("lint_script_frontmatter_r4_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _write_py(d: Path, name: str, content: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# extract_frontmatter
# ---------------------------------------------------------------------------
def test_extract_full_keys(MOD):
    fm = MOD.extract_frontmatter(GOOD_FM)
    assert fm is not None
    for k in MOD.REQUIRED_KEYS:
        assert k in fm
    # スカラー値は trim される
    assert fm["name"] == "sample"
    assert fm["network"] == "false"


def test_extract_no_block_returns_none(MOD):
    # "# /// script" が無ければ None
    assert MOD.extract_frontmatter("#!/usr/bin/env python3\nprint('hi')\n") is None


def test_extract_unterminated_block_returns_none(MOD):
    # 開始はあるが "# ///" 終端が無い → None
    text = "# /// script\n# name: x\n# purpose: y\n"
    assert MOD.extract_frontmatter(text) is None


def test_extract_list_continuation_appends_to_last_key(MOD):
    # "- item" 行は直前キーへ連結される (last_key 経路)
    text = (
        "# /// script\n"
        "# inputs:\n"
        "#   - a\n"
        "#   - b\n"
        "# ///\n"
    )
    fm = MOD.extract_frontmatter(text)
    assert "inputs" in fm
    assert "- a" in fm["inputs"] and "- b" in fm["inputs"]


def test_extract_blank_comment_line_skipped(MOD):
    # ブロック内の空コメント (body が空) は continue される
    text = (
        "# /// script\n"
        "#\n"
        "# name: z\n"
        "# ///\n"
    )
    fm = MOD.extract_frontmatter(text)
    assert fm == {"name": "z"}


def test_extract_dash_line_without_prior_key_ignored(MOD):
    # last_key が無い状態の "- " 行はどの分岐にも入らず無視される
    text = (
        "# /// script\n"
        "#   - orphan\n"
        "# name: w\n"
        "# ///\n"
    )
    fm = MOD.extract_frontmatter(text)
    assert fm == {"name": "w"}


def test_extract_colon_in_value_partitions_only_first(MOD):
    # partition(":") は最初のコロンのみで分割し、値側のコロンは残す
    text = (
        "# /// script\n"
        "# requires-python: \">=3.9\"\n"
        "# ///\n"
    )
    fm = MOD.extract_frontmatter(text)
    assert fm["requires-python"] == '">=3.9"'


# ---------------------------------------------------------------------------
# main — 正常系
# ---------------------------------------------------------------------------
def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["lint-script-frontmatter.py", *args])


def test_main_all_good_returns_0(MOD, tmp_path, monkeypatch, capsys):
    _write_py(tmp_path, "good.py", GOOD_FM)
    _argv(monkeypatch, str(tmp_path))
    assert MOD.main() == 0
    err = capsys.readouterr().err
    assert "OK (checked=1" in err


def test_main_exempt_init_skipped(MOD, tmp_path, monkeypatch, capsys):
    # __init__.py は EXEMPT_NAMES で走査対象外 → checked に数えられない
    _write_py(tmp_path, "__init__.py", "x = 1\n")
    _write_py(tmp_path, "good.py", GOOD_FM)
    _argv(monkeypatch, str(tmp_path))
    assert MOD.main() == 0
    assert "checked=1" in capsys.readouterr().err


def test_main_pycache_skipped(MOD, tmp_path, monkeypatch, capsys):
    # __pycache__ 配下は除外される
    _write_py(tmp_path / "__pycache__", "cached.py", "x=1\n")
    _write_py(tmp_path, "good.py", GOOD_FM)
    _argv(monkeypatch, str(tmp_path))
    assert MOD.main() == 0
    assert "checked=1" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main — 違反系
# ---------------------------------------------------------------------------
def test_main_missing_block_violation(MOD, tmp_path, monkeypatch, capsys):
    _write_py(tmp_path, "nofm.py", "print('no frontmatter')\n")
    _argv(monkeypatch, str(tmp_path))
    assert MOD.main() == 1
    out = capsys.readouterr().out
    assert "missing # /// script" in out


def test_main_missing_keys_violation(MOD, tmp_path, monkeypatch, capsys):
    # block はあるが name/purpose 以外を欠落
    partial = (
        "# /// script\n"
        "# name: x\n"
        "# purpose: y\n"
        "# ///\n"
    )
    _write_py(tmp_path, "partial.py", partial)
    _argv(monkeypatch, str(tmp_path))
    assert MOD.main() == 1
    cap = capsys.readouterr()
    assert "missing keys:" in cap.out
    # inputs/outputs/contexts/network/write-scope/dependencies が列挙される
    assert "inputs" in cap.out and "write-scope" in cap.out
    assert "violations=1" in cap.err


def test_main_pending_file_downgraded_to_warning(MOD, tmp_path, monkeypatch, capsys):
    # PENDING_FILES のファイルは違反でも stderr 警告 (PENDING) に降格し exit 0
    pending_name = sorted(MOD.PENDING_FILES)[0]
    _write_py(tmp_path, pending_name, "print('no fm')\n")
    _argv(monkeypatch, str(tmp_path))
    assert MOD.main() == 0
    cap = capsys.readouterr()
    assert cap.out == ""  # violations への出力は無い
    assert "PENDING" in cap.err
    assert "pending=1" in cap.err


def test_main_mixed_violation_and_pending(MOD, tmp_path, monkeypatch, capsys):
    # 通常違反 1 + pending 1 が同時に存在 → exit 1 かつ pending は警告
    pending_name = sorted(MOD.PENDING_FILES)[0]
    _write_py(tmp_path, pending_name, "print('p')\n")
    _write_py(tmp_path, "bad.py", "print('b')\n")
    _argv(monkeypatch, str(tmp_path))
    assert MOD.main() == 1
    cap = capsys.readouterr()
    assert "bad.py" in cap.out
    assert "PENDING" in cap.err
    assert "violations=1" in cap.err and "pending=1" in cap.err


# ---------------------------------------------------------------------------
# main — エッジ / 引数
# ---------------------------------------------------------------------------
def test_main_default_dir_when_no_argv(MOD, tmp_path, monkeypatch, capsys):
    # 引数なし → 既定 "plugins"。tmp_path で chdir し空の plugins を用意して再現性確保
    (tmp_path / "plugins").mkdir()
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch)
    assert MOD.main() == 0
    assert "checked=0" in capsys.readouterr().err


def test_main_not_a_directory_warns_and_skips(MOD, tmp_path, monkeypatch, capsys):
    # 存在しないパスは "not a directory" 警告を出し走査対象から外す
    _argv(monkeypatch, str(tmp_path / "ghost"))
    assert MOD.main() == 0
    err = capsys.readouterr().err
    assert "not a directory" in err
    assert "checked=0" in err


def test_main_multiple_target_dirs(MOD, tmp_path, monkeypatch, capsys):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    _write_py(d1, "g1.py", GOOD_FM)
    _write_py(d2, "g2.py", GOOD_FM)
    _argv(monkeypatch, str(d1), str(d2))
    assert MOD.main() == 0
    assert "checked=2" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main — subprocess (__main__ ガード + exit code 契約)
# ---------------------------------------------------------------------------
def test_subprocess_pass(tmp_path):
    _write_py(tmp_path, "good.py", GOOD_FM)
    r = _run([str(tmp_path)])
    assert r.returncode == 0
    assert "OK (checked=1" in r.stderr


def test_subprocess_fail(tmp_path):
    _write_py(tmp_path, "bad.py", "print('x')\n")
    r = _run([str(tmp_path)])
    assert r.returncode == 1
    assert "missing # /// script" in r.stdout
