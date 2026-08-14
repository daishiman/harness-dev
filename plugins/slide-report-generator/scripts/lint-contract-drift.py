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
_VAR_SOURCES = ("vendor/scripts/style-builder.cjs", "vendor/scripts/render-report.js")
_VAR_DEF_RE = re.compile(r"(--[a-z0-9-]+)\s*:")
# 生成器は `--space-${i + 1}: ...` のように族をループ生成することがある。
# 静的抽出では 1 件も名前が取れないので、補間を含む定義は「接頭辞の族」として
# 許容する (これを見ないと --space-4 等が丸ごと未定義に見え、偽陽性で埋まる)。
_VAR_FAMILY_RE = re.compile(r"(--[a-z0-9-]*?)\$\{[^}]*\}\s*:")
# `var(--x)` = フォールバック無し / `var(--x, ...)` = あり。後者だけが安全。
_VAR_USE_RE = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*([,)])")

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
    (
        "コードの字面 .code-block font-size (typography.min の面座標表現)",
        ("vendor/scripts/style-builder.cjs",
         r"\.code-block \{[^}]*font-size: ([0-9.]+)rem"),
        ("references/spec-registry.md", r"`font-size: ([0-9.]+)rem; line-height: 1\.7;"),
    ),
)


_PALETTE_SRC = "vendor/scripts/style-builder.cjs"
_SPEC_COLORS_RE = re.compile(r"colors:\s*\{(.*?)\n  \}", re.S)
_COLOR_ENTRY_RE = re.compile(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'")
_PALETTE_MARKER = "palette-variant:"
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def _camel_to_var(key: str) -> str:
    """SPEC.colors のキー名を、生成器が :root へ書く CSS 変数名へ写す。

    buildRootVars() が `--bg-dark: ${c.bgDark}` の形で 1:1 に書き下しているので、
    ここでの変換規則はその写像そのもの。写像を持たない別表を作ると、
    「正本の正本」が 2 つになって同じドリフトを再発させる。
    """
    return "--" + re.sub(r"(?<!^)(?=[A-Z])", "-", key).lower()


def _palette(root: Path) -> dict[str, str]:
    """配色の正本 SPEC.colors を {CSS 変数名: hex} で返す。"""
    m = _SPEC_COLORS_RE.search(_read(root, _PALETTE_SRC))
    if not m:
        return {}
    return {_camel_to_var(k): v for k, v in _COLOR_ENTRY_RE.findall(m.group(1))}


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

    # G: references の CSS 変数がフォールバックを持つか
    defined: set[str] = set()
    families: set[str] = set()
    for rel in _VAR_SOURCES:
        src = _read(root, rel)
        defined |= set(_VAR_DEF_RE.findall(src))
        families |= set(_VAR_FAMILY_RE.findall(src))
    if not defined:
        add("css-var-fallback", "生成器から CSS 変数定義を抽出できない (出力の書き方が変わった)",
            _VAR_SOURCES[0])
    else:
        for path in sorted((root / "references").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            # 同じファイル内で :root 定義しているものは、その文書の中で閉じている。
            local = set(_VAR_DEF_RE.findall(text))
            missing = sorted({
                m.group(1) for m in _VAR_USE_RE.finditer(text)
                if m.group(2) == ")" and m.group(1) not in defined and m.group(1) not in local
                and not any(m.group(1).startswith(f) for f in families)
            })
            if missing:
                rel = path.relative_to(root).as_posix()
                add("css-var-fallback",
                    f"生成器が定義しない CSS 変数をフォールバック無しで参照: {', '.join(missing)}。"
                    "未定義の var() は宣言ごと無効になるため、色・背景が黙って消える。"
                    "`var(--x, <実値>)` の形にするか、生成器側へ定義を足す",
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
