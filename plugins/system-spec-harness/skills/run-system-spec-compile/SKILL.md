---
name: run-system-spec-compile
description: 収集済み仕様 (spec-state.json) と取得済み最新ドキュメント・設計知識参照を章立ての複数 Markdown ファイル + index の仕様書ドキュメントセットへまとめたいとき、ヒアリング結果を仕様書へコンパイルしたいときに使う。
disable-model-invocation: false
user-invocable: true
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-07-11
version: 0.1.0
source: plugins/system-spec-harness/skills/run-system-spec-compile/
source-tier: internal
last-audited: 2026-07-11
audit-trigger: official-update
responsibility_refs:
  - prompts/R1-assemble.md
  - prompts/R2-render.md
  - prompts/R3-crosslink.md
reference_refs:
  - references/resource-map.yaml
script_refs:
  - scripts/compile-spec-doc.py
  - ../../scripts/validate-coverage-matrix.py
  - ../../scripts/validate-source-citation.py
schema_refs:
  - ../../schemas/spec-state.schema.json
  - ../../schemas/fetched-references.schema.json
allowed-tools:
  - Read
  - Write
  - Bash
responsibilities:
  - id: R1
    name: assemble
    prompt_required: true
  - id: R2
    name: render
    prompt_required: true
  - id: R3
    name: crosslink
    prompt_required: true
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: compile retries select the failed deterministic/content gate dynamically; the SKILL body is the runtime SSOT."
feedback_contract:
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      verify_by: script
      text: 生成直前の spec-state.json と fetched-references.json に対し validate-coverage-matrix.py と validate-source-citation.py が exit0。
    - id: OUT1
      loop_scope: outer
      verify_by: test
      text: 生成された仕様書ドキュメントセットがカテゴリ×プラットフォームの確定/対象外理由と最新ドキュメント出典を含むことを受入テストが確認。
---

# run-system-spec-compile

> 収集済み仕様 (spec-state.json) と取得済み最新ドキュメント (fetched-references.json)・設計知識参照を、**章立ての複数 Markdown ファイル + index.md** の仕様書ドキュメントセットへまとめる run skill。ヒアリング継続やドキュメント再取得はしない (入力を組み立てるのみ)。

## Purpose & Output Contract

**入力** (境界・厳守):
- `spec-state.json` — カテゴリ×プラットフォーム収集マトリクス (C01 run-system-spec-elicit の単一 writer が所有)。
- `fetched-references.json` — 取得済み最新公式ドキュメントの出典記録 (C02 が取得)。
- 設計知識参照 — `../ref-system-design-knowledge/references/*.md` (C04)。

**出力**: `system-spec/` 配下の、**先頭にU1-U9と意思決定表を持つ要件定義書 (`00-requirements-definition.md`) + 章別 Markdown 複数ファイル (`<category>.md`) + `index.md`**。

**完了条件**: 要件定義書 + 全カテゴリ章 + index.md が生成され、IN1 (2 決定論ゲート exit0) と OUT1 (受入テスト) を満たす。

**上位概念 anchor (要件 C9)**: spec-state.json の `requirements_foundation` (U1-U9) を **`00-requirements-definition.md` (要件定義書=憲法) として最初の章**に生成し、各技術章 frontmatter の `serves_goals` (セル serves_goals の集約) で全章を上位概念へトレース (anchor) する。`index.md` は要件定義書を先頭に相互参照する。requirements_foundation 不在の spec-state でも空落ちさせず draft の要件定義書を出す。

**やらないこと** (boundary): ヒアリングの継続 (C01 の責務)、ドキュメントの再取得 (C02 の責務)、spec-state.json の書換え。本 skill は**入力を章へ組み立てるだけ**で、収集状態そのものは変更しない。

## 章 frontmatter の確定マーカー仕様 (C11 hook の判定ソース・厳守)

各章 Markdown の frontmatter は次の確定マーカーを持つ。C11 hook (`guard-confirmed-chapter-overwrite.py`) はこのマーカーと spec-state.json のセル状態を判定ソースとして確定章の誤上書きを fail-closed で遮断する。

```
---
status: confirmed        # 終端カテゴリ (集約=確定/対象外) は confirmed。進行中 (未着手/収集中) は draft
category: database        # 章のカテゴリ id
aggregate: 確定           # 真理値表導出の集約状態 (未着手/収集中/確定/対象外)
spec_cells: [database.web, database.mobile, ...]   # 対応する spec-state マトリクスセル id
serves_goals: [G1, G2]    # 章が資する上位概念ゴール id (セル serves_goals の集約・要件 C9 anchor)
---
```

