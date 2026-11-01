# handout-extract (C08) 受入テスト — 赤で固定した契約

対象 build_target: `plugins/guide-doc-generator/commands/handout-extract.md` (P05 で実装)

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/handout-extract -p 'test_*.py'
```

Python 3.10+ 標準ライブラリのみ (`unittest`)。PyYAML は使わず、command 定義の
frontmatter は `contract_lib.py` の YAML 部分集合パーサで読む。

## 何を検査しているか

C08 は slash-command component なので、テストは command の実行そのものではなく
**`handout-extract.md` の宣言的契約**を機械検査する。

最重要は次の 2 点である。

1. **入口が自前でパースロジックを持たない** (R14)。HTML の走査・部品同定・
   復元不能箇所の補完はすべて C02 skill (`run-handout-extract`) の責務であり、
   command 定義が `BeautifulSoup` / `html.parser` / `lxml` などの解析手段を
   本文へ書いた時点で `AC-C08-PARSE` が落ちる。
2. **引数既定値と上書きの解決結果**を 13 通り全件で固定する。`--out` の既定は
   入力 HTML と同じディレクトリの `handout-config.json`、既存ファイルは黙って
   上書きしない、html-path が不在 / ディレクトリなら委譲先を起動せず停止する。
   これを散文ではなく機械可読な `CR-EXTRACT-ARGS` ブロックとして宣言させ、
   `resolution_spec.py` の正解表と突き合わせる。

## ファイル構成

| ファイル | 役割 | 実装前の状態 |
|---|---|---|
| `resolution_spec.py` | 引数解決の正解表 (オラクル)。`expected(case)` と、宣言された `CR-EXTRACT-ARGS` を評価する `resolve_declared()` | — |
| `contract_lib.py` | command 定義の契約チェッカ。`check_command(plugin_root) -> [Violation]` | — |
| `reject_cases.py` | 非受入例の定義 (受入例へ 1 箇所だけ違反を注入する固定入力 29 件) | — |
| `fixtures/accept/` | 受入例。契約を満たす `commands/handout-extract.md` + 委譲先 skill / script のスタブ | — |
| `test_contract_checker.py` | 判定器が受入例を通し非受入例を落とすことを固定 | **緑** (実装に依存しない) |
| `test_argument_resolution.py` | 正解表そのものの性質 (緑) + 実装が宣言する解決規則の 13 通り照合 (赤) | 一部**赤** |
| `test_handout_extract_command.py` | 契約 id ごとの受入判定 (赤) + plan 側の事実の固定 (緑) | 一部**赤** |

## 引数解決の正解表 (CR-EXTRACT-ARGS)

`command-brief-C08.json` の `arguments[]` / `behavior` 1 / `failure_modes` 1-2 から起こした。
入口検証 → `--out` 解決 → 上書き確認 の順に評価し、先に一致した条件で行動が決まる。

| 条件 | 行動 | 出典 |
|---|---|---|
| positional 未指定 | `stop` (`html-path-missing`) | arguments `html-path` required=true |
| html-path が存在しない | `stop` (`html-path-not-found`) | behavior 1 / failure_modes 1 |
| html-path がディレクトリ | `stop` (`html-path-is-directory`) | 「展開せず停止する」 |
| `--out` 先が既存 | `confirm-overwrite` | 「黙って上書きせず、上書き可否を確認する」 |
| 上記以外 | `delegate` | behavior 2 |

解決結果:

- `--out` 未指定 → `{html_dir}/handout-config.json` (入力 HTML の隣)
- `--out` 指定 → 指定値そのまま (**変わるのは構成データ JSON の書き出し先だけ**)
- 逆抽出レポートの配置 → `--out` と同じディレクトリ

導かれる不変条件:

- 13 通りのうち `delegate` になるのは **html-path が実在ファイルで `--out` 先が未作成の 2 通りだけ**。
- 停止時は出力先を解決しない (停止したのに書き出し先が決まっている状態を作らない)。
- ディレクトリ指定はどの `--out` 指定でも停止する (どの HTML を正とするかを command が推測しない)。

### 機械可読形式について

brief は引数規則を散文でしか持たないため、機械検査できる単一の形として本テスト群は
実装へ次を要求する (テスト側が定めた形式。ブリーフ由来ではない → 下の gap 2)。

`handout-extract.md` の本文に `"id": "CR-EXTRACT-ARGS"` を持つ fenced ```json ブロックを
1 つ置き、`flags["--out"].default` (テンプレート `{html_dir}` を使う) /
`report_placement` (テンプレート `{out_dir}`) / `preconditions` (first-match の配列で
各要素は `{"when": {...}, "action": "stop|confirm-overwrite|delegate", "reason": "..."}`)
を宣言する。受入例 `fixtures/accept/commands/handout-extract.md` に満たす形の実物がある。

