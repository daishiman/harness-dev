# Handoff Contract (pointer)

正本: plugin root の `references/handoff-contract.md`（この skill ディレクトリからは `../../references/handoff-contract.md`。repo 内では `plugins/skill-intake/references/handoff-contract.md`）。本ファイルは正本参照。複製禁止 (cross-boundary invariant) — phase 間 schema をここへインライン複製しない (旧複製は mode A-E のみ・`handoff_target` 無しの stale drift を起こした)。

- 各 phase の handoff JSON 契約は各 phase 担当 skill / schema が正本: 委譲 skill (`run-intake-kickoff` 等) は各 `schemas/output.schema.json` (`schemas/` を持たない P6 `run-intake-option-catalog` と P10 `run-notion-intake-publish` は委譲先 SKILL.md の完了条件。SKILL.md Key Rule 3)、SubAgent phase (P2/P3/P5/P8) は `workflow-manifest.json` の `outputSchemaId` が指す `./schemas/phase*-*.schema.json`。
- Phase 11 `next-action.json` (mode A-E/P + `handoff_target`) の正本は `plugins/skill-intake/skills/run-intake-next-action/schemas/output.schema.json`。
- intake.json (Phase 9) と下流 (harness-creator / plugin-dev-planner) への引き渡し契約は正本の「harness-creator 論理マッピング (現行 runtime では未自動射影)」「plugin-dev-planner 分岐 (mode P)」節を参照。
- P5 を SKIP した経路 (`needs_excavation=false`) で `build-skipped-purpose.py` が作る purpose.json を intake.json §3 へ写す方法は、正本の「P5 を SKIP した経路の §3」節を参照。
