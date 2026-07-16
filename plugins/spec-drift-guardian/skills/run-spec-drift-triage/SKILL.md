---
name: run-spec-drift-triage
description: spec-drift issue が起票され diff トリアージが必要なとき、C11 が再構成した issue 単位の完全 diff を hunk 化し name/type/required/enum/semantics 各軸の影響を before/after/evidence 付きで判定して triage-report を出したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--issue NUMBER] [--events FILE]"
arguments: [issue, events]
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-07-13
version: 0.1.0
source: plugins/spec-drift-guardian/skills/run-spec-drift-triage/
source-tier: internal
last-audited: 2026-07-13
audit-trigger: official-update
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-parse.md
  - prompts/R3-triage.md
reference_refs:
  - references/resource-map.yaml
script_refs:
  - ../../scripts/aggregate-issue-diffs.py
  - ../../scripts/parse-spec-diff.py
  - ../../scripts/map-field-impact.py
schema_refs:
  - ../../schemas/triage-report.schema.json
allowed-tools:
  - Read
  - Write
  - Bash
responsibilities:
  - id: R1
    name: elicit
    prompt_required: true
  - id: R2
    name: parse
    prompt_required: true
  - id: R3
    name: triage
    prompt_required: true
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
feedback_contract:
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      verify_by: script
      text: C11出力がcomplete=trueでcommit pair/digestを持ち、C08/C09出力のname/type/required/enum/semantics・before/after/evidence必須キー欠落が0件。
    - id: OUT1
      loop_scope: outer
      verify_by: test
      text: Issue #17完全commit pairとsource-category fixture matrixに対し4軸+semanticsの誤検出/見逃しがthreshold内で、truncated preview入力はfail-closedになる。
---

# run-spec-drift-triage

> 検知済み spec-drift issue の**影響トリアージ**を行う run skill。C11 (`aggregate-issue-diffs.py`) がローカル git から再構成した issue 単位の**全未triage完全 diff** を、C08 (`parse-spec-diff.py`) で hunk 化し C09 (`map-field-impact.py`) で影響候補へ写像したうえで、name/type/required/enum/semantics 各軸の影響を before/after/evidence 付きで判定し、`triage-report` schema 準拠の JSON を emit する。**提案・適用 (C02)・独立判定 (C03) はやらない**。

## Purpose & Output Contract

**目的 (goal)**: C11 が再構成した issue 単位の全未triage完全 diff を hunk 単位で構造化し、artifact kind/path と name/type/required/enum/semantics 各軸への影響を before/after/evidence 付きで判定したトリアージレポートを生成した状態にする。

**背景 (purpose_background)**: spec-drift issue の影響判定 (step2) が人手依存であり、`spec-diff-history.md` の 80 行 preview だけでは Issue #17 の 945 行完全差分を判定できない。C11 の commit pair 再構成と C09 の 4 軸 + semantics 写像により、取りこぼしと判断ブレを防ぐ。

**入力** (境界・厳守):
- `--issue NUMBER` — 対象 GitHub issue 番号。
- `--events FILE` — gh issue metadata / comment timestamps と `spec-diff-history.md` 見出し (**索引としてのみ使用**) から組み立てたイベント表。実 diff はローカル git commit pair から復元する (network=false)。
- **入力の正体は「C11 がローカル git から再構成した全未triage完全 diff」**。検知・issue 起票は既存 workflow (`update-yaml-spec.yml` / `ref-yaml-spec-fetcher`) の責務であり、本 skill は行わない。

**出力**:
- `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json` — `../../schemas/triage-report.schema.json` 準拠。`issue` / `base_commit` / `source_commit` / `diff_sha256` / `complete` / `impacts[]` (`artifact_kind` / `artifact_path` / `axis` / `before` / `after` / `impacted` / `evidence`) を持つ。
- 完了レポート (日本語、JSON キー・CLI 引数・軸名は英語)。

**完了条件**: C11 出力が `complete=true` かつ commit pair / digest を伴い、C08/C09 の必須キー欠落 0 件 (IN1) で、triage-report が schema 準拠かつ 4 軸 + semantics の判定が fixture matrix に対し threshold 内 (OUT1) を満たす。

