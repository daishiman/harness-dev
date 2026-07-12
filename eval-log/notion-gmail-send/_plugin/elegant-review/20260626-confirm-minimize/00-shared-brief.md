# elegant-review run: 20260626-confirm-minimize

## 対象
`plugins/notion-gmail-send/`（Notion 2DB → Gmail 一斉個別送信 plugin）

## ユーザー要望（最上位ゴール）
**この plugin を自動化したい。確認事項（人間の対話的確認）が多いと手間がかかる。確認事項を最大限省略し、最悪0でも問題ない。** 既に Notion 側でチェック（`送信対象=✅` 等）を付けているので、**Notion のチェックを承認シグナルとして扱い**、対話的な確認手順を最大限減らしたい。改善は **skill-creator の仕組み**（skill-improve / run-build-skill / feedback_contract）を通して行う。

## 現状の「確認」構造（親エージェントが事前精査した事実 — 各自で裏も取ること）

### (A) 機械的安全チェック（人間の手間ゼロ・誤送信/二重送信の核 — 原則温存）
`lib/send_guard.py check()` が Gmail API 到達前に全件一致を強制:
- approved_plan_hash == plan_hash（units から決定論再計算で束縛 / plan.json 改竄・件数偽装を弾く）
- approved_count == actual_count
- approved_first_to == actual_first_to
- reserved_log_id 存在（事前予約なしの送信禁止）
- unresolved_tokens 空（未置換 `{{}}` 残存で fail-closed skip）
- from_verified（sendAs/impersonate 検証）
- **approved_nonce == actual_nonce**（後述・読解強制の機械エンフォース）
- content ベース冪等 dedup `{本文page_id}:{宛先page_id}:{content_hash}`（campaign_id 非依存・二重送信防止）

### (B) 対話的人間確認（摩擦の本体 — 今回の削減対象）
1. `/run-notion-gmail-dry-run` が plan.json + 全件プレビュー + `APPROVE <plan_hash> <count> <first_to> <確認語>` 文字列を出力
2. 人間が**全件プレビューを目視**（rendered 後フル本文）
3. 人間がプレビュー特定単位の行末から **`<確認語>`(nonce) を読み取る**（blind approve 防止）
4. 人間が `APPROVE <plan_hash> <count> <first_to> <確認語>` を**完全一致で入力**
5. 以降は自動: presend-verifier(context:fork) → preflight(G1/G2/G3) → send_guard → Gmail送信 → ログ

### 要石: approval_nonce（`lib/plan_build.py approval_nonce()`）
- plan_hash から決定論的に1単位を選び content_hash にバインドした6桁短コード。
- dry-run は該当単位プレビュー行末にのみ表示。APPROVE 行には載せない。
- `send_guard` が再計算照合 → 人間が「該当単位を目視で探して読む」ことを強制（=理解のコスト上げ）。
- **これは機械チェックだが目的は人間の注意喚起**。承認を Notion へ移すなら、この目的（理解の保証）の再配置が論点。

### Notion 側の既存チェック（承認シグナル候補）
- 宛先DB(メール送信先_DB): `送信対象=✅`（送信対象に含める）/ `メールを送らない=✅`（最優先抑制）。
- 本文DB(メール本文_DB): `メッセージ対象=✅`（送る本文）。
- これらは既に**宛先ごと/本文ごとの熟慮的な人間操作**。`送信対象=✅` は事実上の per-recipient 承認。

## 設計仮説（親の初期見立て — 検証/反証/改善せよ）
**承認シグナルを「対話時の APPROVE 文字列/確認語」から「Notion チェックボックス(データ層)」へ移設**し、`run-notion-gmail-send` に **非対話 auto-approve モード**を追加する。送信コマンドが内部で dry-run→plan 構築→APPROVE tuple を**plan から自己導出**して送信する。機械安全チェック(A)は全て温存（plan改竄/二重送信/未置換skip/From検証は人間の注意とは無関係に効く）。nonce の「理解強制」目的は「Notion でチェックを付ける熟慮的行為」へ再配置。
- 安全網の候補（検討せよ）: 本文DBに campaign 単位の `送信承認=✅` トグルを追加（go シグナルを1スイッチに集約）/ source-audit を送信前に自動実行（空本文・未置換・不正アドレスは元々 fail-closed skip）/ 初回 canary 既定。
- ただしユーザーは「最悪0でも問題ない」と明言。過剰な代償ゲートで要望を相殺しないこと。

## ★ユーザー確定（2026-06-26 追補・最重要）
**目標の確認回数: 既定＝0回（理想）、最悪でも1回まで。極力ゼロ。**
- 「できれば確認することなく送る。もしくは最低1回。極力確認することなく送りたい」。
- ⇒ 設計目標は「**対話的確認0をデフォルト達成可能**にする」。承認は Notion のチェック（データ層）が担う。
- 1回許容される確認は、複雑な `APPROVE <plan_hash> <count> <first_to> <確認語>` 完全一致のような重いものではなく、**最小の単純確認**（あるいは Notion 側の1トグル）に限る。
- 機械的安全層(A)は確認回数と独立に常時オン（手間ではないので温存）。誤送信防止は対話確認ではなく機械＋Notionデータで担保する。

## 検証4条件（全て PASS が完了条件）
- 矛盾なし / 漏れなし / 整合性あり / 依存関係整合

## 主要ファイル
- README.md（三本柱・TL;DR・運用フロー）
- skills/run-notion-gmail-send/{SKILL.md, prompts/R1-orchestrate.md, prompts/R2-presend-verify.md, scripts/send-campaign.py, scripts/verify-plan.py}
- skills/run-notion-gmail-dry-run/{SKILL.md, scripts/build-plan.py}
- lib/{send_guard.py, plan_build.py, gmail_client.py, idempotent_log.py, preflight.py, notion_client.py, notion_config.py, message_assemble.py, render_substitute.py}
- hooks/guard-gmail-send.py
- agents/gmail-send-presend-verifier.md
- skills/ref-notion-gmail-send-spec/references/spec-detail.md（データ契約・安全設計の参照正本）
- doc/run-notion-gmail-send-仕様と検証メモ.md（実装 SSOT。repo-root の doc/）
- tests/（pytest 168 件規模）

## 出力規約
各分析エージェントは findings を構造化して返し、`eval-log/notion-gmail-send/_plugin/elegant-review/20260626-confirm-minimize/` 配下へ自分の成果物 md を書くこと。最終 text にも要約を必ず含める（final text が親へ返る唯一経路）。
