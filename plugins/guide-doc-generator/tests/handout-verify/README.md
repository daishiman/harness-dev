# handout-verify (C09) 受入テスト — 赤で固定した契約

対象 build_target: `plugins/guide-doc-generator/commands/handout-verify.md` (P05 で実装)

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/handout-verify -p 'test_*.py'
```

Python 3.10+ 標準ライブラリのみ (`unittest`)。PyYAML は使わず、command 定義の
frontmatter は `contract_lib.py` の YAML 部分集合パーサで読む。

## 何を検査しているか

C09 は slash-command component なので、テストは command の実行そのものではなく
**`handout-verify.md` の宣言的契約**と、**集約規則 CR-GATE-AGG の入出力契約**を
機械検査する。

最重要は「**not-run を pass に丸めない**」ことである。実行されなかったゲートを
pass と偽装しないことを、4 状態 (pass / fail / error / not-run) x 4 ゲート面の
全組み合わせ (4^4) に `--only` 使用有無を掛けた **512 通り**で赤に固定した。

## ファイル構成

| ファイル | 役割 | 実装前の状態 |
|---|---|---|
| `aggregation_spec.py` | 集約規則の正解表 (オラクル)。`aggregate(states, only_used) -> verdict` と、宣言された `verdict_table` を評価する `resolve()` | — |
| `contract_lib.py` | command 定義の契約チェッカ。`check_command(plugin_root) -> [Violation]` | — |
| `reject_cases.py` | 非受入例の定義 (受入例へ 1 箇所だけ違反を注入する固定入力 23 件) | — |
| `fixtures/accept/` | 受入例。契約を満たす `commands/handout-verify.md` + script 実体 5 件 | — |
| `test_contract_checker.py` | 判定器が受入例を通し非受入例を落とすことを固定 | **緑** (実装に依存しない) |
| `test_aggregation_rule.py` | 正解表そのものの性質 (緑) + 実装が宣言する `verdict_table` の 512 通り照合 (赤) | 一部**赤** |
| `test_handout_verify_command.py` | 契約 id ごとの受入判定 | **赤** |

## 集約規則の正解表 (CR-GATE-AGG)

`command-brief-C09.json` behavior 手順 4-6 と `canonical_aggregation` から起こした。
優先順位つきで、上から先に一致した行が全体 verdict になる。

| 条件 | 全体 verdict | 出典 |
|---|---|---|
| 4 面のいずれかが `fail` または `error` | `fail` | behavior 5-a / failure_modes「exit 2」 |
| `--only` を使った実行 (fail も error も無い) | `partial` | arguments `--only` override_rule |
| `not-run` が 1 つ以上 (fail も error も無い、全実行) | `incomplete` | behavior 5-c |
| 4 面すべて `pass` (全実行) | `pass` | behavior 5-b |

導かれる不変条件:

- `pass` になる入力は **(4 面すべて pass, `--only` 未使用) のちょうど 1 通り**だけ。
- `not-run` を含む 512 通りのどれも `pass` にならない。
- `error` は資料の合格の証拠にならないので `fail` 側へ倒す (fail-closed)。
- 4 面すべて `not-run` (= 1 ゲートも走らなかった) は `incomplete` であり `pass` ではない。

### 機械可読形式について

brief は集約規則を散文でしか持たないため、機械検査できる単一の形として本テスト群は
実装へ次を要求する (テスト側が定めた形式。ブリーフ由来ではない → 下の「gap」参照)。

`handout-verify.md` の本文に、`"id": "CR-GATE-AGG"` を持つ fenced ```json ブロックを
1 つ置き、`gate_faces` / `states` / `not_run_reasons` / `verdict_table` を宣言する。
`verdict_table` は first-match で評価され、各行は
`{"when": {"any_state": [...], "all_states": [...], "only_used": bool}, "verdict": "..."}`。
受入例 `fixtures/accept/commands/handout-verify.md` に満たす形の実物がある。

## 契約 id と出典の対応表

