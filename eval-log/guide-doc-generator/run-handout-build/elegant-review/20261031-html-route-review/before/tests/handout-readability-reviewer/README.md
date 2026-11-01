# C06 `handout-readability-reviewer` 受入テスト (P04-C06-01)

実装 (`plugins/guide-doc-generator/agents/handout-readability-reviewer.md`) より先に
判定基準を確定させ、赤で固定したテスト群。**P05 の実装側がここを自分に都合よく
書き換えて緑にすることは許されない**。契約を変えるときは先にブリーフを直す。

契約の正本は 1 つだけである。

| 何の契約か | 正本 |
| --- | --- |
| frontmatter / 入出力 / 責務境界 / 手順 / 失敗モード / 受入検査 | `plugin-plans/guide-doc-generator/briefs/agent-brief-C06.json` |

C06 は script ではなく **sub-agent の定義 Markdown** なので、検査対象は実行結果ではなく
**宣言的契約** (frontmatter・必須セクション・責務境界の明記・返す findings スキーマの宣言) である。
「渡した資料に対して実際にどんな findings が返るか」(ブリーフ AC6) は LLM 実行を伴うため
P06 の受入であり、ここでは扱わない。ここが固定するのは「その実行が正しく行われうる形に
定義が書かれているか」までである。

期待値のうち機械可読なもの (frontmatter フィールド一覧・`body_sections`・`tools`・
`axis` / `severity` 語彙・`description`・`build_target`) は**ブリーフから実行時に読み出して**おり、
テスト側へ複製していない。ブリーフが変われば期待値も追随する。
規則の複製を持たないのは C10 のテストと同じ方針である。

## 実行

repo ルートから:

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/handout-readability-reviewer -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。現状は **164 tests / 161 failures / 0 errors (赤)**。
161 件はすべて「未実装: `plugins/guide-doc-generator/agents/handout-readability-reviewer.md`
が存在しない」で落ちる。緑の 3 件は `TestTestDirectoryHygiene` (実装の有無に依存しない
write_scope の自己検査) である。

**errors ではなく failures で落ちる形にしてある。** 実装の有無は module import 時でも
`setUpClass` でもなく、基底クラス `AgentContractTestCase.setUp` の `require_agent()` で見ている。
`setUpClass` で例外を投げると unittest は error として記録し、「赤で固定した」ことにならない。

### 過剰拘束でないことの確認

契約を満たす agent 定義の下書きを作って同じ suite を通し、**164 中 161 が緑**に
なることを確認済み (残る 3 件は下書きを `agents/` 配下に置かなかったためのパス検査)。
つまりこの赤は「実装すれば緑にできる赤」であり、満たしようのない要求は入っていない。

## ファイル構成

| ファイル | 件数 | 役割 |
| --- | ---: | --- |
| `hb_c06.py` | — | 共通ハーネス (テストではない)。ブリーフ読み出し・frontmatter/セクション解析・lint 実行・断言ヘルパ |
| `test_frontmatter.py` | 27 | AC1 frontmatter と tool 付与 |
| `test_lint_gates.py` | 7 | AC1 / AC2 p0_lint 3 本の exit0 |
| `test_body_sections.py` | 5 | `body_sections` の存在と順序 |
| `test_purpose.py` | 8 | `question_solved` の落とし込みと追跡可能性 |
| `test_input_contract.py` | 13 | `input_contract.receives` / `reads_files` / 起動前提 |
| `test_context_isolation.py` | 13 | **親会話の前提を持ち込んだ場合に落ちる検査** (`must_not_assume`) |
| `test_output_contract.py` | 31 | **AC5 返却物の形式検査** (findings スキーマ・verdict 規則) |
| `test_boundary_exclusions.py` | 25 | AC3 機械ゲートとの責務境界 |
| `test_readonly_and_bash_scope.py` | 8 | AC4 read-only と Bash 用途の限定 |
| `test_blocked_path.py` | 5 | AC7 ゲート FAIL 時の差し戻し |
| `test_procedure_coverage.py` | 6 | `procedure` 14 手順の被覆と順序 |
| `test_failure_modes.py` | 8 | `failure_modes` 7 件に対応する防止策の存在 |
| `test_no_side_effects.py` | 8 | `build_target` の置き場所と write_scope の自己検査 |