## 契約 id と出典の対応表

`AC-C08-1` 〜 `AC-C08-4` は brief の `acceptance_checks` の id そのもの。
`AC-C08-ARGS` / `AC-C08-DEGRADE` / `AC-C08-FM-*` / `AC-C08-PARSE` は brief に id が
無いため、出典 (arguments / failure_modes / boundary) を示す形で本テスト群が付番した
派生 id である。

| 契約 id | 内容 | 出典 | 固定しているテスト |
|---|---|---|---|
| AC-C08-0 | build_target に command 定義が実在する | task-spec `acceptance_criterion` | `test_AC_C08_0_build_target_exists` |
| AC-C08-1 | frontmatter が inventory #C08 と一致する。`argument-hint` は `<html-path> [--out <config.json>]` 完全一致、`allowed-tools` は Read / Write / Bash / Skill の **4 件ちょうど** (過不足禁止)、`disable-model-invocation: false` | brief `acceptance_checks#AC-C08-1`, inventory #C08 | `test_AC_C08_1_frontmatter_matches_inventory`, `PlanContractTest.test_AC_C08_1_checker_constants_match_inventory` |
| AC-C08-2 | `Skill(run-handout-extract, args="$ARGUMENTS")` の宣言、委譲先 skill の実在、委譲チェーン 4 script (C20/C12/C11/C16) の宣言と実在、委譲する責務 R1-scan / R2-complete / R3-roundtrip の明示 | brief `delegates_to`, `delegation_form`, `allowed_tools_rationale`, `acceptance_checks#AC-C08-2`, skill-brief-C02 `deterministic_checks` / `responsibilities` | `test_AC_C08_2_delegates_to_run_handout_extract`, `BuildTargetLayoutTest`, `PlanContractTest` 3 件 |
| AC-C08-3 | round-trip の粒度 (正規化後の構成データ等価で判定し HTML バイト一致は課さない / バイト一致は同一構成データからの再生成のみ) を**起動時に先に**宣言し、復元される範囲と復元されない意味情報を具体名で区別する | brief `acceptance_checks#AC-C08-3`, behavior 3-4 | `test_AC_C08_3_roundtrip_granularity_disclosed` |
| AC-C08-4 | 生成 (C07) と検証 (C09) を兼ねない。構成データを出すところで止まり、案内は `/handout-build --config <出力パス>` に留まる。内容の書き換え・改善提案をしない | brief `acceptance_checks#AC-C08-4`, `boundary`, behavior 8 | `test_AC_C08_4_no_overlap_with_build_and_verify`, `PlanContractTest.test_AC_C08_4_*` |
| AC-C08-ARGS | 引数既定値と上書きの解決結果 13 通りが正解表と一致し、停止理由の語彙が 3 分岐に 1:1 対応する。散文側にも既定値・上書き確認・レポート併置が書かれている | brief `arguments[]`, behavior 1, task-spec `acceptance_criterion`「引数既定値と上書きの解決結果」 | `test_AC_C08_ARGS_defaults_and_overrides`, `DeclaredResolutionTest` 3 件 |
| AC-C08-DEGRADE | 委譲先 skill / 委譲チェーン script が解決できない場合、成功として返さず停止し、解決を試みたパスを示す | task-spec `acceptance_criterion`「委譲先不在時の縮退」+ brief `failure_modes` 3 の思想 (→ gap 3) | `test_AC_C08_DEGRADE_missing_delegate_is_not_success`, `BuildTargetLayoutTest` |
| AC-C08-FM-1 | html-path 未指定 / 不在 / ディレクトリで委譲先を起動せず停止し、解決したパスと期待する形 (単一 HTML ファイル) を示す | brief `failure_modes` 1, behavior 1 | `test_AC_C08_FM_1_entry_stop_without_delegation` |
| AC-C08-FM-2 | `--out` の既存ファイルを黙って上書きしない | brief `failure_modes` 2 | `test_AC_C08_FM_2_no_silent_overwrite` |
| AC-C08-FM-3 | 部品構造を同定できない場合、抽出できた範囲と同定不能領域を返す。空の構成データを成功として返さず、部分成功を部分成功として提示する | brief `failure_modes` 3 | `test_AC_C08_FM_3_partial_success_stays_partial` |
| AC-C08-FM-4 | 復元不能箇所を「キーパス / 理由 / 補完方針」の 3 点セットで列挙し、補完方針を推測値の充填・空のまま残置・利用者への確認から明示、推測値と実測値を区別する。黙って落とさない | brief `failure_modes` 4, behavior 5 | `test_AC_C08_FM_4_unrestorable_info_is_reported` |
| AC-C08-FM-5 | round-trip 差分ありは差分キーパスと両側の値を出して FAIL。等価扱いにしない | brief `failure_modes` 5, behavior 7 | `test_AC_C08_FM_5_roundtrip_diff_is_fail` |
| AC-C08-FM-6 | validate-handout-config.py が FAIL でも構成データは書き出し、「そのままでは生成に使えない」と明示する。値を捏造して通さない | brief `failure_modes` 6, behavior 6 | `test_AC_C08_FM_6_validate_fail_is_not_fabricated_away` |
| AC-C08-PARSE | 入口が自前の HTML 解析手段を持たず、HTML の解釈にも構成データの補完にも関与しない。Read の用途は入力 HTML の存在確認に限る。走査と部品同定は skill へ渡す | R14, brief `boundary`, behavior 2, `allowed_tools_rationale` | `test_AC_C08_PARSE_entry_has_no_parsing_logic` |

