# 03. YAML / Frontmatter（先頭メタ情報） 設計判断

## このファイルの責務

`SKILL.md` frontmatter の **設計判断・組み合わせ事故・運用ルール** を保持する。公式 field 一覧・型・default 値・cap 数値は記載しない。

**更新責務マトリクス**: 公式 frontmatter field の追加・廃止・default 変更・1,536 文字 cap 変更などは `16` のみを更新する。本ファイルは「どの組み合わせで設計事故が起こるか」「`description` をどう書くか」が変わったときだけ更新する。

→ 公式 frontmatter 全項目仕様は [16-official-skills-complete-reference.md §10](./16-official-skills-complete-reference.md#10-frontmatter先頭メタ情報-全項目)
→ String substitutions (`$ARGUMENTS`, `${CLAUDE_SKILL_DIR}` 等): [§11](./16-official-skills-complete-reference.md#11-string-substitutions-全項目)
→ Pre-approve tools (`allowed-tools` 仕様): [§15](./16-official-skills-complete-reference.md#15-pre-approve-tools)
→ Passing arguments: [§16](./16-official-skills-complete-reference.md#16-passing-arguments)
→ Dynamic context injection (`!`): [§17](./16-official-skills-complete-reference.md#17-dynamic-context-injection)
→ `context: fork`: [§19](./16-official-skills-complete-reference.md#19-run-skills-in-a-subagent)
→ Multi-project rubric composition (`rubric_refs` 詳細): [29-multi-project-rubric-composition.md](./29-multi-project-rubric-composition.md)

## 構成レベル別 frontmatter（設計テンプレート）

公式仕様上、frontmatter field はすべて optional であり、`description` だけが推奨である（正本は `16`）。このファイルでいう「最小構成」「推奨構成」は本設計書の出荷基準であり、公式必須項目ではない。

出荷基準として、`validate-frontmatter.py` は全スキルに `name` / `description` / `kind` / `version` / `owner` の 5 項目（commonCore。正本は `capability-manifest.schema.json`）を求め、`kind: ref` には `source` と `source-tier` も求める。下の 3 例はどれも `validate-frontmatter.py` と `lint-skill-description.py` を通る（`warn:` は出ても exit 0）。

### 最小構成

```yaml
---
name: ref-project-rules
description: このリポジトリのコードを編集するとき、変更をレビューするときに読む。
kind: ref
version: 0.1.0
owner: team-platform
source: CONTRIBUTING.md
source-tier: internal
---
```

使う場面: reference content / low-risk skill / まず発動確認したい初期段階。`kind: ref` 以外なら `source` / `source-tier` は省けるが、`source` が無いと `warn:` が出る。

### 推奨構成

```yaml
---
name: run-release-check
description: リリース前に出荷できる状態かを確かめたいとき、タグを打つ前の最終確認をしたいときに使う。
kind: run
version: 0.1.0
owner: team-platform
argument-hint: "[version]"
arguments: [version]
disable-model-invocation: true
allowed-tools:
  - Bash(git status *)
  - Bash(gh *)
---
```

使う場面: user-facing workflow / 引数あり / 副作用または準副作用あり / tool preapproval が必要。`user-invocable` を書かずに `disable-model-invocation: true` を置くと、`validate-frontmatter.py` は既定値を true とみなして `warn:`（exit 0）を出す。手動専用の workflow としては意図どおりなので、そのままでよい。

### 高度構成

```yaml
---
name: assign-skill-review-evaluator
description: SKILL.md の設計をレビューしたいとき、rubric に沿っているかを確かめたいときに使う。
kind: assign
version: 0.1.0
owner: team-platform
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Grep
hooks:
  PreToolUse:
    - matcher: "Read"
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/deny-secret-read.py"'
paths:
  - ".claude/skills/**/SKILL.md"
model: inherit
effort: high
pair: assign-skill-review-generator
---
```

使う場面: internal evaluator / generator、forked subagent 実行、file pattern で対象を絞る、独自 metadata を lint / CI で検査。`assign-*` は `context: fork` と `user-invocable: false` が必須（`validate-frontmatter.py`）。`hooks` は空の配列ではなく、イベント名をキーにした対応表で書く（形式は `16` §10 の「hooks in skills and agents」）。

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
※ description は**日本語で書く**（必須）。lint R5 は末尾を「使う。」「読む。」「起動する。」に限るため、英語の description は機械ゲートを通らない。発動キー（「とき」「場合」「際」「時に」）は 2 個ちょうどで書く。rubric FM-003 は 2〜3 個を許すが、`validate-frontmatter.py` は 2 個ちょうど、lint R1 は 3 個以上を違反にするので、実際に通るのは 2 個だけである。数え方は単純な文字列の出現数なので、「実際」「同時に」のような語も 1 個に数えられる。

設計規律（必須3点 / 2個ルール）:

1. **発動トリガー句は 2 個ちょうど** — 1 個では Claude が user 発話と照合する鍵が不足し、3 個目以降は次のどちらかに化けやすい: (a) 重複 (b) 処理の流れが紛れ込む。原典 L504 は「上限は 2 個前後」とする。本群の機械ゲートは **2 個ちょうど** を強制する（`validate-frontmatter.py` が `== 2`、lint R1 が 3 個以上を違反。cap 1,536 字の余裕確保も兼ねる）。rubric FM-003 は 2〜3 個を許すが、3 個の description はゲートで落ちるので書かない。
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
- 下限を含む「2 個ちょうど」は `validate-frontmatter.py` が見る（R1 は上限だけを担う）。
- 違反は `plugins/skill-governance-config/config/governance-policy.json` の `machine_enforcement.linked_lints` 経由で CI ゲート対象。
- `validate-frontmatter.py` と lint R1 は本節を根拠に 2 個ちょうどを強制する。一方、rubric.json `FM-003`（1.5.0）の check 式は 2〜3 個のままで、三者は揃っていない。書くときは機械ゲートに合わせて 2 個にする。rubric 側を締めるかは rubric の改正手続き（27章）で決める。

良い例 / 悪い例:

```yaml
# Good: 発動条件 2 個・動詞ベース・動作詳細なし
description: SKILL.md の設計をレビューしたいとき、rubric に沿っているかを確かめたいときに使う。

# Bad: 発動条件 4 個（重複）+ 動作詳細「JSON で返す」混入
description: スキル評価。「skillレビュー」「SKILL.md採点」「スキル設計の評価」「Skill品質チェック」で発動しJSONで返す。

# Bad: 発動条件 1 個（鍵不足）+ 動作詳細「2 段階レビュー」混入
description: コードレビュー。仕様準拠と品質を 2 段階でレビューする。
```

## `when_to_use` の使いどころ

`description` だけでは説明不足な場合の補助。**`description` + `when_to_use` 合算が 1,536 文字 cap**（→ [§10](./16-official-skills-complete-reference.md#10-frontmatter先頭メタ情報-全項目)）に含まれることに注意。

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
| `kind` | 粒度や分類。SKILL.md では prefix と同じ値を使う | 全 Skill（必須） |
| `version` | Skill の版。SemVer（X.Y.Z） | 全 Skill（必須） |
| `owner` | 保守責任者 | 全 Skill（必須） |
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
description: SKILL.md の設計をレビューしたいとき、rubric に沿っているかを確かめたいときに使う。
kind: assign
version: 0.1.0
owner: team-platform
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Grep
model: inherit
effort: high
pair: assign-skill-review-generator
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
  - plugins/skill-governance-lint/scripts/lint-rubric-refs-exist.py
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
| `kind:` | string。SKILL.md では prefix と同じ run\|ref\|assign\|wrap\|delegate を使う。`validate-frontmatter.py` は互換のため workflow\|reference\|evaluator\|generator も通す | スキル種別を機械読み取り可能な形で宣言 | `scripts/validate-frontmatter.py` の `KIND_VALUES`（prefix の分類は 06章） |
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

`validate-frontmatter.py` は知らないキーがあっても落とさない。公式フィールドと独自フィールドの混在は設計上意図されたもので、エラーではない。一方、次の独自フィールドは値まで検査し、外れると exit 1 にする。

- 存在: `kind` / `version` / `owner`（commonCore の必須項目）。`kind: ref` では `source` と `source-tier` も必須。それ以外の kind で `source` が無いと `warn:`（exit 0）
- 値の形: `kind`（`KIND_VALUES`）、`version`（SemVer）、`effect`、`merge_strategy` / `conflict_policy`（29章の enum）、`source-tier`、`last-audited`（ISO 日付）
- 参照先の実在: `rubric_refs` / `reference_refs` / `script_refs`（無ければ `MISSING_REF`）
- 組み合わせ: `assign-*` の `context: fork` と `user-invocable: false`

`pair:` の相方が実在するかは検査しない。

Claude Code 公式が `kind:` / `pair:` に当たるフィールドを採用したときは、本節の独自拡張表から外して `16` の公式項目へ移す。
