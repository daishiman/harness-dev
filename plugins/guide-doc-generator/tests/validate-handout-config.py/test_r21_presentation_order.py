# -*- coding: utf-8 -*-
"""R21 C49 presentation_order の決定論導出 (CR-PRESENTATION-ORDER / N4b)。

AC-C12-R21-49 が出所。導出表は none → demo_first / basic → demo_first /
intermediate → explain_first。明示指定は上書きされず 'explicit' として記録される。
"""

import unittest

import _harness as H

DERIVATION = {
    "none": "demo_first",
    "basic": "demo_first",
    "intermediate": "explain_first",
}


class PresentationOrderDerivation(H.C12TestCase):

    def _normalized(self, prior_level, explicit=None, out_name="out.json"):
        cfg = H.valid_config()
        cfg["prior_knowledge_level"] = prior_level
        if explicit is None:
            cfg.pop("presentation_order", None)
        else:
            cfg["presentation_order"] = explicit
        if prior_level == "none":
            cfg["glossary"] = [{"term": "プロンプト", "plain": "AI へ渡す指示文"}]
        out = self.tmp / out_name
        res, _, out = self.normalize(cfg, out=out)
        return res, out

    def test_derivation_table(self):
        """AC-C12-R21-49: 3 段それぞれからの導出値と source の記録。"""
        for level, expected in DERIVATION.items():
            with self.subTest(prior_knowledge_level=level):
                res, out = self._normalized(level, out_name="out-%s.json" % level)
                self.assert_exit(res, 0)
                data = self.read_out(out)
                self.assertEqual(expected, data["presentation_order"])
                self.assertEqual(
                    "derived-from-prior-knowledge",
                    data["provenance"]["presentation_order_source"],
                )

    def test_basic_is_demo_first(self):
        """basic の境界を demo_first 側へ倒す (R21 の一次観測)。"""
        res, out = self._normalized("basic")
        self.assert_exit(res, 0)
        self.assertEqual("demo_first", self.read_out(out)["presentation_order"])

    def test_intermediate_is_explain_first(self):
        """境界は intermediate に置く。"""
        res, out = self._normalized("intermediate")
        self.assert_exit(res, 0)
        self.assertEqual("explain_first", self.read_out(out)["presentation_order"])

    def test_null_value_is_treated_as_absent(self):
        """N4b: null も導出の経路に入る。"""
        cfg = H.valid_config()
        cfg["presentation_order"] = None
        cfg["prior_knowledge_level"] = "intermediate"
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual("explain_first", data["presentation_order"])
        self.assertEqual("derived-from-prior-knowledge", data["provenance"]["presentation_order_source"])

    def test_explicit_value_is_not_overwritten(self):
        """AC-C12-R21-49: 明示指定は導出に負けない (none + explain_first がそのまま残る)。"""
        res, out = self._normalized("none", explicit="explain_first")
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual("explain_first", data["presentation_order"])
        self.assertEqual("explicit", data["provenance"]["presentation_order_source"])

    def test_explicit_matching_derivation_is_still_explicit(self):
        """導出結果と同値を明示した場合も source は explicit (由来が判別できること)。"""
        res, out = self._normalized("basic", explicit="demo_first")
        self.assert_exit(res, 0)
        self.assertEqual("explicit", self.read_out(out)["provenance"]["presentation_order_source"])

    def test_invalid_enum_value(self):
        """列挙外は E-PRESENTATION-ORDER。"""
        cfg = H.valid_config()
        cfg["presentation_order"] = "demo-first"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-PRESENTATION-ORDER", "/presentation_order")

    def test_derivation_is_deterministic_across_runs(self):
        """AC-C12-R21-49: 同一入力を何度実行しても同じ値 (バイト一致)。"""
        cfg = H.valid_config()
        del cfg["presentation_order"]
        out1 = self.tmp / "d1.json"
        out2 = self.tmp / "d2.json"
        r1, path, _ = self.normalize(cfg, out=out1)
        r2 = self.run_cli("--config", path, "--normalize", "--out", out2)
        self.assert_exit(r1, 0)
        self.assert_exit(r2, 0)
        self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_validation_without_normalize_does_not_require_the_field(self):
        """presentation_order は normalize が導出するフィールドなので、未指定の検証は落ちない。"""
        cfg = H.valid_config()
        del cfg["presentation_order"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-PRESENTATION-ORDER")


if __name__ == "__main__":
    unittest.main()
