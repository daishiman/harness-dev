---
name: company-master-notion-upsert
description: 補完済み企業レコードを固定 Notion 企業マスタ DB へ法人番号キーで安全に upsert/backfill したいときに使う。
tools: Read, Bash(python3 *)
model: haiku
kind: agent
version: 0.1.0
owner: harness maintainers
since: 2026-06-10
---

## Purpose

enrich 済みレコードを固定 Notion 企業マスタ DB へ安全に反映する純決定論 SubAgent。DB ID は `notion_config.get_db_id('company-master')` で解決し、法人番号が確定している行だけ upsert キーとして突合する。既存非空セルは上書きせず、法人番号未確定行は代替キーで新規追記のみとし既存行を誤更新しない。

本 agent は『Notion 反映処理を親セッションから fork する境界 + 親へ返す要約契約』を担う。upsert ロジックの実体 (DB ID 解決・法人番号キー突合・既存非空セル保護・新規追記判定) は決定論で `../scripts/notion_upsert.py` にある。決定論処理のため LLM 判断ループを持たず、対応する7層 prompt も持たない (判断ロジックは決定論 script が正本)。

## Inputs

- 上流 (`company-master-enrich-attributes`) からの補完結果 JSON: `fields` / `certainty_by_field` / `overall_certainty` / `remarks_text` / `source_by_field`。`source_urls` は `source_by_field` から導出される legacy/派生値で、正入力として扱わない。
- 実行スクリプト: `../scripts/notion_upsert.py` (DB ID 解決・キー突合・7列upsert(会社名title=正式名称優先)・確認用URL本文同期)、`../scripts/confirm_url.py` (確認用URL本文テンプレート展開)、`../scripts/notion_config.py` (DB ID/token 解決の vendored SSOT)、`../scripts/backfill.py` (空欄列補完経路)
- 参照: `../references/company-master-columns.md` (7列定義+確認用URL本文)、`../references/confirm-url-template.md` (確認用URL本文テンプレートの正本)、`../references/README-setup.md` (Notion/gBizINFO 必須鍵、日本郵便任意鍵、upsert 挙動)

## Outputs

- 親セッションへ返す反映結果 JSON (構造化)

出力 JSON 雛形:

```json
{
  "action": "created",
  "page_id": "abcd1234-...",
  "key": "1234567890123",
  "next_agent": null
}
```

`action` は実装 (`notion_upsert.py`) の戻り値に合わせて `created | updated | skipped | rejected` のいずれか。

## ゴールシーク実行
<!-- 固定手順を書かない。Goal+Checklist を宣言し、手順は実行時に都度生成する。詳細: run-build-skill references/goal-seek-paradigm.md -->

### ゴール (Goal)

補完済みレコードが固定 Notion 企業マスタ DB へ、法人番号確定行は upsert・未確定行は新規追記で反映され、既存非空セルを破壊せず page_id/action/key が確定した状態。

### 完了チェックリスト (Checklist)

- [ ] 入力レコード (`Inputs`) を検証した
- [ ] DB ID を `notion_config.get_db_id('company-master')` で解決した (リテラル直書きなし)
- [ ] Notion token を Keychain `notion-api-key.<keychain-prefix>` から解決した
- [ ] 法人番号が確定している場合のみ upsert キーとして突合した
- [ ] 法人番号未確定行は代替キーで新規追記のみとし既存行を更新しなかった
- [ ] 既存非空セルを上書きしなかった
- [ ] 出力 (`Outputs`) が JSON 契約 (`action`/`page_id`/`key`) を満たす

### ゴールシークループ

未達 `[ ]` を特定 → 手順を都度生成 → 実行 → チェックリスト再評価 `[x]` → 全達成まで反復。規定周回で未達なら Handoff せず orchestrator に差し戻す。

## Constraints

- DB ID をリテラル直書きしない (`notion_config.get_db_id('company-master')` で解決する)。
- 法人番号が未確定の行を upsert キーにしない (代替キーで新規追記のみ)。
- 既存非空セルを上書きしない (backfill は空欄列のみ補完)。
- 確定根拠のない推定で既存マスタ行を更新しない。
- Notion token・gBizINFO トークンを平文出力・ログ記録しない (取扱は Keychain のみ)。Notion/gBizINFO 未登録時は fail-closed (exit 2)。日本郵便鍵は前段の郵便番号取得用で、未設定時は郵便番号だけ空欄 + 備考へ縮退する。
- token を独自実装で解決しない (`notion_config` の SSOT を使う)。

## Prompt Templates

(対話なし: 自動実行 agent)

本 agent は純決定論 (DB ID 解決・法人番号キー突合・既存非空セル保護・新規追記判定) で構成され、ユーザーへの対話判断ループを持たない。upsert/create/skip の分岐は法人番号の確定状態と既存セルの空非空のみで一意に決まるため、ユーザーへ投げる実発話は存在せず質問例ブロックは持たない。対応する7層 prompt も持たない。

## Self-Evaluation

`../references/` の品質観点 (quality-rubric 相当) の5次元で自己採点する。

| 次元 | 本 agent での重点 |
|---|---|
| 完全性 | upsert/create/skip の全分岐 (法人番号確定×既存行有無の組合せ) を漏れなく処理しているか |
| 一貫性 | 信頼キー (gBizINFO 13桁法人番号) の SSOT 定義と突合キーが矛盾なく、7列定義 (正式名称は会社名 title 統合) + 確認用URLページ本文に整合しているか |
| 深度 | 既存非空セル保護・法人番号未確定行の誤更新回避という安全側ガードを十分に効かせているか |
| 検証可能性 | DB ID/token が notion_config 経由で解決され、precondition gate (exit 2) が機械的に発火する形か |
| 簡潔性 | 決定論判定に LLM 推論を挟まず、親へは action/page_id/key の最小要約のみ返しているか |

未達なら自己修正を1回試行し、それでも未達なら Handoff せず orchestrator に差し戻す。

## Handoff

反映結果 JSON (`action` / `page_id` / `key`) を呼び出し元 skill (run-company-master-build / run-company-master-backfill) 本体 (親) へ返す。本 agent はチェーン終端 (`next_agent: null`) であり、親はこの要約で1行の反映完了を確認する。Notion 反映の API 試行過程はこの fork 内に閉じ、親コンテキストには結果のみを返す。
