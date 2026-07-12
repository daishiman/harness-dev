---
name: run-mf-invoice-db-setup
description: 発行漏れチェック用のNotion DBを初回構築したいとき、DBのプロパティ設計を作り直したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--parent-page-id <id>]"
arguments: [parent_page_id]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-19
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-06-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-build-db.md
  - prompts/R2-verify-schema.md
schema_refs:
  - schemas/notion-db-schema.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: schema 適用後に verify_db_schema.py が schemas/notion-db-schema.json の properties 全件の型・select option・number format を PASS とし、適用前に存在した現行管理列・既存ページデータを破壊せず、削除は schema.deprecated_properties に明示した旧列だけに限定される冪等適用である。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: プロパティ定義の正本が schemas/notion-db-schema.json のみで、build_notion_db.py / verify_db_schema.py が SKILL.md にハードコードせず schema を読んで動く(対応状況は status 型でなく select、number は format:yen)こと。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: tenant overlay またはローカル config が供給する database_id への既存DB適用と parent_page_id 指定での新規作成という2モードが、後段 run-mf-invoice-check の出力先準備という導入者目的を過不足なく満たし、配布既定はID空のまま fail-closed となり database_id/parent_page_id 未解決時は安全に停止する設計になっていること。
      verify_by: elegant-review
---

# run-mf-invoice-db-setup

## Purpose & Output Contract

発行漏れチェック (`run-mf-invoice-check`) の出力先となる Notion DB のスキーマを用意する。事実列 (API由来) と管理列 (人の運用) を分離したプロパティ設計を `schemas/notion-db-schema.json` 正本 (プロパティ数はこの正本が唯一の真実。本文に固定値を書かない) から物質化する。DB は 1 顧客=1 ページ (upsert キー=顧客ID単独) の顧客一覧で、各行は最新月スナップショット。月次履歴は各顧客ページ本文の table block に蓄積する (DB プロパティではない)。冪等に動く 2 モード:

- **既存DBへ適用** (既定): tenant overlay またはローカル `.mf-kessai-config.json` で `database_id` が設定済みの場合、その DB に不足プロパティを追加し、タイトル列を `取引先企業名` に、宣言された列リネーム (`schemas/notion-db-schema.json` の `renames` = `判定`→`今月の発行状況`) を値保持でリネームする。`deprecated_properties` (対応状況/チェック実行ID/初回請求月(API推定) 等) は自動削除する。schema 現行列と既存ページデータは壊さない。配布既定の ID は意図的に空で、tenant 未選択のまま本番先へ書き込まない。
- **新規作成**: `--parent-page-id <id>` を指定した場合は config の `database_id` より優先して、その親ページ配下に新規 DB を作成し `database_id` をローカル `.mf-kessai-config.json` に記録する。CLI 引数を使わない場合は、config に `database_id` が無く `parent_page_id` があると新規作成する。

**入力**: `parent_page_id` (新規作成モードのみ。既定では不要)
**出力**: Notion DB が schema 通りに整い、`verify_db_schema.py` が全プロパティ PASS を返す。
**完了条件**: 対象 DB のプロパティが schema と一致 + `verify_db_schema.py` が PASS。

## ゴールシーク実行

### ゴール (Goal)
発行漏れチェック結果を投入できる Notion DB が、事実列＋管理列の設計通りに整い (tenant config で指定された既存 DB へ適用、または親ページ配下に新規作成)、`verify_db_schema.py` が PASS した状態。

### 目的・背景 (Why)
月次チェックの出力先を用意する。API由来の事実列と人が運用する管理列を分離した設計を確立し、後段の冪等 upsert が安定して書き込める土台を作る。スキーマ drift を検知するため適用後に機械検証する。出力先 ID は tenant overlay/ローカル config が供給し、配布既定は空のまま fail-closed とする。

### 完了チェックリスト (Checklist)
- [ ] `database_id` が解決できる (既定 `mf-kessai-config.default.json` か、ローカル上書き、または `parent_page_id` からの新規作成)
- [ ] `build_notion_db.py` がスキーマを適用する (既存DB→不足追加+タイトル/select 列 rename + deprecated 削除 / 新規→作成し database_id 記録)
- [ ] 事実列 (取引先企業名/顧客ID/対象年月/今月の発行状況/商品名/前月金額/今月金額/発行日/更新日/確認済み日時) が存在
- [ ] 管理列 (初回契約月/請求要否/支払サイクル/チェック済/備考) が存在
- [ ] 旧プロパティ (対応状況/チェック実行ID/初回請求月(API推定)) が DB から削除され、`判定` は `今月の発行状況` に値保持リネームされている
- [ ] `verify_db_schema.py` が全プロパティ PASS (件数は schema 正本 `len(expected)` 由来。固定値を書かない)

