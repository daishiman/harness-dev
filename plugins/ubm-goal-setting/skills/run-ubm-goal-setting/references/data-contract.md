# UBM目標設定 エージェント間データ契約

Phase間のデータ受け渡し仕様を定義するドキュメント。
各エージェントはこの契約に従ってデータを生成・消費する。

---

## Phase間データフロー図

```
Phase 0 ──[GoalConfig]──> Phase 1-2 ──[PastSummary]──> Phase 3 ──[InterviewData]──> Phase 4 ──[FormattedOutput]──> File
(目標種別確認)          (info-collector)             (phase3-coordinator)         (output-formatter)          (05_Project/UBM/目標設定/)
```

| 契約名 | 生産者 | 消費者 | データ形式 |
|--------|--------|--------|-----------|
| GoalConfig | Phase 0（メインフロー） | info-collector | 構造化テキスト |
| PastSummary | info-collector | phase3-coordinator | マーク付き構造化サマリー（文脈フィールド継承を含む。§2.8） |
| InterviewData | phase3-coordinator | output-formatter | 構造化テキスト（全35フィールド） |
| FormattedOutput | output-formatter | ファイルシステム | Markdown ファイル |

---

## 1. GoalConfig（Phase 0 → Phase 1-2）

Phase 0 でユーザーから取得し、info-collector SubAgent に渡すパラメータ。

| フィールド | 型 | 必須 | 説明 | 例 |
|-----------|-----|------|------|-----|
| goal_type | enum: `weekly` / `monthly` / `bimonthly` | Yes | 目標種別 | `weekly` |
| target_period | object: `{start: date, end: date}` | Yes | 対象期間（YYYY-MM-DD形式） | `{start: 2026-03-30, end: 2026-04-05}` |

### バリデーション

- `goal_type` は3つの列挙値のいずれかであること
- `target_period.start` < `target_period.end` であること
- 日付はYYYY-MM-DD形式であること

### 取得方法

- コマンド引数で指定されている場合: そのまま使用
- 未指定の場合: AskUserQuestion で1ターンで取得

---

## 2. PastSummary（Phase 1-2 → Phase 3）

info-collector SubAgent が返す構造化サマリー。全項目に `[自動取得]` / `[要ヒアリング]` マークを付与する。現在の月報/期報から継承した文脈フィールド10種（inherited_context・§2.8）を含み、週報の自動継承元となる。

### 2.1 トップレベル構造

| フィールド | 型 | 説明 |
|-----------|-----|------|
| user_info | object | ユーザー基本情報 |
| prev_goals | object[] | 過去目標の配列（取得スコープに応じた件数） |
| inherited_context | object / null | 現在の月報/期報から継承した今期文脈（週報の自動継承元）。詳細は §2.8 |
| pattern_analysis | object / null | パターン分析（複数期間データがある場合） |
| camp_data | object / null | 合宿データ（最新のもの） |
| knowledge_hits | object[] | ナレッジ検索結果 |
| ubm_root_files | string[] | UBMルート直下の関連ファイル一覧 |
| data_marks | object | 各項目の `[自動取得]` / `[要ヒアリング]` マーク集約 |

### 2.2 user_info

| フィールド | 型 | マーク | 説明 |
|-----------|-----|--------|------|
| name | string | [自動取得] / [要ヒアリング] | ユーザー名 |
| business | string | [自動取得] / [要ヒアリング] | 事業内容 |
| phase | enum: `0→1` / `1→10` / `10→100` | [自動取得] / [要ヒアリング] | 事業フェーズ |
| type | enum: `店舗` / `無形` | [自動取得] / [要ヒアリング] | ビジネス形態 |
| prev_sales | number / null | [自動取得] / [要ヒアリング] | 顧問参加前月商 |
| last_camp | date / null | [自動取得] / [要ヒアリング] | 直近合宿参加日 |

