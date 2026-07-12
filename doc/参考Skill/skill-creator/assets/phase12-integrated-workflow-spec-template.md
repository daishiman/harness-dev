# Phase 12 統合 workflow 正本テンプレート

> **用途**: `references/workflow-<feature>.md` を新規作成し、cross-cutting follow-up の実装内容、苦戦箇所、5分解決カード、SubAgent 分担、検証証跡を 1 ファイルへ集約する。
> **使う条件**:
> - 更新先が 4 仕様書以上に分散する
> - `task-workflow.md` / `lessons-learned.md` / domain spec だけでは全体像を再現しにくい
> - preview/search、guard、pointer sweep、theme remediation のように UI/状態/運用/検証が横断する
> **同時更新先**:
> - `indexes/resource-map.md`
> - `indexes/quick-reference.md`
> - 対象 skill の `SKILL.md`
> - 必要なら `LOGS.md`

---

## 1. ヘッダー

```markdown
# <feature-name> ワークフロー仕様

> 本ドキュメントは AIWorkflowOrchestrator の仕様書です。
> 管理: `.claude/skills/aiworkflow-requirements/references/`
> テンプレート: `skill-creator/assets/phase12-integrated-workflow-spec-template.md`
> 派生元: `phase12-system-spec-retrospective-template.md` / `phase12-spec-sync-subagent-template.md`
```

---

## 2. 概要ブロック

```markdown
## 概要

`<TASK-ID>` で実装した `<feature-name>` の統合正本。
今回の実装内容、苦戦箇所、SubAgent 分担、検証値、再利用手順、最適なファイル形成を 1 ファイルへ集約し、次回の同種課題で複数仕様書を横断検索しなくて済むようにする。

**トリガー**: `<再発しやすい症状を3-6個>`
**実行環境**: `<worktree / app / workflow / screenshot / validator など>`
**検索キーワード**: `<feature keyword>`, `<helper>`, `<validator>`, `<fallback>`
```

---

## 3. 仕様書別 SubAgent 編成

```markdown
## 仕様書別 SubAgent 編成

| SubAgent | 関心ごと | 主担当仕様書 / 実装 | 目的 |
| --- | --- | --- | --- |
| SubAgent-A | `<search/ui/helper/state>` | `<files / spec docs>` | `<責務を1行>` |
| SubAgent-B | `<transport/error/retry>` | `<files / spec docs>` | `<責務を1行>` |
| SubAgent-C | `<workflow/audit/docs>` | `<files / spec docs>` | `<責務を1行>` |
| Lead | integrated spec / lookup | `references/workflow-<feature>.md`, `indexes/resource-map.md`, `indexes/quick-reference.md`, `SKILL.md` | 次回の初動を 1 入口へまとめる |
```

---

## 4. 実装内容サマリー

```markdown
## 今回実装・更新した内容（YYYY-MM-DD）

| 観点 | 内容 | 主要ファイル |
| --- | --- | --- |
| `<観点1>` | `<何をどう変えたか>` | `<file-a>, <file-b>` |
| `<観点2>` | `<何をどう変えたか>` | `<file-c>, <file-d>` |
| `<観点3>` | `<何をどう変えたか>` | `<file-e>, <file-f>` |

### 実測サマリー

| 項目 | 値 |
| --- | --- |
| targeted vitest | `<x files / y tests PASS>` |
| typecheck | `PASS` / `FAIL` |
| eslint | `PASS` / `FAIL` |
| screenshot coverage | `<expected / covered>` |
| screenshot source | `<external-dev-server / static-build / N/A>` |
| phase output validation | `<count PASS>` |
| workflow spec validation | `<phase count PASS>` |
| current audit | `<current violations 0 など>` |
```

---

## 5. 苦戦箇所と標準ルール