task-spec `P04-C06-01.md` の `acceptance_criterion` が名指しした 2 本は
`test_output_contract.py` (返却物の形式検査) と `test_context_isolation.py`
(親会話の前提を持ち込んだ場合に落ちる検査) である。

## 契約 id とテストの対応

### acceptance_checks

| id | 固定した内容 | テスト |
| --- | --- | --- |
| AC1 | name / description (ブリーフ一致) / `tools: Read, Bash` で Write 非付与 / `isolation: fork` / `kind: agent` / `owner_skill` / `prompt_ref` / 宣言済み 13 フィールドの存在と非空 | `test_frontmatter.py::TestFrontmatterPresence` `::TestFrontmatterValues` `::TestToolGrant` |
| AC1 (lint) | `validate-frontmatter` exit0 / `lint-skill-description` の R1-R5 違反 0 | `test_lint_gates.py::TestP0Lint` |
| AC2 | `lint-agent-prompt-section` exit0。加えて lint と独立に `## Prompt Templates` / `## Self-Evaluation` の存在と、Self-Evaluation が 完全性/一貫性/深度/検証可能性/簡潔性 のいずれかに言及すること | `test_lint_gates.py::TestPromptSectionShape` |
| AC3 | C16/C17/C18/C22 が除外リストとして列挙され、絵文字・aria・印刷版面・日付書式・存在検査・字数・外部参照・glossary 宣言被覆が「見ない」側に明記。かつ 6 軸それぞれで意味側との 1 対 1 対比 (「〜ではなく〜か」) が書かれている | `test_boundary_exclusions.py::TestExcludedGatesAreNamed` `::TestExcludedSurfaces` `::TestSemanticCounterparts` |
| AC4 | Write 非付与 + 本文で「資料も構成データも書き換えない」「Bash 経由の書き込みも禁止」。Bash 用途は verify 系 4 script の読み取り実行に限定され、書き込みは `--json-report` の一時パスのみ | `test_readonly_and_bash_scope.py` |
| AC5 | トップレベル 7 キーと finding の 9 フィールド (`location` は `section_id` / `element` / `quote`)、axis 6 語・severity 3 語とその定義、verdict 規則 (high 1 件で FAIL / それ以外 PASS)、`machine_gate_overlap=true` 禁止、戻り値で返しファイルを書かない | `test_output_contract.py` |
| AC6 | 実行を伴う面は P06。ここでは「成果物を 1 バイトも変更しない」「findings をファイルで受け渡さない」の宣言と、`build_target` の置き場所だけを固定 | `test_no_side_effects.py` |
| AC7 | ゲート FAIL で `status=blocked` + `blocked_reason`、意味レビューへ進まない、理由 (形式問題に埋もれる) の明示、Bash による再確認 | `test_blocked_path.py` |

### input_contract

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| `receives` | `html_path` / `config_path` / `gate_reports` / `reader_profile` / `scope` が `## Inputs` に宣言され、`scope` は任意で省略時は全体。`reader_profile` は reader / prior_knowledge_level / usage_scene を含む | `TestReceives` |
| 起動前提 | C16/C17/C18/C22 の 4 本が名指しされ、全て exit0 が前提と書かれている | `TestGatePrecondition` |
| `reads_files` | 生成 HTML・正規化済み構成データ・json-report・`references/` (ref-handout-design-system) | `TestReadsFiles` |
| `must_not_assume` (1) | 設計意図・「こういう狙い」を持ち込まない / 判定根拠は書かれている文字 (逐語引用) だけ | `TestMustNotAssume::test_1_*` |
| (2) | ヒアリング生ログを持ち込まない / `reader_profile` を超える前提知識を読者に仮定しない | `::test_2_*` |
| (3) | 参照 HTML v1/v2 の文面を根拠にしない / 規範は文章設計の型であって文面ではない | `::test_3_*` |
| (4) | 何周目か・締切・残り loop 数を持ち込まない | `::test_4_*` |
| (5) | 過去の findings を持ち込まない / 毎回通読する | `::test_5_*` |

### boundary (責務境界)

