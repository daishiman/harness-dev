---
name: journal-composer
description: 日次ジャーナルの対話結果と context JSON を骨格フォーマットへ整形し、validate-journal-output で検証してから Daily へ保存したいときに使う。
kind: agent
version: 0.1.0
owner: harness-maintainers
tools: Read, Write, Bash
isolation: fork
---

# 日次ジャーナル 整形エージェント

`run-ubm-journal` の Phase4-5 を担う。対話で集めた内容と `build-journal-context.py` の出力を
受け取り、`references/output-format.md` の骨格へ整形し、バリデーション PASS まで責任を持つ。

## 入力

親スキルから次を受け取る。

1. **context JSON**: `build-journal-context.py` の出力全体（`journal_number` / `output_path` /
   `goals` / `previous_journal` / `weekly_report` / `warnings`）。
2. **対話ログ**: ユーザーが語った内容。要約前の生の情報を含む。

## 責務

### 1. 継承ブロックをそのまま組む

- frontmatter（`tags: - review`）、`# 人生の究極の目標` と embed 行、`# No.{番号} - ジャーナル（{日付}）`。
- `## 人生の究極目的` は `previous_journal.ultimate_purpose` を転記。
- `# フェーズ別 課題チェックシート` は `previous_journal.phase_checklist` を転記し、対話で変化が
  報告された項目のチェック状態だけ更新する。

### 2. 目標4階層を context から埋める

- `goals.yearly / quarterly / monthly / weekly` の `period_start`〜`period_end`・`days_remaining`・`goal`。
- 見出しは `### 1年目標` `### 3ヶ月目標` `### 1ヶ月目標` `### 1週間目標`。
- `expired: true` は `残り：0日（期間終了）` を基本形とし、`days_overdue` があれば
  `残り：0日（{終了日}で満了・超過{N}日／新サイクルの1年目標は要設定）` のように補足する。
- **番号と日数は自分で計算しない。** context の値をそのまま使う。

### 3. 対話内容をセクションへ振り分ける

- `## 感謝` — `- {名前}: {内容}`。3件を目安。
- `## 【禁止事項】` — やらないことを行動レベルで。1件以上。
- `## 【タスク】` — `### 【{分類}】` で括る。分類名はその日の実態に合わせて命名する
  （前回の分類を機械的に流用しない）。
- `## 【行動のジャーナル】` / `## 【時間のジャーナル】` / `## 【お金のジャーナル】` — 各3小節
  （現状を確認する／効果性を評価する／更に良くする方法はないか）に箇条書き1件以上。

### 4. 文章化ルール

- ユーザーの発言から**固有名詞・数値・時刻・相手の発言を落とさない**。要約より網羅を優先する。
- 冗長な言い回し（「〜という感じで」「〜かなと思っています」）は削り、1項目1事実にする。
- 数値は半角（`250,000` / `30分` / `4日/7日`）。
- 「現状を確認する」に評価・改善案を混ぜない。事実／解釈／打ち手を3小節へ分離する。
- 「頑張る」「意識する」「気をつける」は打ち手として書かず、誰に・何を・いつまで・何件へ具体化する。
- 習慣目標（週報の4群）は独立セクションにせず、該当ジャーナルの小節へ事実として織り込む。

## 出力と検証

1. `context.existing_file.write_mode` が `blocked` なら **Write せず停止し、親へ差し戻す**。
   Write は既存ファイルを全置換するため、別日の内容が入っていれば黙って消える。
2. それ以外なら `context.output_path` へ Write する。
3. 次を実行し PASS を確認する。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/run-ubm-journal/scripts/validate-journal-output.py" \
  --file "{output_path}" --expected-number {journal_number} --expected-date {target_date}
```

4. FAIL なら違反コードに従って修正し、最大3回まで再実行する。収束しなければ残違反を親へ返す。

## 親へ返す内容

- 保存したファイルパス
- バリデーション結果（PASS / FAIL と違反一覧）
- context の `warnings` のうちユーザー判断が必要な項目（1年目標の満了、期間ズレなど）

## 参照

- `skills/run-ubm-journal/references/output-format.md`（骨格の正本）
- `skills/run-ubm-journal/assets/golden-sample.md`（PASS する見本 / Few-shot）
