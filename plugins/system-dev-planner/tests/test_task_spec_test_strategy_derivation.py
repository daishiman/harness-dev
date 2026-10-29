"""層別方針の導出規則・冪等性・契約版境界値 (TS-B01..B10).

対応 task: SYS-TASK-SPEC-TEST-STRATEGY-P05 / test 設計正本:
`docs/features/feat-task-spec-test-strategy/test-plan.md` §4。

`Workstream applicability` の applicable 宣言から必須テスト層を導き、層別方針が
その層の必須マーカーを含むかを検査する経路を対象にする。全体 fixture を組まず
公開関数へ直接入力するのは、対象を導出規則そのものに絞るため (単体)。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_runtime as fx
from test_task_spec_test_strategy_sections import (
    CONTRACT_VERSION,
    ITEMS,
    spec_with_strategy,
    strategy_block,
)


VALIDATOR = fx.VALIDATOR
SCHEMA = json.loads(
    (fx.PLUGIN / "schemas" / VALIDATOR.TEST_STRATEGY_SCHEMA).read_text(encoding="utf-8")
)
PACKAGE_SCHEMA = json.loads(
    (fx.PLUGIN / "schemas" / "feature-execution-package.schema.json").read_text(encoding="utf-8")
)
# patch 差し替え後に module 属性を引くと自分自身を呼んで再帰するため、import 時に束縛する。
_CURRENT_TASK_SPEC_TEXT = fx.task_spec_text


def spec(workstream: str, policies: str = ITEMS["層別方針"]) -> str:
    return spec_with_strategy(
        "P01", block=strategy_block({**ITEMS, "層別方針": policies}), workstream=workstream
    )


def violation_codes(text: str, *, enforced: bool = True) -> list[str]:
    return [code for code, _ in VALIDATOR.test_strategy_violations(text, enforced=enforced)]


def version_tuple(value: str) -> tuple[int, ...]:
    """契約 version の大小比較。文字列比較では `1.10.0 < 1.2.0` と誤判定する。"""
    return tuple(int(part) for part in value.split("."))


class LayerDerivationTests(unittest.TestCase):
    """applicable な workstream から必須層を導き、方針の欠落を拒否する。"""

    def test_frontend_applicable_requires_behavior_policy(self):
        """TS-B01: フロントが applicable なら behavior ベースの方針が要る (qa-078)。"""
        text = spec("- Frontend: applicable; 画面を追加する")
        self.assertEqual(VALIDATOR.derive_required_layers(text), ["frontend"])
        self.assertIn("task-spec-test-strategy-layer", violation_codes(text))
        self.assertEqual(violation_codes(spec("- Frontend: applicable; 画面を追加する",
                                              "frontend: behavior ベースで検証する")), [])

    def test_backend_applicable_requires_contract_and_db_policy(self):
        """TS-B02: バックエンドは API 契約と DB 結合の双方が要る。片方だけでは通さない。"""
        text = spec("- Backend: applicable; 集計処理を足す")
        self.assertEqual(VALIDATOR.derive_required_layers(text), ["backend"])
        self.assertIn("task-spec-test-strategy-layer", violation_codes(text))
        half = spec("- Backend: applicable; 集計処理を足す", "backend: API 契約テストを置く")
        self.assertEqual(violation_codes(half), ["task-spec-test-strategy-layer"])
        full = spec("- Backend: applicable; 集計処理を足す",
                    "backend: API 契約テストとロジック単体、DB 結合テストを置く")
        self.assertEqual(violation_codes(full), [])

    def test_infrastructure_applicable_requires_iac_and_smoke_policy(self):
        """TS-B03: インフラは IaC 静的検証と smoke の双方が要る。"""
        text = spec("- Infrastructure: applicable; デプロイ定義を変える")
        self.assertEqual(VALIDATOR.derive_required_layers(text), ["infrastructure"])
        self.assertIn("task-spec-test-strategy-layer", violation_codes(text))
        full = spec("- Infrastructure: applicable; デプロイ定義を変える",
                    "infrastructure: IaC 静的検証と smoke テストを行う")
        self.assertEqual(violation_codes(full), [])

    def test_api_or_data_alone_still_requires_backend_policy(self):
        """TS-B04: API のみ / Data のみでも backend 層へ OR 結合される。

        層は「どのファイルを触るか」ではなく「どの実行基盤が壊れうるか」で決まる。
        API 契約変更も migration も壊す先は同じ backend である。
        """
        for line in ("- API: applicable; 契約を変える", "- Data: applicable; migration を足す"):
            with self.subTest(line=line):
                text = spec(line)
                self.assertEqual(VALIDATOR.derive_required_layers(text), ["backend"])
                self.assertIn("task-spec-test-strategy-layer", violation_codes(text))

    def test_all_layers_not_applicable_requires_explicit_na(self):
        """TS-B05: 全層 N/A なら方針は `N/A:` 明示で足りるが、空欄は許さない。

        「該当なし」と「書き忘れ」を機械可読に区別することが目的であり、
        沈黙を合格にすると層別方針は容易に空文になる。
        """
        text = spec("- Quality: applicable; 検証だけ行う\n- Frontend: N/A: 画面変更なし")
        self.assertEqual(VALIDATOR.derive_required_layers(text), [])
        self.assertEqual(violation_codes(text), [])
        self.assertIn("task-spec-test-strategy-item-empty",
                      violation_codes(spec("- Quality: applicable; 検証だけ行う", "")))

    def test_non_layer_workstreams_derive_no_layer(self):
        """Security/Quality/Documentation/Operations は層別テスト方針を導出しない。"""
        lines = "\n".join(
            f"- {name}: applicable; 変更する"
            for name in ("Security", "Quality", "Documentation", "Operations")
        )
        self.assertEqual(VALIDATOR.derive_required_layers(spec(lines)), [])

    def test_layer_order_is_stable_for_multiple_applicable_workstreams(self):
        """複数層が applicable でも戻り順は固定 (violation 列の決定性の前提)。"""
        text = spec(
            "- Infrastructure: applicable; deploy\n- Backend: applicable; logic\n"
            "- Frontend: applicable; view"
        )
        self.assertEqual(VALIDATOR.derive_required_layers(text), ["frontend", "backend", "infrastructure"])


class IdempotencyAndContractTests(unittest.TestCase):
    """再生成冪等性と契約版の境界値。"""

    def test_parse_is_idempotent_for_identical_input(self):
        """TS-B06: 同一本文の parse は項目集合も順序も一致する。"""
        text = spec_with_strategy("P01")
        first, first_errors = VALIDATOR.parse_test_strategy(text)
        second, second_errors = VALIDATOR.parse_test_strategy(text)
        self.assertEqual(first, second)
        self.assertEqual(list(first), list(second))
        self.assertEqual(first_errors, second_errors)
        self.assertEqual(
            list(first), ["schema_version", *(key for _, key in VALIDATOR.TEST_STRATEGY_ITEMS)]
        )

    def test_violations_are_idempotent_for_identical_input(self):
        """TS-B07: 同一入力の violation 列は順序まで完全一致する (証跡の再現性)。"""
        text = spec("- Backend: applicable; 集計処理を足す")
        first = VALIDATOR.test_strategy_violations(text, enforced=True)
        self.assertEqual(first, VALIDATOR.test_strategy_violations(text, enforced=True))
        self.assertEqual([code for code, _ in first], ["task-spec-test-strategy-layer"] * 2)

    def test_schema_required_matches_canonical_item_labels(self):
        """TS-B08: schema 正本の required と Python 側の 4 項目定数の drift を検出する。"""
        self.assertEqual(
            sorted(SCHEMA["required"]),
            sorted(["schema_version", *(key for _, key in VALIDATOR.TEST_STRATEGY_ITEMS)]),
        )
        self.assertEqual(SCHEMA["additionalProperties"], False)
        self.assertEqual(set(SCHEMA["properties"]), set(SCHEMA["required"]))

    def test_contract_version_threshold_boundaries(self):
        """TS-B09: 契約 version 台帳が enforced / legacy の境界を決める。

        段階適用の鍵は package の自己申告ではなく canonical digest である。台帳未登録
        (= 未知 digest) と digest 不能は latest へ倒れ、免除は台帳登録済みの digest に
        だけ与えられる。台帳の欠落・削除は「免除なし = より厳格」へ倒れる。
        """
        for version, expected in (("1.0.0", False), ("1.1.0", False), (CONTRACT_VERSION, True)):
            with self.subTest(version=version):
                self.assertEqual(VALIDATOR.CONTRACT_VERSIONS[version]["test_strategy"], expected)
        # latest が閾値と同値なのは契約が追加されるまでの偶然なので、主張するのは
        # 「latest は閾値以上」かつ「latest でも テスト戦略 は必須」の方。1.3.0 で
        # 世代非依存 rerun command が加わり両者は分離した (HarnessHub-ji8y)。
        latest = VALIDATOR.CONTRACT_VERSION_LATEST
        self.assertGreaterEqual(version_tuple(latest), version_tuple(CONTRACT_VERSION))
        self.assertTrue(VALIDATOR.CONTRACT_VERSIONS[latest]["test_strategy"])
        baseline = {"sha256:known": "1.1.0"}
        self.assertEqual(VALIDATOR.resolve_contract_version("sha256:known", baseline), "1.1.0")
        for unknown in ("sha256:" + "0" * 64, None):
            with self.subTest(digest=unknown):
                self.assertEqual(VALIDATOR.resolve_contract_version(unknown, baseline), latest)
        self.assertEqual(VALIDATOR.resolve_contract_version("sha256:known", {}), latest)

    def test_existing_generation_shape_stays_passing(self):
        """TS-B10: 15 section のみの既存形状は台帳免除下で pass のまま (AC-7 の実装側根拠)。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = fx.make_repo(root)
            with mock.patch.object(
                fx, "task_spec_text", lambda phase: _CURRENT_TASK_SPEC_TEXT(phase, strategy=None)
            ):
                staging, digest = fx.make_fixture(root, repository_id)
            before = VALIDATOR.validate(staging, repository_id, baseline={digest: "1.1.0"})
            self.assertEqual(before["status"], "pass", before["violations"])
            self.assertEqual(before["validated_digest"], digest)
            self.assertEqual(before["violations"], [])
            self.assertEqual(before["phase_refs"], VALIDATOR.PHASES)
            self.assertEqual(before["test_strategy_contract"]["mode"], "legacy")
            self.assertEqual(
                VALIDATOR.test_strategy_violations(
                    fx.task_spec_text("P01"), enforced=False
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
