# -*- coding: utf-8 -*-
"""部品 id 語彙の単一正本 (RESOLUTION-P03.md Y-05)。

確定事項:
- 部品 id 集合の正本は config/handout-parts.json (owner: C11) ただ 1 箇所。
- C20 が保持してよいのは「その部品種別をクラス名から見分ける根拠」だけで、
  「どの部品 id が存在するか」も「id とクラス名の対応そのもの」も保持しない。
- 照合表の鍵は部品 id ではなくカタログの data_block_type であり、
  「部品 id → クラス名」はカタログとの join で導出する
  (裁定: schemas/PART-CLASS-MAP-RESOLUTION.md)。
- 照合表にあってカタログのどの部品も要求していない block type、および
  カタログにあって鍵が無い部品は、起動時の自己整合検査で列挙して報告する (双方向)。
- C12 のスキーマを id 語彙の出所として参照しない。

第二の正本が生えていないことは挙動テストだけでは落とせないので、
モジュール実体 (照合表そのもの) とソースの両面から固定する。
"""

import importlib.util
import json
import re
import unittest

import _harness as H


class CatalogIsTheOnlyVocabulary(H.C20TestCase):

    def _module(self):
        """build_target をモジュールとして読み込む (main を実行させない)。"""
        path = self.script_path()
        self.assertTrue(path.exists(), "実装が存在しない: %s" % path)
        spec = importlib.util.spec_from_file_location("hb_extract_under_test", path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except BaseException as exc:      # SystemExit も含めて失敗として報告する
            self.fail("import しただけで例外/終了した (main を副作用なしに import できない): %r" % exc)
        return module

    def _class_map(self, module):
        """『部品 id → クラス名』の対応表をモジュールから 1 つだけ見つける。

        名前ではなく形で探す (テストが実装の変数名を固定しないため)。
        現在この表はカタログとの join の導出値だが、_class_map は由来を問わない。
        「部品 id を鍵とする表が 2 つ以上ある = 第二の名簿」の検出はここが担う。
        """
        candidates = []
        for name in dir(module):
            if name.startswith("__"):
                continue
            value = getattr(module, name)
            if isinstance(value, dict) and value and all(
                    isinstance(k, str) and H.PART_ID_RE.match(k) for k in value):
                candidates.append((name, value))
        self.assertTrue(
            candidates,
            "部品 id を鍵とする照合表がモジュールに無い (heuristic 経路の class_map)")
        self.assertEqual(
            1, len(candidates),
            "部品 id を鍵とする表が複数ある (第二の正本の疑い): %r" % [n for n, _ in candidates])
        return candidates[0][1]

    # ---- 照合表とカタログの関係 -------------------------------------------

    def test_class_map_keys_are_all_in_the_catalog(self):
        """カタログに無い id を鍵に持つ行を残さない (Y-05 の片方向)。"""
        keys = set(self._class_map(self._module()))
        unknown = sorted(keys - self.catalog_ids())
        self.assertEqual([], unknown, "カタログに無い部品 id を鍵に持つ行がある: %r" % unknown)

    def test_class_map_does_not_declare_part_existence(self):
        """照合表は『存在する id の名簿』ではない。値はクラス名 (文字列/文字列列) である。"""
        for part_id, value in self._class_map(self._module()).items():
            if isinstance(value, (list, tuple, set)):
                self.assertTrue(all(isinstance(v, str) for v in value),
                                "%s の値がクラス名でない: %r" % (part_id, value))
            else:
                self.assertIsInstance(value, str, "%s の値がクラス名でない: %r" % (part_id, value))

    def test_no_part_id_literal_outside_the_catalog(self):
        """ソース中の部品 id リテラルはすべてカタログ (と非部品マーカー) に載っている。"""
        catalog = self.parts_catalog()
        allowed = self.catalog_ids() | set(
            catalog.get("non_part_structure_markers", {}).get("values", []))
        found = set(re.findall(r"['\"](B\d{2}|IMG|DIAGRAM|TEXT)['\"]", self.script_source()))
        self.assertEqual(set(), found - allowed,
                         "カタログに無い部品 id が script に書かれている: %r" % sorted(found - allowed))

    def test_document_scope_part_ids_are_not_hardcoded(self):
        """chrome の読み飛ばしは data-hb-generated とクラス名で行う (id 名指しではない)。"""
        document_scope = {p["id"] for p in self.parts_catalog()["parts"]
                          if p.get("section_scope") == "document"}
        literals = set(re.findall(r"['\"]([A-Z0-9]+)['\"]", self.script_source()))
        self.assertEqual(set(), literals & document_scope,
                         "document スコープ部品の id を script が名指ししている")

    def test_catalog_path_is_read(self):
        """id 集合はカタログから読む (script 内に持たない)。"""
        source = self.script_source()
        self.assertIn("handout-parts.json", source,
                      "部品カタログ (config/handout-parts.json) を読んでいない")

    def test_c12_is_not_used_as_the_id_vocabulary_source(self):
        """C12 は正規化関数の共有先であって id 語彙の出所ではない。"""
        source = self.script_source()
        for token in ("part_data_schema", "part_catalog"):
            self.assertNotIn(token, source,
                             "C12 のスキーマを id 語彙の出所として参照している: %s" % token)

    # ---- 起動時の自己整合検査 (双方向) ------------------------------------

    def _catalog_with(self, add=None, remove=None):
        catalog = self.parts_catalog()
        if remove:
            catalog["parts"] = [p for p in catalog["parts"] if p["id"] not in remove]
        for part_id in (add or []):
            catalog["parts"].append({
                "id": part_id, "name_ja": "検査用", "kind": "content",
                "section_scope": "in-section", "data_block_type": "test",
                "since": "plan", "source": "test fixture",
            })
        self.write_parts_catalog(catalog)
        return catalog

    def test_catalog_entry_without_class_map_row_is_reported(self):
        """カタログにあって照合表に鍵が無い部品を列挙して報告する。

        この向きは部品がカタログに実在するので部品 id で名指せる。
        こちらも drift 検査が鳴ったことを診断コードまで見て固定する。
        """
        self._catalog_with(add=["B98"])
        res, _ = self.extract()
        self.assert_diag(res, self._module().W_CATALOG_DRIFT, "B98")

    def test_class_map_row_without_catalog_entry_is_reported(self):
        """照合表にあってカタログのどの部品も要求していない行を報告する。

        照合表の鍵は data_block_type なので、カタログから部品を消すと「その部品が
        使っていた block type の行」が孤児になる。消えた部品の id はもうどこにも
        残っていないため、報告は block type 名で行う。

        drift 検査そのものが効いていることを固定するため、診断コードまで見る。
        E-EXTRACT-UNRECOVERABLE (未知の data-hb-part を復元しない検査) は別件で
        あり、そちらが鳴っていても本検査の代わりにはならない。
        """
        module = self._module()
        removed = sorted(set(self._class_map(module)))[0]
        block_types = {p["id"]: p.get("data_block_type")
                       for p in self.parts_catalog()["parts"]}
        orphaned = block_types[removed]
        self.assertIn(orphaned, module.BLOCK_TYPE_CLASS_MAP,
                      "前提が崩れている: %s の block type が照合表に無い" % removed)
        self._catalog_with(remove={removed})
        res, _ = self.extract()
        self.assert_diag(res, module.W_CATALOG_DRIFT, orphaned)

    def test_self_check_report_uses_diagnostic_code_lines(self):
        """報告は stderr の 1 行 1 件・先頭に診断コード (stderr 契約と同じ形)。"""
        self._catalog_with(add=["B98"])
        res, _ = self.extract()
        lines = [l for l in res.stderr.splitlines() if "B98" in l]
        self.assertTrue(lines, "B98 に関する報告行が無い")
        for line in lines:
            self.assertRegex(line, r"^[EW]-[A-Z0-9-]+ ",
                             "先頭が診断コードでない: %r" % line)

    def test_self_check_is_quiet_when_catalog_and_table_agree(self):
        """過不足が無ければ自己整合検査は何も言わない (常時ノイズを出さない)。"""
        module = self._module()
        catalog = self.parts_catalog()
        keys = set(self._class_map(module))
        catalog["parts"] = [p for p in catalog["parts"]
                            if p.get("section_scope") != "in-section" or p["id"] in keys]
        self.write_parts_catalog(catalog)
        # カタログを絞ったので、照合表に載っている部品だけで組んだ HTML を使う
        res, _ = self.extract(H.full_html(sections=[H.section_html(
            "intro", parts=H.part_b03() + H.part_text() + H.part_b11())]))
        self.assert_exit(res, 0)
        self.assertEqual("", res.stderr.strip(),
                         "整合しているのに自己整合検査が何か言っている: %r" % res.stderr)

    # ---- カタログ駆動であることの挙動側の証拠 ------------------------------

    def test_unknown_part_id_in_html_is_not_silently_accepted(self):
        """カタログに無い data-hb-part 値は復元せず報告する。"""
        part = '  <div data-hb-part="B97" data-hb-part-id="x1">未知の部品</div>\n'
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=part)]))
        self.assert_exit(res, 1)
        self.assert_diag(res, H.E_UNRECOVERABLE, "B97")

    def test_part_added_to_catalog_is_recognised_without_touching_the_script(self):
        """カタログへ部品を足せば script 無改修で部品として復元される。"""
        self._catalog_with(add=["B97"])
        part = '  <div data-hb-part="B97" data-hb-part-id="x1">新しい部品</div>\n'
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=part)]))
        parts = self.read_out()["sections"][0]["parts"]
        self.assertEqual(["B97"], [p["part"] for p in parts],
                         "カタログへ足した部品が認識されていない")

    def test_part_removed_from_catalog_stops_being_recognised(self):
        """逆向き: カタログから消せば認識されなくなる (id 集合を自前に持っていない証拠)。"""
        self._catalog_with(remove={"B16"})
        res, _ = self.extract(H.full_html(sections=[
            H.section_html("intro", parts=H.part_b16())]))
        self.assert_exit(res, 1)
        self.assert_diag(res, H.E_UNRECOVERABLE, "B16")

    def test_missing_catalog_is_exit2_not_a_silent_fallback(self):
        """カタログが無いときに内蔵の名簿へ退避しない (第二の正本を作らない)。"""
        path = self.parts_catalog_path()
        if path.exists():
            path.unlink()
        res, _ = self.extract()
        self.assert_exit(res, 2)


class PlanCatalogIsTheReference(H.C20TestCase):
    """テスト側が参照している正本が plan と実装で食い違っていないことの見張り。"""

    def test_plan_catalog_exists(self):
        self.assertTrue(H.PLAN_PARTS_CATALOG.exists(),
                        "plan 側の部品カタログ正本が無い: %s" % H.PLAN_PARTS_CATALOG)

    def test_built_catalog_matches_plan_catalog_ids(self):
        built = self.parts_catalog_path()
        if not built.exists():
            self.skipTest("実装側カタログは P05 で生成される")
        plan_ids = {p["id"] for p in json.loads(
            H.PLAN_PARTS_CATALOG.read_text(encoding="utf-8"))["parts"]}
        built_ids = {p["id"] for p in json.loads(built.read_text(encoding="utf-8"))["parts"]}
        self.assertEqual(plan_ids, built_ids)


if __name__ == "__main__":
    unittest.main()