### 2.3 prev_goals（配列の各要素）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| period | string | 対象期間 |
| goal_type | enum | 目標種別（週報/月報/期報） |
| sales_target | number / null | 売上目標 |
| sales_actual | number / null | 売上実績（[要ヒアリング]の場合あり） |
| other_target | string / null | 成果目標 |
| other_actual | string / null | 成果実績（[要ヒアリング]の場合あり） |
| action_targets | string[] | 行動目標の一覧 |
| action_results | string[] / null | 行動実績（[要ヒアリング]の場合あり） |

### 2.4 pattern_analysis（複数期間データがある場合）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| sales_trend | string | 売上推移の傾向 |
| recurring_issues | string[] | 繰り返されている課題 |

### 2.5 camp_data

| フィールド | 型 | 説明 |
|-----------|-----|------|
| date | date | 合宿日 |
| freshness_mark | enum | `[自動取得]`: 3ヶ月以内 / `[鮮度注意]`: 3ヶ月超 / `[要ヒアリング]`: データなし |
| business_direction | string | 事業方針 |
| camp_actions | string[] | 具体的アクション |
| camp_challenges | string[] | 克服すべき課題 |
| camp_targets | string / null | 数値目標 |

#### freshness_mark の判定ロジック

| 条件 | マーク | Phase 3 での扱い |
|------|--------|-----------------|
| 合宿日が現在から3ヶ月以内 | `[自動取得]` | Step 5 で整合性チェックを実行 |
| 合宿日が現在から3ヶ月超 | `[鮮度注意]` | 参考情報として扱い、目標方針の更新要否を確認 |
| 合宿ファイルが存在しない | `[要ヒアリング]` | 合宿整合性チェックをスキップ。代替として北原原則整合性チェック（ターン5C）を実行 |

### 2.6 knowledge_hits（配列の各要素）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| id | string | ナレッジエントリID |
| category | string | カテゴリ（principles/consultation/phase/action/transformation/case） |
| content | string | 抽出内容 |
| tags | string[] | タグ |
| applicable_when | string | 適用場面 |

### 2.7 data_marks

各セクションの取得状況を集約したマップ。Phase 3 はこの情報で質問対象を決定する。

| キー | 値の型 | 説明 |
|------|--------|------|
| user_info | `[自動取得]` / `[要ヒアリング]` | 基本情報の取得状況 |
| prev_goals | `[自動取得]` / `[要ヒアリング]` | 過去目標の取得状況 |
| camp_data | `[自動取得]` / `[鮮度注意]` / `[要ヒアリング]` | 合宿情報の取得状況 |
| knowledge | `[自動取得]` / `[取得不可]` | ナレッジの取得状況 |

### 2.8 inherited_context（継承文脈10種）

info-collector が「現在の月報/期報」から抽出し、週報の自動継承元となる今期文脈。週報は新規ヒアリングを行わず、この値を表示・確認して必要時のみ上書きする（所要時間5-8分維持）。月報・期報はフル elicitation で確定する。全項目に `[自動取得]` / `[要ヒアリング]` マークを付与する。

各フィールドの型は InterviewData の文脈フィールド（#22-31）と一致させる。

| フィールド | 型 | マーク | 説明 | InterviewData対応 |
|-----------|-----|--------|------|------------------|
| period_sales_target | number | [自動取得] / [要ヒアリング] | 今期の売上目標（期アンカー・全レベル同値） | #22 |
| period_sales_cumulative | number | [自動取得] / [要ヒアリング] | 今期の累計売上実績（期アンカー・週次更新） | #23 |
| business_partner_count | number | [自動取得] / [要ヒアリング] | 現在事業パートナー数（スナップショット） | #24 |
| grid_partner_count | number | [自動取得] / [要ヒアリング] | 現在のグリッドパートナー数（スナップショット） | #25 |
| grid_partner_goal | number / null | [自動取得] / [要ヒアリング] | グリッドパートナー目標数（スナップショット）。未設定時は null | #26 |
| last_academy_date | date / null | [自動取得] / [要ヒアリング] | 前回のアカデミーへの参加日（スナップショット） | #27 |
| next_academy_date | date / null | [自動取得] / [要ヒアリング] | 次回のアカデミーへの参加日（スナップショット） | #28 |
| next_sparring_date | date / null | [自動取得] / [要ヒアリング] | 次回の壁打ち予定日（スナップショット） | #29 |
| sparring_target_state | string | [自動取得] / [要ヒアリング] | 次回の壁打ち予定月までに目指している状態（スナップショット） | #30 |
| sparring_deliverables | string | [自動取得] / [要ヒアリング] | 次回の壁打ち予定日までに達成させること（スナップショット） | #31 |

