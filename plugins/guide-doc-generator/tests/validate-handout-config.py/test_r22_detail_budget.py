# -*- coding: utf-8 -*-
"""R22 C63 (適用側) — CR-DETAIL-TEXT-BUDGET。

RESOLUTION-R22.md の責務表で C63 は「C11 (数値の正本) / C12 (適用)」であり、
本ファイルは適用側だけを固定する (数値の正本とレンダリングの検査は
tests/render-handout.py/test_r22_detail_attributes.py)。

規則 (script-brief-C12.json r22_granularity_constraints.detail_text_budget):
- CR-TEXT-FOLD の上限を detail_level ごとにテーマトークン
  text_limits.block_body_max_chars_by_detail_level から引く。
- この script は上限の数値リテラルを 1 つも持たない。
- 該当キーが無いテーマでは block_body_max_chars を全水準へ適用する (fail-soft)。
- R25/REQ-7 (goal-spec C73 / script-brief-C12.json:120,:869) により、折り畳みの
  実行回数上限は第1稿を含む全経路で 0 になった。どの水準でも超過は畳まず
  E-TEXT-OVERFLOW (level=error) で exit 1。旧仕様 (全水準で畳み detailed だけ
  open=true にする) は撤回済みで、script-brief-C11.json の
  added_block_r22_values.why_no_longer_open_true がその撤回を記録している。
  超過を実際に止めるのは E-TEXT-OVERFLOW (水準別上限で判定・level=error) で
  あり、E-TEXT-FOLDED は「折り畳みへ退避した回数 > 0」を禁じる二重化として
  残るだけで到達しない (validate-handout-config.py の fold_section 直前の
  注記が正本)。


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
    return H.with_visual_floor(cfg)


class DetailBudgetTestCase(H.C12TestCase):
    """テーマトークンを水準別上限つきで用意する足場。"""

    def relax_sentence_gates(self):
        """文の長さ・本数の上限だけを外す (字数予算を測るための足場)。

        字数予算と文の作り方は別の軸で、config/handout-visual-policy.json#sentence
        が後者の正本である。字数予算を上げた検査に固定長の文を並べると、上げた
        のは字数なのに文数・文長で落ちてしまい、何を測っているのか分からなくなる。
        ここでは前者だけを見たいので後者を無効化する (後者そのものは
        test_sentence_gate 系が固定する)。
        """
        path = self.root / "config/handout-visual-policy.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        sentence = policy.setdefault("sentence", {})
        sentence.setdefault("sentence_gate", {})["max_chars"] = 10000
        per_body = sentence.setdefault("sentences_per_body", {})
        per_body["max_sentences"] = 10000
        per_body.pop("max_sentences_by_detail_level", None)
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def normalize_result(self, body, detail_level, theme, name):
        """exit code を前提にしない正規化実行 (fail-closed 側の検査用)。"""
        cfg = text_config(body, detail_level)
        cfg["theme"] = theme
        out = self.tmp / name
        res, _, out = self.normalize(cfg, out=out)
        return res, out


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
    """R25/REQ-7: 超過は水準ごとの上限で判定し、どの水準でも畳まずに落とす。"""

    def test_same_body_is_rejected_at_overview_but_accepted_at_detailed(self):
        """上限を跨ぐ 1 本の本文が、水準によって落ちたり通ったりする。"""
        self.relax_sentence_gates()
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body((limits["overview"] + limits["standard"]) // 2)

        res, out = self.normalize_result(body, "overview", theme, "budget-ov.json")
        self.assert_fails_with(res, "E-TEXT-OVERFLOW", "/sections/0/parts/0")
        self.assertFalse(out.exists(), "超過したのに正規化済み構成が書き出されている: %s" % out)

        data = self.normalized_parts(body, "detailed", theme, "budget-dt.json")
        # 視覚部品の下限を満たすために足した DIAGRAM/IMG は数えない (見るのは
        # 本文が分割されていないこと)。
        parts = [p for p in data["sections"][0]["parts"] if p["part"] == "TEXT"]
        self.assertEqual(1, len(parts), "detailed では上限内なので部品は増えないはず")
        self.assertEqual(body, parts[0]["data"]["body"])

    def test_over_limit_is_rejected_at_every_level(self):
        """どの水準にも「畳んで通す」逃げ道が無い。"""
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(limits["detailed"] * 2)
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                res, out = self.normalize_result(body, level, theme, "over-%s.json" % level)
                self.assert_fails_with(res, "E-TEXT-OVERFLOW")
                self.assertFalse(out.exists(), "%s で書き出されている: %s" % (level, out))

    def test_within_limit_body_is_preserved_at_every_level(self):
        """上限内なら水準を問わず原文のまま (分割も切り詰めもしない)。"""
        self.relax_sentence_gates()
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(max(1, limits["overview"] // 2))
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                data = self.normalized_parts(body, level, theme, "keep-%s.json" % level)
                parts = [p for p in data["sections"][0]["parts"] if p["part"] == "TEXT"]
                self.assertEqual(1, len(parts), "本文が分割されている: %r" % [p["id"] for p in parts])
                self.assertEqual(body, parts[0]["data"]["body"])

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


class NoAccordionIsGenerated(DetailBudgetTestCase):
    """B10 への退避そのものが起きない (旧 FoldBehaviourAtDetailed の撤回)。

    旧クラスは「折り畳みは全水準で行い detailed の B10 だけ open=true」を期待値に
    していた。script-brief-C11.json の added_block_r22_values.why_no_longer_open_true
    が『R25 は折り畳みそのものを長文の逃げ道として塞ぐため、この妥協は不要に
    なった』と撤回を記録している。
    """

    def test_no_generated_part_at_any_level(self):
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(limits["detailed"] * 2)
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                res, out = self.normalize_result(body, level, theme, "gen-%s.json" % level)
                self.assert_exit(res, 1)
                if out.exists():
                    parts = json.loads(out.read_text(encoding="utf-8"))["sections"][0]["parts"]
                    self.assertEqual(
                        ["TEXT"], [p["part"] for p in parts],
                        "折り畳み先が生成されている: %r" % [p["id"] for p in parts],
                    )

    def test_fold_count_is_zero_at_every_level(self):
        """provenance.text_fold_count が非 0 になる経路は残っていない。"""
        theme = self.theme_name()
        limits = self.token_limits(theme)
        body = long_body(max(1, limits["overview"] // 2))
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                data = self.normalized_parts(body, level, theme, "count-%s.json" % level)
                self.assertEqual(0, data["provenance"]["text_fold_count"])


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
                res, _ = self.normalize_result(body, level, theme, "soft-%s.json" % level)
                self.assert_fails_with(res, "E-TEXT-OVERFLOW")

    def test_existing_themes_are_not_broken(self):
        """水準別キーが無くても上限内なら exit 0 で通る (既存テーマを壊さない)。"""
        theme = self.theme_name()
        limits = self.token_limits(theme)

        def mutate(tokens):
            tokens.setdefault("text_limits", {}).pop(BY_DETAIL_KEY, None)

        self.write_tokens(theme, mutate)
        cfg = text_config(long_body(max(1, limits["overview"] // 2)), "detailed")
        cfg["theme"] = theme
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


if __name__ == "__main__":
    unittest.main()
