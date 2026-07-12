---
name: run-mf-invoice-check
description: 前月と今月の請求書発行漏れをチェックしたいとき、月次で請求発行状況を確認したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--month YYYY-MM] [--backfill --from YYYY-MM --to YYYY-MM]"
arguments: [month, backfill, from, to]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-19
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-06-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-collect.md
  - prompts/R2-diff.md
  - prompts/R3-verify.md
  - prompts/R4-sink.md
schema_refs:
  - schemas/invoice-gap-result.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 発行漏れ候補が「前月取引−今月取引」の差集合として transaction.date 帰属で正しく算出され、月またぎ発行(例 6月取引→7月発行)も誤判定しないことを pytest で機械検証できる。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 二段確認の物理境界が機構強制される——sink が確定リスト(mfk-gap-verified.json)不在では fail-closed(exit 2)で停止し、未検証候補の直結投入を防ぐことを test_check_invoice_gaps で機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: スキル全体がユーザ目的(発行漏れの早期発見・独立 context での誤検出排除・候補0件月も含む確認済み履歴の保全・参照専用の保証)を最適に反映し、collect→verify→finalize→sink と Notion 冪等 upsert の責務分割が目的に対し過不足ないこと。
      verify_by: elegant-review
---

# run-mf-invoice-check

## Purpose & Output Contract

前月取引・今月取引の取引先（発行漏れ候補）を MF掛け払い API から差集合で洗い出し、商品名・前月/今月金額・取引先企業名を突合して Notion DB に冪等 upsert し、画面にも要確認リストを表示する。月帰属は `transaction.date` (取引日・月末締め) 基準で、発行日が翌月月初でも対象月の請求として扱う。upsert キーは顧客ID単独で 1 顧客=1 ページ。既存顧客は月が変わっても同じページを更新し、未登録顧客だけ新規ページを作成する（月ごとの重複ページは作らない）。月次履歴は各顧客ページ本文の table block に蓄積する。候補0件の月も全チェック対象顧客の行が table に残り確認済み月を記録する。

**入力**: `month`（任意。既定は実行日の年月を「今月」とし、比較する前月はその1つ前を自動算出。例: 2026年6月中は 対象年月=2026-06、今月金額=2026-06、前月金額=2026-05）。過去月の範囲一括投入は `--backfill --from YYYY-MM --to YYYY-MM` (両端含む・月昇順、`--month` と排他)
**出力**: 発行漏れ候補が Notion DB に反映 (1 顧客=1 ページ) + 各顧客ページ本文の月次履歴 table に当月行を upsert + 画面に要確認リスト。
**完了条件**: collect→verify(subagent)→sink が完了し、確定候補が顧客IDキーで Notion に upsert され月次履歴 table に当月行が反映された状態。

## End-to-End Flow

```
[1 collect]  check_invoice_gaps.py --collect → eval-log/mfk-gap-candidates.json (未検証の月次チェック行) + 画面サマリ
[2 diff]     lib/mfk_invoice_diff.detect_gaps (collect内, 純関数・pytest済)
[3 verify]   subagent mfk-gap-verifier (context:fork) で誤検出排除
[4 finalize] check_invoice_gaps.py --finalize [--exclude-ids …] → eval-log/mfk-gap-verified.json (確定)
[5 sink]     check_invoice_gaps.py --sink → 確定リストを顧客IDキーで Notion 冪等upsert (1顧客=1ページ、既存顧客は更新、未登録顧客だけ作成)、ページ本文の月次履歴 table に当月行を upsert
             ↑ 確定リスト不在なら fail-closed(exit 2)。MF APIは全GET / 変更系は hook(guard-mfk-readonly.py)で遮断
```

詳細は `workflow-manifest.json`、責務は `prompts/R1-R4`。collect 出力(未検証)と finalize 出力(確定)を
別ファイルに分離し、sink が確定リストを fail-closed で要求することで二段確認を標準フローで要求する。

## ゴールシーク実行

### ゴール (Goal)
前月取引−今月取引の差集合（発行漏れ候補）が商品名/金額/取引先企業名つきで Notion DB に冪等 upsert され、独立 context の subagent で誤検出を排除した要確認リストが画面に提示された状態。

### 目的・背景 (Why)
発行漏れの早期発見。チェック漏れは取引先との信頼低下に直結するため、月次で機械的に差集合を洗い出す。契約終了等の除外は API で判別できないため人が請求要否列で管理し、機械では消さない。誤検出を防ぐため候補は独立 context で二段確認する。

### 責務サマリと完了条件の正本

各責務の**完了条件の詳細は `prompts/Rn` の L5.3 完了チェックリストを正本 (SSOT)** とする (片側更新ドリフトを避けるため SKILL 側で再定義しない)。本節は俯瞰用の責務サマリのみ示す。