- 継承供給源: weekly は『現在の月報』、monthly/bimonthly は『現在の期報』から抽出する。取得不可は `[要ヒアリング]` を付与する。
- `grid_partner_goal` は number / null（#26 と一致）。専用出力セクションは持たず、文脈・行動目標へ反映する。
- `period_sales_cumulative` のみ週報でも必須で、当該週時点の累計実績に週次更新する（継承値の更新が前提）。
- 種別別の必須/任意/継承度は §3.1.3 マトリクスに従う。

### バリデーション（Phase 1-2 完了時）

- 全セクションに `[自動取得]` または `[要ヒアリング]` マークが付いていること
- `[自動取得]` の数値データが半角数字であること
- prev_goals が goal_type の取得スコープに合致する件数であること
- camp_data の freshness_mark が3つの列挙値のいずれかであること

---

## 3. InterviewData（Phase 3 → Phase 4）

phase3-coordinator が全5Stepのヒアリングで収集し、output-formatter に引き渡す構造化データ。

### 3.1 全35フィールド一覧

| # | フィールド | 型 | 説明 | 取得Step | 必須 | 備考 |
|---|-----------|-----|------|---------|------|------|
| 1 | name | string | ユーザー名 | Step 1 | Yes | |
| 2 | business | string | 事業内容 | Step 1 | Yes | |
| 3 | phase | enum: `0→1` / `1→10` / `10→100` | 事業フェーズ | Step 1 | Yes | |
| 4 | type | enum: `店舗` / `無形` | ビジネス形態 | Step 1 | Yes | |
| 5 | prev_sales_target | number | 前回売上目標 | Step 1 | No | 初回の場合は null |
| 6 | prev_sales_actual | number | 前回売上実績 | Step 1 | No | 初回の場合は null |
| 7 | prev_sales_diff | string | 売上差分（+/-付き半角数字） | Step 2 | No | 初回の場合は null。例: `+50000`, `-300000` |
| 8 | prev_other_target | string | 前回成果目標 | Step 1 | No | |
| 9 | prev_other_actual | string | 前回成果実績 | Step 1 | No | |
| 10 | root_cause | string | 差分の根本原因 | Step 2 | No | 初回または目標達成時は null |
| 11 | bottleneck | string | ボトルネック箇所 | Step 2 | No | 「商品作り→外交→商談→成約→フォロー」のいずれか |
| 12 | sales_target | number | 今回売上目標 | Step 3 | Yes | 半角数字のみ |
| 13 | other_targets | string[] | 今回成果目標（複数可） | Step 3 | Yes | |
| 14 | action_daily | string[] | 毎日の行動目標 | Step 4 | Yes | 数値・期日・物理的行動を含むこと |
| 15 | action_period | string[] | 期間内の行動目標（期日付き） | Step 4 | Yes | 数値・期日・物理的行動を含むこと |
| 16 | not_doing | string[] | やらないこと | Step 4 | Yes | 3つ以上 |
| 17 | decision_criteria | string | 判断基準（1文） | Step 4 | Yes | Yes/No で判定可能なこと |
| 18 | projects | object[] | プロジェクト別タスク（先方担当者・期日・提出先/宛先・対象物/行動・済/未済） | Step 4 | 種別依存 | 月報=必須／週報=任意（既定省略・方式2）／期報=出力しない。2階層まで。粒度は粗くてOK。出力はチェックリスト形式 |
| 19 | habit_check | object / null | 習慣目標（30分切替・分散・粗い粒度の3原則）。週報のみ必須 | Step 4 | weekly のみ Yes | 月報・期報では null |
| 20 | camp_alignment | object / null | 合宿整合性チェック結果 | Step 5 | No | camp_data が null の場合は null |
| 21 | behavior_change | string | 前回からの行動変化 | Step 2-3 | No | 初回の場合は null |
| 22 | period_sales_target | number | 今期の売上目標（§1: 期アンカー・全レベル同値・period語化しない） | Step 1（週報=継承確認）/ Step 3（月報・期報=フル確認） | 種別依存 | 3.1.3参照。週報=任意（継承）／月報・期報=必須 |
| 23 | period_sales_cumulative | number | 今期の累計売上実績（§1: 期アンカー・週次更新） | Step 1 | 種別依存 | 3.1.3参照。週報も必須（週次更新） |
| 24 | business_partner_count | number | 現在事業パートナー数（§1: スナップショット・as-of-now） | Step 1 | 種別依存 | 3.1.3参照 |
| 25 | grid_partner_count | number | 現在のグリッドパートナー数（§1: スナップショット・週/月/期共通） | Step 1 | 種別依存 | 3.1.3参照 |
| 26 | grid_partner_goal | number / null | グリッドパートナー目標数（§1: スナップショット。育成行動の目安） | Step 1（週報=継承確認）/ Step 3（月報・期報=フル確認） | 種別依存 | 3.1.3参照。未設定時は null。専用出力セクションは持たず文脈・行動目標に反映 |
| 27 | last_academy_date | date / null | 前回のアカデミーへの参加日（§1: スナップショット） | Step 1 | 種別依存 | 3.1.3参照 |
| 28 | next_academy_date | date / null | 次回のアカデミーへの参加日（§1: スナップショット） | Step 1（週報=継承確認）/ Step 3（月報・期報=フル確認） | 種別依存 | 3.1.3参照 |
| 29 | next_sparring_date | date / null | 次回の壁打ち予定日（§1: スナップショット） | Step 1（週報=継承確認）/ Step 3（月報・期報=フル確認） | 種別依存 | 3.1.3参照 |
| 30 | sparring_target_state | string | 次回の壁打ち予定月までに目指している状態（§1: スナップショット） | Step 1（週報=継承確認）/ Step 3（月報・期報=フル確認） | 種別依存 | 3.1.3参照 |
| 31 | sparring_deliverables | string | 次回の壁打ち予定日までに達成させること（§1: スナップショット） | Step 1（週報=継承確認）/ Step 3（月報・期報=フル確認） | 種別依存 | 3.1.3参照 |
| 32 | prev_action_target | string[] | 前期間の行動目標（行動管理）。§1: period語化対象（前週/前月/前期） | Step 1 | No | 初回は null。前期間レビュー4種の1。Step 1 で表示・収集 |
| 33 | prev_action_actual | string[] | 前期間の行動実績（行動管理）。§1: period語化対象 | Step 1 | No | 初回は null。Step 1 で表示・収集 |
| 34 | prev_action_diff | string | 前期間の行動目標と実績の差分。§1: period語化対象 | Step 2 | No | 初回は null。+/-付き半角数字または要約文。Step 2 で算出 |
| 35 | prev_action_change | string[] | 前期間の行動に対して未達を挽回するための行動。§1: period語化対象 | Step 2 | No | 初回は null。Step 2 で算出 |

