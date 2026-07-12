# Prompt: R1-collect

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-collect |
| skill | run-mf-invoice-report |
| responsibility | R1 対象月決定 + 前月/今月 MF実績取得 + per-月verdict収集 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (schema なし・C03 mfk_period_report.py の入力 I/O 契約が正本) |
| reproducible | true (同一 target・同一 API 応答に対し同一 per-月 verdict 入力) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- MF掛け払い API は GET のみ。変更系 (POST/PATCH/DELETE) は一切行わない (hook `guard-mfk-readonly.py` でも遮断)。
- 月帰属の判定軸は必ず `transaction.date` (取引日・月末締め)。「6月分の請求書」は取引日 `2026-06-30` の請求で、発行日が翌月月初でも 6月分として扱う。
- **今月 = 直近締め済みの請求対象月** (実行日カレンダー月の前月)。例: 2026-07-02 実行 → 今月=`2606` (2026-06分)・先月=`2605` (2026-05分)。対象月決定は `mfk_period_report.resolve_target_months` の規約に一致させる (自作の月計算を発明しない)。
- **per-月 verdict は既存 `lib/mfk_reconcile.py` の出力を消費するのみ** (SUPPRESS_ENDED / SUPPRESS_ANNUAL / MATCH_ANNUAL / REVIEW_ENDED_NO_BASIS 等)。C03 が消費する verdict を R1 で再照合・再パースしない (終了根拠判定 SSOT=mfk_reconcile)。
- 取引先の突合キーは既存 `mfk_reconcile.normalize`/`extract_names` で正規化して表記揺れを吸収する (自作正規化を発明しない)。

### 1.2 倫理ガード
- MF APIキー / Notion トークンは Keychain のみ (別 entry)。平文出力・ログ復唱をしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 対象月 (今月/先月) を決定し、前月・今月の全取引先 MF発行実績を参照専用 GET で取得、既存 reconcile engine で per-月 verdict を収集し、取引先×商品で状態遷移 (今月あり×前月あり / 今月あり×前月なし / 今月なし×前月なし / 今月なし×前月あり) を抽出する。差分に現れた**該当取引先のみ** 12 ヶ月分の発行履歴を追加取得し、請求確認シート由来の契約終了月も収集する。最終的に C03 (`mfk_period_report.py`) が読む入力 JSON (`curr-verdicts` / `prev-verdicts` / `lookback-12mo` / `contract-end`) を組む。
- 非担当: 前月↔今月の状態遷移分類・事情コメント生成 (R2=C03)、二段確認 (R3 sub-agent)、Notion 書込 (R4=C04)。

