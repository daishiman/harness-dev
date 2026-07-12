# Prompt: R2-reconcile

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R2-reconcile |
| skill | run-mf-invoice-reconcile |
| responsibility | R2 契約マスタ生成 + 双方向照合・判定 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/reconcile-result.schema.json |
| reproducible | true (同一 target・同一シート・同一 MF index に対し同一判定 JSON) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- MF API は GET のみ。本責務は MF へ POST/PATCH/DELETE を一切発行せず、R1 collect が取得済みの `mf_index`/`mf_raw` を消費する純関数 (`mfk_reconcile`) 主体で動く。変更系は hook `guard-mfk-readonly.py` で遮断。
- DB への書込は sync-master の `sheet_to_master.upsert_master` (DB1 契約マスタへ契約ID キーで冪等 upsert) のみ。DB2 月次チェックの物理書込は本責務に含めない (R4)。
- **順方向 (発行漏れ GAP / 金額一致 MATCH / 金額差 / 数量差 / 対象外) は当月シート行を期待集合とし、逆方向 orphan の名寄せだけは全月契約で行う**。当月だけだと数量差を誤発し、全月だと orphan を誤発するため、期待集合と orphan 被覆集合を構造的に分離する。
- 判定語彙 (internal `verdict` → 日本語ラベル / AIチェック可否 / 警告クラス) は `../schemas/verdict-mapping.json` を唯一の正本 (SSOT) とし、別表記を作らない。engine が emit する verdict は mappings の部分集合 (emit ⊆ mappings)。
- 年周期 = `ANNUAL_MONTHS=12` 固定。支払サイクルは sync-master が請求確認シートから DB1 初期値を自動生成し、reconcile engine は DB1 相当の『支払サイクル』列を SSOT として読む (`_resolve_cycle` は列を最優先、空欄時のみ月払い fallback)。

### 1.2 倫理ガード
- MF APIキー / Notion トークンは Keychain のみ (別 entry)。平文出力・ログ復唱をしない。
- `人間対応済み` は人間専用列。AI は読むだけで書かない。本責務は判定のみで凍結判定・DB2 書込は行わない (R4)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当 (a) sync-master: 請求確認シート (当月) を query → `sheet_to_master.build_contracts(sheet_rows, mf_index=mf_raw, target_ym)` で distinct 契約へ集約し、`infer_cycle` で支払サイクルを自動推定。`--apply` 時のみ `upsert_master(contracts, db1, …)` で DB1 契約マスタへ契約ID キーで冪等 upsert。
- 担当 (b) reconcile: `mfk_reconcile.reconcile(contracts, mf_index, target)` で順方向 (当月シート由来の期待契約 × MF実績) を判定し、`mfk_reconcile.detect_orphans(contracts_all, mf_index, target)` で逆方向 orphan (MF実績のみ=要マスタ登録) を検出。`result["orphans"]` は全月契約由来で上書きする。
- 非担当: MF実績取得 (R1)、二段確認 (R3 subagent `mfk-reconcile-verifier`)、DB2 月次チェックへの物理書込 (R4)。ただし sync-master の DB1 upsert は本責務に含む。

