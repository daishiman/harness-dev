"""判定器 (contract_lib.check_skill) の判定力を固定するための受入例。

ここに置くのは **実装ではなく例示**である。P05 の実装者はこのファイルを写して
SKILL.md を作るのではなく、契約 (README.md の対応表) を満たす本文を書くこと。

受入例は tempfile 上に materialize する。checked-in の fixture ツリーを持たない
のは、vendoring 実体の実在検査 (AC-C04-23) が「skill ディレクトリ配下に実体が
あるか」を見るため、tests/ 配下に本物そっくりの skill ツリーを置くと、実装の
有無を取り違える読み手が出るからである。
"""

from __future__ import annotations

from pathlib import Path

VENDORED_REL = "assets/jp-web-design-mode-b.md"

ACCEPT_SKILL_MD = """---
name: ref-handout-design-system
description: 資料の部品カタログを確認するとき、デザイントークンの値を引くとき、アイコン規約を確認するときに読む参照。
disable-model-invocation: false
user-invocable: false
allowed-tools: [Read]
kind: ref
prefix: ref
hierarchy_level: L1
output_language: ja
source: plugin-plans/guide-doc-generator/component-inventory.json#C04
---

# ref-handout-design-system

## Purpose & Output Contract

guide-doc-generator のデザイン言語の参照正本。問い合わせに対して 4 面を引用で返す:
部品カタログの構成データ表現 / CSS 変数トークン一覧 / アイコン規約 / 文章設計の型。

デザイン言語の出典は jp-web-design のモードB「Pop・親しみ」であり、実行時に
外部資産を読まないよう `""" + VENDORED_REL + """` へ vendoring 済み。
ユーザーグローバル資産 (`~/.claude/skills` 配下など) は参照しない。

## 責務境界 (Boundary)

- 入力 = 部品またはトークンの問い合わせ / 出力 = 規範の引用。
- HTML の生成はしない (単独 writer は C11 render-handout.py)。
- 生成物の検証はしない (自己完結・アイコン様式は C16、a11y と印刷は C17、
  言語規約は C18 が持つ)。

## 部品カタログの構成データ表現

部品 id の語彙はこの skill に持たない。問い合わせのたびに正本
`config/handout-parts.json` (owner: C11) のカタログを読んで答える。
用途語彙は `config/handout-purposes.json` (owner: C23)、
セクション種別は `config/handout-sections.json` (writer: C12) を引く。

## CSS 変数トークン

アクセントは 1 色。そこから明度 4 段階を派生させ、`:root` へ展開する。
実値が現れるのはこのブロックだけで、以降の CSS と SVG は `var()` 参照にする。
値の正本は `assets/tokens/<theme>.json` であり、テーマを足す / 差し替えるときは
このファイルを増やす。この skill に実値を書かない。

```css
:root {
  --pop-primary: #0b7285;
  --pop-primary-pastel: #d8f0f4;
  --pop-primary-soft: #7fc4d0;
  --pop-primary-deep: #07505d;
}
.card { border-color: var(--pop-primary-soft); }
body { font-feature-settings: "palt"; }
.num { font-variant-numeric: tabular-nums; }
@keyframes rise-in { from { opacity: 0; transform: translateY(12px); } }
.section { animation: rise-in 480ms both; animation-delay: var(--stagger, 0ms); }
@media (prefers-reduced-motion: reduce) { .section { animation: none; } }
```

- 和文は `font-feature-settings: "palt"` を body に置く。
- 数値は tabular-nums で桁を揃える。
- 入場は rise-in のスタガー。段差はインライン変数 `--stagger` で与え、JS 非依存
  で成立させる (JavaScript を使わない)。
- テーマトークンには `text_limits.block_body_max_chars` (既定 400) が入る。
  このスキーマの owner は C11 であり、超過分の折り畳み規則は C12 の CR-TEXT-FOLD
  が正本。この skill は値も規則も決めない。

## アイコン規約

```html
<svg width="0" height="0" aria-hidden="true">
  <symbol id="hbic-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round">
    <path d="M4 12l5 5L20 6" />
  </symbol>
</svg>
<use href="#hbic-check" />
```

- 様式は viewBox="0 0 24 24" / stroke="currentColor" / fill="none" /
  stroke-linecap="round" の 4 点で固定。
- 定義は `<symbol>`、参照は `<use>`。未使用 symbol は 0 件にする。
- sprite の生成と symbol id の採番は C15 build-icon-sprite.py が行う。
  この skill は様式を答えるだけで生成しない。
- アイコンの代わりに絵文字は使わない。

## 文章設計の型

- 見出しは体言止め、本文は 1 段落 1 論点。
- 数値と単位の間は詰めない。
- 断定できない事柄は「未確定」と書き、推測を事実の形で書かない。
"""

VENDORED_BODY = """# jp-web-design モードB「Pop・親しみ」 (vendored)

出典: jp-web-design skill のモードB。実行時に外部を読まないため本 plugin へ複製した。
アクセント 1 色 + 明度 4 段階、CSS 変数駆動、rise-in スタガー入場を骨格とする。
"""


def write_accept(root) -> Path:
    """受入例の skill ディレクトリを作って返す。"""
    skill_dir = Path(root) / "skills" / "ref-handout-design-system"
    (skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(ACCEPT_SKILL_MD, encoding="utf-8")
    (skill_dir / VENDORED_REL).write_text(VENDORED_BODY, encoding="utf-8")
    return skill_dir
