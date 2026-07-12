# 23a prefix 駆動型内部構造規約と manifest 駆動 contract モデル

作成日: 2026-05-22
位置付け: 23章 (meta-skill-architecture) の補章であり、各 Skill の **内部構造** を prefix によって非対称に規定する正本。
適用範囲: `plugins/<plugin>/skills/<skill-name>/` 配下の構成と、それを支える `workflow-manifest.json` / `schemas/` / `prompts/` の契約。

> 本章の核心キーワード「prefix駆動型」「manifest駆動contract」「三層contractモデル」は本章でのみ定義する。他章は参照リンクのみ。

> **Capability 抽象への汎化注記 (2026-05-22):** 本章が定義する三層 contract モデル (`workflow-manifest.json` + `schemas/` + `prompts/<R-id>.md`) は、当初 `kind: skill` を前提として書かれたが、23章 § Capability 抽象への拡張 にて Skill / Agent / Hook / Command / Plugin-Composition / Prompt / Workflow の 7 kind 横断に汎化された。本章の **prefix 規約は `kind: skill` 配下のサブ分類** として継続有効であり、他 kind の Capability も同一の三層 contract に従う (intent/interface/invariant の写像は 23章 § Capability 横断適用 表を参照)。Capability の共通核スキーマ正本は `plugins/harness-creator/skills/run-build-skill/references/capability-manifest.schema.json`。

---

## § 1 背景と問題提起

2026-05 までの elegant-review で観察された Skill 品質劣化には、再現性の高い 2 つの構造的ループが存在した。

1. **SKILL.md 散文肥大ループ**: Step / Gate / Key Rules / Decision Table を SKILL.md 本文に散文で直書きする結果、SKILL.md が 300 行 hard cap を突破し、Progressive Disclosure（07章）の前提が崩れる。散文は機械検証できないため、改訂のたびに齟齬が増殖する。
2. **蓄積断絶ループ**: `prompts/` ディレクトリ規約が存在するのに実体 0 件、`changelog/` `lessons-learned/` `EVALS.json` が plugin 直下に揃わない、`rubric.json` がルート直と `references/` 配下に混在する、といった配置ばらつきにより、改善知見がスキル間に蓄積されず、同じ失敗が再発する。

両ループの根因は **「prefix が宣言する実行モードと、内部構造との対応が暗黙のまま放置されている」** ことにある。本章は対応を明文化し、`SKILL.md` を宣言の参照役に降格させ、契約（contract）を機械可読側へ移管する。

---

## § 2 原則

### 原則A: prefix が実行モードを宣言する

5 prefix（06章で確立済み）は、単なる命名規約ではなく **実行モードの宣言** として扱う。

| prefix | 実行モード | 出力性質 |
|---|---|---|
| `run-*` | workflow runner（phase + gate を進める） | 副作用あり成果物 |
| `ref-*` | knowledge dictionary（Read-only 辞書） | 知識参照 |
| `assign-*` | judge / evaluator（rubric に従う採点） | score + findings |
| `delegate-*` | external delegate（SubAgent / 外部スキルへ委譲） | handoff payload |
| `wrap-*` | wrapper / adapter（既存資産を Skill 化） | 変換後の interface |

### 原則B: 内部構造は prefix に応じて非対称に決まる

「全 Skill に同一の `references/` `scripts/` `templates/` を強制する」設計を**禁止**する。prefix が宣言した実行モードに必要なディレクトリだけを設置する。非対称性こそが破綻防止の本体である。

### 原則C: contract は機械可読側で固定する

Step / Gate / handoff の正本は `workflow-manifest.json` + `schemas/` + `prompts/<R-id>.yaml` の三層 contract に置く。SKILL.md は **これらを参照するだけ** の宣言役に徹し、散文に同じ内容を写経しない。これを **manifest駆動contract** と呼ぶ。

---

## § 3 prefix × 内部構造 対応表

