---
name: run-notion-gmail-send
description: Notionメール本文DBの内容を送信先DBへGmailで一斉個別送信したいとき（既定はNotionチェックを承認とみなす最小確認1回=preview→単一確認、無人cronは--auto-approveで確認0も可）、差し込み置換して送りたいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "(既定:最小確認1回) 引数なしでpreview→ --confirm-token <plan_hash>  |  [--canary <N>] [--db1 <id>] [--db2 <id>] [--config <path>] [--allow-resend]  |  (無人cron) --auto-approve  |  (厳格対話) --plan <plan.json> --approved-nonce <確認語>"
arguments: [plan]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-24
version: 0.1.0
source: doc/run-notion-gmail-send-仕様と検証メモ.md
source-tier: internal
last-audited: 2026-06-24
audit-trigger: runtime-failure
responsibility_refs:
  - prompts/R1-orchestrate.md
  - prompts/R2-presend-verify.md
schema_refs:
  - schemas/send-verdict.schema.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: live-send が plan_hash 不一致時に Gmail API を呼ばず fail-closed で停止し、厳格対話モードでは plan.json が非信頼アーティファクトのため send_guard が件数偽装・未置換トークン・From 不整合・確認語 nonce 不一致を実効検出すること、非対話(preview/confirm/cron)では承認 tuple が同一プロセス内の新鮮 plan からの self-derive ゆえ plan_hash/件数/content_hash 照合は恒真(defense-in-depth=compose バグ検出に留まり plan 改竄保護価値は持たない)で実効する独立検証は source-audit/fresh rebuild/C-1 送信時 suppress 再検証(subtract-only)/From 検証/content dedup であること、nonce 照合は厳格対話限定・送信件数が新鮮 plan を超えないこと、confirm モードが新鮮 plan の plan_hash と CONFIRM_TOKEN 一致時のみ送信し不一致(preview 後の変化)で送らないことを test_send_campaign / test_auto_send / test_preflight で機械検証できる。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 冪等ログが「本文page_id:宛先page_id:content_hash」(campaign 非依存)キーで reserved→sent/unknown 遷移し、再実行・別実行の二重送信を防ぎ、送信成功後のログ失敗を unknown_needs_reconcile として自動再送しないことを test_idempotent_log で機械検証できる。
      verify_by: test
    - id: IN3
      loop_scope: inner
      text: 既定の最小確認1回モードが (a)引数なしで preview(exit 10)し送信せず要約+CONFIRM_TOKEN を出力、(b)--confirm-token 一致時のみ全 ✅ 宛先へ送信し不一致で exit 11、(c)source-audit high を全停止せず ⚠️ 警告として要約へ出し人間判断に委ねる(該当 unit は送信時 per-unit skip)こと、および無人 cron(--auto-approve/--yes)が (d)送信前に source-audit 集約ゲート(run_full_audit)を実行し high 残存で1通も送らず fail-closed(無人ゆえの原則的非対称)、(e)端末確認なしで 送信対象=✅ の全宛先へ送信、(f)opt-in --canary N で先頭 N 件のみ送信し再実行で content dedup により既送を skip、(g)dry-run と同一の plan_compose ロジックで決定論的に同じ plan を生成、(h)recipient_db 未解決時に C-1 再検証不能で fail-closed することを test_auto_send / test_plan_compose で機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 確認既定1回(最小=コンパクト要約[件数/先頭To/本文先頭/抑制skip/⚠️警告]+単一確認・CONFIRM_TOKEN で preview 内容へ束縛・最悪0=無人 cron)で承認の所在を Notion データ層(送信対象=✅)へ移し、重い APPROVE文字列/nonce 読解強制を軽量な単一確認へ圧縮し、plan改竄照合の過大表現を是正して実効安全層(source-audit/fresh rebuild/C-1 送信時 suppress 再検証/From 検証/content dedup)へ正直に再配置し、source-audit gate の全停止を「人間がループに居る既定=警告/無人 cron=fail-closed」の原則的非対称へ階層化することで、誤送信・二重送信リスクを許容範囲へ吸収する設計がユーザー目的(送信の手間を最小化・最小確認1回)を最適に反映し過不足ないことを run-elegant-review の4条件で確認する。
      verify_by: elegant-review
---

# run-notion-gmail-send

## Purpose & Output Contract

メール送信先_DB の `送信対象=✅` を承認シグナルとして、本文 × 宛先の各送信単位を live-send preflight (G1/G2/G3) と `send_guard` を通して Gmail API で1通ずつ送信し、各結果を Notion 送信ログDBへ事前予約つきで冪等記録する不可逆送信の制御層。**既定は最小確認1回**（重い APPROVE文字列/nonce 読解強制を、コンパクト要約+単一確認へ圧縮）。承認は Notion のチェック（データ層）が担い、誤送信防止は確認の重さとは独立した機械的安全層が担う。

