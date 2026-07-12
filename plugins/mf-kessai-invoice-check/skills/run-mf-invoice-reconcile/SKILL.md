---
name: run-mf-invoice-reconcile
description: 請求確認シートを基準にMF掛け払いの発行漏れと契約マスタ未登録を双方向照合したいとき、月次で発行網羅性を検証し記録を残したいときに使う。
disable-model-invocation: false  # 自然文「請求確認シートの内容がMFに反映されてるか確認して」で自動起動させる。READMEが約束する自然文起動と設定を整合させるため true→false。書込安全は既定 dry-run + --apply に --verified を要求するゲートで担保 (company-master/run-company-master-build と同型: external-mutation でも model-invocable)。
user-invocable: true
argument-hint: "[--target YYMM] [--apply --verified] [--steps collect,sync-master,reconcile,sink]"
arguments: [target, apply, verified, steps]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-26
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-06-26
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-collect.md
  - prompts/R2-reconcile.md
  - prompts/R3-verify.md
  - prompts/R4-sink.md
schema_refs:
  - schemas/reconcile-result.schema.json
  - schemas/verdict-mapping.json
  - schemas/contract-master-db.schema.json
  - schemas/monthly-check-db.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 双方向照合が正しく分類されることを test_mfk_reconcile で機械検証できる——順方向(当月シート由来の期待契約 − MF実績 = 発行漏れGAP/金額一致MATCH)と逆方向(MF実績 − 全月契約 = orphan要マスタ登録)を金額+名前トークン(NFKC正規化・取引先境界で供給分割)で突合し、presence-based(該当品目が1件でも反映で発行漏れにはしない・数量差はREVIEW_QTY_MISMATCHへ降格)と年間前払い期間中の抑制が成立する。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 判定語彙・AI確認・履歴非破壊性が機構強制されることを test_verdict_mapping_parity と test_notion_reconcile_sink で機械検証できる——engine が emit する内部 verdict が verdict-mapping.json(日本語ラベルSSOT)の部分集合(emit ⊆ mappings)で語彙ドリフトせず、DB2 sink が ai_check 由来の『AI確認済み』を機械更新し、当月(対象年月)のみ更新・過去月を構造的に不可侵・人間対応済み=true の行を凍結(skip)する非破壊 upsert である。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: スキル全体がユーザ目的(入力は請求確認シートのみ・契約マスタ/月次チェックは Claude Code が自動移管生成・発行漏れと要マスタ登録の双方向検知・確認済み履歴の翌月保全・MF参照専用の保証)を最適に反映し、collect→reconcile→verify(dry-run二段確認)→sink と DB1契約マスタ/DB2月次チェックの二層分離の責務分割が目的に対し過不足ないこと。
      verify_by: elegant-review
---

# run-mf-invoice-reconcile

## Purpose & Output Contract

担当者が「請求確認シート」(年月/取引先/商品/確認内容/契約開始日/契約終了月 を 1 明細=1 行で入力) に記録した対象月の各行を基準に、MF掛け払いの対象月取引実績 (`/billings/qualified` + `/transactions`、参照専用 GET。月帰属は `transaction.date`) と**双方向照合**する。順方向 (基準−実績) で発行漏れ・金額差を、逆方向 (実績−基準) で契約マスタ未登録 (orphan=要マスタ登録) を検出し、**契約マスタ DB1** (AI 自動生成) と**月次発行チェック DB2** (AI 生成・月次蓄積) へ非破壊 upsert する。さらに判定 SoR=DB2 から**請求確認シート各行へ『判定』(5値select)・『AI確認』(checkbox)・『確認ポイント』(rich_text=何を確認すべきか) を片方向ミラー書き戻し**し、経理がシート上で結果と次のアクションを確認できるようにする (責務分離ハイブリッド)。

**ユーザーが入力するのは請求確認シートのみ**。DB1 契約マスタ・DB2 月次チェックは本スキルが自動生成・移管する (担当者の入力負荷を増やさない)。

