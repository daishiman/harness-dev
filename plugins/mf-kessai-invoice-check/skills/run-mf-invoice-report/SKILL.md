---
name: run-mf-invoice-report
description: 前月と今月のMF掛け払い発行状況を比較して請求漏れレポートを出したいとき、年契約やトライアル完了などのイレギュラーを事情コメント付きで月次レポートDBへ冪等生成したいときに使う。
disable-model-invocation: false  # 自然文「前月と今月の請求書発行状況を比較して漏れレポートを出して」で自動起動させる。書込安全は既定 dry-run + --apply に --verified を要求するゲートで担保 (reconcile と同型: external-mutation でも model-invocable)。
user-invocable: true
argument-hint: "[--target YYMM] [--apply --verified]"
arguments: [target, apply, verified]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-07-07
version: 0.4.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-07-10
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-collect.md
  - prompts/R2-classify.md
  - prompts/R3-verify.md
  - prompts/R4-render.md
  - prompts/R5-archive.md
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 前月↔今月比較と 12 ヶ月フル遡り(差分該当取引先のみ)の年契約周期/トライアル完了/契約終了分類が test_mfk_period_report で機械検証でき、正常イレギュラーと真の発行漏れを取り違えず取引先名/対象月/漏れチェック(checkbox 正常=✓/要対応=☐)/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの8列が『この左→右の順で』定義され各行で該当列が埋まる(停止/契約完了行の今月の金額・新規/継続漏れ行の先月の金額は意味的に空を許容)。両月未発行でも今月 verdict=GAP の継続漏れ・および支払サイクル=月払いのアクティブ契約が完了未確認で 2ヶ月以上未発行 (要因C) は要対応として emit し脱落させない(Notion title=取引先名を先頭・列7=テキスト説明・金額は税抜)
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 同一対象月で 2 営業日目・3 営業日目相当のデータを与え連続実行しても C04 sink が指定見出しに紐づく同じ report_db_id を更新し、単一恒久 DB へ入力同定 {取引先×契約ID×商品} と stored key (対象月,取引先名,商品名) で同一行を 1 行へ収束させ (同月 2 回実行で重複行 0・日々追加・二重 DB 0・非破壊マージで run-1={A,B}→run-2={A,C} 後も DB が {A,B,C} を保持=以前 run の行が消えない/clear-then-insert と区別可能・契約ID違いは要対応優先で collapse 計上)、別月行も対象月列で同一 DB に共存すること、各イレギュラー行がなぜ先月あって今月なくて問題ないかの事情コメントを持ち分類不能な差分だけが真の発行漏れとして漏れチェックに残ることを受入テストが確認する
      verify_by: test
---

# run-mf-invoice-report

## Purpose & Output Contract

MF掛け払いの**前月↔今月の請求書発行状況を突合**し、状態遷移 (今月あり×前月あり=継続発行 / 今月あり×前月なし=新規・年→月切替 / 今月なし×前月あり=非請求事情確認→発行漏れ候補 / 今月なし×前月なし=対象外・ただし今月 verdict=GAP の継続漏れ・および支払サイクル=月払いのアクティブ契約が完了未確認で 2ヶ月以上未発行 は要対応→要因C) を分類して、**取引先名 / 対象月 / 漏れチェック / 商品名 / 先月の金額 / 今月の金額 / 先月と今月の比較 / コメント の 8 列を『この左→右の順で固定』** (取引先名=title を先頭・漏れチェック=checkbox: 正常=✓/要対応=☐) したレポートテーブルを生成する。継続発行 (今月あり×前月あり) も漏れチェック=正常 (✓) として**全行 emit** し全請求書一覧を成す (非 emit は今月なし×前月なしのうち、今月 verdict=GAP の継続漏れでも要因C(月払いアクティブ契約の完了未確認 2ヶ月以上未発行)でもない=正常抑制 SUPPRESS_*/元々請求なし の行のみ)。真の発行漏れ (単月遷移の漏れ + 両月未発行の継続漏れ) だけを漏れチェック=要対応に残し、年契約/年→月切替/トライアル完了/契約終了の正常イレギュラーには**なぜ問題ないかの事情コメント**を焼く。

**対象月の定義**: 今月=直近締め済みの請求対象月 (例: 2026-07-02 実行なら 2026-06 分=`2606`)、先月はその 1 ヶ月前 (`2605`)。実行日カレンダー月ではない。

出力先は**指定見出しに紐づく単一恒久レポート DB** (または config `notion.report_database_id` で明示 pin した DB)。C04 sink はまず **`report_database_id` (明示 pin・step0) が set ならその DB を構造同定を経ず直接更新**し (出力先を指定先へ確実に着地させ、構造同定のズレで別 DB=phantom へチェックが書かれる症状を根治=要件2)、未 pin なら `report_toggle_block` が指すトグル見出し/プレーン見出し2を起点に既存 DB を構造同定して更新する。**明示 pin なし かつ 既存 DB 未発見のときは phantom を作らず fail-closed (exit 2) で停止**し (別 DB へ誤書込しない)、新規作成は初回セットアップ用の `--allow-create` 明示時のみ見出しの下 (ページ直下) に行う。**指定見出しはこのレポート専用の器ゆえ配下 DB は表示名非依存で同定する** — ユーザーが DB を『請求漏れ確認レポート』等どんな名前で手作りしても既存として更新し、title 列名が Notion 既定の『名前』でも実名を検出して書く (名前ドリフトによる二重作成/全行 skip を防ぐ)。新規作成はページ直下に落ちるため初回のみ UI で見出しの下へ移動すれば以後自動更新。C04 sink 経由で単一 DB へ書き、同月内の 2/3 営業日目再実行は入力同定 **{取引先(customer) × 契約ID(contract_id) × 商品(product)}** と C04 の stored key **(対象月, 取引先名, 商品名)** で重複行を出さず**日々追加**する。固定 8 列に契約ID列は無いため契約IDは永続化せず、契約ID違いは要対応優先で 1 行へ収束し `collapsed_multi_contract` に計上する。非破壊マージにより以前 run で書いた行も別月行も今回入力に無くても削除しない。DB 構築/配置/冪等 upsert は C04 sink が所有する。

