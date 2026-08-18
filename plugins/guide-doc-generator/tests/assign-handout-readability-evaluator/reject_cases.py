"""非受入例 (reject fixture) の定義。

受入例 `fixtures/accept/skills/assign-handout-readability-evaluator/SKILL.md` に対して
1 箇所だけ契約違反を注入した固定入力を作る。各ケースは「どの契約 id が落ちるべきか」を
明示的に持ち、チェッカが常時 PASS する空ゲートになっていないことを固定する。

C03 は委譲 skill なので、非受入例の重心は次の 3 つに置いてある。
  1. 委譲の配線が切れる (独立 context でなくなる / 委譲先 agent が別物になる)
  2. 委譲の入出力契約から項目が欠落する (入力 5 種・verdict 7 項目・findings 6 項目)
  3. C03 が自分で判定してしまう (判定基準の保持・verdict の再判定・ループ制御の吸収)
"""

# (case_name, 置換前, 置換後, 落ちるべき契約 id)
REJECT_CASES = [
    # --- identity ---------------------------------------------------------
    (
        "hierarchy-downgraded",
        "hierarchy: L2",
        "hierarchy: L1",
        "AC-C03-2",
    ),
    (
        "user-invocable-opened",
        "user-invocable: false",
        "user-invocable: true",
        "AC-C03-2",
    ),
    (
        "description-loses-trigger-vocabulary",
        "読みやすさレビューを依頼したいとき",
        "内容確認を依頼したいとき",
        "AC-C03-3",
    ),
    # --- 委譲の配線 --------------------------------------------------------
    (
        "context-not-forked",
        "context: fork",
        "context: inline",
        "AC-C03-4",
    ),
    (
        "delegated-to-generic-agent",
        "agent: handout-readability-reviewer\n",
        "agent: general-purpose\n",
        "AC-C03-4",
    ),
    (
        "agent-ref-dropped",
        "agent_refs:\n  - ../../agents/handout-readability-reviewer.md\n",
        "",
        "AC-C03-4",
    ),
    # --- 責務 -------------------------------------------------------------
    (
        "extra-responsibility-added",
        "  - id: R1-assign\n    prompt_required: true\n",
        "  - id: R1-assign\n    prompt_required: true\n"
        "  - id: R2-judge\n    prompt_required: true\n"
        "    summary: \"回収した findings を自分で採点し直して最終 verdict を決める\"\n",
        "AC-C03-5",
    ),
    (
        "responsibility-prompt-unreferenced",
        "responsibility_refs:\n  - prompts/R-review-readability.md\n",
        "",
        "AC-C03-6",
    ),
    (
        "depends-on-c18-dropped",
        "depends_on: [C04, C18]",
        "depends_on: [C04]",
        "AC-C03-7",
    ),
    (
        "deterministic-check-script-unreferenced",
        "script_refs:\n  - ../../scripts/verify-handout-language.py\n",
        "",
        "AC-C03-8",
    ),
    (
        "required-section-renamed",
        "## Key Rules",
        "## ルール",
        "AC-C03-9",
    ),
    # --- read-only 境界 ----------------------------------------------------
    (
        "write-tool-granted",
        "allowed-tools: [Read, Bash(python3 *), Task]",
        "allowed-tools: [Read, Write, Bash(python3 *), Task]",
        "AC-C03-10",
    ),
    (
        "delegation-tool-removed",
        "allowed-tools: [Read, Bash(python3 *), Task]",
        "allowed-tools: [Read, Bash(python3 *)]",
        "AC-C03-10",
    ),
    (
        "rewrite-boundary-erased",
        "資料を書き換えないことがこの skill の境界である。修正は C01 run-handout-build の責務。",
        "必要なら該当箇所を直してから返す。",
        "AC-C03-10",
    ),
    # --- 判定基準を持たない -------------------------------------------------
    (
        "own-judgement-criteria-introduced",
        "本 skill は判定基準を持たない。",
        "本 skill は初心者向けかどうかの判定基準を持つ。",
        "AC-C03-11",
    ),
    (
        "verdict-recomputed-by-self",
        "は handout-readability-reviewer\n  (C06) 側の規則であり、本 skill は再判定しない。回収した verdict を書き換えない。",
        "を本 skill が適用して最終 verdict を決める。",
        "AC-C03-11",
    ),
    # --- 委譲入力の欠落 ----------------------------------------------------
    (
        "reader-profile-input-dropped",
        "| `reader_profile` | 構成データの reader / prior_knowledge_level / usage_scene |\n",
        "",
        "AC-C03-12",
    ),
    (
        "gate-reports-input-dropped",
        "| `gate_reports` | 決定論ゲート (C16 / C17 / C18 / C22) の json-report のパス一覧と各 exit code |\n",
        "",
        "AC-C03-12",
    ),
    (
        "scope-made-mandatory",
        "| `scope` | 任意。特定セクションのみをレビューさせる場合の section id 一覧 (省略時は全体) |",
        "| `scope` | 特定セクションのみをレビューさせる section id 一覧 |",
        "AC-C03-12",
    ),
    # --- ゲート前提 --------------------------------------------------------
    (
        "gate-exit0-precondition-softened",
        "が全て exit0 であることが委譲の前提である",
        "が概ね通っていることが望ましい",
        "AC-C03-13",
    ),
    (
        "blocked-swallowed",
        "残る状態では意味レビューへ進まない。この場合 C06 は `status=blocked` を返すので、\n  そのまま呼び出し元へ差し戻す。",
        "残る状態でも意味レビューを依頼してよい。`status=blocked` が返ったら PASS とみなす。",
        "AC-C03-13",
    ),
    # --- 出力契約の項目欠落 -------------------------------------------------
    (
        "strengths-dropped-from-verdict",
        "`status` / `verdict` (PASS または FAIL) / `reviewed_as` / `findings` / `strengths` /\n`not_reviewed` / `blocked_reason` の 7 項目。",
        "`status` / `verdict` (PASS または FAIL) / `reviewed_as` / `findings` /\n`not_reviewed` / `blocked_reason` の 6 項目。",
        "AC-C03-14",
    ),
    (
        "finding-evidence-fields-dropped",
        "`axis` / `location` (section_id と逐語引用) / `why_not_understood` / `suggestion` /\n`machine_gate_overlap` を持つ。",
        "`axis` を持つ。",
        "AC-C03-14",
    ),
    # --- 独立 context の保全 ------------------------------------------------
    (
        "parent-context-leaked-into-delegation",
        "委譲入力に含めず渡さない: 構成データの設計意図、ヒアリングの生ログ、参照 HTML v1/v2 の\n  文面、これが何周目の loop かという情報、過去に C06 が出した findings。",
        "委譲入力へ補足として同梱する: 構成データを設計したときの狙いと、直前に直した箇所。",
        "AC-C03-15",
    ),
    # --- ループ制御を持たない -----------------------------------------------
    (
        "loop-control-absorbed",
        "本 skill は 1 回の委譲と 1 回の\n  回収で終わる。",
        "本 skill が max_loops 3 まで再レビューを回す。",
        "AC-C03-16",
    ),
    (
        "feedback-contract-skip-reason-rewritten",
        '  skip_reason: "assign kind は評価委譲のみで自身は反復ループを持たない (evaluator verdict でカバーする)"',
        '  skip_reason: "評価が不要なため"',
        "AC-C03-16",
    ),
    # --- メタ -------------------------------------------------------------
    (
        "rubric-ref-dropped",
        "rubric_refs:\n  - ref-handout-design-system\n",
        "",
        "AC-C03-17",
    ),
    (
        "output-language-changed",
        "output_language: ja",
        "output_language: en",
        "AC-C03-18",
    ),
    (
        "source-traceability-lost",
        "source: plugin-plans/guide-doc-generator/component-inventory.json#C03",
        "source: internal",
        "AC-C03-19",
    ),
    (
        "proposer-approver-rationale-erased",
        "生成した本人が自作を採点する\n構図 (proposer≠approver の崩れ) を避けるために委譲する。",
        "レビューの質を上げるために委譲する。",
        "AC-C03-20",
    ),
]
