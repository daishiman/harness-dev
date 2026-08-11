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

除外規則 (誤検出を出さないための意図的な非対象):
  1. **助数詞だけの一致は採らない。** `ゴールデンは 5 件`(chart-types.md の
     図ごとの要素数) のような文書固有の値は「ゴールデン」+ 数字で当たるが、
     助数詞を「組」に限定することで外れる。同様に `階層 2-4 層` 等も対象外。
  2. **`D0-D13` 形式の検査コード範囲は un-annotated 走査の対象にしない。**
     `references/diagram-layout-contract.md` は SVG 断片側の部分集合を
     正当に `D0-D13` と呼ぶ。範囲名は「個数の主張」と「部分集合の名前」を
     文面から区別できないため、アノテーション経由 (`diagramCheckMax`) でのみ縛る。
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


def _m_d3_component(root: Path) -> int | None:
    src = _read(root, _RENDER_SLIDE)
    i = src.find("D3_COMPONENTS")
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
                break
        k += 1
    keys = set(re.findall(r"'([A-Za-z0-9_-]+)'\s*:", src[j + 1:k]))
    return len(keys) or None


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
