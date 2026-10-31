"""C12 契約 version 互換性の回帰テスト。

promote 済み content-addressed package は digest 不変ゆえ後追い修正できない。
validator の契約が強化されたとき、旧 package を当時の契約で再検証しつつ、
新規 package には強化後の契約を fail-closed で適用し続けることを固定する。
"""
from __future__ import annotations

import ast
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_runtime as runtime

VALIDATOR = runtime.VALIDATOR
REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATIONS = REPO_ROOT / ".dev-graph" / "plans" / "generations"
DIGEST_FILES = [*VALIDATOR.BASE_DIGEST_FILES, VALIDATOR.HANDOFF_PATH]
GOAL_SEEK_BLOCK = re.compile(
    rf"\n## {re.escape(VALIDATOR.GOAL_SEEK_SECTION)}\n.*?(?=\n## )", re.S
)
# patch 差し替え後に module 属性を引くと自分自身を呼んで再帰するため、import 時に束縛する。
_CURRENT_TASK_SPEC_TEXT = runtime.task_spec_text
LEGACY_SECTIONS = VALIDATOR.CONTRACT_VERSIONS["1.0.0"]["required_sections"]


def legacy_task_spec_text(phase: str) -> str:
    """契約 v1.0.0 当時の task spec を再現する (goal-seek 節ごと不在)。

    P13 writeback marker も当該節の内側にあるため、節の削除で v1.1.0 が追加した
    3 契約すべてが未充足になる。
    """
    return GOAL_SEEK_BLOCK.sub("", _CURRENT_TASK_SPEC_TEXT(phase))


def make_legacy_fixture(root: Path, repository_id: str) -> tuple[Path, str]:
    """契約 v1.0.0 当時の生成経路を再現し、実体から再計算した canonical digest を返す。

    C14 handoff builder (build-system-handoff.py) は同じ契約検査を独自に複製して保持する。
    現行 marker/節集合のままでは旧形式 task spec を封じ込められないため、当時の builder を
    patch で再現する。生成後に本文を書き換える方法では handoff の source digest が壊れ、
    契約 version とは無関係な違反が混ざるので、この経路でしか旧 package は再現できない。
    """
    with mock.patch.object(runtime, "task_spec_text", legacy_task_spec_text), \
            mock.patch.object(runtime.HANDOFF, "REQUIRED_TASK_SPEC_SECTIONS", LEGACY_SECTIONS), \
            mock.patch.object(runtime.HANDOFF, "METHODOLOGY_MARKER", ""), \
            mock.patch.object(runtime.HANDOFF, "GOAL_SEEK_PASS_MARKER", ""), \
            mock.patch.object(runtime.HANDOFF, "P13_WRITEBACK_MARKER", ""):
        staging, _ = runtime.make_fixture(root, repository_id)
    return staging, VALIDATOR.canonical_digest(staging, DIGEST_FILES)


def add_unregistered_qa_lineage(root: Path, staging: Path) -> None:
    """QA gate の導入前 package では未検査、現行 package では fail となる lineage を作る。"""
    (root / "features" / "FEATURE-1.md").write_text(
        "---\ntags: [\"qa-099\"]\n---\n\n# Feature\n",
        encoding="utf-8",
    )
    (root / "system-spec").mkdir(parents=True, exist_ok=True)
    (root / "system-spec" / "spec-state.json").write_text(
        json.dumps({"qa_log": []}),
        encoding="utf-8",
    )
    (staging / "goal-spec.json").write_text(
        json.dumps({
            "purpose": "qa-099 を実装する",
            "goal": "",
            "scope_in": [],
            "scope_out": [],
            "acceptance": [],
            "quality_constraints": [],
        }),
        encoding="utf-8",
    )


class ContractVersionResolutionTests(unittest.TestCase):
    def test_unknown_and_undigestable_targets_resolve_to_latest(self):
        baseline = {"sha256:known": "1.0.0"}
        self.assertEqual(VALIDATOR.resolve_contract_version("sha256:known", baseline), "1.0.0")
        self.assertEqual(
            VALIDATOR.resolve_contract_version("sha256:other", baseline), VALIDATOR.CONTRACT_VERSION_LATEST
        )
        self.assertEqual(
            VALIDATOR.resolve_contract_version(None, baseline), VALIDATOR.CONTRACT_VERSION_LATEST
        )
        self.assertEqual(
            VALIDATOR.resolve_contract_version("sha256:known", {}), VALIDATOR.CONTRACT_VERSION_LATEST
        )

    def test_absent_or_malformed_baseline_yields_no_exemption(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = root / "absent.json"
            corrupt = root / "corrupt.json"
            corrupt.write_text("{not json", encoding="utf-8")
            wrong_shape = root / "wrong.json"
            wrong_shape.write_text(json.dumps({"packages": {"a": "1.0.0"}}), encoding="utf-8")
            unknown_version = root / "unknown.json"
            unknown_version.write_text(
                json.dumps({"packages": [{"canonical_digest": "sha256:x", "contract_version": "9.9.9"}]}),
                encoding="utf-8",
            )
            for path in (missing, corrupt, wrong_shape, unknown_version):
                with self.subTest(path=path.name):
                    self.assertEqual(VALIDATOR.load_contract_baseline(path), {})

    def test_early_failure_report_still_declares_contract_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repository_id = runtime.make_repo(root)
            staging, _ = runtime.make_fixture(root, repository_id)
            (staging / "feature-package.json").unlink()

            report = VALIDATOR.validate(staging, repository_id)

            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST)
            self.assertFalse(report["contract_baseline_exemption"])


