# 03. YAML / Frontmatter（先頭メタ情報） 設計判断

## このファイルの責務

`SKILL.md` frontmatter の **設計判断・組み合わせ事故・運用ルール** を保持する。公式 field 一覧・型・default 値・cap 数値は記載しない。

**更新責務マトリクス**: 公式 frontmatter field の追加・廃止・default 変更・1,536 文字 cap 変更などは `16` のみを更新する。本ファイルは「どの組み合わせで設計事故が起こるか」「`description` をどう書くか」が変わったときだけ更新する。

→ 公式 frontmatter 全項目仕様は [16-official-skills-complete-reference.md §10](./16-official-skills-complete-reference.md#10-frontmatter-全項目)
→ String substitutions (`$ARGUMENTS`, `${CLAUDE_SKILL_DIR}` 等): [§11](./16-official-skills-complete-reference.md#11-string-substitutions-全項目)
→ Pre-approve tools (`allowed-tools` 仕様): [§15](./16-official-skills-complete-reference.md#15-pre-approve-tools)
→ Passing arguments: [§16](./16-official-skills-complete-reference.md#16-passing-arguments)
→ Dynamic context injection (`!`): [§17](./16-official-skills-complete-reference.md#17-dynamic-context-injection)
→ `context: fork`: [§19](./16-official-skills-complete-reference.md#19-run-skills-in-a-subagent)
→ Multi-project rubric composition (`rubric_refs` 詳細): [29-multi-project-rubric-composition.md](./29-multi-project-rubric-composition.md)

## 構成レベル別 frontmatter（設計テンプレート）

公式仕様上、frontmatter field はすべて optional であり、`description` だけが推奨である（正本は `16`）。このファイルでいう「最小構成」「推奨構成」は本設計書の出荷基準であり、公式必須項目ではない。

### 最小構成

```yaml
---
name: ref-project-rules
description: Project rules. Use when editing or reviewing this repository.
---
```

使う場面: reference content / low-risk skill / まず発動確認したい初期段階。

### 推奨構成

```yaml
---
name: run-release-check
description: Release check. Use when the user asks to verify a release.
argument-hint: "[version]"
arguments: [version]
disable-model-invocation: true
allowed-tools:
  - Bash(git status *)
  - Bash(gh *)
---
```

使う場面: user-facing workflow / 引数あり / 副作用または準副作用あり / tool preapproval が必要。

### 高度構成

```yaml
---
name: assign-skill-review-evaluator
description: Skill review evaluator. Use internally to evaluate SKILL.md design.
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Grep
hooks: []
paths:
  - ".claude/skills/**/SKILL.md"
model: inherit
effort: high
pair: assign-skill-review-generator
kind: evaluator
---
```

使う場面: internal evaluator / generator、forked subagent 実行、file pattern で対象を絞る、独自 metadata を lint / CI で検査。

## 組み合わせ事故（重要）

| 組み合わせ | 結果 | 使ってよい条件 |
|---|---|---|
| `disable-model-invocation: true` のみ | user は `/skill` で呼べる。Claude は呼べない | deploy / send / commit など手動 workflow |
| `user-invocable: false` のみ | user menu から隠れる。Claude / parent Skill は呼べる | `assign-*` internal worker |
| 両方 true | user からも Claude からも通常 invocation できない | Read 経由専用 reference として **設計した場合だけ** |
| `disable-model-invocation: true` + subagent `skills:` preload | preload されない | 矛盾。subagent が読みたいなら disable しない |
| `context: fork` + reference のみの本文 | subagent が task を持たず空回り | actionable Skill にだけ fork を付ける |

## `description` 設計規律

`description` は紹介文ではなく、Claude が「この Skill を読むべきか」を判断するための **trigger 条件**。

悪い例:
```yaml
description: スキルレビュー機能。スキル設計を採点するためのスキルです。
```

良い例（日本語）:
```yaml
description: スキル設計の評価器。SKILL.md をレビュー対象としたいとき、rubric 準拠を確認したいときに使う。
```
※ description は**日本語で書く**（必須）。英語の良い例は参考目的の参照に留め、出荷スキルでは日本語で記述する。発動キーは「〜とき」「〜場合」を 2 個（rubric FM-003 / lint R1 の hard rule）。

設計規律（必須3点 / 2個ルール）:

1. **発動トリガー句は 2 個前後（hard rule: ≤ 2）** — 1 個では Claude が user 発話と照合する鍵が不足し、3 個目以降は次のどちらかに化けやすい: (a) 重複 (b) 処理の流れが紛れ込む。原典 L504 の「上限は 2 個前後」を本群では **≤ 2 を hard rule** とする（cap 1,536 字の余裕確保も兼ねる）。
2. **動詞や手順で「いつ呼ぶか」を書く** — 「〜とき」「Use when the user asks to …」の動作主導形式。発動条件としての動詞であり、処理の動詞ではない。
3. **動作詳細を description に混ぜない** — 「採点する」「JSON で返す」「4 枚並列実行」「2 段階レビューする」「N 個のパラダイム」のような処理の流れ・段数・出力形式は description に書かない。本文側へ。これが実行されてしまうのを防ぐため

3 つの落とし穴 (anti-patterns):

- **(a) 発動ワードがない、または多すぎる** — 0 個は鍵不足で発動しない、3 個以上は重複/処理流れに化ける。
- **(b) 役割・派生元・採点根拠が description に混ざる** — `assign-*-evaluator` なら何の ref を根拠とするか、`wrap-*` なら何の base を呼び出すかを、description ではなく frontmatter の 1 行（`kind` / `pair` / `base` / `rubric_refs` / `reference_refs`）で示す。description は「いつ呼ぶか」専用。
- **(c) 動詞や手順で動作説明が混じっている** — description は呼び出しトリガーだけ。動作はすべて本文へ。

補助規律:

- 呼ばれた後の手順や段数は本文へ書く。
- 出力形式や JSON の詳細は本文へ。
- **先頭に最も重要な use case** を置く（cap で truncate されても残るように）。
- 末尾は「使う。」「読む。」「起動する。」のいずれかに統一する（後段機械検査で使用）。

機械強制:

- `scripts/lint-skill-description.py` が R1–R5 (trigger ≤ 2 / banned terms / paradigm列挙 / ≤ 280字 / 末尾統一) を強制する。
- 違反は `creator-kit/config/governance-policy.json` の `machine_enforcement.linked_lints` 経由で CI ゲート対象。
- rubric.json `FM-003` と lint R1 は `count == 2` に揃える（hard rule 一致）。設計書本節・rubric・lint の三点同期が崩れたら本節を正本とする。

良い例 / 悪い例:

```yaml
# Good: 発動条件 2 個・動詞ベース・動作詳細なし
description: Skill design evaluator. Use when the user asks to "review a Skill" or score a SKILL.md against the rubric.

# Bad: 発動条件 4 個（重複）+ 動作詳細「JSON で返す」混入
description: スキル評価。「skillレビュー」「SKILL.md採点」「スキル設計の評価」「Skill品質チェック」で発動しJSONで返す。

# Bad: 発動条件 1 個（鍵不足）+ 動作詳細「2 段階レビュー」混入
description: コードレビュー。仕様準拠と品質を 2 段階でレビューする。
```

## `when_to_use` の使いどころ

`description` だけでは説明不足な場合の補助。**`description` + `when_to_use` 合算が 1,536 文字 cap**（→ [§10](./16-official-skills-complete-reference.md#10-frontmatter-全項目)）に含まれることに注意。

- `description` では短すぎる例示の追加
- file type / domain の補足
- 誤発動しやすい近接 Skill との境界条件

## `allowed-tools` の落とし穴

`allowed-tools` は **deny ではなく allow** であることを誤解しやすい（→ [§15](./16-official-skills-complete-reference.md#15-pre-approve-tools)）。

設計ルール:

- `allowed-tools` だけでは Write / Edit を禁止できない。
- 禁止は `permissions.deny` で行う（→ [04-invocation-permissions-settings.md](./04-invocation-permissions-settings.md)）。
- Project Skill に broad `allowed-tools` を置く場合は **repository trust と security review** が必要。

## `context: fork` の適用判断

適用: heavy research / evaluator / independent review / 大量 reference 読み込み。
不適用: reference content だけ / actionable task がない guidelines。

**Why（理由）**: subagent は親 history を持たないため、prompt（= SKILL.md 本文）に task が明示されていなければ何も実行できない。

## `paths` の用途

特定 file pattern に関係する時だけ auto activation させたい Skill に使う（例: `packages/api/**`, `**/*.openapi.yaml`）。誤発動を防ぐ最も決定論的な手段。

## 独自メタデータ（CI/lint で強制）

Claude Code が公式に解釈しないが、設計・棚卸し・lint に使うフィールド。

| フィールド | 用途 | 対象 |
|---|---|---|
| `base` | 派生元 Skill | `wrap-*` |
| `pair` | generator / evaluator の相方 | `assign-*` |
| `kind` | 粒度や分類 | `ref-*` |
| `owner` | 保守責任者 | 全 Skill |
| `since` | 導入日 | 全 Skill |
| `deprecated_in` | 廃止予定 | 移行中 Skill |
| `replaces` | 置換元 | rename / refactor |
| `rubric_refs` | 評価基準への依存注入。`array of string`。例: `[ref-skill-design-rubric, references/project-x.yaml]`。不在 ref は `validate-frontmatter.py` が fail-fast（実装済み） | `assign-*-evaluator`, `run-build-*` |
| `reference_refs` | 根拠資料・用語集・API契約への依存注入。`array of string`。例: `[ref-company-security-rules, references/projects/acme/api-contract（契約）.yaml]` | `run-*`, `assign-*`, `delegate-*` |
| `script_refs` | 決定論的検査への依存注入。`array of string`。例: `[scripts/validate-frontmatter.py, scripts/lint-dependency-direction.py]` | `run-*`, `assign-*-evaluator`, Hook / CI |
| `merge_strategy` | rubric 合成戦略。enum `deep-merge \| strict \| override \| layered`（既定 `deep-merge`） | `assign-*-evaluator`, `run-build-*` |
| `conflict_policy` | 衝突時の解決方針。enum `most-specific-wins \| error \| warn-and-merge`（既定 `most-specific-wins`） | `assign-*-evaluator`, `run-build-*` |

**Why（理由）**: Claude Code が読まないからこそ、独自契約として CI で強制できる。公式 field と衝突しない領域に独自運用を寄せることで、公式 schema 変更の影響を受けない。

## `rubric_refs` による依存注入

**用途**: 評価基準（rubric）を SKILL.md 本文にハードコードせず、外部 reference として **依存注入** する仕組み。同一の evaluator Skill を複数プロジェクト・複数文脈で再利用するための中核。

**適用 Skill 種別**:

- `assign-*-evaluator` 系 — Skill 設計レビュー、コードレビュー、ドキュメント評価など、明示的な採点軸を持つ evaluator。
- `run-build-*` 系 — ビルド成果物の品質ゲート、リリース前チェックなど、project 固有の合否基準を読み込む runner。

**動作概要**:

1. evaluator/runner は本文に「評価手順」だけを書き、評価軸そのものは持たない。
2. `rubric_refs` に列挙された参照（Skill 名 or 相対 path）を `merge_strategy` に従って合成し、合成済み rubric を評価入力とする。
3. 衝突が起きた場合は `conflict_policy` に従って解決する（既定では最も具体的な ref が優先）。

**完全な frontmatter 例**:

```yaml
---
name: assign-skill-review-evaluator
description: Skill design evaluator. Use when the user asks to "review a Skill" or score a SKILL.md.
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Grep
model: inherit
effort: high
pair: assign-skill-review-generator
kind: evaluator
rubric_refs:
  - ref-skill-design-rubric            # 共通 baseline rubric
  - references/project-x-overrides.yaml # project 固有上書き
merge_strategy: deep-merge
conflict_policy: most-specific-wins
---
```

**設計規律**:

- evaluator は `rubric_refs` を **必須** とし、本文には評価軸を書かない（軸の散在を防ぐ）。
- `merge_strategy: strict` は ref 間に同一 key があるだけで失敗するため、契約安定性が必要な CI gate に限定する。
- `conflict_policy: error` は「予期せぬ上書きを禁じたい」ケース、`warn-and-merge` は「合成は行うが lint で検知したい」ケースに使う。

詳細な合成アルゴリズム・複数 ref のレイヤー順・project ↔ user ↔ plugin 階層の解決ルールは [29-multi-project-rubric-composition.md](./29-multi-project-rubric-composition.md) を参照。

## `reference_refs` / `script_refs` の使い分け

`rubric_refs` は「何を合格とするか」を注入する。これに対して、`reference_refs` は「判断の根拠資料」、`script_refs` は「機械判定の実行入口」を注入する。

```yaml
reference_refs:
  - ref-company-security-rules
  - references/projects/acme/api-contract（契約）.yaml
  - references/projects/acme/domain-dictionary.yaml
  - references/tasks/task-123/acceptance.yaml
script_refs:
  - scripts/validate-frontmatter.py
  - scripts/validate-rubric-composition.py
  - scripts/lint-dependency-direction.py
```

設計規律:

- `reference_refs` は read-only。根拠資料を読ませるだけで、評価基準の点数化は `rubric_refs` に寄せる。
- `script_refs` は P0 判定。exit code / JSON / stdout を評価入力にし、LLM が機械判定を上書きしない。
- 参照順は L0 company → L1 domain/project → L2 task → artifact-local criteria とする。
- 不在 ref は warning ではなく fail-fast。必要情報が欠けたまま合格させない。

---

## 独自拡張フィールド（A3/C3 パッチ — 慣習の明示）

本設計書では Claude Code 公式 frontmatter フィールドに加えて、以下の**独自拡張フィールド**を使用している。これらは Claude Code 公式仕様には存在せず、本リポジトリの設計慣習として定めたものである。

| フィールド | 型 | 用途 | 正本 |
|---|---|---|---|
| `pair:` | string | generator/evaluator のペア関係を宣言 | 本設計書 09章 |
| `kind:` | string (run\|ref\|assign\|wrap\|delegate) | スキル種別を機械読み取り可能な形で宣言 | 本設計書 06章 |
| `owner:` | string | 管理チーム | 本設計書 23章 |
| `rubric_refs:` | list | 参照する rubric ファイルのパスリスト | 本設計書 29章 |
| `merge_strategy:` | string (deep-merge\|strict\|override\|layered) | rubric 多重継承時の合成戦略 | 本設計書 29章 |
| `conflict_policy:` | string (most-specific-wins\|error\|warn-and-merge) | rubric 衝突時の解決方針 | 本設計書 29章 |
| `context-budget:` | comment形式 | 章ロード上限 (CD-005 context予算制約) | 本設計書 25章 |

### 重要な注意

- `pair:` / `rubric_refs:` / `merge_strategy:` / `conflict_policy:` は Claude Code が自動解釈するフィールドではない。これらは**人間および Claude への設計意図の伝達**が目的であり、Claude Code ランタイムが直接参照するわけではない。
- `kind:` も同様に独自拡張。公式には `description` のみが invoke 判定に使われる。
- validate-frontmatter.py がこれらの独自フィールドを検証する際は、公式仕様との混同を避けるため、独自フィールドを別セクション（`# xl-skills custom fields`）としてコメントで明記することを推奨する。

### lint での扱い

`validate-frontmatter.py` は独自フィールドを「警告なし」で通過させる。ただし `merge_strategy` / `conflict_policy` は29章の enum に対して検証する。公式フィールドと独自フィールドの混在は設計上意図されたもので、エラーではない。

TODO(human): 将来 Claude Code 公式が `kind:` / `pair:` 相当を正式採用した場合は、本節の独自拡張表から削除し 16章へ移動すること。