**入力**: `--target YYMM` (対象月・省略時は実行日から直近締め済み月を導出)。既定は dry-run (集計・分類のみ・Notion 書き込みゼロ)、レポート DB への反映を含む `--apply` は dry-run と二段確認完了を示す `--verified` を必須にする。
**出力**: 8 列レポートテーブル (title=取引先名・列7=テキスト説明・金額税抜) + 判定内訳サマリ (継続発行/新規・年→月切替/対象外/発行漏れ候補の件数)。
**完了条件**: dry-run で分類内訳を確認 (二段確認) し、`--apply --verified` で単一恒久レポート DB へ 8 列行が冪等 upsert され、別月/以前 run 行が履歴として残り、続けて R5 (C07) が対象月の請求書確認シート行を月別 DB『請求書確認シートYYMM』へ完全移行 (検証成功行だけ元シートから削除=月次ロールオーバー) した状態。

> **⚠️ AI・開発者向け — 分類/照合/冪等 upsert は実装済み・自作禁止**: 前月↔今月の状態遷移分類・事情コメント生成・単一恒久 DB への冪等 upsert は**完成・テスト済み**。**自前の比較スクリプトを書いたり、分類 (classify/compare/period_diff 相当) を新規実装したり、判定を `TODO(human)` で人間に書かせたりしてはならない**。正本は次の 3 実体:
> - **`scripts/mfk_period_report.py`** (C03・前月↔今月分類エンジン): 既存 `lib/mfk_reconcile.py` の per-月 verdict を入力に取り、状態遷移だけを分類する薄い差分エンジン。終了根拠の一次情報源は既存 `mfk_reconcile.has_end_basis`→verdict `SUPPRESS_ENDED` であり、自由文を再パースしない。
> - **`lib/mfk_reconcile.py`** (per-月 verdict の供給源・突合キー正規化 `normalize`/`extract_names`)。
> - **`scripts/notion_report_sink.py`** (C04・Design D sink): 出力先 DB 解決 + 非破壊冪等 upsert。DB 生成/列型写像は `skills/run-mf-invoice-db-setup/scripts/build_notion_db.py` を再利用する。
>
> - **`scripts/mfk_verdict_export.py`** (C05・R1 決定論 producer): `reconcile()` を当月/先月で回し全 row (GAP/SUPPRESS 含む) + orphans を carrier 込みで `curr-verdicts`/`prev-verdicts` へ無損失直列化する。LLM 手動直列化 (発行済み社の当月行を落とし curr=None を生む構造的主因) を置換する。R1 はこの producer を呼ぶだけで verdict を手組みしない。
> - **`scripts/mfk_collect_status.py`** (C01・発行後 status 収集 SSOT): `collect_mf` の `/billings/qualified` 取得を `invoice_issued` 限定でなく発行後 status (`account_transfer_notified` 等) も含める client 側フィルタの判定源。
> - **`scripts/mfk_sheet_archive.py` + `lib/notion_sheet_archive.py`** (C07・月次アーカイブ&ロールオーバー): 対象月の請求書確認シート行を月別 DB へ完全移行し検証後に元行削除する正本。R4 後段で自動連鎖する。**シートのアーカイブ/月別 DB への移行/正本削除を自作しない** (verify-then-delete と冪等を機械化済み)。verdict の解釈・照合はせず行の move/verify/delete のみ (分類は C03 が正本)。
>
> 自然文で頼まれたら新規実装せず `/run-mf-invoice-report --target YYMM` を **dry-run → 二段確認 (`mfk-report-verifier`) → `--apply --verified`** の順で実行する。**機械強制**: `hooks/guard-mfk-no-reinvent.py` (PreToolUse) が、正本以外への状態遷移分類の再実装 (`def compare_*`/`def period_diff`/`def classify_*` 等) と本ドメインでの `TODO(human)` 書き込みを exit 2 で遮断する (prose 指示が出力スタイルに上書きされても効く機械層)。

## End-to-End Flow

