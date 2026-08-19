"""RESOLUTION-R23 (b) — 焼き込み量の確定値と 3 form の allowlist。

**数値の正本は 1 箇所** — `script-brief-C21.json` の `baked_text_discipline`。
本ファイルは `H.blocks_per_image_max()` / `H.chars_per_block_max()` 経由でしか上限を参照せず、
数値リテラルを 1 つも持たない (AC-C21-14 の明記事項)。

固定する性質:
- 上限ちょうどは通り、1 超過で exit2 になる (境界が単一整数であること自体の検査)。
- form は閉じた 3 語。各 form の許容形を外れたものは書けない。
- 句点を含む完全文は焼けない (form 検査で落ちるので exit1 か exit2 のいずれか)。
- metric は条件付き必須で、数字はセクションの構成データに逐語で存在する。
"""

import unittest

import _harness as H
import _r23_support as R

NUMERIC_LEAD = "この節を読むと入力から出力までの工数を94パーセント減らせる筋道が分かる"


def numeric_section(section_id="metrics", **extra):
    """構成データに数字を持つセクション (metric ブロックが条件付き必須になる)。"""
    return H.section(section_id, lead_line=NUMERIC_LEAD, **extra)


def keyword_blocks(count, text="要点"):
    return [R.keyword_block(text) for _ in range(count)]


class BlockCountBoundaryTest(R.R23TestCase):
    """blocks_per_image_max はちょうどが通り 1 超過で落ちる単一整数である。"""

    def test_exactly_the_maximum_number_of_blocks_is_accepted(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(
                tmp, [H.section("intro", baked_text=keyword_blocks(H.blocks_per_image_max()))]
            )
            self.assertNotExit2(ctx, "上限ちょうどのブロック数が拒否されている")

    def test_one_block_over_the_maximum_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [H.section("intro", baked_text=keyword_blocks(H.blocks_per_image_max() + 1))]
            )
            self.assertExit2(ctx, "ブロック数の超過が通っている")

    def test_block_count_violation_stops_before_delegating(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [H.section("intro", baked_text=keyword_blocks(H.blocks_per_image_max() + 1))]
            )
            self.assertStoppedBeforeDelegating(ctx)

    def test_empty_baked_text_is_exit2_for_the_baking_policy(self):
        """既定 policy で焼く文字が 0 件なら『焼き込み画像』になっていない。"""
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", baked_text=[])])
            self.assertExit2(ctx, "焼き込み既定なのに baked_text が空で通っている")

    def test_missing_baked_text_key_is_exit2(self):
        with self.temp() as tmp:
            broken = H.section("intro")
            broken.pop("baked_text")
            ctx = self.run_plan(tmp, [broken])
            self.assertExit2(ctx, "baked_text 欠落が通っている")


class BlockLengthBoundaryTest(R.R23TestCase):
    """chars_per_block_max は書記素単位の単一整数である。"""

    def test_exactly_the_maximum_length_is_accepted(self):
        with self.temp() as tmp:
            text = "あ" * H.chars_per_block_max()
            ctx = self.dry_run_plan(tmp, [H.section("intro", baked_text=[R.keyword_block(text)])])
            self.assertNotExit2(ctx, "上限ちょうどの字数が拒否されている")

    def test_one_character_over_the_maximum_is_exit2(self):
        with self.temp() as tmp:
            text = "あ" * (H.chars_per_block_max() + 1)
            ctx = self.run_plan(tmp, [H.section("intro", baked_text=[R.keyword_block(text)])])
            self.assertExit2(ctx, "字数の超過が通っている")

    def test_length_is_counted_in_graphemes_not_code_points(self):
        """結合文字を 1 字として数える (baked_text_discipline.chars_rationale)。

        書記素数は上限ちょうど、コードポイント数はその 2 倍の文字列を通す。
        コードポイント数で数えている実装はここで落ちる。
        """
        with self.temp() as tmp:
            text = "e\u0301" * H.chars_per_block_max()  # 結合アクセント: 書記素 1 / コードポイント 2
            ctx = self.dry_run_plan(tmp, [H.section("intro", baked_text=[R.keyword_block(text)])])
            self.assertNotExit2(ctx, "コードポイント数で字数を数えている")