> **⚠️ AI・開発者向け — 照合/判定ロジックは実装済み・自作禁止**: 請求確認シート (年月/取引先/商品/確認内容) × MF掛け払いの照合と判定は**完成・テスト済み**。**自前の照合スクリプトを書いたり、判定 (classify 相当) を `TODO(human)` で人間に書かせたりしてはならない** (人の運用方針も `verdict-mapping.json`/`sheet_to_master` に既に encode 済み)。正本エントリは **`scripts/reconcile_invoices.py`** (月次 orchestrator、既定 dry-run)、判定エンジンは **`lib/mfk_reconcile.py`** (`reconcile()` / `classify()` / `detect_orphans()`)、判定語彙 5 値の SSOT は **`schemas/verdict-mapping.json`**。自然文で頼まれたら新規実装せず `/run-mf-invoice-reconcile --target YYMM` を **dry-run → 二段確認 (`mfk-reconcile-verifier`) → `--apply --verified`** の順で実行する。**機械強制**: `hooks/guard-mfk-no-reinvent.py` (PreToolUse) が、正本以外への照合再実装 (`def classify`/`def reconcile` 等) と本ドメインでの `TODO(human)` 書き込みを exit 2 で遮断する (prose 指示が出力スタイルに上書きされても効く機械層)。

**入力**: `--target YYMM` (対象月、例 2606)。既定は dry-run (集計のみ・書き込みゼロ)、DB2/シート反映を含む `--apply` は dry-run と二段確認完了を示す `--verified` を必須にする。`--steps` でスクリプト部分実行可 (collect,sync-master,reconcile,sink)。verify は `--steps` ではなく `mfk-reconcile-verifier` SubAgent で実行する独立フェーズ。DB id は引数 > 環境変数 > `.mf-kessai-config.json` で解決。DB1/DB2 の初期構築は `scripts/build_reconcile_dbs.py` (冪等 find-or-create) で行う。
**出力**: DB1 (契約ごとに支払サイクル/現行単価/契約期間/期待明細数) + DB2 (順方向 rows + 逆方向 orphan、判定=日本語ラベル、AI確認済み=ai_check 派生) + 請求確認シートへの『判定』5値+『AI確認』書き戻し + 画面に判定内訳サマリ。
**完了条件**: dry-run で判定内訳を確認 (二段確認) し、`--apply` で DB1/DB2 が当月分のみ非破壊 upsert され請求確認シートに当月判定が反映され、過去月の確認済み履歴と `人間対応済み` が保全された状態。

### DB ライフサイクル (毎回 upsert・新規作成しない・履歴保全)

月次運用では DB1/DB2 を**作り直さず upsert で更新**する。id は `.mf-kessai-config.json` (notion.reconcile_db1_id/db2_id) に固定し毎回同じ DB を指す。`build_reconcile_dbs.py` は **find-or-create** で、id が実在すれば再利用 (schema 不足列だけ冪等追加)・欠落時のみ `parent_page_id` 配下へ作成し id を保存する (再実行で重複作成しない=断片化防止)。**履歴が消えない二層設計**: DB1=最新状態マスタ (1 契約=1 行を上書き更新・改定は `単価改定履歴` 列) / DB2=不変アーカイブ (upsert キーに `対象年月` を含み月別に積層・過去月は query 当月限定で構造的に不可侵・`人間対応済み`=true 行は凍結)。シート『判定』は片方向ミラー (毎回最新で上書き・stale は再実行で自己修復)。

## End-to-End Flow

```
[1 collect]     reconcile_invoices.py --steps collect → MF掛け払い当月発行を全ページGET → build_mf_index (参照専用)
[2 sync-master] 請求確認シート(当月)をquery → build_contracts(支払サイクル自動推定) → (--apply) DB1契約マスタへ冪等upsert
[3 reconcile]   build_contracts × mf_index で照合。順方向=当月シート行 / orphan名寄せ=全月契約 → 判定verdict付きrows+orphans
[4 verify]      dry-run(--apply無し)の判定内訳を二段確認。subagent mfk-reconcile-verifier(context:fork)で発行漏れ/orphan/金額差の誤検出を排除
[5 sink]        --apply --verified で各rowにcontract_page_id解決 → DB2月次チェックへ非破壊upsert(当月のみ・過去月不可侵・AI確認済み更新・人間対応済み凍結)
                → 続けて請求確認シート各行へ『判定』(5値)+『AI確認』を片方向ミラー書き戻し(人間列『チェック済み』不可侵)
                ↑ MF APIは全GET / 変更系は hook(guard-mfk-readonly.py)で遮断。Notion書込は MFK_NOTION_WRITE_GAP のレート間隔付き
```

詳細は `workflow-manifest.json`、責務は `prompts/R1-R4`。dry-run (集計のみ) と --apply (書き込み) を分離し、判定内訳を確認してから適用することで二段確認を標準フローで要求する。

## ゴールシーク実行

