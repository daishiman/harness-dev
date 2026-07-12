# 監査結果記録テンプレート

## 用途

Phase 12 実施中に `audit-unassigned-tasks --diff-from HEAD` と、必要に応じた `audit-unassigned-tasks --target-file ...` を実行した結果を、**current violations（本タスク新規）**と**baseline violations（既知の未解決）**に分離して記録するためのテンプレートです。

これにより、本タスク範囲での検証と、将来の修正対象の明確化ができます。

---

## 実行情報

### コマンド実行の詳細

| 項目 | 値 |
|------|-----|
| 実行日時 | {{YYYY-MM-DD HH:MM:SS}} |
| 実行者 | {{YOUR_NAME}} |
| 実行環境 | {{OS_VERSION}} (Node.js {{NODE_VERSION}}) |
| diff-from | HEAD（タスク着手時点） |
| 実行コマンド | `pnpm audit-unassigned-tasks --diff-from HEAD`（必要時: `pnpm audit-unassigned-tasks --target-file <path>` を併記） |
| 出力ファイル | {{output-filename.json}} |

### 実行環境確認コマンド

```bash
# 確認用（実行前に念のため確認）
node --version
pnpm --version
git rev-parse HEAD  # 着手時点のコミットハッシュ確認
```

---

## Current Violations（本タスク実施中に発生した新規違反）

**定義**: `audit --diff-from HEAD` または placement に応じた `audit --target-file` の実行結果で、`currentViolations` セクションに含まれる違反。  
本タスク実施中に新規に生成された仕様書・コードの不整合。

### 実行結果

| 項目 | 値 |
|------|-----|
| 違反数 (total) | {{CURRENT_TOTAL}} |
| 期待値 | **0** |
| 実績 | {{CURRENT_ACTUAL}} |
| **判定** | {{current_total === 0 ? "✓ PASS" : "✗ FAIL"}} |

### 違反詳細

#### パターン1: Current Violations が 0件（正常系）

```json
{
  "currentViolations": {
    "total": 0,
    "details": []
  }
}
```

**記録例**:

| # | 違反ID | 種別 | 説明 | 原因 |
|----|--------|------|------|------|
| - | - | - | 違反なし | 正常 |

**判定**: ✓ **PASS** → Phase 12 完了判定へ進む

---

#### パターン2: Current Violations が存在（異常系）

```json
{
  "currentViolations": {
    "total": 2,
    "details": [
      {
        "id": "NA-001",
        "type": "MISSING_SPEC",
        "description": "新規IPC handlerの仕様書未記載",
        "file": "apps/desktop/src/main/ipc-handlers.ts:42"
      },
      {
        "id": "NA-002",
        "type": "UNDOCUMENTED_CHANGE",
        "description": "AgentConfig型の新フィールド未記載",
        "file": "apps/desktop/src/main/agent-config.ts:15"
      }
    ]
  }
}
```

**記録例**:

| # | 違反ID | 種別 | 説明 | ファイル | 原因 |
|----|--------|------|------|---------|------|
| 1 | NA-001 | MISSING_SPEC | 新規IPC handlerの仕様書未記載 | ipc-handlers.ts:42 | api-ipc-*.md 更新漏れ |
| 2 | NA-002 | UNDOCUMENTED_CHANGE | AgentConfig型の新フィールド未記載 | agent-config.ts:15 | interfaces-*.md 更新漏れ |

**判定**: ✗ **FAIL** → 以下のいずれかで対応：

**対応方法1**: 仕様書更新（推奨）

- interfaces-agent.md に AgentConfig の新フィールドを追加
- api-ipc-agent.md に 新規 IPC handler の仕様を追加
- 修正後、再度 `audit-unassigned-tasks --diff-from HEAD` を実行し、必要なら `audit-unassigned-tasks --target-file <path>` も再実行

**対応方法2**: 未タスク化（Phase 12 Task 4）

- 違反を `unassigned-task/` に指示書として作成
- `task-workflow.md` の残課題テーブルに登録
- 関連仕様書に参照リンクを追加

---

## Baseline Violations（タスク着手前から存在する既知の違反）

**定義**: `audit --diff-from HEAD` または `audit --target-file <path>` の実行結果で、`baselineViolations` セクションに含まれる違反。  
本タスク着手前から存在する、未解決の仕様・実装の乖離。

### 実行結果

