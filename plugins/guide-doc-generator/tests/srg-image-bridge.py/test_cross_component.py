"""component 境界 — AC-C21-4 (C01 との fail-soft 統合) / C13 との責務境界。

AC-C21-4 の判定そのものは C01 側の統合テストが持つが、**C21 の skip が呼び出し元へ
伝わること**は C21 の受入条件でもある。ここでは C21 側から観測できる 2 点を固定する。
1. C01 が C21 を起動し、skip を成果物 (生成レポート) へ明示する契約を宣言していること。
2. data URI 化 (C13) と素材配置 (C19) を C21 が肩代わりしていないこと。
"""

import unittest
from pathlib import Path

import _harness as H


BUILD_SKILL = H.PLUGIN_ROOT / "skills" / "run-handout-build" / "SKILL.md"
EMBED_SCRIPT = H.PLUGIN_ROOT / "scripts" / "embed-assets.py"  # C13


class BuildSkillContractTest(H.BridgeTestCase):
    """AC-C21-4: 画像ステップだけが skip され、成功として黙って畳まれない。"""

    def _text(self):
        return H.require_file(self, BUILD_SKILL, "C01").read_text(encoding="utf-8")

    def test_build_skill_invokes_this_script(self):
        self.assertIn(H.SCRIPT_NAME, self._text(), "C01 が C21 を起動する記述が無い")

    def test_build_skill_surfaces_the_skip_reason(self):
        text = self._text()
        self.assertTrue(
            any(reason in text for reason in H.SKIP_REASONS),
            "skip 理由をレポートへ明示する記述が無い (skip を成功へ畳む余地が残る)",
        )

    def test_build_skill_does_not_treat_exit0_as_generated(self):
        """exit 0 は『生成した』と『skip した』の両方を含むので、status を見る必要がある。"""
        self.assertIn("status", self._text(), "stdout の status を読む記述が無い")


class DataUriBoundaryTest(H.BridgeTestCase):
    """C13 が data URI 化の owner。C21 は PNG を素材ディレクトリへ置くところまで。"""

    def test_embed_assets_script_is_the_base64_owner(self):
        text = H.require_file(self, EMBED_SCRIPT, "C13").read_text(encoding="utf-8")
        self.assertIn("base64", text, "C13 が data URI 化を持っていない")

    def test_bridge_source_has_no_base64(self):
        self.assertNotIn("base64", H.read_source(self), "C21 が C13 の責務を肩代わりしている")


class InventorySyncTest(unittest.TestCase):
    """ブリーフと inventory の宣言が食い違っていないこと (P03 Y-01 / Y-09)。"""

    def test_component_kind_and_name(self):
        component = H.inventory_component("C21")
        self.assertEqual("script", component.get("component_kind"))
        self.assertEqual(H.SCRIPT_NAME, component.get("name"))

    def test_network_is_true_in_both_sources(self):
        self.assertIs(True, H.inventory_component("C21").get("network"))
        self.assertIs(True, H.brief()["network"]["value"])

    def test_stdlib_only_is_declared(self):
        self.assertIs(True, H.inventory_component("C21").get("stdlib_only"))
        self.assertIs(True, H.brief()["stdlib_only"])

    def test_write_scope_is_assets_dir(self):
        self.assertEqual("assets-dir", H.inventory_component("C21").get("write_scope"))


if __name__ == "__main__":
    unittest.main()
