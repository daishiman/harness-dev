#!/usr/bin/env python3
"""実体と言及を構造で分ける共通型。

検査器が壊れる形の 1 つに「**実体でないものを実体として読む**」がある。2026-08-14 に
別の検査器・別の言語・別のファイル種で独立に 3 回出た。

  1. validate-linebreak-position.mjs が d3-slide-template.html:952 の `${d.label}` を検出。
     テンプレートリテラルのソース断片
  2. lint-contract-drift.py が known-unfixed.md の表セル
     `box-shadow: var(--shadow-subtle)` を「経路宣言の無い実参照」として検出。
     出荷デッキで見つかった違反を**記録した**行

2 例目が特に悪い。違反を記録した文書が、その記録ゆえに違反判定される。記録を増やすほど
赤が増えるので、検査が記録を増やす動機を奪う。

## 判定は構造だけで行う

「記録っぽい」「表のセルっぽい」といった内容による推測は入れない。外した理由が後から
誰にも分からなくなるため。ここで見るのは構文上その範囲だと決まるものだけ。

## 構造で分けられるかどうかの判断基準

**その文書の見出し・節の構造が、意味の境界と一致しているか。**一致していれば構造で
分けられる。一致していなければ分けられない。ファイル種 (html / markdown) で決まる話
ではなく、**文書ごとに測る**。

  - 分けられる例: references/spec-registry.md の §17 は、節の境界が「規則を定める側」と
    「規則の対象を数える側」の境界と一致している。だから節を割れば構造で分けられる
    (lint-sr-ledger-parity.py が踏んだ問題はこの形で解ける)
  - 分けられない例: references/known-unfixed.md は、**記録と指示が同じ表・同じ記法に
    同居している**。見出しはどちらも区別しないので、構造で割る場所が無い

## 対象は html だけ。markdown は入れていない (2026-08-14 実測)

上の基準を当てた結果として markdown を入れていない。markdown で「インラインコード =
言及」にするのは**間違いだと測って分かった**。実測: この規則を .md へ当てるとフォール
バック無しの `var()` 参照が 393 -> 329 へ 64 件 (16%) 減り、その中に実装の指示が
含まれていた。

  - references/spec-registry.md:177 は SR-8-01 の**標準実装**をインラインコードで書いて
    いる (`.pg-dots__item:nth-child(5n) { width: 1.2vh; height: 1.2vh; }`)。
    読み手はこれを写して使う。剥がすと実在の指摘が黙って消える
  - references/known-unfixed.md の VG08 行は**違反の記録**を同じインラインコードで書いて
    いた

**この 2 つは構造が同一で、意味が正反対。**したがって markdown では、インラインコードは
言及かどうかを決めない。決めるとすれば文書自身の宣言 (記録専用であることを先頭で
明示する等) だが、それは「宣言すれば黙る」仕組みなので _VAR_ROUTE_SOURCES と同じ
埋葬地の性質を持つ。入れるかどうかは持ち主の判断で、ここでは実装しない。

なお html を入れられるのは、`<script>` / `<style>` / コメントの境界が構文で決まって
いて、意味の境界と一致しているからである。同じ基準の適用結果であって、例外ではない。

## 剥がす向きの危険度は対称でない

**剥がして赤が増える誤りは自己修復し、赤が減る誤りは自己隠蔽する。**増える側は書いた
本人の目の前に赤が出るので直る。減る側は誰も何も見ないまま緑になる。上の markdown の
例はまさに減る側で、実装していれば凍結中の accent 2 件が黙って消えていた。
**判定を緩める変更を入れるときは、赤が減る側かどうかを先に見ること。**

なお html のフェンス相当 (script / style) にこの曖昧さは無い。`<script>` の中身が
「読者が読む文章」や「その場所の実装として効く CSS」であることはない。

## 削除でなく同長の空白へ潰す

行番号と文字位置が元ファイルと一致し続けるようにするため。lint-contract-drift.py の
経路マーカーは位置で効くので、長さが変わると照合先が変わる。
validate-linebreak-position.mjs の maskNonProse も同じ理由で同長置換にしてある。

## 剥がした量を見せる

剥がした結果は必ず数として出すこと。「言及だったので除外した」件数が見えないと、
剥がしすぎて全部除外しても緑になる。呼び出し側は spans と dropped を出力へ載せる。
"""

from __future__ import annotations

import re

# html: 読者が読む文章でも、実装として効く記述でもない領域。
# validate-linebreak-position.mjs の NON_PROSE と同じ 3 種を同じ順で持つ。
# 突合は tests/test_mention_mask.py が node 側を実際に走らせて行う
# (どちらかを変えたら落ちる)。
_HTML_NON_PROSE = re.compile(
    r"<script\b[^>]*>[\s\S]*?</script\s*>"
    r"|<style\b[^>]*>[\s\S]*?</style\s*>"
    r"|<!--[\s\S]*?-->",
    re.IGNORECASE,
)

_KINDS = ("html",)


def _blank(s: str) -> str:
    """改行だけ残して同じ長さの空白にする。"""
    return "".join("\n" if c == "\n" else " " for c in s)


def mask(text: str, kind: str) -> tuple[str, list[dict]]:
    """言及の領域を同長の空白へ潰した文字列と、潰した範囲を返す。

    戻り値の 2 番目は呼び出し側が「何をいくつ剥がしたか」を出力へ載せるためのもの。
    黙って剥がすと、剥がしすぎたことが緑として現れる。
    """
    if kind not in _KINDS:
        raise ValueError(
            f"未知の kind: {kind} (使えるのは {', '.join(_KINDS)})。"
            "markdown を入れていない理由は本モジュールの docstring を参照"
        )

    spans: list[dict] = []
    out = list(text)
    for m in _HTML_NON_PROSE.finditer(text):
        head = m.group(0)[:6].lower()
        what = "comment" if head.startswith("<!--") else "style" if head == "<style" else "script"
        spans.append({"kind": what, "start": m.start(), "end": m.end(),
                      "line": text.count("\n", 0, m.start()) + 1})
        out[m.start():m.end()] = list(_blank(m.group(0)))
    return "".join(out), spans


def dropped(raw: str, masked: str, pattern: re.Pattern) -> int:
    """剥がしたことで対象が何件減ったかを数える。

    件数を出さずに剥がすと、剥がしすぎて対象が 0 件になった状態が「違反 0 件」と
    同じ見た目になる。validate-linebreak-position.mjs が checked を出しているのと
    同じ理由で、こちらも減った数を出す。
    """
    return len(pattern.findall(raw)) - len(pattern.findall(masked))
