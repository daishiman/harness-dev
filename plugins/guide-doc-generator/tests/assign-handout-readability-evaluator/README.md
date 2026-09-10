# assign-handout-readability-evaluator (C03) 受入テスト

P04-C03-01 で**実装前に赤で固定した**受入判定。実装 (P05) はこのテストを緑にする形でのみ
完了とし、判定基準そのものを書き換えて緑にすることはできない。

- 対象 build_target: `plugins/guide-doc-generator/skills/assign-handout-readability-evaluator/`
- 実行: repo ルートから
  `python3 -m unittest discover -s plugins/guide-doc-generator/tests/assign-handout-readability-evaluator -p 'test_*.py'`
- 依存: Python 3.10+ 標準ライブラリのみ (pytest / PyYAML は使わない)

## ファイル構成

| ファイル | 役割 |
| --- | --- |
| `contract_lib.py` | SKILL.md の宣言的契約チェッカ (`check_skill` が `Violation` の一覧を返す)。frontmatter は本 plugin が使う YAML 部分集合だけを解釈する簡易パーサで読む |
| `test_assign_handout_readability_review_skill.py` | **赤で固定する本体**。build_target に対し契約 id ごとに 1 メソッド |
| `test_contract_checker.py` | チェッカ自身の検査。受入例が通り、非受入例が対応 id で落ちることを固定する (実装前でも緑が正しい) |
| `reject_cases.py` | 非受入例の定義。受入例へ 1 箇所だけ違反を注入する固定入力 |
| `fixtures/accept/` | 受入例。`skills/assign-handout-readability-evaluator/SKILL.md` と、参照先の実在検査に要る `agents/handout-readability-reviewer.md` / `scripts/verify-handout-language.py` のスタブ |

`fixtures/accept/` の SKILL.md は**契約を満たす最小例**であって、実装の下書きではない。
実装が同じ文面である必要はなく、契約 id を満たす限り自由に書いてよい。

## なぜ SKILL.md の宣言を見るのか

C03 は skill component であり、「実際にレビューが良かったか」をテストで測れない。
測れるのは **委譲の契約** — 誰へ、何を渡し、何を受け取り、何を自分でしないか — であり、
これは SKILL.md の宣言に現れる。C03 の価値は判定の質ではなく
「判定を自分でしないこと」に置かれている (skill-brief-C03 `purpose_background`) ため、
契約検査で捕まえられる範囲と C03 の責務範囲がほぼ一致する。

## 契約 id と出典の対応表

