# info-collector の出力テンプレート

`agents/info-collector.md` の Step 4（構造化サマリーの生成）で使う出力の形の正本。info-collector は Step 4 の前にこのファイルを Read し、全項目に [自動取得] または [要ヒアリング] などのマークを付けてこの形で返す。

## 出力テンプレート

受領先: Phase 3 ヒアリングエージェント

```
## 過去目標サマリー
### ユーザー基本情報
- 名前: {{name}} [自動取得] / [要ヒアリング]
- 事業内容: {{business}} [自動取得] / [要ヒアリング]
- フェーズ: {{phase}} [自動取得] / [要ヒアリング]
- 形態: {{type}} [自動取得] / [要ヒアリング]
- 顧問参加前月商: {{prev_sales}} [自動取得] / [要ヒアリング]
- 直近合宿参加日: {{last_camp}} [自動取得] / [要ヒアリング]
### 1年層の到達点（現在の1年目標／最新の挑戦宣言から継承・種別を問わず載せる）
- 1年後の月間売上到達点: {{yearly_monthly_sales_goal}} [自動取得] / [要ヒアリング] / null（理由）
- 1年後の月額継続コンサル人数: {{yearly_continuous_consult_count}} [自動取得] / [要ヒアリング] / null（理由）
- 出所: 1年目標ファイルのパス {{yearly_path}} ／ 挑戦宣言のパス {{challenge_declaration_path}}

### 継承文脈（現在の月報/期報から継承。1年も現在の期報から）
- 今期の売上目標: {{period_sales_target}} [自動取得] / [要ヒアリング]
- 今期の累計売上実績: {{period_sales_cumulative}} [自動取得] / [要ヒアリング]
- 現在事業パートナー数: {{business_partner_count}} [自動取得] / [要ヒアリング]
- 現在のグリッドパートナー数: {{grid_partner_count}} [自動取得] / [要ヒアリング]
- グリッドパートナー目標人数: {{grid_partner_goal}} [自動取得] / [要ヒアリング]
- 前回のアカデミー参加日: {{last_academy_date}} [自動取得] / [要ヒアリング]
- 次回のアカデミー参加日: {{next_academy_date}} [自動取得] / [要ヒアリング]
- 次回の壁打ち予定日: {{next_sparring_date}} [自動取得] / [要ヒアリング]
- 壁打ちで到達したい状態: {{sparring_target_state}} [自動取得] / [要ヒアリング]
- 壁打ちまでの成果物: {{sparring_deliverables}} [自動取得] / [要ヒアリング]
### 前回の目標と実績
- 売上目標: {{target}} / 実績: [要ヒアリング] / 差分: [要計算]
- 成果目標: {{other_target}} / 実績: [要ヒアリング]
- 行動目標: {{action_target}} / 実績: [要ヒアリング]
### パターン分析（複数期間データがある場合）
- 売上推移: {{sales_trend}}
- 繰り返されている課題: {{recurring_issues}}
### 前回のプロジェクト別タスク継続状況
- アクティブなプロジェクト: {{active_projects}} [自動取得] / [要ヒアリング]
- 未完了のまま繰り越されているタスク: {{carryover_tasks}}
- 完了率: {{completion_ratio}}
### 前回の習慣目標達成状況（weeklyのみ）
- 30分切替: {{habit_30min}} [自動取得] / [要ヒアリング]
- 大物分散: {{habit_distribution}}
- 粒度の粗さ: {{habit_granularity}}
## 直近の合宿アドバイス（最重要）
### 合宿日: {{camp_date}} [自動取得] / [合宿情報なし]
- 事業方針: {{business_direction}}
- 具体的アクション: {{camp_actions}}
- 克服すべき課題: {{camp_challenges}}
- 数値目標: {{camp_targets}}
### 整合性チェックポイント
- 目標設定がこの方針とズレていないか確認する
- 合宿で決めたアクションが行動目標に含まれているか確認する
## 挑戦宣言からの文脈
- source_path / declared_on: {{challenge_source}} / [挑戦宣言なし]
- 確定した目的・目標・行動・報告周期: {{challenge_context}}
- 今回の目標への採用は Phase3 で利用者確認
## 層間照合の参照ファイル
- peer_paths: {{peer_paths}}（同じ期の絶対パスと期間。欠けた層は null と理由）
## ナレッジサマリー
- knowledge_candidates: {{実検索JSONオブジェクト（search_id・zero_hit・matched_ids・matches[] の各候補の source_ref と file_sha256）}} / [検索待ち]
- 親へ返す検索語: {{search_terms と理由}}（検索待ちのときだけ）
- 適用の判断理由: {{順位付き候補から選択/不採用した理由。実usageはPhase3後に親が記録}}
### 上位概念（このユーザーへの翻訳済み）
- 概念1: 【原則】{{principle_1}} → 【このユーザーの場合】{{application_1}}
- 概念2: 【原則】{{principle_2}} → 【このユーザーの場合】{{application_2}}
- 概念3: 【原則】{{principle_3}} → 【このユーザーの場合】{{application_3}}
### 引用候補（Phase 3 で使う言葉）
- 引用1: 「{{quote_1}}」— 使い所: {{usage_1}}
- 引用2: 「{{quote_2}}」— 使い所: {{usage_2}}
### フェーズ別の注力点
- {{phase_focus}}
### ナレッジ不足の場合
- フォールバック先: {{fallback_source}} [自動取得] / [ナレッジ未同期]
## ジャーナルサマリー（weekly のみ）
### 対象期間: {{start_date}}〜{{end_date}}
- 読み取り済みジャーナル: {{journal_dates}} [自動取得] / [ジャーナルなし]
- 行動実績:
  - {{action_summary}}
- 時間配分:
  - {{time_summary}}
- お金・売上活動:
  - {{money_summary}}
- 繰り返されている課題: {{recurring_issues_from_journal}}
- 気づき・改善アイデア: {{insights}}
## 直近の相談からの引き継ぎ（run-ubm-consult の引き継ぎ）
- 参照した相談記録: {{consult_handoff_ref}} [自動取得] / [相談履歴なし]
- 相談で言語化された課題: {{consult_issue_statement}}
- ユーザー自身の言葉での解決策: {{consult_user_solution}}
- 相談の次の一歩（今回の目標種別に合致すれば行動目標候補）: {{consult_next_step}}
```