- **R1 collect** (`prompts/R1-collect.md`): 前月・今月の `/billings/qualified` を全ページ取得する。
- **R2 diff** (`prompts/R2-diff.md`): 取得集合を `発行漏れ候補/継続発行/今月新規` に差集合分類し金額変動を検出する。
- **R3 verify** (`prompts/R3-verify.md`): subagent `mfk-gap-verifier` が独立 context で誤検出を排除する。
- **R4 sink** (`prompts/R4-sink.md`): 顧客ID単独キーで Notion DB に冪等 upsert する (1 顧客=1 ページ、既存顧客は更新、未登録顧客だけ作成し、月ごとの重複ページは作らない。既存ページの管理列に触れない)。新規ページでは `初回契約月` を空欄初期化して未設定顧客を Notion ビューで表示できるようにする (`支払サイクル` は初期化せず人が設定)。各顧客ページ本文の月次履歴 table に当月行 (自然キー `period_ym`) を upsert し確認済み履歴を残す。

横断不変条件 (各 Rn の L1/L4 が担保): **支払サイクルが `年間払い` かつ初回契約月から12ヶ月以内の発行漏れ候補だけを機械が自動抑制する** (`初回契約月` + `支払サイクル` から `billing_lifecycle` で判定し、年間前払い期間中で月次発行が無いのが正常な顧客を候補から除外)。`支払サイクル` が `月払い`/空欄/不明、または `初回契約月` が空/不明の顧客は fail-safe で発行漏れ候補に残す。一方、契約終了・請求要否など API で判別できない例外判断は引き続き人が `請求要否` 列で行う。MF API への POST/PATCH/DELETE は hook で遮断され参照専用が保証される。

### 完了チェックリスト (Checklist)
> 各責務の停止条件詳細は `prompts/Rn` の L5.3 を正本 (SSOT) とする。本節は俯瞰用の二値チェックのみ。
- [ ] `--collect` が前月/今月の qualified billing を全ページ取得し未検証候補 JSON を出力した (R1/R2)
- [ ] subagent `mfk-gap-verifier` が独立 context で誤検出を排除した (R3)
- [ ] `--finalize` が確定リスト `eval-log/mfk-gap-verified.json` を物質化した (二段確認の物理境界)
- [ ] `--sink` が確定リストを顧客ID単独キーで冪等 upsert した (1 顧客=1 ページ、既存顧客は更新、未登録顧客だけ作成、月ごとの重複ページなし、管理列不可侵, R4)
- [ ] `--sink` が各顧客ページ本文の月次履歴 table に当月行 (自然キー `period_ym`) を upsert した (同月再実行は行更新で重複しない)
- [ ] 運用者が任意の過去月の確認済み状態を Notion 上 (各顧客ページ本文の月次履歴 table) で参照できる (見方は README『過去月の状態を確認する』参照)
- [ ] `database_id` 未設定時は db-setup へ差し戻した

### ゴールシークループ
1. `--collect` で現状取得→差集合→突合し未検証候補JSONを得る（`R1`/`R2`）。
2. subagent で二段確認し誤検出を排除（`R3`）。
3. `--finalize [--exclude-ids …]` で確定リストへ昇格（`R3`）。確定リスト不在では次へ進めない。
4. `--sink` で確定リストを Notion へ冪等 upsert（`R4`）。既存顧客は更新し、未登録顧客だけ作成する。確定リスト不在なら fail-closed。
5. 全 checklist 充足で完了。`database_id` 未設定なら db-setup へ差し戻す。

## Key Rules

