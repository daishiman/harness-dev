#!/usr/bin/env python3
# /// script
# name: lint-count-parity
# purpose: 散文が主張する「集合の個数」を正本から実測した値と機械突合し、count-drift(散文の数詞が実装から静かにずれる)を fail-closed で封鎖する plugin-root glue。`<!-- count: <key> -->N` アノテーションで散文側の数詞を宣言化し、未アノテーションの数詞も検出する。CLI と import(pytest) 両対応・Python 標準ライブラリのみ。
# inputs:
#   - CLI: [--root <plugin-root>] [--json] [--self-test]
# outputs:
#   - stdout: JSON (passed/count/findings[])
#   - exit: 0=drift 無し(PASS) / 1=drift 検出(fail-closed) / 2=対象ファイル不在・self-test 失敗。
# contexts: [glue]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""散文の数詞 ↔ 正本の実測値 の count-parity ゲート (fail-closed)。

## 何を解く問題か

`107 slideType` `CSS 型 44 種` `slide テンプレート 128 本` のように、
**集合の大きさ**が散文の複数箇所へコピーされている。正本 (schema の enum /
ファイル群 / 見出し群) が増えても散文は変わらないので、数字は静かに腐る。
既存の `lint-contract-drift.py` の検査 B は `key=N` 形式の閾値しか見ないため、
自然文中の数詞を 1 件も捕捉できない (これが本 lint の存在理由)。

**数字を消して「正本の名前だけ書く」のが最善**だが、prompt/README は読者に規模を
渡す必要があり数字が消せない面がある。そこで数字を残す代わりに
**「その数字が何の個数か」を機械可読に宣言させ、実測と突合する**。

## 規約 1: count アノテーション

    <!-- count: slideType -->107 slideType

- アノテーション直後、**同一行**に現れる最初の整数リテラルが対象値。
- Markdown の HTML コメントなので描画に出ない。JSON の description 内にも書ける。
- 実測値と一致しなければ `count-parity` finding。key が未登録なら `count-unknown-key`。

## 規約 2: 未アノテーション数詞の検出 (`count-unannotated`)

導入時点でしか効かない lint を避けるため、アノテーションの無い数詞も検出する。
ただし誤検出が多いと lint が無視されるので、**汎用の「N 種」は一切見ない**。
本 plugin が管理する名前空間を指す固有の文脈パターンに現れる整数だけを対象にする。

検出パターン (`_CONTEXT_PATTERNS`。各 key ごとに正規表現を明示列挙):
  - `slideType`      : `107 slideType` / `slideType 107 種`
  - `slideTypeNonD3` : `53種 + D3 24種` の左側
  - `d3Component`    : `D3 24種` / `D3図解 24種` / `D3（d3-* 24種）`
  - `slideTemplate`  : `slide テンプレート 128 本` / `slideType 別テンプレート（128 種）`
  - `cssDiagramType` : `CSS 型 44 種`
  - `svgBuilder`     : `決定論ビルダー 38 種` / `実在ビルダー 38 種`
  - `diagramGolden`  : `ゴールデン 63 組` (助数詞は「組」限定)
  - `svgVariant`     : `variant … 32 種`
  - `specRegistryRule` : `SR-ID 62` / `SR-ID 62 件`
  - `validationRule` : `V-ID 40 件` / `V_DEFINITIONS 40 件`

