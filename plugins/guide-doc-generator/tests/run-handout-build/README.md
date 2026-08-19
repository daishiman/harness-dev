# run-handout-build (C01) 受入テスト — 赤で固定した契約

対象 build_target: `plugins/guide-doc-generator/skills/run-handout-build/` (P05 で実装)

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/run-handout-build -p 'test_*.py'
```

Python 3.10+ 標準ライブラリのみ (`unittest`)。PyYAML は使わず、SKILL.md の
frontmatter は `contract_lib.py` の YAML 部分集合パーサで読む。

## 何を検査しているか

C01 は skill component なので、テストは skill の実行そのものではなく
**SKILL.md の宣言的契約**を機械検査する。

- frontmatter (identity / responsibilities / combinators / goal_seek / feedback_contract / allowed-tools)
- 本文の必須セクション骨格
- 参照する決定論 script のパスが実在すること
- R21 ヒアリング必須項目の宣言 (C01 が定義の単一正本)
- 呼び出す / 委譲する component の宣言 (C09 / C19 / C03 / C05)

## ファイル構成

| ファイル | 役割 | 実装前の状態 |
|---|---|---|
| `contract_lib.py` | 契約チェッカ本体 (判定器)。`check_skill(skill_dir) -> [Violation]` | — |
| `reject_cases.py` | 非受入例の定義 (受入例へ 1 箇所だけ違反を注入する固定入力 16 件) | — |
| `fixtures/accept/` | 受入例。契約を満たす SKILL.md + prompts 4 件 + script 実体 7 件 | — |
| `test_contract_checker.py` | 判定器が受入例を通し非受入例を落とすことを固定 | **緑** (実装に依存しない) |
| `test_run_handout_build_skill.py` | 実 build_target への契約テスト (契約 id ごとに 1 メソッド) | **赤** |

`test_contract_checker.py` が緑であるのは意図どおりで、
「`test_run_handout_build_skill.py` が使う判定器が、何も検出しない空ゲートでは
ないこと」を先に固定するためにある。実装が存在しないうちに判定器の判定力を
検証できる唯一の手段がこの受入例 / 非受入例のペアである。

## 契約 id と出典の対応表

正本は `plugin-plans/guide-doc-generator/briefs/skill-brief-C01.json`。
ブリーフ側に `AC-C01-*` の採番が存在しなかったため、本テストで採番した
(`gaps` 参照)。

| 契約 id | 内容 | 出典 |
|---|---|---|
| AC-C01-1 | build_target に SKILL.md が実在する | task-spec `P04-C01-01.md` acceptance_criterion / inventory `C01.build_target` |
| AC-C01-2 | `name=run-handout-build` / `prefix=run` / `kind=run` / `hierarchy=L1` | brief `skill_name` / `prefix` / `kind` / `hierarchy_level` |
| AC-C01-3 | description が「〜したいときに使う」形で trigger 語彙を持つ | brief `trigger_conditions` + repo の run 系 SKILL.md 慣行 |
| AC-C01-4 | responsibilities が R1-elicit / R2-design / R3-render / R4-verify / R5-refine の 5 件ちょうど、全て `prompt_required: true` | brief `responsibilities` |
| AC-C01-5 | `responsibility_refs` が `prompts/<R-id>.md` を指し実在する | inventory `goal_seek.engine=inline` の配線 (repo 慣行) |
| AC-C01-6 | combinators = with-goal-seek / with-feedback-contract、goal_seek = inline / subagent / 5 | inventory `C01.combinators` / brief `goal_seek` |
| AC-C01-7 | feedback_contract に IN1 (inner/script) / OUT1 (outer/test) / OUT2 (outer/test) | inventory `C01.feedback_contract.criteria` |
| AC-C01-8 | 必須セクション: Purpose & Output Contract / ゴールシーク実行 (6 サブ節) / Criteria acceptance / Gotchas | repo の run 系 SKILL.md 骨格 |
| AC-C01-9 | `## Criteria acceptance` が IN1 / OUT1 / OUT2 すべてに言及 | 同上 + inventory criteria |
| AC-C01-10 | `deterministic_checks` の 7 script が `script_refs` にあり、参照パスが実在する | brief `deterministic_checks` |
| AC-C01-11 | R21 必須ヒアリング 5 項目が過不足なく宣言され `required` と `question_ja` を持つ | brief `hearing_required_items_r21.items` (**C01 が唯一の項目定義**) |
| AC-C01-12 | `target_tasks` は `min_count: 1`、`checked_by` が C12 `E-TARGET-TASKS-EMPTY` を指す | RESOLUTION-R21 C58 / brief 同項目 |
| AC-C01-13 | `must_remember` と `no_need_to_remember` の相互 `paired_with`、`max_count: 2`、`E-REMEMBER-PAIR` | RESOLUTION-R21 C57 / brief 同項目 |
| AC-C01-14 | `presentation_order` をヒアリング項目にしない。導出は C12 `CR-PRESENTATION-ORDER`。提示順を尋ねる質問文を持たない | brief `presentation_order_is_not_a_hearing_item` / RESOLUTION-R21 |
| AC-C01-15 | ゲート 4 状態集約を自前で持たない。`/handout-verify` (C09) 経由で `CR-GATE-AGG` へ委譲し「再実装しない」と宣言。`not-run` を pass へ畳む記述を持たない | **P03 Y-07** / brief R4-verify |
| AC-C01-16 | `handout-config.json` と `assets/` の配置は C19 (`--place-config` / `--assets-src`)。自分で書く記述を持たない | **P03 Y-04** / brief R4-verify |
| AC-C01-17 | `README.md` の writer は C01 で、原題 / 目的 / 適用プリセット / 同梱物一覧 / 使い方 の 5 節を宣言 | brief `readme_writer` |
| AC-C01-18 | `depends_on` に C03 を含み、読みやすさ判定を `assign-handout-readability-evaluator` へ委譲 | **P03 Y-09** / brief `boundary` |
| AC-C01-19 | 検証済み構成データ直渡しの非対話経路を塞がない | brief `boundary` / R1-elicit |
| AC-C01-20 | HTML の組み立ては決定論 script へ委譲し「LLM で書かない」 | brief `boundary` |
| AC-C01-21 | Purpose & Output Contract に同梱 4 点と生成レポート 4 要素 (適用部品 / 埋め込みサイズ / warning / ゲート結果) | brief `output_contract` |
| AC-C01-22 | allowed-tools が Read / Write / Bash を含む | brief `deterministic_checks` (Bash 起動) + `readme_writer` (Write) からの導出 |
| AC-C01-23 | `output_language: ja` | brief `output_language` |
| AC-C01-24 | `source` が `component-inventory.json#C01` を指す | repo の SKILL.md 慣行 (追跡性) |