class FormAllowlistTest(R.R23TestCase):
    """form は閉じた 3 語で、各 form の許容形を外れたものは表現できない。"""

    def test_unknown_form_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [H.section("intro", baked_text=[R.block_of_form("sentence", "要点語")])]
            )
            self.assertExit2(ctx, "3 語の allowlist 外の form が通っている")

    def test_bare_string_block_is_exit2(self):
        """裸の文字列は {form, text} のタグ付きオブジェクトではない。"""
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", baked_text=["要点語"])])
            self.assertExit2(ctx, "裸の文字列ブロックが通っている")

    def test_block_without_form_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", baked_text=[{"text": "要点語"}])])
            self.assertExit2(ctx, "form 無しのブロックが通っている")

    def test_keyword_with_a_full_stop_is_rejected(self):
        """句点を含む完全文は焼けない (exit1 か exit2 のいずれかで落ちる)。"""
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [H.section("intro", baked_text=[R.keyword_block("手順を守る。")])]
            )
            self.assertIn(
                ctx["proc"].returncode, (1, 2),
                "句点を含む完全文が焼き込みとして通っている:\n" + H.describe(ctx["proc"]),
            )

    def test_keyword_with_a_reading_comma_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [H.section("intro", baked_text=[R.keyword_block("入力、整形")])]
            )
            self.assertExit2(ctx, "読点を含む keyword が通っている")

    def test_keyword_with_an_exclamation_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", baked_text=[R.keyword_block("最短！")])])
            self.assertExit2(ctx, "文末記号を含む keyword が通っている")

    def test_question_ending_with_ka_is_accepted(self):
        with self.temp() as tmp:
            block = R.block_of_form(R.form_named("question"), "どこから始めるか")
            ctx = self.dry_run_plan(tmp, [H.section("intro", baked_text=[block])])
            self.assertNotExit2(ctx, "正しい question 形が拒否されている")

    def test_question_not_ending_with_ka_or_question_mark_is_exit2(self):
        with self.temp() as tmp:
            block = R.block_of_form(R.form_named("question"), "どこから始める")
            ctx = self.run_plan(tmp, [H.section("intro", baked_text=[block])])
            self.assertExit2(ctx, "問いの形を成さない question が通っている")

    def test_question_with_an_interior_full_stop_is_exit2(self):
        with self.temp() as tmp:
            block = R.block_of_form(R.form_named("question"), "始める。次はどこか")
            ctx = self.run_plan(tmp, [H.section("intro", baked_text=[block])])
            self.assertExit2(ctx, "末尾以外に文末記号を持つ question が通っている")


class MetricConditionalRequirementTest(R.R23TestCase):
    """metric は条件付き必須で、数字の出所は構成データに固定される。"""

    def _metric(self, text, **extra):
        return R.block_of_form(R.form_named("metric"), text, **extra)

    def test_numeric_section_without_a_metric_block_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [numeric_section(baked_text=[R.keyword_block("工数削減")])])
            self.assertExit2(ctx, "数値を持つセクションに metric が無くても通っている")

    def test_numeric_section_with_exactly_one_sourced_metric_is_accepted(self):
        with self.temp() as tmp:
            blocks = [self._metric("94パーセント減", emphasis="max"), R.keyword_block("工数削減")]
            ctx = self.dry_run_plan(tmp, [numeric_section(baked_text=blocks)])
            self.assertNotExit2(ctx, "条件を満たす metric が拒否されている")

    def test_two_metric_blocks_are_exit2(self):
        with self.temp() as tmp:
            blocks = [
                self._metric("94パーセント減", emphasis="max"),
                self._metric("94件", emphasis="max"),
            ]
            ctx = self.run_plan(tmp, [numeric_section(baked_text=blocks)])
            self.assertExit2(ctx, "metric が 2 件でも通っている")

    def test_metric_without_max_emphasis_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [numeric_section(baked_text=[self._metric("94パーセント減")])])
            self.assertExit2(ctx, "emphasis=max を持たない metric が通っている")

    def test_metric_number_absent_from_the_section_data_is_exit2(self):
        """E-IMG-METRIC-UNSOURCED: 効果的に見える数字の捏造を落とす。"""
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [numeric_section(baked_text=[self._metric("77パーセント減", emphasis="max")])]
            )
            self.assertExit2(ctx, "構成データに無い数字が焼けてしまう")

    def test_metric_in_a_section_without_numbers_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [H.section("intro", baked_text=[self._metric("94件", emphasis="max")])]
            )
            self.assertExit2(ctx, "数値を持たないセクションで metric が通っている")

    def test_metric_without_any_digit_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [numeric_section(baked_text=[self._metric("大幅削減", emphasis="max")])]
            )
            self.assertExit2(ctx, "数字を含まない metric が通っている")

    def test_metric_with_a_full_stop_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(
                tmp, [numeric_section(baked_text=[self._metric("94減。", emphasis="max")])]
            )
            self.assertExit2(ctx, "文末記号を含む metric が通っている")


class NumericLiteralHygieneTest(H.BridgeTestCase):
    """AC-C21-14: 期待値は brief から導く。本テスト群が数値の第 2 の正本にならないこと。"""

    def test_limits_come_from_the_brief(self):
        discipline = H.baked_text_discipline()
        self.assertIsInstance(discipline["blocks_per_image_max"], int)
        self.assertIsInstance(discipline["chars_per_block_max"], int)
        self.assertEqual(H.blocks_per_image_max(), discipline["blocks_per_image_max"])
        self.assertEqual(H.chars_per_block_max(), discipline["chars_per_block_max"])

    def test_forms_are_a_closed_allowlist_in_the_brief(self):
        self.assertEqual(3, len(H.baked_forms()), "form の allowlist が 3 語でない")

    def test_the_script_does_not_borrow_the_c11_key_name(self):
        """not_c11_text_limits: C11 の text_limits と同じキー名へ寄せない (正本の二重化を防ぐ)。"""
        self.assertNotIn(
            "text_limits", H.read_source(self),
            "C11 の text_limits と同じキー名を使っている (別系統の閾値である)",
        )

    def test_c11_text_limits_are_declared_as_a_separate_system(self):
        self.assertIn("not_c11_text_limits", H.baked_text_discipline())


if __name__ == "__main__":
    unittest.main()
