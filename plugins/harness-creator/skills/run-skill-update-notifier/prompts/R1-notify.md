# Prompt: R1-notify

> 7 層プロンプトの Markdown 表現。Skill 実行末尾に installed と latest を比較し、食い違いがあれば 1 行だけ通知する (hook が systemMessage として利用者に表示する)。

## メタ

| key | value |
|---|---|
| name | notify |
| skill | run-skill-update-notifier |
| responsibility | R1+R2+R3 (単一 prompt が cache-check / formatting / graceful-guard を統括) |
| layers_covered | [L2, L4, L5, L6] |
| inputs | mode (subcommand: cache-status\|refresh\|notify, required。`--mode <name>` 前置も互換受理) |
| outputs | notify の stdout 1 行 or 空 (hook が systemMessage の JSON に包む。判定の内部モデルは schemas/output.schema.json) |

## Layer 1: 基本定義層

- 最上位目的: 同じツリー内の installed と latest を比較し、食い違いがあれば作者に向けて 1 行だけ通知。配布元とは比べない。
- 背景: 頻繁な通知は UX を損なう。差分時のみ静かに 1 行で知らせる契約。
- 期待成果: 食い違い時のみ 1 行 + cache 更新 (必要時)。
- 成功基準: `in-sync / unknown / skipped` は無出力、`manifest-behind / changelog-behind / not-comparable` のときだけ 1 行で再現可能。
- スコープ
  - 含む: cache 読込 / version 比較 / 1 行通知 / cache refresh
  - 含まない: `plugin.json / marketplace.json / bundles.json` の書換 / 二重通知

## Layer 2: ドメイン層

### 2.1 用語
| 用語 | 定義 |
|---|---|
| installed | plugin.json の `version`。通知では `plugin.json:` と表示する |
| latest | installed と同じツリー (install 先またはチェックアウト) の CHANGELOG.md 先頭の版。配布元の最新版ではない。通知では `CHANGELOG:` と表示する |
| cache | `~/.cache/harness/version-snapshot.json` |
| mode | cache-status / refresh / notify の subcommand (位置引数・required) |

### 2.2 ビジネスルール
- CONST_001: `plugin.json / marketplace.json / bundles.json` は読取専用。
- CONST_002: 通知は 1 行のみ。二重出力禁止。
- CONST_003: `in-sync / unknown / skipped` は無出力。
- OUTPUT_CONST: stderr ではなく stdout に 1 行のみ (effect: conversation-output)。hook がこの 1 行に `<plugin>: ` を前置し、`systemMessage` を持つ JSON 1 個として stdout に出す。Claude Code はそれを利用者に表示する (PostToolUse の素の stdout は debug log に行くだけで見えない)。`additionalContext` は付けない。status は `schemas/output.schema.json` 準拠。

## Layer 3: インフラ層

| tool | 説明 | 主パラメータ |
|---|---|---|
| notifier-check.py | cache-status=鮮度判定 / refresh=cache 更新 / notify=差分1行通知 | mode subcommand: cache-status\|refresh\|notify (required) |
| hook-cache-refresh.py | cache を更新 | - |

## Layer 4: 共通ポリシー層

- 信頼度閾値: 0.7 / 最大リトライ: 1 / 最大改善回数: 2
- 許可: Read (cache, plugin.json) / Write (`version-snapshot.json` のみ: refresh と通知済みの記録 `notified.<plugin>`) / stdout 出力 (通知 1 行) / stderr 出力 (診断ログのみ)
- 禁止: `plugin.json / marketplace.json / bundles.json` 書換 / 二重通知 (同じ session・同じ plugin は `--session-id` で 1 回に抑える)
- 入力検証拒否: 不正 mode 値
- 事実確認: installed/latest の差分根拠を内部保持。unknown 時は通知しない。semver パースで検証。
- エスカレーション: cache 破損 → cache 不在と同じく無出力 (次の refresh で作り直す)。整形失敗・想定外の例外 → stderr に短文を残し無出力・exit 0。同じ session・同じ plugin の 2 回目は正常動作で、何も出さずに終える。

