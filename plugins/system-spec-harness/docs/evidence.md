# system-spec-harness 受入 Evidence (P11)

> 第三者が本記録の fixture / コマンド / artifact から同一の合否へ到達できることを目的とした受入証跡。
> 実行ログの貼付でなく **再現入力 (fixtures) への参照** を主とする。全コマンドは repo-root cwd 前提。

## Evidence 5 要素

| # | 要素 | 再現入力 (fixture) | 再現コマンド | 期待 |
|---|---|---|---|---|
| 1 | ヒアリング resume (5周保存→resume) | `plugins/system-spec-harness/skills/run-system-spec-elicit/fixtures/hearing-turns.json` (9 turn=6周超), `expected-resume-spec-state.json` | `python3 -m pytest -q plugins/system-spec-harness/skills/run-system-spec-elicit/tests` | 5周目に `hearing_progress.complete=false`・`next_question` 非null で保存 |
| 2 | 公式文書鮮度 | `plugins/system-spec-harness/skills/run-system-spec-doc-fetch/tests/fixture-references-host-mismatch.json` / `-missing.json` | `python3 plugins/system-spec-harness/scripts/validate-source-citation.py --targets <t> --references <r>` | 正例 exit0 / 非公式host・欠落 exit1 |
| 3 | C02→C03→C05 自動連鎖 | `plugins/system-spec-harness/commands/spec-compile.md` | `/spec-compile` | 出典準備→compile→評価が自動連鎖 |
| 4 | Write/Edit 負例 (確定章上書き遮断) | `plugins/system-spec-harness/tests/test_guard_hook.py` (確定章 Write/Edit fixture) | `python3 -m pytest -q plugins/system-spec-harness/tests/test_guard_hook.py` | 確定章 Write/Edit → exit2 / 非対象・reopen → exit0 |
| 5 | Bash 書換負例 (spec-state 動的書換遮断) | `tests/test_guard_hook.py` (sed -i/リダイレクト fixture) | 同上 | spec-state.json への `sed -i`/リダイレクト → exit2 / read-only → exit0 |

## 受入 Evidence Matrix (goal-spec C1-C12 / P07 AC 1:1)

| 要件 | 受入観点 | Evidence (fixture/artifact) | 検証コマンド | 状態 |
|---|---|---|---|---|
| C1 | カテゴリ一覧+収集状態明示 | C04 taxonomy + C03 expected-database + C12真理値表 | `python3 -m pytest -q plugins/system-spec-harness/tests/test_validate_scripts.py -k aggregate` | PASS |
| C2 | canonical platform id 6種 | C12 platform正負例 | `python3 -m pytest -q plugins/system-spec-harness/tests -k platform` | PASS |
| C3 | 往復ヒアリングで停止しない | Evidence#1 + C01 R3 + C06 | `python3 -m pytest -q plugins/system-spec-harness/skills/run-system-spec-elicit/tests` | PASS |
| C4 | deep knowledge反映 | C04 deep cards + C03 deep render fixtures | `python3 -m pytest -q plugins/system-spec-harness/skills/run-system-spec-compile/tests -k deep` | PASS |
| C5 | 最新ドキュメント出典記録 | Evidence#2 + C13/C08 | `python3 -m pytest -q plugins/system-spec-harness/tests/test_validate_scripts.py -k c13` | PASS |
| C6 | 章立て複数Markdown+index | C03 golden fixtures | `python3 -m pytest -q plugins/system-spec-harness/skills/run-system-spec-compile/tests` | PASS |
| C7 | 網羅マトリクス検証 | C12正負例 | `python3 plugins/system-spec-harness/scripts/validate-coverage-matrix.py --matrix <s> --require-complete` | PASS |
| C8 | packaging 契約充足 | `.claude-plugin/plugin.json` / `EVALS.json` / route-build-report×13 | `check-build-handoff.py` / `validate-route-build-reports.py --complete` | PASS |
| C9 | 上位概念U1-U9とgoal trace | `requirements_foundation` fixture + `00-requirements-definition.md` | `python3 -m pytest -q plugins/system-spec-harness/tests/test_validate_foundation.py` | PASS |
| C10 | 迷った時のAI案内とユーザー確認保留 | R5 prompt + decision transition正負例 | `python3 -m pytest -q plugins/system-spec-harness/skills/run-system-spec-elicit/tests -k decision` | PASS |
| C11 | open-world deep knowledge | knowledge cards/catalog/lifecycle | `python3 plugins/system-spec-harness/skills/ref-system-design-knowledge/scripts/validate-knowledge-cards.py` | PASS |
| C12 | prompt-creator意味契約 | 全18 prompt + `eval-log/system-spec-harness/build/prompt-design-findings.json` | `verify-completeness.py` + `validate-prompt.py` (18件) | PASS |

## 網羅性 (カテゴリ×プラットフォーム) の再現

C01 が初期化するマトリクスは 8カテゴリ × 6プラットフォーム = 48セル。各セルが `未収集/対象外/確定` の3値で、確定は `qa_ref`・対象外は `reason` を持つことを C12 が機械検証する。fixture `skills/run-system-spec-elicit/fixtures/expected-final-spec-state.json` を `validate-coverage-matrix.py --require-complete` に通すと未収集0で exit0 になり、第三者がカテゴリ×プラットフォーム網羅を再現確認できる。

## 全体テスト証跡
`python3 -m pytest -q plugins/system-spec-harness` → 293 passed。全18 promptは両validator PASS、独立意味評価は `prompt-design-findings.json` でC1-C4全PASS・high 0。
