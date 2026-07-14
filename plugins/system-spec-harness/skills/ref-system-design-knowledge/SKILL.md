---
name: ref-system-design-knowledge
description: システム設計知識の深いカード・一次資料・鮮度やシステム構成カテゴリのseed初期集合を参照したいとき、seed外の設計知識をopen-worldで発見・拡張したいときに使う。
disable-model-invocation: true
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-07-11
version: 0.1.0
source: plugins/system-spec-harness/skills/ref-system-design-knowledge/references/system-category-taxonomy.json
source-tier: internal
last-audited: 2026-07-11
audit-trigger: official-update
responsibility_refs:
  - prompts/R1-system-design-knowledge.md
schema_refs:
  - references/knowledge-card.schema.json
completeness_exempt:
  - "manifest: ref/effect:none exposes immutable reference material and has no executable workflow phases."
allowed-tools:
  - Read
---

# ref-system-design-knowledge

## Purpose & Output Contract

システム構築の仕様ヒアリングで参照する**設計知識の参照正本**。`run-system-spec-elicit` (C01) がカテゴリ初期集合を、`run-system-spec-compile` (C03) が各章の設計知識ポインタを、本スキルの `references/` から引く。

**入力**: 参照要求カテゴリ (設計知識領域 or システム構成カテゴリ taxonomy)。
**出力**: 該当知識領域の深い知識カード、一次資料・鮮度情報、open-world発見playbook、およびカテゴリ×プラットフォーム taxonomy。
**完了条件**: 参照のみ。個別プロジェクトの設計判断そのものは elicit/compile 側の責務 (本スキルは知識源であって意思決定者ではない)。

境界: `references/` 配下の `system-category-taxonomy.json` は **C01 のカテゴリ初期集合の正本を兼ねる** (prompt へ直書きせず本ファイルを SSOT とする)。現行6領域と8カテゴリは網羅リストではなく **seed examples** である。C04 は `ref/effect:none` のため発見・取得・永続化を実行せず、発見方法と品質契約だけを提供する。実プロジェクトの discover/公式一次資料取得/project candidate 記録は C01/C02、curated promotion は保守担当の承認付き更新が担う。

各知識カードは `references/knowledge-card.schema.json` の必須概念に従い、目的・背景・解決する問題・中核概念・適用条件・非適用条件・トレードオフ/失敗モード・目的達成への寄与・一次資料・鮮度を保持する。浅い pointer-only 要約は正本カードとして受け入れない。

### 知識依存グラフ (goal-spec C13/C14)
`references/knowledge-catalog.json` は各 entry が typed 辺 (`depends_on` / `refines` / `conflicts_with`) を持つ**知識依存グラフ**である。`A depends_on B` は「B が前提で B を A より先に出す」precedence DAG で、循環/dangling/root到達性/孤立 node と辺型則 (`refines`=有向精緻化・非循環、`conflicts_with`=対称非順序) を `$CLAUDE_PLUGIN_ROOT/scripts/validate-knowledge-graph.py --profile knowledge` が検証する。C01 (R5) / C03 (R2) はこの validator の位相順 (`--order`・上位概念→下位概念、同順位 knowledge_id 昇順) を**同一 JSON として消費**し、設計知識を上流から下流の順で章へ反映する。この validator が保証するのは well-formedness (形状・辺型則・写像全射) と位相順の決定性のみで、知識辺の意味妥当性 (依存関係が設計上正しいか) は content-review/human の未閉塞責務である。

