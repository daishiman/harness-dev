#!/usr/bin/env python3
# /// script
# name: lint-contract-drift
# purpose: report 経路の prose(references/prompts)↔code(render-report.js/validate-report-visual.py/schema)の contract-drift を fail-closed 検出する plugin-root glue。散文が主張する data-* 属性名・閾値・render-fidelity class・placement field 消費を実装と機械突合し、「宣言 > 実装」の同型ドリフト(phantom data-focal-y / report.css phantom / dead field / 閾値ズレ)の再発を封鎖する。CLI と import(pytest)両対応・Python 標準ライブラリのみ。
# inputs:
#   - CLI: [--root <plugin-root>] [--json]
# outputs:
#   - stdout: JSON (findings[])
#   - exit: 0=drift 無し(PASS) / 1=drift 検出(fail-closed) / 2=対象ファイル不在。
# contexts: [glue]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""report 経路の prose↔code contract-drift ゲート (fail-closed)。

30思考法エレガント検証(3 独立 analyst)が amplified pattern として一致提案した機構。
build のたびに散文(prompts/references)と実装(renderer/validator/schema)が
静かに乖離する『宣言 > 実装/ゲート』の同型ドリフトを、人手照合でなく機械で封鎖する。

検査 (report 語彙にスコープ):
  A data-attr existence : prose が引用する data-* 属性名を render-report.js が実 emit するか。
                          (phantom 属性 = 実装しない属性名の教示 を検出。例: data-focal-y)
                          図解散文 (_SLIDE_SCOPED_PROSE) だけは slide 経路も跨ぐため
                          render-slide.cjs の emit も真とみなす。
  B threshold parity    : prose が `key=N` で引用する閾値が DEFAULT_THRESHOLDS の値と一致するか。
                          (例: doc_highlight_budget=24 の散文↔code ズレ)
  C fidelity chain      : validate-report-visual.py が render-fidelity で検査する class/属性を
                          render-report.js が実 emit するか。(validator が emit しない class を
                          検査する = 常に fail する空ゲート を検出)
  D placement field     : schema placement の各 field が render-report.js に消費されるか、
                          消費しないなら schema description に "advisory" と明記されているか。
                          (dead field = 宣言のみで render 未反映 を検出)
  F constant parity     : 生成器の定数と、それを検査する検査器の定数が同値か。
                          (svg-kit.cjs STROKE.hairline ↔ validate-svg-diagram.py MIN_STROKE_WIDTH、
                          render-report.js --report-measure ↔ validate-report-layout.js CPL_TARGET。
                          片側だけ動かすと検査が静かに無効化される二重定義を封鎖)
  G css var fallback    : references の CSS/SVG 例が引く `var(--x)` のうち、生成器
                          (style-builder.cjs / render-report.js) が定義しない変数に
                          フォールバックが付いているか。未定義変数をフォールバック無しで
                          引くと、CSS はその宣言ごと無効化する (色や背景が黙って消える)。
  H palette parity      : references の散文が載せる `--x: #hex` / `var(--x, #hex)` /
                          表の色見本が、配色の正本 style-builder.cjs SPEC.colors と
                          一致するか。散文の色見本はそのまま複製されるので、古い値を
                          置くと誤った配色が「正解」として増殖する (実測: ライト/ダーク/
                          Lotus White の 3 テーマ表がどれも実出力と違う値を『デフォルト』
                          として載せていた)。意図的に別値を載せる面 (上書き例・vendor の
                          逐語引用・d3 固有パレット) は直前に `<!-- palette-variant: 理由 -->`
                          を書いて除外する。暗黙の例外は作らない。
  E role-policy SSOT     : role→narrative 方針の機械可読 SSOT (validate-report-visual.py の
                          _NARRATIVE_REQUIRED/OPTIONAL_ROLES) と reference report-narrative-logic.md
                          §6.1 の role 群表が過不足なく一致するか。(3系統手更新の drift を封鎖。
                          schema role enum との MECE は tests が担保)

exit: 0=PASS(drift 無し) / 1=drift 検出 / 2=usage・対象ファイル不在。
pytest からは run_checks(root) を import して findings[] を得る。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _plugin_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    # scripts/lint-contract-drift.py → plugin root は 1 つ上。
    return Path(__file__).resolve().parent.parent


# report 経路で「render が X を Y へ反映する」系の主張を書く散文ファイル群 (drift 源)。
_PROSE_GLOBS = [
    "references/report-*.md",
    "references/mermaid-integration.md",
    # 図解経路の散文。第 4 次 update で D14-D17 / C25 の閾値をこれらが持つように
    # なったため、report 系と同じ drift 監視下へ入れる。layout-contract は
    # §D-2 / §D-4 の数値の正本そのもので、検査器が実行時に読む相手でもある。
    "references/diagram-layout-contract.md",
    "references/diagram-style-tokens.md",
    "references/diagram-type-crosswalk.md",
    # NOTE: 型テンプレート集 (diagram-visual / -comparison / -cycle-flow / -business /
    # -extended / -technical …) は意図的に含めない。これらは HTML/SVG のコード例をそのまま載せる
    # 面なので、骨格や tpl の data-* 属性 (data-diagram-id / data-figure-width /
    # data-tooltip / data-start …) がチェック A に phantom 属性として拾われる (実測: 上記
    # 3 ファイルを入れると 5 件)。それらは render-report.js が emit するものではなく
    # 「作図側が書く属性」で、drift ではない。diagram-technical.md (§11.35-11.40 の
    # 技術系 6 型) も同じ理由で除外する (実測: 追加すると data-diagram-id /
    # data-figure-width が phantom 属性として 2 件誤検出される)。
    "skills/run-slide-report-generate/references/report-*.md",
    "skills/run-slide-report-generate/prompts/R2-agent-report-structure-designer.md",
    "skills/run-slide-report-generate/prompts/R2-agent-visual-strategist.md",
    "skills/run-slide-report-generate/prompts/R3-agent-report-composer.md",
    "skills/run-slide-report-generate/prompts/R3-agent-report-quality-reviewer.md",
    # schema の description は「実装がこう振る舞う」を日本語で書ける唯一の JSON で、
    # 値・data-* 属性が散文と同じ形で紛れ込む (実測: 追加しても新規 finding 0 件＝誤検出無し)。
    # visual-derivation-table.json のように description が長い決定表を守るため対象へ入れる。
    "schemas/*.json",
    # NOTE: "skills/*/SKILL.md" は意図的に含めない。agent 名 `data-visualizer` を
    # チェック A が data-* 属性の主張と誤認して phantom 属性 1 件を出す (実測)。
    # 属性でない `data-` 前置の固有名詞が SKILL.md には日常的に出るため、
    # allowlist で個別に潰すと allowlist 側が新たな二重管理になる。
]