### ゴール (Goal)
請求確認シート (基準) に対し当月の MF 発行実績を双方向照合した結果——発行漏れ・要マスタ登録 (orphan)・金額差・対象外——が判定ラベル付きで DB2 に非破壊 upsert され、契約マスタ DB1 が請求確認シートから自動生成され、独立 context の subagent で誤検出を排除した要対応リストが画面に提示された状態。

### 目的・背景 (Why)
発行漏れの早期発見と、契約マスタ未登録 (今後の月で誤 GAP を量産する継続契約) の補足。担当者の入力を請求確認シート 1 箇所に集約し、契約マスタ・月次記録は機械が移管することで管理負荷を増やさない。誤検出を防ぐため候補は dry-run と独立 context の二段で確認する。

### 責務サマリと完了条件の正本

各責務の**完了条件の詳細は `prompts/Rn` の L5.3 完了チェックリストを正本 (SSOT)** とする (片側更新ドリフトを避けるため SKILL 側で再定義しない)。本節は俯瞰用の責務サマリのみ示す。

- **R1 collect** (`prompts/R1-collect.md`): 対象月の `/billings/qualified` + `/transactions` を全ページ取得し MF 実績 index を作る (参照専用 GET)。
- **R2 reconcile** (`prompts/R2-reconcile.md`): 請求確認シート→契約マスタを生成し、順方向 (当月) と逆方向 orphan (全月) を金額+名前トークンで照合し判定 verdict を付与する。
- **R3 verify** (`prompts/R3-verify.md`): subagent `mfk-reconcile-verifier` が独立 context で発行漏れ/orphan/金額差の誤検出を排除する。
- **R4 sink** (`prompts/R4-sink.md`): DB1 契約マスタの契約 ID から relation page_id を解決し、DB2 月次チェックへ方向別キーで非破壊 upsert する (当月のみ更新・過去月不可侵・人間対応済み凍結)。DB2 upsert に failed が無い場合、判定 SoR=DB2 (forward rows) から請求確認シート各行へ『判定』(5値=未照合/AIの確認OK/対象外/要確認/発行漏れ・SSOT=verdict-mapping.json の sheet_label)+『AI確認』+『確認ポイント』を片方向ミラー書き戻しする (人間列『チェック済み』不可侵・ORPHAN はシート行なしで投影しない)。DB2 frozen 行は上書きしないが、シートの現在判定/確認ポイント投影は継続する。

横断不変条件 (各 Rn の L1/L4 が担保): **照合は presence-based** (請求確認シートの重複明細は MF で 1 請求にまとまる前提で、該当品目が 1 件でも反映されていれば発行漏れにはしない。契約ID境界内で複数シート行の期待額合計が MF 1 明細と一致する場合は `MATCH_MONTHLY` として扱い、単なる件数差では発行漏れにしない。合計一致しない数量差は発行済み証跡を保持したまま `REVIEW_QTY_MISMATCH` へ降格し、AI確認済みにはしない)。**順方向 (発行漏れ/金額一致) は当月シート行を期待集合とし、逆方向 orphan の名寄せだけは全月契約で行う** (年間前払い等で当月シートに無いが他月に登録済みの継続契約を誤 orphan しない)。支払サイクルは sync-master が請求確認シートから初期生成し、reconcile engine は DB1 相当の支払サイクル列を SSOT として読む (年周期 12 ヶ月固定・月額/年間一括は契約による)。確認内容に `期間：A〜B` がある契約は「作業開始から 1 年間」の初年度年間払いとして扱い、契約開始日が空なら期間開始 A で補完する。ただし `チイキズカン利用料（2年目以降）` は月払い、`100億ThinkTank利用料` は年間一括更新として扱う。期間も契約開始日も未記入の契約は原則月払いとして毎月請求期待に倒し、非月払いのデータ不備で要確認化しない (従量・保留は専用判定)。年間前払い期間中で月次発行が無いのが正常な契約は GAP から除外する。**契約終了月 M の最終請求書は役務の翌月 (M+1) に発行されるのが正常 (月またぎ発行)** なので、終了月〜終了月+1 の MF 請求は `MATCH_ENDED_FINAL` (発行確認OK・最終請求) とし過剰請求にしない。過剰請求 (`REVIEW_ENDED_BUT_BILLED`) は終了月+2 以降に MF 請求がある場合のみ。MF API への POST/PATCH/DELETE は hook で遮断され参照専用が保証される。

