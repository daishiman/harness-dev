---
name: run-mf-invoice-report
description: 前月↔今月のMF掛け払い発行状況を比較して漏れレポートを手動起動したいとき、2営業日目以降に何度でも冪等再実行して専用DBへ上書きしたいときに使う。
argument-hint: "[--target YYMM] [--apply --verified]"
allowed-tools: Read, Bash, Skill
entrypoint: run-mf-invoice-report
---

# /run-mf-invoice-report

`$ARGUMENTS` を `run-mf-invoice-report` スキルに渡し、MF 掛け払いの**前月↔今月の請求書発行状況を突合**して発行漏れ比較レポートを生成する。今月=直近締め済みの請求対象月 (例 2026-07-02 実行なら 2026-06 分=`2606`)、先月はその 1 ヶ月前 (`2605`)。2 営業日目以降に何度でも冪等再実行でき、指定見出しに紐づく単一恒久レポート DB へ日々追加 (非破壊マージ) する。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-invoice-report`。

## 振る舞い

1. `Skill(run-mf-invoice-report, args="$ARGUMENTS")` を呼ぶ。
2. 既定は **dry-run** (分類・集計のみ・Notion 書き込みゼロ)。collect→classify を回し、継続発行/新規・年→月切替/対象外/発行漏れ候補の判定内訳を提示する。
3. 独立 context の `mfk-report-verifier` で二段確認 (真の発行漏れを『問題ない』と誤って隠していないかの差し戻し) したのち、`--apply --verified` を付けたときだけ単一恒久レポート DB へ 8 列行を非破壊冪等 upsert する。
4. **Design D**: 出力先は指定見出し (`notion.report_toggle_block`・トグル見出しでもプレーン見出し2でも可) に紐づく単一の恒久レポート DB。sink は (1)見出しがトグルなら配下の DB → (2)プレーン見出しなら直下 (ページ兄弟・次セクション手前まで=重複と区別) → (3)ページ直下の既存 DB → (4)見出しの下へ新規作成、の順で解決し、複数月を `対象月` 列付きで非破壊 upsert する。Notion API は database を block_id 親で『作成』できないが、UI で作られた見出し配下/直下の DB の『更新』はできるため、その DB をそのまま更新する。config は配布既定に焼き込み済みで設定不要。別ワークスペース/別ページへ出す場合のみ `.mf-kessai-config.json` で上書き。`report_parent_page` を空にすると `--apply` 時 fail-closed (exit 2)。
5. **月次アーカイブ&ロールオーバー (C07・R5・自動連鎖)**: 手順 3 の `--apply --verified` upsert が成功した後に**常に自動**で `mfk_sheet_archive.py --target <YYMM> --apply --verified` を走らせ、対象月 (`年月` select==YYMM) の請求書確認シート (`notion.sheet_db_id`) 行を、シートと同じ親ページ配下の月別 DB『請求書確認シートYYMM』へ**全プロパティ完全移行** (元ページID冪等・API 非対応型は rich_text 降格で値温存・長文は chunk 全文保持) し、写像先の読み戻し検証に通った行だけ元シートを Notion archive (in_trash・30日復元可) する=月次ロールオーバー。正本削除は (a) `--verified` 機械ゲート (未指定 exit 2)、(b) verify-then-delete で不一致行は温存、(c) 削除=archive で可逆、の三重に安全化。冪等ゆえ再実行は重複 0・archive 済みは no-op (crash-safe)。**レポートが dry-run のときは R5 も dry-run** で「N 行を『請求書確認シートYYMM』へ移行し検証後に削除します」の移行プレビューのみ (書き込みゼロ)。写像先 DB は Notion API 制約で page_id 親のみ作成可 (親解決順=`--parent-page-id`>env `MFK_ARCHIVE_PARENT_PAGE_ID`>config `notion.archive_parent_page`>シート親>`report_parent_page`)。

## レポート列 (8 列・金額は税抜)

生成 DB は次の 8 列を持つ (**金額は税抜**)。継続発行 (今月あり×前月あり) も正常として全行 emit し (漏れチェック=✓)、真の発行漏れ (継続漏れを含む) だけが「漏れチェック=☐ (要対応)」に残る。

列は左→右の順で確定する (取引先名=title を先頭に置き Notion の title 最左固定と定義順を一致させる)。

| 列 | 型 | 内容 |
|---|---|---|
| 取引先名 | title | Notion のページ名 (= 各行)。Notion table view は title を最左固定で描画するため先頭に置く |
| 対象月 | rich_text | 対象月 YYYY-MM。単一 DB で複数月を区別する |
| 漏れチェック | checkbox | ✓ (チェックあり) = 正常 / ☐ (チェックなし) = 要対応 (発行漏れ候補)。チェックの有無で直感的に判別 |
| 商品名 | rich_text | 対象商品 |
| 先月の金額 | number(税抜) | 先月分の税抜金額 (停止/契約完了行は空) |
| 今月の金額 | number(税抜) | 今月分の税抜金額 (新規/継続漏れ行は空のことがある) |
| 先月と今月の比較 | rich_text | 状態ラベル (継続発行 / 新規・年→月切替 / 契約完了 / 継続 等) |
| コメント | rich_text | 年契約・契約終了・トライアル完了などの正常事情、または要対応の根拠 |

## 実行コード

スラッシュが使えない環境では、プラグイン配下の fetch fidelity 監査 (C06) → 分類エンジン (C03) → sink (C04) → 月次アーカイブ (C07) を直接実行する (既定 dry-run)。C03 の `--target-month` と C06/C04/C07 の `--target` は必ず同じ対象月 (YYMM) を渡すこと。ズレていると sink が誤月行の投入を防ぐため fail-closed (exit 2) で中止する。分類 (C03) は C06 の fetch fidelity report を `--fidelity-report` で必須受領し (欠くと argparse が exit 2)、当月/先月の fetch NG は fail-closed で非 emit・lookback 部分欠損は要確認降格する。C07 は C04 の `--apply --verified` upsert が成功した後にだけ `--apply --verified` で走らせる (レポートが dry-run なら C07 も dry-run)。

```bash
# 1) fetch fidelity 監査 (最新性の fail-closed ゲート)。fetch-trace は R1 collect が GET 時に記録する
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/mfk_fetch_audit.py" \
  --fetch-trace fetch-trace.json --target 2606 --out fidelity.json

# 2) 前月↔今月分類 (参照専用・dry-run)。curr/prev の per-月 verdict と fetch-trace は R1 collect が組む
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/mfk_period_report.py" \
  --curr-verdicts curr.json --prev-verdicts prev.json --fidelity-report fidelity.json \
  --lookback-12mo lookback.json --contract-end ends.json --target-month 2606 > rows.json

# 3) 単一恒久レポート DB へ非破壊冪等 upsert (--apply --verified で書き込み)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/notion_report_sink.py" \
  --rows rows.json --target 2606                # dry-run (計画のみ・書き込みゼロ)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/notion_report_sink.py" \
  --rows rows.json --target 2606 --apply --verified   # report DB へ upsert (日々追加・非破壊)。--verified 必須 (未指定は exit2)

# 4) 月次アーカイブ&ロールオーバー (R5・手順3の --apply --verified 成功後に常に自動連鎖)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/mfk_sheet_archive.py" \
  --target 2606                                 # dry-run (移行プレビューのみ・書き込みゼロ)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/mfk_sheet_archive.py" \
  --target 2606 --apply --verified              # 対象月シート行を『請求書確認シート2606』へ完全移行→検証→検証成功行だけ元シート削除。--verified 必須 (未指定は exit2)
```
