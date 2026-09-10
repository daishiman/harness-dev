#!/usr/bin/env python3
# /// script
# name: build-slide-skeleton-css
# purpose: assets/slide-templates/frame-contract.json (幾何) と vendor/scripts/style-builder.cjs の SPEC.colors (配色) から slide-skeleton.css を決定論生成する。面の寸法・chrome 予約帯・A4 レターボックス印刷指定・色トークンを単一の値源から作り、ひな形 CSS に数値も色も手写ししない。--check で再生成結果と現物の一致を検証する (fail-closed)。
# inputs:
#   - assets/slide-templates/frame-contract.json
#   - vendor/scripts/style-builder.cjs (SPEC.colors = 配色の正本・read-only)
#   - vendor/scripts/svg-kit.cjs (色相名の現行値 = fallback の出所・read-only)
#   - CLI: [--root <plugin-root>] [--check]
# outputs:
#   - assets/slide-templates/slide-skeleton.css (--check 時は書かない)
#   - references/theme-style.md の生成区間 (手書き経路が貼る :root・--check 時は書かない)
#   - exit: 0=生成成功/一致 / 1=--check で不一致 / 2=契約が読めない
# contexts: [glue]
# network: false
# write-scope: assets/slide-templates/slide-skeleton.css, references/theme-style.md (生成区間のみ)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""ページひな形が使う CSS を寸法契約から生成する。

## なぜ生成するのか

面の数値 (1280x720 / chrome 48-56-64 / stage 1152x616 / A4 レターボックス
21.47mm) は、ひな形 22 枚・レンダラ・検査器・印刷 CSS の 4 か所で同じ値を
必要とする。手で写すと必ずどこか 1 か所が取り残される。実際、既存実装では
「chrome の予約余白 (--pg-reserve-*)」と「chrome の実物 (pagination.css)」が
別々に定義されていたため、インデックス位置とページ番号がズレていた。

そこで数値の正本を `frame-contract.json` 1 つに閉じ、CSS は生成物にする。
`--check` は生成結果と現物を突合するので、CSS を手で編集した瞬間に赤くなる。

## 面と印刷の関係 (ズレを構造的に消す)

面の内部は常に 1280x720 の絶対座標。画面表示は外側の `transform: scale()`
だけで拡縮する。したがって画面と PDF は「スケール係数が違うだけの同一物」で、
要素の相対位置は定義上ズレない。

印刷は A4 横 (297x210mm)。幅で決まるので 297mm / 1280px = 0.2320mm/px、
面の高さは 720px * 0.2320 = 167.06mm。A4 の高さ 210mm との差 42.94mm が
上下に 21.47mm ずつのレターボックス帯として出る。`cover` による端切れは禁止。

## 色をここで「定義」する理由