### 完了チェックリスト (Checklist)
> 各責務の停止条件詳細は `prompts/Rn` の L5.3 を正本 (SSOT) とする。本節は俯瞰用の二値チェックのみ。
- [ ] `--steps collect` が対象月の qualified billing + transactions を全ページ取得し MF index を作った (R1)
- [ ] `--steps sync-master` が請求確認シート(当月)から契約マスタを生成し DB1 へ冪等 upsert した (R2、--apply 時)
- [ ] reconcile が順方向 (当月) と逆方向 orphan (全月) を分離して判定し dry-run で内訳を提示した (R2)
- [ ] subagent `mfk-reconcile-verifier` が独立 context で発行漏れ/orphan/金額差の誤検出を排除した (R3)
- [ ] `--apply` が DB2 月次チェックへ方向別キーで非破壊 upsert した (当月のみ・過去月不可侵・人間対応済み凍結、R4)
- [ ] `--apply` が請求確認シート各行へ『判定』(5値)+『AI確認』+『確認ポイント』(何を確認すべきか) を片方向ミラー書き戻しした (人間列不可侵、R4)
- [ ] 運用者が翌月以降も過去月の確認済み状態を DB2 (対象年月でフィルタ) で参照でき、当月結果を請求確認シート上でも確認できる (見方は README 参照)
- [ ] DB1/DB2 は毎回 upsert 更新で作り直さない (id は config 固定・build_reconcile_dbs.py は find-or-create で重複作成しない)
- [ ] DB id 未設定時は fail-closed (exit 2) で差し戻した

### ゴールシークループ
1. `--steps collect` で MF 実績を取得 (`R1`)。
2. 既定 dry-run で sync-master→reconcile を回し判定内訳を得る (`R2`)。
3. subagent で二段確認し誤検出を排除 (`R3`)。
4. `--apply --verified` で DB1/DB2 へ非破壊 upsert (`R4`)。過去月と人間対応済みは保全。
5. 全 checklist 充足で完了。DB id 未設定なら fail-closed で差し戻す。

## Key Rules

