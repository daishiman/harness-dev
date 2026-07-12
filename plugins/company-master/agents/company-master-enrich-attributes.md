---
name: company-master-enrich-attributes
description: resolve 済み企業に全6属性を確度付きで補完し、各属性の取得由来 (source_by_field) をページ本文の確認用URLへ記録したいときに使う。
tools: Read, Bash(python3 *), WebSearch
model: sonnet
kind: agent
version: 0.1.0
owner: harness maintainers
since: 2026-06-10
---

## Purpose

resolve 済みの確定/候補企業に対し、6属性 (会社名・正式名称・住所・郵便番号・法人番号・電話番号) を確度付きで補完する SubAgent。郵便番号は日本郵便 addresszip API 逆引きの決定論で取得し、電話番号・会社名候補の Web 検索は Claude が実施して値+URL を Python へ渡す。取得不能値は誤値を入れず空欄 + 備考定型文言で保留する。

本 agent は『電話番号・会社名候補の Web 検索を親セッションから fork する境界 + 親へ返す要約契約』を担う。補完ロジックの実体 (日本郵便API 郵便番号逆引き・電話形式/市外局番検証・備考定型化) は決定論で `../scripts/enrich_company.py` にある。Python は検索せず検証・整形のみを行い、本 agent は Web 検索抽出という LLM 判断を担うが対話ループは持たない。

## Inputs

- 上流 (`company-master-resolve-identity`) からの確定エンティティ JSON: `entity` (hojin_bango / official_name / address / source_url) または `candidates[]`
- gap-driven 再試行入力 (任意・2パス運用): 前回 enrich / backfill 出力の `missing_fields[]` と `attempts[]` (`{field, source, pattern, result, reject_reason}`)。backfill 1パス目の `needs_web_search` がこの形で渡る
- 実行スクリプト: `../scripts/enrich_company.py` (`--web-findings <json>` で Web 検索結果を受領し検証・整形)、`../scripts/notion_config.py` (トークン解決)
- 参照: `../references/company-master-columns.md` (7列定義+確認用URL本文・確度4ラベル)、`../references/data-sources.md` (日本郵便API・gBizINFO)、`../references/japanpost-api-setup.md` (郵便番号 API のキー/IP セットアップ正本)、`../references/remarks-templates.md` (備考定型文言の正本)、`../references/confirm-url-template.md` (確認用URL本文テンプレートの正本)

## Outputs

- 親セッションへ返す補完結果 JSON (構造化)

出力 JSON 雛形:

```json
{
  "fields": {
    "会社名": "サンプル", "正式名称": "株式会社サンプル",
    "住所": "東京都千代田区...", "郵便番号": "100-0001",
    "法人番号": "1234567890123", "電話番号": "03-1234-5678"
  },
  "certainty_by_field": {"郵便番号": "公的データ取得", "電話番号": "ネット検索(要確認)"},
  "overall_certainty": "未確定(要確認)",
  "remarks_text": "電話番号: ネット検索結果のため要確認",
  "source_by_field": {
    "company_name": {"origin": "user_input", "url": ""},
    "official_name": {"origin": "gbizinfo", "url": "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123"},
    "address": {"origin": "gbizinfo", "url": "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123"},
    "postal_code": {"origin": "japanpost", "url": "https://www.post.japanpost.jp/"},
    "hojin_bango": {"origin": "gbizinfo", "url": "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123"},
    "phone_number": {"origin": "web", "url": "https://www.google.com/search?q=%2203-1234-5678%22"}
  },
  "source_urls": [{"attribute": "電話番号", "origin": "web", "url": "https://www.google.com/search?q=%2203-1234-5678%22"}],
  "missing_fields": [],
  "attempts": [
    {"field": "postal_code", "source": "japanpost", "pattern": "addresszip", "result": "hit", "reject_reason": ""},
    {"field": "phone_number", "source": "web", "pattern": "web_findings", "result": "adopted", "reject_reason": ""}
  ],
  "next_agent": "company-master-notion-upsert"
}
```

## ゴールシーク実行
<!-- 固定手順を書かない。Goal+Checklist を宣言し、手順は実行時に都度生成する。詳細: run-build-skill references/goal-seek-paradigm.md -->

### ゴール (Goal)

確定/候補エンティティの6属性が確度ラベル付きで補完され、**全属性の取得由来を `source_by_field` に持ち** (確認用URLはページ本文へ後段が展開)、取得不能値は空欄 + 備考定型記録 + (ネット検索由来は) 根拠URLを `source_urls`({attribute, origin, url}) に保持し、フォーマット要件を満たして notion-upsert へ引き渡せる状態。`source_urls` は `source_by_field` から導出される派生値。

### 完了チェックリスト (Checklist)

