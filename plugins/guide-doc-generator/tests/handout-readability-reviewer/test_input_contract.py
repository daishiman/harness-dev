"""input_contract: ## Inputs が受け取るものと、起動の前提を宣言していること。"""

from __future__ import annotations

import hb_c06 as H

INPUTS = "## Inputs"


class TestReceives(H.AgentContractTestCase):
    """input_contract.receives の 5 項目が Inputs に宣言されていること。"""

    def test_html_path(self):
        self.assert_mentions("html_path", "判定対象 HTML の受け口", where=INPUTS)

    def test_config_path(self):
        self.assert_mentions("config_path", "正規化済み構成データの受け口", where=INPUTS)

    def test_gate_reports(self):
        self.assert_mentions("gate_reports", "決定論ゲート結果の受け口", where=INPUTS)

    def test_reader_profile(self):
        self.assert_mentions("reader_profile", "誰の立場で読むかの指定", where=INPUTS)

    def test_scope(self):
        self.assert_mentions("scope", "部分レビュー指定の受け口", where=INPUTS)

    def test_scope_is_optional_and_defaults_to_whole(self):
        self.assert_mentions_any(
            ("省略時は全体", "任意", "optional"),
            "scope が任意であり省略時は全体レビューになることの宣言",
            where=INPUTS,
        )

    def test_reader_profile_fields(self):
        for field in ("reader", "prior_knowledge_level", "usage_scene"):
            with self.subTest(field=field):
                self.assert_mentions(
                    field, "reader_profile の構成要素", where=INPUTS
                )


class TestGatePrecondition(H.AgentContractTestCase):
    """AC7 の前段: 決定論ゲート 4 本が exit0 であることが起動の前提。"""

    def test_all_four_gates_named(self):
        for gate in H.MACHINE_GATES:
            with self.subTest(gate=gate):
                self.assert_mentions(gate, "決定論ゲート {} の明示".format(gate))

    def test_exit0_precondition_declared(self):
        self.assert_mentions_any(
            ("exit0", "exit 0"), "全ゲート exit0 が起動の前提であることの明示"
        )


class TestReadsFiles(H.AgentContractTestCase):
    """input_contract.reads_files: 読む対象が宣言され、規範の正本が references であること。"""

    def test_reads_generated_html(self):
        self.assert_mentions("html_path", "生成 HTML を読む")

    def test_reads_normalized_config(self):
        self.assert_mentions("config_path", "正規化済み構成データを読む")

    def test_reads_gate_json_reports(self):
        self.assert_mentions_any(
            ("json-report", "json_report"), "決定論ゲートの json-report を読む"
        )

    def test_reads_design_system_references(self):
        self.assert_mentions_any(
            ("plugins/guide-doc-generator/references/", "ref-handout-design-system"),
            "評価規範 (文章設計の型) の正本を読む",
        )
