---
name: run-notion-gmail-dry-run
description: Notion 2DBから本文×宛先の差し込みメール送信計画を生成しプレビューしたいとき、送信せず内容を確認したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--db1 <id>] [--db2 <id>] [--out <plan.json>] [--config <path>] [--canary <N>]"
allowed-tools:
  - Read
  - Bash(python3 *)
kind: run
prefix: run
effect: local-artifact
owner: team-platform
version: 0.1.0
since: 2026-06-24
source: doc/run-notion-gmail-send-仕様と検証メモ.md
source-tier: internal
last-audited: 2026-06-24
audit-trigger: source-update
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 宛先解決が「送信対象=false 除外 → メールを送らない=true 抑制(最優先) → プロ人材メール空 invalid_to → プロ人材重複は created_time 降順(tie=page_id 降順)で最新1件のみ残す dedup」の順序で決定論的に処理されることを test_recipient_resolution で機械検証できる。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: build-plan が「本文true × 宛先解決後」の直積を生成し plan_hash/content_hash と承認 nonce を後付け観測メタ(cc_suppressed 等)に非依存で算出し、1通も送信せず local-artifact のみ出力することを test_build_plan で機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: dry-run が「送信前に全件を目視プレビューさせ機械照合可能な APPROVE 文字列契約を live-send へ渡す(誤送信の停止点)」というユーザー目的を過不足なく満たし、--canary/--limit の少数検品が不可逆送信の承認契約を崩さないことを run-elegant-review の4条件で確認する。
      verify_by: elegant-review
---

# run-notion-gmail-dry-run

## Purpose & Output Contract

Notion 2DB（メール本文DB / メール送信先_DB）を入力に、`本文true × 宛先(解決後)` の直積で送信単位を生成し、`{{}}` トークンを差し込み置換のうえ MIME 組立して `plan.json` と全件プレビューを出力する **dry-run 専用スキル**。**Gmail API は呼ばず1通も送信しない**。送信前に「何が・誰に・どんな本文で」送られるかを安全に何度でも確認する独立価値を持つ。既定の最小確認1回・無人確認0(--auto-approve)では必須ではなく、厳格対話モードや canary 前の全件目視材料として使う（既定モードは send-campaign.py の preview がコンパクト要約を出すが、dry-run は全件フルプレビューを出す）。

**入力**: なし（既定）。任意で `--db1 <id>` / `--db2 <id>`（config の DB を override。両方指定時は `.notion-config.json` 不在でも dry-run 可）、`--out <path>`（plan.json 出力先）、`--canary <N>` / `--limit <N>`（少数検品用に送信可能 unit を安定順の先頭 N 件へ限定）。
**出力**:
- `plan.json`（本文全文を含むためローカル作業領域 `eval-log/notion-gmail-send/` のみ・git 管理外。Notion ログには保存しない。§12 PII）
- 標準出力に承認文字列 `APPROVE <plan_hash> <count> <first_to> <確認語>` ＋ 第1段件数 ＋ 全件プレビュー（差し込み後の件名/本文抜粋/To/CC・`multi_to_visible` 警告・`skipped_validation` 内訳・プロ人材重複除外）

**完了条件**: 第1段件数（本文true×宛先true）・`plan_hash`・全件プレビュー・`APPROVE` 文字列・`plan.json` が提示され、運用者が内容を目視できる状態。

## End-to-End Flow

`scripts/build-plan.py` が以下を決定論的に実行する（LLM 判断不要の本体）。

```
[1 取得]  config notion_gmail_send.source.{body_db,recipient_db} を解決し DB1/DB2 を REST 取得
          → 本文true(bodies) / 宛先解決(recips) を抽出。送らない抑制=suppressed / プロ人材重複=duplicate_dropped
[2 直積]  本文true × 宛先(解決後) で送信単位候補を生成（第1段件数 = len×len。送信ログDB不要 = G0）
[3 置換]  件名/本文の {{会社名}}{{担当者様名}} を宛先値で置換。未置換残存(廃止{{部署名}}含む)は skip
[4 組立]  From=本文DB送り主 / To=メール（プロ人材） / CC=本文DB CC＋メール（cc秘書） を結合し1通へ MIME 組立
[5 canary] 必要なら --canary N で送信可能 unit を安定順の先頭 N 件へ限定
[6 hash]  campaign_id / content_hash / plan_hash / 冪等キー を算出し finalize_plan で plan 確定
[7 出力]  plan.json（本文全文・ローカル）+ stdout に APPROVE文字列・第1段件数・全件プレビュー
```

