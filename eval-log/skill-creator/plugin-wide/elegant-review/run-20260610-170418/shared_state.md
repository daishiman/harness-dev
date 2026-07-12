# shared_state (Phase 1 → Phase 2 ファンアウト中継)

skill-creator=Capability 7 kindを生成・評価・統治するメタplugin。28 skill/6 agent/5 command/7 hook構成、run-skill-create→run-build-skill→run-elegant-reviewの3層が中核。最重要懸念: composition invariant「cross-plugin参照はskill-intake限定」と実参照(governance-lint/prompt-creator等)の矛盾、dangling参照(elegant-review-protocol.md不在)、run-skill-feedbackの構成登録漏れ。