| 項目 | 値 |
|------|-----|
| 違反数 (total) | {{BASELINE_TOTAL}} |
| 本タスクへの影響 | **なし**（判定に影響しない） |
| 今後の対応 | 別タスクで対応予定 |
| **判定** | - （参考値として記録のみ） |

### 違反詳細

#### パターン1: Baseline Violations が 0件

```json
{
  "baselineViolations": {
    "total": 0,
    "details": []
  }
}
```

**記録例**:

| # | 違反ID | 種別 | 説明 | タスク化状況 |
|----|--------|------|------|-----------|
| - | - | - | 既知の違反なし | - |

**注記**: タスク着手時点で既知違反が0件という状態。望ましい状態です。

---

#### パターン2: Baseline Violations が存在

```json
{
  "baselineViolations": {
    "total": 3,
    "details": [
      {
        "id": "OLD-001",
        "type": "INCOMPLETE_SPEC",
        "description": "SkillExecutor の権限管理仕様が未完成",
        "file": "packages/shared/src/skill-executor.ts:28",
        "firstDetectedAt": "2026-02-15"
      },
      {
        "id": "OLD-002",
        "type": "TODO_COMMENT",
        "description": "P34 未解決: DI Setter Injection の詳細設計",
        "file": "apps/desktop/src/main/skill-service.ts:45",
        "firstDetectedAt": "2026-02-20"
      },
      {
        "id": "OLD-003",
        "type": "TEST_PENDING",
        "description": "SkillService の統合テスト 3件スキップ状態",
        "file": "apps/desktop/src/main/__tests__/skill-service.test.ts:120",
        "firstDetectedAt": "2026-02-18"
      }
    ]
  }
}
```

**記録例**:

| # | 違反ID | 種別 | 説明 | 初検出日 | 関連タスク | 優先度 |
|----|--------|------|------|---------|-----------|-------|
| 1 | OLD-001 | INCOMPLETE_SPEC | SkillExecutor権限管理仕様が未完成 | 2026-02-15 | TASK-FIX-7-1 | 高 |
| 2 | OLD-002 | TODO_COMMENT | P34 未解決: DI Setter Injection詳細設計 | 2026-02-20 | UT-FIX-7-1-DI-PATTERN | 中 |
| 3 | OLD-003 | TEST_PENDING | SkillService統合テスト3件スキップ | 2026-02-18 | UT-FIX-7-1-INTEGRATION-TEST | 中 |

**注記（重要）**: これらの違反は本タスク範囲外であり、本タスクの PASS/FAIL 判定に**影響しない**（FR-3 AC-3-2 準拠）。

**今後の対応**:

- 各違反に対し、関連タスク ID を記録
- 優先度を付与（高/中/低）
- 次のフェーズ（Phase 13 以降）でそれぞれのタスクとして対応

---

## 判定ルール

### Current Violations に基づく判定

| currentViolations.total | Phase 12 判定 | 理由 |
|------------------------|--------------|------|
| **0** | ✓ **PASS** | 本タスク範囲で新規違反がない。Phase 12 完了判定として OK |
| **> 0** | ✗ **FAIL** | 本タスク範囲で新規違反が発生。対応が必要 |

### Baseline Violations に基づく判定

| baselineViolations の有無 | Phase 12 判定への影響 | 理由 |
|--------------------------|------------------|------|
| 0件 | **影響なし** | 既知違反がない理想的な状態 |
| 1件以上 | **影響なし** | タスク着手前から存在する既知違反。本タスク範囲外 |

**重要**: baseline が多数あっても、current = 0 であれば Phase 12 は PASS です。baseline の削減は別タスク（未タスク化、または関連タスク）で対応してください。

---

## 判定フロー

```
audit コマンド実行
    ↓
JSON パース → current と baseline を分離
    ↓
current === 0？
    ├─ YES → Phase 12 PASS → 完了判定へ
    │
    └─ NO → Phase 12 FAIL → 対応フロー
            ├─ 仕様書更新で対応
            └─ または未タスク化して Task 4 へ
```

---

## 監査実行コマンド

### コマンド1: 基本形

```bash
# プロジェクトルートから実行
cd /Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator
pnpm audit-unassigned-tasks --diff-from HEAD
```

### コマンド2: JSON を整形して出力

```bash
cd /Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator
pnpm audit-unassigned-tasks --diff-from HEAD | jq . > audit-result.json
cat audit-result.json
```

### コマンド3: Current Violations のみ表示

```bash
cd /Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator
pnpm audit-unassigned-tasks --diff-from HEAD | jq '.currentViolations'
```

