"""契約を読めないときに既定値へ落ちない (fail-closed) ことを固定する。

Unknown slide types must never become a plausible message slide。同じ型の話として、
実描画検査器が frame-contract.json の観測点を読めないときに自前の viewport で
走り出さないことも、ここで踏んでおく。踏まれない fail-closed は fail-open へ
化けても誰も気づかない。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RENDERER = PLUGIN_ROOT / "vendor" / "scripts" / "render-slide.cjs"
LAYOUT_VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-slide-layout.js"


def test_unknown_slide_type_fails_without_writing_deck(tmp_path: Path) -> None:
    source = tmp_path / "structure.json"
    output = tmp_path / "deck"
    source.write_text(
        json.dumps(
            {
                "meta": {"title": "fail closed"},
                "slides": [
                    {"slideType": "diagram-does-not-exist", "content": {"title": "x"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["node", str(RENDERER), str(source), "--out", str(output), "--no-validate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 3
    assert "unknown slideType or missing template" in proc.stderr
    assert not (output / "index.html").exists()


def _validator_with_contract(tmp_path: Path, contract: str | None) -> Path:
    """契約を差し替えた検査器一式を tmp へ組む。プラグイン配下の実ファイルは触らない。

    検査器は自分の 1 つ上を PLUGIN_ROOT とみなして契約を引くので、その形だけ
    tmp に作れば観測点の読み込み経路をそのまま踏める。playwright は要らない
    (観測点の解決は browser 起動より前に済む)。
    """
    root = tmp_path / "plugin"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    templates = root / "assets" / "slide-templates"
    templates.mkdir(parents=True, exist_ok=True)
    shutil.copy(LAYOUT_VALIDATOR, root / "scripts" / LAYOUT_VALIDATOR.name)
    if contract is not None:
        (templates / "frame-contract.json").write_text(contract, encoding="utf-8")
    return root / "scripts" / LAYOUT_VALIDATOR.name


def _run_validator(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_layout_validator_refuses_to_run_without_contract_viewports(
    tmp_path: Path,
) -> None:
    """契約が無い / 観測点が無い場合に、自前の viewport で走り出さない。"""
    deck = tmp_path / "deck.html"
    deck.write_text("<!doctype html><html><body></body></html>", encoding="utf-8")

    missing = _validator_with_contract(tmp_path / "a", None)
    got = _run_validator(missing, str(deck))
    assert got.returncode == 1
    assert "viewports.default" in got.stderr

    empty = _validator_with_contract(
        tmp_path / "b", json.dumps({"canvas": {"width": 1280, "height": 720}})
    )
    got = _run_validator(empty, str(deck))
    assert got.returncode == 1
    assert "viewports.default" in got.stderr


def test_layout_validator_reads_viewports_from_contract(tmp_path: Path) -> None:
    """陽性対照。観測点を読めたときは観測点では止まらず、次の検査へ進む。

    ここで止まらないことまで見ないと、上の 2 件は「常に 1 で落ちるだけ」の
    検査と区別がつかない。
    """
    contract = json.dumps({"viewports": {"default": [{"width": 1280, "height": 720}]}})
    script = _validator_with_contract(tmp_path / "c", contract)

    got = _run_validator(script, str(tmp_path / "no-such-deck.html"))
    assert got.returncode == 1
    assert "viewports.default" not in got.stderr
    assert "ファイルが無い" in got.stderr

    # --viewport を明示した場合は契約を引かない (壊れた契約でも観測点では止まらない)。
    broken = _validator_with_contract(tmp_path / "d", "{ not json")
    got = _run_validator(broken, str(tmp_path / "no-such-deck.html"), "--viewport", "1280x720")
    assert got.returncode == 1
    assert "viewports.default" not in got.stderr
    assert "ファイルが無い" in got.stderr


def test_structural_slide_carries_referential_declaration() -> None:
    script = f"""
const {{ enrichSlideContext }} = require({json.dumps(str(RENDERER))});
const ctx = enrichSlideContext({{
  slideType: 'diagram-er',
  content: {{
    title: 'ER',
    entities: [{{name:'顧客', fields:['id']}}, {{name:'注文', fields:['顧客']}}],
    relations: [{{from:'顧客', to:'注文'}}],
  }},
}}, 0);
process.stdout.write(ctx.svg);
"""
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert "data-srg-declaration=" in proc.stdout
    assert "&quot;entities&quot;" in proc.stdout
