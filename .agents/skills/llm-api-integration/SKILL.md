---
name: llm-api-integration
description: >
  アプリケーションに LLM API(OpenAI / Anthropic / Gemini 等)を組み込む際のコスト最適化・セキュリティ・運用の必須パターン集。
  「AI機能を付けて」「AIで読み取り」「画像認識」「PDFから抽出」「OCR」「自動分類」「レコメンド」「AI連携」「OpenAI APIを使う」
  「チャットボット」「LLMを組み込む」などの文脈で、新規アプリ・既存アプリを問わず必ず使用する。
  ユーザーが「AI」と明示しなくても、非構造データ(画像/PDF/自由文)からの情報抽出・分類・判別の要件が含まれるなら必ずこのスキルを読むこと。
  AI機能のコスト見積・APIキー管理・利用量ダッシュボードの設計・レビューでもトリガーする。
  実測グラウンディング付きの費用試算が必要な場合は Skill llm-cost-simulator を併用。
  既定スタック(社内業務アプリ、mvp-first)の必須スキルではない optional 群。上記の AI 要件が要件定義で明示された場合、
  または app-orchestrator の要件フラグ「AI機能あり」で指示された場合のみロードする。
---

# LLM API 組み込みの必須パターン

収益不動産マッチングシステム(物件概要書PDF/名刺画像 → gpt-5.4-mini で構造化抽出)で確立したパターン。
**5つの柱: ①AIは判別にだけ使う ②miniファースト ③Structured Outputs 必須 ④利用量の記録と可視化ページ ⑤APIキーの暗号化保持(個人+共有の2段構え)。**

---

## 1. 設計原則: AIは「判別」にだけ使う

LLM呼び出しはアプリの中で**最小の一点**に絞る。生成に使う前に、分類に落とせないか必ず検討する。

### 判断フロー(上から順に検討)

1. **コードで書けるか?** → 正規表現・ルールベースで足りるなら AI 不要(郵便番号、金額パース等)
2. **無料の代替があるか?** → ブラウザ内 OCR(Tesseract.js)等をデフォルト経路にし、AI はオプトインの「高精度モード」にする
3. **分類・判別に落とせるか?** → 非構造データ → **enum(選択肢)への分岐**だけを AI にやらせる。以降の表示・処理は既存の決定的コードに流す
4. **抽出か?** → Structured Outputs で JSON スキーマに強制。自由記述はさせない
5. **本当に自由生成が必要か?** → ここまで落とせない場合のみ生成タスクとして扱う(コストは桁で増えることを明記して合意を取る)

### 「enum分岐 + 決定的な後段」パターン

AI にカテゴリ判定だけさせ、カテゴリごとの文言・処理はコード側に持つ。出力トークンが激減し、品質も安定する。

```typescript
// AI がやるのはこれだけ(出力は数トークン)
property_type: "apartment_building" | "office_building" | "hotel"
             | "store" | "warehouse" | "land" | "other" | null

// 説明文・アイコン・後続処理はコード側の定義を引く(AI に書かせない)
const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = { ... }
```

### 「推測禁止 + 低信頼フラグ」パターン

抽出タスクでは幻覚を仕組みで抑え、人間のレビューに繋ぐ:

- 不明・判読不能な項目は **null**(推測で埋めさせない)とプロンプトに明記
- `low_confidence_fields: string[]` をスキーマに必ず含め、換算した値・不鮮明な値のフィールド名を列挙させる
- UI 側で low_confidence フィールドをハイライトし、人間が確認してから確定する導線にする

---

## 2. モデル選択とコスト制御

### miniファースト

- **既定は最安クラスの mini モデル**(例: gpt-5.4-mini)。判別・抽出タスクはこれで十分なことがほとんど
- 精度が出ないと**実測で確認できた場合のみ**上位モデルに切り替える。最初から上位を選ばない
- モデル名はハードコードせず **env var で切り替え可能に**しておく(precision 問題が出たら deploy なしで昇格できる):

```typescript
export const DEFAULT_MODEL = "gpt-5.4-mini"; // コスト重視の既定
export function extractionModel(env: AppEnv): string {
  return env.OPENAI_MODEL || DEFAULT_MODEL;
}
```

- モデル名・単価は実装時点の最新をドキュメントで確認する(訓練データの記憶で書かない)

### 推論強度を下げる

