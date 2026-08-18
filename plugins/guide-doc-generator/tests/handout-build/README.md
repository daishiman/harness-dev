# C07 handout-build 受入テスト (赤で固定)

対象 build_target: `plugins/guide-doc-generator/commands/handout-build.md` (未実装)

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/handout-build -p 'test_*.py'
```

Python 3.10+ 標準ライブラリのみ。外部依存なし。

## 構成

| ファイル | 役割 | 実装前の色 |
| --- | --- | --- |
| `contract_lib.py` | command 定義 Markdown の宣言的契約チェッカ (判定器) | — |
| `fixtures/accept/` | 契約を満たす受入例。判定器が「違反 0 件」を返すべき唯一の入力 | — |
| `reject_cases.py` | 受入例へ違反を 1 箇所ずつ注入する差分表 (34 件) | — |
| `test_contract_checker.py` | 判定器が空ゲートでないことの固定。実装に依存しない | **緑** |
| `test_handout_build_command.py` | 契約 id ごとの受入判定 + 定数の出所照合 | **赤** |

`test_contract_checker.py` が緑であることに意味がある。判定器が何も検出しない
空ゲートなら、実装後に `test_handout_build_command.py` が「全部通った」と言えて
しまう。非受入例 34 件が対応する契約 id で落ちることを先に固定してある。

`SourceOfTruthTest` は `contract_lib` の期待値 (description / allowed-tools /
引数名 / delegation_form / 用途語彙) が brief と component-inventory から来て
いることを照合する。P05 の実装側が判定器の期待値を書き換えて緑にする経路を
塞ぐためのもの。

## 実装前の実行結果

```
Ran 45 tests ... FAILED (failures=26)
```

errors 0 / failures 26。import 例外や `setUpClass` の例外で落ちる構造は使って
いない (実装不在は `assertContract` が `self.fail` で明示的に赤にする)。

## 契約 id と出典

出典の略号: `B` = `briefs/command-brief-C07.json` (正本)、`I` =
`component-inventory.json#C07`、`S` = `briefs/skill-brief-C01.json`。

| 契約 id | 固定した内容 | 出典 |
| --- | --- | --- |
| `AC-C07-0` | build_target に command 定義が実在する | task-spec acceptance_criterion |
| `AC-C07-1` | frontmatter: name / description 完全一致 / argument-hint が 6 引数を露出 / allowed-tools = Read・Write・Bash・Skill と過不足なく一致 / disable-model-invocation = false | I, B `acceptance_checks[AC-C07-1]`, B `allowed_tools_rationale` |
| `AC-C07-ARGS` | 6 引数それぞれの既定値と上書き規則が宣言される。題材のみ positional、6 件とも required=false | B `arguments[]`, task-spec「引数既定値と上書きの解決結果」 |
| `AC-C07-2` | 用途種別の語彙 8 語が command 定義に 1 件も現れない。`resolve-handout-preset.py --list` を候補提示の手段として案内する | B `acceptance_checks[AC-C07-2]`, B `arguments[--doc-type]`, C42 |
| `AC-C07-3` | --theme の 3 点 (構成データにテーマ欄が無い場合のみ有効 / 採用値は同梱構成データへ書き戻される / 再現の単位は同梱構成データ) + 書き戻しの実行者が `render-handout.py` (C11) であることの名指し | B `acceptance_checks[AC-C07-3]`, B `arguments[--theme]` |
| `AC-C07-DATE` | 正本書式 yyyy/mm/dd + 寛容書式 3 種の素通し / command は書式判定しない / command も skill も自前で現在日を取得しない / 単一 writer は `validate-handout-config.py --normalize` | B `arguments[--date]`, B `open_questions[1]` (X-01 決着) |
| `AC-C07-OUTDIR` | 親ディレクトリだけを上書き / `<YYYY-MM-DD>-<種別>-<主題slug>/` の命名規則は上書き不可 / 導出は `route-handout-output.py` (C19) | B `arguments[--out-dir]`, R17 |
| `AC-C07-CONFIG` | 存在と JSON 可読性だけを Read で確認 / 内容の妥当性は判定しない (C12 の責務) / 構成データが常に CLI フラグより強い正本 | B `arguments[--config]`, B `behavior[3]` |
| `AC-C07-4` | `Skill(run-handout-build, args="$ARGUMENTS")` の形で委譲 / 委譲先 build_target の明記 / C01 が skill として実在し build_target が一致 | B `delegates_to`, B `delegation_form`, B `acceptance_checks[AC-C07-4]`, I#C01 |
| `AC-C07-5` | --config あり = 非対話経路 (ヒアリング省略で R2-design へ)、--config なし = ヒアリング駆動。「対話は既定経路であって唯一経路ではない」の明記 | B `acceptance_checks[AC-C07-5]`, B `behavior[2]`, S `boundary` |
| `AC-C07-6` | 薄い入口: 判断も加工もしない / 資料の内容にも HTML の組み立てにも関与しない / skill 側の責務 4 種 (ヒアリング・プリセット解決・出力先ルーティング・ゲート結果集約) を command が持たない | B `boundary`, B `behavior[5]` |
| `AC-C07-B1` | 未知フラグを推測解釈せず停止する | B `behavior[1]` |
| `AC-C07-B2` | 題材と --config の同時指定は矛盾として停止する | B `behavior[2]`, B `arguments[題材]` |
| `AC-C07-FM-1` | 引数なし起動はエラーにせず R1-elicit を開始する | B `failure_modes[0]`, R19 |
| `AC-C07-FM-2` | --config が読めないとき委譲先を起動せず停止し、解決したパスを表示する (ヒアリング経路へ暗黙フォールバックしない) | B `failure_modes[1]` |
| `AC-C07-FM-3` | 語彙外 --doc-type は C23 の exit≠0 を受けて停止し候補提示を案内する | B `failure_modes[2]` |
| `AC-C07-FM-4` | 衝突はキーパスと両方の値を示して停止。黙って無視も上書きもしない | B `failure_modes[3]` |
| `AC-C07-FM-5` | ゲート exit≠0 は生成物を残したまま FAIL を明示し、成功と読める要約を書かない | B `failure_modes[4]`, S `feedback_contract[OUT1]` |
| `AC-C07-FM-6` | slide-report-generator 不在は skip 理由つき報告 + 他ステップ完走 (fail-soft) | B `failure_modes[5]`, C18 |
| `AC-C07-REPORT` | 生成レポートの 5 要素 (出力ディレクトリ / 同梱 4 点 / 適用部品 / 埋め込みサイズと warning / 各ゲートの結果) を加工せずそのまま提示 | B `behavior[6]` |
| `AC-C07-THEME-NOTICE` | --theme 採用時に「以後の再現は同梱構成データ 1 点で足り、--theme の再指定は不要」と伝える | B `behavior[7]` |