_RENDER = "vendor/scripts/render-report.js"
# 図解の散文は slide と report の両経路を跨いで書かれる (図解は両方の成果物に載る)。
# これらのファイルに限り、チェック A の「実装が emit する」真の集合へ slide の
# renderer も含める。report 経路の散文へ緩めると、report 側の phantom 属性を
# slide 側の emit が隠してしまうため、対象はここに挙げたファイルだけに閉じる。
_SLIDE_RENDER = "vendor/scripts/render-slide.cjs"
_SLIDE_SCOPED_PROSE = (
    "references/diagram-layout-contract.md",
    "references/diagram-style-tokens.md",
    "references/diagram-type-crosswalk.md",
)
_VALIDATOR = "scripts/validate-report-visual.py"
_SCHEMA = "schemas/report-structure.schema.json"

_DATA_ATTR_RE = re.compile(r"data-[a-z][a-z0-9-]*")
# render が emit する data-* だけを真とみなすため、renderReport 由来のコードから抽出する。
# prose 側で意味マーカとして許容する非 render 由来の data-*（現状なし）はここで allowlist する。
_DATA_ATTR_ALLOWLIST: set[str] = set()


def _cited_data_attrs(text: str) -> set[str]:
    """散文中で『HTML data-* 属性として主張されている』トークンだけを抽出する。

    backtick インラインコード内 or 属性構文 `data-xxx=` に現れるものに限定し、
    『data-ink 比』のような可視化ドメイン用語(属性でない散文)を誤検出しない。
    """
    attrs: set[str] = set()
    for span in re.findall(r"`([^`]+)`", text):          # インラインコード span 内
        attrs.update(_DATA_ATTR_RE.findall(span))
    attrs.update(re.findall(r"(data-[a-z][a-z0-9-]*)\s*=", text))  # 属性構文 data-xxx=
    return attrs


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _prose_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for g in _PROSE_GLOBS:
        files.extend(sorted(root.glob(g)))
    return [f for f in files if f.is_file()]


