"""非受入例 (reject fixture) の定義。

受入例 `fixtures/accept/agents/handout-content-architect.md` に対して 1 箇所だけ
契約違反を注入した固定入力を作る。各ケースは「どの契約 id が落ちるべきか」を
明示的に持ち、チェッカが常時 PASS する空ゲートになっていないことを固定する。
"""

# (case_name, 置換前, 置換後, 落ちるべき契約 id)
REJECT_CASES = [
    (
        "tools-bash-added",
        "tools: Read, Write",
        "tools: Read, Write, Bash",
        "AC-C05-3",
    ),
    (
        "isolation-not-fork",
        "isolation: fork",
        "isolation: none",
        "AC-C05-2",
    ),
    (
        "description-drifted",
        "description: ヒアリング結果から資料の構成データ",
        "description: 資料の構成をよい感じに考える",
        "AC-C05-4",
    ),
    (
        "prompt-ref-wrong-target",
        "prompt_ref: skills/run-handout-build/prompts/R-design-config.md",
        "prompt_ref: skills/run-handout-build/prompts/R2-design.md",
        "AC-C05-5",
    ),
    (
        "responsibility-anchor-unmatchable",
        "<!-- responsibility: R1 -->",
        "<!-- responsibility: R-design-config -->",
        "AC-C05-6",
    ),
    (
        "prompt-templates-section-dropped",
        "## Prompt Templates\n\n(対話なし: 自動実行 agent)\n",
        "",
        "AC-C05-6",
    ),
    (
        "auto-agent-marker-dropped",
        "(対話なし: 自動実行 agent)",
        "起動時に渡される task brief に従う。",
        "AC-C05-7",
    ),
    (
        "self-eval-dimensions-dropped",
        "返す前に完全性 (14 項目と必須フィールドの充足)・一貫性 (全体ゴールと各 goal の連なり)・\n検証可能性 (config_path が実在し schema に沿う) を自己点検する。",
        "返す前にひととおり見直す。",
        "AC-C05-7",
    ),
    (
        "html-generation-instructed",
        "- HTML を 1 行も書かない。CSS 変数値・クラス名・SVG マークアップも出力しない。",
        "- セクションごとに <div> でラップした HTML 断片も添えて返す。",
        "AC-C05-8",
    ),
    (
        "must-not-assume-currentdate-dropped",
        "- 現在日を自分で取得しない。",
        "- 日付が無いときは当日の日付を埋めてよい。",
        "AC-C05-9",
    ),
    (
        "must-not-assume-refhtml-dropped",
        "- 参照 HTML (reference-guide-v2.html など) の本文・見出し・例文を流用しない。",
        "- 文体は参照資料に合わせる。",
        "AC-C05-9",
    ),
    (
        "parent-context-leaked",
        "## Purpose\n",
        "## Purpose\n\n題材は plugin-plans/guide-doc-generator の開発計画である。\n",
        "AC-C05-10",
    ),
    (
        "goal-replaced-by-lead-line",
        "- lead_line と goal は別フィールドであり、一方が他方を代替しない (C40)。",
        "- goal は lead_line で兼用してよい。",
        "AC-C05-11",
    ),
    (
        "date-selffilled",
        "- date が入力に無ければ日付フィールドを出力しない。既定充填は C12 の --normalize に委ねる。",
        "- date が入力に無ければ生成実行日を日付フィールドへ入れる。",
        "AC-C05-12",
    ),
    (
        "presentation-order-derivation-duplicated",
        "- presentation_order は自分で導出しない。null なら構成データにも書かず、規則 CR-PRESENTATION-ORDER",
        "- presentation_order は basic までなら demo_first、それ以外は explain_first として自分で決める。規則 CR-PRESENTATION-ORDER",
        "AC-C05-13",
    ),
    (
        "logistics-not-isolated",
        "- どれにも紐づかない伝達事項は logistics セクションとして appendix へ隔離する。",
        "- どれにも紐づかない伝達事項は本編の適当な位置へ入れる。",
        "AC-C05-14",
    ),
    (
        "flow-overview-detail-allowed",
        "- 冒頭に flow-overview を 1 件置く。個々の手順の詳細は書かない。件数上限は",
        "- 冒頭に flow-overview を 1 件置き、当日の手順を余さず並べる。件数上限は",
        "AC-C05-15",
    ),
    (
        "capability-slot-order-dropped",
        "  順に与える。lead_line を機能名から始めない。",
        "  順に与える。",
        "AC-C05-16",
    ),
    (
        "dialogue-and-handson-dropped",
        "- dialogue 枠と handson (config/handout-parts.json で data_block_type=handson を持つ部品) と anticipated-qa を preset の required に従って置き、\n  各セクションへ duration を書く。",
        "- 時間が余りそうなら質疑の時間を取る。",
        "AC-C05-17",
    ),
    (
        "remember-pair-not-blocking",
        "must_remember と no_need_to_remember は対であり、片方だけが\n埋まっている入力も blocked とする。",
        "must_remember と no_need_to_remember は対で扱う。",
        "AC-C05-18",
    ),
    (
        "hearing-field-dropped",
        " / attainment_level",
        "",
        "AC-C05-19",
    ),
    (
        "return-key-dropped",
        "- decision_log / open_questions / blocked_reason",
        "- decision_log / open_questions",
        "AC-C05-20",
    ),
    (
        "self-approval-allowed",
        "- validate-handout-config.py と route-handout-output.py は親が実行する。この agent は\n  Bash を持たないため script を起動しない。自分の出力を自分で合格判定しない。",
        "- 書き終えたら自分で検証スクリプトを走らせて合否を確かめる。",
        "AC-C05-21",
    ),
    (
        "part-ids-enumerated-in-prose",
        "- attainment_level を超える内容のセクションを作らない。",
        "- attainment_level を超える内容のセクションを作らない。\n- 使ってよい部品は B01 / B02 / B03 / B04 / B05 とする。",
        "AC-C05-22",
    ),
    (
        "downstream-boundary-dropped",
        "- 図解はパターン名と構造データの宣言までで、SVG の座標計算は C14 が行う。",
        "- 図解は座標まで決めて書き出す。",
        "AC-C05-23",
    ),
    (
        "emoji-introduced",
        "## Self-Evaluation",
        "## Self-Evaluation\n\n\U0001F600 点検の観点",
        "AC-C05-24",
    ),
    (
        "glossary-body-pairing-dropped",
        "- glossary で宣言した用語は本文フィールドの初出で括弧書き併記する。",
        "- glossary へ用語を並べる。",
        "AC-C05-25",
    ),
    (
        "preset-composition-allowed",
        "3. preset を読み、セクション順序と推奨部品を採用する。プリセットを合成しない。",
        "3. preset を読み、混成用途なら 2 つのプリセットを足し合わせる。",
        "AC-C05-26",
    ),
]
