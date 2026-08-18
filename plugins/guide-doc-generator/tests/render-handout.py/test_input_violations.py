"""違反系入力で exit 1 になる系 (script-brief-C11.json failure_modes / algorithm 3,5,6,7,8)。

いずれも「差し戻し先は構成データ側」= exit 1。HTML は出力されない。
"""

import copy
import tempfile
import unittest
from pathlib import Path

import _harness as H


class ViolationTestBase(unittest.TestCase):
    def render_expect(self, config, code, must_be_in_stderr=()):
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", config)
            out = Path(td) / "handout.html"
            res = H.run_render(["--config", cfg, "--out", out])
            self.assertEqual(code, res.returncode, "stderr=%s" % res.stderr)
            if code != 0:
                self.assertFalse(out.exists(), "違反時は HTML を出力しない")
            for token in must_be_in_stderr:
                self.assertIn(token, res.stderr)
            return res


class UnnormalizedConfigTest(ViolationTestBase):
    def test_missing_normalized_flag_is_exit1(self):
        """algorithm 3 / AC-C11-16: normalized:true が無い構成データは受け付けない。"""
        cfg = H.base_config()
        del cfg["normalized"]
        self.render_expect(cfg, 1, ["normalized"])

    def test_missing_schema_version_is_exit1(self):
        cfg = H.base_config()
        del cfg["schema_version"]
        self.render_expect(cfg, 1, ["schema_version"])

    def test_missing_date_is_exit1(self):
        """日付の単一ソースは C12。レンダラは既定値を埋めずに落とす。"""
        cfg = H.base_config()
        del cfg["date"]
        self.render_expect(cfg, 1, ["date"])

    def test_no_current_time_source_in_script(self):
        """AC-C11-16 後半: 現在日時を自前で取得する処理を 1 つも持たない。"""
        src = H.source_text()
        for forbidden in ("datetime.now", "date.today", "time.time", "datetime.today", "utcnow"):
            self.assertNotIn(forbidden, src, "%s を使ってはならない" % forbidden)


class DocumentFieldTest(ViolationTestBase):
    REQUIRED = (
        "title", "date", "reader", "prior_knowledge_level", "doc_type",
        "essential_problem", "purpose", "background", "goal", "duration", "sections",
    )

    def test_each_required_document_field_missing_is_exit1(self):
        """algorithm 6: 資料単位の必須フィールドはどれが欠けても exit 1 + キーパス。"""
        for field in self.REQUIRED:
            with self.subTest(field=field):
                cfg = H.base_config()
                del cfg[field]
                self.render_expect(cfg, 1, [field])

    def test_empty_string_document_field_is_exit1(self):
        """存在しても空文字なら exit 1 (存在と非空の両方を課す)。"""
        cfg = H.base_config(purpose="")
        self.render_expect(cfg, 1, ["purpose"])

    def test_unknown_doc_type_is_exit1(self):
        """algorithm 5: doc_type が用途語彙正本 (C23) に無ければ exit 1。"""
        cfg = H.base_config(doc_type="totally-unknown-purpose")
        self.render_expect(cfg, 1, ["doc_type"])

    def test_purpose_vocabulary_is_not_enumerated_in_script(self):
        """checklist C42: 用途語彙 8 語を script へ列挙しない (C23 の resolver 経由で照合)。"""
        src = H.source_text()
        self.assertIn("resolve-handout-preset", src, "C23 の resolver を import して照合すること")


