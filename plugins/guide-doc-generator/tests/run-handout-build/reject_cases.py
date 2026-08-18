"""非受入例 (reject fixture) の定義。

受入例 `fixtures/accept/skills/run-handout-build/SKILL.md` に対して 1 箇所だけ
契約違反を注入した固定入力を作る。各ケースは「どの契約 id が落ちるべきか」を
明示的に持ち、チェッカが常時 PASS する空ゲートになっていないことを固定する。
"""

# (case_name, 置換前, 置換後, 落ちるべき契約 id)
REJECT_CASES = [
    (
        "target-tasks-min-count-zero",
        '      min_count: 1\n      checked_by: "C12 E-TARGET-TASKS-EMPTY',
        '      min_count: 0\n      checked_by: "C12 E-TARGET-TASKS-EMPTY',
        "AC-C01-12",
    ),
    (
        "target-tasks-item-dropped",
        """    - field: target_tasks
      question_ja: "この資料を読んだ人が、自分の仕事で具体的に何をできるようになりたいですか (例 車両収支の集計を自動化する)"
      required: true
      min_count: 1
      checked_by: "C12 E-TARGET-TASKS-EMPTY / E-SECTION-UNTIED-TASK"
""",
        "",
        "AC-C01-11",
    ),
    (
        "must-remember-max-relaxed",
        "      max_count: 2\n      paired_with: no_need_to_remember",
        "      max_count: 5\n      paired_with: no_need_to_remember",
        "AC-C01-13",
    ),
    (
        "remember-pair-broken",
        "      paired_with: must_remember\n",
        "",
        "AC-C01-13",
    ),
    (
        "presentation-order-asked",
        "    - field: must_remember",
        """    - field: presentation_order
      question_ja: "デモから始めるのと先に説明するのでは、どちらがよいですか"
      required: true
      checked_by: "C12 CR-PRESENTATION-ORDER"
    - field: must_remember""",
        "AC-C01-14",
    ),
    (
        "gate-aggregation-reimplemented",
        "4 ゲート (C16 / C17 / C18 / C22) は `/handout-verify` (C09) 経由で実行し、その集約結果を受け取るだけにする。4 状態分類と全体 verdict の判定規則は C09 の CR-GATE-AGG が単一正本であり、本 skill では再実装も再解釈もしない。",
        "4 ゲート (C16 / C17 / C18 / C22) を順に起動し、本 skill が結果を pass / fail / error / not-run の 4 状態へ分類して全体 verdict を決める。",
        "AC-C01-15",
    ),
    (
        "not-run-folded-into-pass",
        "本 skill では再実装も再解釈もしない。",
        "本 skill では再実装も再解釈もしない。ただしゲートが動かなかった場合は not-run を pass とみなして先へ進む。",
        "AC-C01-15",
    ),
    (
        "config-placed-by-self",
        "`route-handout-output.py` (C19) へ `--place-config` と `--assets-src` を渡し、handout-config.json と assets/ の複製は C19 に行わせる。",
        "handout-config.json と assets/ の原本は本 skill が出力ディレクトリ直下へ複製して配置する。",
        "AC-C01-16",
    ),
    (
        "criteria-acceptance-section-missing",
        "## Criteria acceptance",
        "## 受入基準まとめ",
        "AC-C01-8",
    ),
    (
        "goal-seek-max-loops-changed",
        "  max_loops: 5",
        "  max_loops: 3",
        "AC-C01-6",
    ),
    (
        "script-ref-missing",
        "  - ../../scripts/verify-handout-narrative.py\n",
        "",
        "AC-C01-10",
    ),
    (
        "c03-dependency-dropped",
        "depends_on: [C03, C04,",
        "depends_on: [C04,",
        "AC-C01-18",
    ),
    (
        "out2-verify-by-weakened",
        "バイト一致することを受入テストが確認する\"\n      verify_by: test",
        "バイト一致することを受入テストが確認する\"\n      verify_by: live-trial",
        "AC-C01-7",
    ),
    (
        "extra-responsibility-added",
        "  - id: R4-verify\n    prompt_required: true",
        "  - id: R5-selfreview\n    prompt_required: true\n    summary: \"自分で読みやすさを採点する\"\n  - id: R4-verify\n    prompt_required: true",
        "AC-C01-4",
    ),
    (
        "html-written-by-llm",
        "HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。",
        "HTML は本 skill が直接書き起こす。",
        "AC-C01-20",
    ),
    (
        # writer 宣言を消しても同梱物一覧の言及が残る形。body 全体一致では落ちない。
        "readme-writer-handed-to-c19",
        "C19 が返した出力ディレクトリ直下へ `README.md` を書くのは本 skill の責務で、内容は原題・目的・適用プリセット・同梱物一覧・各同梱物の使い方の 5 節とする。",
        "README.md の作成も C19 に任せる。",
        "AC-C01-17",
    ),
    (
        # 5 節のうち 1 節だけを落とす。語自体は他節の見出しに残る。
        "readme-section-mokuteki-dropped",
        "内容は原題・目的・適用プリセット",
        "内容は原題・適用プリセット",
        "AC-C01-17",
    ),
    (
        # 決定論委譲の宣言だけを消す。語は完了チェックリストに残る。
        "deterministic-delegation-dropped",
        "HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。",
        "HTML の組み立て自体は既存テンプレートの流用で行い LLM で書かない。",
        "AC-C01-20",
    ),
    (
        "non-interactive-path-blocked",
        "検証済みの構成データを直接渡された場合はヒアリングを省き、非対話経路として R2 以降へ進む。",
        "常に対話でヒアリングを行ってから R2 へ進む。",
        "AC-C01-19",
    ),
]