### task-spec が名指しした 2 点の所在

- **引数既定値と上書きの解決結果** → `AC-C07-ARGS` (6 引数の表) + 個別の
  `AC-C07-CONFIG` / `AC-C07-OUTDIR` / `AC-C07-3` / `AC-C07-DATE`。
- **委譲先不在時の縮退** → `AC-C07-FM-6` (任意依存 slide-report-generator の
  fail-soft skip) と `AC-C07-4` / `BuildTargetLayoutTest.test_delegate_skill_exists`
  (必須依存 C01 skill の不在は縮退させず未達として落とす)。任意依存と必須依存で
  縮退の可否が逆であることを 2 つの契約に分けて固定した。

## テスト側が導入した表現上の要求 (ブリーフに規定が無い部分)

`CR-HB-ARGS`: 引数の既定値と上書き規則を機械検査するため、本文に
`{"id": "CR-HB-ARGS", "arguments": [...]}` の fenced json を 1 つ置くことを
要求する。brief は引数を散文で持つだけで機械可読形式を規定していないため、
検査可能な単一形式をテスト側で決めた。同じ手は C09 (`CR-GATE-AGG`) でも採って
いる。契約の**中身**は brief の `arguments[]` そのままで、増やしていない。

## gaps

| # | what | why |
| --- | --- | --- |
| 1 | `--presentation-order` (demo_first / explain_first) を C07 が透過的に C01 へ渡す契約が、どのブリーフにも書かれていない | `RESOLUTION-R21.md` の C50 行の「CLI は `--presentation-order`」は **C23 `resolve-handout-preset.py` の flag** を指す (`script-brief-C23.json` の `flag: --presentation-order`)。導出の単一正本は C12 の `CR-PRESENTATION-ORDER`、C01 は利用者が自発的に述べたときだけ明示上書きを構成データへ書く (`skill-brief-C01.json` の `presentation_order_is_not_a_hearing_item`) と決まっており、`command-brief-C07.json` の `arguments[]` にこのフラグは無い。C07 に slash-command 面の `--presentation-order` を持たせるかは未決。**推測で発明せずテストに入れていない** — 持たせるなら brief の `arguments[]` と `argument_hint` への追記が先。逆に持たせないなら「提示順は CLI 入口を持たない」ことを C07 の boundary に明記したい (現状どちらも書かれていない) |
| 2 | `argument-hint` が inventory と brief で食い違う | I#C07 は `[題材] [--out-dir <path>] [--theme <preset> (構成データ未指定時のみ)]` の 3 引数版、B `argument_hint` は `--config` / `--doc-type` / `--date` を含む 6 引数版。B `acceptance_checks[AC-C07-1]` は「frontmatter が I と一致すること」を要求するため、そのまま読むと `--config` を argument-hint から隠すことになり、AC-C07-5 の非対話経路が入口 hint から見えなくなる。**テストは brief を正本として 6 引数すべてを含むことを要求**した (`AC-C07-1`)。I#C07 の `argument-hint` を brief 側へ揃える更新が要る |
| 3 | C11 側の衝突時挙動が未統一 | B `open_questions[0]`: `--theme` / `--date` が構成データの既存欄と衝突したとき、C07 は停止するが `render-handout.py` (C11) が同じ状況で「無視」か「exit≠0」かは未決で、P03 design-gate で統一するとある。`RESOLUTION-P03.md` の Y-01〜Y-09 にこの突き合わせの記録が無く、**未解消のまま P04 に来ている**。command を経由しない直叩き時に挙動が変わる |
| 4 | `disable-model-invocation` の値の出典が inventory のみ | B の frontmatter 相当項目 (`description` / `argument_hint` / `allowed_tools`) に `disable-model-invocation` が無く、B `acceptance_checks[AC-C07-1]` は照合対象に挙げている。I#C07 の `false` を採用した。C08 / C09 と揃っているかは別 leaf の確認事項 |