### 2.2 ドメインルール
- **presence-based**: 請求確認シートの重複明細は MF で 1 請求にまとまる前提。該当品目が 1 件でも反映されていれば発行漏れ (GAP) にはしない。契約ID境界内で複数シート行の期待額合計 (`現行単価 × 期待明細数`) が MF 1 明細と一致する場合は `MATCH_MONTHLY` として扱い、単なる件数差で発行漏れ・数量差にはしない。合計一致しない数量差 (シート件数 > MF供給件数) は `quantity_downgrade` (F1) で `REVIEW_QTY_MISMATCH` に降格し、発行済み証跡を保持しつつ AI確認済みにはしない。
- **名寄せ (J1)**: 金額 + 名前トークン (取引先/確認内容の人名・企業名 ↔ MF顧客名/明細括弧内) を `normalize` (NFKC) で突合。境界は `_boundary_customers` が ①MF顧客ID 一致 → ②取引先の会社名一致 (`_company_match`) の順で解決し、取引先境界で供給を分割して name-global 偽陰性を回避する。同名人物が別会社に請求された場合は `cross_client` として MATCH 扱いせず GAP + 証跡で要確認化。
- **支払サイクル**: `infer_cycle` が確認内容 + 商品 canon + MF実績シグナル (`build_mf_signals`: has_split / riyo_lump / riyo_monthly) から DB1 初期値を推定する。確認内容に `期間：A〜B` がある契約は「作業開始から1年間」の初年度年間払いとして扱い、契約開始日が空なら期間開始 A で補完する。例外として `100億ThinkTank利用料` は年間一括更新、`チイキズカン利用料（2年目以降）` は月払い。期間も契約開始日も未記入の契約は原則月払いとして毎月請求期待に倒し、非月払いのデータ不備で要確認化しない (従量・保留は専用判定)。MECE6値+従量 = 月払い / 年間払い / 年間一括更新 / 単発 / 分割 / 隔月 / 従量(都度)。年周期 12 ヶ月固定。判別不能は None (=保留)。
- **年間前払い抑制**: 年間払い 0<elapsed<12 / 年間一括更新 elapsed%12!=0 は当月の月次請求なしが正常 → `SUPPRESS_ANNUAL`。年間前払い期間中で月次発行が無いのが正常な契約は GAP から除外する。
- **金額差 (B1)**: 名寄せ供給があり金額のみ不一致は GAP に落とさず `REVIEW_AMOUNT_MISMATCH` (桁区切り typo は `REVIEW_AMOUNT_TYPO`)。GAP は名寄せ供給が皆無のときに限定する。
- **取消・未確定取引の可視化**: 有効供給 (`status=passed` / 空 / None) がゼロで、同一境界に `status=canceled` 取引がある場合は `REVIEW_CANCELED`。`billing.amount=0` でも description/商品名が残る canceled 取引は取消証跡として扱い、単純な0円除外・GAP・対象外にしない。`amount=None` の canceled も `build_mf_index` が 0 円へ正規化して inactive へ残し取りこぼさない。`canceled` 以外の非 passed 取引は `REVIEW_TXN_NOT_PASSED` として、審査中/否決/停止等の状態確認を促す。年払い系では年額一括相当の非active供給に限ってこの分岐を使い、年間前払い期間中の小額取消で `SUPPRESS_ANNUAL` を誤昇格しない。
- **対象外行への取消注記の横断併記 (WARN-not-FAIL)**: 契約終了/年間前払い/単発/off-cycle の抑制 verdict (`SUPPRESS_ENDED`/`SUPPRESS_ANNUAL`/`SUPPRESS_ONESHOT`/`SUPPRESS_OFFMONTH`/根拠なし終了 `REVIEW_ENDED_NO_BASIS`) が確定した直後に `_annotate_cancellation`→`cancellation_note` を呼び、当月境界に取消/未確定供給があれば `warning` へ取消注記を併記する (verdict/sheet_label は据え置き)。終了契約の presence 判定は取消 (canceled) を無視するため「一度発行→取消」が対象外行から消えるが、この一段の注記で横断救済し書き戻し層 (`compose_note`) が対象外行の確認ポイントへ取消理由を流す (書き戻し層は不改修)。
- **商品空メモ行の防御**: 商品空のメモ行 (連絡先変更等・金額なし) が実商品行と同一バケツに入ったら、`_majority` が非空商品名を優先し、最終防御で `_to_props` が空商品を「未分類」へ倒す (Notion の空 select 拒否を防ぐ)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --target | string(YYMM) | yes | 対象月。例 `2606`。YYMM 不正は exit 2 |
| --steps | string(csv) | no | `collect,sync-master,reconcile` を含める。reconcile は sync-master+collect 必須 |
| --apply | flag | no | DB1 へ冪等 upsert する。無指定は dry-run (集計のみ・書込ゼロ) |
| sheet_rows | list[dict] | (内部) | `query_sheet_rows` が当月『年月』select でフィルタした請求確認シート行 |
| mf_index / mf_raw | dict | (内部) | R1 collect の `build_mf_index` / raw MF JSON。支払サイクル推定と名寄せ実績の双方が消費 |

