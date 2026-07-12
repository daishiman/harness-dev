---
name: anti-patterns
description: ヒアリング頻出失敗パターン辞書 (検出シグナル・対処 SubAgent)
type: reference
---

# アンチパターン辞書

ヒアリング過程で頻出する失敗パターン。`failure-modes.md` がフロー中の失敗動作を扱うのに対し、こちらは**結果物の構造的な失敗**を扱う。

## 一覧

| # | 名称 | カテゴリ | 検出 | 対処 SubAgent |
|---|------|----------|------|---------------|
| 1 | 「毎朝のスケジュール」型 | 抽象要望 | 具体動詞ゼロ | assumption-challenger |
| 2 | 「全部自動化」型 | 過大期待 | 制約に「ない」連発 | option-presenter |
| 3 | 「とりあえず」型 | 動機弱 | jtbd.so_i_can が空 | purpose-excavator |
| 4 | 「便利にしたい」型 | 抽象的価値 | KPI 数値ゼロ | value-checker |
| 5 | 「他の人もやってる」型 | 模倣 | 自分の文脈未確認 | user-profiler |
| 6 | 「一人でできる」型 | 共有忘却 | share_target 未確定 | interviewer |
| 7 | 「いまのままでいい」型 | 現状肯定 | 痛み件数ゼロ | assumption-challenger |
| 8 | 「全部聞かれた通り」型 | 同意ループ | Reverse Brief 訂正ゼロ | summarizer |
| 9 | 「完璧主義」型 | 過剰要件 | 必須でない要件多数 | next-action-advisor |
| 10 | 「マルチスキル混在」型 | 範囲爆発 | 出力 2 種以上 | kickoff |

---

## 1. 「毎朝のスケジュール」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「毎朝のスケジュールをまとめてほしい」 |
| 検出シグナル | 動詞「まとめる」のみ、出力先・共有相手未指定 |
| 真の課題候補 | 出力先未定／共有相手未定／通知タイミング／不要情報除外 |
| 対処 | assumption-challenger が 5 軸全部を一気に問う |

## 2. 「全部自動化」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「フォーム作成・告知・集計・リマインドまで全自動」 |
| 検出シグナル | 動詞が 3 つ以上、依存サービスが 5 つ以上 |
| 対処 | マルチスキル分割提案 + Magic Wand で優先順位付け |

## 3. 「とりあえず」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「とりあえず作ってみたい」 |
| 検出シグナル | jtbd.so_i_can が「特に何も」「いろいろ」 |
| 対処 | 「作った翌朝、何が違っていたら成功？」と未来質問 |

## 4. 「便利にしたい」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「もうちょっと便利にしたい」 |
| 検出シグナル | KPI 数値ゼロ |
| 対処 | Pain Story で「直近で一番困った 1 件」を再現 |

## 5. 「他の人もやってる」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「みんな ChatGPT 使ってるからうちも」 |
| 検出シグナル | 自分の文脈・痛みの説明なし |
| 対処 | user-profiler が role/context を確定させる |

## 6. 「一人でできる」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「自分用なので共有相手はいない」 |
| 検出シグナル | share_target が空のまま |
| 対処 | 「未来の自分が見るのも共有」と再定義 |

## 7. 「いまのままでいい」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「困ってないけどなんとなく」 |
| 検出シグナル | pain_stories ゼロ件 |
| 対処 | スキル化を中止する選択肢を提示 |

## 8. 「全部聞かれた通り」型

| 項目 | 内容 |
|------|------|
| 表層例 | こちらの提案に全部「はい」 |
| 検出シグナル | Reverse Brief で訂正 0 回 |
| 対処 | わざとずらした提案で反応を見る |

## 9. 「完璧主義」型

| 項目 | 内容 |
|------|------|
| 表層例 | エッジケースを際限なく追加 |
| 検出シグナル | 要件 10 個以上、優先順位なし |
| 対処 | MoSCoW（Must/Should/Could/Won't）で分類 |

## 10. 「マルチスキル混在」型

| 項目 | 内容 |
|------|------|
| 表層例 | 「議事録 → スライド → 配信 → 集計」 |
| 検出シグナル | 出力形式 2 種以上、フェーズ明確分離 |
| 対処 | kickoff で分割提案、orchestrator 候補化 |

## 検出ルール表

```javascript
const antiPatternRules = {
  surfaceVague: (intake) =>
    !intake.purpose.excavated || intake.purpose.excavated === intake.purpose.stated,
  shareForgotten: (intake) =>
    !intake.five_axes.share_target.answer,
  noNumbers: (intake) =>
    !/[0-9]/.test(JSON.stringify(intake.purpose)),
  multiSkill: (intake) =>
    intake.similar_skills?.filter(s => s.score >= 0.4).length >= 2,
  knowledgeUnverified: (intake) =>
    !intake.five_axes.knowledge_assets?.verified
};
```

## 対処の自動化

`scripts/quality_gate.py` がアンチパターン検出ルールを実行し、該当する場合は対応 SubAgent に自動再ヒアリング指示を送る。