### 3.1.1 projects（#18）の構造

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| name | string | Yes | プロジェクト名 |
| client_owner | string | Yes | 先方担当者名。不明な場合は `未確認` |
| why | string | Yes | 何のために（目的・1文） |
| tasks | object[] | Yes | タスク配列 `{ due: string, recipient: string, what: string, done: boolean }`。出力形式は `- [ ] [due] [recipient] what` |
| subprojects | object[] / null | No | サブプロジェクト（1階層のみ）。`{ name, client_owner?, tasks[] }`。3階層以上は禁止 |

- 月報の projects は週報からの集約（ロールアップ）ではなく、前回月報の未完了タスク繰越＋当月の新規案件を Step 4 で生成する。週報→月報の集約対象外であり、逆に月報→週報の1:N分解（優先度ABC・日別到達ライン）の供給元となる。

### 3.1.2 habit_check（#19）の構造

週報のみ。3原則の運用状況をチェックボックス形式で保持する。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| focus_blocks_per_day | number | 1日に回す30分ブロックの最低本数（目安） |
| big_task_name | string | 今週分散させる大物タスクの名前 |
| split_days | number | 大物を分散する日数 |

### 3.1.3 文脈フィールドの種別別 必須/任意/継承マトリクス

統一ハイブリッド化（canonical-spec §10）で追加した文脈フィールド（#22-31）と habit_check（#19）の種別別必須度。週報は「現在の月報/期報」からの継承値を既定とし、info-collector が自動継承する（週報の所要時間5-8分を維持）。ターンでは一括確認のみ行い、変更があれば上書きする。月報・期報はフル elicitation で必須。

