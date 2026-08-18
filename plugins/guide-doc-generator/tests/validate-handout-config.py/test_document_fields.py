# -*- coding: utf-8 -*-
"""文書レベル / セクションレベルの意味規約 (A5 / A6 / A7 / A10 / A11 / A12)。

AC-C12-02/03/04/12/13/18/19/20 と、document_level_fields / section_fields の制約が出所。
"""

import unicodedata
import unittest

import _harness as H


class DocumentFields(H.C12TestCase):

    def test_required_document_field_missing(self):
        """必須 document フィールドの欠落は E-FIELD-MISSING (A5)。"""
        for key in ("title", "doc_type", "purpose", "background", "goal", "reader",
                    "prior_knowledge_level", "essential_problem", "duration"):
            with self.subTest(key=key):
                cfg = H.valid_config()
                del cfg[key]
                res, _ = self.validate(cfg)
                self.assert_fails_with(res, "E-FIELD-MISSING", "/" + key)

    def test_required_document_field_blank(self):
        """空白のみの文字列は空扱いで E-FIELD-EMPTY (A5)。"""
        cfg = H.valid_config()
        cfg["purpose"] = "   "
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FIELD-EMPTY", "/purpose")

    def test_unknown_top_level_key(self):
        """AC-C12-19: 既知キー以外のトップレベルキーは E-KEY-UNKNOWN。"""
        cfg = H.valid_config()
        cfg["author"] = "だれか"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-KEY-UNKNOWN", "/author")

    def test_use_scene_is_rejected_as_unknown_key(self):
        """failure_modes: doc_type と同義の use_scene を第 2 の入口にしない。"""
        cfg = H.valid_config()
        cfg["use_scene"] = "勉強会"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-KEY-UNKNOWN", "/use_scene")
        self.assertIn("doc_type", res.stderr, "doc_type を使うよう促していない: %r" % res.stderr)

    def test_unknown_key_inside_section(self):
        """未知キーは全レベルで落とす。"""
        cfg = H.valid_config()
        cfg["sections"][0]["memo"] = "x"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-KEY-UNKNOWN", "/sections/0/memo")

    def test_title_length_upper_bound(self):
        """title は 1..120 文字。超過は違反。"""
        cfg = H.valid_config()
        cfg["title"] = "a" * 121
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_title_long_is_warning_only(self):
        """60 文字超は W-TITLE-LONG (警告であって違反ではない)。"""
        cfg = H.valid_config()
        cfg["title"] = "a" * 61
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-TITLE-LONG", "/title")

    def test_strict_turns_warning_into_failure(self):
        """AC-C12-20: warning のみの入力は --strict なしで 0、ありで 1。"""
        cfg = H.valid_config()
        cfg["title"] = "a" * 61
        res_lax, _ = self.validate(cfg)
        self.assert_exit(res_lax, 0)
        self.assert_diag(res_lax, "W-TITLE-LONG")
        res_strict, _ = self.validate(cfg, "--strict")
        self.assert_exit(res_strict, 1)
        self.assert_diag(res_strict, "W-TITLE-LONG")

    def test_prior_knowledge_level_enum(self):
        """prior_knowledge_level は none|basic|intermediate の 3 段固定。"""
        cfg = H.valid_config()
        cfg["prior_knowledge_level"] = "advanced"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_document_duration_format(self):
        """document.duration は既定の 3 書式のみ。"""
        cfg = H.valid_config()
        cfg["duration"] = "だいたい 1 時間くらい"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_document_duration_accepts_range_and_page_count(self):
        """範囲表記と 'A4 n 枚相当' は document レベルでは受理される。"""
        for value in ("30〜45分", "A4 3 枚相当", "2時間"):
            with self.subTest(value=value):
                cfg = H.valid_config()
                cfg["duration"] = value
                res, _ = self.validate(cfg)
                self.assert_exit(res, 0)

    def test_subject_slug_format(self):
        """subject_slug は ^[a-z0-9][a-z0-9-]{0,39}$。"""
        cfg = H.valid_config()
        cfg["subject_slug"] = "AI_Handout"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_schema_version_unknown(self):
        """既知バージョンとの完全一致。未知は E-SCHEMA-VERSION。"""
        cfg = H.valid_config()
        cfg["schema_version"] = "2.0"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SCHEMA-VERSION", "/schema_version")

    def test_sections_many_is_warning(self):
        """failure_modes: 12 件超は W-SECTIONS-MANY で通す (分量は正しさの問題ではない)。"""
        cfg = H.valid_config()
        cfg["sections"] = [H.section("s%02d" % i) for i in range(13)]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-SECTIONS-MANY")

    def test_sections_empty(self):
        """sections は 1 件以上。"""
        cfg = H.valid_config()
        cfg["sections"] = []
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)