### 2.2 ドメインルール
- 候補取得は**取引先単位**で絞り、分類照合とコメント根拠は**取引先×商品単位**で行う。同一取引先・同一商品に複数契約があるときのみ契約ID (`contract_id`) を disambiguator に足す (C03 の `_needs_disambiguation` と同じ規約)。
- 12 ヶ月遡りは**差分該当取引先のみ**に限定する (全件遡らない=API 負荷最小化)。`--lookback-12mo` には差分該当分だけを渡す前提。
- **STATE_NEW (前月なし今月あり) 候補が 1 件以上あるなら 12ヶ月ルックバックを必須 fetch する** (D1)。C03 は裏付け (12ヶ月履歴の年契約一括) がある行のみ正常☑・裏付けなし (未実行 or 年契約履歴なし=真の新規) は要確認☐へ flip するため、STATE_NEW 該当取引先の 12ヶ月履歴 fetch を省略すると全 STATE_NEW 行が要確認固定になる (安全側だが過剰報告)。MF実績自体が 12ヶ月前まで存在しない取引先のみ源を明示して省略可。fetch 部分欠損 (C06 exit3=lookback 部分欠損) の該当行も C03 が要確認へ降格する。
- **12 ヶ月遡りのデータ源は MF掛け払い API の発行実績 (`transaction.date` 履歴) であり、請求確認シートではない**。シートは `--contract-end` (契約終了月=二次情報) の源にすぎず、シートの開始月 (例: 2605 開始) は 12 ヶ月遡りの可否と無関係。前月なし今月あり (新規/年→月切替) は「12ヶ月前の年契約一括→月額自動切替」の可能性が高い (C3) ため、**シートの開始月を理由に 12 ヶ月遡りを省略しない**。MF 実績自体が 12 ヶ月前まで存在しない場合 (口座開設が新しい等) のみ遡り不可で、そのときは省略理由を「MF実績が YYMM 開始のため」と源を正しく特定して明示する (シートと取り違えない)。省略した場合、C03 は前月なし今月あり行のコメントへ『12ヶ月ルックバック未実行→年→月切替か真の新規か未確認』を焼き、stderr に警告を出す (silent skip の禁止)。
- per-月 verdict 行の各要素は C03 (`mfk_period_report.py`) が消費するキーを保持する: `verdict` / `customer` (または `取引先`) / `product` (または `商品`) / `contract_id` / `evidence`(desc/amount) / `現行単価` 等の金額 / トライアル信号のための canon 前の生商品名 (`商品生名`/`product_raw`) や `確認内容`。
- **【保持キー契約 (C05 mfk_actuals の MF実績 carrier)】** classify (lib/mfk_reconcile.py) は全 status 行へ MF実績由来の carrier を焼く。決定論 producer `mfk_verdict_export.py` (C05) が `curr-verdicts` / `prev-verdicts` JSON へこれらを**直列化して落とさない**ことを保証する: `actual_amount` (MF が当月に実発行した税抜額・active 供給限定・inactive/none は null) / `reliable_issued` (MF実績由来の active 発行有無=期待額一致でなく実績) / `supply_state` (`active` / `inactive_canceled` / `inactive_pending` / `none`) / `canceled_at`。これらが amount-gate 根治の carrier であり、C03 の `_amount_of` (実額優先) と `_is_issued` (reliable_issued 起点・evidence.amount fallback は supply_state==active 限定) が読む。**evidence は据え置く** (書き換えず READ 専用の後方互換のみ・DB2 温存境界)。**producer は `reconcile().rows` 全件 (状態問わず1 contract=1 row) を persist するため curr=None は構造的に起きない** (発行済み社の当月行を落とさない=C2 根治)。producer は直列化前に carrier 欠落を検証し exit 1 (fail-closed)。
- 契約終了月 (`--contract-end`) は二次情報。C03 は `has_end_basis` 由来の既存 verdict を一次源にし、構造化列『契約終了月』は cross-check に使う (根拠なき終了月を抑制に使わない)。
- **【curr-present 化 (GAP-R1-COLLECT-CURR-PRESENT 根治済み・C05)】curr の非請求月 suppress 行の curr-present 化**: reconcile は非請求月にも `SUPPRESS_OFFMONTH`/`SUPPRESS_ONESHOT`/`SUPPRESS_ANNUAL` を算出する。旧経路 (LLM 手動直列化 / DB2 スナップショット由来) ではこの抑制行が persist されず落ち C03 で `curr=None` になっていたが、**C05 決定論 producer `mfk_verdict_export.py` が `reconcile().rows` 全件 (SUPPRESS_* 含む) を無損失 persist することで根治した**。producer は carrier をそのまま直列化し (suppress/GAP 行は reliable_issued=False・actual_amount=null なので C03 `_is_issued` が True 化して継続発行へ誤分類することはない=副契約を機械的に満たす)。MF実績ありマスタ未登録は curr=None でなく `orphans` (要マスタ登録) へ分離。追跡=handoff `GAP-R1-COLLECT-CURR-PRESENT` (本 plan C05 が根治領域として引き取り解消・fidelity plan 側は tracked=true・blocking=false のまま)。
- `status=canceled` かつ商品名が残る 0円明細は取消証跡として保持する (単純 0円除外にしない・`build_mf_index` が inactive へ残す)。
- **【fetch fidelity trace の記録 (C06 mfk_fetch_audit.py への配線)】** 当月/先月/12ヶ月ルックバックの全 read-only fetch を `lib/mfk_api.iter_all`/`get_with_trace` の `trace_sink` 経由で行い、各ページの pagination metadata (`has_next`/`end`/`total`/`items_count`/`params`(issue_date_from/to 含む)) を落とさず `fetch_trace` JSON へ束ねる。site は billings/transactions(per-billing)/customer-name/lookback を区別し、月コンテキスト (`curr`/`prev`/`lookback[YYMM]`) で束ねる。この `fetch_trace` を `scripts/mfk_fetch_audit.py --fetch-trace <path> --target <YYMM>` へ渡して監査し、その出力 (fidelity report) を C03 の `--fidelity-report` へ渡す。監査 exit1 (当月/先月 pagination/total/issue_date NG または trace 完全不在) は fail-closed で漏れ確認処理を実行しない。exit3 (lookback 部分欠損) は該当行を要確認へ降格する (全停止しない)。legacy な `pagination.total` 破棄経路 (trace 皆無) は fidelity violation として通さない。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --target | string(YYMM) | no | 今月=対象月 (例 `2606`)。省略時は実行日から直近締め済み月を導出。YYMM 不正は fail-closed |