class SectionFieldTest(ViolationTestBase):
    def test_empty_section_goal_is_exit1_with_section_id(self):
        """AC-C11-7 / checklist C38: section goal を 1 件だけ空にしたら exit 1 + 該当 section id。"""
        s1, s2 = H.base_section(1), H.base_section(2, id="s2")
        s2["goal"] = ""
        self.render_expect(H.base_config(sections=[s1, s2]), 1, ["s2", "goal"])

    def test_missing_lead_line_is_exit1(self):
        """checklist C40: lead_line は goal とは別軸として独立に必須。"""
        s1 = H.base_section(1)
        del s1["lead_line"]
        self.render_expect(H.base_config(sections=[s1]), 1, ["lead_line"])

    def test_missing_judgment_axis_is_exit1(self):
        """checklist C40: judgment_axis も goal / lead_line と独立に必須。"""
        s1 = H.base_section(1)
        del s1["judgment_axis"]
        self.render_expect(H.base_config(sections=[s1]), 1, ["judgment_axis"])

    def test_missing_section_heading_is_exit1(self):
        s1 = H.base_section(1)
        del s1["heading"]
        self.render_expect(H.base_config(sections=[s1]), 1, ["heading"])


class NavIntegrityTest(ViolationTestBase):
    def test_dangling_nav_fragment_is_exit1(self):
        """AC-C11-8 / checklist C3: 存在しない fragment を指す nav は exit 1 + 未解決アンカー。"""
        cfg = H.base_config()
        cfg["nav"] = [{"href": "#s1", "label": "A"}, {"href": "#s99", "label": "B"}]
        self.render_expect(cfg, 1, ["s99"])

    def test_orphan_section_without_nav_entry_is_exit1(self):
        """1:1 対応なので、nav に現れない section も exit 1 (孤立 section id を報告)。"""
        cfg = H.base_config()
        cfg["nav"] = [{"href": "#s1", "label": "A"}]
        self.render_expect(cfg, 1, ["s2"])


class BlockVocabularyTest(ViolationTestBase):
    def test_unknown_block_type_is_exit1(self):
        """failure_modes: 未知の block.type は既定部品へフォールバックせず fail-closed。"""
        block = {"id": "blk-x", "type": "no-such-block-type"}
        self.render_expect(H.config_with_block(block), 1, ["no-such-block-type"])

    def test_nested_tabs_second_level_is_exit1(self):
        """failure_modes: tabs の入れ子は 1 段まで。2 段目は exit 1 + キーパス。"""
        inner = copy.deepcopy(H.BLOCK_FIXTURES["tabs"])
        inner["id"] = "blk-tabs-inner"
        outer = copy.deepcopy(H.BLOCK_FIXTURES["tabs"])
        outer["tabs"][0]["blocks"] = [inner]
        self.render_expect(H.config_with_block(outer), 1, ["tabs"])

    def test_single_level_tabs_is_accepted(self):
        """1 段までは受理する (禁止の範囲を 2 段目に限定していることの担保)。"""
        self.render_expect(H.config_with_block(copy.deepcopy(H.BLOCK_FIXTURES["tabs"])), 0)


class ExternalReferenceTest(ViolationTestBase):
    def test_external_reference_in_config_is_exit1(self):
        """algorithm 23: 出力前に CR-EXT を当て、違反があれば出力せず exit 1。"""
        block = {
            "id": "blk-image",
            "type": "image",
            "asset_id": "asset-1",
            "alt": "外部画像",
            "data_uri": "https://example.com/screen.png",
            "caption": "外部参照",
        }
        cfg = H.config_with_block(block)
        cfg["assets"][0]["data_uri"] = "https://example.com/screen.png"
        self.render_expect(cfg, 1, ["https://example.com/screen.png"])

    def test_url_in_body_text_is_not_a_violation(self):
        """CR-EXT: テキストノード中の URL 文字列は違反ではない (fetch が起きないため)。"""
        block = {"id": "blk-text", "type": "text", "body": "参考: https://example.com を見てください"}
        self.render_expect(H.config_with_block(block), 0)

    def test_external_reference_rule_is_not_reimplemented(self):
        """CR-EXT の実装は C16 に 1 つだけ。C11 は scan_external_references を呼ぶ。"""
        src = H.source_text()
        self.assertIn("scan_external_references", src)
        self.assertIn("verify-handout-selfcontained", src)


if __name__ == "__main__":
    unittest.main()