1. **参照専用 (二層で抑止)**: 第1層=`hooks/guard-mfk-readonly.py` (PreToolUse) が Bash 経由の MF 変更系を遮断。第2層=`lib/mfk_api.py` は GET 専用で POST/PATCH/DELETE 関数を構造的に持たない。
2. **二層分離・入力は請求確認シートのみ**: 担当者は請求確認シート (年月 + 1 明細=1 行) だけを入力する。**シートの『年月』select は取引日 (月末締め) の月で記入する** (例: 取引日 `2026/06/30` 締め→年月 `2606`、`--target 2606` と一致)。月帰属は MF 側も `transaction.date` (取引日) 軸のため、発行月 (翌月月初) で記入すると当月の期待集合 (順方向 GAP 検知の母集合) から外れ、真の発行漏れを見逃す。DB1 契約マスタ (支払サイクル/単価/期間を契約単位に集約) と DB2 月次チェックは本スキルが自動生成・移管する。DB1 の支払サイクル初期値は `sheet_to_master.infer_cycle` が確認内容+商品+MF実績シグナルから推定する (ユーザーは入力しない)。確認内容の `期間：A〜B` は作業開始から1年間の契約期間として扱い、初年度は年間払い、それ以外は月払いへ倒す。ただし商品定義上の 2年目以降利用料は月払い、ThinkTank は年間一括更新。
3. **双方向照合**: 順方向 (基準−実績) = 発行漏れ GAP/金額差/対象外。逆方向 (実績−基準) = orphan 要マスタ登録。**順方向は当月シート行・orphan 名寄せは全月契約**で行う (当月だけだと QTY 誤発・全月だと orphan 誤発するため分離)。
4. **presence-based**: 重複明細は MF で 1 請求にまとまる前提。該当品目が 1 件でも反映されていれば発行漏れにはしない。契約ID境界内で `現行単価 × 期待明細数` が MF 1 明細の金額と一致する場合は、MF 側で集約済みとして `MATCH_MONTHLY` にする。合計一致しない数量差 (シート件数>MF件数) は `REVIEW_QTY_MISMATCH` へ降格し、AI確認済みにはしない。
5. **履歴非破壊 (翌月も先月確認済みが残る)**: DB2 sink は当月 (対象年月==target) の行だけを upsert し、過去月は query フィルタで構造的に触れない。`人間対応済み`=true の行は frozen で skip。方向別キー (順方向={契約ID}_{ym} / orphan=ORPHAN_{MF顧客ID}_{ym}) で同月再実行は行更新 (冪等)。
6. **二段確認 (dry-run + `--verified` が物理境界)**: 既定は dry-run (集計のみ・書き込みゼロ)。DB2/シート反映を含む `--apply` は `--verified` 明示時だけ通す。判定内訳を dry-run で確認し、subagent の二段確認後にだけ `--apply --verified` を使う (誤投入防止)。
7. **Notion 書込はレート間隔付き**: 一括投入は Notion のレート制限で弾かれるため、書き込み系 (POST/PATCH/PUT/DELETE) は `notion_transport._write_gap` が `MFK_NOTION_WRITE_GAP` (既定 0.34 秒) を挟む。GET は間隔なし。page_id 重複除去で二重 archive を防ぐ。
8. **AI確認と人間確認を分離**: DB2 の `AI確認済み` checkbox は `verdict-mapping.json` の `ai_check` から機械が更新する。`人間対応済み` checkbox は人が対応完了を記録する列で、AI は新規時 false 初期化以外は書かない (frozen 判定の入力に使う)。
9. **判定ラベルは SSOT**: 内部 verdict→日本語ラベル/AIチェック可否/警告クラス/シート5値の対応は `schemas/verdict-mapping.json` を唯一の正本とし、engine emit ⊆ mappings を parity test で機械保証する (別表記を作らない)。DB2『判定』は `judge_label` distinct、シート『判定』は 5 値 (`sheet_label`) と別軸で、いずれも同一 SSOT から派生する。
10. **シート書き戻しは片方向ミラー**: 判定 SoR=DB2 (裏方台帳)。請求確認シートの『判定』(5値select=未照合/AIの確認OK/対象外/要確認/発行漏れ・色付き)・『AI確認』・『確認ポイント』(rich_text=何を確認すべきか) は DB2 から決定論的に再計算した投影で、`--apply --verified` 時に当月 forward rows を各シート行へ冪等 PATCH する。機械が常時上書きするのはこの 3 列のみで、加えて `契約開始日` が空欄の場合だけ確認内容の期間から派生した値を補完する。人間列『チェック済み』『確認内容』『取引先』『商品』は不可侵で、`契約終了月` は誤推定防止のため補完しない。`確認ポイント` は verdict 定型ガイダンス (verdict-mapping.json の `action_hint` SSOT) + 行固有の警告詳細を連結する。空にするのは `AIの確認OK` (MATCH_*) だけで、`対象外` (SUPPRESS_*) はなぜ対象外かを必ず出す。**`対象外` でも当月MFに取消取引があれば確認ポイントに取消理由 (取消前金額/取消日) を併記する** (engine の `cancellation_note` が `warning` へ注記・verdict/sheet_label は据え置き=WARN-not-FAIL)。stale は再実行で自己修復。ORPHAN (逆方向・シート行なし) は投影しない。保留/未締結契約は `REVIEW_PENDING` として『判定=要確認』に投影し、理由を『確認ポイント』へ書く。**未照合 (シート『判定』空欄) の発生基準**: 当月 (対象年月) に登録された行は保留契約も含め必ず判定が付くため、シート『判定』が空欄に残るのは「その行が当月照合の対象でない (対象月以外の年月の行・当月シートに登録の無い行)」場合のみ。経理は当月の年月でフィルタして確認する (空欄=当月対象外であり判定漏れではない)。
11. **DB は作り直さず更新 (find-or-create)**: `build_reconcile_dbs.py` は config の reconcile_db1_id/db2_id が実在すれば再利用 (不足列だけ冪等追加)・欠落時のみ parent_page_id 配下へ作成し id を保存する。月次運用で DB を新規作成しない (重複・断片化防止)。履歴は DB1=最新状態 / DB2=対象年月キーで月別積層 の二層で保全。

## Gotchas