### 2.4 出力契約
- R1 単体の成果物: R2 (C03) が読む入力ファイル一式 = per-月 verdict JSON (`curr-verdicts`/`prev-verdicts`/任意 `lookback-12mo`/`contract-end`) **+ C06 fetch fidelity report JSON (`fidelity-report`)**。verdict JSON は per-月 verdict 行の list もしくは `{"rows":[...]}` 形 (C03 の `_rows_of` が受ける形)。
- **`fidelity-report` は R2 の必須入力**: `mfk_fetch_audit.py` が `fetch_trace` を監査した exit_code 付き JSON で、R2 が `--fidelity-report` へ必ず渡す (これを R1 が用意しないと R2 が argparse exit 2 でレポートを一切出さない=準拠経路が停止する)。
- 画面には対象月 (今月/先月) と収集件数サマリ (`[collect] 今月=YYMM 先月=YYMM / MF顧客 N社 / 差分該当 N社 12ヶ月遡り`) を出す。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| api lib | `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` | GET 専用 API クライアント (`iter_all` / `get`) |
| reconcile engine | `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` | per-月 verdict 供給 (`build_mf_index` / `reconcile`) + 突合キー正規化 (`normalize` / `extract_names`) |
| classify engine | `$CLAUDE_PLUGIN_ROOT/scripts/mfk_period_report.py` | 対象月決定規約 (`resolve_target_months`) と入力キー契約の確認 |
| api spec | `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` | エンドポイント・判定仕様の正本 |

### 3.2 外部ツール / API
- MF掛け払い API (GET のみ。変更系は hook `guard-mfk-readonly.py` で遮断)。
- Notion REST (請求確認シート read = 契約終了月収集。GET のみ)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `--target` が YYMM 不正なら exit 2 (fail-closed)。
- API エラー (HTTP / 接続 / ページング異常) は stderr に出し、部分取得のまま入力 JSON を確定しない。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に対象月 (今月/先月) と MF顧客数・差分該当取引先数・12ヶ月遡り対象数のサマリ。

