"""非受入例 (reject fixture) の定義。

受入例 `fixtures/accept/skills/run-handout-extract/SKILL.md` に対して 1 箇所だけ
契約違反を注入した固定入力を作る。各ケースは「どの契約 id が落ちるべきか」を
明示的に持ち、チェッカが常時 PASS する空ゲートになっていないことを固定する。

注入内容の出典は README.md の契約 id 対応表を参照。
"""

# (case_name, 置換前, 置換後, 落ちるべき契約 id)
REJECT_CASES = [
    # --- 逆抽出の入出力契約 -------------------------------------------------
    (
        "html-parsed-by-skill",
        "本 skill は\n自前で HTML を parse しない",
        "本 skill は\nhtml.parser で HTML を直接走査する",
        "AC-C02-11",
    ),
    (
        "roundtrip-judged-by-byte-equality",
        "HTML のバイト一致は課さない (バイト一致が課されるのは同一構成データからの再生成だけである)",
        "HTML のバイト一致で round-trip を判定する",
        "AC-C02-12",
    ),
    (
        "provenance-included-in-projection",
        "比較対象射影は provenance ブロックを除いた残りであり",
        "比較対象射影は正規化済み構成データの全キーであり",
        "AC-C02-12",
    ),
    (
        "never-guessed-relaxed",
        "マーカーが無い限り推測しない\n(C20 の never_guessed 規則)",
        "マーカーが無い場合は本文の位置から推測して埋める\n(復元率を上げるため)",
        "AC-C02-13",
    ),
    (
        "completion-policy-narrowed",
        "推測値の充填 / 空のまま残置 / 利用者への確認 のいずれかであり",
        "推測値の充填 に統一し",
        "AC-C02-14",
    ),
    (
        "unrecoverable-silently-dropped",
        "黙って欠落させることはしない。",
        "件数が多い場合はレポートから省く。",
        "AC-C02-14",
    ),
    (
        "fidelity-distinction-dropped",
        "推測で埋めた値と HTML から実際に読み取った値は、レポートの fidelity (exact / heuristic) で必ず区別する。",
        "復元した値はレポートへまとめて記載する。",
        "AC-C02-15",
    ),
    (
        "report-roundtrip-diff-element-dropped",
        "   - round-trip 差分 (JSON Pointer / expected / actual)\n",
        "",
        "AC-C02-16",
    ),
    (
        "improvement-suggestion-added",
        "資料内容の書き換え・改善提案はしない。",
        "復元した構成データに対して改善提案を添える。",
        "AC-C02-17",
    ),
    (
        "generation-boundary-crossed",
        "本 skill は構成データを出すところで止まる。",
        "本 skill が続けて資料の生成まで行う。",
        "AC-C02-18",
    ),
    (
        "values-fabricated-to-pass-validation",
        "検証を通すために値を捏造することはしない",
        "検証を通すために不足値を妥当な既定で補う",
        "AC-C02-19",
    ),
    (
        "empty-config-returned-as-success",
        "空の構成データを成功として返さない",
        "部品が 1 件も取れなかった場合も成功として返す",
        "AC-C02-19",
    ),
    (
        "diff-summarized-as-equivalent",
        "差分ありを等価と読める要約にしない。",
        "軽微な差分は等価として要約する。",
        "AC-C02-20",
    ),
    (
        "extract-flags-unspecified",
        "`extract-handout-config.py --html <入力> --out <構成データ> --report <レポート>` を\nBash で起動する。",
        "`extract-handout-config.py` を Bash で起動する。",
        "AC-C02-25",
    ),
    (
        "rerender-path-dropped",
        "確定した構成データを `render-handout.py` で再レンダリングし、",
        "確定した構成データを元 HTML と目視で見比べ、",
        "AC-C02-26",
    ),
    (
        "selfcontained-gate-dropped",
        "`verify-handout-selfcontained.py` で自己完結性を確認したうえで、",
        "そのまま、",
        "AC-C02-26",
    ),

    # --- frontmatter / 骨格 -------------------------------------------------
    (
        "hierarchy-changed",
        "hierarchy: L1",
        "hierarchy: L2",
        "AC-C02-2",
    ),
    (
        "description-trigger-vocabulary-lost",
        "description: 既存の単一 HTML から構成データを逆抽出したいとき、手書き HTML をテンプレート化したいときに使う。",
        "description: 資料まわりの作業を手伝いたいときに使う。",
        "AC-C02-3",
    ),
    (
        "extra-responsibility-added",
        "  - id: R3-roundtrip\n    prompt_required: true",
        "  - id: R4-improve\n    prompt_required: true\n    summary: \"復元した資料の改善案を作る\"\n  - id: R3-roundtrip\n    prompt_required: true",
        "AC-C02-4",
    ),
    (
        "responsibility-ref-dropped",
        "  - prompts/R2-complete.md\n",
        "",
        "AC-C02-5",
    ),
    (
        "goal-seek-max-loops-changed",
        "  max_loops: 5",
        "  max_loops: 3",
        "AC-C02-6",
    ),
    (
        "out1-verify-by-weakened",
        "      verify_by: test",
        "      verify_by: live-trial",
        "AC-C02-7",
    ),
    (
        "extra-criterion-added",
        "    - id: OUT1",
        "    - id: OUT9\n      loop_scope: outer\n      text: \"逆抽出の所要時間が短い\"\n      verify_by: test\n    - id: OUT1",
        "AC-C02-7",
    ),
    (
        "criteria-acceptance-section-renamed",
        "## Criteria acceptance",
        "## 受入基準まとめ",
        "AC-C02-8",
    ),
    (
        "criteria-acceptance-drops-in1",
        "- **IN1** (inner / script): `validate-handout-config.py` が exit 0 を返し、復元不能箇所が\n  補完方針つきでレポートへ列挙されていること。\n",
        "",
        "AC-C02-9",
    ),
    (
        "script-ref-missing",
        "  - ../../scripts/verify-handout-selfcontained.py\n",
        "",
        "AC-C02-10",
    ),
    (
        "c20-dependency-dropped",
        "depends_on: [C11, C12, C16, C20]",
        "depends_on: [C11, C12, C16]",
        "AC-C02-21",
    ),
    (
        "bash-tool-dropped",
        "allowed-tools: [Read, Write, Bash]",
        "allowed-tools: [Read, Write]",
        "AC-C02-22",
    ),
    (
        "output-language-changed",
        "output_language: ja",
        "output_language: en",
        "AC-C02-23",
    ),
    (
        "source-untracked",
        "source: plugin-plans/guide-doc-generator/component-inventory.json#C02",
        "source: handwritten",
        "AC-C02-24",
    ),
    (
        "checklist-item-dropped",
        "- [ ] round-trip 等価の確認\n",
        "",
        "AC-C02-27",
    ),
]
