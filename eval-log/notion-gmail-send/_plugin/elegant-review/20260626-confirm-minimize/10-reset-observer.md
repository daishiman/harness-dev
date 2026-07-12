# Phase1 思考リセット・俯瞰レポート — notion-gmail-send（確認0自動化レンズ）

参照済み: README.md / 両 SKILL.md（send・dry-run）/ lib/send_guard.py / lib/plan_build.py / skills/run-notion-gmail-send/scripts/send-campaign.py / prompts/R1-orchestrate.md / agents/gmail-send-presend-verifier.md / hooks/guard-gmail-send.py / 00-shared-brief.md

## ① 確認ポイントの地図
- **対話的人間確認は実質1ゲートのみ**。dry-run 全件プレビューを (a)目視 → (b)特定単位行末の `<確認語>`(nonce)読み取り → (c)`APPROVE <plan_hash> <count> <first_to> <確認語>` 完全一致入力 — この3動作が唯一の人間の摩擦。
- それ以降は全自動: presend-verifier(fork) → preflight(G1認証/G2送信ログDB/G3整合) → send_guard → Gmail送信 → 冪等ログ → 日本語レポート。
- 機械的安全層(A)は人間確認と独立して効く。send_guard.check() が plan_hash/件数/先頭To/reserved/未置換/From/nonce を全一致強制、send-campaign.py が units から plan_hash・件数・content_hash を決定論再計算して三者照合。
- Notion側の承認シグナル候補が既存: 宛先DB `送信対象=✅`/`メールを送らない=✅`、本文DB `メッセージ対象=✅`。
- 既に送信時 suppress 再検証(C-1) が「承認後に `メールを送らない=✅`/`送信対象=☐` に変えた宛先は送らない」を subtract-only で実装済 = Notion を最新の送信意思ソースとして送信直前に引く経路が既存。
- nonce は plan_hash から1単位を決定論選択し content_hash にバインドした6桁。機械チェックだが目的は純粋に人間の注意喚起（読解強制）。

## ② 第一印象の懸念点
**事実(コードに存在):** F1.対話確認は1ゲートに集約=摩擦の本体 / F2.send_guard・決定論セルフチェック・preflight・dedup・hook は人間確認に非依存 / F3.nonce の目的は読解強制のみ / F4.C-1 で Notion 最新状態を送信直前再取得し抑制。

**懸念(仮定・要検証):**
- A1. 承認の意味論ズレ: `送信対象=✅` は「この人/本文に送る」意思だが、差し込み後の最終本文とは別物。チェック時点と送信時点の間に変更が入ると「Notionチェック=最終内容承認」とは限らない。
- A2. auto-approveでトートロジー化: 承認tupleを plan から自己導出すると `approved_plan_hash==plan_hash` が「自作物と自分が一致」になり内容妥当性の独立停止点が消える。残るは「plan.json外部改竄なし/Notionデータ通り送った」保証のみ。
- A3. presend-verifier の意義が宙吊り: 二段確認は「人間入力のAPPROVE文字列」を入力に取る。対話承認を消すと検証対象が plan 自己整合のみになり目的が変質。
- A4. nonce が二択化: 確認0なら nonce は (i)撤去 か (ii)残置auto照合(A2でトートロジー)。確認0と原理的に両立しない。
- A5. 残せそうな安全網: canary既定/source-audit自動実行/preflight G1-G3 は対話確認0でも機能。過剰代償にならず温存可能。

## ③ 後続3分析が見るべき論点
**論理構造:** L-1 send_guard 各フィールドを「改竄検出」と「人間の内容承認=停止点」のどちらが担うかで分離し auto-approve化で温存/消失する不変条件を構造列挙 / L-2 承認tuple自己導出が `approved_*==actual_*` をトートロジー化する正確な条件と残る防御の射程を切り分け。
**メタ発想:** M-1 確認を対話イベント→データ状態へ移すと生じる承認の時間アンカー問題（チェック時点/dry-run生成時点/送信時点）/ M-2 nonce の理解強制目的を チェック付与行為/source-audit pass/canary必須 のどれに再配置しうるか発散。
**システム戦略:** S-1 既存機構(C-1/content dedup/source-audit/preflight/canary)で対話確認0のリスクを吸収する安全網の再配置戦略 / S-2 skill-creator(feedback_contract)経由改善が両SKILLの IN1/IN2(test)・OUT1(elegant-review 4条件)に契約レベルでどう波及するか。