- **status**: `confirmed`=章凍結 (集約が終端の 確定/対象外)、`draft`=進行中。集約は宣言値ではなくセル状態から**真理値表で再導出**する (決定論)。
- **spec_cells**: 章が対応する `<category>.<platform>` セル id 一覧 (canonical platform 順)。
- **serves_goals**: 章の確定セルが資する上位概念ゴール id の和集合 (要件 C9 の anchor)。要件定義書 (`00-requirements-definition.md`) の goals へトレースし、どのゴールにも資さない収集を drift として `--require-foundation` が検出する。
- 各章本文は**カテゴリ別収集状態表** (未収集 / 対象外+理由 / 確定+qa_ref) と設計知識参照ポインタと最新ドキュメント出典表を持つ (要件 C1)。

## 単一 writer / 確定状態保全 (C01/C03)

`system-spec/` への正本書込経路は **C03 (本 skill) の `scripts/compile-spec-doc.py`** に一本化する。確定済み章の確定状態 (spec-state 確定セル・対象外理由) は保全され、勝手な巻き戻しをしない。これは C01 (spec-state.json の単一 transition writer) と対をなす**二輪の単一 writer**であり、C11 hook はこの正本防御を二重化する fail-closed の補助防御にすぎない (正本防御は writer 側が担う)。spec-state 上でセルが R4-reopen 済み (再オープン) のときだけ、該当章を draft へ戻して再レンダリングできる。

## 手順 (責務プロンプト正本 = prompts/*.md)

1. **R1-assemble** (`prompts/R1-assemble.md`): spec-state.json の `requirements_foundation` (上位概念) を先頭章に、収集済みカテゴリ×プラットフォーム結果を各技術章に組み立てる (カテゴリ順・canonical platform 順・集約状態を真理値表導出)。
2. **R2-render** (`prompts/R2-render.md`): 章立てに沿って章別 Markdown へレンダリングし、設計知識参照 (C04) と最新ドキュメント出典 (fetched-references) を各章へ、各技術章 frontmatter へ `serves_goals` (上位概念トレース) を反映する。
3. **R3-crosslink** (`prompts/R3-crosslink.md`): 全章横断の `index.md` を生成し、要件定義書を先頭に、各章と収集マトリクス集約状態 (未着手/収集中/確定/対象外) を相互参照可能にする。

決定論の組み立て・frontmatter 生成・index 相互参照は `scripts/compile-spec-doc.py` (Python 標準ライブラリのみ) が担い、責務プロンプトは判断・章構成の意味付けを担う (機械=再現性 / AI=自由度の二層分離)。

## Key Rules

1. **確定性優先**: 集約状態・確定マーカーは spec-state のセルから真理値表で**再導出**し、宣言値を鵜呑みにしない。
2. **入力非改変**: spec-state.json / fetched-references.json を書換えない (読むだけ)。
3. **出典必須**: 章に反映する最新ドキュメントは source_url・公式発行元・version|last_updated・取得/最新確認日時を伴う (C13 が形式検証)。
4. **対象外は理由付き**: 対象外セルは必ず理由 (または承認参照) を章へ明示する (C12 が検証)。
5. **日本語成果物**: 章・index の本文は日本語 (カテゴリ id・platform id・JSON キーは英語)。

## ゴールシーク実行

IN1/OUT1 の未達ゲートを起点に assemble/render/crosslink の該当責務だけを再実行する。各反復で決定論ゲートを先に通し、最大5周で未達なら成果物を確定せず呼出元へ blocker を返す。全ゲートPASS時だけ完了する。

## Feedback Contract (with-feedback-contract / with-goal-seek)

- **IN1** (inner, script): 生成直前の spec-state.json / fetched-references.json に対し `../../scripts/validate-coverage-matrix.py --matrix <spec>` と `../../scripts/validate-source-citation.py --targets <spec> --references <refs>` が exit0。
- **OUT1** (outer, test): 生成ドキュメントセットがカテゴリ×プラットフォームの確定/対象外理由と最新ドキュメント出典を含むことを `tests/test_compile_spec_doc.py` が確認。
- goal-seek (engine=inline, fork=subagent, max_loops=5): IN1/OUT1 を満たすまで章構成・レンダリングを反復改善する。

## Additional Resources

`references/resource-map.yaml` を最初に読む。主要参照:

- `scripts/compile-spec-doc.py` — 要件定義書 (00-requirements-definition.md) + 章別 Markdown + index.md の決定論コンパイラ (frontmatter 確定マーカー / serves_goals / 状態表 / 出典表 / 相互参照)
- `references/chapter-template.md` — 章 Markdown の構造テンプレート
- `prompts/R1-assemble.md` / `prompts/R2-render.md` / `prompts/R3-crosslink.md` — R1/R2/R3 責務別プロンプト
- 入力: `spec-state.json` (C01) / `fetched-references.json` (C02) / `../ref-system-design-knowledge/references/*.md` (C04)
- 決定論ゲート: `../../scripts/validate-coverage-matrix.py` (C12) / `../../scripts/validate-source-citation.py` (C13)
