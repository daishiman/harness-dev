# 述語スコープ方針 (contract_lib の AC 述語と reject 可能性)

対象: `plugins/guide-doc-generator/tests/run-handout-build/contract_lib.py` の `check_skill`
出典タスク: `plugin-plans/guide-doc-generator/task-specs/P05-x-17.md` (`P05-x-14` が発見した潜在欠陥)

## 1. 問題

`reject_cases.py` の違反注入は単一の `(old, new)` ペアであり、`test_contract_checker.py`
の `_materialize` は `text.count(old) == 1` を assert している。つまり reject fixture の
設計思想は「受入 fixture の **1 箇所だけ**を潰して違反状態を作る」である。

一方 `contract_lib` には本文 (`body`) 全体への部分文字列一致で成否を決める述語がある。
同じ語が本文の別箇所にも現れる場合、宣言を消しても述語は満たされたままになり、
reject fixture が違反状態にならない。テストは「落ちるべき id が出ていない」ではなく
「落ちるべき id が出ている」だけを見ているので、これは**偽緑**として素通りする。

## 2. 述語の列挙とスコープ分類 (実測)

列挙元は `contract_lib.py` 中の `Violation("AC-C01-*")` 発生箇所 (正規表現
`Violation\(\s*\n?\s*"(AC-C01-\d+)"` による静的走査。件数は本文に手書きせず走査から導出)。

| 判定スコープ | 発生箇所数 | 内訳 (代表) |
| --- | --- | --- |
| frontmatter の値・構造 | 33 | identity / responsibilities / criteria / hearing 項目 / allowed-tools 等 |
| 参照ファイルの実在 | 3 | AC-C01-1 (SKILL.md) / AC-C01-5 (prompts) / AC-C01-10 (scripts) |
| 本文の見出し行一致 | 2 | AC-C01-8 (必須セクション / サブセクション) |
| 節スコープ | 6 | AC-C01-9 (`## Criteria acceptance`) / AC-C01-19 (非対話節) / AC-C01-21 (`## Purpose & Output Contract`) |
| 宣言行スコープ | 4 | AC-C01-17 (README writer 行) / AC-C01-20 (LLM 委譲宣言行) |
| 本文全体への存在要求 | 6 | AC-C01-14 CR-PRESENTATION-ORDER / AC-C01-15 `/handout-verify`・CR-GATE-AGG・再実装しない / AC-C01-16 フラグ 2 種 / AC-C01-18 assign-handout-readability-evaluator |
| 本文全体への禁止要求 (加算型) | 4 | AC-C01-14 質問文 / AC-C01-15 not-run→pass・4 状態自前列挙 / AC-C01-16 自前配置行 |
| 合計 | 58 (契約 id 24 種) | |

このうち偽緑の危険があるのは「本文全体への**存在**要求」だけである。
禁止要求 (加算型) は違反注入が 1 行の**追加**なので、他箇所の語の有無に依存しない。
frontmatter・ファイル実在・見出し行一致・節スコープの述語も、注入点が一意に定まる。

## 3. 単一箇所注入で発火するかの機械的確認

`test_predicate_scope.py` が確認する。手順は `test_contract_checker._materialize` と同一
(`fixtures/accept` 全体を temp へ `copytree` し `SKILL.md` だけ差し替えて
`check_skill(skill_dir)` を呼ぶ。`prompts/` を欠いた不完全ツリーでは別の AC が発火して
結論を誤るため、必ずツリー全体を複製する)。

- 変異は 58 の発生箇所すべてを覆い、定数リストで回る述語 (7 script / 5 ヒアリング項目 /
  10 見出し / 3 criteria など) は要素ごとに 1 変異を持つ。総変異数は
  `test_predicate_scope.MUTATIONS` の長さとして機械的に得られる (現状 122)。
- 変異は `sub` (SKILL.md の 1 箇所置換、`text.count(old) == 1` を assert) か
  `delfile` (参照ファイル 1 個の削除) のみ。複数箇所の同時置換は使わない。
- `test_every_violation_site_has_a_mutation` が、契約 id 集合の一致と
  「発生箇所数 <= 変異数」を要求する。述語を増やして変異を足し忘れると赤になる。
