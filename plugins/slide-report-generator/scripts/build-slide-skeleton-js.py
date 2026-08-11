#!/usr/bin/env python3
# /// script
# name: build-slide-skeleton-js
# purpose: assets/slide-templates/frame-contract.json から slide-skeleton.js を決定論生成する。ひな形が宣言する data-autofit (文字の自動縮小) と --srg-fit (面の画面フィット) の実装を 1 か所で持ち、面ごとに JS を書かせない。--check で再生成結果と現物の一致を検証する。
# inputs:
#   - assets/slide-templates/frame-contract.json
#   - CLI: [--root <plugin-root>] [--check]
# outputs:
#   - assets/slide-templates/slide-skeleton.js (--check 時は書かない)
#   - exit: 0=生成成功/一致 / 1=--check で不一致 / 2=契約が読めない
# contexts: [glue]
# network: false
# write-scope: assets/slide-templates/slide-skeleton.js
# dependencies: []
# requires-python: ">=3.10"
# ///
"""ひな形の実行時挙動 (自動縮小・画面フィット) を寸法契約から生成する。

## なぜ必要か

ひな形と README は以前から「`data-autofit` を持つ要素は溢れている間だけ
font-size が下がり、下限 `--srg-fs-min` で止まる」と宣言していた。しかし
その動作を実装したファイルはどこにも存在せず、`--srg-fit` も値を書き込む
側がいなかった。つまり**契約だけがあって履行者がいない**状態で、収まらない
文字はただ切れていた。ここがその履行者。

## 設計の要点

1. **下限で止め、止まったことを表に出す**。無限に縮めて「収まった」ことに
   するのは、溢れているのと同じ壊れ方。下限でなお溢れる面には
   `data-overflow="true"` を付け、検査器と目視の両方から「面を割れ」と
   分かるようにする。
2. **外部依存ゼロ**。図解契約 D12 が成果物内の外部参照を禁じているので、
   このファイルもライブラリを読まない。成果物へは scripts.js へ連結して届ける。
3. **数値を持たない**。下限も canvas 寸法も契約から流し込む。JS 側に
   マジックナンバーを置くと、契約を変えたとき JS だけ取り残される。
4. **冪等**。何度呼んでも同じ状態へ収束するよう、毎回 font-size を初期値へ
   戻してから測り直す (resize やフォント読み込み完了で再実行されるため)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CONTRACT = "assets/slide-templates/frame-contract.json"
_OUT = "assets/slide-templates/slide-skeleton.js"


def _plugin_root(explicit: str | None) -> Path:
    return Path(explicit) if explicit else Path(__file__).resolve().parent.parent


def build_js(c: dict) -> str:
    cv, ty = c["canvas"], c["typography"]
    return f"""/* slide-skeleton.js — 生成物。手で編集しない。
 * 正本: {_CONTRACT}
 * 再生成: python3 scripts/build-slide-skeleton-js.py
 * 検証:   python3 scripts/build-slide-skeleton-js.py --check
 *
 * ひな形が宣言する 2 つの契約を履行する:
 *   data-autofit  溢れている間だけ font-size を下げる (下限 {ty["min"]}px)
 *   --srg-fit     面 {cv["width"]}x{cv["height"]} を親要素へ収める倍率
 * 外部依存なし。成果物へは scripts.js の末尾へ連結して届ける
 * (インライン <script> にはしない。assets/slide-templates/README.md「成果物への届け方」)。
 */
