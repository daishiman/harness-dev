"""validate-slide-layout.js の L8-void (余白の配り方) を実ブラウザで検証する。

frame-contract.json の fill_policy.min_largest_void_share は「面内の空きを矩形へ分割し、
最大の空き矩形の面積 / 面内余白の総面積」で、下回ると余白が全隙間へ均されている
(均等配置) と判定する。検査は両方向で見る。均等配置の面が落ちることだけを見ると、
常に赤を返す実装でも緑になるため、一箇所へ寄せた面が通ることも同じ形で固定する。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-slide-layout.js"
CONTRACT = PLUGIN_ROOT / "assets" / "slide-templates" / "frame-contract.json"

# 実描画が要るので plugin-local playwright が無い環境では skip する
# (理由は test_slide_layout_output.py と同じ)。
_PLAYWRIGHT = PLUGIN_ROOT / "vendor" / "node_modules" / "playwright"
pytestmark = pytest.mark.skipif(
    not _PLAYWRIGHT.exists(),
    reason=f"plugin-local playwright 未導入 ({_PLAYWRIGHT} 不在): 実描画検査は実行できない",
)

# 面の骨格。canvas 1280x720 / stage は左 64・上 48 の 1152x616。
# kind は code を名乗らせる。低密度が意匠の 4 kind (cover / section-divider /
# quote / message) は契約で void_exempt になっており、そこで検査すると
# 免除の側を測ってしまう。code は充填率のレンジだけが緩い kind で、
# L8-void は既定どおり掛かるので、余白の配り方だけを切り出して見られる。
_HEAD = (
    "<!doctype html><html><head><style>"
    "html,body{margin:0}"
    "*{box-sizing:border-box}"
    ".srg-slide{position:relative;width:1280px;height:720px;overflow:hidden}"
    ".srg-slide__stage{position:absolute;left:64px;top:48px;width:1152px;height:616px}"
    ".srg-slide__main{position:relative;width:1152px;height:616px}"
    ".card{width:1152px;height:100px;background:#eef;font-size:24px;line-height:32px}"
    ".card p{margin:0;padding:8px;font-size:24px;line-height:32px}"
    "</style></head><body>"
    '<section class="srg-slide" data-slide-skeleton="layout-code" data-fill-exception="code">'
    '<div class="srg-slide__stage"><div class="srg-slide__main">'
)
_TAIL = "</div></div></section></body></html>"


def _cards(count: int, gap: int) -> str:
    out = []
    for i in range(count):
        mb = 0 if i == count - 1 else gap
        out.append(
            f'<div class="card" style="margin-bottom:{mb}px">'
            f"<p>余白の配り方を測るための部材 {i + 1}</p></div>"
        )
    return "".join(out)


def _write(path: Path, count: int, gap: int) -> Path:
    path.write_text(_HEAD + _cards(count, gap) + _TAIL, encoding="utf-8")
    return path


def _run(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(VALIDATOR), str(target), "--viewport", "1280x720", *extra],
        cwd=PLUGIN_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _void_share(stdout: str) -> float:
    m = re.search(r"void_share=([0-9.]+)", stdout)
    assert m, f"--measure が void_share を出していない: {stdout}"
    return float(m.group(1))


def test_contract_threshold_is_the_only_source():
    # 閾値をテスト側へ写さない。契約に key が実在することだけを固定する
    # (値が動いたら下の 2 検査は契約の値で判定される)。
    fp = json.loads(CONTRACT.read_text(encoding="utf-8"))["fill_policy"]
    assert isinstance(fp.get("min_largest_void_share"), float)
    assert fp["exceptions"]["code"].get("void_exempt") is None


def test_evenly_spread_void_is_reported(tmp_path: Path):
    # 5 枚を 29px 等間隔で並べ、面の縦を余さず使う (100*5 + 29*4 = 616)。
    # 余白は 4 か所へ均等に配られるので、最大の空き矩形は余白総面積の 1/4 = 0.25。
    deck = _write(tmp_path / "even.html", count=5, gap=29)
    got = _run(deck)
    assert "[L8-void]" in got.stderr, got.stdout + got.stderr

    measured = _run(deck, "--measure")
    share = _void_share(measured.stdout)
    threshold = json.loads(CONTRACT.read_text(encoding="utf-8"))["fill_policy"]["min_largest_void_share"]
    assert share == pytest.approx(0.25, abs=0.01), measured.stdout
    assert share < threshold


def test_void_gathered_into_one_place_passes(tmp_path: Path):
    # 3 枚を隙間なく上へ寄せる。余白は下側の 1 枚の矩形にまとまるので share = 1.0。
    deck = _write(tmp_path / "gathered.html", count=3, gap=0)
    got = _run(deck)
    assert "[L8-void]" not in got.stderr, got.stdout + got.stderr

    measured = _run(deck, "--measure")
    share = _void_share(measured.stdout)
    threshold = json.loads(CONTRACT.read_text(encoding="utf-8"))["fill_policy"]["min_largest_void_share"]
    assert share == pytest.approx(1.0, abs=0.01), measured.stdout
    assert share >= threshold


def test_low_density_kinds_are_exempt(tmp_path: Path):
    # 同じ均等配置でも、低密度が意匠の kind (message) は void_exempt で免除される。
    # 免除が効いていないと、表紙・章扉・引用が面の側に解の無い指摘を受け続ける。
    deck = tmp_path / "exempt.html"
    deck.write_text(
        _HEAD.replace('data-fill-exception="code"', 'data-fill-exception="message"')
        + _cards(5, 29)
        + _TAIL,
        encoding="utf-8",
    )
    got = _run(deck)
    # 「出ないこと」だけを見ると、検査器が起動に失敗しても緑になる (壊して実測済み:
    # VALIDATOR を実在しないパスにすると rc=1 だが stderr に [L8-void] は出ないので通ってしまう)。
    # 検査器が自分の判定を返したことを exit code で先に確かめる。ここは WARNING 止まりなので正常系は 0。
    assert got.returncode == 0, f"検査器が判定を返していない (rc={got.returncode}):\n{got.stderr}"
    # さらに「免除が無ければ鳴る条件が揃っている」ことを測る。これが無いと、たまたま余白が
    # 寄っていて鳴らなかった場合と、免除が効いて鳴らなかった場合を区別できない。
    measured = _run(deck, "--measure")
    assert measured.returncode == 0, f"--measure が判定を返していない (rc={measured.returncode}):\n{measured.stderr}"
    share = _void_share(measured.stdout)
    threshold = json.loads(CONTRACT.read_text(encoding="utf-8"))["fill_policy"]["min_largest_void_share"]
    assert share < threshold, f"免除の検証になっていない配置 (share={share} は下限 {threshold} を下回らない)"
    assert "[L8-void]" not in got.stderr, got.stdout + got.stderr