**3つのモード**（確認の重さで直交）:
- **既定: 最小確認1回**: 引数なしで preview（送信せず要約[件数/先頭To/本文先頭/抑制·skip/⚠️警告]+CONFIRM_TOKEN を出力・exit 10）→ 人間が要約を見て**単一の送信可否確認** → `--confirm-token <plan_hash>` で再実行し、新鮮 plan の plan_hash が一致する時だけ送信（preview 後に Notion が変われば exit 11 で再 preview）。`--canary N` で先頭 N 件のみ送信（残りは再実行で content dedup が既送を skip）。
- **無人確認0: `--auto-approve` / `--yes`**: cron 等。端末確認なしで送信。人間の目視がないため source-audit high 残存で fail-closed（0 送信）。
- **厳格対話: `--plan ... --approved-*`（後方互換）**: dry-run プレビュー目視 → `APPROVE <plan_hash> <count> <first_to> <確認語>` を完全一致入力 → 送信。読解強制で慎重に送りたいとき用。

**出力**: Gmail 送信 + 送信ログDB の reserved→sent/unknown 記録 + 日本語送信レポート（送信/スキップ/失敗/要照合の件数・内訳・次アクション）。preview は要約+CONFIRM_TOKEN のみ（送信しない）。
**完了条件**: 送信単位が「送信(sent) / 冪等スキップ / 検証スキップ / 要照合」のいずれかに確定し、ログDBへ反映された状態。外部実体未確定・plan改竄(対話)・件数偽装・reserved不在・CONFIRM_TOKEN不一致・(cron)source-audit high 残存では **1通も送らず** fail-closed 中断・誘導。

## End-to-End Flow

**既定: 最小確認1回（推奨）**
```
[1 整備]     Notion で 送信対象=✅(宛先) / メッセージ対象=✅ かつ {{}}入り本文(本文) を用意
[2 preview]  /run-notion-gmail-send   (引数なし)
              └ send-campaign.py: source-audit警告整形 → 最新 Notion から新鮮 plan 構築
                 → 要約[件数/先頭To/本文先頭/抑制·skip/⚠️警告] + CONFIRM_TOKEN を出力し exit 10 (送信しない)
[3 単一確認] R1 が要約を提示 → 人間が「送る/やめる」を1回答える
[4 送信]     承認なら /run-notion-gmail-send --confirm-token <plan_hash>
              └ 新鮮 plan を再構築し plan_hash が token と一致する時だけ:
                 承認 tuple を plan から self-derive → reserved 予約 → send_guard 通過 → Gmail 送信 → sent/unknown 更新
                 (不一致=preview 後に Notion 変化 → exit 11 で再 preview)
[5 レポート]  日本語送信レポート (sent/skip/error/要照合)
              ↑ Gmail 直接送信は hook(guard-gmail-send.py)が補助遮断、正本は send_guard
```

**無人確認0（cron・端末入力ゼロ）**
```
/run-notion-gmail-send --auto-approve   (preview/確認なし。source-audit high 残存で fail-closed)
```

**厳格対話モード（後方互換・慎重運用）**
```
[1 dry-run]   Skill(run-notion-gmail-dry-run) → plan.json + APPROVE文字列 + 全件プレビュー
[2 承認]      人間が差し込み後フル本文を目視 → APPROVE <plan_hash> <count> <first_to> <確認語> を入力
[3 二段確認]  Task(gmail-send-presend-verifier, context:fork) が plan を独立再計算で検査
[4-6]         preflight(G1/G2/G3) → reserved 予約 → send_guard → Gmail → ログ → レポート
```

責務は `prompts/R1-orchestrate.md`(統括) / `prompts/R2-presend-verify.md`(二段確認 SSOT・厳格対話モード)。全モードとも安全の正本は `lib/send_guard.py`(機械層)。

## ゴールシーク実行

### ゴール (Goal)
**既定の最小確認1回モード**では、preview が最新 Notion から構築した新鮮 plan の要約+CONFIRM_TOKEN を提示し人間の単一確認を取った上で、confirm 段が新鮮 plan を再構築し plan_hash が CONFIRM_TOKEN と一致する各送信単位が、決定論セルフチェック・preflight 全通過・reserved 事前予約・`send_guard` 通過・C-1 送信時 suppress 再検証を経て Gmail 送信され、結果が Notionページ単位の content ベース冪等キー `{本文page_id}:{宛先page_id}:{content_hash}`（campaign_id 非依存）で記録され、日本語レポートが提示された状態。承認は Notion の `送信対象=✅`（厳格対話モードでは加えて APPROVE 文字列）が担う。CONFIRM_TOKEN 不一致・(cron)source-audit high 残存・plan 改竄(対話)・件数偽装・reserved 不在・外部実体未確定では1通も送らず中断・誘導した状態。

