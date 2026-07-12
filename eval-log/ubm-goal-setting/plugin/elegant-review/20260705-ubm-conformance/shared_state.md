# shared_state (Phase 1 → Phase 2 中継)

ubm-goal-setting は ObsidianMemo vault 資産を移植した個人利用 plugin (bundle/distributable:false)。2 run-skill (goal-setting/knowledge-sync)+5 agent+6 prompt+3 script+1 hook+28 knowledge JSON。HC 仕様の検証軸6つ: (1)PKG契約 schema/catalog 網羅、(2)SKILL frontmatter 完備、(3)capability-manifest enum(kind/tier)、(4)prompt-placement SSOT の向き、(5)命名/禁止CLI、(6)knowledge-loop 記述子。composition の kind:script・tier:supporting が schema enum 外の疑い、pkg_checks が 001-008 止まり、knowledge-sync の completeness_exempt と prompts 実在の矛盾が要精査。

## HC 仕様正本 (SSOT)
- ref-pkg-contract/schemas/package-contract.schema.json — PKG契約schema
- ref-pkg-contract/references/pkg-id-catalog.yaml — PKG-001..015
- ref-claude-code-skill-spec/references/frontmatter-fields.md — SKILL frontmatter
- run-build-skill/references/prompt-placement-convention.md — prompts=正本/agents=薄adapter
- run-build-skill/references/capability-manifest.schema.json — composition schema
- ref-skill-naming-convention/references/decision-table.md — 命名規約
- ref-cross-platform-runtime/references/forbidden-clis.md — 禁止CLI
- ref-knowledge-loop/references/knowledge-construction.md — knowledge loop

## Phase 1 第一印象懸念 (要 Phase 2 検証、仮説扱い)
1. composition kind:script (C01-03) が capability-manifest schema enum 外の疑い
2. composition tier:supporting (C08-12) が tier enum [core,ref,extension] 外の疑い
3. pkg_checks 001-008 止まり、catalog bundle 適用 009/010/011/012/013a-d/014/015 不在。001=skip
4. knowledge-sync completeness_exempt「R-id prompts 置かない」vs R1-knowledge-extract.md 実在 = 自己矛盾
5. prompt-placement SSOT 反転疑い: 7層本文43KBが agents/knowledge-extractor.md 内包、prompts/R1は46行英語要約
6. R1-knowledge-extract.md 英語、invariant「日本語」と他R1-R5(日本語)に不整合
7. knowledge_loop 記述子不在 + record_usage.py/add_entry.py + §12 usage_log 不在
8. hook capability ref が非相対パス文字列 "hook:PreToolUse-WriteEdit/ubm-write-path-guard"
