# Measurement Modes — 実測でグラウンディングする

`scripts/measure.py` の使い方と、4 ティアの意味・注意点。

## 認証(キーをハードコードしない)

- **Anthropic**: `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`、または `ant auth login`(OAuth)。
  Claude Code/サブスク利用者は OAuth プロファイルでサブスク枠を使える。
- **OpenAI**: `OPENAI_API_KEY`。
- いずれも環境変数 / SDK プロファイルから読む。スクリプトに鍵を書かない。

SDK 未導入時の挙動: `anthropic` 未導入なら T1(count_tokens)はスキップして警告、`tiktoken`
未導入なら OpenAI 入力はヒューリスティック(文字数/4)にフォールバックして `estimate` 扱い。

## probe JSON

代表的な「1 回の呼び出し」を再現する最小リクエスト:

```json
{
  "provider": "anthropic",
  "model": "claude-haiku-4-5",
  "system": "あなたは…",
  "tools": [ { "name":"…","description":"…","input_schema":{…} } ],
  "messages": [ { "role":"user", "content":"…代表的なユーザー入力…" } ],
  "max_tokens": 1024,
  "samples": 1
}
```

`system` と `tools` を入れると、それらも入力トークンに正しく含まれる(計上漏れ防止)。

## Tier ごとの実行

### T1 — 無料の正確入力カウント

```bash
python3 scripts/measure.py probe.json
```

- Anthropic: `messages.count_tokens`(課金なしの専用エンドポイント)で `input_tokens` を取得。
  画像/PDF/ツール込みで正確。**tiktoken は Claude に使わない**(15-20% 過小)。
- OpenAI: ローカル tiktoken。出力は別途。

### T2 — Claude(サブスク枠)で出力を実測

```bash
# 対象が Claude モデル
python3 scripts/measure.py probe.json --run --samples 3

# 対象が OpenAI/Gemini 等 → 安い Claude を proxy にして「出力長サンプル」を取る
python3 scripts/measure.py probe.json --run --proxy-model claude-haiku-4-5 --samples 3
```

- 実際に 1〜N 回生成し `usage`(input/output、キャッシュ内訳)を読む。出力 min/avg/max を返す。
- **proxy の注意**: 出力長はモデルで変わる。proxy(Claude)で測った出力トークンを対象モデルの
  単価で掛けるのは **推定**。レポートでは「出力長は proxy 由来の推定」と明示する。
  入力は対象モデルのトークナイザ(T1)で別途 exact に取る。
- サブスク利用者にとって T2 は実質「枠内」。API キー従量課金の場合は極小だが課金される点に留意。

### T3 — 実プロバイダで ground-truth(実費)

```bash
python3 scripts/measure.py probe.json --run --yes-spend   # 対話で最終確認
```

- 非 Anthropic の実 API を叩く。`--yes-spend` かつ対話 y/N の二重確認。**承諾なしに課金しない。**
- 最も正確。最終確定や、proxy 推定の妥当性検証に使う。

## 実測値のシナリオ反映

`measure.py` の出力 JSON から:
- `input_tokens_exact` → 該当 call の入力 component 合計の確定に使う(または `cache_read`/`cache_write`
  実測があれば明示方式で入れる)。
- `output_tokens.avg`(必要なら min/max でレンジ)→ `tokens.output`。
- reasoning モデルは出力に思考が含まれる。Anthropic は usage の output に思考込み。分離が必要なら
  `thinking` を別途見積もる。

反映後、`confidence` を `measured`/`counted` に更新し、`meta.measurement_tier` を記録する。

## 推奨フロー

1. まず T0(コード読解)でシナリオの骨子を作る。
2. 各 call の入力を T1 で exact 化。
3. 出力が読めない/支配的な call は T2 で実測(非 Claude は proxy)。
4. 採算判断に効くクリティカルな call だけ、必要なら T3 で確定。

「安い・無料」から始め、効くところだけ精度を上げる。全部を T3 で測る必要はない。
