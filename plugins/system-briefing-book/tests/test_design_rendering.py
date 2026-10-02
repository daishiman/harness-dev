"""案件の配色がボードと単独配布のまとめで同じ役割に届くことを実ブラウザで確認する。"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conftest import PLUGIN_ROOT, needs_browser, node_eval, run_script


@needs_browser
@pytest.mark.parametrize("custom", [False, True])
def test_board_and_standalone_book_share_design(case_with_png: Path, tmp_path: Path, custom: bool) -> None:
    # 案件の配色は標準カラーへの上書き。基本色だけを変えれば、ボードとまとめの役割が付いてくる
    overlay = ":root { --p-brand-indigo: #56338A; --p-ink: #30243D; }\n" if custom else None
    css = node_eval(
        'import { composeTokens } from "./lib/palette.mjs";\n'
        f'console.log(JSON.stringify(composeTokens({json.dumps({"css": overlay, "label": "案件"}) if custom else "undefined"})));'
    )
    (case_with_png / "_src/tokens.css").write_text(css, encoding="utf-8")
    (case_with_png / "_src/common.css").write_bytes((PLUGIN_ROOT / "assets/css/common.css").read_bytes())
    # This test covers CSS delivery; fixture images carry no renderer receipt.
    for png in case_with_png.glob("*.png"):
        os.utime(png, None)
    rc, result, err = run_script("build-briefing-book", "--dir", str(case_with_png))
    assert rc == 0, (result, err)
    standalone = tmp_path / "delivery.html"
    standalone.write_bytes(Path(result["out"]).read_bytes())
    urls = [(case_with_png / "_src/02_phone-send.html").as_uri(), standalone.as_uri()]
    styles = node_eval('''
import {launchBrowser, findBrowser} from "./lib/browser-session.mjs";
const browser = await launchBrowser(findBrowser());
try {
  const page = await browser.newPage({width: 1440, height: 1000});
  const results = [];
  for (const [i, url] of URLS.entries()) {
    await page.goto(url);
    results.push(await page.evaluate(`(() => {
      const style = selector => getComputedStyle(document.querySelector(selector));
      return {
        ink: style('body').color,
        font: style('body').fontFamily,
        brand: style('${i === 0 ? '.board-head .kicker' : '.tb-title b'}').color,
        secondary: style('${i === 0 ? '.board-head .lead' : '.cover .sub'}').color,
        scheme: style(':root').colorScheme
      };
    })()`));
  }
  console.log(JSON.stringify(results));
} finally { await browser.close(); }
'''.replace("URLS", json.dumps(urls)), timeout=180)
    assert styles[0] == styles[1]
    assert styles[1]["brand"] == ("rgb(86, 51, 138)" if custom else "rgb(23, 71, 181)")
    assert styles[1]["ink"] == ("rgb(48, 36, 61)" if custom else "rgb(20, 35, 59)")
    assert styles[1]["scheme"] == "light"
