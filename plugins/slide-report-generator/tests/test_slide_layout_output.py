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
    deck = tmp_path / "skeleton.html"
    deck.write_text(
        "<!doctype html><html><head><style>"
        "html,body{margin:0}.srg-slide{width:1280px;height:720px;overflow:hidden}"
        "</style></head><body>"
        '<section class="srg-slide" data-slide-skeleton="layout-message"></section>'
        "</body></html>",
        encoding="utf-8",
    )
    got = _run(deck)
    assert got.returncode == 0, got.stdout + got.stderr
    assert "system=skeleton" in got.stdout
    assert "slides_checked=1" in got.stdout