### 2.4 出力契約
- schema: `../schemas/reconcile-result.schema.json` (additionalProperties:false)。内部結果は `target_ym` + 順方向 `rows` + 逆方向 `orphans` + verdict件数 `summary`。`verdict` 語彙は `../schemas/verdict-mapping.json` から逐語引用する。
- 判定語彙 SSOT: `../schemas/verdict-mapping.json` (judge_label / ai_check / warning_class はここから `judge_label()` 等で導出。独立列挙しない)。DB1 形状は `../schemas/contract-master-db.schema.json`。
- 出力: メモリ内 `result = {target_ym, rows(順方向), orphans(逆方向), summary(verdict件数)}` + 画面に件数・判定内訳サマリ。dry-run では DB へ書かない。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| orchestrator | `$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py` | sync-master / reconcile step の配線 |
| sheet→master lib | `$CLAUDE_PLUGIN_ROOT/lib/sheet_to_master.py` | build_contracts / infer_cycle / upsert_master |
| reconcile engine | `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` | reconcile / classify / detect_orphans / find_mf_match / judge_label |
| verdict SSOT | ../schemas/verdict-mapping.json | internal_verdict → 日本語ラベルの唯一の正本 |
| 出力 schema | ../schemas/reconcile-result.schema.json | 照合結果 JSON の契約 |
| DB1 schema | ../schemas/contract-master-db.schema.json | 契約マスタの property 形状 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py" --target <YYMM> --steps collect,sync-master,reconcile [--apply]`
- Notion REST (シート read / DB1 read+write。書込は `notion_transport._write_gap` の `MFK_NOTION_WRITE_GAP` レート間隔付き)。MF API は R1 で取得済み (本責務は GET も発行しない純関数主体)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- DB id (sheet_db/db1) 未解決は fail-closed (exit 2、欠落 id を明示)。`--steps` 依存違反 (reconcile に sync-master+collect 無し) も exit 2。
- DB1 upsert の個別失敗は `upsert_master` が try/except で握って `failed` に記録し**全体を止めない** (silent cap 禁止)。失敗は stderr に契約ID + error を必ず出す。
- 既定は dry-run (集計サマリのみ・書込ゼロ)。`--apply` で初めて DB1 upsert を実行する。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に sync-master のシート行数→契約件数・DB1 upsert 内訳 (created/updated/failed)、reconcile の順方向行数 / 逆方向 orphan 件数 / verdict 別件数サマリ。
- DB1 失敗は stderr に詳細 (契約ID + error)。

### 4.3 セキュリティ
- MF は参照のみ (本責務は GET も発行しない)。Notion 書込は DB1 upsert のみで `_write_gap` のレート間隔を挟む。secret は Keychain 参照のみで平文出力しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- sync-master + reconcile 実行 (決定論 lib 主体、context-fork 不要。二段確認の独立 context は R3 が担当)。

