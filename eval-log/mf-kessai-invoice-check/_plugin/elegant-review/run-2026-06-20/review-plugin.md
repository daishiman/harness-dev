# elegant-review レポート — mf-kessai-invoice-check (plugin scope)

- run-id: run-2026-06-20
- 検証パラダイム: 30 思考法 (3 SubAgent 並列ファンアウト) × 4 条件
- 起点: ユーザー改善要望「毎月のNotion上書きで過去月の完了/未完了が失われる懸念。履歴を残す仕組み(ページ本文 or プロパティ)を検討。矛盾・認識不足の確認も」
- 最終 verdict: **矛盾なし=PASS / 漏れなし=PASS / 整合性あり=PASS / 依存関係整合=PASS**
- 承認: 独立 context (proposer≠approver) が REQUEST_CHANGES(G5) を指摘 → 修正 → APPROVE

## 最重要結論: ユーザーのご懸念は「実装済み」で不成立

「毎月上書きで過去月が失われる」という懸念は、**既に実装済みの仕組みにより成立しません**。3 analyst が独立に同一結論へ収束しました。

| ご懸念 | 実態 | 根拠 |
|---|---|---|
| 毎月上書きで過去月が消える | upsertキーが `顧客ID×対象年月` なので**月ごとに別行**。上書きされない | notion_invoice_sink.py:52-64 |
| 完了した月の記録が残らない | `__monthly_summary__×対象年月` の**月次サマリ行**で候補0件月も「確認済み」を記録 | :139-156 |
| 過去の確認情報が残らない | **ページ本文に実行履歴を毎回追記**し過去証跡を消さない | _append_audit:104-132 |
| プロパティ vs ページ本文どちらが良い? | **両方実装済みで役割分担** (プロパティ=最新スナップショット/絞り込み用、本文=累積履歴/監査ログ) | README:198 |

→ 真の課題は「実装欠落」ではなく **「実装済みであることと過去月の見方が運用者に伝わっていない」という文書/可視化の omission**。

## プロセス

1. **Phase1 思考リセット・俯瞰**: 全関連ファイルを fresh read → `shared_state.md`(200字)。先行context(前回6/19結論)に引きずられず再検証。
2. **Phase2 並列多角分析**: 論理構造(10)/メタ発想(9)/システム戦略(11) の3 SubAgent が独立に30思考法を適用。3 context が「認識ギャップ」「件数プロパティ欠落」に独立収束=二段確認成立。
3. **改善スコープ確認**: outward-facing な Notion DB スキーマ変更を含むためユーザー承認 → **フルセット(A〜D)** を選択。
4. **Phase3 改善**: 2 executor を並列(core=schema/sink/test, doc=README/SKILL)、ファイル分担で衝突回避。
5. **承認**: 独立 context(general-purpose) が4条件検証 → README プロパティ数の追従漏れ(G5)を発見 → 修正 → 4条件全PASS。
6. **配線**: `make sync` で `.claude/` へ4件symlink反映(プラグインを実際に呼べる状態に)。

## 解消した改善ポイント (5 findings)

| # | severity | 内容 | 解消 |
|---|---|---|---|
| G1 | omission | 過去月の見方ガイド + Claude Codeへの頼み方(プロンプト例)が文書に不在 | README『過去月の状態を確認する』Q&A節 +『Claude Codeへの頼み方』対応表 + SKILL観測軸 |
| G2 | omission | 月次サマリ件数が _props 未マッピングでテーブル非表示(本文限定) | schema数値列3つ(発行漏れ件数/金額変動件数/チェック件数合計)+ _props マッピング + test |
| G3 | dependency_break | 『継続発行』が画面(全件N)とサマリ(金額変動M)で別定義・同ラベル(N≠M) | sinkラベル明示『金額変動』+ collect画面で全件/変動を分離表示 |
| G4 | smell | ページ本文が同月再実行で単調増加(run_id重複追記の歯止め無し) | _has_run_id_block で同一run_id既存なら追記スキップ(真の冪等化・既存履歴非破壊) |
| G5 | contradiction | README の verify実行例が旧プロパティ数『全16』(件数3列で19へ追従漏れ) | 16→19 修正(承認者=独立contextが発見) |

## ユーザー要望への対応マッピング

- (a) ページ本文に「いついつ確認済み」を追記 → **元から実装済**(_append_audit) + G4でrun_id冪等化
- (b) プロパティに直近完了月/件数 → 確認済み日時/チェック実行IDは**元から実装済**。G2で**件数(発行漏れ件数等)もテーブル一覧可能に**
- (c) テーブルに直近の完了月 → 月次サマリ行(対象年月別)で**元から実装済**。G2で件数も可視化
- プロパティ vs ページ → **両方が役割分担で正解**(G1でREADMEに明示)
- 「入力方法がわからない」(追加要望) → G1で『Claude Codeへの頼み方』対応表(自然言語の一言→コマンド)を新設

## 30 思考法カバレッジ

全30種使用 (skip 0)。A2 論理構造10 / A3 メタ発想9 / A4 システム戦略11。3 context が独立適用。

## 検証ログ

- pytest: 32 passed (件数プロパティ検証 + run_id冪等テスト test_append_audit_idempotent_skips_existing_run_id 新規含む。ベースライン31→32)
- 件数列名「発行漏れ件数」: schema(properties+fact_columns)/sink._props/test/R4-sink.md/db-setup SKILL の7ファイル一致
- DBプロパティ数: 19 (fact 15 + managed 4) で README/verify 整合
- 全 .py compile OK / 全 .json 妥当
- `.claude/` 反映: make sync で created=4(run-mf-invoice-check/db-setup/ref-mf-kessai-api + mfk-gap-verifier)、sync-check drift 0
- ロールバック: pre-phase3-backup.tgz(55287 bytes) 退避済

## 残課題 (非ブロッキング)

- G4の本文冪等は「同一run_id」基準。**別run_id(別日の再チェック)は履歴として正しく残る**(監査ログの意図通り)。件数プロパティ化(G2)で「最新は本文を開かず確認」できるため、本文肥大の主な弊害は緩和済。
- 未チェック月の能動的列挙(`--missing-months`相当)は今回スコープ外(将来任意)。月次サマリ行の有無で目視判別は可能。