class DocTypeVocabulary(H.C12TestCase):

    def test_unknown_doc_type(self):
        """AC-C12-12: 語彙外の doc_type は E-DOCTYPE-UNKNOWN で exit 1。"""
        cfg = H.valid_config()
        cfg["doc_type"] = "workshop"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-DOCTYPE-UNKNOWN", "/doc_type")

    def test_unknown_doc_type_lists_vocabulary(self):
        """AC-C12-12: 全語彙一覧を stderr に出す (利用者が直せる情報量)。"""
        cfg = H.valid_config()
        cfg["doc_type"] = "workshop"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)
        catalog_path = self.root / H.PURPOSES_CATALOG_RELPATH
        self.assertTrue(catalog_path.exists(), "用途語彙正本が無い: %s" % catalog_path)
        import json as _json
        # 語彙配列のキーは "vocabulary" (owner: C23 resolve-handout-preset.py)。
        # "entries" ではない — 正本のキー名は C23 の script と他 3 スイートが読む側に揃える。
        slugs = [e["slug"]
                 for e in _json.loads(catalog_path.read_text(encoding="utf-8"))["vocabulary"]]
        for slug in slugs:
            self.assertIn(slug, res.stderr, "語彙一覧に %s が無い: %r" % (slug, res.stderr))

    def test_alias_is_normalized_to_slug(self):
        """AC-C12-13: alias で書かれた doc_type は正規の slug へ置き換わる (N6)。"""
        cfg = H.valid_config()
        cfg["doc_type"] = "勉強会"
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual("lecture", self.read_out(out)["doc_type"])

    def test_alias_passes_validation_without_normalize(self):
        """alias は語彙正本に含まれるので検証だけでも通る。"""
        cfg = H.valid_config()
        cfg["doc_type"] = "勉強会"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