| 契約 id | 内容 | 出典 | 固定しているテスト |
|---|---|---|---|
| AC-C09-0 | build_target に command 定義が実在する | task-spec `acceptance_criterion` | `test_AC_C09_0_build_target_exists` |
| AC-C09-1 | frontmatter (name / description / argument-hint / allowed-tools / disable-model-invocation)。**Skill と Write を持たない** | brief `acceptance_checks#AC-C09-1`, inventory #C09, `allowed_tools_rationale` | `test_AC_C09_1_frontmatter_matches_inventory` |
| AC-C09-2 | 委譲先 script 4 本 (C16/C17/C18/C22) の実在と argv (`--html` / `--config` / `--out-dir` / `--json-report`)、`${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/` での解決 | brief `acceptance_checks#AC-C09-2`, `gates[]`, `delegation_form` | `test_AC_C09_2_delegated_scripts_exist_with_matching_argv`, `BuildTargetLayoutTest` |
| AC-C09-3 | `--config` 未指定 / 未正規化 → language・narrative が not-run (`config-missing` / `config-not-normalized`)、全体 `incomplete`。検出は `validate-handout-config.py --strict` | brief `acceptance_checks#AC-C09-3`, `failure_modes` 2-3 | `test_AC_C09_3_config_missing_degrades_to_not_run`, `test_AC_C09_3_config_missing_scenario` |
| AC-C09-4 | fail-fast にしない。1 ゲート fail でも後続を全部走らせ全体 `fail` | brief `acceptance_checks#AC-C09-4`, behavior 3, `failure_modes`「複数ゲートが同時に fail」 | `test_AC_C09_4_no_fail_fast`, `test_AC_C09_4_one_gate_fail_scenario` |
| AC-C09-5 | `--only` は成功時でも `partial`。除外は not-run (`excluded-by-only`)。未知 gate_id は停止 | brief `acceptance_checks#AC-C09-5`, arguments `--only`, `failure_modes`「未知の gate_id」 | `test_AC_C09_5_only_run_is_partial`, `test_AC_C09_5_only_selfcontained_scenario` |
| AC-C09-6 | 生成 (C07) / 逆抽出 (C08) / 正規化 (C12) を行わない read-only 集約入口 | brief `acceptance_checks#AC-C09-6`, `boundary` | `test_AC_C09_6_read_only_boundary` |
| AC-C09-7 | html-path 不在 / ディレクトリ指定は 1 ゲートも実行せず停止。空の集約を pass にしない | brief `failure_modes`「html-path 未指定 / 不在 / ディレクトリ指定」, behavior 1 | `test_AC_C09_7_entry_stop_is_not_pass` |
| AC-C09-9 | script 不在は not-run (`script-absent`) + 解決を試みたパスの提示。skip を pass に読み替えない | brief `failure_modes`「検証 script が見つからない」 | `test_AC_C09_9_script_absent_is_not_run` |
| AC-C09-10 | 報告に 4 ゲート全行 (not-run も省かない)、gate_id / 理由 / 該当箇所、`--json-report` の集約サマリ (`verdict` + `gates`)、次の一手 | brief behavior 6-8 | `test_AC_C09_10_reports_all_four_gates` |
| AC-C09-11 | 引数 5 件の既定値と上書き規則 (`--out-dir` 既定 = html-path の親、`--only` 既定 = 4 ゲート全実行 ほか) | brief `arguments[]`, task-spec `acceptance_criterion`「引数既定値と上書きの解決結果」 | `test_AC_C09_11_argument_defaults_and_overrides` |
| AC-C09-AGG-1 | 集約規則の単一正本が本 command であり、C09 直叩き経路と C01 R4-verify 経路が同一 verdict を返す | brief `canonical_aggregation`, `acceptance_checks#AC-C09-AGG-1`, RESOLUTION-P03 Y-07 | `test_AC_C09_AGG_1_single_source_of_truth`, `ConsumerParityTest` |
| AC-C09-AGG-2 | 宣言された `verdict_table` が **512 通りすべて**で正解表と一致する | brief behavior 5, `canonical_aggregation.statement` | `DeclaredAggregationTest` 全件 |
| AC-C09-AGG-3 | 4 状態 / 4 verdict / not-run 理由 4 種 / exit 0-1-2 の写像が宣言されている | brief behavior 4, `open_questions`「exit code 規約」 | `test_AC_C09_AGG_3_states_reasons_and_exit_codes_declared` |
| AC-C09-AGG-4 | not-run を pass へ畳む記述が無く、畳まない旨が明示される | brief `canonical_aggregation.statement`, behavior 5 | `test_AC_C09_AGG_4_not_run_is_never_folded_into_pass`, `test_not_run_is_never_folded_into_pass` |

## 3 面の担当 (どのファイルのどのテストが何を見ているか)

