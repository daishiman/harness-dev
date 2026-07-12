---
name: run-contract-finalize
description: 業務委託契約書をSlack承認後にPDF発行・確定したいとき、承認(✅/OK)をポーリング検知してPDF生成・共有したいときに使う。
disable-model-invocation: true
user-invocable: true
allowed-tools: [Read, Bash(python3 *)]
kind: run
version: 0.3.0
owner: harness maintainers
since: 2026-05-30
role_suffix: generator
hierarchy_level: L1
rubric_refs:
  - "../../../harness-creator/skills/run-elegant-review/references/thought-methods.yaml"
  - "../../lib/slack_poll.py"
  - "../../lib/render.py"
responsibility_refs: [prompts/R1-approve-and-finalize.md, ../../agents/contract-finalize-agent.md, scripts/finalize.py]
prompt_ssot: prompts/R1-approve-and-finalize.md
effect: external-mutation
source: output/contract-generator-v2/(slack-2phase-design.md, refactor-plan.md)
source-tier: internal
last-audited: 2026-05-30
audit-trigger: on-change
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: ユーザーが Claude Code で finalize を実行した draft 行のみ completed 化され PDF_URL が書き戻る一方、未実行の draft 行は draft のまま保持される(pull型の誤確定なし)ことを --dry-run と台帳観測で機械検証できる。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 生成PDFが法務承認済書式を保ち黄色除去のみ(条文非改変)で、台帳ステータス遷移が冪等(completed 二重書き込みを起こさない)であることを finalize 単発実行で検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 「発火条件は Claude Code 実行のみ・Slack✅/OK は発火条件でない(pull型)」という中核ゲート設計が SKILL.md/prompt SSOT/agent アダプタ/scripts まで一貫し、確認と確定のライフサイクル分離というユーザ目的を常駐デプロイ不要・再入可能な形で最適反映している。
      verify_by: elegant-review
---

# run-contract-finalize

## Purpose & Output Contract
`run-contract-generate` が作った下書き(台帳 `draft`)を、**黄色除去PDF(提出用)** として個人/法人フォルダへ保存→Slackスレッドに**再共有**→台帳を `completed` 化する。**発火条件はただ一つ「Claude Code 上で finalize を実行(=ユーザーが確定を指示)」**(pull 型)。実体は共有エンジン `../../lib/engine.py --phase finalize`(`draft` 行を直接PDF化→completed)を `scripts/finalize.py` が呼ぶ。**Slack の ✅/OK は発火条件ではない**(Slack通知は単なるお知らせで承認ゲートとして要求しない)。ユーザーが内容を確認して Claude Code で実行する行為そのものが人間のゲート。常駐サーバー不要。自動ポーリング(/loop・cron)は **任意**(LLM を回す /loop はトークン費用が嵩むため、自動化する場合も純 Python の `scripts/finalize.py` を cron で回す。詳細は「運用」)。

## 境界
PDF確定・共有(`draft`→`completed`)まで。下書き生成は `run-contract-generate`、ひな形変更は `run-template-sync` に分離。発火は Claude Code 上の finalize 実行(pull型)。**任意**で Slack✅/OK を承認記録にしたい場合のみ `--phase poll`(draft→approved)を挟める(後方互換。既定経路ではない)。webhook常駐は不採用。

## 主要ルール
- **発火条件は Claude Code 実行のみ**: `finalize` は `draft`(および後方互換の `approved`)行を対象に直接PDF化する。ユーザーが内容確認のうえ実行する行為が人間のゲート(誤確定はこの明示実行で防ぐ)。Slack承認は必須ではない。
- 任意の poll を使う場合の承認検知は台帳 `Slack_メッセージTS` を突合キーに `reactions.get`/`conversations.replies` を読む。
- PDFは法務承認済書式を維持(黄色除去のみ)。条文は改変しない。
- 認証: Service Account(Drive/Sheets) + Slack Bot Token は Keychain のみ(plugin直下 `README.md` Task 4/8)。
- 状態は台帳(単一真実源)で引き継ぐ。スキル間結合は台帳ステータス列のみ。

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、最適手順を都度生成。詳細は run-build-skill `references/goal-seek-paradigm.md`。

### ゴール (Goal)
ユーザーが Claude Code で finalize を実行した台帳 `draft` 行が、提出用PDFとして該当フォルダに生成・Slack再共有され、台帳が `completed` になっている状態。

### 目的・背景 (Why)
下書き内容の確認とPDF確定は別ライフサイクル(確認に分〜日かかりうる)。確定をユーザーの明示実行(pull型)に委ねることで、承認ゲートを Claude Code 実行という単一の人間行為に集約し、デプロイ不要・誤確定なしで再入可能にする。

### 完了チェックリスト (Checklist)
- [ ] `python3 $CLAUDE_PLUGIN_ROOT/lib/config_auth.py check` で Drive/Sheets 認証が通る
- [ ] `draft` 行を finalize 対象として抽出できる(Claude Code 実行が発火条件)
- [ ] `draft`(または任意で `approved`)行の黄色除去PDFを生成し個人/法人フォルダへ保存できる
- [ ] Slackスレッドに PDF URL を再共有できる(通知のみ・任意)
- [ ] 台帳を `completed` 化し PDF_URL を書き戻せる
- [ ] 未実行の行は `draft` のまま保持(ユーザーが実行するまで確定しない)

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成 → 3. 実行 → 4. 再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues へ。