### ゴールシークループ
1. config の `database_id`/`parent_page_id` を読み現状評価 (`R1`)。
2. `--parent-page-id` が指定されていれば新規作成、未指定で `database_id` があれば既存DBへスキーマ適用、無く `parent_page_id` があれば新規作成、どちらも無ければ停止し共有依頼。
3. `verify_db_schema.py` で検証 (`R2`)。FAIL なら欠落を提示し再実行/手動追補へ差し戻す。
4. 全 checklist 充足で完了。

### ゴールシーク配線
本スキルは初回1回の単発が主だが、verify FAIL → 欠落追補 → 再 verify の再試行で多周回す場合の周回状態とドリフト圧縮を配線する。周回末に `eval-log/run-mf-invoice-db-setup-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変 (SHA-256 を `eval-log/run-mf-invoice-db-setup-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回の手順生成は直前の `merged_directive_for_next` と `original_goal` を必須入力として読む (AI 単独再導出禁止)。1周で PASS すれば本配線は no-op。

```bash
# 中間成果物アンカーの機械検査 (run-goal-seek/SKILL.md と同型 SSOT)
python3 - "$PWD/eval-log/run-mf-invoice-db-setup-progress.json" "$PWD/eval-log/run-mf-invoice-db-setup-intermediate.jsonl" <<'PY'
import json, os, sys, hashlib
prog_path, inter_path = sys.argv[1], sys.argv[2]
required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}
if not os.path.exists(inter_path):
    print("intermediate.jsonl 未生成 (ループ未実行)"); sys.exit(0)
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}
lines = [l for l in open(inter_path, encoding="utf-8").read().splitlines() if l.strip()]
first = None
for i, line in enumerate(lines):
    e = json.loads(line)
    assert not (required_keys - e.keys()), f"intermediate[{i}] 必須キー不足"
    if i == 0:
        first = e["original_goal"]
        h = hashlib.sha256(first.encode()).hexdigest()
        assert prog.get("original_goal_hash") in (None, h), "original_goal_hash drift"
    assert e["original_goal"] == first, f"intermediate[{i}] anchor 不変性違反"
print(f"anchor OK: {len(lines)} 行 / 不変 / hash 一致")
PY
```

## Key Rules

1. **通常は database_id 優先、CLI parent_page_id は新規作成を強制**: `--parent-page-id` があれば新規 DB を作成する。未指定なら `database_id` があれば既存DBへ冪等適用。両方空なら停止 (Notion integration 接続が前提)。
2. **status型は使わない**: 管理列の `請求要否`/`支払サイクル` は select で表現 (Notion API は status 新規作成不可)。
3. **管理列を破壊しない**: 再実行・再適用でも人が記入した現行管理列・既存ページデータを壊さない。列削除は schema の `deprecated_properties` whitelist に宣言した旧列のみ。`初回契約月` は MF API から取得できない顧客別情報であり人が YYYY-MM で記入し、`支払サイクル` (月払い/年間払い) は人が設定する。
4. **schema 正本一元**: プロパティ定義は `schemas/notion-db-schema.json` のみ。スクリプトはそれを読む。列の改名は `renames` (値保持リネーム)、削除は `deprecated_properties` で宣言する。

## Gotchas

1. Notion トークンと MF APIキーは**別 Keychain entry**。本スキルは Notion トークン (`notion-api-key.<keychain-prefix>`) を使う。
2. 既存DBへ適用する場合、タイトル列は schema の `取引先企業名` にリネームされる (既存の `名前` 等)。
3. `number` プロパティは `format: yen` で円表示。DB への integration 未接続だと `404 object_not_found`。

## Additional Resources

- `schemas/notion-db-schema.json` — DBプロパティ正本 (事実列/管理列/upsert_key)
- `scripts/build_notion_db.py` — 既存DBへスキーマ冪等適用 / 新規DB作成 + database_id 記録
- `scripts/verify_db_schema.py` — プロパティ存在検証 (drift検知)
- `prompts/R1-build-db.md` / `prompts/R2-verify-schema.md` — 責務プロンプト
- `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` — Notion へ入れるデータの取得元仕様