```
[1 collect]     対象月を決定 (今月=直近締め済み請求対象月・先月=その1ヶ月前) →
                前月/今月/lookback の全取引先 MF発行実績を参照専用GET (lib/mfk_api.py)・pagination trace を fetch_trace へ記録
                (collect_mf は発行後 status=account_transfer_notified 等も収集=C01・mfk_collect_status.is_issued_billing) →
                per-月 verdict は決定論 producer mfk_verdict_export.py (C05) が reconcile() の全 row (GAP/SUPPRESS 含む)+orphans を
                carrier 込みで無損失直列化 (LLM 手組みでなく=curr=None を出さない構造的主因の根治) →
                MF顧客ID (無ければ取引先名) ×商品で状態遷移を抽出し (ID 第一キーで取引先名 drift の分裂を根治=要因A)、差分に現れた該当取引先 (STATE_NEW 含む) のみ 12ヶ月分の発行履歴を追加取得 →
                請求確認シート由来の契約終了月も収集 →
                curr-verdicts / prev-verdicts / lookback-12mo / contract-end / fetch_trace の JSON 入力を組む
[2 fetch-audit] mfk_fetch_audit.py (C06) が fetch_trace を監査し fetch fidelity report を出力 (取得の完全性ゲート・MF実績起点判定の前提) →
                exit0=OK / exit1=当月or先月 fetch NG→fail-closed (漏れ確認レポートを emit しない) / exit3=lookback 部分欠損→該当行を要確認へ降格
[3 classify]    mfk_period_report.py (C03) で前月↔今月の状態遷移をイレギュラー分類し各行の事情コメント生成
                (C06 の fidelity report を `--fidelity-report` で必須受領し fail-closed/要確認降格を適用・金額は MF実発行額 actual_amount 優先=D3)
                → 分類済みレポート行 JSON (取引先/漏れチェック/商品/先月金額/今月金額/比較/コメント)
[4 verify]      mfk-report-verifier sub-agent (context:fork) で独立contextの二段確認。
                真の発行漏れを『問題ない』と誤って隠していないかを検証 (誤って対象外化した候補を差し戻す)
[5 render]      notion_report_sink.py (C04・Design D) でトグル内の単一恒久レポート DB へ非破壊冪等upsert
                (出力先解決=トグル内DB優先・対象月列で複数月を非破壊保持・同月のみ上書き・deleted常時0)
[6 archive]     mfk_sheet_archive.py (C07) で対象月の請求書確認シート行を月別 DB『請求書確認シートYYMM』へ完全移行し
                検証後に元シートから削除 (月次ロールオーバー・R4 が --apply --verified で成功した後に常に自動連鎖)
                (シートと同じ親ページ配下へ find-or-create・全プロパティ写像・元ページID冪等・verify-then-delete・削除=archive可逆)
                ↑ MF APIは全GET / 変更系は hook(guard-mfk-readonly.py)で遮断。分類再発明は hook(guard-mfk-no-reinvent.py)で遮断
```

詳細は `workflow-manifest.json`、責務は `prompts/R1-R4`。dry-run (分類のみ) と `--apply` (Notion 書き込み) を分離し、分類内訳を確認してから適用することで二段確認を標準フローで要求する。C03/C04/C06 は決定論 script (fetch-audit=C06 は収集 R1 の取得完全性ゲート)、収集 (R1)→fetch fidelity 監査→分類呼出→二段確認→冪等描画のオーケストレーションが本 skill の責務。

> **exit1 (C05 producer の carrier 検証違反) の対処**: `mfk_verdict_export.py` は全 row の carrier (`actual_amount`/`reliable_issued`/`supply_state`/`canceled_at`) 欠落を直列化前に fail-closed 検証し、1 行でも欠落があれば exit 1 で curr/prev-verdicts を一切書き出さない (過少報告=真の漏れを隠す退行を止める意図的トレードオフ)。通常は `reconcile()` の `_new_row`/`_orphan_to_row` が全 row へ carrier 既定値を設定するため exit1 は起きないが、発生時は「レポート全体が 1 行の欠落で停止する」all-or-nothing 挙動になる。対処: stderr の `schema 違反` メッセージが指す行 (verdict) を手掛かりに、`lib/mfk_reconcile.py` 側の carrier 付与漏れ (find_mf_match を経ない新経路の追加等) を調査する。原因行を特定・修正するまで当該月のレポートは出せない (安全側)。

## DB ライフサイクル (単一恒久 DB・作り直さない・履歴保全)

月次運用では **Design D + 明示 pin (要件2)**: 出力先を**指定見出し (`report_toggle_block`・トグル見出しでもプレーン見出し2でも可) に紐づく単一の恒久レポート DB** (または config `notion.report_database_id` で pin した DB) に一本化し、そこへ upsert で更新する。C04 sink は **(0) config `report_database_id` が set なら構造同定を経ずその DB を直接更新対象にし (明示 pin・step0・出力先を指定先へ確実に着地=phantom 回避の核)**、未 pin なら (1) 指定見出しがトグルで配下に持つ report DB、無ければ (2) プレーン見出しの**直下**(ページ兄弟・次セクション見出しの手前まで=見出しの下に置いた DB を重複と区別して同定)、無ければ (3) 親ページ (`report_parent_page`) 直下の title が『請求漏れ比較レポート』で始まる既存 report DB、どれも無く **`--allow-create` 明示時のみ** (4) 見出しの下 (ページ直下) へ新規作成、の順に出力先 DB を解決する (`db_location`=pinned/in-block/under-heading/page/page-created・未発見かつ非作成は none で開示)。**明示 pin なし かつ 既存 DB 未発見 かつ `--allow-create` なしのときは phantom を作らず fail-closed (exit 2) で停止**する (構造同定のズレで別 DB=phantom を作り、書き込みチェックが本来 DB に反映されない症状の根治=要件2)。pin 値は DB id でもビュー/DB の URL でも可 (path 側の 32hex を DB id として抽出)、不正 id なら `_ensure_db_schema` の GET が例外を投げ呼出側が exit 2 で停止する。**(1)(2) の指定トグル/見出しはこのレポート専用の器ゆえ、配下 DB は表示名に依存せず構造的位置で採用する** (ユーザーが『請求漏れ確認レポート』等どんな名前で手作りしても既存として更新=title 前方一致は同点解消/後方互換のヒントに留め、複数併存時のみ prefix 一致→先頭で決定論選択し stderr へ警告)。(3) の親ページ直下だけは無関係 DB が同居しうるので title 前方一致で限定する。**Notion API は database を block_id (トグル) 親で『作成』できないが、ユーザーが Notion UI でトグル内に作った DB の『更新』(行 upsert・列 PATCH) はできる**ため、トグル内 DB をそのまま更新できる。単一 DB に複数月を保持するため **`対象月` 列 (YYYY-MM)** で月を区別し、行同定キー (対象月, 取引先名, 商品名) で同月の再実行のみ上書き・別月/以前行は非破壊保持する。対象月列が無い旧 DB には `_ensure_db_schema` が PATCH で対象月列を後付けし、title 列名が『取引先名』でなく Notion 既定の『名前』等でも実名を検出して行を書く (非破壊)。新規作成 DB はページ直下に落ちるため、**初回のみ Notion UI で指定見出しの下へドラッグ移動**すると以後 in-block/under-heading で自動更新される。出力先 ID は tenant overlay/ローカル config が供給し、配布既定は空のまま fail-closed とする。

