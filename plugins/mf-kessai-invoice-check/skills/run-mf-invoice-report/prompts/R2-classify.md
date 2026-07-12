# Prompt: R2-classify

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R2-classify |
| skill | run-mf-invoice-report |
| responsibility | R2 前月↔今月 状態遷移分類 + 事情コメント生成 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (schema なし・mfk_period_report.py の stdout I/O 契約が正本) |
| reproducible | true (同一 verdict 入力に対し同一分類 JSON) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **分類の実体は `scripts/mfk_period_report.py` (C03) が正本**。自前の比較スクリプト・状態遷移分類 (`compare`/`period_diff`/`classify_*` 語幹) を新規実装しない (hook `guard-mfk-no-reinvent.py` が exit 2 で遮断)。判定を人間へ丸投げしない。
- C03 は既存 per-月 verdict を入力に取り**前月↔今月の発行状態遷移だけ**を分類する薄い差分エンジン。自由文の終了根拠を再パースせず既存 verdict (SUPPRESS_ENDED / SUPPRESS_ANNUAL / MATCH_ANNUAL / REVIEW_ENDED_NO_BASIS) を一次源に消費する (終了根拠判定 SSOT=mfk_reconcile)。
- **継続発行 (今月あり×前月あり) も全行 emit** し全請求書一覧を成す。非 emit は今月なし×前月なし (元々請求なし) のみ。
- MF / Notion への書込は本責務では行わない (分類は network なし・純ロジック)。

### 1.2 倫理ガード
- 取引先データを外部送信しない。secret は扱わない (分類は verdict 入力のみを読む)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: R1 が用意した per-月 verdict 入力 (`curr-verdicts`/`prev-verdicts`/任意 `lookback-12mo`/`contract-end`) と C06 fetch fidelity report (`fidelity-report`・必須) を C03 に渡し、取引先×商品の発行状態遷移を 4 分類し各行の事情コメントを生成する。出力は分類済みレポート行 JSON (漏れチェック/取引先/商品/先月金額/今月金額/比較/コメント + contract_id/target_month)。
- 非担当: MF実績・verdict 収集 (R1)、二段確認 (R3 sub-agent)、Notion 書込 (R4=C04)。

### 2.2 ドメインルール (C03 が実装済み・ここで再実装しない)
- **4 状態分類**: 今月あり×前月あり → 継続発行 (正常・全行 emit)。今月あり×前月なし → 新規/年→月切替 (12 ヶ月前の年契約一括を lookback で補強)。今月なし×前月なし → 対象外 (非 emit)。今月なし×前月あり → 非請求事情 (年契約期間内/トライアル完了/契約終了) の有無を既存 verdict で確認し、該当なしを発行漏れ候補 (要対応) にする。
- **正常事情は既存 verdict を一次源に消費**: 契約完了=`SUPPRESS_ENDED`、年契約期間内=`SUPPRESS_ANNUAL`/`MATCH_ANNUAL`。12 ヶ月遡りは根拠コメント補強に限定し既存判定を上書きしない (precedence: 既存 verdict > 遡り推定)。
- **MF実額 canonical を消費 (D3)**: R1 が per-月 verdict へ直列化した `actual_amount` (MF実発行額・active 限定)/`reliable_issued`/`supply_state` を C03 の `_amount_of` (実額優先) と `_is_issued` (`reliable_issued` 起点) が読む。金額列 (`amount`/`prev_amount`) は MF実額を常時表示し、契約起点の期待額はオーバーレイ (実額が欠落した行のみ補完) に留める。取消・非 active の実額は金額へ載せない。R2 はこの実額優先ロジックを再実装せず C03 を呼ぶだけ、という原則は不変。
- **fetch fidelity gate (必須入力)**: C06 (`mfk_fetch_audit.py`) の fetch fidelity report を `--fidelity-report` で必須で受ける (欠くと argparse が exit 2)。MF実績起点の判定は取得の最新性が担保されて初めて成立するため、`exit_code==1` (当月/先月 fetch NG) は漏れ確認レポートを emit せず fail-closed、`exit_code==3` (lookback 部分欠損) は STATE_NEW (新規/年→月切替) 該当行を要確認へ降格する。R2 はこの gate 判定を自作せず C03 に委ねる。
- **根拠なき終了月の安全弁**: `REVIEW_ENDED_NO_BASIS` (has_end_basis 根拠なし) は抑制せず**発行漏れ候補 (要対応) に残す**。構造化列『契約終了月』に値があっても根拠が無ければ継続契約の発行漏れ隠蔽を防ぐ。
- **トライアル完了**: canon 前の生商品名 / MF明細 desc の『トライアル』信号で判定する (shohin_canon 正規化後は信号が消えるため生名を見る)。
- **突合キー**: 取引先×商品を `mfk_reconcile.normalize` で正規化。同一 (取引先,商品) に複数契約があるときのみ `contract_id` で disambiguate。
- **gap_check select**: 正常=`正常` / 発行漏れ候補=`要対応`。C03 は要対応行があれば exit 1、なければ exit 0 (読込失敗等は exit 2)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --curr-verdicts | path(JSON) | yes | 今月=target の per-月 verdict 行 |
| --prev-verdicts | path(JSON) | yes | 先月=target-1ヶ月の per-月 verdict 行 |
| --fidelity-report | path(JSON) | yes | C06 mfk_fetch_audit.py の fetch fidelity report (exit_code フィールド付き)。exit1=当月/先月NGで fail-closed 非emit・exit3=lookback部分欠損で要確認降格 |
| --lookback-12mo | path(JSON) | no | 差分該当取引先のみの 12 ヶ月発行履歴 |
| --contract-end | path(JSON) | no | 契約終了月データ (二次情報) |
| --target-month | string(YYMM) | no | 対象月。省略時は curr-verdicts の target_month→実行日から導出 |