1. **参照専用（二層で抑止）**: 第1層=`hooks/guard-mfk-readonly.py`（PreToolUse）が Bash 経由の MF 変更系コマンドを遮断。第2層=`lib/mfk_api.py` は GET 専用で POST/PATCH/DELETE 関数を構造的に持たない。
2. **一覧は qualified**: インボイスモードで `/billings` は空。`/billings/qualified` を使う。
3. **冪等 upsert**: 顧客ID単独キー。1 顧客=1 ページ。既存顧客は月が変わっても同じページを更新し、未登録顧客だけ新規ページを作成する。月ごとの重複ページは作らない。事実列・監査メタ列 (最新月スナップショット) のみ書き、既存ページの管理列は触らない。新規ページ作成時だけ `初回契約月` を空欄初期化する。
4. **月次履歴は本文 table**: 各顧客ページ本文の table block (列: 対象年月/今月の発行状況/前月金額/今月金額/確認済み日時) に 1 行=1 対象年月で蓄積。自然キー `period_ym` で当月行を upsert し、同月再実行は行更新 (冪等)。サマリ行・件数集計プロパティ・paragraph 追記は持たない。候補0件月も全チェック対象顧客の行を collect が毎月記録する。
5. **二段確認必須（標準フロー）**: collect は未検証候補、finalize が確定リストを別ファイルに物質化。sink は確定リストを fail-closed で要求し、未検証投入は `--force-unverified` 明示時のみ。verify をスキップした直結投入を標準導線から外す（Sycophancy/誤検出防止）。
6. **年間契約期間は機械が自動抑制／契約終了の例外は人**: 発行漏れ候補のうち**支払サイクルが `年間払い` かつ初回契約月から12ヶ月以内の顧客だけ**を機械が自動抑制し候補から除外する (`suppress_annual_period_gaps`、年間前払い期間中は月次発行が無いのが正常)。一方、契約終了・請求要否など API で判別できない例外判断は引き続き人が Notion `請求要否` 列で行う。月払い/支払サイクル空欄/初回契約月空欄の顧客は fail-safe で発行漏れ候補に残す。
7. **初回契約月・支払サイクルは人が記入**: MF API に契約 Object は無く、契約開始月・支払サイクルは API から判別できない。`初回契約月` に YYYY-MM、`支払サイクル` (月払い/年間払い) を人が設定する。月次 sink はこれら管理列に触れない。**機械は `支払サイクル=年間払い` と記入された顧客だけ `初回契約月` を使って年間契約期間中の発行漏れ候補を自動抑制する**。
8. **既定対象月＝実行日の年月**: `--month` 未指定時の「今月」は実行日の年月。`対象年月(period_ym)` ラベルもこの今月に一致する（label==今月の不変条件を維持）。例: 2026年6月30日 23:59 までは 対象年月=2026-06・今月金額=2026-06・前月金額=2026-05。2026年7月1日 0:00 以降は 対象年月=2026-07・今月金額=2026-07・前月金額=2026-06。特定月を見たいときは `--month YYYY-MM` を明示。
9. **固定プロパティ＋上書き＋本文履歴**: DB の `今月金額`/`前月金額` は月ごとに増やさない**固定 number プロパティ**で、毎回最新月スナップショットに**上書き更新**（どの月かは `対象年月` プロパティが示す）。過去月の推移は各顧客ページ**本文の table block** で管理。`今月金額` が空（発行漏れ候補）/非空で DB を直接フィルタできるよう、列は固定のまま据え置く。

## Gotchas

1. `database_id` 未設定なら `run-mf-invoice-db-setup` を先に実行。
2. MF APIキーと Notion トークンは別 Keychain entry。
3. `updated_at` は無いので更新日は `created_at` で代替。
4. 月をまたぐ発行（6月取引→7月発行）があるため、判定軸は必ず `transaction.date`。`issue_date` は取得窓として対象月初〜翌月末を over-fetch するために使う。
5. 過去月の見方・要対応ビューの作り方は README『過去月の状態を確認する』節を参照。月次履歴は各顧客ページを開き本文 table block (対象年月/今月の発行状況/前月金額/今月金額/確認済み日時) で確認。DB は顧客一覧 (最新月スナップショット) として使う。
6. 過去月の範囲一括投入 (backfill) は `--backfill --from YYYY-MM --to YYYY-MM` で範囲 (両端含む) を月昇順に collect→sink で回す。複数月を自動で回すため対話 verify は挟めず `--month` の単月フローとは排他。既定では未検証の `発行漏れ候補` は投入せず、継続発行/今月新規のみ履歴化する。発行漏れ候補まで履歴 table に残す必要がある場合だけ `--force-unverified` を明示する。
7. **全体トータル/件数は持たない設計**。集計は Notion DB ビューのフィルタ件数 (例: `今月の発行状況 = 発行漏れ候補` で絞った行数) で代替し、サマリ列を手動で足さない。`--sink` は upsert 後に live DB を read-only GET して旧サマリ列・余剰列の残存を検知し、残っていれば stderr で `/run-mf-invoice-db-setup` 再実行を誘導する (検知のみ・列削除はしない=参照専用維持)。旧サマリ列や `全体トータル` 列が残っていたら db-setup を再実行して掃除する。月次フローは参照専用(検知のみ・列削除しない)を中核保証とし、列削除は db-setup の責務に集約する(責務分離。月次が勝手に列を消すと人が意図的に足した列の破壊や参照専用保証の崩壊を招く)。deprecated 登録の既知集計列(全体トータル等)は db-setup で自動削除/verify で FAIL。whitelist に無い新名の集計列(総計/月次サマリ等)は『集計列の疑い』として検知され画面/verify で掃除誘導される(削除はしない)。

## Additional Resources

- `workflow-manifest.json` — collect/diff/verify/sink の Step 定義 + hook guard
- `scripts/check_invoice_gaps.py` — collect/finalize/sink 実行スクリプト (出力先は env MFK_OUTPUT_DIR > CLAUDE_PROJECT_DIR > CWD で解決)
- `prompts/R1-collect.md`〜`R4-sink.md` — 責務プロンプト
- `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` — API仕様・判定アルゴリズム正本
- `$CLAUDE_PLUGIN_ROOT/lib/` — mfk_api / mfk_keychain / mfk_invoice_diff / notion_invoice_sink
- `$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-readonly.py` — 参照専用ガード
- `$CLAUDE_PLUGIN_ROOT/agents/mfk-gap-verifier.md` — 二段確認 subagent