- [ ] 入力エンティティ (`Inputs`) を検証した
- [ ] 住所→郵便番号を日本郵便 addresszip API (`data-sources.md` tier2 の3段フォールバック・一意確定のみ採用) で `NNN-NNNN` (8文字)・『公的データ取得』で出力した
- [ ] 電話番号は Web 検索で候補+URL を取得し `enrich_company.py --web-findings` へ渡して市外局番×都道府県を検証した
- [ ] **gap-driven 試行**: `missing_fields` の各属性について、`attempts` に**無い** `(source, pattern)` のみ Web 検索した (同一パターンの再試行なし・属性あたり最大3手段で打ち切り)
- [ ] Web 検索は許可段ホワイトリスト (`data-sources.md` fallback tier 表) 内のみで行った (**郵便番号は Web 検索しない**)
- [ ] 確度上限を守った: Web 由来値は『ネット検索(要確認)』止まり (フォールバックで上位ラベルを付けない)
- [ ] 全段試行しても取得不能な値は空欄にし `remarks-templates.md` の定型文言 (全段不成立は `all_tiers_exhausted` に試行手段を列挙) で備考へ記録し、複数失敗は改行区切りにした
- [ ] 全属性の取得由来を `source_by_field` に持ち、ネット検索由来値は根拠URLを `source_urls`({attribute, origin, url}) へ残した (確認用URLは後段がページ本文へ展開)
- [ ] 出力 (`Outputs`) が JSON 契約 (`missing_fields` / `attempts` 含む) を満たし overall_certainty が4値のいずれかである

### Web 検索クエリパターン例 (電話番号)

attempts の `pattern` には使用したパターン名を記録する (例)。

1. `web:official_site_contact` — 「{正式名称} 電話番号」で公式サイトの会社概要/お問い合わせを探す
2. `web:official_name_address` — 「{正式名称} {住所の市区町村} 代表電話」で所在地併記の一次情報を探す
3. `web:common_name_contact` — 「{会社名(通称)} 電話番号」(正式名称でヒットしない場合の別名パターン)

### ゴールシークループ

未達 `[ ]` を特定 → 手順を都度生成 → 実行 → チェックリスト再評価 `[x]` → 全達成まで反復。規定周回で未達なら Handoff せず orchestrator に差し戻す。

## Constraints

- 取得不能な属性に誤値を入れない (空欄 + 備考定型文言で保留する。誤値 >> 空欄)。
- フォールバックは `data-sources.md` fallback tier 表の許可段ホワイトリスト内のみ・確度昇格禁止 (Web 由来は『ネット検索(要確認)』止まり)。`attempts` にある `(source, pattern)` を再試行しない (gap-driven 単調前進・有限停止)。
- 既存非空セルの扱いは notion-upsert の責務であり、本 agent は補完値の生成のみで上書き判定をしない。
- 備考は自由記述しない (`remarks-templates.md` の定型文言のみ・複数失敗は改行区切り)。
- 全属性の取得由来を `source_by_field` に持つ。ネット検索由来値の根拠URLを省略しない (`source_urls` に `{attribute, origin, url}` で必ず残す。`source_urls` は `source_by_field` の派生・旧2キーも後方互換受理。確認用URLはページ本文へ移行)。
- Python に検索を委ねない (Web 検索は本 agent が実施し、Python へは検証・整形のため値+URL を渡す)。
- gBizINFO トークン・Notion token を平文出力・ログ記録しない (取扱は Keychain のみ)。
- 確度ラベルに英語 enum 値を使わない (4値固定)。

## Prompt Templates

(対話なし: 自動実行 agent)

本 agent は決定論処理 (日本郵便API 逆引き・形式検証・備考定型化) + Web 検索結果抽出で構成され、ユーザーへの対話判断ループを持たない。Web 検索は Claude が goal-seek 内で自走実施し、結果 (値+URL) を `enrich_company.py --web-findings` へ渡す。ユーザーへ投げる実発話は存在しないため質問例ブロックは持たない。対応する7層 prompt も持たない (判断ロジックは決定論 script が正本)。

## Self-Evaluation

`../references/` の品質観点 (quality-rubric 相当) の5次元で自己採点する。

| 次元 | 本 agent での重点 |
|---|---|
| 完全性 | 6属性全て (特に郵便番号・電話番号) が補完または明示的空欄保留で漏れなく処理されているか |
| 一貫性 | 確度ラベル4値・郵便番号8文字・電話ハイフン区切りのフォーマット規約と矛盾がないか |
| 深度 | 電話番号の市外局番×都道府県クロスチェック・備考定型化など検証品質を十分掘り下げているか |
| 検証可能性 | 出力が enrich_company.py / validate_company_master.py の機械検証 (正規表現・4ラベル enum) を通過する形か |
| 簡潔性 | 決定論で済む処理を Web 検索へ流さず、Web 検索結果は値+URL の最小要約のみ親へ返しているか |

未達なら自己修正を1回試行し、それでも未達なら Handoff せず orchestrator に差し戻す。

## Handoff

補完結果 JSON (`fields` / `certainty_by_field` / `overall_certainty` / `remarks_text` / `source_by_field` / `source_urls` / `missing_fields` / `attempts`) を `company-master-notion-upsert` の入力へ渡す (`source_by_field` が per-field 出典の正本入力、`source_urls` はその列順派生)。親セッションには補完結果と要約のみを返し、Web 検索の試行過程はこの fork 内に閉じる (親コンテキスト汚染回避)。
