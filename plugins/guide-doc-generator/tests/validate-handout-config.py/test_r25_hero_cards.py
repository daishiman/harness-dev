# -*- coding: utf-8 -*-
"""冒頭カードの受入テスト (P05-x-40 / 利用者要求 R3・R9)。

ここで固定するのは 3 点。

1. **1 文長ゲートが冒頭にも当たる**: 走査対象は長らく sections[].parts[] の
   TEXT 部品だけで、読み手が最初に見る hero は 1 文字も検査されていなかった
   (F-P05X35SENT-SCOPE-01)。閾値も判定も新設せず、対象集合だけを広げている
   ことを陽性・陰性で確かめる。
2. **文数の上限が冒頭にも要る**: 1 文ずつ短くても、宣言のあとに説明を足せば
   冒頭は段落になる。上限は正本 (opening.hero_fields.max_sentences) が持つ。
3. **正本で緩められない**: level を下げても冒頭のゲートは error のまま。
   利用者要求 R7/R9 は「絶対に防ぐ」側であり、設定で緩む方が事故になる。
"""

import json
import unittest

from test_opening import OpeningTestBase, VISUAL_POLICY_RELPATH


def sentence_of(chars):
    """句点込みで chars 文字ちょうどの 1 文を作る。"""
    return "あ" * (chars - 1) + "。"


class HeroSentenceLength(OpeningTestBase):
    """W-SENTENCE-LONG の走査対象に冒頭が入っていること。"""

    def canon_max_chars(self):
        return self.visual_policy()["sentence"]["sentence_gate"]["max_chars"]

    def test_a_long_sentence_in_the_goal_stops_the_build(self):
        limit = self.canon_max_chars()
        # 字数上限 (goal 50 字) より 1 文長上限の方が緩いので、字数側を先に
        # 広げてから 1 文長だけを超えさせる (どちらが発火したかを分ける)。
        self.patch_opening(hero_fields={"max_chars": {"goal": 400}})
        res, _ = self.validate(self.visual_ok_config(goal=sentence_of(limit + 1)))
        self.assert_fails_with(res, "W-SENTENCE-LONG", "/goal")

    def test_exactly_at_the_limit_passes(self):
        limit = self.canon_max_chars()
        self.patch_opening(hero_fields={"max_chars": {"goal": 400}})
        res, _ = self.validate(self.visual_ok_config(goal=sentence_of(limit)))
        self.assert_no_diag(res, "W-SENTENCE-LONG")

    def test_the_limit_is_the_same_one_the_body_uses(self):
        """冒頭用に別の閾値を新設していないことの対照。

        本文側の上限を動かすと冒頭の判定も動く。動かなければ、同じ名前の
        つまみが 2 つある (どちらを回せばよいか分からない) 状態になっている。
        """
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        policy["sentence"]["sentence_gate"]["max_chars"] = 400
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        self.patch_opening(hero_fields={"max_chars": {"goal": 400}})
        res, _ = self.validate(self.visual_ok_config(goal=sentence_of(120)))
        self.assert_no_diag(res, "W-SENTENCE-LONG")


class HeroSentenceCount(OpeningTestBase):
    """E-HERO-PARAGRAPH。宣言のあとに説明を足させない。"""

    def canon_max_sentences(self, field):
        return (self.visual_policy()["opening"]["hero_fields"]
                ["max_sentences"]["value"][field])

    def test_one_sentence_goal_passes(self):
        res, _ = self.validate(self.visual_ok_config(goal="読み終えたら試せる。"))
        self.assert_no_diag(res, "E-HERO-PARAGRAPH")

    def test_two_sentence_goal_stops_the_build(self):
        self.assertEqual(1, self.canon_max_sentences("goal"))
        res, _ = self.validate(
            self.visual_ok_config(goal="読み終えたら試せる。手順も分かる。"))
        self.assert_fails_with(res, "E-HERO-PARAGRAPH", "/goal")

    SENTENCES = ["触れる人がいない。", "導入は決まった。", "期日も近い。",
                 "今の担当は 1 人。", "引き継ぎ先も未定。"]

    def background_of(self, sentences):
        """指定した文数の背景。正本の値を跨いだ検査を文数で書けるようにする。"""
        self.assertLessEqual(sentences, len(self.SENTENCES))
        return "".join(self.SENTENCES[:sentences])

    def test_background_may_carry_the_reason(self):
        """背景だけは『こうだから』の説明を足せる (正本が複数文を許している)。

        許す文数の値そのものは正本 (opening.hero_fields.max_sentences) が持つ。
        2026-08-19 に 2→3 文へ広げた (利用者指定: 冒頭の情報量を増やす)。
        ここは値を写さず、正本ちょうどの文数が通ることだけを固定する。
        """
        allowed = self.canon_max_sentences("background")
        self.assertGreater(allowed, 1, "背景が 1 文だけなら理由を書く余地が無い")
        res, _ = self.validate(
            self.visual_ok_config(background=self.background_of(allowed)))
        self.assert_no_diag(res, "E-HERO-PARAGRAPH")

    def test_background_over_the_canon_stops_the_build(self):
        allowed = self.canon_max_sentences("background")
        res, _ = self.validate(self.visual_ok_config(
            background=self.background_of(allowed + 1)))
        self.assert_fails_with(res, "E-HERO-PARAGRAPH", "/background")

    def test_the_limit_comes_from_the_canon(self):
        self.patch_opening(hero_fields={"max_sentences": {"value": {"goal": 3}}})
        res, _ = self.validate(
            self.visual_ok_config(goal="読み終えたら試せる。手順も分かる。"))
        self.assert_no_diag(res, "E-HERO-PARAGRAPH")

    def test_demoting_the_level_does_not_re_open_the_gate(self):
        self.patch_opening(hero_fields={
            "max_chars": {"goal": 400},
            "max_sentences": {"value": {"goal": 1}, "level": "warning"}})
        res, _ = self.validate(
            self.visual_ok_config(goal="読み終えたら試せる。手順も分かる。"))
        self.assert_fails_with(res, "E-HERO-PARAGRAPH", "/goal")


class OverflowGuidanceNamesTheEscape(OpeningTestBase):
    """溢れたときの逃がし先を診断が名指しすること。

    「上限を超えた」だけでは書き手は削るか折り畳むかしかできない。折り畳みは
    長さを消さず読み手から隠すだけなので、逃がし先 (箇条書き / セクション) を
    診断そのものが持つ。文言の正本は config 側の escape。
    """

    def test_diagnostic_carries_the_escape_from_the_canon(self):
        escape = self.visual_policy()["opening"]["hero_fields"]["escape"]
        res, _ = self.validate(self.visual_ok_config(
            goal="読み終えたら試せる。手順も分かる。"))
        self.assertIn(escape, res.stderr)


if __name__ == "__main__":
    unittest.main()