### 目的・背景 (Why)
不可逆な外部副作用 (メール送信) を、**確認の重さと独立に効く機械的安全層**で安全化する制御層。(1) plan 整合（厳格対話モードは plan.json がディスク経由の非信頼アーティファクトのため units からの plan_hash/件数/content_hash 決定論再計算が改竄・件数偽装を実効検出する。非対話は送信直前に最新 Notion から fresh rebuild し、confirm モードは plan_hash を CONFIRM_TOKEN へ束縛する。非対話の再計算照合は self-derive ゆえ恒真で defense-in-depth）、(2) 承認の所在は Notion のチェック（`送信対象=✅`）= データ層。既定は最小確認1回（要約への単一確認）で送り、無人 cron は確認0、厳格対話は加えて APPROVE 文字列の確認語が blind approve のコストを上げる（ただし「人間が読み理解した」ことは機構で強制できない）、(3) Notionページ単位の content ベース冪等ログが再実行・別実行の二重送信と送信成功後ログ失敗を防ぐ。さらに非対話は source-audit で空本文/To/From不正等を検出し、cron は fail-closed・既定 preview は警告提示する。固定手順では入力 (モード/外部依存状態/quota) に脆いため、未達ゲートを都度埋める。

### 責務サマリと完了条件の正本
各責務の停止条件詳細は `prompts/Rn` を正本 (SSOT) とし、本節は俯瞰のみ示す (片側更新ドリフト回避)。
- **R1 orchestrate** (`prompts/R1-orchestrate.md`): モード判定（既定 confirm=最小確認1回 / 無人 cron / 厳格対話）・confirm は preview→要約提示→単一確認→`--confirm-token` 送信・cron は `--auto-approve`・厳格対話は dry-run 委譲＋`APPROVE <plan_hash> <count> <first_to> <確認語>` 受領＋二段確認・送信可否判断・最終レポート生成。
- **R2 presend-verify** (`prompts/R2-presend-verify.md` / agent `gmail-send-presend-verifier`): **厳格対話モード限定**で context:fork で plan を独立再検査 (plan_hash/件数/先頭To/未置換トークン/宛先形式)。非対話は source-audit/C-1/fresh rebuild の独立 fetch が代替。
- 決定論本体: `scripts/send-campaign.py`(非対話は compose→audit警告/gate→self-derive→(confirm は token 照合)→reserve→send_guard→Gmail→log) / `lib/plan_compose.py`(新鮮 plan) / `lib/mail_db_audit.py run_full_audit`(cron gate / 既定 preview 警告) / `scripts/verify-plan.py`(対話二段確認) / `../../lib/`。

### 完了チェックリスト (Checklist)
- [ ] モードを判定した（既定 confirm=最小確認1回 / 無人 cron=確認0 / 厳格対話=APPROVE）
- [ ] (confirm) `send-campaign.py` を引数なしで preview(exit 10)し、要約+CONFIRM_TOKEN を人間へ提示し単一の送信可否確認を取り、承認時のみ `--confirm-token <plan_hash>` で送信した（plan_hash 不一致は exit 11 で再 preview）
- [ ] (cron) `送信対象=✅` を整備し `--auto-approve`/`--yes` で起動した（source-audit high で fail-closed・最新 Notion から新鮮 plan を self-derive で送信）
- [ ] (厳格対話) 人間が差し込み後フル本文を目視し `APPROVE <plan_hash> <count> <first_to> <確認語>` を完全一致で入力し、`Task(gmail-send-presend-verifier)` の verdict が pass
- [ ] `send-campaign.py` の preflight G1(認証)/G2(送信ログDB・本文true≥1)/G3(整合) が全 PASS
- [ ] 各送信単位を送信ログDBへ reserved 事前予約し、既存 sent/reserved/unknown は自動再送しなかった
- [ ] `send_guard`(機械層) 通過後のみ Gmail 送信し、sent / unknown_needs_reconcile を記録した
- [ ] quota 安全停止時は残件を reserved のまま次回再開対象にした
- [ ] 日本語送信レポート (sent/skip/error/要照合の件数・内訳・次アクション) を提示した

