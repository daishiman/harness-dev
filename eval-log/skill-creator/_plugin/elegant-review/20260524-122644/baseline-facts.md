# Phase1 機械観測ベースライン (analyst入力)

## 確定事実
- 仕様正本: capability-manifest.schema.json#/definitions/commonCore.required = [name, description, kind, version, owner](全kind)。run-build-skill KeyRule17 + ゴールシークchecklist も commonCore(name/kind/version/owner/since/source-tier)必須を宣言。
- version欠落: 26中25スキル(run-build-skillのみ保持)。
- 根本原因: validate-frontmatter.py の SKILL.md経路 REQUIRED={name,description} のみ。commonCore強制(version含む)は validate_capability()=非SKILL.md(agent/hook等)経路限定(L242)。→ skillはversion未検査で drift。
- ゴールシーク実行節: 実行系kind(run/assign/wrap/delegate)全てに存在(OK)。
- lint-skill-completeness.py: 全26 PASS。
- frontmatter dangling-ref(bare local path がローカル不在; 実体は別skillの共有正本):
  - assign-plugin-package-evaluator: schemas/package-contract.schema.json (実体=ref-pkg-contract)
  - run-plugin-package-check: schemas/package-contract.schema.json (同上)
  - assign-skill-design-evaluator: scripts/compose-rubrics.py (不在)
  - run-skill-elicit: schemas/skill-brief.schema.json (不在)
  - run-goal-seek: references/goal-seek-paradigm.md(実体=run-build-skill) + schemas/goal-spec.schema.json(不在)
- 構造極薄: run-goal-seek(subdir皆無/113行) run-goal-elicit(schemasのみ/100行)。

## 確定済み改善方針(ユーザー承認)
- version初期値=全て0.1.0
- スコープ=データ修正(25 skillへversion) + ゲート修正(validate-frontmatter.py SKILL.md経路でcommonCore強制)
