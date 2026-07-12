# 10. Subagents / Hooks 連携の設計判断

## このファイルの責務

Skill ↔ Subagent ↔ Hooks の **設計判断・Hook を選ぶ基準・Skill 設計から見た適用例** を保持する。Subagent frontmatter 全項目、Hook event 全一覧、Hook decision JSON schema は記載しない。

**更新責務マトリクス**: Subagent frontmatter / Hook event / decision schema の公式変更は `17` のみ更新する。本ファイルは「どの Hook で何を gate するか」「Skill 設計から見てどう使うか」が変わったときだけ更新する。

→ Subagent frontmatter 全項目: [17-agent-teams-reference.md §2.1](./17-agent-teams-reference.md#21-subagent-frontmatter-全項目公式)
→ Skill と Subagent の 2 方向 / `skills:` preload: [17 §2.1](./17-agent-teams-reference.md#21-subagent-frontmatter-全項目公式)
→ 公式 Hook event 一覧 / decision schema / exit code 2 挙動: [17 §2.1](./17-agent-teams-reference.md#21-subagent-frontmatter-全項目公式)
→ Agent Team quality gates: [17 §11](./17-agent-teams-reference.md#11-quality-gates-with-hooks)

## 設計判断 1: Skill と Subagent の選択基準

| ねらい | 推奨 | 理由 |
|---|---|---|
| 親会話と独立に重い調査 | Skill `context: fork` | Skill 単位で完結、再現性が高い |
| reusable な role（複数 Skill から使う） | Subagent + `skills:` preload | role を 1 箇所に集約、Skill は薄く保てる |
| 結果だけ親に戻す軽い委譲 | Subagent（task tool 経由） | overhead 最小 |
| 複数視点を並列に競わせる | Agent Team（→ [17](./17-agent-teams-reference.md)） | inter-agent messaging が必要 |

## 設計判断 2: `skills:` preload を使うか Skill tool 呼び出しか

- **preload する**: subagent 起動時に常に必要、かつ description だけでは不十分な reference。
- **Skill tool で都度呼ぶ**: 条件次第で必要、context を節約したい。

注意（公式制約）:

- `disable-model-invocation: true` の Skill は **preload できない**。
- `skills` は access 制御ではない。**未列挙 Skill も Skill tool で呼べる**。Skill tool 自体を防ぐなら `tools` / `disallowedTools` を使う。

## 設計判断 3: 自然言語ではなく Hook で守る

Skill 本文に「○○してはいけない」と書いても Claude は破ることがある。**決定論で守れる境界は Hook に移す**。Skill は hook の存在と結果解釈を本文に書く。

| やりたいこと | 推奨手段 |
|---|---|
| 危険 command を絶対 block | `PreToolUse` hook + `permissions.deny` |
| evaluator 出力 schema 検証 | `SubagentStop` hook |
| 完了前のテスト必須化 | `TaskCompleted` hook（exit 2）または `Stop` hook |
| compaction を跨ぐ goal 引継ぎ | `PreCompact` で handoff 生成 → `PostCompact` で再読込 |
| SKILL.md 編集時の lint | `FileChanged` hook |
| `/deploy` 直叩きに追加確認 | `UserPromptExpansion` hook |

## 設計判断 4: Hook と permission の優先順位

PreToolUse hook の allow は permission deny / ask を **bypass しない**（公式: blocking hook は allow rule より優先）。設計則:

- 「絶対禁止」は `permissions.deny` に書く。Hook はそれを補強する。
- Hook の allow は「permission が ask になる箇所を黙って通す」用途にだけ使う。
- decision JSON schema は [17 §2.1](./17-agent-teams-reference.md#21-subagent-frontmatter-全項目公式) を参照。

## 設計判断 5: Skill 設計で使う Hook 例（実用パターン）

- `PreToolUse`: `git push`, `rm -rf`, production deploy を block。
- `UserPromptExpansion`: `/deploy` direct invocation に追加確認。
- `SubagentStop`: evaluator が想定 JSON schema を返したか検査。schema 違反は exit 2 で block。
- `PreCompact`: handoff file を `.claude/handoff/<session>.md` に生成。
- `PostCompact`: handoff file を Read して goal / next steps を復元。
- `FileChanged`: `SKILL.md` frontmatter を YAML lint。`description` 1,536 cap 超過を検出。
- `TaskCreated`（Agent Team）: file ownership が他 teammate と衝突する task を block。
- `TaskCompleted`（Agent Team）: evaluator JSON / 必要 artifact がない completion を block。
- `TeammateIdle`: 必要 artifact がないのに idle 入りを block し作業継続。

## 設計判断 6: Agent Team で同一 file 編集を避ける

Agent Team は same-file edits に弱い（→ [17 §2](./17-agent-teams-reference.md#2-いつ使うか)）。Skill 側で task を生成するときに、**task ごとの file ownership を frontmatter に書く** 運用を推奨する。`TaskCreated` hook がそれを検査する設計とセットで使う。

## 設計判断 7: Hook競合解決の意思決定フロー

同一 Skill で複数 Hook が同時/連鎖発火する場合、**決定論的な優先順位と責務分離** を明文化しないと「allow が deny を上書きしたつもり」「Hook で access 制御したつもり」といった事故が起きる。本節は競合パターンと解決則をまとめる。

### 7.1 競合パターン分類

| パターン | 例 | リスク |
|---|---|---|
| 同イベントで複数 Hook 発火 | `PreToolUse` に 2 つの hook が登録され、片方が allow / 片方が deny を返す | 決定が不定に見える / 設定漏れに気付けない |
| 異イベントが連鎖発火 | `PreToolUse` allow → tool 実行 → `PostToolUse` で deny相当の判定 | 既に副作用が出てから止める形になる |
| Hook × `permissions.deny` の組合せ | `PreToolUse` が allow を返すが `permissions.deny` に該当 | allow は deny を **bypass しない**（公式） |
| Hook × `permissions.allow` | blocking hook が deny、`permissions.allow` に該当 | blocking hook が **優先** される |

### 7.2 決定論的優先順位

1. **イベント種別**: blocking（`PreToolUse` / `SubagentStop` / `Stop` / `PreCompact` 等）が non-blocking より先に評価される。
2. **登録順**: 同一イベント内では settings の登録順に評価し、**最初に deny / exit 2 を返した hook で確定**（fail-fast）。
3. **permissions との関係**: `permissions.deny` は常に最優先。blocking hook は `permissions.allow` より優先するが、`permissions.deny` は上書きできない。

### 7.3 決定木（ASCII）

```
              tool 呼び出し
                   │
                   ▼
        ┌─────────────────────┐
        │ permissions.deny に  │ ── match ──▶ BLOCK（hook 評価せず）
        │     match するか    │
        └─────────────────────┘
                   │ no match
                   ▼
        ┌─────────────────────┐
        │ PreToolUse hooks 順 │ ── deny/exit2 ─▶ BLOCK（後続 hook 評価せず）
        │     に評価          │
        └─────────────────────┘
                   │ all allow / no decision
                   ▼
        ┌─────────────────────┐
        │ permissions.allow / │ ── ask ─▶ ユーザ確認
        │       ask 判定      │ ── allow ▶ tool 実行
        └─────────────────────┘
                   │ allow
                   ▼
              tool 実行 ─▶ PostToolUse hooks（副作用後の検査）
```

### 7.4 二段防御パターン

**一段目（宣言的・静的）**: `permissions.deny` で「絶対禁止」を declare する。compound command を含めて文字列 match なので、`Bash(rm:*)` 等の rule で広く塞ぐ。

**二段目（動的・文脈依存）**: `PreToolUse` hook で「文脈次第で危険」なケースを deterministic に判定する。例: 引数の path が `.claude/` 配下、現在 branch が `main`、target が production env など。

この二段で「permission rule の文字列 match の限界」と「自然言語禁則の不確実性」の両方を埋める。`PostToolUse` は副作用後の audit / cleanup 用途であり、access 制御の責務には置かない。

### 7.5 アンチパターン

- **Hook で access 制御**: `permissions.deny` を書かずに `PreToolUse` hook の allow/deny だけで守る。hook 設定ミスや disable で素通りする。`permissions.deny` を必ず併用する。
- **同イベント複数 hook で矛盾判定**: hook A が allow、hook B が deny を返す構成。登録順依存で読み取り困難になる。判定 hook は **同一イベントにつき 1 つ** に集約する。
- **PostToolUse で禁止を表現**: 副作用が出てからの block は意味がない。禁止は `PreToolUse` + `permissions.deny`、`PostToolUse` は検査・通知に限定。
- **`disableAllHooks` 想定外**: settings で hooks が無効化されても安全側に倒れるよう、`permissions.deny` を一段目に必ず置く。

→ `permissions` 側からの併用ルール: [04 §権限とHookの併用パターン](./04-invocation-permissions-settings.md#権限とhookの併用パターン)

## 設計則のまとめ

1. **Skill は判断と入口、Subagent は role、Hook は境界**。
2. 自然言語の禁則より、permission deny + Hook の二段で守る。
3. preload は重い reference に限定し、access 制御と混同しない。
4. compaction を跨ぐ workflow は handoff file と Hook で再現性を担保する。