### コマンド4: Baseline Violations のみ表示

```bash
cd /Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator
pnpm audit-unassigned-tasks --diff-from HEAD | jq '.baselineViolations'
```

---

## 記録例（全体）

```json
{
  "metadata": {
    "executedAt": "2026-03-01T14:30:45.123Z",
    "executedBy": "leader",
    "taskId": "UT-IMP-PHASE12-SUBAGENT-NA-LOG-GUARD-001",
    "diffFrom": "HEAD"
  },
  "currentViolations": {
    "total": 0,
    "details": []
  },
  "baselineViolations": {
    "total": 2,
    "details": [
      {
        "id": "OLD-001",
        "type": "INCOMPLETE_SPEC",
        "description": "SkillExecutor権限管理仕様未完成",
        "relatedTask": "TASK-FIX-7-1",
        "priority": "高"
      },
      {
        "id": "OLD-002",
        "type": "TODO_COMMENT",
        "description": "P34: DI Setter Injection詳細設計",
        "relatedTask": "UT-FIX-7-1-DI-PATTERN",
        "priority": "中"
      }
    ]
  },
  "verdict": {
    "phase12Status": "PASS",
    "reason": "currentViolations.total === 0",
    "nextPhase": "Phase 13（PR作成）"
  }
}
```

---

## テンプレート使用フロー

### Phase 12 実行中（複数回実行）

1. **SubAgent 分担時**: 初回実行して baseline の全体像を把握
2. **各SubAgent 完了後**: 段階的に実行して current の増減を確認
3. **Phase 12 最終段階**: 最終実行で current === 0 を確認

### Phase 12 完了判定時（必須）

1. `audit-unassigned-tasks --diff-from HEAD` を**最後に一度実行**
2. currentViolations が 0件であることを確認
3. このテンプレートに結果を記録
4. `phase12-completion-guard-checklist.md` の P4 で確認

---

## FAQ

### Q: Current と Baseline をどう使い分ける？

**A**:

- **Current**: 本タスク実施中に新規に発生した違反。本タスク範囲での品質指標。
- **Baseline**: タスク着手前から存在する既知違反。過去の技術債。別タスクで対応。

本タスクの PASS/FAIL は **Current のみ** で判定します。

### Q: Baseline が100件あっても Phase 12 PASS？

**A**: はい。Baseline が何件あっても、Current === 0 であれば Phase 12 PASS です。

ただし、Baseline の削減計画を立てることをお勧めします。Baseline 違反は未タスク化し、優先度を付与して順次対応してください。

### Q: Current > 0 で FAIL した場合、どのくらい時間がかかる？

**A**: 原因により異なります：

- **仕様書更新漏れ**: 該当ファイルを修正して再実行（15-30分）
- **未タスク化**: Task 4 で指示書・リンク追加（30-60分）
- **複合原因**: 上記両方（45-90分）

修正後は必ず `audit-unassigned-tasks --diff-from HEAD` を再実行して検証してください。

### Q: 監査コマンドがエラーで実行できない

**A**: 以下を確認：

1. Node.js / pnpm がインストールされているか
2. プロジェクトルート（`/Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator`）から実行しているか
3. `pnpm install` で依存関係がインストールされているか

```bash
node --version  # v18.0 以上
pnpm --version  # 9.0 以上
```

---

## 関連ドキュメント

| ドキュメント | 参照する理由 |
|------------|-----------|
| `phase12-completion-guard-checklist.md` | P4 セクションで監査実行・確認方法 |
| `phase12-na-judgment-log-template.md` | N/A判定による違反回避方法 |
| `.claude/rules/05-task-execution.md` | Phase 12 全体フロー、P43対策 |
| `.claude/rules/06-known-pitfalls.md` | P42（.trim()バリデーション）、P43（rate limit） |
| `.claude/scripts/src/audit-output-parser.ts` | 監査出力パースの仕様 |

---

## チェックリスト：監査記録が完成したか

このテンプレートを記入し終わったら、以下をチェック：

- [ ] 実行情報（日時、実行者、環境）が記入されている
- [ ] currentViolations のセクション（total と details）が完成している
- [ ] baselineViolations のセクション（total と details）が完成している
- [ ] 判定ルールに基づいて Phase 12 判定を記入している
- [ ] current === 0 であることを確認している
- [ ] `phase12-completion-guard-checklist.md` の P4 へ報告している
