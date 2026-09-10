from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_active_ci_workflows_run_full_fleet_contract_gates():
    for relative in (
        ".github/workflows/governance-check.yml",
        ".github/workflows/harness-creator-kit-ci.yml",
    ):
        workflow = (ROOT / relative).read_text(encoding="utf-8")
        assert "audit-capability-parity.py --repo-root . --all" in workflow, relative
        assert "lint-plugin-composition.py plugins/*/plugin-composition.yaml" in workflow, relative


def test_iterative_update_requires_full_fleet_contract_gate():
    skill = (
        ROOT
        / "plugins/harness-creator/skills/run-skill-iter-improve/SKILL.md"
    ).read_text(encoding="utf-8")

    assert "sync-plugin-platforms.py --all --check" in skill
    assert "audit-capability-parity.py --repo-root . --all" in skill
    assert "lint-plugin-composition.py plugins/*/plugin-composition.yaml" in skill


def test_native_docs_keep_product_specific_hook_delivery_and_activation_terms():
    readme = (ROOT / "plugins/harness-creator/README.md").read_text(encoding="utf-8")
    contract = (
        ROOT / "plugins/harness-creator/references/native-surface-contract.md"
    ).read_text(encoding="utf-8")
    operations = (
        ROOT / "plugins/harness-creator/references/native-surface-operations.md"
    ).read_text(encoding="utf-8")

    assert "Claude Codeは標準pathを" in readme and "自動検出する" in readme
    assert "Claude manifestの`hooks`で同じfileを再宣言してはならない" in contract
    assert "harness-creator@harness-local" in operations
    assert "Codex local sourceは`live-source`、Git refは`git-snapshot`" in operations
    assert "Codex が plugin を cache へ copy" not in operations