def _load_thresholds(root: Path) -> dict:
    """validate-report-visual.py を import せず DEFAULT_THRESHOLDS を決定論抽出する。"""
    src = _read(root, _VALIDATOR)
    m = re.search(r"DEFAULT_THRESHOLDS\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
    out: dict[str, int] = {}
    if not m:
        return out
    for key, val in re.findall(r'"([a-z_]+)"\s*:\s*(\d+)', m.group(1)):
        out[key] = int(val)
    return out


def _validator_fidelity_targets(root: Path) -> set[str]:
    """validate-report-visual.py が render-fidelity で存在検査する class/data 属性を抽出する。"""
    src = _read(root, _VALIDATOR)
    targets: set[str] = set()
    # `"report-xxx" not in html` / `"data-xxx" not in html` パターン + block_class map の値。
    for tok in re.findall(r'"(report-[a-z-]+|data-[a-z-]+)"\s*(?:not )?in html', src):
        targets.add(tok)
    for tok in re.findall(r'"(report-[a-z-]+)"', src):
        # block_class map の値 (report-deflist 等) も含める。render-fidelity で使う class に限定するため
        # 実際の in-html 検査に現れるものだけを上で拾い、ここは補助 (block_class 由来)。
        if tok in ("report-deflist", "report-footnotes", "report-tasklist"):
            targets.add(tok)
    return targets


def _load_role_sets(root: Path) -> tuple[set[str], set[str]]:
    """validate-report-visual.py を機械可読 SSOT とみなし role→narrative 方針2集合を抽出する。"""
    src = _read(root, _VALIDATOR)

    def extract(name: str) -> set[str]:
        m = re.search(name + r"\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
        return set(re.findall(r'"([a-z-]+)"', m.group(1))) if m else set()

    return extract("_NARRATIVE_REQUIRED_ROLES"), extract("_NARRATIVE_OPTIONAL_ROLES")


def _reference_role_groups(root: Path) -> dict[str, set[str]]:
    """report-narrative-logic.md §6.1 の role→narrative 表から group 別 role 集合を抽出する。

    group 列 (`**期待**` / `**不要**` / `**文脈依存**`) を含む行の backtick role を拾う。
    表が見つからなければ空 dict (構造変更時に誤検出しないため呼び出し側で skip)。
    """
    text = _read(root, "references/report-narrative-logic.md")
    groups: dict[str, set[str]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        for label, key in (("**期待**", "expected"), ("**不要**", "optional_strict"), ("**文脈依存**", "context")):
            if label in line:
                roles = set(re.findall(r"`([a-z][a-z-]*)`", line))
                if roles:
                    groups[key] = roles
    return groups


def _placement_fields(root: Path) -> tuple[list[str], dict[str, str]]:
    """schema placement の field 名と各 field description を返す (deprecated alias emphasis は除外)。"""
    try:
        schema = json.loads(_read(root, _SCHEMA))
    except (json.JSONDecodeError, ValueError):
        return [], {}
    props = (((schema.get("$defs") or {}).get("placement") or {}).get("properties")) or {}
    fields = [k for k in props if k != "emphasis"]  # emphasis は emphasisZone の後方互換 alias
    descs = {k: (props[k].get("description") or "") for k in props}
    return fields, descs


# 生成器と検査器に二重定義された定数の対。片側変更で検査が静かに無効になるため、
# コメントによる人手同期義務でなく機械で縛る。値は Python から JS を import できない
# 制約に合わせ、正規表現で定義行から抜く (_load_thresholds と同じ手口)。
# 生成器が :root へ流し込む CSS 変数の出どころ。ここに定義が無い変数を
# references が引くなら、フォールバック無しでは実行環境で解決できない。
#
# 経路ごとに別の集合を持つ。**5 経路を 1 つの集合へ混ぜてはいけない**。混ぜると
# 「どこかの経路に存在すれば緑」になり、決定論経路の CSS へ手書き経路の名前を書いても
# 通ってしまう (実例: `--fs-body-lg` は決定論経路に無く、宣言ごと無効になっていた)。
# 名前が偶然重なるので個数照合も効かない: 決定論 slide の font-size 系 4 種と report の
# 5 種は、和集合がちょうど 7 種になり、ひな形 slide の 7 種と個数が一致してしまう。
# 集合そのもので照合すること。
# 経路の登録簿。ここに載せた経路だけが「CSS 変数を :root へ出す主体」で、
# 文書側の var() はこの集合とだけ照合される。
#
# 登録の条件 (2026-08-14): 各エントリに **何がそれを出力し、何がそれを消費するか**を
# 書けること。登録すればその変数は鳴らなくなるので、この登録簿は _KNOWN_GAPS と同じ
# 「書けば黙る」性質を持つ。産出元と消費先を書けないものは経路ではないので載せない。
#
# 定義を含むファイルすべてがここへ載るわけではない。定義元は素性で 5 つに分かれ、
# 経路として登録するのは 1 種類目だけ。残りの区分と根拠は _NON_ROUTE_DEFINERS に置く。
_VAR_ROUTE_SOURCES = {
    # 決定論 slide。style-builder.cjs が寸法・単位・書体を、html-scaffold.js が
    # palette を :root へ流し、render-slide.cjs が面ごとの実測値 (--fit-t / --fit-d) を
    # 実行時に足す。3 ファイルで 1 経路 (どれも同じ 1 枚の deck の :root を作る)。
    # 産出: structure.json -> deck の index.html / 消費: validate-print.js,
    #       validate-slide-layout.js, evaluate-deck.js
    "det-slide": ("vendor/scripts/style-builder.cjs", "vendor/scripts/html-scaffold.js",
                  "vendor/scripts/render-slide.cjs"),
    # ひな形 slide (.srg-* 体系)。閾値の正本は frame-contract.json で、
    # それを CSS へ落とすのが build-slide-skeleton-css.py。
    # 産出: assets/slide-templates/slide-skeleton.css / 消費: build-slide-skeletons.py,
    #       validate-slide-skeleton.py
    # build-slide-skeletons.py は 2026-08-14 に外した。ひな形 HTML を組み立てるだけで
    # CSS 変数を 1 つも出しておらず (実測 defs=0)、登録簿が「出している」と主張しながら
    # 出していない状態だった。宣言と実体のずれは、この検査器が他所で潰している形と同じ。
    "skeleton-slide": ("scripts/build-slide-skeleton-css.py",),
    # 手書き slide (slider-* 体系)。LLM が HTML を書く経路で、:root の実体が
    # references/theme-style.md にある (文書が実装を兼ねている状態)。
    # 単位トークン (--su / --sv / --slide-max-*) だけは html-generation-rules.md の
    # §5.6.1 :root が正本で、slide-types-basic.md も「--su / --sv は
    # html-generation-rules.md §5.6.1 の :root で定義する」と名指ししている。
    # 2 ファイルで 1 経路 (どちらも手書きデッキの同じ :root を作る)。
    "hand-slide": ("references/theme-style.md",
                   "skills/run-slide-report-generate/references/html-generation-rules.md"),
    # report。
    # 産出: report.html の :root / 消費: validate-report-visual.py, validate-print.js
    "report": ("vendor/scripts/render-report.js",),
    # 図解 (SVG)。値の正本は svg-kit.cjs の TOKENS / SERIES と style-builder の
    # SPEC.colors の 2 つだけ、と diagram-style-tokens.md 自身が宣言している。
    # ただし **CSS 変数を出しているのは style-builder だけ**で、svg-kit の TOKENS は
    # JS の値として SVG 属性へ直接焼かれる (実測 defs=0)。2026-08-14 に svg-kit を
    # 外し、この経路の CSS 変数集合は style-builder 単独であることを明示した。
    # 値の正本が 2 つあること自体は変わらない (それは constant-parity が見る)。
    # 産出: 図解 SVG を含む面の :root / 消費: validate-svg-diagram.py,
    #       render-diagram-golden.cjs
    "diagram": ("vendor/scripts/style-builder.cjs",),
    # 全面画像デッキ。image-deck-plan.json + slide-NN.meta.json から自己完結の
    # index.html を決定論生成する。2026-08-14 に追加 (それまで登録簿に無く、12 個の
    # 定義がどの経路にも属さない扱いになっていた)。
    # 産出: 全面画像 deck の index.html / 消費: build-single-html.js,
    #       validate-ai-image-assets.js
    "full-image-deck": ("vendor/scripts/build-deck-html.js",),
}

# 経路ではないが CSS 変数の定義を含むファイル。区分と、なぜその区分かを 1 行で置く。
# ここに無く経路にも無い定義元は「孤児」として orphan_definer_findings が鳴らす。
#
# 区分を動かすときは根拠の行も書き換えること。根拠が無いと次の人が動かせない。
_NON_ROUTE_DEFINERS = {
    # 生成物: 経路の出力。入力として二重に数えないために経路へ載せない。
    "assets/slide-templates/slide-skeleton.css":
        "生成物。先頭に「生成物。手で編集しない。再生成: build-slide-skeleton-css.py」と明記。skeleton-slide 経路の出力",
    # 共通テンプレート: 自分の名前空間を定義しつつ、値は経路変数を消費する。
    # どの経路にも属さないが孤児でもない (経路をまたいで使われるのが正しい)。
    "vendor/assets/pagination.css":
        "共通テンプレート。--pg-* を自分で定義し値は var(--ink, #141412) 等で経路変数を消費する。style-builder.cjs / render-slide.cjs / build-slide-skeleton-css.py から参照",
    "vendor/assets/d3-slide-template.html":
        "共通テンプレート。D3 スライドの雛形で、validate-d3.js が消費する",
    # 検査器・テスト: 期待値として CSS を書くので定義に見えるだけ。
    "scripts/validate-visual-generation.py":
        "検査器。--fs-lead: 6rem 等は判定用の期待値文字列で、どの deck にも出力されない",
    "scripts/lint-contract-drift.py":
        "検査器。この検査器自身のメッセージ文字列",
}
# 文書がどの経路のものかは機械には判定できないので、文書自身に宣言させる。
# この行より後ろの var() は、その経路の集合とだけ照合する (次の宣言まで有効)。
# 宣言の無いまま `var(--x)` を書いた文書は fail-closed で落とす。和集合へ退避すると
# 「どこかにあれば緑」へ戻り、この検査の意味が無くなる。
_VAR_ROUTE_MARK_RE = re.compile(r"<!--\s*css-route:\s*([a-z-]+)\s*-->")
_VAR_DEF_RE = re.compile(r"(--[a-z0-9-]+)\s*:")
# 生成器は `--space-${i + 1}: ...` のように族をループ生成することがある。
# 静的抽出では 1 件も名前が取れないので、補間を含む定義は「接頭辞の族」として
# 許容する (これを見ないと --space-4 等が丸ごと未定義に見え、偽陽性で埋まる)。
_VAR_FAMILY_RE = re.compile(r"(--[a-z0-9-]*?)\$\{[^}]*\}\s*:")
# `var(--x)` = フォールバック無し / `var(--x, ...)` = あり。後者だけが安全。
_VAR_USE_RE = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*([,)])")


def _var_scan_targets(root: Path) -> list[Path]:
    """CSS 変数の照合対象となる文書。

    plugin root の `references/*.md` だけを見ていた頃は、手書き経路の記述が
    `skills/*/references/` にあるため丸ごと検査圏外だった。references は再帰で、
    skills 配下は references と prompts を拾う (prompts も CSS 例を載せる)。
    """
    seen: list[Path] = []
    for pat in ("references/**/*.md",
                "skills/*/references/**/*.md",
                "skills/*/prompts/**/*.md"):
        seen.extend(root.glob(pat))
    return sorted(set(seen))

_CONSTANT_PAIRS = (
    (
        "図解の最小線幅",
        ("vendor/scripts/svg-kit.cjs", r"hairline:\s*([0-9.]+)"),
        ("scripts/validate-svg-diagram.py", r"^MIN_STROKE_WIDTH\s*(?::\s*float\s*)?=\s*([0-9.]+)"),
    ),
    (
        "本文の 1 行あたり文字数",
        ("vendor/scripts/render-report.js", r"--report-measure:\s*([0-9.]+)em"),
        ("scripts/validate-report-layout.js", r"CPL_TARGET\s*=\s*([0-9.]+)"),
    ),
    # --- 図解の幾何 (v7.7.0 で spec-registry §15 へ明文化した値) -----------------
    # 対の相手は spec-registry.md。ここだけ「実装 ↔ 検査器」でなく「実装 ↔ 正本文書」に
    # なるのは、これらの値を検査器が持たない (D10/D11/D13 は実装から実行時抽出する
    # = SR-15-11) 一方、契約として読者へ数値を示す必要があるため。数値を文書へ書いた
    # 時点で二重管理が生まれるので、書いた数値は必ずここで縛る。
    # 逆に言えば、ここへ登録できない数値は文書に書かない (正本の名前だけ書く)。
    (
        "矢じりの幅 MARKER.w",
        ("vendor/scripts/svg-kit.cjs", r"const MARKER = \{(?:.|\n)*?\bw:\s*([0-9.]+),"),
        ("references/spec-registry.md", r"`MARKER = \{ w: ([0-9.]+),"),
    ),
    (
        "矢じりの参照点 MARKER.refX (overhang = w - refX の基準)",
        ("vendor/scripts/svg-kit.cjs", r"const MARKER = \{(?:.|\n)*?\brefX:\s*([0-9.]+),"),
        ("references/spec-registry.md", r"`MARKER = \{[^`]*refX: ([0-9.]+)"),
    ),
    (
        "矢じりの開き MARKER.h (FAN_MIN_GAP = snap(h × primary) の因子)",
        ("vendor/scripts/svg-kit.cjs", r"const MARKER = \{(?:.|\n)*?\bh:\s*([0-9.]+),"),
        ("references/spec-registry.md", r"`MARKER = \{ w: [0-9.]+, h: ([0-9.]+),"),
    ),
    (
        "主コネクタの線幅 STROKE.primary (FAN_MIN_GAP = snap(h × primary) の因子)",
        ("vendor/scripts/svg-kit.cjs", r"const STROKE = \{(?:.|\n)*?\bprimary:\s*([0-9.]+),"),
        ("references/spec-registry.md", r"`primary: ([0-9.]+)`"),
    ),
    (
        "図解 canvas の標準幅 CANVAS.w",
        ("vendor/scripts/svg-builder.cjs", r"const CANVAS = \{\s*w:\s*([0-9.]+),"),
        ("references/spec-registry.md", r'viewBox="0 0 ([0-9.]+) 540"'),
    ),
    (
        "D11 の複雑度係数 COMPLEXITY_FACTOR",
        ("scripts/validate-svg-diagram.py", r"^COMPLEXITY_FACTOR\s*=\s*([0-9.]+)"),
        ("references/spec-registry.md", r"`COMPLEXITY_FACTOR = ([0-9.]+)`"),
    ),
    # --- コードブロックの幾何 (spec-registry §10) --------------------------------
    # engine が `calc(60 * var(--sv))` へ移った後も、§10 と CONST_020 と S26 と
    # structure-template が「420px が正しい」と言い続けていた。数値の正本が
    # style-builder.cjs にしか無いのに、読者向けの写しがどこにも縛られていなかった
    # ためで、check-consistency.js は V-005 を実装していないので緑でも意味が無い。
    # ここへ登録して、写しは spec-registry §10 の 1 枚だけにする。
    (
        "コードブロックの縦上限 .code-block max-height",
        ("vendor/scripts/style-builder.cjs",
         r"\.code-block \{ max-height: calc\(([0-9.]+) \* var\(--sv\)\)"),
        ("references/spec-registry.md",
         r"`\.code-block \{ max-height: calc\(([0-9.]+) \* var\(--sv\)\)"),
    ),
    (
        "Before/After パネルの縦上限 .code-panel max-height",
        ("vendor/scripts/style-builder.cjs",
         r"\.code-panel \{ width: 48%; max-height: calc\(([0-9.]+) \* var\(--sv\)\)"),
        ("references/spec-registry.md",
         r"\.code-panel \{ width: 48%; max-height: calc\(([0-9.]+) \* var\(--sv\)\)"),
    ),
    # 字面の下限は frame-contract.json が正本で、style-builder.cjs はそれを
    # `${MIN_REM_ENGINE}rem` として埋め込むだけになった。生成器側にもう数値の実体が
    # 無いので、突合の src は契約そのものを見る。
    (
        "コードの字面 .code-block font-size (typography.min_rem_engine の面座標表現)",
        ("assets/slide-templates/frame-contract.json",
         r'"min_rem_engine":\s*([0-9.]+)'),
        ("references/spec-registry.md", r"`font-size: ([0-9.]+)rem; line-height: 1\.7;"),
    ),
)


_PALETTE_SRC = "vendor/scripts/style-builder.cjs"
_SPEC_COLORS_RE = re.compile(r"colors:\s*\{(.*?)\n  \}", re.S)
_COLOR_ENTRY_RE = re.compile(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'")
# buildRootVars() の `  --fg-muted: ${c.inkMuted};` から (変数名, キー名) を採る。
_ROOT_ASSIGN_RE = re.compile(r"--([a-z0-9-]+):\s*\$\{c\.(\w+)\}")
_PALETTE_MARKER = "palette-variant:"
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


_CONTRACT_PATH = "assets/slide-templates/frame-contract.json"
# frame-contract.json の節のうち、**1 経路しか読んでいない**もの。
#
# 事故は「節名が主張する適用範囲」と「実際の読み手の範囲」がずれたときに起きる。
# 複数経路が読む節は名前が広くて読み手も広いので一致している。危ないのは名前が広くて
# 読み手が狭い節で、別経路が同じ名前を見て「自分の契約だ」と読むと、片方の経路にしか
# 正しくない値がもう片方へ流れる。
#
# いちばん強い直し方は名前を直すことなので、`print` は `print_skeleton` へ改名済み。
# この集合は改名の代わりではなく、改名できていない節 (chrome / media) を止めるためと、
# 改名した節を将来また広げないための二重化。
#
# 逆に複数経路が読む節 (canvas / grid / stage / typography / fill_policy 等) はここに
# 挙げない。そこにあるのは全経路で同じ値が正しい面の幾何で、経路ごとに値が違う箇所は
# 既にキーが割られている (typography.min = ひな形 / min_rem_engine・min_font_scale =
# エンジン)。読み手を固定しても経路の主張にはならず、読み手が増えるたびの更新作業だけ
# が残る。
#
# 限界を明記する: 判定は「契約を読むファイルが節名の文字列を綴っているか」であって、
# 実際に契約から読んだかではない。build-slide-skeletons.py のようにひな形自身の
# spec dict が `"chrome": "full"` を持つ書き方は同名で当たる (両者とも集合内なので
# 現状は無害)。集合外のファイルが同名の自前キーを持った場合は偽陽性になるので、
# そのときは節名を改名して衝突を解く (免除を足さない)。
_SECTION_READERS = {
    "print_skeleton": (
        "scripts/build-slide-skeleton-css.py",
        "scripts/build-slide-skeletons.py",
        "scripts/validate-slide-skeleton.py",
        "tests/test_slide_skeleton.py",
    ),
    "chrome": (
        "scripts/build-slide-skeleton-css.py",
        "scripts/build-slide-skeletons.py",
        "scripts/validate-slide-skeleton.py",
    ),
    "media": (
        "scripts/build-slide-skeletons.py",
        "scripts/validate-slide-skeleton.py",
    ),
}
_SECTION_READER_ROUTE = "ひな形 (slide-skeleton) 経路"
# 検査器と検査器のテストは、節名を「宣言として」綴るので必ず当たる。値を読む側では
# ないため対象外にする。ここを広げると自己免除で検査が無効になるので、2 本に閉じる。
_SECTION_READER_EXEMPT = (
    "scripts/lint-contract-drift.py",
    "tests/test_lint_contract_drift.py",
)
_CODE_SUFFIXES = (".py", ".js", ".cjs", ".mjs")


def _section_ref_re(section: str) -> re.Pattern:
    """節名の参照だけを拾う。`print(` のような同名の言語機能は拾わない。"""
    return re.compile(r"""["'\[]""" + re.escape(section) + r"""["'\]]|\.""" + re.escape(section) + r"\b")


def _contract_loaders(root: Path) -> list[Path]:
    """frame-contract.json を読み得るコードファイル (パスを綴っているもの) を返す。

    契約のパスを綴っていないファイルは節を読めないので対象外。ここを広げると
    `print` のような普遍名が無関係なコードで大量に当たる。
    """
    out = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in _CODE_SUFFIXES or not path.is_file():
            continue
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        if "frame-contract" in path.read_text(encoding="utf-8", errors="ignore"):
            out.append(path)
    return out


def section_reader_findings(root: Path) -> list[dict]:
    """経路専有の契約節を、宣言された集合の外のファイルが読んでいないか照合する。

    run_checks から切り出してあるのは、この検査自身を反例で試せるようにするため。
    どこにも違反が無い状態でしか動かしていない検査は、検査しているのか素通りして
    いるのか区別が付かない (それが今回潰している欠陥そのもの)。
    """
    findings: list[dict] = []
    if not (root / _CONTRACT_PATH).is_file():
        return [{"check": "contract-section-reader",
                 "message": f"{_CONTRACT_PATH} が無い (節の読み手を照合できない)",
                 "where": _CONTRACT_PATH}]
    loaders = _contract_loaders(root)
    for section, allowed in _SECTION_READERS.items():
        ref_re = _section_ref_re(section)
        for path in loaders:
            rel = path.relative_to(root).as_posix()
            if rel in allowed or rel in _SECTION_READER_EXEMPT:
                continue
            if not ref_re.search(path.read_text(encoding="utf-8", errors="ignore")):
                continue
            findings.append({
                "check": "contract-section-reader",
                "message": (
                    f"{rel} が frame-contract の '{section}' 節を読んでいるが、"
                    f"この節は {_SECTION_READER_ROUTE} 専有として宣言されている "
                    f"(読み手は {', '.join(allowed)})。"
                    "別経路が読むと、片方にしか正しくない値がもう片方へ静かに流れる "
                    "(例: print_skeleton は 297x167.06mm のレターボックス版面で、"
                    "決定論エンジンの印刷 297x210mm full-bleed とは別物)。"
                    f"その経路にも同じ値が正しいなら _SECTION_READERS['{section}'] へ足す。"
                    "経路ごとに値が違うなら、経路名を含む別キーへ割ること"
                ),
                "where": rel,
            })
    return findings


# 読み取り用画像 (QR 等) の寸法規約 CONST_010 を、文書の側で守らせる検査。
#
# 規約は 2 つある。(1) 上限は面高に対する比で置く。(2) `vh` は使わない
# (`@media print` で基準が用紙高へ変わり、画面と印刷で寸法が食い違う)。
# どちらも 2026-08-14 までは文書にしか無く、守らせる実行体が無かった。
#
# 比の正本は frame-contract.json の read_image.max_height_ratio 1 箇所。生成された
# CSS 文字列ではなく契約を読むのは、生成器を差し替えた日にこの検査が黙って的外れに
# ならないようにするため。
#
# 文書の CSS 例は `var(--qr-max-ratio, 0.26)` の形で書く。--qr-max-ratio を :root へ
# 出す経路が 1 つも無いので、フォールバックが無いと解決しない。この 0.26 は契約値の
# 第 2 の写しなので、下の _QR_FALLBACK_RE で拾って契約値と突き合わせる。写しを許す
# 代わりに、写しが正本から離れられないようにする形。
_QR_RATIO_KEY = ("read_image", "max_height_ratio")
_QR_VAR = "--qr-max-ratio"
_QR_FALLBACK_RE = re.compile(r"var\(\s*" + re.escape(_QR_VAR) + r"\s*,\s*([0-9.]+)\s*\)")
# 読み取り用画像の寸法を書いている行の目印。`.qr-img` を含む行だけを見る
# (文書全体から vh を狩ると、無関係な例まで巻き込む)。
_QR_SEL = ".qr-img"
_QR_VH_RE = re.compile(r"[0-9.]+vh\b")
# vh の検査はコードフェンスの中だけに効かせる。規約が禁じているのは「CSS が vh で
# 書かれていること」であって、vh という文字列が文書に出ることではない。実際、
# CONST_010 の未解決メモは出荷済み deck が 18vh / 26vh で書かれている事実を述べる
# ために .qr-img と vh を同じ行へ並べており、フェンスを見ないとこの記述が落ちる。
# 違反を記録した文が違反として落ちる検査は、記録を消させる方向に働くので採らない。
_FENCE_RE = re.compile(r"^\s*```")


# 孤児定義 (どの経路にも属さない :root 定義) の検査。
#
# 見つけたい欠陥は「経路をまたいで値が違うこと」ではない。経路ごとに値が違うのは
# 正しい (--fs-body は report で 1.0625rem、slide で vw 基準。読み手は必ず自分の経路の
# 値を引く)。実測でも「同名・異値」を素直に鳴らすと 205 変数中 99 変数が該当し、その
# ほとんどが意図した経路差だった。
#
# 事故が起きるのは **どの経路にも属さない定義が存在するとき**。読んだ人はどの経路でも
# 使われていない値を引き、それが正しいかどうかを確かめる手段が無い。実例が
# vendor/assets/src/styles/variables.css の旧 Lotus パレット (--fg: #43436c) で、
# 現行のどの生成器も出していない --fg の第 2 の正本になっている。
#
# 異名・同値 (--fg-dim と --fuji-gray がどちらも #6a6a68 等) はここでは見ない。あれは
# 単射性の問題で、図解側の検査が別に見ている。混ぜると、意図的に名前を寄せた結果まで
# 赤になる。
_VAR_DEF_VALUE_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;\n}]+)")
# 値に和文が混じる「定義」は CSS ではない。実測で 2 種類に当たった:
#   - CLI フラグのヘルプ (validate-structure.js の `--strict: WARN を FAIL に格上げ`)
#   - コメントの散文 (pagination.js の `--fit-t : 11.00 が消え、見出しが ...`)
# 規約が禁じているのは値がそこで定義されていることであって、`--x:` という並びが
# ファイルに出ることではない。フェンス判定と同じ理由でここも実体だけを見る。
_JP_RE = re.compile(r"[぀-ヿ一-鿿]")
_DEFINER_SUFFIXES = (".css", ".js", ".cjs", ".mjs", ".py", ".html")