| 面 | 担当 |
|---|---|
| 違反系入力で落ちる | `reject_cases.py` + `test_contract_checker.py::TestRejectFixtures` |
| argv と exit code 契約 | `test_handout_verify_command.py::test_AC_C09_2_*` / `::test_AC_C09_11_*`、`test_aggregation_rule.py::TestOracleShape::test_exit_code_mapping`、`test_argv_and_reproducibility.py::GateArgvMatchesRealScriptsTest` |
| 再現性 | `test_argv_and_reproducibility.py::CheckerReproducibilityTest` / `::AggregationReproducibilityTest` |

build_target が Markdown であるため、この 2 面は次の対応物として定義した。

- **argv**: 従来の AC-C09-2 は「command 本文にフラグが現れるか」をテスト側の表と
  突き合わせるだけで、実 script が受け取らないフラグでも緑になった。
  `GateArgvMatchesRealScriptsTest` は同じフラグを実 script の argparse と突合し、
  config 必須ゲートと `--config` の受け口が一致することまで見る。
  さらに `contract_lib._check_scripts` の argv 検査を、本文全体への出現から
  **当該 script を名指しする行への束縛**へ変更した (他ゲート専用フラグの混入も違反)。
  従来は本文のどこかに `--config` が一度あれば全ゲート分が満たされていた。
- **exit code**: C09 が持つ対応物は「起動した script の exit code をどう読むか」
  という**解釈規則**で、これは実行ではなく写像宣言なので Markdown でも成立する。
  `AC-C09-AGG-3` は従来 `exit 0` という番号の出現しか見ておらず
  `exit 0 -> fail` と書いても緑だったため、**同じ行に対応状態語があること**と
  **他状態へ写す宣言が無いこと**まで見るようにした。その先の 4 状態集約は
  `test_aggregation_rule.py` の担当。
- **再現性**: 実行の再現性ではなく、(1) 判定器が同一入力へ同一の違反列を返すこと
  (同プロセス 2 回 + 別プロセス 2 回)、(2) 集約オラクルと実装の宣言表が全組み合わせで
  安定し、ゲートの並び順にも抽出の再読み込みにも依存しないこと。

## 正本リテラルを写さない方針

ゲート名簿 (gate_id / component / script / argv / config 必須面) の正本は
`command-brief-C09.json#gates[]` ただ 1 つで、`aggregation_spec.py` は import 時に
そこから実測で導出する (読めなければ `RuntimeError` で fail-closed)。
`ARGUMENT_HINT_TOKENS` は brief の `argument_hint` から、`--only` 未指定時の全実行
本数はゲート名簿の要素数から導く。散文中の「4 面」という記述は説明であって期待値
ではないため、そのまま残している。

## acceptance_criterion 後半について

「build_target が未実装の時点で実行すると失敗する」は、実装が既に存在するため
**現物では再現できない**。実装を削除して測ることは禁止されているので、
`UnimplementedBuildTargetSurrogateTest` が空ディレクトリを plugin root と見立てて
判定器の挙動 (AC-C09-1 で停止する) だけを固定している。これは代理であって
現物での再現ではない。

## 実装前の実行結果 (赤の記録)

```
Ran 60 tests
FAILED (failures=33)
```

失敗はすべて failures (assertion) であり errors (import 例外) ではない。
実装が無い状態を「違反 0 件」と読ませないため、`assertContract()` は
build_target 不在を明示的に `fail()` させている。

## gap (P05 実装側が判断を要する点)

1. **`argument-hint` の正本が 2 つある。** `component-inventory.json#C09` は
   `<html-path> [--config <config.json>]`、`command-brief-C09.json` は
   `--out-dir` / `--only` / `--json-report` を含む長い形を持つ。AC-C09-1 は
   「inventory と一致」と書くが、brief の behavior は 5 引数すべてを要求する。
   テストは **brief 側を採り**、`<html-path>` で始まり 5 引数すべてを含むことを
   要求する構造検査にした (完全一致比較にはしていない)。inventory 側の更新が要る。
2. **集約規則の機械可読形式は brief に無い。** 上記「機械可読形式について」の
   fenced json 形式は本テスト群が定めた。散文だけでは 512 通りの集約結果を
   機械検査できないため導入したが、別形式を採るなら `contract_lib.extract_aggregation_block`
   と `aggregation_spec.resolve` を差し替えること (正解表 `aggregate()` は動かさない)。
3. **exit 2 の意味。** brief `open_questions` のとおり、引数エラーを exit 2 に含めるかは
   C16/C17/C18/C22 側の確定待ち。本テストは brief の前提どおり
   「exit 2 = error、fail 側へ倒す」で固定した。