除外規則 (誤検出を出さないための意図的な非対象):
  1. **助数詞だけの一致は採らない。** `ゴールデンは 5 件`(chart-types.md の
     図ごとの要素数) のような文書固有の値は「ゴールデン」+ 数字で当たるが、
     助数詞を「組」に限定することで外れる。同様に `階層 2-4 層` 等も対象外。
  2. **`D0-D13` `V-001〜V-030` 形式の ID 範囲は un-annotated 走査の対象にしない。**
     `references/diagram-layout-contract.md` は SVG 断片側の部分集合を
     正当に `D0-D13` と呼ぶ。範囲名は「個数の主張」と「部分集合の名前」を
     文面から区別できないため、アノテーション経由 (`diagramCheckMax`) でのみ縛る。
     加えて `validationRule` は欠番を含み末尾が連番の続きでもないので、
     そもそも範囲式では総数を表せない。**範囲式で書けないと判った箇所を
     範囲式へ書き直して辻褄を合わせないこと** (書けないことが実態)。
  3. **コードブロック(``` 囲み)内は走査しない。** 実装例の数値は散文の主張ではない。
  4. **`<!-- count-exempt: 理由 -->` を同一行に持つ行は走査しない。**
     文書が自分自身の記載量を述べる自己記述的な表 (例: 決定木の分類カバー数表は
     「本マトリクスに何件書いてあるか」であって schema の enum 数ではない) を、
     外部 allowlist を作らずにファイル内で明示免除するための逃がし口。
  5. 走査対象は `*.md` (plugin root) `references/**.md` `skills/**.md`
     `agents/**.md` `schemas/*.json` `.claude-plugin/*.json`。
     `vendor/` の値はvendor integrity gateが担い、`tests/` は固定値を持つ。
     当初 `.md` 3 系統だけを見ていたが、`.claude-plugin/plugin.json` の
     `description` にあった `97 slideType` がこの死角で生き残った。利用者が読む
     散文はファイル拡張子では決まらない。
  6. **JSON はアノテーションを要求せず、文脈一致した整数を直接実測と突合する。**
     HTML コメントを置けない形式に「アノテーションを付けろ」と言うと、
     恒久的に免除されるのと同じになる。

## count key と実測方法 (正本を直接数える。散文からは決して読まない)

| key                  | 正本 | 実測 |
|---|---|---|
| slideType            | schemas/structure.schema.json | `$defs.slideTypeEnum.enum` の len |
| slideTypeNonD3       | 同上 | 同 enum のうち `d3-` 前置でないものの len |
| structureDef         | 同上 | `$defs` のキー数 |
| svgVariant           | schemas/report-structure.schema.json | `$defs.svgSpec.properties.variant.enum` の len |
| slideTemplate        | vendor/scripts/templates/ | `*.html.tpl` の glob 件数 |
| cssDiagramType       | references/diagram-*.md | `^#+ §?11.<n>` 見出しの distinct 件数 |
| diagramCheck         | scripts/validate-svg-diagram.py | `ALL_CODES = frozenset(f"D{i}" for i in range(N))` の N |
| diagramCheckMax      | 同上 | N - 1 (`D0-D<max>` の右端) |
| diagramGolden        | examples/diagram-goldens/ | `*-golden.html` の再帰件数 |
| diagramGoldenHand    | 同上 | 直下 (builders/ を除く) の件数 |
| diagramGoldenBuilder | 同上 builders/ | 件数 |
| diagramGoldenProduction | 同上 production/ | 件数 (本番語彙 svgSpec 経路) |
| d3Component          | vendor/scripts/render-slide.cjs | `D3_COMPONENTS = {...}` の distinct キー数 |
| svgBuilder           | svg-builder.cjs + svg-structures.cjs + render-report.js | Core + Struct + Own の合計 |
| svgBuilderCore       | vendor/scripts/svg-builder.cjs | `^function build*` の件数 |
| svgBuilderStruct     | vendor/scripts/svg-structures.cjs | `^function build*` の件数 |
| svgBuilderOwn        | vendor/scripts/render-report.js | ローカル `function build*` かつ `render: (...) => buildX(` から呼ばれるもの |
| slideTypeDecision    | references/slide-type-decision-tree.md | `DT-<n>` の distinct 件数 |
| specRegistryRule     | references/spec-registry.md | 行頭 `| SR-...` の distinct 行 ID 件数 |
| validationRule       | vendor/scripts/validate-structure.js | `V_DEFINITIONS = {...}` の distinct `V-NNN` キー数 |

exit: 0=PASS / 1=drift 検出 / 2=usage・対象不在・self-test 失敗。
pytest からは run_checks(root) を import して findings[] を得る。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path


def _plugin_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parent.parent


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


# ---------------------------------------------------------------------------
# 実測器 (measurers): 各 key の「正本」を直接数える。散文は読まない。
# 数えられない (正本が壊れている/読めない) 場合は None を返し、呼び出し側が
# fail-closed に倒す。0 を返してはならない (0 は「空集合」という別の主張)。
# ---------------------------------------------------------------------------
_STRUCTURE_SCHEMA = "schemas/structure.schema.json"
_REPORT_SCHEMA = "schemas/report-structure.schema.json"
_TEMPLATE_GLOB = "vendor/scripts/templates/*.html.tpl"
# ページひな形 (手書き経路の面)。vendor の tpl とは別体系なので別キーで数える。
# 宣言 (散文の「22 種」) と実体の乖離を数える機構が `layout-*` だけを数えると、
# 乖離の当事者を候補から外してしまう。*.html で全数を数える。
_SKELETON_GLOB = "assets/slide-templates/*.html"
_GOLDEN_DIR = "skills/run-slide-report-generate/examples/diagram-goldens"
_RENDER_SLIDE = "vendor/scripts/render-slide.cjs"
_SVG_BUILDER = "vendor/scripts/svg-builder.cjs"
_SVG_STRUCTURES = "vendor/scripts/svg-structures.cjs"
_RENDER_REPORT = "vendor/scripts/render-report.js"
_VALIDATE_DIAGRAM = "scripts/validate-svg-diagram.py"
_DECISION_TREE = "references/slide-type-decision-tree.md"
_SPEC_REGISTRY = "references/spec-registry.md"
_VALIDATE_STRUCTURE = "vendor/scripts/validate-structure.js"
_SVG_KIT = "vendor/scripts/svg-kit.cjs"

# STROKE のうち「太さの段」に数えない役割名。band は線でなく面として読ませる値
# (24) で、段に混ぜると段数が 1 つ増えて散文の「3 段」と食い違う。除外の根拠は
# svg-kit.cjs の band 自身のコメントにある。名前が消えたら段数が黙って変わるので、
# self-test 側で「この名前が STROKE に実在すること」を固定する。
_STROKE_NON_TIER = ("band",)

_SECTION_11_RE = re.compile(r"^#{2,4}\s+§?(11\.\d+)", re.M)
_BUILD_FN_RE = re.compile(r"^function (build[A-Z]\w*)", re.M)


def _slide_type_enum(root: Path) -> list[str] | None:
    try:
        schema = json.loads(_read(root, _STRUCTURE_SCHEMA))
    except (json.JSONDecodeError, ValueError):
        return None
    enum = (((schema.get("$defs") or {}).get("slideTypeEnum") or {}).get("enum"))
    return enum if isinstance(enum, list) and enum else None


def _m_slide_type(root: Path) -> int | None:
    enum = _slide_type_enum(root)
    return len(enum) if enum else None


def _m_slide_type_non_d3(root: Path) -> int | None:
    enum = _slide_type_enum(root)
    return len([x for x in enum if not x.startswith("d3-")]) if enum else None


def _m_structure_def(root: Path) -> int | None:
    try:
        schema = json.loads(_read(root, _STRUCTURE_SCHEMA))
    except (json.JSONDecodeError, ValueError):
        return None
    defs = schema.get("$defs")
    return len(defs) if isinstance(defs, dict) and defs else None


def _m_svg_variant(root: Path) -> int | None:
    try:
        schema = json.loads(_read(root, _REPORT_SCHEMA))
    except (json.JSONDecodeError, ValueError):
        return None
    node = ((schema.get("$defs") or {}).get("svgSpec") or {})
    enum = ((node.get("properties") or {}).get("variant") or {}).get("enum")
    return len(enum) if isinstance(enum, list) and enum else None


def _m_slide_template(root: Path) -> int | None:
    n = len(list(root.glob(_TEMPLATE_GLOB)))
    return n or None


def _m_slide_skeleton(root: Path) -> int | None:
    n = len(list(root.glob(_SKELETON_GLOB)))
    return n or None


def _m_css_diagram_type(root: Path) -> int | None:
    seen: set[str] = set()
    for path in sorted((root / "references").glob("diagram-*.md")):
        seen.update(_SECTION_11_RE.findall(path.read_text(encoding="utf-8")))
    return len(seen) or None


def _diagram_check_span(root: Path) -> int | None:
    m = re.search(r"ALL_CODES[^\n]*range\((\d+)\)", _read(root, _VALIDATE_DIAGRAM))
    return int(m.group(1)) if m else None


def _m_diagram_check(root: Path) -> int | None:
    return _diagram_check_span(root)


def _m_diagram_check_max(root: Path) -> int | None:
    n = _diagram_check_span(root)
    return n - 1 if n else None


def _m_diagram_golden(root: Path) -> int | None:
    n = len(list((root / _GOLDEN_DIR).rglob("*-golden.html")))
    return n or None


def _m_diagram_golden_hand(root: Path) -> int | None:
    n = len(list((root / _GOLDEN_DIR).glob("*-golden.html")))
    return n or None


def _m_diagram_golden_builder(root: Path) -> int | None:
    n = len(list((root / _GOLDEN_DIR / "builders").glob("*-golden.html")))
    return n or None


def _m_diagram_golden_production(root: Path) -> int | None:
    # 本番語彙 (svgSpec) のゴールデン。射影を 1 層踏むので builders/ とは別勘定。
    n = len(list((root / _GOLDEN_DIR / "production").glob("*-golden.html")))
    return n or None


def _brace_block(src: str, anchor: str) -> str | None:
    """`anchor` の直後に開く `{...}` の中身を返す。見つからなければ None。

    JS のオブジェクトリテラルを正規表現で 1 発で取ると、中の `}` で早く閉じる。
    深さを数えて取る。
    """
    i = src.find(anchor)
    if i < 0:
        return None
    j = src.find("{", i)
    if j < 0:
        return None
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j + 1:k]
        k += 1
    return None


def _m_d3_component(root: Path) -> int | None:
    body = _brace_block(_read(root, _RENDER_SLIDE), "D3_COMPONENTS")
    if body is None:
        return None
    keys = set(re.findall(r"'([A-Za-z0-9_-]+)'\s*:", body))
    return len(keys) or None


def _m_validation_rule(root: Path) -> int | None:
    """機械検証項目 V-ID の総数。正本は validate-structure.js の `V_DEFINITIONS`。

    連番ではないので「V-001〜V-0NN」の形の範囲では表せない (欠番があり、末尾は
    連番の続きでもない)。総数だけが主張できる値なので、総数だけを数える。
    """
    body = _brace_block(_read(root, _VALIDATE_STRUCTURE), "V_DEFINITIONS")
    if body is None:
        return None
    return len(set(re.findall(r'"(V-\d+)"\s*:', body))) or None


def _m_svg_builder_core(root: Path) -> int | None:
    return len(_BUILD_FN_RE.findall(_read(root, _SVG_BUILDER))) or None


def _m_svg_builder_struct(root: Path) -> int | None:
    return len(_BUILD_FN_RE.findall(_read(root, _SVG_STRUCTURES))) or None


def _m_svg_builder_own(root: Path) -> int | None:
    """render-report.js が自前で持つ図ビルダー数。

    `function build*` を全部数えると buildReportCss / buildFootnoteRegistry のような
    非図解の生成関数まで入る。図として描かれるものだけを取るため、決定表の
    ビルダー登録 (`render: (d, opts) => buildXxx(`) から呼ばれ、かつ同ファイルで
    ローカル宣言されている名前に限定する (`svg.buildXxx` は svg-builder.cjs 側)。
    """
    src = _read(root, _RENDER_REPORT)
    if not src:
        return None
    local = set(_BUILD_FN_RE.findall(src))
    rendered = set(re.findall(r"render:\s*\([^)]*\)\s*=>\s*(build[A-Z]\w*)\(", src))
    return len(local & rendered) or None


def _m_svg_builder(root: Path) -> int | None:
    core = _m_svg_builder_core(root)
    struct = _m_svg_builder_struct(root)
    own = _m_svg_builder_own(root)
    if core is None or struct is None or own is None:
        return None
    return core + struct + own


def _m_slide_type_decision(root: Path) -> int | None:
    ids = set(re.findall(r"DT-(\d+)", _read(root, _DECISION_TREE)))
    return len(ids) or None


def _m_spec_registry_rule(root: Path) -> int | None:
    ids = set(re.findall(r"^\|\s*(SR-[0-9]+-[0-9A-Za-z-]+)\s*\|", _read(root, _SPEC_REGISTRY), re.M))
    return len(ids) or None


_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_STROKE_ENTRY_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*:\s*([0-9]*\.?[0-9]+)\s*,", re.M)


def _stroke_entries(root: Path) -> dict[str, str] | None:
    """svg-kit.cjs の `STROKE` を {役割名: 値の文字列} で返す。

    値は文字列のまま持つ。float へ寄せると 1.25 と 1.250 が同じになる一方で
    表記のぶれが見えなくなるため、散文と突き合わせる「値の見た目」を保つ。
    """
    body = _brace_block(_read(root, _SVG_KIT), "STROKE")
    if body is None:
        return None
    entries = _STROKE_ENTRY_RE.findall(_COMMENT_RE.sub("", body))
    return dict(entries) or None


def _m_stroke_role(root: Path) -> int | None:
    """線幅の役割名の数。正本は svg-kit.cjs の `STROKE` のキー。

    次の `_m_stroke_tier` と対で数える。**片方だけでは足りない**。役割名は
    呼ぶ側が意図を書くためのもので、実際の太さはそれより少ない段へ落ちる。
    名前だけ数えると「6 段ある」と読め、段だけ数えると「名前は 3 つ」と読める。
    """
    entries = _stroke_entries(root)
    return len(entries) if entries else None


def _m_stroke_tier(root: Path) -> int | None:
    """線幅の段の数 (distinct な値の数)。正本は同じく `STROKE`。

    `_STROKE_NON_TIER` の役割は面として読ませる値なので段に数えない。
    名前数と段数が一致しないのは欠落ではなく、一致させようとして段を増やすと
    比 1.33 のような「目には分かれていない段」が戻る。
    """
    entries = _stroke_entries(root)
    if not entries:
        return None
    tiers = {v for k, v in entries.items() if k not in _STROKE_NON_TIER}
    return len(tiers) or None


_SERIES_ANCHOR = "const SERIES = ["
_SERIES_ITEM_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")
_SERIES_HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}")


def _series_literals(root: Path) -> list[str] | None:
    """svg-kit.cjs の `SERIES` を、配列リテラルに書かれた順で返す。

    ブロックを取ってから、その中だけコメントを落とす (`_stroke_entries` と同じ流儀)。
    ファイル全文へ `_COMMENT_RE` を当ててはいけない。svg-kit.cjs には
    `xmlns="http://...` のように `://` を含む行があり、`//` 以降を落とすと
    文字列そのものが壊れて、数える前に対象が消える。
    """
    src = _read(root, _SVG_KIT)
    i = src.find(_SERIES_ANCHOR)
    if i < 0:
        return None
    j = src.find("[", i)
    if j < 0:
        return None
    depth, k, body = 0, j, None
    while k < len(src):
        if src[k] == "[":
            depth += 1
        elif src[k] == "]":
            depth -= 1
            if depth == 0:
                body = src[j + 1:k]
                break
        k += 1
    if body is None:
        return None
    items = [a or b for a, b in _SERIES_ITEM_RE.findall(_COMMENT_RE.sub("", body))]
    return items or None


def _m_series(root: Path) -> int | None:
    """系列色の枠の数。正本は svg-kit.cjs の `SERIES` の要素数。

    散文にある「5 色」はこの枠数ではない。`SERIES` の直後には別名が 5 つ並ぶが、
    そのうち 1 つは `VAR_VIOLET = SERIES[0]` で先頭の枠を指し直しているだけで、
    枠は増えていない。名前の数を枠の数として読むと、呼ぶ側は「2 通りある」と
    信じて 2 枠を同時に取り、区別できない 2 系列が出る。
    次の `_m_series_distinct` と対で数える。**片方だけでは足りない**。
    """
    items = _series_literals(root)
    return len(items) if items else None


def _m_series_distinct(root: Path) -> int | None:
    """区別できる系列の数。正本は同じく `SERIES`。

    各要素の CSS 変数フォールバック (`var(--x, #RRGGBB)` の HEX) で数える。
    HEX が無い要素はリテラル全体を鍵にする。
    限界を書いておく: 変数側が同じ値へ解決されれば画面では同色になるが、ここは
    別物として数える。CSS 変数の実値との突合は drift 側の管轄で、ここへ持ち込むと
    同じ事項の正本が 2 つになる。
    """
    items = _series_literals(root)
    if not items:
        return None
    keys = set()
    for it in items:
        m = _SERIES_HEX_RE.search(it)
        keys.add(m.group(0).lower() if m else it.strip())
    return len(keys) or None


MEASURERS = {
    "slideType": _m_slide_type,
    "slideTypeNonD3": _m_slide_type_non_d3,
    "structureDef": _m_structure_def,
    "svgVariant": _m_svg_variant,
    "slideTemplate": _m_slide_template,
    "slideSkeleton": _m_slide_skeleton,
    "cssDiagramType": _m_css_diagram_type,
    "diagramCheck": _m_diagram_check,
    "diagramCheckMax": _m_diagram_check_max,
    "diagramGolden": _m_diagram_golden,
    "diagramGoldenHand": _m_diagram_golden_hand,
    "diagramGoldenBuilder": _m_diagram_golden_builder,
    "diagramGoldenProduction": _m_diagram_golden_production,
    "d3Component": _m_d3_component,
    "svgBuilder": _m_svg_builder,
    "svgBuilderCore": _m_svg_builder_core,
    "svgBuilderStruct": _m_svg_builder_struct,
    "svgBuilderOwn": _m_svg_builder_own,
    "slideTypeDecision": _m_slide_type_decision,
    "specRegistryRule": _m_spec_registry_rule,
    "validationRule": _m_validation_rule,
    "strokeRole": _m_stroke_role,
    "strokeTier": _m_stroke_tier,
    "series": _m_series,
    "seriesDistinct": _m_series_distinct,
}

# ---------------------------------------------------------------------------
# 散文走査
# ---------------------------------------------------------------------------
_ANNOTATION_RE = re.compile(r"<!--\s*count:\s*([A-Za-z][A-Za-z0-9_]*)\s*-->")
_EXEMPT_RE = re.compile(r"<!--\s*count-exempt:")
_INT_RE = re.compile(r"\d+")
_FENCE_RE = re.compile(r"^\s*```")

# 未アノテーション検出。key -> [(regex, 説明)]。regex の group(1) が整数。
# 「その整数が本 plugin の名前空間の大きさを主張している」と言い切れる文脈だけを
# 列挙する (docstring の除外規則 1 を満たすため、汎用助数詞は使わない)。
_CONTEXT_PATTERNS: dict[str, list[str]] = {
    "slideType": [
        r"(\d+)\s*slideType",
        r"slideType\s*(\d+)\s*種",
    ],
    "slideTypeNonD3": [
        r"(\d+)\s*種\s*\+\s*D3",
        r"(\d+)種\s*\+\s*D3",
        r"(\d+)種\+D3",
    ],
    "d3Component": [
        r"D3\s*(\d+)\s*種",
        r"D3図解\s*(\d+)\s*種",
        r"d3-\*\s*(\d+)\s*種",
        r"D3（d3-\*\s*(\d+)\s*種）",
    ],
    "slideTemplate": [
        r"slide\s*テンプレート\s*(\d+)\s*[本種]",
        r"テンプレート（(\d+)\s*種）",
        r"tpl\s*(\d+)\b",
    ],
    "slideSkeleton": [
        r"ひな形\s*(\d+)\s*種",
        r"(\d+)\s*種のひな形",
        r"ひな形を?\s*(\d+)\s*枚",
    ],
    "cssDiagramType": [
        r"CSS\s*型\s*(\d+)\s*種?",
    ],
    "svgBuilder": [
        r"決定論ビルダー\s*(\d+)\s*種?",
        r"実在ビルダー\s*(\d+)\s*種",
        r"ビルダー\s*(\d+)\s*/",
    ],
    "diagramGolden": [
        r"ゴールデン\s*(\d+)\s*組",
    ],
    "svgVariant": [
        r"variant\s*(?:enum)?\s*(\d+)\s*種",
    ],
    # SR-ID / V-ID は名前空間の識別子そのものが `SR-4-03` `V-001` の形なので、
    # 「識別子トークン + 空白 + 裸の整数」は個数の主張以外に読みようがない。
    # 逆に `V-001〜V-030` のような範囲式には当たらない (当てない)。範囲式は
    # 部分集合の名前かもしれず、また V-ID は欠番があって範囲では総数を表せない。
    "specRegistryRule": [
        r"SR-ID\s*(?:全|計)?\s*(\d+)\s*[件本個]",
        r"SR-ID\s+(\d+)(?![-\d])",
    ],
    "validationRule": [
        r"V-ID\s*(?:全|計)?\s*(\d+)\s*[件本個]",
        r"V-ID\s+(\d+)(?![-\d])",
        r"V_DEFINITIONS\s*(?:全|計)?\s*(\d+)\s*[件本個種]",
    ],
}
_COMPILED_CONTEXT = {k: [re.compile(p) for p in v] for k, v in _CONTEXT_PATTERNS.items()}

