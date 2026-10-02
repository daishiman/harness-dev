# Pricing Notes — 料金の意味と更新

`data/pricing.json` のスキーマと、課金機構の正しい解釈。料金は USD / 100万トークン。

## モデルエントリ

```jsonc
{
  "provider": "anthropic|openai|google|…",
  "id": "claude-opus-4-8",          // シナリオ/CLI が参照する一意キー
  "display_name": "Claude Opus 4.8",
  "input": 5.0,                      // 入力 / 1M
  "output": 25.0,                    // 出力(思考込み) / 1M
  "cached_input": 1.25,              // (任意) キャッシュ読の絶対単価。あれば read_mult より優先
  "context_window": 1000000,
  "max_output": 128000,
  "reasoning": true,                 // 思考/推論トークンを出力単価で課金するか
  "context_tiers": [                 // (任意) 長文脈の階層料金
    { "min_input_tokens": 200001, "input": 2.5, "output": 15.0 }
  ],
  "as_of": "2026-05-26",
  "confidence": "authoritative|verify|estimate",
  "source": "…", "notes": "…"
}
```

`provider_defaults[provider]` でキャッシュ/バッチの倍率を既定し、モデル側で上書き可能。
優先順位は `model > provider_defaults > generic`。

## キャッシュ機構(プロバイダ差)

| 機構 | Anthropic | OpenAI | Google |
|------|-----------|--------|--------|
| read(キャッシュ読) | ~0.1× 入力 | ~0.5×(`cached_input` 明示が多い) | ~0.25×(+保存課金は未モデル化) |
| write 5m | 1.25× | 1.0×(書込み割増なし) | 1.0× |
| write 1h | 2.0× | — | — |

- Anthropic: prefix の **書込みに割増**(1.25×/2.0×)、**読込みは激安**(0.1×)。安定 prefix を
  繰り返すエージェント/RAG で効果絶大(入力を最大 ~90% 削減)。
- OpenAI: 自動キャッシュ。書込み割増なし、読が約半額。
- Google: コンテキストキャッシュは割引 + **トークン時間あたりの保存課金**が別途あるが、本ツールは
  保存課金を計上しない(注記済み)。長時間保持する設計では別途加味すること。

エンジンは `cached_input` があればそれを read 単価に、なければ `input × cache_read_mult` を使う。

## Batch API

`batch_mult`(主要プロバイダ 0.5 = 50% 引き)。非同期で許容できる分類/抽出/要約に有効。
シナリオの call に `"batch": true` を立てると全課金に倍率が掛かる。

## 思考/推論トークン(reasoning)

`reasoning: true` のモデルでは思考トークンが **出力単価** で課金され、しばしば支配的。
シナリオでは `tokens.thinking` に計上(出力単価で `output` と合算される)。実測時は usage の
output に含まれることが多い。effort/budget で制御可能だが、未制御だと跳ねる。

## 階層料金(long-context)

`context_tiers` は入力(+キャッシュ)合計トークンで判定し、閾値超で単価を差し替える。
例: Gemini 2.5 Pro は >200K で入力 1.25→2.5、出力 10→15。
Claude Opus 4.x は **1M まで一律**(長文脈割増なし)。

## 料金の鮮度と更新

- **Anthropic** は claude-api スキル由来で `authoritative`。信頼してよい。
- **OpenAI/Google 等は `verify`**。学習データの as_of 値であり、変動している可能性が高い。
  **ROI 判断の前に必ず公式ページで再確認**:
  - OpenAI: https://openai.com/api/pricing/ ・ https://platform.openai.com/docs/pricing
  - Google: https://ai.google.dev/gemini-api/docs/pricing
  - Anthropic: https://platform.claude.com/docs/en/pricing
  - 横断確認: https://openrouter.ai/models
- 更新手順: WebFetch で当該ページを取得 → input/output/cached を 1M 単位で読み取り →
  `data/pricing.json` を編集(`as_of`/`confidence` も更新)→ `simulate.py` を再実行。
- **新モデル/新プロバイダ**は `models[]` に追記するだけで `--compare` や HTML 比較の対象になる。
  Bedrock/Vertex 等は `anthropic.`/プロバイダ接頭辞付き ID で別エントリにし、必要なら
  `provider_defaults` を足す。

## サニティチェック

- 比較表の「最安比」が極端(例: Opus が最安の 30×)なのは正しい挙動。安いモデルは品質要件を
  満たすか必ず実測で検証する旨をレポートに残す。
- `confidence: verify/estimate` の数値で意思決定する場合は、その旨を必ず明示する。