**履歴が消えない設計**: 単一 DB に `対象月` 列で複数月を保持する。行同定キーは **(対象月, 取引先名, 商品名)** で、別月の行は別キーゆえ非破壊共存し、同月内の再実行のみ 1 行へ収束 (重複行 0・日々追加)。**非破壊マージ**: 以前の run で書いた行も別月の行も今回入力に無くても削除しない (`deleted` 常時 0・clear-then-insert でない)。手動追記運用は無い前提ゆえ frozen 列は設けない。

> **列順 SSOT (固定 8 列)**: [取引先名(title=ページ名), 対象月(rich_text), 漏れチェック(checkbox: 正常=✓/要対応=☐), 商品名(rich_text), 先月の金額(number/yen), 今月の金額(number/yen), 先月と今月の比較(rich_text=テキスト説明), コメント(rich_text)]。取引先名=title を先頭に置き Notion の title 最左固定と定義順を一致させる (定義順=実表示順)。金額は税抜。列型写像は build_notion_db を再利用。固定 8 列に契約ID 列は無いため、DB 内の 1 行は (対象月, 取引先名, 商品名) で回収され、契約ID は入力同定用メタとして主キーに含むが persist しない (C04 の `_stored_key` が SSOT)。

## boundary (責務境界)

- **入力**: MF掛け払い実績 (参照専用 GET) + 既存 `mfk_reconcile` の per-月 verdict + 請求確認シート (契約終了月)。
- **出力**: 指定見出しに紐づく単一恒久レポート DB の冪等上書き + (R5) 月別 DB『請求書確認シートYYMM』への対象月シート行の完全移行 + 正本シートからの対象月行削除 (archive)。
- **MF への書き込みはしない** (GET のみ・変更系は hook `guard-mfk-readonly.py` で遮断)。R5 の書込先は Notion のみ (MF は触らない)。
- イレギュラー分類の実体は **C03 エンジン**・出力先 DB 解決/冪等 upsert は **C04 sink**・シート月次アーカイブ&ロールオーバーは **C07 engine** (`mfk_sheet_archive.py`) に委譲し、本 skill は収集→分類呼出→二段確認→冪等描画→月次アーカイブの**オーケストレーションに徹する**。
- **既存 reconcile/check スキルの再設計はしない** (単月照合=`run-mf-invoice-reconcile`、前月↔今月比較=本 skill と役割分離)。R5 は正本シート (`sheet_db_id`) を書き換える唯一の経路だが、対象月行の月別 DB への切り出し (move) に限り、reconcile が使う writeback 列 (判定/AI確認/確認ポイント) の意味論には踏み込まない。

## ゴールシーク実行

### ゴール (Goal)
前月↔今月の MF 発行状況を突合した結果——継続発行 (全行)・新規/年→月切替・対象外・発行漏れ候補——が 8 列レポート行として単一恒久レポート DB へ非破壊冪等 upsert され、正常イレギュラーには事情コメントが焼かれ、独立 context の sub-agent で「真の発行漏れを問題ないと隠していないか」を確認した上で、分類不能な差分だけが漏れチェック=要対応として残った状態。

### 目的・背景 (Why)
単月照合では拾えない前月↔今月の発行増減を一望し、正常イレギュラー (年契約期間内/トライアル完了/契約終了) と真の漏れを分離して**なぜ問題ないかをコメント説明**することで、経理の請求漏れ確認を最新状態で回すため。誤って正常化して真の漏れを隠す事故を防ぐため、候補は dry-run と独立 context の二段で確認する。

### 責務サマリと完了条件の正本

各責務の**完了条件の詳細は `prompts/Rn` の L5.3 完了チェックリストを正本 (SSOT)** とする (片側更新ドリフトを避けるため SKILL 側で再定義しない)。本節は俯瞰用の責務サマリのみ示す。

- **R1 collect** (`prompts/R1-collect.md`): 対象月を決定し前月/今月の全取引先 MF実績 (参照専用 GET) と per-月 verdict を収集、差分該当取引先のみ 12 ヶ月遡り、契約終了月を集め C03 入力 JSON を組む。
- **R2 classify** (`prompts/R2-classify.md`): `mfk_period_report.py` で状態遷移を分類し事情コメントを生成する (既存 verdict を消費・再パースしない)。
- **R3 verify** (`prompts/R3-verify.md`): sub-agent `mfk-report-verifier` が独立 context で「真の発行漏れを問題ないと隠していないか」を二段確認する。
- **R4 render** (`prompts/R4-render.md`): `notion_report_sink.py` で単一恒久レポート DB へ 8 列行を非破壊冪等 upsert する (既存 DB 優先解決・日々追加・別月/以前行保全)。
- **R5 archive** (`prompts/R5-archive.md`): `mfk_sheet_archive.py` (C07) で対象月の請求書確認シート行を月別 DB『請求書確認シートYYMM』へ完全移行し検証成功行だけ元シートから削除する月次ロールオーバー。R4 が `--apply --verified` で成功した後に**常に自動連鎖**し、レポート dry-run では archive も dry-run (移行プレビューのみ)。冪等 (元ページID)・verify-then-delete (不一致は温存)・削除=archive (可逆) で正本削除を三重に安全化する。