_SCAN_GLOBS = (
    "*.md",
    "references/**/*.md",
    "skills/**/*.md",
    # 散文の数字は .md だけに出るという前提は誤りだった。plugin.json の description と
    # agents/*.md の frontmatter description も利用者が読む散文で、実際に
    # `.claude-plugin/plugin.json` の `97 slideType` が本 lint をすり抜けて生き残った。
    "agents/**/*.md",
    ".claude-plugin/*.json",
    # .md / .json 以外は数字が腐らないという前提も同じく誤りだった。skill 私有の
    # references/*.yaml (resource-map.yaml 等) は LLM が読む散文を値に持ち、実際に
    # ref-diagram-system の「実在ビルダー全 37 種」が実測 38 とずれたまま生き残った。
    "references/**/*.yaml",
    "skills/**/*.yaml",
)


def _scan_files(root: Path) -> list[Path]:
    seen: dict[str, Path] = {}
    for g in _SCAN_GLOBS:
        for p in root.glob(g):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if rel.startswith("vendor/"):
                continue
            seen[rel] = p
    # schema の description も散文なので同列に扱う。
    for p in sorted((root / "schemas").glob("*.json")):
        seen[p.relative_to(root).as_posix()] = p
    return [seen[k] for k in sorted(seen)]


def _annotated_hits(line: str) -> list[tuple[str, int | None]]:
    """1 行から (key, 直後の最初の整数) を左から順に取る。整数が無ければ None。"""
    hits: list[tuple[str, int | None]] = []
    for m in _ANNOTATION_RE.finditer(line):
        tail = line[m.end():]
        # 次のアノテーションより手前だけを見る (同一行に複数ある場合の取り違え防止)。
        nxt = _ANNOTATION_RE.search(tail)
        if nxt:
            tail = tail[: nxt.start()]
        i = _INT_RE.search(tail)
        hits.append((m.group(1), int(i.group(0)) if i else None))
    return hits


