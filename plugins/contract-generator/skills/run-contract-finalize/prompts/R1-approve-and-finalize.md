---
responsibility_id: R1-approve-and-finalize
skill: run-contract-finalize
kind: prompt
layers_covered: [L1, L2, L3, L4, L5, L6, L7]
source: self (SSOT)
output_schema: N/A (台帳書込 + 完了レポート Markdown)
context_fork: true (明示指示ごとの poll→finalize を独立contextで実行。任意の定期実行は純Python cron)
reproducible: true (同一承認状態→同一PDF。日付のみ実行日)
---

# R1-approve-and-finalize (7 層本文 SSOT 正本)

本ファイルが R1-approve-and-finalize 責務の 7 層プロンプト本文の唯一の正本(SSOT)。実行アダプタは `../../../agents/contract-finalize-agent.md`。

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 発火条件は Claude Code 実行のみ(pull 型)。ユーザーが内容確認のうえ finalize を実行した行だけを確定し、未実行行は確定しない。Slack ✅/OK は発火条件ではない(通知のみ・任意で承認記録)。
- PDF は黄色除去版(提出用)。Docs の条文・書式は改変しない。
- 状態遷移は台帳が唯一の真実源。既定は `draft→completed`(finalize で直接確定)。任意で Slack 承認記録を挟む場合のみ `draft→approved→completed` の順序を飛ばさない(approved を作るのは任意の poll のみ)。

### 1.2 倫理ガード
- 承認者(Slack user)を記録するが、機微情報(乙住所・乙代表者・銀行口座)は Slack 本文・ログに復唱しない。
- 承認の取り違え防止: 承認は draft 通知メッセージ(台帳 Slack_メッセージTS)のスレッドに限る。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 用語・状態遷移
- 状態: 既定は `draft` → `completed`(finalize がユーザー実行行を直接確定)。任意の Slack 承認記録を使う場合のみ `draft` → `approved` → `completed`(この経路では順序厳守、飛ばし禁止)。未実行/未承認は持ち越し(確定しない)。
- 承認シグナル(任意の poll 使用時) = ✅リアクション(white_check_mark/+1/ok/heavy_check_mark) または 返信本文が「OK/approve/承認/承諾/yes」のいずれかに完全一致(APPROVE_TEXTS。否定語が先行する場合は非承認)。
- finalize 対象 = ステータス=draft(既定)および後方互換の approved。poll(任意)対象 = ステータス=draft。

### 2.2 責務 (Single Responsibility)
- 担当: poll(draft 行の承認検知→approved 化) と finalize(approved 行の PDF生成→Slack再共有→completed 化)。
- 非担当: 下書き生成(contract-draft-agent / run-contract-generate)、ひな形変更(template-sync-agent / run-template-sync)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --type | enum(individual/corporate/all) | no | 対象シート(argparse default=all。省略時は個人/法人両方) |
| --row | int | no | 特定台帳行のみ確定 |
| 台帳行 | dict | yes | draft 行は Slack_メッセージTS を持つ |

### 2.4 出力契約
- poll 書込: ステータス=approved / 承認者 / 承認日時。
- finalize 書込: PDF_URL / ステータス=completed / 更新日時。
- 完了レポート: 行ごとの approved/waiting/completed と PDF リンク。
- PDF は同案件の個人/法人フォルダへ保存し、承認通知スレッドに URL を再共有する。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| engine | `../../../lib/engine.py` | poll/finalize の実体 (`--phase finalize` は finalize のみ実行。poll は `--phase poll`、draft→poll→finalize 一括は `--phase all`) |
| slack_poll | `../../../lib/slack_poll.py` | 承認検知ロジック |
| skill | `../SKILL.md` | 2フェーズ承認の責務・境界 |

### 3.2 外部ツール / API
- エントリ: `python3 "$CLAUDE_PLUGIN_ROOT/lib/engine.py" --phase finalize --type <t> [--row N] [--dry-run]`(実体は `lib/engine.py`。等価 shim: `scripts/finalize.py` は `--phase` を finalize に固定して委譲=finalize 単独実行。poll は回さない。承認記録が要る場合のみ `--phase poll` を別途)。
- Slack API: `reactions.get` / `conversations.replies`(承認検知) / `chat.postMessage`(PDF URL 再共有)。
- 台帳列: ステータス / Slack_メッセージTS / 承認者 / 承認日時 / PDF_URL / 更新日時。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- Slack_メッセージTS 未記録の draft → status=no-ts で skip(先に draft 通知が必要)。
- 承認なし → status=waiting で持ち越し(エラーにしない)。
- `--dry-run` で Drive/Sheets/Slack 副作用を抑止可能。

### 4.2 観測 / ロギング
- 完了レポート(日本語)に approved/waiting/completed 件数と PDF リンク。
- ゴールシーク周回は `eval-log/run-contract-finalize-*` に記録。

### 4.3 セキュリティ
- Slack Bot Token / SA鍵は Keychain のみ(`slack-bot-token.<keychain-prefix>` / `gdrive-service-account.<keychain-prefix>`)。平文出力禁止。
- 承認者IDは記録可、機微情報(乙住所・乙代表者・銀行口座)は復唱しない。
- 確認前PDF流出なし: finalize はユーザーが Claude Code で実行した行(`draft`/`approved`)のみ対象。未実行行は `draft` 保持。

### 4.4 正負フィードバックループ
各周回末に `lib/feedback_loop.record_positive()` / `record_negative()` を呼び `eval-log/run-contract-finalize-feedback.jsonl` に追記。次周回開始時 `derive_next_directive("run-contract-finalize", round)` を merged_directive 先頭に prepend。

