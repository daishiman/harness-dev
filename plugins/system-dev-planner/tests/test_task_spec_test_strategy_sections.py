"""`## テスト戦略` section 契約の構造・fail-closed 実効性・正本 parity (TS-A01..A16).

対応 task: SYS-TASK-SPEC-TEST-STRATEGY-P05 / test 設計正本:
`docs/features/feat-task-spec-test-strategy/test-plan.md` §3。

悪性ケースのメソッド名には `malformed` を含める。P09 の automated command が
`pytest -k malformed` で悪性部分集合だけを選択するため、命名がそのまま
選択条件になっている (test-plan §6)。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_runtime as fx


VALIDATOR = fx.VALIDATOR
HANDOFF = fx.HANDOFF
PLUGIN = fx.PLUGIN
TEMPLATE = PLUGIN / "references" / "system-task-spec-template.md"
PLAN_TEMPLATE = (
    PLUGIN.parents[1]
    / "plugin-plans"
    / "system-dev-planner"
    / "references"
    / "system-task-spec-template.md"
)
# テスト戦略 section を必須化した契約版と、その直前版。段階適用は package の自己申告では
# なく契約 version 台帳 (canonical digest -> version) が決めるため、テスト側も
# 「台帳に登録されているか」で enforced / legacy を作り分ける。
CONTRACT_VERSION = VALIDATOR.TEST_STRATEGY_CONTRACT_FROM
LEGACY_CONTRACT_VERSION = "1.1.0"
DIGEST_FILES = [*VALIDATOR.BASE_DIGEST_FILES, VALIDATOR.HANDOFF_PATH]

# 4 項目の正本ラベルと、必須語をすべて満たす良性の本文。
ITEMS: dict[str, str] = {
    "テストレベル選定": "単体・結合・境界値・回帰の4レベルを適用する。",
    "カバレッジ目標": "既定 80% を維持する。",
    "層別方針": "N/A: 実行基盤の層を触らない変更である。",
    "保守性制約": "pixel 位置依存と DOM 構造依存のテストを禁止する。",
}


def strategy_block(items: dict[str, str] | None = None, order: list[str] | None = None) -> str:
    items = ITEMS if items is None else items
    return "\n".join(f"- {label}: {items[label]}".rstrip() for label in (order or list(items)))


# fx.task_spec_text() が埋める Workstream applicability の本文 (置換対象)。
BASE_WORKSTREAM = "- Quality: applicable; verify the phase\n- Frontend: N/A: no UI change"


def spec_with_strategy(
    phase: str,
    block: str | None = None,
    *,
    anchor: str = "## Verification and evidence",
    workstream: str | None = None,
) -> str:
    """base task spec の指定 anchor 直前へ `## テスト戦略` を差し込む。

    共有 fixture は既定で section を含むため、差し込み対象は `strategy=None` で
    section を落とした本文を使う。そうしないと重複違反が混ざって検査対象がぼやける。
    """
    text = fx.task_spec_text(phase, strategy=None)
    if workstream is not None:
        text = text.replace(BASE_WORKSTREAM, workstream, 1)
    section = f"## テスト戦略\n\n{strategy_block() if block is None else block}\n\n"
    if anchor == "END":
        return text + "\n" + section
    return text.replace(anchor, section + anchor, 1)


def legacy_baseline(staging: Path) -> dict[str, str]:
    """当該 staging 実体を契約 1.1.0 (テスト戦略 導入前) へ解決させる台帳を返す。

    digest は staging-manifest.json の申告値ではなく実ファイル群から再計算する。
    validator が免除判定に使うのと同じ経路でなければ、テストが実際の解決規則ではなく
    申告値を検証してしまう。
    """
    return {VALIDATOR.canonical_digest(staging, DIGEST_FILES): LEGACY_CONTRACT_VERSION}


def baseline_for(staging: Path, contract_version: str) -> dict[str, str]:
    """enforced は空台帳 (未知 digest -> latest)、legacy は当該 digest の登録で表す。"""
    return {} if contract_version == CONTRACT_VERSION else legacy_baseline(staging)


def rebuild(root: Path, staging: Path, repository_id: str) -> str:
    """task spec / package を書き換えた後に handoff と manifest を再確定する。

    manifest だけ更新すると handoff の source digest が古いままとなり、本 feature の
    検査とは無関係な violation が混ざる。make_fixture と同じ経路で作り直す。
    C14 は commit point として「既存 handoff の source digest が現在の入力と一致する」
    ことを要求するため、いったん base manifest 状態 (handoff 無し) へ戻してから通す。
    """
    (staging / "system-build-handoff.json").unlink(missing_ok=True)
    rels = list(VALIDATOR.BASE_DIGEST_FILES)
    fx.dump(staging / "staging-manifest.json", {
        "files": {rel: hashlib.sha256((staging / rel).read_bytes()).hexdigest() for rel in rels},
        "canonical_digest": VALIDATOR.canonical_digest(staging, rels),
    })
    package, inventory, graph, contents, manifest, source_manifest = HANDOFF._validate_sources(
        repo_root=root.resolve(), staging=staging.resolve(), repository_id=repository_id, validator=VALIDATOR,
    )
    handoff = HANDOFF._build_handoff(package, inventory, graph, contents, source_manifest)
    HANDOFF._schema_check(handoff, VALIDATOR)
    return HANDOFF._commit(staging, manifest, handoff, contents)["canonical_digest"]


def enforced_fixture(root: Path, repository_id: str, *, with_section: bool = True) -> Path:
    """13 件すべてに section を持つ (または全件から落とした) 台帳未登録 package。

    台帳未登録 = 未知 digest なので、validator は latest (テスト戦略 必須) で検証する。
    """
    staging, _ = fx.make_fixture(root, repository_id)
    if not with_section:
        for rel, phase in zip(VALIDATOR.TASK_PATHS, VALIDATOR.PHASES):
            (staging / rel).write_text(fx.task_spec_text(phase, strategy=None), encoding="utf-8")
        rebuild(root, staging, repository_id)
    return staging


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["violations"]}


class TestStrategySectionContractTests(unittest.TestCase):
    """契約版で段階適用される section 検査の受理/拒否境界。"""

    def test_legacy_package_without_section_passes(self):
        """TS-A01: 台帳で 1.1.0 へ免除 + section 無し = 既存 promoted 世代の形状。

        テスト戦略 導入前に promote された package は digest 不変ゆえ section を後から
        足せない。台帳経由の免除でしか非退行 (exact-13 acceptance 7) を守れない。
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = enforced_fixture(root, repository_id, with_section=False)
            report = VALIDATOR.validate(staging, repository_id, baseline=legacy_baseline(staging))
            self.assertEqual(report["status"], "pass", report["violations"])
            self.assertEqual(report["test_strategy_contract"]["mode"], "legacy")

    def test_enforced_package_without_section_is_rejected(self):
        """TS-A02: 台帳未登録 (= 現行契約) の package は section 欠落を 13 件全件で拒否する。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = enforced_fixture(root, repository_id, with_section=False)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "fail")
            missing = [x for x in report["violations"] if x["code"] == "task-spec-test-strategy-missing"]
            self.assertEqual(len(missing), 13)
            self.assertEqual(report["test_strategy_contract"]["mode"], "enforced")

    def test_enforced_package_with_complete_section_passes(self):
        """TS-A03: 4 項目を正順で満たした 13 件は enforced でも pass する。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = enforced_fixture(root, repository_id)
            report = VALIDATOR.validate(staging, repository_id, baseline={})
            self.assertEqual(report["status"], "pass", report["violations"])
            self.assertEqual(report["test_strategy_contract"]["mode"], "enforced")

    def _reject(self, text: str, expected: str, *, version: str = CONTRACT_VERSION) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging = enforced_fixture(root, repository_id)
            (staging / VALIDATOR.TASK_PATHS[0]).write_text(text, encoding="utf-8")
            fx.refresh_manifest(staging)
            report = VALIDATOR.validate(staging, repository_id, baseline=baseline_for(staging, version))
            self.assertEqual(report["status"], "fail")
            self.assertIn(expected, codes(report))

    def test_malformed_duplicate_section_is_rejected(self):
        """TS-A04 (R-2): 2 個目の `## テスト戦略` はどちらを正とするか決められない。"""
        self._reject(
            spec_with_strategy("P01") + "\n## テスト戦略\n\n" + strategy_block() + "\n",
            "task-spec-test-strategy-duplicate",
        )

    def test_malformed_empty_section_body_is_rejected(self):
        """TS-A05 (R-3): 見出しだけ置いて中身を書かない緑化を拒否する。"""
        self._reject(spec_with_strategy("P01", block=""), "task-spec-test-strategy-empty")

    def test_malformed_partial_item_loss_is_rejected(self):
        """TS-A06 (R-4): 4 項目のうち 1 件欠落を 4 通りすべてで拒否する。"""
        for dropped in ITEMS:
            with self.subTest(dropped=dropped):
                order = [label for label in ITEMS if label != dropped]
                self._reject(
                    spec_with_strategy("P01", block=strategy_block(order=order)),
                    "task-spec-test-strategy-item-missing",
                )

    def test_malformed_item_order_swap_is_rejected(self):
        """TS-A07 (R-5): 項目順序は再生成冪等性の判定単位なので入替も拒否する。"""
        swapped = ["カバレッジ目標", "テストレベル選定", "層別方針", "保守性制約"]
        self._reject(
            spec_with_strategy("P01", block=strategy_block(order=swapped)),
            "task-spec-test-strategy-item-order",
        )

    def test_malformed_empty_item_body_is_rejected(self):
        """TS-A08 (R-6): ラベルだけ並べて本文を空にする形骸化を拒否する。"""
        for empty in ITEMS:
            with self.subTest(empty=empty):
                items = {**ITEMS, empty: ""}
                self._reject(
                    spec_with_strategy("P01", block=strategy_block(items)),
                    "task-spec-test-strategy-item-empty",
                )

    def test_malformed_missing_required_marker_is_rejected(self):
        """TS-A09 (R-7): 必須語 (4レベル語 / 80% / pixel / DOM) の欠落を schema が拒否する。"""
        cases = {
            "テストレベル選定": "単体と結合だけを行う。",
            "カバレッジ目標": "できるだけ広く測る。",
            "保守性制約": "実装詳細へ密結合させない。",
        }
        for label, weakened in cases.items():
            with self.subTest(label=label):
                self._reject(
                    spec_with_strategy("P01", block=strategy_block({**ITEMS, label: weakened})),
                    "task-spec-test-strategy-content",
                )

    def test_malformed_section_placement_is_rejected(self):
        """TS-A10 (R-9): scope→テスト範囲→検証手段の並びを崩す配置を拒否する。"""
        self._reject(spec_with_strategy("P01", anchor="END"), "task-spec-test-strategy-placement")

    def test_legacy_package_with_malformed_section_is_rejected(self):
        """TS-A11: strict-if-present。台帳で免除された世代でも書いた以上は検査が発火する。"""
        order = ["テストレベル選定", "カバレッジ目標", "層別方針"]
        self._reject(
            spec_with_strategy("P01", block=strategy_block(order=order)),
            "task-spec-test-strategy-item-missing",
            version=LEGACY_CONTRACT_VERSION,
        )

    def test_cli_exit_code_is_two_on_missing_section(self):
        """TS-A14: fail-closed の実効性は report ではなく exit code で担保される。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); repository_id = fx.make_repo(root)
            enforced_fixture(root, repository_id, with_section=False)
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}, clear=True), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = VALIDATOR.main(["--repo-root", str(root), "--staging", ".dev-graph/staging/run-1"])
            self.assertEqual(rc, 2)
            self.assertIn("task-spec-test-strategy-missing", stdout.getvalue())

    def test_report_declares_contract_mode(self):
        """TS-A15: 適用モードを常に出力する。silent skip は緑の意味を壊す。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            staging, _ = fx.make_fixture(root, repository_id)
            legacy = VALIDATOR.validate(
                staging, repository_id, baseline=legacy_baseline(staging)
            )["test_strategy_contract"]
            self.assertEqual(legacy, {
                "mode": "legacy",
                "contract_version": LEGACY_CONTRACT_VERSION,
                "enforced_from": CONTRACT_VERSION,
            })
            enforced = VALIDATOR.validate(
                staging, repository_id, baseline={}
            )["test_strategy_contract"]
            self.assertEqual(enforced, {
                "mode": "enforced",
                "contract_version": VALIDATOR.CONTRACT_VERSION_LATEST,
                "enforced_from": CONTRACT_VERSION,
            })