class SectionFields(H.C12TestCase):

    def test_section_goal_missing(self):
        """AC-C12-02: セクション goal の欠落は E-FIELD-MISSING と該当キーパス (C38)。"""
        cfg = H.valid_config()
        del cfg["sections"][1]["goal"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FIELD-MISSING", "/sections/1/goal")

    def test_section_lead_line_empty(self):
        """AC-C12-03: lead_line の空文字は E-FIELD-EMPTY (C15)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["lead_line"] = ""
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FIELD-EMPTY", "/sections/0/lead_line")

    def test_section_judgment_axis_empty(self):
        """judgment_axis の空文字も同じく違反 (C15)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["judgment_axis"] = ""
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FIELD-EMPTY", "/sections/0/judgment_axis")

    def test_r11_and_r19_checks_are_independent(self):
        """AC-C12-04: lead_line/judgment_axis (R11) と goal (R19) は互いを代替しない (C40)。"""
        base = H.valid_config()
        res_ok, _ = self.validate(base)
        self.assert_exit(res_ok, 0)

        only_r11 = H.valid_config()
        only_r11["sections"][0]["goal"] = ""
        res1, _ = self.validate(only_r11)
        self.assert_fails_with(res1, "E-FIELD-EMPTY", "/sections/0/goal")

        only_r19 = H.valid_config()
        only_r19["sections"][0]["lead_line"] = ""
        only_r19["sections"][0]["judgment_axis"] = ""
        res2, _ = self.validate(only_r19)
        self.assert_exit(res2, 1)
        self.assert_diag(res2, "E-FIELD-EMPTY", "/sections/0/lead_line")
        self.assert_diag(res2, "E-FIELD-EMPTY", "/sections/0/judgment_axis")

    def test_lead_line_multiline(self):
        """lead_line に改行を含むと E-LEADLINE-MULTILINE。"""
        cfg = H.valid_config()
        cfg["sections"][0]["lead_line"] = "指示は目的から書く\nそして前提を書く"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-LEADLINE-MULTILINE", "/sections/0/lead_line")

    def test_judgment_axis_multiline(self):
        """judgment_axis に改行を含むと E-AXIS-MULTILINE。"""
        cfg = H.valid_config()
        cfg["sections"][0]["judgment_axis"] = "迷ったら受け手で決める\n次に頻度で決める"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-AXIS-MULTILINE", "/sections/0/judgment_axis")

    def test_lead_line_long_is_warning(self):
        """60 文字超の lead_line は W-LEADLINE-LONG (80 文字以内なら違反ではない)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["lead_line"] = "あ" * 61
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-LEADLINE-LONG", "/sections/0/lead_line")

    def test_section_id_duplicate(self):
        """section id は sections 内で一意。"""
        cfg = H.valid_config()
        cfg["sections"][1]["id"] = cfg["sections"][0]["id"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_section_id_reserved_word(self):
        """予約語 (hero / nav / footer / memo) は id に使えない (C11 の chrome と衝突)。"""
        for reserved in ("hero", "nav", "footer", "memo"):
            with self.subTest(reserved=reserved):
                cfg = H.valid_config()
                cfg["sections"][0]["id"] = reserved
                cfg["sections"][0]["parts"] = [H.text_part("t1")]
                res, _ = self.validate(cfg)
                self.assert_exit(res, 1)

    def test_section_id_format(self):
        """section id は ^[a-z0-9][a-z0-9-]{0,39}$。"""
        cfg = H.valid_config()
        cfg["sections"][0]["id"] = "-Intro"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_unknown_section_kind(self):
        """section_kind は config/handout-sections.json の slug に限る (A7)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["section_kind"] = "brainstorm"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_all_catalog_section_kinds_are_accepted(self):
        """語彙正本にある slug は (追加制約を満たす限り) 拒否されない。列挙元はデータファイル。"""
        catalog = self.sections_catalog()
        slugs = [k["slug"] for k in catalog["section_kinds"]]
        self.assertIn("standard", slugs)
        cfg = H.valid_config()
        cfg["sections"][0]["section_kind"] = "standard"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_parts_empty(self):
        """parts は 1 件以上。"""
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = []
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_document_scope_part_cannot_be_placed_in_section(self):
        """section_scope=document の部品 (B01/B02) は generated-chrome で parts に置けない (A8)。"""
        for part_id in ("B01", "B02"):
            with self.subTest(part=part_id):
                cfg = H.valid_config()
                cfg["sections"][0]["parts"] = [{"part": part_id, "id": "x1", "data": {}}]
                res, _ = self.validate(cfg)
                self.assert_exit(res, 1)

    def test_unknown_part_id(self):
        """カタログに無い part id は違反 (id を script が列挙しない)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = [{"part": "B99", "id": "x1", "data": {}}]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_part_shape_mismatch(self):
        """B05 の cells 数と columns 数の不一致は E-PART-SHAPE。"""
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = [{
            "part": "B05", "id": "tbl", "data": {
                "columns": ["A", "B"],
                "rows": [{"header": "行1", "cells": ["1"], "highlight": []}],
            },
        }]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-PART-SHAPE")

    def test_nested_tabs_are_rejected(self):
        """B13 の中に B13 を入れ子にできない (E-PART-NESTED-TABS)。"""
        inner = {"part": "B13", "id": "inner", "data": {"tabs": [
            {"key": "a", "label": "A", "panel_parts": [H.text_part("i1")]},
            {"key": "b", "label": "B", "panel_parts": [H.text_part("i2")]},
        ]}}
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = [{"part": "B13", "id": "outer", "data": {"tabs": [
            {"key": "a", "label": "A", "panel_parts": [inner]},
            {"key": "b", "label": "B", "panel_parts": [H.text_part("o1")]},
        ]}}]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-PART-NESTED-TABS")


class ReferencesAndGlossary(H.C12TestCase):

    def test_dangling_attachment_reference(self):
        """AC-C12-17: 存在しない attachment_id を参照する B12 は E-REF-DANGLING。"""
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = [
            {"part": "B12", "id": "dl", "data": {"attachment_id": "nope", "label": "台帳をダウンロード"}}
        ]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REF-DANGLING", "/sections/0/parts/0")

    def test_dangling_asset_reference(self):
        """IMG の asset_id dangling も E-REF-DANGLING。"""
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = [
            {"part": "IMG", "id": "img", "data": {"asset_id": "nope", "lightbox": False}}
        ]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REF-DANGLING")

    def test_dangling_diagram_reference(self):
        """DIAGRAM の diagram_id dangling も E-REF-DANGLING。"""
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = [
            {"part": "DIAGRAM", "id": "dg", "data": {"diagram_id": "nope"}}
        ]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REF-DANGLING")

    def test_unused_asset_is_warning(self):
        """N9: 参照されない assets は W-REF-UNUSED (違反ではない)。"""
        cfg = H.valid_config()
        cfg["assets"] = [{
            "id": "shot1", "kind": "image", "src": "img/a.png",
            "alt": "集計画面のスクリーンショット", "caption": None, "role": "screenshot",
        }]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-REF-UNUSED", "/assets/0")

    def test_asset_role_is_required(self):
        """assets[].role は必須で既定値を充填しない (E-ASSET-ROLE-MISSING / C56 の前提)。"""
        cfg = H.valid_config()
        cfg["assets"] = [{
            "id": "shot1", "kind": "image", "src": "img/a.png",
            "alt": "集計画面", "caption": None,
        }]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-ASSET-ROLE-MISSING", "/assets/0")

    def test_asset_alt_is_required(self):
        """alt は a11y ゲートを構成データ段で満たすため必須。"""
        cfg = H.valid_config()
        cfg["assets"] = [{
            "id": "shot1", "kind": "image", "src": "img/a.png",
            "caption": None, "role": "figure",
        }]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_glossary_duplicate_term(self):
        """AC-C12-18: 同一 term の重複は E-GLOSSARY-DUP。"""
        cfg = H.valid_config()
        cfg["glossary"] = [
            {"term": "プロンプト", "plain": "AI へ渡す指示文"},
            {"term": "プロンプト", "plain": "指示のこと"},
        ]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-GLOSSARY-DUP", "/glossary/1")

    def test_glossary_duplicate_across_scopes(self):
        """A11: section スコープの term が document スコープと衝突しても E-GLOSSARY-DUP。"""
        cfg = H.valid_config()
        cfg["sections"][0]["glossary"] = [{"term": "プロンプト", "plain": "指示文"}]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-GLOSSARY-DUP", "/sections/0/glossary/0")

    def test_glossary_duplicate_is_nfc_compared(self):
        """term の一意性は NFC 正規化後に比較する。"""
        cfg = H.valid_config()
        nfc = unicodedata.normalize("NFC", "ガイド")
        nfd = unicodedata.normalize("NFD", "ガイド")
        self.assertNotEqual(nfc, nfd)
        cfg["glossary"] = [
            {"term": nfc, "plain": "手引き"},
            {"term": nfd, "plain": "手引き (分解済み)"},
        ]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-GLOSSARY-DUP")

    def test_glossary_empty_with_no_prior_knowledge_is_warning(self):
        """prior_knowledge_level=none で glossary 0 件は W-GLOSSARY-EMPTY。"""
        cfg = H.valid_config()
        cfg["prior_knowledge_level"] = "none"
        cfg["glossary"] = []
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-GLOSSARY-EMPTY", "/glossary")

    def test_section_glossary_is_not_merged_by_normalize(self):
        """N10: section スコープの glossary を document へマージしない (C20 の復元性)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["glossary"] = [{"term": "トークン", "plain": "文字のかたまり"}]
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual([{"term": "トークン", "plain": "文字のかたまり"}],
                         data["sections"][0]["glossary"])
        self.assertEqual(["プロンプト"], [g["term"] for g in data["glossary"]])


if __name__ == "__main__":
    unittest.main()
