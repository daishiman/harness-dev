# elegant-review レポート: ubm-goal-setting（scope_mode=plugin）

- run: `run-20261103-reset-cascade`
- 対象: `plugins/ubm-goal-setting`（ワークツリー上の未コミット変更 0.9.2〜0.9.3 を含む）
- 反復: 分析 loop0〜loop5、改善 iter1〜iter6（max_iter=3 を超えている）
- status: **incomplete**（最後の分析 loop5 で4条件に FAIL が残った。force_pass はしない。human_review で判断を待つ）
- 30思考法: 各 loop で30件すべて使用、skip 0（`validate-paradigm-coverage.py --strict-signal` で確認）
- 検証: findings.schema.json に適合、`--phase-order` rc=0、`verdict.json` は `build-verdict.py` で loop5 の findings から導出

## 4条件の推移

| 条件 | loop2 | loop3 | loop4 | loop5 | 判定（loop5） |
|---|---|---|---|---|---|
| C1 矛盾なし（contradiction） | 13 | 6 | 4 | 5 | FAIL |
| C2 漏れなし（omission） | 7 | 4 | 9 | 6 | FAIL |
| C3 整合性あり（inconsistency） | 9 | 4 | 8 | 5 | FAIL |
| C4 依存関係整合（dependency_break） | 2 | 2 | 2 | 3 | FAIL |
| 違反の合計 | 31 | 16 | 23 | 19 | – |
| smell（警告） | – | 4 | 5 | 4 | – |

loop4 で増えたのは、確定事項 M〜T（売上を根本で追う・G を全層の大前提にする・月報の最重要数字に売上の行など）で規則を足したため。loop5 で減り、2周続けて増える発散は起きていない。

## iter6（loop5 の23件への対応）

ユーザーの承認（2026-11-03）: A「判定と聞き取りにも伝える」、B「役割を分けて両方直す」、D「質問を分けて3問以内にする」、進め方「直して修正箇所だけ独立確認」。

| 論点 | 対応の要点 |
|---|---|
| 1年だけが初回 | 前年の1年目標は無いが期報・月報はある場合を、G・R1 7.1・R3 3C-2・goal-reviewer 項目6・報告テンプレート・R5 に通した |
| 現在地 | 到達点（月間売上）と比べる現在地は直近の月商。累計は `period_sales_cumulative` の1つの値を添えるだけで、足し上げない。「積み上げ」の呼び方を外した |
| 対話の材料 | 前回 YES をくれた相手の名前はフィールドを持たず、R1 → R3 3C-2 へ対話の材料として渡す |
| 問いの数 | 1ターン4問以上を「（1回目）」「（2回目）」に分けた。数え方の正本は CONST_001。`tests/test_turn_question_limit.py` で回ごとに検査 |
| 判定の文 | 連続の判定の結果の文を G に置き、goal-reviewer・報告テンプレート・R5 は G に従う（当てはまるものを併記） |
| validator・手本・テスト | 最重要数字の売上の行で行頭の記号を読み飛ばす。週報の手本と fixture を「今週の売上＋人数・件数」の形に。月報 fixture に売上の行 |
| 写しの削減 | data-contract の層別表の最重要数字の行を、共通部品F への参照にした |

詳細は `phase3-plan-iter6.md`、差分は `iter6.diff`（18ファイル＋新規テスト1件）。

## 独立確認（修正箇所だけ / 改善した context とは別の担当）

1. 1回目: **FAIL**。23件のうち22件は解消、#15 は部分解消。新しい指摘 A〜F（info-collector の受け渡し欄、「直近の期報・月報」の定義、R3 の語、番号の無い確認の数え方、週報 fixture、人数でまとめた項目の名前）。6件とも直した。
2. 2回目（A〜F の修正だけ）: **FAIL**。A・B・C・E・F は解消、D は部分解消（CONST_001 の文とテストの数え方のずれ）。新しい指摘は medium 2件・low 7件。D の仕上げ（CONST_001 に除外の行を明記、R5 ターン5C を「親が確かめ、当てはまらない項目だけを3問まで尋ねる」形に、導入の2文目から数える、期報ターン6 の印）と、小さな2件（G の読み先を管理用の節に、R2 入力契約に直近の月商）を直した。残る4件は下の「残り」へ。
3. 3回目は行わない。2回目のあとに直した箇所は、別の担当の確認を経ていない（`phase3-plan-iter6.md`）。

## テスト

`python3 -m pytest -q plugins/ubm-goal-setting/tests`: **1287 passed**（独立確認2回目のあとの修正まで含めた最終の状態。iter6 の前半の修正後は 1286 passed で、差の1件は `test_counter_counts_unnumbered_confirmation`）。

## 根本原因

loop3 で見つけた型が続いている。**正本（G・data-contract・CONST）に規則を足すと、適用先（発話テンプレート・受け渡しの欄・判定する側・手本・fixture・検査）のどこか1か所に降りない。** iter6 の独立確認の A（取得範囲は足したが出力の欄が無い）と D（規則の文は足したが数え方が検査とずれた）も同じ型だった。

文言の grep では、この切れ目を見つけられない。効いたのは、規則を機械検査にしたものだった。

- `tests/test_turn_question_limit.py`: 1回の発話の問いの数（CONST_001）
- `tests/test_field_closure.py`: フィールドの「集める問い → 出力する層」の閉包
- `validate-goal-output.py` の売上の行の照合: 最重要数字の売上と、その層の売上目標の一致

## 残り（bd issue の候補）

- 独立確認2回目の残り: 継続コンサル人数の「現在」の値の受け渡し（medium。R2:182・191 の `{{現在の人数}}` の出所）、「直近」の上限（1年の期間の開始日より前）、info-collector の実行フロー表の完了条件、`test_build_journal_context.py:137` の古い行動行
- 以前からの残り: W の欠落6件、引用上限の単位、(d) の限界と語の表、R1 5.3、plugin-fingerprints の更新、期報だけの7変数、#17 decision_criteria、月報の完全な fixture
- 回の分割が対話の時間（週報5〜8分など）に与える影響を、実走で観察する

## 承認

proposer ≠ approver。改善した context は自分の修正を承認していない。修正箇所の確認は別の担当が行った（上の「独立確認」）。4条件の再判定（loop6）は max_iter を超えるため行わず、human_review で続けるかを判断する。
