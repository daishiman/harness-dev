---
name: llm-cost-simulator
description: >
  任意のアプリのコードベースを解析して LLM API 呼び出し箇所を洗い出し、「1 回の処理(フロー)で
  どれだけのトークン/費用がかかるか」「N 件・DAU 規模でいくらか」を根拠付きで試算するスキル。
  プロンプト/ツール定義/RAG/エージェントループ/キャッシュ/思考トークンまで合算し、無料 or 確認付き
  有料の実測でグラウンディングする。成果物は Markdown レポート + 対話 HTML 計算機 + コスト JSON。
  「このアプリの API コストはいくら」「モデル別/件数別の費用」「LLM の ROI 試算」「トークン数を数えて」
  「1リクエストいくら」等で起動。既定スタックの必須スキルではない optional 群であり、AI 機能を含む要件で明示された場合、
  または app-orchestrator が v1 前・AI 機能変更時の試算として指示した場合のみロードする。
---

# LLM Cost Simulator

LLM を呼ぶアプリの **1 フローあたりのトークン数と費用を、根拠を持って算出する** ための
ワークフローとツール群。「なんとなく高そう」を「この処理は $X、月 N 件で $Y、Haiku なら 1/30」
に変える。

## いつ使うか

- アプリのコードを見て「この 1 回の処理でいくらかかるか」を知りたい
- モデル/プロバイダ別、件数別、DAU 別のコストを比較・投影したい
- 本番運用の ROI / 採算ラインを根拠付きで説明したい
- 単に「この処理に何トークンかかるか」を実測したい

## 中核の考え方 — グラウンディング・ラダー

数値には必ず **確度ラベル** を付ける。安いものから順に積み上げる:

| Tier | 内容 | コスト | 使う場面 |
|------|------|--------|---------|
| **T0** | 静的推定。コードを読みテンプレ長をトークナイザで数え、可変部は仮定 | 無料 | 最初の概算 |
| **T1** | 無料の正確入力カウント。Claude=`count_tokens`(無料エンドポイント) / OpenAI=tiktoken(ローカル) | 無料 | 入力トークンを確定 |
| **T2** | **Claude Code/サブスク枠で代表処理を 1 回実行**し `usage` から出力を実測。非 Claude なら proxy で出力長サンプル | サブスク内/極小 | 出力トークンを実測 |
| **T3** | 実プロバイダで ground-truth | **実費発生** | 最終確認・厳密化 |

**お金が発生する操作(T3, および API キー従量課金の実 API 呼び出し)は、必ず事前にユーザーへ
見積もりを提示し承諾を得てから実行する。** 既定は T0→T1→T2 の無料経路。

## ワークフロー

### 1. Discover — LLM 呼び出し箇所を全部洗い出す

コード全体を grep して呼び出し点・モデル・設定を特定する:

```bash
# プロバイダ SDK / エンドポイント / モデル名 / 主要パラメータ
rg -n -i \
  -e 'anthropic|@anthropic-ai|messages\.create|messages\.stream|count_tokens|claude-[0-9]' \
  -e 'openai|OpenAI\(|chat\.completions|responses\.create|\bgpt-[0-9]|\bo[1-4]\b' \
  -e 'generativeai|genai|GenerativeModel|generateContent|gemini-[0-9]|vertexai' \
  -e 'langchain|ChatOpenAI|ChatAnthropic|ChatGoogleGenerativeAI|llama_index|litellm' \
  -e 'max_tokens|max_completion_tokens|tool_choice|tools\s*[:=]|system\s*[:=]|effort|thinking|budget_tokens' \
  -e 'api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com|OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY' \
  --glob '!**/node_modules/**' --glob '!**/.venv/**'
```

各ヒットについて記録: ファイル:行 / プロバイダ / モデル / どのユーザー操作(フロー)に属するか。
1 つのフローが複数呼び出しを誘発する(分類→生成→エージェントループ等)点に注意。

### 2. Characterize — 各呼び出しのトークン構成を読む

呼び出しごとに **入力を構成する全要素** を集める。詳細な計上ルールは
[references/methodology.md](references/methodology.md):

- **入力**: system プロンプト / **ツール・関数定義の JSON スキーマ(毎回送られる。忘れやすい)** /
  few-shot / **RAG 注入(チャンク tok × 件数 k)** / 会話履歴 / ユーザー入力 / 画像・PDF(プロバイダ別式)
- **出力**: `max_tokens` は上限。可能なら T2 で実測。**思考/推論(thinking/reasoning)トークンは
  出力単価で課金され、しばしば支配的** — 必ず計上。
