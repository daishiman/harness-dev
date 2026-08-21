"""SR-3-09 / V-021 の位置検査を固定する。

縛りたいのは 2 点。
  1. 判定に文字数を使わないこと（正本が明示的に否定した基準）
  2. 語彙を挿入器と検査器で共有していること（別々に持つと、挿入器が入れた
     <br> を検査器が落とす）
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-linebreak-position.mjs"
UTILS = PLUGIN_ROOT / "vendor" / "scripts" / "utils.js"
INSERTER = PLUGIN_ROOT / "vendor" / "scripts" / "auto-linebreak.js"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(VALIDATOR), *args], capture_output=True, text=True, check=False
    )


def _html(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / f"{name}.html"
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return path


def test_self_test_passes() -> None:
    got = _run("--self-test")
    assert got.returncode == 0, got.stdout + got.stderr
    # 件数は直書きしない。ケースを足すたびにここが落ちると、
    # 「テストを通すために期待値を書き換える」だけの作業が発生する。
    # 縛りたいのは「1 件も FAIL していないこと」で、総数ではない。
    assert "FAIL" not in got.stdout, got.stdout
    assert re.search(r"^PASS (\d+)/\1$", got.stdout, re.M), got.stdout
    assert "utils.js" in got.stdout  # 語彙の由来を出している


def test_script_and_style_are_not_prose(tmp_path: Path) -> None:
    """script / style / コメントの中身は検査対象にしない。

    ここを剥がさないと、検査器自身のパターン定義やテンプレートリテラルの断片を
    違反として拾う。実際、剥がす前は実ファイルで検出 13 件が全件この誤検出だった。
    self-test が script を含まない裸の断片だけだったので、合成入力では一度も
    再現せず、実物に当てて初めて出た。
    """
    path = tmp_path / "masked.html"
    path.write_text(
        "<html><body>\n"
        '<script>const P = /([。！？])(?!<br>)/g; tpl(`${d.label}<br>${d.value}`);</script>\n'
        '<style>.x::after{content:"<br>"}</style>\n'
        "<!-- 旧実装では 文字数<br>で切っていた -->\n"
        "</body></html>",
        encoding="utf-8",
    )
    got = _run(str(path), "--json")
    assert got.returncode == 0, got.stdout + got.stderr
    payload = json.loads(got.stdout)
    # violations だけを見ると、走査していても中身が合法なら 0 になり得る。
    # checked まで縛らないと除外を検証したことにならない。
    assert payload["results"][0]["checked"] == 0
    assert payload["verdict"] == "not-checked"


def test_prose_after_script_is_still_checked(tmp_path: Path) -> None:
    """除外が効きすぎて本文まで隠れていないこと。"""
    path = tmp_path / "after-script.html"
    path.write_text(
        '<html><body><script>x = "<br>";</script>'
        "<p>途中で切れる文字<br>列</p></body></html>",
        encoding="utf-8",
    )
    got = _run(str(path), "--json")
    assert got.returncode == 1
    payload = json.loads(got.stdout)
    assert payload["results"][0]["checked"] == 1
    assert payload["violations"] == 1


def test_indented_break_is_not_a_violation(tmp_path: Path) -> None:
    """整形された HTML で <br> が次行にあっても落とさない。

    末尾の空白を落とさないと直前の語が空白になり、正しい改行が全部落ちる。
    """
    path = tmp_path / "indented.html"
    path.write_text(
        "<html><body>\n  <p>ここまでです。\n    <br>\n    次の行</p>\n</body></html>",
        encoding="utf-8",
    )
    got = _run(str(path), "--json")
    assert got.returncode == 0, got.stdout + got.stderr
    payload = json.loads(got.stdout)
    assert payload["results"][0]["checked"] == 1
    assert payload["verdict"] == "pass"


def test_zero_targets_is_distinguishable_from_pass(tmp_path: Path) -> None:
    """「対象 0 件」と「検査して違反なし」を出力で区別できること。

    どちらも exit 0 / violations 0 なので、verdict が無いと呼び出し側からは
    区別できず、何も検査していない緑を合格と読む。
    """
    empty = _html(tmp_path, "empty", "<p>改行の無い文章</p>")
    got = _run(str(empty), "--json")
    assert json.loads(got.stdout)["verdict"] == "not-checked"
    assert "未検査" in _run(str(empty)).stdout

    ok = _html(tmp_path, "ok", "<p>資料を配布します。<br>ご確認ください</p>")
    got = _run(str(ok), "--json")
    assert json.loads(got.stdout)["verdict"] == "pass"


def test_break_after_clause_passes_and_mid_word_fails(tmp_path: Path) -> None:
    ok = _html(tmp_path, "ok", "<p>資料を配布します。<br>ご確認ください</p>")
    got = _run(str(ok))
    assert got.returncode == 0, got.stdout + got.stderr

    ng = _html(tmp_path, "ng", "<p>途中で切れる文字<br>列になっている</p>")
    got = _run(str(ng), "--json")
    assert got.returncode == 1
    payload = json.loads(got.stdout)
    assert payload["violations"] == 1
    assert payload["results"][0]["checked"] == 1


def test_length_is_never_used(tmp_path: Path) -> None:
    """長さで結論が変わらないこと。

    同じ文節の切れ目で改行した短文と長文が、どちらも通る。文字数の閾値が
    紛れ込むと、長い方だけが落ちる（あるいは短い方だけが落ちる）。
    """
    short = _html(tmp_path, "short", "<p>私は、<br>行く</p>")
    long_body = "とても長い前置きの文章がここに延々と続いていて、<br>" + "後半も同様に長い文章が続く"
    long = _html(tmp_path, "long", f"<p>{long_body}</p>")
    assert _run(str(short)).returncode == 0
    assert _run(str(long)).returncode == 0

    # <br> を持たない長文は対象外（長さの閾値を持たないことの裏返し）。
    none = _html(tmp_path, "none", "<p>" + "改行の無い長い文章" * 20 + "</p>")
    got = _run(str(none), "--json")
    assert got.returncode == 0
    assert json.loads(got.stdout)["results"][0]["checked"] == 0


def test_vocabulary_is_shared_with_inserter() -> None:
    """語彙の正本が 1 つであること。挿入器が自前の語彙表を持ち直したら落とす。"""
    assert "LINEBREAK_RULES" in UTILS.read_text(encoding="utf-8")

    inserter = INSERTER.read_text(encoding="utf-8")
    assert "LINEBREAK_RULES" in inserter, "挿入器は共有の語彙を読むこと"
    # 旧実装のリテラル表が復活していないこと。
    assert "(は|が|を|に|で|と|も|の)" not in inserter


def test_unreadable_vocabulary_is_fail_closed(tmp_path: Path) -> None:
    """語彙が読めないなら判定しない。

    空集合のまま走ると全部 FAIL になるか全部 PASS になるかのどちらかで、
    どちらも「検査した」と読まれる。
    """
    probe = tmp_path / "validate-linebreak-position.mjs"
    source = VALIDATOR.read_text(encoding="utf-8")
    # utils.js を解決できない位置へ置いた複製を走らせる。
    probe.write_text(source, encoding="utf-8")
    got = subprocess.run(
        ["node", str(probe), "--self-test"], capture_output=True, text=True, check=False
    )
    assert got.returncode == 3
    assert "fail-closed" in got.stderr
