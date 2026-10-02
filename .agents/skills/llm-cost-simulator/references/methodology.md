# Methodology — トークン計上とシナリオ記法

このスキルの数値の「根拠」を支える計上ルール。`scripts/engine.py` の実装と一対一で対応する。

## 1. 1 フロー = 1 ユーザー操作

「フロー」は **ユーザーから見た 1 回の処理**。1 フローが内部で複数の LLM 呼び出しを誘発しうる
(例: 意図分類 → 回答生成 → ツール使用エージェントループ → 要約)。シナリオの `calls[]` に
すべて列挙し、合算する。

## 2. 入力トークンを構成する全要素(計上漏れ撲滅)

呼び出し 1 回の入力は次の合算。`tokens` の各キーに入れる:

| キー | 内容 | 見落とし注意 |
|------|------|------------|
| `system` | system プロンプト全文 | — |
| `tools` | **ツール/関数定義の JSON スキーマ。毎リクエスト送られる** | ★最頻出の計上漏れ |
| `context` | RAG 注入・添付ドキュメント・few-shot 等の可変文脈 | RAG は「チャンク tok × 件数 k」 |
| `history` | 会話履歴(マルチターン時) | エージェントでは毎ターン累積 |
| `user_input` | そのターンのユーザー入力 | — |

これらの合算が **full-price 入力**。画像/PDF はプロバイダ別の式でトークン換算して `context` に
加算する(下記 §6)。

## 3. 出力トークン

| キー | 内容 |
|------|------|
| `output` | 生成テキスト。`max_tokens` は**上限**にすぎない。可能なら T2/T3 で実測 |
| `thinking` | **思考/推論トークン。出力単価で課金され、推論モデルでは支配的になりうる** |

`output` と `thinking` は出力単価で合算課金される。reasoning 系(o-series, gpt-5 思考, Gemini
thinking, Claude extended thinking)では `thinking` を必ず見積もる/実測する。

## 4. キャッシュの記法(★二重計上に注意)

安定 prefix(typically system+tools+静的 context)はプロンプトキャッシュ対象にできる。
表現方法は 2 つ:

**(A) レート方式 — 推奨**: `tokens.cacheable_prefix` に prefix トークン数を入れる。
エンジンが `projection.cache_hit_rate` で read/write に分割する(hit→read, miss→write)。
**このとき prefix のトークンを `system`/`tools`/`context` に重複して入れない。**
prefix は別プールとして計上される。

```json
// 正: system+tools=2300 を prefix に集約。component には残り(可変文脈)だけ
"tokens": { "context": 6000, "user_input": 220, "cacheable_prefix": 2300, "output": 700 }
```

**(B) 明示方式**: 実測の `usage` から得た `cache_read` / `cache_write` を直接入れる。
このときも component 側は「フルプライスで請求された残り(uncached)入力」のみ。
合計プロンプト = full-price 入力 + cache_read + cache_write(Anthropic usage の
`input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` に対応)。

`cache_write_ttl` は `"5m"`(既定, 1.25×)か `"1h"`(2.0×)。

## 5. エージェントループ(履歴累積)

ツール使用ループは反復ごとに履歴が膨らみ、コストが非線形に増える。`agent_loop` で表現:

```json
"tokens": { "user_input": 120, "output": 350 },
"agent_loop": {
  "iterations": 4,
  "history_growth_per_iter": 900,
  "cached_prefix_tokens": 2300,
  "history_cached": false
}
```

エンジンのモデル:
- 反復 i (0始まり): fresh 入力 = `base_input(=component合計) + history_growth × i`
- 反復 0 は prefix を **書込み**(cache_write)、以降は **読込み**(cache_read)
- `history_cached: true` なら累積履歴も read レートで計上(キャッシュ運用済みの楽観ケース)、
  `false` なら full price(キャッシュ未運用の上限ケース。既定)

prefix は `cached_prefix_tokens` に集約し、component(`user_input` 等)に重複させない。

## 6. 画像・PDF のトークン換算(概算)

正確な値は各プロバイダの式に従うが、概算の目安:

- **Anthropic 画像**: `tokens ≈ (width_px × height_px) / 750`(上限 ~1568px/辺。Opus 4.7+ は
  高解像度で最大 ~4784 tok/枚)。`count_tokens` に画像ブロックを渡せば正確。
- **OpenAI 画像**: detail=low ≈ 85 tok。high は 512px タイル数 × 170 + 85。
- **Gemini**: 画像はおおむね固定 ~258 tok/枚(モデルにより変動)。
- **PDF**: ページを画像化+テキスト抽出として課金されることが多い。`count_tokens`(Anthropic)
  や実測(T2/T3)で確定するのが確実。

換算結果を `context` に加算する。

## 7. 確度ラベル(`confidence`)

| 値 | 意味 |
|----|------|
| `measured` | T2/T3 で実測 |
| `counted` | T1 で正確カウント(出力は推定でも入力が exact なら可) |
| `estimated` | T0 静的推定/仮定 |

各 call に付け、レポートに表示される。仮定は `assumptions[]` に明文化する。

## 8. シナリオ JSON スキーマ(全フィールド)

```jsonc
{
  "meta": { "app_name", "flow_name", "analyzed_at", "measurement_tier", "notes" },
  "compare_models": ["<model id>", ...],          // 省略時は simulate.py --compare
  "calls": [{
    "id", "label", "model",                        // model は pricing.json の id
    "source_ref",                                  // "file:line"
    "confidence": "measured|counted|estimated",
    "runs_per_flow": 1,                            // このフローで何回呼ばれるか
    "batch": false,                                // Batch API か
    "tokens": {
      "system", "tools", "context", "history", "user_input",  // full-price 入力
      "cacheable_prefix",                          // または cache_read/cache_write
      "cache_read", "cache_write", "cache_write_ttl",
      "output", "thinking"
    },
    "agent_loop": { "iterations", "history_growth_per_iter",
                    "cached_prefix_tokens", "history_cached" },
    "assumptions": ["…"]
  }],
  "projection": {
    "volumes": [1,100,1000,10000,100000,1000000],
    "monthly_volume": 30000,
    "dau_scenarios": [100,1000,10000],
    "flows_per_user_per_day": 3,
    "cache_hit_rate": 0.7
  }
}
```

## 9. コスト式(per call, per execution)

```
full_input = system+tools+context+history+user_input
write_rate = input × (ttl=="1h" ? 1h_mult : 5m_mult)
read_rate  = cached_input(あれば) または input × cache_read_mult
cost = ( full_input × input
       + cache_read × read_rate
       + cache_write × write_rate
       + (output+thinking) × output ) / 1e6
cost ×= batch ? batch_mult : 1
cost ×= runs_per_flow
```

階層料金(`context_tiers`)は full_input+cache の合計で判定して単価を差し替える。