### doctrine anchor 写像 (goal-spec C15)
`references/doctrine-anchor-registry.json` は正本単位を system category でなく**design concern** とし、7 concern を 4 authority (presentation=Apple HIG / application-architecture・data-access=Clean Architecture / security・authentication=OWASP ASVS+Secrets Management / reliability・operations=Google SRE) へ **1 concern 1 authority** で固定する (authority は 4 種で application-architecture↔data-access 等の複数 concern に共有されうる)。全 in-scope category は必要 concern へ全件写像され、C03 が各章生成時に category→concern→authority を**上流指針として反映**する (具体技術は直書きせず上流工程を導く)。registry 形状・concern_id 一意性 (authority 一意性ではない)・カテゴリ写像全射は `$CLAUDE_PLUGIN_ROOT/scripts/validate-knowledge-graph.py --profile doctrine` が、意味反映は content-review/human が検証する。未帰属 category は owner/reason/approval_state を持つ pending 例外として compile を保留する。

## 参照知識領域 (references/)

| 領域 | ファイル | 要点 |
|---|---|---|
| Clean Architecture | `references/clean-architecture.md` | 依存を内向きに保ち中核ルールを技術変化から守る (変更/テスト容易性の崩壊を防ぐ) |
| Design Patterns | `references/design-patterns.md` | 変わる軸を局所化し変更の波及を止める設計語彙 (解く問題で選定・過剰適用回避) |
| API Design Patterns | `references/api-design-patterns.md` | 他者依存の契約を壊さず進化させ再送安全にする (冪等性/後方互換/一貫エラー契約) |
| Secure by Design | `references/secure-by-design.md` | 攻撃者前提で被害を封じ込める設計 (最小権限/多層防御/fail-closed/脅威モデル) |
| DDD (ドメイン駆動設計) | `references/ddd.md` | ドメインの複雑さに境界と共通言語で対処 (境界づけられたコンテキスト/集約/コアドメイン) |
| Clean Code | `references/clean-code.md` | 変更し続けられる可読性を保つ (意図の命名/単一責務/副作用局所化/テスト容易性) |
| システム構成 taxonomy | `references/system-category-taxonomy.json` | カテゴリ×canonical platform id (C01 初期集合の正本) |
| Open-world lifecycle | `references/open-world-knowledge-lifecycle.md` | discover→qualify→deepen→goal map→candidate→promotion→freshness audit |
| Knowledge catalog | `references/knowledge-catalog.json` | seed/card metadata と深度・鮮度 + typed 辺 (depends_on/refines/conflicts_with) の知識依存グラフ (goal-spec C13) |
| Doctrine anchor registry | `references/doctrine-anchor-registry.json` | design concern→doctrine authority (Apple HIG/Clean Arch/OWASP/SRE) と全 category→concern 写像 (goal-spec C15) |
| Card schema | `references/knowledge-card.schema.json` | 深い知識カード/project candidate の必須契約 |

## 使い方

1. カテゴリ初期集合が必要なとき (C01 R1-init): `references/system-category-taxonomy.json` を Read し `categories` / `platforms` を取得する。
2. 設計知識ポインタが必要なとき (C03 R2-render): 該当領域の `references/*.md` を Read し要点と一次資料 URL を章へ反映する。
3. seed外の知識候補が必要なとき: `references/open-world-knowledge-lifecycle.md` を Read し、C01/C02 に発見・一次資料qualification・project candidate作成を委譲する。C04自身は検索や書込を行わない。
4. 設計知識を位相順で消費するとき (C01 R5 / C03 R2): `$CLAUDE_PLUGIN_ROOT/scripts/validate-knowledge-graph.py --profile knowledge --input references/knowledge-catalog.json --order` の topo_order に従い上位概念→下位概念の順で反映する。
5. 章の上流指針が必要なとき (C03 R2): `references/doctrine-anchor-registry.json` の `category_concern_map` から対象カテゴリの concern を引き、`concerns[].authority` を上流 doctrine として章へ反映する (`$CLAUDE_PLUGIN_ROOT/scripts/validate-knowledge-graph.py --profile doctrine` で写像全射を事前検証)。

## 責務プロンプト

- `prompts/R1-system-design-knowledge.md` — 参照要求カテゴリを受けて該当 references を案内する 7 層責務プロンプト。
