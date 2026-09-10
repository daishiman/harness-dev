"""vendor 側検査器の fail-closed を固定する。

どちらも「判定できない状態を緑にしない」ことが本体。判定材料 (link 先の CSS /
style genome) を失ったときに黙って通ると、検査は動いているのに何も見ていない
という一番気づけない壊れ方をする。落ちる側を踏んでおく。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PRINT_VALIDATOR = PLUGIN_ROOT / "vendor" / "scripts" / "validate-print.js"
D3_VALIDATOR = PLUGIN_ROOT / "vendor" / "scripts" / "validate-d3.js"
D3_UTILS = PLUGIN_ROOT / "vendor" / "scripts" / "utils.js"

# 印刷 CSS としては完備した中身。P01 以降が見るものはすべて揃っている。
PRINT_CSS = (
    "@media print{"
    " body>*:not(.slider){display:none!important;}"
    " .slider__item{width:297mm;height:210mm;padding:8mm;isolation:isolate;"
    "overflow:hidden;page-break-after:always;print-color-adjust:exact;}"
    " .pagination{color:#141412;}"
    ' .pagination::after{content:counter(page) " / " attr(data-total);}'
    "}"
)
BODY = '<body><div class="slider"><div class="slider__item" data-total="2"></div></div></body>'


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(script), *args], capture_output=True, text=True, check=False
    )


def _print_deck(tmp_path: Path, name: str, head: str) -> Path:
    deck = tmp_path / name
    deck.mkdir(parents=True, exist_ok=True)
    (deck / "styles.css").write_text(PRINT_CSS, encoding="utf-8")
    html = deck / "index.html"
    html.write_text(f"<html><head>{head}</head>{BODY}</html>", encoding="utf-8")
    return html


def _print_report(html: Path) -> tuple[int, dict]:
    got = _run(PRINT_VALIDATOR, str(html), "--json")
    return got.returncode, json.loads(got.stdout)


def test_print_validator_passes_when_stylesheet_resolves(tmp_path: Path) -> None:
    """陽性対照。link 先が解決できる正常な deck では 1 件も落とさない。"""
    html = _print_deck(tmp_path, "ok", '<link rel="stylesheet" href="styles.css">')
    code, report = _print_report(html)
    assert code == 0, json.dumps(report, ensure_ascii=False)
    assert report["criticalFails"] == 0
    assert report["unresolvedStylesheets"] == []


def test_print_validator_fails_when_stylesheet_missing(tmp_path: Path) -> None:
    """link 先が無いだけで印刷 CSS の実体が消えるので、判定に進ませない。"""
    html = _print_deck(tmp_path, "broken", '<link rel="stylesheet" href="missing.css">')
    code, report = _print_report(html)
    assert code == 1
    failed = [r["id"] for r in report["results"] if not r["passed"]]
    assert "P00" in failed
    assert report["unresolvedStylesheets"]


def test_print_validator_flags_only_p00_when_inline_css_is_complete(tmp_path: Path) -> None:
    """本命。inline print CSS 完備 + link 先欠落。

    この形は P01 以降が全部通る。P00 が無いと deck 全体が緑になり、
    「解決できていない link がある」事実だけが消える。落ちるのは P00 だけで
    あることまで見ないと、P00 を消したときに他の 2 件は緑のままで気づけない。
    """
    html = _print_deck(
        tmp_path, "inline-plus-missing",
        f'<link rel="stylesheet" href="missing.css"><style>{PRINT_CSS}</style>',
    )
    code, report = _print_report(html)
    assert code == 1
    assert report["criticalFails"] == 1
    assert report["passed"] == report["total"] - 1
    failed = [r["id"] for r in report["results"] if not r["passed"]]
    assert failed == ["P00"]


def _d3_tree(tmp_path: Path, component: str, genome: str | None) -> Path:
    """検査器一式を tmp へ組む。プラグイン配下の実ファイルは触らない。

    検査器は自分の 1 つ上の assets/ を見るので、その形だけ作れば genome の
    読み込み経路をそのまま踏める。
    """
    root = tmp_path / "vendor"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    components = root / "assets" / "d3-components"
    components.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    shutil.copy(D3_VALIDATOR, root / "scripts" / D3_VALIDATOR.name)
    shutil.copy(D3_UTILS, root / "scripts" / D3_UTILS.name)
    (components / "sample.js").write_text(component, encoding="utf-8")
    if genome is not None:
        (root / "assets" / "style-genome-test.json").write_text(genome, encoding="utf-8")
    return root / "scripts" / D3_VALIDATOR.name


COMPONENT_WITH_COLOR = "export const fill = '#141412';\n"
GENOME = json.dumps({"palette": {"paper": "#F7F6F3", "ink": "#141412"}})


def test_d3_validator_errors_when_genome_is_unreadable(tmp_path: Path) -> None:
    """genome が無いとパレット準拠は判定できない。判定できないものを通さない。"""
    got = _run(_d3_tree(tmp_path / "a", COMPONENT_WITH_COLOR, None))
    assert got.returncode != 0
    assert "パレット準拠を判定できません" in got.stdout + got.stderr


def test_d3_validator_reads_palette_from_genome(tmp_path: Path) -> None:
    """陽性対照。genome を読めたときはパレット判定で止まらない。

    ここを見ないと上の 1 件は「常に落ちるだけ」の検査と区別がつかない。
    """
    got = _run(_d3_tree(tmp_path / "b", COMPONENT_WITH_COLOR, GENOME))
    out = got.stdout + got.stderr
    assert "パレット準拠を判定できません" not in out
    # 判定を飛ばしたのではなく、genome の色として通ったことまで見る。
    assert "成功: 1 項目" in out
