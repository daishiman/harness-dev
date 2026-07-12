# shared_state (Phase 1 出力, 200字以内)

skill-creator の run-build-skill が量産する run/wrap/delegate 系スキルへ評価基準 `feedback_contract`(inner/outer criteria) を自動注入する機構。注入は render-combinators の default-ON コンビネータと templates 直書きの2経路、criteria 文面は render-frontmatter._feedback_contract_mapping が brief/goal から fail-closed 導出。R1/R4 で必須化、lint-feedback-contract と content-review が欠落/未評価を exit1。全32 loop-kind backfill 済。

## scope
plugin=skill-creator / focus=評価基準の量産先伝播機構 (committed 3 commits + uncommitted WIP combinator)