推論系モデル(GPT-5系等)は、判別・抽出タスクなら推論強度を最低にする。コストとレイテンシが大きく下がる:

```typescript
...(model.startsWith("gpt-5") ? { reasoning: { effort: "low" as const } } : {}),
```

### 入力側の上限(現実的なラインで止める)

「言われすぎない」ためのガードは入力側に置く:

- **ファイルサイズ上限**(例: 25MB)と **MIME タイプ許可リスト**をルートハンドラの先頭で検証
- 画像の `detail` は用途で選ぶ(細かい文字を読むなら high、分類だけなら auto/low)
- 自由入力をそのままプロンプトに流さない。長文はトリムし、必要な部分だけ渡す
- チャット型なら履歴を全部送らず直近 N ターン + 要約に圧縮する

### 支出の上限

- **プロバイダ側のハードリミット**(OpenAI なら Project ごとの Budget limit)を必ず設定する。アプリ側の制御はバグで抜けるが、プロバイダ側の上限は抜けない
- アプリ側にも月次概算のソフトリミットを持ち、閾値超過で警告 or AI 機能を一時停止できると更に良い

---

## 3. Structured Outputs は必須

自由テキストを返させて JSON.parse で祈るのは禁止。**json_schema + strict: true** で出力をスキーマに強制する(パース失敗・リトライループが消える = コスト削減でもある):

```typescript
const response = await client.responses.create({
  model,
  input: [
    { role: "system", content: systemPrompt },
    { role: "user", content: [contentPart, { type: "input_text", text: instruction }] },
  ],
  text: {
    format: { type: "json_schema", name: schemaName, strict: true, schema },
  },
});
const data = JSON.parse(response.output_text) as T;
```

- PDF は `input_file`(data URL)、画像は `input_image` で直接渡せる(OpenAI Responses API)
- スキーマの型定義はクライアント/サーバーで共有ファイルに置き、UI と AI の契約を一本化する
- プロンプトには**単位の正規化ルール**を明記する(「金額は円の整数」「面積は㎡、坪しかなければ換算して low_confidence_fields に入れる」等)。後段のコードが単位判定をしなくて済む

---

## 4. 利用量の記録と可視化ページ(必ず作る)

AI 機能を持つアプリには**利用状況ページを必ず1枚作る**。「いくら使ったか分からない AI 機能」はリリースしない。

### 記録: 全 AI 呼び出しが usage を返す契約にする

```typescript
// AI ラッパーの戻り値に usage を必須で含める
return {
  data: JSON.parse(text) as T,
  usage: {
    inputTokens: response.usage?.input_tokens ?? 0,
    outputTokens: response.usage?.output_tokens ?? 0,
  },
};

// 呼び出し側は必ず DB に記録(usage_log テーブル)
await insertUsage({
  userEmail: user.email,
  kind: "ai_extract",
  model: extractionModel(env),
  inputTokens: usage.inputTokens,
  outputTokens: usage.outputTokens,
  detail: { doc: "property", keySource: resolved.source }, // 何に・どのキーで使ったか
});
```

### 単価は env var、費用は「概算」と明記

```typescript
// 価格改定に追従できるよう単価はコードにハードコードしない
OPENAI_PRICE_IN_USD_PER_M=0.25
OPENAI_PRICE_OUT_USD_PER_M=2.0
USD_JPY_RATE=155
```

- 表示は「概算」であること、**請求の正はプロバイダの管理画面**であることをページ上に明記する
- 少額利用で「0円」表示にならないよう、10円未満は小数1桁で見せる(例: 「約0.3円」)

### 利用状況ページの構成(/usage)

1. **今月の概算費用**(円建て・大きく)+ USD とリクエスト回数
2. 入力/出力トークンの内訳
3. **利用者別の内訳テーブル**(誰が何回・いくら) — 認証があるアプリでは必須
4. 最近の利用ログ(種別・利用者・モデル・トークン・日時)
5. 従量課金の外部サービス(メール送信等)があれば無料枠の消費状況も同じページに載せる

---

## 5. APIキー管理: 個人キー + 共有キーの2段構え

### キー解決の優先順位

「会社で1個の共有キー」と「利用者が自分で入れる個人キー」を両立させる。解決順は **個人 → 共有 → なし**:

