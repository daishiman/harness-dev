"""criteria 検証対象の機械生成名簿 (手編集禁止)。

生成器: tests/criteria/build_criteria_roster.py --write (探索正本は同 discover())。
役割: validate-llm-coverage.py の被覆判定は「criterion id と skill 名が
tests/**/*.py に静的出現するか」を見るため、動的探索だけでは新 skill の被覆が
計測されない。本ファイルが全対象 (plugin, skill, criterion id 集合) を静的
テキストとして固定する。各 id の genuine 検証実体は
test_all_skills_criteria.py::test_criterion_is_genuinely_verified の
parametrized 実行 (inner=決定論 lint exit0 / outer=verdict PASS)。
discovery との乖離は test_roster_matches_discovery が検出し再生成を要求する。
"""

ROSTER: list[tuple[str, str, tuple[str, ...]]] = [
    ("company-master", "run-company-master-backfill", ("IN1", "IN2", "IN3", "OUT1")),
    ("company-master", "run-company-master-build", ("IN1", "IN2", "OUT1", "OUT2")),
    ("contract-generator", "run-contract-finalize", ("IN1", "IN2", "OUT1")),
    ("contract-generator", "run-contract-generate", ("IN1", "IN2", "OUT1")),
    ("contract-generator", "run-template-sync", ("IN1", "IN2", "OUT1")),
    ("extract-system-blueprint", "assign-blueprint-fidelity-evaluator", ("IN1", "OUT1")),
    ("extract-system-blueprint", "run-blueprint-apply", ("IN1", "OUT1")),
    ("extract-system-blueprint", "run-extract-blueprint", ("IN1", "OUT1")),
    ("harness-creator", "delegate-codex-skill-review", ("IN1", "IN2", "OUT1", "OUT2")),
    ("harness-creator", "run-build-skill", ("IN1", "IN2", "IN3", "OUT1", "OUT2")),
    ("harness-creator", "run-elegant-review", ("IN1", "IN2", "OUT1", "OUT2")),
    ("harness-creator", "run-goal-elicit", ("IN1", "OUT1", "OUT2")),
    ("harness-creator", "run-goal-seek", ("IN1", "IN2", "OUT1", "OUT2")),
    ("harness-creator", "run-migrate-audit", ("IN1", "IN2", "OUT1", "OUT2")),
    ("harness-creator", "run-plugin-package-check", ("IN1", "IN2", "OUT1")),
    ("harness-creator", "run-skill-create", ("IN1", "IN2", "OUT1", "OUT2")),
    ("harness-creator", "run-skill-elicit", ("IN1", "IN2", "OUT1")),
    ("harness-creator", "run-skill-feedback", ("IN1", "IN2", "IN3", "OUT1", "OUT2")),
    ("harness-creator", "run-skill-iter-improve", ("IN1", "IN2", "OUT1", "OUT2")),
    ("harness-creator", "run-skill-live-trial", ("IN1", "IN2", "OUT1", "OUT2", "OUT3")),
    ("harness-creator", "run-skill-rename", ("IN1", "IN2", "OUT1")),
    ("harness-creator", "run-skill-rubric-governance", ("IN1", "IN2", "OUT1", "OUT2")),
    ("harness-creator", "run-skill-update-notifier", ("IN1", "IN2", "IN3", "OUT1")),
    ("harness-creator", "wrap-git-commit-safe", ("IN1", "IN2", "OUT1")),
    ("mf-kessai-invoice-check", "run-mf-initial-month-enrich", ("IN1", "IN2", "OUT1")),
    ("mf-kessai-invoice-check", "run-mf-invoice-check", ("IN1", "IN2", "OUT1")),
    ("mf-kessai-invoice-check", "run-mf-invoice-db-setup", ("IN1", "IN2", "OUT1")),
    ("mf-kessai-invoice-check", "run-mf-invoice-reconcile", ("IN1", "IN2", "OUT1")),
    ("mf-kessai-invoice-check", "run-mf-invoice-report", ("IN1", "OUT1")),
    ("notion-gmail-send", "run-notion-gmail-dry-run", ("IN1", "IN2", "OUT1")),
    ("notion-gmail-send", "run-notion-gmail-send", ("IN1", "IN2", "IN3", "OUT1")),
    ("notion-gmail-send", "run-notion-gmail-sendlog-setup", ("IN1", "OUT1")),
    ("notion-gmail-send", "run-notion-gmail-source-audit", ("IN1", "OUT1")),
    ("plugin-dev-planner", "run-plugin-dev-plan", ("IN1", "IN2", "OUT1", "OUT2")),
    ("prompt-creator", "run-prompt-create", ("IN1", "IN2", "OUT1")),
    ("prompt-creator", "run-prompt-creator-7layer", ("IN1", "IN2", "OUT1")),
    ("prompt-creator", "run-prompt-elicit", ("IN1", "IN2", "OUT1")),
    ("skill-intake", "assign-notion-fidelity-evaluator", ("IN1", "IN2", "OUT1")),
    ("skill-intake", "run-intake-finalize", ("IN1", "IN2", "OUT1", "IN3", "OUT2")),
    ("skill-intake", "run-intake-interview", ("IN1", "IN2", "OUT1", "IN3", "IN4", "OUT2", "OUT3")),
    ("skill-intake", "run-intake-kickoff", ("IN1", "IN2", "OUT1")),
    ("skill-intake", "run-intake-next-action", ("IN1", "IN2", "OUT1")),
    ("skill-intake", "run-intake-option-catalog", ("IN1", "IN2", "OUT1", "OUT2")),
    ("skill-intake", "run-intake-revise", ("IN1", "IN2", "OUT1")),
    ("skill-intake", "run-intake-visualize", ("IN1", "IN2", "OUT1")),
    ("skill-intake", "run-notion-intake-publish", ("IN1", "IN2", "OUT1")),
    ("skill-intake", "run-skill-intake", ("IN1", "IN2", "OUT1")),
    ("slide-report-generator", "run-cross-deck-review", ("IN1", "OUT1")),
    ("slide-report-generator", "run-slide-report-generate", ("IN1", "OUT1")),
    ("slide-report-generator", "run-slide-report-modify", ("IN1", "OUT1")),
    ("system-spec-harness", "run-system-spec-compile", ("IN1", "OUT1")),
    ("system-spec-harness", "run-system-spec-doc-fetch", ("IN1", "OUT1")),
    ("system-spec-harness", "run-system-spec-elicit", ("IN1", "OUT1", "OUT2")),
    ("ubm-goal-setting", "run-ubm-consult", ("IN1", "OUT1", "OUT2")),
    ("ubm-goal-setting", "run-ubm-goal-setting", ("IN1", "OUT1", "OUT2")),
    ("ubm-goal-setting", "run-ubm-knowledge-sync", ("IN1", "OUT1")),
    ("ubm-goal-setting", "run-ubm-youtube-ingest", ("IN1", "OUT1")),
]
