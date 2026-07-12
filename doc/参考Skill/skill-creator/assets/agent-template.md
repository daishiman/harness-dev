# Task仕様書：{{TASK_TITLE}}

> **読み込み条件**: {{LOAD_CONDITION}}
> **相対パス**: `agents/{{FILE_NAME}}.md`

## 1. メタ情報

| 項目     | 内容             |
| -------- | ---------------- |
| 名前     | {{PERSONA_NAME}} |
| 専門領域 | {{EXPERTISE}}    |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

{{BACKGROUND}}

### 2.2 目的

{{PURPOSE}}

### 2.3 責務

| 責務 | 成果物 |
| ---- | ------ |

{{#each RESPONSIBILITIES}}
| {{this.task}} | {{this.output}} |
{{/each}}

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント | 適用方法 |
| ----------------- | -------- |

{{#each REFERENCES}}
| {{this.name}} | {{this.application}} |
{{/each}}

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション | 担当 |
| -------- | ---------- | ---- |

{{#each STEPS}}
| {{this.step}} | {{this.action}} | {{this.owner}} |
{{/each}}

### 4.2 チェックリスト

| 項目 | 基準 |
| ---- | ---- |

{{#each CHECKLIST}}
| {{this.item}} | {{this.criteria}} |
{{/each}}

### 4.3 ビジネスルール（制約）

| 制約 | 説明 |
| ---- | ---- |

{{#each CONSTRAINTS}}
| {{this.name}} | {{this.description}} |
{{/each}}

---

## 5. インターフェース

### 5.1 入力

| データ名 | 提供元 | 検証ルール | 欠損時処理 |
| -------- | ------ | ---------- | ---------- |

{{#each INPUTS}}
| {{this.name}} | {{this.source}} | {{this.validation}} | {{this.fallback}} |
{{/each}}

### 5.2 出力

| 成果物名 | 受領先 | 内容 |
| -------- | ------ | ---- |

{{#each OUTPUTS}}
| {{this.name}} | {{this.destination}} | {{this.content}} |
{{/each}}

{{#if OUTPUT_SCHEMA}}

#### 出力スキーマ

```json
{{OUTPUT_SCHEMA}}
```

{{/if}}

{{#if PRE_PROCESS}}

### 5.3 前処理（Script Task - 100%精度）

```bash
{{PRE_PROCESS}}
```

{{/if}}

{{#if POST_PROCESS}}

### 5.4 後続処理

```bash
{{POST_PROCESS}}
```

{{/if}}

---

## 6. アーキテクチャ層別責務

{{#if ARCHITECTURE_LAYERS}}

> このTaskが関与するElectronアーキテクチャ層と責務を定義する

| 層  | 責務 | 関連ファイル | 制約 |
| --- | ---- | ------------ | ---- |

{{#each ARCHITECTURE_LAYERS}}
| {{this.layer}} | {{this.responsibility}} | {{this.files}} | {{this.constraints}} |
{{/each}}

### 6.1 層間通信フロー

```
{{LAYER_COMMUNICATION_FLOW}}
```

### 6.2 層別セキュリティ境界

| 層               | 許可される操作                    | 禁止される操作                            |
| ---------------- | --------------------------------- | ----------------------------------------- |
| Renderer Process | DOM操作、UIイベント、IPC送信      | ファイルシステム直接アクセス、Node.js API |
| Preload Script   | contextBridge経由のAPI公開        | 任意のNode.js API公開                     |
| Main Process     | ファイルI/O、システムAPI、IPC受信 | DOM操作                                   |
| IPC Channel      | 型安全なメッセージパッシング      | 生のオブジェクト参照共有                  |

{{/if}}

---

## 7. 統合テスト連携【必須】

### 7.1 統合ポイント（API/IPC契約）

{{#if INTEGRATION_POINTS}}
| 統合ID | 種別 | エンドポイント/チャンネル | リクエスト型 | レスポンス型 | 契約バージョン |
| --- | --- | --- | --- | --- | --- |
{{#each INTEGRATION_POINTS}}
| {{this.id}} | {{this.type}} | {{this.endpoint}} | {{this.requestType}} | {{this.responseType}} | {{this.version}} |
{{/each}}
{{else}}
| 統合ID | 種別 | エンドポイント/チャンネル | リクエスト型 | レスポンス型 | 契約バージョン |
| --- | --- | --- | --- | --- | --- |
| INT-001 | IPC | {{IPC_CHANNEL}} | {{REQUEST_TYPE}} | {{RESPONSE_TYPE}} | v1.0 |
{{/if}}

### 7.2 統合テストチェックリスト

| テストID | テスト内容 | 前提条件 | 期待結果 | 優先度 |
| -------- | ---------- | -------- | -------- | ------ |

{{#each INTEGRATION_TESTS}}
| {{this.id}} | {{this.description}} | {{this.precondition}} | {{this.expected}} | {{this.priority}} |
{{/each}}
{{#unless INTEGRATION_TESTS}}
| IT-001 | IPC通信の正常系 | Main/Renderer両プロセス起動 | 期待するレスポンス受信 | HIGH |
| IT-002 | IPC通信のエラーハンドリング | 不正なリクエスト送信 | エラーメッセージ返却 | HIGH |
| IT-003 | 型安全性の検証 | TypeScript型定義存在 | コンパイルエラーなし | MEDIUM |
| IT-004 | タイムアウト処理 | 応答遅延シミュレーション | タイムアウトエラー発生 | MEDIUM |
{{/unless}}

### 7.3 契約テスト（Contract Testing）

<!-- prettier-ignore-start -->
{{#if CONTRACT_TESTS}}
```typescript
{{CONTRACT_TESTS}}
```
{{else}}
```typescript
// IPC契約テストの例
describe('{{IPC_CHANNEL}} Contract', () => {
  it('should match request schema', async () => {
    const request: {{REQUEST_TYPE}} = { /* valid request */ };
    expect(validateRequest(request)).toBe(true);
  });

  it('should match response schema', async () => {
    const response = await ipcRenderer.invoke('{{IPC_CHANNEL}}', validRequest);
    expect(validateResponse(response)).toBe(true);
  });
});
```
{{/if}}
<!-- prettier-ignore-end -->

### 7.4 依存関係マトリクス

| このTask | 依存先Task | 統合ポイント | テスト方針 |
| -------- | ---------- | ------------ | ---------- |

{{#each DEPENDENCIES}}
| {{../TASK_TITLE}} | {{this.target}} | {{this.point}} | {{this.testStrategy}} |
{{/each}}
{{#unless DEPENDENCIES}}
| {{TASK_TITLE}} | 依存先なし | - | 単体テストのみ |
{{/unless}}

<!-- prettier-ignore-start -->
{{#if APPENDIX}}
---

## 8. 補足

{{APPENDIX}}
{{/if}}
<!-- prettier-ignore-end -->
