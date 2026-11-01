"""非受入例。受入例へ 1 箇所だけ違反を注入し、落ちるべき契約 id を宣言する。

判定器が「何も検出しない空ゲート」でないことを、実装が存在しない段階で示す
唯一の手段がこの受入例 / 非受入例のペアである。
"""

from __future__ import annotations

from collections import namedtuple

import fixtures_lib

RejectCase = namedtuple("RejectCase", ["name", "expected_id", "mutate"])


def _replace(old, new):
    def _m(text, files):
        assert old in text, f"注入対象が受入例に無い: {old!r}"
        return text.replace(old, new, 1), files
    return _m


def _replace_all(old, new):
    """規約そのものを落とす注入。散文と例示の両方から消す (1 契約 1 注入)。"""
    def _m(text, files):
        assert old in text, f"注入対象が受入例に無い: {old!r}"
        return text.replace(old, new), files
    return _m


def _drop_vendored(text, files):
    return text, {}


CASES = (
    # --- identity -----------------------------------------------------------
    RejectCase("prefix-not-ref", "AC-C04-2", _replace("prefix: ref", "prefix: run")),
    RejectCase("hierarchy-l2", "AC-C04-2", _replace("hierarchy_level: L1", "hierarchy_level: L2")),
    RejectCase(
        "description-loses-trigger", "AC-C04-3",
        _replace("資料の部品カタログを確認するとき、", ""),
    ),
    RejectCase("output-language-en", "AC-C04-4", _replace("output_language: ja", "output_language: en")),
    RejectCase(
        "source-untraceable", "AC-C04-5",
        _replace("component-inventory.json#C04", "briefs/README.md"),
    ),

    # --- ref kind の権限と宣言 ------------------------------------------------
    RejectCase(
        "allowed-tools-write", "AC-C04-6",
        _replace("allowed-tools: [Read]", "allowed-tools: [Read, Write, Bash]"),
    ),
    RejectCase(
        "goal-seek-declared", "AC-C04-7",
        _replace("kind: ref\n", "kind: ref\ngoal_seek:\n  engine: inline\n"),
    ),

    # --- 4 面 ----------------------------------------------------------------
    RejectCase(
        "icon-face-missing", "AC-C04-8c",
        _replace("## アイコン規約", "## その他"),
    ),
    RejectCase(
        "writing-face-missing", "AC-C04-8d",
        _replace("## 文章設計の型", "## 付録"),
    ),

    # --- 責務境界 -------------------------------------------------------------
    RejectCase(
        "html-generation-claimed", "AC-C04-9",
        _replace(
            "- HTML の生成はしない (単独 writer は C11 render-handout.py)。",
            "- 問い合わせに応じて HTML の断片を生成して返す。",
        ),
    ),
    RejectCase(
        "verification-claimed", "AC-C04-9",
        _replace(
            "- 生成物の検証はしない (自己完結・アイコン様式は C16、a11y と印刷は C17、\n  言語規約は C18 が持つ)。",
            "- 生成物の自己完結性を自分で検査して合否を返す。",
        ),
    ),

    # --- 語彙の複製 (P03 Y-05 / Y-06 / Y-08) -----------------------------------
    RejectCase(
        "part-ids-enumerated", "AC-C04-10",
        _replace(
            "部品 id の語彙はこの skill に持たない。",
            "部品は B01 表紙 / B02 目次 / B03 ステップ行 のように並ぶ。",
        ),
    ),
    RejectCase(
        "parts-catalog-pointer-dropped", "AC-C04-10",
        _replace("`config/handout-parts.json` (owner: C11)", "手元の一覧"),
    ),
    RejectCase(
        "purpose-vocab-enumerated", "AC-C04-11",
        _replace(
            "用途語彙は `config/handout-purposes.json` (owner: C23)、",
            "用途は guide と lecture と onboarding がある。用途語彙は"
            " `config/handout-purposes.json` (owner: C23)、",
        ),
    ),
    RejectCase(
        "section-kind-enumerated", "AC-C04-12",
        _replace(
            "セクション種別は `config/handout-sections.json` (writer: C12) を引く。",
            "セクション種別は standard / decisions / dialogue の 3 種。"
            "正本は `config/handout-sections.json` (writer: C12)。",
        ),
    ),

    # --- トークン --------------------------------------------------------------
    RejectCase(
        "accent-steps-missing", "AC-C04-13",
        _replace("  --pop-primary-deep: #07505d;\n", ""),
    ),
    RejectCase(
        "var-reference-rule-missing", "AC-C04-14",
        _replace(".card { border-color: var(--pop-primary-soft); }", ".card { border-color: #7fc4d0; }"),
    ),
    RejectCase(
        "accent-value-in-prose", "AC-C04-15",
        _replace(
            "この skill に実値を書かない。",
            "既定のアクセントは #0b7285 である。",
        ),
    ),
    RejectCase(
        "text-limit-owner-claimed", "AC-C04-16",
        _replace(
            "  このスキーマの owner は C11 であり、超過分の折り畳み規則は C12 の CR-TEXT-FOLD\n  が正本。この skill は値も規則も決めない。",
            "  上限値と折り畳み規則はこの skill が決める。",
        ),
    ),

    # --- タイポグラフィと入場 ---------------------------------------------------
    RejectCase(
        "palt-missing", "AC-C04-17",
        _replace_all('font-feature-settings: "palt"', "letter-spacing: 0.01em"),
    ),
    RejectCase(
        "tabular-nums-missing", "AC-C04-17",
        _replace_all("tabular-nums", "monospace"),
    ),
    RejectCase(
        "stagger-needs-js", "AC-C04-18",
        _replace(
            "- 入場は rise-in のスタガー。段差はインライン変数 `--stagger` で与え、JS 非依存\n  で成立させる (JavaScript を使わない)。",
            "- 入場は rise-in のスタガー。段差は読み込み後に JavaScript で付与する。",
        ),
    ),
    RejectCase(
        "reduced-motion-missing", "AC-C04-18",
        _replace(
            "@media (prefers-reduced-motion: reduce) { .section { animation: none; } }\n",
            "",
        ),
    ),

    # --- アイコン ---------------------------------------------------------------
    RejectCase(
        "icon-viewbox-free", "AC-C04-19",
        _replace_all('viewBox="0 0 24 24"', 'viewBox="0 0 32 32"'),
    ),
    RejectCase(
        "icon-stroke-hardcoded", "AC-C04-19",
        _replace_all('stroke="currentColor"', 'stroke="var(--pop-primary)"'),
    ),
    RejectCase(
        "sprite-owner-claimed", "AC-C04-20",
        _replace(
            "- sprite の生成と symbol id の採番は C15 build-icon-sprite.py が行う。\n  この skill は様式を答えるだけで生成しない。",
            "- sprite の生成と symbol id の採番はこの skill が行う。",
        ),
    ),
    RejectCase(
        "unused-symbol-allowed", "AC-C04-20",
        _replace("未使用 symbol は 0 件にする。", "未使用 symbol が残ってもよい。"),
    ),

    # --- 絵文字 -----------------------------------------------------------------
    RejectCase(
        "emoji-rule-dropped", "AC-C04-21",
        _replace("- アイコンの代わりに絵文字は使わない。", "- アイコンは意味のある箇所にだけ置く。"),
    ),
    RejectCase(
        "emoji-used", "AC-C04-21",
        _replace("# ref-handout-design-system", "# ref-handout-design-system \U0001F3A8"),
    ),

    # --- 自己完結 ---------------------------------------------------------------
    RejectCase(
        "user-global-asset-referenced", "AC-C04-22",
        _replace(
            "ユーザーグローバル資産 (`~/.claude/skills` 配下など) は参照しない。",
            "トークンの原本は `~/.claude/skills/jp-web-design/assets/` から読む。",
        ),
    ),
    RejectCase(
        "absolute-path-hardcoded", "AC-C04-22",
        _replace(
            "値の正本は `assets/tokens/<theme>.json` であり",
            "値の正本は `/Users/dev/handout/assets/tokens/<theme>.json` であり",
        ),
    ),

    # --- vendoring --------------------------------------------------------------
    RejectCase(
        "vendor-source-unstated", "AC-C04-23",
        _replace("jp-web-design のモードB「Pop・親しみ」", "社内のデザイン指針"),
    ),
    RejectCase("vendored-file-absent", "AC-C04-23", _drop_vendored),
)


def materialize(case, root):
    """非受入例を tempdir へ書き出して skill ディレクトリを返す。"""
    from pathlib import Path

    text = fixtures_lib.ACCEPT_SKILL_MD
    files = {fixtures_lib.VENDORED_REL: fixtures_lib.VENDORED_BODY}
    text, files = case.mutate(text, files)

    skill_dir = Path(root) / "skills" / "ref-handout-design-system"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    for rel, body in files.items():
        target = skill_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return skill_dir
