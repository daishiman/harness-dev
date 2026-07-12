# Runtime ワークフロー仕様

Renderer から IPC 経由で駆動する Runtime Skill Creator ワークフローの詳細仕様。SKILL.md entrypoint から退避した内容を集約する。

## 状態遷移

```
plan → review (awaiting user input) → execute → verify → [pass] handoff
                ↑ needs_changes              ↑          → [fail] improve → reverify → ...
                └──────────────────┘         │
                ↑ reject (verification)      │
                └────────────────────────────┘
```

## submitUserInput phase transition semantics（TASK-SDK-04-U1）

`submitUserInput()` は `awaitingUserInput.reason` と `selectedOptionId` に基づき phase 遷移を適用する:

| reason                | selectedOptionId   | 遷移                                                   |
| --------------------- | ------------------ | ------------------------------------------------------ |
| `plan_review`         | `ready_to_execute` | currentPhase → `execute`                               |
| `plan_review`         | `needs_changes`    | currentPhase → `plan`                                  |
| `verification_review` | `approve`          | verifyResult: `pass` / `handoff`                       |
| `verification_review` | `improve`          | verifyResult.nextAction: `improve`                     |
| `verification_review` | `reject`           | currentPhase → `plan`, verifyResult: `fail` / `review` |

遷移発生時は `phase_transition` artifact（`fromPhase`, `toPhase`, `reason`, `selectedOptionId`）を記録する。未知の reason/option は no-op フォールバック。

## IPC チャネル

| Phase       | IPC チャネル                           | 型                                  |
| ----------- | -------------------------------------- | ----------------------------------- |
| plan        | `skill-creator:plan`                   | `SkillCreatorPlanResult`            |
| review      | `skill-creator:submit-user-input`      | `SkillCreatorUserInputRequest`      |
| execute     | `skill-creator:execute-plan`           | `SkillCreatorExecutePlanResult`     |
| verify      | `skill-creator:get-verify-detail`      | `RuntimeSkillCreatorVerifyDetail`   |
| reverify    | `skill-creator:reverify-workflow`      | `RuntimeSkillCreatorReverifyResult` |
| improve     | `skill-creator:improve-skill`          | `RuntimeSkillCreatorImproveResult`  |
| state query | `skill-creator:get-workflow-state`     | `SkillCreatorWorkflowState`         |
| state push  | `skill-creator:workflow-state-changed` | (event)                             |
| SDK 正規化  | `skill-creator:normalize-sdk-messages` | `SkillCreatorSdkEvent`              |

## plan エラーレスポンス（TASK-RT-01）

`RuntimeSkillCreatorFacade` の LLMAdapter からのエラーは `RuntimeSkillCreatorPlanErrorResponse` として propagate される（TASK-RT-01 で silent failure → explicit error response へ改善）。

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `status` | `"error"` | plan フェーズのエラーを示す固定値 |
| `degradedReason` | `RuntimeSkillCreatorDegradedReason` | 劣化理由（`llm_unavailable` / `api_key_missing` / `unknown` 等） |

Renderer はこのレスポンスを受け取った場合、`plan.status === "error"` + `degradedReason` で劣化状態を UI に表示する。

## AskUserQuestion MCP カスタムツール（TASK-SDK-SC-01）

SDK セッション（`SkillCreatorSdkSession`）は `createSdkMcpServer` + `tool` API で `AskUserQuestion` をカスタム MCP ツールとして提供する。ユーザー入力が必要なときは必ずこのツールを呼び出す。

**ツール名**: `AskUserQuestion`

| パラメータ    | 型                                                                 | 必須 | 説明                                               |
| ------------- | ------------------------------------------------------------------ | ---- | -------------------------------------------------- |
| `question`    | `string`                                                           | ✓    | ユーザーに提示する質問文                           |
| `type`        | `"single_select" \| "multi_select" \| "free_text" \| "secret" \| "confirm"` | —    | 入力種別（省略時は `free_text`）                   |
| `options`     | `Array<{ value?: string; label?: string; description?: string; preview?: string }>` | —    | `single_select` / `multi_select` 時の選択肢        |
| `placeholder` | `string`                                                           | —    | `free_text` 時の入力欄ヒント文字列                 |

呼び出し例:
```json
{
  "question": "インタビューの深度を選んでください",
  "type": "single_select",
  "options": [
    { "value": "quick",    "label": "Quick（最小限）" },
    { "value": "standard", "label": "Standard（推奨）" },
    { "value": "detailed", "label": "Detailed（詳細）" }
  ]
}
```

ツールが返す値はユーザーが入力したテキスト（`multi_select` の場合は JSON 配列文字列、`confirm` の場合は `"true"` / `"false"`）。

## ユーザー入力ブリッジ（5種）

| kind            | 用途                  | 例                      |
| --------------- | --------------------- | ----------------------- |
| `single_select` | 選択肢から1つ選択     | plan review の承認/却下 |
| `multi_select`  | 選択肢から複数選択    | interview で利用機能を複数選ぶ |
| `free_text`     | 自由テキスト入力      | フィードバックコメント  |
| `secret`        | 秘匿入力（APIキー等） | LLM API キー            |
| `confirm`       | Yes/No 確認           | reverify 実行確認       |

## Verify Detail Surface（layer3/layer4）

