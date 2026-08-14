"""validate-slide-layout.js の入力・体系判定を実ブラウザで検証する。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-slide-layout.js"

# 本ファイルの 3 検査 (L0 の 0 件判定 / L7 の体系混在 / PASS 経路) はいずれも
# ページを実際に描いてから DOM を数えるため、plugin-local な playwright と
# Chromium が無いと動かない。vendor/node_modules は gitignore で CI では
# 存在しないので、無い環境では skip する。「playwright が実在すること」自体は
# scripts/validate-output-mode.py の preflight (test_validate_output_mode.py)
# が別途固定しており、ここで代替検証すると browser 無しで通る偽の緑になる。
_PLAYWRIGHT = PLUGIN_ROOT / "vendor" / "node_modules" / "playwright"
pytestmark = pytest.mark.skipif(
    not _PLAYWRIGHT.exists(),
    reason=f"plugin-local playwright 未導入 ({_PLAYWRIGHT} 不在): 実描画検査は実行できない",
)


def _run(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(VALIDATOR), str(target), "--viewport", "1280x720", "--strict"],
        cwd=PLUGIN_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_rejects_directory_and_zero_slide(tmp_path: Path):
    assert _run(tmp_path).returncode == 1
    empty = tmp_path / "empty.html"
    empty.write_text("<!doctype html><html><body></body></html>", encoding="utf-8")
    got = _run(empty)
    assert got.returncode == 1
    assert "slide 要素が 0 件" in got.stderr


def test_rejects_mixed_engine_and_skeleton_markup(tmp_path: Path):
    deck = tmp_path / "mixed.html"
    deck.write_text(
        "<!doctype html><html><body>"
        '<div class="slider__item" data-slide="1"></div>'
        '<section class="srg-slide" data-slide-skeleton="layout-message"></section>'
        "</body></html>",
        encoding="utf-8",
    )
    got = _run(deck)
    assert got.returncode == 1
    assert "同一 deck に混在" in got.stderr


def test_accepts_single_skeleton_system(tmp_path: Path):
    # この検査の主題は「単一体系を受理するか」だが、--strict では L8 (充填率) と
    # L9 (縦の残余) も fail へ昇格する。空の面は充填率 0 で必ず落ちるため、
    # 面の体裁を持った最小の内容を入れて契約のレンジに実際に収める。
    # 収まる根拠 (canvas 1280x720 / stage 64,48,1152x616 / kind=message 0.25-0.55):
    #   充填率 = (h2 1152x64 + card 500x400) / (1152x616) = 0.39
    #   縦の残余 = (616 - 512) / 616 = 0.17、上下余白は 52px ずつで非対称 0
    deck = tmp_path / "skeleton.html"
    deck.write_text(
        "<!doctype html><html><head><style>"
        "html,body{margin:0}"
        ".srg-slide{position:relative;width:1280px;height:720px;overflow:hidden}"
        ".srg-slide__stage{position:absolute;left:64px;top:48px;width:1152px;height:616px}"
        ".srg-slide__main{position:absolute;left:0;top:52px;width:1152px;height:512px}"
        ".srg-slide__main h2{margin:0;height:64px;font-size:40px;line-height:64px}"
        ".card{margin-top:48px;width:500px;height:400px;background:#eef}"
        ".card p{margin:0;padding:16px;font-size:24px;line-height:36px}"
        "</style></head><body>"
        '<section class="srg-slide" data-slide-skeleton="layout-message">'
        '<div class="srg-slide__stage"><div class="srg-slide__main">'
        "<h2>単一体系の面</h2>"
        '<div class="card"><p>この面は体系判定のための最小の内容を持つ。'
        "充填率と縦の残余の契約を実際に満たすので、--strict でも赤にならない。"
        "空の面で通してしまうと、体系判定だけが緑で他の契約は素通りになる。</p></div>"
        "</div></div></section>"
        "</body></html>",
        encoding="utf-8",
    )
    got = _run(deck)
    assert got.returncode == 0, got.stdout + got.stderr
    assert "system=skeleton" in got.stdout
    assert "slides_checked=1" in got.stdout