```typescript
export async function resolveApiKey(env: AppEnv): Promise<ResolvedApiKey> {
  const user = await getUser();
  // 1. 本人が設定した暗号化キー(D1に保存)
  if (env.KEY_ENCRYPTION_SECRET) {
    const row = await getUserApiKeyRow(user.email);
    if (row) {
      try {
        const apiKey = await decryptSecret(row.key_ciphertext, env.KEY_ENCRYPTION_SECRET);
        return { user, apiKey, source: "personal" };
      } catch (error) {
        console.error("api key decrypt failed:", user.email, error);
        // マスターキー変更等で復号不能 → 共有キーにフォールバック
      }
    }
  }
  // 2. 会社の共有キー(wrangler secret / 環境変数)
  if (env.OPENAI_API_KEY) return { user, apiKey: env.OPENAI_API_KEY, source: "shared" };
  // 3. キーなし → AI機能だけ無効。アプリ自体は動く
  return { user, apiKey: null, source: null };
}
```

- usage_log に `keySource`(personal/shared)も記録し、誰のキーで呼んだか追跡できるようにする

### 個人キーの暗号化保存(AES-GCM)

ユーザーがアプリ画面から入れるキーは**平文で DB に置かない**。マスターシークレット(wrangler secret 等、環境のシークレットストア)で AES-GCM 暗号化して保存する:

- マスターキー: `KEY_ENCRYPTION_SECRET`(任意の長いランダム文字列)を SHA-256 で 256bit 鍵に正規化
- 暗号化: AES-GCM、IV は 12byte ランダム、`base64(iv || ciphertext)` を DB に保存
- 復号は**サーバー内(Server Action / Route Handler)のみ**。平文キーをレスポンス・ログ・クライアントに一切出さない
- Web Crypto API(`crypto.subtle`)で実装できるので外部ライブラリ不要(Workers/Node 両対応)

### キー設定 UI の必須要件(/settings)

1. 入力形式のバリデーション(OpenAI なら `/^sk-[A-Za-z0-9_-]{20,}$/`)。不正形式は保存前に弾く
2. 保存後は**末尾4桁(last4)だけ**を表示。「二度と全文は表示されません」と明記
3. 「暗号化して保存する」等、**何が起きるかをボタン文言とヘルプで正直に説明**する(送信はHTTPS・保存はAES-GCM・呼び出しはサーバー内のみ)
4. 削除ボタンを必ず用意(削除後は共有キーにフォールバックすることも表示)
5. `KEY_ENCRYPTION_SECRET` 未設定ならこの機能自体を無効表示にする(中途半端に平文保存しない)
6. キーの発行場所(platform.openai.com 等)への案内を添える

---

## 6. グレースフルデグラデーション

AI が使えない状態でもアプリは成立させる:

- レスポンスに `aiAvailable: boolean` を含め、キー未設定なら**手入力・無料OCRモード**で同じフローを完走できるようにする
- AI 呼び出し失敗時のエラーメッセージは「読み取りに失敗しました。もう一度試すか、**手入力に切り替えてください**」のように**代替手段への導線**を含める
- AI を呼ばない保存専用モード(`mode=store`: 原本ファイルだけ保存)を用意すると、無料運用とAI運用を同じAPIで切り替えられる

---

## 7. 実装チェックリスト

設計時:
- [ ] AI 呼び出し箇所は最小の一点に絞ったか(判別/抽出だけか)
- [ ] enum 分岐に落とせる部分を自由生成にしていないか
- [ ] 無料の代替経路(ブラウザOCR・手入力)があるか
- [ ] mini モデルが既定か。モデル名は env var か

実装時:
- [ ] Structured Outputs(strict: true)を使っているか
- [ ] 推論系モデルで reasoning effort を下げたか
- [ ] 入力にサイズ上限・MIME 許可リストがあるか
- [ ] 不明項目は null + low_confidence_fields の契約か
- [ ] 全 AI 呼び出しで usage を DB に記録しているか
- [ ] 単価が env var 管理か(ハードコードしていないか)

運用機能:
- [ ] 利用状況ページ(/usage)があるか(月次概算費用・利用者別内訳)
- [ ] プロバイダ側の支出上限(Budget limit)を設定したか
- [ ] APIキーは 個人(AES-GCM暗号化) → 共有(secret) → なし の3段で解決されるか
- [ ] キー設定 UI は last4 のみ表示・削除可能・正直な説明付きか
- [ ] キーなしでもアプリの主要フローが完走するか
