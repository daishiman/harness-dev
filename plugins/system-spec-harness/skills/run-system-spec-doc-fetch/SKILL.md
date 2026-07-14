---
name: run-system-spec-doc-fetch
description: 対象カテゴリで使う予定のツール・インフラ・フレームワークの最新公式ドキュメントを集めて公式host・version や更新日・確認時刻・参照元を fetched-references.json に記録したいとき、spec-compile 前に公式サイトの現行版で裏取りしたいときに使う。
disable-model-invocation: false
user-invocable: true
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-07-11
version: 0.1.0
source: plugins/system-spec-harness/component-inventory.json
source-tier: internal
last-audited: 2026-07-11
audit-trigger: official-update
allowed-tools:
  - WebSearch
  - WebFetch
  - Read
  - Bash
responsibility_refs:
  - prompts/R1-identify.md
  - prompts/R2-fetch.md
  - prompts/R3-record.md
schema_refs:
  - ../../schemas/fetched-references.schema.json
responsibilities:
  - id: R1-identify
    name: identify
    prompt_required: true
  - id: R2-fetch
    name: fetch
    prompt_required: true
  - id: R3-record
    name: record
    prompt_required: true
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: official-source discovery is an inline goal-seek loop selected from unmet targets; the SKILL body is the runtime SSOT."
feedback_contract: # per-skill 評価基準 (component-inventory.json C02 SSOT)
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-source-citation.py で対象 target_id と fetched-references.json が全件対応し retrieved_at/source_url/official_publisher/official_host/(version または last_updated)/latest_checked_at を持ち公式host一致であることを検証し欠落0件。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 対象ツール/インフラ/フレームワークごとに C08 が公式サイト上の現行版を再確認し version/更新日・確認時刻・参照元が記録されていることを受入テストが確認する。
      verify_by: test
---

# run-system-spec-doc-fetch

> システム仕様ヒアリングで使う予定の外部技術について、**最新公式ドキュメントの出典記録** `fetched-references.json` を都度取得して組み立てる run skill。起動経路は (a) `spec-compile` (C10) 前の未取得参照検出、(b) `run-system-spec-elicit` (C01) R2 ヒアリング中の裏取り要求の 2 系統。責務の正本は `prompts/R1-identify.md` / `R2-fetch.md` / `R3-record.md`。

## Purpose & Output Contract

**入力**: `spec-state.json` (C01 出力) の`targets[]`、`decisions[].options[].evidence_refs`候補、`knowledge_candidates[]`。ヒアリング/R5意思決定中の裏取りでは比較候補の公式文書・公式価格ページ。seed外knowledgeでは `status=discovered` candidateの一次資料を確認する。
**出力**: `fetched-references.json` (共有データ契約)。

意思決定候補の価格/無料枠/制約は変動するため、R5の推奨前に通常の鮮度契約（公式publisher/host、versionまたは更新日、retrieved/latest_checked_at）で再確認する。
**完了条件**: 下記「完了チェックリスト」を全充足 (IN1 = `validate-source-citation.py` exit0)。

**上流指針 (doctrine anchor)**: 取得対象の技術は `ref-system-design-knowledge/references/doctrine-anchor-registry.json` の concern authority (presentation=Apple HIG / application-architecture・data-access=Clean Architecture / authentication・security=OWASP ASVS+Secrets Management / reliability・operations=Google SRE) が示す上流指針に沿った公式一次資料を優先取得する。取得した参照は IN1 の official_host 検証 (C13 citation gate) と併せて、C14 knowledge graph の位相順 (上位概念→下位概念) で後続 (C01/C03) の参照へ供給する。registry は具体技術を直書きせず上流工程を導くのみで、本 skill の取得対象 (`target_id`) 自体は `spec-state.json` が正本。

`fetched-references.json` の形状 (厳守):

```json
{"references": [
  {"target_id":"react","retrieved_at":"2026-07-11T00:00:00Z",
   "source_url":"https://react.dev/reference/react","official_publisher":"Meta",
   "official_host":"react.dev","version":"19.0",
   "latest_checked_at":"2026-07-11T00:00:00Z","summary":"..."}
]}
```

- 必須: `target_id` / `retrieved_at` / `source_url` / `official_publisher` / `official_host` / `latest_checked_at` / `summary`、および `version` か `last_updated` のいずれか。
- 全件対応: `spec-state.targets[]` の各 `target_id` に record が 1 件対応 (欠落 0・重複 0)。
- host 一致: `source_url` の host が `official_host` と一致する。

## Key Rules

1. **公式一次情報のみ**: 参照は公式 publisher/host に限る。ブログ/まとめ/ミラーは採らない (R2 の判定基準 = `references/official-source-catalog.md`)。
2. **捏造しない**: 取得できた素材だけを記録する。未取得は「取得済み」と偽らず理由付きで残す (fail-visible)。
3. **恒久キャッシュ禁止**: `fetched-references.json` は都度生成。ミラーリングや永続キャッシュはしない。
4. **決定論組み立て**: 記録は `scripts/build-fetched-references.py` で正規化し、`validate-source-citation.py` (IN1) で機械検証する。手書き JSON で緑化しない。
5. **時刻は実取得値**: `retrieved_at`/`latest_checked_at` は R2 が控えた実時刻をそのまま用いる (壁時計上書きなし = 再現性)。
6. **鮮度判定は分離**: 現行最新版かの意味判定は本 skill でなく C08 (`system-spec-doc-freshness-auditor`, OUT1) の担当。本 skill は形式・全件・host 一致まで。
7. **MCP 対象外**: 取得は WebSearch/WebFetch のみで完結する (MCP 連携は `open_issues` GAP-MCP-DOCFETCH で保留)。
8. **言語**: 本文は日本語、`target_id`/URL/version/JSON キーは英語のまま。
9. **Knowledge qualification担当**: C02は`discovered` candidateごとに公式/一次HTTPS資料を取得し、実確認時刻付き`source_refs[]`を作る。C01の単一writer `set-knowledge-candidate` を通してのみ `qualified` へ進める。C02はdeep card作成やcurated昇格を代行しない。