def run_checks(root: Path, scan_root: Path | None = None) -> list[dict]:
    """`root` の正本を実測し、`scan_root` (既定 = root) の散文と突合する。

    self-test は scan_root だけを合成ディレクトリへ向けることで、検出ロジックの
    複製ではなく本体そのものを検証する (複製した検査は、検査対象と同じようにドリフトする)。
    """
    scan_root = scan_root or root
    findings: list[dict] = []

    def add(check: str, message: str, where: str) -> None:
        findings.append({"check": check, "message": message, "where": where})

    # 実測値を一度だけ確定する。measurer が None を返す = 正本が読めない → fail-closed。
    measured: dict[str, int] = {}
    for key, fn in MEASURERS.items():
        val = fn(root)
        if val is None:
            add("count-measure-failed",
                f"count key '{key}' の実測に失敗した (正本が読めない・定義の書き方が変わった。"
                "実測関数を追随させる。実測できない key を放置すると parity 検査が静かに無効になる)",
                "scripts/lint-count-parity.py")
        else:
            measured[key] = val

    for path in _scan_files(scan_root):
        rel = path.relative_to(scan_root).as_posix()
        text = path.read_text(encoding="utf-8")
        in_fence = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if path.suffix == ".md" and _FENCE_RE.match(line):
                in_fence = not in_fence
                continue

            # -- A: アノテーション付き数詞 ↔ 実測 -----------------------------
            for key, cited in _annotated_hits(line):
                if key not in MEASURERS:
                    add("count-unknown-key",
                        f"未登録の count key '{key}'。MEASURERS に実測関数を足すか key 名を直す "
                        f"(登録済み: {', '.join(sorted(MEASURERS))})",
                        f"{rel}:{lineno}")
                    continue
                if cited is None:
                    add("count-annotation-orphan",
                        f"`<!-- count: {key} -->` の直後・同一行に整数が無い "
                        "(アノテーションは対象の数詞の直前に置く)",
                        f"{rel}:{lineno}")
                    continue
                if key in measured and cited != measured[key]:
                    add("count-parity",
                        f"散文が {key}={cited} と主張するが正本の実測は {measured[key]} "
                        "(count-drift。散文を実測値へ直すか、数詞を消して正本の名前だけを書く)",
                        f"{rel}:{lineno}")

            # -- B: 未アノテーション数詞 -------------------------------------
            if in_fence or _EXEMPT_RE.search(line):
                continue
            annotated = {k for k, _ in _annotated_hits(line)}
            # アノテーション本体の文字列は文脈照合から外す (key 名の "D3" 等が誤爆する)。
            probe = _ANNOTATION_RE.sub(" ", line)
            # JSON は HTML コメントを置けないのでアノテーションを要求できない。
            # 代わりに文脈一致した整数をそのまま実測と突合する (要求できないから
            # 見逃す、にすると plugin.json のような配布メタデータが恒久的な死角になる)。
            can_annotate = path.suffix != ".json"
            for key, regexes in _COMPILED_CONTEXT.items():
                if key in annotated:
                    continue
                for rx in regexes:
                    for m in rx.finditer(probe):
                        cited = int(m.group(1))
                        if not can_annotate:
                            if key in measured and cited != measured[key]:
                                add("count-parity",
                                    f"'{m.group(0).strip()}' が {key}={cited} と主張するが"
                                    f"正本の実測は {measured[key]} "
                                    "(count-drift。JSON はアノテーション不可のため文脈照合で直接突合している)",
                                    f"{rel}:{lineno}")
                            break
                        add("count-unannotated",
                            f"'{m.group(0).strip()}' は {key} の個数の主張だがアノテーションが無い。"
                            f"`<!-- count: {key} -->{m.group(1)}` の形にする "
                            "(自己記述の表など個数の主張でないなら `<!-- count-exempt: 理由 -->` を同一行に置く)",
                            f"{rel}:{lineno}")
                        break
                    else:
                        continue
                    break

    return findings


