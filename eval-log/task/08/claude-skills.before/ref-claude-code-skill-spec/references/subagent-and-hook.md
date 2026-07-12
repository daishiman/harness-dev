# Subagent / Agent Teams / hooks（17章圧縮）

## Subagent

- 独立した context・独立した system prompt を持つLLM呼出
- `agent: general-purpose` で起動
- 親に返るのは STDOUT のみ
- 採点・批判・専門タスクに向く

## Agent Teams

- 複数 subagent が役割分担して1タスクを完遂
- 典型構成:
  - Planner（計画）
  - Worker（実装）
  - Critic（採点）= assign-*-evaluator
- Skill は Agent Teams の各役へ割当可能

## hooks

| event | timing |
|---|---|
| `UserPromptSubmit` | ユーザー入力直後 |
| `PreToolUse` | tool 実行前 |
| `PostToolUse` | tool 実行直後 |
| `Stop` | 会話終了 |
| `Notification` | 通知時 |

設定: `~/.claude/settings.json` の `hooks` キー。
Skill 内 `hooks/<event>.sh` を参照させる構成も可。

## 連携パターン

### A. evaluator を hook から呼ぶ

PostToolUse(Write) で `assign-skill-design-evaluator` 起動 → score 80 未満なら警告。

### B. delegate Skill から subagent 起動

`delegate-general-purpose` の Step 1 で subagent 呼出 → 結果を整形して返す。

### C. Agent Team の Critic 役

`assign-*-evaluator` を Critic として配置。Goodhart 防止のため必ず fork。

## アンチパターン

- subagent 内で更に subagent を呼ぶ深い再帰（context 爆発）
- hook で長時間 blocking 処理（応答性劣化）
- evaluator subagent が Write tool を持つ（採点者が被採点物を改変、Goodhart）