| フィールド | 週報 | 月報 | 期報 | 既定（継承元） | §1分類 |
|-----------|------|------|------|---------------|--------|
| period_sales_target (#22) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | 期アンカー |
| period_sales_cumulative (#23) | 必須（週次更新） | 必須 | 必須 | 現在の月報/期報を週次更新 | 期アンカー |
| business_partner_count (#24) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| grid_partner_count (#25) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| grid_partner_goal (#26) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| last_academy_date (#27) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| next_academy_date (#28) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| next_sparring_date (#29) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| sparring_target_state (#30) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| sparring_deliverables (#31) | 任意（継承） | 必須 | 必須 | 現在の月報/期報 | スナップショット |
| habit_check (#19) | 必須 | 対象外（null） | 対象外（null） | — | 週報固有 |

- 「任意（継承）」: 週報では値を新規ヒアリングせず、現在の月報/期報から継承した値を表示・確認する。継承値が取得できない場合のみヒアリングする。
- period_sales_cumulative のみ週報でも必須。週次で当該週時点の累計実績に更新する（継承値の更新が前提）。
- 前期間行動レビュー4種（prev_action_target/actual/diff/change・#32-35）は §1: period語化対象。全種別で初回は null、2回目以降は前期間データがあれば反映する。取得Stepは target/actual（#32-33）を Step 1 で表示・収集、diff/change（#34-35）を Step 2 で算出する。

### 3.2 camp_alignment の構造

| フィールド | 型 | 説明 |
|-----------|-----|------|
| direction_aligned | boolean | 合宿の方向性と目標が整合しているか |
| actions_reflected | boolean | 合宿で決めたアクションが行動目標に反映されているか |
| issues_addressed | boolean | 合宿で指摘された課題への対処が含まれているか |
| notes | string / null | 補足（ズレがある場合の説明） |

### 3.3 Step別の完了条件とフィールド対応

| Step | 完了条件 | 確定するフィールド |
|------|----------|-------------------|
| Step 1 | 基本情報 + 前回実績の数値が揃っている + 文脈フィールドの継承/一括確認（週報=#22-31）またはフル確認（月報・期報=#23-25, #27） + 前期間行動の目標/実績を表示・収集 | #1-6, #8-9, #32-33 + 文脈フィールド（週報=#22-31／月報・期報=#23-25, #27） |
| Step 2 | 根本原因が1つ特定されている + 前期間行動の差分・挽回行動を算出 | #7, #10-11, #34-35 |
| Step 3 | 売上目標・成果目標が具体的な数値で確定 + 目標文脈のフル確認（月報・期報=#22, #26, #28-31） | #12-13, #21 + 文脈フィールド（月報・期報=#22, #26, #28-31） |
| Step 4 | 行動目標3つ以上 + やらないこと3つ以上 + 判断基準1文 + プロジェクト別タスク（月報=必須・週報=任意・期報=非対象） + 習慣目標（週報のみ） | #14-19 |
| Step 5 | 8項目チェック全通過 + ユーザー承認 | #20 |

### 3.4 Step遷移条件

| 遷移 | 条件 |
|------|------|
| Step 1 → Step 2 | `name`, `business`, `phase`, `type` が確定。前回データがある場合は `prev_sales_target`, `prev_sales_actual` も確定 |
| Step 2 → Step 3 | `root_cause` が1つ特定されている（初回の場合は Step 2 スキップ可） |
| Step 3 → Step 4 | `sales_target`, `other_targets` が具体的な数値で確定 |
| Step 4 → Step 5 | `action_daily` + `action_period` 合計3つ以上、`not_doing` 3つ以上、`decision_criteria` 1文、`projects`（月報は1件以上必須・週報は任意で省略可・期報は非対象）、週報の場合は `habit_check` が確定 |
| Step 5 → 完了 | 8項目チェック全通過 + ユーザー承認 |

### バリデーション（Phase 3 完了時）

- 必須フィールド（#1-4, #12-17）が全て埋まっていること（#18 projects は種別依存: 月報=必須／週報=任意／期報=非対象。#22-31 文脈フィールドは 3.1.3 の種別別必須度に従う）
- 数値フィールド（#5, #6, #12）が半角数字であること
- `prev_sales_diff`（#7）に `+` または `-` が付いていること
- `not_doing`（#16）が3要素以上であること
- `action_daily` / `action_period` の各要素に数値または期日が含まれていること
- `projects`（#18）は月報で1件以上必須・週報は任意（省略可）・期報は非対象。出力する場合は各プロジェクトに `name` / `why` / `tasks` が揃っていること（subprojects は1階層まで）
- 週報の場合 `habit_check`（#19）が null でないこと
- `decision_criteria`（#17）がYes/Noで判定可能な1文であること

---

## 4. FormattedOutput（Phase 4 → ファイル）

output-formatter SubAgent が生成する最終成果物。

### 4.1 出力仕様

| フィールド | 型 | 説明 | 例 |
|-----------|-----|------|-----|
| file_name | string | 命名規則に従ったファイル名 | `UBM - 1-週報 - 2026-03-30〜2026-04-05.md` |
| content | string | Markdown形式の目標設定ドキュメント | output-formats.md のテンプレートに準拠 |
| save_path | string | 保存先ディレクトリ | `05_Project/UBM/目標設定/` |

### 4.2 ファイル命名規則

| goal_type | パターン |
|-----------|----------|
| weekly | `UBM - 1-週報 - {{start_date}}〜{{end_date}}.md` |
| monthly | `UBM - 2-月報（１ヶ月） - {{start_date}}〜{{end_date}}.md` |
| bimonthly | `UBM - 3-月報（２ヶ月） - {{start_date}}〜{{end_date}}.md` |

### 4.3 output-formatter への入力

| パラメータ | 提供元 | 説明 |
|-----------|--------|------|
| goal_type | GoalConfig | 目標種別 |
| target_period | GoalConfig | 対象期間 |
| interview_data | InterviewData | Phase 3 の全35フィールド |
| past_data | PastSummary | info-collector の構造化サマリー（そのまま引き渡し） |

### 4.4 バリデーション（Phase 4 完了時）

`$CLAUDE_PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-goal-output.py` による自動チェック:

| # | チェック項目 | 判定 | 説明 |
|---|-------------|------|------|
| 1 | ファイル名プレフィックス | FAIL | `UBM - {1,2,3}-` で始まること |
| 2 | 日付パターン | FAIL | `YYYY-MM-DD〜YYYY-MM-DD` を含むこと |
| 3 | 全角数字 | FAIL | 見出し行以外に全角数字がないこと（`１ヶ月`/`２ヶ月` は許容） |
| 4 | 差分の +/- 表記 | WARN | 差分値に `+` または `-` が付いていること |
| 5 | 必須セクション | FAIL | goal_type に応じた必須セクションが存在すること |
| 6 | 空セクション | WARN | `## 【` で始まるセクションが空でないこと |
| 7 | NG表現 | FAIL | 行動目標に「頑張る/意識する/気をつける/心がける/努力する」がないこと |
| 8 | 数値あり | WARN | 行動目標の各項目に数値が含まれていること |
| 9 | 期日あり | WARN | 行動目標の各項目に期日が含まれていること |
| 10 | やらないこと | FAIL | 3項目以上あること |
| 11 | 固有名詞 | WARN | 行動目標に人名（「さん」「様」）が含まれていること |
| 12 | プロジェクト別タスク | 種別依存 | 月報=`## 【プロジェクト別タスク】` セクションが存在し各タスクが `- [ ] [期日] [提出先・宛先] 対象物・行動` 形式であること（不在で FAIL）／期報=セクションが存在したら FAIL（出力禁止）／週報=任意（既定省略・方式2。存在時のみ整形チェック） |
| 13 | 習慣目標（週報のみ） | FAIL | weekly の場合 `## 【習慣目標（仕組みで動く土台）】` セクションが存在すること |

**判定ルール**: FAIL が1件以上 → STATUS: FAIL（修正して再バリデーション、最大3回）

### 4.5 goal_type 別の必須セクション

| goal_type | 必須セクション |
|-----------|---------------|
| weekly | 今週の売上目標、今週の売上以外の成果目標、今週の行動目標、最重要数字、習慣目標、やらないこと、判断基準、現在のグリッドパートナー数 |
| monthly | 売上目標、売上以外の成果目標、行動目標、プロジェクト別タスク、やらないこと |
| bimonthly | 売上目標、売上以外の成果目標、行動目標、事業の柱、やらないこと |

週報の任意セクション（欠落時 WARN・準静的/継承表示ゾーン。`check_section_optional`）: 到達ライン、今期の売上目標、前回のアカデミーへの参加日、次回のアカデミーへの参加日、次回の壁打ち予定日、現在事業パートナー数。「到達ライン」は二値性が行動目標のチェックボックスで担保されるため必須ではなく任意（WARN）。

---

## 5. 数値ルール（全Phase共通）

全てのPhaseで厳守する数値の取り扱いルール。

| ルール | 説明 | NG例 | OK例 |
|--------|------|------|------|
| 半角数字のみ | 全ての数値は半角で記載 | `６０万円`、`60万円` | `600000` |
| 差分記号 | 差分値には必ず `+` または `-` を付与 | `300000` | `-300000`、`+50000` |
| 行動目標の数値 | 行動目標に具体的な数値を含める | 「外交を増やす」 | 「個別メッセージを1日3件送る」 |
| 行動目標の期日 | 行動目標に期日を含める | 「資料を作る」 | 「3/15までにセミナー資料を完成」 |

---

## 6. エラーハンドリング

各Phaseでデータが欠落・不正な場合の対応方針。

### Phase 1-2（info-collector）

| 状況 | 対応 | 後続Phaseへの影響 |
|------|------|-----------------|
| ディレクトリ不在 | `[取得不可: ディレクトリなし]` マーク | Phase 3 で該当項目を全てヒアリング |
| ファイル0件 | `[取得不可: ファイルなし]` マーク | Phase 3 で該当項目を全てヒアリング |
| ナレッジ空 | フォールバック（Tier 1/2 直接読み込み） | ナレッジなしでも Phase 3 は継続可能 |
| 合宿ファイルなし | `[要ヒアリング]` マーク | Phase 3 Step 5 で合宿整合性チェックをスキップ |
| 日付パターン不正 | ファイル更新日時で代替ソート | 正常系と同じフローで継続 |

### Phase 3（phase3-coordinator）

| 状況 | 対応 | 後続Phaseへの影響 |
|------|------|-----------------|
| ユーザーが初回（前回データなし） | Step 2 をスキップ（root_cause = null） | Phase 4 では差分セクションを省略 |
| 曖昧回答 | 選択肢を3つ提示して選択 | 具体化されるまで次Stepに進まない |
| 精神論の回答 | 「仕組みで考えましょう」と再質問 | 具体化されるまで次Stepに進まない |

### Phase 4（output-formatter）

| 状況 | 対応 | 最終結果 |
|------|------|---------|
| バリデーション FAIL | エラー箇所を修正して再バリデーション（最大3回） | 3回失敗時はエラー箇所をユーザーに報告 |
| テンプレート不一致 | テンプレートを再読み込みして修正 | |
| 数値が全角 | 自動で半角変換 | |

---

## Version

| Version | Date | Changes |
|---------|------|---------|
| 2.3.0 | 2026-06-30 | **PastSummary 継承文脈契約の拡張（継承供給源の確立）**: §2.1 トップレベルに `inherited_context`（object/null・現在の月報/期報から継承した今期文脈・週報の自動継承元）を追加。§2.8 を新設し継承文脈10種（InterviewData #22-31 と一致・grid_partner_goal=number/null）の型定義を明文化。フロー契約表と §2 冒頭の PastSummary 説明に「文脈フィールド継承を含む」を追記。§3.1.1 に月報 projects は週報集約ではなく前回月報繰越＋当月新規（Step 4 生成）である旨を追記。prev_action #32-35 の取得Stepを #32-33=Step 1（target/actual 表示・収集）／#34-35=Step 2（diff/change 算出）へ修正し §3.3 と整合 |
| 2.2.1 | 2026-06-30 | **§4.5 週報必須セクションを validator と同期**: `validate-goal-output.sh` の週報判定（FAIL/WARN）に一致させ、必須に「今週の売上目標／今週の売上以外の成果目標／現在のグリッドパートナー数」を追加、行動目標系の表記を validator の実キー（今週の…）へ統一。「到達ライン」を必須→任意（WARN）へ降格し、任意（WARN）セクション一覧を明記。月報・期報の必須記述は不変 |
| 2.2.0 | 2026-06-30 | **統一ハイブリッド対応（canonical-spec §10）**: InterviewData に文脈フィールド10種（#22-31: 今期売上目標/累計実績・事業/グリッドパートナー数・グリッド目標・前回/次回アカデミー・次回壁打ち日/目指す状態/達成事項）と前期間行動レビュー4種（#32-35）を追加し全35フィールド化。種別別 必須/任意/継承マトリクス（3.1.3）を新設（文脈系は週報=任意・継承／月報・期報=必須、period_sales_cumulative は週報も必須、habit_check は週報のみ）。プロジェクト別タスクを単一SSoT化（月報=必須／週報=任意・既定省略・方式2／期報=禁止）し #18・3.3/3.4・バリデーション項目12・4.5週報必須セクション（プロジェクト別タスク削除）へ反映 |
| 2.1.0 | 2026-05-06 | **プロジェクト別タスクの宛先明確化**: `projects.client_owner` と `tasks[].recipient/what` を追加。出力形式を表ではなく `- [ ] [期日] [提出先・宛先] 対象物・行動` のチェックリスト形式に固定 |
| 2.0.0 | 2026-05-05 | **「明日朝一番」削除＋プロジェクト/習慣目標の導入**: (1) field 18 `first_action_tomorrow` を削除し、`projects`（プロジェクト別タスク・2階層まで）と `habit_check`（週報のみの習慣目標）を新設。(2) 必須セクション一覧と Step遷移条件を更新。(3) バリデーション項目を 12 → 13 に再構成（精神論チェックを廃止し、プロジェクト/習慣セクションの存在チェックを追加） |
| 1.0.0 | 2026-03-31 | 初版作成。GoalConfig / PastSummary / InterviewData / FormattedOutput の4契約を定義。バリデーションルール・エラーハンドリング・数値ルールを明文化 |