### 完了チェックリスト (Checklist)
> 各責務の停止条件詳細は `prompts/Rn` の L5.3 を正本 (SSOT) とする。本節は俯瞰用の二値チェックのみ。
- [ ] 対象月 (今月=直近締め済み請求対象月・先月=その1ヶ月前) を決定し、前月/今月の MF実績と per-月 verdict を収集した (R1)
- [ ] 差分に現れた該当取引先のみ 12 ヶ月遡りの発行履歴と契約終了月を集めた (R1・全件遡らない=API 負荷最小化)
- [ ] `mfk_period_report.py` で状態遷移を分類し継続発行を全行 emit・正常イレギュラーに事情コメントを焼いた (R2)
- [ ] sub-agent `mfk-report-verifier` が独立 context で真の発行漏れを隠していないか二段確認した (R3)
- [ ] `--apply --verified` で単一恒久レポート DB へ 8 列行を非破壊冪等 upsert した (重複行 0・二重 DB 0・deleted 0・R4)
- [ ] 月跨ぎでは対象月列で別月行が同一 DB に共存し、別月/以前 run 行が履歴として残った (R4)
- [ ] 出力先 report DB の解決が要件2 に従った (--apply 時): config `report_database_id` の明示 pin があればその DB へ直接 upsert し、pin なし かつ 既存 report DB 未発見時は phantom を作らず fail-closed (exit 2) で差し戻した (新規作成は `--allow-create` 明示時のみ・その際 `report_parent_page` 未解決なら exit 2)
- [ ] R4 の `--apply --verified` 成功後に mfk_sheet_archive.py を自動連鎖し、対象月の請求書確認シート行を月別 DB『請求書確認シートYYMM』へ完全移行 (元ページID冪等・全プロパティ写像) して検証成功行だけ元シートから削除した (R5・検証不一致行は温存・削除=archive 可逆・レポート dry-run では archive も dry-run)

### ゴールシークループ
1. `--target` を決定し R1 で MF実績 + per-月 verdict + 12 ヶ月遡り + 契約終了月を収集 (`R1`)。
2. 既定 dry-run で `mfk_period_report.py` を回し分類内訳を得る (`R2`)。
3. sub-agent で二段確認し、正常化しすぎて隠れた真の漏れを差し戻す (`R3`)。
4. `--apply --verified` で単一恒久レポート DB へ非破壊冪等 upsert (`R4`)。別月/以前行は保全。
5. R4 が `--apply --verified` で成功したら `mfk_sheet_archive.py --target <YYMM> --apply --verified` を自動連鎖し、対象月の請求書確認シート行を月別 DB へ完全移行→検証→検証成功行だけ元シート削除 (`R5`)。レポート dry-run なら R5 も dry-run で移行プレビューのみ。
6. 全 checklist 充足で完了。出力先は config `report_database_id` の明示 pin (step0) を最優先し、pin なし かつ 既存 DB 未発見時は phantom を作らず fail-closed で差し戻す (新規作成は `--allow-create` opt-in・その際 `report_parent_page` 未解決も fail-closed)。

## Key Rules

