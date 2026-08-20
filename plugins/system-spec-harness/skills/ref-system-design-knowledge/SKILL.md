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
  - ../../schemas/information-priority-map.schema.json
script_refs:
  - ../../scripts/validate-knowledge-graph.py
  - ../../scripts/validate-information-priority.py
completeness_exempt:
  - "manifest: ref/effect:none exposes immutable reference material and has no executable workflow phases."
allowed-tools:
  - Read
runtime_root_policy: host-skill-path
---

# ref-system-design-knowledge

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

システム構築の仕様ヒアリングで参照する**設計知識の参照正本**。`run-system-spec-elicit` (C01) がカテゴリ初期集合を、`run-system-spec-compile` (C03) が各章の設計知識ポインタを、本スキルの `references/` から引く。

**入力**: 参照要求カテゴリ (設計知識領域 or システム構成カテゴリ taxonomy)。
**出力**: 該当知識領域の深い知識カード、一次資料・鮮度情報、open-world発見playbook、およびカテゴリ×プラットフォーム taxonomy。
**完了条件**: 参照のみ。個別プロジェクトの設計判断そのものは elicit/compile 側の責務 (本スキルは知識源であって意思決定者ではない)。

境界: `references/` 配下の `system-category-taxonomy.json` は **C01 のカテゴリ初期集合の正本を兼ねる** (prompt へ直書きせず本ファイルを SSOT とする)。現行の設計知識領域 (正本 = `references/knowledge-catalog.json` の entries。個数をここへ複製しない) と 8 カテゴリは網羅リストではなく **seed examples** である。C04 は `ref/effect:none` のため発見・取得・永続化を実行せず、発見方法と品質契約だけを提供する。実プロジェクトの discover/公式一次資料取得/project candidate 記録は C01/C02、curated promotion は保守担当の承認付き更新が担う。

各知識カードは `references/knowledge-card.schema.json` の必須概念に従い、目的・背景・解決する問題・中核概念・適用条件・非適用条件・トレードオフ/失敗モード・目的達成への寄与・一次資料・鮮度を保持する。浅い pointer-only 要約は正本カードとして受け入れない。

### 知識依存グラフ (goal-spec C13/C14)
`references/knowledge-catalog.json` は各 entry が typed 辺 (`depends_on` / `refines` / `conflicts_with`) を持つ**知識依存グラフ**である。`A depends_on B` は「B が前提で B を A より先に出す」precedence DAG で、循環/dangling/root到達性/孤立 node と辺型則 (`refines`=有向精緻化・非循環、`conflicts_with`=対称非順序) を `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-knowledge-graph.py --profile knowledge` が検証する。C01 (R5) / C03 (R2) はこの validator の位相順 (`--order`・上位概念→下位概念、同順位 knowledge_id 昇順) を**同一 JSON として消費**し、設計知識を上流から下流の順で章へ反映する。この validator が保証するのは well-formedness (形状・辺型則・写像全射) と位相順の決定性のみで、知識辺の意味妥当性 (依存関係が設計上正しいか) は content-review/human の未閉塞責務である。