class LegacyPackageCompatibilityTests(unittest.TestCase):
    def test_registered_legacy_digest_passes_under_its_promotion_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repository_id = runtime.make_repo(root)
            staging, digest = make_legacy_fixture(root, repository_id)

            strict = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(strict["status"], "fail")
            self.assertEqual(strict["contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST)
            self.assertFalse(strict["contract_baseline_exemption"])
            codes = [item["code"] for item in strict["violations"]]
            self.assertEqual(codes.count("task-spec-section-missing"), 13)
            self.assertEqual(codes.count("inner-goal-seek-contract"), 13)
            self.assertEqual(codes.count("p13-spec-architecture-writeback"), 1)

            exempt = VALIDATOR.validate(staging, repository_id, baseline={digest: "1.0.0"})
            self.assertEqual(exempt["violations"], [])
            self.assertEqual(exempt["status"], "pass")
            self.assertEqual(exempt["contract_version"], "1.0.0")
            self.assertTrue(exempt["contract_baseline_exemption"])

    def test_current_contract_package_never_needs_exemption(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repository_id = runtime.make_repo(root)
            staging, _ = runtime.make_fixture(root, repository_id)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST)
            self.assertFalse(report["contract_baseline_exemption"])

    def test_qa_semantic_gate_is_versioned_without_weakening_current_packages(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repository_id = runtime.make_repo(root)
            legacy, legacy_digest = make_legacy_fixture(root, repository_id)
            add_unregistered_qa_lineage(root, legacy)

            exempt = VALIDATOR.validate(
                legacy,
                repository_id,
                baseline={legacy_digest: "1.0.0"},
                repo_root=root,
            )
            self.assertEqual(exempt["status"], "pass")
            self.assertEqual(exempt["violations"], [])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repository_id = runtime.make_repo(root)
            current, _ = runtime.make_fixture(root, repository_id)
            add_unregistered_qa_lineage(root, current)

            strict = VALIDATOR.validate(
                current,
                repository_id,
                baseline={},
                repo_root=root,
            )
            self.assertEqual(strict["contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST)
            self.assertFalse(strict["contract_baseline_exemption"])
            self.assertIn(
                "qa-ref-unregistered",
                {item["code"] for item in strict["violations"]},
            )

    def test_exemption_is_scoped_to_contract_delta_not_to_violation_codes(self):
        """免除 package でも v1.0.0 が要求する節の欠落は fail する。

        違反 code 単位で免除すると task-spec-section-missing が丸ごと無効化され、
        goal-seek 以外の節欠落まで素通りする fail-open になる。
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repository_id = runtime.make_repo(root)
            staging, _ = make_legacy_fixture(root, repository_id)
            path = staging / VALIDATOR.TASK_PATHS[0]
            path.write_text(
                re.sub(r"\n## 目的\n.*?(?=\n## )", "", path.read_text(encoding="utf-8"), flags=re.S),
                encoding="utf-8",
            )
            digest = VALIDATOR.canonical_digest(staging, DIGEST_FILES)
            report = VALIDATOR.validate(staging, repository_id, baseline={digest: "1.0.0"})
            self.assertEqual(report["contract_version"], "1.0.0")
            self.assertEqual(report["status"], "fail")
            self.assertIn(
                ("task-spec-section-missing", "目的"),
                {(item["code"], item["detail"]) for item in report["violations"]},
            )

    def test_manifest_declared_digest_cannot_purchase_an_exemption(self):
        """免除照合は実体再計算 digest のみ。manifest の申告値は根拠にしない。

        staging-manifest.json は digest 対象集合の外にあり書き換え可能なので、
        申告値で免除を決めると台帳登録済み digest を騙るだけで契約を回避できる。
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repository_id = runtime.make_repo(root)
            staging, digest = make_legacy_fixture(root, repository_id)
            manifest_path = staging / "staging-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["canonical_digest"] = "sha256:" + "0" * 64
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            report = VALIDATOR.validate(staging, repository_id, baseline={digest: "1.0.0"})
            self.assertEqual(report["contract_version"], "1.0.0")
            self.assertIn("canonical-digest", {item["code"] for item in report["violations"]})

            spoofed = VALIDATOR.validate(
                staging, repository_id, baseline={"sha256:" + "0" * 64: "1.0.0"}
            )
            self.assertEqual(spoofed["contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST)
            self.assertFalse(spoofed["contract_baseline_exemption"])


class PromotionExemptionBoundaryTests(unittest.TestCase):
    def test_promotion_paths_never_consult_the_contract_baseline(self):
        """promote 経路は常に最新契約で検証する。

        免除を promotion へ効かせると、台帳へ digest を先回り登録するだけで旧契約準拠の
        package を新規昇格でき、契約強化が無意味になる。免除は既 promote package の
        再検証専用という境界を、呼び出し形として固定する。
        """
        source = (VALIDATOR.HERE / "promote-system-plan.py").read_text(encoding="utf-8")
        calls = [
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "validate"
        ]
        self.assertTrue(calls, "promoter must call the deterministic validator")
        for call in calls:
            keywords = {kw.arg: kw.value for kw in call.keywords}
            self.assertIn("baseline", keywords, "promotion must pin the contract baseline explicitly")
            self.assertIsInstance(keywords["baseline"], ast.Dict)
            self.assertEqual(keywords["baseline"].keys, [], "promotion must pass an empty baseline")


class BaselineAssetTests(unittest.TestCase):
    """同梱台帳の形を固定する。promote 済み generation の有無に依存しない。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline_document = json.loads(VALIDATOR.CONTRACT_BASELINE_ASSET.read_text(encoding="utf-8"))

    def test_asset_declares_the_latest_contract_version_known_to_the_validator(self):
        self.assertEqual(
            self.baseline_document["latest_contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST
        )
        self.assertEqual(
            set(self.baseline_document["contract_versions"]), set(VALIDATOR.CONTRACT_VERSIONS)
        )

    def test_every_entry_names_a_known_contract_version(self):
        packages = self.baseline_document.get("packages")
        self.assertIsInstance(packages, list, "baseline asset must be loadable")
        for entry in packages:
            with self.subTest(digest=str(entry.get("canonical_digest"))[:19]):
                self.assertRegex(entry.get("canonical_digest", ""), r"^sha256:[0-9a-f]{64}$")
                self.assertIn(entry.get("contract_version"), VALIDATOR.CONTRACT_VERSIONS)


@unittest.skipUnless(GENERATIONS.is_dir(), "promoted generations are not present in this checkout")
class ShippedBaselineTests(unittest.TestCase):
    """同梱台帳が実在 generation を指し、その契約で残違反ゼロになることを固定する。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = VALIDATOR.load_contract_baseline()
        # 検査対象 checkout の repository identity は validator 本体と同じ C09 解決に委ねる。
        cls.repository_id = VALIDATOR._resolver().build_context(
            ["--repo-root", str(REPO_ROOT), "--config", ".dev-graph/config.json"], dict(os.environ)
        )["repository_id"]
        cls.staged: dict[str, Path] = {}
        for package_json in sorted(GENERATIONS.glob("*/*/feature-package.json")):
            staging = package_json.parent
            if all((staging / rel).is_file() for rel in DIGEST_FILES):
                cls.staged[VALIDATOR.canonical_digest(staging, DIGEST_FILES)] = staging

    def test_every_registered_digest_resolves_to_a_promoted_generation(self):
        unknown = sorted(set(self.baseline) - set(self.staged))
        self.assertEqual(unknown, [], "台帳の digest が実在 generation と一致しない")

    def test_registered_generations_pass_under_their_recorded_contract(self):
        for digest, version in sorted(self.baseline.items()):
            with self.subTest(digest=digest[:19]):
                report = VALIDATOR.validate(self.staged[digest], self.repository_id)
                self.assertEqual(report["contract_version"], version)
                self.assertEqual(report["violations"], [])
                self.assertEqual(report["status"], "pass")

    def test_generations_passing_the_current_contract_are_not_registered(self):
        """現行契約で通る package を免除枠へ入れない (免除の希釈を防ぐ)。"""
        for digest, staging in sorted(self.staged.items()):
            if digest in self.baseline:
                continue
            with self.subTest(digest=digest[:19]):
                report = VALIDATOR.validate(staging, self.repository_id, baseline={})
                self.assertEqual(report["contract_version"], VALIDATOR.CONTRACT_VERSION_LATEST)
                self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
