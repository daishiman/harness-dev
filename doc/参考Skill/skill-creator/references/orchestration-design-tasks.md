# 設計タスク向けオーケストレーション

設計タスク（Phase 1-3 中心）では実装タスクと異なるエージェント戦略が有効。SKILL.md entrypoint から退避した Phase 12 関連設計詳細を集約する。

## 設計タスクのフェーズ戦略

| Phase     | 実装タスクとの差異                                                             | 備考                                 |
| --------- | ------------------------------------------------------------------------------ | ------------------------------------ |
| Phase 4-8 | テスト作成・実装が「型定義・仕様書作成」に置き換わる                           | コードテストではなく仕様整合性テスト |
| Phase 9   | `pnpm lint/typecheck` ではなく `quick_validate.js` でゲート                    | 仕様書品質検証                       |
| Phase 11  | UI テストではなく設計文書ウォークスルー（SF-01）                               | NON_VISUAL 判定                      |
| Phase 12  | システム仕様書更新は2段階方式（SF-02）、未タスクは実装タスク4パターン（SF-03） | `phase-template-phase12.md` 参照     |

参考:
- [task-specification-creator/references/phase-template-phase11.md](../../task-specification-creator/references/phase-template-phase11.md) — SF-01（設計タスク向けウォークスルー）
- [task-specification-creator/references/phase-template-phase12.md](../../task-specification-creator/references/phase-template-phase12.md) — SF-02/SF-03（設計タスク向け補足）

## 設計タスク並列エージェント戦略

```
Phase 2（設計）並列実行可能なSubAgent分担例:
  SubAgent-A: 型定義・インターフェース設計
  SubAgent-B: API/IPC契約設計
  SubAgent-C: UI/UX仕様設計
  SubAgent-D: セキュリティ/権限設計
```

**注意**: 各SubAgentに割り当てるファイル数は3ファイル以下を推奨（P43対策）。

## Phase 12 再監査ショートカット

- `spec_created` / docs-heavy task を更新する時は、先に [task-specification-creator/references/phase-11-12-guide.md](../../task-specification-creator/references/phase-11-12-guide.md) と [task-specification-creator/references/spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md) を開く。
- SubAgent lane は `A: system spec`, `B: screenshot evidence`, `C: unassigned formalize`, `D: skill update + mirror` を基本形にする。
- [assets/phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md) と `assets/phase12-spec-sync-subagent-template.md` を同じターンで使い、system spec / lessons / backlog / skill update を分離して進める。
- `verify-unassigned-links --source <workflow>/outputs/phase-12/unassigned-task-detection.md`、`audit --diff-from HEAD`、`quick_validate.js` / `validate_all.js`、`diff -qr` をまとめて閉じる。
- NON_VISUAL / docs-heavy / env blocker task では、screen evidence の代替根拠、blocker の絶対パス、既存未タスクとの重複確認結果を同じターンで記録する。
- UI 再撮影がある場合は `theme lock → screenshot evidence → docs/spec sync` の順で閉じ、`NON_VISUAL` のまま止めず `SCREENSHOT + outputs` を優先する。

### Phase 12 skill feedback 反映

Phase 12 の `skill-feedback-report.md` に改善提案が出た場合は、次の順で処理する。

1. 既存 skill の reference に最小追記できる提案は同一 wave で反映する。
2. 新規テンプレート追加や agent 構造変更が必要な提案は、`unassigned-task-detection.md` に formalize する。
3. 反映先は `task-specification-creator`（Phase 運用）、`aiworkflow-requirements`（system spec / indexes / lessons）、`skill-creator`（SubAgent / orchestration / skill生成規約）に分ける。
4. canonical `.claude/skills/...` を編集し、mirror が存在する場合は mirror sync と `diff -qr` で閉じる。

ADR / topology drift タスクで頻出する改善は、Phase 1 の重複候補検索、base case 別差分マトリクス、Phase 4 doc-only grep、Phase 11 NON_VISUAL evidence の4点を優先して反映する。

## P43対策: SubAgent ファイル分割基準

| 状況                        | 対応                                               |
| --------------------------- | -------------------------------------------------- |
| 更新対象が4ファイル以上     | SubAgentを複数に分割し各3ファイル以下に制限        |
| 単一AgentへのRate limit懸念 | ファイルグループを先に決め、SubAgent割り当てを明示 |
| Phase 12 仕様書更新         | 3ファイル/SubAgent に分割（P43 再発防止）          |

参考: [parallel-execution-guide.md](parallel-execution-guide.md)

## ベストプラクティス

| すべきこと                           | 避けるべきこと                    |
| ------------------------------------ | --------------------------------- |
| 問題を先に特定する（Problem First）  | 機能から設計を始める              |
| Core Domainに集中する                | 全体を均等に設計する              |
| Outcomeでゴール定義                  | Outputでゴール定義する            |
| Script優先（決定論的処理）           | 全リソースを一度に読み込む        |
| LLMは判断・創造のみ                  | Script可能な処理をLLMに任せる     |
| Progressive Disclosure               | 具体例をテンプレートに書く        |
| クロススキル参照は相対パスで         | 絶対パスやハードコードで参照      |
| SubAgentは3ファイル以下/エージェント | 多数ファイルを1エージェントに集中 |
| エージェントプロンプトはprompt-creatorで生成 | skill-creator内で独自フォーマットのプロンプトを書く |
| 1プロンプト5000文字以内・単一責務 | 複数責務を1ファイルに詰め込む |

> **自己参照ノート**: skill-creator自体がクロススキル参照パターンの実例。
> `resolve-skill-dependencies.md` で設計した参照構造は、skill-creatorが他スキルの
> SKILL.mdを読み込んで公開インターフェースを特定する際のパターンそのもの。