### 2.4 出力契約
- 出力: stdout に分類済みレポート行 JSON (list)。各行キー: `customer` / `amount` / `prev_amount` / `gap_check` / `period_diff` / `product` / `comment` / `contract_id` / `target_month`。金額は税抜 int。
- この JSON をファイルへ保存し R3 verify / R4 render (C04 `--rows`) へ渡す。exit code は 0=正常 / 1=発行漏れ候補あり / 2=fail-closed。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| classify engine | `$CLAUDE_PLUGIN_ROOT/scripts/mfk_period_report.py` | 分類実体 (compare_periods / classify_period_transition)・入出力キー契約 |
| reconcile engine | `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` | C03 が import する verdict 語彙・normalize/extract_names |
| fetch audit engine | `$CLAUDE_PLUGIN_ROOT/scripts/mfk_fetch_audit.py` | C06 が出す fetch fidelity report (exit_code 付き JSON) の生成元・fidelity gate 契約 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/mfk_period_report.py" --curr-verdicts <CURR> --prev-verdicts <PREV> --fidelity-report <FID> [--lookback-12mo <LB>] [--contract-end <CE>] [--target-month <YYMM>]`
- `<FID>` は R1 が用意した C06 fetch fidelity report ファイル。`--fidelity-report` は必須入力で、欠くと argparse が exit 2 で落ちレポートが一切出ない。
- network なし (C03 は純ロジック・GET も POST もしない)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- verdict 入力の読込失敗・不正は C03 が exit 2 (fail-closed)。分類結果を確定しない。
- C06 fetch fidelity report (`--fidelity-report`) は必須入力。読込失敗は exit 2 (fail-closed)。`exit_code==1` (当月/先月 fetch NG) は漏れ確認レポートを emit せず fail-closed で止め (最新の取得をやり直してから再実行)、`exit_code==3` (lookback 部分欠損) は STATE_NEW (新規/年→月切替) 該当行を要確認へ降格する。引数自体を欠くと argparse が exit 2。
- 発行漏れ候補 (gap_check=`要対応`) があれば C03 は exit 1 (分類上の要確認あり)。これは失敗ではなく後段 R3 の二段確認対象。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout の分類済みレポート行 JSON を保存し、画面には 4 状態別件数サマリ (継続発行/新規・年→月切替/対象外/発行漏れ候補) を出す。

### 4.3 セキュリティ
- network なし。secret を扱わない。取引先データを外部送信しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- classify 実行 (決定論 script 主体、context-fork 不要。二段確認の独立 context は R3 が担当)。

