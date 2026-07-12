---
name: run-notion-gmail-source-audit
description: メール本文DB/メール送信先_DBのデータ品質を送信前に点検したいとき、空本文や不正アドレスや未置換リスクを洗い出したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--db1 <id>] [--db2 <id>] [--config <path>] [--json]"
arguments: [db1, db2]
allowed-tools:
  - Read
  - Bash(python3 *)
kind: run
prefix: run
effect: conversation-output
owner: team-platform
since: 2026-06-24
version: 0.1.0
source: doc/run-notion-gmail-send-仕様と検証メモ.md
source-tier: internal
last-audited: 2026-06-24
audit-trigger: source-update
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 送信元2DBの品質監査が空本文・未知/廃止トークン(deprecated_token)・不正アドレス・プロ人材重複・空差し込み値を検出し、Notion へ一切書き込まず(conversation-output)skip 予測のみを提示することを test_notion_mock / test_core_logic の audit テスト群で機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 「送信前にデータ品質を点検し送信時に skip される行を事前に可視化する(参照専用)」というユーザー目的を過不足なく満たし、dry-run/send の preflight 判定基準と監査観点が整合することを run-elegant-review の4条件で確認する。
      verify_by: elegant-review
---

# run-notion-gmail-source-audit

## Purpose & Output Contract

送信元の2DB（メール本文_DB / メール送信先_DB）のスキーマとデータ品質を**送信前に**監査し、送信成功率を下げる問題（空本文・未知トークン・不正アドレス・プロ人材重複・空差し込み値）を行単位で洗い出す。Notion への書き込みはせず（改善は人が Notion 上で行う領域）、何を直せばよいかと送信時 skip 予測を提示する。

**入力**: `db1` / `db2`（任意。未指定なら `.notion-config.json` の `notion_gmail_send.source` から解決）
**出力**: 改善推奨レポート（行単位の issue + severity + 推奨アクション）+ 送信時 skip 予測（未置換になる宛先数・プロ人材重複数）。`--json` で機械可読。
**完了条件**: 2DB を取得し、本文DB/宛先DB/クロスの issue を全件提示した状態。high severity 0 件なら dry-run へ進める。

## End-to-End Flow

```
[1 取得]    audit_mail_dbs.py が DB1/DB2 を REST 取得 (GET のみ・送信しない)
[2 本文監査] メッセージ対象✅の本文行: 空本文/複数codeblock/未知トークン(typo)/From・CC不正
[3 宛先監査] 送信対象✅の宛先行: プロ人材メール空/不正アドレス/秘書CC不正/送らない抑制/プロ人材重複
[4 クロス]   本文が使うトークン × 宛先の対応値が空 → 送信時 unresolved_token skip を事前予告
[5 レポート] 行単位 issue + severity + 送信時 skip 予測。改善は人が Notion で実施
```

実行: `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-source-audit/scripts/audit_mail_dbs.py"`（`--db1/--db2` override、`--json` 機械可読）。詳細仕様は `../ref-notion-gmail-send-spec/`。

## ゴールシーク実行

### ゴール (Goal)
メール本文DB と メール送信先_DB の送信対象行が、空本文・未知トークン・不正アドレス・プロ人材重複・空差し込み値の有無を行単位で検査され、送信時に skip される組が事前予告され、改善推奨レポートが提示された状態。high severity 0 件なら dry-run へ安全に進める。

### 目的・背景 (Why)
送信は不可逆なので、落ちる送信単位は送る前に直すのが安全かつ効率的。dry-run は送信単位(直積)を作って初めて skip を検出するが、本スキルは**行レベルで先回り**し「この宛先への全本文が未置換で落ちる」「この本文は送り主が不正」を事前に示す。改善判断（契約終了・宛先メンテ等）は人の領域なので機械は検出のみ行い、Notion を書き換えない（仕様書 §1）。

### 完了チェックリスト (Checklist)
- [ ] `.notion-config.json` の `notion_gmail_send.source`（または `--db1/--db2`）で2DBを解決した
- [ ] 本文DB: メッセージ対象✅だが本文が使えない行（空本文/複数codeblock/取得失敗）を検出した
- [ ] 本文DB: 件名・本文の {{}} トークンが既知集合（会社名/担当者様名）外（typo）/廃止（部署名=deprecated_token）の行を検出した
- [ ] 本文DB: 送り主(From)・CC のアドレス形式不正を検出した
- [ ] 宛先DB: 送信対象✅だがプロ人材メール空/不正、秘書(CC)アドレス不正、送らない抑制、プロ人材重複(最新 `created_time` 1件のみ、同時刻は `page_id` 降順)を検出した
- [ ] クロス: 本文が使うトークンに対し値が空な宛先（送信時 unresolved skip）を予告した
- [ ] 行単位 issue + severity + 送信時 skip 予測を日本語レポートで提示した
- [ ] Notion へ書き込んでいない（検出のみ）

### ゴールシークループ
1. `audit_mail_dbs.py` を実行し、本文DB/宛先DB/クロスの issue を取得する。
2. high severity の issue を優先提示し、改善方法（Notion 上で本文記入・トークン修正・アドレス訂正・重複整理）を案内する。
3. 利用者が Notion を修正したら再実行し、high severity 0 件になるまで反復する。
4. high severity 0 件で完了。次工程 `run-notion-gmail-dry-run` へ送信計画確認を促す。

## Key Rules

1. **read-only**: 本スキルは Notion を書き換えない。検出と改善提案のみ（宛先メンテは人の領域 §1）。Notion API は GET のみ。
2. **送信前の関所**: dry-run の前段。high severity が残るまま送信フローへ進めると skip が増える。
3. **既知トークンは2つ**: `会社名` `担当者様名`。これ以外の {{}} は typo として high(`unknown_token`) で報告。廃止の `部署名` は medium(`deprecated_token`) で削除を案内（いずれも送信時 unresolved で skip）。
4. **クロス検査が肝**: 本文が使うトークンと宛先値の突合で「送信時に落ちる組」を事前予告する。
5. **秘密値非出力**: Notion API キーは Keychain 経由のみ。生値を出力しない。

## Gotchas

1. `.notion-config.json` 未設定なら `--db1/--db2` で DB id を直接指定。
2. メッセージ対象✅でない本文行・送信対象✅でない宛先行は母集団外として扱い計上しない。
3. プロ人材重複（同一プロ人材メールが複数page）は同一人物への重複送信につながるため medium で報告する。秘書CCだけの重複はこの判定対象にしない。
4. 改善後は必ず再 audit → dry-run の順で確認する。

## Additional Resources

- `scripts/audit_mail_dbs.py` — 2DB データ品質監査の実行本体（read-only）
- `../ref-notion-gmail-send-spec/` — 2DB列マッピング・本文true/宛先true定義・トークン仕様の参照正本
- `../../lib/mail_db_audit.py` — 本文/宛先/クロス監査ロジック
- `../run-notion-gmail-dry-run/` — 監査後に送信計画を作る次工程
