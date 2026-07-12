# transcript JSONL — live-trial 完了検知の一次情報源

> **版依存につき spec-drift 監視対象**: 本 ref のイベント型・subtype・フィールド名は
> Claude Code 内部仕様で無保証 (実測ベース 2026-06)。版が変わって分類が狂ったら
> `scripts/live-trial-status.py` の分類器と本 ref を実測で更新する
> (実測手順: `python3 -c` で各行 json.loads し type を集計する)。

`~/.claude/projects/<cwd-slug>/<session-id>.jsonl`。1 行 1 JSON。boot が
`claude --session-id <uuid>` で UUID を固定するためパスは決定的。**TUI 起動時では
なく初 prompt 送信時に生成** (boot の READY 検知が TUI capture のままなのはこのため)。
resume は同一ファイルに追記 (新ファイルなし)。判定実装は
`scripts/live-trial-status.py` (分類器) と `scripts/live-trial-poll.py` (利用側)。

## イベント型 14 種 = 3 群 (実測: 全 395 transcript)

| 群 | type | timestamp | 扱い |
|---|---|---|---|
| 会話 (判定の本体) | `user` / `assistant` / `system` | あり | 状態分類に使用 |
| 付帯 | `attachment` / `queue-operation` / `pr-link` | あり | 無視 (型フィルタで落ちる) |
| メタ状態 | `mode` / `permission-mode` / `last-prompt` / `bridge-session` / `ai-title` / `custom-title` / `agent-name` / `file-history-snapshot` | **なし** | timestamp フィルタで先頭除外 |

- `file-history-snapshot` は 9.3MB 単一行の実例あり → tail 増分読みは有害。全量 parse で
  十分速い (23MB 0.105s / 1MB 5-9ms)。

## ターン終端マーカー: `system` subtype=`turn_duration`

- 非 meta の prompt と **1:1 対応** (実測)。「最後の実 prompt より後に turn_duration が
  ある」= ターン完了。
- 実 prompt の判定 (`_is_real_prompt`): `type=="user"` かつ `isMeta!=true` かつ
  `isCompactSummary!=true` かつ content に text があり、`[Request interrupted` /
  `<command-name>` / `<local-command` を含まない。
- **interrupt 例外**: Esc 中断は turn_duration を出さず `[Request interrupted` の user 行を
  残す → これも終端扱いにしないと永久 busy 誤判定。
- `away_summary` / `stop_hook_summary` 等の他 system subtype は終端マーカーではない
  (turn_duration が先行する)。

## pending tool_use = busy / 対話 gate の判定軸

- assistant の `tool_use` id 集合 − user の `tool_result` tool_use_id 集合 = **pending**。
- **busy 中の jsonl は完全無音** (長 Bash で 192-207s、thinking で 63-70s のギャップ実測)
  → 経過時間で busy 判定は不可。pending の有無で `BUSY_TOOL_RUNNING` /
  `BUSY_GENERATING` を分ける。
- **対話 gate**: `AskUserQuestion` が pending のまま待つ (178s 待ちの実例) →
  `WAITING_USER_INPUT`。`ExitPlanMode` は実例ゼロのまま同型と推測 (E2E 要確認)。

## 状態分類 (live-trial-status.py の 4 状態)

1. pending に AskUserQuestion / ExitPlanMode → `WAITING_USER_INPUT`
2. 最後の実 prompt index > 最後の終端 index で pending あり → `BUSY_TOOL_RUNNING`
3. 同上で pending なし → `BUSY_GENERATING`
4. それ以外 → `IDLE_TURN_COMPLETE`

## 順序は配列 index で判定 (timestamp 比較は不可)

compact 後に timestamp 非単調の実例あり。「どちらが後か」は必ず行順 (配列 index) で
比較する。

## fork (Skill/Agent) 内実行の進捗合算

fork 内の長時間実行は main jsonl 無音のまま進む — `<session-id>/subagents/*.jsonl` の
bytes を `transcript_bytes()` が合算し、poll の構造的 STALL 誤報を防ぐ (既知 issue への対処)。

## 既知の限界・version 依存性

- **kill/crash したセッションは BUSY_GENERATING のまま凍結** (turn_duration が書かれない)
  → tmux 生存確認 (backend `has-session`) が最終フォールバックとして必須。
- 分類が狂ったら中央 `tests/test_live_trial_harness.py` の合成 fixture と本 ref を実測で
  更新する。