実行コマンド:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-dry-run/scripts/build-plan.py"
# DB override / 出力先指定が必要なときのみ:
#   --db1 <body_db_id> --db2 <recipient_db_id> --out <plan.json> --config <.notion-config.json>
#   --canary 3   # 少数検品用。限定後の count/plan_hash/確認語で承認を束縛する
```

Notion APIキーは Keychain `notion-api-key.<keychain-prefix>`（**GET のみ**。Gmail も送信ログDBも触らない）。

## ゴールシーク実行

### ゴール (Goal)
本文true×宛先true の全送信単位が差し込み置換・MIME組立まで完了し、`content_hash`/`plan_hash` 付きの `plan.json` と全件プレビューと `APPROVE <plan_hash> <count> <first_to> <確認語>` 文字列が提示され、運用者が送信前に内容を目視確認できる状態。**送信は一切行わない。**

### 目的・背景 (Why)
不可逆な外部副作用（メール送信）の前に、誤った本文・誤った宛先を構造的に検出して止める安全材料を作る。送信ログDBが未確定でも第1段件数（本文true×宛先true）は常に算出でき（G0）、本文が0通でも「記入すべきもの」を運用者へ示せる。対話モードでは、承認を機械照合可能な `APPROVE` 文字列に束縛する。

### 完了チェックリスト (Checklist)
- [ ] DB1/DB2 を取得し、本文true（メッセージ対象✅ かつ 本文非空）/ 宛先（送信対象✅ かつ 送らない☐ かつ プロ人材メール非空・重複は最新 `created_time` 1件、同時刻は `page_id` 降順）を抽出した
- [ ] 送らない抑制(suppressed) / プロ人材重複除外(duplicate_dropped) を可視化した
- [ ] 本文true × 宛先(解決後) の直積を生成し、第1段件数を算出した
- [ ] 件名と本文の `{{会社名}}` `{{担当者様名}}` を置換し、未置換（廃止 `{{部署名}}` 含む）が残る単位は skip した
- [ ] To=メール（プロ人材）/ CC=本文CC＋メール（cc秘書）を結合（To除外・重複排除）して1通に MIME 組立し、不正アドレスを含む単位は skip した
- [ ] `content_hash` / `plan_hash` / `campaign_id` を算出し、本文全文入り `plan.json` をローカルに生成した
- [ ] `--canary N` 指定時は送信可能 unit を安定順の先頭 N 件へ限定し、限定後の `plan_hash` / 件数 / 確認語を出した
- [ ] 第1段件数・`APPROVE <plan_hash> <count> <first_to> <確認語>`・全件プレビューを標準出力へ提示した
- [ ] `skipped_validation` 内訳（reason_code 別）とプロ人材重複除外を検知・報告した
- [ ] 送信可能 0通のとき「メッセージ対象✅ かつ `{{}}` 入り本文の記入」を運用者へ促した

### ゴールシークループ
1. `build-plan.py` を実行し、第1段件数・`plan.json`・全件プレビュー・`APPROVE` 文字列を得る。
2. プレビューを目視し、未充足のチェックリスト項目があれば原因を特定する。
   - `exit 2`（config/接続/Keychain エラー）→ `.notion-config.json` の `notion_gmail_send.source`、または config をまだ作らずに計画だけ見たい場合は `--db1/--db2` の両方、Keychain `notion-api-key.<keychain-prefix>` を確認して再実行。
   - 送信可能 0通 → DB1 のメッセージ対象✅ ページに `{{}}` 入り本文を記入して再実行（チェックリスト最終項目）。
   - `skipped_validation` 多数 → reason_code（`unresolved_token`/`unsafe_header`/`invalid_to`/`invalid_cc`）別に Notion 元データを修正して再実行。
   - `⚠️ プロ人材重複` → 同一人物への重複送信防止のため宛先DBの重複ページを点検する。
3. 全チェックリストが充足したら完了。生成した `plan.json` と `APPROVE` 文字列を次工程の承認入力として引き渡す。
4. 本文記入や複数DBの遡及で多周回するときは下記「ゴールシーク配線」に従い周回状態をアンカーする。単発の確認では1周で完了し配線は no-op。

### ゴールシーク配線
本文の記入待ち・複数DB横断・修正再実行で多周回するときの周回状態とドリフト圧縮の配線。周回末に `eval-log/run-notion-gmail-dry-run-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変（SHA-256 を `eval-log/run-notion-gmail-dry-run-progress.json` の `original_goal_hash` に固定し毎周回照合）。次周回の手順生成は直前の `merged_directive_for_next` と `original_goal` を必須入力として読む（AI 単独再導出禁止）。本スキルは単発の dry-run で完結し、多周回が必要な場合も上位 orchestrator（run-notion-gmail-send）が制御する。