1. **参照専用 (二層で抑止)**: 第1層=`hooks/guard-mfk-readonly.py` (PreToolUse) が Bash 経由の MF 変更系を遮断。第2層=`lib/mfk_api.py` は GET 専用で POST/PATCH/DELETE 関数を構造的に持たない。MF へは一切書き込まない。
2. **分類再発明の遮断**: `hooks/guard-mfk-no-reinvent.py` が正本 (`mfk_period_report.py`/`mfk_reconcile.py`/`reconcile_invoices.py`) 以外への状態遷移分類関数 (`compare`/`period_diff`/`classify_*` 語幹) の再実装と `TODO(human)` を exit 2 で遮断する。分類は C03 が正本。
3. **対象月は直近締め済み**: 今月=実行日カレンダー月の前月 (直近締め済み請求対象月)、先月はその 1 ヶ月前。MF の月帰属は `transaction.date` (取引日・月末締め) 軸で、C03 の `resolve_target_months` が導出する。
4. **全行 emit で全請求書一覧**: 継続発行 (今月あり×前月あり) も漏れチェック=正常として全行 emit する。今月なし×前月なし (STATE_NONE) は原則 非 emit (正常抑制 SUPPRESS_*/元々請求なし) だが、**継続漏れは 2 系統を要対応として emit** し脱落させない: (a) 今月 verdict=GAP の継続漏れ、(b) 支払サイクル=月払いのアクティブ契約が先月も今月も未発行 (契約完了/年契約/対象外/トライアル/審査中 のいずれでもない=要因C・`_classify_both_absent`)。真の発行漏れ (単月遷移の漏れ + 継続漏れ) だけを漏れチェック=要対応に残す。
5. **正常事情は既存 verdict を一次源に消費 (再パース禁止)**: 契約完了=`SUPPRESS_ENDED`、年契約期間内=`SUPPRESS_ANNUAL`/`MATCH_ANNUAL` を一次源にし、12 ヶ月遡りは根拠コメント補強に限定 (既存判定を上書きしない)。トライアル完了は canon 前の生商品名/MF 明細 desc の『トライアル』信号で判定。**根拠なき終了月** (`REVIEW_ENDED_NO_BASIS`) は抑制せず発行漏れ候補に残す (漏れ隠蔽防止の既存安全弁を保全)。
6. **12 ヶ月遡りは差分該当取引先のみ**: 前月↔今月の差分に現れた取引先だけ 12 ヶ月履歴を追加取得する (全件遡らない=API 負荷最小化)。
7. **二段確認 (dry-run + `--verified` が物理境界・機械強制)**: 既定は dry-run (分類のみ・書き込みゼロ)。レポート DB 反映を含む `--apply` は `--verified` 明示時だけ通す — これは prose の約束でなく `notion_report_sink.py` が `--apply` かつ `--verified` でなければ書込を拒否し exit 2 する**機械ゲート**である (MEMORY『保証要件は機械層で担保』)。分類内訳を dry-run で確認し、sub-agent の二段確認後にだけ `--apply --verified` を使う (誤投入防止)。
8. **単一恒久 DB を作り直さない (Design D + 明示 pin・要件2)**: 出力先は config `report_database_id` の**明示 pin (step0) を最優先**で解決し (構造同定を経ず直接更新=phantom 回避)、未 pin ならトグル内の report DB→見出しの下=ページ直下→親ページ直下の既存 DB の順で構造同定する。そこへ `対象月` 列付きで複数月を非破壊 upsert する (同月のみ上書き・別月/以前行は保全)。**明示 pin なし かつ 既存 DB が皆無のときは phantom を作らず fail-closed (exit 2)**・新規作成は初回セットアップ用の `--allow-create` 明示時だけ (見出しの下)。
9. **非破壊冪等 upsert**: 同月再実行は入力同定 {取引先 × 契約ID × 商品} と stored key (対象月, 取引先名, 商品名) で同一行を 1 行へ収束 (重複行 0)。固定 8 列に契約IDは永続化しないため、契約ID違いは要対応優先で collapse し `collapsed_multi_contract` に計上する。以前 run の行も別月行も今回入力に無くても削除しない (`deleted` 常時 0)。
10. **列順は固定 SSOT (定義順=実表示順)**: [取引先名, 対象月, 漏れチェック, 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] を左→右順で固定。C04 の `COLUMN_ORDER` が正本。取引先名=title (=各行=ページ名)・対象月=rich_text・漏れチェック=checkbox (正常=✓/要対応=☐)・列7=テキスト説明・金額は税抜。**Notion table view は title 列を最左に固定描画する**ため、title (取引先名) を `COLUMN_ORDER` 先頭に定義することで定義順と実描画順を一致させている (列定義順 SSOT がそのまま実表示順=設定通り・以前あった「定義順≠実表示順」の乖離を解消)。
11. **月次アーカイブ&ロールオーバーは R4 の後段で常に自動連鎖 (C07・R5)**: R4 が `--apply --verified` でレポート DB へ upsert に成功したら、続けて `mfk_sheet_archive.py --target <YYMM> --apply --verified` を**常に自動**で走らせ、対象月 (`年月` select==YYMM) の請求書確認シート (`sheet_db_id`) 行を、シートと同じ親ページ配下の月別 DB『請求書確認シートYYMM』へ**全プロパティ完全移行** (元ページID冪等・title 保持・API 非対応型は rich_text 降格で値温存・長文は chunk 全文保持) し、写像先の読み戻し検証 (全写像列 plain-text 一致) に通った行だけ元シートを Notion archive (in_trash・30日復元可) する。**正本削除を三重に安全化**する: (a) `--apply` に `--verified` を機械層で必須 (未指定は exit 2・正本からの誤削除を物理拒否)、(b) verify-then-delete=もれなく移行できた行だけ切り出し不一致行は温存 (fail-closed)、(c) 削除=archive で可逆。冪等ゆえ再実行は重複行 0・archive 済み行は `年月` query 対象外で no-op (crash-safe)。レポートが dry-run のときは R5 も dry-run で移行プレビューのみ (書き込みゼロ)。本 engine は行の move/verify/delete のみで verdict を解釈・照合せず、状態遷移分類は C03 が正本 (guard-mfk-no-reinvent との整合)。

## Gotchas