- `BodyWidePredicateScopeTest` が、本文側述語の語が**判定スコープ内で一意**である
  ことを受入 fixture に対して固定する。将来 fixture が語を散らした瞬間に赤になる。

## 4. 確認できなかった述語と採った方針

方針の選択肢は (A) 検出条件を節/宣言行スコープへ寄せる、(B) `REJECT_CASES` を複数置換
対応にする、の 2 つ。**(B) は退ける。** `_materialize` の `text.count(old) == 1` は
「1 箇所だけ違反を注入する」という reject fixture の不変条件そのものであり、複数置換対応
はこの不変条件を壊す (P05-x-14 と同じ判断)。したがって全件 **(A)** を採った。

| 契約 id | 元の述語 | 受入 fixture 上の残存数 | 採用方針 | 変更後のスコープ |
| --- | --- | --- | --- | --- |
| AC-C01-17 | `"README.md" not in body` | body に 2 (同梱物一覧 + writer 宣言) | (A) | `README.md` を含み書き込み動詞 (`WRITE_VERBS`) を含む行 |
| AC-C01-17 | `sec not in body` (README 5 節) | `目的` が body に 2 (`### 目的・背景 (Why)` 見出しと 5 節宣言) | (A) | 同上 (writer 宣言行) |
| AC-C01-20 | `"決定論" not in body` | body に 3 (委譲宣言・完了チェックリスト等) | (A) | `LLM で書かない` を含む宣言行 |

いずれも**判定は狭くなる方向にしか動かない** (本文のどこかに語があれば通る → 宣言行に
無ければ落ちる) ので、既存 assert の緩和には当たらない。受入 fixture と実装
`plugins/guide-doc-generator/skills/run-handout-build/SKILL.md` はどちらも変更後の述語を
そのまま満たす (本文修正は不要だった)。

対応する reject case を `reject_cases.py` へ追加した。

- `readme-writer-handed-to-c19` (AC-C01-17): writer 宣言を C19 へ譲る。同梱物一覧の
  `README.md` は残るため、旧述語では発火しなかった。
- `readme-section-mokuteki-dropped` (AC-C01-17): 5 節から `目的` だけを落とす。
  `### 目的・背景 (Why)` が残るため、旧述語では発火しなかった。
- `deterministic-delegation-dropped` (AC-C01-20): 決定論委譲の宣言だけを落とす。
  完了チェックリストに `決定論` が残るため、旧述語では発火しなかった。

### 本文全体一致のまま残した述語

AC-C01-14 (`CR-PRESENTATION-ORDER`)、AC-C01-15 (`/handout-verify` / `CR-GATE-AGG` /
`再実装…しない`)、AC-C01-16 (`--place-config` / `--assets-src`)、AC-C01-18
(`assign-handout-readability-evaluator`) は、受入 fixture 上で語が本文に 1 回しか現れず、
単一箇所注入で違反状態を作れることを実測した (task-spec が「AC-C01-15 の CR-GATE-AGG /
AC-C01-18 の assign-handout-readability-evaluator 等」を偽緑候補として挙げていたが、
実測ではこれらは現時点で単一箇所注入が成立している)。これらは節や宣言行という自然な
スコープを本文構造から一意に決めにくい (該当の語が節見出しに現れない) ため、スコープを
狭めるより `BodyWidePredicateScopeTest` の一意性固定で守る方を採った。**受入 fixture で
語が 2 回以上現れるようになった時点でテストが赤になり、その時に (A) を適用する**という
運用である。

なお実装側 `SKILL.md` の本文では `assign-handout-readability-evaluator` が 2 回、
`/handout-verify` が 3 回、`README.md` が 3 回、`決定論` が 5 回現れる。reject 可能性は
受入 fixture に対する性質なので実装側の重複は偽緑を生まないが、「語が散る」現象は
実装側で実際に起きている。上記の一意性テストがその波及を受入 fixture 側で止める。

## 5. 変更したファイル

- `contract_lib.py`: AC-C01-17 / AC-C01-20 を宣言行スコープへ変更
- `reject_cases.py`: 上記 3 ケースを追加
- `test_predicate_scope.py`: 新規。全発生箇所の単一箇所注入と、本文側述語の
  スコープ内一意性を機械的に固定する
- `PREDICATE-SCOPE-POLICY.md`: 本ファイル