### ゴールシークループ
正本 `../run-notion-gmail-dry-run/SKILL.md` 同様、未達チェックリスト項目を埋める手順を都度生成する。
1. **既定（最小確認1回）**: `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-send/scripts/send-campaign.py"`（引数なし）で preview(exit 10) → 要約+CONFIRM_TOKEN を人間へ提示し単一確認 → `… --confirm-token <plan_hash>` で送信（少数検品は `--canary N`・意図的再送のみ `--allow-resend`・無人 cron は `--auto-approve`/`--yes`）。内部で source-audit(既定は警告整形/cron は gate)→最新 Notion から新鮮 plan 構築→(confirm は token 照合)→self-derive→guard→送信。high 残存(cron)/preflight 未充足なら誘導 (source-audit/GCP手順/db-setup/本文記入) し1通も送らず中断。
2. **対話（慎重運用）**: plan.json が無ければ `run-notion-gmail-dry-run` を起動し plan と APPROVE文字列を得る → 人間に全件プレビューを目視させ `APPROVE <plan_hash> <count> <first_to> <確認語>` を受領 → `Task(gmail-send-presend-verifier)` を context:fork で独立再検査(fail なら差し戻し) → `send-campaign.py --plan <plan.json> --approved-plan-hash <h> --approved-count <n> --approved-first-to <to> --approved-nonce <確認語>` を実行。
3. 全 checklist 充足で完了。quota 停止 (exit 3) なら再実行で残件継続。

### ゴールシーク配線
quota 安全停止後の再開や verify FAIL 後の再試行で多周回する場合の周回状態。周回末に `eval-log/notion-gmail-send/run-notion-gmail-send-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変 (SHA-256 を `eval-log/notion-gmail-send/run-notion-gmail-send-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回の手順生成は直前の `merged_directive_for_next` と `original_goal` を必須入力とする (AI 単独再導出禁止)。単発キャンペーンでは1周で完了し本配線は no-op。冪等ログが部分再開の物理的な起点となる。冪等キーは content ベース (campaign_id 非依存) なので、再開時に campaign_id を維持する必要はなく、別実行で同一 plan.json を使い直しても既 sent 単位は機構で skip される。

## Key Rules

1. **承認は Notion のチェック（データ層）が担う**: 既定の最小確認1回は `送信対象=✅` を承認シグナルとし、preview の要約に対する**人間の単一確認**で送る（重い APPROVE文字列/nonce 読解強制は厳格対話モードに温存）。無人 cron は `--auto-approve`/`--yes`。どのモードでも下記の機械的安全層は確認の重さと独立に常時オン。
2. **send_guard が正本防御（確認非依存）**: `lib/gmail_client.py` が `lib/send_guard.py` を内部で必ず呼び、plan_hash/件数/先頭To/reservedログ行/未置換トークン/From検証が揃わない限り Gmail API へ到達しない。非対話(preview/confirm/cron)でも承認 tuple を新鮮 plan から self-derive した上でこの per-unit guard loop を必ず通す（人間入力のみ bypass）。ただし非対話では plan_hash/件数/content_hash 照合は self-derive ゆえ恒真（defense-in-depth=compose バグ検出）で、plan 改竄を実効検出するのは plan.json が非信頼アーティファクトとなる厳格対話モード。PreToolUse hook (`guard-gmail-send.py`) は補助。
3. **非対話は fresh rebuild + confirm-token 束縛 / source-audit**: 古い plan.json を使い回さず、送信直前に最新 Notion から `plan_compose` で新鮮 plan を構築する。confirm モードは新鮮 plan の plan_hash が `--confirm-token` と一致する時だけ送る（preview 内容への束縛・不一致は exit 11）。無人 cron は送信前に `run_full_audit` を実行し high が残れば1通も送らず fail-closed。既定 (最小確認1回) の preview は high を ⚠️ 警告として要約へ出し全停止しない（該当 unit は送信時 per-unit skip・人間が要約を見て判断）。
4. **reserved 事前予約なしに送信しない**: 送信前に Notion ログへ reserved を作り、同一冪等キー（content ベース・campaign 非依存）が sent/reserved/unknown なら自動再送しない。2行以上は `duplicate_log_key` で fail-closed。`--canary N` の段階送信も既送は dedup で skip。
5. **送信成功後ログ失敗は unknown_needs_reconcile**: ローカル journal に退避し自動再送しない。
6. **送信時 suppress 再検証 (C-1)**: 全モードとも、plan 構築後に `メールを送らない=✅`/`送信対象=☐` へ変えた宛先は送信直前に再取得して送らない（subtract-only・承認件数を超えない）。非対話は recipient_db 未解決時に C-1 再検証不能で fail-closed。
7. **context:fork 二段確認は厳格対話モード限定**: `gmail-send-presend-verifier` は人間入力の APPROVE 文字列を独立再検査する装置。非対話モードでは入力が無く proposer==approver になるため使わず、独立検証は source-audit（独立 fetch）・C-1（独立 fetch の別スナップショット照合）・fresh rebuild・from 検証・content dedup が担う（plan_hash/content_hash 自己照合は非対話では恒真ゆえ独立検証に数えない）。
8. **sent は到達保証でない**: status=sent は Gmail API 受理を意味し受信者到達を保証しない。
9. **外部実体未確定は fail-closed**: SA鍵/DWD/sendAs/送信ログDB ID/本文記入が未充足なら送信せず誘導する。

