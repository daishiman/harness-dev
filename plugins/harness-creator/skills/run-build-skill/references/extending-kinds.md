# Extending Capability Kinds — 新 kind 追加チェックリスト

> ガイドレール再現性の輪を閉じるための「自己進化手順」。新しい kind(例: mcp-tool、subagent-team 等)を Capability 抽象に追加するときに、どの5箇所を整えるべきかを示す。**強制ではなく道しるべ**。

## いつ使うか

- 新しい Claude Code 拡張資産タイプを Capability に取り込みたいとき
- 既存 kind を分割したいとき(例: hook を `hook-blocking` と `hook-observe` に分けたい等)
- 7 kind の現状で目的が表現しきれないとき

## 5 箇所チェックリスト

新 kind を `<new-kind>` と呼ぶ。以下を順に整える。各ステップは「最小限から始める」原則 — テンプレートが粗くても先に通し、運用しながら整える。

### 1. Schema(必須・最初に書く)
**ファイル**: `plugins/harness-creator/skills/run-build-skill/references/capability-manifest.schema.json`

- `definitions/kind<NewKind>` を追加(camelCase で命名)
- `commonCore.properties.kind.enum` に `<new-kind>` を追加
- `oneOf` 配列に `$ref: "#/definitions/kind<NewKind>"` を追加
- kind 固有 properties は **最小必須項目だけ** で始める(後で増やせる)

### 2. Template(粒度の出発点)
**ファイル**: `plugins/harness-creator/skills/run-build-skill/templates/<new-kind>-skeleton.<md|yaml>`

- `{{CAPABILITY_NAME}}` `{{OWNER}}` 等のプレースホルダで雛形化
- frontmatter は commonCore + kind 固有の最小項目だけ埋める
- 本文は `## Purpose` `## Steps` `## Output Contract` `## Self-Evaluation` の4見出しを最低限置く

### 3. Rubric(目的に応じたチェック・3〜5個から始める)
**ファイル**: `plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json`

- 新 kind 用の rule id プレフィックスを決める(例: `MT-` for mcp-tool)
- 既存 kind と同等の網羅性を目指さず、**最小限の3〜5 rule**から始める
- 各 rule に `applies_to_kinds: ["<new-kind>"]` を明示
- 共通核に追加すべき rule があれば `applies_to_kinds: ["*"]` で別途追加

### 4. Validator(分岐ロジック追加)
**ファイル**: `plugins/harness-creator/skills/run-build-skill/scripts/validate-build-trace.py`

- `_KIND_DISPATCH` dict に `<new-kind>: _check_<new_kind>` エントリ追加
- `_check_<new_kind>(manifest, findings)` 関数を実装
- `--self-test` の内蔵サンプルに 1 ケース(最小 OK 例)を追加すれば dogfooding が回る

### 5. Composition manifest と metrics(任意・運用後でOK)
**ファイル**:
- `plugins/harness-creator/plugin-composition.yaml` の capabilities[] に新 kind の実体を加える
- `plugins/harness-creator/scripts/compute-dogfooding-metrics.py` の `KNOWN_KINDS` タプルに `<new-kind>` を追加

これらは新 kind の実体ができてから整えれば十分。

## 「いい感じに整える」原則

1. **粒度は目的に合わせる**: schema/rubric/template は最初から完璧を目指さない。3〜5項目で動き始め、lessons-learned が溜まったら rubric proposal 経路で自動的に追加 rule が提案される。
2. **テンプレートは出発点**: skeleton は「ここから始める」雛形であり、kind 固有の事情で自由に変形してよい。共通核(name/description/kind/version/owner/contract)だけは保つ。
3. **強制ではなくガイド**: lint hook は exit 0(非ブロック)で warn を出すだけ。ブロックは composition manifest 上で必要な場合のみ exit_code_policy で明示宣言する。
4. **拡張のたびに5箇所を一気に整える必要はない**: 1→2→4 だけでも動く。3(rubric)と 5(composition)は後追いで OK。

## アンチパターン

- 新 kind を増やす前に既存7 kind のどれかで表現できないか **一度問う**。kind 数の爆発は MECE 性を壊す
- 共通核から逃げて kind 固有 schema に必須項目を増やしすぎる(commonCore は神聖、kind 固有は自由)
- rule を最初から10個以上書く(運用前の過剰設計、Goodhart の温床)

## 関連参照

- [capability-manifest.schema.json](capability-manifest.schema.json) — 7 kind 統一スキーマ
- [build-steps.md](build-steps.md) — kind 別の build 手順
- [../../../doc/ClaudeCodeスキルの設計書/23-meta-skill-architecture.md](../../../../../doc/ClaudeCodeスキルの設計書/23-meta-skill-architecture.md) — Capability 抽象の動機