| prefix | prompts/ | agents/ | schemas/ | templates/ | references/ | manifest | 主用途 |
|---|---|---|---|---|---|---|---|
| `run-*` | 必須 | 任意 | 必須 | 任意 | 補助 | 必須 | workflow runner |
| `ref-*` | 必須 | — | 任意 | — | 必須 | — | knowledge dictionary |
| `assign-*` | 必須 | — | 必須 | — | rubric | — | judge / evaluator |
| `delegate-*` | 必須 | 必須 | 必須 | 任意 | 接続仕様 | 任意 | external delegate |
| `wrap-*` | 必須 | — | 必須 | 必須 | — | — | wrapper / adapter |

凡例: 「必須」= 欠落で lint FAIL、「任意」= 必要に応じて設置、「—」= 設置禁止（無関係なディレクトリの追加を不許可とする）。

---

## § 4 各ディレクトリの役割定義（三層 contract モデル）

> **Capability 共通核との接続**: 本節 4.1〜4.6 は `kind: skill` の場合の具体配置を示すが、他 kind (`agent / hook / command / plugin-composition / prompt / workflow`) の Capability も、共通核フィールド (`name / description / kind / version / owner / tags / since`) は `CapabilityManifest` として `plugins/harness-creator/skills/run-build-skill/references/capability-manifest.schema.json` に従って宣言する。kind 固有スキーマは同 schema に注入される (23章 § Capability 抽象への拡張 を参照)。

### 4.1 workflow-manifest.json （第1層: 実行手順の正本）

`run-*` および任意で `delegate-*` に設置。phases 配列で実行順序・ゲート・依存・hook を宣言する。

```jsonc
{
  "phases": [
    {
      "id": "P1-discovery",
      "step": 1,
      "gate": "C1",
      "dependsOn": [],
      "entryHook": "preload-resource-map",
      "exitHook": "validate-build-trace",
      "resourceIds": ["resource://rubric/v1"],
      "delegateSkill": null,
      "fatal_exit_codes": [2, 3]
    }
  ]
}
```

必須キー: `id` / `step` / `gate` / `dependsOn` / `entryHook` / `exitHook` / `resourceIds` / `delegateSkill` / `fatal_exit_codes`。SKILL.md の散文 Step 記述は本ファイルへの参照に置換する。

### 4.2 schemas/ （第2層: handoff 型の正本）

Skill 間 / phase 間で受け渡される JSON の型を JSON Schema として固定する。各 `.json` には次が必須:

- `$schema` (Draft URI)
- `$id` (skill 名 + handoff 名で一意)
- `title`
- `required`
- `additionalProperties: false`

kind → template 対応表のような宣言性の高い情報も schemas/ へ外出しする。

### 4.3 prompts/<R-id>.md （第3層: 責務単位の prompt 正本、Markdown 既定）

`responsibility_refs` と一対一対応する固定 slot 構造で記述する。
**新規 prompt は Markdown (`.md`) を既定形式**とし、骨格は
`plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-markdown-template.md`
を写経する。1 ファイル = 1 責務 = 1 agent。

YAML (`.yaml`) は既存資産のみ legacy として許容し、新規作成は禁止 (lint で warn)。
JSON は tool args として埋め込む場合のみ許容。

Markdown 形式の必須見出し (7 層):

```markdown
## メタ (responsibility, output_schema, layers_covered)
## Layer 1: 基本定義層 (不変ルール / 倫理ガード)
## Layer 2: ドメイン層 (責務 / 入力契約 / 出力契約)
## Layer 3: インフラ層 (参照リソース / 外部ツール)
## Layer 4: 共通ポリシー層 (失敗時 / 観測 / セキュリティ)
## Layer 5: エージェント層 (担当 agent / 推論手順 / 自己検証)
## Layer 6: オーケストレーション層 (上位接続 / 並列性)
## Layer 7: UI / 提示層 (提示形式 / 言語)
## 出力指示 (LLM 実行時に読む箇所)
```

参考 YAML (legacy):

```yaml
name: R1-elicit
responsibility: <1行宣言>
expected_output_schema: schemas/handoff-r1.json
self_evaluation_checklist: [...]
```

### 4.4 references/ （Progressive Disclosure 対象）

`resource-map.yaml` で `when_to_read` を誘導する knowledge 群。`ref-*` では中核、`run-*`/`assign-*` では補助。`assign-*` の `rubric.json` は **必ず** `references/rubric.json` 配下に置き、ルート直配置を禁止する。