### 5.2 ゴール定義
- 目的: 請求確認シート (当月) を contracts に集約し DB1 契約マスタを自動生成 (--apply 時 upsert)、当月期待 × MF実績の順方向判定と全月契約での逆方向 orphan 検出を verdict 付きで揃え、dry-run で判定内訳を提示する。
- 背景: 担当者の入力を請求確認シート 1 箇所に集約し、契約マスタ・支払サイクル・月次判定は機械が移管する。期待集合 (当月) と orphan 被覆集合 (全月) を分離しないと数量差/orphan を誤発するため、reconcile は両集合を別々に構築する。
- 達成ゴール: command 実行により build_contracts → (--apply) DB1 upsert → reconcile (順方向) + detect_orphans (逆方向・全月) が完了し、`result = {target_ym, rows, orphans, summary}` が `reconcile-result.schema.json` 準拠で判定語彙 (verdict-mapping.json SSOT) に一致した状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `query_sheet_rows` が当月 (年月 select) の請求確認シート行を全ページ取得した
- [ ] `build_contracts` で distinct 契約へ集約し `infer_cycle` で支払サイクルを推定した (保留は None)
- [ ] (--apply 時) `upsert_master` が DB1 契約マスタへ契約ID キーで冪等 upsert し、個別失敗を failed/stderr に記録した (全体は止めない)
- [ ] 順方向 `reconcile(contracts, mf_index, target)` を当月シート由来の期待集合で判定した (presence-based・契約ID境界内のMF 1明細集約一致・金額差 B1・数量差 F1・年間前払い抑制・取消/未確定取引の可視化)
- [ ] 逆方向 `detect_orphans(contracts_all, mf_index, target)` を**全月契約**で名寄せし orphan を検出して `result["orphans"]` を上書きした
- [ ] 全 verdict が `verdict-mapping.json` の internal_verdict 部分集合 (emit ⊆ mappings) で、`result` が `reconcile-result.schema.json` 準拠
- [ ] dry-run で順方向行数 / 逆方向 orphan 件数 / verdict 別内訳サマリを画面提示した
- [ ] MF への POST 等変更系を一切呼んでいない (純関数・参照のみ)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (steps 調整 / --apply 切替 / 再実行)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-reconcile` SKILL Step 2 (sync-master) + Step 3 (reconcile)。
- 前段 phase: R1 collect (MF実績 index)。後続 phase: R3 verify (二段確認) → R4 sink (DB2 非破壊 upsert)。

### 6.2 ハンドオフ / 並列性
- 提供元: ユーザー (`--target`/`--apply`/`--steps`) / 請求確認シート (当月行) / R1 collect (`mf_index`/`mf_raw`)。
- 受領先: R3 verify (`result` の rows/orphans を独立 context でレビューし誤検出を排除) → R4 sink (各 row に `contract_page_id` を解決し DB2 へ方向別キーで非破壊 upsert)。
- 引き渡し形式: メモリ内 `result = {target_ym, rows, orphans, summary}`。順方向は当月 contracts、orphan は全月 contracts_all で構築済み。DB1 upsert (--apply 時) は同 step 内で完了。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に sync-master (シート行数→契約件数・DB1 upsert 内訳) と reconcile (順方向行数 / 逆方向 orphan 件数 / verdict 別件数) のサマリ (Markdown)。dry-run/apply のモードを明示。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum / verdict / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`python3 "$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py" --target <YYMM> --steps collect,sync-master,reconcile [--apply]` を実行する。まず `query_sheet_rows` で当月 (年月 select) の請求確認シート行を全ページ取得し、`sheet_to_master.build_contracts(…, mf_index=mf_raw, target_ym)` で distinct 契約へ集約 (`infer_cycle` で支払サイクル初期値を推定)。`infer_cycle` は確認内容の `期間：A〜B` を作業開始から1年間の契約期間として扱い、月額表記が併記されても初年度は年間払いを優先する。ただし `チイキズカン利用料（2年目以降）` は月払い、`100億ThinkTank利用料` は年間一括更新とする。`--apply` 時のみ `upsert_master` で DB1 契約マスタへ契約ID キーで冪等 upsert し、個別失敗は failed/stderr に記録して全体を止めない。続いて `mfk_reconcile.reconcile(contracts, mf_index, target)` で**当月シート由来の期待集合**を順方向判定 (presence-based・契約ID境界内の MF 1明細集約一致・金額差 B1・数量差 F1 は `REVIEW_QTY_MISMATCH`・年間前払い抑制・`status=canceled` の `REVIEW_CANCELED`・その他非passedの `REVIEW_TXN_NOT_PASSED`) し、`detect_orphans(contracts_all, mf_index, target)` で**全月契約**を名寄せして逆方向 orphan を検出 `result["orphans"]` に上書きする (期待集合=当月 / orphan 被覆=全月 を分離)。verdict→日本語ラベルは `../schemas/verdict-mapping.json` を唯一の正本とし (emit ⊆ mappings)、`result = {target_ym, rows, orphans, summary}` を `../schemas/reconcile-result.schema.json` 準拠で揃える。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。既定は dry-run (集計のみ・書込ゼロ)、`--apply` で初めて DB1 へ書く。MF は参照のみ。出力はサマリのみ、前置き禁止。
