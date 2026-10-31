# C19 独立 content レビュー案

対象: `/Users/dm/orca/workspaces/harness/pr86-ci-fix/plugins/dev-graph/skills/run-dev-graph-system-spec/` 全体と今回の未コミット差分。レビュー時点の全6ファイルの digest は `source-manifest.json` に記録した。SKILL.md は `b3f81c242405791af3b642ec9f3b07e56f1f3e756d3833ca0d00d757d8bb39e7`。

結論: 今回の cwd/path binding 修理は PASS。規範採点は 84/100、閾値80、high 0。`elegance-verdict.json` は4観点の独立 focused review に基づく案であり、30思考法のフル実走を表さない。正式な host live trial の合格や人間承認を捏造していない。

## 読んだ規範と対象

`assign-skill-design-evaluator/SKILL.md`、`prompts/R1-evaluate.md`、`references/evaluator-contract.md`、L0 `ref-skill-design-rubric/references/rubric.json` 1.6.0、evaluator L2 override を読み、正規採点器を L0→L2 で実行した。C19 の SKILL.md・R0/R1/R2/R3 prompt・新 helper を全文確認した。

境界の照合には C24 `resolve-repo-context.py`、C02 `_spec_confirmation` と取込の呼出し箇所、共有 `prompt-common-layers.md`、system-spec-harness の evaluator の SKILL.md と R1/R2、および snapshot writer / aggregate の該当処理を読んだ。既存 content-review の2 verdict は形状の参考に限り、過去の合否・人間判断・残課題の受容を引き継いでいない。

親の変更通知を受け、最終版の集約ログ単独更新の追記を再読し、採点器と境界テストを再実行した。

## 規範採点

`rubric-raw.json` が採点器の生出力。適用24、機械採点23、意味判断1、未実装0。FM-005 low、PD-001 low、PD-002 mediumの計16点減点で84。いずれも今回差分以前からある構造。

機械が保留した BD-004 は、この独立レビューのLLM判断として2つの trigger を1対1で確認した。仕様作成は手順3/R2の正規Skill委譲、lineage付き取込は手順4/R3のC02取込に対応する。人間が評価したという意味ではない。

正規評価スキルが通常求める既存 eval-log への append は、親の「既存証跡変更禁止」に従い実行していない。原本は変更せず、案を `/tmp` のみに置いた。

## 4観点の判断

| 観点 | 今回差分の判断 | 根拠 |
| --- | --- | --- |
| 矛盾 | PASS | R2/R3/Gotchasが絶対spec_dir・outputとrepo相対evidence_ref/lineageを同じ契約で扱う。helper失敗の起動禁止とreport不一致時の1回再評価を区別する。 |
| 漏れ | PASS | helperがreceipt mode、5 identity、2 content root、root内spec、eval-log配下非symlink outputを検証する。親単独集約ログと子の局所ログを分ける追記が4キー/6キー混在を避ける。 |
| 整合性 | PASS | helperのshlex.joinは空白・単引用符・日本語rootで復元できる。絶対spec_dirはevaluatorの「引数値をそのままreportへ書く」契約と一致する。 |
| 依存関係 | PASS（既存制限は別記） | C24のcontainmentとC02のdirectory照合に接続できる。C02の絶対spec_dir受容は既存実装で、今回の変更が受入範囲を広げたものではない。 |

## 実行した確認

- `python3 -B -m pytest -q -p no:cacheprovider plugins/dev-graph/tests/test_system_spec_evaluation_paths.py --basetemp=/tmp/pr86-c19-content-review/pytest-final`: **14 passed**。`pytest-final-output.txt` に生出力。`git_dir`を含むidentity、content root、foreign cwd、外部出力、symlink、環境root不一致、エラーコードの検査を含む。
- `probe_boundaries.py`: `/tmp` 内の合成Git repoだけを作成し、11記録を採取。caller rootに空白・単引用符・日本語を含め、foreign cwdからhelperを起動して同一JSONと同じ絶対引数を確認した。絶対output・parent traversal・外部receipt root・外部config rootは拒否された。結果は `boundary-probe-results.json`。
- C02の実関数を読取り専用で呼び、正しい絶対spec_dirは受理、別ディレクトリの絶対spec_dirは `invalid_confirmation_evidence` で拒否されることを確認した。この合成reportは本物のevaluator出力や監査証跡ではない。

最初の独自fixtureはmacOSの `/tmp` → `/private/tmp` 正規化を期待値に入れ忘れてassertに失敗した。fixture側をrealpath化して再実行したところ通過した。sourceに対する修正ではない。

## 既存制限と必要最小限の提案

1. **C02のsnapshot接地（medium、既存依存の検証限界）**: `_spec_confirmation` はreport PASS/spec_dirとpayload同士のdigest一致を見るが、report.artifact_snapshotの章digestは照合しない。fixtureでは、章を変更してpayloadのdigestを現在値にすると古い最小reportを受理した。`dependency-scope.json` にC02がHEADと同一であることを保存した。この抜けは今回のabsolute path化以前から存在し、今回のcwd混同を直す変更で導入されたhighではない。別の追跡項目として、C02がreport snapshotの該当source_path/digestを照合する最小改修を検討する。
2. **非標準system_spec root（low、既存）**: C24の設定変更は許されるが、elicit/compile/snapshotの既定はsystem-spec。evaluator Gotchas 12はbasenameがsystem-specでないspec_dirを評価開始前に差し戻すのでfail-closedになる。C19で未対応rootを早く診断すれば迷いが減る。
3. **progress検証（low、既存）**: goal検証snippetはprogress.jsonの達成状態を検査しない。今回のログ所有権追記は形状衝突を解消するが、完了状態の機械照合を増やしたものではない。
4. **版の古い文言（low、既存）**: R1のsummary/不変目的に古い>=0.1.0がある。実判定はcompositionを正本と明示しており、新たな版判定不具合は確認していない。

今回の修理の通常経路は、評価後に章を書き換えず、委譲先の正規 evaluator/aggregate を通し、C02に同一payloadを渡すことで境界づけられる。aggregateのreport検査は形状・合否・fork帰属・spec_dirを確認する。**report snapshotと現在snapshotの完全一致はproduction `build-resume-receipt.py` が実装する別ゲートであり、C19の通常取込でC02が同じ照合を行っているとは言わない。** helper自身はパス・identityの検査器であり、bytes snapshotの検証器ではない。

## 成果物と範囲

`rubric-verdict.json` / `elegance-verdict.json` が差替え候補、`rubric-raw.json` が採点器の生出力。全て `/tmp/pr86-c19-content-review/` のみへ書いた。sourceと既存証跡の編集、既存ログへの採点append、コミット、push、human承認、host監査fork、fresh live trialは行っていない。合成fixtureのGit commitは一時repoのidentity準備だけで、作業repoはcommitしていない。