1. 出力先 (`notion.report_toggle_block` / `report_parent_page`・任意で `report_database_id`) は tenant overlay またはローカル `.mf-kessai-config.json` で与える。配布既定は全 ID を空にし、tenant 未選択の書き込みを fail-closed で防ぐ。**Design D + 明示 pin (要件2)**: sink は config `report_database_id` が set ならその DB を構造同定を経ず直接更新し (明示 pin・step0・phantom 回避)、未 pin ならトグル内 report DB→見出しの下=ページ直下の既存 DB を構造同定する。**明示 pin なし かつ 既存 DB 未発見時は phantom を作らず fail-closed (exit 2)**・新規作成は初回セットアップ用の `--allow-create` 明示時のみ (見出しの下)。API は database を block_id (トグル) 親で作成できないが、UI 作成のトグル内 DB の更新はできる。別ワークスペース/別ページへ出す・あるいは毎回同じ表へ確実に反映する場合は `.mf-kessai-config.json` (gitignore) で `notion.report_database_id` にその DB の id (またはリンク) を設定する。`report_parent_page` を空にすると新規作成の `--apply` 時に fail-closed (exit 2)。dry-run は書き込みなしで完走する。
2. MF APIキーと Notion トークンは別 Keychain entry (`mfkessai-api-key.<keychain-prefix>` / `notion-api-key.<keychain-prefix>`、いずれも account=<keychain-prefix>)。
3. **database は block_id (トグル) 親で『作成』できない** (POST /databases に block_id 親は 400)。ただし UI で作られたトグル内 DB の『更新』(行 upsert・列 PATCH) はできる。ゆえに Design D は新規作成のみ見出しの下 (ページ直下) に落とし、以後の更新はトグル内 DB へ行う。折り返し (wrap)/列幅はビュー format 設定で API 非公開ゆえ `placement.view_format_note` で UI 手順を開示する。
4. 固定 8 列 (取引先名/対象月/漏れチェック/商品名/先月の金額/今月の金額/先月と今月の比較/コメント) に契約ID 列は無い。DB 内の 1 行は (対象月, 取引先名, 商品名) で識別され、契約ID は入力同定用メタ (persist しない=既存ページから回収できない)。C03 は同一取引先・同一商品の複数契約を契約ID で別行に分離するが、C04 は契約ID列が無いため (対象月, 取引先名, 商品名) で 1 行に収束する。この収束時は **要対応 (発行漏れ候補) を正常が上書きしない safe guard** で漏れ隠蔽 (false-negative) を防ぎ、多契約 collapse 件数を stdout の `collapsed_multi_contract` に計上する (常態化すれば契約ID列追加への移行トリガ)。「多契約×同一商品は稀」という前提で 8 列固定を優先した設計判断。safe guard は **run 内 collapse だけでなく cross-run 更新にも対称に効く**: 前 run で立てた要対応行を次 run の正常が無条件上書きせず要対応を保持し、正常化した旨をコメントへ注記する。同 severity の要対応×要対応 collapse は両者のコメントを連結マージして片方の漏れ詳細を失わない。
5. カタカナが NFD (macOS/MF API 由来) でリテラル(NFC)と != になるため突合キーは `mfk_reconcile.normalize` (NFKC) を再利用する (自作正規化を発明しない)。
6. per-月 verdict は既存 reconcile engine の出力を消費する。C03 は verdict を再照合・再パースしないため、上流の verdict が誤っていれば分類も従う (真の漏れ判定は R3 の二段確認で担保)。
7. **レポート DB は機械専有 (machine-owned)**: C04 sink が冪等上書きする出力先で、経理の手動トリアージ (人間対応済み/確認メモ) は本 DB でなく単月照合の DB2 (`run-mf-invoice-reconcile` の月次チェック DB) で行う。本 DB に人が手で追記した checkbox/コメントは翌日の非破壊 upsert で機械が上書きしうる (frozen 列を持たない=手動追記運用が無い前提)。経理は本 DB を「読んで確認する」用途で使い、対応記録は reconcile DB2 側に残す。
8. **今月の金額/先月の金額 の意味 (D3・MF実発行額を常時表示)**: `今月の金額`/`先月の金額` は **MF 実発行額 (actual_amount) を常時表示**する — C05 (`mfk_actuals`・MF実績SSOT) が MF実績から焼いた carrier を C03 の `_amount_of` が**最優先**する (以前の「契約の期待単価を優先して載せる」旧仕様を D3 amount-gate 根治で**反転**した)。契約の期待額と実額が異なる場合でも**実額を表示したうえで、金額差はコメント/『先月と今月の比較』列で開示**する (期待額で実額を上書きしない)。**取消/供給なし (`supply_state`≠active) の行は金額列を空 (None) にし、取消前の額を出さない**。actual_amount carrier を持たない legacy 行や active だが実額欠落のときのみ期待額 (現行単価) へ fail-soft する。厳密な単月の実発行額照合は引き続き単月 `run-mf-invoice-reconcile` が担う。
9. **exit 1 は失敗でない**: `mfk_period_report.py` は発行漏れ候補 (要対応) が 1 件でもあると exit 1 を返す (正常な検出結果)。CI/オーケストレーションは fatal を exit 2 のみとし exit 1 を失敗扱いしないこと (workflow-manifest の classify phase に明記)。
10. **折り返し (wrap) は API で設定できない=UI で一度だけ**: 全列の折り返し表示 (wrap) は Notion の**ビュー表示設定**であって**プロパティ (スキーマ) 設定ではない**。Notion 公開 API (2022-06-28) はビューの format (折り返し・列幅・列順・列の固定) を一切操作できない (列順は DB 作成時の properties 定義順で既定ビューへ反映できるが、wrap/幅は不能)。全内容を折り返すには、Notion UI で当該 report DB ビューの『**…**』メニュー →『**すべての列を折り返す (Wrap all columns)**』を一度トグルする (以後そのビューに永続)。C04 はこの制約と手順を出力の `placement.view_format_note` で毎回開示する (列順・DB 配置と同じ「API 能力境界」の正直な開示)。
11. **前月なし今月あり (新規/年→月切替) は 12ヶ月ルックバックで裏付ける**: 前月なし今月ありは「12ヶ月前の年契約一括→月額自動切替」の可能性が高い (C3)。この裏付けデータ源は **MF 実績の 12ヶ月履歴 (`transaction.date`) であり請求確認シートではない** — シートの開始月 (例 2605) は遡りの可否と無関係。`--lookback-12mo` 未指定のまま新規行を分類すると C03 は各行コメントに『⚠️ 12ヶ月ルックバック未実行→年→月切替か真の新規か未確認』を焼き stderr へ警告する (silent に『新規発行』と断定しない)。MF 実績自体が 12ヶ月前まで無い口座のときのみ、源を「MF実績が YYMM 開始のため」と正しく特定して省略する (シートと取り違えない)。
12. **月跨ぎ突合は MF顧客ID が第一キー (取引先名 drift の分裂を根治・要因A)**: `compare_periods` は先月↔今月の行を **① MF顧客ID (`MF顧客ID`・sheet_to_master が C02 `mfk_customer_id_resolve` で解決し契約→verdict 行へ carry) → ② 取引先名×商品** の 2 pass で突合する。MF顧客ID は MF が採番する永続識別子で月をまたいで安定するため、取引先名が月間で表記ずれ (日本語⇄英語・社名変更・NFKC で吸収しきれない揺れ) しても先月/今月が STOPPED+NEW に分裂せず 1 件の継続に収束する (=「前回取れたのに今回取れない」の根治)。片月だけ明示 ID を持つ同名契約は名前→ID bridge で継承する。代理店 (同一 MF顧客ID×同一商品で複数エンドクライアント) は ID キーにもエンドクライアント名/契約ID の disambiguation を重ねて幻の collapse を防ぐ。ID を解決できない行だけ従来の取引先名×商品キーへ fallback する (=IDが 0 件でも従来動作を割らない)。
13. **新規の年契約開始は支払サイクルで正常☑ (要因B)**: 先月なし今月あり (STATE_NEW) で、当月 verdict が MATCH_ANNUAL/SUPPRESS_ANNUAL でなくても **契約の支払サイクルが年契約系 (`年間払い`/`年間一括更新`) なら『年契約開始=今月一括発行済み=正常☑』** と判定する (12ヶ月履歴なしの真の初年度でも要確認☐へ誤爆しない・シート推定の支払サイクルを一次シグナルに DB1 支払サイクル未配線を補う)。支払サイクル=月払いの新規は本分岐に来ず従来どおり D1 で 12ヶ月裏付けを要求する (年→月切替の裏付けなしは要対応のまま)。
14. **先月も今月も未発行の月払いアクティブ契約は要対応で surface (要因C)**: STATE_NONE (両月未発行) は原則 非 emit だが、**支払サイクル=月払い かつ 契約完了 (終了 verdict/ステータス終了・SUPPRESS_ENDED・MATCH_ENDED_FINAL) でも年契約非請求月でも対象外抑制 (SUPPRESS_*) でもトライアルでも審査中 (REVIEW_*) でもない**行は『契約完了の確認が取れず 2ヶ月以上請求書が発行されていない=継続発行漏れの可能性・要対応☐』として可視化する (`_classify_both_absent`)。完了済みなら契約終了月をシートへ記入すると正常化する。月払い以外 (年契約/従量/分割/保留=支払サイクル不明) は積極シグナルなしゆえ surface しない (過剰報告回避)。
15. **R5 アーカイブは正本シートを削る=毎回レポート `--apply --verified` が当月分を切り出す (設計選択)**: R4 成功後に R5 が自動で対象月シート行を月別 DB へ移し正本から archive するため、レポート `--apply --verified` を回すたびに当月分が正本シートから消える (=ロールオーバー運用)。これは意図した設計 (締め済み月を月別アーカイブへ切り出し正本を軽く保つ) であり、`--verified` ゲート + verify-then-delete + archive 可逆性で誤削除を防ぐ。当月内の reconcile 照合 (`run-mf-invoice-reconcile`) はレポート `--apply` 前に済ませる運用を前提にする (レポート `--apply` は締めの最終工程)。写像先 DB は Notion API 制約で page_id 親のみ作成可のため、シート親が page でない (ワークスペース直下) ワークスペースでは `notion.archive_parent_page` か `report_parent_page` を親 fallback に用いる。`元ページID` 列は冪等/crash-safe 再開のため写像先へ足す provenance で、元シートには足さない (正本スキーマ不変)。