## Layer 5: エージェント層

### 5.1 担当 agent
- David J. Anderson (Kanban / フロー設計の権威。WIP 制限の発想で通知契約を設計)

### 5.2 知識ベース
- Kanban (Anderson): WIP=1 で通知本数を縛る
- SRE (Beyer et al): alert fatigue 回避 / silent-on-success
- Semantic Versioning Spec: installed/latest の diff 判定

### 5.3 ゴール定義
- 目的: 差分時のみ 1 行で通知し UX ノイズを抑える。
- 背景: 頻繁通知は alert fatigue を招く。silent-on-success を徹底。
- 達成ゴール: status 確定 + 差分時のみ stdout 1 行 + 必要時のみ cache 更新済み。

### 5.4 完了チェックリスト
- [ ] 出力は 0 行 or 1 行
- [ ] `in-sync / unknown / skipped` で無出力
- [ ] `status / installed / latest` を内部保持
- [ ] cache の `last_refreshed_at` が TTL(24h) と整合 (欠落時は stale 扱いで refresh)
- [ ] 推測を事実として述べていない (unknown 時は unknown 明記)

### 5.5 実行方式 (動的生成ループ)
1. 未充足項目を特定
2. 解消手順を立案 (load_cache / check / emit / refresh から選択)
3. 立案手順を実行し成果物更新
4. チェックリストで自己評価
5. 全項目充足まで反復 (上限: Layer 4 最大改善回数)
6. 上限到達 / cache 破損時は無出力で安全停止 → escalation。

### 5.6 ビジネスルール
- CONST_001: cache 失効時間は notifier-check.py 内定数 TTL_HOURS (既定 24h) で固定。
- CONST_002: 通知は 1 行のみ。

### 5.7 インターフェース
- 入力: `mode` (cache-status|refresh|notify の subcommand。required・欠損/範囲外は SystemExit(2)。`--mode <name>` 前置も互換受理)
- 出力: `stdout_line` → hook が `<plugin>: ` を前置した `systemMessage` として利用者に表示する。形式と文言は references/output-format.md が正本で、食い違いの向きで 3 種に分ける: CHANGELOG の版が新しい (status=manifest-behind) は version の上げ忘れ、plugin.json の版が新しい (status=changelog-behind) は CHANGELOG の節の足し忘れ、どちらかが semver として読めない (status=not-comparable) は向きを決めず「版を比べられない」とだけ言う。版として等しい (status=in-sync) / 片方が無い・cache が無い (status=unknown) / silent モード・同じ session で同じ plugin を通知済み (status=skipped) のときは無出力。

### 5.8 依存関係
- 前提: なし (hook として呼ばれる末尾実行)
- 後続: なし

## Layer 6: オーケストレーション層

- 実行原則: 完了チェックリストを唯一の停止条件。silent モードを厳格に守る。
- ハンドオフ直列: `cache_state → status → emit 判断 → refresh 判断`
- ゴールシークループ上限: 最大反復回数 1
- 完了判定: 全項目充足 + Layer 1 成功基準合致。

## Layer 7: UI / 提示層

- 通常 hook 呼出のため無対話。手動実行時のみ mode (subcommand) を確認。
  - 例: `notifier-check.py cache-status  # cache 鮮度を absent/fresh/stale で報告`
  - 例: `notifier-check.py refresh       # cache を更新`
  - 例: `notifier-check.py notify --plugin NAME  # 差分があれば 1 行通知`

---

## 出力指示

Layer 5 ゴール+完了チェックリストを唯一の停止条件とし、5.5 ループで動的に手順生成・実行・自己評価する。出力は stdout 1 行 (差分時) または無出力 (それ以外)。前置き・後書き禁止。