# ---------------------------------------------------------------------------
# self-test: 正しい状態と壊れた状態の両方を検出できることを自己検証する
# ---------------------------------------------------------------------------
def _self_test(root: Path) -> tuple[bool, list[str]]:
    log: list[str] = []
    ok = True

    def check(label: str, cond: bool) -> None:
        nonlocal ok
        log.append(f"{'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            ok = False

    # T1: 全 measurer が正の整数を返す (実測不能が 1 件でもあれば検査は空になる)。
    for key, fn in MEASURERS.items():
        val = fn(root)
        check(f"T1 measurer '{key}' が正の整数を返す (実測={val})", isinstance(val, int) and val > 0)

    # T2: 既知の正本値と一致する (実測器が別のものを数えていないことの固定)。
    #     ここは「実測器 ↔ 正本」の二重確認であり、散文からは 1 バイトも読まない。
    live = {k: fn(root) for k, fn in MEASURERS.items()}
    check("T2 slideType = slideTypeNonD3 + d3Component (enum の d3 分割が整合)",
          live["slideType"] == live["slideTypeNonD3"] + live["d3Component"])
    check("T2 diagramGolden = Hand + Builder + Production (ゴールデンの内訳が総数と整合)",
          live["diagramGolden"] == live["diagramGoldenHand"] + live["diagramGoldenBuilder"]
          + live["diagramGoldenProduction"])
    check("T2 diagramCheckMax = diagramCheck - 1 (D0 起点の連番)",
          live["diagramCheckMax"] == live["diagramCheck"] - 1)
    check("T2 svgBuilder = Core + Struct + Own (3 経路の合算が総数と整合)",
          live["svgBuilder"] == live["svgBuilderCore"] + live["svgBuilderStruct"] + live["svgBuilderOwn"])
    # 役割名は段より多い。等しくなったら「名前と段を一致させる」方向へ動いた合図で、
    # 目には分かれない段が戻っている可能性がある。少ないのは数え落とし。
    check("T2 strokeRole > strokeTier (役割名は段へ落ちる。名前数と段数は一致しない)",
          live["strokeRole"] > live["strokeTier"])
    _stroke = _stroke_entries(root) or {}
    check(f"T2 _STROKE_NON_TIER の役割が STROKE に実在する (除外={', '.join(_STROKE_NON_TIER)})",
          all(name in _stroke for name in _STROKE_NON_TIER))
    # 枠数と区別できる数は一致していなければならない。`series >= seriesDistinct` は
    # 実測器の性質から常に真で何も主張しないので、等号を取る。ここが割れた状態
    # (枠は 4 だが区別できるのは 3) は、2 枠が同じ色を指したということで、過去に
    # 実際に起きて D29 が鳴った形。減った側が枠の数へ吸われて見えなくなる。
    check(f"T2 series = seriesDistinct (区別できない 2 系列が無い。枠={live['series']} "
          f"区別={live['seriesDistinct']})",
          live["series"] == live["seriesDistinct"])
    _series = _series_literals(root) or []
    check("T2 SERIES の全要素が var(--名前, #HEX) の形 (フォールバック無しは変数未定義で無色になる)",
          bool(_series) and all(
              re.fullmatch(r"var\(--[A-Za-z0-9-]+,\s*#[0-9A-Fa-f]{3,8}\)", s.strip())
              for s in _series))

    # T3/T4/T5/T6: 合成 root を作り、正しい状態 / 壊れた状態の双方を判定できるか。
    with tempfile.TemporaryDirectory() as td:
        sandbox = Path(td)
        (sandbox / "references").mkdir()
        (sandbox / "schemas").mkdir()

        # 正本 (schemas 等) は実 root から読ませ、走査だけ sandbox へ向けるため、
        # 実測に必要な最小構成を sandbox から実 root へ委譲する。
        (sandbox / ".claude-plugin").mkdir()

        def scan_only(text: str, name: str = "probe.md") -> list[dict]:
            for stale in list(sandbox.glob("probe.*")) + list(
                    (sandbox / ".claude-plugin").glob("probe.*")):
                stale.unlink()
            (sandbox / name).write_text(text, encoding="utf-8")
            # measurer は本物の root、走査は sandbox。検出ロジックは本体を通る。
            return run_checks(root, scan_root=sandbox)

        good = f"<!-- count: slideType -->{live['slideType']} slideType を使う\n"
        check("T3 正しい注釈は finding 0", scan_only(good) == [])

        bad = f"<!-- count: slideType -->{live['slideType'] + 1} slideType を使う\n"
        f_bad = scan_only(bad)
        check("T4 数字を 1 ずらすと count-parity を出す",
              any(f["check"] == "count-parity" for f in f_bad))

        un = f"{live['slideType']} slideType を使う\n"
        f_un = scan_only(un)
        check("T5 注釈の無い数詞は count-unannotated を出す",
              any(f["check"] == "count-unannotated" for f in f_un))

        fenced = "```\n%d slideType\n```\n" % live["slideType"]
        check("T6 コードブロック内は走査しない", scan_only(fenced) == [])

        exempt = f"<!-- count-exempt: 自己記述 -->{live['slideType']} slideType\n"
        check("T7 count-exempt 行は走査しない", scan_only(exempt) == [])

        unknown = "<!-- count: noSuchKey -->5 個\n"
        check("T8 未登録 key は count-unknown-key を出す",
              any(f["check"] == "count-unknown-key" for f in scan_only(unknown)))

        orphan = "<!-- count: slideType --> 直後に整数が無い行\n"
        check("T9 整数を伴わない注釈は count-annotation-orphan を出す",
              any(f["check"] == "count-annotation-orphan" for f in scan_only(orphan)))

        # T10/T11: JSON は注釈を置けないので、文脈一致した整数を直接突合する。
        # `.claude-plugin/plugin.json` の `97 slideType` が走査対象外で生き残った
        # 事故の再発を、この 2 件が機械的に止める。
        j_ok = '{"description": "slide=%d slideType"}\n' % live["slideType"]
        check("T10 JSON の正しい数詞は finding 0 (注釈を要求しない)",
              scan_only(j_ok, ".claude-plugin/probe.json") == [])

        j_bad = '{"description": "slide=%d slideType"}\n' % (live["slideType"] + 1)
        f_jbad = scan_only(j_bad, ".claude-plugin/probe.json")
        check("T11 JSON の数字を 1 ずらすと count-parity を出す",
              any(f["check"] == "count-parity" for f in f_jbad))

        # T12/T13: ID 名前空間 (SR-ID / V-ID) の個数主張は捕まえ、ID 範囲式は捕まえない。
        # 実際に起きた事故が両方向にあるのでどちらも固定する。散文の `SR-ID 62` は
        # 実測 (当時 124) から静かにずれていた。逆に `V-001〜V-030` のような範囲式を
        # 個数の主張と読む抽出は、欠番のある集合へ存在しない穴を報告する。
        for label, text in (
            ("SR-ID", f"spec-registry SR-ID {live['specRegistryRule'] + 1} を参照\n"),
            ("V-ID", f"V-ID {live['validationRule'] + 1} 件を検証\n"),
        ):
            check(f"T12 {label} の裸の個数主張は count-unannotated を出す",
                  any(f["check"] == "count-unannotated" for f in scan_only(text)))
        check("T13 ID 範囲式は個数の主張として扱わない",
              scan_only("V-001〜V-043 と D0-D13 と SR-4-03 / V-001 を見る\n") == [])

    return ok, log


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lint-count-parity",
        description="散文の数詞 ↔ 正本の実測値 の count-parity ゲート (fail-closed)",
    )
    p.add_argument("--root", default=None, help="plugin root (既定=本スクリプトの1つ上)")
    p.add_argument("--json", action="store_true", help="(既定で JSON 出力・互換用フラグ)")
    p.add_argument("--self-test", action="store_true", help="実測器と検出器の自己検証のみ行う")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    root = _plugin_root(args.root)
    if not (root / _STRUCTURE_SCHEMA).is_file():
        sys.stderr.write(f"error: {_STRUCTURE_SCHEMA} not found under {root}\n")
        return 2
    if args.self_test:
        ok, log = _self_test(root)
        sys.stdout.write(json.dumps(
            {"passed": ok, "count": len(log), "findings": log}, ensure_ascii=False, indent=2) + "\n")
        return 0 if ok else 2
    findings = run_checks(root)
    result = {"passed": len(findings) == 0, "count": len(findings), "findings": findings}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