以前は `var(--srg-surface, #FFFFFF)` のように**使用側だけ**が色を持ち、
`--srg-surface` を定義する場所がどこにも無かった。CSS カスタムプロパティは
定義が無ければ fallback が常に最終値になるので、これは既定値ではなく
**上書き不能な定数**として振る舞う。しかもその定数 (#FFFFFF / #F8F7F0 /
#DCD7BA) は本 plugin の実パレット (SPEC.colors) に存在しない値だった。
つまり「仕様外の配色が唯一の正解として全 deck へ配られる」状態だった。

そこで配色の正本を `vendor/scripts/style-builder.cjs` の `SPEC.colors`
1 つに固定し、ここでは **`:root` に `--srg-*` を定義する**。定義の中身は
`var(--ink, #141412)` のようにパレット変数への参照 + 生成された
fallback なので、

- deck に読み込まれたとき: `:root` のパレット変数が効く (テーマ追随)
- ひな形を単体で開いたとき: fallback が効く (SR-2-08 の自己完結要件)

の両方を満たす。fallback は手書きせず SPEC.colors から生成するので、
パレットを変えれば `--check` が即座に不一致を検出する。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_CONTRACT = "assets/slide-templates/frame-contract.json"
_PALETTE_SRC = "vendor/scripts/style-builder.cjs"
_SERIES_SRC = "vendor/scripts/svg-kit.cjs"
_OUT = "assets/slide-templates/slide-skeleton.css"
_THEME_DOC = "references/theme-style.md"

# theme-style.md の中で生成器が管理する区間。この外側は人が書く。
_THEME_BEGIN = "<!-- BEGIN GENERATED: palette (scripts/build-slide-skeleton-css.py) -->"
_THEME_END = "<!-- END GENERATED: palette -->"

# SPEC.colors のキー → deck の :root が持つパレット変数名。
# この対応は vendor の buildRootVars() が実際に出力している名前と 1:1。
_PALETTE_VARS = {
    "paper": "--paper",
    "ink": "--ink",
    "inkMuted": "--fg-muted",
    "hairline": "--hairline",
}

# 手書き経路が使う名前 → パレット変数名。名前の集合は決定論経路と別で、
# ここでは統合しない (統合すると既存の手書き記述が宣言ごと無効になる)。
# 値だけをパレットへ寄せて、色の実体を SPEC.colors 1 つに閉じる。
_HANDWRITTEN_ALIASES = [
    ("--bg-dark", "--paper", "面の地"),
    ("--fg", "--ink", "本文"),
    ("--fg-dim", "--fg-muted", "注記・補助"),
    ("--bg-dim", "--paper", "沈めた地。面の色数は 3 なので地は紙のまま"),
    ("--bg-card", "--paper", "カードの地。囲いは罫だけで作るので地は紙のまま"),
    ("--sumi-ink", "--paper", "面の地の最下段。名前は本家パレットのスロット名で、暗いという意味ではない"),
]

# 色相名。図版の系列色として参照されているが、定義はどこにも無い。
# 値の由来は下の read_legacy_hues() を読むこと。
#
# 当初は 6 名だった。うち 2 名は**別名が別の色を主張していただけ**で実体が無く、
# 名前ごと落とした:
#   --spring-violet -> --wave-blue と同値 (#4B6681)
#   --fuji-gray     -> --fg-dim   と同値 (#6A6A68)
# 同じ値に 2 つ名前があると、読む側はそれを 2 種類の区別として扱う。
# 参照側 (図解経路の golden 408 + 17 件) も同じ便で寄せてある。
_LEGACY_HUES = [
    "--sakura-pink", "--wave-blue", "--wave-aqua", "--autumn-yellow",
]


def read_legacy_hues(root: Path) -> dict[str, str]:
    """色相名の現行値を svg-kit.cjs の fallback から読む。

    ## なぜ「一時定義」が要るのか

    これらは `var(--wave-blue, #4B6681)` の形で多数参照されているが、
    `:root` にも生成区間にも定義が無い。fallback すら無い参照は
    **宣言ごと無効**になって色が落ちている。参照側の fallback を外す作業が
    この定義待ちで止まっているので、規範 (符号系) が決まるまでのあいだ、
    今出ているのと同じ値で名前だけを定義する。

    ## なぜ値を書き写さないのか

    手で `--sakura-pink: #141412` と書くと、正本が動いた日に静かにズレる。
    そこで `svg-kit.cjs` が実際に出している fallback を読んで生成する。
    同じ名前に違う hex が付いていたら例外にするので、正本側が食い違った
    瞬間 `--check` が赤くなる。

    ## なぜ移行後の値 (符号系の fill) から作らないのか

    符号系は 1 名を (fill, stroke, dash) の組へ写す。CSS 変数は組を運べない
    ので、そこから作れるのは fill だけになる。地 + 輪郭で区別する系列は
    fill が紙色なので、`--autumn-yellow` のような塗り用の名前が
    「紙色・輪郭なし」になって図形が消える。互換名の役目は移行前の見た目を
    1 ドットも変えずに保つことなので、値は移行前の svg-kit の fallback から
    作る。組は `seriesStyle()` が運ぶ。

    ## いつ消えるか

    参照側が `seriesStyle()` へ移った時点。人の記憶に頼らないよう、互換名の
    定義と `seriesStyle(` が同時に存在したら落ちるテストを
    `tests/test_legacy_hue_aliases.py` に置いてある。
    """
    src = (root / _SERIES_SRC).read_text(encoding="utf-8")
    hues: dict[str, str] = {}
    for name in _LEGACY_HUES:
        found = {
            m.group(1).upper()
            for m in re.finditer(rf"var\(\s*{re.escape(name)}\s*,\s*(#[0-9A-Fa-f]{{6}})\s*\)", src)
        }
        if not found:
            raise ValueError(
                f"{_SERIES_SRC} に {name} の fallback が無い。"
                f" 符号系へ移行済みなら互換名ごと削除する (tests/test_legacy_hue_aliases.py 参照)"
            )
        if len(found) > 1:
            raise ValueError(f"{_SERIES_SRC} の {name} に複数の値 {sorted(found)} が付いている")
        hues[name] = found.pop()
    return hues


def read_palette(root: Path) -> dict[str, str]:
    """配色の正本 SPEC.colors を vendor から読む (read-only・vendor は改変しない)。

    ここで読むのは「同じ色を 2 か所に書かない」ため。散文表や CSS へ写すと、
    パレットを変えたとき写した側が必ず取り残される。
    """
    src = (root / _PALETTE_SRC).read_text(encoding="utf-8")
    m = re.search(r"\bcolors:\s*\{(.*?)\n\s*\},", src, flags=re.S)
    if not m:
        raise ValueError(f"{_PALETTE_SRC} から SPEC.colors を読み取れない")
    pal = dict(re.findall(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'", m.group(1)))
    missing = sorted(set(_PALETTE_VARS) - set(pal))
    if missing:
        raise ValueError(f"{_PALETTE_SRC} の SPEC.colors に {missing} が無い")
    return pal


def _rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _mix(fg_hex: str, bg_hex: str, alpha: float) -> str:
    """fg を alpha の割合で bg へ重ねた不透明色を作る。

    半透明のまま置かない理由: 印刷経路と画像化経路では合成結果が環境依存に
    なるため。生成時に solid へ焼いておけば、画面・PDF・画像で同じ色が出る。
    """
    f, b = _rgb(fg_hex), _rgb(bg_hex)
    return "#" + "".join(f"{round(f[i] * alpha + b[i] * (1 - alpha)):02X}" for i in range(3))


def _tokens(pal: dict[str, str]) -> list[tuple[str, str, str]]:
    """(トークン名, 値, 用途コメント) を返す。値は必ずパレット由来。"""
    surface = pal["paper"]
    fg = pal["ink"]
    r, g, b = _rgb(surface)
    return [
        ("--srg-surface", f"var({_PALETTE_VARS['paper']}, {surface})", "面の地色"),
        ("--srg-fg", f"var({_PALETTE_VARS['ink']}, {fg})", "本文色"),
        ("--srg-fg-muted", f"var({_PALETTE_VARS['inkMuted']}, {pal['inkMuted']})", "注記・出典"),
        ("--srg-focal", f"var({_PALETTE_VARS['ink']}, {fg})",
         "焦点色。色相ではなく濃度と反転で作るので本文色と同じインクになる"),
        ("--srg-link", f"var({_PALETTE_VARS['ink']}, {fg})", "ナビ・リンク"),
        ("--srg-warn", f"var({_PALETTE_VARS['inkMuted']}, {pal['inkMuted']})",
         "自動縮小が下限に達した面の警告枠。破線という形で区別し、色は足さない"),
        # 面の色数は 3 (VGCONST_001)。カードの地を独自に持つとその 1 つを消費する
        # うえ、囲いを外した意匠と食い違うので、地は面と同じ紙にする。
        ("--srg-surface-2", f"var({_PALETTE_VARS['paper']}, {surface})", "カードの地色 (面と同じ紙)"),
        # 罫は vendor の --hairline (本文色 15% を紙へ重ねた solid) と同一値。
        # ここで別の濃度を決めると罫の太さ感が deck と skeleton で食い違う。
        ("--srg-hairline", f"var({_PALETTE_VARS['hairline']}, {pal['hairline']})", "罫線 (本文色 15%)"),
        ("--srg-letterbox", _mix(fg, surface, 0.08), "面の外側 (本文色 8%)"),
        ("--srg-scrim", f"rgba({r}, {g}, {b}, .88)", "全面画像の上に題を置くときの下敷き"),
    ]


def build_theme_block(pal: dict[str, str], hues: dict[str, str]) -> str:
    """手書き経路が成果物へ貼る `:root` ブロックを SPEC.colors から作る。

    なぜ文書の中へ生成するのか: 手書き経路の「実装」は references/theme-style.md
    そのもので、LLM がこの `:root` を読んで成果物の styles.css へ書き出す。
    つまり文書が実装なので、文書の中に値を手で書いた瞬間そこが第 2 の正本になる。

    なぜ別 CSS への link にしないのか: 出荷される deck の styles.css は
    index.html へインライン展開されたコピーで、ブラウザは外部 CSS を読んでいない。
    link で足しても「見えるが効かない」ファイルが 1 つ増えるだけになる。加えて
    別ファイルは同期で消えたとき無言で既定色へ落ちる (壊れて見えない故障)。
    """
    need = ["paper", "ink", "inkMuted", "hairline", "tone1", "tone2", "tone3"]
    missing = [k for k in need if k not in pal]
    if missing:
        raise ValueError(f"{_PALETTE_SRC} の SPEC.colors に {missing} が無い")
    names = {
        "--paper": pal["paper"], "--ink": pal["ink"],
        "--fg-muted": pal["inkMuted"], "--hairline": pal["hairline"],
        "--tone-1": pal["tone1"], "--tone-2": pal["tone2"], "--tone-3": pal["tone3"],
    }
    notes = {
        "--paper": "紙", "--ink": "インク", "--fg-muted": "注記 (インク 62%)",
        "--hairline": "罫 (インク 15%)",
        "--tone-1": "図版の淡い段", "--tone-2": "図版の中間段", "--tone-3": "図版の濃い段",
    }
    pal_lines = "\n".join(f"  {n}: {v};  /* {notes[n]} */" for n, v in names.items())
    alias_lines = "\n".join(
        f"  {name}: var({target});  /* {note} */" for name, target, note in _HANDWRITTEN_ALIASES
    )
    # 色相名は値を書き写さず、svg-kit の fallback と一致するパレット変数を指す。
    # パレットに無い値だったときだけ hex を直に置く (その状態は正本のズレを意味する)。
    by_value = {v.upper(): n for n, v in names.items()}
    hue_lines = "\n".join(
        f"  {name}: var({by_value[value]});  /* {value} */" if value in by_value
        else f"  {name}: {value};  /* パレットに無い値 */"
        for name, value in ((n, hues[n]) for n in _LEGACY_HUES)
    )
    return f"""```css
/* 生成物。手で編集しない。編集しても再生成で消える。
 * 値の正本: {_PALETTE_SRC} の SPEC.colors
 * 再生成:   python3 scripts/build-slide-skeleton-css.py
 * 検証:     python3 scripts/build-slide-skeleton-css.py --check
 *
 * 手書き経路はこのブロックを成果物の styles.css へそのまま貼る。
 * 外部 CSS への link にはしない (出荷 deck の styles.css は index.html へ
 * インライン展開された写しで、外部 CSS はブラウザに読まれていない)。
 */
:root {{
  /* ---- パレット (色数 3: 紙・インク・反転面) ---- */
{pal_lines}

  /* ---- 手書き経路の名前。値はパレットを指すだけで実体を持たない ---- */
{alias_lines}

  /* ---- 色相名 (一時定義)。値の出所は {_SERIES_SRC} の fallback ----
   * 定義が無いせいで 265 箇所が宣言ごと無効になっていたので、今出ているのと
   * 同じ値で名前だけを与える。見た目は 1 ドットも変わらない。
   * 色相を戻したのではない。区別は色でなく (濃度 x 形) の系列へ移す設計で、
   * 参照側が seriesStyle() を呼ぶようになった時点でこの節ごと消える。
   * 消し忘れは tests/test_legacy_hue_aliases.py が落として知らせる。
   */
{hue_lines}
}}
```"""


def apply_theme_block(root: Path, block: str, check: bool) -> tuple[bool, str]:
    """theme-style.md の管理区間を差し替える。戻り値 (一致したか, メッセージ)。

    区間標識が無ければ失敗させる (fail-closed)。黙って追記すると、
    どこが生成物か分からない写しが増える。
    """
    path = root / _THEME_DOC
    if not path.is_file():
        return False, f"{_THEME_DOC} が無い"
    src = path.read_text(encoding="utf-8")
    if src.count(_THEME_BEGIN) != 1 or src.count(_THEME_END) != 1:
        return False, f"{_THEME_DOC} に生成区間の標識が 1 組ちょうど無い"
    head, rest = src.split(_THEME_BEGIN, 1)
    _, tail = rest.split(_THEME_END, 1)
    want = f"{head}{_THEME_BEGIN}\n{block}\n{_THEME_END}{tail}"
    if src == want:
        return True, f"{_THEME_DOC}: 正本と一致 -> PASS"
    if check:
        return False, (
            f"{_THEME_DOC} の生成区間が SPEC.colors から生成される内容と異なる。\n"
            "文書側を手で直さず `python3 scripts/build-slide-skeleton-css.py` で再生成する。")
    path.write_text(want, encoding="utf-8")
    return True, f"wrote {_THEME_DOC} (生成区間 {len(block)} bytes)"


def _plugin_root(explicit: str | None) -> Path:
    return Path(explicit) if explicit else Path(__file__).resolve().parent.parent


def build_css(c: dict, pal: dict[str, str]) -> str:
    cv, ch, st = c["canvas"], c["chrome"], c["stage"]
    sp, ty, pr = c["spacing"], c["typography"], c["print_skeleton"]
    # fill_policy / vertical_margin_policy は CSS へ写さない。検査器
    # (scripts/validate-slide-layout.js) が frame-contract.json を直接読むため、
    # CSS 変数として出しても消費者ゼロの第 3 の写しになり、契約を動かすたびに
    # 再生成が要る割にどれが正本か分からなくなる。
    tokens = "\n".join(
        f"  /* {note} */\n  {name}: {value};" for name, value, note in _tokens(pal)
    )
    return f"""/* slide-skeleton.css — 生成物。手で編集しない。
 * 幾何の正本: {_CONTRACT}
 * 配色の正本: {_PALETTE_SRC} の SPEC.colors
 * 再生成: python3 scripts/build-slide-skeleton-css.py
 * 検証:   python3 scripts/build-slide-skeleton-css.py --check
 *
 * 面の内部は 1280x720 の絶対座標。画面表示は --srg-fit の scale だけで拡縮する。
 * 画面と PDF はスケール係数が違うだけの同一物になり、位置がズレない。
 */

/* ---- 色トークン ----------------------------------------------------------- */
/* すべて SPEC.colors から生成する。ここが --srg-* の唯一の定義場所で、
   使用側 (下記の各規則・ひな形 HTML) は hex を持たない。
   値の形は var(パレット変数, 生成 fallback):
     deck に読み込まれたとき   -> パレット変数が効く (テーマ追随)
     ひな形を単体で開いたとき -> fallback が効く (自己完結)
   fallback を手書きしないので、パレットを変えれば --check が不一致を出す。 */
:root {{
{tokens}

  /* ---- 幾何 (frame-contract.json 由来) ---- */
  --srg-canvas-w: {cv["width"]}px;
  --srg-canvas-h: {cv["height"]}px;
  --srg-chrome-top: {ch["top"]}px;
  --srg-chrome-bottom: {ch["bottom"]}px;
  --srg-chrome-side: {ch["side"]}px;
  --srg-stage-w: {st["width"]}px;
  --srg-stage-h: {st["height"]}px;
  --srg-gap: {sp["gap"]}px;
  --srg-gap-tight: {sp["gap_tight"]}px;
  --srg-gap-loose: {sp["gap_loose"]}px;
  --srg-title-h: {sp["title_block_height"]}px;
  --srg-radius: {sp["radius"]}px;
  --srg-fs-title: {ty["title"]}px;
  --srg-fs-heading: {ty["heading"]}px;
  --srg-fs-subheading: {ty["subheading"]}px;
  --srg-fs-body: {ty["body"]}px;
  --srg-fs-note: {ty["note"]}px;
  --srg-fs-caption: {ty["caption"]}px;
  /* 自動縮小の下限。これを下回る文字を面に置かない (読めない文字で「収まった」
     ことにするのは、溢れているのと同じくらい壊れている)。 */
  --srg-fs-min: {ty["min"]}px;
  /* 画面での拡縮率。レンダラが実測して上書きする。既定は等倍。 */
  --srg-fit: 1;
}}

/* ---- 面の外枠 ------------------------------------------------------------ */
/* deck 側の枠。面は常に固定 px で、ここだけが画面幅に追随する。 */
.srg-deck {{
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--srg-letterbox);
}}

/* 画面表示のときだけ deck に自前の高さを与える。
   deck が中身で高さを決めると clientHeight は面の高さ ({cv["height"]}px) そのものに
   なり、fitStage の h / {cv["height"]} が常に約 1 になる — つまり**縦方向のフィットが
   一度も効かず**、倍率が横幅だけで決まる。縦長の窓では面が下へはみ出し、
   大画面では拡大されないまま中央に小さく残る。
   印刷側は @page が帯を作るのでこの指定を持ち込まない (@media screen で閉じる)。 */
@media screen {{
  .srg-deck {{
    width: 100%;
    min-height: 100vh;
  }}
}}

.srg-slide {{
  position: relative;
  width: var(--srg-canvas-w);
  height: var(--srg-canvas-h);
  flex: none;
  transform: scale(var(--srg-fit));
  transform-origin: center center;
  /* transform は**見た目だけ**を縮め、レイアウト box は {cv["width"]}x{cv["height"]} のまま残る。
     このままだと --srg-fit で縮めた面の周りに、縮めた分の空きが予約され続ける
     (面が 1 枚なら中央寄せに紛れて見えないが、deck に面が並ぶと面と面の間へ
     そのまま出る = 封じ手で潰したはずの空白過多の再発点)。
     同じ --srg-fit から負の margin を引いて、予約 box を見た目の box へ一致させる。
     fit=1 のとき margin は 0 なので、等倍表示の挙動は変わらない。 */
  margin: calc(var(--srg-canvas-h) * (var(--srg-fit) - 1) / 2)
          calc(var(--srg-canvas-w) * (var(--srg-fit) - 1) / 2);
  overflow: hidden;
  background: var(--srg-surface);
  color: var(--srg-fg);
  font-size: var(--srg-fs-body);
  box-sizing: border-box;
}}
.srg-slide *, .srg-slide *::before, .srg-slide *::after {{ box-sizing: border-box; }}

/* ---- chrome 予約帯 (実物もこの同じ値から描く) ---------------------------- */
.srg-slide__chrome-top,
.srg-slide__chrome-bottom {{
  position: absolute;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  pointer-events: none;
}}
.srg-slide__chrome-top {{ top: 0; height: var(--srg-chrome-top); padding: 0 var(--srg-chrome-side); }}
.srg-slide__chrome-bottom {{ bottom: 0; height: var(--srg-chrome-bottom); padding: 0 var(--srg-chrome-side); }}

/* ---- stage: 本文が使える唯一の領域 --------------------------------------- */
/* 高さを固定して子をここへ押し込むので、要素が少ない面でも空白が伸びない。 */
.srg-slide__stage {{
  position: absolute;
  left: var(--srg-chrome-side);
  top: var(--srg-chrome-top);
  width: var(--srg-stage-w);
  height: var(--srg-stage-h);
  display: flex;
  flex-direction: column;
  gap: var(--srg-gap);
}}

.srg-slide__title {{
  flex: none;
  min-height: var(--srg-title-h);
  display: flex;
  align-items: center;
  font-size: var(--srg-fs-heading);
  font-weight: 700;
  line-height: 1.3;
}}
.srg-slide__lead {{ flex: none; font-size: var(--srg-fs-subheading); line-height: 1.4; }}
/* main は残り高さを必ず埋める。空白過多の構造的な封じ手。 */
.srg-slide__main {{ flex: 1 1 auto; min-height: 0; display: flex; gap: var(--srg-gap); }}
.srg-slide__note {{ flex: none; font-size: var(--srg-fs-note); color: var(--srg-fg-muted); }}

/* ---- 面の分割 ------------------------------------------------------------ */
.srg-split {{ display: grid; gap: var(--srg-gap); width: 100%; height: 100%; }}
.srg-split--half {{ grid-template-columns: 1fr 1fr; }}
.srg-split--text-media {{ grid-template-columns: 3fr 2fr; }}
.srg-split--media-text {{ grid-template-columns: 2fr 3fr; }}
.srg-grid {{ display: grid; gap: var(--srg-gap); width: 100%; height: 100%; }}
.srg-grid--2x2 {{ grid-template-columns: repeat(2, 1fr); grid-template-rows: repeat(2, 1fr); }}
.srg-grid--3x2 {{ grid-template-columns: repeat(3, 1fr); grid-template-rows: repeat(2, 1fr); }}
.srg-grid--3x1 {{ grid-template-columns: repeat(3, 1fr); }}
.srg-band {{ display: flex; align-items: center; gap: var(--srg-gap); width: 100%; height: 100%; }}

.srg-card {{
  border: 1px solid var(--srg-hairline);
  border-radius: var(--srg-radius);
  padding: var(--srg-gap);
  background: var(--srg-surface-2);
  display: flex;
  flex-direction: column;
  gap: var(--srg-gap-tight);
  min-height: 0;
  overflow: hidden;
}}

/* ---- media スロット ------------------------------------------------------ */
/* 図解 (SVG) / D3 / チャート / Codex 画像 が入る唯一の口。
   contain 固定なので、どの差し込み物でも面から食み出さない。 */
.srg-media {{
  position: relative;
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}}
.srg-media > svg,
.srg-media > figure,
.srg-media > .srg-diagram {{ width: 100%; height: 100%; }}
.srg-media svg {{ display: block; width: 100%; height: 100%; }}
.srg-media img,
.srg-media picture {{ display: block; width: 100%; height: 100%; object-fit: contain; }}
/* 背面に敷く画像 (全面画像の面・表紙の背景)。面いっぱいに広げるが、
   object-fit は contain のまま (cover にすると画中の文字や人物が切れる)。 */
.srg-media[data-media-slot="background"] {{
  position: absolute;
  inset: 0;
  z-index: 0;
}}
.srg-slide__stage {{ z-index: 1; }}
.srg-media__caption {{
  flex: none;
  font-size: var(--srg-fs-caption);
  line-height: 1.5;
  color: var(--srg-fg-muted);
}}

/* ---- 文字量に応じた自動縮小 ----------------------------------------------- */
/* data-autofit を持つ要素は、レンダラが scrollHeight > clientHeight の間だけ
   font-size を 1px ずつ落とす (刻み幅の正本は build-slide-skeleton-js.py の STEP。
   下限 --srg-fs-min)。下限でなお溢れる場合は
   面を割るか本文を削る — 縮めて誤魔化さない。CSS 側は溢れを隠す責務だけ持つ。 */
[data-autofit] {{ overflow: hidden; }}
[data-autofit][data-autofit-floored="true"] {{ outline: 1px dashed var(--srg-warn); }}

/* ---- 溢れの可視化 (開発時のみ・検査器と同じ条件) ------------------------- */
.srg-slide[data-overflow="true"] {{ outline: 2px solid var(--srg-focal); outline-offset: -2px; }}

/* ---- 印刷: A4 横レターボックス ------------------------------------------- */
/* 面は 1280x720 の座標系のまま zoom だけで縮む。画面で見えていた位置関係が
   そのまま出るので、PDF でだけズレる、が起きない。
   レターボックス帯は要素 margin ではなく @page margin で取る:
   @page margin は要素 zoom の影響を受けないため、帯幅が倍率で狂わない。
   @page 宣言はこの 1 か所だけが持つ (複数ソースが各々 @page を書くと
   どれが効くかが読み込み順に依存し、印刷結果が再現しなくなる)。 */
@page {{ size: {pr["page"]}; margin: {pr["letterbox_band_mm"]}mm 0; }}

@media print {{
  .srg-deck {{ display: block; background: transparent; }}
  .srg-slide {{
    /* CSS px は 1/96 inch = 0.264583mm 固定。1280px をそのまま出すと
       338.67mm になるので、{pr["zoom_factor"]} 倍して {pr["stage_width_mm"]}mm x {pr["stage_height_mm"]}mm に落とす。
       @page margin が上下 {pr["letterbox_band_mm"]}mm ずつのレターボックス帯になる。 */
    zoom: {pr["zoom_factor"]};
    width: {cv["width"]}px;
    height: {cv["height"]}px;
    margin: 0;
    transform: none;
    page-break-after: always;
    break-after: page;
    break-inside: avoid;
    overflow: hidden;
    box-shadow: none;
  }}
  .srg-slide:last-child {{ page-break-after: auto; break-after: auto; }}
  .srg-slide, .srg-slide * {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
}}
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build-slide-skeleton-css")
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

    try:
        pal = read_palette(root)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"error: 配色の正本を読めない: {e}\n")
        return 2

    try:
        hues = read_legacy_hues(root)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"error: 色相名の現行値を読めない: {e}\n")
        return 2

    try:
        block = build_theme_block(pal, hues)
    except ValueError as e:
        sys.stderr.write(f"error: 手書き経路のブロックを作れない: {e}\n")
        return 2

    css = build_css(contract, pal)
    out = root / _OUT
    rc = 0
    if args.check:
        cur = out.read_text(encoding="utf-8") if out.is_file() else ""
        if cur == css:
            sys.stdout.write("slide-skeleton.css: 契約と一致 -> PASS\n")
        else:
            sys.stderr.write(
                "slide-skeleton.css が frame-contract.json から生成される内容と異なる。\n"
                "CSS を手で編集した場合は編集を frame-contract.json 側へ移し、\n"
                "`python3 scripts/build-slide-skeleton-css.py` で再生成する。\n")
            rc = 1
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(css, encoding="utf-8")
        sys.stdout.write(f"wrote {_OUT} ({len(css)} bytes)\n")

    # 手書き経路の色も同じ SPEC.colors から出す。ここを別スクリプトにすると
    # 正本の読み手が 2 つになり、片方だけ取り残される欠陥が戻る。
    ok, msg = apply_theme_block(root, block, args.check)
    (sys.stdout if ok else sys.stderr).write(msg + "\n")
    if not ok:
        rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