| 契約 id | 何を固定するか | 出典 |
| --- | --- | --- |
| AC-C03-1 | build_target に SKILL.md が実在する | task-spec P04-C03-01 `acceptance_criterion` |
| AC-C03-2 | `name` / `prefix: assign` / `kind: assign` / `hierarchy: L2` / `user-invocable: false` | skill-brief-C03 `skill_name` `prefix` `kind` `hierarchy_level` / repo の assign 系 convention |
| AC-C03-3 | description が trigger (読みやすさ・レビュー・資料/handout) から発見でき「〜使う」で終わる | skill-brief-C03 `trigger_conditions` / lint-skill-description |
| AC-C03-4 | `context: fork` で `handout-readability-reviewer` (C06) へ委譲し、agent 実体が存在する | skill-brief-C03 `needs_independent_context: true` / inventory #C06 `name` `build_target` / agent-brief-C06 `isolation_rationale` |
| AC-C03-5 | responsibilities は `R1-assign` 1 件ちょうど・`prompt_required: true` | skill-brief-C03 `responsibilities` |
| AC-C03-6 | `prompts/R1-review-readability.md` が宣言され実在する | agent-brief-C06 `prompt_ref` |
| AC-C03-7 | `depends_on` は C04 / C18 と完全一致 | component-inventory #C03 `depends_on` (P03 Y-09: 依存グラフの正本は inventory) |
| AC-C03-8 | `verify-handout-language.py` が `script_refs` にあり実体が存在する | skill-brief-C03 `deterministic_checks` |
| AC-C03-9 | `## Purpose & Output Contract` / `## Key Rules` / `## Gotchas` / `## Additional Resources` | repo の assign 系 SKILL.md 7 本中 6 本が共有する骨格 |
| AC-C03-10 | 書き込み系ツール (Write/Edit/MultiEdit/NotebookEdit) 非付与・Read と委譲手段の付与・「資料を書き換えない / 修正は C01」の明記 | skill-brief-C03 `boundary` / agent-brief-C06 `boundary` |
| AC-C03-11 | 判定基準を持たない・verdict を再判定しない。`high` と `FAIL` を同時に含む行は C06 へ帰属させる | agent-brief-C06 `boundary` (「C03 は判定基準を持たず」) / `output_contract` |
| AC-C03-12 | 委譲入力 `html_path` / `config_path` / `gate_reports` / `reader_profile` を出力契約節で宣言し、`scope` は任意と明記 | agent-brief-C06 `input_contract.receives` |
| AC-C03-13 | C16/C17/C18/C22 の全 exit0 が委譲の前提。FAIL 残存時は `status=blocked` を意味レビューへ進まず差し戻す | agent-brief-C06 `input_contract.receives.gate_reports` / `procedure[0]` / AC7 / `failure_modes` (blocked の握りつぶし) |
| AC-C03-14 | verdict 7 項目 (`status` `verdict` `reviewed_as` `findings` `strengths` `not_reviewed` `blocked_reason`) と findings 6 項目 (`severity` `axis` `location` `why_not_understood` `suggestion` `machine_gate_overlap`)・`PASS`/`FAIL` を出力契約節で欠落なく宣言 | agent-brief-C06 `output_contract.returns` / skill-brief-C03 `output_contract` |
| AC-C03-15 | 設計意図・ヒアリング生ログ・参照 HTML・loop 回数・過去 findings を委譲入力へ渡さない | agent-brief-C06 `input_contract.must_not_assume` / `isolation_rationale` |
| AC-C03-16 | `combinators` 空・`goal_seek` 無し・`feedback_contract.skip_reason` が inventory と一致・本文に `max_loops` を持たない | component-inventory #C03 `feedback_contract.skip_reason` / `combinators: []` / agent-brief-C06 `boundary` (loop 制御を持たない) |
| AC-C03-17 | `rubric_refs` に `ref-handout-design-system` | skill-brief-C03 `rubric_refs` |
| AC-C03-18 | `output_language: ja` | skill-brief-C03 `output_language` |
| AC-C03-19 | `source` が `component-inventory.json#C03` を指す | 本 plugin の他 leaf と同じ追跡規約 |
| AC-C03-20 | proposer≠approver (生成した本人が採点しない) と独立 context の明記 | skill-brief-C03 `purpose_background` / agent-brief-C06 `isolation_rationale` (inventory #C06 `evaluator_pair: C01`) |

`test_contract_checker.py::test_reject_cases_cover_every_contract_id` が
AC-C03-2〜20 の全 19 契約に非受入例があることを強制する。AC-C03-1 だけは
`test_missing_skill_md_is_rejected` (空ディレクトリ) が受け持つ。

## 赤の記録 (実装前)

```
Ran 34 tests
FAILED (failures=24)
```

- 赤 24 件はすべて `test_assign_handout_readability_review_skill.py` (build_target 未実装)。
  **errors は 0 件**であり、import 例外ではなく assert が評価された上で落ちている。
- 緑 10 件は `test_contract_checker.py` (チェッカの判定力)。実装の有無に依存しないので
  実装前から緑が正しい。

## 検査していないこと (P05 / P06 の担当)

- レビュー結果の質そのもの (「初心者に伝わる」の判定が妥当か)。C06 の AC6/AC7 として
  P06 の実行受入で見る。
- P0 lint (`lint-skill-name` / `validate-frontmatter` 等) の exit code。
  inventory #C03 `quality_gates.p0_lint` が持ち、本テストは重複実装しない。
- C06 agent 本体 (`plugins/guide-doc-generator/agents/handout-readability-reviewer.md`) の
  中身。ここでは委譲先として**実在するか**だけを見る (C06 の契約は C06 の leaf が固定する)。

## gaps (ブリーフに書かれておらず、テスト側で確定させた判断)

| what | why |
| --- | --- |
| 委譲先を指す frontmatter キーを `agent:` / `context: fork` / `agent_refs:` に確定した | skill-brief-C03 は `needs_independent_context: true` と `placement_candidates: [Skill]` しか持たず、キー名を定めていない。repo の assign 系 (`assign-skill-design-evaluator` の `agent:` / `assign-plugin-plan-evaluator` の `context: fork`) に合わせた。P05 が別のキー名を採るなら、本テストと合わせて 1 回だけ変更してよい (契約の意味 = 独立 context の named agent への委譲 は変えないこと) |
| 責務 prompt のファイル名を `prompts/R1-review-readability.md` に固定した | 当初は `R-review-readability.md` (責務番号なし) だったが `lint-prompt-placement.py` の skill-local-v1 regex (`R<数字>[a-z]?-<slug>`) に適合しないため `R1-` を付けて確定した。責務 id は `R1-assign` のまま、本文アンカーも `<!-- responsibility: R1 -->` のままで、`lint-agent-prompt-section.py` の ANCHOR_RE (`R<数字>`) と両立する。名前を変えるなら C05/C06 と揃えて 1 回だけ変更すること |
| `user-invocable: false` を契約に含めた | ブリーフに記載が無い。assign は上位 skill から呼ばれる評価委譲であり、repo の assign 系 6/7 が `user-invocable: false` を持つことから採った |
| 必須セクションを repo の assign 系 4 見出しに固定した | skill-brief-C03 は `body_sections` を持たない (C06 の agent-brief だけが持つ)。run 系の骨格 (`## ゴールシーク実行` 等) は C03 がループを持たない以上そぐわないため、assign 系の共通骨格を採った |
| verdict 回収時の「項目欠落」を、埋めずに欠落のまま報告する扱いにした | C06 の出力契約は 7 項目を必須としているが、欠落時に C03 が何をするかはどのブリーフにも無い。C03 が補完すると判定を持たない前提が崩れるため、報告に倒した。P05 で別の扱い (再委譲など) を採るならブリーフ側の追記が要る |
| `gate_reports` の json-report 出力先を誰が用意するかは検査していない | agent-brief-C06 `open_questions` で未確定 (C03 が渡す案 / C06 が `$TMPDIR` を使う案)。確定前に片方をテストで固定すると P05 の選択を潰すため、パスの owner は契約に入れていない |
| verdict=FAIL 時の再レビュー上限を C03 が持たないことだけを固定した | agent-brief-C06 `open_questions` は「C03 が verdict を返すだけで打ち切り判断をしない点は C01 の feedback_contract と突合が要る」と残している。C01 側 (max_loops 5) との突合は P06 の統合受入の担当 |
