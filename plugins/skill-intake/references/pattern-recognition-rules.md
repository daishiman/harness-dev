---
name: pattern-recognition-rules
description: 既存スキルとの類似度判定とマルチスキル疑い検出ロジック
type: reference
---

# 既存スキル類似判定ルール

新しいヒアリングが既存スキルとどれくらい似ているかを早期に判定し、車輪の再発明を回避する。`skill-intake-kickoff` SubAgent が起動直後に走らせる。

## 既存スキル特徴ベクトル

| スキル | 主要シグナル | パターン |
|--------|--------------|----------|
| google-forms-generator | フォーム／申込／Google Forms／Sheets 自動連携 | A |
| xl-contract-generator | 契約書／業務委託／PDF／.docx／Drive 出力 | C |
| presentation-slide-generator | スライド／プレゼン／16:9／セミナー資料 | A |
| arxiv-paper-reporter | 論文／arxiv／毎日収集／Discord／スコアリング | B |
| x-post-reporter | X(Twitter)／AI／スレッド配信／Discord／自動収集 | B |
| google-meet-minutes-generator | Meet／録画／議事録／Whisper／Discord Bot | B/D |
| ai-release-reporter | OpenAI／Anthropic／リリース／RSS／Discord | B |
| flyer-generator | チラシ／画像生成プロンプト／8 人レビュー | A |
| prompt-creator | プロンプト／7 層構造／対話生成 | A |
| contract-generator | 取引基本契約書／対話 | C |

## 類似度シグナル

### A: 出力形式シグナル

| シグナル | スコア寄与 |
|----------|------------|
| 「契約書／法律文書」 | xl-contract +0.4, contract-generator +0.4 |
| 「フォーム／申込」 | google-forms +0.5 |
| 「スライド／プレゼン」 | presentation +0.5 |
| 「チラシ／ポスター」 | flyer +0.5 |
| 「議事録／会議録」 | meet-minutes +0.5 |

### B: 連携先シグナル

| シグナル | 寄与 |
|----------|------|
| Google Forms | google-forms +0.3 |
| Google Drive | xl-contract +0.2, google-forms +0.1 |
| Discord | arxiv +0.3, x-post +0.3, ai-release +0.3, meet-minutes +0.3 |
| arxiv | arxiv +0.5 |
| X / Twitter | x-post +0.5 |

### C: 起動形態シグナル

| シグナル | 寄与 |
|----------|------|
| 「毎朝／毎日／定時」 | パターン B 候補 +0.3 |
| 「対話で／聞きながら」 | パターン A/C 候補 +0.3 |
| 「録画から／音声から」 | meet-minutes +0.4 |
| 「収集→要約→配信」 | パターン B 候補 +0.5 |

### D: スコアリング手法シグナル

| シグナル | 寄与 |
|----------|------|
| 「キーワード+LLM で上位 N 件」 | arxiv +0.4 |
| 「Grok 要約」 | x-post +0.4 |
| 「Whisper 文字起こし」 | meet-minutes +0.5 |

## 類似度判定式

```
similarity(skill_X) = sum(signal_weights) for matched signals
類似判定:
  similarity >= 0.7 → 「既存スキル X の派生／拡張」を提案
  0.4 <= sim < 0.7 → 「一部流用可能」と通知
  similarity < 0.4 → 新規スキル
```

## サンプル: google-forms-generator 想定発話

> 「セミナーの申込フォームを Google で自動で作って、Sheets に集計して欲しい」

| シグナル | スコア |
|----------|--------|
| 「フォーム／申込」 | google-forms +0.5 |
| Google Forms 直接言及 | +0.3 |
| 対話形式想定 | パターン A +0.3 |
| **合計** | google-forms 0.8 → 既存スキル流用 |

→ kickoff は「google-forms-generator が既にあります。新規作成せず実行しますか？」と提示。

## マルチスキル疑い検出ロジック

ユーザー要望が**複数の既存スキルにまたがる**場合、単一スキルで実装してはいけない。

### 検出条件

- 2 つ以上のスキルで `similarity >= 0.4`
- 出力形式が 2 種類以上（例: スライド + 議事録）
- フェーズが 2 つ以上明確に分かれる（例: 収集→生成→配信）

### 検出時の対応

1. ヒアリングで「これは 2 つの仕事に見えます。分けて作りますか？」と確認
2. ユーザーが分割同意 → 各スキルの hint を separate に出す
3. ユーザーが統合希望 → orchestrator として上位スキルを提案（依存スキル明示）

### サンプル

> 「Meet の録画から議事録作って、要点をスライドにして共有」

| 該当 | スコア |
|------|--------|
| google-meet-minutes-generator | 0.8 |
| presentation-slide-generator | 0.7 |

→ **マルチスキル疑い**。次のように提案。

```
これは 2 つに分けられます:
  1. 録画→議事録: google-meet-minutes-generator
  2. 議事録→スライド: presentation-slide-generator
両者を連携させる新スキル meeting-to-slides を上位に作る案もあります。どうしますか？
```

## 出力

判定結果は intake.json の補助フィールドに格納。

```json
{
  "similar_skills": [
    { "name": "google-forms-generator", "score": 0.8, "action": "extend-or-reuse" }
  ],
  "multi_skill_suspected": false
}
```