## ゴールシーク実行

> 本 skill は固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。局面カタログは順序固定でなく、未達に応じて選ぶメニュー。反復上限 = `feedback_contract.max_iterations` (5)。

### ゴール (Goal)

対象カテゴリで使う予定のツール/インフラ/フレームワークの最新公式ドキュメントが取得され、`target_id` 全件対応・公式 publisher/host・version または更新日・取得/確認時刻・参照元を保持した `fetched-references.json` が、現行版を再照合できる状態で確定している。

### 目的・背景 (Why)

設計判断が古い情報に基づくと仕様全体が陳腐化する。最新の公式情報を都度取得し出典を追跡可能にすることで、後続の `spec-compile` が各章に確かな一次資料ポインタを添えられる。

### 完了チェックリスト (停止条件)

- [ ] R1 が `spec-state.json` 由来の取得対象一覧 (`target_id` 群) を捏造 0 で確定している
- [ ] R2 が各対象の公式 host を特定し、非公式ソースで穴埋めしていない (未取得は理由付きで明示)
- [ ] 各 record が必須フィールドを充足し version か `last_updated` のいずれかを持つ
- [ ] `source_url` の host が `official_host` と一致している
- [ ] 対象一覧と `fetched-references.json` が全件対応 (欠落 0・重複 0)
- [ ] IN1: `validate-source-citation.py --targets <targets> --references fetched-references.json` が exit0
- [ ] `knowledge_candidates[]` のdiscovered対象は、公式/一次HTTPS `source_refs[]` と実`checked_at`を得たものだけがqualifiedになっている

### ゴールシークループ

正本 goal-seek-paradigm.md の 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し) に従う。IN1 違反は該当対象を R2 へ差し戻して取り直す。5 反復で埋まらない対象は理由を明示して呼出元 (C10 / C01 / ユーザー) へ差し戻す。

## 局面カタログ (順序は都度判断)

- **取得対象特定 (R1)**: `spec-state.json` の `targets[]` と確定/収集中セルから外部技術を洗い出し `target_id` へ正規化する。詳細 = `prompts/R1-identify.md`。
- **seed外knowledge qualification (R1/R2)**: `knowledge_candidates[]` のdiscovered対象を取得一覧へ加え、R2が公式/一次HTTPS資料と`checked_at`を取得する。C01の`set-knowledge-candidate`でqualifiedへ遷移する。
- **公式ドキュメント取得 (R2)**: `WebSearch` で公式 host を特定し `WebFetch` で現行版・要点・更新日を取得する。詳細 = `prompts/R2-fetch.md` / `references/official-source-catalog.md`。
- **記録・検証 (R3)**: `build-fetched-references.py assemble --records <素材> --targets <targets> --out fetched-references.json` で組み立て、`validate-source-citation.py` で IN1 検証する。詳細 = `prompts/R3-record.md`。
- **反復差し戻し**: 検証違反・未取得対象を R2 へ戻し、全件緑まで繰り返す。

## 検証コマンド

```bash
PLUGIN_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"   # plugins/system-spec-harness を指す
# R3 決定論組み立て (全件対応も同時検査)
python3 skills/run-system-spec-doc-fetch/scripts/build-fetched-references.py \
  assemble --records records.json --targets targets.json --out fetched-references.json
# IN1 ゲート (共有 script)
python3 scripts/validate-source-citation.py \
  --targets targets.json --references fetched-references.json
```

## Gotchas

1. 公式 host を一意に特定できない対象は「未取得 (要確認)」に倒す。非公式で埋めない。
2. `source_url` は必ず `official_host` 配下のページにする (host 不一致は IN1 で弾かれる)。
3. version が数値化されない技術はページ最終更新日を `last_updated` に記録する (version と両欠落は FAIL)。
4. 同一技術が複数カテゴリに跨っても `target_id` は 1 件に束ねる (重複は FAIL)。
5. ヒアリング中裏取り (経路 b) では対象をユーザー指定分に絞ってよいが、記録形状と検証は同一。

## Additional Resources

- `prompts/R1-identify.md` / `prompts/R2-fetch.md` / `prompts/R3-record.md` — 責務 SSOT (7 層)
- `scripts/build-fetched-references.py` — record 素材を契約形状へ正規化・全件突合する決定論 assembler
- `references/official-source-catalog.md` — 公式 host 判定の指針と代表例
- `references/resource-map.yaml` — Progressive Disclosure 索引
- `../../scripts/validate-source-citation.py` — IN1 検証ゲート (plugin-root 共有 script)
- consumer: `spec-compile` (C10) / `run-system-spec-elicit` (C01) / `system-spec-doc-freshness-auditor` (C08 = OUT1)