- **倍率**: エージェントループの反復数(履歴が毎ターン累積する=コスト爆発要因) / リトライ /
  ファンアウト / 1 フローあたり実行回数。
- **割引機構**: プロンプトキャッシュ(安定 prefix の read ~0.1×) / Batch API(-50%)。

### 3. Assemble — シナリオ JSON を組み立てる

[examples/scenario.example.json](examples/scenario.example.json) を雛形にする。スキーマと
**重要な計上規約**(キャッシュ prefix を component 側と二重計上しない等)は
[references/methodology.md](references/methodology.md)。最小構成:

```json
{
  "meta": {"app_name":"…","flow_name":"…","analyzed_at":"…","measurement_tier":"T1+T2"},
  "compare_models": ["claude-opus-4-8","claude-sonnet-4-6","claude-haiku-4-5","gpt-4o","gemini-2.5-flash"],
  "calls": [
    {"id":"c1","label":"…","model":"claude-haiku-4-5","source_ref":"src/x.ts:12",
     "confidence":"counted","tokens":{"system":350,"user_input":220,"output":40}}
  ],
  "projection": {"monthly_volume":30000,"dau_scenarios":[100,1000,10000],
                 "flows_per_user_per_day":3,"cache_hit_rate":0.7}
}
```

### 4. Measure — 実測でグラウンディング(任意だが推奨)

代表的な入力で probe JSON を作り `measure.py` を実行:

```bash
# T1: 無料の正確入力カウントのみ
python3 scripts/measure.py probe.json

# T2: Claude(サブスク枠)で出力を 1 回実測。非 Claude 対象なら proxy を指定
python3 scripts/measure.py probe.json --run --proxy-model claude-haiku-4-5

# T3: 実プロバイダで ground-truth(実費。--yes-spend かつ対話確認が必要)
python3 scripts/measure.py probe.json --run --yes-spend
```

得た実測値(出力 min/avg/max、exact 入力)をシナリオの該当 call の `tokens` に反映し、
`confidence` を `measured`/`counted` に更新する。詳細は
[references/measurement-modes.md](references/measurement-modes.md)。

### 5. Simulate — レポート/HTML/JSON を生成

```bash
python3 scripts/simulate.py scenario.json --out-dir <app>/cost_out/ \
  --compare claude-opus-4-8,claude-sonnet-4-6,claude-haiku-4-5,gpt-4o,gpt-4o-mini,gemini-2.5-flash
```

出力(`--out-dir`):
- `cost_report.md` — 結論(1 フロー単価)、呼び出し内訳、モデル比較、件数/DAU 投影、
  キャッシュ感度、前提、推奨アクション、料金出典
- `calculator.html` — 自己完結の対話計算機(モデル切替・キャッシュ率・出力倍率・件数スライダー)
- `cost_model.json` — 機械可読のコストモデル

### 6. Report — ユーザーへ提示

1 フロー単価と月間/年間、最安候補との差、主要な前提と確度を要約。`verify` 確度の料金は
ROI 判断前に再確認するよう明示。

## 料金の鮮度ルール(重要)

- `data/pricing.json` が唯一の料金ソース。Anthropic は claude-api スキル由来で **authoritative**。
- **OpenAI / Google など非 Anthropic は `verify` 扱い。実際の ROI 判断の前に必ず公式ページで
  再確認**し、`data/pricing.json` を更新してから再計算する(URL は同ファイル `meta.refresh`)。
- 新モデル/新プロバイダは `data/pricing.json` の `models` に追記すれば自動で計算対象になる。
  料金詳細の意味(キャッシュ/バッチ/階層)は [references/pricing-notes.md](references/pricing-notes.md)。

## ファイル構成

- `scripts/engine.py` — コスト計算エンジン(依存なし)
- `scripts/measure.py` — トークン実測(T1/T2/T3)
- `scripts/simulate.py` — シナリオ→レポート/HTML/JSON
- `data/pricing.json` — 料金表(拡張可能)
- `templates/calculator.html.template` — 対話計算機テンプレート
- `examples/scenario.example.json` — シナリオ雛形
- `references/` — methodology / measurement-modes / pricing-notes

## 設計原則

- **すべての数値に確度ラベルと出典**。推測と実測を区別する。
- **無料がデフォルト**。お金が動く前に必ず承諾を取る。
- **計上漏れを潰す**: ツール定義・思考トークン・履歴累積・キャッシュ書込みは見落としやすい。
- 結論は常に「1 フロー単価 → 件数スケール」で示し、意思決定に直結させる。