(function () {{
  'use strict';

  var CANVAS_W = {cv["width"]};
  var CANVAS_H = {cv["height"]};
  var FS_MIN = {ty["min"]};
  var STEP = 1;          // 1px ずつ下げる。粗くすると下限手前で無駄に小さくなる
  var MAX_STEPS = 200;   // 測定が病的な場合の保険 (無限ループにしない)

  function slides(root) {{
    return Array.prototype.slice.call((root || document).querySelectorAll('.srg-slide'));
  }}

  /* 面を親要素へ収める倍率を --srg-fit へ書く。
     面の内部は常に {cv["width"]}x{cv["height"]} の絶対座標のままなので、
     画面と PDF は「スケール係数が違うだけの同一物」であり続ける。 */
  function fitStage(root) {{
    slides(root).forEach(function (slide) {{
      var box = slide.parentElement;
      if (!box) return;
      var w = box.clientWidth;
      var h = box.clientHeight;
      if (!w || !h) return;
      var fit = Math.min(w / CANVAS_W, h / CANVAS_H);
      slide.style.setProperty('--srg-fit', String(Math.round(fit * 10000) / 10000));
    }});
  }}

  /* 溢れている間だけ font-size を下げる。下限で止まり、止まったことを表に出す。 */
  function autofitOne(el) {{
    el.style.removeProperty('font-size');           // 冪等にするため毎回初期値へ戻す
    el.removeAttribute('data-autofit-floored');
    var size = parseFloat(getComputedStyle(el).fontSize);
    if (!size) return false;

    var steps = 0;
    while (el.scrollHeight > el.clientHeight + 0.5 && size > FS_MIN && steps < MAX_STEPS) {{
      size -= STEP;
      el.style.fontSize = size + 'px';
      steps++;
    }}

    var stillOverflowing = el.scrollHeight > el.clientHeight + 0.5;
    if (size <= FS_MIN && stillOverflowing) {{
      /* 下限に達してなお溢れている。ここから先は縮めない —
         読めない文字で「収まった」ことにするのは、溢れているのと同じ。
         面を割るか本文を削るべき面として印を付ける。 */
      el.style.fontSize = FS_MIN + 'px';
      el.setAttribute('data-autofit-floored', 'true');
      return true;
    }}
    return false;
  }}

  function autofit(root) {{
    slides(root).forEach(function (slide) {{
      var floored = false;
      Array.prototype.forEach.call(slide.querySelectorAll('[data-autofit]'), function (el) {{
        if (autofitOne(el)) floored = true;
      }});
      if (floored) slide.setAttribute('data-overflow', 'true');
      else slide.removeAttribute('data-overflow');
    }});
  }}

  function apply(root) {{
    autofit(root);   // 先に文字を決めてから
    fitStage(root);  // 面の倍率を測る (順序が逆だと 1 フレーム分ズレる)
  }}

  /* 起動と再実行。フォントの読み込み完了で行数が変わるので、そこでも測り直す。 */
  function boot() {{
    apply(document);
    if (document.fonts && document.fonts.ready) {{
      document.fonts.ready.then(function () {{ apply(document); }});
    }}
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', boot);
  }} else {{
    boot();
  }}

  var pending = null;
  window.addEventListener('resize', function () {{
    if (pending) cancelAnimationFrame(pending);
    pending = requestAnimationFrame(function () {{ pending = null; apply(document); }});
  }});

  /* 印刷の直前に --srg-fit を等倍へ戻し、文字だけ測り直す。
     **二重掛けを止めているのはこの JS ではなく print CSS の方**である
     (`@media print` が transform: none と margin: 0 を宣言するので、
     --srg-fit が残っていても zoom と重ならない)。headless の page.pdf() は
     beforeprint を発火しないことがあり、ここを唯一の防波堤にはできない。
     この handler が担うのは、印刷プレビューを出したブラウザで
     倍率の変わった面に対して autofit を測り直すことだけ。 */
  window.addEventListener('beforeprint', function () {{
    slides(document).forEach(function (s) {{ s.style.setProperty('--srg-fit', '1'); }});
    autofit(document);
  }});
  window.addEventListener('afterprint', function () {{ apply(document); }});

  window.SRGSkeleton = {{ apply: apply, autofit: autofit, fitStage: fitStage }};
}})();
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build-slide-skeleton-js")
    ap.add_argument("--root", default=None)
    ap.add_argument("--check", action="store_true",
                    help="生成せず、現物と生成結果の一致だけを検証する")
    args = ap.parse_args(argv)

    root = _plugin_root(args.root)
    src = root / _CONTRACT
    if not src.is_file():
        sys.stderr.write(f"error: {_CONTRACT} が無い\n")
        return 2
    try:
        contract = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.stderr.write(f"error: {_CONTRACT} が壊れている: {e}\n")
        return 2

    js = build_js(contract)
    out = root / _OUT
    if args.check:
        cur = out.read_text(encoding="utf-8") if out.is_file() else ""
        if cur == js:
            sys.stdout.write("slide-skeleton.js: 契約と一致 -> PASS\n")
            return 0
        sys.stderr.write(
            "slide-skeleton.js が frame-contract.json から生成される内容と異なる。\n"
            "JS を手で編集した場合は編集を scripts/build-slide-skeleton-js.py へ移し、\n"
            "再生成する。\n")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(js, encoding="utf-8")
    sys.stdout.write(f"wrote {_OUT} ({len(js)} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