`RuntimeSkillCreatorVerifyDetail` は layer3（構造検証）と layer4（品質検証）の check を自動生成する。
各 check は `info` / `warning` / `error` の severity を持ち、`reverifyEligible` フラグで再検証可否を判定する。
`disabledReason` は 4段階（`no_plan` / `already_running` / `all_checks_pass` / `cooldown`）で UI の disable 理由を通知する。

## 動的リソース選択（PhaseResourcePlanner / SkillCreatorSourceResolver）

- **PhaseResourcePlanner**: max bytes ベースの context budget で `required-core` / `required-context` / `optional-quality` / `optional-deep-dive` の 4 tier にリソースを分類し、budget 超過時は下位 tier を自動カットする。
- **SkillCreatorSourceResolver**: manifest 定義と fallback 候補（`.claude/skills/skill-creator` / `.agents/skills/skill-creator`）の競合を structure signature で解決し、`manifest` / `bundled` / `project` の source mode を確定する。
- **SkillCreatorWorkflowSourceProvenance**: 解決結果を `resolvedSkillCreatorRoot` / `resourceDescriptorHash` / `manifestPath` / `manifestCacheKey` として plan result に埋め込む。

## Session Persistence & Resume（TASK-SDK-08）

- **`SkillCreatorPersistedWorkflowCheckpoint`**: phase boundary で生成される永続化単位。`checkpointId` / `planId` / `workflowStateSnapshot` / `revision` / `lease` を持つ。
- **`WorkflowCheckpointLease`**: stale write guard 用。`ownerInstanceId` / `leaseExpiresAt` / `acquiredAt` で排他制御する。
- **`ResumeCompatibilityResult`**: resume 可否評価結果。`status` / `reasons: ResumeIncompatibilityReason[]` / `warnings` を返す。
- **`ResumeIncompatibilityReason`**: `"version_mismatch"` | `"route_type_mismatch"` | `"manifest_cache_key_mismatch"` の3種。
- **`SkillCreatorWorkflowEngine.hydrateFromCheckpoint(checkpoint)`**: persisted checkpoint から `SkillCreatorWorkflowStateSnapshot` を復元するメソッド。

## SDKMessage 正規化（TASK-RT-06）

- **`SkillCreatorSdkEvent`**: `query()` が返す生 `SDKMessage` を lane 安定契約へ変換した結果型。`eventType: "init" | "assistant" | "result" | "error"` で分類。UI / IPC / WorkflowEngine はこの型のみを消費する。
- **`SkillCreatorSdkEventSourceProvenance`**: `sourceRoot` / `manifestHash` を含む source 解決結果。`SkillCreatorSdkEvent` に埋め込む。
- **`sdkMessageNormalizer.ts`**: `apps/desktop/src/main/services/runtime/` に配置。IPC チャネル `skill-creator:normalize-sdk-messages` 経由で提供する。

## verify → improve → re-verify 閉ループ（TASK-P0-02）

`verifyAndImproveLoop()` は verify → improve → re-verify のサイクルを自動的に回す閉ループパイプライン。

| フェーズ | 処理 |
| ------- | ---- |
| verify | `skill-creator:get-verify-detail` を実行し、check 結果を取得 |
| improve | `failedChecks`（error/warning）のみを LLM 改善入力に渡す。`info` は除外 |
| re-verify | improve 適用後に再度 verify を実行 |

**ループ制御**（`RuntimeSkillCreatorFacadeDeps.maxImproveRetry`）:
- デフォルト 3、範囲 1-10（範囲外は自動クランプ）
- 直前の improve 要約を次回 feedback に合成（feedback memory）し、同一修正の繰り返しを抑制
- 全 check PASS → `finalStatus: "pass"` で正常終了
- `maxImproveRetry` 到達 → `loopExhausted: true`、ユーザー判断を要求

**結果型**: `RuntimeSkillCreatorVerifyAndImproveResult`（`finalStatus`, `totalAttempts`, `finalChecks`, `loopExhausted`, `errorMessage?`, `workflowSnapshot`）

## execute() → SkillFileWriter persist 統合（TASK-P0-05）

`execute()` の Step 3.5-3.6 で LLM 応答からスキルコンテンツを抽出し、ファイルシステムへ永続化する。

**二重パイプライン設計**:

| 経路 | パイプライン | 正式度 | 説明 |
| --- | --- | --- | --- |
| A経路 | Facade → `parseLlmResponseToContent()` → `SkillFileWriter.persist()` | 正式経路 | execute() 内で直接コンテンツ抽出・永続化 |
| B経路 | `SkillCreatorOutputHandler` → `SkillRegistry` | 別系統 | IPC Bridge 経由のセッション完了時パイプライン |

**Setter Injection**: `SkillFileWriter` は `RuntimeSkillCreatorFacadeDeps.skillFileWriter?` で optional inject。未注入時は `console.warn` で警告し persist をスキップ（graceful degradation）。

**結果型拡張**: `SkillExecuteResult` に以下のフィールドを追加:
- `persistResult: PersistResult | null` - persist 成功時の書き込み結果
- `persistError: string | null` - persist 中の例外メッセージ（スキル実行自体の成否とは独立）

## Orchestrate モード

実行エンジン選択: `claude` | `codex` | `gemini` | `claude-to-codex`

詳細は [execution-mode-guide.md](execution-mode-guide.md) を参照。
