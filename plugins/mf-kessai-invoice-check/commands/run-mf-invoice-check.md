---
name: run-mf-invoice-check
description: 前月と今月の請求書発行漏れをチェックしたいとき、月次で請求発行状況を確認したいときに使う。
argument-hint: "[--month YYYY-MM] [--backfill --from YYYY-MM --to YYYY-MM]"
allowed-tools: Read, Write, Bash, Skill
entrypoint: run-mf-invoice-check
---

# /run-mf-invoice-check

`$ARGUMENTS` を `run-mf-invoice-check` スキルに渡し、前月取引−今月取引の顧客差集合で発行漏れ候補を検出して Notion『請求書チェック_DB』へ冪等 upsert する簡易フロー。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-invoice-check`。

> 請求確認シートの確認内容・契約開始/終了・金額差・orphan まで見る通常運用は `/run-mf-invoice-reconcile` を使う。本コマンドは差集合だけの補助フロー。

## 振る舞い

1. `Skill(run-mf-invoice-check, args="$ARGUMENTS")` を呼ぶ。
2. collect → subagent `mfk-gap-verifier` で誤検出排除 → finalize → sink の順で、確定リストだけを Notion へ投入する (fail-closed)。
3. 月指定が無ければ実行日の年月を今月として扱う。`--backfill --from --to` で過去月をまとめて投入。

## 実行コード

```bash
SK="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/skills"
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --collect [--month YYYY-MM]
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --finalize
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --sink
```