1. DB id (sheet_db/db1/db2) 未設定なら fail-closed (exit 2)。`.mf-kessai-config.json` の `notion.{sheet_db_id,reconcile_db1_id,reconcile_db2_id}` か引数で指定。
2. MF APIキーと Notion トークンは別 Keychain entry (`mfkessai-api-key.<keychain-prefix>` / `notion-api-key.<keychain-prefix>`、いずれも account=<keychain-prefix>)。
3. 取引先は**集約元**のことがあり実 MF 顧客は確認内容内の別名のことがある (例 HOSONO→タップス株式会社)。名寄せは MF 顧客名/明細括弧内の人名・企業名 ↔ シートの取引先/確認内容を NFKC 正規化して突合する。
4. 確認内容の `期間：A〜B` は「前回共有された期間=作業開始から1年間」の根拠として扱う。月額表記が併記されても初年度は年間払いを優先し、期間開始 A を契約開始日に補完する。2年目以降利用料はすでに月額移行済みとして月払い。
5. カタカナが NFD (macOS/MF API 由来) でリテラル(NFC)と != になるため `normalize("NFKC")` 必須。MF 明細は API 上で同一行が二重化されるため `(billing_id,desc,amount)` で dedup してから数量を数える。
6. 商品空のメモ行 (連絡先変更等・金額なし) が実商品行と同一バケツに入ると Notion の空 select が拒否される。`_majority` が空文字を非空商品名へ劣後させ、最終防御で `_to_props` が空商品を「未分類」へ倒す。
7. 過去月の確認済みの見方・要対応ビューの作り方は README を参照。DB2 を `対象年月` でフィルタすれば月次の確認済み履歴が残る (sink が非破壊のため翌月も消えない)。
8. **契約終了月の翌月請求を過剰請求と誤判定しない**: 終了月 M の役務は翌月 (M+1) に最終請求書が発行されるのが正常。終了月〜M+1 の MF 請求は `MATCH_ENDED_FINAL` (発行確認OK・最終請求) で過剰請求にしない。過剰請求 (`REVIEW_ENDED_BUT_BILLED`) は M+2 以降の請求のみ。DB2 では `発行確認OK(最終請求)` の専用ラベルで通常の OK と区別し監査できる (シート 5値では `AIの確認OK`)。
9. **金額0円でも商品名が残る取消を対象外にしない / 取消の判定軸**: MF側で `billing.amount=0` になっていても、transaction が `status=canceled` かつ description/商品名を保持している場合は取消証跡として扱う。**月次/年額で当月の有効供給(passed)がゼロかつ取消あり → `REVIEW_CANCELED` (要確認(取消))** で GAP や `対象外` へ落とさない。一方 **契約終了/年間前払い/単発/off-cycle の抑制で当月が取消のみ → verdict は `対象外` のまま据え置き、確認ポイントに取消注記を併記** (`cancellation_note`・WARN-not-FAIL)。終了契約の presence 判定は取消を無視するため「一度発行→取消」が対象外行から消える問題を、この一段の注記で横断的に救済する。`amount=None` の取消も `build_mf_index` が 0 円へ正規化して inactive へ残し取りこぼさない。

## Additional Resources

- `workflow-manifest.json` — collect/sync-master/reconcile/verify/sink の Step 定義 + hook guard
- `$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py` — 月次 1 コマンド orchestrator (--target/--apply/--steps、既定 dry-run)
- `$CLAUDE_PLUGIN_ROOT/scripts/build_reconcile_dbs.py` — DB1/DB2 冪等 find-or-create ビルダー (id 再利用・欠落時のみ作成)
- `$CLAUDE_PLUGIN_ROOT/scripts/clear_unsupported_end_dates.py` — 保守(独立パス・dry-run既定): 確認内容に終了根拠が無いのに契約終了月が入った行を空欄へ戻す (継続契約の発行漏れ隠蔽を健全化)。reconcile の健全性検知が件数告知時に誘導する
- `$CLAUDE_PLUGIN_ROOT/scripts/backfill_sheet_contract_dates.py` — 保守(独立パス・dry-run既定): 同一取引先で契約開始日が1種類に収束する場合のみ空欄行へ伝播 backfill (競合する取引先は非伝播=conflicts)。契約終了月は根拠なき伝播を避けるため対象外
- `prompts/R1-collect.md`〜`R4-sink.md` — 責務プロンプト
- `schemas/` — reconcile-result / verdict-mapping(判定SSOT・judge_label distinct + sheet_label 5値) / contract-master-db / monthly-check-db
- `$CLAUDE_PLUGIN_ROOT/lib/` — mfk_reconcile(照合engine・sheet_label派生) / sheet_to_master(シート→契約マスタ・_sheet_row_ids) / notion_reconcile_sink(DB2非破壊upsert) / notion_sheet_writeback(シート判定書き戻し) / notion_transport(レート間隔) / mfk_api / mfk_keychain
- `$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-readonly.py` — 参照専用ガード
- `$CLAUDE_PLUGIN_ROOT/agents/mfk-reconcile-verifier.md` — 二段確認 subagent