```bash
# 中間成果物アンカーの機械検査 (run-goal-seek/SKILL.md と同型 SSOT)
python3 - "$PWD/eval-log/run-notion-gmail-dry-run-progress.json" "$PWD/eval-log/run-notion-gmail-dry-run-intermediate.jsonl" <<'PY'
import json, os, sys, hashlib
prog_path, inter_path = sys.argv[1], sys.argv[2]
required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}
if not os.path.exists(inter_path):
    print("intermediate.jsonl 未生成 (ループ未実行)"); sys.exit(0)
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}
lines = [l for l in open(inter_path, encoding="utf-8").read().splitlines() if l.strip()]
first = None
for i, line in enumerate(lines):
    e = json.loads(line)
    assert not (required_keys - e.keys()), f"intermediate[{i}] 必須キー不足"
    if i == 0:
        first = e["original_goal"]
        h = hashlib.sha256(first.encode()).hexdigest()
        assert prog.get("original_goal_hash") in (None, h), "original_goal_hash drift"
    assert e["original_goal"] == first, f"intermediate[{i}] anchor 不変性違反"
print(f"anchor OK: {len(lines)} 行 / 不変 / hash 一致")
PY
```

## Key Rules

1. **送信しない（独立価値）**: Gmail API を一切呼ばない read-only 工程。Notion は GET のみ・`plan.json` はローカル書込のみ。安全に何度でも実行できる。送信は次工程 `run-notion-gmail-send` の責務。
2. **第1段件数は常に算出可（G0）**: 第1段 計画送信単位 = 本文true件数 × 宛先true件数。送信ログDB未確定でも dry-run はここまで提示する（第2段の冪等差し引きは live-send 側 G2 通過後）。
3. **fail-closed で送信単位を除外**: 未置換 `{{}}` トークン残存（`unresolved_token`）・ヘッダ危険値（`unsafe_header`）・不正アドレス（`invalid_to`/`invalid_cc`）の単位は `skipped_validation` として除外し、件数・内訳をプレビューに計上する。warning 止まりにしない（§5）。
4. **置換スコープは件名＋本文の両方**: `{{会社名}}` `{{担当者様名}}` を件名(title)と本文コードブロックの双方で置換する。`{{部署名}}` は廃止（D1）。置換元が空値の単位も未置換扱いで skip（§5）。
5. **`plan.json` はローカルのみ**: 本文全文を含むため `eval-log/notion-gmail-send/` のローカル作業領域に書き、Notion ログにも git にも保存しない（§12 PII。Notion ログへ残すのは `content_hash` と件名のみ）。
6. **本文0通は記入を促す**: 送信可能が0通なら送信せず終了し、「メッセージ対象=✅ かつ `{{}}` 入り本文の記入」を運用者へ案内する（§10-G2）。

## Gotchas

1. `--db1/--db2` を両方指定したときは config を読まずに DB を解決する（read-only dry-run のため）。片方でも未指定なら config `notion_gmail_send.source.{body_db,recipient_db}` で不足分を補い、両方未解決なら `exit 2`。
2. `--out` 未指定時の plan.json 既定は `<config親>/eval-log/notion-gmail-send/plan-<campaign_id>.json`。
3. To が複数アドレスの単位は `multi_to_visible=true`（受信者が互いのアドレスを見られる）。プレビューで `⚠️` 警告し承認 echo 対象に含める（§6）。
4. 本文コードブロックは最初の非空 `code` block のみ採用。複数非空なら `multiple_body_code_blocks` として本文除外（暗黙連結しない。§3）。
5. `content_hash` の To/CC は順序非依存に正規化（sorted）されるため、宛先列の並び替えだけでは hash は変わらない（`lib/plan_build.py`）。
6. 同一プロ人材メールが複数ページに存在すると同一人物へ重複送信し得る。dry-run の `duplicate_dropped` 報告を必ず点検する（§11）。
7. `--canary` / `--limit` は dry-run plan を限定するだけで、Notion 側の ✅ は変更しない。検品後に残りを送るときは Notion の対象フラグを広げるか、`--canary` なしで plan を再生成する。

## Additional Resources

- `scripts/build-plan.py` — dry-run plan 構築の決定論本体（DB取得→直積→置換→組立→hash→plan.json）
- `../../lib/render_substitute.py` — `{{}}` 置換と未置換/危険値検出（§5）
- `../../lib/message_assemble.py` — From/To/CC 写像・カンマ分割・MIME 組立・アドレス検証（§6）
- `../../lib/plan_build.py` — `campaign_id`/`content_hash`/`plan_hash`/冪等キー/`finalize_plan`（§4）
- `../../lib/notion_client.py` / `notion_config.py` / `secrets.py` — Notion REST 取得・config 解決・Keychain
- `doc/run-notion-gmail-send-仕様と検証メモ.md` — 実装 SSOT（§4 直積/§5 置換/§6 組立/§10 G0/§12 PII）
- 次工程: `../run-notion-gmail-send/` — `plan.json` と `APPROVE` 文字列を承認入力に取り、`plan_hash` 一致時のみ送信する