### 4.3 セキュリティ
- GET のみ。secret は Keychain 参照のみで平文出力しない。取引先データを外部送信しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- collect 実行 (決定論 lib / GET 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 対象月を正しく決定し、前月/今月の MF発行実績と per-月 verdict、差分該当取引先の 12 ヶ月履歴、契約終了月を漏れなく集め、C03 が消費する入力 JSON を揃える。
- 背景: 対象月の取り違え (実行日カレンダー月を今月にする等) や 12 ヶ月全件遡りは、分類の腐敗・API 過負荷を招く。対象月決定は C03 規約に、遡りは差分該当のみに機構で固定する。
- 達成ゴール: `curr-verdicts`/`prev-verdicts`/(必要時)`lookback-12mo`/`contract-end` の JSON が用意され、per-月 verdict が既存 engine の出力そのままで、突合キーが `normalize`/`extract_names` で正規化された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 対象月 (今月=直近締め済み請求対象月・先月=その1ヶ月前) を `resolve_target_months` 規約で決定した
- [ ] 前月・今月の全取引先 MF発行実績を全ページ GET し per-月 verdict を既存 `mfk_reconcile` engine で収集した (再照合・再パースなし)。この GET は `lib/mfk_api` の `trace_sink` 経由で行い各ページの pagination metadata を落とさず `fetch_trace` JSON へ束ねた (site=billings/transactions/customer-name/lookback・月コンテキスト curr/prev/lookback[YYMM] で区別)
- [ ] 取引先×商品で状態遷移を抽出し、差分に現れた**該当取引先のみ** 12 ヶ月分の発行履歴を **MF API (transaction.date 履歴) から** 追加取得した (全件遡らない・請求確認シートの開始月を理由に省略しない。MF実績自体が無いときのみ源を明示して省略)
- [ ] 請求確認シート由来の契約終了月を収集した (二次情報・`contract-end` JSON)
- [ ] 突合キーを `mfk_reconcile.normalize`/`extract_names` で正規化した (自作正規化なし)
- [ ] `fetch_trace` を `mfk_fetch_audit.py --fetch-trace <path> --target <YYMM>` で監査し **fetch fidelity report JSON を生成**した (R2 の `--fidelity-report` 必須入力。exit1=当月/先月 NG は後段が fail-closed 非emit・exit3=lookback 部分欠損は要確認降格)
- [ ] R2 (C03) が読む入力一式 (`curr-verdicts`/`prev-verdicts`/**`fidelity-report`**/任意 lookback/contract-end) を組み R2 へ渡せる状態にした
- [ ] POST 等変更系を一切呼んでいない (GET のみ)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (対象月決定 / GET / verdict 収集 / 遡り絞り込み / JSON 組み立て)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-report` SKILL Step 1 (collect)。
- 後続 phase: R2 (classify=C03) が同一実行内で続く。

### 6.2 ハンドオフ / 並列性
- 提供元: ユーザー (`--target`) / MF API / 請求確認シート / 既存 reconcile engine (per-月 verdict)。
- 受領先: R2 classify (`mfk_period_report.py` の `--curr-verdicts`/`--prev-verdicts`/`--fidelity-report` (必須)/`--lookback-12mo`/`--contract-end`)。
- 引き渡し形式: JSON ファイル群。per-月 verdict 行の list か `{"rows":[...]}`。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に対象月 (今月/先月) と収集件数サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

まず対象月を決定する。`--target YYMM` があればそれを今月とし、無ければ `mfk_period_report.resolve_target_months` の規約 (今月=実行日カレンダー月の前月=直近締め済み請求対象月・先月=その1ヶ月前) で導出する。例: 2026-07-02 実行 → 今月=`2606`・先月=`2605`。

前月・今月の全取引先 MF発行実績を `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` で参照専用 GET する。この GET は `lib/mfk_api` の `get_with_trace`/`iter_all` の `trace_sink` 経由で行い、各ページの pagination metadata (`has_next`/`end`/`total`/`items_count`/`params`) を落とさず `fetch_trace` JSON へ束ねる (site=billings/transactions/customer-name/lookback を区別し月コンテキスト curr/prev/lookback[YYMM] で束ねる)。当月/先月の `collect_mf` raw JSON (`{customers:...}`) と請求確認シート行 JSON を用意する。**per-月 verdict の直列化は LLM が手組みせず、決定論 producer `$CLAUDE_PLUGIN_ROOT/scripts/mfk_verdict_export.py` (C05) に委譲する** (LLM 手動直列化が発行済み社の当月行を落とし curr=None を生む構造的主因の根治)。この producer は既存 `lib/mfk_reconcile.reconcile()` を当月/先月で実行し、`classify()` が全 contract へ状態問わず1行返す性質を利用して **rows 全件 (GAP/SUPPRESS 含む) + orphans** を MF実績 carrier 込みで無損失に直列化する (再照合・再パースをしない):

```
python3 "$CLAUDE_PLUGIN_ROOT/scripts/mfk_verdict_export.py" \
  --sheet <請求確認シート行 JSON> \
  --mf-curr <当月 collect_mf raw JSON> --mf-prev <先月 collect_mf raw JSON> \
  --target <YYMM> --out-curr curr-verdicts.json --out-prev prev-verdicts.json
```

producer は全 row の carrier (`actual_amount`/`reliable_issued`/`supply_state`/`canceled_at`) 存在を直列化前に検証し、欠落があれば exit 1 (fail-closed) で curr=None / 過少報告方向の退行を止める。**contract 由来の行は必ず出るため curr=None は構造的に起きない** (発行済み社の当月 MATCH 行を落とさない)。MF実績はあるがマスタ未登録の請求は `orphans` (要マスタ登録) へ分離され、curr=None ではなく可視の逆方向行として保持される。突合キー正規化は producer が呼ぶ `mfk_reconcile.normalize`/`extract_names` に委ねる。

次に取引先×商品で状態遷移 (今月あり×前月あり / 今月あり×前月なし / 今月なし×前月なし / 今月なし×前月あり) を抽出し、差分に現れた**該当取引先のみ** 12 ヶ月分の発行履歴を追加 GET する (全件遡らない=API 負荷最小化)。**STATE_NEW (前月なし今月あり) 候補が 1 件以上あるなら 12ヶ月ルックバックを必須 fetch し `--lookback-12mo` へ渡す** (D1・C3 の年→月切替裏付け)。請求確認シートを read-only GET して契約終了月を収集する (二次情報・任意 `contract-end`)。

取得の最新性を担保するため、束ねた `fetch_trace` を `python3 "$CLAUDE_PLUGIN_ROOT/scripts/mfk_fetch_audit.py" --fetch-trace <fetch_trace.json> --target <YYMM>` で監査し、その出力 (fetch fidelity report JSON・exit_code 付き) を保存する。**これは R2 (`mfk_period_report.py`) の `--fidelity-report` 必須入力であり、R1 が用意しないと R2 が argparse exit 2 でレポートを一切出さない** (準拠経路が停止する)。監査 exit1 (当月/先月の pagination/total/issue_date NG または trace 皆無) は fail-closed で R2 が漏れ確認を非emit、exit3 (lookback 部分欠損) は STATE_NEW 該当行を要確認へ降格する (全停止しない)。

producer が出力した `curr-verdicts.json` / `prev-verdicts.json` と、監査で得た fidelity report を C03 (`mfk_period_report.py`) が読む。各行は C03 が消費するキー (`verdict`/`customer`/`product`/`contract_id`/`エンドクライアント名`/`evidence`/金額/canon 前の生商品名) と MF実績 carrier (`actual_amount`/`reliable_issued`/`supply_state`/`canceled_at`) を保持する (producer が保証)。

Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。GET のみ (変更系を一切呼ばない)。出力は対象月と収集件数サマリのみ、前置き禁止。