## 非受入例 (reject fixture) と落ちるべき契約 id

`reject_cases.py` の 16 件 + `test_contract_checker.py` 内の 3 件 (SKILL.md 欠落 /
prompt ファイル欠落 / 参照 script 実体欠落)。責務境界に関する主な非受入例:

| ケース | 注入する違反 | 落ちる契約 |
|---|---|---|
| `gate-aggregation-reimplemented` | 4 状態分類を C01 が自前で行うと書く | AC-C01-15 |
| `not-run-folded-into-pass` | not-run を pass とみなして進むと書く | AC-C01-15 |
| `config-placed-by-self` | handout-config.json / assets/ を自分で配置すると書く | AC-C01-16 |
| `presentation-order-asked` | 提示順をヒアリング項目に足す | AC-C01-14 |
| `target-tasks-min-count-zero` | target_tasks を 0 件でも可にする | AC-C01-12 |
| `remember-pair-broken` | 覚える / 覚えなくてよい の対を崩す | AC-C01-13 |
| `c03-dependency-dropped` | depends_on から C03 を外す | AC-C01-18 |
| `extra-responsibility-added` | 自作の自己レビュー責務 R5 を足す | AC-C01-4 |
| `html-written-by-llm` | HTML を skill が直接書くと書く | AC-C01-20 |

## 3 面の担当 (どのファイルのどのテストが何を見ているか)

| 面 | 担当 |
|---|---|
| 違反系入力で落ちる | `reject_cases.py` + `test_contract_checker.py::TestRejectFixtures` / `test_predicate_scope.py::PredicateSinglePointRejectabilityTest` (1 点注入) |
| 委譲 argv と exit code 契約 | `test_argv_and_reproducibility.py::DelegationArgvContractTest` |
| 再現性 | `test_argv_and_reproducibility.py::CheckerReproducibilityTest` / `::Out2RegenerationInvariantTest` |

skill component は自身が argv を受けて exit code を返すわけではないため、
この 2 面は次の対応物として定義した。

- **argv**: SKILL.md が決定論 script の名前の隣に書いたフラグは、その script の
  argparse に実在しなければならない (宣言はあるが受け口が無い型を落とす)。
- **exit code**: 0/1/2 → pass/fail/error の意味づけの正本は C09 の CR-GATE-AGG
  であり、C01 はそれを再定義しない (再定義していたら赤)。
- **再現性**: (1) 判定器が同一入力に対し同一の違反列を返すこと (同プロセス 2 回 +
  別プロセス 2 回)、(2) 契約としての再現性 = OUT2 (同梱構成データからの 2 回生成で
  バイト一致) を壊さないための宣言、すなわち R5-refine が生成済み HTML の直接編集を
  禁じ決定論経路で作り直すと書いていること。

## 正本リテラルを写さない方針

`contract_lib.py` の値域・件数は `skill-brief-C01.json` と
`component-inventory.json#C01` から import 時に実測で導出する (読めなければ
`RuntimeError` で fail-closed)。とくに `goal_seek.max_loops` は F-C06-04 で
C01 goal_seek を唯一の owner に畳んだ経緯があるため、テスト側・reject fixture 側
(`reject_cases.py` / `test_predicate_scope.py`) の注入文字列も正本から組み立てる。
`test_argv_and_reproducibility.py::NoLiteralCopyOfCanonTest` がこの退行を検出する。

`fixtures/accept/.../SKILL.md` は SKILL.md の例示なので具体値を持つ。正本の値が
変わればこの fixture は AC-C01-6 で赤くなる (黙って古くなるのではなく落ちる)。

## acceptance_criterion 後半について

「build_target が未実装の時点で実行すると失敗する」は、実装が既に存在するため
**現物では再現できない**。実装を削除して測ることは禁止されているので、
`UnimplementedBuildTargetSurrogateTest` が空ディレクトリを build_target と見立てて
判定器の挙動 (AC-C01-1 で停止する) だけを固定している。これは代理であって
現物での再現ではない。

## P05 実装者への注意

- テストを緑にするために `contract_lib.py` / `reject_cases.py` / `fixtures/` を
  書き換えないこと。契約を変えたい場合は先にブリーフ (正本) を変える。
- `fixtures/accept/skills/run-handout-build/SKILL.md` は契約を満たす形の
  **例示**であり実装ではない。文面をそのまま流用しても契約は満たすが、
  資料生成の中身 (手順・prompts) は別途書く必要がある。