**やらないこと (boundary)**:
- **完全性 (`complete=true`) を証明できない入力は判定しない (fail-closed)**。truncated preview / digest 不一致 / commit 欠落は triage せず理由付きで停止する。
- 更新提案・実適用は **C02 (`run-rubric-sync`)** の責務。
- 生 diff からの独立再導出・照合は **C03 (`spec-impact-verifier`)** の責務。本 skill の出力は C03 が独立に照合する対象であって、自ら再判定はしない。
- commit / PR / issue close は行わない。

## 決定論段 (Bash) と意味判断 (LLM) の二層分離

再現性が要る変換は 3 つの決定論 script が担い、LLM は**意味判断のみ** (軸判定の妥当性確認・レポート組み立て) に限定する。写像規則は `../../references/field-impact-map` の SSOT を C09 が読むだけで、LLM はこれを hardcode・改変しない。

| 段 | 実体 | 役割 | fail-closed 条件 |
|---|---|---|---|
| C11 集約 | `python3 $CLAUDE_PLUGIN_ROOT/scripts/aggregate-issue-diffs.py --issue N --events FILE` | issue 単位の未triage全 diff を完全 commit diff として時系列集約 | 欠落 / 曖昧照合 / shallow clone / digest 不一致 (exit≠0) |
| C08 hunk化 | `python3 $CLAUDE_PLUGIN_ROOT/scripts/parse-spec-diff.py --stdin` | C11 stdout を verbatim で受け `untriaged_entries` を選別し unified hunk 単位へ構造化 (commit pair / digest 継承) | `complete=false` / digest 不一致 / commit pair 混在 (exit2)、入力形状不正・JSON parse 失敗 (exit1) |
| C09 写像 | `python3 $CLAUDE_PLUGIN_ROOT/scripts/map-field-impact.py --stdin` | hunk から artifact kind/path と 4 軸+semantics の before/after/evidence 候補へ写像 | 必須キー欠落 / 写像表不備 (exit≠0) |

LLM が担うのは、C09 の影響候補が実 hunk 証拠と整合するかの**軸判定の妥当性確認**と、schema 準拠の triage-report への**組み立て**のみ。`base_commit` / `source_commit` / `diff_sha256` / `complete` は C11 が算出した provenance を**そのまま転記**し、LLM が再計算しない (C03 verdict と一致必須のため)。

## End-to-End Flow (責務プロンプト正本 = prompts/*.md)

```
[R1 elicit] gh issue metadata/comment + spec-diff-history 見出し(索引) → events FILE
            → aggregate-issue-diffs.py --issue N --events FILE
            → entries / untriaged_entries / source_provenance (complete=true, base/source/digest)
            ─[complete 証明できなければ fail-closed で停止]─▶
[R2 parse]  untriaged 完全 diff → parse-spec-diff.py --stdin → hunks JSON (commit pair/digest 継承)
            → map-field-impact.py --stdin → 影響候補 (artifact kind/path, 4軸+semantics, before/after/evidence)
            ─[必須キー欠落 0 件が IN1]─▶
[R3 triage] LLM: 各軸判定を hunk 証拠と照合し妥当性確認 → triage-report 組み立て
            → $CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json
```

1. **R1-elicit** (`prompts/R1-elicit.md`): 対象 issue を確定し、events FILE を組み立て、`aggregate-issue-diffs.py` で未triage 全 diff 集合を集約する。`complete=true` と commit pair / digest を確認できないときは判定に進まず停止する。
2. **R2-parse** (`prompts/R2-parse.md`): 集約 diff を `parse-spec-diff.py --stdin` で hunk 化し、`map-field-impact.py --stdin` で影響フィールド候補へ写像する。exit2 (`complete=false` / digest 不一致) は fail-closed。
3. **R3-triage** (`prompts/R3-triage.md`): C09 候補の各軸 (name/type/required/enum/semantics) を hunk 証拠と照合し、`impacted` と before/after/evidence を確定して schema 準拠の `triage-report.json` を emit する。

## Key Rules

1. **完全性優先 / fail-closed**: `complete=true` かつ digest 一致を証明できない入力は判定しない。truncated preview は必ず fail-closed。
2. **provenance 転記**: `base_commit` / `source_commit` / `diff_sha256` / `complete` は C11 出力を verbatim 転記し、LLM が再計算・改変しない。
3. **写像非 hardcode**: diff→フィールド写像は C09 が `references/field-impact-map` を読むだけ。LLM は写像規則を prompt に埋め込まない (guardian 自身の drift 源化を防ぐ)。
4. **軸網羅**: name / type / required / enum / semantics の 5 軸を各 hunk で評価する。`impacted=false` の軸も evidence 付きで列挙してよい (schema 許容)。
5. **境界厳守**: 提案・適用 (C02)・独立判定 (C03)・issue close はしない。出力はトリアージまで。
6. **単一 writer**: `.spec-drift/<issue>/triage-report.json` への書込は本 skill のみ。上書き前に既存内容と issue/digest 整合を確認する。
7. **日本語成果物**: レポート本文は日本語。JSON キー・CLI 引数・軸名 (name/type/required/enum/semantics) は英語。