def _definition_names(text: str) -> set[str]:
    """CSS 変数の実定義名を返す (和文値のものは定義として数えない)。"""
    return {m.group(1) for m in _VAR_DEF_VALUE_RE.finditer(text)
            if not _JP_RE.search(m.group(2))}


def _definer_files(root: Path) -> list[Path]:
    """CSS 変数の定義を含みうるコードを列挙する (文書とテストは対象外)。

    文書 (.md) を除くのは、文書は `<!-- css-route: -->` で自分の経路を宣言する別の
    仕組みに乗っているため。テストと golden を除くのは、fixture の期待値が定義に
    見えるだけだから。
    """
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in _DEFINER_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("tests/") or "/tests/" in rel or "node_modules/" in rel:
            continue
        if "examples/diagram-goldens/" in rel:
            continue
        out.append(path)
    return sorted(out)


def orphan_definer_findings(root: Path) -> list[dict]:
    """経路にも既知区分にも属さない CSS 変数定義元を鳴らす。

    併せて逆向きも見る。**登録簿が「出している」と主張しているのに 1 つも出していない
    ファイル**は、登録簿と実体のずれなので鳴らす。登録すれば黙る仕組みなので、
    登録が実体を伴っているかを機械で確かめないと、この登録簿自体が埋葬地になる。
    """
    findings: list[dict] = []
    known = {rel for rels in _VAR_ROUTE_SOURCES.values() for rel in rels}

    for rel in sorted(known):
        path = root / rel
        if not path.is_file():
            findings.append({
                "check": "orphan-var-definer",
                "message": (f"経路の定義元として登録されている {rel} が存在しない。"
                            "登録簿が実体を失っている"),
                "where": rel,
            })
            continue
        if not _definition_names(path.read_text(encoding="utf-8", errors="ignore")):
            findings.append({
                "check": "orphan-var-definer",
                "message": (
                    f"{rel} は経路の定義元として登録されているが CSS 変数を 1 つも"
                    "出していない。登録簿が「出している」と主張しながら出していない状態で、"
                    "この登録を根拠に黙る変数があると、根拠の無い緑になる。"
                    "出さないなら _VAR_ROUTE_SOURCES から外すこと"
                ),
                "where": rel,
            })

    for path in _definer_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in known or rel in _NON_ROUTE_DEFINERS:
            continue
        names = _definition_names(path.read_text(encoding="utf-8", errors="ignore"))
        if not names:
            continue
        sample = ", ".join(sorted(names)[:5])
        findings.append({
            "check": "orphan-var-definer",
            "message": (
                f"{rel} が CSS 変数を {len(names)} 個定義しているが、どの経路にも"
                f"既知の区分にも属していない (例: {sample})。どの経路も出していない値なので、"
                "ここを読んだ人は使われていない第 2 の正本を引く。"
                "経路なら _VAR_ROUTE_SOURCES へ産出元と消費先を書いて登録し、"
                "生成物・共通テンプレート・検査器なら _NON_ROUTE_DEFINERS へ根拠を書いて置く"
            ),
            "where": rel,
        })
    return findings