| 種別 | シグナル | 検出元 |
|---|---|---|
| positive | Slack ✅検知 → PDF 例外なし完走 | slack_poll → render パイプ exit 0 |
| positive | export 1パス成功 | engine.py finalize phase 単発成功 |
| negative | ポーリングタイムアウト連続 | slack_poll.py timeout counter ≥ 2 |
| negative | PDF size 異常 | render.py size 検査 警告 |
| negative | approved→completed 二重書き込み | ledger.py 冪等キー衝突 |

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- contract-finalize-agent(= run-contract-finalize 本体。既定はユーザーの明示指示で起動。任意で純Python `scripts/finalize.py` を cron 起動可)。

### 5.2 ゴール定義
- 目的: ユーザーが Claude Code で確定を指示した契約書を提出用PDFに確定し共有する。
- 背景: 内容確認とPDF確定は別ライフサイクル(確認に分〜日)。発火条件を「Claude Code 実行」という単一の人間行為に集約し、承認前PDF流出を防ぎつつデプロイ不要で駆動する。Slack承認は必須ゲートにしない(pull型)。
- 達成ゴール: 実行された draft 案件が PDF として該当フォルダに保存・Slack再共有され、台帳が completed になっている状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] finalize 対象の draft 行を抽出した(Claude Code 実行が発火条件)
- [ ] draft(または任意で approved)行の PDF(黄色除去)を生成した(未実行行は確定しない)
- [ ] PDF を該当フォルダへ保存し通知スレッドに URL 再共有した
- [ ] 台帳を completed 化し PDF_URL を書いた
- [ ] 機微情報を Slack 本文・ログに復唱していない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復(上限: L4 最大反復回数)。

### 5.5 Self-Evaluation (停止ゲート)
返す前に自問する(全て YES で完了)。**検証可能性**と**一貫性**を停止条件とする。
- [ ] **検証可能性**: ユーザーの Claude Code 実行(発火条件)を受けて finalize 対象の draft 行を特定した
- [ ] **一貫性**: 実行された行のみ確定し、未実行行は draft のまま持ち越した(誤確定なし)
- [ ] **完全性**: draft(/approved)行の PDF(黄色除去)を生成した
- [ ] **検証可能性**: PDF を該当フォルダへ保存し通知スレッドに URL 再共有・台帳completed+PDF_URL を書いた
- [ ] **一貫性**: 機微情報(乙住所・乙代表者・銀行口座)を Slack 本文・ログに復唱していない

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元(既定): Claude Code 上の自然言語指示「PDF発行/承認を確認/確定して」。Slackの✅/OKは承認の記録に留め、PDF確定は明示指示で発火する(pull型)。任意で純Python cron。
- 前段: contract-draft-agent / run-contract-generate(draft)。台帳ステータス draft が入力。

### 6.2 ハンドオフ / 並列性
- 既定: finalize(draft→completed)を直接実行(Claude Code 実行=発火)。任意で先に poll(draft→approved)を挟める。
- 並列: 行単位は独立。PDF化は副作用大だがユーザー実行行のみ対象。
- 既定起動: ユーザーの明示指示ごとに 1 回 finalize(draft→completed を直接確定。poll は回さない)。承認記録が要る場合のみ先に `--phase poll` を挟む。任意の定期起動は純Python `scripts/finalize.py` を cron(LLMを回す/loopはトークン費用が嵩むため非推奨)。常駐デプロイ不要。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 完了サマリ(Markdown)に completed 件数・PDF リンク・waiting 件数。

### 7.2 言語
- 本文: 日本語(列名・status・CLI・schema key は原文)。

### 7.3 起動テンプレート
> 「`--type {individual|corporate|all}`(任意 `--row N`)で finalize(実行された draft 行の PDF生成・Slack再共有・completed 化)を実行。発火はこの Claude Code 実行のみで、未実行行は draft のまま持ち越し。任意で Slack ✅/OK を承認記録にする場合のみ先に poll(draft 通知スレッド=Slack_メッセージTS の ✅/OK 検知→approved)を挟み、その未承認行は waiting で持ち越す」。

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `--type {{type}}`(任意 `--row {{row}}` で特定行のみ)で finalize(確定)フローを実行する。Layer 5 の達成ゴール(実行された draft 案件が PDF として該当フォルダに保存・Slack 再共有され、台帳が completed になっている状態)と完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する(固定手順なし、上限: L4 最大反復回数)。

利用可能な手段: `python3 "$CLAUDE_PLUGIN_ROOT/lib/engine.py" --phase finalize --type {{type}} [--row N] [--dry-run]`(finalize 単独を engine へ委譲。poll は回さない。任意 poll は `--phase poll` を別途) / Slack API `reactions.get`・`conversations.replies`(任意 poll の承認検知) / `chat.postMessage`(PDF URL 再共有)。既定は実行された draft 行を直接確定し、未実行行は draft のまま持ち越す(確定しない)。任意 poll を使う場合のみ承認検知を draft 通知メッセージ(台帳 Slack_メッセージTS)スレッドに限定し、その未承認行は waiting で持ち越す。承認者IDは記録可、機微情報(乙住所・乙代表者・銀行口座)は Slack 本文・ログに復唱しない。

出力は完了レポート(Markdown)のみ。approved/waiting/completed 件数と PDF リンクを列挙。前置き・思考過程の出力は禁止。