| 分界 | 固定した内容 | テスト |
| --- | --- | --- |
| 対 C1x 機械ゲート | 除外リストの列挙 + 意味側との 1 対 1 対比 | `TestExcludedSurfaces` / `TestSemanticCounterparts` |
| 対 C03 | C03 が運搬と verdict 回収、C06 は loop 制御と受け渡しを持たない | `TestComponentBoundaries` |
| 対 C01 | 修正は C01 の責務、`suggestion` は提案であって適用指示ではない | `TestComponentBoundaries` |
| 重複の自己除去 | `machine_gate_overlap=true` 禁止・除外リストとの突合・除去分は `not_reviewed` へ | `TestOverlapSelfCheck` |

### procedure / failure_modes

| 契約 | 固定した内容 | テスト |
| --- | --- | --- |
| `procedure` 14 手順 | 各手順を代表語 1 つで被覆。件数がブリーフとずれたら落ちる | `test_procedure_coverage.py::TestProcedureSteps` |
| 手順の順序 | ゲート確認 → 意味レビュー、読者確定 → 判定、severity 付与 → 除外突合 の 3 つの前後関係だけを固定 | `::TestProcedureOrder` |
| `failure_modes` 7 件 | 各モードに対応する防止策が本文にあること。件数がブリーフとずれたら落ちる | `test_failure_modes.py` |

## gaps (P05 で確定が要るもの・このテストで断定を避けた点)

1. **`description` の末尾句点** — ブリーフの `description` は句点で終わらないが、
   `lint-skill-description.py` の R5 は末尾が「使う。」であることを要求する。
   AC1 は両方 (ブリーフ一致 + lint exit0) を求めており、そのままでは両立しない。
   テストは**末尾句点の有無だけを吸収して**突合し、lint 違反 0 を別テストで見ている。
   ブリーフ側 (と `component-inventory.json`) の description に句点を足すのが本筋。

2. **責務アンカーの形** — ブリーフ `open_questions[0]` のとおり、
   `lint-agent-prompt-section.py` の `ANCHOR_RE` は `R<数字>` しか受けないのに
   inventory の `responsibility_anchor` は `prompts/R1-review-readability.md` である。
   どちらに寄せるかが未確定なので、テストは**アンカーが 1 個存在すること**だけを固定し、
   形は `lint-agent-prompt-section` の exit0 に委ねている。C05 と揃えて P05 で決めること。

3. **`prompt_ref` の基準ディレクトリ** — ブリーフ本文は
   `plugins/guide-doc-generator/skills/.../R1-review-readability.md`、
   先例 (`ui-quality-reviewer.md`) は `skills/...` の plugin 相対である。
   テストは「`prompts/R1-review-readability.md` で終わる」かつ
   「`skills/assign-handout-readability-evaluator/` を含む」までしか見ていない。

4. **`model` の値** — `sonnet` 固定か `inherit` かが未確定 (`open_questions[3]`)。
   テストは**宣言の有無**だけを固定し、値を断定していない。

5. **`--json-report` の出力先を誰が用意するか** — `open_questions[4]` のとおり未確定。
   テストは「書き込みは `--json-report` の一時パスのみ」という制約の明記までを見ており、
   一時ディレクトリの provider (C03 か C06 の `$TMPDIR` か) を固定していない。

6. **R21 (C46-C59) が C06 のブリーフへ反映されていない** — task 指示にあった
   「説明が機能名から始まっていないか」「覚える対象が絞られているか」は
   `RESOLUTION-R21.md` では C51 (owner=C12、副検査 C18 `LANG-07`) と
   C57 (owner=C12) に割り当たっており、**C06 の責務ではない**。
   agent-brief-C06.json の `requirements_covered` も R11/R19/R20 のままで R21 を含まない。
   したがってこの 2 観点をテストに入れていない。C06 に「機能名始まりが読者に伝わるか」
   などの意味面を持たせるなら、先にブリーフへ足すこと (テストの推測で発明しない)。

7. **AC6 の実測** — 「lead-line が具体の要約になっている資料を渡すと axis=lead-line の
   finding が返る」は LLM 実行を伴うため、この suite では検証できない。P06 の受入。