def qr_ratio_findings(root: Path) -> list[dict]:
    """CONST_010 (読み取り用画像の上限比) を文書に対して照合する。

    section_reader_findings と同じく run_checks から切り出してあるのは、この検査
    自身を反例で試せるようにするため。違反の無い木でしか動かしていない検査は、
    検査しているのか素通りしているのか区別が付かない。
    """
    contract = root / _CONTRACT_PATH
    if not contract.is_file():
        return [{"check": "contract-qr-ratio",
                 "message": f"{_CONTRACT_PATH} が無い (読み取り用画像の上限比を照合できない)",
                 "where": _CONTRACT_PATH}]
    data = json.loads(contract.read_text(encoding="utf-8"))
    node = data
    for key in _QR_RATIO_KEY:
        if not isinstance(node, dict) or key not in node:
            return [{"check": "contract-qr-ratio",
                     "message": (f"frame-contract に {'.'.join(_QR_RATIO_KEY)} が無い。"
                                 "上限比の正本が消えると、文書側の写しを突き合わせる相手が"
                                 "居なくなる (写しだけが残って静かに漂う)"),
                     "where": _CONTRACT_PATH}]
        node = node[key]
    ratio = float(node)

    findings: list[dict] = []
    for path in _var_scan_targets(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        in_code = False
        for num, line in enumerate(text.splitlines(), 1):
            if _FENCE_RE.match(line):
                in_code = not in_code
                continue
            for hit in _QR_FALLBACK_RE.finditer(line):
                if float(hit.group(1)) == ratio:
                    continue
                findings.append({
                    "check": "contract-qr-ratio",
                    "message": (
                        f"{rel}:{num} の {_QR_VAR} フォールバック {hit.group(1)} が、"
                        f"frame-contract の {'.'.join(_QR_RATIO_KEY)} = {ratio} と違う。"
                        "フォールバックは契約値の写しなので、離れると文書の例だけが別の"
                        "上限を主張する。値を変えるなら契約側を直してから写しを合わせること"
                    ),
                    "where": rel,
                })
            if in_code and _QR_SEL in line and _QR_VH_RE.search(line):
                findings.append({
                    "check": "contract-qr-ratio",
                    "message": (
                        f"{rel}:{num} が読み取り用画像の寸法を vh で書いている "
                        f"({_QR_VH_RE.search(line).group(0)})。CONST_010 は面高に対する比で"
                        "置くことを求めている。vh は @media print で基準が用紙高へ変わるため、"
                        "画面と印刷で寸法が食い違う (CONST_006 違反)。"
                        f"calc(var(--stage-h) * var({_QR_VAR}, {ratio})) の形へ直すこと"
                    ),
                    "where": rel,
                })
    return findings


def _palette(root: Path) -> dict[str, str]:
    """配色の正本を {CSS 変数名: hex} で返す。

    キー名から変数名を綴り規則で推測しない。buildRootVars() が
    `--fg-muted: ${c.inkMuted}` のようにキーと違う名前で書き出す組があり、
    規則で当てにいくとその組だけ検査から静かに漏れる (漏れても緑のままなので
    気付けない)。変数名 ↔ キーの対応は生成器の本文そのものから読む。
    """
    src = _read(root, _PALETTE_SRC)
    m = _SPEC_COLORS_RE.search(src)
    if not m:
        return {}
    hexes = dict(_COLOR_ENTRY_RE.findall(m.group(1)))
    return {
        f"--{var}": hexes[key]
        for var, key in _ROOT_ASSIGN_RE.findall(src)
        if key in hexes
    }


def _palette_checkable_lines(text: str):
    """散文から『パレット値を主張している行』だけを (行番号, 行) で列挙する。

    `<!-- palette-variant: 理由 -->` を書いた直後のブロック (表 or コードフェンス、
    次の空行まで) は対象外にする。上書き例・別テーマ・vendor の逐語引用のように、
    正本と違う値をわざと載せる面が実在するため。除外は必ず理由付きの明示マーカで、
    暗黙の例外は作らない。
    """
    skipping = False
    started = False
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if _PALETTE_MARKER in line:
            skipping, started = True, False
            continue
        if skipping:
            if line.strip():
                started = True
            elif started and not in_fence:
                skipping = False
            if skipping:
                continue
        yield i, line


def run_checks(root: Path) -> list[dict]:
    """4 チェックを実行し drift findings[] を返す (副作用なし)。"""
    findings: list[dict] = []

    def add(check, message, where):
        findings.append({"check": check, "message": message, "where": where})

    render_src = _read(root, _RENDER)
    if not render_src:
        add("io", f"{_RENDER} が読めない (対象不在)", _RENDER)
        return findings

    # render が emit する data-* の集合 (真の実装側)。
    emitted_attrs = set(_DATA_ATTR_RE.findall(render_src)) | _DATA_ATTR_ALLOWLIST

    prose_files = _prose_files(root)

    # 図解散文だけが参照できる slide 側の data-* (data-v8-diagram 等)。
    slide_attrs = emitted_attrs | set(_DATA_ATTR_RE.findall(_read(root, _SLIDE_RENDER)))

    # -- A: prose の data-* を render が emit するか -------------------------------
    for pf in prose_files:
        text = pf.read_text(encoding="utf-8")
        rel = pf.relative_to(root).as_posix()
        truth = slide_attrs if rel in _SLIDE_SCOPED_PROSE else emitted_attrs
        for attr in sorted(_cited_data_attrs(text)):
            if attr not in truth:
                add("data-attr-phantom",
                    f"prose が data 属性 '{attr}' を主張するが render-report.js が emit しない (phantom 属性・実装と一致させる)",
                    str(pf.relative_to(root)))

    # -- B: prose の閾値引用が DEFAULT_THRESHOLDS と一致するか ---------------------
    thresholds = _load_thresholds(root)
    for pf in prose_files:
        text = pf.read_text(encoding="utf-8")
        for key, val in thresholds.items():
            for cited in re.findall(re.escape(key) + r"\s*[=＝]\s*(\d+)", text):
                if int(cited) != val:
                    add("threshold-drift",
                        f"prose が '{key}={cited}' と引用するが DEFAULT_THRESHOLDS は {key}={val} (閾値ズレ)",
                        str(pf.relative_to(root)))

    # -- C: validator の render-fidelity 検査対象を render が emit/生成するか --------
    for target in sorted(_validator_fidelity_targets(root)):
        if target not in render_src:
            add("fidelity-orphan",
                f"validate-report-visual.py が render-fidelity で '{target}' を検査するが render-report.js が生成しない (空ゲート・検査は常に fail する)",
                _VALIDATOR)

    # -- D: schema placement field が render 消費 or advisory 明記か -----------------
    fields, descs = _placement_fields(root)
    for field in fields:
        consumed = (f"layout.{field}" in render_src) or (f".{field}" in render_src) or (field in render_src and field == "grid")
        advisory = "advisory" in descs.get(field, "")
        if not consumed and not advisory:
            add("placement-dead-field",
                f"schema placement.{field} が render-report.js に消費されず schema description にも 'advisory' 明記が無い (dead field・live 化 or advisory 明記が要る)",
                _SCHEMA)

    # -- E: role→narrative 方針の SSOT(validator)↔ reference §6.1 表 一致 --------------
    # validate-report-visual.py の2集合を機械可読 SSOT とし、reference の role 群表が
    # それと過不足なく一致するか検証する (3系統手更新の drift を封鎖)。
    required, optional = _load_role_sets(root)
    groups = _reference_role_groups(root)
    if required and optional and {"expected", "optional_strict", "context"} <= set(groups):
        ref_expected = groups["expected"]
        ref_optional = groups["optional_strict"] | groups["context"]
        if ref_expected != required:
            add("role-policy-drift",
                f"reference §6.1『期待』群 {sorted(ref_expected)} が validator _NARRATIVE_REQUIRED_ROLES {sorted(required)} と不一致",
                "references/report-narrative-logic.md")
        if ref_optional != optional:
            add("role-policy-drift",
                f"reference §6.1『不要+文脈依存』群 {sorted(ref_optional)} が validator _NARRATIVE_OPTIONAL_ROLES {sorted(optional)} と不一致",
                "references/report-narrative-logic.md")
    elif required and optional and _read(root, "references/report-narrative-logic.md") and "**期待**" not in _read(root, "references/report-narrative-logic.md"):
        add("role-policy-drift",
            "reference report-narrative-logic.md に §6.1 role→narrative 表(**期待**/**不要**/**文脈依存**)が見つからない (SSOT 表が消失・validator と突合不能)",
            "references/report-narrative-logic.md")

    # -- F: 生成器定数 ↔ 検査器定数の等値 -----------------------------------------
    for label, (src_rel, src_re), (chk_rel, chk_re) in _CONSTANT_PAIRS:
        src_txt = _read(root, src_rel)
        chk_txt = _read(root, chk_rel)
        if not src_txt or not chk_txt:
            add("constant-parity", f"{label}: 対象ファイルが読めない ({src_rel} / {chk_rel})", src_rel)
            continue
        m1 = re.search(src_re, src_txt, re.M)
        m2 = re.search(chk_re, chk_txt, re.M)
        if not m1 or not m2:
            add("constant-parity",
                f"{label}: 定数を抽出できない (定義の書き方が変わった。抽出正規表現を追随させる)",
                src_rel if not m1 else chk_rel)
            continue
        v1, v2 = float(m1.group(1)), float(m2.group(1))
        if v1 != v2:
            add("constant-parity",
                f"{label}: 生成器 {src_rel}={v1} と検査器 {chk_rel}={v2} が不一致。"
                "片側だけ動かすと検査が実質無効になる",
                chk_rel)

    # G: 文書の CSS 変数が「その文書の経路」で定義されているか
    #
    # 照合は経路ごとに閉じる。文書 1 件を 1 つの経路の集合とだけ突き合わせ、
    # 全経路の和集合は決して作らない (_VAR_ROUTE_SOURCES のコメント参照)。
    routes: dict[str, tuple[set[str], set[str]]] = {}
    for route, rels in _VAR_ROUTE_SOURCES.items():
        d, f = set(), set()
        for rel in rels:
            src = _read(root, rel)
            d |= set(_VAR_DEF_RE.findall(src))
            f |= set(_VAR_FAMILY_RE.findall(src))
        routes[route] = (d, f)
        if not d:
            add("css-var-fallback",
                f"経路 {route} から CSS 変数定義を抽出できない (出力の書き方が変わった)。"
                "抽出できない経路は照合が素通りするので、緑を信用してはいけない",
                rels[0])

    for path in _var_scan_targets(root):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root).as_posix()
        # 同じファイル内で :root 定義しているものは、その文書の中で閉じている。
        local = set(_VAR_DEF_RE.findall(text))
        # 経路宣言は位置で効く。宣言行より後ろの var() がその経路に属する。
        # 1 文書が複数経路の実装例を載せることがある (spec-registry のような索引) ので、
        # 文書単位でなく宣言単位で切る。どちらにせよ 1 つの var() が照合される集合は 1 つ。
        marks = [(m.start(), m.group(1)) for m in _VAR_ROUTE_MARK_RE.finditer(text)]
        undeclared: set[str] = set()
        per_route: dict[str, set[str]] = {}
        unknown_routes: set[str] = set()
        for m in _VAR_USE_RE.finditer(text):
            if m.group(2) != ")":
                continue  # フォールバックがあるので未定義でも壊れない
            name = m.group(1)
            if name in local:
                continue
            route = None
            for pos, r in marks:
                if pos < m.start():
                    route = r
                else:
                    break
            if route is None:
                undeclared.add(name)
                continue
            if route not in routes:
                unknown_routes.add(route)
                continue
            defined, families = routes[route]
            if name not in defined and not any(name.startswith(f) for f in families):
                per_route.setdefault(route, set()).add(name)

        if undeclared:
            add("css-var-fallback",
                f"経路の宣言が無いまま CSS 変数をフォールバック無しで参照: {', '.join(sorted(undeclared))}。"
                "どの経路の :root で解決される想定かが決まらないと、定義の有無を照合できない。"
                f"`<!-- css-route: <{'|'.join(_VAR_ROUTE_SOURCES)}> -->` を該当箇所より前に置く",
                rel)
        if unknown_routes:
            add("css-var-fallback",
                f"未知の経路名を宣言している: {', '.join(sorted(unknown_routes))}。"
                f"使えるのは {', '.join(_VAR_ROUTE_SOURCES)} のみ",
                rel)
        for route in sorted(per_route):
            add("css-var-fallback",
                f"経路 {route} が定義しない CSS 変数をフォールバック無しで参照: "
                f"{', '.join(sorted(per_route[route]))}。"
                "未定義の var() は宣言ごと無効になるため、色・背景が黙って消える。"
                "`var(--x, <実値>)` の形にするか、その経路の生成器へ定義を足す",
                rel)

    # H: 散文が載せるパレット値が SPEC.colors と一致するか
    palette = _palette(root)
    if not palette:
        add("palette-drift",
            f"{_PALETTE_SRC} から SPEC.colors を抽出できない (定義の書き方が変わった。抽出正規表現を追随させる)",
            _PALETTE_SRC)
    else:
        # 長い名前から並べ、後続に語構成文字を許さない。`\b` だけだと `--fg-dim` が
        # `--fg` として先にマッチし、別変数の値を突き合わせて誤検出する。
        names_alt = "|".join(sorted((v[2:] for v in palette), key=len, reverse=True))
        var_re = re.compile(r"--(?:" + names_alt + r")(?![\w-])")
        kit_fallbacks = {
            (m.group(1), m.group(2).lower())
            for m in re.finditer(r"var\(\s*(--[\w-]+)\s*,\s*(#[0-9A-Fa-f]{6})\s*\)",
                                 _read(root, "vendor/scripts/svg-kit.cjs"))
        }
        for path in sorted((root / "references").glob("*.md")):
            rel = path.relative_to(root).as_posix()
            for lineno, line in _palette_checkable_lines(path.read_text(encoding="utf-8")):
                # 変数と hex の対応が行の中で確定する書き方だけを見る。
                # `var(--x) ... #hex` のように別々の変数の値が同居する行を
                # 突き合わせると、無関係な hex を誤検出する。
                claims = [(m.group(1), m.group(2))
                          for m in re.finditer(
                              r"var\(\s*(" + var_re.pattern + r")\s*,\s*(#[0-9A-Fa-f]{6})", line)]
                claims += [(m.group(1), m.group(2))
                           for m in re.finditer(
                               r"(" + var_re.pattern + r")\s*:\s*(#[0-9A-Fa-f]{6})", line)]
                if not claims and line.lstrip().startswith("|"):
                    # 表は「変数名の列」と「値の列」で 1 行 1 変数を宣言する形が定型。
                    names = set(var_re.findall(line))
                    hexes = _HEX_RE.findall(line)
                    if len(names) == 1 and len(hexes) == 1:
                        claims = [(names.pop(), hexes[0])]
                for name, got in claims:
                    want = palette[name]
                    if got.lower() == want.lower():
                        continue
                    if (name, got.lower()) in kit_fallbacks:
                        # svg-kit.cjs の TOKENS が持つ逐語のフォールバック。
                        # 図解の D10 (パレット逸脱) は許可色を svg-kit から実行時抽出
                        # するので、作例はこの綴りでなければ warning になる。
                        # フォールバック値と :root 実値の乖離は vendor 側の 1 件の問題で、
                        # diagram-style-tokens.md §1.1 の † 注記が正本として記録している。
                        # ここで作例ごとに数百件へ増幅しても、直せる場所は増えない。
                        continue
                    add("palette-drift",
                        f"{rel}:{lineno} が {name} = {got} と主張するが "
                        f"SPEC.colors は {want}。散文の色見本はそのまま複製されるため、"
                        f"古い値を載せると誤った配色が正解として増殖する。"
                        f"正本へ揃えるか、意図的な別値なら直前に "
                        f"`<!-- {_PALETTE_MARKER} 理由 -->` を書く",
                        rel)

    # I: 経路専有の契約節を、集合外のファイルが読んでいないか
    findings.extend(section_reader_findings(root))

    # J: 読み取り用画像の上限比 (CONST_010) と、文書側の写しの一致
    findings.extend(qr_ratio_findings(root))

    # K: どの経路にも属さない CSS 変数定義元 (と、登録だけあって出していない経路)
    findings.extend(orphan_definer_findings(root))

    return findings


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lint-contract-drift",
        description="report 経路 prose↔code の contract-drift ゲート (fail-closed): data-attr/閾値/render-fidelity/placement field",
    )
    p.add_argument("--root", default=None, help="plugin root (既定=本スクリプトの1つ上)")
    p.add_argument("--json", action="store_true", help="(既定で JSON 出力・互換用フラグ)")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    root = _plugin_root(args.root)
    if not (root / _RENDER).is_file():
        sys.stderr.write(f"error: render source not found under {root}\n")
        return 2
    findings = run_checks(root)
    result = {"passed": len(findings) == 0, "count": len(findings), "findings": findings}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
