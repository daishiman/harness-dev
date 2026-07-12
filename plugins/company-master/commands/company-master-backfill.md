---
name: company-master-backfill
description: 固定 Notion 企業マスタ DB の空欄列・要確認行だけを再取得対象にして backfill する。
argument-hint: "[--dry-run] [--web-findings <json>] [--migrate-company-title]"
allowed-tools: Read, Bash, Skill
entrypoint: run-company-master-backfill
---

# /company-master-backfill

固定 Notion 企業マスタ DB を既定の対象として、空欄列または `ネット検索(要確認)` / `未確定(要確認)` の行だけを補完対象にする。
Marketplace から install した場合の呼び出し名は通常 `/company-master:company-master-backfill`。

## 振る舞い

1. Notion token と gBizINFO token が Keychain にあることを fail-closed で確認する。
2. 既存非空セルは上書きしない。
3. 取得不能な項目は備考の定型文言と、ネット検索由来値はページ本文の確認用URLセクションで監査できる状態にする。
4. `--dry-run` 指定時は副作用を抑えて対象選定だけ確認する。
5. **2 パス運用 (Web 検索が必要な行)**: 1 パス目の出力 `needs_web_search` (page_id + `missing_fields` + `attempts`) が Claude 介入リスト。許可段ホワイトリスト (`data-sources.md` fallback tier 表) 内で Web 検索し、`attempts` に無い `(source, pattern)` のみ試行のうえ `--web-findings` で再投入する。

## 実行コード

```bash
# 1 パス目: 対象選定 + Claude 介入リスト (needs_web_search) の確認
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" backfill --dry-run

# 2 パス目: Web 検索結果 (page_id キーの属性別候補マップ) を再投入
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" backfill \
  --web-findings '{"<page_id>": {"phone": {"value": "03-1234-5678", "source_url": "https://..."}}}'
```