## Feedback Contract (with-feedback-contract / with-goal-seek)

- **IN1** (inner, script): C11 出力が `complete=true` で commit pair / digest を持ち、C08/C09 出力の `name` / `type` / `required` / `enum` / `semantics`・`before` / `after` / `evidence` 必須キー欠落が 0 件。検証は 3 決定論 script の exit code (C11≠0 / C08 exit2 / C09≠0 で不成立) で機械判定する。
- **OUT1** (outer, test): Issue #17 完全 commit pair と source-category fixture matrix に対し 4 軸 + semantics の誤検出 / 見逃しが threshold 内で、truncated preview 入力は fail-closed になる。
- **goal-seek** (engine=inline, fork=subagent, max_loops=5): IN1 / OUT1 を満たすまで、events 再構成・軸判定の妥当性確認・レポート組み立てを反復改善する。fork=subagent で独立 context で評価し Sycophancy を避ける。max_loops=5 で未収束なら residual findings 付きで停止し fail-closed 状態を報告する。

## Gotchas

1. **preview を diff と誤認しない**: `spec-diff-history.md` の 80 行 preview は**イベント日時の索引**にのみ使う。実 diff は必ず C11 が commit pair から復元したものを使う。
2. **triage 済みを再集約しない**: 集約対象は `entries` (issue の全 diff 履歴) ではなく `untriaged_entries` (未処理のみ)。C08 は C11 stdout を **verbatim で受け取り** untriaged_entries を自ら選別するため、再ラップも最新 1 件固定も不要 (`entries` を渡すと triage 済みまで再集約する)。
3. **digest を跨いで混ぜない**: triage-report は `base_commit`/`source_commit`/`diff_sha256` を各 1 個しか持てない (単一 digest 契約・C03 verdict と一致必須)。積層できるのは **1 commit pair 内の複数ファイル・複数 hunk** までで、untriaged が複数 commit pair に跨る入力は C08 が集約せず fail-closed (exit2) する。同一 commit pair が履歴に重複しても C08 が dedup するので二重計上しない。
4. **複数 commit pair の issue は分割する**: 出力先 `.spec-drift/<issue>/triage-report.json` は issue 単位で 1 本 (単一 writer)。1 issue に複数 commit pair の未triage変更が溜まった場合、同じパスへ上書きすると先の triage 証跡を失うため、**issue を commit pair 単位へ分割してから** triage する (C10 も `--triage-report` 単数 + digest 一致必須のため、1 issue = 1 commit pair が close 可能な形)。
5. **impacted の根拠必須**: `impacted=true` も `false` も `evidence` (hunk 抜粋・行番号) を空にしない (schema `minLength:1`)。
6. **context 予算**: SKILL.md / 各 prompt は簡潔に保つ。`references/resource-map.yaml` を最初に読み、必要ファイルのみ open する。

## Additional Resources

`references/resource-map.yaml` を最初に読む。主要参照:

- `../../scripts/aggregate-issue-diffs.py` (C11) — issue 単位の完全 diff 集約。`--issue NUMBER --events FILE`
- `../../scripts/parse-spec-diff.py` (C08) — 集約 diff の hunk 化。`--stdin`
- `../../scripts/map-field-impact.py` (C09) — hunk→4 軸+semantics 影響候補写像。`--stdin`
- `../../references/field-impact-map` — C09 が読む diff→フィールド写像表 (read-only / 本 skill は改変しない)
- `../../schemas/triage-report.schema.json` — 出力契約スキーマ
- `prompts/R1-elicit.md` / `prompts/R2-parse.md` / `prompts/R3-triage.md` — R1/R2/R3 責務別プロンプト (7 層)
- 消費先: C03 (`spec-impact-verifier`) が独立照合 / C10 (`check-triage-complete.py`)・C07 (`guard-spec-drift-close.py`) close gate が消費
