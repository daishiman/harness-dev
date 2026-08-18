"""R21 (goal-spec C46-C59) のうち C11 が owner / 描画責務を持つ分。

RESOLUTION-R21.md の割り当て表で C11 に紐づくのは、
- C52 テーマトークン text_limits のスキーマ owner (切り詰めは C11 側で行わない)
- C57 の描画で片方だけを出す経路が無いこと (AC-C11-R21-b)
- R21 追加属性の焼き込み (AC-C11-R21-a) / B17 の描画 (C53)
判定 (合否を決める側) は C12 / C16 / C18 / C22 が持ち、C11 は判定しない。
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _harness as H

# C11 theme_token_schema_ownership が定義する text_limits ブロックのキー。
# 「config/ が何本あるか」という導出値ではなく、この住所の不変条件を検査する。
TEXT_LIMIT_KEYS = frozenset(
    {"text_limits", "block_body_max_chars", "block_body_max_chars_by_detail_level"}
)


def _keys_of(node):
    """JSON 木に現れる全キー名。"""
    keys = set()
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(key)
            keys |= _keys_of(value)
    elif isinstance(node, list):
        for value in node:
            keys |= _keys_of(value)
    return keys


def r21_config():
    """AC-C11-R21-a の入力: R21 の全フィールドを埋めた正規化済み構成データ。"""
    handson = copy.deepcopy(H.BLOCK_FIXTURES["handson"])
    image = copy.deepcopy(H.BLOCK_FIXTURES["image"])
    features = copy.deepcopy(H.BLOCK_FIXTURES["features"])
    features["slot"] = "feature"
    outcome = copy.deepcopy(H.BLOCK_FIXTURES["text"])
    outcome["id"] = "blk-outcome"
    outcome["slot"] = "outcome"
    breakdown = copy.deepcopy(H.BLOCK_FIXTURES["steps"])
    breakdown["slot"] = "breakdown"

    main_section = H.base_section(
        1,
        blocks=[image, handson],
        section_kind="handson",
        attainment_step="operable",
        ties_to="target_task:tt1",
        role="main",
    )
    capability = H.base_section(
        2,
        id="s2",
        blocks=[outcome, breakdown, features],
        section_kind="capability-explainer",
        attainment_step="reproducible",
        ties_to="focus_theme:0",
        role="main",
    )
    logistics = H.base_section(
        3,
        id="s3",
        blocks=[copy.deepcopy(H.BLOCK_FIXTURES["text"])],
        section_kind="logistics",
        attainment_step="overview",
        ties_to="goal",
        role="appendix",
    )
    return H.base_config(
        sections=[main_section, capability, logistics],
        focus_theme=["手順をそろえる", "自分で再現する"],
        target_tasks=[
            {"id": "tt1", "label": "週次レポートを自分で作る"},
            {"id": "tt2", "label": "つまずいたときに自分で調べる"},
        ],
        attainment_level="reproducible",
        must_remember=["最初に権限を確認する", "保存先を間違えない"],
        no_need_to_remember=["画面の細かい配置はこの資料を見返せばよい"],
        presentation_order="demo_first",
        provenance={"presentation_order_source": "explicit"},
    )


class R21AttributeTest(unittest.TestCase):
    """AC-C11-R21-a: R21 追加属性が定義どおりの要素へ全て付く。"""

    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls.config = r21_config()
        cls.result, cls.html, _ = H.render_html(cls._td.name, cls.config)
        if cls.result.returncode != 0:
            raise AssertionError("R21 fixture の生成に失敗: %s" % cls.result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()

    def html_element(self):
        for el in H.parse(self.html):
            if el.tag == "html":
                return el
        raise AssertionError("<html> 要素が無い")

    def test_presentation_order_and_source_on_html(self):
        """C49/C50: C12 が確定させた値をそのまま出す (C11 は導出しない)。"""
        el = self.html_element()
        self.assertEqual("demo_first", el.get("data-hb-presentation-order"))
        self.assertEqual("explicit", el.get("data-hb-presentation-order-source"))

    def test_presentation_order_is_not_derived_by_the_renderer(self):
        """導出点は C12 の CR-PRESENTATION-ORDER のみ。C11 は prior_knowledge から導かない。"""
        cfg = r21_config()
        cfg["prior_knowledge_level"] = "intermediate"  # 導出すれば explain_first になる値
        cfg["presentation_order"] = "demo_first"
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        el = [e for e in H.parse(html_text) if e.tag == "html"][0]
        self.assertEqual("demo_first", el.get("data-hb-presentation-order"))

    def test_section_role_and_ties_to_and_attainment_step(self):
        """C48/C54: section の role / ties_to / attainment_step を素値で出す。"""
        sections = [el for el in H.parse(self.html) if el.tag == "section"]
        self.assertEqual(len(self.config["sections"]), len(sections))
        for el, src in zip(sections, self.config["sections"]):
            self.assertEqual(src["role"], el.get("data-hb-section-role"))
            self.assertEqual(src["ties_to"], el.get("data-hb-ties-to"))
            self.assertEqual(src["attainment_step"], el.get("data-hb-attainment-step"))

    def test_slot_is_emitted_only_for_capability_explainer_parts(self):
        """C51: slot が null の部品には付けない。"""
        slots = H.elements_with(self.html, "data-hb-slot")
        self.assertEqual(
            ["outcome", "breakdown", "feature"], [el.get("data-hb-slot") for el in slots]
        )

    def test_asset_role_is_emitted(self):
        """C56: assets[].role の素値を data-hb-asset-role として出す。"""
        roles = {el.get("data-hb-asset-role") for el in H.elements_with(self.html, "data-hb-asset-role")}
        self.assertEqual({"screenshot"}, roles)

    def test_text_limit_is_baked_on_html(self):
        """C52: 採用テーマの text_limits.block_body_max_chars を <html> へ 1 値だけ焼く。"""
        value = self.html_element().get("data-hb-text-limit")
        self.assertIsNotNone(value, "data-hb-text-limit が無い")
        self.assertRegex(value, r"^\d+$")

    def test_r21_fields_are_rendered(self):
        """C47/C58/C54/C57: 追加された描画必須フィールドが data-hb-field で出る。"""
        for field in ("focus_theme", "target_task", "attainment_level",
                      "must_remember", "no_need_to_remember"):
            with self.subTest(field=field):
                self.assertTrue(H.field_elements(self.html, field),
                                "data-hb-field=%s が描画されていない" % field)

    def test_focus_theme_and_target_task_render_every_entry(self):
        self.assertEqual(len(self.config["focus_theme"]), len(H.field_elements(self.html, "focus_theme")))
        self.assertEqual(len(self.config["target_tasks"]), len(H.field_elements(self.html, "target_task")))

    def test_handson_row_renders_the_triple(self):
        """C53: B17 は 操作 / 期待される結果 / つまずいたときの見どころ の 3 つ組を 1 行で並べる。"""
        roots = H.part_elements(self.html, "B17")
        self.assertTrue(roots, "B17 が描画されていない")
        text = roots[0].text
        step = self.config["sections"][0]["blocks"][1]["steps"][0]
        for key in ("operation", "expected", "stuck_hint"):
            self.assertIn(step[key], text, "B17 の %s が 1 行に出ていない" % key)


class RememberPairTest(unittest.TestCase):
    """AC-C11-R21-b (C57): 片方だけを出す経路が存在しないことを固定する。"""

    def test_both_remember_fields_are_always_rendered_together(self):
        cfg = r21_config()
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertTrue(H.field_elements(html_text, "must_remember"))
        self.assertTrue(H.field_elements(html_text, "no_need_to_remember"))

    def test_regression_guard_detects_a_renderer_that_drops_one_side(self):
        """回帰の見張り: no_need_to_remember を出さない改変レンダラでは a が FAIL する。

        改変は tmp へ複製した写しに対して行い、実装本体には触れない。
        """
        H.require_script()
        cfg = r21_config()
        with tempfile.TemporaryDirectory() as td:
            clone_root = Path(td) / "plugin"
            shutil.copytree(H.PLUGIN_ROOT, clone_root, symlinks=True)
            script = clone_root / "scripts" / "render-handout.py"
            src = script.read_text(encoding="utf-8")
            self.assertIn("no_need_to_remember", src)
            script.write_text(src.replace("no_need_to_remember", "no_need_to_remember_DISABLED"),
                              encoding="utf-8")
            cfg_path = H.write_config(Path(td) / "config.json", cfg)
            out = Path(td) / "handout.html"
            proc = subprocess.run(
                [sys.executable, str(script), "--config", str(cfg_path), "--out", str(out)],
                capture_output=True, text=True,
                env={**os.environ, "HB_ROOT": str(clone_root)},
            )
            broken_html = out.read_text(encoding="utf-8") if out.is_file() else ""
        self.assertFalse(
            proc.returncode == 0 and bool(H.field_elements(broken_html, "no_need_to_remember")),
            "片方を落とした改変が検出されない = 対の描画が検査できていない",
        )


class TextLimitNoTruncationTest(unittest.TestCase):
    """AC-C11-R21-c (C52): C11 は本文を切り詰めない (切り詰めると C20 の round-trip が壊れる)。"""

    def test_body_over_the_limit_is_rendered_verbatim(self):
        long_body = "あ" * 1200
        block = {"id": "blk-long", "type": "text", "body": long_body}
        cfg = H.config_with_block(block)
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertIn(long_body, html_text, "本文を切り詰めてはならない")
        self.assertNotIn("…", html_text)

    def test_renderer_does_not_fold_into_accordion(self):
        """折り畳み (B10 生成) の実行者は C12 --normalize であって C11 ではない。"""
        block = {"id": "blk-long", "type": "text", "body": "い" * 1200}
        cfg = H.config_with_block(block)
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual([], H.part_elements(html_text, "B10"),
                         "C11 が勝手に B10 を作ってはならない")


class ThemeTokenSchemaTest(unittest.TestCase):
    """theme_token_schema_ownership (C52): text_limits ブロックのスキーマ owner は C11。"""

    def test_theme_tokens_declare_text_limits(self):
        tokens = H.PLUGIN_ROOT / "assets" / "tokens" / "pop.json"
        if not tokens.is_file():
            raise AssertionError("テーマトークン正本が未実装: %s" % tokens)
        data = json.loads(tokens.read_text(encoding="utf-8"))
        self.assertIn("text_limits", data)
        self.assertIsInstance(data["text_limits"].get("block_body_max_chars"), int)

    def test_no_config_file_added_for_text_limits(self):
        """not_a_new_config_file: text_limits のために config/ を増やさない。

        本検査はかつて config/ の**ファイル名リスト**を固定していたが、それは導出値
        (config が何本あるか) を契約に書いた形であり、C19 に従って別の目的で
        `handout-output.json` が増えた時点で偽陽性になった (RESOLUTION-P04-x-05
        『契約に書くのは不変条件であって導出値ではない』)。
        C11 の `not_a_new_config_file` が守らせたい不変条件は本数ではなく
        **text_limits の住所が config/ ではなくテーマトークンであること**なので、
        その述語をそのまま検査する。
        """
        config_dir = H.PLUGIN_ROOT / "config"
        if not config_dir.is_dir():
            raise AssertionError("config/ が未実装: %s" % config_dir)
        offenders = []
        for path in sorted(config_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in _keys_of(data):
                if key in TEXT_LIMIT_KEYS:
                    offenders.append("%s:%s" % (path.name, key))
        self.assertEqual(
            [], offenders,
            "text_limits 系の値が config/ 側に住んでいる (正本は assets/tokens/<theme>.json)",
        )

    def test_text_limits_live_in_the_theme_tokens(self):
        """住所の正本側。config/ を増やさない代わりにテーマトークンが持つ。"""
        tokens_dir = H.PLUGIN_ROOT / "assets" / "tokens"
        if not tokens_dir.is_dir():
            raise AssertionError("テーマトークンのディレクトリが未実装: %s" % tokens_dir)
        holders = [
            path.name
            for path in sorted(tokens_dir.glob("*.json"))
            if "text_limits" in _keys_of(json.loads(path.read_text(encoding="utf-8")))
        ]
        self.assertTrue(holders, "text_limits を持つテーマトークンが 1 件も無い: %s" % tokens_dir)


if __name__ == "__main__":
    unittest.main()
