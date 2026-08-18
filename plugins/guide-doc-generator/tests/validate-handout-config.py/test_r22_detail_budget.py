# -*- coding: utf-8 -*-
"""R22 C63 (適用側) — CR-DETAIL-TEXT-BUDGET。

RESOLUTION-R22.md の責務表で C63 は「C11 (数値の正本) / C12 (適用)」であり、
本ファイルは適用側だけを固定する (数値の正本とレンダリングの検査は
tests/render-handout.py/test_r22_detail_attributes.py)。

規則 (script-brief-C12.json r22_granularity_constraints.detail_text_budget):
- CR-TEXT-FOLD の折り畳み上限を detail_level ごとにテーマトークン
  text_limits.block_body_max_chars_by_detail_level から引く。
- この script は上限の数値リテラルを 1 つも持たない。
- 該当キーが無いテーマでは block_body_max_chars を全水準へ適用する (fail-soft)。
- 折り畳み自体は全水準で行い、detailed のみ生成する B10 を open=true にする
  (script-brief-C11.json added_block_r22_values.fold_behavior_at_detailed)。

上限の数値はテーマトークン (無ければ C11 のブリーフ) から読み、テストソースへ
書かない。
"""

import json
import re
import unittest

import _harness as H

DETAIL_LEVELS = ("overview", "standard", "detailed")

BRIEFS_DIR = H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs"
C11_BRIEF = BRIEFS_DIR / "script-brief-C11.json"

BY_DETAIL_KEY = "block_body_max_chars_by_detail_level"


def long_body(total_chars, sentence_len=40):
    """文末 (。) を含む決定論的な長文 (test_r21_text_fold.py と同じ作り方)。"""
    out = []
    n = 0
    while n < total_chars:
        out.append("あ" * (sentence_len - 1) + "。")
        n += sentence_len
    return "".join(out)[:total_chars]


def text_config(body, detail_level):
    cfg = H.valid_config(detail_level=detail_level)
    cfg["sections"] = [H.section("intro", parts=[H.text_part("intro-t1", body)])]
    return cfg


class DetailBudgetTestCase(H.C12TestCase):
    """テーマトークンを水準別上限つきで用意する足場。"""

    def brief_limits(self):
        if not C11_BRIEF.is_file():
            self.fail("水準別上限の値が読める正本が無い: %s" % C11_BRIEF)
        data = json.loads(C11_BRIEF.read_text(encoding="utf-8"))
        values = (data.get("theme_token_schema_ownership") or {}).get("added_block_r22_values")
        if not isinstance(values, dict):
            self.fail("script-brief-C11.json に added_block_r22_values が無い")
        limits = {lv: values.get(lv) for lv in DETAIL_LEVELS}
        for level, value in limits.items():
            if not isinstance(value, int):
                self.fail("added_block_r22_values.%s が整数でない: %r" % (level, value))
        return limits

    def theme_name(self):
        tokens_dir = self.root / H.TOKENS_RELDIR
        self.assertTrue(tokens_dir.exists(), "テーマトークン置き場が無い: %s" % tokens_dir)
        names = sorted(p.stem for p in tokens_dir.glob("*.json"))
        self.assertTrue(names, "テーマトークンが 1 件も無い: %s" % tokens_dir)
        return names[0]

    def token_limits(self, theme):
        """テーマトークンが持つ水準別上限 (無ければ失敗させる)。"""
        path = self.root / H.TOKENS_RELDIR / ("%s.json" % theme)
        tokens = json.loads(path.read_text(encoding="utf-8"))
        limits = (tokens.get("text_limits") or {}).get(BY_DETAIL_KEY)
        self.assertIsInstance(
            limits, dict, "text_limits.%s がテーマトークンに無い: %s" % (BY_DETAIL_KEY, path)
        )
        for level in DETAIL_LEVELS:
            self.assertIsInstance(
                limits.get(level), int, "%s.%s が整数でない" % (BY_DETAIL_KEY, level)
            )
        return limits

    def write_tokens(self, theme, mutate):
        path = self.root / H.TOKENS_RELDIR / ("%s.json" % theme)
        tokens = json.loads(path.read_text(encoding="utf-8"))
        mutate(tokens)
        path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")

    def normalized_parts(self, body, detail_level, theme, name):
        cfg = text_config(body, detail_level)
        cfg["theme"] = theme
        out = self.tmp / name
        res, _, out = self.normalize(cfg, out=out)
        self.assert_exit(res, 0)
        return self.read_out(out)


class LimitSourceIsTheThemeToken(DetailBudgetTestCase):

    def test_token_declares_all_three_levels(self):
        theme = self.theme_name()
        self.token_limits(theme)

    def test_token_values_match_the_canonical_values(self):
        """値の正本は C11 のテーマトークンスキーマ (ブリーフの確定値と一致すること)。"""
        theme = self.theme_name()
        self.assertEqual(self.brief_limits(), self.token_limits(theme))

    def test_levels_are_strictly_increasing(self):
        """NAR-09 が宣言↔実態を判別できるだけの帯が開いていること。"""
        limits = self.token_limits(self.theme_name())
        self.assertLess(limits["overview"], limits["standard"])
        self.assertLess(limits["standard"], limits["detailed"])

    def test_script_has_no_numeric_literal_of_level_limits(self):
        """水準別の上限を script 側へ書かない。

        standard は R21 C52 の既定値 (text_limits キー欠落時のフォールバック) と
        一致するため、この script が持ちうるのは standard 相当の 1 値だけ。
        overview / detailed の値がソースに現れたら二重正本。
        """
        src = self.script_source()
        limits = self.token_limits(self.theme_name())
        for level in ("overview", "detailed"):
            with self.subTest(level=level):
                self.assertIsNone(
                    re.search(r"(?<![\w.])%d(?![\w.])" % limits[level], src),
                    "水準別の上限 %s (%d) が script へ数値リテラルとして埋め込まれている"
                    % (level, limits[level]),
                )