class TemplateAndParityTests(unittest.TestCase):
    """生成側正本と検証側定数の drift 検出 (finding F-1 の緩和策を含む)。"""

    def test_plan_ssot_and_built_template_are_byte_identical(self):
        """TS-A16: plan 正本と配布用 plugin copy の片側更新を拒否する。"""
        self.assertEqual(PLAN_TEMPLATE.read_bytes(), TEMPLATE.read_bytes())

    def test_template_reference_declares_section_and_items(self):
        """TS-A12: 生成器が読むテンプレート正本に見出しと 4 ラベルが正順で存在する。

        ここが欠けると validator だけが section を要求し生成器は永久に出力しない、
        という空洞化した契約になる。
        """
        text = TEMPLATE.read_text(encoding="utf-8")
        headings = [name for name, _ in VALIDATOR._task_spec_sections(text)]
        self.assertIn(VALIDATOR.TEST_STRATEGY_SECTION, headings)
        before, after = VALIDATOR.TEST_STRATEGY_PLACEMENT
        self.assertLess(headings.index(before), headings.index(VALIDATOR.TEST_STRATEGY_SECTION))
        self.assertLess(headings.index(VALIDATOR.TEST_STRATEGY_SECTION), headings.index(after))
        value, errors = VALIDATOR.parse_test_strategy(text)
        self.assertEqual(errors, [])
        self.assertEqual(
            sorted(value), sorted(["schema_version", *(key for _, key in VALIDATOR.TEST_STRATEGY_ITEMS)])
        )
        self.assertIn("template_version: 1.2.0", text)

    def test_required_sections_parity_between_c12_and_c14(self):
        """TS-A13: 15 section 契約は C12 と C14 に独立コピーされている (F-1)。

        本 feature は複製を増やさない代わりに、既存の drift を検出する機構を置く。
        テスト戦略検査は C12 のみが持つ (promotion authority は C12 の exit code)。
        """
        self.assertEqual(VALIDATOR.REQUIRED_TASK_SPEC_SECTIONS, HANDOFF.REQUIRED_TASK_SPEC_SECTIONS)
        self.assertNotIn(VALIDATOR.TEST_STRATEGY_SECTION, VALIDATOR.REQUIRED_TASK_SPEC_SECTIONS)
        self.assertFalse(hasattr(HANDOFF, "TEST_STRATEGY_SECTION"))


if __name__ == "__main__":
    unittest.main()