### 4.5 agents/ （SubAgent 定義）

`delegate-*` または `run-*` のみ設置可。frontmatter に `owner_skill` を必須化し、agents が skill 外に集約され owner 未明記となる状態（elegant-* の旧形式）を禁止する。

### 4.6 templates/ （scaffold 雛形）

`wrap-*` または `run-*` の scaffold 用。生成対象の SKILL.md / config を雛形として保持する。

---

## § 5 再現性保証メカニズム

1. **manifest 機械検証**: `lint-manifest-contents.py` を拡張し、`workflow-manifest.json` の必須キー欠落・phase 番号の不連続・`dependsOn` の循環を検出する。
2. **schemas による handoff 型検査**: `validate-build-trace.py` を schema 駆動に切り替え、phase 間 handoff を schemas/ の `$id` で参照解決する。
3. **prompts/<R-id>.yaml の self_evaluation_checklist 埋め込み**: prompt 自身に自己採点項目を持たせ、SubAgent が出力前に自己検査できるようにする。
4. **三点蓄積による FB ループ閉鎖**: plugin 直下に `EVALS.json` + `changelog/` + `lessons-learned/` を揃え、改善知見が次回起動時に必ず読み込まれる状態を作る。

---

## § 6 SKILL.md 圧縮ルール

- 散文の Step / Gate 記述は `workflow-manifest.json` への参照に置換する
- kind → template 対応表など宣言性の高い情報は `schemas/` へ外出しする
- frontmatter に `responsibility_refs` と `manifest` を追加し、参照を明示する
- 目標行数:

| prefix | SKILL.md 目標行数 |
|---|---|
| `run-*` | ≤ 180 |
| `ref-*` | ≤ 120 |
| `assign-*` | ≤ 150 |
| `delegate-*` | ≤ 120 |
| `wrap-*` | ≤ 100 |

---

## § 7 アンチパターン

| # | アンチパターン | 何が壊れるか |
|---|---|---|
| A1 | SKILL.md に Step / Gate / Key Rules を散文直書き | 機械検証不能、改訂のたびに齟齬増殖 |
| A2 | `prompts/` ディレクトリ規約があるのに実体 0 件 | 責務単位の prompt が SKILL.md に逆流し肥大 |
| A3 | `rubric.json` placement 混在 (ルート直 vs `references/`) | lint が不安定、横断比較が不可能 |
| A4 | `elegant-*` のように agents が skill 外に集約され `owner_skill` 未明記 | 所有関係が断絶、agents の改訂責任が不明 |
| A5 | `changelog/` / `EVALS.json` 不在で改善が蓄積しない | 同一失敗が再発、FB ループが閉じない |

---

## § 8 参考実装との比較

| 観点 | `doc/参考Skill/harness-creator/` | 本章が定める prefix 駆動型 |
|---|---|---|
| 構造単位 | 単一スキル内マルチ責務（1 SKILL.md に build / lint / eval が同居） | 横展開 + 内部規約（prefix 別 Skill に分離し、内部は非対称） |
| contract の置き場 | SKILL.md 散文 + scripts/ の README | `workflow-manifest.json` + `schemas/` + `prompts/<R-id>.yaml` の三層 |
| 蓄積基盤 | scripts 出力に依存 | plugin 直下 `EVALS.json` + `changelog/` + `lessons-learned/` |
| 改訂耐性 | 散文が肥大化しやすい | 機械可読 contract が散文を抑制 |

---

## § 9 関連章

- 06章: prefix と命名規約の条文（本章は内部構造側の補章）
- 07章: Progressive Disclosure（`references/` の when_to_read 誘導）
- 11章: 汎用テンプレート（本章は prefix 別に細分化した正本）
- 13章: チェックリスト（本章で追加する項目は 13章 へ反映）
- 23章: meta-skill アーキテクチャ全体像（本章はその内部構造側）
- 24章: メタSkill テンプレート（本章の三層 contract を反映する対象）
- 25章: メタSkill 運用 Runbook
- 26章: dogfooding（本章規約の自己適用）
- 27章: rubric governance Runbook
- 33章: 変更ガバナンス（本章新設は impact=high で履歴記録）
