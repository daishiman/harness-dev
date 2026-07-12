# Handoff Contract (pointer)

正本: `plugins/skill-intake/references/handoff-contract.md` (plugin-root)。本ファイルは正本参照。複製禁止 (cross-boundary invariant) — phase 間 schema をここへインライン複製しない (旧複製は mode A-E のみ・`handoff_target` 無しの stale drift を起こした)。

- 各 phase の handoff JSON 契約は各 phase 担当 skill / schema が正本: 委譲 skill (`run-intake-kickoff` 等) は各 `schemas/output.schema.json`、SubAgent phase (P2/P3/P5/P8) は `workflow-manifest.json` の `outputSchemaId` が指す `./schemas/phase*-*.schema.json`。
- Phase 11 `next-action.json` (mode A-E/P + `handoff_target`) の正本は `plugins/skill-intake/skills/run-intake-next-action/schemas/output.schema.json`。
- intake.json (Phase 9) と下流 (harness-creator / plugin-dev-planner) への引き渡し契約は正本の「harness-creator 入力契約マッピング」「plugin-dev-planner 分岐 (mode P)」節を参照。