## 実装前の実行結果 (赤の記録)

```
Ran 47 tests
FAILED (failures=21)
```

失敗はすべて failures (assertion) であり errors (import 例外) ではない。
実装が無い状態を「違反 0 件」と読ませないため、`assertContract()` は
build_target 不在を明示的に `fail()` させている。

## gap (P05 実装側が判断を要する点)

1. **逆抽出レポートのファイル名が brief に無い。** brief は「`--out` と同じ
   ディレクトリへ併置する」としか書いておらず、ファイル名を決めていない。
   テストは**ディレクトリの一致だけ**を固定し、名前は問わない
   (`resolution_spec.REPORT_PLACEMENT_TEMPLATE`)。名前を契約にするなら
   C02 / C20 のブリーフ側で決めてからテストへ足すこと。
2. **引数解決の機械可読形式は brief に無い。** 上記「機械可読形式について」の
   fenced json 形式は本テスト群が定めた。散文だけでは 13 通りの解決結果を
   機械検査できないため導入したが、別形式を採るなら
   `contract_lib.extract_args_block` と `resolution_spec.resolve_declared` を
   差し替えること (正解表 `expected()` は動かさない)。
3. **委譲先不在時の縮退が brief の failure_modes に無い。** task-spec の
   `acceptance_criterion` は要求しているので、`failure_modes` 3
   (「空の構成データを『成功』として返さない」) の思想を延長し、
   「停止 + 解決を試みたパスの提示」で固定した。停止理由の語彙
   (`html-path-missing` / `html-path-not-found` / `html-path-is-directory`) も
   テスト側の命名である。brief 側へ failure_mode として追記するのが望ましい。
4. **`--out` の上書き確認の実施主体が未決 (brief `open_questions` 1)。**
   command 側の対話で行うか、`extract-handout-config.py` (C20) に既存拒否
   フラグを持たせるかが決まっていない。テストは **command 定義側に
   `confirm-overwrite` の宣言があること**だけを固定した。C20 が無条件上書き
   なら宣言が素通りになるため、P05 では C20 のブリーフと突き合わせること。
5. **round-trip 比較の実行主体が未決 (brief `open_questions` 2)。**
   `extract-handout-config.py --compare` で行うか skill の再レンダリング比較で
   行うかは C02 / C20 側の決着に従う。command の契約は変わらないので、
   テストは委譲チェーン 4 script が宣言・実在することだけを固定した。
6. **`fixtures/accept/` の skill / script はスタブである。** 契約検査は
   「参照先が実在するか」しか見ないため、中身は空でよい。実装の
   `plugins/guide-doc-generator/{skills,scripts}/` に対しては
   `BuildTargetLayoutTest` が実体の存在を要求する。
