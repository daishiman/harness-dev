"""task spec 本文が提示する validate-system-plan 再実行コマンドの世代非依存性 (契約 1.3.0).

対応 issue: HarnessHub-ji8y。C11 promotion は staging を content-addressed generation へ
atomic rename するため、task spec 本文に書かれた `--staging .` は promote 後に解決できない。
既に promote 済みの task projection を下流で修復したのが HarnessHub-cc6
(`test_rerun_command_resolution.py`) で、本ファイルはその欠陥を生む上流
(生成器 prompt + C12 promotion gate) を塞ぐ検査を対象にする。

検査対象はコマンドとして提示された断片 (fenced block / inline code span) だけで、散文中の
script 名への言及は対象外。既に promote 済みの package が説明文として script 名を書いており、
そこまでコマンド扱いすると digest 不変の既存世代を後から fail させてしまうため。

悪性ケースのメソッド名には `malformed` を含める。P09 の automated command が
`pytest -k malformed` で悪性部分集合だけを選択するため、命名がそのまま選択条件になっている。
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

import test_runtime as fx
from test_task_spec_test_strategy_sections import (
    codes,
    legacy_baseline,
    rebuild,
)


VALIDATOR = fx.VALIDATOR
PLUGIN = fx.PLUGIN
TEMPLATE = PLUGIN / "references" / "system-task-spec-template.md"
PACKAGE_CONTRACT = PLUGIN / "references" / "feature-execution-package-contract.md"
EMIT_PROMPT = PLUGIN / "skills" / "run-system-dev-plan" / "prompts" / "R3-emit.md"
ARCHITECT_AGENT = PLUGIN / "agents" / "system-dev-plan-architect.md"
BASELINE_ASSET = PLUGIN / "assets" / "validation-contract-baseline.json"

# fx.make_fixture が全 13 task spec へ書く feature_package_id。
PACKAGE_ID = "feature-package/feat"
OTHER_PACKAGE_ID = "feature-package/other"
SCRIPT = "python3 plugins/system-dev-planner/scripts/validate-system-plan.py"

STAGING_CODE = "task-spec-rerun-staging-path"
MISSING_CODE = "task-spec-rerun-package-missing"
MISMATCH_CODE = "task-spec-rerun-package-mismatch"
ALL_CODES = (STAGING_CODE, MISSING_CODE, MISMATCH_CODE)

GOOD = f"`{SCRIPT} --repo-root . --feature-package {PACKAGE_ID}`"
STAGING = f"`{SCRIPT} --repo-root . --staging .`"
NO_PACKAGE = f"`{SCRIPT} --repo-root .`"
OTHER_PACKAGE = f"`{SCRIPT} --repo-root . --feature-package {OTHER_PACKAGE_ID}`"
# 既に promote 済みの feat-publish-pipeline phase-01 が持つ散文 (実測形)。コマンドではない。
PROSE = "validate-system-plan.py 実行時に --repo-root を明示指定する運用とする。"
# R3-emit prompt が「台帳未登録の新規 package はこの version で検証される」と名指しする箇所。
LATEST_CLAIM = re.compile(r"未登録ゆえ[^。]*?`([0-9]+\.[0-9]+\.[0-9]+)`")


def violations(text: str, package_id: str | None = PACKAGE_ID) -> list[tuple[str, str]]:
    return VALIDATOR.rerun_command_violations(text, package_id)


def spec_with_command(phase: str, command: str) -> str:
    """base task spec の `Verification and evidence` へ再実行コマンド行を足す。

    共有 fixture の Automated commands は `verify {phase}` だけで validator script を
    含まないため、差し込まない限り本検査は何も見ない (= 既存 fixture は非退行)。
    """
    return fx.task_spec_text(phase).replace(
        f"- Automated commands: verify {phase}",
        f"- Automated commands: verify {phase}\n- Rerun: {command}",
        1,
    )


def fixture_with_command(root: Path, repository_id: str, command: str, *, first_only: bool = False) -> Path:
    """再実行コマンドを持つ台帳未登録 package を組む (未知 digest -> 最新契約)。"""
    staging, _ = fx.make_fixture(root, repository_id)
    targets = VALIDATOR.TASK_PATHS[:1] if first_only else VALIDATOR.TASK_PATHS
    for rel, phase in zip(targets, VALIDATOR.PHASES):
        (staging / rel).write_text(spec_with_command(phase, command), encoding="utf-8")
    rebuild(root, staging, repository_id)
    return staging


class CommandExtractionTests(unittest.TestCase):
    """「何をコマンドとみなすか」の抽出規則 (誤検出/検出漏れの境界)。"""

    def test_generation_independent_command_has_no_violation(self):
        """自 package の `--feature-package` は promote 後も current pointer から解決できる。"""
        self.assertEqual(violations(GOOD), [])

    def test_malformed_staging_flag_is_rejected(self):
        """`--staging` は atomic rename 後に消える path を指すため受理できない。"""
        self.assertEqual([code for code, _ in violations(STAGING)], [STAGING_CODE])

    def test_malformed_missing_feature_package_flag_is_rejected(self):
        """`--staging` が無くても世代解決手段が無ければ再実行できない。"""
        self.assertEqual([code for code, _ in violations(NO_PACKAGE)], [MISSING_CODE])

    def test_malformed_other_package_id_is_rejected(self):
        """他 package の id を書くと自分ではない世代を検証してしまう。"""
        found = violations(OTHER_PACKAGE)
        self.assertEqual([code for code, _ in found], [MISMATCH_CODE])
        self.assertIn(PACKAGE_ID, found[0][1])
        self.assertIn(OTHER_PACKAGE_ID, found[0][1])

    def test_unknown_package_id_degrades_to_format_check(self):
        """package_id を確定できない入力では id 一致を主張しない (誤った期待値を出さない)。"""
        self.assertEqual(violations(OTHER_PACKAGE, None), [])
        self.assertEqual([code for code, _ in violations(NO_PACKAGE, None)], [MISSING_CODE])

    def test_prose_mention_is_not_treated_as_a_command(self):
        """散文中の script 名は運用説明であり、コマンド扱いすると既存 promoted 世代が落ちる。"""
        self.assertEqual(violations(f"## Verification and evidence\n\n- 注記: {PROSE}\n"), [])

    def test_fenced_block_is_inspected(self):
        """fenced block は実行を指示する提示形なので検査対象。"""
        text = f"```bash\n{SCRIPT} --repo-root . --staging .\n```\n"
        self.assertEqual([code for code, _ in violations(text)], [STAGING_CODE])

    def test_malformed_tilde_fenced_block_is_rejected(self):
        """CommonMark の tilde fence も fenced block であり、検査を迂回できない。"""
        text = f"~~~~bash\n{SCRIPT} --repo-root . --staging .\n~~~~~\n"
        self.assertEqual([code for code, _ in violations(text)], [STAGING_CODE])

    def test_malformed_unclosed_fenced_block_is_rejected(self):
        """閉じ fence が無くても EOF まで code block なので fail-open にしない。"""
        text = f"```bash\n{SCRIPT} --repo-root . --staging .\n"
        self.assertEqual([code for code, _ in violations(text)], [STAGING_CODE])

    def test_fenced_block_line_continuation_is_folded(self):
        """`\\` 継続行を行単位で割ると `--feature-package` を見失って誤検出する。"""
        text = f"```bash\n{SCRIPT} \\\n    --repo-root . \\\n    --feature-package {PACKAGE_ID}\n```\n"
        self.assertEqual(violations(text), [])

    def test_fenced_block_is_not_counted_twice(self):
        """fenced block 内の断片を inline code としても数えると同じ違反が二重に出る。"""
        text = f"```bash\n{SCRIPT} --repo-root . --staging .\n```\n"
        self.assertEqual(len(violations(text)), 1)

    def test_multiple_commands_are_each_reported(self):
        """1 spec が複数コマンドを書く場合は行ごとに帰属させる。"""
        self.assertEqual(
            [code for code, _ in violations(f"{GOOD}\n\n{STAGING}\n\n{NO_PACKAGE}\n")],
            [STAGING_CODE, MISSING_CODE],
        )

    def test_unrelated_commands_are_ignored(self):
        """他 script のコマンドは本契約の対象外 (過剰検査で運用を縛らない)。"""
        self.assertEqual(violations("`pytest -q`\n\n`python3 scripts/promote-system-plan.py --staging .`"), [])

    def test_staging_flag_requires_exact_token(self):
        """`--staging-note` のような別 flag を部分一致で拾わない。"""
        self.assertEqual(
            [code for code, _ in violations(f"`{SCRIPT} --staging-note x --feature-package {PACKAGE_ID}`")],
            [],
        )


class RerunCommandContractTests(unittest.TestCase):
    """C12 promotion gate としての fail-closed 実効性と契約版による段階適用。"""

    def test_enforced_package_with_generation_independent_command_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = fixture_with_command(root, repository_id, GOOD)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "pass", report["violations"])
            self.assertEqual(report["rerun_command_contract"]["mode"], "enforced")

    def test_enforced_package_without_any_validator_command_passes(self):
        """再実行コマンドを書かない spec は本契約の対象外 (既存 fixture の非退行)。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging, _ = fx.make_fixture(root, repository_id)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "pass", report["violations"])
            self.assertFalse(codes(report) & set(ALL_CODES))

    def _reject(self, command: str, expected: str) -> dict:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = fixture_with_command(root, repository_id, command, first_only=True)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "fail")
            self.assertIn(expected, codes(report))
            return report

    def test_malformed_staging_rerun_command_is_rejected_by_the_gate(self):
        """本 issue の実害形。C12 が拒否しなかったため 195 件の projection 修復が必要になった。"""
        report = self._reject(STAGING, STAGING_CODE)
        hit = [item for item in report["violations"] if item["code"] == STAGING_CODE]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["path"], VALIDATOR.TASK_PATHS[0])

    def test_malformed_rerun_command_without_feature_package_is_rejected_by_the_gate(self):
        self._reject(NO_PACKAGE, MISSING_CODE)

    def test_malformed_rerun_command_with_other_package_is_rejected_by_the_gate(self):
        self._reject(OTHER_PACKAGE, MISMATCH_CODE)

    def test_malformed_rerun_command_is_rejected_in_every_task_spec(self):
        """13 件のうち 1 件だけ検査して残りを素通りさせない。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = fixture_with_command(root, repository_id, STAGING)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "fail")
            hit = [item for item in report["violations"] if item["code"] == STAGING_CODE]
            self.assertEqual(sorted(item["path"] for item in hit), sorted(VALIDATOR.TASK_PATHS))

    def test_legacy_package_with_staging_rerun_command_passes(self):
        """契約 1.2.0 以前で登録済みの世代は digest 不変ゆえ後追い修正できない (非退行)。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = fixture_with_command(root, repository_id, STAGING)
            report = VALIDATOR.validate(staging, repository_id, baseline=legacy_baseline(staging))
            self.assertEqual(report["status"], "pass", report["violations"])
            self.assertEqual(report["rerun_command_contract"]["mode"], "legacy")

    def test_enforced_package_with_prose_mention_passes(self):
        """散文で script 名に触れただけの promoted 世代を fail させない (誤検出の回帰固定)。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = fixture_with_command(root, repository_id, PROSE)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "pass", report["violations"])

    def test_report_declares_the_rerun_command_contract(self):
        """検査したのか黙って飛ばしたのかを証跡から区別できること (gate liveness)。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = fixture_with_command(root, repository_id, GOOD)
            declared = VALIDATOR.validate(staging, repository_id, baseline={})["rerun_command_contract"]
            self.assertEqual(declared["enforced_from"], VALIDATOR.RERUN_COMMAND_CONTRACT_FROM)
            self.assertEqual(declared["contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST)
            legacy = VALIDATOR.validate(
                staging, repository_id, baseline=legacy_baseline(staging)
            )["rerun_command_contract"]
            self.assertEqual(legacy["contract_version"], "1.1.0")
            self.assertEqual(legacy["mode"], "legacy")


class RerunCommandSourceOfTruthTests(unittest.TestCase):
    """検査規則が生成器 prompt・テンプレート・契約正本と同じことを言っているか。"""

    def test_contract_version_is_declared_in_the_baseline_asset(self):
        asset = json.loads(BASELINE_ASSET.read_text(encoding="utf-8"))
        version = VALIDATOR.RERUN_COMMAND_CONTRACT_FROM
        self.assertEqual(asset["latest_contract_version"], version)
        self.assertIn(version, asset["contract_versions"])
        self.assertIn("--feature-package", asset["contract_versions"][version]["description"])

    def test_no_registered_package_is_exempted_by_a_future_version(self):
        """台帳の contract_version は validator が知る version 集合の部分集合であること。"""
        asset = json.loads(BASELINE_ASSET.read_text(encoding="utf-8"))
        known = set(VALIDATOR.CONTRACT_VERSIONS)
        self.assertLessEqual({item["contract_version"] for item in asset["packages"]}, known)

    def test_template_documents_the_violation_codes(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        for code in ALL_CODES:
            self.assertIn(code, text)
        self.assertIn("--feature-package", text)

    def test_package_contract_documents_the_generation_independent_form(self):
        text = PACKAGE_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("--feature-package", text)
        for code in ALL_CODES:
            self.assertIn(code, text)

    def test_emit_prompt_instructs_the_generation_independent_form(self):
        """生成器側に規則が無いと、gate は毎回 fail してから直す運用になる。"""
        text = EMIT_PROMPT.read_text(encoding="utf-8")
        self.assertIn("--feature-package", text)
        self.assertIn(VALIDATOR.RERUN_COMMAND_CONTRACT_FROM, text)

    def test_emit_prompt_names_the_current_latest_contract(self):
        """prompt が名指しする「台帳未登録 -> この version」が validator と drift しないこと。

        契約を上げるたびに prompt 側の版番号が取り残されると、生成器は古い契約の
        チェックリストで自己評価して C12 の実際の要求とずれる。
        """
        claims = set(LATEST_CLAIM.findall(EMIT_PROMPT.read_text(encoding="utf-8")))
        self.assertTrue(claims, "prompt が最新契約 version を名指ししていない")
        self.assertEqual(claims, {VALIDATOR.CONTRACT_VERSION_LATEST})

    def test_architect_agent_uses_the_current_contract_and_rerun_form(self):
        """実行 agent の停止条件が generator/validator より古い版へ drift しないこと。"""
        text = ARCHITECT_AGENT.read_text(encoding="utf-8")
        self.assertIn(
            f"新規 package は台帳未登録ゆえ `{VALIDATOR.CONTRACT_VERSION_LATEST}`",
            text,
        )
        self.assertIn("--feature-package <feature_package_id>", text)
        self.assertIn("--staging` ではなく", text)


if __name__ == "__main__":
    unittest.main()
