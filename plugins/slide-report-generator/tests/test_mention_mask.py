"""実体と言及を分ける共通型 (scripts/mention_mask.py) の検査。

この型は「剥がす」側なので、**剥がしすぎても静かに緑になる**。だから
  - 剥がした範囲を数として返すこと
  - 剥がした後も残るべきものが残ること
  - 別実装 (JS 側) と同じ結果を出すこと
の 3 つを縛る。1 つ目が無いと、全部剥がした状態が「違反 0 件」と同じ見た目になる。
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_LINEBREAK = _PLUGIN_ROOT / "scripts" / "validate-linebreak-position.mjs"

_spec = importlib.util.spec_from_file_location(
    "mention_mask", _PLUGIN_ROOT / "scripts" / "mention_mask.py")
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)

_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)

# 実ファイルで誤検出になった 2 例をそのまま持つ。合成の断片だけで固めると、
# 「実物に当てたら別の形だった」で漏れる (JS 側の self-test がその欠陥を持っていた)。
_CASES = [
    ('<script>const P = /([。！？])(?!<br>)/g;</script>', "検査器自身のパターン定義"),
    ('<script>tpl(`${d.label}<br>${d.value}`)</script>', "テンプレートリテラルの断片"),
    ('<style>.x::after{content:"<br>"}</style>', "style の content"),
    ('<!-- 旧実装では 本文です。<br>次 と書いていた -->', "コメント内の記録"),
    ('<script>x="<br>"</script><p>本文です。<br>次</p>', "剥がした後も後続の本文は残る"),
    ('<p>本文です。<br>次</p>', "剥がす対象が無い"),
    ('<SCRIPT>a="<br>"</SCRIPT><p>です。<br>次</p>', "大文字タグでも剥がす"),
]


def _masked_br(html: str) -> int:
    masked, _ = mm.mask(html, "html")
    return len(_BR.findall(masked))


def test_mask_keeps_length_and_line_numbers():
    # 同長でないと、位置で効く仕組み (css-route マーカー等) の照合先がずれる。
    src = "<p>あ。<br>い</p>\n<script>x=\"<br>\"</script>\n<p>う。<br>え</p>\n"
    masked, spans = mm.mask(src, "html")
    assert len(masked) == len(src)
    assert masked.count("\n") == src.count("\n")
    assert [s["line"] for s in spans] == [2]


def test_mask_reports_what_it_removed():
    # 剥がした量が返らないと、剥がしすぎたことが緑として現れる。
    src = '<script>a</script><style>b</style><!-- c -->'
    _, spans = mm.mask(src, "html")
    assert [s["kind"] for s in spans] == ["script", "style", "comment"]


def test_dropped_counts_the_difference():
    src = '<script>x="<br>"</script><p>本文です。<br>次</p>'
    masked, _ = mm.mask(src, "html")
    assert mm.dropped(src, masked, _BR) == 1


def test_masking_does_not_swallow_the_prose_around_it():
    # 剥がす型で一番怖いのは、対象ごと消えて 0 件になること。
    src = '<script>x="<br>"</script><p>本文です。<br>次</p>'
    assert _masked_br(src) == 1


def test_markdown_is_rejected_rather_than_guessed():
    # markdown を入れていないのは測った結果 (docstring 参照)。黙って html 扱いで
    # 通すと、呼び出し側は剥がせたつもりになる。使えないものは例外にする。
    with pytest.raises(ValueError):
        mm.mask("`--x` を使う", "markdown")


def test_inline_code_in_markdown_is_not_a_reliable_marker():
    # 上の判断の根拠を実物で固定する。同じインラインコードの表セルが、
    # 片方は実装の指示・片方は違反の記録。構造が同一なので構造では分けられない。
    spec = (_PLUGIN_ROOT / "references" / "spec-registry.md").read_text(encoding="utf-8")
    assert "`.pagination .dot:nth-child(5n) { background: var(--accent-aqua-vivid);" in spec


@pytest.mark.parametrize("html,label", _CASES)
def test_parity_with_the_js_implementation(html, label, tmp_path):
    """JS 側 (validate-linebreak-position.mjs) と同じ結果になること。

    突合の相手は JS の checked。あちらは maskNonProse をかけた後に残った <br> を
    数えるので、こちらの masked から数えた <br> と一致しなければ、どちらかの
    剥がし方が違う。共通型と言う以上、ここが割れていてはいけない。
    """
    p = tmp_path / "case.html"
    p.write_text(html, encoding="utf-8")
    r = subprocess.run([_node(), str(_LINEBREAK), str(p), "--json"],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    checked = json.loads(r.stdout)["checked"]
    assert _masked_br(html) == checked, f"{label}: py={_masked_br(html)} js={checked}"


def _node() -> str:
    from shutil import which
    exe = which("node")
    if exe is None:
        pytest.skip("node が無い")
    return exe
