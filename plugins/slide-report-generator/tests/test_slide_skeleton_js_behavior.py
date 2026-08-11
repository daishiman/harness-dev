"""slide-skeleton.js を実行して挙動を確かめる。

既存の検査 (validate-slide-skeleton.py の S4-js-drift) が見ているのは
「生成器の出力とファイルがバイト一致するか」だけで、その JS が**何をするか**
は一度も走らせていない。生成器のロジックを壊しても、再生成すれば両者は
一致するので S4 は緑のまま通る。ここはその穴を塞ぐ層で、
`tests/fixtures/skeleton-js-harness.js` の擬似 DOM 上で実際に実行し、
ひな形と README が宣言している 4 つの契約を判定する。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "fixtures" / "skeleton-js-harness.js"
TARGET = ROOT / "assets" / "slide-templates" / "slide-skeleton.js"
FS_MIN = 18.0

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node が無い")


@pytest.fixture(scope="module")
def result() -> dict:
    proc = subprocess.run(
        ["node", str(HARNESS), str(TARGET)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, f"harness が落ちた:\n{proc.stderr}"
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def snap(result: dict) -> dict:
    # harness は自作 fixture であって環境依存物ではない。scrollHeight 模型が
    # 値を返さないのは「この環境では測れない」ではなく「測る道具が壊れた」なので、
    # skip にすると autofit の 4 契約が 1 件も検査されないまま 5 skipped で緑になる
    # — このテスト自身が塞ごうとしている緑化経路そのものになる。assert で落とす。
    assert result.get("contentModelImplemented"), (
        "harness の scrollHeight 模型が値を返していない。skip すると 4 契約が"
        "未検査のまま緑になるため落とす "
        "(tests/fixtures/skeleton-js-harness.js の hardBody.scrollHeight を確認する)"
    )
    return result["first"]


def test_shrinks_only_until_it_fits(snap: dict) -> None:
    """契約 1: 収まる面は下限まで落とさず、途中で止まる。"""
    assert FS_MIN < snap["easyFontSize"] < 32, snap
    assert not snap["easyFloored"]


def test_never_goes_below_floor(snap: dict) -> None:
    """契約 2: 下限 18px を割らない。読めない文字で「収まった」ことにしない。"""
    assert snap["hardFontSize"] >= FS_MIN, snap


def test_marks_the_slide_it_could_not_fit(snap: dict) -> None:
    """契約 3: 救えなかったことを黙って飲み込まず、属性で表に出す。"""
    assert snap["hardFloored"] and snap["hardOverflow"], snap
    assert not snap["easyOverflow"], snap


def test_fit_scale_matches_the_smaller_axis(snap: dict) -> None:
    """--srg-fit は縦横のうち厳しい側で決まる (640x360 の器に 1280x720 → 0.5)。

    大きい方を採ると面が器からはみ出し、平均を採ると片側が切れる。
    """
    assert snap["fit"] == "0.5", snap


def test_idempotent_across_reapply(result: dict) -> None:
    """契約 4: resize やフォント読み込み完了で何度呼ばれても同じ状態へ収束する。"""
    assert result.get("contentModelImplemented"), (
        "harness の scrollHeight 模型が値を返していない (skip せず落とす。理由は snap fixture 参照)"
    )
    assert result["first"] == result["second"]