### ゴールシーク配線
承認ポーリングを多周回す場合の周回状態とドリフト圧縮の配線。周回末に `eval-log/run-contract-finalize-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変(SHA-256 を `eval-log/run-contract-finalize-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回は直前の `merged_directive_for_next` と `original_goal` を必須入力として読む(AI単独再導出禁止)。重い周回は `Skill(run-goal-seek)` に fork 委譲。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/lib/check_intermediate.py" run-contract-finalize
# → eval-log/run-contract-finalize-intermediate.jsonl の original_goal_hash 不変・required_keys 充足を検査
# 不整合は exit 2 で次周回を停止
```

## ゴールシーク品質ループ (正負フィードバック)

各周回末に `lib/feedback_loop.py` の `record_positive()` / `record_negative()` を呼び、シグナルを `eval-log/run-contract-finalize-feedback.jsonl` に追記。次周回開始時に `derive_next_directive("run-contract-finalize", round)` を参照し、戻り値を `merged_directive_for_next` の先頭に prepend する。

### 正負シグナル定義表 (run-contract-finalize)

| 種別 | シグナル | 検出元 |
|---|---|---|
| positive | Slack ✅検知 → PDF 例外なし完走 | slack_poll → render パイプ exit 0 |
| positive | export 1パス成功 | engine.py finalize phase 単発成功 |
| negative | ポーリングタイムアウト連続 | slack_poll.py timeout counter ≥ 2 |
| negative | PDF size 異常 | render.py size 検査 警告 |
| negative | approved→completed 二重書き込み | ledger.py 冪等キー衝突 |

反映タイミング: 周回末 `record_*` → 次周回開始時 `derive_next_directive` → merged_directive に prepend。

## 検証
- finalize は `draft`/`approved` 行を対象にPDF生成(ユーザーが Claude Code で実行した行のみ確定)
- PDF生成後に台帳 PDF_URL/ステータス=completed が書かれている
- 未実行の行は `draft` のまま保持(誤確定なし)
- `--dry-run` で Drive/Sheets/Slack 副作用を抑止可能
- 実装: `scripts/finalize.py`(薄い shim, finalize 単独)/ `$CLAUDE_PLUGIN_ROOT/lib/engine.py`(process_row phase分岐)

## Gotchas
- **発火条件は Claude Code 実行のみ(pull型)**: PDF確定はユーザーが Claude Code で「確定して/PDF発行して」と指示し finalize を実行したときに 1 回だけ走る。**Slackの ✅/OK は発火条件ではない**(Slack通知は単なるお知らせ)。内容確認のうえ実行する行為そのものが人間のゲート。
- 自動化が要る場合は純Pythonの `scripts/finalize.py` を cron で回す(Google/Slack APIは無料枠・呼出課金なし=費用は実質ゼロ)。**/loop はLLMを毎周回すためトークン費用が嵩むので非推奨**。真のイベント駆動(承認の瞬間発火)は Slack Events API の webhook 常駐が必要で本スキルは不採用。
- 任意で二者承認(Slack✅→確定)したい場合のみ `--phase poll` を挟む。その際の承認メッセージは `run-contract-generate` がdraft時に送った通知スレッドであること(TS突合)。
- Slack Bot Token は機微情報。Keychain限定・平文禁止(hooks/hook-guard-secret.py が保護)。

## 変数化契約
`slack_channel`/`slack_keychain_*`/出力フォルダID/`spreadsheet_id` は `google-config.json` と Keychain から注入。具体値は本文に直書きしない。

## 追加リソース
- plugin直下 `README.md` — Slack/Keychain/SA セットアップ(Task 1-14)
- `output/contract-generator-v2/slack-2phase-design.md` — 2フェーズ承認の設計
- `prompts/R1-approve-and-finalize.md` — 承認検知・PDF確定・台帳completedの責務単位7層プロンプト(SSOT正本)。`../../agents/contract-finalize-agent.md` は本プロンプトを参照する薄い実行アダプタ(本文を持たない)。
- 追加リソースは plugin 直下 `lib/` ディレクトリ全体を参照。各ファイルは PEP723 風メタブロックで purpose を記載。
- 本 skill が強く依存する lib: `slack_poll.py`(承認検知) / `render.py`(PDF 生成) / `engine.py`(--phase poll/finalize 委譲先) / `ledger.py`(approved/completed 書戻し) / `slack_notify.py`(再共有)
- `scripts/finalize.py` — 薄い shim(`lib/engine.py --phase finalize` 委譲のみ。任意で二者承認フローを挟む場合は先に `lib/engine.py --phase poll` を別途実行)

## 運用(既定=明示指示駆動 / 常駐デプロイ不要)
```bash
# 既定: ユーザーが Claude Code で確定を指示したときに 1 回実行(承認済み行のみPDF化)
python3 scripts/finalize.py --type all          # finalize 単独(draft→completed 直接確定・poll は回さない・費用¥0)
python3 scripts/finalize.py --type all --dry-run # 副作用なしで承認状態を確認

# 任意の自動化(費用に注意): 自動ポーリングは純Pythonをcronで。LLMを回す/loopは非推奨
# 導入後の plugin 実体は固定文字列で書かず自動検出した絶対パスを使う(<plugin> をそのまま貼らない):
#   CG=$(find "$HOME/.claude" -type d -path '*/contract-generator' -print -quit)
#   */5 * * * * cd "$CG" && python3 scripts/finalize.py --type all   # 例: 5分ごと・トークン費用ゼロ
```

## セキュリティと権限
外部書込(Drive/Sheets/Slack, `effect=external-mutation`)。`hooks/hook-guard-secret.py`(plugin)がSA鍵/Slackトークンの平文出力・誤削除をブロック。`references` 経由で `settings-hardening.json` の deny を適用。鍵はKeychainのみ。