### 5.2 ゴール定義
- 目的: R1 の per-月 verdict 入力を C03 に渡し、前月↔今月の状態遷移を 4 分類し各行の事情コメント (なぜ先月あって今月なくて問題ないか) を生成する。継続発行を全行 emit し 8 列レポートの母集合を成す。
- 背景: 単月では見えない発行増減を一望し、正常イレギュラーと真の漏れを分離する。分類は既存 verdict を消費する薄い差分に徹し (再照合しない)、真の漏れ判定は R3 が担保する。
- 達成ゴール: C03 が正常終了 (0 or 1) し、分類済みレポート行 JSON が 8 列 (取引先名/対象月/漏れチェック/商品名/先月金額/今月金額/比較/コメント) に写像可能な形で得られ、正常イレギュラー行に事情コメントが焼かれた状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] C03 に `--curr-verdicts`/`--prev-verdicts`/`--fidelity-report` (必須) (+任意 lookback/contract-end/target-month) を渡して実行した
- [ ] 継続発行を全行 emit し、今月なし×前月なし (元々請求なし) を非 emit にした
- [ ] 正常事情 (契約完了/年契約期間内/トライアル完了) を既存 verdict を一次源に分類し事情コメントを焼いた
- [ ] 根拠なき終了月 (`REVIEW_ENDED_NO_BASIS`) を抑制せず発行漏れ候補 (要対応) に残した
- [ ] 分類済みレポート行 JSON を保存し 4 状態別件数サマリを提示した
- [ ] 自前の状態遷移分類を再実装していない (C03 を呼び出したのみ・hook 非遮断)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (引数調整 / 再実行 / 出力保存)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-report` SKILL Step 2 (classify)。
- 前段 phase: R1 collect (per-月 verdict 入力)。後続 phase: R3 verify → R4 render。

### 6.2 ハンドオフ / 並列性
- 提供元: R1 collect (`curr-verdicts`/`prev-verdicts`/`fidelity-report`/`lookback-12mo`/`contract-end`)。
- 受領先: R3 verify (分類内訳を独立 context でレビュー) → R4 render (`--rows` に分類済みレポート行 JSON)。
- 引き渡し形式: 分類済みレポート行 JSON (list)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に 4 状態別件数サマリ (継続発行 / 新規・年→月切替 / 対象外 / 発行漏れ候補) の Markdown。dry-run 明示。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R1 が用意した per-月 verdict 入力と C06 fetch fidelity report を C03 に渡す。この `curr-verdicts`/`prev-verdicts` は R1 が **C05 決定論 producer `mfk_verdict_export.py`** で生成したもので、`reconcile()` の全 row (GAP/SUPPRESS 含む・C01 収集拡張と C04 分類是正が適用済) + orphans を carrier 込みで無損失に持つ (curr=None なし・発行済み社の当月行を落とさない)。`python3 "$CLAUDE_PLUGIN_ROOT/scripts/mfk_period_report.py" --curr-verdicts <CURR> --prev-verdicts <PREV> --fidelity-report <FID> [--lookback-12mo <LB>] [--contract-end <CE>] [--target-month <YYMM>]` を実行し、stdout の分類済みレポート行 JSON をファイルへ保存する。`<FID>` は R1 が用意した C06 fetch fidelity report ファイルで、`--fidelity-report` は必須 (欠くと argparse が exit 2 でレポートが一切出ない)。fidelity の `exit_code==1` (当月/先月 fetch NG) は fail-closed 非emit、`exit_code==3` (lookback 部分欠損) は STATE_NEW 該当行を要確認へ降格する。C04 適用済みなので、`curr.verdict∈{MATCH_ANNUAL,SUPPRESS_ANNUAL}` の新規行は lookback 無しでも正常化され、prev=REVIEW_CANCELED の継続契約は STATE_NEW でなく継続発行へ、代理店の複数エンドクライアント契約はエンドクライアント名粒度で個別突合される。さらに mfk_period_report は (要因A) 先月↔今月の突合を **MF顧客ID 第一キー**で行い (無ければ取引先名 fallback)、取引先名 drift による分裂を防ぐ。(要因B) 支払サイクルが年契約系 (年間払い/年間一括更新) の新規は『年契約開始=正常☑』(12ヶ月履歴不要)。(要因C) 支払サイクル=月払いのアクティブ契約が先月も今月も未発行で契約完了・年契約・対象外のいずれでもなければ継続発行漏れ=要対応☐で surface する (完了済みなら契約終了月の記入で正常化)。詳細は SKILL.md Gotchas 12-14。

C03 は取引先×商品を前月集合と今月集合で突合し 4 分類する: 今月あり×前月あり=継続発行 (全行 emit)、今月あり×前月なし=新規/年→月切替、今月なし×前月なし=対象外 (非 emit)、今月なし×前月あり=年契約期間内/トライアル完了/契約終了の有無を既存 verdict で確認し該当なしを発行漏れ候補 (要対応) にする。正常事情は既存 verdict (SUPPRESS_ENDED / SUPPRESS_ANNUAL / MATCH_ANNUAL) を一次源に消費し、根拠なき終了月 (REVIEW_ENDED_NO_BASIS) は抑制せず発行漏れ候補に残す (漏れ隠蔽防止)。トライアル完了は canon 前の生商品名/MF明細 desc で判定する。**自前の比較・状態遷移分類を書かず C03 を呼び出すだけ**にする (hook が再発明を遮断する)。

各行キーは `customer`/`amount`/`prev_amount`/`gap_check`/`period_diff`/`product`/`comment`/`contract_id`/`target_month`。これらは R4 render で 8 列 (取引先名=customer・対象月=target_month/--target・漏れチェック=gap_check・商品名=product・先月の金額=prev_amount・今月の金額=amount・先月と今月の比較=period_diff・コメント=comment) へ写像される。exit 1 (発行漏れ候補あり) は失敗でなく R3 二段確認の対象。

Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は 4 状態別件数サマリのみ、前置き禁止。