## Additional Resources

- `workflow-manifest.json` — collect/classify/verify/render/archive の Step 定義 + hook guard
- `$CLAUDE_PLUGIN_ROOT/scripts/mfk_period_report.py` — 前月↔今月分類エンジン (C03・既存 per-月 verdict を消費する薄い差分エンジン・network なし)
- `$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py` — 単一恒久レポート DB sink (C04・出力先 DB 解決 + 非破壊冪等 upsert)
- `$CLAUDE_PLUGIN_ROOT/scripts/mfk_sheet_archive.py` — 請求書確認シート月次アーカイブ&ロールオーバー CLI (C07・対象月行を月別 DB へ完全移行し検証後に元行削除・config/token/親解決 + 二段確認ゲート)
- `$CLAUDE_PLUGIN_ROOT/lib/notion_sheet_archive.py` — アーカイブ engine (対象月抽出/スキーマ写像/元ページID冪等 upsert/読み戻し検証/archive の純関数・req 注入でオフライン可能)
- `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` — per-月 verdict 供給源 + 突合キー正規化 (normalize/extract_names)
- `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` — MF掛け払い GET 専用クライアント
- `$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py` — DB 生成/列型写像 (C04 が再利用)
- `prompts/R1-collect.md`〜`R4-render.md` — 責務プロンプト (7 層構造)
- `$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-readonly.py` — 参照専用ガード / `guard-mfk-no-reinvent.py` — 分類再発明ガード
- `$CLAUDE_PLUGIN_ROOT/agents/mfk-report-verifier.md` — 二段確認 sub-agent (責務本文 SSOT=prompts/R3-verify.md)
