"""validate-slide-layout.js の入力・体系判定を実ブラウザで検証する。"""
from __future__ import annotations

import subprocess
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-slide-layout.js"


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
