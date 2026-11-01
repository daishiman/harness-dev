"""RESOLUTION-R23 (a) — textPolicy 既定は baked-with-overlay。overlayText が常に正本。

固定する性質は 3 つ。
1. 何も指定しなければ焼き込む (既定は『何も言わなかったときに正しい方』へ置く)。
2. `overlay-only` は `text_policy_reason` との**対**でしか選べない。片方だけは exit2。
3. 印刷 (R15) の安全弁は「焼かないこと」ではなく「正本が画像の外にあること」なので、
   `overlayText` は両 policy で必須・非空。

対応する正本: RESOLUTION-R23 (a) / script-brief-C21 algorithm[7] / algorithm 8b (a) /
acceptance_checks AC-C21-12 / AC-C21-13。
"""

import re
import unittest

import _harness as H
import _r23_support as R


class DefaultPolicyTest(R.R23TestCase):
    """AC-C21-12: text_policy を書かない計画は焼き込み側の既定になる。"""

    def test_default_text_policy_is_baked_with_overlay(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, [H.section("intro"), H.section("build")])
            for _, slide in self.slides(ctx):
                self.assertEqual(
                    R.DEFAULT_TEXT_POLICY, slide.get("textPolicy"),
                    "既定が焼き込み側でない:\n" + H.describe(ctx["proc"]),
                )

    def test_default_plan_carries_non_empty_baked_text(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, [H.section("intro"), H.section("build")])
            for _, slide in self.slides(ctx):
                self.assertTrue(slide.get("bakedText"), "bakedText が空:\n" + H.describe(ctx["proc"]))

    def test_baked_text_is_the_texts_in_order_without_form_metadata(self):
        """委譲先の入力契約は文字列配列のまま。form / emphasis は handout 側の検査用メタ。"""
        blocks = [R.keyword_block("入力"), R.keyword_block("組み立て"), R.keyword_block("印刷")]
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, [H.section("intro", baked_text=blocks), H.section("build")])
            texts = [b["text"] for b in blocks]
            slides = self.slides(ctx)
            self.assertIn(
                texts, [s.get("bakedText") for _, s in slides],
                "bakedText が baked_text[].text の順並びになっていない:\n" + H.describe(ctx["proc"]),
            )
            for _, slide in slides:
                for entry in slide.get("bakedText") or []:
                    self.assertIsInstance(entry, str, "bakedText に構造体が漏れている")

    def test_overlay_only_is_not_hard_coded_in_the_generated_plan(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, [H.section("intro"), H.section("build")])
            for _, slide in self.slides(ctx):
                self.assertNotEqual(R.OVERLAY_ONLY_POLICY, slide.get("textPolicy"))

    def test_overlay_only_is_not_pinned_in_the_source(self):
        """AC-C21-12: script 本文に textPolicy の overlay-only 固定が残っていない。"""
        source = H.read_source(self)
        self.assertIsNone(
            re.search(
                r"""textPolicy["']?\s*[:=]\s*["']{}""".format(re.escape(R.OVERLAY_ONLY_POLICY)),
                source,
            ),
            "textPolicy の overlay-only 固定がソースに残っている (R23 (a) で撤回済み)",
        )


class OverlayTextIsMandatoryTest(R.R23TestCase):
    """AC-C21-13: overlayText の欠落は exit2 (E-IMG-OVERLAY-MISSING)。"""

    def test_empty_overlay_text_list_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", overlay_text=[])])
            self.assertExit2(ctx, "overlayText が空なのに通っている")

    def test_missing_overlay_text_key_is_exit2(self):
        with self.temp() as tmp:
            broken = H.section("intro")
            broken.pop("overlay_text")
            ctx = self.run_plan(tmp, [broken])
            self.assertExit2(ctx, "overlayText 欠落が通っている")

    def test_overlay_text_missing_stops_before_delegating(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", overlay_text=[])])
            self.assertStoppedBeforeDelegating(ctx)

    def test_overlay_text_is_required_even_for_overlay_only(self):
        """焼かない policy でも正本の外部化は必須 (安全弁の実体は overlayText 側にある)。"""
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp,
                [H.section(
                    "intro",
                    overlay_text=[],
                    text_policy=R.OVERLAY_ONLY_POLICY,
                    text_policy_reason="料金表の値が四半期ごとに変わるため",
                )],
            )
            self.assertExit2(ctx, "overlay-only なら overlayText 不要という扱いになっている")


class OverlayOnlyRequiresReasonTest(R.R23TestCase):
    """AC-C21-13: overlay-only は理由との対指定でのみ選べる (E-IMG-POLICY-REASON-MISSING)。"""

    def test_overlay_only_without_reason_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", text_policy=R.OVERLAY_ONLY_POLICY)])
            self.assertExit2(ctx, "理由なしで焼き込みを外せてしまう")

    def test_overlay_only_with_empty_reason_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp,
                [H.section("intro", text_policy=R.OVERLAY_ONLY_POLICY, text_policy_reason="")],
            )
            self.assertExit2(ctx, "空文字の理由が通っている")

    def test_reason_without_overlay_only_is_exit2(self):
        """片方だけの指定は exit2 (対でしか意味を持たない)。"""
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", text_policy_reason="値が変わるため")])
            self.assertExit2(ctx, "policy 指定なしの理由だけが通っている")

    def test_unknown_text_policy_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", text_policy="no-such-policy")])
            self.assertExit2(ctx, "未知の text_policy が通っている")

    def test_overlay_only_with_reason_is_accepted(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(
                tmp,
                [H.section(
                    "intro",
                    text_policy=R.OVERLAY_ONLY_POLICY,
                    text_policy_reason="料金表の値が四半期ごとに変わるため",
                )],
            )
            self.assertNotExit2(ctx, "対指定の overlay-only が拒否されている")

    def test_overlay_only_reaches_the_delegate_as_overlay_only(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(
                tmp,
                [H.section(
                    "intro",
                    text_policy=R.OVERLAY_ONLY_POLICY,
                    text_policy_reason="料金表の値が四半期ごとに変わるため",
                )],
            )
            for _, slide in self.slides(ctx):
                self.assertEqual(R.OVERLAY_ONLY_POLICY, slide.get("textPolicy"), H.describe(ctx["proc"]))

    def test_overlay_only_slide_has_no_baked_text(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(
                tmp,
                [H.section(
                    "intro",
                    text_policy=R.OVERLAY_ONLY_POLICY,
                    text_policy_reason="料金表の値が四半期ごとに変わるため",
                )],
            )
            for _, slide in self.slides(ctx):
                self.assertFalse(
                    slide.get("bakedText"),
                    "overlay-only なのに焼き文字が乗っている:\n" + H.describe(ctx["proc"]),
                )


if __name__ == "__main__":
    unittest.main()
