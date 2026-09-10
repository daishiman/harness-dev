# スクリプト/LLM パターンガイド

> **読み込み条件**: 実行時の処理分担を理解する必要がある時
> **責務**: 「いつ」スクリプト/LLMを使うかの判断基準を提供

---

## 概要

X長文投稿クリエーター内の処理を「スクリプト（決定論的）」と「LLM（創造的）」に適切に分担する。

**原則**: Script First（決定論的処理は100%精度のスクリプトで実行）

---

## 処理分担マトリクス

| 処理 | 担当 | 理由 |
|------|------|------|
| **日付計算** | スクリプト | ルールが明確（最新+1日） |
| **ファイル名生成** | スクリプト | 命名規則に基づく決定論的処理 |
| **文字数カウント** | スクリプト | 数値計算は100%精度必要 |
| **テンプレート展開** | スクリプト | 変数置換は決定論的 |
| **00ネタファイル更新** | スクリプト | ファイル操作は決定論的 |
| **構成要素抽出** | LLM | 文脈理解・意図の解釈が必要 |
| **矛盾解決** | LLM | 論理的判断が必要 |
| **スタイルゲノム適用** | LLM | 文体調整は創造的処理 |
| **文章最適化** | LLM | 冗長表現判断は主観的 |
| **タイトル作成** | LLM | 創造的な表現が必要 |
| **短文投稿生成** | LLM | フォーマット選定と表現は創造的 |

---

## スクリプト一覧

| スクリプト | 用途 | 入力 | 出力 |
|-----------|------|------|------|
| `calculate-next-date.js` | 次の投稿日を計算 | 00ネタファイルパス | JSON（日付） |
| `generate-filename.js` | ファイル名生成 | 日付、タイトル | JSON（パス） |
| `count-chars.js` | 文字数カウント・検証 | テキスト | JSON（統計） |
| `update-neta-file.js` | 00ネタファイル更新 | ファイルパス、ファイル名 | JSON（結果） |
| `expand-template.js` | テンプレート展開 | テンプレート、変数 | 展開済みテキスト |
| `log_usage.js` | 使用記録 | 結果、Phase | ログファイル |

---

## 実行フロー

```
[入力: キャッチコピー + メモ]
         │
         ▼
┌─────────────────────────────┐
│ Script: calculate-next-date │ ← 00ネタファイルから日付計算
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ LLM: 構成要素抽出            │ ← prompts/x-longpost-parse-input.md
│ LLM: 矛盾解決               │ ← prompts/x-longpost-resolve-contradictions.md
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ LLM: スタイルゲノム適用      │ ← prompts/x-longpost-apply-style-genome.md
│ LLM: 文章最適化             │ ← prompts/x-longpost-optimize-length.md
│ LLM: タイトル作成           │ ← prompts/x-longpost-create-title.md
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Script: count-chars         │ ← 文字数検証
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Script: generate-filename   │ ← ファイル名生成
│ Script: expand-template     │ ← テンプレート展開
│ Script: update-neta-file    │ ← 00ネタ更新
└─────────────────────────────┘
         │
         ▼
[出力: 投稿ファイル]
```

---

## スクリプト使用例

### 日付計算
```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/calculate-next-date.js \
  --neta-file "/05_Project/X/X長文投稿-prompt作成 - 0000-00-00_ネタ - プロンプト作りで大事なこと.md"
```

出力:
```json
{
  "nextDate": "2026-02-05",
  "latestDate": "2026-02-04",
  "source": "00ネタファイル"
}
```

### ファイル名生成
```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-filename.js \
  --date "2026-02-05" \
  --title "AIで開発環境を整えたら、作業時間が10分の1になった"
```

### 文字数検証
```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-chars.js \
  --text "投稿文テキスト..." \
  --min 1800 \
  --max 2200
```

### 00ネタファイル更新
```bash
node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/update-neta-file.js \
  --neta-file "${XLP_NETA_FILE}" \
  --filename "X長文投稿-prompt作成 - 2026-02-05_タイトル.md"
```

---

## 判断基準

### スクリプト化すべき処理

以下の質問にすべて「はい」なら決定論的:

- [ ] 入力が同じなら出力は常に同じか？
- [ ] ルール・テーブルで完全に定義できるか？
- [ ] 人間の判断なしに実行できるか？
- [ ] 例外ケースもルール化できるか？

### LLMに任せるべき処理

以下のいずれかに該当すればLLM:

- [ ] 同じ入力でも複数の妥当な出力がありうる
- [ ] 「良い」「適切」などの主観的判断が必要
- [ ] 文脈やニュアンスの理解が必要
- [ ] 創造的な生成が必要
- [ ] 自然言語での表現・言語化が必要

---

## 関連リソース

| 次のステップ | 参照先 |
|-------------|--------|
| 構成要素抽出 | [prompts/x-longpost-parse-input.md](../../../prompts/x-longpost-parse-input.md) |
| 文章最適化 | [prompts/x-longpost-optimize-length.md](../../../prompts/x-longpost-optimize-length.md) |
| 短文投稿生成 | [prompts/x-longpost-short-post-optimizer.md](../../../prompts/x-longpost-short-post-optimizer.md) |
| 出力テンプレート | [../../../assets/output-template.md](../../../assets/output-template.md) |