## Gotchas

1. SA鍵/DWD/sendAs 未設定なら G1 で停止 → `../ref-gmail-dwd-setup/` と `doc/GCP-Gmail送信設定手順.md`。
2. 送信ログDB 未構築/未設定なら G2 で停止 → `../run-notion-gmail-sendlog-setup/`。
3. **非対話(preview/confirm/cron)モードは毎回最新 Notion から新鮮 plan を構築する**ため古い plan の使い回しは起きず、承認後にアドレスを編集しても次回実行では最新が反映される（confirm モードは preview 後に内容が変われば CONFIRM_TOKEN 不一致 exit 11 で再 preview を促す）。厳格対話モードの plan.json はソース変更後に dry-run を再生成して使う（古い plan を使うと plan_hash/承認文字列が変わり古い承認は通らない。仮に古い plan.json を承認文字列ごと再利用しても、既に送った単位は content ベース冪等ログが skip するため二重送信にはならない）。
4. quota 停止 (exit 3) 後は再実行で残件を継続（停止単位は reserved へ戻り自動再開対象）。dedup は content ベースなので campaign_id 維持は不要。非対話モードの再実行も新鮮 plan を作り直すが、既送は dedup で skip される。
5. 同一内容を**意図的に**再送する場合のみ `--allow-resend`（既定はクロス実行の二重送信を機構で防止）。
6. (厳格対話モードのみ) 承認には dry-run がプレビュー該当単位の行末にのみ表示する `<確認語>` が必要（`APPROVE <plan_hash> <count> <first_to> <確認語>` 完全一致・blind approve 防止）。非対話モードは確認語不要で、既定(最小確認1回)は preview 要約への単一確認＋Notion チェック整備＋source-audit 警告で代替する。
7. `multi_to_visible` の送信単位は To 受信者が互いのアドレスを見られる。厳格対話モードは承認 echo、既定(最小確認1回)は preview 要約、無人 cron は dry-run/plan.json のプレビューで事前に点検する。
8. **無人 cron(--auto-approve) は source-audit high 残存で1通も送らず停止する**（空本文/未知トークン/不正アドレス/空差し込み値）。既定(最小確認1回)の preview は同じ high を ⚠️ 警告として要約へ出し、該当 unit は送信時に per-unit skip する（全停止しない・人間が要約を見て判断する）。`/run-notion-gmail-source-audit` で内訳を確認し Notion 上で直すと skip を減らせる。送信可能 0 通なら送信せず `送信対象=✅`/本文記入を案内して終了する。
9. 送信ログDBへの書き込み（1単位ごと reserve→sending→sent の複数回）は `lib/notion_client.py` が**一定間隔でプッシュ**する（公称 3 req/sec を守る最小呼び出し間隔スロットル＋429 は `Retry-After` 尊重で自動再試行）。大量件数を一度に投げて Notion に弾かれるのを予防する。間隔/再試行回数の正本は `DEFAULT_MIN_INTERVAL_SEC`/`DEFAULT_MAX_RETRIES`（コード側 SSOT）。

## Additional Resources

- `scripts/send-campaign.py` — live-send 本体 (preflight→reserve→send_guard→Gmail→log→report)
- `scripts/verify-plan.py` — 送信前二段確認の独立再計算
- `prompts/R1-orchestrate.md` / `prompts/R2-presend-verify.md` — 責務プロンプト
- `../ref-notion-gmail-send-spec/` — データ契約・安全設計の参照正本
- `../run-notion-gmail-dry-run/` — plan.json と APPROVE文字列を生成する前段
- `../../agents/gmail-send-presend-verifier.md` — context:fork 二段確認 subagent
- `../../lib/` — send_guard / gmail_client / idempotent_log / plan_build / preflight ほか
- `../../hooks/guard-gmail-send.py` — Gmail 直接送信の補助遮断