class FoldThresholdFollowsDetailLevel(DetailBudgetTestCase):

    def test_same_body_folds_at_overview_but_not_at_detailed(self):
        """上限を跨ぐ 1 本の本文が、水準によって畳まれたり畳まれなかったりする。"""
        theme = self.theme_name()
        limits = self.token_limits(theme)
        length = (limits["overview"] + limits["standard"]) // 2
        body = long_body(length)

        overview = self.normalized_parts(body, "overview", theme, "budget-ov.json")
        self.assertEqual(
            2,
            len(overview["sections"][0]["parts"]),
            "overview では上限を超えるので B10 へ畳まれるはず",
        )
        self.assertEqual(1, overview["provenance"]["text_fold_count"])

        detailed = self.normalized_parts(body, "detailed", theme, "budget-dt.json")
        self.assertEqual(
            1,
            len(detailed["sections"][0]["parts"]),
            "detailed では上限内なので畳まれないはず",
        )
        self.assertEqual(0, detailed["provenance"]["text_fold_count"])

    def test_head_length_is_within_the_level_limit(self):
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(limits["detailed"] * 2)
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                data = self.normalized_parts(body, level, theme, "head-%s.json" % level)
                head = data["sections"][0]["parts"][0]["data"]["body"]
                self.assertLessEqual(len(head), limits[level])

    def test_overflow_diagnostic_follows_the_level(self):
        """--normalize なしの検証も水準別の上限で判定する。"""
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body((limits["overview"] + limits["standard"]) // 2)

        cfg = text_config(body, "overview")
        cfg["theme"] = theme
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-TEXT-OVERFLOW", "/sections/0/parts/0")

        cfg = text_config(body, "detailed")
        cfg["theme"] = theme
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-TEXT-OVERFLOW")

    def test_no_content_is_lost_at_any_level(self):
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(limits["detailed"] * 2)
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                data = self.normalized_parts(body, level, theme, "lossless-%s.json" % level)
                joined = "".join(
                    [data["sections"][0]["parts"][0]["data"]["body"]]
                    + [
                        item["body"]
                        for part in data["sections"][0]["parts"][1:]
                        for item in part["data"]["items"]
                    ]
                )
                self.assertEqual(body, joined)


class FoldBehaviourAtDetailed(DetailBudgetTestCase):
    """折り畳みは全水準で行い、detailed が生成する B10 だけ open=true。"""

    def _generated_items(self, level):
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(limits["detailed"] * 2)
        data = self.normalized_parts(body, level, theme, "open-%s.json" % level)
        parts = data["sections"][0]["parts"]
        self.assertGreater(len(parts), 1, "どの水準でも折り畳み自体は行う")
        return [item for part in parts[1:] for item in part["data"]["items"]]

    def test_detailed_generates_open_accordion(self):
        items = self._generated_items("detailed")
        for item in items:
            self.assertIs(True, item["open"], "detailed の B10 は open=true")

    def test_overview_generates_closed_accordion(self):
        for item in self._generated_items("overview"):
            self.assertIs(False, item["open"])

    def test_standard_generates_closed_accordion(self):
        for item in self._generated_items("standard"):
            self.assertIs(False, item["open"])

    def test_structure_is_identical_across_levels(self):
        """open 属性以外は水準で変わらない (構造の同一性を保つ理由)。"""
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(limits["detailed"] * 2)
        shapes = {}
        for level in DETAIL_LEVELS:
            data = self.normalized_parts(body, level, theme, "shape-%s.json" % level)
            shapes[level] = [
                (part["part"], part["id"]) for part in data["sections"][0]["parts"]
            ]
        self.assertEqual(shapes["overview"], shapes["standard"])
        self.assertEqual(shapes["overview"], shapes["detailed"])


class FailSoftWhenKeyAbsent(DetailBudgetTestCase):
    """キーを持たないテーマでは block_body_max_chars を全水準へ適用する。"""

    def test_all_levels_use_block_body_max_chars(self):
        theme = self.theme_name()
        limits = self.token_limits(theme)
        fallback = limits["overview"]

        def mutate(tokens):
            text_limits = tokens.setdefault("text_limits", {})
            text_limits.pop(BY_DETAIL_KEY, None)
            text_limits["block_body_max_chars"] = fallback

        self.write_tokens(theme, mutate)
        body = long_body(fallback * 2)
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                data = self.normalized_parts(body, level, theme, "soft-%s.json" % level)
                head = data["sections"][0]["parts"][0]["data"]["body"]
                self.assertLessEqual(len(head), fallback)

    def test_existing_themes_are_not_broken(self):
        """水準別キーが無くても exit 0 で通る (既存テーマを壊さない)。"""
        theme = self.theme_name()
        limits = self.token_limits(theme)

        def mutate(tokens):
            tokens.setdefault("text_limits", {}).pop(BY_DETAIL_KEY, None)

        self.write_tokens(theme, mutate)
        cfg = text_config(long_body(limits["overview"] // 2), "detailed")
        cfg["theme"] = theme
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


if __name__ == "__main__":
    unittest.main()