```markdown
## 苦戦箇所と標準ルール

| 苦戦箇所 | 再発条件 | 今回の対処 | 標準ルール |
| --- | --- | --- | --- |
| `<課題1>` | `<再発条件>` | `<今回の対処>` | `<次回の標準ルール>` |
| `<課題2>` | `<再発条件>` | `<今回の対処>` | `<次回の標準ルール>` |
| `<課題3>` | `<再発条件>` | `<今回の対処>` | `<次回の標準ルール>` |
```

---

## 6. 同種課題の 5 分解決カード

```markdown
## 同種課題の 5 分解決カード

1. `references/workflow-<feature>.md` を起点に、domain spec / task / lessons の分担を先に決める。
2. helper / contract / state reset / error taxonomy の責務を最初に分ける。
3. UI タスクでは screenshot source と coverage validator を同一ターンで固定する。
4. workflow 監査では `verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` / `audit --target-file` の要否を先に判定する。
5. `resource-map.md` / `quick-reference.md` / `SKILL.md` まで直リンクを戻して、次回の入口を 1 本化する。
```

---

## 7. 最適なファイル形成

```markdown
## 最適なファイル形成

| 情報の種類 | 最適な反映先 | 理由 |
| --- | --- | --- |
| 実装全体像、SubAgent 編成、苦戦箇所、5分解決カード | `references/workflow-<feature>.md` | cross-cutting 全体像を 1 入口で再利用できる |
| 契約や UI の個別詳細 | `<domain-spec>.md` | ドメイン責務ごとに保守できる |
| 検証値、残課題、完了記録 | `task-workflow.md` | 台帳として追跡しやすい |
| 再発条件、短手順、失敗パターン | `lessons-learned.md` | 次回の初動短縮に直結する |
| 読み始めの導線 | `indexes/resource-map.md` / `indexes/quick-reference.md` / `SKILL.md` | 正本への入口を迷わせない |
```

---

## 8. 検証コマンド

```markdown
## 検証コマンド

| コマンド | 目的 | 合格条件 |
| --- | --- | --- |
| `<typecheck command>` | 型整合確認 | PASS |
| `<targeted test command>` | 対象回帰 | PASS |
| `<phase11 validator>` | screenshot coverage 確認 | PASS |
| `<phase12 validator>` | outputs / guide 監査 | PASS |
| `<verify-all-specs>` | workflow 仕様整合 | PASS |
| `<verify-unassigned-links>` | 未タスク参照整合 | PASS |
| `<audit --target-file>` | current violations 確認 | PASS |
| `<diff -qr .claude ... .agents ...>` | mirror sync 確認 | 差分なし |
```

---

## 9. 関連ドキュメント

```markdown
## 関連ドキュメント

| ドキュメント | 用途 |
| --- | --- |
| `[<domain-spec-a>.md](./<domain-spec-a>.md)` | `<用途>` |
| `[<domain-spec-b>.md](./<domain-spec-b>.md)` | `<用途>` |
| `[../../../docs/30-workflows/<workflow>/outputs/phase-12/implementation-guide.md](../../../docs/30-workflows/<workflow>/outputs/phase-12/implementation-guide.md)` | 実装詳細 |
| `[../../../docs/30-workflows/<workflow>/outputs/verification-report.md](../../../docs/30-workflows/<workflow>/outputs/verification-report.md)` | 検証値と補足 |
```

---

## 10. 完了チェック

- [ ] `references/workflow-<feature>.md` を新規作成している
- [ ] 実装内容と苦戦箇所が同一ファイルにそろっている
- [ ] 5分解決カードが `task-workflow.md` / `lessons-learned.md` と矛盾しない
- [ ] `indexes/resource-map.md` / `indexes/quick-reference.md` / `SKILL.md` に入口を追加している
- [ ] UI タスクでは screenshot source と coverage validator の結果を明記している
- [ ] `phase12-task-spec-compliance-check.md` または同等の root evidence へリンクしている
- [ ] canonical root と mirror root の同期方法を記録している