### doctrine anchor 写像 (goal-spec C15)
`references/doctrine-anchor-registry.json` は正本単位を system category でなく**design concern** とし、7 concern を 4 authority (presentation=Apple HIG / application-architecture・data-access=Clean Architecture / security・authentication=OWASP ASVS+Secrets Management / reliability・operations=Google SRE) へ **1 concern 1 authority** で固定する (authority は 4 種で application-architecture↔data-access 等の複数 concern に共有されうる)。全 in-scope category は必要 concern へ全件写像され、C03 が各章生成時に category→concern→authority を**上流指針として反映**する (具体技術は直書きせず上流工程を導く)。registry 形状・concern_id 一意性 (authority 一意性ではない)・カテゴリ写像全射は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-knowledge-graph.py --profile doctrine` が、意味反映は content-review/human が検証する。未帰属 category は owner/reason/approval_state を持つ pending 例外として compile を保留する。

## 参照知識領域 (references/)

| 領域 | ファイル | 要点 |
|---|---|---|
| Clean Architecture | `references/clean-architecture.md` | 依存を内向きに保ち中核ルールを技術変化から守る (変更/テスト容易性の崩壊を防ぐ) |
| Design Patterns | `references/design-patterns.md` | 変わる軸を局所化し変更の波及を止める設計語彙 (解く問題で選定・過剰適用回避) |
| API Design Patterns | `references/api-design-patterns.md` | 他者依存の契約を壊さず進化させ再送安全にする (冪等性/後方互換/一貫エラー契約) |
| Secure by Design | `references/secure-by-design.md` | 攻撃者前提で被害を封じ込める設計 (最小権限/多層防御/fail-closed/脅威モデル) |
| DDD (ドメイン駆動設計) | `references/ddd.md` | ドメインの複雑さに境界と共通言語で対処 (境界づけられたコンテキスト/集約/コアドメイン) |
| Clean Code | `references/clean-code.md` | 変更し続けられる可読性を保つ (意図の命名/単一責務/副作用局所化/テスト容易性) |
| Information Design (情報設計) | `references/information-design.md` | 表現物の情報を「文脈→棚卸し→グループ化→優先順位→削減→加工→形式選定→強弱→装飾」の順で設計する (装飾は最後で意味を運ぶ役) |
| システム構成 taxonomy | `references/system-category-taxonomy.json` | カテゴリ×canonical platform id (C01 初期集合の正本) |
| Open-world lifecycle | `references/open-world-knowledge-lifecycle.md` | discover→qualify→deepen→goal map→candidate→promotion→freshness audit |
| Knowledge catalog | `references/knowledge-catalog.json` | seed/card metadata と深度・鮮度 + typed 辺 (depends_on/refines/conflicts_with) の知識依存グラフ (goal-spec C13) |
| Doctrine anchor registry | `references/doctrine-anchor-registry.json` | design concern→doctrine authority (Apple HIG/Clean Arch/OWASP/SRE) と全 category→concern 写像 (goal-spec C15) |
| Card schema | `references/knowledge-card.schema.json` | 深い知識カード/project candidate の必須契約 |

## 使い方

1. カテゴリ初期集合が必要なとき (C01 R1-init): `references/system-category-taxonomy.json` を Read し `categories` / `platforms` を取得する。
2. 設計知識ポインタが必要なとき (C03 R2-render): 該当領域の `references/*.md` を Read し要点と一次資料 URL を章へ反映する。
3. seed外の知識候補が必要なとき: `references/open-world-knowledge-lifecycle.md` を Read し、C01/C02 に発見・一次資料qualification・project candidate作成を委譲する。C04自身は検索や書込を行わない。
4. 設計知識を位相順で消費するとき (C01 R5 / C03 R2): `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-knowledge-graph.py --profile knowledge --input references/knowledge-catalog.json --order` の topo_order に従い上位概念→下位概念の順で反映する。
5. 人間が読む表現物 (画面・report・slide・CLI 出力・通知・エラーメッセージ) を設計/レビューするとき: `references/information-design.md` を Read し、成果物側は `../../schemas/information-priority-map.schema.json` 準拠の宣言を持つ。`python3 ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-information-priority.py <map.json>` が手順の順序制約 (順位確定→装飾) と削除/加工の説明責任を機械検査する (exit 0=OK / 1=違反 / 2=usage)。
6. 章の上流指針が必要なとき (C03 R2): `references/doctrine-anchor-registry.json` の `category_concern_map` から対象カテゴリの concern を引き、`concerns[].authority` を上流 doctrine として章へ反映する (`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-knowledge-graph.py --profile doctrine` で写像全射を事前検証)。

## Gotchas

- **exit 0 を「依存が正しい」と読まない**: validator の保証範囲は上の「知識依存グラフ」節の通り well-formedness だけ。カード追加時は本文で依存の理由を述べること — 機械は理由の不在を検出しない。
- **カード追加はカタログ 1 行では終わらない**: `references/*.md` 実体・`knowledge-catalog.json` entry・`resource-map.yaml` の `read_when` の三者が parity を保つ必要があり、加えて `read_when` の字面は下流の写像そのものである — `run-system-spec-compile` の `category_design_refs()` はハードコード表を持たず `read_when` へのカテゴリ id 部分一致で章の設計知識ポインタを導出する。`read_when` からカテゴリ名を言い換えただけで写像は静かに空へ落ちる (`../run-system-spec-compile/tests/test_compile_spec_doc.py::test_category_design_refs_derived_from_resource_map` が代表カテゴリを pin している)。
- **`resource-map.yaml` の path は `references/` からの相対**: skill 外の資産も載せてよく (`run-system-spec-elicit` が `../../../scripts/validate-coverage-matrix.py` を列挙している)、**基点は skill root ではなく `references/`** なので `../../scripts/…` と書くと 1 段浅く外して解決しない。この誤りは repo 内に実在する — `run-system-spec-compile` の resource-map の skill 外 3 entry は全て `../../scripts/*.py` で、`references/` 起点では 1 本も解決しない (真似る先を間違えないこと)。frontmatter 側は逆に **skill root 相対**なので、同じ資産を両方へ書くと段数が 1 つずれる (揃えられない)。ただし `validate-frontmatter.py:check_refs_exist` が実在検査するのは `rubric_refs` / `reference_refs` / `script_refs` の 3 つだけで、**`schema_refs` は検査対象外** — ここの段数ミスは機械では止まらない。
- **`kind: ref` は CI の content-review 対象外**: `scripts/lint-content-review.py` の `EXEMPT_KINDS` に `ref` が入るため verdict 不在でも CI は緑になる。一方 stop hook (`check-review-trigger.py`) には同じ除外が無いので、変更すればローカルではレビューを求められる。CI が緑=レビュー済み、と読み替えないこと。
- **`allowed-tools: [Read]` は事故防止であって不便ではない**: 検索・取得・書込を足したくなったら C01/C02 側へ置く (責務は上の「完了条件」と「境界」の通り)。ここに取得処理が入ると、参照した瞬間に内容が変わりうる正本になる。

## 責務プロンプト

- `prompts/R1-system-design-knowledge.md` — 参照要求カテゴリを受けて該当 references を案内する 7 層責務プロンプト。
