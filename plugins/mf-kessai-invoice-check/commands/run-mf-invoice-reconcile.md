---
name: run-mf-invoice-reconcile
description: 請求確認シートを基準にMF掛け払いの発行漏れと契約マスタ未登録を双方向照合したいとき、月次で発行網羅性を検証し記録を残したいときに使う。
argument-hint: "[--target YYMM] [--apply --verified] [--steps collect,sync-master,reconcile,sink]"
allowed-tools: Read, Write, Bash, Skill
entrypoint: run-mf-invoice-reconcile
---

# /run-mf-invoice-reconcile

`$ARGUMENTS` を `run-mf-invoice-reconcile` スキルに渡し、請求確認シート (年月/取引先/商品/確認内容) を基準に MF 掛け払いの当月発行実績を双方向照合する。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-invoice-reconcile`。

## 振る舞い

1. `Skill(run-mf-invoice-reconcile, args="$ARGUMENTS")` を呼ぶ。
2. 既定は **dry-run** (集計のみ・書き込みゼロ)。collect→sync-master→reconcile を回し、発行漏れ/金額差/対象外/要マスタ登録 (orphan) の判定内訳を提示する。
3. 独立 context の `mfk-reconcile-verifier` で二段確認したのち、`--apply --verified` を付けたときだけ DB1 契約マスタ・DB2 月次チェックへ非破壊 upsert し、請求確認シートへ判定/AI確認/確認ポイントを書き戻す。
4. DB id (sheet_db/db1/db2) 未設定は fail-closed (exit 2)。`.mf-kessai-config.json` か引数で指定する。

## 実行コード

スラッシュが使えない環境では、プラグイン配下の orchestrator を直接実行する (既定 dry-run)。

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/reconcile_invoices.py" --target 2606
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/reconcile_invoices.py" --target 2606 --apply --verified
```
